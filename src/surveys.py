"""Reading a declared mobility survey: its trips, its modes, and its kind of day.

This is the half of the exposure measurement that knows about surveys, and it
stops exactly where geometry begins. What comes out is one row per actor type,
day type and origin-destination pair, carrying a number of trips per day. What
that becomes on the map is `exposure`'s problem.

The split is deliberate. Four surveys have to pass through here and they agree on
almost nothing: 2023 is cp1252 where 2015 and 2019 are utf-8, its numbers are
text with a comma decimal separator and a trailing space, three of its column
names are wrapped in spaces, its modes are labels where 2015's are numeric codes,
2011 arrives as two Access databases rather than as a file of text, and each year
says which kind of day a trip was made on in a different way. All of that is
declared in `config.MobilitySurvey` and resolved here, once. Nothing downstream of
this module can tell which year it is looking at, which is the property that makes
three of the four years a declaration each.

**Three registries and no second reader.** How a table is opened, how a year says
which kind of day a trip was made on, and how it states a duration are each a
declared rule dispatched through a registry here. That is what kept the fourth year
from bending the shape: 2011 needed a container nobody had seen and a day type that
is a property of the file rather than of the record, and both went in as an entry
beside the others. The one thing that is not allowed is a second way of reading a
file — a day-type rule that opened the Saturday database itself would have been the
smallest diff and the worst shape.

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
# The same expansion under the narrower pedestrian definition: a walking record
# shorter than the declared floor contributes zero here and its full weight to
# the column above, and every record of the other three modes contributes the
# same number to both. It travels beside the first from the moment the records
# are grouped into zone pairs, so the apportionment runs over both at once and
# the second column goes through the very same spatial operators as the first
# rather than being scaled out of it. See D39.
TRIPS_OVER_15MIN_COL = "_TRIPS_PER_AVERAGE_DAY_OVER_15MIN"
ZONE_CODE_COL = "_ZONE"
# Which declared source a row was read out of. Written by the reader because the
# reader is the only thing that knows it: once the sources are concatenated, a row
# no longer says which file it came from, and for 2011 that is the only thing that
# says which kind of day it is.
SOURCE_COL = "_SOURCE"


@dataclass(frozen=True)
class SurveyTrips:
    """One survey, read and reduced to what the geometry needs.

    The counts travel with the table rather than being recomputed from it later,
    because the point of the balance check is to compare what was apportioned
    against what came out of the file, and a total derived from the apportionment
    would agree with it by construction.
    """

    survey: config.MobilitySurvey
    # One row per actor type, day type and origin-destination pair, carrying the
    # trips of the pair under both pedestrian definitions.
    pairs: pd.DataFrame
    # The zones those pairs are keyed on, in the study's metric CRS. Read here
    # rather than by the caller because the reader needs them itself: an
    # origin-destination pair cannot be checked for plausibility without knowing
    # how far apart its two zones are.
    zones: gpd.GeoDataFrame
    # Share of the surveyed universe covered by each day type's households.
    universe_shares: pd.Series
    records_read: int
    records_measured: int
    records_without_weight: int
    file_total: float
    # Trips per day per actor type and day type, straight from the file, before
    # any zone or unit has been looked at.
    totals: pd.Series
    # The same, under the narrower pedestrian definition. It is what the balance
    # of the second column is checked against, and it is a separate measurement
    # of the file rather than a fraction of the first.
    totals_over_15min: pd.Series
    # What the two pedestrian definitions come to over the whole surveyed region,
    # per day type, before any record is set aside for its zone or its geometry.
    # Kept because it is the figure the four years are compared on and the one
    # the survey's own publications state: the removals are the study's and the
    # published splits are not made over them.
    pedestrian_definitions: pd.DataFrame
    # Trips per day of the modes deliberately left outside the study, by the label
    # the file gives them, and of the records that carry no origin or destination
    # zone. Both are here so the run can check that the four measured modes plus
    # everything set aside add up to the file, which is a different grouping of the
    # same column and therefore an actual check rather than a restatement.
    not_measured_totals: pd.Series
    unzoned_total: float
    # Trips per day dropped because the two zones are further apart than the mode
    # could have covered in the reported duration, by actor type. Kept so the
    # balance can name them and the report can say how much of each mode went.
    implausible_totals: pd.Series
    implausible_records: int


# ---------------------------------------------------------------------------
# Reading a delimited table
# ---------------------------------------------------------------------------


def _read_delimited_table(table: config.DelimitedTable, log: RunLog) -> pd.DataFrame:
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


def _read_access_table(table: config.AccessTable, log: RunLog) -> pd.DataFrame:
    """Read one table out of a delivered Access database, through the ODBC driver.

    2011 is the only year delivered this way. The connection needs the 64-bit
    Access driver matched to a 64-bit Python; a 32-bit driver cannot open these
    files from this environment at all, and `pyodbc` is imported here rather than
    at the top of the module so that the three years delivered as CSV do not
    require it to be installed.

    The rows are fetched through the cursor and assembled here rather than handed
    to `pandas.read_sql`, which warns on a raw `pyodbc` connection because it is
    not a SQLAlchemy connectable. The warning is noise, and a pipeline that prints
    warnings nobody reads is how a real one gets missed.

    Unlike the text reader this does not force everything to text: the driver
    returns numbers as numbers, and rewriting them as strings only to parse them
    back would be a round trip with nothing to gain and a decimal separator to get
    wrong. The text columns get the same stripping the other reader applies, so
    that a year is not measured differently for having been delivered in a
    different container.
    """
    import pyodbc  # noqa: PLC0415 — only 2011 needs it; see the docstring

    path = config.resolve_source_path(table.path)
    connection = pyodbc.connect(
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + str(path.resolve())
    )
    try:
        cursor = connection.cursor()
        cursor.execute(f"SELECT * FROM [{table.table}]")
        columns = [description[0] for description in cursor.description]
        rows = [tuple(row) for row in cursor.fetchall()]
    finally:
        connection.close()

    frame = pd.DataFrame.from_records(rows, columns=columns)
    if table.strip_whitespace:
        frame.columns = [str(name).strip() for name in frame.columns]
        for column in frame.columns:
            if frame[column].dtype == object:
                frame[column] = frame[column].str.strip()

    log.info(
        "read %d row(s) and %d column(s) from %s of %s",
        len(frame),
        len(frame.columns),
        table.table,
        path.name,
    )
    return frame


# Which reader opens which declared kind of table. A registry rather than a branch
# on the type, for the same reason the day type and the duration have one: a
# delivery arriving in a container nobody has seen yet adds a reader beside these
# two, and a declared table with no reader fails with a message naming itself.
_TABLE_READERS = {
    config.DelimitedTable: _read_delimited_table,
    config.AccessTable: _read_access_table,
}


def read_table(table: config.DelimitedTable | config.AccessTable, log: RunLog) -> pd.DataFrame:
    """One declared table, read by whichever reader its kind names."""
    reader = _TABLE_READERS.get(type(table))
    if reader is None:
        raise NotImplementedError(
            f"{type(table).__name__} is declared as a source of data but no reader in "
            f"surveys._TABLE_READERS opens it. Add one beside the others rather than reading "
            "the file a second way somewhere else"
        )
    return reader(table, log)


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

    A column that is already numeric is returned as it is. 2011 arrives out of a
    database rather than out of a text file, so its factor is a double before this
    sees it, and writing it out as text only to parse it back would be a round trip
    that can only lose.
    """
    if pd.api.types.is_numeric_dtype(values):
        return values.astype("float64")
    text = values.astype("string")
    if decimal != ".":
        text = text.str.replace(decimal, ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


def zone_code_text(values: pd.Series, where: str) -> pd.Series:
    """Zone codes as text, spelled the same way on both sides of every join.

    The zoning stores its code as a float and the trips store theirs as whatever
    their delivery used — text in the three CSV years, a double in 2011's database.
    "810", "810.0" and 810.0 are one zone to a reader and three different keys to a
    join, which would then match nothing at all and take the trips with it.

    So both sides go through here: a code that reads as a whole number comes out as
    that number's digits, and a code that reads as no number at all keeps its text,
    so that it still reaches the check that refuses codes the zoning does not have.
    A code with a fraction in it is neither, and stops the run: a zone numbered
    810.5 is not a rounding of anything.
    """
    numbers = pd.to_numeric(values, errors="coerce")
    fractional = numbers.notna() & (numbers != numbers.round())
    if fractional.any():
        raise ValueError(
            f"{where}: {int(fractional.sum())} zone code(s) are numbers with a fraction, such "
            f"as {numbers[fractional].iloc[0]}. A zone is identified by a whole number and "
            "rounding one to reach a polygon would put trips in a zone nobody named"
        )
    text = values.astype("string")
    whole = numbers.notna()
    text[whole] = numbers[whole].astype("int64").astype("string")
    return text


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
    #
    # Unless the survey declares that its factor already expands to one day of the
    # record's own kind, in which case there is nothing to convert and every share
    # is one. That branch is what stops the next year from being forced through
    # 2023's answer to a question each year answers for itself.
    weight_by_type = households.groupby(config.DAY_TYPE_COL)["_WEIGHT"].sum()
    if survey.weight_expands_to == config.WEIGHT_EXPANDS_TO_DAY_OF_TYPE:
        shares = pd.Series(1.0, index=weight_by_type.index)
    else:
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


def _day_type_from_record_flags(
    rule: config.DayTypeFromRecordFlags,
    trips: pd.DataFrame,
    survey: config.MobilitySurvey,
    log: RunLog,
) -> tuple[pd.Series, pd.Series]:
    """Day type per trip from flags the delivery already wrote on the record.

    2015 ships `DIA_HABIL` and `DIA_NOHABIL`, one set and never both. The flags
    are read rather than derived because they are what the consultant grouped by
    when they published the origin-destination matrices this pipeline rebuilds,
    and because that year's interview date is unreadable on one household whose
    row is displaced by a column — a rule reading the date would stop the run over
    one corrupted record while the flag on its eight trips is perfectly good.

    What a flag names is not taken from what it is called. `DIA_NOHABIL` could be
    a Saturday, a Sunday or both, and the declaration says which, with the year's
    own statement quoted beside it.

    Every record must carry exactly one flag. A record with none has no day, and a
    record with two would be counted under both — either is a misreading of the
    delivery rather than a case to resolve with a default.
    """
    for day_type in rule.flags.values():
        if day_type not in config.DAY_TYPES:
            raise ValueError(
                f"{survey.label} maps one of its day-type flags to {day_type!r}, which is not "
                f"one of {', '.join(config.DAY_TYPES)}. The exposure table joins on this value "
                "and the casualty side has to be able to name the same one"
            )
    require_columns(trips, tuple(rule.flags), f"{survey.label} day types")

    # A flag is "set" when it holds anything at all: these columns carry a 1 on
    # the records they apply to and nothing on the rest, and reading them as
    # presence rather than as the value 1 is what keeps a delivery that writes
    # "SI" or "TRUE" from silently landing every record in no day type.
    set_flags = pd.DataFrame(
        {column: trips[column].notna() for column in rule.flags}, index=trips.index
    )
    how_many = set_flags.sum(axis=1)
    if (how_many != 1).any():
        none_set, several = int((how_many == 0).sum()), int((how_many > 1).sum())
        raise ValueError(
            f"{survey.label}: {none_set} record(s) carry none of "
            f"{', '.join(rule.flags)} and {several} carry more than one. The flags have to "
            "partition the file: a record with no flag has no day type, and one with two would "
            "be counted under both"
        )

    # Assigned column by column rather than through a single select, because the
    # check above has already established that exactly one flag is set on every
    # record: there is no default case left for a select to need, and giving it
    # one would be writing a fallback for a state that cannot occur.
    assigned = pd.Series(index=trips.index, dtype="object")
    for column, day_type in rule.flags.items():
        assigned[set_flags[column]] = day_type

    # Each day type's subsample expands to a whole day of its own kind, so there
    # is nothing to convert and every share is one. A year whose factor spreads
    # the universe across its reference days needs the household weights to say
    # what fraction each day covers, and a flag on the trip cannot supply them —
    # so this rule serves that year not at all, and says so rather than inventing
    # a share of one that would quietly rescale nothing.
    if survey.weight_expands_to != config.WEIGHT_EXPANDS_TO_DAY_OF_TYPE:
        raise ValueError(
            f"{survey.label} takes its day type from a flag on the trip record but declares "
            f"that its factor expands to {survey.weight_expands_to!r}. Converting to one day "
            "of that kind needs the share of the universe each day type's households cover, "
            "and a flag on a trip does not carry it. Either the year expands to one day of the "
            "record's own kind, or its day type has to come from the households"
        )
    day_types = list(dict.fromkeys(rule.flags.values()))
    shares = pd.Series(1.0, index=pd.Index(day_types, name=config.DAY_TYPE_COL))

    log.info(
        "%s: day type read from %s; records by day type: %s. Stated by %s",
        survey.label,
        ", ".join(rule.flags),
        ", ".join(
            f"{day_type} {int((assigned == day_type).sum()):,}" for day_type in day_types
        ),
        rule.stated_by or "nothing declared, which is a gap and not a licence",
    )
    if not rule.stated_by:
        log.warn(
            "%s takes its day type from a flag and names nothing in the delivery that says "
            "which day the flag means. A column called \"not a working day\" does not say "
            "whether it is a Saturday or a Sunday, and the two are different denominators",
            survey.label,
        )
    return assigned, shares


def _day_type_is_always_one(
    rule: config.DayTypeIsAlwaysOne,
    trips: pd.DataFrame,
    survey: config.MobilitySurvey,
    log: RunLog,
) -> tuple[pd.Series, pd.Series]:
    """One kind of day for the whole survey, and a universe share of one.

    A year that surveyed a single kind of day has nothing to split and nothing to
    convert: its factor already expands to one day of that kind, so the two trip
    columns coincide and the run says so rather than dividing by a share of one
    and implying a conversion happened.

    The claim is quoted on every run from the year's own documents. "This survey
    only covers one day" is a statement about somebody else's fieldwork, and the
    cost of getting it wrong is a Saturday that silently never existed, so it is
    said out loud where it can be disputed.
    """
    if rule.day_type not in config.DAY_TYPES:
        raise ValueError(
            f"{survey.label} declares its only day type as {rule.day_type!r}, which is not one "
            f"of {', '.join(config.DAY_TYPES)}. The exposure table joins on this value and the "
            "casualty side has to be able to name the same one"
        )

    assigned = pd.Series(rule.day_type, index=trips.index, dtype="object")
    shares = pd.Series([1.0], index=pd.Index([rule.day_type], name=config.DAY_TYPE_COL))

    log.info(
        "%s: every record is %s and the survey distinguishes no other kind of day, so its two "
        "trip columns coincide. Stated by %s",
        survey.label,
        rule.day_type,
        rule.stated_by or "nothing declared, which is a gap and not a licence",
    )
    if not rule.stated_by:
        log.warn(
            "%s declares a single day type but names nothing in the delivery that says so. A "
            "year covering one day is a strong claim about someone else's fieldwork; find the "
            "statement before any figure drawn from this year is quoted",
            survey.label,
        )
    return assigned, shares


def _day_type_from_source(
    rule: config.DayTypeFromSource,
    trips: pd.DataFrame,
    survey: config.MobilitySurvey,
    log: RunLog,
) -> tuple[pd.Series, pd.Series]:
    """The day type is the one the record's own source declared.

    2011 is the year this was written for, and it is the fourth way the four
    surveys state one thing. Its weekday and its Saturday are separate samples of
    separate households in separate Access databases, so the day type is a property
    of the file and of nothing on the record.

    This reads the tag the reader wrote on every row, and nothing else. It opens no
    file: the alternative shape — a day-type rule that goes and loads the second
    database itself — would make this the second reader in a design that has had
    exactly one since 2023, and the ragged fact would sit inside a handler instead
    of in the declaration where it can be seen.
    """
    declared = {
        source.table.path.name: source.day_type
        for source in survey.trips
        if source.day_type is not None
    }
    if len(declared) != len(survey.trips):
        unnamed = [
            source.table.path.name for source in survey.trips if source.day_type is None
        ]
        raise ValueError(
            f"{survey.label} takes its day type from the source a record came out of, but "
            f"{len(unnamed)} of its {len(survey.trips)} source(s) declare none: "
            f"{', '.join(unnamed)}. A source with no day type under this rule has no day type "
            "at all, and an unknown day type is not a day type"
        )
    for day_type in declared.values():
        if day_type not in config.DAY_TYPES:
            raise ValueError(
                f"{survey.label} declares one of its sources as {day_type!r}, which is not one "
                f"of {', '.join(config.DAY_TYPES)}. The exposure table joins on this value and "
                "the casualty side has to be able to name the same one"
            )

    assigned = trips[SOURCE_COL].map(declared)
    unresolved = int(assigned.isna().sum())
    if unresolved:
        raise ValueError(
            f"{survey.label}: {unresolved} record(s) carry a source this rule does not know. "
            "The reader and the declaration have gone out of step, which cannot happen by "
            "reading a file and can happen by editing one of the two"
        )

    # Each source is its own sample expanding to its own universe once, so there is
    # nothing to convert and every share is one. A year whose factor spread the
    # universe across its reference days would need the household weights to say
    # what fraction each day covers, and the name of a file cannot supply them.
    if survey.weight_expands_to != config.WEIGHT_EXPANDS_TO_DAY_OF_TYPE:
        raise ValueError(
            f"{survey.label} takes its day type from the file a record came out of but declares "
            f"that its factor expands to {survey.weight_expands_to!r}. Converting to one day of "
            "that kind needs the share of the universe each day type's households cover, and "
            "which file a record came out of does not carry it"
        )
    day_types = list(dict.fromkeys(declared.values()))
    shares = pd.Series(1.0, index=pd.Index(day_types, name=config.DAY_TYPE_COL))

    log.info(
        "%s: day type read from the source each record came out of; %s. Stated by %s",
        survey.label,
        ", ".join(
            f"{day_type} {int((assigned == day_type).sum()):,} record(s) from {name}"
            for name, day_type in declared.items()
        ),
        rule.stated_by or "nothing declared, which is a gap and not a licence",
    )
    if not rule.stated_by:
        log.warn(
            "%s takes its day type from which file a record came out of and names nothing in "
            "the delivery that says which day each file holds. A file name is not evidence, "
            "and a Saturday that is really a Friday is invisible in every figure downstream",
            survey.label,
        )
    return assigned, shares


# Which handler resolves which declared rule. A registry rather than a chain of
# isinstance checks, so that the year whose day type arrives as a flag on the
# record or as a separate database adds an entry here and a declaration in the
# configuration, and touches nothing else in this module.
_DAY_TYPE_HANDLERS = {
    config.DayTypeFromHouseholdDate: _day_type_from_household_date,
    config.DayTypeIsAlwaysOne: _day_type_is_always_one,
    config.DayTypeFromRecordFlags: _day_type_from_record_flags,
    config.DayTypeFromSource: _day_type_from_source,
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
# How long a trip took
# ---------------------------------------------------------------------------


def _duration_from_minutes_column(
    rule: config.DurationFromMinutesColumn,
    trips: pd.DataFrame,
    survey: config.MobilitySurvey,
    log: RunLog,
) -> pd.Series:
    """The column, as declared, in the delivery's own decimal notation."""
    require_columns(trips, (rule.column,), f"{survey.label} durations")
    return to_number(trips[rule.column], survey.trips_decimal)


def _duration_from_clock_columns(
    rule: config.DurationFromClockColumns,
    trips: pd.DataFrame,
    survey: config.MobilitySurvey,
    log: RunLog,
) -> pd.Series:
    """Minutes between a departure and an arrival stored as clock values.

    2019 stores both as fractions of a day, the way a spreadsheet does, so the
    duration is the gap times the minutes in a day. Two details are not cosmetic.
    A trip arriving at a smaller clock value than it left crossed midnight and its
    gap has to wrap; 189 of 2019's records do. And the result is rounded to the
    minute, because 0.302083333333333 minus 0.291666666666667 is 14.999999999
    rather than 15, and every threshold in the study would take that trip for a
    shorter one than the survey does.
    """
    require_columns(trips, (rule.start_column, rule.end_column), f"{survey.label} durations")
    start = to_number(trips[rule.start_column], survey.trips_decimal)
    end = to_number(trips[rule.end_column], survey.trips_decimal)

    minutes = (end - start) * rule.minutes_per_unit
    wrapped = 0
    if rule.wrap_at_midnight:
        crossing = minutes < 0
        wrapped = int(crossing.sum())
        minutes = minutes.where(~crossing, minutes + rule.minutes_per_unit)
    if rule.round_to_minute:
        minutes = minutes.round()

    log.info(
        "%s: duration derived from %s and %s as clock values, %d record(s) crossing midnight; "
        "median %.0f min",
        survey.label,
        rule.start_column,
        rule.end_column,
        wrapped,
        float(minutes.median()),
    )
    return minutes


def _duration_from_text_clock_columns(
    rule: config.DurationFromTextClockColumns,
    trips: pd.DataFrame,
    survey: config.MobilitySurvey,
    log: RunLog,
) -> pd.Series:
    """Minutes between a departure and an arrival written as `HH:MM:SS` text.

    2015's `HORA_INICIO` and `HORA_FIN`. The parsing is done on the three parts
    rather than through a datetime parser because these are durations of day and
    not instants: an hour of 24 or more is a legitimate way to write "after
    midnight" and a parser refuses it, returning nothing where the arithmetic is
    obvious.

    The wrap is the same as 2019's — 503 of 2015's records arrive at a smaller
    clock value than they left — and the rounding is not: see the rule for why
    this year's derivation is exact and rounding it would be the error rather than
    the repair.
    """
    require_columns(trips, (rule.start_column, rule.end_column), f"{survey.label} durations")

    def clock_minutes(column: str) -> pd.Series:
        parts = trips[column].astype("string").str.strip().str.split(":", expand=True)
        if parts.shape[1] != 3:
            raise ValueError(
                f"{survey.label}: {column} does not hold HH:MM:SS — splitting on the colon "
                f"gives {parts.shape[1]} part(s) rather than three"
            )
        numbers = parts.apply(lambda part: pd.to_numeric(part, errors="coerce"))
        return numbers[0] * 60 + numbers[1] + numbers[2] / 60

    start, end = clock_minutes(rule.start_column), clock_minutes(rule.end_column)
    unreadable = int((start.isna() | end.isna()).sum())

    minutes = end - start
    wrapped = 0
    if rule.wrap_at_midnight:
        crossing = minutes < 0
        wrapped = int(crossing.sum())
        minutes = minutes.where(~crossing, minutes + rule.minutes_per_day)
    if rule.round_to_minute:
        minutes = minutes.round()

    log.info(
        "%s: duration derived from %s and %s as HH:MM:SS text, %d record(s) crossing midnight, "
        "%s to the minute; median %.0f min",
        survey.label,
        rule.start_column,
        rule.end_column,
        wrapped,
        "rounded" if rule.round_to_minute else "not rounded",
        float(minutes.median()),
    )
    if unreadable:
        log.warn(
            "%s: %d record(s) have no readable clock value in %s or %s, so their duration is "
            "unknown and the pair they name cannot be judged",
            survey.label,
            unreadable,
            rule.start_column,
            rule.end_column,
        )
    return minutes


# The same registry pattern as the day type, and for the same reason: three of
# the four surveys state the duration three different ways, so a year adds a rule
# beside the others rather than a second way of reading a file.
_DURATION_HANDLERS = {
    config.DurationFromMinutesColumn: _duration_from_minutes_column,
    config.DurationFromClockColumns: _duration_from_clock_columns,
    config.DurationFromTextClockColumns: _duration_from_text_clock_columns,
}


def trip_duration_minutes(
    trips: pd.DataFrame,
    survey: config.MobilitySurvey,
    log: RunLog,
) -> pd.Series | None:
    """Minutes per trip under the year's declared rule, or None if it declares none."""
    rule = survey.duration_rule
    if rule is None:
        return None
    handler = _DURATION_HANDLERS.get(type(rule))
    if handler is None:
        raise NotImplementedError(
            f"{survey.label} declares its duration as {type(rule).__name__}, which no handler "
            f"in surveys._DURATION_HANDLERS resolves. Add the handler beside the others rather "
            "than reading the file a second way"
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
# Records the geometry contradicts
# ---------------------------------------------------------------------------


def implausible_records(
    trips: pd.DataFrame,
    zones: gpd.GeoDataFrame,
    survey: config.MobilitySurvey,
    log: RunLog,
    duration: pd.Series | None,
) -> pd.Series:
    """Which records name two zones the mode could not have crossed in the time.

    The test is deliberately the most forgiving one available. It compares the
    **shortest distance between the two zone polygons** — the best case the
    traveller could possibly have had, not the centroid distance the desire line
    will actually use — against a generous ceiling speed for the mode times the
    duration the record itself reports. A record that fails could not have been
    made however the trip ran inside its own zones.

    It exists because looking at the pedestrian map raised the question: lines
    crossing the whole city, for a mode whose trip-weighted median line is 1.3 km.
    The extreme case is 82.3 km in 15 minutes, and it is not an artefact of taking
    centroids for large peripheral zones — those two polygons are 61.8 km apart at
    their nearest points and do not touch. Something in the record is wrong, the
    file does not say what, and the line drawn from it is a line nobody travelled.

    `duration` is the year's minutes per record, computed once by the caller and
    aligned to `trips`, because the second thing that needs it — which walking
    trips are in D39's narrower definition — needs it over a wider set of records
    than this test does. Deriving it twice would mean two chances to derive it
    differently.

    Returns a boolean mask over `trips`. A record with no duration cannot be
    judged and is kept, which the run reports: a check that quietly drops what it
    cannot evaluate is worse than one that says how much it could not see.
    """
    verdict = pd.Series(False, index=trips.index)
    if duration is None:
        log.warn(
            "%s: no duration rule is declared, so no origin-destination pair can be checked "
            "against the mode that made it. A fifth of the 2023 pedestrian trips fail that "
            "check, so this year is not known to be free of the same records — it is unexamined",
            survey.label,
        )
        return verdict

    # Measured once per distinct pair of zones and joined back, not once per
    # record: the distance between two polygons is a property of the pair, and
    # there are 24,354 pairs behind 62,055 records.
    distinct = trips.loc[
        trips[ZONE_ORIGIN_COL] != trips[ZONE_DESTINATION_COL],
        [ZONE_ORIGIN_COL, ZONE_DESTINATION_COL],
    ].drop_duplicates()
    if distinct.empty:
        return verdict

    geometry = zones.set_index(ZONE_CODE_COL).geometry
    origins = gpd.GeoSeries(geometry.loc[distinct[ZONE_ORIGIN_COL]].to_numpy(), crs=zones.crs)
    destinations = gpd.GeoSeries(
        geometry.loc[distinct[ZONE_DESTINATION_COL]].to_numpy(), crs=zones.crs
    )
    distinct = distinct.assign(
        _GAP_KM=origins.distance(destinations, align=False).to_numpy() / 1000.0
    )

    gap = trips[[ZONE_ORIGIN_COL, ZONE_DESTINATION_COL]].merge(
        distinct, on=[ZONE_ORIGIN_COL, ZONE_DESTINATION_COL], how="left"
    )["_GAP_KM"]
    gap.index = trips.index
    # An intra-zonal pair never appears in `distinct` and its gap is zero, which
    # is right: it is a trip inside one zone and no distance is implied.
    gap = gap.fillna(0.0)

    ceiling = trips[config.ACTOR_TYPE_COL].map(config.MODE_SPEED_CEILING_KMH)
    reachable = ceiling * duration / 60.0
    verdict = (gap > reachable) & reachable.notna() & duration.notna()

    unjudged = int(duration.isna().sum())
    if unjudged:
        log.warn(
            "%s: %d record(s) yield no duration under %s, so whether the mode could have "
            "covered the distance cannot be decided; they are kept",
            survey.label,
            unjudged,
            type(survey.duration_rule).__name__,
        )
    return verdict


# ---------------------------------------------------------------------------
# Reading a survey
# ---------------------------------------------------------------------------


def read_sources(survey: config.MobilitySurvey, log: RunLog) -> pd.DataFrame:
    """Every declared source of one year's trips, read and stacked into one frame.

    Three of the four years declare a single source and come out of here exactly as
    they went in, with one extra column nothing outside this module reads. 2011
    declares two, because its weekday and its Saturday are separate samples of
    separate households in separate databases.

    Each row is tagged with the file it came out of. That is the one fact the
    concatenation would otherwise destroy, and for 2011 it is the only thing that
    says which kind of day the row is — so it is written here, by the only step
    that knows it, rather than reconstructed later from something that correlates
    with it.

    The sources have to agree on their columns. Two files with different column
    sets stacked together give a frame full of holes wherever one of them was
    silent, and a hole in a zone column is indistinguishable from a record whose
    zone was never coded.
    """
    frames = []
    for source in survey.trips:
        frame = read_table(source.table, log)
        frame[SOURCE_COL] = source.table.path.name
        frames.append(frame)

    if len(frames) == 1:
        return frames[0]

    first, *rest = frames
    expected = list(first.columns)
    for source, frame in zip(survey.trips[1:], rest):
        if list(frame.columns) != expected:
            absent = [name for name in expected if name not in frame.columns]
            extra = [name for name in frame.columns if name not in expected]
            raise ValueError(
                f"{survey.label}: {source.table.path.name} does not carry the same columns as "
                f"{survey.trips[0].table.path.name}. Absent: {', '.join(absent) or 'none'}; "
                f"extra: {', '.join(extra) or 'none'}. Stacking them would leave a hole "
                "wherever one file is silent, and a hole in a zone column reads as a record "
                "whose zone was never coded"
            )

    stacked = pd.concat(frames, ignore_index=True)
    log.info(
        "%s: %d source(s) stacked into %d record(s) — %s",
        survey.label,
        len(frames),
        len(stacked),
        ", ".join(
            f"{len(frame):,} from {source.table.path.name}"
            for source, frame in zip(survey.trips, frames)
        ),
    )
    return stacked


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
    frame = read_sources(survey, log)
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

    weights = to_number(frame[survey.weight_column], survey.trips_decimal)
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

    # Derived once, over every record the file holds, because two different
    # things need it: which origin-destination pairs the mode could not have
    # covered, and which walking trips are in D39's narrower definition. The
    # second needs it before any record has been set aside, so this is the only
    # place both can read the same numbers.
    duration = trip_duration_minutes(frame, survey, log)
    if duration is None and config.PEDESTRIAN in survey.actor_types:
        # D38 could let a year state no duration: what it lost was the
        # plausibility test, and the run said so rather than pretending to have
        # made it. D39 makes the duration load-bearing in a second way — the
        # pedestrian series is read on the fifteen-minute column and there is no
        # way to build that column without it — so a walking year with no
        # duration rule now stops the run instead of exporting a null the
        # interpolation would meet four stages later.
        raise ValueError(
            f"{survey.label} declares no duration_rule, so it cannot state the fifteen-minute "
            "pedestrian definition D39 reads the series on. Declare one beside the rules in "
            "config.py, or take the year out of MOBILITY_SURVEYS; both are decisions for a "
            "person"
        )

    file_total = float(weights.sum())

    # The reconstructed total against the one the survey publishes. This is the
    # check that turns "we believe this column is the expansion factor" into
    # something demonstrated: the 2023 factor arrives as text with a comma decimal
    # and a trailing space, so a column read the obvious way sums to zero without
    # complaining, and several plausible-looking columns sit beside it.
    if survey.published_total is None:
        log.warn(
            "%s: no published total is declared for %s, so the reconstruction is checked "
            "against nothing. Find one in the survey's own documentation before any figure "
            "drawn from this year is quoted",
            survey.label,
            survey.weight_column,
        )
    elif not np.isclose(file_total, survey.published_total, rtol=config.SURVEY_CONTROL_TOTAL_RTOL):
        raise ValueError(
            f"{survey.label}: {survey.weight_column} sums to {file_total:,.1f} but the survey "
            f"publishes {survey.published_total:,.1f} ({survey.published_total_source}). "
            "Either the column is not the expansion factor, or it is being read or filtered "
            "differently from the way it was published; both are decisions, not rounding"
        )
    else:
        log.info(
            "%s: %s sums to %s, matching the published %s (%s)",
            survey.label,
            survey.weight_column,
            f"{file_total:,.1f}",
            f"{survey.published_total:,.1f}",
            survey.published_total_source,
        )
    log.info(
        "%s: one unit of %s is a trip on %s",
        survey.label,
        survey.weight_column,
        survey.weight_expands_to,
    )

    weighted = frame[frame[TRIPS_COL].notna()]
    not_measured_totals = (
        weighted[weighted[config.ACTOR_TYPE_COL].isna()]
        .groupby(survey.mode_column)[TRIPS_COL]
        .sum()
    )
    measured = weighted[weighted[config.ACTOR_TYPE_COL].notna()].copy()

    # The two pedestrian definitions, one written into the table and one written
    # into the file's own totals. A walk shorter than the floor keeps its whole
    # weight in the first column and contributes nothing to the second; every
    # record of the other three modes carries the same number in both, because no
    # other mode has two definitions to choose between.
    measured[TRIPS_OVER_15MIN_COL] = measured[TRIPS_COL]
    if duration is not None:
        walking = measured[config.ACTOR_TYPE_COL] == config.PEDESTRIAN
        walk_minutes = duration.loc[measured.index]
        short = walking & ~(walk_minutes >= config.PEDESTRIAN_LONG_WALK_MIN_MINUTES)
        measured.loc[short, TRIPS_OVER_15MIN_COL] = 0.0
        unjudged_walk = int((walking & walk_minutes.isna()).sum())
        if unjudged_walk:
            # A walking record with no duration cannot be placed on either side of
            # the threshold, and dropping it out of the narrow column silently
            # would make that column smaller for a reason nothing records. None of
            # the four years has one; a year that did would need a decision.
            log.warn(
                "%s: %d walking record(s) yield no duration, so which of the two pedestrian "
                "definitions they belong to cannot be decided; they are counted in the full "
                "column and left out of the fifteen-minute one, which understates it. See D39",
                survey.label,
                unjudged_walk,
            )
        pedestrian_definitions = (
            measured[walking]
            .groupby(config.DAY_TYPE_COL)[[TRIPS_COL, TRIPS_OVER_15MIN_COL]]
            .sum()
        )
    else:
        pedestrian_definitions = measured.iloc[:0].groupby(config.DAY_TYPE_COL)[
            [TRIPS_COL, TRIPS_OVER_15MIN_COL]
        ].sum()

    for source_column, target in (
        (survey.origin_zone_column, ZONE_ORIGIN_COL),
        (survey.destination_zone_column, ZONE_DESTINATION_COL),
    ):
        # Zone codes are compared as text on both sides of every join in this
        # module, and both sides are spelled by the same function. The zoning
        # stores its code as a float and the trips store theirs as text in the
        # three CSV years and as a double in 2011, and "810", "810.0" and 810.0
        # are one zone to a reader and three keys to a join that would then match
        # nothing at all.
        measured[target] = zone_code_text(
            measured[source_column], f"{survey.label} {source_column}"
        )

    # A zone is missing in two ways and both end the same place. It can be absent,
    # and it can be a code the delivery uses for "no answer" or wrote in error —
    # 2019 does both, with a 0 on records that carry no municipality and no UTAM
    # either, and one record naming a code above the top of its own zoning. A
    # declared code is counted here rather than left to fail the zone lookup,
    # because the lookup failing is what should happen to a code nobody decided
    # about, and these were decided about.
    absent = measured[ZONE_ORIGIN_COL].isna() | measured[ZONE_DESTINATION_COL].isna()
    placeless = pd.Series(False, index=measured.index)
    if survey.zone_codes_meaning_no_zone:
        named = list(survey.zone_codes_meaning_no_zone)
        placeless = measured[ZONE_ORIGIN_COL].isin(named) | measured[ZONE_DESTINATION_COL].isin(
            named
        )
    unzoned = absent | placeless
    unzoned_total = float(measured.loc[unzoned, TRIPS_COL].sum())
    if unzoned.any():
        log.warn(
            "%s: %d record(s) of the measured modes cannot be placed, %s trips per day — "
            "%d with no zone at all and %d naming a code declared to be no place (%s)",
            survey.label,
            int(unzoned.sum()),
            f"{unzoned_total:,.1f}",
            int(absent.sum()),
            int((placeless & ~absent).sum()),
            ", ".join(survey.zone_codes_meaning_no_zone) or "none declared",
        )
        measured = measured[~unzoned]

    # The zoning is read here rather than by the caller because the next step
    # needs it: whether a record's two zones are too far apart for the mode that
    # made it cannot be asked without the polygons.
    zones = read_zoning(survey, log)
    _require_known_zones(measured, zones, survey)

    impossible = implausible_records(
        measured,
        zones,
        survey,
        log,
        duration=None if duration is None else duration.loc[measured.index],
    )
    implausible_totals = measured.loc[impossible].groupby(config.ACTOR_TYPE_COL)[TRIPS_COL].sum()
    implausible_count = int(impossible.sum())
    if implausible_count:
        log.warn(
            "%s: %d record(s) name two zones further apart than the mode could cover in the "
            "duration they report, %s trips per day, and are dropped. By mode: %s. The "
            "shortest distance between the two polygons is what was compared, so these could "
            "not have happened however the trip ran inside its zones",
            survey.label,
            implausible_count,
            f"{float(implausible_totals.sum()):,.1f}",
            "; ".join(
                f"{actor} {float(value):,.0f} "
                f"({100 * value / measured[measured[config.ACTOR_TYPE_COL] == actor][TRIPS_COL].sum():.1f}%)"
                for actor, value in implausible_totals.items()
            ),
        )
        measured = measured[~impossible]

    grouped = measured.groupby([config.ACTOR_TYPE_COL, config.DAY_TYPE_COL])[
        [TRIPS_COL, TRIPS_OVER_15MIN_COL]
    ].sum()
    totals = grouped[TRIPS_COL]
    totals_over_15min = grouped[TRIPS_OVER_15MIN_COL]

    pairs = (
        measured.groupby(
            [config.ACTOR_TYPE_COL, config.DAY_TYPE_COL, ZONE_ORIGIN_COL, ZONE_DESTINATION_COL],
            observed=True,
        )[[TRIPS_COL, TRIPS_OVER_15MIN_COL]]
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
                -(records_read - without_weight - implausible_count - len(measured)),
                "records of a mode outside the four measured, or with no origin or destination zone",
            ),
            (
                -implausible_count,
                "records naming two zones further apart than the mode could cover in the "
                "duration they report",
            ),
            (
                len(pairs) - len(measured),
                "rows lost to grouping the records into actor type, day type and zone pair",
            ),
        ],
        notes=[
            f"source={survey.trips_label}, {survey.measures}",
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
            "pedestrian, whole surveyed region, before the removals: " + "; ".join(
                f"{day_type} {row[TRIPS_COL] / universe_shares.get(day_type, 1.0):,.0f} on every "
                f"walking trip and {row[TRIPS_OVER_15MIN_COL] / universe_shares.get(day_type, 1.0):,.0f} "
                f"of fifteen minutes or more ({100 * row[TRIPS_OVER_15MIN_COL] / row[TRIPS_COL]:.1f}%)"
                for day_type, row in pedestrian_definitions.iterrows()
            ),
        ],
    )

    return SurveyTrips(
        survey=survey,
        pairs=pairs,
        zones=zones,
        universe_shares=universe_shares,
        records_read=records_read,
        records_measured=len(measured),
        records_without_weight=without_weight,
        file_total=file_total,
        totals=totals,
        totals_over_15min=totals_over_15min,
        pedestrian_definitions=pedestrian_definitions,
        not_measured_totals=not_measured_totals,
        unzoned_total=unzoned_total,
        implausible_totals=implausible_totals,
        implausible_records=implausible_count,
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
    # Spelled by the same function that spells the trips' codes, so the two sides
    # of the join cannot disagree about what "810" is. The shapefile stores the
    # code as a float, so a straight cast would give "810.0" against the trips'
    # "810" — but a zoning code that is not a number at all is a defect in the
    # zoning rather than a code to carry forward, so it stops the run here.
    codes = pd.to_numeric(zones[zoning.code_column], errors="coerce")
    if codes.isna().any():
        raise ValueError(
            f"{survey.label}: {int(codes.isna().sum())} zone(s) of {path.name} have no "
            f"readable code in {zoning.code_column}"
        )
    zones[ZONE_CODE_COL] = zone_code_text(
        zones[zoning.code_column], f"{survey.label} zoning {zoning.code_column}"
    )

    duplicated = int(zones[ZONE_CODE_COL].duplicated().sum())
    if duplicated and not zoning.zone_delivered_in_parts:
        raise ValueError(
            f"{survey.label}: {duplicated} zone code(s) of {path.name} appear more than once, "
            "so a trip keyed on one of them would be placed in two zones. If the delivery means "
            "them as pieces of one zone, say so with zone_delivered_in_parts and write down what "
            "shows it; two different zones sharing a number is a defect this reader cannot tell "
            "from that on its own"
        )
    if duplicated:
        # Dissolved rather than kept apart, so that everything downstream can go
        # on treating a zone code as one geometry: the centroid a desire line is
        # drawn between, the polygon a unit is overlaid with, and the gap the
        # plausibility test measures are each defined for a zone and not for a
        # piece of one. 2015 has three such features across two codes.
        zones = zones.dissolve(by=ZONE_CODE_COL, as_index=False)
        log.info(
            "%s: %d feature(s) of %s carry a code another feature already carries and are "
            "declared to be pieces of one zone, so they are dissolved into %d zone(s)",
            survey.label,
            duplicated,
            path.name,
            len(zones),
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


def _require_known_zones(
    trips: pd.DataFrame,
    zones: gpd.GeoDataFrame,
    survey: config.MobilitySurvey,
) -> None:
    """Every zone the trips name has to exist in the zoning, or the trip is nowhere.

    Checked before any geometry is measured, because a zone code with no polygon
    produces a line with a missing endpoint, and a line with a missing endpoint is
    dropped by the overlay without a word. It is also what makes the distance
    lookups downstream safe to index directly.
    """
    known = set(zones[ZONE_CODE_COL])
    missing_origin = ~trips[ZONE_ORIGIN_COL].isin(known)
    missing_destination = ~trips[ZONE_DESTINATION_COL].isin(known)
    unknown = missing_origin | missing_destination
    if not unknown.any():
        return

    codes = sorted(
        set(trips.loc[missing_origin, ZONE_ORIGIN_COL])
        | set(trips.loc[missing_destination, ZONE_DESTINATION_COL])
    )
    raise ValueError(
        f"{survey.label}: {len(codes)} zone code(s) named by the trips are not in "
        f"{survey.zoning.shapefile.name}, carrying "
        f"{float(trips.loc[unknown, TRIPS_COL].sum()):,.1f} trips per day: "
        f"{', '.join(codes[:20])}{' ...' if len(codes) > 20 else ''}. A trip whose zone has no "
        "polygon has no place, and dropping it silently is how a mode ends up smaller than it is"
    )
