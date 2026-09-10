"""Exposure in the fourteen years no survey covers, as a rate rather than a level.

The surveys sit at 2011, 2015, 2019 and 2023, evenly spaced four years apart, and
the casualty series runs 2007-2024. Four of those eighteen years are measured,
nine fall between two measured years, four fall before the first and one after the
last. The panel the models are fitted on needs all eighteen.

**What is interpolated is the rate and not the level.** The level is the product
of two things that move at different speeds and are known with very different
confidence: how many people live in a unit, which the census panel gives every
year, and how much each of them travels, which four surveys give four times.
Interpolating the level throws the annual knowledge away and smears the
demographic change across four-year steps; interpolating the rate uses each source
for what it is good for. In a unit whose population grew forty per cent between
two surveys — and several of the western expansions did — the two give visibly
different answers, and only one of them uses information we actually have.

**It runs per unit, and that is the point rather than a detail.** The study is
thirty units over eighteen years, so a city curve handed identically to every unit
would not be an exposure panel at all: its within-unit variation would be the same
everywhere and it would carry no spatial information between survey years. The
price is that every one of the 30 x 4 x day-type series inherits its own unit's
sampling noise, and `step_volatility` measures that price on every run.

**Every cell says where it came from.** `EXPOSURE_PROVENANCE` and
`YEARS_TO_NEAREST_SURVEY` are not decoration: fourteen of the eighteen years are
constructed, and a model fitted on all eighteen without knowing which is fourteen
observations of an assumption.

This module reads the exposure table another run exported and the population panel,
and writes one more table. **It never reads a survey and never touches
`analysis__exposure_by_unit`**: that table is the record of what the surveys say,
and this one is a construction that sits beside it, exactly as the corrected
casualty set sits beside the observed one (D31).

See D39, D40 and `docs/interpolating-the-exposure.md`.

Run it:

    python -m src.run_pipeline interpolation
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

try:  # regular package import
    from src import config, population
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import population  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


MEASURED_TABLE_FILENAME = f"{config.ANALYSIS_PREFIX}__exposure_by_unit.parquet"

# The two levels the table carries and the rate each one is interpolated on. One
# mapping rather than four names repeated at every step, because the whole
# procedure is "do it twice and change nothing else" and a second definition that
# drifted out of step with the first is exactly what D39 refused.
_SERIES: dict[str, str] = {
    config.TRIPS_PER_DAY_OF_TYPE_COL: config.INTERPOLATED_RATE_COL,
    config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL: config.INTERPOLATED_RATE_OVER_15MIN_COL,
}

_SERIES_KEY = [config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]


@dataclass(frozen=True)
class MeasuredExposure:
    """The exported exposure table, and which run it was read from.

    The run id travels with the table because every figure in this study carries
    the run it came from, and a constructed panel whose input cannot be named is
    checkable against nothing later.
    """

    table: pd.DataFrame
    # What each survey measures over the whole surveyed region, per mode and day
    # type, before this study's removals. It is here because every figure the
    # deliveries publish is stated on that footprint and none on the thirty units,
    # so a comparison against a published number has to come back to it.
    city_totals: pd.DataFrame
    source_run: str

    @property
    def survey_years(self) -> tuple[int, ...]:
        return tuple(sorted(self.table[config.YEAR_COL].unique()))

    def anchors_of(self, day_type: str) -> tuple[int, ...]:
        """The survey years that measured one kind of day.

        Read from the table rather than from the survey declarations, because the
        table is what this stage interpolates and a day type declared but absent
        from it would be a series with no anchors at all.
        """
        rows = self.table[self.table[config.DAY_TYPE_COL] == day_type]
        return tuple(sorted(rows[config.YEAR_COL].unique()))


# ---------------------------------------------------------------------------
# Reading what another run measured
# ---------------------------------------------------------------------------


def read_measured(log: RunLog, run: str | None = None) -> MeasuredExposure:
    """The exposure table exported by the `exposure` route, from a named run or the last.

    Read from a file rather than rebuilt in memory on purpose. Rebuilding it would
    mean reading four surveys again to produce a table this stage is not allowed to
    change, and it would make the interpolation look like a second measurement of
    the same thing. What it costs is that the run has to say which run it read, and
    it does.
    """
    run = config.INTERPOLATION_SOURCE_RUN if run is None else run
    run_dir = config.run_directory_holding(MEASURED_TABLE_FILENAME, run)
    table = pd.read_parquet(run_dir / config.DATA_SUBDIR / MEASURED_TABLE_FILENAME)

    expected = list(config.survey_exposure_columns())
    missing = [column for column in expected if column not in table.columns]
    if missing:
        # The one that will actually happen is a run from before D39, whose table
        # has no fifteen-minute column. Naming the decision is what turns a
        # KeyError four functions later into a sentence somebody can act on.
        raise ValueError(
            f"{run_dir.name} exported an exposure table without {', '.join(missing)}. The "
            "pedestrian series is read on TRIPS_PER_DAY_OF_TYPE_OVER_15MIN (D39), so a table "
            "from before that column existed cannot be interpolated. Re-run the exposure route"
        )

    city_totals_path = (
        run_dir / config.DATA_SUBDIR / f"{config.SURVEY_CITY_TOTALS_FILENAME}.parquet"
    )
    if not city_totals_path.exists():
        raise FileNotFoundError(
            f"{run_dir.name} exported no {config.SURVEY_CITY_TOTALS_FILENAME}. The comparison "
            "against what the 2005 survey published is made over the whole surveyed region, "
            "because that is the footprint every delivery states its figures on, and this "
            "table is the only place the region totals survive apportionment. Re-run the "
            "exposure route"
        )
    city_totals = pd.read_parquet(city_totals_path)

    log.record(
        "read the measured exposure table",
        rows_in=len(table),
        rows_out=len(table),
        notes=[
            f"source run={run_dir.name}"
            + ("" if run else ", the most recent that exported one"),
            "years: " + ", ".join(str(year) for year in sorted(table[config.YEAR_COL].unique())),
            "day types: " + "; ".join(
                f"{day_type} in "
                + ", ".join(
                    str(year)
                    for year in sorted(
                        table.loc[table[config.DAY_TYPE_COL] == day_type, config.YEAR_COL].unique()
                    )
                )
                for day_type in config.DAY_TYPES
                if day_type in set(table[config.DAY_TYPE_COL])
            ),
            f"{len(city_totals)} row(s) of region totals per year, mode and day type read "
            "beside it, which is the footprint every published figure is stated on",
            "this stage reads no survey and writes no change to either table",
        ],
    )
    return MeasuredExposure(table=table, city_totals=city_totals, source_run=run_dir.name)


# ---------------------------------------------------------------------------
# One series, over the whole window
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Filled:
    """One year of one series: the rate, where it came from, and what it rests on."""

    rate: float
    provenance: str
    years_to_nearest_survey: int
    # The survey years the value was built from — one for a measured or a held
    # year, two for an interpolated one. What `SAMPLE_SUPPORT` is carried from.
    rests_on: tuple[int, ...]
    # True where the segment had to be filled linearly because the logarithm was
    # undefined at one of its ends. Counted and reported; never silently smoothed.
    linear_because_of_a_zero: bool = False


def fill_series(rates: dict[int, float], window: range) -> dict[int, Filled]:
    """Carry a handful of measured rates across every year of the window.

    Log-linear between two measured years — a constant proportional change per
    year rather than a constant absolute one, which keeps every value positive and
    treats a mode growing from a small base the way growth actually works. Flat
    outside them, because prolonging a slope fitted to two points four years
    backwards is extrapolating from an artefact as readily as from a trend, and
    D40 refuses it.

    A rate of exactly zero at either end of a segment makes the logarithm
    undefined, so that segment is filled linearly instead and says so. Zero is an
    observation here — three whole units did no cycling at all on 2011's Saturday
    — so the segment is filled rather than dropped, and no epsilon is introduced
    to keep the logarithm alive.
    """
    anchors = sorted(rates)
    if not anchors:
        raise ValueError("a series with no measured year cannot be carried anywhere")
    first, last = anchors[0], anchors[-1]

    filled: dict[int, Filled] = {}
    for year in window:
        nearest = min(abs(year - anchor) for anchor in anchors)
        if year in rates:
            filled[year] = Filled(rates[year], config.MEASURED_EXPOSURE, nearest, (year,))
            continue
        if year < first:
            filled[year] = Filled(rates[first], config.HELD_EXPOSURE, nearest, (first,))
            continue
        if year > last:
            filled[year] = Filled(rates[last], config.HELD_EXPOSURE, nearest, (last,))
            continue

        before = max(anchor for anchor in anchors if anchor < year)
        after = min(anchor for anchor in anchors if anchor > year)
        start, end = rates[before], rates[after]
        through = (year - before) / (after - before)
        if start > 0 and end > 0:
            # Written as a ratio raised to a power rather than as exp of a sum of
            # logs so that the two ends come back exactly when `through` is 0 or 1.
            rate = start * (end / start) ** through
            linear = False
        else:
            rate = start + (end - start) * through
            linear = True
        filled[year] = Filled(
            rate, config.INTERPOLATED_EXPOSURE, nearest, (before, after), linear
        )
    return filled


def _support_of(rests_on: tuple[int, ...], support_by_year: dict[int, str]) -> str:
    """The sample support a constructed value inherits from the years it rests on.

    The weaker of the two wins. A year built by interpolating between 2011's
    Saturday and 2015's rests on a sample the consultant themself only ever claimed
    at the scale of the city, and a constructed value cannot be better supported
    than what it was constructed from.
    """
    supports = {support_by_year[year] for year in rests_on}
    if config.SAMPLE_CITY_LEVEL_ONLY in supports:
        return config.SAMPLE_CITY_LEVEL_ONLY
    return config.SAMPLE_SUPPORTS_UNIT


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------


def build(
    measured: MeasuredExposure,
    panel: pd.DataFrame,
    units: gpd.GeoDataFrame,
    log: RunLog,
    window: range | None = None,
) -> pd.DataFrame:
    """One row per unit, year, actor type and day type, over the whole window.

    The measured years are in it unchanged — their level is carried straight
    through rather than recomputed from a rate, so an observation cannot be moved
    by the arithmetic that fills the years around it — and every other year is
    constructed and says so.

    The window is the study's whole 2007-2024 rather than the corrected set's
    2008-2024, because which casualty set the models take is not this stage's
    decision (D31 says both exist) and building the wider one keeps the choice a
    filter.
    """
    window = window or config.STUDY_YEARS
    table = measured.table

    populations = {
        year: population.for_year(panel, year) for year in window
    }
    support_by_year = {
        (row[config.AREA_CODE_COL], row[config.ACTOR_TYPE_COL], row[config.DAY_TYPE_COL], row[config.YEAR_COL]):
        row[config.SAMPLE_SUPPORT_COL]
        for _, row in table.iterrows()
    }

    day_types = [day for day in config.DAY_TYPES if day in set(table[config.DAY_TYPE_COL])]
    anchors_by_day = {day: measured.anchors_of(day) for day in day_types}

    single_anchor = [day for day, years in anchors_by_day.items() if len(years) == 1]
    if single_anchor and not config.INTERPOLATION_HOLDS_SINGLE_ANCHOR_DAY_TYPES:
        for day in single_anchor:
            log.warn(
                "%s rests on the single survey year %d, and the configuration leaves it out of "
                "the interpolated table rather than holding it flat across the window",
                day,
                anchors_by_day[day][0],
            )
        day_types = [day for day in day_types if day not in single_anchor]

    measured_by_key = table.set_index(
        _SERIES_KEY + [config.YEAR_COL]
    )[list(_SERIES)].to_dict("index")

    rows: list[dict[str, object]] = []
    linear_cells = {level: 0 for level in _SERIES}
    for day_type in day_types:
        anchors = anchors_by_day[day_type]
        block = table[table[config.DAY_TYPE_COL] == day_type]
        for area_code in units[config.AREA_CODE_COL]:
            for actor in sorted(block[config.ACTOR_TYPE_COL].unique()):
                key = (area_code, actor, day_type)
                # The rate of each measured year, one per level. Divided by the
                # population of the same unit and the same year, which is what the
                # interpolation runs on and what the level is recovered from.
                rates: dict[str, dict[int, float]] = {level: {} for level in _SERIES}
                levels: dict[str, dict[int, float]] = {level: {} for level in _SERIES}
                for year in anchors:
                    cell = measured_by_key[(area_code, actor, day_type, year)]
                    residents = float(populations[year][area_code])
                    if not residents > 0:
                        raise ValueError(
                            f"{area_code} has no population in {year}, so the rate the "
                            "interpolation runs on cannot be formed. The population panel is "
                            "required to be complete over the study's units and years (D36)"
                        )
                    for level in _SERIES:
                        levels[level][year] = float(cell[level])
                        rates[level][year] = float(cell[level]) / residents

                filled = {
                    level: fill_series(rates[level], window) for level in _SERIES
                }
                for level in _SERIES:
                    linear_cells[level] += sum(
                        1 for value in filled[level].values() if value.linear_because_of_a_zero
                    )

                shape = filled[config.TRIPS_PER_DAY_OF_TYPE_COL]
                for year in window:
                    residents = float(populations[year][area_code])
                    at = shape[year]
                    row: dict[str, object] = {
                        config.AREA_CODE_COL: area_code,
                        config.YEAR_COL: year,
                        config.ACTOR_TYPE_COL: actor,
                        config.DAY_TYPE_COL: day_type,
                        config.POPULATION_COL: residents,
                        config.EXPOSURE_PROVENANCE_COL: at.provenance,
                        config.YEARS_TO_NEAREST_SURVEY_COL: at.years_to_nearest_survey,
                        config.SAMPLE_SUPPORT_COL: _support_of(
                            at.rests_on,
                            {
                                anchor: support_by_year[(area_code, actor, day_type, anchor)]
                                for anchor in anchors
                            },
                        ),
                    }
                    for level, rate_column in _SERIES.items():
                        value = filled[level][year]
                        row[rate_column] = value.rate
                        # On a measured year the level is the survey's own number,
                        # carried through rather than recovered from the rate. The
                        # round trip through a division and a multiplication is
                        # correct to a part in 1e16 and this table has to reproduce
                        # the measured one exactly, so the arithmetic is not done at
                        # all where there is nothing to compute.
                        row[level] = (
                            levels[level][year]
                            if value.provenance == config.MEASURED_EXPOSURE
                            else value.rate * residents
                        )
                    rows.append(row)

    built = pd.DataFrame(rows)

    geometry = units[[config.AREA_CODE_COL, config.AREA_NAME_COL, config.AREA_UNIT_KM2_COL]]
    built = built.merge(geometry, on=config.AREA_CODE_COL, how="left")
    built[config.SCALE_COL] = config.active_scale().label
    built = (
        built[list(config.interpolated_exposure_columns())]
        .sort_values(
            [config.YEAR_COL, config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    census = built[config.EXPOSURE_PROVENANCE_COL].value_counts()
    log.record(
        "interpolate the exposure over the years no survey covers",
        rows_in=len(table),
        rows_out=len(built),
        changes=[
            (
                len(built) - len(table),
                f"rows for the {len(window) - len(measured.survey_years)} year(s) of "
                f"{window.start}-{window.stop - 1} that no survey covers, constructed from the "
                "rate of the years that do",
            ),
        ],
        notes=[
            f"source run={measured.source_run}",
            "day types and their anchors: " + "; ".join(
                f"{day} {'/'.join(str(year) for year in anchors_by_day[day])}"
                for day in day_types
            ),
            ", ".join(
                f"{provenance} {int(census.get(provenance, 0)):,}"
                for provenance in config.EXPOSURE_PROVENANCES
            ),
            "cells filled linearly because a rate of exactly zero makes the logarithm "
            "undefined: " + ", ".join(
                f"{level} {count}" for level, count in linear_cells.items()
            ),
        ],
    )

    for day_type in single_anchor:
        if day_type not in day_types:
            continue
        held = int(
            (
                (built[config.DAY_TYPE_COL] == day_type)
                & (built[config.EXPOSURE_PROVENANCE_COL] == config.HELD_EXPOSURE)
            ).sum()
        )
        log.warn(
            "%s rests on the single survey year %d, so it has no trajectory at all: %d of its "
            "rows are that year's rate moved by nothing but the population, and are marked %s. "
            "A model reading them is reading one survey seventeen times. They are in the table "
            "rather than out of it because a table that holds them filters down to one that "
            "does not and the reverse is impossible, and because every one of them says what it "
            "is. See D40",
            day_type,
            anchors_by_day[day_type][0],
            held,
            config.HELD_EXPOSURE,
        )

    return built


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def dictionary_table(measured: MeasuredExposure) -> pd.DataFrame:
    """What each column of the interpolated table holds, and what built it.

    Built from the same declarations the interpolation runs on, so it cannot
    describe a column the table does not have or miss one it does. The identity
    columns are in it because the table is joined to others outside this
    repository, where a reader has neither this code nor the surveys.
    """
    anchors = "; ".join(
        f"{day} {'/'.join(str(year) for year in measured.anchors_of(day))}"
        for day in config.DAY_TYPES
        if day in set(measured.table[config.DAY_TYPE_COL])
    )
    source = (
        f"interpolated from {config.ANALYSIS_PREFIX}__exposure_by_unit of run "
        f"{measured.source_run} and the population panel; anchors by day type: {anchors}"
    )

    rows = [
        {
            "COLUMN": column,
            "UNIT": "",
            "MEANS": means,
            "IS_ALTERNATIVE_ALLOCATION": False,
            "SOURCE": "",
        }
        for column, means in (
            (config.SCALE_COL, "the territorial scale the row is measured at"),
            (config.AREA_CODE_COL, "the unit, spelled as every other table of the study spells it"),
            (config.AREA_NAME_COL, "the unit's name, from the cartography"),
            (config.AREA_UNIT_KM2_COL, "the unit's area in square kilometres"),
            (
                config.YEAR_COL,
                "the year of the row, over the study's whole window. Only four of them were "
                "surveyed; EXPOSURE_PROVENANCE says which",
            ),
            (config.ACTOR_TYPE_COL, "the road user type, as the casualty matrix names it"),
            (
                config.DAY_TYPE_COL,
                "the kind of day. WEEKDAY rests on four surveys, SATURDAY on three and its "
                "longest gap is the eight years from 2015 to 2023, and SUNDAY on one",
            ),
            (
                config.POPULATION_COL,
                "the unit's residents in that year, from the annual census panel (D36). This is "
                "the denominator the rate was formed on and the multiplier the level was "
                "recovered with, so the two columns can be checked against each other in the "
                "table they appear in",
            ),
        )
    ]
    rows.extend(
        {
            "COLUMN": quantity.name,
            "UNIT": quantity.unit,
            "MEANS": quantity.means,
            "IS_ALTERNATIVE_ALLOCATION": quantity.is_alternative,
            "SOURCE": source,
        }
        for quantity in config.INTERPOLATED_EXPOSURE_QUANTITIES
    )
    rows.append(
        {
            "COLUMN": config.EXPOSURE_PROVENANCE_COL,
            "UNIT": "",
            "MEANS": (
                f"{config.MEASURED_EXPOSURE} where the year is a survey year and the value is "
                f"the survey's own; {config.INTERPOLATED_EXPOSURE} where it was built "
                f"log-linearly from the rate of the two surveys either side of it; "
                f"{config.HELD_EXPOSURE} where it is outside the measured range and the rate "
                "was held flat while the population moved. READ THIS BEFORE READING A LEVEL: "
                "fourteen of the eighteen years are constructed"
            ),
            "IS_ALTERNATIVE_ALLOCATION": False,
            "SOURCE": "",
        }
    )
    rows.append(
        {
            "COLUMN": config.YEARS_TO_NEAREST_SURVEY_COL,
            "UNIT": "years",
            "MEANS": (
                "distance in years to the nearest year that measured this series. Zero on a "
                "survey year and nowhere else. It is here so a model can weight by it, or drop "
                "the held block, without re-running anything"
            ),
            "IS_ALTERNATIVE_ALLOCATION": False,
            "SOURCE": "",
        }
    )
    rows.append(
        {
            "COLUMN": config.SAMPLE_SUPPORT_COL,
            "UNIT": "",
            "MEANS": (
                f"carried through from the survey year the value rests on, and the weaker of "
                f"the two where it rests on two: {config.SAMPLE_CITY_LEVEL_ONLY} says the "
                "survey behind it only ever claimed the figure at the scale of the city. A "
                "constructed value cannot be better supported than what it was constructed from"
            ),
            "IS_ALTERNATIVE_ALLOCATION": False,
            "SOURCE": "",
        }
    )
    return pd.DataFrame(rows)


def export(table: pd.DataFrame, measured: MeasuredExposure, log: RunLog) -> dict[str, Path]:
    """Write the interpolated panel and the dictionary that reads it."""
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    table_path = data_dir / f"{config.ANALYSIS_PREFIX}__exposure_by_unit_interpolated.csv"
    table.to_csv(table_path, index=False, encoding="utf-8")
    table.to_parquet(table_path.with_suffix(".parquet"))
    paths["interpolated_table"] = table_path

    dictionary_path = (
        data_dir / f"{config.REFERENCE_PREFIX}__exposure_interpolated_dictionary.csv"
    )
    dictionary_table(measured).to_csv(dictionary_path, index=False, encoding="utf-8")
    paths["interpolated_dictionary"] = dictionary_path

    log.info(
        "exported the interpolated exposure panel (%d rows) and its dictionary to %s/",
        len(table),
        config.DATA_SUBDIR,
    )
    return paths


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(
    table: pd.DataFrame,
    measured: MeasuredExposure,
    panel: pd.DataFrame,
    units: gpd.GeoDataFrame,
    log: RunLog,
    paths: dict[str, Path] | None = None,
    window: range | None = None,
) -> bool:
    """Check the panel against the table it was built from, and against arithmetic.

    The check that matters is the first one: **an interpolation must not move an
    observation.** Everything after it is arithmetic, and section 6 of
    `docs/interpolating-the-exposure.md` is the list of ways this stage can pass
    all of it and still be useless — which is why the run also reports the
    volatility of the per-unit steps and the comparison against 2005, neither of
    which is a check that can pass or fail.
    """
    window = window or config.STUDY_YEARS
    checks: list[tuple[str, bool, str]] = []

    expected_columns = list(config.interpolated_exposure_columns())
    checks.append((
        "the table carries exactly the declared columns, in the declared order",
        list(table.columns) == expected_columns,
        f"{len(table.columns)} of {len(expected_columns)} declared",
    ))

    expected_units = set(units[config.AREA_CODE_COL])
    checks.append((
        "every row names a unit of the study",
        set(table[config.AREA_CODE_COL]) <= expected_units,
        f"{table[config.AREA_CODE_COL].nunique()} of {len(expected_units)}",
    ))

    key = [config.YEAR_COL, config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]
    checks.append((
        "no combination of unit, year, actor type and day type appears twice",
        not table.duplicated(subset=key).any(),
        f"{int(table.duplicated(subset=key).sum())} duplicated",
    ))

    # The grid, per day type. A day type covers the whole window or it is not in
    # the table at all: what is never allowed is a year of it missing without a
    # word, which is D10 applied to a dimension ragged by construction.
    for day_type in sorted(table[day_col := config.DAY_TYPE_COL].unique()):
        block = table[table[day_col] == day_type]
        actors = measured.table.loc[
            measured.table[day_col] == day_type, config.ACTOR_TYPE_COL
        ].nunique()
        expected_rows = len(expected_units) * actors * len(window)
        checks.append((
            f"{day_type}: the grid of unit, actor type and year is complete over the window",
            len(block) == expected_rows,
            f"{len(block)} rows against {expected_rows} expected "
            f"({len(expected_units)} units x {actors} modes x {len(window)} years)",
        ))

    # **The interpolation must not move an observation.** Every measured year, on
    # every column the two tables share, to the last decimal.
    shared = [
        config.AREA_NAME_COL,
        config.AREA_UNIT_KM2_COL,
        config.POPULATION_COL,
        config.TRIPS_PER_DAY_OF_TYPE_COL,
        config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL,
        config.SAMPLE_SUPPORT_COL,
    ]
    left = measured.table.set_index(key)[shared].sort_index()
    right = table[table[config.EXPOSURE_PROVENANCE_COL] == config.MEASURED_EXPOSURE]
    right = right.set_index(key)[shared].sort_index()
    same_rows = list(left.index) == list(right.index)
    identical = same_rows and all(
        bool(np.array_equal(left[column].to_numpy(), right[column].to_numpy()))
        for column in shared
    )
    checks.append((
        "every measured year comes out identical to the measured table",
        identical,
        f"{len(right)} measured row(s) against {len(left)}, "
        f"{len(shared)} shared column(s), compared bit for bit",
    ))

    # The level is the rate times the population, on both pedestrian definitions.
    # Checked against the columns in the same table, because that is what a reader
    # would recompute it from.
    for level, rate_column in _SERIES.items():
        checks.append((
            f"{level} is {rate_column} times the population of the same unit and year",
            bool(np.allclose(
                (table[rate_column] * table[config.POPULATION_COL]).to_numpy(),
                table[level].to_numpy(),
                rtol=1e-12,
            )),
            f"compared to 1e-12 over {len(table)} row(s)",
        ))

    quantities = [config.POPULATION_COL] + [q.name for q in config.INTERPOLATED_EXPOSURE_QUANTITIES]
    nulls = int(table[quantities].isna().to_numpy().sum())
    negatives = int((table[quantities] < 0).to_numpy().sum())
    checks.append((
        "no null and no negative anywhere a number is required",
        nulls == 0 and negatives == 0,
        f"{nulls} null, {negatives} negative over {len(quantities)} column(s)",
    ))

    # Provenance is a closed vocabulary, and the number of measured years of a
    # series is the number of survey years that measured that kind of day: four
    # for the weekday, three for the Saturday, one for the Sunday.
    undeclared = sorted(set(table[config.EXPOSURE_PROVENANCE_COL]) - set(config.EXPOSURE_PROVENANCES))
    checks.append((
        "every row's provenance is one of the declared three",
        not undeclared,
        ", ".join(
            f"{provenance} {int((table[config.EXPOSURE_PROVENANCE_COL] == provenance).sum()):,}"
            for provenance in config.EXPOSURE_PROVENANCES
        ) + (f"; undeclared: {', '.join(undeclared)}" if undeclared else ""),
    ))

    per_series_ok = True
    detail = []
    for day_type in sorted(table[config.DAY_TYPE_COL].unique()):
        anchors = measured.anchors_of(day_type)
        block = table[table[config.DAY_TYPE_COL] == day_type]
        counted = block[block[config.EXPOSURE_PROVENANCE_COL] == config.MEASURED_EXPOSURE]
        by_series = counted.groupby(_SERIES_KEY).size()
        ok = bool((by_series == len(anchors)).all()) and len(by_series) == block.groupby(
            _SERIES_KEY
        ).ngroups
        per_series_ok = per_series_ok and ok
        detail.append(f"{day_type} {len(anchors)} per series")
    checks.append((
        "each series has exactly as many measured years as surveys measured that day type",
        per_series_ok,
        ", ".join(detail),
    ))

    zero_distance = table[config.YEARS_TO_NEAREST_SURVEY_COL] == 0
    is_measured = table[config.EXPOSURE_PROVENANCE_COL] == config.MEASURED_EXPOSURE
    checks.append((
        "the distance to the nearest survey is zero on the measured years and nowhere else",
        bool((zero_distance == is_measured).all()),
        f"{int((zero_distance & ~is_measured).sum())} constructed row(s) at distance zero, "
        f"{int((~zero_distance & is_measured).sum())} measured row(s) at distance above zero; "
        f"the largest distance is {int(table[config.YEARS_TO_NEAREST_SURVEY_COL].max())} year(s)",
    ))

    # D39's two invariants have to survive the interpolation, and one of them is
    # not obvious: the two definitions are interpolated separately, so nothing in
    # the arithmetic guarantees the narrower one stays inside the wider one on a
    # constructed year. Log-linear interpolation does preserve it — the ratio of
    # two log-linear curves is log-linear between two ratios that are both at most
    # one — but the linear branch a zero rate forces does not have to, and that is
    # exactly why this is checked rather than argued.
    others = table[table[config.ACTOR_TYPE_COL] != config.PEDESTRIAN]
    checks.append((
        "the fifteen-minute column equals the full one on the modes with one definition",
        bool(np.allclose(
            others[config.TRIPS_PER_DAY_OF_TYPE_COL].to_numpy(),
            others[config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL].to_numpy(),
            rtol=1e-12,
        )),
        f"{len(others)} row(s) of {config.BICYCLE}, {config.MOTORCYCLE} and {config.CAR}",
    ))
    walking = table[table[config.ACTOR_TYPE_COL] == config.PEDESTRIAN]
    over_the_whole = int((
        walking[config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL]
        > walking[config.TRIPS_PER_DAY_OF_TYPE_COL] * (1 + 1e-9)
    ).sum())
    checks.append((
        "the fifteen-minute walking of a constructed year is still a part of its walking",
        over_the_whole == 0,
        f"{over_the_whole} row(s) where the part exceeds the whole, over {len(walking)} "
        "walking row(s)",
    ))

    # The denominator is the panel's and not a number this module made up.
    from_panel = panel.set_index([config.AREA_CODE_COL, config.YEAR_COL])[config.POPULATION_COL]
    joined = table.set_index([config.AREA_CODE_COL, config.YEAR_COL])[config.POPULATION_COL]
    aligned = from_panel.reindex(joined.index)
    checks.append((
        "the population of every row is the population panel's for that unit and year",
        bool(np.allclose(joined.to_numpy(), aligned.to_numpy(), rtol=0, atol=0)),
        f"{int(aligned.isna().sum())} row(s) the panel does not cover",
    ))

    if paths:
        written = [path for path in paths.values() if path.exists() and path.stat().st_size > 0]
        checks.append((
            "every exported file is on disk and none is empty",
            len(written) == len(paths),
            f"{len(written)} of {len(paths)}",
        ))

    width = max(len(name) for name, _, _ in checks)
    rendered = [
        f"{'check'.ljust(width)}  {'result':>8}  detail",
        f"{'-' * width}  {'-' * 8}  ------",
    ]
    for name, ok, detail_text in checks:
        rendered.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail_text}")
    log.table("interpolated exposure verification:", "\n".join(rendered))

    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("interpolated exposure verification FAILED")
    return passed


# ---------------------------------------------------------------------------
# The price of interpolating per unit
# ---------------------------------------------------------------------------


def _steps_of(
    rows: pd.DataFrame,
    series_column: str,
    residents: pd.Series,
    anchors: list[int],
) -> pd.DataFrame:
    """One row per unit, mode and pair of adjacent surveys, with the factor between.

    The rate and not the level, because the rate is what is interpolated: a unit
    whose population grew by half between two surveys would show a step the
    interpolation never sees if the level were measured instead.
    """
    rates = rows[series_column].to_numpy() / residents.reindex(
        pd.MultiIndex.from_arrays([rows[config.AREA_CODE_COL], rows[config.YEAR_COL]])
    ).to_numpy()
    wide = rows.assign(_RATE=rates).pivot_table(
        index=[config.AREA_CODE_COL, config.AREA_NAME_COL, config.ACTOR_TYPE_COL],
        columns=config.YEAR_COL,
        values="_RATE",
    )

    steps: list[dict[str, object]] = []
    for before, after in zip(anchors, anchors[1:]):
        for (code, name, actor), row in wide.iterrows():
            start, end = float(row[before]), float(row[after])
            if start > 0 and end > 0:
                factor = max(end / start, start / end)
            elif start == 0 and end == 0:
                factor = 1.0
            else:
                # One end is an observed zero, so no factor exists. It is not a
                # small move and it is not a large one; it is a different kind of
                # step, and calling it infinite would put it at the top of a table
                # of ratios it does not belong in.
                factor = float("nan")
            steps.append(
                {
                    "STEP": f"{before}-{after}",
                    config.AREA_CODE_COL: code,
                    config.AREA_NAME_COL: name,
                    config.ACTOR_TYPE_COL: actor,
                    "RATE_BEFORE": start,
                    "RATE_AFTER": end,
                    "FACTOR": factor,
                    "ANNUAL_CHANGE": (
                        (end / start) ** (1.0 / (after - before)) - 1.0
                        if start > 0 and end > 0
                        else float("nan")
                    ),
                }
            )
    return pd.DataFrame(steps)


def _wide_steps_by_step(steps: pd.DataFrame, actor: str | None = None) -> str:
    """How many steps of one mode exceed the factor, written step by step."""
    rows = steps if actor is None else steps[steps[config.ACTOR_TYPE_COL] == actor]
    return "/".join(
        str(int(((rows["STEP"] == step) & (rows["FACTOR"] > config.EXPOSURE_STEP_FACTOR)).sum()))
        for step in sorted(rows["STEP"].unique())
    )


def step_volatility(
    measured: MeasuredExposure,
    panel: pd.DataFrame,
    log: RunLog,
    day_type: str = config.WEEKDAY_TYPE,
) -> pd.DataFrame:
    """How far each unit's rate moves between two adjacent surveys.

    This is the price of interpolating per unit and the run prints it on every
    execution. **It does not fail on it**: a rate that really did multiply by nine
    in four years is possible — Chapinero's cycling is one, and 2019 and 2023 hold
    the higher level — and no check can tell a real change from sampling noise.
    What is not acceptable is producing three constructed years on top of a step
    like that without saying so.

    Measured on the rate, because the rate is what is interpolated, and on
    `TRIPS_PER_DAY_OF_TYPE_OVER_15MIN`, because that is the column the series is
    read on for every mode: it is the narrower pedestrian definition and it is the
    same number as the full one for the other three (D39).

    Whether the trajectories need shrinking toward the city's is a question for a
    person, and it is asked with this table in hand rather than answered by
    smoothing quietly.
    """
    series_column = config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL
    rows = measured.table[measured.table[config.DAY_TYPE_COL] == day_type].copy()
    if rows.empty:
        return pd.DataFrame()

    residents = panel.set_index([config.AREA_CODE_COL, config.YEAR_COL])[config.POPULATION_COL]
    anchors = sorted(rows[config.YEAR_COL].unique())
    table = _steps_of(rows, series_column, residents, anchors)

    wide_steps = table[table["FACTOR"] > config.EXPOSURE_STEP_FACTOR]
    counts = (
        wide_steps.pivot_table(
            index="STEP", columns=config.ACTOR_TYPE_COL, values="FACTOR", aggfunc="size"
        )
        .reindex(columns=[actor for actor in config.ROAD_USER_TYPES if actor in set(table[config.ACTOR_TYPE_COL])])
        .fillna(0)
        .astype(int)
    )
    rendered = [
        f"{'step':>10}  " + "  ".join(f"{actor:>12}" for actor in counts.columns),
        f"{'-' * 10}  " + "  ".join("-" * 12 for _ in counts.columns),
    ]
    for step, row in counts.iterrows():
        rendered.append(f"{step:>10}  " + "  ".join(f"{int(value):>12}" for value in row))
    log.table(
        f"how far a unit's rate moves between two adjacent surveys, {day_type.lower()}, on "
        f"{series_column} — combinations moving by more than a factor of "
        f"{config.EXPOSURE_STEP_FACTOR:g}, out of {len(table)}:",
        "\n".join(rendered),
    )

    widest = table.nlargest(config.EXPOSURE_WIDEST_STEPS_REPORTED, "FACTOR")
    lines = [
        f"{'step':>10}  {'unit':>28}  {'mode':>11}  {'factor':>7}  {'per year':>9}",
        f"{'-' * 10}  {'-' * 28}  {'-' * 11}  {'-' * 7}  {'-' * 9}",
    ]
    for _, row in widest.iterrows():
        lines.append(
            f"{row['STEP']:>10}  "
            f"{row[config.AREA_CODE_COL] + ' ' + str(row[config.AREA_NAME_COL]):>28}  "
            f"{row[config.ACTOR_TYPE_COL]:>11}  {row['FACTOR']:>7.2f}  "
            f"{row['ANNUAL_CHANGE']:>+8.1%}"
        )
    log.table(
        f"the {len(widest)} widest steps, and what log-linear interpolation makes of each of "
        "them in every constructed year of that segment:",
        "\n".join(lines),
    )

    total_wide = len(wide_steps)
    by_step = wide_steps["STEP"].value_counts()
    worst_step = by_step.idxmax() if len(by_step) else "none"
    log.warn(
        "%d of the %d unit x mode x step combinations of the %s move by more than a factor of "
        "%g between adjacent surveys, and %d of them are on the %s step. The interpolation runs "
        "straight through every one of them, and the run does not fail on it: part of the "
        "change is real. Whether the per-unit trajectories need shrinking toward the city's is "
        "a decision for a person, and this is the table it is asked with. See D40",
        total_wide,
        len(table),
        day_type.lower(),
        config.EXPOSURE_STEP_FACTOR,
        int(by_step.max()) if len(by_step) else 0,
        worst_step,
    )

    undefined = int(table["FACTOR"].isna().sum())
    if undefined:
        log.info(
            "%d combination(s) have an observed zero at one end of a step, so no factor exists "
            "for them and they are in none of the counts above; those segments are the ones "
            "filled linearly rather than log-linearly",
            undefined,
        )

    # The same table on the full pedestrian column, for the one mode where the two
    # definitions differ. It is not an alternative measurement — the series is read
    # on the narrower column and this table is about that series — but the figure
    # first recorded for it was measured on the full column, and a table that moved
    # without saying which column it moved on would be two measurements sharing a
    # name.
    full = _steps_of(rows, config.TRIPS_PER_DAY_OF_TYPE_COL, residents, anchors)
    log.info(
        "measured on the full pedestrian column instead, %s contributes %d of these rather than "
        "%d, by step %s against %s. The other three modes carry the same number in both "
        "columns, so walking is the whole difference between the two versions of this table",
        config.PEDESTRIAN,
        int((
            (full[config.ACTOR_TYPE_COL] == config.PEDESTRIAN)
            & (full["FACTOR"] > config.EXPOSURE_STEP_FACTOR)
        ).sum()),
        int((
            (table[config.ACTOR_TYPE_COL] == config.PEDESTRIAN)
            & (table["FACTOR"] > config.EXPOSURE_STEP_FACTOR)
        ).sum()),
        _wide_steps_by_step(full, config.PEDESTRIAN),
        _wide_steps_by_step(table, config.PEDESTRIAN),
    )
    return table


# ---------------------------------------------------------------------------
# Against what 2005 published
# ---------------------------------------------------------------------------


def compare_with_2005(
    measured: MeasuredExposure,
    table: pd.DataFrame,
    panel: pd.DataFrame,
    log: RunLog,
    reference: config.PublishedYear | None = None,
) -> pd.DataFrame:
    """The held block against the only survey older than the study's first one.

    This is the test D40 defers the 2005 survey on, and it is a measurement rather
    than an argument: the interpolation is built on four years, the held rate
    produces a 2007-2010 block, and that block is compared against the figures the
    2011 delivery publishes for 2005. If it lands far from them, 2005 is worth
    implementing and the reason for implementing it is a number.

    **It is made on the whole surveyed region and not on the thirty units**, which
    is not a convenience. Every figure the deliveries publish is stated on that
    territory, and the share of a mode that reaches the units differs by mode and
    by year — 53 % of 2011's cycling against 75 % of its car travel — so comparing
    a per-unit composition against a published one would measure the funnel and
    call it a change in the city. What makes the region comparison transfer to the
    panel is that the held block carries the anchor year's composition by
    construction, and the run checks how far that is from true.

    The control is what makes any of it safe: the same source publishes 2011, this
    study read 2011, and if the two disagree about 2011 then nothing can be
    concluded about 2005.
    """
    reference = reference or config.PUBLISHED_2005
    series_column = config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL
    modes = [actor for actor in config.ROAD_USER_TYPES if actor in reference.mode_shares]
    control_year = reference.control_year

    log.info(
        "comparing the held block against %s. Source: %s. Both years count %s",
        reference.label,
        reference.source,
        reference.definition,
    )

    # -- the control -------------------------------------------------------
    region = measured.city_totals
    anchor = region[
        (region[config.YEAR_COL] == control_year)
        & (region[config.DAY_TYPE_COL] == config.WEEKDAY_TYPE)
        & (region[config.ACTOR_TYPE_COL].isin(modes))
    ]
    if len(anchor) != len(modes):
        raise ValueError(
            f"the exported region totals do not cover the four modes of {control_year} on a "
            f"{config.WEEKDAY_TYPE}, so the comparison has no control to rest on"
        )
    ours = anchor.set_index(config.ACTOR_TYPE_COL)[series_column].reindex(modes)
    ours_share = ours / ours.sum()

    published_control = pd.Series(reference.control_mode_shares).reindex(modes)
    published_control = published_control / published_control.sum()
    control_gap = float((ours_share - published_control).abs().max()) * 100

    lines = [
        f"{'mode':>11}  {'published ' + str(control_year):>15}  {'this study':>11}  {'gap':>7}",
        f"{'-' * 11}  {'-' * 15}  {'-' * 11}  {'-' * 7}",
    ]
    for mode in modes:
        lines.append(
            f"{mode:>11}  {published_control[mode]:>15.1%}  {ours_share[mode]:>11.1%}  "
            f"{(ours_share[mode] - published_control[mode]) * 100:>+6.1f}"
        )
    log.table(
        f"the control: how the {len(modes)} modes of this study divide between themselves in "
        f"{control_year}, as the source publishes it and as this study measures it — both over "
        "the whole surveyed region, which is the only footprint the two share:",
        "\n".join(lines),
    )
    if control_gap > 2.0:
        log.warn(
            "the study and the source disagree about %d by up to %.1f points, so nothing can be "
            "concluded from the %d column below: the comparison rests on the two readings "
            "agreeing about the year they share",
            control_year,
            control_gap,
            reference.year,
        )
    else:
        log.info(
            "the two readings of %d agree to %.1f point(s) at worst, so the %d column below is "
            "being compared against something",
            control_year,
            control_gap,
            reference.year,
        )

    # -- does the held block carry the anchor's composition? ---------------
    # It has to, or the region comparison says nothing about the panel. It is not
    # exactly the anchor's, because the thirty units grow at different rates and a
    # composition of levels moves with them; the run measures how far.
    first_year = int(table[config.YEAR_COL].min())
    weekday = table[
        (table[config.DAY_TYPE_COL] == config.WEEKDAY_TYPE)
        & (table[config.ACTOR_TYPE_COL].isin(modes))
    ]
    inside = weekday.pivot_table(
        index=config.YEAR_COL, columns=config.ACTOR_TYPE_COL, values=series_column, aggfunc="sum"
    )[modes]
    inside = inside.div(inside.sum(axis=1), axis=0)
    drift = float((inside.loc[first_year] - inside.loc[control_year]).abs().max()) * 100
    log.info(
        "inside the thirty units the held block's composition at %d differs from the anchor's "
        "at %d by %.2f point(s) at most, which is the different pace at which the units grow "
        "and nothing else — holding a rate flat holds the composition with it, so the region "
        "comparison below transfers to the panel",
        first_year,
        control_year,
        drift,
    )

    # -- the test ----------------------------------------------------------
    published_old = pd.Series(reference.mode_shares).reindex(modes)
    published_old = published_old / published_old.sum()

    lines = [
        f"{'mode':>11}  {'published ' + str(reference.year):>15}  "
        f"{'held block':>11}  {'gap':>7}",
        f"{'-' * 11}  {'-' * 15}  {'-' * 11}  {'-' * 7}",
    ]
    for mode in modes:
        lines.append(
            f"{mode:>11}  {published_old[mode]:>15.1%}  {ours_share[mode]:>11.1%}  "
            f"{(ours_share[mode] - published_old[mode]) * 100:>+6.1f}"
        )
    log.table(
        f"and the test: the same composition in {reference.year} as published, against what the "
        f"held block carries. The held block cannot differ from {control_year} at all, because "
        "holding the rate flat holds the composition with it:",
        "\n".join(lines),
    )

    # -- growth, which is what the held rate actually asserts ---------------
    span = control_year - reference.year
    residents = panel.groupby(config.YEAR_COL)[config.POPULATION_COL].sum()
    demographic = float(residents[control_year] / residents[first_year]) ** (
        span / (control_year - first_year)
    )

    rounding = reference.share_rounding
    rows = []
    for mode in modes:
        old_share = reference.mode_shares[mode]
        new_share = reference.control_mode_shares[mode]
        old_level = old_share * reference.total_trips_per_weekday
        new_level = new_share * reference.control_total_trips_per_weekday
        rows.append(
            {
                "MODE": mode,
                f"PUBLISHED_{reference.year}": old_level,
                f"PUBLISHED_{control_year}": new_level,
                "PUBLISHED_GROWTH": new_level / old_level,
                # The shares are labels on a pie chart, in whole per cent. Half a
                # point of rounding is nothing at 46 % and half the value at 1 %, so
                # the factor is a band and quoting its midpoint alone would claim a
                # precision the source does not have.
                "GROWTH_LOW": (
                    (new_share - rounding) * reference.control_total_trips_per_weekday
                ) / ((old_share + rounding) * reference.total_trips_per_weekday),
                "GROWTH_HIGH": (
                    (new_share + rounding) * reference.control_total_trips_per_weekday
                ) / ((old_share - rounding) * reference.total_trips_per_weekday),
                "HELD_GROWTH": demographic,
            }
        )
    growth = pd.DataFrame(rows)
    growth["CONTRADICTED"] = growth["GROWTH_LOW"] > growth["HELD_GROWTH"]

    lines = [
        f"{'mode':>11}  {str(reference.year):>12}  {str(control_year):>12}  "
        f"{'published':>10}  {'band':>16}  {'held':>7}  ",
        f"{'-' * 11}  {'-' * 12}  {'-' * 12}  {'-' * 10}  {'-' * 16}  {'-' * 7}  ",
    ]
    for _, row in growth.iterrows():
        lines.append(
            f"{row['MODE']:>11}  {row[f'PUBLISHED_{reference.year}']:>12,.0f}  "
            f"{row[f'PUBLISHED_{control_year}']:>12,.0f}  {row['PUBLISHED_GROWTH']:>10.2f}x  "
            f"{row['GROWTH_LOW']:>7.2f}x-{row['GROWTH_HIGH']:<7.2f}  {row['HELD_GROWTH']:>6.2f}x  "
            + ("contradicts the held rate" if row["CONTRADICTED"] else "consistent with it")
        )
    log.table(
        f"what the level did between {reference.year} and {control_year}, as published, against "
        f"what the held rate implies it did over the same span — which is the population and "
        "nothing else, because a held rate moves only with its denominator. The band is what "
        "the shares' rounding allows:",
        "\n".join(lines),
    )

    contradicted = list(growth.loc[growth["CONTRADICTED"], "MODE"])
    log.info(
        "%d of the %d modes contradict the held rate even at the most forgiving end of their "
        "rounding: %s. The others are %s",
        len(contradicted),
        len(modes),
        ", ".join(contradicted) or "none",
        ", ".join(sorted(set(modes) - set(contradicted))) or "none",
    )

    # -- the rate itself, which is the quantity being held ------------------
    index = config.PUBLISHED_2005_TRIPS_PER_PERSON
    if index:
        moves = [after / before for before, after in index.values()]
        log.warn(
            "the same chapter publishes trips per person for %d and %d, by socioeconomic "
            "stratum: %s. Every one of them rises, by %.0f%% to %.0f%% over %d years, %.0f%% on "
            "the median. THE HELD BLOCK ASSERTS THAT THIS QUANTITY DID NOT MOVE AT ALL, because "
            "holding a rate flat is holding trips per person flat. That is the assumption the "
            "%d-%d block rests on and it is the one the source contradicts most directly. See "
            "D40",
            reference.year,
            control_year,
            "; ".join(
                f"{name} {before:.2f}->{after:.2f}" for name, (before, after) in index.items()
            ),
            100 * (min(moves) - 1),
            100 * (max(moves) - 1),
            span,
            100 * (float(np.median(moves)) - 1),
            first_year,
            min(config.STUDY_YEARS) + 3,
        )

    for caveat in reference.caveats:
        log.info("caveat on the %d comparison: %s", reference.year, caveat)

    return growth


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def report(table: pd.DataFrame, measured: MeasuredExposure, log: RunLog) -> None:
    """What the panel holds, for whoever reads the log instead of the table."""
    census = table[config.EXPOSURE_PROVENANCE_COL].value_counts()
    log.info(
        "the panel is %d rows: %s. %d of them are constructed, which is %.0f%% of the table",
        len(table),
        ", ".join(
            f"{provenance} {int(census.get(provenance, 0)):,}"
            for provenance in config.EXPOSURE_PROVENANCES
        ),
        len(table) - int(census.get(config.MEASURED_EXPOSURE, 0)),
        100 * (1 - census.get(config.MEASURED_EXPOSURE, 0) / len(table)),
    )

    thin = int((table[config.SAMPLE_SUPPORT_COL] == config.SAMPLE_CITY_LEVEL_ONLY).sum())
    if thin:
        by_day = (
            table[table[config.SAMPLE_SUPPORT_COL] == config.SAMPLE_CITY_LEVEL_ONLY]
            .groupby(config.DAY_TYPE_COL)
            .size()
        )
        log.warn(
            "%d row(s) rest on a survey year the consultant only ever claimed at the scale of "
            "the city, and they are not an estimate of the same kind as the rest: %s. A "
            "constructed value inherits the weaker support of the anchors it was built from, "
            "which is why the block reaches years the marked survey did not measure",
            thin,
            "; ".join(f"{day} {int(count):,}" for day, count in by_day.items()),
        )

    # The city curve, which is what a reader will look at first and the one thing
    # the table must not have been built from. It is printed on the column the
    # series is read on, and the provenance of each year is printed beside it so
    # that four measured years cannot be read as eighteen.
    series_column = config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL
    weekday = table[table[config.DAY_TYPE_COL] == config.WEEKDAY_TYPE]
    actors = [actor for actor in config.ROAD_USER_TYPES if actor in set(weekday[config.ACTOR_TYPE_COL])]
    totals = weekday.pivot_table(
        index=config.YEAR_COL, columns=config.ACTOR_TYPE_COL, values=series_column, aggfunc="sum"
    )[actors]
    provenance = weekday.groupby(config.YEAR_COL)[config.EXPOSURE_PROVENANCE_COL].first()

    lines = [
        f"{'year':>6}  {'':>13}  " + "  ".join(f"{actor:>12}" for actor in actors),
        f"{'-' * 6}  {'-' * 13}  " + "  ".join("-" * 12 for _ in actors),
    ]
    for year, row in totals.iterrows():
        lines.append(
            f"{year:>6}  {provenance[year]:>13}  "
            + "  ".join(f"{value:>12,.0f}" for value in row)
        )
    log.table(
        f"the interpolated exposure of the thirty units, one weekday, on {series_column} — the "
        "column the series is read on for all four modes:",
        "\n".join(lines),
    )

    held = table[table[config.EXPOSURE_PROVENANCE_COL] == config.HELD_EXPOSURE]
    if len(held):
        # Per day type, because the held years are not the same for all three and a
        # single list of years reads as though the whole table were held: the
        # weekday and the Saturday are held at their two ends, and the Sunday is
        # held everywhere except the one year that measured it.
        blocks = []
        for day_type, rows in held.groupby(config.DAY_TYPE_COL):
            years = sorted(rows[config.YEAR_COL].unique())
            spans = []
            start = previous = years[0]
            for year in years[1:] + [None]:
                if year == previous + 1 if year is not None else False:
                    previous = year
                    continue
                spans.append(str(start) if start == previous else f"{start}-{previous}")
                if year is not None:
                    start = previous = year
            blocks.append(f"{day_type} {len(rows):,} row(s) over {', '.join(spans)}")
        log.info(
            "the held block is %d row(s): %s. Its rate does not move at all and its level moves "
            "only with the population, so it carries demographic variation and no behavioural "
            "variation. Whether it belongs in the models is open, and %s is in the table so "
            "that it can be tested rather than assumed",
            len(held),
            "; ".join(blocks),
            config.YEARS_TO_NEAREST_SURVEY_COL,
        )
