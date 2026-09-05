"""Reading a declared mobility survey: its trips, its modes, and its kind of day.

This is the half of the exposure measurement that knows about surveys, and it
stops exactly where geometry begins. What comes out is one row per actor type,
day type and origin-destination pair, carrying a number of trips per day. What
that becomes on the map is `exposure`'s problem.

The split is deliberate. Four surveys have to pass through here and they agree on
almost nothing: 2023 is cp1252 where 2015 and 2019 are utf-8, its numbers are
text with a comma decimal separator and a trailing space, three of its column
names are wrapped in spaces, its modes are labels where 2015's are numeric codes,
and each year says which kind of day a trip was made on in a different way. All
of that is declared in `config.MobilitySurvey` and resolved here, once. Nothing
downstream of this module can tell which year it is looking at, which is the
property that makes the next three years a declaration each.

**What the expansion factor expands, and why two numbers come out of one.** A
household is surveyed once, on one date, and its weight says how many households
it stands for. Those weights are calibrated so that the whole sample — every
reference day together — represents the universe once, not so that each day's
subsample represents it. Summing the trip factor over the households whose
reference day was a weekday therefore gives the weekday contribution to an
average day of the collection period, and not the trips of one weekday. The share
of the universe those households cover is what converts between the two, and both
quantities leave this module because neither answers the other's question. See
D38.

Run it through the exposure route:

    python -m src.run_pipeline exposure
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd

try:  # regular package import
    from src import config
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# Working columns, private to this module and to the geometry that consumes it.
# Named apart from the configured ones so it is obvious at a glance that none of
# them reaches an exported table.
ZONE_ORIGIN_COL = "_ZONE_ORIGIN"
ZONE_DESTINATION_COL = "_ZONE_DESTINATION"
TRIPS_COL = "_TRIPS_PER_AVERAGE_DAY"
ZONE_CODE_COL = "_ZONE"


@dataclass(frozen=True)
class SurveyTrips:
    """One survey, read and reduced to what the geometry needs.

    The counts travel with the table rather than being recomputed from it later,
    because the point of the balance check is to compare what was apportioned
    against what came out of the file, and a total derived from the apportionment
    would agree with it by construction.
    """

    survey: config.MobilitySurvey
    # One row per actor type, day type and origin-destination pair.
    pairs: pd.DataFrame
    # Share of the surveyed universe covered by each day type's households.
    universe_shares: pd.Series
    records_read: int
    records_measured: int
    records_without_weight: int
    file_total: float
    # Trips per day per actor type and day type, straight from the file, before
    # any zone or unit has been looked at.
    totals: pd.Series
    # Trips per day of the modes deliberately left outside the study, by the label
    # the file gives them, and of the records that carry no origin or destination
    # zone. Both are here so the run can check that the four measured modes plus
    # everything set aside add up to the file, which is a different grouping of the
    # same column and therefore an actual check rather than a restatement.
    not_measured_totals: pd.Series
    unzoned_total: float


# ---------------------------------------------------------------------------
# Reading a delimited table
# ---------------------------------------------------------------------------


def read_table(table: config.DelimitedTable, log: RunLog) -> pd.DataFrame:
    """Read one delivered text table as declared, as text, and stripped.

    Everything is read as text and converted afterwards. Letting pandas infer the
    types is what buried the 2023 expansion factor: `fexp_vj` arrives as `6,2 `,
    with a comma decimal separator and a trailing space, so it infers an object
    column, sums to zero and does not complain. Reading as text makes the
    conversion an explicit step that can fail loudly.
    """
    path = config.resolve_source_path(table.path)
    frame = pd.read_csv(path, sep=table.separator, encoding=table.encoding, dtype=str)

    if table.strip_whitespace:
        # The names as well as the values: 2023 ships ` hora_ini ` and
        # ` duracion_min ` with the spaces inside the header.
        frame.columns = [str(name).strip() for name in frame.columns]
        for column in frame.columns:
            if frame[column].dtype == object:
                frame[column] = frame[column].str.strip()

    log.info("read %d row(s) and %d column(s) from %s", len(frame), len(frame.columns), path.name)
    return frame


def require_columns(frame: pd.DataFrame, columns: tuple[str, ...], where: str) -> None:
    """Stop unless every declared column is there, naming all that are not.

    Reported together rather than one at a time, because a delivery that renamed
    one column usually renamed several and finding them one run at a time is the
    slowest way to learn that.
    """
    absent = [column for column in columns if column not in frame.columns]
    if absent:
        raise ValueError(
            f"{where}: the delivered file does not carry {', '.join(absent)}. "
            f"It carries {len(frame.columns)} columns; the declaration names them as the "
            "delivered file spells them, and a renamed column is a decision, not a default"
        )


def to_number(values: pd.Series, decimal: str) -> pd.Series:
    """A declared text column as floats, with the delivery's decimal separator.

    Nulls are preserved rather than filled. A record with no expansion factor is
    a record the survey could not weight, and turning that into a zero would
    silently move it out of the totals the run is checked against.
    """
    text = values.astype("string")
    if decimal != ".":
        text = text.str.replace(decimal, ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


# ---------------------------------------------------------------------------
# The kind of day
# ---------------------------------------------------------------------------


def _day_type_from_household_date(
    rule: config.DayTypeFromHouseholdDate,
    trips: pd.DataFrame,
    survey: config.MobilitySurvey,
    log: RunLog,
) -> tuple[pd.Series, pd.Series]:
    """Day type per trip, and the share of the universe each day type covers.

    Both come from the household table because both are properties of the
    household: the date it was interviewed and the weight it carries. Reading it
    once for the two is deliberate — a second read is a second chance to derive a
    different day type for the same household.

    The interview date is shifted back by the declared number of days. 2023 asks
    about the day before the interview, so a household interviewed on a Sunday
    reports a Saturday, and taking the interview date itself would file every one
    of those trips under the wrong kind of day.
    """
    households = read_table(rule.households, log)
    require_columns(
        households,
        (rule.join_column, rule.date_column, rule.weight_column),
        f"{survey.label} households",
    )

    interviewed = pd.to_datetime(
        households[rule.date_column], dayfirst=rule.day_first, errors="coerce"
    )
    unreadable = int(interviewed.isna().sum())
    if unreadable:
        raise ValueError(
            f"{survey.label}: {unreadable} household interview date(s) in "
            f"{rule.date_column} could not be read. The day type of every trip of those "
            "households would be unknown, and an unknown day type is not a day type"
        )

    reported = interviewed - pd.Timedelta(days=rule.days_before)
    weekday_number = reported.dt.dayofweek
    households[config.DAY_TYPE_COL] = np.select(
        [
            weekday_number == config.SATURDAY_WEEKDAY_NUMBER,
            weekday_number == config.SUNDAY_WEEKDAY_NUMBER,
        ],
        [config.SATURDAY_TYPE, config.SUNDAY_TYPE],
        default=config.WEEKDAY_TYPE,
    )
    households["_WEIGHT"] = to_number(households[rule.weight_column], rule.households.decimal)

    duplicated = int(households[rule.join_column].duplicated().sum())
    if duplicated:
        raise ValueError(
            f"{survey.label}: {duplicated} household key(s) appear more than once in "
            f"{rule.households.path.name}; joining the trips onto them would fan out and "
            "count those trips twice"
        )

    lookup = households.set_index(rule.join_column)[config.DAY_TYPE_COL]
    assigned = trips[rule.join_column].map(lookup)
    orphaned = int(assigned.isna().sum())
    if orphaned:
        raise ValueError(
            f"{survey.label}: {orphaned} trip(s) belong to a household that is not in "
            f"{rule.households.path.name}, so the day they were made on cannot be resolved"
        )

    # The share of the universe each day type's households cover. This is the
    # only quantity that says the three day types are not three measurements of
    # the same thing: the weights represent the universe once over the whole
    # sample, so each day type covers a fraction of it.
    weight_by_type = households.groupby(config.DAY_TYPE_COL)["_WEIGHT"].sum()
    shares = weight_by_type / weight_by_type.sum()

    log.info(
        "%s: reference day is %d day(s) before the interview; households by day type: %s",
        survey.label,
        rule.days_before,
        ", ".join(
            f"{day_type} {int((households[config.DAY_TYPE_COL] == day_type).sum()):,} "
            f"({shares.get(day_type, 0.0):.1%} of the universe)"
            for day_type in config.DAY_TYPES
            if day_type in set(households[config.DAY_TYPE_COL])
        ),
    )
    return assigned, shares


# Which handler resolves which declared rule. A registry rather than a chain of
# isinstance checks, so that the year whose day type arrives as a flag on the
# record or as a separate database adds an entry here and a declaration in the
# configuration, and touches nothing else in this module.
_DAY_TYPE_HANDLERS = {
    config.DayTypeFromHouseholdDate: _day_type_from_household_date,
}


def assign_day_type(
    trips: pd.DataFrame,
    survey: config.MobilitySurvey,
    log: RunLog,
) -> tuple[pd.Series, pd.Series]:
    """Resolve the declared day-type rule, or say plainly that it is not written yet."""
    rule = survey.day_type_rule
    handler = _DAY_TYPE_HANDLERS.get(type(rule))
    if handler is None:
        raise NotImplementedError(
            f"{survey.label} declares its day type as {type(rule).__name__}, which no handler "
            f"in surveys._DAY_TYPE_HANDLERS resolves. Every year says which kind of day a trip "
            "was made on differently, so the rule is declared and dispatched; add the handler "
            "beside the others rather than reading the file a second way"
        )
    return handler(rule, trips, survey, log)


# ---------------------------------------------------------------------------
# The modes
# ---------------------------------------------------------------------------


def map_modes(trips: pd.DataFrame, survey: config.MobilitySurvey, log: RunLog) -> pd.Series:
    """Turn the survey's own mode labels into the study's four actor types.

    Exhaustive and explicit, which is D4's rule applied to a source whose
    vocabulary changes every year. Every label the file holds must be either
    mapped to an actor type or declared as deliberately not measured; anything in
    neither stops the run. The failure this prevents is the quiet one — an
    unmapped label becomes a null, the null disappears in a groupby, and the mode
    it belonged to is simply smaller than it should be with nothing to show for it.

    Note that unlike the vehicle types of the casualty source there is no OTHER to
    fall back to. The study measures four modes and the rest of the survey is out
    of scope, so an unrecognised label is a question for a person and not a
    category.
    """
    labels = trips[survey.mode_column]
    present = set(labels.dropna().unique())
    undeclared = sorted(present - set(survey.modes_declared))
    if undeclared:
        raise ValueError(
            f"{survey.label}: {survey.mode_column} holds {len(undeclared)} value(s) the "
            f"declaration accounts for in neither mode_map nor modes_not_measured: "
            f"{', '.join(repr(value) for value in undeclared)}. Every label is either one of "
            "the four actor types or deliberately outside them, and which of the two is a "
            "decision rather than a default"
        )

    declared_absent = sorted(set(survey.modes_declared) - present)
    if declared_absent:
        log.warn(
            "%s: %d declared mode label(s) do not occur in the file: %s. The declaration is "
            "wider than the delivery, which is harmless but means one of the two is stale",
            survey.label,
            len(declared_absent),
            ", ".join(declared_absent),
        )

    if labels.isna().any():
        raise ValueError(
            f"{survey.label}: {int(labels.isna().sum())} record(s) have no value in "
            f"{survey.mode_column}, so the mode they were made by is unknown"
        )

    return labels.map(survey.mode_map)


# ---------------------------------------------------------------------------
# Reading a survey
# ---------------------------------------------------------------------------


def read(survey: config.MobilitySurvey, log: RunLog) -> SurveyTrips:
    """One declared survey, as trips per day between pairs of zones.

    The reduction to origin-destination pairs happens here rather than in the
    geometry, and it is what makes the geometry affordable: the share of a line
    that falls in a unit depends on the pair of zones and on nothing else, so
    24,354 lines are built and split once and then multiplied by the trips of
    every actor type and day type that used them. Building one line per surveyed
    record instead would draw the same line dozens of times and split it dozens
    of times, for the same answer.
    """
    frame = read_table(survey.trips, log)
    require_columns(
        frame,
        (
            survey.weight_column,
            survey.origin_zone_column,
            survey.destination_zone_column,
            survey.mode_column,
        ),
        survey.label,
    )
    records_read = len(frame)

    weights = to_number(frame[survey.weight_column], survey.trips.decimal)
    without_weight = int(weights.isna().sum())
    negative = int((weights < 0).sum())
    if negative:
        raise ValueError(
            f"{survey.label}: {negative} record(s) carry a negative {survey.weight_column}; "
            "a count of trips is not negative"
        )
    if without_weight:
        # Not an error. The survey's own published total is the sum that excludes
        # them, so they are outside the universe the file describes rather than a
        # hole in it. Said loudly on every run because that is an assumption about
        # someone else's file and it should not go unnoticed.
        log.warn(
            "%s: %d of %d record(s) carry no %s and are dropped. The file's own total is the "
            "sum that excludes them, so this is what the survey counts and not a loss; "
            "imputing a weight for them would be inventing trips",
            survey.label,
            without_weight,
            records_read,
            survey.weight_column,
        )

    frame[TRIPS_COL] = weights
    frame[config.ACTOR_TYPE_COL] = map_modes(frame, survey, log)
    day_type, universe_shares = assign_day_type(frame, survey, log)
    frame[config.DAY_TYPE_COL] = day_type

    file_total = float(weights.sum())
    weighted = frame[frame[TRIPS_COL].notna()]
    not_measured_totals = (
        weighted[weighted[config.ACTOR_TYPE_COL].isna()]
        .groupby(survey.mode_column)[TRIPS_COL]
        .sum()
    )
    measured = weighted[weighted[config.ACTOR_TYPE_COL].notna()].copy()

    for source_column, target in (
        (survey.origin_zone_column, ZONE_ORIGIN_COL),
        (survey.destination_zone_column, ZONE_DESTINATION_COL),
    ):
        # Zone codes are compared as text on both sides of every join in this
        # module. The zoning stores them as a number and the trips as text, and
        # "810" and "810.0" are the same zone to a reader and two zones to a join
        # that would then match nothing at all.
        measured[target] = measured[source_column].astype("string")

    unzoned = measured[ZONE_ORIGIN_COL].isna() | measured[ZONE_DESTINATION_COL].isna()
    unzoned_total = float(measured.loc[unzoned, TRIPS_COL].sum())
    if unzoned.any():
        log.warn(
            "%s: %d record(s) of the measured modes carry no origin or destination zone, "
            "%s trips per day, and cannot be placed",
            survey.label,
            int(unzoned.sum()),
            f"{unzoned_total:,.1f}",
        )
        measured = measured[~unzoned]

    totals = measured.groupby([config.ACTOR_TYPE_COL, config.DAY_TYPE_COL])[TRIPS_COL].sum()

    pairs = (
        measured.groupby(
            [config.ACTOR_TYPE_COL, config.DAY_TYPE_COL, ZONE_ORIGIN_COL, ZONE_DESTINATION_COL],
            observed=True,
        )[TRIPS_COL]
        .sum()
        .reset_index()
    )

    log.record(
        f"read the {survey.year} mobility survey",
        rows_in=records_read,
        rows_out=len(pairs),
        changes=[
            (-without_weight, f"records with no {survey.weight_column}, outside the file's own total"),
            (
                -(records_read - without_weight - len(measured)),
                "records of a mode outside the four measured, or with no origin or destination zone",
            ),
            (
                len(pairs) - len(measured),
                "rows lost to grouping the records into actor type, day type and zone pair",
            ),
        ],
        notes=[
            f"source={survey.trips.path.name}, {survey.measures}",
            f"{file_total:,.1f} trips per day in the file; "
            f"{float(totals.sum()):,.1f} of them in the four measured modes",
            "modes: " + ", ".join(
                f"{actor} {float(totals.xs(actor, level=0).sum()):,.0f}"
                for actor in survey.actor_types
            ),
            "day types: " + ", ".join(
                f"{day_type} {universe_shares.get(day_type, float('nan')):.4f} of the universe"
                for day_type in config.DAY_TYPES
                if day_type in universe_shares.index
            ),
        ],
    )

    return SurveyTrips(
        survey=survey,
        pairs=pairs,
        universe_shares=universe_shares,
        records_read=records_read,
        records_measured=len(measured),
        records_without_weight=without_weight,
        file_total=file_total,
        totals=totals,
        not_measured_totals=not_measured_totals,
        unzoned_total=unzoned_total,
    )


# ---------------------------------------------------------------------------
# The zoning
# ---------------------------------------------------------------------------


def read_zoning(survey: config.MobilitySurvey, log: RunLog) -> gpd.GeoDataFrame:
    """The zones the survey's origins and destinations are keyed on.

    Reprojected to the study's metric CRS here, once, so that no caller has to
    remember which projection a year was delivered in. The 2023 zoning is
    EPSG:3116 where the 2015 and 2019 zonings and the study's own cartography are
    EPSG:4686, and a zone read as degrees and intersected with a unit read as
    metres produces an empty overlay and no error at all.
    """
    zoning = survey.zoning
    path = config.resolve_source_path(zoning.shapefile)
    zones = gpd.read_file(path)

    if zoning.code_column not in zones.columns:
        raise ValueError(
            f"{survey.label}: the zoning {path.name} does not carry {zoning.code_column}"
        )
    if zones.crs is None:
        if zoning.crs_if_undeclared is None:
            raise ValueError(
                f"{survey.label}: the zoning {path.name} declares no coordinate reference "
                "system and the configuration names none for it. Guessing one would place "
                "every zone somewhere plausible and wrong"
            )
        zones = zones.set_crs(epsg=zoning.crs_if_undeclared)

    zones = zones.to_crs(epsg=config.PROJECTED_CRS)
    # Matching the trips' text codes. The shapefile stores the code as a float,
    # so a straight cast would give "810.0" against the trips' "810".
    codes = pd.to_numeric(zones[zoning.code_column], errors="coerce")
    if codes.isna().any():
        raise ValueError(
            f"{survey.label}: {int(codes.isna().sum())} zone(s) of {path.name} have no "
            f"readable code in {zoning.code_column}"
        )
    zones[ZONE_CODE_COL] = codes.astype("int64").astype("string")

    duplicated = int(zones[ZONE_CODE_COL].duplicated().sum())
    if duplicated:
        raise ValueError(
            f"{survey.label}: {duplicated} zone code(s) of {path.name} appear more than once, "
            "so a trip keyed on one of them would be placed in two zones"
        )

    log.info(
        "%s: read %d zone(s) from %s, reprojected from %s to EPSG:%d",
        survey.label,
        len(zones),
        path.name,
        gpd.read_file(path, rows=1).crs,
        config.PROJECTED_CRS,
    )
    return zones[[ZONE_CODE_COL, "geometry"]]


def check_zone_coverage(
    trips: SurveyTrips,
    zones: gpd.GeoDataFrame,
    log: RunLog,
) -> None:
    """Every zone the trips name has to exist in the zoning, or the trip is nowhere.

    Checked before any geometry is built, because a zone code with no polygon
    produces a line with a missing endpoint, and a line with a missing endpoint
    is dropped by the overlay without a word.
    """
    known = set(zones[ZONE_CODE_COL])
    pairs = trips.pairs
    missing_origin = ~pairs[ZONE_ORIGIN_COL].isin(known)
    missing_destination = ~pairs[ZONE_DESTINATION_COL].isin(known)
    unknown = missing_origin | missing_destination
    if not unknown.any():
        log.info(
            "%s: every zone code the trips name is in the zoning (%d distinct origins, "
            "%d distinct destinations)",
            trips.survey.label,
            pairs[ZONE_ORIGIN_COL].nunique(),
            pairs[ZONE_DESTINATION_COL].nunique(),
        )
        return

    codes = sorted(
        set(pairs.loc[missing_origin, ZONE_ORIGIN_COL])
        | set(pairs.loc[missing_destination, ZONE_DESTINATION_COL])
    )
    raise ValueError(
        f"{trips.survey.label}: {len(codes)} zone code(s) named by the trips are not in "
        f"{trips.survey.zoning.shapefile.name}, carrying "
        f"{float(pairs.loc[unknown, TRIPS_COL].sum()):,.1f} trips per day: "
        f"{', '.join(codes[:20])}{' ...' if len(codes) > 20 else ''}. A trip whose zone has no "
        "polygon has no place, and dropping it silently is how a mode ends up smaller than it is"
    )
