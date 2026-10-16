"""The origin-destination matrix of a year no survey covers, reconstructed by fitting.

D54 declared iterative proportional fitting in the anteproyecto and D60 settled what
it is fitted on. This module is the stage; `fitting` is the arithmetic it calls, and
knows nothing about surveys, units, years or modes.

**What it reconstructs, in one sentence.** For a year between two surveys, take the
nearest survey's zone-level matrix as the seed, require it to produce the trips each
unit generates and attracts in that year, and let the fitting find the matrix that
does so while staying as close to the seed as the margins allow.

**The three pieces, in the order they are built.** The margins per unit and year,
which is this half of the module; their disaggregation onto the seeding survey's
zones; and the fitting itself. Only the first is here so far, and it is deliberately
separable: a margin table is something a reader can check against the surveys without
knowing anything about the fitting, and a fitting whose margins are wrong is wrong in
a way no amount of iteration reveals.

**Why the margins are carried the same way D40 carries the exposure.** They are built
on `interpolation.fill_series` rather than on arithmetic of their own, which matters
for a reason that is not convenience: the fitted panel and D40's panel are going to be
compared, and if the two interpolated their inputs by different schemes the comparison
would measure the difference between the schemes as readily as the difference the
fitting makes. One scheme, one difference.

**What this stage does not do.** It reads no survey file and writes no change to the
measured exposure table, exactly as `interpolation` does not: that table is the record
of what the surveys say, and everything built on top of it sits beside it.

See D54, D60 and `docs/implementing-ipf.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

try:  # regular package import
    from src import (
        config,
        exposure,
        fitting,
        interpolation,
        mobility_reports,
        population,
        surveys,
    )
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import exposure  # type: ignore[no-redef]
    import fitting  # type: ignore[no-redef]
    import interpolation  # type: ignore[no-redef]
    import mobility_reports  # type: ignore[no-redef]
    import population  # type: ignore[no-redef]
    import surveys  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# Working columns for the disaggregation. Private: they live between the unit margins
# and the fitting and appear in nothing anybody exports.
_SEED_AT_ORIGIN_COL = "_SEED_AT_ORIGIN"
_SEED_AT_DESTINATION_COL = "_SEED_AT_DESTINATION"
_UNPLACEABLE_ORIGIN_COL = "_UNPLACEABLE_AT_ORIGIN"
_UNPLACEABLE_DESTINATION_COL = "_UNPLACEABLE_AT_DESTINATION"
_GROWTH_COL = "_GROWTH"
_OUTSIDE_GROWTH_COL = "_OUTSIDE_GROWTH"
_WEIGHTED_COL = "_WEIGHTED_GROWTH"
_INSIDE_SHARE_COL = "_SHARE_INSIDE_ANY_UNIT"
_UNIVERSE_SHARE_COL = "_UNIVERSE_SHARE"
_MARGIN_NAME_COL = "MARGIN"
_UNPLACEABLE_TRIPS_COL = "TRIPS_PER_DAY"

# What one block's fitting reports about itself. The iteration count and the margin
# error are not decoration: a block that took 300 iterations to reach the tolerance and
# one that took 4 are different kinds of answer, and a reader who cannot tell them apart
# cannot judge the year they are in.
_ZONES_COL = "ZONES"
_SEED_CELLS_COL = "SEED_CELLS"
_FITTED_CELLS_COL = "FITTED_CELLS"
_ITERATIONS_COL = "ITERATIONS"
_CONVERGED_COL = "CONVERGED"
_MARGIN_ERROR_COL = "WORST_MARGIN_ERROR"
# Whether the block needed the floor, and what the floor left behind. Public, with the
# block total, because `reconstruction_figures` draws them and a figure that reaches
# into a module's private names is a figure that breaks when the module is tidied. **This is the
# travel the reconstruction added and no survey ever saw**, so it is a column and not a
# log line: the thesis has to be able to quote it per block, and a reader has to be able
# to see that the years which needed it are not the years the study leans on.
FLOORED_COL = "FLOORED"
_OPENED_CELLS_COL = "CELLS_OPENED_BY_THE_FLOOR"
OPENED_TRIPS_COL = "TRIPS_ON_OPENED_CELLS"
_PRUNED_TRIPS_COL = "TRIPS_PRUNED"
# El total del bloque, en la base de dia promedio de la encuesta que siembra, que es
# la base en la que estan `TRIPS_ON_OPENED_CELLS` y `TRIPS_PRUNED`. Sin el, lo
# inventado es un numero absoluto que nadie puede juzgar, y buscarlo en el panel
# obliga a convertir de base para compararlo: dos sitios donde equivocarse.
BLOCK_TRIPS_COL = "TRIPS_IN_THE_BLOCK"
_DISCOVERY_ITERATIONS_COL = "DISCOVERY_ITERATIONS"
_FIT_REPORT_COLUMNS = [
    config.ACTOR_TYPE_COL,
    config.DAY_TYPE_COL,
    _ZONES_COL,
    _SEED_CELLS_COL,
    _FITTED_CELLS_COL,
    FLOORED_COL,
    _OPENED_CELLS_COL,
    OPENED_TRIPS_COL,
    _PRUNED_TRIPS_COL,
    BLOCK_TRIPS_COL,
    _DISCOVERY_ITERATIONS_COL,
    _ITERATIONS_COL,
    _CONVERGED_COL,
    _MARGIN_ERROR_COL,
]

# The two small tables a disaggregation reports on, declared so that an empty one has
# the same columns as a full one. A year where nothing could be placed is the normal
# case, and a caller that has to test for emptiness before reading a column is a caller
# that will forget to.
_UNPLACEABLE_COLUMNS = [
    config.ACTOR_TYPE_COL,
    config.DAY_TYPE_COL,
    config.AREA_CODE_COL,
    _MARGIN_NAME_COL,
    _UNPLACEABLE_TRIPS_COL,
]
_COMPONENTS_COL = "SUPPORT_COMPONENTS"
_MOVED_MARGINS_COL = "MARGINS_MOVED"
_WORST_COMPONENT_COL = "WORST_COMPONENT_CORRECTION"
# **La cifra que de verdad dice cuanto hizo la reconciliacion.** El peor factor por
# componente puede ser del 100 % en un componente de cuarenta viajes, que no es nada, y
# del 1 % en el que lleva casi toda la matriz, que es mucho. Los viajes movidos no
# tienen esa ambiguedad y son lo que una comprobacion tiene que mirar.
_TRIPS_MOVED_COL = "TRIPS_MOVED"
_TRIPS_IN_BLOCK_COL = "TRIPS_IN_BLOCK"
_RECONCILIATION_COLUMNS = [
    config.ACTOR_TYPE_COL,
    config.DAY_TYPE_COL,
    _COMPONENTS_COL,
    _MOVED_MARGINS_COL,
    _WORST_COMPONENT_COL,
    _TRIPS_MOVED_COL,
    _TRIPS_IN_BLOCK_COL,
]

# The two margins a zone carries. **They are on the seeding survey's average-day basis
# and not on the day-of-type one**, because the matrix the fitting scales is the
# survey's own and that is the basis it is written in. The conversion happens inside the
# growth factor: both sides of that ratio are put on the day-of-type basis, the ratio is
# dimensionless, and applying it to an average-day seed leaves an average-day result.
# Getting this backwards would rescale 2023's matrix by 1.29 and nothing would complain.
ZONE_AT_ORIGIN_COL = "_ZONE_AT_ORIGIN"
ZONE_AT_DESTINATION_COL = "_ZONE_AT_DESTINATION"

# Which surveys a reconstructed year was built from, and in what proportion. Not private:
# they travel on every row of the exposure this stage produces, because a panel of
# thirteen years resting on four matrices is unreadable without them — a year built mostly
# from 2011 and a year built mostly from 2023 are answers of different quality and these
# columns are what let anyone say so.
#
# **Three numeric columns rather than one string holding "2015:0.75;2019:0.25".** A table
# the dashboard joins has to be read without parsing, and a field whose separator has to
# be guessed is how a measurement of this very study came out wrong once.
SEED_YEAR_COL = "SEED_SURVEY_YEAR"            # the earlier survey, or the only one
SEED_SECOND_YEAR_COL = "SEED_SURVEY_YEAR_SECOND"  # the later one, or null when there is one
SEED_WEIGHT_COL = "SEED_SURVEY_WEIGHT"        # the weight of the first; the second's is 1 − it

# The three columns of the comparison against D40. Named rather than inline because
# the table they build is what the deliverable quotes from, and a column called
# "RATIO" in one place and "razon" in another is how a figure and a sentence drift.
_FITTED_LEVEL_COL = "EXPOSURE_FITTED"
_INTERPOLATED_LEVEL_COL = "EXPOSURE_INTERPOLATED"
_RATIO_COL = "FITTED_OVER_INTERPOLATED"

# The two margins again, each paired with the unit margin it is spread from, the seed
# column it is spread in proportion to, and the two things the spreading has to report.
# One tuple so the disaggregation is written once and the second margin cannot acquire a
# second definition, which is `_MARGINS`' reason one level down.
_DISAGGREGATION: tuple[tuple[str, str, str, str], ...] = (
    (
        config.MARGIN_AT_ORIGIN_COL,
        _SEED_AT_ORIGIN_COL,
        ZONE_AT_ORIGIN_COL,
        _UNPLACEABLE_ORIGIN_COL,
    ),
    (
        config.MARGIN_AT_DESTINATION_COL,
        _SEED_AT_DESTINATION_COL,
        ZONE_AT_DESTINATION_COL,
        _UNPLACEABLE_DESTINATION_COL,
    ),
)


# The two margins, each with the column of the measured table it is read from, the
# rate it is interpolated on and the factor its reconciliation leaves behind. One
# mapping rather than two blocks of near-identical code, for `interpolation._SERIES`'
# reason: the procedure is "do it twice and change nothing else", and a second
# definition of the second margin is a place for the two to drift apart.
#
# **The source column is on the average-day basis and the margin is not.** The
# division by `DAY_TYPE_UNIVERSE_SHARE` happens where the anchors are read, because
# an interpolation is a comparison between years and D38 allows only one basis for
# that.
_MARGINS: dict[str, tuple[str, str, str]] = {
    config.MARGIN_AT_ORIGIN_COL: (
        config.TRIPS_AT_ORIGIN_COL,
        config.MARGIN_AT_ORIGIN_RATE_COL,
        config.MARGIN_AT_ORIGIN_RECONCILIATION_COL,
    ),
    config.MARGIN_AT_DESTINATION_COL: (
        config.TRIPS_AT_DESTINATION_COL,
        config.MARGIN_AT_DESTINATION_RATE_COL,
        config.MARGIN_AT_DESTINATION_RECONCILIATION_COL,
    ),
}

_MARGIN_KEY = [config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]


# ---------------------------------------------------------------------------
# The margins, per unit and year
# ---------------------------------------------------------------------------


def unit_margins(
    measured: interpolation.MeasuredExposure,
    panel: pd.DataFrame,
    units: gpd.GeoDataFrame,
    log: RunLog,
    window: range | None = None,
) -> pd.DataFrame:
    """One row per unit, year, actor type and day type: what it generates and attracts.

    **The margin is not the exposure, and the difference is the whole reason the
    fitting is worth doing.** The exposure of a unit is what reaches it by any route,
    including a trip that crosses it without stopping; a margin counts only the trips
    that begin or end there. 2011's Saturday has a unit with 1,351 cycling trips of
    exposure and a margin of zero at both ends — travel passing through and none of it
    local. A margin of zero is therefore an observation and not a gap, and it is left
    as it is.

    **The measured years keep the survey's own number.** Carried straight through
    rather than recovered from a rate, for D40's reason: an observation must not be
    moved by the arithmetic that fills the years around it. It also means the identity
    check D60 rests on has something exact to be checked against.

    **Both margins are per inhabitant, which the anteproyecto declares and which is a
    stronger assumption at the destination than at the origin.** Residents are what
    generates a trip; what attracts one is work and services, which this panel does
    not carry. Scaling attraction by residents therefore holds the ratio of the two
    constant within a unit between surveys. The thing it cannot do is invent a new
    centre of attraction, and the thesis says so rather than letting the per-inhabitant
    phrasing cover both cases equally.
    """
    window = window or config.STUDY_YEARS
    table = measured.table

    missing = [
        source for source, _, _ in _MARGINS.values() if source not in table.columns
    ]
    if missing:
        raise ValueError(
            f"{measured.source_run} exported an exposure table without "
            f"{', '.join(missing)}. The two endpoint allocations are what the fitting's "
            "margins are built from (D60), so a table from before they existed cannot "
            "seed it. Re-run the exposure route"
        )

    day_types = [day for day in config.DAY_TYPES if day in set(table[config.DAY_TYPE_COL])]
    anchors_by_day = {day: measured.anchors_of(day) for day in day_types}
    span_by_day = {
        day: interpolation.series_window(anchors_by_day[day], window) for day in day_types
    }
    # One set of anchors per margin and mode, not one per day type. 2005's pedestrian
    # endpoint columns count long walking where the other four years count all of it,
    # and the exclusion is declared on the column in `config.MOBILITY_SURVEYS` rather
    # than decided here. For every other mode and both margins the five years anchor.
    anchors_by_margin = {
        day: {
            (margin, actor): measured.anchors_of(day, source, actor)
            for margin, (source, _, _) in _MARGINS.items()
            for actor in sorted(table[config.ACTOR_TYPE_COL].unique())
        }
        for day in day_types
    }

    anchor_years = {year for day in day_types for year in anchors_by_day[day]}
    populations = {
        year: population.for_year(panel, year)
        for year in range(min([window.start, *anchor_years]), window.stop)
    }
    # The per-year, per-day-type scalar that puts the average-day columns of the
    # measured table onto the comparable basis. One value per year and day type, so it
    # is read once rather than per unit.
    universe_shares = (
        table.groupby([config.YEAR_COL, config.DAY_TYPE_COL])[
            config.DAY_TYPE_UNIVERSE_SHARE_COL
        ]
        .first()
        .to_dict()
    )

    support_by_key = {
        (row[config.AREA_CODE_COL], row[config.ACTOR_TYPE_COL],
         row[config.DAY_TYPE_COL], row[config.YEAR_COL]): row[config.SAMPLE_SUPPORT_COL]
        for _, row in table.iterrows()
    }
    measured_by_key = table.set_index(_MARGIN_KEY + [config.YEAR_COL])[
        [source for source, _, _ in _MARGINS.values()]
    ].to_dict("index")

    rows: list[dict[str, object]] = []
    linear_cells = {margin: 0 for margin in _MARGINS}
    for day_type in day_types:
        anchors = anchors_by_day[day_type]
        block = table[table[config.DAY_TYPE_COL] == day_type]
        for area_code in units[config.AREA_CODE_COL]:
            for actor in sorted(block[config.ACTOR_TYPE_COL].unique()):
                rates: dict[str, dict[int, float]] = {margin: {} for margin in _MARGINS}
                levels: dict[str, dict[int, float]] = {margin: {} for margin in _MARGINS}
                for year in anchors:
                    cell = measured_by_key[(area_code, actor, day_type, year)]
                    share = float(universe_shares[(year, day_type)])
                    if not share > 0:
                        raise ValueError(
                            f"{day_type} of {year} covers none of the surveyed universe, so "
                            "the comparable basis of its margins is undefined. The share is "
                            "the fraction of the universe whose reference day was of this "
                            "kind and a zero there means the day type should not be in the "
                            "table at all"
                        )
                    residents = float(populations[year][area_code])
                    if not residents > 0:
                        raise ValueError(
                            f"{area_code} has no population in {year}, so the rate the "
                            "margins are carried on cannot be formed. The population panel "
                            "is required to be complete over the study's units and years "
                            "(D36)"
                        )
                    for margin, (source, _, _) in _MARGINS.items():
                        level = float(cell[source]) / share
                        levels[margin][year] = level
                        # A year that measures the column but is not comparable on it
                        # puts its value in the table and not in the curve, exactly as
                        # in D40.
                        if year in anchors_by_margin[day_type][(margin, actor)]:
                            rates[margin][year] = level / residents

                filled = {
                    margin: interpolation.fill_series(rates[margin], span_by_day[day_type])
                    for margin in _MARGINS
                }
                for margin in _MARGINS:
                    linear_cells[margin] += sum(
                        1 for value in filled[margin].values()
                        if value.linear_because_of_a_zero
                    )

                # The provenance follows the origin margin. The two are carried over
                # the same anchors in every mode but the 2005 pedestrian, where both
                # are excluded together, so one column answers for both rather than
                # two columns saying the same word 7,200 times.
                shape = filled[config.MARGIN_AT_ORIGIN_COL]
                for year in span_by_day[day_type]:
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
                        config.SAMPLE_SUPPORT_COL: interpolation.support_of(
                            at.rests_on,
                            {
                                anchor: support_by_key[(area_code, actor, day_type, anchor)]
                                for anchor in anchors
                            },
                        ),
                    }
                    for margin, (_, rate_column, _) in _MARGINS.items():
                        value = filled[margin][year]
                        if year in levels[margin]:
                            row[margin] = levels[margin][year]
                            row[rate_column] = levels[margin][year] / residents
                        else:
                            row[rate_column] = value.rate
                            row[margin] = value.rate * residents
                    rows.append(row)

    built = pd.DataFrame(rows)
    built = reconcile(built, anchors_by_day, log)

    geometry = units[[config.AREA_CODE_COL, config.AREA_NAME_COL]]
    built = built.merge(geometry, on=config.AREA_CODE_COL, how="left")
    built[config.SCALE_COL] = config.active_scale().label
    built = (
        built[list(config.unit_margin_columns())]
        .sort_values(
            [config.YEAR_COL, config.AREA_CODE_COL, config.ACTOR_TYPE_COL,
             config.DAY_TYPE_COL],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    census = built[config.EXPOSURE_PROVENANCE_COL].value_counts()
    log.record(
        "carry the unit margins across the years no survey covers",
        rows_in=len(table),
        rows_out=len(built),
        changes=[
            (
                len(built) - len(table),
                f"one row per unit, year, mode and day type over each day type's own span "
                f"({'; '.join(f'{day} {span.start}-{span.stop - 1}' for day, span in span_by_day.items())}), "
                f"against {len(table)} measured rows",
            )
        ],
        notes=[
            f"source run={measured.source_run}",
            "; ".join(
                f"{int(count)} {provenance.lower()}" for provenance, count in census.items()
            ),
            "both margins on the day-of-type basis: the average-day columns of the "
            "measured table divided by DAY_TYPE_UNIVERSE_SHARE, because an "
            "interpolation is a comparison between years (D38)",
            "the margin is not the exposure: it counts only the trips that begin or end "
            "in the unit, so a unit with travel crossing it and none of its own has a "
            "margin of zero and an exposure that is not zero",
        ] + [
            f"{count} cell(s) of {margin} filled linearly because a margin of exactly zero "
            "left the logarithm undefined at one end of the segment"
            for margin, count in linear_cells.items() if count
        ],
    )
    return built


# ---------------------------------------------------------------------------
# Making the two margins agree about the grand total
# ---------------------------------------------------------------------------


def reconcile(
    built: pd.DataFrame,
    anchors_by_day: dict[str, tuple[int, ...]],
    log: RunLog,
) -> pd.DataFrame:
    """Scale both margins of each constructed year to the mean of their two totals.

    **No matrix has two margins that disagree about its grand total**, so the fitting
    cannot be handed them and this is not a refinement. There are two separate reasons
    they disagree and both are real.

    At a survey year, a trip whose origin falls in a unit and whose destination falls
    outside the study area or in a boundary sliver enters one margin and not the other,
    and the two lose different amounts that way. Measured over the five surveys it runs
    from 0.016 % to 1.242 %.

    At a constructed year the disagreement is larger, up to 3.4 %, and it comes from
    interpolating per unit. The sum of thirty log-linear curves is not the log-linear
    curve of their sum — 2013's Saturday motorcycle totals 13.3 % below what the city
    curve would give at the origin and 10.5 % below it at the destination — and the gap
    between those two shortfalls is the disagreement. It is distributed rather than
    local: every one of the thirty units has its 2013 rate between its 2011 and 2015
    rates, the largest single contributor is two fifths of the net, and the
    contributions cancel in both directions. **So the reconciliation absorbs a known
    cost of D40's per-unit interpolation and is not hiding a defect**, which is worth
    stating because a correction applied to a total is exactly where a defect would
    hide.

    **The mean of the two totals rather than one of them**, so that neither margin is
    privileged and neither moves by more than half the disagreement. Preferring the
    origin would have been defensible — generation is the better-measured of the two —
    but it would also have put the whole correction on attraction, which is the margin
    already carrying the weaker per-inhabitant assumption.

    **A year whose own kind of day a survey measured is left alone.** It is not fitted,
    so it needs no consistent pair, and touching it would move a measured number for
    the benefit of a construction that does not use it. Which is why the anchors arrive
    per day type and not as a list of survey years: 2019 is a survey year and no survey
    measured a Saturday in 2019, so 2019's Saturday margins are as constructed as
    2017's and have to be reconciled like them. Reading the flat list of survey years
    there left 240 constructed rows unreconciled, and a fitting handed them would have
    stopped on margins that disagree.
    """
    built = built.copy()
    origin, destination = config.MARGIN_AT_ORIGIN_COL, config.MARGIN_AT_DESTINATION_COL
    origin_factor = _MARGINS[origin][2]
    destination_factor = _MARGINS[destination][2]

    built[origin_factor] = 1.0
    built[destination_factor] = 1.0

    anchored = pd.Series(False, index=built.index)
    for day_type, anchors in anchors_by_day.items():
        anchored |= (built[config.DAY_TYPE_COL] == day_type) & built[
            config.YEAR_COL
        ].isin(anchors)
    constructed = ~anchored

    group = [config.YEAR_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]
    totals = built[constructed].groupby(group)[[origin, destination]].transform("sum")
    target = (totals[origin] + totals[destination]) / 2.0

    # A group whose total is zero needs no scaling and must not be divided by zero to
    # find that out. It happens where a mode did no travel of this kind at all, which
    # the 2011 Saturday has for cycling in three units and could have for a whole mode
    # in a narrower universe.
    for column, factor in ((origin, origin_factor), (destination, destination_factor)):
        scale = pd.Series(1.0, index=totals.index)
        movable = totals[column] > 0
        scale[movable] = target[movable] / totals.loc[movable, column]
        built.loc[constructed, factor] = scale
        built.loc[constructed, column] = built.loc[constructed, column] * scale

    moved = built.loc[constructed, group + [origin_factor, destination_factor]]
    worst_row = (
        moved.assign(_size=(moved[origin_factor] - 1.0).abs())
        .sort_values("_size", ascending=False)
        .head(1)
    )
    worst = float(worst_row["_size"].iloc[0]) if len(worst_row) else 0.0
    where = (
        f"{worst_row[config.ACTOR_TYPE_COL].iloc[0]} on the "
        f"{worst_row[config.DAY_TYPE_COL].iloc[0].lower()} of "
        f"{int(worst_row[config.YEAR_COL].iloc[0])}"
        if len(worst_row)
        else "nowhere"
    )
    if worst > config.MARGIN_RECONCILIATION_LIMIT:
        # Not a failure: the size of this correction is a property of the per-unit
        # interpolation and a threshold crossed is a thing to look at rather than a
        # thing to stop for. It is a warning so that it cannot be crossed quietly.
        log.warn(
            "the two margins of %s had to be moved %.3f%% each to agree about the grand "
            "total, past the %.1f%% the configuration declares as worth looking at. The "
            "cause is that a sum of per-unit log-linear curves is not the curve of the "
            "sum (D40), so it grows with how unevenly the units move between two "
            "surveys; see reconstruction.reconcile",
            where,
            worst * 100,
            config.MARGIN_RECONCILIATION_LIMIT * 100,
        )

    log.record(
        "reconcile the two margins of every constructed year to one grand total",
        rows_in=len(built),
        rows_out=len(built),
        notes=[
            f"{int(constructed.sum())} of {len(built)} rows reconciled; the "
            f"{int(anchored.sum())} rows whose own kind of day a survey measured are left "
            "as the surveys measured them, because such a year is not fitted",
            f"largest correction {worst * 100:.3f} % of the margin, at {where}, and each "
            "margin moves by at most half of the disagreement because the target is the "
            "mean of the two totals",
            "the factor each row was multiplied by is kept in the table: dividing recovers "
            "the interpolated margin",
        ],
    )
    return built


# ---------------------------------------------------------------------------
# Which survey seeds a year, and the zones its margin is spread over
# ---------------------------------------------------------------------------


def seeding_blend(year: int, anchors: tuple[int, ...]) -> tuple[tuple[int, float], ...]:
    """The surveys a year is reconstructed from, and with what weight: the two around it.

    Per kind of day, which is why the anchors arrive as an argument. The Saturday has
    surveys at 2011, 2015 and 2023 and the Sunday only at 2023, so "the surveys around
    this year" is three different questions and asking it once with the weekday's answer
    would seed a Saturday from a year that measured none.

    **Linear in the year, which is what D40 already does with the rates.** 2017 is three
    quarters of 2015 and one quarter of 2019. The alternative was the nearest survey
    alone, and it is what D64 replaced: the shape of the matrix then changed in one step
    at 2014, 2018 and 2022, and because a unit's exposure counts the travel that crosses
    it as well as the travel that begins there, that step landed in the exposure. The
    fitted panel jumped 2.55 times its own year-to-year change at those three years.

    **A year at an anchor returns that anchor alone, with weight one.** Not as a special
    case — the linear weight is exactly one there — and it is what keeps a surveyed year
    an observation rather than something this function built. Outside the anchors there
    is no pair to interpolate between, so the nearest survey is held: 2024 is 2023's
    matrix, and saying so is more honest than extrapolating a shape.

    The weights are returned as a tuple rather than a dict because their order is the
    order of the years and two components with equal weight — 2013, 2017 and 2021 sit
    exactly halfway — must not depend on how a mapping happens to iterate.
    """
    if not anchors:
        raise ValueError(
            f"{year} has no survey of its kind of day to be seeded from, and a matrix "
            "cannot be reconstructed out of nothing. A day type with no anchor must be "
            "left out of the window rather than fitted"
        )
    ordered = tuple(sorted(set(anchors)))
    if year in ordered:
        return ((year, 1.0),)
    earlier = [anchor for anchor in ordered if anchor < year]
    later = [anchor for anchor in ordered if anchor > year]
    if not earlier:
        return ((later[0], 1.0),)
    if not later:
        return ((earlier[-1], 1.0),)
    before, after = earlier[-1], later[0]
    weight_after = (year - before) / (after - before)
    return ((before, 1.0 - weight_after), (after, weight_after))


def seed_zone_margins(pairs: pd.DataFrame) -> pd.DataFrame:
    """One row per actor type, day type and zone: what the survey saw begin and end there.

    The row and column sums of the survey's own matrix, which is all a margin is. They
    are formed here rather than read from the exposure table because the exposure table
    is already apportioned to units and the whole point of this stage is to go the other
    way.

    **Origin and destination are summed over different keys and then joined, not summed
    together.** A zone is almost always both an origin and a destination, but not
    always: 2015's Saturday cycling has 220 origin zones and 218 destination zones, and
    a zone that only ever appears at one end has to arrive as a zero at the other rather
    than as a missing row the fitting would silently drop.
    """
    key = [config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]
    at_origin = (
        pairs.groupby(key + [surveys.ZONE_ORIGIN_COL], as_index=False)[surveys.TRIPS_COL]
        .sum()
        .rename(columns={surveys.ZONE_ORIGIN_COL: surveys.ZONE_CODE_COL,
                         surveys.TRIPS_COL: _SEED_AT_ORIGIN_COL})
    )
    at_destination = (
        pairs.groupby(key + [surveys.ZONE_DESTINATION_COL], as_index=False)[surveys.TRIPS_COL]
        .sum()
        .rename(columns={surveys.ZONE_DESTINATION_COL: surveys.ZONE_CODE_COL,
                         surveys.TRIPS_COL: _SEED_AT_DESTINATION_COL})
    )
    both = at_origin.merge(
        at_destination, on=key + [surveys.ZONE_CODE_COL], how="outer"
    )
    both[_SEED_AT_ORIGIN_COL] = both[_SEED_AT_ORIGIN_COL].fillna(0.0)
    both[_SEED_AT_DESTINATION_COL] = both[_SEED_AT_DESTINATION_COL].fillna(0.0)
    return both


@dataclass(frozen=True)
class ZoneMargins:
    """The margins one year's fitting is given, and everything needed to judge them."""

    # One row per actor type, day type and zone, with the two margins.
    table: pd.DataFrame
    year: int
    seed_year: int
    # The trips per day the unit margins asked for and no zone of the seed could hold,
    # per actor type and day type. It is never a rounding error: it means the seeding
    # survey saw no travel of that mode anywhere in that unit, so the fitting has no
    # cell to put it in and no iteration would find one.
    unplaceable: pd.DataFrame
    # What the margins had to be moved by, per actor type and day type, so that every
    # connected piece of the seed's support balances on its own. One row per block, with
    # how many pieces it splits into, how many margins moved, and how much of the block's
    # travel that amounted to.
    reconciliation: pd.DataFrame

    @property
    def worst_reconciliation(self) -> float:
        """The largest correction any one connected piece needed.

        Read it beside `share_of_trips_reconciled` and never alone: the pieces that need a
        large correction are the ones holding two or three zones, so this number is
        routinely large and routinely meaningless.
        """
        if not len(self.reconciliation):
            return 0.0
        return float(self.reconciliation[_WORST_COMPONENT_COL].max())

    @property
    def share_of_trips_reconciled(self) -> float:
        """What the reconciliation moved, as a share of the margins it was given.

        **The number to judge it by.** A piece holding forty trips can have its margins
        halved without that meaning anything, and the piece holding almost the whole
        matrix cannot move a per cent without meaning a great deal. This does not have
        that ambiguity, which is why the checks read it and not the worst factor.
        """
        if not len(self.reconciliation):
            return 0.0
        total = float(self.reconciliation[_TRIPS_IN_BLOCK_COL].sum())
        if not total > 0:
            return 0.0
        return float(self.reconciliation[_TRIPS_MOVED_COL].sum()) / total


