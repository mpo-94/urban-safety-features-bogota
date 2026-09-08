"""Travel exposure per territorial unit, measured two ways from two sources.

This is not an urban predictor and the separation is deliberate. A predictor says
what a place is built like; exposure says how much traffic there is in it to be
hurt. In a rate model they sit on opposite sides, so the exposure never enters the
predictor correlation matrix and never appears in either figure set: a row for it
there would invite a reader to compare it with variables it does not compete with.

**There are two halves to this module and they measure different things.** The
first half measures the delivered desire lines: 181 lines of one mode, already
drawn, which is what the pipeline read before the mobility surveys arrived. The
second builds the lines from the survey itself, for four modes, four years and
three kinds of day, and that is the variable the study now uses. The delivered
layer stays because several finished figures were measured on it and they have to
remain reproducible, and because it turned out to be worth keeping as evidence:
it is a 9.6% sample of the 2019 survey and D38 records how that was established.

The one operation the two halves must not do differently — cutting a line at the
unit boundaries and measuring the pieces — lives in `predictors` and is called by
both, so the kilometres of a line inside a unit cannot come out two slightly
different ways depending on which half asked.

What follows immediately below is the first half. The second begins at "Exposure
built from the survey".

**What the delivered source is.** Each line runs from the centroid of an origin zone of the
mobility survey to the centroid of a destination zone, and carries the survey's
own expansion of the trip it stands for. Two expansions arrive on every record and
they are different quantities, which is the whole difficulty:

* `f_exp` is the expansion factor — how many real trips one surveyed trip stands
  for on a day.
* `ResultadoExp` is that factor multiplied by the number of days per week the trip
  is made. It counts trips per week.

The legacy pipeline multiplied a length by `f_exp` and wrote the product back over
a column called `len_km`, so a sum of kilometre-trips left the pipeline named as
kilometres of infrastructure and 674,158 of them were reported for a layer 1,219 km
long. Nothing here can repeat that: every quantity has a column of its own, the
unit and the period are in the column's name, and no column is overwritten by
anything derived from it.

**How a trip is allocated.** A line crosses three units in the median and up to
ten, so it has to be divided. Each line gives every unit it crosses the share of
its trips that matches the share of its length falling inside that unit: a line
worth 100 trips lying 50%, 30% and 20% across three units contributes 50, 30 and
20. What leaves the study area is not redistributed; it is measured, reported, and
used to check that the parts add up to the layer.

**The limitation that has to travel with the number.** The lines are straight.
Sinuosity is exactly 1.000 on all 181 of them — the intermediate vertices are the
densification of a geodesic, and the first and last land on the declared origin and
destination coordinates to the millimetre. So the kilometres inside a unit are a
share of a chord that nobody rode, not distance pedalled there. Two alternative
allocations that do not depend on the geometry, counting the trip at its origin
and at its destination, are measured on every run and exported beside the variable
for exactly that reason. They are not model variables; they exist so the
sensitivity of a result to the rule can be shown rather than asserted. See D35.

Run it:

    python -m src.run_pipeline exposure
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

try:  # regular package import
    from src import config, maps, population, predictors, surveys
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import maps  # type: ignore[no-redef]
    import population  # type: ignore[no-redef]
    import predictors  # type: ignore[no-redef]
    import surveys  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# Working columns, private to this module. Named apart from the configured ones
# so it is obvious at a glance that none of them reaches an exported table.
_LINE_ID_COL = "_LINE"
_LINE_KM_COL = "_LINE_TOTAL_KM"
_SHARE_COL = "_SHARE_INSIDE"
_COVERED_COL = "_SHARE_COVERED"


@dataclass(frozen=True)
class Apportionment:
    """The allocation of one layer over the units, with everything needed to check it.

    The totals travel with the per-unit table rather than being recomputed later
    from it, because the point of the check is to compare what was allocated
    against what came out of the file, and a total derived from the allocation
    would agree with it by construction.
    """

    layer: config.SurveyLineLayer
    per_unit: pd.DataFrame
    lines_read: int
    lines_reaching_a_unit: int
    layer_weekly: float
    layer_daily: float
    layer_km: float
    outside_weekly: float
    outside_daily: float
    outside_km: float
    largest_covered_share: float

    @property
    def allocated_weekly(self) -> float:
        return float(self.per_unit[self.layer.column(config.TRIPS_WEEKLY_SUFFIX)].sum())

    @property
    def allocated_daily(self) -> float:
        return float(self.per_unit[self.layer.column(config.TRIPS_DAILY_SUFFIX)].sum())

    @property
    def allocated_km(self) -> float:
        return float(self.per_unit[self.layer.column(config.LINE_KM_INSIDE_SUFFIX)].sum())


# ---------------------------------------------------------------------------
# Reading the layer
# ---------------------------------------------------------------------------


def read_layer(layer: config.SurveyLineLayer, log: RunLog) -> gpd.GeoDataFrame:
    """Read the declared layer and hold the declaration to account.

    Every column the measurement uses is named in the configuration and read
    through it, so a column renamed in a future delivery raises here rather than
    quietly measuring something else. The mode is checked rather than trusted: the
    whole table is labelled with one mode, and a layer that turned out to hold two
    would make that label a lie.
    """
    try:
        path = config.resolve_source_path(layer.path)
    except FileNotFoundError as missing:
        raise FileNotFoundError(
            f"{layer.name}: the declared source {layer.path} does not exist; "
            f"layer {layer.source_layer!r}, file {layer.source_file!r}"
        ) from missing

    lines = gpd.read_file(path, columns=list(layer.attribute_columns))

    absent = [column for column in layer.attribute_columns if column not in lines.columns]
    if absent:
        raise ValueError(
            f"{layer.name}: {path.name} does not carry {', '.join(absent)}. The .dbf format "
            "truncates a field name to ten characters, so the declaration spells the columns "
            "the way the delivered file spells them, truncation included"
        )

    present = set(lines.geom_type.dropna())
    unexpected = sorted(present - set(config.GEOMETRY_TYPES[layer.geometry]))
    if unexpected:
        raise ValueError(
            f"{layer.name}: declared as {layer.geometry} geometry, but {layer.source_file} "
            f"holds {', '.join(unexpected)}"
        )

    modes = sorted(lines[layer.mode_column].dropna().unique())
    if modes != [layer.mode_value]:
        raise ValueError(
            f"{layer.name}: declared to cover {layer.mode_value!r} only, but "
            f"{layer.mode_column} holds {modes}. Every row of the exported table is labelled "
            f"{layer.mode!r}, and that label would be wrong"
        )

    for column in (layer.weekly_weight_column, layer.daily_weight_column):
        values = pd.to_numeric(lines[column], errors="coerce")
        if values.isna().any() or (values < 0).any():
            raise ValueError(
                f"{layer.name}: {column} has {int(values.isna().sum())} unreadable and "
                f"{int((values < 0).sum())} negative value(s); a trip count is neither"
            )
        lines[column] = values.astype(float)

    lines = lines.to_crs(epsg=config.SOURCE_CRS)
    log.info(
        "%s: read %d line(s) from %s/%s, all of mode %s",
        layer.name,
        len(lines),
        layer.source_layer,
        layer.source_file,
        layer.mode_value,
    )
    return lines


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------


def apportion(
    lines: gpd.GeoDataFrame,
    units: gpd.GeoDataFrame,
    layer: config.SurveyLineLayer,
    log: RunLog,
) -> Apportionment:
    """Split each line's trips between the units it crosses, by share of length.

    The share is the line's length inside the unit over the line's whole length,
    which means the shares of a line that leaves the study area add to less than
    one. That remainder is the point of the `outside_*` totals: it is measured
    rather than absorbed, so the check downstream can be that what was allocated
    plus what fell outside equals what the file holds.
    """
    projected = lines.to_crs(epsg=config.PROJECTED_CRS).reset_index(drop=True)
    projected[_LINE_ID_COL] = np.arange(len(projected))
    projected[_LINE_KM_COL] = projected.geometry.length / 1000.0

    # A line of no length has no shares to compute and would divide by zero. None
    # exists in the delivered layer, and the failure it would otherwise cause is a
    # null in one unit rather than a message.
    degenerate = projected[_LINE_KM_COL] * 1000.0 <= config.EXPOSURE_MIN_LINE_LENGTH_M
    if degenerate.any():
        raise ValueError(
            f"{layer.name}: {int(degenerate.sum())} line(s) have no length, so the share of "
            "them falling inside a unit is undefined"
        )

    weekly, daily = layer.weekly_weight_column, layer.daily_weight_column
    fragments = predictors.split_lines_by_unit(projected, units, _LINE_ID_COL)
    fragments = fragments.merge(
        projected[[_LINE_ID_COL, _LINE_KM_COL, weekly, daily]], on=_LINE_ID_COL, how="left"
    )
    fragments[_SHARE_COL] = fragments[predictors.FRAGMENT_LENGTH_COL] / fragments[_LINE_KM_COL]
    weekly_out = layer.column(config.TRIPS_WEEKLY_SUFFIX)
    daily_out = layer.column(config.TRIPS_DAILY_SUFFIX)
    fragments[weekly_out] = fragments[weekly] * fragments[_SHARE_COL]
    fragments[daily_out] = fragments[daily] * fragments[_SHARE_COL]

    per_unit = fragments.groupby(config.AREA_CODE_COL).agg(
        **{
            weekly_out: (weekly_out, "sum"),
            daily_out: (daily_out, "sum"),
            layer.column(config.LINE_KM_INSIDE_SUFFIX): (predictors.FRAGMENT_LENGTH_COL, "sum"),
            layer.column(config.LINES_TOUCHING_SUFFIX): (_LINE_ID_COL, "nunique"),
        }
    )

    # How much of each line the study area accounts for. Summed per line and not
    # per fragment, because a line that leaves a unit and comes back contributes
    # two fragments to the same unit and one share.
    covered = fragments.groupby(_LINE_ID_COL)[_SHARE_COL].sum().rename(_COVERED_COL)
    lines_with_cover = projected[[_LINE_ID_COL, _LINE_KM_COL, weekly, daily]].join(
        covered, on=_LINE_ID_COL
    )
    lines_with_cover[_COVERED_COL] = lines_with_cover[_COVERED_COL].fillna(0.0)
    uncovered = 1.0 - lines_with_cover[_COVERED_COL]

    reached = int(fragments[_LINE_ID_COL].nunique())
    outside = len(projected) - reached
    split = len(fragments) - reached

    log.record(
        f"apportion {layer.name} over the units",
        rows_in=len(lines),
        rows_out=len(fragments),
        changes=[
            (-outside, "lines falling outside every unit, contributing to no unit"),
            (split, "fragments gained where a line crosses a unit boundary and is split between units"),
        ],
        notes=[
            f"source={layer.source_layer}/{layer.source_file}, {layer.measures}",
            f"{float(fragments[predictors.FRAGMENT_LENGTH_COL].sum()):,.2f} km of "
            f"{float(projected[_LINE_KM_COL].sum()):,.2f} km fall inside the units "
            f"({100 * float(fragments[predictors.FRAGMENT_LENGTH_COL].sum()) / float(projected[_LINE_KM_COL].sum()):.2f}%)",
            "allocation rule: each line gives a unit the share of its trips that matches the "
            "share of its length inside that unit",
        ],
    )

    return Apportionment(
        layer=layer,
        per_unit=per_unit,
        lines_read=len(projected),
        lines_reaching_a_unit=reached,
        layer_weekly=float(projected[weekly].sum()),
        layer_daily=float(projected[daily].sum()),
        layer_km=float(projected[_LINE_KM_COL].sum()),
        outside_weekly=float((lines_with_cover[weekly] * uncovered).sum()),
        outside_daily=float((lines_with_cover[daily] * uncovered).sum()),
        outside_km=float((lines_with_cover[_LINE_KM_COL] * uncovered).sum()),
        largest_covered_share=float(lines_with_cover[_COVERED_COL].max()),
    )


def endpoint_totals(
    lines: gpd.GeoDataFrame,
    units: gpd.GeoDataFrame,
    layer: config.SurveyLineLayer,
    x_column: str,
    y_column: str,
    column_name: str,
    log: RunLog,
) -> pd.Series:
    """Trips per week counted whole in the unit containing one end of the line.

    One of the two allocations that owe nothing to the geometry between the
    endpoints, which is what makes them worth having: the chord is a straight line
    the survey never measured, but the origin and the destination are what the
    survey actually recorded. A trip whose endpoint falls outside every unit is
    counted nowhere, and the run says how many did.
    """
    endpoints = gpd.GeoDataFrame(
        lines[[layer.weekly_weight_column]].copy(),
        geometry=gpd.points_from_xy(lines[x_column], lines[y_column]),
        crs=config.SOURCE_CRS,
    ).to_crs(epsg=config.PROJECTED_CRS)

    joined = gpd.sjoin(
        endpoints,
        units[[config.AREA_CODE_COL, "geometry"]],
        how="inner",
        predicate=config.SPATIAL_JOIN_PREDICATE,
    )

    # Only possible where unit polygons overlap, and resolved the way every other
    # point join in the pipeline resolves it, so one trip cannot be counted twice.
    ambiguous = int(joined.index.duplicated().sum())
    if ambiguous:
        log.warn(
            "%s: %d %s(s) fall inside more than one unit; keeping the lowest unit code",
            layer.name,
            ambiguous,
            column_name,
        )
        joined = joined.sort_values(config.AREA_CODE_COL, kind="stable")
        joined = joined[~joined.index.duplicated(keep="first")]

    located = len(joined)
    log.info(
        "%s: %d of %d %s fall inside a unit (%.1f%%), carrying %s of %s trips per week",
        layer.name,
        located,
        len(endpoints),
        column_name,
        100 * located / len(endpoints) if len(endpoints) else 0.0,
        f"{joined[layer.weekly_weight_column].sum():,.0f}",
        f"{lines[layer.weekly_weight_column].sum():,.0f}",
    )
    return joined.groupby(config.AREA_CODE_COL)[layer.weekly_weight_column].sum().rename(column_name)


# ---------------------------------------------------------------------------
# Population
# ---------------------------------------------------------------------------


def population_by_year(
    units: gpd.GeoDataFrame,
    log: RunLog,
    scale: config.TerritorialScale | None = None,
    layers: tuple[config.SurveyLineLayer, ...] | None = None,
) -> dict[int, pd.Series]:
    """The population of every unit, for each year a declared layer divides by.

    Exposure is a snapshot and population is a series, so the two only meet at a
    year somebody has to name. Each layer names its own — the one date attached to
    the file it came from — and this returns exactly those years, so the module can
    never divide by a year no layer asked for. See D36.

    The panel itself is built by the population module and not read here. Two
    readers of one file would be two chances to sum it differently, and the
    checks that say the sum is right live with the module that does it.
    """
    layers = layers or config.EXPOSURE_LAYERS
    panel, _, _ = population.build(units, log, scale=scale)
    return {
        year: population.for_year(panel, year)
        for year in config.exposure_population_years(tuple(layers))
    }


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------


def measure_layer(
    units: gpd.GeoDataFrame,
    layer: config.SurveyLineLayer,
    log: RunLog,
) -> tuple[gpd.GeoDataFrame, Apportionment, pd.DataFrame]:
    """Everything one exposure layer contributes: its lines, its totals, its columns.

    Returned separately from the assembly so that adding a second layer adds a
    trip round this function and changes nothing else. The lines come back too
    because the verification checks the table against the layer rather than
    against the arithmetic that consumed it.
    """
    lines = read_layer(layer, log)
    allocation = apportion(lines, units, layer, log)
    at_origin = endpoint_totals(
        lines, units, layer,
        layer.origin_x_column, layer.origin_y_column,
        layer.column(config.TRIPS_WEEKLY_AT_ORIGIN_SUFFIX), log,
    )
    at_destination = endpoint_totals(
        lines, units, layer,
        layer.destination_x_column, layer.destination_y_column,
        layer.column(config.TRIPS_WEEKLY_AT_DESTINATION_SUFFIX), log,
    )
    contribution = allocation.per_unit.join([at_origin, at_destination], how="outer")
    return lines, allocation, contribution


def build(
    units: gpd.GeoDataFrame,
    log: RunLog,
    layers: tuple[config.SurveyLineLayer, ...] | None = None,
    scale: config.TerritorialScale | None = None,
) -> tuple[pd.DataFrame, dict[str, Apportionment], dict[str, gpd.GeoDataFrame]]:
    """One row per unit, and one set of columns per exposure layer.

    The table is wide over modes rather than long over them: a unit is a row, and
    a second layer adds columns instead of duplicating the thirty rows. That is
    what the mode in each column name buys, and it is the shape the panel joins
    against — the casualty matrix is already keyed on unit and year, and an
    exposure table with two rows per unit would need a filter before every join.

    Every unit gets a row whatever any layer did, which is D22's rule applied
    here: Torca is crossed by no desire line at all, and that is an observation of
    zero rather than an absence of one. It comes out as a zero with the status
    MEASURED, and only a unit with no usable area would come out null.
    """
    layers = layers or config.EXPOSURE_LAYERS
    scale = scale or config.active_scale()
    projected = predictors.prepare_units(units)

    table = projected[[config.AREA_CODE_COL, config.AREA_NAME_COL, config.AREA_UNIT_KM2_COL]].copy()

    allocations: dict[str, Apportionment] = {}
    lines_by_layer: dict[str, gpd.GeoDataFrame] = {}
    counted_columns: list[str] = []
    untouched: list[tuple[int, str]] = []

    for layer in layers:
        lines, allocation, contribution = measure_layer(projected, layer, log)
        allocations[layer.name] = allocation
        lines_by_layer[layer.name] = lines
        table = table.join(contribution, on=config.AREA_CODE_COL)

        weekly = layer.column(config.TRIPS_WEEKLY_SUFFIX)
        measured = [
            weekly,
            layer.column(config.TRIPS_DAILY_SUFFIX),
            layer.column(config.LINE_KM_INSIDE_SUFFIX),
            layer.column(config.TRIPS_WEEKLY_AT_ORIGIN_SUFFIX),
            layer.column(config.TRIPS_WEEKLY_AT_DESTINATION_SUFFIX),
        ]
        untouched.append((
            int(table[weekly].isna().sum()),
            f"units no {layer.mode.lower()} line reaches, materialised as a measured zero "
            "rather than left absent",
        ))
        table[measured] = table[measured].fillna(0.0).astype(float)
        touching = layer.column(config.LINES_TOUCHING_SUFFIX)
        table[touching] = table[touching].fillna(0).astype(int)
        counted_columns.extend(measured)

    residents_by_year = population_by_year(projected, log, scale=scale, layers=tuple(layers))
    for year, residents in residents_by_year.items():
        table[config.population_column(year)] = table[config.AREA_CODE_COL].map(residents)

    area = table[config.AREA_UNIT_KM2_COL]
    unusable_area = ~(area > 0)
    for layer in layers:
        weekly = layer.column(config.TRIPS_WEEKLY_SUFFIX)
        table[layer.column(config.TRIPS_WEEKLY_PER_KM2_SUFFIX)] = (
            table[weekly] / area.where(area > 0)
        )
        # Each layer divides by its own year, which is the year its column name
        # carries. Null rather than zero wherever the denominator is missing: a
        # rate with no denominator is not a rate of nought.
        residents = table[config.population_column(layer.population_reference_year)]
        table[layer.column(config.TRIPS_WEEKLY_PER_PERSON_SUFFIX)] = (
            table[weekly] / residents.where(residents > 0)
        )

    table[config.PREDICTOR_STATUS_COL] = np.where(
        unusable_area, config.NOT_MEASURED_STATUS, config.MEASURED_STATUS
    )
    # A unit with no usable area could not be measured, and must not carry a zero
    # that would read as an observation.
    table.loc[unusable_area, counted_columns] = np.nan

    table[config.SCALE_COL] = scale.label
    # No exposure layer states a year: the desire lines date only their own export
    # in ArcGIS. Null rather than guessed, and the column is here so a delivery
    # that does carry a year joins this table without a schema change.
    table[config.YEAR_COL] = pd.array([pd.NA] * len(table), dtype="Int64")

    table = (
        table[list(config.exposure_columns(tuple(layers)))]
        .sort_values(config.AREA_CODE_COL, kind="stable")
        .reset_index(drop=True)
    )

    log.record(
        "assemble the exposure table",
        rows_in=sum(len(allocation.per_unit) for allocation in allocations.values()),
        rows_out=len(table) * len(layers),
        changes=untouched,
        notes=[
            f"one row per unit at {scale.label}, year null on every row",
            "modes: " + ", ".join(layer.mode for layer in layers),
            f"{int(unusable_area.sum())} unit(s) with no usable area, marked {config.NOT_MEASURED_STATUS}",
        ],
    )
    return table, allocations, lines_by_layer


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def dictionary_table(layers: tuple[config.SurveyLineLayer, ...] | None = None) -> pd.DataFrame:
    """What each column of the exposure table holds, in its own units.

    Exported for the same reason the predictor dictionary is: the tables are
    joined to others outside this repository, and a column called
    BICYCLE_TRIPS_PER_WEEK_AT_ORIGIN has to be readable without the code that made
    it. Every entry names the period it counts and the mode it counts it for,
    because those are the two distinctions the naming exists to protect.

    Built from the same declarations the measurement runs on, so the dictionary
    cannot describe a column the table does not have or miss one it does.
    """
    layers = layers or config.EXPOSURE_LAYERS
    rows = [
        {
            "COLUMN": layer.column(quantity.suffix),
            "MODE": layer.mode,
            "UNIT": quantity.unit,
            "MEANS": quantity.describe(layer),
            "IS_ALTERNATIVE_ALLOCATION": quantity.is_alternative,
            "SOURCE_LAYER": layer.source_layer,
            "SOURCE_FILE": layer.source_file,
            "TIME_COVERAGE": layer.time_coverage,
        }
        for layer in layers
        for quantity in config.EXPOSURE_QUANTITIES
    ]

    # The columns that belong to the unit rather than to a mode. Population names
    # the file it comes from: a dictionary row pointing it at the desire lines
    # would state, in the one document meant to make provenance checkable, that a
    # mobility survey counts residents.
    for year in config.exposure_population_years(tuple(layers)):
        rows.append({
            "COLUMN": config.population_column(year),
            "MODE": "",
            "UNIT": "inhabitants",
            "MEANS": (
                f"resident population of the unit in {year}, read from "
                f"{config.POPULATION_SOURCE.path.name} and not from any exposure layer. It is "
                f"here because a layer dated {year} divides by it; the population of every year "
                "is in the population table"
            ),
            "IS_ALTERNATIVE_ALLOCATION": False,
            "SOURCE_LAYER": config.POPULATION_SOURCE.path.parent.name,
            "SOURCE_FILE": config.POPULATION_SOURCE.path.name,
            "TIME_COVERAGE": str(year),
        })
    rows.append({
        "COLUMN": config.PREDICTOR_STATUS_COL,
        "MODE": "",
        "UNIT": "",
        "MEANS": (
            f"{config.MEASURED_STATUS} where the unit was measured, whatever came out, and "
            f"{config.NOT_MEASURED_STATUS} where it could not be; a unit no line reaches is "
            f"{config.MEASURED_STATUS} with a zero"
        ),
        "IS_ALTERNATIVE_ALLOCATION": False,
        "SOURCE_LAYER": "",
        "SOURCE_FILE": "",
        "TIME_COVERAGE": "",
    })
    return pd.DataFrame(rows)


def export(
    table: pd.DataFrame,
    log: RunLog,
    layers: tuple[config.SurveyLineLayer, ...] | None = None,
) -> dict[str, Path]:
    """Write the delivered layer's table and the dictionary that reads it.

    Filed as a reference table and no longer as the analysis one. It was the
    study's exposure while it was the only measurement there was; now that the
    survey produces one, this is the comparison it is measured against and the
    provenance of the figures already quoted from it. Naming it `analysis` beside
    a table that is actually analysed would invite the wrong one into a model.
    """
    layers = layers or config.EXPOSURE_LAYERS
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    table_path = data_dir / f"{config.REFERENCE_PREFIX}__delivered_desire_lines_by_unit.csv"
    table.to_csv(table_path, index=False, encoding="utf-8")
    table.to_parquet(table_path.with_suffix(".parquet"))
    paths["table"] = table_path

    dictionary_path = (
        data_dir / f"{config.REFERENCE_PREFIX}__delivered_desire_lines_dictionary.csv"
    )
    dictionary_table(layers).to_csv(dictionary_path, index=False, encoding="utf-8")
    paths["dictionary"] = dictionary_path

    log.info("exported 2 reference tables for the delivered layer to %s/", config.DATA_SUBDIR)
    return paths


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------


def render_figures(
    table: pd.DataFrame,
    units: gpd.GeoDataFrame,
    log: RunLog,
    layers: tuple[config.SurveyLineLayer, ...] | None = None,
) -> tuple[list[Path], list[int]]:
    """Draw one choropleth per exposure layer, with and without a scale bar.

    Two files per layer for the same reason the reference map produces two: a map
    at the width of a page can carry a scale bar and one shrunk into a slide
    cannot, and which one a document uses is then a matter of which file it
    includes rather than of editing a setting and running again.
    """
    layers = layers or config.EXPOSURE_LAYERS
    directory = log.run_dir / config.FIGURES_SUBDIR / config.EXPOSURE_FIGURES_SUBDIR

    out_paths: list[Path] = []
    overflowing: list[int] = []
    for layer in layers:
        # Under a `choropleth/` folder like every other figure in the tree, even
        # though this layer produces only two files. The rule is what makes
        # `**/choropleth/*.pdf` mean "every choropleth"; an exception for the one
        # odd artefact would cost more than the folder does.
        into = directory / layer.figures_subdir / config.EXPOSURE_CHOROPLETH_SUBDIR
        stem = f"{config.EXPOSURE_FIGURES_SUBDIR}__{layer.name.lower()}"
        variants = maps.figure_variants(into, stem)

        values = table.set_index(config.AREA_CODE_COL)[layer.column(config.TRIPS_WEEKLY_SUFFIX)]
        caption = f"{layer.label_es} por semana"

        for position, (path, scalebar) in enumerate(variants):
            spilling = maps.render_choropleth(
                units, values, path, caption, scalebar=scalebar
            )
            if position == 0:
                overflowing.extend(spilling)
        out_paths.extend(path for path, _ in variants)

        log.info(
            "choropleth %s: %d units, range %s to %s %s, %d observed zero(s), %d not measured",
            layer.name,
            len(values),
            f"{values.min():,.0f}",
            f"{values.max():,.0f}",
            caption.lower(),
            int((values == 0).sum()),
            int(values.isna().sum()),
        )
        if spilling:
            names = ", ".join(
                f"{units.iloc[position][config.AREA_CODE_COL]} "
                f"({units.iloc[position][config.AREA_NAME_COL]})"
                for position in spilling
            )
            log.warn("%d label(s) do not fit inside their unit: %s", len(spilling), names)

    for path in out_paths:
        log.info("wrote %s", path)
    return out_paths, overflowing


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(
    table: pd.DataFrame,
    allocations: dict[str, Apportionment],
    lines_by_layer: dict[str, gpd.GeoDataFrame],
    units: gpd.GeoDataFrame,
    log: RunLog,
    layers: tuple[config.SurveyLineLayer, ...] | None = None,
    paths: dict[str, Path] | None = None,
) -> bool:
    """Check the table against the layers it was built from, and against arithmetic.

    The check that matters is the balance: what was allocated to the units plus
    what fell outside them has to equal what the file holds. It is the check the
    legacy pipeline could not have made, because the quantity it exported was not
    a quantity the file held. Every layer is checked separately and in full, so
    adding one adds its own rows to the table of checks rather than diluting an
    aggregate that could pass while one layer failed.
    """
    layers = layers or config.EXPOSURE_LAYERS
    checks: list[tuple[str, bool, str]] = []
    rtol = config.EXPOSURE_BALANCE_RTOL

    # First the checks about the table as a whole, which belong to no single layer.
    expected_units = set(units[config.AREA_CODE_COL])
    checks.append((
        "every unit of the layer has exactly one row",
        set(table[config.AREA_CODE_COL]) == expected_units and len(table) == len(expected_units),
        f"{len(table)} rows for {len(expected_units)} units",
    ))
    expected_columns = list(config.exposure_columns(tuple(layers)))
    checks.append((
        "the table carries exactly the declared columns, in the declared order",
        list(table.columns) == expected_columns,
        f"{len(table.columns)} columns against {len(expected_columns)} declared",
    ))

    # Every value column carries its mode, which is what stops a second exposure
    # layer from colliding with this one. Checked rather than trusted, because the
    # collision it prevents would be silent: two layers writing the same column
    # name would leave one of them in the file and no sign of the other.
    missing_columns = [
        layer.column(quantity.suffix)
        for layer in layers
        for quantity in config.EXPOSURE_QUANTITIES
        if layer.column(quantity.suffix) not in table.columns
    ]
    checks.append((
        "every declared quantity is present under its mode-prefixed name",
        not missing_columns,
        f"{len(missing_columns)} missing"
        + (f": {', '.join(missing_columns)}" if missing_columns else ""),
    ))

    measured = table[table[config.PREDICTOR_STATUS_COL] == config.MEASURED_STATUS]

    for layer in layers:
        allocation = allocations[layer.name]
        lines = lines_by_layer[layer.name]
        tag = layer.mode.lower()
        weekly = layer.column(config.TRIPS_WEEKLY_SUFFIX)
        daily = layer.column(config.TRIPS_DAILY_SUFFIX)

        for name, allocated, outside, total in (
            ("trips per week", allocation.allocated_weekly,
             allocation.outside_weekly, allocation.layer_weekly),
            ("trips per day", allocation.allocated_daily,
             allocation.outside_daily, allocation.layer_daily),
            ("kilometres", allocation.allocated_km,
             allocation.outside_km, allocation.layer_km),
        ):
            checks.append((
                f"{tag}: {name} allocated plus {name} outside equals the layer",
                bool(np.isclose(allocated + outside, total, rtol=rtol)),
                f"{allocated:,.4f} + {outside:,.4f} = {allocated + outside:,.4f} "
                f"against {total:,.4f}",
            ))

        checks.append((
            f"{tag}: no line is allocated more than once over",
            allocation.largest_covered_share <= 1 + config.EXPOSURE_MAX_OVER_COVERAGE,
            f"largest share of a line covered by the units: "
            f"{allocation.largest_covered_share:.9f}, "
            f"tolerance {1 + config.EXPOSURE_MAX_OVER_COVERAGE:.9f}",
        ))

        negatives = int((measured[weekly] < 0).sum())
        checks.append((f"{tag}: no negative trip count", negatives == 0, f"{negatives} negative"))

        # The daily and weekly columns are the same apportionment of two different
        # expansions, so their ratio is the average number of days a week a trip is
        # made, and it has to land between one and seven wherever both are non-zero.
        both = measured[measured[daily] > 0]
        ratio = both[weekly] / both[daily]
        checks.append((
            f"{tag}: weekly over daily lies between 1 and 7 in every unit",
            bool(((ratio >= 1) & (ratio <= 7)).all()) if len(ratio) else True,
            f"observed {ratio.min():.3f} to {ratio.max():.3f} days per week"
            if len(ratio) else "no unit with trips",
        ))

        # The endpoints the origin and destination rules use are attributes of the
        # record, not the geometry. If the two ever disagreed, those two columns
        # would be measuring a different set of lines from the one the variable
        # measures.
        projected = lines.to_crs(epsg=config.PROJECTED_CRS)
        declared_origin = gpd.GeoSeries(
            gpd.points_from_xy(lines[layer.origin_x_column], lines[layer.origin_y_column]),
            crs=config.SOURCE_CRS,
        ).to_crs(epsg=config.PROJECTED_CRS)
        declared_end = gpd.GeoSeries(
            gpd.points_from_xy(lines[layer.destination_x_column], lines[layer.destination_y_column]),
            crs=config.SOURCE_CRS,
        ).to_crs(epsg=config.PROJECTED_CRS)
        first = gpd.GeoSeries(
            [Point(geometry.coords[0]) for geometry in projected.geometry],
            crs=config.PROJECTED_CRS,
        )
        last = gpd.GeoSeries(
            [Point(geometry.coords[-1]) for geometry in projected.geometry],
            crs=config.PROJECTED_CRS,
        )
        gap = max(
            float(first.distance(declared_origin).max()),
            float(last.distance(declared_end).max()),
        )
        checks.append((
            f"{tag}: the declared endpoints are the ends of the geometry",
            gap < 1.0,
            f"largest gap {gap:.6f} m",
        ))

        checks.append((
            f"{tag}: the per-km2 column is the variable over the area of its unit",
            bool(np.allclose(
                (measured[weekly] / measured[config.AREA_UNIT_KM2_COL]).to_numpy(),
                measured[layer.column(config.TRIPS_WEEKLY_PER_KM2_SUFFIX)].to_numpy(),
                rtol=1e-12,
            )),
            "compared to 1e-12",
        ))

        # The denominator is a year of a series and the numerator has no year at
        # all, so the one thing that can be checked is that the division is the
        # division the column name states. It is checked against the population
        # column of the same year in the same table, which is what a reader would
        # recompute it from.
        residents_column = config.population_column(layer.population_reference_year)
        residents = measured[residents_column]
        checks.append((
            f"{tag}: the per-inhabitant column is the variable over {residents_column}",
            bool(np.allclose(
                (measured[weekly] / residents.where(residents > 0)).to_numpy(),
                measured[layer.column(config.TRIPS_WEEKLY_PER_PERSON_SUFFIX)].to_numpy(),
                rtol=1e-12,
                equal_nan=True,
            )),
            f"compared to 1e-12 against {residents_column}",
        ))

        # A zero is a measurement here and a null is not. Confusing them is what
        # this pipeline exists to make impossible, so it is checked rather than
        # assumed.
        zero_rows = table[table[weekly] == 0]
        checks.append((
            f"{tag}: a unit no line reaches carries a zero and the status MEASURED",
            bool((zero_rows[config.PREDICTOR_STATUS_COL] == config.MEASURED_STATUS).all()),
            f"{len(zero_rows)} unit(s) at zero: "
            + (", ".join(zero_rows[config.AREA_CODE_COL]) if len(zero_rows) else "none"),
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
    for name, ok, detail in checks:
        rendered.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("exposure verification:", "\n".join(rendered))

    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("exposure verification FAILED")
    return passed


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def report(
    table: pd.DataFrame,
    allocations: dict[str, Apportionment],
    log: RunLog,
    layers: tuple[config.SurveyLineLayer, ...] | None = None,
) -> None:
    """What each layer says, in numbers, for whoever reads the log instead."""
    layers = layers or config.EXPOSURE_LAYERS

    for layer in layers:
        allocation = allocations[layer.name]
        weekly = layer.column(config.TRIPS_WEEKLY_SUFFIX)

        log.info(
            "%s: %d lines, %d of them reaching a unit; %s trips per week and %s per day "
            "in the layer",
            layer.name,
            allocation.lines_read,
            allocation.lines_reaching_a_unit,
            f"{allocation.layer_weekly:,.0f}",
            f"{allocation.layer_daily:,.0f}",
        )
        log.info(
            "of that, %s trips per week (%.1f%%) fall inside the %d units and %s fall outside",
            f"{allocation.allocated_weekly:,.0f}",
            100 * allocation.allocated_weekly / allocation.layer_weekly,
            len(table),
            f"{allocation.outside_weekly:,.0f}",
        )
        log.info(
            "%s km of the %s km in the layer lie inside the units (%.1f%%)",
            f"{allocation.allocated_km:,.2f}",
            f"{allocation.layer_km:,.2f}",
            100 * allocation.allocated_km / allocation.layer_km,
        )

        top = table.sort_values(weekly, ascending=False).head(3)
        log.info(
            "most exposed to %s: %s",
            layer.mode.lower(),
            "; ".join(
                f"{row[config.AREA_CODE_COL]} {row[config.AREA_NAME_COL]} {row[weekly]:,.0f}"
                for _, row in top.iterrows()
            ),
        )
        empty = table[table[weekly] == 0]
        if len(empty):
            log.info(
                "no %s desire line reaches %s, which is an observed zero and not a missing value",
                layer.mode.lower(),
                ", ".join(
                    f"{row[config.AREA_CODE_COL]} ({row[config.AREA_NAME_COL]})"
                    for _, row in empty.iterrows()
                ),
            )

        # The alternatives are exported to be compared, so the comparison is made
        # here rather than left for someone to do by hand. Rank correlation rather
        # than Pearson: what matters is whether the rules order the units the same
        # way, not whether they agree on a magnitude they do not share.
        alternatives = [weekly] + [
            layer.column(quantity.suffix)
            for quantity in config.EXPOSURE_QUANTITIES
            if quantity.is_alternative
        ]
        ranks = table[alternatives].corr(method="spearman")
        log.table(
            f"{layer.mode.lower()}: rank correlation between the allocation rules "
            "(Spearman), the variable first:",
            ranks.to_string(float_format=lambda value: f"{value:.3f}"),
        )

    for layer in layers:
        year = layer.population_reference_year
        rate = table[layer.column(config.TRIPS_WEEKLY_PER_PERSON_SUFFIX)]
        if rate.notna().any():
            log.info(
                "%s per inhabitant of %d: %.2f to %.2f trips per week, median %.2f",
                layer.mode.lower(),
                year,
                rate.min(),
                rate.max(),
                rate.median(),
            )
        # Said on every run, because a column that looks like a rate will be used
        # as one. This one is a snapshot of unknown date over the residents of a
        # single year, so it describes and it does not model: put it in a panel and
        # it would move with its denominator alone. See D36.
        log.warn(
            "%s is descriptive only. The trips carry no year, so dividing them by a population "
            "that does gives a ratio for %d and never a series; the models take their "
            "denominator from the population table, per unit and per year. See D36",
            layer.column(config.TRIPS_WEEKLY_PER_PERSON_SUFFIX),
            year,
        )


# ===========================================================================
# Exposure built from the survey
# ===========================================================================
# Everything above measures the delivered desire lines. Everything below builds
# the lines from the survey itself and measures those, which is the variable the
# study now uses; the delivered layer stays because it is what several finished
# figures were measured on, and it is exported as a comparison rather than as the
# variable. See D38.
#
# The two share the one operation they must not do differently — cutting a line
# at the unit boundaries and measuring the pieces, which lives in `predictors`
# and is called by both.


# Working columns for the survey path. Private to this module, like the ones the
# delivered layer uses, and named apart from anything exported.
_PAIR_ID_COL = "_PAIR"
_PAIR_KM_COL = "_PAIR_TOTAL_KM"
_ZONE_AREA_COL = "_ZONE_TOTAL_AREA"
_ZONE_SHARE_COL = "_ZONE_AREA_SHARE"
_LINE_SHARE_COL = "_LINE_LENGTH_SHARE"
_COVERED_SHARE_COL = "_SHARE_INSIDE_THE_STUDY"
_ALLOCATED_COL = "_ALLOCATED"
_FRAGMENT_AREA_COL = "_FRAGMENT_AREA"


@dataclass(frozen=True)
class SurveyApportionment:
    """One survey's trips spread over the units, with everything needed to check it.

    The three totals are kept apart rather than added up, because the balance the
    run checks is that the two routes into a unit plus what left the study area
    equal what the file holds, and a single total would hide which of the three
    moved if it ever stopped closing.
    """

    trips: surveys.SurveyTrips
    # One row per unit, actor type and day type, carrying the measured quantities.
    per_unit: pd.DataFrame
    # Trips per day that fell outside every unit, per actor type and day type.
    outside: pd.Series
    # The lines themselves, one per distinct zone pair, and the trips each carries
    # per actor type and day type. Kept rather than discarded because this
    # pipeline builds its own desire lines, so the figure that draws them is the
    # only way anyone can see what was built. Nothing else in the study draws its
    # own input, and nothing else has to.
    lines: gpd.GeoDataFrame
    line_trips: pd.DataFrame
    zones_read: int
    zones_reaching_a_unit: int
    pairs_built: int
    pairs_reaching_a_unit: int
    largest_covered_share: float

    @property
    def survey(self) -> config.MobilitySurvey:
        return self.trips.survey


# ---------------------------------------------------------------------------
# How a zone reaches a unit
# ---------------------------------------------------------------------------


def zone_area_shares(
    zones: gpd.GeoDataFrame,
    units: gpd.GeoDataFrame,
    survey: config.MobilitySurvey,
    log: RunLog,
) -> pd.DataFrame:
    """The share of each survey zone's area that falls inside each unit.

    This is the rule for everything that has no line to be spread along: a trip
    that begins and ends in the same zone, and the two alternative allocations
    that count a trip at one of its endpoints. One rule rather than two, so that
    an intra-zonal trip and an inter-zonal one are governed by the same idea of
    what it means for a zone to be in a unit.

    Slivers are dropped and not renormalised. The survey's zoning and the study's
    cartography draw the same boundaries from different sources, so their overlay
    produces fragments of a few square metres along every shared edge; left in,
    they hand a trip to units the zone does not touch. What is dropped is counted
    as falling outside the study area, which is what it is — the alternative
    would fold cartographic noise into the units and leave the balance unable to
    distinguish it from a zone that genuinely lies half in Soacha.
    """
    zones = zones.copy()
    zones[_ZONE_AREA_COL] = zones.geometry.area

    degenerate = zones[_ZONE_AREA_COL] <= 0
    if degenerate.any():
        raise ValueError(
            f"{survey.label}: {int(degenerate.sum())} zone(s) have no area, so the share of "
            "them falling inside a unit is undefined"
        )

    fragments = gpd.overlay(
        zones[[surveys.ZONE_CODE_COL, _ZONE_AREA_COL, "geometry"]],
        units[[config.AREA_CODE_COL, "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    fragments[_FRAGMENT_AREA_COL] = fragments.geometry.area
    fragments[_ZONE_SHARE_COL] = fragments[_FRAGMENT_AREA_COL] / fragments[_ZONE_AREA_COL]

    if config.ZONE_UNIT_RENORMALISE:
        raise NotImplementedError(
            "ZONE_UNIT_RENORMALISE is declared true, but renormalising the kept shares is "
            "deliberately not implemented: it would fold the boundary slivers back into the "
            "units and leave the balance unable to tell them from a zone lying outside the "
            "city. Changing the flag is a decision that needs the reasoning in D38 revisited"
        )

    # Summed before the threshold is applied, because a zone that leaves a unit
    # and comes back gives that unit two fragments and one share, and thresholding
    # the pieces would drop a real share that arrived in two parts.
    shares = fragments.groupby(
        [surveys.ZONE_CODE_COL, config.AREA_CODE_COL], as_index=False
    ).agg(
        **{
            _ZONE_SHARE_COL: (_ZONE_SHARE_COL, "sum"),
            _FRAGMENT_AREA_COL: (_FRAGMENT_AREA_COL, "sum"),
        }
    )
    slivers = shares[_ZONE_SHARE_COL] <= config.ZONE_UNIT_MIN_AREA_SHARE
    discarded_area = float(shares.loc[slivers, _FRAGMENT_AREA_COL].sum())
    shares = shares.loc[~slivers, [surveys.ZONE_CODE_COL, config.AREA_CODE_COL, _ZONE_SHARE_COL]]

    reached = shares[surveys.ZONE_CODE_COL].nunique()
    split = int((shares.groupby(surveys.ZONE_CODE_COL)[config.AREA_CODE_COL].nunique() > 1).sum())
    log.info(
        "%s: %d of %d zone(s) reach a unit, %d of them divided between more than one; "
        "%d sliver fragment(s) below %g of their zone dropped, %.2f m2 in all",
        survey.label,
        reached,
        len(zones),
        split,
        int(slivers.sum()),
        config.ZONE_UNIT_MIN_AREA_SHARE,
        discarded_area,
    )
    return shares


# ---------------------------------------------------------------------------
# The desire lines, built rather than delivered
# ---------------------------------------------------------------------------


def build_desire_lines(
    pairs: pd.DataFrame,
    zones: gpd.GeoDataFrame,
    survey: config.MobilitySurvey,
    log: RunLog,
) -> gpd.GeoDataFrame:
    """One straight line per distinct origin-destination pair, between zone centroids.

    Built once for every pair the survey uses and reused by every actor type and
    day type that uses it, because the share of a line falling in a unit is a
    property of the pair of zones and of nothing else. Building one line per
    surveyed record would draw the same line dozens of times, split it dozens of
    times and arrive at the same answer.

    The line is a chord and the limitation is the same one D35 recorded for the
    delivered layer: nobody rode it. What the apportionment does is spread a trip
    along the corridor between its endpoints, and that is not a measurement of
    distance travelled in the unit. It is why the two endpoint allocations are
    measured beside the variable on every run.
    """
    centroids = zones.set_index(surveys.ZONE_CODE_COL).geometry.centroid

    distinct = (
        pairs[[surveys.ZONE_ORIGIN_COL, surveys.ZONE_DESTINATION_COL]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    distinct[_PAIR_ID_COL] = np.arange(len(distinct))

    origins = centroids.loc[distinct[surveys.ZONE_ORIGIN_COL]].to_numpy()
    destinations = centroids.loc[distinct[surveys.ZONE_DESTINATION_COL]].to_numpy()
    lines = gpd.GeoDataFrame(
        distinct,
        geometry=[
            LineString([(start.x, start.y), (end.x, end.y)])
            for start, end in zip(origins, destinations)
        ],
        crs=zones.crs,
    )
    lines[_PAIR_KM_COL] = lines.geometry.length / 1000.0

    # Two distinct zones whose centroids coincide would give a line of no length
    # and a division by zero. None occurs; the guard is here because the failure
    # would otherwise be a null in one unit rather than a message.
    degenerate = lines[_PAIR_KM_COL] * 1000.0 <= config.EXPOSURE_MIN_LINE_LENGTH_M
    if degenerate.any():
        raise ValueError(
            f"{survey.label}: {int(degenerate.sum())} origin-destination pair(s) of distinct "
            "zones have centroids in the same place, so the line between them has no length "
            "and no shares to compute"
        )

    log.info(
        "%s: built %d desire line(s) between zone centroids, %s km in all, median %.2f km",
        survey.label,
        len(lines),
        f"{float(lines[_PAIR_KM_COL].sum()):,.1f}",
        float(lines[_PAIR_KM_COL].median()),
    )
    return lines


def line_length_shares(
    lines: gpd.GeoDataFrame,
    units: gpd.GeoDataFrame,
    log: RunLog,
) -> pd.DataFrame:
    """The share of each desire line's length falling inside each unit.

    Cut by the same function the cycleway kilometres and the delivered layer are
    cut by, which is the point of that function living in `predictors`: the
    kilometres of a line inside a unit cannot end up measured two slightly
    different ways depending on which caller asked.
    """
    fragments = predictors.split_lines_by_unit(lines, units, _PAIR_ID_COL)
    fragments = fragments.merge(
        lines[[_PAIR_ID_COL, _PAIR_KM_COL]], on=_PAIR_ID_COL, how="left"
    )
    fragments[_LINE_SHARE_COL] = (
        fragments[predictors.FRAGMENT_LENGTH_COL] / fragments[_PAIR_KM_COL]
    )
    # Summed per pair and unit, not per fragment: a line that leaves a unit and
    # comes back gives that unit two pieces and one share.
    shares = fragments.groupby(
        [_PAIR_ID_COL, config.AREA_CODE_COL], as_index=False
    ).agg(
        **{
            _LINE_SHARE_COL: (_LINE_SHARE_COL, "sum"),
            predictors.FRAGMENT_LENGTH_COL: (predictors.FRAGMENT_LENGTH_COL, "sum"),
        }
    )
    log.info(
        "%d of %d desire line(s) reach at least one unit, in %d (line, unit) piece(s)",
        shares[_PAIR_ID_COL].nunique(),
        len(lines),
        len(shares),
    )
    return shares


# ---------------------------------------------------------------------------
# Apportionment
# ---------------------------------------------------------------------------


def _spread(
    pairs: pd.DataFrame,
    shares: pd.DataFrame,
    on: list[str],
    share_column: str,
    output_column: str,
) -> tuple[pd.DataFrame, pd.Series]:
    """Multiply a table of trips by a table of shares, and measure what is left over.

    Returns the allocated rows and, per actor type and day type, the trips whose
    shares did not add to one — the part of the study area's edge that is not the
    study area. That remainder is measured rather than absorbed, which is what
    lets the balance downstream be an equality instead of an inequality.
    """
    allocated = pairs.merge(shares, on=on, how="inner")
    allocated[output_column] = allocated[surveys.TRIPS_COL] * allocated[share_column]

    covered = shares.groupby(on, as_index=False)[share_column].sum()
    covered = covered.rename(columns={share_column: _COVERED_SHARE_COL})
    with_cover = pairs.merge(covered, on=on, how="left")
    with_cover[_COVERED_SHARE_COL] = with_cover[_COVERED_SHARE_COL].fillna(0.0)
    outside = (
        with_cover[surveys.TRIPS_COL] * (1.0 - with_cover[_COVERED_SHARE_COL])
    ).groupby(
        [with_cover[config.ACTOR_TYPE_COL], with_cover[config.DAY_TYPE_COL]]
    ).sum()
    return allocated, outside


def apportion_survey(
    trips: surveys.SurveyTrips,
    zones: gpd.GeoDataFrame,
    units: gpd.GeoDataFrame,
    log: RunLog,
) -> SurveyApportionment:
    """Spread one survey's trips over the units, by the two routes a trip can take.

    A trip between two zones is spread along the line between their centroids, by
    the share of that line's length inside each unit. A trip that begins and ends
    in the same zone has no line at all — one centroid, no length — and is spread
    over the units covering that zone by area share instead.

    **The intra-zonal trips are not dropped, and that is the decision this
    function exists to implement.** They are 18.1% of the travel the 2023 survey
    measures in the four modes and 39% of the short walking, so discarding them
    would not lose precision evenly: it would remove a fifth to two fifths of
    pedestrian exposure, and it would remove more of it in a unit built of large
    zones than in one built of small ones. Two rules rather than one because a
    zero-length line cannot be apportioned, not because the two kinds of trip are
    different kinds of travel.
    """
    survey = trips.survey
    pairs = trips.pairs
    intra_zonal = pairs[surveys.ZONE_ORIGIN_COL] == pairs[surveys.ZONE_DESTINATION_COL]

    zone_shares = zone_area_shares(zones, units, survey, log)
    lines = build_desire_lines(pairs[~intra_zonal], zones, survey, log)
    length_shares = line_length_shares(lines, units, log)

    # -- inter-zonal: along the line ---------------------------------------
    between = pairs[~intra_zonal].merge(
        lines[[surveys.ZONE_ORIGIN_COL, surveys.ZONE_DESTINATION_COL, _PAIR_ID_COL]],
        on=[surveys.ZONE_ORIGIN_COL, surveys.ZONE_DESTINATION_COL],
        how="left",
    )
    along_line, outside_between = _spread(
        between, length_shares, [_PAIR_ID_COL], _LINE_SHARE_COL, _ALLOCATED_COL
    )

    # -- intra-zonal: over the area of the one zone ------------------------
    within = pairs[intra_zonal].copy()
    within_shares = zone_shares.rename(columns={surveys.ZONE_CODE_COL: surveys.ZONE_ORIGIN_COL})
    in_zone, outside_within = _spread(
        within, within_shares, [surveys.ZONE_ORIGIN_COL], _ZONE_SHARE_COL, _ALLOCATED_COL
    )

    # -- the two endpoint allocations --------------------------------------
    # Divided between units by the same area rule as an intra-zonal trip, so that
    # "a zone is in a unit" means one thing in this module. What makes them
    # alternatives is which geometry they use — the endpoint zone rather than the
    # corridor — and not a second idea of how a zone is divided.
    at_origin, _ = _spread(
        pairs,
        zone_shares.rename(columns={surveys.ZONE_CODE_COL: surveys.ZONE_ORIGIN_COL}),
        [surveys.ZONE_ORIGIN_COL],
        _ZONE_SHARE_COL,
        config.TRIPS_AT_ORIGIN_COL,
    )
    at_destination, _ = _spread(
        pairs,
        zone_shares.rename(columns={surveys.ZONE_CODE_COL: surveys.ZONE_DESTINATION_COL}),
        [surveys.ZONE_DESTINATION_COL],
        _ZONE_SHARE_COL,
        config.TRIPS_AT_DESTINATION_COL,
    )

    key = [config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]
    contributions = [
        along_line.groupby(key, as_index=False).agg(
            **{
                config.TRIPS_PER_AVERAGE_DAY_COL: (_ALLOCATED_COL, "sum"),
                config.DESIRE_LINE_KM_COL: (predictors.FRAGMENT_LENGTH_COL, "sum"),
                config.OD_PAIRS_TOUCHING_COL: (_PAIR_ID_COL, "nunique"),
            }
        ),
        in_zone.groupby(key, as_index=False).agg(
            **{config.INTRAZONAL_TRIPS_COL: (_ALLOCATED_COL, "sum")}
        ),
        at_origin.groupby(key, as_index=False).agg(
            **{config.TRIPS_AT_ORIGIN_COL: (config.TRIPS_AT_ORIGIN_COL, "sum")}
        ),
        at_destination.groupby(key, as_index=False).agg(
            **{config.TRIPS_AT_DESTINATION_COL: (config.TRIPS_AT_DESTINATION_COL, "sum")}
        ),
    ]
    per_unit = contributions[0]
    for contribution in contributions[1:]:
        per_unit = per_unit.merge(contribution, on=key, how="outer")
    for column in (
        config.TRIPS_PER_AVERAGE_DAY_COL,
        config.DESIRE_LINE_KM_COL,
        config.INTRAZONAL_TRIPS_COL,
        config.TRIPS_AT_ORIGIN_COL,
        config.TRIPS_AT_DESTINATION_COL,
    ):
        per_unit[column] = per_unit[column].fillna(0.0).astype(float)
    per_unit[config.OD_PAIRS_TOUCHING_COL] = (
        per_unit[config.OD_PAIRS_TOUCHING_COL].fillna(0).astype(int)
    )
    # The variable is the whole of what reached the unit, by whichever route. The
    # intra-zonal part stays in its own column as a part of it and never as an
    # addition to it, so a reader can see how much of a unit's walking never left
    # its zone.
    per_unit[config.TRIPS_PER_AVERAGE_DAY_COL] = (
        per_unit[config.TRIPS_PER_AVERAGE_DAY_COL] + per_unit[config.INTRAZONAL_TRIPS_COL]
    )

    outside = outside_between.add(outside_within, fill_value=0.0)
    covered_per_pair = length_shares.groupby(_PAIR_ID_COL)[_LINE_SHARE_COL].sum()
    covered_per_zone = zone_shares.groupby(surveys.ZONE_CODE_COL)[_ZONE_SHARE_COL].sum()
    largest = float(max(covered_per_pair.max(), covered_per_zone.max()))

    log.record(
        f"apportion the {survey.year} survey over the units",
        rows_in=len(pairs),
        rows_out=len(per_unit),
        changes=[
            (len(per_unit) - len(pairs), "zone pairs replaced by one row per unit, actor type and day type"),
        ],
        notes=[
            f"{int((~intra_zonal).sum()):,} inter-zonal pair-rows spread along a line and "
            f"{int(intra_zonal.sum()):,} intra-zonal ones spread over the area of one zone",
            f"{float(pairs.loc[intra_zonal, surveys.TRIPS_COL].sum()):,.1f} trips per day are "
            f"intra-zonal, {100 * float(pairs.loc[intra_zonal, surveys.TRIPS_COL].sum()) / float(pairs[surveys.TRIPS_COL].sum()):.1f}% "
            "of the four measured modes, and are apportioned rather than discarded",
            f"{float(outside.sum()):,.1f} trips per day fall outside the {len(units)} units, "
            "which is the surveyed region beyond the study area and not a loss",
        ],
    )

    return SurveyApportionment(
        trips=trips,
        per_unit=per_unit,
        outside=outside,
        lines=lines[[_PAIR_ID_COL, _PAIR_KM_COL, "geometry"]],
        line_trips=between[
            [config.ACTOR_TYPE_COL, config.DAY_TYPE_COL, _PAIR_ID_COL, surveys.TRIPS_COL]
        ],
        zones_read=len(zones),
        zones_reaching_a_unit=int(zone_shares[surveys.ZONE_CODE_COL].nunique()),
        pairs_built=len(lines),
        pairs_reaching_a_unit=int(length_shares[_PAIR_ID_COL].nunique()),
        largest_covered_share=largest,
    )


# ---------------------------------------------------------------------------
# The long table
# ---------------------------------------------------------------------------


def build_from_surveys(
    units: gpd.GeoDataFrame,
    log: RunLog,
    survey_list: tuple[config.MobilitySurvey, ...] | None = None,
    scale: config.TerritorialScale | None = None,
) -> tuple[pd.DataFrame, dict[int, SurveyApportionment]]:
    """One row per unit, year, actor type and day type, for every declared survey.

    The grid is complete by construction: every unit gets a row for every actor
    type the survey measures and every day type it distinguishes, whether or not
    a trip reached it. A unit no line of a mode reaches is a zero and an
    observation, exactly as Torca is for the delivered layer; a unit with no
    usable area is null and not measured. What is never materialised is a
    combination the survey does not have — a year with no usable Saturday must be
    absent, not zero, and that is D10 applied to a dimension that is ragged by
    construction.
    """
    survey_list = survey_list or config.MOBILITY_SURVEYS
    scale = scale or config.active_scale()
    projected = predictors.prepare_units(units)

    panel, _, _ = population.build(projected, log, scale=scale)

    blocks: list[pd.DataFrame] = []
    apportionments: dict[int, SurveyApportionment] = {}

    for survey in survey_list:
        trips = surveys.read(survey, log)
        allocation = apportion_survey(trips, trips.zones, projected, log)
        apportionments[survey.year] = allocation

        # The full grid first, so that a combination nothing reached arrives as a
        # gap the code can see rather than as a row that is simply not there.
        grid = pd.MultiIndex.from_product(
            [
                projected[config.AREA_CODE_COL],
                survey.actor_types,
                [day for day in config.DAY_TYPES if day in set(trips.universe_shares.index)],
            ],
            names=[config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL],
        ).to_frame(index=False)

        block = grid.merge(
            allocation.per_unit,
            on=[config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL],
            how="left",
        )
        block[config.YEAR_COL] = survey.year
        blocks.append(block)

    table = pd.concat(blocks, ignore_index=True)

    counted = [
        config.TRIPS_PER_AVERAGE_DAY_COL,
        config.INTRAZONAL_TRIPS_COL,
        config.TRIPS_AT_ORIGIN_COL,
        config.TRIPS_AT_DESTINATION_COL,
        config.DESIRE_LINE_KM_COL,
    ]
    untouched = int(table[config.TRIPS_PER_AVERAGE_DAY_COL].isna().sum())
    table[counted] = table[counted].fillna(0.0).astype(float)
    table[config.OD_PAIRS_TOUCHING_COL] = (
        table[config.OD_PAIRS_TOUCHING_COL].fillna(0).astype(int)
    )

    # The universe share is a property of the year and the day type, so it is the
    # same on every unit and actor type of a block. It travels in the table rather
    # than in the log because it is what converts one trip column into the other,
    # and a reader who cannot recompute the conversion cannot check it.
    shares = pd.concat(
        [
            apportionments[survey.year].trips.universe_shares.rename(
                config.DAY_TYPE_UNIVERSE_SHARE_COL
            ).to_frame().assign(**{config.YEAR_COL: survey.year})
            for survey in survey_list
        ]
    ).reset_index(names=config.DAY_TYPE_COL)
    table = table.merge(shares, on=[config.YEAR_COL, config.DAY_TYPE_COL], how="left")

    geometry = projected[
        [config.AREA_CODE_COL, config.AREA_NAME_COL, config.AREA_UNIT_KM2_COL]
    ]
    table = table.merge(geometry, on=config.AREA_CODE_COL, how="left")

    # The denominator is read at the year of the numerator, which is what the
    # survey path buys over the delivered layer: the trips now carry a year, so
    # the population does not have to be pinned to one and named for it. This is
    # what supersedes POPULATION_2023. See D36 and D38.
    residents = {
        survey.year: population.for_year(panel, survey.year) for survey in survey_list
    }
    table[config.POPULATION_COL] = [
        residents[year].get(code, np.nan)
        for year, code in zip(table[config.YEAR_COL], table[config.AREA_CODE_COL])
    ]

    table[config.TRIPS_PER_DAY_OF_TYPE_COL] = (
        table[config.TRIPS_PER_AVERAGE_DAY_COL] / table[config.DAY_TYPE_UNIVERSE_SHARE_COL]
    )
    area = table[config.AREA_UNIT_KM2_COL]
    table[config.TRIPS_PER_KM2_COL] = (
        table[config.TRIPS_PER_AVERAGE_DAY_COL] / area.where(area > 0)
    )
    people = table[config.POPULATION_COL]
    table[config.TRIPS_PER_INHABITANT_COL] = (
        table[config.TRIPS_PER_AVERAGE_DAY_COL] / people.where(people > 0)
    )

    unusable_area = ~(area > 0)
    table[config.PREDICTOR_STATUS_COL] = np.where(
        unusable_area, config.NOT_MEASURED_STATUS, config.MEASURED_STATUS
    )
    table.loc[unusable_area, counted] = np.nan

    table[config.SCALE_COL] = scale.label
    table = (
        table[list(config.survey_exposure_columns())]
        .sort_values(
            [config.YEAR_COL, config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    log.record(
        "assemble the long exposure table",
        rows_in=sum(len(a.per_unit) for a in apportionments.values()),
        rows_out=len(table),
        changes=[
            (
                len(table) - sum(len(a.per_unit) for a in apportionments.values()),
                "combinations of unit, actor type and day type that no trip reached, "
                "materialised as a measured zero rather than left absent",
            ),
        ],
        notes=[
            f"one row per unit, year, actor type and day type at {scale.label}",
            "years: " + ", ".join(str(survey.year) for survey in survey_list),
            f"{untouched} combination(s) with no trip at all, each an observed zero",
            f"{int(unusable_area.sum())} row(s) with no usable area, marked "
            f"{config.NOT_MEASURED_STATUS}",
        ],
    )
    return table, apportionments


def survey_dictionary_table(
    survey_list: tuple[config.MobilitySurvey, ...] | None = None,
) -> pd.DataFrame:
    """What each column of the long exposure table holds, in its own units.

    Built from the same declarations the measurement runs on, so it cannot
    describe a column the table does not have or miss one it does. The identity
    columns are in it too, because the table is joined to others outside this
    repository and a reader there has neither this code nor the survey.
    """
    survey_list = survey_list or config.MOBILITY_SURVEYS
    sources = "; ".join(
        f"{survey.year}: {survey.trips.path.name} with {survey.zoning.shapefile.name}"
        for survey in survey_list
    )

    rows = [
        {
            "COLUMN": config.ACTOR_TYPE_COL,
            "UNIT": "",
            "MEANS": (
                "the road user type whose travel is counted, in the vocabulary the casualty "
                f"matrix uses: {', '.join(config.ROAD_USER_TYPES)}. It is the column the matrix "
                f"is joined on, against its {config.PARTY_TYPE_COL}"
            ),
            "IS_ALTERNATIVE_ALLOCATION": False,
            "SOURCE": sources,
        },
        {
            "COLUMN": config.DAY_TYPE_COL,
            "UNIT": "",
            "MEANS": (
                f"the kind of day the trips were made on: {', '.join(config.DAY_TYPES)}. A "
                "dimension and not a suffix, so a year with no usable Saturday is absent from "
                "this column rather than carrying a zero"
            ),
            "IS_ALTERNATIVE_ALLOCATION": False,
            "SOURCE": sources,
        },
        {
            "COLUMN": config.POPULATION_COL,
            "UNIT": "inhabitants",
            "MEANS": (
                "resident population of the unit in the year of the row, read from "
                f"{config.POPULATION_SOURCE.path.name} and not from any survey. It carries no "
                "year in its name because the row does"
            ),
            "IS_ALTERNATIVE_ALLOCATION": False,
            "SOURCE": config.POPULATION_SOURCE.path.name,
        },
    ]
    rows.extend(
        {
            "COLUMN": quantity.name,
            "UNIT": quantity.unit,
            "MEANS": quantity.means,
            "IS_ALTERNATIVE_ALLOCATION": quantity.is_alternative,
            "SOURCE": sources,
        }
        for quantity in config.SURVEY_EXPOSURE_QUANTITIES
    )
    rows.append(
        {
            "COLUMN": config.PREDICTOR_STATUS_COL,
            "UNIT": "",
            "MEANS": (
                f"{config.MEASURED_STATUS} where the unit was measured, whatever came out, and "
                f"{config.NOT_MEASURED_STATUS} where it could not be; a unit no trip reaches is "
                f"{config.MEASURED_STATUS} with a zero"
            ),
            "IS_ALTERNATIVE_ALLOCATION": False,
            "SOURCE": "",
        }
    )
    return pd.DataFrame(rows)


def export_from_surveys(
    table: pd.DataFrame,
    log: RunLog,
    survey_list: tuple[config.MobilitySurvey, ...] | None = None,
) -> dict[str, Path]:
    """Write the long exposure table and the dictionary that reads it."""
    survey_list = survey_list or config.MOBILITY_SURVEYS
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    table_path = data_dir / f"{config.ANALYSIS_PREFIX}__exposure_by_unit.csv"
    table.to_csv(table_path, index=False, encoding="utf-8")
    table.to_parquet(table_path.with_suffix(".parquet"))
    paths["survey_table"] = table_path

    dictionary_path = data_dir / f"{config.REFERENCE_PREFIX}__exposure_dictionary.csv"
    survey_dictionary_table(survey_list).to_csv(dictionary_path, index=False, encoding="utf-8")
    paths["survey_dictionary"] = dictionary_path

    log.info(
        "exported the long exposure table (%d rows) and its dictionary to %s/",
        len(table),
        config.DATA_SUBDIR,
    )
    return paths


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def render_survey_figures(
    table: pd.DataFrame,
    units: gpd.GeoDataFrame,
    apportionments: dict[int, SurveyApportionment],
    log: RunLog,
    survey_list: tuple[config.MobilitySurvey, ...] | None = None,
) -> tuple[list[Path], list[int]]:
    """Two figures for every combination of survey year, actor type and day type.

    A choropleth of how much travel each unit ends up with, and beside it the
    desire lines that put it there. The second exists because this pipeline
    builds its own lines instead of receiving them drawn, so without a figure of
    them nobody can see what was built.

    **The choropleth shows `TRIPS_PER_DAY_OF_TYPE` and not the variable**, which
    is the one thing about these figures that has to be said out loud. A map
    titled "trips per day" has to carry the trips of a day, and the variable
    counts a day type's share of an average day — on a Saturday map that is six
    times too small, for no reason except that a seventh of the households were
    surveyed about a Saturday. See D38.

    **The colour scale is shared across the day types of one mode and never
    across modes.** Sharing it within a mode is what makes the three days
    comparable at a glance, which is the point of having the day as a dimension
    at all; sharing it across modes would draw bicycle and motorcycle at a fifth
    of a ramp scaled by walking and leave neither pattern readable.
    """
    survey_list = survey_list or config.MOBILITY_SURVEYS
    directory = log.run_dir / config.FIGURES_SUBDIR / config.EXPOSURE_FIGURES_SUBDIR
    mapped = config.TRIPS_PER_DAY_OF_TYPE_COL

    out_paths: list[Path] = []
    overflowing: list[int] = []
    for survey in survey_list:
        allocation = apportionments[survey.year]
        year_rows = table[table[config.YEAR_COL] == survey.year]
        day_types = [
            day for day in config.DAY_TYPES if day in set(year_rows[config.DAY_TYPE_COL])
        ]

        for actor in survey.actor_types:
            for_actor = year_rows[year_rows[config.ACTOR_TYPE_COL] == actor]
            if for_actor.empty:
                continue

            # One ramp for the mode, taken over its day types together. Computed
            # before any of the three is drawn, because a scale derived from the
            # first map would not be a shared scale.
            ceiling = float(for_actor[mapped].max())
            shared = (
                (0.0, ceiling)
                if config.MAP_CHOROPLETH_SHARE_SCALE_ACROSS_DAY_TYPES and ceiling > 0
                else None
            )

            for day_type in day_types:
                drawn = for_actor[for_actor[config.DAY_TYPE_COL] == day_type]
                if drawn.empty:
                    continue
                into = config.exposure_figure_dir(
                    directory, survey.year, actor, config.EXPOSURE_CHOROPLETH_SUBDIR
                )
                stem = (
                    f"{config.EXPOSURE_FIGURES_SUBDIR}__{survey.year}_{actor.lower()}"
                    f"_{day_type.lower()}"
                )
                values = drawn.set_index(config.AREA_CODE_COL)[mapped]
                caption = (
                    f"{config.ROAD_USER_LABELS_ES[actor]}, viajes por día · "
                    f"{config.DAY_TYPE_LABELS_ES[day_type]} {survey.year}"
                )

                variants = maps.figure_variants(into, stem)
                for position, (path, scalebar) in enumerate(variants):
                    spilling = maps.render_choropleth(
                        units, values, path, caption,
                        scalebar=scalebar, value_range=shared,
                    )
                    if position == 0:
                        overflowing.extend(spilling)
                out_paths.extend(path for path, _ in variants)

                log.info(
                    "choropleth %d %s %s: %d units, %s to %s trips per day, ramp to %s, "
                    "%d observed zero(s)",
                    survey.year,
                    actor,
                    day_type,
                    len(values),
                    f"{values.min():,.0f}",
                    f"{values.max():,.0f}",
                    f"{ceiling:,.0f}",
                    int((values == 0).sum()),
                )

                counts, line_paths = _render_desire_line_map(
                    allocation, units, actor, day_type, survey, directory, log
                )
                out_paths.extend(line_paths)
                if line_paths:
                    lines_drawn, reaching, built = counts
                    log.info(
                        "desire lines %d %s %s: %d line(s) built, %d reaching the units, "
                        "%d drawn (%.0f%% of the trips); the rest stay in the data",
                        survey.year,
                        actor,
                        day_type,
                        built,
                        reaching,
                        lines_drawn,
                        100 * config.MAP_DESIRE_LINE_TRIP_COVERAGE,
                    )

    for path in out_paths:
        log.info("wrote %s", path)
    return out_paths, overflowing


def _render_desire_line_map(
    allocation: SurveyApportionment,
    units: gpd.GeoDataFrame,
    actor: str,
    day_type: str,
    survey: config.MobilitySurvey,
    directory: Path,
    log: RunLog,
) -> tuple[tuple[int, int, int], list[Path]]:
    """The desire lines of one mode and day, drawn over the units.

    Only the inter-zonal trips have a line to draw. The intra-zonal ones are on
    the choropleth and cannot be here, because a trip that begins and ends in one
    zone has no line — which is exactly the fact that made them need a rule of
    their own. The caption says so rather than leaving the difference between the
    two figures unexplained.
    """
    selected = allocation.line_trips[
        (allocation.line_trips[config.ACTOR_TYPE_COL] == actor)
        & (allocation.line_trips[config.DAY_TYPE_COL] == day_type)
    ]
    if selected.empty:
        log.warn(
            "%d %s %s: no inter-zonal trip at all, so no desire-line map is drawn",
            survey.year,
            actor,
            day_type,
        )
        return (0, 0, 0), []

    geometry = allocation.lines.merge(
        selected[[_PAIR_ID_COL, surveys.TRIPS_COL]], on=_PAIR_ID_COL, how="inner"
    )
    into = config.exposure_figure_dir(
        directory, survey.year, actor, config.EXPOSURE_LINES_SUBDIR
    )
    stem = (
        f"{config.EXPOSURE_LINES_FIGURE_PREFIX}__{survey.year}_{actor.lower()}"
        f"_{day_type.lower()}"
    )
    variants = maps.figure_variants(into, stem)
    caption = (
        f"{config.ROAD_USER_LABELS_ES[actor]}, líneas de deseo entre zonas · "
        f"{config.DAY_TYPE_LABELS_ES[day_type]} {survey.year}"
    )

    weights = geometry[surveys.TRIPS_COL].to_numpy(dtype=float)
    for path, scalebar in variants:
        drawn, reaching = maps.render_desire_lines(
            units, geometry, weights, path, caption, scalebar=scalebar
        )
    return (drawn, reaching, len(geometry)), [path for path, _ in variants]


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_from_surveys(
    table: pd.DataFrame,
    apportionments: dict[int, SurveyApportionment],
    units: gpd.GeoDataFrame,
    log: RunLog,
    survey_list: tuple[config.MobilitySurvey, ...] | None = None,
    paths: dict[str, Path] | None = None,
) -> bool:
    """Check the long table against the surveys it was built from, and against arithmetic.

    The balance is the check that matters and it is made per actor type and day
    type rather than per year: an aggregate over the four modes could close while
    two of them were wrong in opposite directions, which is exactly the kind of
    error a total hides.
    """
    survey_list = survey_list or config.MOBILITY_SURVEYS
    checks: list[tuple[str, bool, str]] = []
    rtol = config.EXPOSURE_BALANCE_RTOL

    expected_columns = list(config.survey_exposure_columns())
    checks.append((
        "the table carries exactly the declared columns, in the declared order",
        list(table.columns) == expected_columns,
        f"{len(table.columns)} columns against {len(expected_columns)} declared",
    ))

    expected_units = set(units[config.AREA_CODE_COL])
    checks.append((
        "every row names a unit of the study",
        set(table[config.AREA_CODE_COL]) <= expected_units,
        f"{table[config.AREA_CODE_COL].nunique()} distinct units of {len(expected_units)}",
    ))

    key = [config.YEAR_COL, config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]
    checks.append((
        "no combination of unit, year, actor type and day type appears twice",
        not table.duplicated(subset=key).any(),
        f"{int(table.duplicated(subset=key).sum())} duplicated",
    ))

    measured = table[table[config.PREDICTOR_STATUS_COL] == config.MEASURED_STATUS]

    for survey in survey_list:
        allocation = apportionments[survey.year]
        year_rows = table[table[config.YEAR_COL] == survey.year]

        expected_rows = (
            len(expected_units)
            * len(survey.actor_types)
            * len(set(allocation.trips.universe_shares.index))
        )
        checks.append((
            f"{survey.year}: the grid of unit, actor type and day type is complete",
            len(year_rows) == expected_rows,
            f"{len(year_rows)} rows against {expected_rows} expected",
        ))

        # The balance, per actor type and day type. What was apportioned to the
        # units plus what fell outside them equals what the file holds — the check
        # the legacy pipeline could not have made, because the quantity it
        # exported was not a quantity the file held.
        worst_name, worst_gap = "", 0.0
        balanced = True
        for (actor, day_type), total in allocation.trips.totals.items():
            allocated = float(
                year_rows[
                    (year_rows[config.ACTOR_TYPE_COL] == actor)
                    & (year_rows[config.DAY_TYPE_COL] == day_type)
                ][config.TRIPS_PER_AVERAGE_DAY_COL].sum()
            )
            outside = float(allocation.outside.get((actor, day_type), 0.0))
            ok = bool(np.isclose(allocated + outside, float(total), rtol=rtol))
            balanced = balanced and ok
            gap = abs(allocated + outside - float(total))
            if gap > worst_gap:
                worst_gap, worst_name = gap, f"{actor}/{day_type}"
        checks.append((
            f"{survey.year}: apportioned plus outside equals the file, per actor type and day",
            balanced,
            f"{len(allocation.trips.totals)} combination(s), largest gap {worst_gap:.6f} "
            f"trips at {worst_name or 'none'}",
        ))

        # The four modes of the file have to be the four modes of the table, or
        # something was lost between the two that the balance would not see
        # because it is checked per mode.
        measured_total = float(allocation.trips.totals.sum())
        table_total = float(
            year_rows[config.TRIPS_PER_AVERAGE_DAY_COL].sum()
        ) + float(allocation.outside.sum())
        checks.append((
            f"{survey.year}: the four measured modes add to the file's own total for them",
            bool(np.isclose(table_total, measured_total, rtol=rtol)),
            f"{table_total:,.2f} against {measured_total:,.2f}",
        ))

        # And the file itself is accounted for. This is the check the whole
        # reading is worth: the four modes the study measures, plus the modes it
        # deliberately does not, plus the records whose zone is missing, add to
        # the survey's own published total. The two sides are different groupings
        # of the same column, so it is a check and not a restatement — a mode
        # quietly dropped between the mapping and the totals would show here and
        # nowhere else.
        implausible = float(allocation.trips.implausible_totals.sum())
        accounted = (
            measured_total
            + float(allocation.trips.not_measured_totals.sum())
            + allocation.trips.unzoned_total
            + implausible
        )
        checks.append((
            f"{survey.year}: every trip the file weights is measured or named as set aside",
            bool(np.isclose(accounted, allocation.trips.file_total, rtol=rtol)),
            f"{measured_total:,.1f} measured + "
            f"{float(allocation.trips.not_measured_totals.sum()):,.1f} in modes outside the "
            f"study + {allocation.trips.unzoned_total:,.1f} unzoned + {implausible:,.1f} "
            f"impossible for their mode = {accounted:,.1f} "
            f"against {allocation.trips.file_total:,.1f}",
        ))

        checks.append((
            f"{survey.year}: nothing is apportioned more than once over",
            allocation.largest_covered_share <= 1 + config.EXPOSURE_MAX_OVER_COVERAGE,
            f"largest share of a line or zone covered by the units: "
            f"{allocation.largest_covered_share:.9f}",
        ))

        # The intra-zonal trips are a part of the variable and not an addition to
        # it, so they can never exceed it.
        year_measured = measured[measured[config.YEAR_COL] == survey.year]
        over = int(
            (
                year_measured[config.INTRAZONAL_TRIPS_COL]
                > year_measured[config.TRIPS_PER_AVERAGE_DAY_COL] * (1 + 1e-9)
            ).sum()
        )
        checks.append((
            f"{survey.year}: the intra-zonal trips are a part of the variable, never more",
            over == 0,
            f"{over} row(s) where the part exceeds the whole",
        ))

    negatives = int((measured[config.TRIPS_PER_AVERAGE_DAY_COL] < 0).sum())
    checks.append(("no negative trip count", negatives == 0, f"{negatives} negative"))

    # The two trip columns are the same apportionment of one expansion read two
    # ways, so one has to be the other divided by the share the table carries. It
    # is checked against the column in the same table because that is what a
    # reader would recompute it from.
    share = measured[config.DAY_TYPE_UNIVERSE_SHARE_COL]
    checks.append((
        "trips per day of type is trips per average day over the universe share",
        bool(np.allclose(
            (measured[config.TRIPS_PER_AVERAGE_DAY_COL] / share).to_numpy(),
            measured[config.TRIPS_PER_DAY_OF_TYPE_COL].to_numpy(),
            rtol=1e-12,
            equal_nan=True,
        )),
        f"compared to 1e-12 over {len(measured)} measured row(s)",
    ))
    checks.append((
        "the universe shares of a year add to one",
        bool(np.allclose(
            [
                float(apportionments[survey.year].trips.universe_shares.sum())
                for survey in survey_list
            ],
            1.0,
            rtol=1e-9,
        )),
        ", ".join(
            f"{survey.year}: {float(apportionments[survey.year].trips.universe_shares.sum()):.12f}"
            for survey in survey_list
        ),
    ))

    checks.append((
        "the per-km2 column is the variable over the area of its own unit",
        bool(np.allclose(
            (measured[config.TRIPS_PER_AVERAGE_DAY_COL]
             / measured[config.AREA_UNIT_KM2_COL]).to_numpy(),
            measured[config.TRIPS_PER_KM2_COL].to_numpy(),
            rtol=1e-12,
        )),
        "compared to 1e-12",
    ))
    people = measured[config.POPULATION_COL]
    checks.append((
        "the per-inhabitant column is the variable over the population of the same year",
        bool(np.allclose(
            (measured[config.TRIPS_PER_AVERAGE_DAY_COL] / people.where(people > 0)).to_numpy(),
            measured[config.TRIPS_PER_INHABITANT_COL].to_numpy(),
            rtol=1e-12,
            equal_nan=True,
        )),
        f"compared to 1e-12; {int(people.isna().sum())} row(s) with no population",
    ))

    zero_rows = table[table[config.TRIPS_PER_AVERAGE_DAY_COL] == 0]
    checks.append((
        "a combination no trip reaches carries a zero and the status MEASURED",
        bool((zero_rows[config.PREDICTOR_STATUS_COL] == config.MEASURED_STATUS).all()),
        f"{len(zero_rows)} row(s) at zero",
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
    for name, ok, detail in checks:
        rendered.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("survey exposure verification:", "\n".join(rendered))

    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("survey exposure verification FAILED")
    return passed


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def report_from_surveys(
    table: pd.DataFrame,
    apportionments: dict[int, SurveyApportionment],
    log: RunLog,
    survey_list: tuple[config.MobilitySurvey, ...] | None = None,
) -> None:
    """What each survey says, in numbers, for whoever reads the log instead."""
    survey_list = survey_list or config.MOBILITY_SURVEYS

    for survey in survey_list:
        allocation = apportionments[survey.year]
        year_rows = table[table[config.YEAR_COL] == survey.year]

        log.info(
            "%s: %d record(s) read, %d measured in the four modes; %s trips per day in the "
            "file, %s of them in those modes",
            survey.label,
            allocation.trips.records_read,
            allocation.trips.records_measured,
            f"{allocation.trips.file_total:,.0f}",
            f"{float(allocation.trips.totals.sum()):,.0f}",
        )
        log.info(
            "%d of %d zone(s) and %d of %d origin-destination pair(s) reach a unit",
            allocation.zones_reaching_a_unit,
            allocation.zones_read,
            allocation.pairs_reaching_a_unit,
            allocation.pairs_built,
        )

        weekday = year_rows[year_rows[config.DAY_TYPE_COL] == config.WEEKDAY_TYPE]
        for actor in survey.actor_types:
            rows = weekday[weekday[config.ACTOR_TYPE_COL] == actor]
            inside = float(rows[config.TRIPS_PER_AVERAGE_DAY_COL].sum())
            total = float(allocation.trips.totals.get((actor, config.WEEKDAY_TYPE), np.nan))
            top = rows.nlargest(3, config.TRIPS_PER_AVERAGE_DAY_COL)
            log.info(
                "%d %s on a typical weekday: %s of %s trips per day inside the units (%.1f%%); "
                "most exposed %s",
                survey.year,
                actor.lower(),
                f"{inside:,.0f}",
                f"{total:,.0f}",
                100 * inside / total if total else float("nan"),
                "; ".join(
                    f"{row[config.AREA_CODE_COL]} {row[config.AREA_NAME_COL]} "
                    f"{row[config.TRIPS_PER_AVERAGE_DAY_COL]:,.0f}"
                    for _, row in top.iterrows()
                ),
            )
            empty = rows[rows[config.TRIPS_PER_AVERAGE_DAY_COL] == 0]
            if len(empty):
                log.info(
                    "no %s trip reaches %s, which is an observed zero and not a missing value",
                    actor.lower(),
                    ", ".join(
                        f"{row[config.AREA_CODE_COL]} ({row[config.AREA_NAME_COL]})"
                        for _, row in empty.iterrows()
                    ),
                )

        # The alternatives exist to be compared, so the comparison is made here
        # rather than left for someone to do by hand. Rank correlation rather
        # than Pearson: what matters is whether the rules order the units the
        # same way, not whether they agree on a magnitude they do not share.
        alternatives = [config.TRIPS_PER_AVERAGE_DAY_COL] + [
            quantity.name
            for quantity in config.SURVEY_EXPOSURE_QUANTITIES
            if quantity.is_alternative
        ]
        for actor in survey.actor_types:
            rows = weekday[weekday[config.ACTOR_TYPE_COL] == actor]
            ranks = rows[alternatives].corr(method="spearman")
            log.table(
                f"{survey.year} {actor.lower()}, typical weekday: rank correlation between the "
                "allocation rules (Spearman), the variable first:",
                ranks.to_string(float_format=lambda value: f"{value:.3f}"),
            )

        # Said on every run, because the number invites a reading it cannot carry.
        # Only for a year whose factor spreads the universe over several reference
        # days: there the two trip columns differ, the rescaled one makes a
        # Saturday look like a weekday, and a reader comparing the day types has
        # to know that before doing it. A year that surveyed one kind of day has
        # nothing to rescale and saying this of it would be false.
        shares = allocation.trips.universe_shares
        rates = {
            day_type: float(
                year_rows[year_rows[config.DAY_TYPE_COL] == day_type][
                    config.TRIPS_PER_DAY_OF_TYPE_COL
                ].sum()
            )
            for day_type in shares.index
        }
        if survey.weight_expands_to == config.WEIGHT_EXPANDS_TO_AVERAGE_DAY:
            log.warn(
                "%d: rescaled to the universe the day types come out at %s trips per day. The "
                "expansion factor represents the universe once over all the reference days "
                "together, so %s counts a day type's share of an average day and %s counts one "
                "day of that type; only the second is comparable between day types, and it says "
                "a Saturday carries as much travel as a weekday. See D38",
                survey.year,
                "; ".join(f"{day_type} {value:,.0f}" for day_type, value in rates.items()),
                config.TRIPS_PER_AVERAGE_DAY_COL,
                config.TRIPS_PER_DAY_OF_TYPE_COL,
            )
        else:
            log.info(
                "%d: %s over one kind of day, %s, so %s and %s hold the same number and no "
                "rescaling happened. The year carries no second day type to compare it against",
                survey.year,
                survey.weight_expands_to,
                "; ".join(f"{day_type} {value:,.0f}" for day_type, value in rates.items()),
                config.TRIPS_PER_AVERAGE_DAY_COL,
                config.TRIPS_PER_DAY_OF_TYPE_COL,
            )


# ---------------------------------------------------------------------------
# One year against the years already measured
# ---------------------------------------------------------------------------


def _mode_share(weekday: pd.DataFrame, year: int, actor: str) -> float:
    """One actor type's share of the four measured modes, in one year."""
    rows = weekday[weekday[config.YEAR_COL] == year]
    whole = float(rows[config.TRIPS_PER_AVERAGE_DAY_COL].sum())
    if not whole:
        return float("nan")
    part = rows[rows[config.ACTOR_TYPE_COL] == actor]
    return float(part[config.TRIPS_PER_AVERAGE_DAY_COL].sum()) / whole


