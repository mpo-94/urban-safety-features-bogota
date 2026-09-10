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

    def anchors_of(
        self, day_type: str, level: str | None = None, actor: str | None = None
    ) -> tuple[int, ...]:
        """The survey years that measured one kind of day, on one column.

        Read from the table rather than from the survey declarations, because the
        table is what this stage interpolates and a day type declared but absent
        from it would be a series with no anchors at all.

        **A year may measure a column and still not anchor it.** 2005 collected no
        walk under fifteen minutes, so its `TRIPS_PER_DAY_OF_TYPE` holds long
        walking where every other year's holds all walking; interpolating across
        that boundary would spread the difference of definition as growth, at 34 %
        a year through 2007-2010 against the 18 % the comparable column reads. The
        value is in the table because the measured table is a record. What keeps it
        out of the interpolation is `not_comparable_on`, declared per year and per
        column, and asked for here.

        `level` of None returns every year present, which is what the grid and the
        provenance are built from.
        """
        rows = self.table[self.table[config.DAY_TYPE_COL] == day_type]
        years = sorted(rows[config.YEAR_COL].unique())
        if level is None:
            return tuple(years)
        excluded = {
            survey.year
            for survey in config.MOBILITY_SURVEYS
            if level in survey.not_comparable_on
            and (actor is None or actor in survey.not_comparable_on[level].actor_types)
        }
        return tuple(year for year in years if year not in excluded)


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

    # Every year of the window, and every year that anchors it. 2005 is the first
    # anchor to sit outside the window and the rate at an anchor is formed with
    # that anchor's own population, so a panel built over the window alone would
    # fail at the moment of forming the rate rather than at the moment of building
    # the panel — far from where the cause is. See `config.population_years`.
    anchor_years = {
        year
        for day_type in config.DAY_TYPES
        if day_type in set(table[config.DAY_TYPE_COL])
        for year in measured.anchors_of(day_type)
    }
    populations = {
        year: population.for_year(panel, year) for year in sorted(set(window) | anchor_years)
    }
    support_by_year = {
        (row[config.AREA_CODE_COL], row[config.ACTOR_TYPE_COL], row[config.DAY_TYPE_COL], row[config.YEAR_COL]):
        row[config.SAMPLE_SUPPORT_COL]
        for _, row in table.iterrows()
    }

    day_types = [day for day in config.DAY_TYPES if day in set(table[config.DAY_TYPE_COL])]
    anchors_by_day = {day: measured.anchors_of(day) for day in day_types}
    # One set of anchors per level, because a year may measure a column without
    # being comparable on it. The provenance and the distance to the nearest survey
    # follow the column the series is read on, which is D39's: a row says how its
    # pedestrian series was built, and the other column of that row carries a note
    # in the dictionary rather than a second provenance column nobody would read.
    anchors_by_level = {
        day: {
            (level, actor): measured.anchors_of(day, level, actor)
            for level in _SERIES
            for actor in sorted(table[config.ACTOR_TYPE_COL].unique())
        }
        for day in day_types
    }
    series_level = config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL

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
                        # A year that measures the column but is not comparable on
                        # it contributes its value to the table and not to the
                        # curve.
                        if year in anchors_by_level[day_type][(level, actor)]:
                            rates[level][year] = float(cell[level]) / residents

                filled = {
                    level: fill_series(rates[level], window) for level in _SERIES
                }
                for level in _SERIES:
                    linear_cells[level] += sum(
                        1 for value in filled[level].values() if value.linear_because_of_a_zero
                    )

                shape = filled[series_level]
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
    # Only the measured years the window contains. 2005 is measured and is not in
    # the panel, because the casualty series starts in 2007 and the window follows
    # it; an anchor outside the window shapes the curve and has no row of its own.
    inside = measured.table[measured.table[config.YEAR_COL].isin(list(window))]
    left = inside.set_index(key)[shared].sort_index()
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
        # The anchors the window contains, which is what can carry a MEASURED row.
        anchors = [
            year for year in measured.anchors_of(day_type) if year in set(window)
        ]
        outside = len(measured.anchors_of(day_type)) - len(anchors)
        block = table[table[config.DAY_TYPE_COL] == day_type]
        counted = block[block[config.EXPOSURE_PROVENANCE_COL] == config.MEASURED_EXPOSURE]
        by_series = counted.groupby(_SERIES_KEY).size()
        ok = bool((by_series == len(anchors)).all()) and len(by_series) == block.groupby(
            _SERIES_KEY
        ).ngroups
        per_series_ok = per_series_ok and ok
        detail.append(
            f"{day_type} {len(anchors)} per series"
            + (f" and {outside} outside the window" if outside else "")
        )
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
    """This study's reading of 2005 against what 2005 published.

    **This function used to test an assumption and now controls a measurement**,
    and the change is what implementing the year did to it. While 2005 was not
    read, D40 held the rate flat before 2011 and this compared that held block
    against the figures the 2011 delivery publishes for 2005; the block landed 15
    to 19 points away, which is the number that decided the year was worth
    implementing. There is no held weekday block any more — 2007 to 2010 are
    interpolated between 2005 and 2011 — so testing it would be testing 2005
    against itself.

    What is worth doing instead is what every other year gets: **read the year,
    then check the reading against what the year published.** The control is the
    same shape as before — how the four modes divide between themselves, over the
    whole surveyed region, which is the only footprint this study and a
    publication share — and it is made twice, once on the year whose reading is
    already trusted and once on the year just added.

    Both are made **before this study's removals**, because a publication does not
    make them: the transfer legs and the walks under the floor are in the
    published totals and are named separately in the balance.
    """
    reference = reference or config.PUBLISHED_2005
    modes = [actor for actor in config.ROAD_USER_TYPES if actor in reference.mode_shares]
    region = measured.city_totals
    # On the fifteen-minute column and not the full one, because that is the
    # partition the source publishes on: the chapter states that everything in it
    # counts trips "incluyendo los viajes a pie mayores o iguales a quince (15)
    # minutos". Comparing 2011's full walking against a fifteen-minute pie puts the
    # control eighteen points out and blames the reading for the difference.
    level = config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL

    log.info(
        "checking this study's reading of %d and %d against %s. Source: %s. Both count %s",
        reference.year,
        reference.control_year,
        reference.label,
        reference.source,
        reference.definition,
    )

    def composition(year: int) -> pd.Series:
        rows = region[
            (region[config.YEAR_COL] == year)
            & (region[config.DAY_TYPE_COL] == config.WEEKDAY_TYPE)
            & (region[config.ACTOR_TYPE_COL].isin(modes))
        ]
        if len(rows) != len(modes):
            raise ValueError(
                f"the exported region totals do not cover the {len(modes)} modes of {year} on a "
                f"{config.WEEKDAY_TYPE}, so there is nothing to control against"
            )
        ours = rows.set_index(config.ACTOR_TYPE_COL)[level].reindex(modes)
        return ours / ours.sum()

    published = {
        reference.control_year: pd.Series(reference.control_mode_shares).reindex(modes),
        reference.year: pd.Series(reference.mode_shares).reindex(modes),
    }
    rows = []
    for year, shares in published.items():
        shares = shares / shares.sum()
        ours = composition(year)
        for mode in modes:
            rows.append(
                {
                    config.YEAR_COL: year,
                    "MODE": mode,
                    "PUBLISHED": float(shares[mode]),
                    "THIS_STUDY": float(ours[mode]),
                    "GAP_POINTS": 100 * float(ours[mode] - shares[mode]),
                }
            )
    control = pd.DataFrame(rows)

    lines = [
        f"{'year':>6}  {'mode':>11}  {'published':>10}  {'this study':>11}  {'gap':>7}",
        f"{'-' * 6}  {'-' * 11}  {'-' * 10}  {'-' * 11}  {'-' * 7}",
    ]
    for _, row in control.iterrows():
        lines.append(
            f"{row[config.YEAR_COL]:>6}  {row['MODE']:>11}  {row['PUBLISHED']:>10.1%}  "
            f"{row['THIS_STUDY']:>11.1%}  {row['GAP_POINTS']:>+6.1f}"
        )
    log.table(
        "how the four modes divide between themselves, as the source publishes it and as this "
        "study reads it, over the whole surveyed region and before this study's removals:",
        "\n".join(lines),
    )

    worst = control.groupby(config.YEAR_COL)["GAP_POINTS"].apply(lambda g: g.abs().max())
    log.info(
        "worst gap by year: %s",
        "; ".join(f"{year} {gap:.1f} point(s)" for year, gap in worst.items()),
    )
    loose = worst[worst > 2.0]
    if len(loose):
        log.warn(
            "this study's reading of %s sits more than two points from the published "
            "composition: %s. Both years are read by one piece of code from two deliveries, so a "
            "gap that differs between them is a property of the delivery or of the publication "
            "rather than of the reading. For 2005 the category that was never pinned is the "
            "private vehicle, whose published share is a whole per cent read off a pie chart and "
            "whose composition — whether the delivery's \"bus privado / de compania\" belongs in "
            "it — the source never states. See section 11 of docs/implementing-2005.md",
            ", ".join(str(year) for year in loose.index),
            "; ".join(f"{year} at {gap:.1f}" for year, gap in loose.items()),
        )

    # And the growth between them, which the composition cannot show: a mode may
    # hold its share while the whole grew by half.
    span = reference.control_year - reference.year
    lines = [
        f"{'mode':>11}  {'published':>10}  {'this study':>11}  {'per year, published':>19}",
        f"{'-' * 11}  {'-' * 10}  {'-' * 11}  {'-' * 19}",
    ]
    for mode in modes:
        old_level = reference.mode_shares[mode] * reference.total_trips_per_weekday
        new_level = reference.control_mode_shares[mode] * reference.control_total_trips_per_weekday
        ours_old = float(
            region[
                (region[config.YEAR_COL] == reference.year)
                & (region[config.DAY_TYPE_COL] == config.WEEKDAY_TYPE)
                & (region[config.ACTOR_TYPE_COL] == mode)
            ][level].iloc[0]
        )
        ours_new = float(
            region[
                (region[config.YEAR_COL] == reference.control_year)
                & (region[config.DAY_TYPE_COL] == config.WEEKDAY_TYPE)
                & (region[config.ACTOR_TYPE_COL] == mode)
            ][level].iloc[0]
        )
        lines.append(
            f"{mode:>11}  {new_level / old_level:>9.2f}x  {ours_new / ours_old:>10.2f}x  "
            f"{(new_level / old_level) ** (1 / span) - 1:>+18.1%}"
        )
    log.table(
        f"and what each mode did between {reference.year} and {reference.control_year}, as "
        "published and as this study reads it:",
        "\n".join(lines),
    )

    for caveat in reference.caveats:
        log.info("caveat on the %d comparison: %s", reference.year, caveat)

    return control


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