def zone_margins(
    seed: surveys.SurveyTrips,
    zone_shares: pd.DataFrame,
    targets: pd.DataFrame,
    year: int,
    log: RunLog | None = None,
) -> ZoneMargins:
    """Spread one year's unit margins over the seeding survey's zones.

    **This is the step D60 declares as an assumption, and the entropy argument does not
    cover it.** The fitting finds the matrix closest to the seed that satisfies the
    margins it is given and adds nothing else; that is an argument about the fitting.
    Deciding what the zone margins are is a prior choice, and the choice made here is
    that **the shape of travel within a unit does not change between surveys, only its
    level**. The methodology chapter has to say so rather than let the entropy argument
    cover the whole stage.

    **The mechanism is one growth factor per unit.** The seeding survey's own zone
    margins, apportioned to the units by area share, give what that survey saw each unit
    generate and attract. The ratio of this year's margin to that is the unit's growth
    factor, and every zone is scaled by the area-weighted average of the factors of the
    units it lies in. For a zone `z` with share `s[z,u]` of its area in unit `u`:

        m[z] = m0[z] * ( SUM_u s[z,u] * g[u]  +  (1 - SUM_u s[z,u]) * g_outside )

    Three properties follow from its being a scaling, and all three are wanted. **A zero
    of the seed stays zero**, which is required and not merely tidy: the fitting cannot
    put a trip in a cell the seed left empty, so a margin asking it to would be
    unreachable and `fitting.unfittable_margins` would say so. **A zone straddling two
    units is governed by both**, in proportion to how much of it lies in each, which is
    the same rule by which its trips were apportioned in the first place — 290 of 2015's
    853 reachable zones straddle, so it is the common case and not a corner. And **the
    part of a zone outside every unit follows `config.OUTSIDE_MARGIN_RULE`**, because the
    study measures nothing about how travel in the ring of municipios grew and therefore
    has nothing of its own to scale it by. That part is not small — between 8.5 % and
    27.7 % of a survey's origin margin — and the constant is where the two answers and
    their cost are written down.

    **What cannot be placed is reported and not absorbed.** If the seeding survey saw no
    travel of a mode anywhere in a unit, that unit's margin for this year has no zone to
    go into: the growth factor is undefined and no redistribution fixes it, because every
    cell of the seed's rows there is zero. Those trips are counted into `unplaceable` and
    dropped. Spreading them by area instead would invent travel the survey never saw,
    which is the one thing this method exists not to do.
    """
    if config.OUTSIDE_MARGIN_RULE not in config.OUTSIDE_MARGIN_RULES:
        raise ValueError(
            f"config.OUTSIDE_MARGIN_RULE is {config.OUTSIDE_MARGIN_RULE!r}, which is not "
            f"one of {', '.join(config.OUTSIDE_MARGIN_RULES)}. It decides what happens to "
            "up to a quarter of a survey's margin, so there is no sensible default to fall "
            "back on"
        )

    key = [config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]
    seeded = seed_zone_margins(seed.pairs)

    # **The seed is chosen per kind of day and not per year**, and this is where getting
    # that wrong is caught. 2011 measured no Sunday, so a Sunday target handed to 2011's
    # matrix has no cell anywhere to go into — all 120 unit-mode combinations of it would
    # come back as unplaceable, which is the word for something small and real and not
    # for a stage wired to the wrong survey. 2019's Saturday is seeded from 2015 while
    # 2019's weekday is seeded from itself, so the caller loops over years and day types
    # together or it gets this.
    unseeded = sorted(
        set(targets[config.DAY_TYPE_COL].unique()) - set(seeded[config.DAY_TYPE_COL].unique())
    )
    if unseeded:
        raise ValueError(
            f"{seed.survey.label} measured no {', '.join(day.lower() for day in unseeded)}, "
            f"so it cannot seed {year}'s margins for that kind of day. The seeding survey is "
            "chosen per day type — `seeding_blend(year, measured.anchors_of(day_type))` — "
            "because the Saturday has surveys at 2011, 2015 and 2023 and the Sunday only at "
            "2023"
        )

    # **And the seed is cut down to what the targets ask about, which is not symmetry for
    # its own sake.** A block the seed carries and the targets do not would come out of
    # the growth factor at zero — no target, so nothing asked — while its outside part
    # went on being held at the seed's level. The result is a block of pure outside, and
    # since the ring is not symmetric between origins and destinations its two margins
    # disagree: handing 2011 a weekday-only target left its Saturday like that and cost
    # the identity 4.65 %. The fitting is per block, so the cut loses nothing.
    asked_about = set(map(tuple, targets[key].drop_duplicates().to_numpy()))
    keep = [tuple(row) in asked_about for row in seeded[key].to_numpy()]
    seeded = seeded.loc[keep].reset_index(drop=True)
    if not len(seeded):
        raise ValueError(
            f"{seed.survey.label} has no travel at all in the blocks {year} asks about, so "
            "there is nothing to seed the reconstruction with"
        )

    # How much of each zone reaches a unit at all. A zone of the municipios ring reaches
    # none and its share is zero, which is what makes the outside rule reachable rather
    # than theoretical.
    inside = (
        zone_shares.groupby(surveys.ZONE_CODE_COL, as_index=False)[exposure.ZONE_SHARE_COL]
        .sum()
        .rename(columns={exposure.ZONE_SHARE_COL: _INSIDE_SHARE_COL})
    )
    seeded = seeded.merge(inside, on=surveys.ZONE_CODE_COL, how="left")
    seeded[_INSIDE_SHARE_COL] = seeded[_INSIDE_SHARE_COL].fillna(0.0)

    # One row per zone, unit, actor type and day type, with the part of each seed margin
    # that unit holds. The scalar that puts it on the day-of-type basis is attached here
    # once: the seed's margins are average-day trips of the seed's own year, the targets
    # are day-of-type trips, and a ratio of the two bases would be wrong by 1.29 in 2023
    # with nothing to complain about it.
    fragments = seeded.merge(zone_shares, on=surveys.ZONE_CODE_COL, how="inner")
    universe = seed.universe_shares
    fragments[_UNIVERSE_SHARE_COL] = [
        float(universe.get(day, 1.0)) for day in fragments[config.DAY_TYPE_COL]
    ]
    for _, seed_column, _, _ in _DISAGGREGATION:
        fragments[_in_unit(seed_column)] = (
            fragments[seed_column]
            * fragments[exposure.ZONE_SHARE_COL]
            / fragments[_UNIVERSE_SHARE_COL]
        )

    zone_table = seeded[key + [surveys.ZONE_CODE_COL, _INSIDE_SHARE_COL]].copy()
    unplaceable_rows: list[dict[str, object]] = []

    for unit_column, seed_column, zone_column, _ in _DISAGGREGATION:
        in_unit = _in_unit(seed_column)
        seeded_per_unit = fragments.groupby(
            key + [config.AREA_CODE_COL], as_index=False
        )[in_unit].sum()

        # An outer join and not a left one: a unit the targets carry and the seed does
        # not is exactly the case that cannot be placed, and an inner join would make it
        # disappear instead of being counted.
        growth = seeded_per_unit.merge(
            targets[key + [config.AREA_CODE_COL, unit_column]],
            on=key + [config.AREA_CODE_COL],
            how="outer",
        )
        growth[in_unit] = growth[in_unit].fillna(0.0)
        growth[unit_column] = growth[unit_column].fillna(0.0)

        nowhere = (growth[in_unit] <= 0) & (growth[unit_column] > 0)
        for _, row in growth[nowhere].iterrows():
            unplaceable_rows.append({
                config.ACTOR_TYPE_COL: row[config.ACTOR_TYPE_COL],
                config.DAY_TYPE_COL: row[config.DAY_TYPE_COL],
                config.AREA_CODE_COL: row[config.AREA_CODE_COL],
                _MARGIN_NAME_COL: unit_column,
                _UNPLACEABLE_TRIPS_COL: float(row[unit_column]),
            })

        divisor = growth[in_unit].where(growth[in_unit] > 0, 1.0)
        growth[_GROWTH_COL] = np.where(
            growth[in_unit] > 0, growth[unit_column] / divisor, 0.0
        )

        # The area-weighted sum of the factors of the units a zone lies in. Weighted and
        # not averaged: the weights are the shares themselves, so a zone three quarters
        # inside one unit contributes three quarters of that unit's factor and the
        # remaining quarter is picked up by the outside rule below.
        weighted = fragments.merge(
            growth[key + [config.AREA_CODE_COL, _GROWTH_COL]],
            on=key + [config.AREA_CODE_COL],
            how="left",
        )
        weighted[_WEIGHTED_COL] = (
            weighted[exposure.ZONE_SHARE_COL] * weighted[_GROWTH_COL].fillna(0.0)
        )
        per_zone = weighted.groupby(
            key + [surveys.ZONE_CODE_COL], as_index=False
        )[_WEIGHTED_COL].sum()

        if config.OUTSIDE_MARGIN_RULE == "CITY":
            city = growth.groupby(key, as_index=False).agg(
                _asked=(unit_column, "sum"), _seeded=(in_unit, "sum")
            )
            city[_OUTSIDE_GROWTH_COL] = np.where(
                city["_seeded"] > 0,
                city["_asked"] / city["_seeded"].where(city["_seeded"] > 0, 1.0),
                1.0,
            )
            outside = city[key + [_OUTSIDE_GROWTH_COL]]
        else:
            outside = seeded[key].drop_duplicates().assign(**{_OUTSIDE_GROWTH_COL: 1.0})

        scaled = (
            seeded[key + [surveys.ZONE_CODE_COL, seed_column, _INSIDE_SHARE_COL]]
            .merge(per_zone, on=key + [surveys.ZONE_CODE_COL], how="left")
            .merge(outside, on=key, how="left")
        )
        scaled[_WEIGHTED_COL] = scaled[_WEIGHTED_COL].fillna(0.0)
        scaled[_OUTSIDE_GROWTH_COL] = scaled[_OUTSIDE_GROWTH_COL].fillna(1.0)
        scaled[zone_column] = scaled[seed_column] * (
            scaled[_WEIGHTED_COL]
            + (1.0 - scaled[_INSIDE_SHARE_COL]) * scaled[_OUTSIDE_GROWTH_COL]
        )
        zone_table = zone_table.merge(
            scaled[key + [surveys.ZONE_CODE_COL, zone_column]],
            on=key + [surveys.ZONE_CODE_COL],
            how="left",
        )
        zone_table[zone_column] = zone_table[zone_column].fillna(0.0)

    zone_table, reconciliation = _reconcile_zone_margins(
        zone_table, seed.pairs, key
    )
    zone_table = (
        zone_table.drop(columns=[_INSIDE_SHARE_COL])
        .sort_values(key + [surveys.ZONE_CODE_COL], kind="stable")
        .reset_index(drop=True)
    )

    result = ZoneMargins(
        table=zone_table,
        year=year,
        seed_year=seed.survey.year,
        unplaceable=pd.DataFrame(unplaceable_rows, columns=_UNPLACEABLE_COLUMNS),
        reconciliation=reconciliation,
    )
    if log is not None:
        _report_zone_margins(result, seeded, log)
    return result