def _trips_per_inhabitant(rows: pd.DataFrame) -> float:
    """Trips per resident, over whatever slice of the table is passed."""
    residents = float(rows[config.POPULATION_COL].sum())
    if not residents:
        return float("nan")
    return float(rows[config.TRIPS_PER_AVERAGE_DAY_COL].sum()) / residents


def _rank_agreement(before: pd.DataFrame, after: pd.DataFrame) -> float:
    """Spearman between two years' orderings of the units, or NaN if not comparable."""
    paired = pd.concat(
        [
            before.set_index(config.AREA_CODE_COL)[config.TRIPS_PER_AVERAGE_DAY_COL],
            after.set_index(config.AREA_CODE_COL)[config.TRIPS_PER_AVERAGE_DAY_COL],
        ],
        axis=1,
    ).dropna()
    if len(paired) <= 2:
        return float("nan")
    return float(paired.corr(method="spearman").iloc[0, 1])


def compare_years(
    table: pd.DataFrame,
    apportionments: dict[int, SurveyApportionment],
    log: RunLog,
) -> None:
    """Put each survey beside the ones before it, and say where they disagree.

    Every year is read through its own declaration, because every survey was run
    by a different administration and catalogues its data its own way. That means
    a handful of independent decisions per year — which column is the expansion
    factor, what it expands to, how the day type is stated, what the mode labels
    are — and any one of them can be wrong in a way that still produces numbers
    that look entirely reasonable on their own.

    Nothing inside a year catches that. What catches it is the year before:
    Bogotá does not remake its travel between two surveys, so a mode share that
    moves fifteen points, a per-inhabitant trip rate that doubles, or a ranking of
    the thirty units that stops agreeing with the previous survey is a misread
    column long before it is a finding about the city.

    Everything here is a warning and never a failure. A real change of that size
    is possible and this cannot tell the two apart; what it can do is refuse to
    let one through unremarked.
    """
    years = sorted(apportionments)
    weekday = table[table[config.DAY_TYPE_COL] == config.WEEKDAY_TYPE]

    rendered = [
        f"{'year':>6}  {'actor type':<12}  {'trips/day':>12}  {'share':>7}  "
        f"{'per inhab.':>10}  {'vs prev.':>8}",
        f"{'-' * 6}  {'-' * 12}  {'-' * 12}  {'-' * 7}  {'-' * 10}  {'-' * 8}",
    ]
    seen: dict[str, pd.DataFrame] = {}
    for year in years:
        rows = weekday[weekday[config.YEAR_COL] == year]
        for actor in apportionments[year].survey.actor_types:
            for_actor = rows[rows[config.ACTOR_TYPE_COL] == actor]
            agreement = _rank_agreement(seen[actor], for_actor) if actor in seen else float("nan")
            seen[actor] = for_actor
            rendered.append(
                f"{year:>6}  {actor:<12}  "
                f"{float(for_actor[config.TRIPS_PER_AVERAGE_DAY_COL].sum()):>12,.0f}  "
                f"{_mode_share(weekday, year, actor):>7.1%}  "
                f"{_trips_per_inhabitant(for_actor):>10.3f}  "
                + (f"{agreement:>8.3f}" if np.isfinite(agreement) else f"{'—':>8}")
            )
    log.table(
        "exposure across the surveys, typical weekday, inside the study units:",
        "\n".join(rendered),
    )

    # What each year set aside, which is the other place a misread declaration
    # shows: a year dropping far more or far less than its neighbours is a year
    # whose duration column, mode map or zoning is not doing what it was declared
    # to do.
    aside = [
        f"{'year':>6}  {'in the file':>14}  {'measured':>14}  {'impossible':>10}  "
        f"{'intra-zonal':>11}  {'outside':>8}",
        f"{'-' * 6}  {'-' * 14}  {'-' * 14}  {'-' * 10}  {'-' * 11}  {'-' * 8}",
    ]
    for year in years:
        allocation = apportionments[year]
        measured = float(allocation.trips.totals.sum())
        impossible = float(allocation.trips.implausible_totals.sum())
        pairs = allocation.trips.pairs
        intra = float(
            pairs.loc[
                pairs[surveys.ZONE_ORIGIN_COL] == pairs[surveys.ZONE_DESTINATION_COL],
                surveys.TRIPS_COL,
            ].sum()
        )
        aside.append(
            f"{year:>6}  {allocation.trips.file_total:>14,.0f}  {measured:>14,.0f}  "
            f"{impossible / (measured + impossible):>10.1%}  {intra / measured:>11.1%}  "
            f"{float(allocation.outside.sum()) / measured:>8.1%}"
        )
    log.table("what each survey set aside, as a share of what it measured:", "\n".join(aside))

    if len(years) < 2:
        log.info(
            "only %d survey is implemented, so there is nothing to compare it against yet. "
            "The two tables above are the baseline the next year is read against; see D38",
            len(years),
        )
        return

    for earlier, later in zip(years, years[1:]):
        for actor in apportionments[later].survey.actor_types:
            before = weekday[
                (weekday[config.YEAR_COL] == earlier) & (weekday[config.ACTOR_TYPE_COL] == actor)
            ]
            after = weekday[
                (weekday[config.YEAR_COL] == later) & (weekday[config.ACTOR_TYPE_COL] == actor)
            ]
            if before.empty or after.empty:
                continue

            moved = _mode_share(weekday, later, actor) - _mode_share(weekday, earlier, actor)
            if abs(moved) > config.EXPOSURE_YEAR_MODE_SHARE_JUMP:
                log.warn(
                    "%s moves %+.1f points of the four-mode share between %d and %d, past the "
                    "%.0f-point threshold. Check the mode map and the expansion factor of %d "
                    "before reading it as a change in the city. See D38",
                    actor, 100 * moved, earlier, later,
                    100 * config.EXPOSURE_YEAR_MODE_SHARE_JUMP, later,
                )

            was, now = _trips_per_inhabitant(before), _trips_per_inhabitant(after)
            if np.isfinite(was) and was > 0:
                change = now / was - 1.0
                if abs(change) > config.EXPOSURE_YEAR_TRIP_RATE_JUMP:
                    log.warn(
                        "%s trips per inhabitant move %+.0f%% between %d and %d, past the %.0f%% "
                        "threshold, from %.3f to %.3f. That is the shape of a factor expanding "
                        "to something other than what %d declares. See D38",
                        actor, 100 * change, earlier, later,
                        100 * config.EXPOSURE_YEAR_TRIP_RATE_JUMP, was, now, later,
                    )

            agreement = _rank_agreement(before, after)
            if np.isfinite(agreement) and agreement < config.EXPOSURE_YEAR_RANK_AGREEMENT_FLOOR:
                log.warn(
                    "%s orders the units at Spearman %.3f between %d and %d, below the %.2f "
                    "floor. The geography of a mode does not reinvent itself between two "
                    "surveys, so suspect the zoning or the zone codes of either year before "
                    "reading it as a change in the city — the one already verified is the less "
                    "likely of the two, not the innocent one. It is the same measurement that "
                    "showed the delivered layer was not what it claimed. See D38",
                    actor, agreement, earlier, later,
                    config.EXPOSURE_YEAR_RANK_AGREEMENT_FLOOR,
                )