# ---------------------------------------------------------------------------
# The panel against the casualty series
# ---------------------------------------------------------------------------


CASUALTY_TABLE_FILENAME = f"{config.ANALYSIS_PREFIX}__matrix_long.parquet"
CORRECTED_CASUALTY_TABLE_FILENAME = (
    f"{config.ANALYSIS_PREFIX}__matrix_long__{config.CORRECTION_FILE_SUFFIX}.parquet"
)


@dataclass(frozen=True)
class Casualties:
    """The two casualty datasets and the run they were read from.

    Both together or neither: the diagnostic is worth making because the difference
    between the two versions separates what the recording change did from
    everything else, and one of them alone cannot show that.
    """

    by_dataset: dict[str, pd.DataFrame]
    source_run: str


def read_casualties(log: RunLog, run: str | None = None) -> Casualties | None:
    """The observed and corrected casualty matrices, from a run that holds both.

    Returns None rather than raising when no run holds them, because the panel does
    not need this: the interpolation is complete without it and forcing a matrix run
    in order to interpolate an exposure would be the wrong coupling. What is not
    acceptable is skipping it silently, so the run says what it could not do and
    which route would produce it.
    """
    try:
        run_dir = config.run_directory_holding(CORRECTED_CASUALTY_TABLE_FILENAME, run)
    except FileNotFoundError as absent:
        log.warn(
            "the panel was not compared against the casualty series: %s. Run "
            "`python -m src.run_pipeline corrected`, which writes both datasets, and run this "
            "route again. The panel itself is complete without it",
            absent,
        )
        return None

    frames: dict[str, pd.DataFrame] = {}
    for dataset, filename in (
        (config.OBSERVED_DATASET, CASUALTY_TABLE_FILENAME),
        (config.CORRECTED_DATASET, CORRECTED_CASUALTY_TABLE_FILENAME),
    ):
        path = run_dir / config.DATA_SUBDIR / filename
        if not path.exists():
            log.warn(
                "%s holds %s but not %s, so only one of the two casualty datasets is available "
                "and the diagnostic is skipped: the point of it is the difference between them",
                run_dir.name,
                CORRECTED_CASUALTY_TABLE_FILENAME,
                filename,
            )
            return None
        frames[dataset] = pd.read_parquet(path)

    log.info(
        "read the casualty matrices of %s: %s",
        run_dir.name,
        "; ".join(
            f"{dataset} {len(frame):,} rows over {int(frame[config.YEAR_COL].min())}-"
            f"{int(frame[config.YEAR_COL].max())}"
            for dataset, frame in frames.items()
        ),
    )
    return Casualties(by_dataset=frames, source_run=run_dir.name)


