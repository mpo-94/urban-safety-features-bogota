"""Travel exposure per territorial unit, from the origin-destination desire lines.

This is not an urban predictor and the separation is deliberate. A predictor says
what a place is built like; exposure says how much traffic there is in it to be
hurt. In a rate model they sit on opposite sides, so the exposure never enters the
predictor correlation matrix and never appears in either figure set: a row for it
there would invite a reader to compare it with variables it does not compete with.

**What the source is.** Each line runs from the centroid of an origin zone of the
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
from shapely.geometry import Point

try:  # regular package import
    from src import config, maps, population, predictors
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import maps  # type: ignore[no-redef]
    import population  # type: ignore[no-redef]
    import predictors  # type: ignore[no-redef]
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
    """Write the exposure table and the dictionary that reads it."""
    layers = layers or config.EXPOSURE_LAYERS
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    table_path = data_dir / f"{config.ANALYSIS_PREFIX}__exposure_by_unit.csv"
    table.to_csv(table_path, index=False, encoding="utf-8")
    table.to_parquet(table_path.with_suffix(".parquet"))
    paths["table"] = table_path

    dictionary_path = data_dir / f"{config.REFERENCE_PREFIX}__exposure_dictionary.csv"
    dictionary_table(layers).to_csv(dictionary_path, index=False, encoding="utf-8")
    paths["dictionary"] = dictionary_path

    log.info("exported 1 analysis table and 1 reference table to %s/", config.DATA_SUBDIR)
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
        stem = f"{config.EXPOSURE_FIGURES_SUBDIR}__{layer.name.lower()}"
        plain = directory / f"{stem}.{config.MAP_FIGURE_FORMAT}"
        with_bar = directory / f"{stem}{config.MAP_SCALEBAR_SUFFIX}.{config.MAP_FIGURE_FORMAT}"

        values = table.set_index(config.AREA_CODE_COL)[layer.column(config.TRIPS_WEEKLY_SUFFIX)]
        caption = f"{layer.label_es} por semana"

        spilling = maps.render_choropleth(units, values, plain, caption, scalebar=False)
        maps.render_choropleth(units, values, with_bar, caption, scalebar=True)
        out_paths.extend([plain, with_bar])
        overflowing.extend(spilling)

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