def _in_unit(seed_column: str) -> str:
    """The working column holding the part of one seed margin that a unit holds."""
    return f"{seed_column}_IN_UNIT"


def _reconcile_zone_margins(
    zone_table: pd.DataFrame,
    seed_pairs: pd.DataFrame,
    key: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Make the two zone margins agree inside every block the seed lets travel within.

    **Not in the grand total, which is where the first version of this did it and which
    is not enough.** A trip can only be moved between cells the seed already holds, so
    each connected piece of the seed's support has to balance on its own: the origins in
    it must be asked for exactly what the destinations in it are asked for. A matrix with
    the given zero pattern and the given margins exists if and only if that holds, and
    when it does not the fitting does not fail — it runs to its iteration limit and
    returns a matrix that misses its margins. The 2015 cycling block splits into eight
    pieces and all eight disagreed; every mode of 2017 ran 2,000 iterations and came back
    with margin errors between 3 % and 113 %.

    **Why the margins arrive disagreeing at all.** They are built from growth factors
    interpolated per unit, and nothing in that construction knows anything about which
    zones the survey saw travel between. A zone whose only cell is its own diagonal is the
    clearest case: its row and its column are the same cell, so they must be equal, and
    the origin and destination growth factors of its unit are interpolated separately and
    are not.

    Same rule as at unit level — each side scaled to the mean of the two sums, so neither
    is privileged and neither moves by more than half the disagreement — applied once per
    piece instead of once per block. Reconciling every piece implies the grand total
    agrees, so this replaces the global correction rather than adding to it.

    **The pieces that need a large correction are tiny.** All but one piece of a block
    holds two or three zones and together they are hundredths of a per cent of the
    matrix's trips, which is why a 16 % correction inside one of them is a different kind
    of number from a 16 % correction to a block. Both are reported.
    """
    rows: list[dict[str, object]] = []
    blocks: list[pd.DataFrame] = []

    for (actor, day_type), block in zone_table.groupby(key, sort=False):
        block = block.copy()
        zones = list(block[surveys.ZONE_CODE_COL])
        position = {zone: index for index, zone in enumerate(zones)}
        cells = seed_pairs[
            (seed_pairs[config.ACTOR_TYPE_COL] == actor)
            & (seed_pairs[config.DAY_TYPE_COL] == day_type)
        ]
        labels = fitting.components_of_edges(
            cells[surveys.ZONE_ORIGIN_COL].map(position).to_numpy(),
            cells[surveys.ZONE_DESTINATION_COL].map(position).to_numpy(),
            len(zones),
            len(zones),
        )
        at_origin = block[ZONE_AT_ORIGIN_COL].to_numpy(dtype=float, copy=True)
        at_destination = block[ZONE_AT_DESTINATION_COL].to_numpy(dtype=float, copy=True)

        worst, moved, pieces = 0.0, 0, 0
        trips_moved = 0.0
        trips_before = float(at_origin.sum() + at_destination.sum()) / 2.0
        for label in np.unique(labels):
            # The same label can mark both origins and destinations, and the two halves
            # of the node list are what tells them apart.
            as_origin = labels[: len(zones)] == label
            as_destination = labels[len(zones):] == label
            if not (as_origin.any() or as_destination.any()):
                continue
            pieces += 1
            out_total = float(at_origin[as_origin].sum())
            in_total = float(at_destination[as_destination].sum())
            target = (out_total + in_total) / 2.0
            if out_total <= 0 and in_total <= 0:
                continue
            for values, inside, total in (
                (at_origin, as_origin, out_total),
                (at_destination, as_destination, in_total),
            ):
                if total <= 0:
                    # One side of the piece is asked for nothing and the other for
                    # something. Scaling cannot bridge that — there is nowhere to put the
                    # trips — so both are taken to zero, which is the only matrix the
                    # pattern admits. It is counted as a correction of 100 % so that it
                    # cannot pass as a rounding.
                    trips_moved += float(np.abs(values[inside]).sum())
                    values[inside] = 0.0
                    worst = max(worst, 1.0)
                    moved += int(inside.sum())
                    continue
                factor = target / total
                trips_moved += float(np.abs(values[inside] * (factor - 1.0)).sum())
                values[inside] = values[inside] * factor
                if abs(factor - 1.0) > 1e-12:
                    worst = max(worst, abs(factor - 1.0))
                    moved += int(inside.sum())
            if out_total <= 0 or in_total <= 0:
                # The other side has to go to zero as well, so that the piece balances
                # at zero rather than at half of one side.
                at_origin[as_origin] = 0.0
                at_destination[as_destination] = 0.0

        block[ZONE_AT_ORIGIN_COL] = at_origin
        block[ZONE_AT_DESTINATION_COL] = at_destination
        blocks.append(block)
        rows.append({
            config.ACTOR_TYPE_COL: actor,
            config.DAY_TYPE_COL: day_type,
            _COMPONENTS_COL: pieces,
            _MOVED_MARGINS_COL: moved,
            _WORST_COMPONENT_COL: worst,
            _TRIPS_MOVED_COL: trips_moved / 2.0,
            _TRIPS_IN_BLOCK_COL: trips_before,
        })

    return pd.concat(blocks, ignore_index=True), pd.DataFrame(
        rows, columns=_RECONCILIATION_COLUMNS
    )


def _report_zone_margins(
    margins: ZoneMargins, seeded: pd.DataFrame, log: RunLog
) -> None:
    """What the disaggregation of one year did, in the terms that could go wrong."""
    blocks = margins.table.groupby(
        [config.ACTOR_TYPE_COL, config.DAY_TYPE_COL], sort=False
    ).ngroups
    lost = float(margins.unplaceable[_UNPLACEABLE_TRIPS_COL].sum())
    placed = float(
        margins.table[[ZONE_AT_ORIGIN_COL, ZONE_AT_DESTINATION_COL]].sum().sum()
    ) / 2.0
    notes = [
        f"seeded on {margins.seed_year}: "
        f"{margins.table[surveys.ZONE_CODE_COL].nunique()} zone(s) over {blocks} "
        "mode-day block(s)",
        f"the part of a zone outside every unit follows {config.OUTSIDE_MARGIN_RULE}, "
        "which is a declared assumption and not a measurement",
        f"the support splits into "
        f"{int(margins.reconciliation[_COMPONENTS_COL].sum())} connected piece(s) across "
        f"the block(s), and the margins were made to agree inside each: "
        f"{int(margins.reconciliation[_MOVED_MARGINS_COL].sum())} margin(s) moved, "
        f"{margins.share_of_trips_reconciled * 100:.4f} % of the trips, worst single "
        f"piece {margins.worst_reconciliation * 100:.2f} %. A piece that does not "
        "balance on its own admits no matrix at all, whatever the grand total says",
    ]
    if lost > 0:
        where = "; ".join(
            f"{row[config.AREA_CODE_COL]} {row[config.ACTOR_TYPE_COL].lower()} "
            f"{row[config.DAY_TYPE_COL].lower()} {row[_UNPLACEABLE_TRIPS_COL]:,.0f}"
            for _, row in margins.unplaceable.head(6).iterrows()
        )
        notes.append(
            f"{lost:,.0f} trips per day, {lost / placed * 100:.4f} % of the margin, could "
            "not be placed because the seeding survey saw no travel of that mode anywhere "
            f"in the unit: {where}"
        )
    log.record(
        f"disaggregate the unit margins of {margins.year} onto the zones of "
        f"{margins.seed_year}",
        rows_in=len(seeded),
        rows_out=len(margins.table),
        notes=notes,
    )


# ---------------------------------------------------------------------------
# The fitting itself, and the apportionment of what comes out
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FittedYear:
    """One year's reconstructed matrix, and what the iteration did to get there."""

    year: int
    # The survey whose matrix was the seed. Kept whole rather than as a year, because
    # the apportionment needs its zones and its label.
    seed: surveys.SurveyTrips
    # The fitted matrix in the same long shape as `surveys.SurveyTrips.pairs`, so that
    # anything able to read a survey's matrix can read this one.
    pairs: pd.DataFrame
    # One row per actor type: iterations, whether it converged, the worst margin error
    # left, and the size of the problem. The run reports it and a reader can see which
    # blocks were easy and which were not.
    fits: pd.DataFrame

    @property
    def converged(self) -> bool:
        return bool(self.fits[_CONVERGED_COL].all())

    @property
    def worst_margin_error(self) -> float:
        return float(self.fits[_MARGIN_ERROR_COL].max()) if len(self.fits) else 0.0


@dataclass(frozen=True)
class BlockFit:
    """One block's fitted matrix, and the whole story of how it was reached."""

    matrix: np.ndarray
    short_walk: np.ndarray
    # Was the floor needed at all? False on every survey year and on every constructed
    # year whose margins the seed's own support could already reach.
    floored: bool
    # Both passes, so that a reader can see which of the two did the work.
    discovery_iterations: int
    iterations: int
    converged: bool
    worst_margin_error: float
    # Cells the floor opened and that survived the pruning, and what they carry. This is
    # the travel the reconstruction added and the survey never saw, and it is the number
    # the thesis has to quote when it says the method is conservative.
    opened_cells: int
    opened_trips: float
    # What the pruning dropped, in trips, and what the margins lost by it.
    pruned_cells: int
    pruned_trips: float


def fit_block(
    seed: np.ndarray,
    short_walk: np.ndarray,
    rows: np.ndarray,
    columns: np.ndarray,
) -> BlockFit:
    """Fit one actor type and kind of day, flooring the seed only if it has to.

    **The seed is tried as it is first, and that is not an optimisation.** A floored seed
    carries slightly more travel than the margins ask for, so fitting it scales everything
    down a little and the result is no longer exactly the seed — and D60's identity check,
    the one that decides whether any of this is right, is that a survey year fitted against
    its own margins comes back as itself. One cheap fitting on a sparse matrix keeps that
    exact, on the survey years and on every constructed year whose margins the survey's own
    support can already reach.

    **When it cannot, the floor opens every cell and the pruning closes almost all of them
    again.** The floor's only job is to find out which cells the margins need; once they
    are known, the cells carrying almost nothing are dropped and the matrix is fitted again
    on what is left, which comes out between one and two and a bit times the seed's own
    cell count and is feasible. So the first pass runs at a loose tolerance — it is
    answering a yes-or-no question about each cell — and the second is the one held to the
    real one.

    `config.RECONSTRUCTION_SEED_FLOOR`, `RECONSTRUCTION_PRUNE_BELOW` and
    `RECONSTRUCTION_DISCOVERY_TOLERANCE` carry the reasoning for each of the three numbers
    and what was measured to choose them.
    """
    occupied = seed > 0
    if not occupied.any():
        # A block with no travel at all. Its margins are zero by construction — the
        # disaggregation cannot give a margin to a zone with no seed — so the answer is
        # the empty matrix and there is nothing to fit.
        empty = np.zeros_like(seed)
        return BlockFit(empty, empty, False, 0, 0, True, 0.0, 0, 0.0, 0, 0.0)

    plain = fitting.fit(seed, rows, columns) if not _hopeless(seed, rows, columns) else None
    if plain is not None and plain.converged:
        return BlockFit(
            matrix=plain.matrix,
            short_walk=_carry_short_walk(plain.matrix, seed, short_walk, occupied),
            floored=False,
            discovery_iterations=0,
            iterations=plain.iterations,
            converged=True,
            worst_margin_error=plain.worst_margin_error,
            opened_cells=0,
            opened_trips=0.0,
            pruned_cells=0,
            pruned_trips=0.0,
        )

    # -- the floor ---------------------------------------------------------
    floored = np.where(
        occupied, seed, seed[occupied].mean() * config.RECONSTRUCTION_SEED_FLOOR
    )
    discovery = fitting.fit(
        floored, rows, columns, tolerance=config.RECONSTRUCTION_DISCOVERY_TOLERANCE
    )
    keep = discovery.matrix > config.RECONSTRUCTION_PRUNE_BELOW
    pruned_cells = int((discovery.matrix > 0).sum() - keep.sum())
    pruned_trips = float(discovery.matrix[~keep].sum())

    # -- the second pass, on what the first one found ----------------------
    support = np.where(keep, discovery.matrix, 0.0)
    if _hopeless(support, rows, columns):
        # The pruning closed a cell the margins needed. Measured over the thirteen years
        # this does not happen — the pruned support is infeasible by a thousandth of a
        # trip, which is rounding — but if it ever does, the unpruned fit is the honest
        # answer and the caller is told the matrix is denser than it should be.
        final = discovery
        keep = discovery.matrix > 0
        pruned_cells, pruned_trips = 0, 0.0
    else:
        final = fitting.fit(support, rows, columns)

    opened = keep & ~occupied
    return BlockFit(
        matrix=final.matrix,
        short_walk=_carry_short_walk(final.matrix, seed, short_walk, occupied),
        floored=True,
        discovery_iterations=discovery.iterations,
        iterations=final.iterations,
        converged=final.converged,
        worst_margin_error=final.worst_margin_error,
        opened_cells=int(opened.sum()),
        opened_trips=float(final.matrix[opened].sum()),
        pruned_cells=pruned_cells,
        pruned_trips=pruned_trips,
    )


def _hopeless(seed: np.ndarray, rows: np.ndarray, columns: np.ndarray) -> bool:
    """Would `fitting.fit` refuse these margins outright?

    Asked before calling it so that a refusal becomes "try the floor" rather than an
    exception travelling up through the stage. The two conditions it asks about are the
    cheap ones; the expensive one, `infeasible_by`, is not asked here because an
    infeasible-but-not-refused problem is exactly what the floor is for and finding out
    costs more than trying.
    """
    return bool(
        fitting.unfittable_margins(seed, rows, columns)
        or fitting.inconsistent_components(seed, rows, columns)
    )


def _carry_short_walk(
    fitted: np.ndarray,
    seed: np.ndarray,
    short_walk: np.ndarray,
    occupied: np.ndarray,
) -> np.ndarray:
    """The fifteen-minute column, carried by the multipliers the fitting applied.

    Iterative proportional fitting scales cell `(i, j)` by `R[i]·C[j]`, so the ratio of the
    fitted matrix to the seed recovers those multipliers wherever the seed is positive, and
    applying them to the narrower column is the same fitting run on that column. It is not
    a rescaling of the fitted total, which is what D39 refuses: each column goes through the
    apportionment on its own afterwards, exactly as it does for a survey.

    **A cell the floor opened was empty in both columns**, so the survey says nothing about
    how much of its travel is walking of fifteen minutes or more, and the block's own share
    is the only estimate there is. Zero would understate the pedestrian exposure of exactly
    the cells the reconstruction added, and the pedestrian is the mode whose series is read
    on this column. For the three motorised modes the share is one and this changes nothing,
    because their two columns are one number written twice.
    """
    factor = np.divide(fitted, seed, out=np.zeros_like(fitted), where=occupied)
    carried = short_walk * factor
    if not config.RECONSTRUCTION_SHORT_WALK_FROM_BLOCK:
        return carried
    total = float(seed[occupied].sum())
    share = float(short_walk[occupied].sum()) / total if total > 0 else 0.0
    opened = (fitted > 0) & ~occupied
    carried[opened] = fitted[opened] * share
    return carried


def fit_year(
    seed: surveys.SurveyTrips,
    margins: ZoneMargins,
    log: RunLog | None = None,
) -> FittedYear:
    """Scale the seeding survey's matrix until it produces this year's margins.

    One fitting per actor type and kind of day, never one for all of them together. The
    modes do not share a matrix — a cycling trip is not an alternative routing of a car
    trip — and fitting them jointly would let one mode's margin be satisfied out of
    another's cells.

    **The narrower pedestrian column is carried by the same multipliers and not fitted
    separately.** Iterative proportional fitting scales cell `(i, j)` by `R[i]·C[j]`, so
    the ratio of the fitted matrix to the seed recovers those multipliers cell by cell
    wherever the seed is positive, and applying them to the fifteen-minute column is the
    same fitting run on that column. It is not a rescaling of the fitted total, which is
    what D39 refuses: each column goes through the apportionment on its own afterwards,
    exactly as it does for a survey. What it does assume is that **the share of a cell
    that is long walking does not change between surveys**, which is an assumption of the
    same kind as the one the fitting already makes about the shape of the matrix, and it
    moves nothing at all for the three motorised modes, whose two columns are one number
    written twice.

    The alternative was to fit the fifteen-minute matrix against fifteen-minute endpoint
    margins, and those do not exist: `apportion_survey` builds its endpoint allocations
    from the full trip column alone. Adding them would mean changing a verified function
    and re-running the exposure, for a second definition of a quantity that is already
    determined by the first.
    """
    key = [config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]
    seed_pairs = seed.pairs
    blocks: list[pd.DataFrame] = []
    reports: list[dict[str, object]] = []

    for (actor, day_type), block in margins.table.groupby(key, sort=True):
        zones = sorted(block[surveys.ZONE_CODE_COL].unique())
        position = {zone: index for index, zone in enumerate(zones)}

        cells = seed_pairs[
            (seed_pairs[config.ACTOR_TYPE_COL] == actor)
            & (seed_pairs[config.DAY_TYPE_COL] == day_type)
        ]
        # Every zone of the seed's matrix is in its own margins by construction, so a
        # pair that cannot be placed in the grid would mean the margins and the matrix
        # were built from different things.
        unknown = set(cells[surveys.ZONE_ORIGIN_COL]) | set(cells[surveys.ZONE_DESTINATION_COL])
        unknown -= set(position)
        if unknown:
            raise ValueError(
                f"{len(unknown)} zone(s) of {seed.survey.label}'s {actor} {day_type} matrix "
                f"are not in the margins built from it, starting with "
                f"{sorted(unknown)[:4]}. The margins and the matrix have to be two views of "
                "the same travel or the fitting is scaling something else"
            )

        rows = cells[surveys.ZONE_ORIGIN_COL].map(position).to_numpy()
        columns = cells[surveys.ZONE_DESTINATION_COL].map(position).to_numpy()
        grid = np.zeros((len(zones), len(zones)))
        np.add.at(grid, (rows, columns), cells[surveys.TRIPS_COL].to_numpy())
        short = np.zeros_like(grid)
        np.add.at(short, (rows, columns), cells[surveys.TRIPS_OVER_15MIN_COL].to_numpy())

        # The narrower definition is a subset of the wider one, so a cell with short
        # walking and no walking at all cannot exist. Checked rather than assumed,
        # because the multipliers below are recovered by dividing by the wider one.
        impossible = int(((grid <= 0) & (short > 0)).sum())
        if impossible:
            raise ValueError(
                f"{impossible} cell(s) of {seed.survey.label}'s {actor} {day_type} matrix "
                "hold walking of fifteen minutes or more and no walking at all, which "
                "cannot be: the narrower definition is a subset of the wider one"
            )

        indexed = block.set_index(surveys.ZONE_CODE_COL)
        wanted_rows = indexed.loc[zones, ZONE_AT_ORIGIN_COL].to_numpy()
        wanted_columns = indexed.loc[zones, ZONE_AT_DESTINATION_COL].to_numpy()

        block_fit = fit_block(grid, short, wanted_rows, wanted_columns)
        fitted_short = block_fit.short_walk

        nonzero = np.nonzero(block_fit.matrix)
        blocks.append(pd.DataFrame({
            config.ACTOR_TYPE_COL: actor,
            config.DAY_TYPE_COL: day_type,
            surveys.ZONE_ORIGIN_COL: [zones[index] for index in nonzero[0]],
            surveys.ZONE_DESTINATION_COL: [zones[index] for index in nonzero[1]],
            surveys.TRIPS_COL: block_fit.matrix[nonzero],
            surveys.TRIPS_OVER_15MIN_COL: fitted_short[nonzero],
        }))
        reports.append({
            config.ACTOR_TYPE_COL: actor,
            config.DAY_TYPE_COL: day_type,
            _ZONES_COL: len(zones),
            _SEED_CELLS_COL: int((grid > 0).sum()),
            _FITTED_CELLS_COL: int(len(nonzero[0])),
            FLOORED_COL: block_fit.floored,
            _OPENED_CELLS_COL: block_fit.opened_cells,
            OPENED_TRIPS_COL: block_fit.opened_trips,
            _PRUNED_TRIPS_COL: block_fit.pruned_trips,
            BLOCK_TRIPS_COL: float(block_fit.matrix.sum()),
            _DISCOVERY_ITERATIONS_COL: block_fit.discovery_iterations,
            _ITERATIONS_COL: block_fit.iterations,
            _CONVERGED_COL: block_fit.converged,
            _MARGIN_ERROR_COL: block_fit.worst_margin_error,
        })

    fitted = FittedYear(
        year=margins.year,
        seed=seed,
        pairs=pd.concat(blocks, ignore_index=True) if blocks else seed_pairs.iloc[:0].copy(),
        fits=pd.DataFrame(reports, columns=_FIT_REPORT_COLUMNS),
    )
    if log is not None:
        _report_fit(fitted, margins, log)
    return fitted


def _report_fit(fitted: FittedYear, margins: ZoneMargins, log: RunLog) -> None:
    """What the iteration did, including the blocks that did not converge."""
    fits = fitted.fits
    stubborn = fits[~fits[_CONVERGED_COL]]
    notes = [
        f"seeded on {margins.seed_year}, {len(fits)} block(s) fitted one per actor type "
        "and kind of day, never jointly: the modes do not share a matrix",
        f"iterations {int(fits[_ITERATIONS_COL].min())}-{int(fits[_ITERATIONS_COL].max())}, "
        f"worst margin error {fitted.worst_margin_error:.2e} relative",
        "the fifteen-minute column is carried by the same multipliers the fitting "
        "applied to the full one, recovered cell by cell (D39)",
    ]
    floored = fits[fits[FLOORED_COL]]
    if len(floored):
        opened = float(floored[OPENED_TRIPS_COL].sum())
        total = float(fits[BLOCK_TRIPS_COL].sum())
        notes.append(
            f"{len(floored)} of {len(fits)} block(s) needed the floor, because the "
            "survey's own support could not reach their margins: "
            + ", ".join(
                f"{row[config.ACTOR_TYPE_COL].lower()} {row[_OPENED_CELLS_COL]:,} cell(s)"
                for _, row in floored.iterrows()
            )
        )
        notes.append(
            f"the floor added {opened:,.1f} trips per day on cells no survey saw travel "
            f"in, {opened / total * 100:.4f} % of the matrix, and the pruning dropped "
            f"{float(floored[_PRUNED_TRIPS_COL].sum()):,.1f}. This is the travel the "
            "reconstruction invented and the thesis has to quote it"
        )
    else:
        notes.append(
            "no block needed the floor: the survey's own support reached every margin, "
            "so nothing was invented and D60's identity holds exactly"
        )
    if len(stubborn):
        log.warn(
            "%d block(s) of %d did not reach the tolerance in %d iterations: %s. The "
            "exposure built from them is reported and not silently used",
            len(stubborn),
            len(fits),
            fitting.DEFAULT_MAX_ITERATIONS,
            "; ".join(
                f"{row[config.ACTOR_TYPE_COL]} {row[config.DAY_TYPE_COL].lower()} at "
                f"{row[_MARGIN_ERROR_COL]:.2e}"
                for _, row in stubborn.iterrows()
            ),
        )
    # Cells in, cells out, and exactly two things can move the count. **Without the floor
    # a fitting can only lose cells**, because both of its operations are multiplications:
    # an empty cell stays empty and a cell whose row or column margin is zero empties. The
    # floor is the only way a cell is ever gained, so the two causes separate cleanly and
    # the balance is the record of how much of each happened — which is the property that
    # makes the method conservative, checked on every year rather than argued once.
    seeded_cells = int(fits[_SEED_CELLS_COL].sum())
    opened_cells = int(fits[_OPENED_CELLS_COL].sum())
    emptied = seeded_cells + opened_cells - len(fitted.pairs)
    changes: list[tuple[int, str]] = []
    if opened_cells:
        changes.append((
            opened_cells,
            "cell(s) the floor opened and the pruning kept, which is the only way this "
            "stage gains a cell: the survey saw no travel in them",
        ))
    if emptied:
        changes.append((
            -emptied,
            "cell(s) driven to zero or pruned away, which is the only direction the "
            "fitting itself can move a cell count",
        ))
    log.record(
        f"fit the matrix of {margins.seed_year} to the margins of {fitted.year}",
        rows_in=seeded_cells,
        rows_out=len(fitted.pairs),
        changes=changes,
        notes=notes,
    )


def apportion(
    fitted: FittedYear,
    units: gpd.GeoDataFrame,
    log: RunLog,
) -> pd.DataFrame:
    """Push a fitted matrix through the apportionment the surveys already go through.

    **Nothing in `exposure.apportion_survey` is changed or duplicated**, and that is the
    point rather than an economy. It is the function that decides what reaches a unit —
    along the line between two zones, or over the area of one zone for a trip that stays
    inside it — and a second implementation of that decision would be a second answer to
    the question the study is about. A reconstructed year reaches its units the same way a
    surveyed year does, so the only thing it needs is to be handed over in the shape a
    survey arrives in.

    The seed is copied with its matrix replaced, and the copy never leaves this function.
    Its totals are recomputed from the fitted matrix rather than carried over, because a
    `SurveyTrips` whose `file_total` describes a different matrix from its `pairs` is the
    kind of object that reads correctly and is wrong — the defect the audit of the legacy
    code records as overwriting a source column with a derived value under the same name.
    """
    totals = fitted.pairs.groupby(
        [config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]
    )[surveys.TRIPS_COL].sum()
    totals_short = fitted.pairs.groupby(
        [config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]
    )[surveys.TRIPS_OVER_15MIN_COL].sum()
    as_a_survey = replace(
        fitted.seed,
        pairs=fitted.pairs,
        totals=totals,
        totals_over_15min=totals_short,
        file_total=float(fitted.pairs[surveys.TRIPS_COL].sum()),
    )
    allocation = exposure.apportion_survey(
        as_a_survey, fitted.seed.zones, units, log
    )
    per_unit = allocation.per_unit.copy()
    per_unit[config.YEAR_COL] = fitted.year

    # **Back onto the day-of-type basis, by the seeding survey's own universe share.**
    # The apportionment returns average-day trips because that is what the matrix holds,
    # and everything that compares two years reads the other basis (D38). The share used
    # is the seed's and not the year's, which is right rather than a shortcut: the share
    # is a property of a survey's design — how much of its universe had a reference day of
    # this kind — and a year with no survey has none. It is also exactly the inverse of
    # the multiplication inside the growth factor, so the two cancel and the fitted unit
    # margin comes back to the day-of-type margin that was asked for. Nothing is assumed
    # about any calendar.
    shares = fitted.seed.universe_shares
    per_unit[config.DAY_TYPE_UNIVERSE_SHARE_COL] = [
        float(shares.get(day, 1.0)) for day in per_unit[config.DAY_TYPE_COL]
    ]
    per_unit[config.TRIPS_PER_DAY_OF_TYPE_COL] = (
        per_unit[config.TRIPS_PER_AVERAGE_DAY_COL]
        / per_unit[config.DAY_TYPE_UNIVERSE_SHARE_COL]
    )
    per_unit[config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL] = (
        per_unit[surveys.TRIPS_OVER_15MIN_COL]
        / per_unit[config.DAY_TYPE_UNIVERSE_SHARE_COL]
    )
    # **The two endpoint allocations on the day-of-type basis too**, which is the basis the
    # margins are stated on. They are what `blended_margin_error` checks against, and they
    # have to be converted here, by this seed's own universe share, rather than after a
    # blend: a blended row has no single survey's share, so dividing the mixed endpoint
    # totals by any single number would compare two quantities carried on different bases.
    # Measured, getting this backwards puts a 2 to 4 % error on every blended year and
    # none at all on the years that rest on one survey, which is how it was found.
    for allocation, margin in (
        (config.TRIPS_AT_ORIGIN_COL, config.MARGIN_AT_ORIGIN_COL),
        (config.TRIPS_AT_DESTINATION_COL, config.MARGIN_AT_DESTINATION_COL),
    ):
        per_unit[margin] = (
            per_unit[allocation] / per_unit[config.DAY_TYPE_UNIVERSE_SHARE_COL]
        )
    # Which survey this year's travel was reconstructed from. It belongs on every row for
    # the reason every provenance column in this study does: a panel of thirteen years
    # built on four matrices, read without knowing which row rests on which, is thirteen
    # observations of something nobody can check.
    per_unit[SEED_YEAR_COL] = fitted.seed.survey.year
    return per_unit


_BLEND_KEY = (
    config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL, config.YEAR_COL,
)

# The margin error each seeding survey leaves on its own, and the one left after the two
# are blended. **Both, because only the pair says anything.** The fitted panel does not
# reproduce the unit margins exactly even when a year rests on a single survey — the
# connected-component reconciliation moves margins so that each piece can balance, and the
# travel outside the thirty units follows a declared rule — so an absolute bound on the
# blended error would be testing the disaggregation and not the blend. What the blend has
# to satisfy is that it adds nothing: see `verify`.
COMPONENT_MARGIN_ERROR_COL = "COMPONENT_MARGIN_ERROR"
BLENDED_MARGIN_ERROR_COL = "BLENDED_MARGIN_ERROR"


def blended_margin_error(blended: pd.DataFrame, wanted: pd.DataFrame) -> pd.Series:
    """Per mode, the worst relative error an apportioned result leaves on the year's margins.

    Called on each seeding survey's result and on the blend of them, because **the number
    only means something as a pair.** A year that rests on a single survey already leaves
    an error here — measured, up to 1.6e-3 in 2024 against zero at a survey year — because
    the disaggregation reconciles the margins inside each connected piece of the seed's
    support before the fitting ever runs, and because the travel outside the thirty units
    follows a declared rule. None of that is the blend's doing.

    What the blend has to satisfy is that **it adds nothing**: a convex combination of two
    results cannot sit further from the margins than the further of the two, since
    |Σ wᵢ(xᵢ − m)| ≤ Σ wᵢ|xᵢ − m| ≤ maxᵢ |xᵢ − m|. That inequality is what `verify`
    checks, and it is not a formality: it fails the moment a unit one survey reaches and
    the other does not is aligned wrongly, which is the one way this function's caller
    could be silently broken.

    The error is relative and the denominator is the margin itself, except where the
    margin is zero: a unit that generates no travel of a mode is an observation (see
    `unit_margins`) and an absolute error against it would divide by nothing, so those
    cells are measured absolutely and in the same trips per day as everything else.
    """
    key = [config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]
    against = blended.merge(wanted, on=key, how="left", suffixes=("", "_wanted"))
    worst = {}
    for actor, block in against.groupby(config.ACTOR_TYPE_COL):
        errors = []
        for margin in (config.MARGIN_AT_ORIGIN_COL, config.MARGIN_AT_DESTINATION_COL):
            # No division here: `apportion` already put the endpoint allocation on the
            # day-of-type basis with each component's own universe share, so both sides
            # of this comparison are on the same basis and the blend of them is linear.
            have = block[margin].to_numpy(dtype=float)
            want = block[f"{margin}_wanted"].to_numpy(dtype=float)
            gap = np.abs(have - want)
            errors.append(np.where(want > 0, gap / np.where(want > 0, want, 1.0), gap))
        worst[actor] = float(np.max(np.concatenate(errors))) if errors else 0.0
    return pd.Series(worst, name=BLENDED_MARGIN_ERROR_COL)


def blend_components(
    parts: list[tuple[int, float, pd.DataFrame]],
    blend: tuple[tuple[int, float], ...],
) -> pd.DataFrame:
    """Combine the apportioned results of the seeding surveys into the year's row.

    **The blending happens here and not before the fitting, because before the fitting
    there is nothing to blend.** The weekday surveys are keyed on three different zonings
    — 2011 and 2015 share `ZATs_2012_MAG`, 2019 has its own 1 141 zones and 2023 its own
    1 215 — so a cell of 2015 and a cell of 2019 are not the same object and cannot be
    averaged. Once each fitted matrix has gone through the apportionment, both describe
    the same thirty units, and that is where they become comparable. D64.

    **It is not an average of two answers, and that is checkable.** `exposure._spread`
    multiplies each pair's trips by a share that comes from geometry alone, so the
    apportionment is linear in the trips: blending the matrices and apportioning gives
    the same numbers as apportioning and blending, wherever both are defined. The only
    pair where both are defined is 2011 with 2015, and `tools/mezcla_de_semillas.py`
    checks that the two roads agree there before the method is used on the pairs where
    only one exists.

    Everything measured in trips is blended with the weights. Two columns are not, and
    each for its own reason. **The universe share is derived back from the two bases**,
    because each component converted to the day-of-type basis with its own survey's
    share and a blended row therefore has no single survey's: the ratio of its two bases
    is the share that makes the row self-consistent, and it lies between the two. **The
    count of origin-destination pairs touching a unit is the larger of the components**,
    which is a lower bound on the union of their supports and not the union itself —
    a count of distinct pairs cannot be recovered from two per-unit aggregates, and
    adding them would count twice every pair both surveys carry.
    """
    if len(parts) == 1:
        single = parts[0][2].copy()
        single[SEED_YEAR_COL] = parts[0][0]
        single[SEED_SECOND_YEAR_COL] = pd.NA
        single[SEED_WEIGHT_COL] = 1.0
        return single

    # The union of the keys, because a unit that one seed's matrix reaches and the other
    # does not has to arrive as a zero rather than disappear in an inner join.
    # `reset_index` y no por limpieza: `concat` conserva los índices de las dos piezas, así
    # que sin esto el marco queda con etiquetas repetidas y cada asignación posterior
    # depende de que sea posicional. Una de ellas dejaría de serlo sin avisar.
    keys = (pd.concat([part[[*_BLEND_KEY]] for _, _, part in parts])
            .drop_duplicates().reset_index(drop=True))
    quantities = [
        column for column in parts[0][2].columns
        if column not in _BLEND_KEY
        and column != config.DAY_TYPE_UNIVERSE_SHARE_COL
        and column != config.OD_PAIRS_TOUCHING_COL
        and pd.api.types.is_numeric_dtype(parts[0][2][column])
    ]

    blended = keys.copy()
    for column in quantities:
        blended[column] = 0.0
    touching = pd.Series(0, index=blended.index, dtype=int)
    for _, weight, part in parts:
        aligned = blended[[*_BLEND_KEY]].merge(part, on=[*_BLEND_KEY], how="left")
        for column in quantities:
            blended[column] = blended[column].to_numpy() + weight * (
                aligned[column].fillna(0.0).to_numpy()
            )
        touching = np.maximum(
            touching.to_numpy(), aligned[config.OD_PAIRS_TOUCHING_COL].fillna(0).to_numpy()
        )
        touching = pd.Series(touching, index=blended.index)

    blended[config.OD_PAIRS_TOUCHING_COL] = touching.astype(int).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(
            blended[config.TRIPS_PER_DAY_OF_TYPE_COL].to_numpy() > 0,
            blended[config.TRIPS_PER_AVERAGE_DAY_COL].to_numpy()
            / blended[config.TRIPS_PER_DAY_OF_TYPE_COL].to_numpy(),
            np.nan,
        )
    # A unit with no travel at all has no share to derive, and the weighted mean of the
    # components' is the only thing left that is not an invention.
    fallback = sum(weight * float(part[config.DAY_TYPE_UNIVERSE_SHARE_COL].iloc[0])
                   for _, weight, part in parts)
    blended[config.DAY_TYPE_UNIVERSE_SHARE_COL] = np.where(
        np.isfinite(share), share, fallback)

    blended[SEED_YEAR_COL] = blend[0][0]
    blended[SEED_SECOND_YEAR_COL] = blend[1][0]
    blended[SEED_WEIGHT_COL] = blend[0][1]
    return blended[list(parts[0][2].columns) + [SEED_SECOND_YEAR_COL, SEED_WEIGHT_COL]]


# ---------------------------------------------------------------------------
# The panel: a third variant beside D40's and D42's
# ---------------------------------------------------------------------------


def build(
    measured: interpolation.MeasuredExposure,
    panel: pd.DataFrame,
    units: gpd.GeoDataFrame,
    surveys_by_year: dict[int, surveys.SurveyTrips],
    log: RunLog,
    years: tuple[int, ...] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The whole reconstruction: margins, disaggregation, fitting, apportionment.

    Returns the panel and, beside it, one row per year and block saying what the fitting
    did to get there. **The second is not a log and belongs in the run's exported
    tables**: it carries how much travel the floor invented, and the thesis cannot claim
    the method is conservative without being able to quote that per block.

    **It is a third variant of the exposure panel and never a replacement**, which is the
    same rule D42's patch follows and for the same reason: what chooses between them
    downstream is a filter rather than a re-run, and a study that cannot show both cannot
    be argued with. Whether the fitting moves the exposure enough to move a coefficient is
    an empirical question, and the run that produces the answer is where the answer
    belongs.

    **The weekday alone**, per `config.RECONSTRUCTION_DAY_TYPES`, where the other two
    variants carry three kinds of day. The deliverable has to say so rather than leave a
    reader to find a table that is ragged in one variant and not the others.
    """
    years = years or tuple(config.REGRESSION_YEARS)
    day_types = [
        day for day in config.RECONSTRUCTION_DAY_TYPES
        if day in set(measured.table[config.DAY_TYPE_COL])
    ]
    if not day_types:
        raise ValueError(
            f"none of the day types the reconstruction is declared for "
            f"({', '.join(config.RECONSTRUCTION_DAY_TYPES)}) is in the measured exposure "
            "table, so there is nothing to reconstruct"
        )

    margins = unit_margins(measured, panel, units, log)
    zone_shares = {
        year: exposure.zone_area_shares(trips.zones, units, trips.survey, log)
        for year, trips in surveys_by_year.items()
    }

    blocks: list[pd.DataFrame] = []
    reports: list[pd.DataFrame] = []
    for year in years:
        for day_type in day_types:
            anchors = measured.anchors_of(day_type)
            blend = seeding_blend(year, anchors)
            missing = [seed_year for seed_year, _ in blend if seed_year not in surveys_by_year]
            if missing:
                raise ValueError(
                    f"{year}'s {day_type.lower()} is seeded on "
                    f"{', '.join(str(y) for y in missing)} and that survey was not read. "
                    "Every survey that seeds a year of the window has to be read before "
                    "the panel is built"
                )
            wanted = margins[
                (margins[config.YEAR_COL] == year)
                & (margins[config.DAY_TYPE_COL] == day_type)
            ]
            # One fitting per component, each against **the same margins**. That is what
            # makes the blend safe rather than an average of two answers to different
            # questions: two matrices with the same margins have those margins in any
            # convex combination, so D60's identity survives the mixing untouched.
            fitted_parts = []
            here: list[pd.DataFrame] = []
            for seed_year, weight in blend:
                seed = surveys_by_year[seed_year]
                zone_level = zone_margins(seed, zone_shares[seed_year], wanted, year, log)
                fitted = fit_year(seed, zone_level, log)
                per_unit = apportion(fitted, units, log)
                fitted_parts.append((seed_year, weight, per_unit))
                # Each survey's own distance from the margins, before anything is mixed.
                # It is the baseline the blended error is read against and it belongs to
                # this component alone.
                own = blended_margin_error(per_unit, wanted)
                here.append(
                    fitted.fits.assign(**{
                        config.YEAR_COL: year,
                        SEED_YEAR_COL: seed_year,
                        SEED_WEIGHT_COL: weight,
                    }).assign(**{
                        COMPONENT_MARGIN_ERROR_COL:
                            lambda rows: rows[config.ACTOR_TYPE_COL].map(own).astype(float),
                    })
                )
            blended = blend_components(fitted_parts, blend)
            # Carried on both components' rows, because the error belongs to what they
            # produced together and neither of them owns it alone.
            error = blended_margin_error(blended, wanted)
            for report in here:
                report[BLENDED_MARGIN_ERROR_COL] = (
                    report[config.ACTOR_TYPE_COL].map(error).astype(float)
                )
            reports.extend(here)
            blocks.append(blended)

    built = pd.concat(blocks, ignore_index=True)
    fits = pd.concat(reports, ignore_index=True)

    # -- the columns the panel is joined on --------------------------------
    populations = {
        year: population.for_year(panel, year) for year in sorted(set(built[config.YEAR_COL]))
    }
    built[config.POPULATION_COL] = [
        float(populations[year][code])
        for year, code in zip(built[config.YEAR_COL], built[config.AREA_CODE_COL])
    ]
    for level, rate in (
        (config.TRIPS_PER_DAY_OF_TYPE_COL, config.INTERPOLATED_RATE_COL),
        (config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL, config.INTERPOLATED_RATE_OVER_15MIN_COL),
    ):
        built[rate] = built[level] / built[config.POPULATION_COL]

    # **A year that is its own seed is measured and says so.** Nothing was fitted for it
    # and nothing disaggregated; its matrix went through the apportionment exactly as the
    # exposure route sends it, which is what D60's identity check proves. Calling it
    # FITTED would put the word on 480 rows that are observations.
    built[config.EXPOSURE_PROVENANCE_COL] = np.where(
        built[SEED_SECOND_YEAR_COL].isna() & (built[config.YEAR_COL] == built[SEED_YEAR_COL]),
        config.MEASURED_EXPOSURE,
        config.FITTED_EXPOSURE,
    )
    built[config.YEARS_TO_NEAREST_SURVEY_COL] = [
        min(abs(year - anchor) for anchor in measured.anchors_of(day))
        for year, day in zip(built[config.YEAR_COL], built[config.DAY_TYPE_COL])
    ]
    # Carried from the seeding surveys and not from the two years an interpolation rests
    # on: this variant rests on a mixture of survey matrices and on the margins of the
    # year, so the support of the result is the support of those surveys. **The rule for
    # combining two is `interpolation.support_of` and not a second one written here** —
    # the weaker of the two wins, because a value cannot be better supported than what it
    # was built from, and that is a decision the study already took once.
    support = {
        (row[config.AREA_CODE_COL], row[config.ACTOR_TYPE_COL], row[config.DAY_TYPE_COL],
         row[config.YEAR_COL]): row[config.SAMPLE_SUPPORT_COL]
        for _, row in measured.table.iterrows()
    }
    built[config.SAMPLE_SUPPORT_COL] = [
        interpolation.support_of(
            tuple(int(y) for y in (first, second) if not pd.isna(y)),
            {
                int(y): support[(code, actor, day, int(y))]
                for y in (first, second) if not pd.isna(y)
            },
        )
        for code, actor, day, first, second in zip(
            built[config.AREA_CODE_COL], built[config.ACTOR_TYPE_COL],
            built[config.DAY_TYPE_COL], built[SEED_YEAR_COL], built[SEED_SECOND_YEAR_COL],
        )
    ]
    built[config.EXPOSURE_VARIANT_COL] = config.FITTED_VARIANT
    # Exactly 1.0, and present because the variant is part of the identity and the columns
    # are not: a table whose three variants do not have the same columns cannot be read as
    # one table. D42's patch does not apply to this variant and the column says so by
    # being one everywhere rather than by being absent.
    built[config.PANDEMIC_PATCH_FACTOR_COL] = 1.0

    geometry = units[[config.AREA_CODE_COL, config.AREA_NAME_COL, config.AREA_UNIT_KM2_COL]]
    built = built.merge(geometry, on=config.AREA_CODE_COL, how="left", suffixes=("_drop", ""))
    built = built.drop(columns=[c for c in built.columns if c.endswith("_drop")])
    built[config.SCALE_COL] = config.active_scale().label
    built = (
        built[[*config.interpolated_exposure_columns(), SEED_YEAR_COL,
                SEED_SECOND_YEAR_COL, SEED_WEIGHT_COL]]
        .sort_values(
            [config.YEAR_COL, config.AREA_CODE_COL, config.ACTOR_TYPE_COL,
             config.DAY_TYPE_COL],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    fits = fits[[config.YEAR_COL, SEED_YEAR_COL, SEED_WEIGHT_COL,
                 COMPONENT_MARGIN_ERROR_COL, BLENDED_MARGIN_ERROR_COL,
                 *_FIT_REPORT_COLUMNS]].reset_index(drop=True)
    floored = fits[fits[FLOORED_COL]]
    invented = float(floored[OPENED_TRIPS_COL].sum()) if len(floored) else 0.0
    # The block totals and not the panel's, because the invented trips are counted on
    # the seeding survey's average-day basis and the panel is on the day-of-type one.
    total = float(fits[BLOCK_TRIPS_COL].sum())
    log.record(
        "assemble the fitted exposure panel",
        rows_in=len(margins),
        rows_out=len(built),
        changes=[(
            len(built) - len(margins),
            f"one row per unit, year and mode over {len(years)} year(s) and "
            f"{len(day_types)} day type(s), against {len(margins)} margin rows covering "
            "every year and day type of the window",
        )],
        notes=[
            f"variant={config.FITTED_VARIANT}, beside {config.INTERPOLATED_VARIANT} and "
            f"{config.PANDEMIC_PATCHED_VARIANT} rather than in place of them",
            f"day type(s): {', '.join(day_types)}. The other two variants carry "
            f"{len(config.DAY_TYPES)}; this one is scoped to the day the models read",
            f"{len(floored)} of {len(fits)} block(s) needed the floor, and it added "
            f"{invented:,.0f} trips per day on cells no survey saw travel in, "
            f"{invented / total * 100:.4f} % of the panel",
            f"{int((fits[_CONVERGED_COL]).sum())} of {len(fits)} block(s) reached the "
            f"tolerance; worst margin error "
            f"{float(fits[_MARGIN_ERROR_COL].max()):.2e} relative",
            "the measured rows are the years that are their own seed, where nothing was "
            "fitted and the matrix went through the apportionment untouched (D60)",
        ],
    )
    return built, fits



def patch_for_the_pandemic(
    built: pd.DataFrame,
    shock: "mobility_reports.MobilityShock",
    log: RunLog,
) -> tuple[pd.DataFrame, interpolation.PandemicPatch | None]:
    """The fitted panel, and the fitted panel with 2020 and 2021 rebuilt, as two variants.

    **D63: the patched one is what the models read**, and the unpatched one stays beside it
    for the reason D42 gives about its own pair — a study that cannot show the unpatched
    construction cannot be argued with, and what chooses between them downstream is a
    filter on `EXPOSURE_VARIANT` rather than a re-run.

    **The patch applies exactly here and not approximately.** Its factor is one number per
    mode and year, identical for every unit, and the apportionment is linear in the trips;
    so multiplying a unit's exposure by it is the same arithmetic as multiplying every cell
    of the fitted matrix by it and apportioning again. That is why this needs no second
    fitting, and it is worth checking rather than assuming, because if the factor ever
    varied by unit the equality would fail and nothing here would notice.

    **The factors come from this panel's own trend.** `interpolation.pandemic_factors`
    divides the shock by the height of the city curve at the patched year, which is what
    turns "2020 against 2022" into "2020 against what 2020 should have been" — and the two
    panels expect different things of 2020, so borrowing D40's factors would patch this one
    against an expectation it does not hold. The variant is passed through for that reason
    and not for symmetry.

    Nothing in `interpolation` is duplicated. Its `apply_pandemic_patch` is what keeps
    D39's two invariants alive through the patch — both levels and both rates multiplied by
    the same factor, so the fifteen-minute column stays a part of the full one and the two
    stay equal on the three modes with a single definition — and a second implementation of
    that would be a second place for the invariants to be lost.
    """
    columns = (*config.interpolated_exposure_columns(), SEED_YEAR_COL,
               SEED_SECOND_YEAR_COL, SEED_WEIGHT_COL)
    patch = interpolation.pandemic_factors(
        built, shock, log, variant=config.FITTED_VARIANT
    )
    both = interpolation.apply_pandemic_patch(
        built,
        patch,
        log,
        patched_variant=config.FITTED_PANDEMIC_PATCHED_VARIANT,
        columns=columns,
    )
    if patch is None:
        log.warn(
            "the fitted panel carries only the %s variant, so the regressions have nothing "
            "to read: %s is what `config.MODEL_EXPOSURE_VARIANT` asks for. The patch needs "
            "Google's community mobility reports; run the route again once they are "
            "readable. See D49 and D63",
            config.FITTED_VARIANT,
            config.MODEL_EXPOSURE_VARIANT,
        )
        return both, None

    # The equality the docstring above claims, checked on the panel rather than argued.
    # If a factor ever became unit-specific this is what would catch it.
    patched = both[both[config.EXPOSURE_VARIANT_COL] == config.FITTED_PANDEMIC_PATCHED_VARIANT]
    key = [config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL, config.YEAR_COL]
    against = patched.set_index(key)[
        [config.TRIPS_PER_DAY_OF_TYPE_COL, config.PANDEMIC_PATCH_FACTOR_COL]
    ].join(
        built.set_index(key)[[config.TRIPS_PER_DAY_OF_TYPE_COL]], rsuffix="_UNPATCHED"
    )
    implied = (
        against[f"{config.TRIPS_PER_DAY_OF_TYPE_COL}_UNPATCHED"]
        * against[config.PANDEMIC_PATCH_FACTOR_COL]
    )
    drift = float(np.max(np.abs(implied - against[config.TRIPS_PER_DAY_OF_TYPE_COL])))
    if drift > 1e-6:
        raise ValueError(
            f"the patched panel is not the unpatched one times its own factor: the worst "
            f"row differs by {drift:.3e} trips per day. The patch is only exact while its "
            "factor is the same for every unit of a mode and year, so either that stopped "
            "being true or the two variants were not built from the same rows"
        )

    in_patch = patched[config.YEAR_COL].isin(list(config.PANDEMIC_PATCH_YEARS))
    log.record(
        "patch the pandemic years of the fitted panel",
        rows_in=len(built),
        rows_out=len(both),
        changes=[(
            len(both) - len(built),
            f"the {config.FITTED_PANDEMIC_PATCHED_VARIANT} variant, which is the same "
            "panel under one more assumption and never rows to be added to the others",
        )],
        notes=[
            f"{int(in_patch.sum())} of {len(patched)} row(s) moved, which is "
            f"{', '.join(str(year) for year in config.PANDEMIC_PATCH_YEARS)} on the "
            f"{config.PANDEMIC_PATCH_DAY_TYPE.lower()}; the rest carry a factor of exactly 1",
            "factors: " + "; ".join(
                f"{mode.lower()} {year} x{factor:.3f}"
                for (mode, year), factor in sorted(patch.factors.items())
            ),
            "recomputed from the fitted panel's own trend and not borrowed from D40's, "
            "because a factor divides by the height of the curve it is patching",
            f"the patched variant is what config.MODEL_EXPOSURE_VARIANT asks for "
            f"({config.MODEL_EXPOSURE_VARIANT}); the unpatched one stays beside it (D63)",
            f"checked exact: the patched level is the unpatched level times its own factor "
            f"to {drift:.1e} trips per day, which holds because the factor is one number "
            "per mode and year and the apportionment is linear in the trips",
        ],
    )
    return both, patch


# ---------------------------------------------------------------------------
# Exporting, and checking what was exported
# ---------------------------------------------------------------------------


def export(built: pd.DataFrame, fits: pd.DataFrame, log: RunLog) -> dict[str, Path]:
    """Write the fitted panel and the record of what the fitting did.

    Two tables and not one. The panel is what anything downstream joins to; the fits say
    how each of its rows was reached, and they are at a different grain — one row per year
    and block rather than per unit — so folding them in would repeat thirty identical rows
    thirty times and invite somebody to sum them.
    """
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    tables = (
        (config.FITTED_EXPOSURE_FILENAME, built),
        (config.FITTED_BLOCKS_FILENAME, fits),
    )
    for name, table in tables:
        for suffix in (".csv", ".parquet"):
            path = data_dir / f"{name}{suffix}"
            if suffix == ".csv":
                table.to_csv(path, index=False, encoding="utf-8")
            else:
                table.to_parquet(path, index=False)
            written[path.name] = path
    log.record(
        "export the fitted exposure panel and its fitting record",
        rows_in=len(built) + len(fits),
        rows_out=len(built) + len(fits),
        notes=[f"{name}: {len(table):,} row(s)" for name, table in tables],
    )
    return written


def verify(
    built: pd.DataFrame,
    fits: pd.DataFrame,
    measured: interpolation.MeasuredExposure,
    units: gpd.GeoDataFrame,
    log: RunLog,
) -> bool:
    """Everything the run must be able to say about the panel before it is trusted.

    **The first check is the one D60 declares as deciding**, and the rest are in the order
    of what they would mean if they failed. A run that writes this panel without them is a
    run that cannot be told apart from one that wrote it wrong.
    """
    checks: list[tuple[str, bool, str]] = []
    day_types = sorted(set(built[config.DAY_TYPE_COL]))

    declared = [*config.interpolated_exposure_columns(), SEED_YEAR_COL,
                SEED_SECOND_YEAR_COL, SEED_WEIGHT_COL]
    checks.append((
        "the table carries exactly the declared columns, in the declared order",
        list(built.columns) == declared,
        f"{len(built.columns)} of {len(declared)} declared; the extra ones over D40's "
        f"panel are {SEED_YEAR_COL}, {SEED_SECOND_YEAR_COL} and {SEED_WEIGHT_COL}",
    ))

    # **The identity.** A year that is its own seed is not fitted and not disaggregated:
    # its matrix goes through the apportionment exactly as the exposure route sends it, so
    # any difference there is a defect of this stage and not of the method.
    # On the unpatched variant alone. A patched row of 2020 is deliberately not the
    # survey's number, so folding the two together would make the identity fail because of
    # the patch rather than because of a defect — and the patch is checked by its own
    # arithmetic in `patch_for_the_pandemic`.
    measured_rows = built[
        (built[config.EXPOSURE_PROVENANCE_COL] == config.MEASURED_EXPOSURE)
        & (built[config.EXPOSURE_VARIANT_COL] == config.FITTED_VARIANT)
    ]
    key = [config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL,
           config.YEAR_COL]
    against = measured_rows.merge(
        measured.table, on=key, suffixes=("_fitted", "_measured")
    )
    worst_identity = max(
        (
            float(np.max(np.abs(against[f"{column}_fitted"] - against[f"{column}_measured"])))
            for column in (config.TRIPS_PER_DAY_OF_TYPE_COL,
                           config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL)
        ),
        default=float("inf"),
    ) if len(against) else float("inf")
    checks.append((
        "D60's identity: a year that is its own seed reproduces the measured exposure",
        len(against) == len(measured_rows)
        and worst_identity <= config.FITTED_IDENTITY_TOLERANCE,
        f"{len(measured_rows)} measured row(s), worst difference {worst_identity:.2e} "
        f"trips per day against the {config.FITTED_IDENTITY_TOLERANCE:.0e} allowed",
    ))

    # -- the blend: the weights, and what they must not have broken ---------
    # **A weight is not a description, it is arithmetic that ran.** These three check the
    # blend itself rather than its result, because a wrong weight produces a panel that is
    # perfectly well formed and quietly wrong — the one failure mode this stage has that
    # nothing else here would catch.
    weights = built[SEED_WEIGHT_COL].to_numpy(dtype=float)
    alone = built[SEED_SECOND_YEAR_COL].isna().to_numpy()
    paired = built[~alone]
    brackets = (
        (paired[SEED_YEAR_COL].to_numpy(dtype=float) < paired[config.YEAR_COL].to_numpy())
        & (paired[config.YEAR_COL].to_numpy() < paired[SEED_SECOND_YEAR_COL].to_numpy(dtype=float))
    ) if len(paired) else np.array([True])
    checks.append((
        "the blend weights close: between zero and one, and exactly one when a year "
        "rests on a single survey",
        bool(((weights >= 0.0) & (weights <= 1.0)).all())
        and bool((weights[alone] == 1.0).all())
        and bool(brackets.all()),
        f"{int(alone.sum())} row(s) on one survey and {len(paired)} on two; "
        f"weights in [{weights.min():.3f}, {weights.max():.3f}]; "
        f"{int(brackets.sum()) if len(paired) else 0} of {len(paired)} paired row(s) "
        "framed by their two surveys",
    ))

    # **The claim the blend rests on, checked rather than argued: it must add nothing.**
    # Not "the blended result sits on the margins" — no result sits on the margins, because
    # the disaggregation reconciles them inside each connected piece of the seed's support
    # before any fitting happens, and that is a property of D60 rather than of the blend.
    # What a convex combination cannot do is land further from the margins than the further
    # of the two things combined, so the comparison is against the components themselves
    # and the tolerance only has to cover floating point.
    per_block = fits.groupby(
        [config.YEAR_COL, config.ACTOR_TYPE_COL]
    )[[COMPONENT_MARGIN_ERROR_COL, BLENDED_MARGIN_ERROR_COL]].max()
    slack = (per_block[BLENDED_MARGIN_ERROR_COL]
             - per_block[COMPONENT_MARGIN_ERROR_COL])
    worst_slack = float(slack.max()) if len(slack) else float("inf")
    checks.append((
        "blending added nothing: no blend sits further from the margins than the survey "
        "it was blended from",
        worst_slack <= config.FITTED_BLEND_MARGIN_TOLERANCE,
        f"worst excess over the component that was already furthest {worst_slack:+.2e} "
        f"against the {config.FITTED_BLEND_MARGIN_TOLERANCE:.0e} allowed; the components "
        f"themselves reach {float(per_block[COMPONENT_MARGIN_ERROR_COL].max()):.2e} "
        "relative, which the disaggregation leaves and the blend inherits",
    ))

    variants = sorted(set(built[config.EXPOSURE_VARIANT_COL]))
    expected = (
        built[config.YEAR_COL].nunique()
        * len(set(units[config.AREA_CODE_COL]))
        * built[config.ACTOR_TYPE_COL].nunique()
        * len(day_types)
        * len(variants)
    )
    checks.append((
        "the panel is a complete grid, so a zero and a missing cell cannot look alike",
        len(built) == expected,
        f"{len(built):,} row(s) against {expected:,}: "
        f"{built[config.YEAR_COL].nunique()} year(s), "
        f"{len(set(units[config.AREA_CODE_COL]))} unit(s), "
        f"{built[config.ACTOR_TYPE_COL].nunique()} mode(s), {len(day_types)} day type(s), "
        f"{len(variants)} variant(s)",
    ))

    checks.append((
        "every row names a unit of the study",
        set(built[config.AREA_CODE_COL]) <= set(units[config.AREA_CODE_COL]),
        f"{built[config.AREA_CODE_COL].nunique()} of "
        f"{len(set(units[config.AREA_CODE_COL]))}",
    ))

    stubborn = fits[~fits[_CONVERGED_COL]]
    checks.append((
        "every block reached the fitting tolerance",
        not len(stubborn),
        f"{len(fits) - len(stubborn)} of {len(fits)} block(s); worst margin error "
        f"{float(fits[_MARGIN_ERROR_COL].max()):.1e} relative"
        + ("" if not len(stubborn) else "; " + "; ".join(
            f"{int(row[config.YEAR_COL])} {row[config.ACTOR_TYPE_COL].lower()} at "
            f"{row[_MARGIN_ERROR_COL]:.1e}" for _, row in stubborn.head(6).iterrows()
        )),
    ))

    floored = fits[fits[FLOORED_COL]]
    invented = float(floored[OPENED_TRIPS_COL].sum()) if len(floored) else 0.0
    in_blocks = float(fits[BLOCK_TRIPS_COL].sum())
    share = invented / in_blocks if in_blocks > 0 else 0.0
    checks.append((
        "the floor invented no more travel than the configuration allows",
        share <= config.FITTED_INVENTED_LIMIT,
        f"{len(floored)} of {len(fits)} block(s) needed it; {invented:,.0f} of "
        f"{in_blocks:,.0f} trips per day on cells no survey saw travel in, "
        f"{share * 100:.4f} % against the {config.FITTED_INVENTED_LIMIT * 100:.2f} % "
        "allowed",
    ))

    recovered = built[config.INTERPOLATED_RATE_COL] * built[config.POPULATION_COL]
    drift = float(np.max(np.abs(recovered - built[config.TRIPS_PER_DAY_OF_TYPE_COL])))
    # **`SEED_SURVEY_YEAR_SECOND` is the one column where a null is the answer**, and it is
    # left out of this check rather than filled with a sentinel: it is empty exactly on the
    # rows that rest on a single survey, and a year written twice would make a row look
    # blended when it is not. How many of them there are is checked by the weights above.
    filled = [column for column in declared if column != SEED_SECOND_YEAR_COL]
    checks.append((
        "nothing null, nothing negative, and the rate times the population is the level",
        not int(built[filled].isna().sum().sum())
        and not int((built[config.TRIPS_PER_DAY_OF_TYPE_COL] < 0).sum())
        and drift <= 1e-6,
        f"{int(built[filled].isna().sum().sum())} null(s) outside "
        f"{SEED_SECOND_YEAR_COL}, where {int(built[SEED_SECOND_YEAR_COL].isna().sum())} "
        "row(s) rest on one survey; "
        f"{int((built[config.TRIPS_PER_DAY_OF_TYPE_COL] < 0).sum())} negative(s), "
        f"level recovered to {drift:.1e} trips per day",
    ))

    # Every value of these two columns has a colour and a Spanish label declared beside
    # it. A value nobody declared fails in a figure, far from here and without saying why.
    undeclared = sorted(
        (set(built[config.EXPOSURE_VARIANT_COL]) - set(config.EXPOSURE_VARIANTS))
        | (set(built[config.EXPOSURE_PROVENANCE_COL]) - set(config.EXPOSURE_PROVENANCES))
    )
    checks.append((
        "the variant and the provenance hold declared values only",
        not undeclared,
        f"variant {sorted(set(built[config.EXPOSURE_VARIANT_COL]))}, provenance "
        f"{sorted(set(built[config.EXPOSURE_PROVENANCE_COL]))}"
        + (f"; undeclared: {', '.join(undeclared)}" if undeclared else ""),
    ))

    # **The variant the models ask for has to be in the table**, and this is the check
    # that says so. `MODEL_EXPOSURE_VARIANT` is read by the regressions, so a run that
    # wrote the panel without it would leave them reading nothing and finding out far from
    # here. The pair is the unpatched construction and the patched one, never one alone:
    # D63 keeps both for D42's reason.
    checks.append((
        "the panel carries the variant the models read, beside the unpatched one",
        set(variants) == {config.FITTED_VARIANT, config.FITTED_PANDEMIC_PATCHED_VARIANT}
        and config.MODEL_EXPOSURE_VARIANT in variants,
        f"{', '.join(variants)}; config.MODEL_EXPOSURE_VARIANT asks for "
        f"{config.MODEL_EXPOSURE_VARIANT}",
    ))

    # The patch moved what it was supposed to and nothing else. Every row outside its two
    # years carries a factor of exactly one, in both variants.
    outside = built[~built[config.YEAR_COL].isin(list(config.PANDEMIC_PATCH_YEARS))]
    moved = built[
        (built[config.EXPOSURE_VARIANT_COL] == config.FITTED_PANDEMIC_PATCHED_VARIANT)
        & built[config.YEAR_COL].isin(list(config.PANDEMIC_PATCH_YEARS))
    ]
    checks.append((
        "the patch moved its own two years and left every other row at a factor of one",
        bool((outside[config.PANDEMIC_PATCH_FACTOR_COL] == 1.0).all())
        and bool((moved[config.PANDEMIC_PATCH_FACTOR_COL] != 1.0).all() if len(moved) else True),
        f"{len(moved)} row(s) patched in "
        f"{', '.join(str(year) for year in config.PANDEMIC_PATCH_YEARS)}; "
        f"{len(outside)} row(s) outside them all at exactly 1.0",
    ))

    width = max(len(name) for name, _, _ in checks)
    rendered = [
        f"{'check'.ljust(width)}  {'result':>8}  detail",
        f"{'-' * width}  {'-' * 8}  ------",
    ]
    for name, ok, detail in checks:
        rendered.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("fitted exposure verification:", "\n".join(rendered))

    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("fitted exposure verification FAILED")
    return passed


def compare_with_interpolated(
    built: pd.DataFrame, d40: pd.DataFrame, log: RunLog
) -> pd.DataFrame:
    """The fitted exposure against D40's, which is the question the variant exists for.

    **Reported and not acted on.** D54 says the comparison belongs in the run that
    produces it, and what it is for is to stop a reader having to take on faith that
    reconstructing the matrix changes anything. If the two were the same everywhere, the
    honest conclusion would be that the extra assumption buys nothing — and that
    conclusion would be worth having too.

    Measured over the thirteen years, the answer is the interesting one: **the two agree
    on the aggregate almost exactly and disagree about individual units by a great deal.**
    The mean ratio is 1.000 for the car and the motorcycle, 1.002 for the bicycle and
    0.990 for the pedestrian, and the median is 1.0 in all four; the range for cycling runs
    from 0.49 to 2.35. That is the case for doing this: a rate interpolated per unit gives
    every unit its own curve and knows nothing about where the travel goes, and the fitting
    is what puts that back.
    """
    column = config.MODEL_EXPOSURE_COLUMN
    key = [config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL,
           config.YEAR_COL]
    unpatched = d40[d40[config.EXPOSURE_VARIANT_COL] == config.INTERPOLATED_VARIANT]
    both = (
        built.set_index(key)[[column, config.EXPOSURE_PROVENANCE_COL]]
        .join(unpatched.set_index(key)[[column]], how="inner", rsuffix="_INTERPOLATED")
        .rename(columns={column: _FITTED_LEVEL_COL,
                         f"{column}_INTERPOLATED": _INTERPOLATED_LEVEL_COL})
        .reset_index()
    )
    both[_RATIO_COL] = both[_FITTED_LEVEL_COL] / both[_INTERPOLATED_LEVEL_COL].where(
        both[_INTERPOLATED_LEVEL_COL] > 0, np.nan
    )
    constructed = both[both[config.EXPOSURE_PROVENANCE_COL] != config.MEASURED_EXPOSURE]
    rows = [
        f"{'mode':<12}  {'cells':>7}  {'median':>8}  {'quartiles':>15}  {'range':>15}",
        f"{'-' * 12}  {'-' * 7}  {'-' * 8}  {'-' * 15}  {'-' * 15}",
    ]
    for actor, block in constructed.groupby(config.ACTOR_TYPE_COL):
        ratio = block[_RATIO_COL]
        rows.append(
            f"{actor:<12}  {len(block):>7,}  {ratio.median():>8.4f}  "
            f"{f'{ratio.quantile(0.25):.3f}-{ratio.quantile(0.75):.3f}':>15}  "
            f"{f'{ratio.min():.3f}-{ratio.max():.3f}':>15}"
        )
    measured_rows = both[
        both[config.EXPOSURE_PROVENANCE_COL] == config.MEASURED_EXPOSURE
    ]
    if len(measured_rows):
        rows.append("")
        rows.append(
            f"the {len(measured_rows)} measured cell(s) agree to "
            f"{float(np.max(np.abs(measured_rows[_RATIO_COL] - 1.0))):.1e}, because "
            "neither variant constructs anything in a survey year"
        )
    rows.append(
        "the two agree on the aggregate and disagree about individual units, which is "
        "what the variant exists to show: an interpolated rate gives a unit its own curve "
        "and knows nothing about where the travel goes"
    )
    log.table(
        "the fitted exposure against D40's, over the constructed years:", "\n".join(rows)
    )
    return both