def build_diagnostic(
    panel: pd.DataFrame,
    casualties: Casualties,
    measured: MeasuredExposure,
    log: RunLog,
) -> pd.DataFrame:
    """What the panel implies about risk, and what smooth risk would imply about exposure.

    D40's third external check, and the one that answers "where is the panel least
    believable" with a year and a unit rather than an impression.

    Four quantities per unit, mode, year and casualty dataset. The **implied risk**
    is the casualty count over the exposure the panel carries — what the study will
    be dividing by when it fits a model, so it is not a hypothetical. The **smooth
    risk** is that same quantity carried across the constructed years by the rule
    D40 applies to the exposure, log-linear between surveys and flat outside them.
    The **implied exposure** is the casualty count over the smooth risk: the
    exposure that would follow from assuming the risk is smooth rather than the
    exposure. And the **ratio** between the two exposures is the diagnostic.

    That ratio reads two ways and they are the same number, which is what makes it
    worth exporting:

        implied exposure / interpolated exposure = implied risk / smooth risk

    So one column answers both "how much would the exposure have to move under the
    opposite assumption" and "how far does the risk this panel implies depart from a
    smooth path". It is one at every survey year by construction, and its distance
    from one in a constructed year is exactly how much of the movement the panel is
    putting into the risk rather than into the exposure.

    **It enters no model.** See D41 and the note beside
    `config.EXPOSURE_DIAGNOSTIC_FILENAME`.
    """
    series_column = config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL
    # A casualty count is annual and carries no kind of day, so it is paired with
    # the weekday exposure and the pairing is declared rather than inferred. The
    # diagnostic is a ratio of ratios, so the choice cancels as long as the day-type
    # mix does not move — which nothing in the panel says it does, all three day
    # types resting on the same anchors.
    weekday = panel[panel[config.DAY_TYPE_COL] == config.WEEKDAY_TYPE]
    exposure = weekday.set_index(
        [config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.YEAR_COL]
    )[[series_column, config.EXPOSURE_PROVENANCE_COL, config.YEARS_TO_NEAREST_SURVEY_COL]]

    anchors = [
        year
        for year in measured.anchors_of(config.WEEKDAY_TYPE)
    ]

    blocks: list[pd.DataFrame] = []
    undefined = 0
    for dataset, matrix in casualties.by_dataset.items():
        counted = (
            matrix.groupby(
                [config.AREA_CODE_COL, config.PARTY_TYPE_COL, config.YEAR_COL], as_index=False
            )[config.AFFECTED_PARTIES_COL]
            .sum()
            .rename(columns={config.PARTY_TYPE_COL: config.ACTOR_TYPE_COL})
        )
        # Only the four modes the exposure measures. PUBLIC_TRANSPORT and OTHER are
        # in the matrix and have no exposure to be divided by, which is D38's
        # decision and not a gap here.
        counted = counted[counted[config.ACTOR_TYPE_COL].isin(set(panel[config.ACTOR_TYPE_COL]))]
        window = range(
            int(counted[config.YEAR_COL].min()), int(counted[config.YEAR_COL].max()) + 1
        )

        joined = counted.join(
            exposure,
            on=[config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.YEAR_COL],
            how="inner",
        )
        joined[config.IMPLIED_RISK_COL] = (
            joined[config.AFFECTED_PARTIES_COL] / joined[series_column]
        )

        smooth: list[float] = []
        for (code, actor), rows in joined.groupby(
            [config.AREA_CODE_COL, config.ACTOR_TYPE_COL], sort=False
        ):
            by_year = rows.set_index(config.YEAR_COL)[config.IMPLIED_RISK_COL]
            measured_risk = {
                year: float(by_year[year]) for year in anchors if year in by_year.index
            }
            filled = fill_series(measured_risk, window)
            smooth.extend(filled[int(year)].rate for year in rows[config.YEAR_COL])
        joined[config.SMOOTH_RISK_COL] = smooth

        # A smooth risk of exactly zero means both anchors of the segment saw no
        # casualty of that type in that unit. Dividing by it would be inventing an
        # infinite exposure out of an observed zero, so the two derived columns are
        # left empty and the run counts them.
        possible = joined[config.SMOOTH_RISK_COL] > 0
        undefined += int((~possible).sum())
        joined[config.IMPLIED_EXPOSURE_COL] = np.where(
            possible,
            joined[config.AFFECTED_PARTIES_COL] / joined[config.SMOOTH_RISK_COL].where(possible),
            np.nan,
        )
        joined[config.EXPOSURE_RATIO_COL] = (
            joined[config.IMPLIED_EXPOSURE_COL] / joined[series_column]
        )
        joined[config.DATASET_COL] = dataset
        blocks.append(joined)

    table = pd.concat(blocks, ignore_index=True)

    names = panel[[config.AREA_CODE_COL, config.AREA_NAME_COL]].drop_duplicates()
    table = table.merge(names, on=config.AREA_CODE_COL, how="left")
    table[config.SCALE_COL] = config.active_scale().label
    table = (
        table[list(config.exposure_diagnostic_columns())]
        .sort_values(
            [config.DATASET_COL, config.YEAR_COL, config.AREA_CODE_COL, config.ACTOR_TYPE_COL],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    # The identity the docstring rests on, checked rather than asserted: the ratio of
    # the two exposures is the ratio of the two risks. If it ever stopped holding,
    # one of the four columns would have been computed from something other than
    # what its name says.
    both = table[table[config.EXPOSURE_RATIO_COL].notna()]
    identity = np.allclose(
        both[config.EXPOSURE_RATIO_COL].to_numpy(),
        (both[config.IMPLIED_RISK_COL] / both[config.SMOOTH_RISK_COL]).to_numpy(),
        rtol=1e-9,
        equal_nan=True,
    )
    if not identity:
        raise ValueError(
            "the ratio of the two exposures is not the ratio of the two risks, which it is by "
            "algebra; one of the four columns is not what its name says"
        )

    weekday_rows = len(weekday)
    log.record(
        "compare the panel against the casualty series",
        rows_in=len(panel),
        rows_out=len(table),
        changes=[
            (
                weekday_rows - len(panel),
                "rows of a day type the casualty series cannot be paired with, a casualty count "
                f"being annual and carrying no kind of day; only {config.WEEKDAY_TYPE} is kept",
            ),
            (
                len(table) - weekday_rows,
                "a second row per unit, year and actor type for the corrected casualty dataset, "
                "over the years D30 leaves it",
            ),
        ],
        notes=[
            f"casualty source run={casualties.source_run}, "
            + ", ".join(sorted(casualties.by_dataset)),
            f"one row per unit, year, actor type and casualty dataset, on "
            f"{config.WEEKDAY_TYPE} exposure",
            f"{undefined} cell(s) where the smoothed risk is zero, so no exposure can be "
            "implied from it",
            "diagnostic only: it enters no model, for the reason D41 gives",
        ],
    )
    return table


def export_diagnostic(table: pd.DataFrame, log: RunLog) -> dict[str, Path]:
    """Write the diagnostic beside the panel it diagnoses."""
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{config.EXPOSURE_DIAGNOSTIC_FILENAME}.csv"
    table.to_csv(path, index=False, encoding="utf-8")
    table.to_parquet(path.with_suffix(".parquet"))
    log.info("exported the casualty diagnostic (%d rows) to %s/", len(table), config.DATA_SUBDIR)
    return {"exposure_diagnostic": path}


def report_diagnostic(table: pd.DataFrame, log: RunLog) -> None:
    """Where the panel is least believable, by year and by unit.

    Two readings of one number, as the build's docstring sets out: at the city it
    says how far the risk this panel implies departs from a smooth path, and at the
    unit it says which cells would move most under the opposite assumption.
    """
    modes = [
        actor for actor in config.ROAD_USER_TYPES if actor in set(table[config.ACTOR_TYPE_COL])
    ]
    for dataset in (config.OBSERVED_DATASET, config.CORRECTED_DATASET):
        block = table[table[config.DATASET_COL] == dataset]
        if block.empty:
            continue
        city = block.groupby([config.YEAR_COL, config.ACTOR_TYPE_COL]).apply(
            lambda rows: float(rows[config.IMPLIED_EXPOSURE_COL].sum())
            / float(rows[config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL].sum()),
            include_groups=False,
        ).unstack()[modes]
        provenance = block.groupby(config.YEAR_COL)[config.EXPOSURE_PROVENANCE_COL].first()

        lines = [
            f"{'year':>6}  {'':>13}  " + "  ".join(f"{actor:>12}" for actor in modes),
            f"{'-' * 6}  {'-' * 13}  " + "  ".join("-" * 12 for _ in modes),
        ]
        for year, row in city.iterrows():
            lines.append(
                f"{year:>6}  {provenance[year]:>13}  "
                + "  ".join(f"{value:>11.2f}x" for value in row)
            )
        log.table(
            f"the panel against the {dataset.lower()} casualty series: the exposure that a "
            "smooth risk would imply, over the exposure the panel carries. One at every survey "
            "year by construction; away from one it is how much of the movement the panel is "
            "putting into the risk rather than into the exposure:",
            "\n".join(lines),
        )

    # The widest constructed cells, on the corrected set, because on the observed
    # one the widest cells are mostly the recording change.
    dataset = (
        config.CORRECTED_DATASET
        if (table[config.DATASET_COL] == config.CORRECTED_DATASET).any()
        else config.OBSERVED_DATASET
    )
    constructed = table[
        (table[config.DATASET_COL] == dataset)
        & (table[config.EXPOSURE_PROVENANCE_COL] != config.MEASURED_EXPOSURE)
        & table[config.EXPOSURE_RATIO_COL].notna()
    ].copy()
    # A cell with no casualty at all implies an exposure of exactly zero, which is
    # not a wide ratio but the method breaking down: a mode nobody was hurt in that
    # year is not a mode nobody travelled in. Those cells have no factor and are
    # counted apart rather than put at the top of a table of ratios.
    ratio = constructed[config.EXPOSURE_RATIO_COL]
    empty = int((ratio == 0).sum())
    constructed["_DISTANCE"] = np.where(
        ratio > 0, np.maximum(ratio, 1.0 / ratio.where(ratio > 0)), np.nan
    )
    wide = constructed[constructed["_DISTANCE"] > config.EXPOSURE_DIAGNOSTIC_FACTOR]
    by_year = wide.groupby(config.YEAR_COL).size().sort_values(ascending=False)
    log.warn(
        "on the %s set, %d of the %d constructed unit-year-mode cells would move by more than a "
        "factor of %g under the opposite assumption. The years that carry most of them: %s. "
        "This fails nothing — it is the cost of having to assume something about one of two "
        "unknowns, and it is the table that says where that cost falls. See D41",
        dataset.lower(),
        len(wide),
        len(constructed),
        config.EXPOSURE_DIAGNOSTIC_FACTOR,
        "; ".join(f"{year} {int(count):,}" for year, count in by_year.head(6).items()),
    )

    # And the low-count cells, because the diagnostic divides by a casualty count and
    # a small one carries its own noise into the ratio.
    thin = int((constructed[config.AFFECTED_PARTIES_COL] < 10).sum())
    log.info(
        "%d of the %d constructed cells rest on fewer than ten casualties, where Poisson noise "
        "alone is worth about a third of the ratio, and %d saw no casualty at all and therefore "
        "imply an exposure of exactly zero — which is the method failing rather than a finding. "
        "The diagnostic is read at the city and at the year before it is read at one unit",
        thin,
        len(constructed),
        empty,
    )
