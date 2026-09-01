"""Static urban predictors measured against every territorial unit.

The other half of the study. The casualty matrix says how much harm happened
where; these variables say what the place is like. Thirteen of them are
implemented here, all single snapshots with no year: five surfaces measured as a
share of the unit, and eight point layers measured as a density over it.

Two of the thirteen are measured on part of their layer rather than all of it,
and both read the same layer as a third that is measured whole. The rule that
selects the part is declared beside the variable, applied when the layer is read,
and reported in the funnel like any other loss of records.

The four layers that carry an annual series — cycleways and the three signage
layers — are not here yet. Nothing in this module is shaped around the absence of
a time dimension: the long table carries a YEAR column already, null for a
snapshot, and a series slots into it without a schema change. All four are line
layers, and the measurement they will use is written and registered: what they
need beyond it is the year, not a way of being measured.

The line splitting is also what the exposure module builds on, which is why it is
a function of its own rather than a step inside the line measurement.

Every variable is declared in the configuration — its source layer as the data
names it, its file, its geometry, what it measures and by which method — and the
measurement runs on that declaration: it builds the path from it, dispatches on
it and checks the geometry of the file against it. The declaration is exported as
a data dictionary beside the tables, so a column name in English can be traced to
a layer named in Spanish without reading any code.

Two things the inherited pipeline did are deliberately not done here:

* A unit with no observation gets a row with a zero, not no row at all. In the
  legacy output a unit with no speed camera and a unit the layer never reached
  look identical, which would quietly turn a histogram of thirty units into a
  histogram of twenty-four.
* Everything the measurement drops is counted and reported. The legacy point
  join was an inner join, so points falling outside every unit disappeared with
  no record of how many.

Run it on its own:

    python -m src.run_pipeline predictors
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Callable

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")  # figures are written to disk, never displayed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:  # regular package import
    from src import config, latex
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import latex  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# Working columns, private to the measurement. They never reach an exported
# table, so they are named apart from the configured ones to make that obvious.
_FEATURE_COL = "_FEATURE"
_FRAGMENT_AREA_COL = "_FRAGMENT_AREA_KM2"

# The one exception to the rule above: this column is part of what
# `split_lines_by_unit` returns, so the exposure module reads it by name. It is
# still working data and still never reaches an exported table.
FRAGMENT_LENGTH_COL = "_FRAGMENT_LENGTH_KM"


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


def prepare_units(units: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Project the unit layer to the metric CRS and attach its own area.

    Area comes from the geometry rather than from the AREA_HA attribute the
    shapefile carries, so that the denominator of every variable is measured in
    the same projection as the numerator. The two agree to within 0.1% where both
    exist, but mixing them would make a share of a unit slightly incoherent with
    itself for no gain.
    """
    projected = units.to_crs(epsg=config.PROJECTED_CRS).copy()
    projected[config.AREA_UNIT_KM2_COL] = projected.geometry.area / 1e6
    return projected


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


def _repair(layer: gpd.GeoDataFrame, predictor: config.StaticPredictor, log: RunLog) -> tuple[gpd.GeoDataFrame, int]:
    """Drop unusable geometries and repair invalid ones, reporting both.

    Repair is `make_valid` followed by `buffer(0)`: the first fixes the topology,
    the second reduces the geometry collection `make_valid` can return — polygons
    plus the lines and points where a ring touched itself — back to its areal
    part, which is the only part that has an area to contribute.
    """
    usable = layer[layer.geometry.notna() & ~layer.geometry.is_empty]
    dropped = len(layer) - len(usable)
    if dropped:
        log.warn("%s: %d feature(s) have no usable geometry and cannot be measured", predictor.name, dropped)

    invalid = ~usable.geometry.is_valid
    invalid_count = int(invalid.sum())
    if invalid_count:
        usable = usable.copy()
        usable.loc[invalid, "geometry"] = usable.loc[invalid, "geometry"].make_valid().buffer(0)
        log.info("%s: repaired %d invalid geometr(ies)", predictor.name, invalid_count)
        emptied = usable[usable.geometry.is_empty]
        if len(emptied):
            log.warn("%s: %d geometr(ies) were emptied by the repair", predictor.name, len(emptied))
            usable = usable[~usable.geometry.is_empty]
            dropped += len(emptied)

    return usable, dropped


def _apply_filter(
    layer: gpd.GeoDataFrame, predictor: config.StaticPredictor, log: RunLog
) -> gpd.GeoDataFrame:
    """Keep the part of a layer its variable is declared to measure.

    Everything the rule touches is reported: the whole distribution of the column
    it reads, what each excluded value cost, and what is left. A selection that
    quietly removed a fifth of a layer would be the same failure as a vehicle type
    falling through a mapping into a null, and it is treated the same way.

    Two things stop the run rather than being worked around, because both mean the
    declaration and the file disagree and neither can be resolved by guessing. A
    value the rule names that the column does not hold means the rule is not doing
    what it says, which is exactly the defect the legacy pipeline had twice: a
    filter that never filters. A null in the column is a row the rule cannot
    classify, and keeping or dropping it would both be an assumption.
    """
    rule = predictor.source_filter
    assert rule is not None  # the caller checks; this keeps the type checker honest

    if rule.column not in layer.columns:
        raise ValueError(
            f"{predictor.name}: the selection rule reads {rule.column!r}, which "
            f"{predictor.source_layer} does not have; it holds {', '.join(sorted(layer.columns))}"
        )

    values = layer[rule.column]
    missing = int(values.isna().sum())
    if missing:
        raise ValueError(
            f"{predictor.name}: {missing:,} row(s) have no {rule.column!r}, so the selection "
            "rule cannot say whether they are in or out; the layer changed and the rule needs "
            "a decision, not a default"
        )

    counts = values.value_counts()
    absent = [value for value in rule.declared_values if value not in counts.index]
    if absent:
        raise ValueError(
            f"{predictor.name}: the rule names {', '.join(absent)}, which {rule.column!r} "
            f"does not contain; it holds {', '.join(map(str, counts.index))}. A rule naming a "
            "value the source does not use does not do what it says, and whichever half of it "
            "is wrong would go unnoticed"
        )

    surviving = values.map(rule.keeps_value)
    kept = layer[surviving]

    # The whole distribution, not only the part that was dropped. Which codes the
    # census uses and how many trees each carries is the evidence the criterion
    # rests on, and it belongs in the log of the run that applied it.
    log.table(
        f"{predictor.name}: {rule.column} across the layer, and what the rule did with each value:",
        "\n".join(
            f"  {str(value):<6} {count:>9,}  {'kept' if rule.keeps_value(value) else 'dropped'}"
            for value, count in counts.items()
        ),
    )
    # Its own entry in the funnel rather than a line folded into the measurement,
    # so the balance still closes on the layer as delivered. The measurement that
    # follows starts from what the rule left, and the funnel says how much that
    # was and why.
    log.record(
        f"select {predictor.name}",
        rows_in=len(layer),
        rows_out=len(kept),
        # One named cause per value the rule sends away, whichever way round the
        # rule is written. Rolling them into a single "did not match" would hide
        # which code cost what, and that breakdown is the evidence the criterion
        # rests on.
        changes=[
            (-int(count), f"features with {rule.column} = {value}, which {rule.rationale}")
            for value, count in counts.items()
            if not rule.keeps_value(value)
        ],
        notes=[f"rule: {rule.description}"],
    )
    return kept


def _read_source(predictor: config.StaticPredictor, log: RunLog) -> gpd.GeoDataFrame:
    """Read the layer a predictor declares, and hold the declaration to account.

    The path is built from the declared layer name and geometry, so a wrong name
    raises here instead of measuring something else, and the geometry types the
    file actually holds are checked against the declared kind. This is what keeps
    the data dictionary from drifting: it is not a description of the pipeline,
    it is what the pipeline reads.
    """
    try:
        path = config.resolve_source_path(predictor.path)
    except FileNotFoundError as missing:
        raise FileNotFoundError(
            f"{predictor.name}: the declared source {predictor.path} does not exist; "
            f"layer {predictor.source_layer!r}, file {predictor.source_file!r}"
        ) from missing

    # Only the geometry and, where there is a selection rule, the one column that
    # rule reads. The measurements use no other attribute, and the tree census
    # carries fifteen columns over 1.5 million rows, so reading the lot would cost
    # a few hundred megabytes to throw them away immediately.
    wanted = [predictor.source_filter.column] if predictor.source_filter else []
    layer = gpd.read_file(path, columns=wanted)
    read = len(layer)

    if predictor.source_filter is not None:
        layer = _apply_filter(layer, predictor, log)

    # Null geometries are not a disagreement about the kind of layer this is; the
    # repair step counts and drops them a moment later.
    present = set(layer.geom_type.dropna())
    unexpected = sorted(present - set(config.GEOMETRY_TYPES[predictor.geometry]))
    if unexpected:
        raise ValueError(
            f"{predictor.name}: declared as {predictor.geometry} geometry, but "
            f"{predictor.source_layer} holds {', '.join(unexpected)}; the declaration and "
            "the file disagree, and the measurement would be meaningless either way"
        )
    log.info(
        "%s: read %s from %s/%s (%s)",
        predictor.name,
        f"{read:,} features"
        if predictor.source_filter is None
        else f"{read:,} features, {len(layer):,} of them kept by the selection rule",
        predictor.source_layer,
        predictor.source_file,
        predictor.geometry,
    )
    return layer


def measure_area_layer(
    predictor: config.StaticPredictor,
    units: gpd.GeoDataFrame,
    log: RunLog,
) -> pd.DataFrame:
    """Surface of the layer inside each unit, in square kilometres.

    The intersection is taken in the projected CRS, so the areas are metric. A
    feature straddling a boundary contributes its own part to each unit it
    reaches, which is why the fragment count exceeds the feature count.
    """
    raw = _read_source(predictor, log)
    polygons, dropped = _repair(raw, predictor, log)

    # Attributes are not used by any of the five area variables — the surface is
    # the whole measurement — so everything but the geometry is discarded before
    # the overlay rather than carried through it.
    polygons = polygons[["geometry"]].to_crs(epsg=config.PROJECTED_CRS).reset_index(drop=True)
    polygons[_FEATURE_COL] = np.arange(len(polygons))
    total_km2 = float(polygons.geometry.area.sum() / 1e6)

    fragments = gpd.overlay(
        polygons,
        units[[config.AREA_CODE_COL, "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    fragments[_FRAGMENT_AREA_COL] = fragments.geometry.area / 1e6

    reached = int(fragments[_FEATURE_COL].nunique())
    outside = len(polygons) - reached
    split = len(fragments) - reached
    captured_km2 = float(fragments[_FRAGMENT_AREA_COL].sum())

    log.record(
        f"measure {predictor.name}",
        rows_in=len(raw),
        rows_out=len(fragments),
        changes=[
            (-dropped, "features with no usable geometry, which cannot be measured"),
            (-outside, "features falling outside every unit, contributing to no unit"),
            (split, "fragments gained where a feature crosses a unit boundary and is split between units"),
        ],
        notes=[
            f"source={predictor.source_layer}/{predictor.source_file}, {predictor.measures}",
            f"{captured_km2:,.4f} km2 captured inside the units of "
            f"{total_km2:,.4f} km2 in the layer "
            f"({100 * captured_km2 / total_km2:.2f}%)" if total_km2 > 0 else "layer has no area",
        ],
    )

    measured = fragments.groupby(config.AREA_CODE_COL)[_FRAGMENT_AREA_COL].sum()
    return measured.rename(config.PREDICTOR_MEASURE_COL).reset_index()


def measure_point_layer(
    predictor: config.StaticPredictor,
    units: gpd.GeoDataFrame,
    log: RunLog,
) -> pd.DataFrame:
    """Number of points of the layer inside each unit.

    MultiPoint features are exploded first, so a station recorded as a collection
    of platforms counts once per platform rather than once per record — which is
    what a density of stations is asking for.
    """
    raw = _read_source(predictor, log)
    usable, dropped = _repair(raw, predictor, log)

    exploded = usable[["geometry"]].explode(index_parts=False).reset_index(drop=True)
    from_multipart = len(exploded) - len(usable)
    points = exploded.to_crs(epsg=config.PROJECTED_CRS)

    joined = gpd.sjoin(
        points,
        units[[config.AREA_CODE_COL, "geometry"]],
        how="inner",
        predicate=config.SPATIAL_JOIN_PREDICATE,
    )

    changes: list[tuple[int, str]] = [
        (-dropped, "features with no usable geometry, which cannot be located"),
        (from_multipart, "parts gained by exploding multi-part features into one point each"),
    ]

    # Only possible where unit polygons overlap. Resolved the same way the
    # casualty join resolves it, so a point cannot be counted twice.
    ambiguous = int(joined.index.duplicated().sum())
    if ambiguous:
        log.warn(
            "%s: %d point(s) fall inside more than one unit; keeping the lowest unit code",
            predictor.name,
            ambiguous,
        )
        joined = joined.sort_values(config.AREA_CODE_COL, kind="stable")
        joined = joined[~joined.index.duplicated(keep="first")]
        changes.append((ambiguous, "points matching more than one unit (overlapping polygons)"))
        changes.append((-ambiguous, "ambiguous matches resolved to the lowest unit code"))

    outside = len(points) - len(joined)
    changes.append((-outside, "points falling outside every unit, counted in no unit"))

    log.record(
        f"measure {predictor.name}",
        rows_in=len(raw),
        rows_out=len(joined),
        changes=changes,
        notes=[
            f"source={predictor.source_layer}/{predictor.source_file}, {predictor.measures}",
            f"{len(joined):,} of {len(points):,} points fall inside a unit "
            f"({100 * len(joined) / len(points):.2f}%)" if len(points) else "layer has no points",
        ],
    )

    measured = joined.groupby(config.AREA_CODE_COL).size()
    return measured.rename(config.PREDICTOR_MEASURE_COL).reset_index()


def usable_lines(layer: gpd.GeoDataFrame, name: str, log: RunLog) -> tuple[gpd.GeoDataFrame, int]:
    """Drop the lines with no geometry, and say how many went.

    Deliberately not the repair the polygon layers get. That repair is
    `make_valid` followed by `buffer(0)`, and the second step reduces a geometry
    to its areal part — which for a line is nothing at all, so the operation that
    rescues a self-touching polygon would silently delete every line it touched.
    There is also nothing for it to fix: a LineString is valid under the OGC rules
    however it crosses itself, so the invalid branch would never fire and would
    destroy the layer on the one occasion it did.
    """
    usable = layer[layer.geometry.notna() & ~layer.geometry.is_empty]
    dropped = len(layer) - len(usable)
    if dropped:
        log.warn("%s: %d line(s) have no usable geometry and cannot be measured", name, dropped)
    return usable, dropped


def split_lines_by_unit(
    lines: gpd.GeoDataFrame,
    units: gpd.GeoDataFrame,
    id_column: str,
) -> gpd.GeoDataFrame:
    """Cut every line at the unit boundaries and measure each piece, in kilometres.

    One row per (line, unit) pair, carrying the length of that line inside that
    unit. A line crossing three units yields three rows, and a line that leaves
    the study area and comes back yields one row per unit with the parts summed
    by the caller, not one row per part.

    This is the operation both callers need and the reason it lives here rather
    than in either of them. A cycleway variable wants the kilometres; the exposure
    module wants the same kilometres as a fraction of the whole line, so it can
    split a trip count between the units the trip crosses. Measuring the two
    slightly differently would be the kind of divergence nobody finds.

    The length is read straight off each fragment's geometry rather than filtering
    the fragments by type first. An intersection of a line with a polygon can come
    back as a point where the line only grazes a boundary, or as a collection of a
    line and a point; in both cases `length` already returns the length of the
    line part and nothing for the point, which is exactly the wanted answer.
    """
    projected = lines[[id_column, "geometry"]].to_crs(epsg=config.PROJECTED_CRS)
    fragments = gpd.overlay(
        projected,
        units[[config.AREA_CODE_COL, "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    fragments[FRAGMENT_LENGTH_COL] = fragments.geometry.length / 1000.0
    # A fragment of no length is a line touching a boundary at a point. It is not
    # a piece of the line inside the unit and would otherwise be counted as one
    # more unit reached.
    return fragments[fragments[FRAGMENT_LENGTH_COL] > 0].reset_index(drop=True)


def measure_line_layer(
    predictor: config.StaticPredictor,
    units: gpd.GeoDataFrame,
    log: RunLog,
) -> pd.DataFrame:
    """Length of the layer inside each unit, in kilometres.

    The line counterpart of the area measurement, and it accounts for itself the
    same way: a feature straddling a boundary contributes its own part to each
    unit it reaches, and what falls outside every unit is counted rather than
    lost. The four layers with an annual series — cycleways and the three signage
    layers — are line layers and will be measured by this.
    """
    raw = _read_source(predictor, log)
    usable, dropped = usable_lines(raw, predictor.name, log)

    lines = usable[["geometry"]].to_crs(epsg=config.PROJECTED_CRS).reset_index(drop=True)
    lines[_FEATURE_COL] = np.arange(len(lines))
    total_km = float(lines.geometry.length.sum() / 1000.0)

    fragments = split_lines_by_unit(lines, units, _FEATURE_COL)

    reached = int(fragments[_FEATURE_COL].nunique())
    outside = len(lines) - reached
    split = len(fragments) - reached
    captured_km = float(fragments[FRAGMENT_LENGTH_COL].sum())

    log.record(
        f"measure {predictor.name}",
        rows_in=len(raw),
        rows_out=len(fragments),
        changes=[
            (-dropped, "features with no usable geometry, which cannot be measured"),
            (-outside, "features falling outside every unit, contributing to no unit"),
            (split, "fragments gained where a feature crosses a unit boundary and is split between units"),
        ],
        notes=[
            f"source={predictor.source_layer}/{predictor.source_file}, {predictor.measures}",
            f"{captured_km:,.4f} km captured inside the units of {total_km:,.4f} km in the layer "
            f"({100 * captured_km / total_km:.2f}%)" if total_km > 0 else "layer has no length",
        ],
    )

    measured = fragments.groupby(config.AREA_CODE_COL)[FRAGMENT_LENGTH_COL].sum()
    return measured.rename(config.PREDICTOR_MEASURE_COL).reset_index()


# The method a variable declares is the key that selects the function which runs.
# A method described in the configuration and bound to nothing here fails at the
# variable that declares it, which is the point: the sentence in the dictionary
# and the code that produces the number are selected by one key.
MEASUREMENTS: dict[str, Callable[[config.StaticPredictor, gpd.GeoDataFrame, RunLog], pd.DataFrame]] = {
    config.AREA_SHARE_METHOD: measure_area_layer,
    config.POINT_DENSITY_METHOD: measure_point_layer,
    config.LINE_LENGTH_METHOD: measure_line_layer,
}


def measure(predictor: config.StaticPredictor, units: gpd.GeoDataFrame, log: RunLog) -> pd.DataFrame:
    """The raw magnitude of one predictor per unit, for the units it reaches."""
    try:
        measurement = MEASUREMENTS[predictor.method]
    except KeyError:
        raise ValueError(
            f"predictor {predictor.name!r} declares the method {predictor.method!r}, "
            "which is described in the configuration but bound to no function here"
        ) from None
    return measurement(predictor, units, log)


# ---------------------------------------------------------------------------
# The long table
# ---------------------------------------------------------------------------


def build_long_table(
    units: gpd.GeoDataFrame,
    log: RunLog,
    scale: config.TerritorialScale | None = None,
) -> pd.DataFrame:
    """Measure every predictor against every unit, on a complete grid.

    Thirty units by every declared variable, always. A unit the layer does not reach gets a
    zero with the status MEASURED, because the measurement ran and found nothing
    there; a unit that could not be measured at all would get NOT_MEASURED and a
    null value, and the two must never be confused. The legacy tables express
    both as an absent row.
    """
    scale = scale or config.active_scale()
    projected = prepare_units(units)
    unit_codes = projected[config.AREA_CODE_COL].tolist()

    measurements: list[pd.DataFrame] = []
    for predictor in config.STATIC_PREDICTORS:
        measured = measure(predictor, projected, log)
        measured[config.PREDICTOR_COL] = predictor.name
        measurements.append(measured)
    observed = pd.concat(measurements, ignore_index=True)

    grid = pd.DataFrame(
        itertools.product(unit_codes, config.STATIC_PREDICTOR_NAMES),
        columns=[config.AREA_CODE_COL, config.PREDICTOR_COL],
    )
    long_table = grid.merge(observed, on=[config.AREA_CODE_COL, config.PREDICTOR_COL], how="left")

    unmatched = len(observed) - len(
        observed.merge(grid, on=[config.AREA_CODE_COL, config.PREDICTOR_COL], how="inner")
    )
    if unmatched:
        raise RuntimeError(
            f"{unmatched} measured (unit, predictor) combination(s) fall outside the declared grid; "
            "the unit roster or the predictor list is incomplete"
        )

    filled = int(long_table[config.PREDICTOR_MEASURE_COL].isna().sum())
    long_table[config.PREDICTOR_MEASURE_COL] = long_table[config.PREDICTOR_MEASURE_COL].fillna(0.0).astype(float)

    # Attributes of the unit and of the variable, attached by lookup so the grid
    # above stays the only thing that decides which rows exist.
    areas = dict(zip(projected[config.AREA_CODE_COL], projected[config.AREA_UNIT_KM2_COL]))
    names = dict(zip(projected[config.AREA_CODE_COL], projected[config.AREA_NAME_COL]))
    long_table[config.AREA_NAME_COL] = long_table[config.AREA_CODE_COL].map(names)
    long_table[config.AREA_UNIT_KM2_COL] = long_table[config.AREA_CODE_COL].map(areas).astype(float)
    long_table[config.PREDICTOR_FAMILY_COL] = long_table[config.PREDICTOR_COL].map(
        {p.name: p.family for p in config.STATIC_PREDICTORS}
    )
    # Units come from the method that produced the number, so the column says what
    # the measurement actually yields rather than what a family is assumed to.
    # Mapped as a pair and split, rather than mapped twice: a dict of plain strings
    # makes pandas infer its str dtype, which writes the column to parquet as
    # large_string while every other text column of the table is string. Same
    # values either way, different file.
    units_by_predictor = long_table[config.PREDICTOR_COL].map(
        {p.name: (p.measure_unit, p.value_unit) for p in config.STATIC_PREDICTORS}
    )
    long_table[config.PREDICTOR_MEASURE_UNIT_COL] = units_by_predictor.str[0]
    long_table[config.PREDICTOR_VALUE_UNIT_COL] = units_by_predictor.str[1]

    # Both families normalise by the area of the unit; what differs is what the
    # quotient means, which is what VALUE_UNIT is for.
    denominator = long_table[config.AREA_UNIT_KM2_COL]
    unusable_denominator = ~(denominator > 0)
    long_table[config.PREDICTOR_VALUE_COL] = (
        long_table[config.PREDICTOR_MEASURE_COL] / denominator.where(denominator > 0)
    )
    long_table[config.PREDICTOR_STATUS_COL] = np.where(
        unusable_denominator, config.NOT_MEASURED_STATUS, config.MEASURED_STATUS
    )
    # A unit with no usable area has no density and no share, and must not carry
    # a zero that would read as an observation.
    long_table.loc[unusable_denominator, config.PREDICTOR_MEASURE_COL] = np.nan

    not_measured = int(unusable_denominator.sum())
    if not_measured:
        log.warn(
            "%d cell(s) could not be measured because their unit has no usable area; "
            "they carry a null value and the status %s, never a zero",
            not_measured,
            config.NOT_MEASURED_STATUS,
        )

    long_table[config.SCALE_COL] = scale.label
    # No static predictor has a year. The column exists so that the four layers
    # with an annual series join this table instead of needing one of their own.
    long_table[config.YEAR_COL] = pd.array([pd.NA] * len(long_table), dtype="Int64")

    ordered = [
        config.SCALE_COL,
        config.AREA_CODE_COL,
        config.AREA_NAME_COL,
        config.AREA_UNIT_KM2_COL,
        config.YEAR_COL,
        config.PREDICTOR_COL,
        config.PREDICTOR_FAMILY_COL,
        config.PREDICTOR_MEASURE_COL,
        config.PREDICTOR_MEASURE_UNIT_COL,
        config.PREDICTOR_VALUE_COL,
        config.PREDICTOR_VALUE_UNIT_COL,
        config.PREDICTOR_STATUS_COL,
    ]
    long_table = (
        long_table[ordered]
        .sort_values([config.AREA_CODE_COL, config.PREDICTOR_COL], kind="stable")
        .reset_index(drop=True)
    )

    log.record(
        "assemble the predictor grid",
        rows_in=len(observed),
        rows_out=len(long_table),
        changes=[
            (
                filled,
                "grid cells the layer does not reach, materialised as a measured zero "
                "rather than left absent",
            )
        ],
        notes=[
            f"grid = {len(unit_codes)} units x {len(config.STATIC_PREDICTORS)} static predictors",
            f"scale recorded as {scale.label} on every row; year null on every row, "
            "since every one of them is a single snapshot",
        ],
    )
    return long_table


def wide_table(long_table: pd.DataFrame) -> pd.DataFrame:
    """One row per unit, one column per variable — what the figures are drawn from.

    Reshaped with pivot rather than pivot_table: there is exactly one row per unit
    and predictor, so nothing needs aggregating, and an aggregating reshape would
    turn a cell that could not be measured into a confident 0.000. pivot also
    raises if the one-row assumption is ever false instead of quietly averaging.
    """
    wide = long_table.pivot(
        index=config.AREA_CODE_COL,
        columns=config.PREDICTOR_COL,
        values=config.PREDICTOR_VALUE_COL,
    ).reindex(columns=list(config.STATIC_PREDICTOR_NAMES))

    identity = (
        long_table[[config.SCALE_COL, config.AREA_CODE_COL, config.AREA_NAME_COL, config.AREA_UNIT_KM2_COL]]
        .drop_duplicates()
        .set_index(config.AREA_CODE_COL)
    )
    joined = identity.join(wide).reset_index()
    # The identifying columns lead, in the same order as in the long table, so
    # both tables read alike and the join keys are where a reader looks for them.
    ordered = [
        config.SCALE_COL,
        config.AREA_CODE_COL,
        config.AREA_NAME_COL,
        config.AREA_UNIT_KM2_COL,
        *config.STATIC_PREDICTOR_NAMES,
    ]
    return joined[ordered].sort_values(config.AREA_CODE_COL, kind="stable").reset_index(drop=True)


def correlation_matrix(wide: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation among every declared variable, in the declared order."""
    values = wide[list(config.STATIC_PREDICTOR_NAMES)]
    return values.corr(method=config.CORRELATION_METHOD)


def model_correlation_matrix(wide: pd.DataFrame) -> pd.DataFrame:
    """The same, restricted to the variables that enter the models.

    Recomputed on the subset rather than sliced out of the full matrix. The two
    give the same numbers, since a Pearson correlation between two columns does
    not depend on which other columns are present, but computing it from the
    declared model set is what makes the exported table follow the declaration
    instead of a slice someone has to keep in step with it.
    """
    values = wide[list(config.MODEL_PREDICTOR_NAMES)]
    return values.corr(method=config.CORRELATION_METHOD)


def _same_source_layer(first: str, second: str) -> bool:
    """Are these two variables two views of one source layer?"""
    declared = config.STATIC_PREDICTORS_BY_NAME
    if first not in declared or second not in declared:
        return False
    return declared[first].source_layer == declared[second].source_layer


def high_correlation_pairs(correlation: pd.DataFrame) -> pd.DataFrame:
    """Pairs whose correlation exceeds the threshold in absolute value.

    Each pair appears once: only the lower triangle is read, so a pair is not
    reported twice under two orderings, and the diagonal — which is 1 by
    construction and says nothing — is excluded.
    """
    names = list(correlation.columns)
    rows = []
    for first, second in itertools.combinations(names, 2):
        value = float(correlation.loc[first, second])
        if abs(value) >= config.CORRELATION_HIGH_THRESHOLD:
            rows.append(
                {
                    "PREDICTOR_A": first,
                    "PREDICTOR_B": second,
                    "CORRELATION": value,
                    # Two variants of one layer are two ways of counting the same
                    # objects, so a high correlation between them is arithmetic
                    # rather than a finding. Without this column the table reads
                    # as though the study had a redundancy problem it does not
                    # have, and only one of any such pair is ever in the models.
                    "SAME_SOURCE_LAYER": _same_source_layer(first, second),
                }
            )
    table = pd.DataFrame(
        rows, columns=["PREDICTOR_A", "PREDICTOR_B", "CORRELATION", "SAME_SOURCE_LAYER"]
    )
    return table.reindex(table["CORRELATION"].abs().sort_values(ascending=False).index).reset_index(drop=True)


def summary_statistics(long_table: pd.DataFrame) -> pd.DataFrame:
    """Minimum, maximum, median and the count of zeros, per variable.

    The zero count is the reason this table exists: it is what says whether a
    variable is a real gradient across the city or a handful of units above zero
    and the rest flat, which changes what a regression on it can mean.
    """
    rows = []
    for predictor in config.STATIC_PREDICTORS:
        subset = long_table[long_table[config.PREDICTOR_COL] == predictor.name]
        values = subset[config.PREDICTOR_VALUE_COL]
        measured = subset[config.PREDICTOR_STATUS_COL] == config.MEASURED_STATUS
        rows.append(
            {
                config.PREDICTOR_COL: predictor.name,
                config.PREDICTOR_FAMILY_COL: predictor.family,
                config.PREDICTOR_VALUE_UNIT_COL: predictor.value_unit,
                "UNITS_MEASURED": int(measured.sum()),
                "UNITS_NOT_MEASURED": int((~measured).sum()),
                "UNITS_AT_ZERO": int((values.fillna(-1) == 0).sum()),
                "MINIMUM": float(values.min()),
                "MEDIAN": float(values.median()),
                "MAXIMUM": float(values.max()),
                "MEAN": float(values.mean()),
                "STD_DEV": float(values.std()),
                "TOTAL_MEASURE": float(subset[config.PREDICTOR_MEASURE_COL].sum()),
                config.PREDICTOR_MEASURE_UNIT_COL: predictor.measure_unit,
            }
        )
    return pd.DataFrame(rows)


def dictionary_table() -> pd.DataFrame:
    """The declaration of every variable, as a table.

    Built from the same objects the measurement runs on, so it cannot describe a
    source the pipeline does not read or a computation it does not perform. It is
    the answer to going from a column name in English to a layer named in Spanish
    and to the file it came out of, which until now took reading the code.

    The source path is written relative to the repository root: an absolute path
    from my machine says nothing to anyone else opening the CSV.
    """
    rows = []
    for predictor in config.STATIC_PREDICTORS:
        rows.append(
            {
                config.PREDICTOR_COL: predictor.name,
                config.PREDICTOR_LABEL_COL: predictor.label,
                config.PREDICTOR_FAMILY_COL: predictor.family,
                config.SOURCE_LAYER_COL: predictor.source_layer,
                config.SOURCE_FILE_COL: predictor.source_file,
                config.SOURCE_PATH_COL: predictor.path.relative_to(config.PROJECT_ROOT).as_posix(),
                config.GEOMETRY_COL: predictor.geometry,
                config.MEASURES_COL: predictor.measures,
                config.PREDICTOR_MEASURE_UNIT_COL: predictor.measure_unit,
                config.PREDICTOR_VALUE_UNIT_COL: predictor.value_unit,
                config.COMPUTATION_COL: predictor.computation,
                config.TIME_COVERAGE_COL: predictor.time_coverage,
                config.ZERO_IMPLAUSIBLE_COL: predictor.zero_is_implausible,
                config.SOURCE_FILTER_COL: predictor.filter_description,
                config.IN_MODEL_COL: predictor.name in config.MODEL_PREDICTOR_NAMES,
                # Which sets of figures draw this variable, as a list rather than
                # a flag: there are two sets and a variable can be in either,
                # both, or neither, and "neither" is a deliberate state here.
                config.FIGURE_SETS_COL: ", ".join(
                    figure_set.name
                    for figure_set in config.FIGURE_SETS
                    if predictor.name in figure_set.predictor_names
                )
                or "none",
                # Blank for the ones that are in, so the column reads as the answer
                # to "why is this one missing from the models" and not as a field
                # every row has to fill.
                config.MODEL_EXCLUSION_REASON_COL: config.MODEL_EXCLUSION_REASONS.get(predictor.name, ""),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export(long_table: pd.DataFrame, log: RunLog) -> dict[str, Path]:
    """Write the long table, the wide table and the two derived views."""
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    # The long table is the one that joins to the matrix and to rho; the wide one
    # is the shape the figures and the correlation need. Same numbers, and the
    # prefix says which is which before anyone opens either.
    long_path = data_dir / f"{config.ANALYSIS_PREFIX}__static_predictors_long.csv"
    long_table.to_csv(long_path, index=False, encoding="utf-8")
    long_table.to_parquet(long_path.with_suffix(".parquet"))
    paths["long"] = long_path

    wide = wide_table(long_table)
    wide_path = data_dir / f"{config.ANALYSIS_PREFIX}__static_predictors_wide.csv"
    wide.to_csv(wide_path, index=False, encoding="utf-8")
    wide.to_parquet(wide_path.with_suffix(".parquet"))
    paths["wide"] = wide_path

    correlation = correlation_matrix(wide)
    correlation_path = data_dir / f"{config.PRESENTATION_PREFIX}__static_predictors_correlation.csv"
    correlation.to_csv(correlation_path, encoding="utf-8")
    paths["correlation"] = correlation_path

    # The model set gets its own correlation, as a CSV and as the LaTeX table the
    # documents include. It is a strict subset of the one above and is exported
    # separately rather than left to be sliced out by hand in the document, which
    # is how the version in the presentation was built and is the step that could
    # go wrong without anything noticing.
    model_correlation = model_correlation_matrix(wide)
    model_correlation_path = data_dir / f"{config.PRESENTATION_PREFIX}__model_correlation.csv"
    model_correlation.to_csv(model_correlation_path, encoding="utf-8")
    paths["model_correlation"] = model_correlation_path
    paths["model_correlation_tex"] = latex.export_correlation(model_correlation, log)

    pairs_path = data_dir / f"{config.PRESENTATION_PREFIX}__static_predictors_high_correlation.csv"
    high_correlation_pairs(correlation).to_csv(pairs_path, index=False, encoding="utf-8")
    paths["high_correlation"] = pairs_path

    summary_path = data_dir / f"{config.PRESENTATION_PREFIX}__static_predictors_summary.csv"
    summary_statistics(long_table).to_csv(summary_path, index=False, encoding="utf-8")
    paths["summary"] = summary_path

    # The dictionary measures nothing, so it is neither an analysis table nor a
    # view of one. It is the declaration the measurement ran on, exported so that
    # a column name in a CSV can be traced to its layer and its file without
    # opening the code.
    dictionary_path = data_dir / f"{config.REFERENCE_PREFIX}__static_predictors_dictionary.csv"
    dictionary_table().to_csv(dictionary_path, index=False, encoding="utf-8")
    paths["dictionary"] = dictionary_path

    log.info(
        "exported 2 analysis tables, 4 presentation tables, 1 LaTeX table and 1 reference table to %s/",
        config.DATA_SUBDIR,
    )
    return paths


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def histogram_edges(values: np.ndarray) -> np.ndarray:
    """Bin edges on round values, by the rule declared in the configuration.

    Degenerate ranges are handled rather than left to produce a figure with one
    infinitely narrow bar: if every unit holds the same value the histogram is a
    single bin around it.
    """
    low, high = float(np.min(values)), float(np.max(values))
    if not np.isfinite(low) or not np.isfinite(high) or low == high:
        centre = low if np.isfinite(low) else 0.0
        span = abs(centre) * 0.05 or 0.5
        return np.array([centre - span, centre + span])
    step = config.histogram_bin_step(low, high)
    return np.array(config.histogram_bin_edges(low, high, step))


def _step_decimals(step: float) -> int:
    """Decimals needed to write `step` exactly, so a tick reads 0.02 and not 0.020."""
    decimals, scaled = 0, float(step)
    while decimals < 6 and abs(scaled - round(scaled)) > 1e-9:
        scaled *= 10
        decimals += 1
    return decimals


def _draw_histogram(values: np.ndarray, predictor: config.StaticPredictor, out_path: Path) -> None:
    edges = histogram_edges(values)
    counts, _ = np.histogram(values, bins=edges)
    step = float(edges[1] - edges[0])
    decimals = _step_decimals(step)

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    widths = np.diff(edges)
    tallest = max(int(counts.max()), 1)
    ax.bar(
        edges[:-1],
        counts,
        width=widths,
        align="edge",
        color=config.HISTOGRAM_BAR_COLOR,
        edgecolor=config.HISTOGRAM_BAR_EDGE_COLOR,
        linewidth=0.8,
    )

    # An empty bin is a finding, not a gap in the figure: the units stop before
    # that range and start again after it. Drawn blank it reads as the figure
    # having failed, so it gets a hatched stub and its own zero, which say that
    # the range was measured and holds nothing.
    empty = np.flatnonzero(counts == 0)
    if len(empty):
        ax.bar(
            edges[empty],
            np.full(len(empty), tallest * config.HISTOGRAM_EMPTY_BIN_STUB_FRACTION),
            width=widths[empty],
            align="edge",
            color=config.HISTOGRAM_EMPTY_BIN_COLOR,
            edgecolor=config.HISTOGRAM_BAR_COLOR,
            linewidth=0.8,
            hatch="///",
        )

    # The count above each bar, because with thirty observations the exact number
    # of units in a bin is the whole content of the figure and reading it off a
    # short axis is guesswork. The zeros are printed where the other counts are,
    # so an empty bin is read the same way as a full one.
    for left, width, count in zip(edges[:-1], widths, counts):
        height = count if count else tallest * config.HISTOGRAM_EMPTY_BIN_STUB_FRACTION
        colour = "black" if count else config.FIGURE_TECHNICAL_LABEL_COLOR
        ax.text(left + width / 2, height, f"{int(count)}", ha="center", va="bottom", fontsize=9, color=colour)

    ax.set_xlabel(f"{predictor.label} ({predictor.value_unit})")
    ax.set_ylabel(f"{config.active_scale().label} units")
    ax.set_title(f"{predictor.name}\n{predictor.measures}", fontsize=10)
    ax.set_ylim(0, max(tallest * 1.18, 1))
    ax.set_yticks(range(0, tallest + 1, max(1, tallest // 6)))

    # The ticks are the bin edges themselves, never the ones the library would
    # pick: every bar then begins and ends on a labelled number, so what a bar
    # covers is read off the axis instead of interpolated between two labels.
    ax.set_xlim(float(edges[0]), float(edges[-1]))
    ax.set_xticks(edges, [f"{edge:.{decimals}f}" for edge in edges], fontsize=9)

    ax.grid(axis="y", color=config.RHO_GRID_COLOR, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    note = f"n = {len(values)} units | {len(edges) - 1} bins of {step:.{decimals}f} ({config.HISTOGRAM_BIN_RULE})"
    if len(empty):
        note += f" | {len(empty)} empty bin(s), hatched"
    ax.annotate(
        note,
        xy=(0.5, -0.26),
        xycoords="axes fraction",
        ha="center",
        fontsize=8,
        color="#666666",
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)


# -- axis labels shared by the correlation matrix and the master table ------
# Both carry the declared variables on an axis, and both are read beside the exported
# tables. A reader who sees only the short label has to guess which column of
# which CSV it became, so the canonical name goes underneath it: smaller, and in
# a monospaced face to mark it as a literal string rather than prose.


def _label_lines(name: str) -> tuple[str, str]:
    """The readable label and the canonical name of a predictor, in that order."""
    return config.STATIC_PREDICTORS_BY_NAME[name].label, name


def _two_line_y_labels(ax, names: list[str]) -> None:
    """Readable label with the canonical name below it, along the vertical axis."""
    ax.set_yticks(range(len(names)), [""] * len(names))
    for position, name in enumerate(names):
        readable, technical = _label_lines(name)
        ax.annotate(
            readable,
            xy=(0, position),
            xycoords=("axes fraction", "data"),
            xytext=(-8, 1),
            textcoords="offset points",
            ha="right",
            va="bottom",
            fontsize=config.FIGURE_READABLE_LABEL_SIZE,
        )
        ax.annotate(
            technical,
            xy=(0, position),
            xycoords=("axes fraction", "data"),
            xytext=(-8, -1),
            textcoords="offset points",
            ha="right",
            va="top",
            fontsize=config.FIGURE_TECHNICAL_LABEL_SIZE,
            color=config.FIGURE_TECHNICAL_LABEL_COLOR,
            family="monospace",
        )


def _two_line_x_labels(ax, names: list[str], rotation: float = 40.0, at_top: bool = False) -> None:
    """The same pair of lines along the horizontal axis, rotated to fit.

    Rotated text has to be offset perpendicular to itself for the second line to
    land parallel underneath the first; offsetting straight down would leave the
    two lines crossing at this angle.
    """
    angle = np.radians(rotation)
    below = np.array([np.sin(angle), -np.cos(angle)])  # unit vector across a rotated line
    gap = 8.5  # points between the two lines, measured across them

    ax.set_xticks(range(len(names)), [""] * len(names))
    if at_top:
        ax.xaxis.set_ticks_position("top")
    edge, base, vertical, horizontal = (
        (1.0, np.array([0.0, 6.0]), "bottom", "left")
        if at_top
        else (0.0, np.array([0.0, -6.0]), "top", "right")
    )
    # At the top the technical line sits nearest the axis, so the readable one
    # stays on the outside where the eye enters the figure.
    readable_offset = base - below * gap if at_top else base
    technical_offset = base if at_top else base + below * gap

    for position, name in enumerate(names):
        readable, technical = _label_lines(name)
        ax.annotate(
            readable,
            xy=(position, edge),
            xycoords=("data", "axes fraction"),
            xytext=tuple(readable_offset),
            textcoords="offset points",
            ha=horizontal,
            va=vertical,
            rotation=rotation,
            rotation_mode="anchor",
            fontsize=config.FIGURE_READABLE_LABEL_SIZE,
        )
        ax.annotate(
            technical,
            xy=(position, edge),
            xycoords=("data", "axes fraction"),
            xytext=tuple(technical_offset),
            textcoords="offset points",
            ha=horizontal,
            va=vertical,
            rotation=rotation,
            rotation_mode="anchor",
            fontsize=config.FIGURE_TECHNICAL_LABEL_SIZE,
            color=config.FIGURE_TECHNICAL_LABEL_COLOR,
            family="monospace",
        )


def _draw_correlation(
    correlation: pd.DataFrame, figure_set: config.FigureSet, out_path: Path
) -> None:
    values = correlation.to_numpy(dtype=float)
    names = list(correlation.columns)

    fig, ax = plt.subplots(figsize=(9.6, 8.4))
    # Centred on zero and symmetric, so that +0.4 and -0.4 are equally far from
    # the neutral colour: the sign is as much of the finding as the magnitude.
    image = ax.imshow(values, cmap=config.CORRELATION_COLORMAP, vmin=-1.0, vmax=1.0, aspect="auto")

    _two_line_x_labels(ax, names)
    _two_line_y_labels(ax, names)
    ax.set_title(
        f"Pearson correlation among {figure_set.label}: {len(names)} static predictors "
        f"({len(correlation)} x {len(correlation)}, n = {config.active_scale().expected_units} "
        f"{config.active_scale().label} units)",
        fontsize=11,
    )

    for row, col in itertools.product(range(len(names)), range(len(names))):
        value = values[row, col]
        # White on the saturated ends of the ramp, black in the pale middle.
        colour = "white" if abs(value) > 0.6 else "black"
        # Adding zero drops the sign of a small negative that rounds to nothing,
        # so the cell reads 0.00 rather than -0.00, which looks like a signed
        # quantity that is not zero. Same rule the emitted LaTeX table follows,
        # and the two are read side by side.
        printed = round(value, 2) + 0.0
        ax.text(col, row, f"{printed:.2f}", ha="center", va="center", fontsize=8, color=colour)

    bar = fig.colorbar(image, ax=ax, shrink=0.85)
    bar.set_label(f"{config.CORRELATION_METHOD} correlation coefficient")
    fig.tight_layout()
    fig.savefig(out_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)


def _draw_master_table(
    wide: pd.DataFrame, names: list[str], figure_set: config.FigureSet, out_path: Path
) -> None:
    """Every unit against every variable, printed and shaded column by column.

    The one figure that shows the predictor half whole. Its colour is computed
    inside each column, from that variable's own minimum to its own maximum,
    because a share of a unit and a density per square kilometre have nothing to
    say to each other on a shared ramp. That makes the colours comparable down a
    column and meaningless across columns, which the figure says twice: in the
    note under the title, and in the range printed at the foot of every column.
    """
    values = wide[names].to_numpy(dtype=float)
    row_count, column_count = values.shape

    shaded = np.full(values.shape, np.nan)
    column_ranges: list[tuple[float, float]] = []
    for index in range(column_count):
        column = values[:, index]
        observed = column[np.isfinite(column)]
        low, high = (float(observed.min()), float(observed.max())) if len(observed) else (np.nan, np.nan)
        column_ranges.append((low, high))
        if np.isfinite(low) and high > low:
            shaded[:, index] = (column - low) / (high - low)
        else:
            # A flat column has no high and no low; painting it at one end of the
            # ramp would invent a gradient that is not in the data.
            shaded[:, index] = np.where(np.isfinite(column), config.MASTER_TABLE_FLAT_COLUMN_POSITION, np.nan)

    colormap = plt.get_cmap(config.MASTER_TABLE_COLORMAP).copy()
    colormap.set_bad(config.HEATMAP_EMPTY_COLOR)

    fig, ax = plt.subplots(figsize=(13.0, 13.5))
    ax.imshow(np.ma.masked_invalid(shaded), cmap=colormap, vmin=0.0, vmax=1.0, aspect="auto")

    # Decimals come from the top of each column, so a column of thousandths and a
    # column of hundreds are both printed to about three significant digits.
    decimals = [config.predictor_decimals(high) for _, high in column_ranges]
    for row, column in itertools.product(range(row_count), range(column_count)):
        value = values[row, column]
        if not np.isfinite(value):
            ax.text(column, row, "-", ha="center", va="center", fontsize=7, color="#444444")
            continue
        colour = "white" if shaded[row, column] > config.MASTER_TABLE_LIGHT_TEXT_ABOVE else "black"
        ax.text(
            column,
            row,
            f"{value:.{decimals[column]}f}",
            ha="center",
            va="center",
            fontsize=7,
            color=colour,
        )

    _two_line_x_labels(ax, names, at_top=True)
    ax.set_yticks(
        range(row_count),
        [f"{code}  {name}" for code, name in zip(wide[config.AREA_CODE_COL], wide[config.AREA_NAME_COL])],
        fontsize=8,
    )

    # Separators on the cell boundaries rather than on the cell centres, so three
    # hundred numbers read as a table instead of as a field of colour.
    ax.set_xticks(np.arange(-0.5, column_count, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, row_count, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.0)
    ax.tick_params(which="minor", length=0)

    # The range each column's colour spans, printed under the column it belongs
    # to: it is what makes the per-column scale checkable rather than a claim in
    # a caption.
    for index, (low, high) in enumerate(column_ranges):
        if not np.isfinite(low):
            continue
        ax.annotate(
            f"{low:.{decimals[index]}f}\nto {high:.{decimals[index]}f}",
            xy=(index, 0),
            xycoords=("data", "axes fraction"),
            xytext=(0, -8),
            textcoords="offset points",
            ha="center",
            va="top",
            fontsize=6.5,
            color=config.FIGURE_TECHNICAL_LABEL_COLOR,
            family="monospace",
        )
    ax.annotate(
        "own colour scale\nof each column:",
        xy=(0, 0),
        xycoords="axes fraction",
        xytext=(-8, -8),
        textcoords="offset points",
        ha="right",
        va="top",
        fontsize=6.5,
        color=config.FIGURE_TECHNICAL_LABEL_COLOR,
    )

    scale = config.active_scale()
    ax.set_title(
        f"Static urban predictors, {figure_set.label}: {row_count} {scale.label} units "
        f"x {column_count} variables\n"
        "Each column is shaded on its own scale, palest at that column's minimum and darkest "
        "at its maximum.\nColours can be compared down a column and never across columns: the "
        "variables are not on one scale.",
        fontsize=10,
        pad=104,
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)


def render_figure_set(
    figure_set: config.FigureSet,
    wide: pd.DataFrame,
    correlation: pd.DataFrame,
    log: RunLog,
) -> int:
    """One histogram per variable of the set, its correlation and its master table.

    The set decides which columns are drawn and nothing else. Both sets come off
    the same two tables, so a number cannot differ between them: if it did, one of
    the two pictures would be wrong and there would be no way to tell which.
    """
    figures_dir = log.run_dir / config.FIGURES_SUBDIR / figure_set.folder
    figures_dir.mkdir(parents=True, exist_ok=True)
    names = list(figure_set.predictor_names)
    written = 0

    for predictor in figure_set.predictors:
        values = wide[predictor.name].to_numpy(dtype=float)
        usable = values[np.isfinite(values)]
        if len(usable) != len(values):
            log.warn(
                "%s: %d unit(s) have no value and are absent from the histogram",
                predictor.name,
                len(values) - len(usable),
            )
        _draw_histogram(
            usable,
            predictor,
            figures_dir / f"histogram__{predictor.name}__{figure_set.name}.png",
        )
        written += 1

    # Restricted rather than recomputed. A Pearson correlation between two columns
    # does not depend on which other columns are present, so the restriction is
    # exact, and taking both sets off one table is what makes them agree by
    # construction instead of by two calculations happening to match.
    _draw_correlation(
        correlation.reindex(index=names, columns=names),
        figure_set,
        figures_dir / f"correlation__predictors__{figure_set.name}.png",
    )
    written += 1

    _draw_master_table(wide, names, figure_set, figures_dir / f"table__predictors__{figure_set.name}.png")
    written += 1

    log.info(
        "%s set: %d figures for %d variables under %s/%s/ (%s)",
        figure_set.name,
        written,
        len(names),
        config.FIGURES_SUBDIR,
        figure_set.folder,
        figure_set.purpose,
    )
    return written


def render_figures(paths: dict[str, Path], log: RunLog) -> int:
    """Every figure of every declared set.

    Drawn from the exported tables read back from disk rather than recomputed
    from memory, as everywhere else in the pipeline: what is seen and what is
    analysed are then the same numbers by construction rather than by care.
    """
    wide = pd.read_csv(paths["wide"])
    correlation = pd.read_csv(paths["correlation"], index_col=0)

    written = sum(render_figure_set(figure_set, wide, correlation, log) for figure_set in config.FIGURE_SETS)

    excluded = ", ".join(config.FIGURE_EXCLUSION_REASONS) or "none"
    log.info(
        "wrote %d figures across %d sets; measured but drawn in no set: %s",
        written,
        len(config.FIGURE_SETS),
        excluded,
    )
    return written


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(
    long_table: pd.DataFrame,
    units: gpd.GeoDataFrame,
    log: RunLog,
    paths: dict[str, Path] | None = None,
) -> bool:
    """Check the tables against the grid they claim to be and against arithmetic.

    Given the exported paths it also checks the data dictionary against the tables
    it describes, reading both back from disk: a declaration nobody checks is a
    comment with a file extension.
    """
    wide = wide_table(long_table)
    correlation = correlation_matrix(wide)
    checks: list[tuple[str, bool, str]] = []

    expected_units = set(units[config.AREA_CODE_COL])
    present_units = set(long_table[config.AREA_CODE_COL])
    checks.append(
        (
            "every unit of the layer is in the grid",
            expected_units == present_units,
            f"{len(present_units)} of {len(expected_units)}",
        )
    )

    expected_rows = len(units) * len(config.STATIC_PREDICTORS)
    checks.append(
        (
            "grid has exactly the declared number of cells",
            len(long_table) == expected_rows,
            f"{len(long_table):,} of {expected_rows:,}",
        )
    )

    per_predictor = long_table.groupby(config.PREDICTOR_COL).size()
    complete = bool((per_predictor == len(units)).all()) and len(per_predictor) == len(config.STATIC_PREDICTORS)
    checks.append(
        (
            "every predictor covers every unit",
            complete,
            f"{len(per_predictor)} predictors, {per_predictor.min()}-{per_predictor.max()} units each",
        )
    )

    negatives = int((long_table[config.PREDICTOR_VALUE_COL] < 0).sum())
    checks.append(("no negative value", negatives == 0, f"{negatives} negative values"))

    negative_measures = int((long_table[config.PREDICTOR_MEASURE_COL] < 0).sum())
    checks.append(
        ("no negative raw magnitude", negative_measures == 0, f"{negative_measures} negative magnitudes")
    )

    # Area shares are a fraction of the unit and cannot leave [0, 1]. A share
    # above one would mean the layer covers more of the unit than the unit has,
    # which is double counting inside the layer.
    shares = long_table[long_table[config.PREDICTOR_FAMILY_COL] == config.AREA_FAMILY][config.PREDICTOR_VALUE_COL]
    out_of_range = int(((shares < 0) | (shares > 1)).sum())
    checks.append(
        (
            "area shares lie between 0 and 1",
            out_of_range == 0,
            f"{out_of_range} outside the range, maximum {shares.max():.4f}",
        )
    )

    # The value is a derived column, so it is worth checking that it is still the
    # quotient it claims to be rather than something that survived a reshape.
    recomputed = long_table[config.PREDICTOR_MEASURE_COL] / long_table[config.AREA_UNIT_KM2_COL]
    agrees = bool(np.allclose(recomputed.dropna(), long_table[config.PREDICTOR_VALUE_COL].dropna(), rtol=1e-12))
    checks.append(("every value is its magnitude over the area of its unit", agrees, "compared to 1e-12"))

    finite = int(np.isfinite(long_table[config.PREDICTOR_VALUE_COL].to_numpy(dtype=float)).sum())
    measured = int((long_table[config.PREDICTOR_STATUS_COL] == config.MEASURED_STATUS).sum())
    checks.append(
        (
            "every measured cell carries a finite value",
            finite == measured,
            f"{finite} finite, {measured} marked {config.MEASURED_STATUS}",
        )
    )

    checks.append(
        (
            "the wide table is one row per unit and one column per predictor",
            len(wide) == len(units) and set(config.STATIC_PREDICTOR_NAMES).issubset(wide.columns),
            f"{len(wide)} rows, {len(config.STATIC_PREDICTOR_NAMES)} predictor columns",
        )
    )

    correlation_values = correlation.to_numpy(dtype=float)
    within = bool(np.all(np.abs(correlation_values) <= 1 + 1e-12))
    checks.append(
        (
            "correlations lie between -1 and 1",
            within,
            f"observed range {np.nanmin(correlation_values):.4f} to {np.nanmax(correlation_values):.4f}",
        )
    )
    diagonal = np.diag(correlation_values)
    checks.append(
        (
            "the correlation diagonal is 1",
            bool(np.allclose(diagonal, 1.0)),
            f"{len(diagonal)} diagonal entries",
        )
    )
    checks.append(
        (
            "the correlation matrix is symmetric",
            bool(np.allclose(correlation_values, correlation_values.T, equal_nan=True)),
            f"{correlation.shape[0]} x {correlation.shape[1]}",
        )
    )

    # -- the declaration against what was measured --------------------------
    # Every declared source has to be on disk. Checked here as well as at read
    # time, so a run whose figures came from a cached table still says whether the
    # declaration still points at something real.
    missing = [p.name for p in config.STATIC_PREDICTORS if not p.path.exists()]
    checks.append(
        (
            "every declared source file exists on disk",
            not missing,
            f"{len(config.STATIC_PREDICTORS) - len(missing)} of {len(config.STATIC_PREDICTORS)}"
            + (f"; missing {', '.join(missing)}" if missing else ""),
        )
    )

    snapshots = {p.name for p in config.STATIC_PREDICTORS if p.time_coverage == config.SNAPSHOT_COVERAGE}
    dated = long_table[long_table[config.PREDICTOR_COL].isin(snapshots)][config.YEAR_COL].notna().sum()
    checks.append(
        (
            "variables declared as snapshots carry no year",
            int(dated) == 0,
            f"{len(snapshots)} snapshot variables, {int(dated)} rows with a year",
        )
    )

    if paths is not None:
        dictionary = pd.read_csv(paths["dictionary"])
        exported_wide = pd.read_csv(paths["wide"])
        declared = set(dictionary[config.PREDICTOR_COL])
        measured_names = set(long_table[config.PREDICTOR_COL])
        undeclared = sorted(measured_names - declared)
        orphaned = sorted(declared - measured_names)
        checks.append(
            (
                "the dictionary and the measured variables are the same set",
                not undeclared and not orphaned,
                f"{len(declared)} declared, {len(measured_names)} measured"
                + (f"; undeclared {', '.join(undeclared)}" if undeclared else "")
                + (f"; orphaned {', '.join(orphaned)}" if orphaned else ""),
            )
        )

        # The wide table is the one the dashboard and the figures read, so its
        # columns are what a reader will look up in the dictionary.
        wide_variables = [column for column in exported_wide.columns if column in declared]
        checks.append(
            (
                "the dictionary covers every column of the wide table",
                set(wide_variables) == declared and len(wide_variables) == len(declared),
                f"{len(wide_variables)} of {len(declared)} columns matched",
            )
        )

        # A dictionary that names the right variables in the wrong units would
        # still pass everything above.
        units_in_tables = (
            long_table.groupby(config.PREDICTOR_COL)[
                [config.PREDICTOR_MEASURE_UNIT_COL, config.PREDICTOR_VALUE_UNIT_COL]
            ]
            .agg(lambda column: set(column))
            .to_dict("index")
        )
        disagreeing = [
            row[config.PREDICTOR_COL]
            for _, row in dictionary.iterrows()
            if units_in_tables[row[config.PREDICTOR_COL]][config.PREDICTOR_MEASURE_UNIT_COL]
            != {row[config.PREDICTOR_MEASURE_UNIT_COL]}
            or units_in_tables[row[config.PREDICTOR_COL]][config.PREDICTOR_VALUE_UNIT_COL]
            != {row[config.PREDICTOR_VALUE_UNIT_COL]}
        ]
        checks.append(
            (
                "the dictionary and the long table agree on the units of every variable",
                not disagreeing,
                f"{len(dictionary) - len(disagreeing)} of {len(dictionary)} variables agree",
            )
        )

        # The table that becomes the LaTeX the documents print, against the same
        # numbers restricted out of the full matrix. The two are computed by
        # different routes on purpose: one from the declared model set, one by
        # slicing everything measured. A correlation between two columns does not
        # depend on which other columns are present, so they must agree, and if
        # they ever stopped agreeing a figure in a document would be quietly
        # wrong with nothing else out of place.
        exported_model = pd.read_csv(paths["model_correlation"], index_col=0)
        model_names = list(config.MODEL_PREDICTOR_NAMES)
        restricted = pd.read_csv(paths["correlation"], index_col=0).reindex(
            index=model_names, columns=model_names
        )
        aligned = list(exported_model.columns) == model_names
        largest_gap = (
            float(np.abs(exported_model.to_numpy(dtype=float) - restricted.to_numpy(dtype=float)).max())
            if aligned
            else float("nan")
        )
        checks.append(
            (
                "the model correlation matches the full one restricted to the model set",
                aligned and largest_gap < 1e-12,
                f"{len(model_names)} variables, largest difference {largest_gap:.2e}"
                if aligned
                else "the exported model correlation is not the declared model set",
            )
        )

    width = max(len(name) for name, _, _ in checks)
    lines = [f"{'check'.ljust(width)}  {'result':>8}  detail", f"{'-' * width}  {'-' * 8}  ------"]
    for name, ok, detail in checks:
        lines.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("static predictor verification:", "\n".join(lines))

    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("static predictor verification FAILED")
    return passed


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _format_value(value: float, family: str) -> str:
    """Shares get four decimals, densities two: their magnitudes differ by orders."""
    if not np.isfinite(value):
        return "-"
    return f"{value:.4f}" if family == config.AREA_FAMILY else f"{value:.2f}"


def report(long_table: pd.DataFrame, log: RunLog) -> None:
    wide = wide_table(long_table)
    correlation = correlation_matrix(wide)

    # -- what each variable is and where it comes from -----------------------
    # First in the log because everything after it is numbers, and a number whose
    # source is three files away is not evidence of anything.
    header = f"{'predictor':<33}  {'source layer':<27}  {'file':<37}  {'geom':<6}  {'value unit':<19}"
    lines = [header, "-" * len(header)]
    for predictor in config.STATIC_PREDICTORS:
        lines.append(
            f"{predictor.name:<33}  {predictor.source_layer:<27}  {predictor.source_file:<37}  "
            f"{predictor.geometry:<6}  {predictor.value_unit:<19}"
        )
    log.table(
        f"static predictor dictionary, {len(config.STATIC_PREDICTORS)} variables "
        f"(exported as {config.REFERENCE_PREFIX}__static_predictors_dictionary.csv):",
        "\n".join(lines),
    )

    lines = []
    for method in config.MEASUREMENT_METHODS.values():
        declared = [p.name for p in config.STATIC_PREDICTORS if p.method == method.name]
        lines.append(f"{method.name} ({len(declared)} variables, {method.measure_unit} -> {method.value_unit})")
        lines.append(f"    {method.computation}")
    log.table("how each magnitude is computed:", "\n".join(lines))

    # -- the table itself, all thirty rows ----------------------------------
    header = f"{'unit':<6}  {'name':<24}  {'km2':>8}"
    for predictor in config.STATIC_PREDICTORS:
        header += f"  {predictor.label[:11]:>11}"
    lines = [header, "-" * len(header)]
    for _, row in wide.iterrows():
        line = (
            f"{row[config.AREA_CODE_COL]:<6}  {str(row[config.AREA_NAME_COL])[:24]:<24}  "
            f"{row[config.AREA_UNIT_KM2_COL]:>8.2f}"
        )
        for predictor in config.STATIC_PREDICTORS:
            line += f"  {_format_value(float(row[predictor.name]), predictor.family):>11}"
        lines.append(line)
    log.table(
        f"static predictors, {len(wide)} {config.active_scale().label} units "
        f"x {len(config.STATIC_PREDICTORS)} variables "
        "(area families as a share of the unit, point families per km2):",
        "\n".join(lines),
    )

    # -- per-variable statistics --------------------------------------------
    summary = summary_statistics(long_table)
    header = (
        f"{'predictor':<33}  {'unit':<19}  {'minimum':>10}  {'median':>10}  "
        f"{'maximum':>10}  {'zeros':>6}  {'not meas.':>9}"
    )
    lines = [header, "-" * len(header)]
    for _, row in summary.iterrows():
        family = row[config.PREDICTOR_FAMILY_COL]
        lines.append(
            f"{row[config.PREDICTOR_COL]:<33}  {row[config.PREDICTOR_VALUE_UNIT_COL]:<19}  "
            f"{_format_value(row['MINIMUM'], family):>10}  {_format_value(row['MEDIAN'], family):>10}  "
            f"{_format_value(row['MAXIMUM'], family):>10}  {int(row['UNITS_AT_ZERO']):>6}  "
            f"{int(row['UNITS_NOT_MEASURED']):>9}"
        )
    log.table("static predictor statistics:", "\n".join(lines))

    # -- the zeros, and whether any of them is impossible --------------------
    lines = []
    suspicious = 0
    for predictor in config.STATIC_PREDICTORS:
        subset = long_table[long_table[config.PREDICTOR_COL] == predictor.name]
        at_zero = subset[subset[config.PREDICTOR_VALUE_COL] == 0]
        if not len(at_zero):
            continue
        codes = ", ".join(
            f"{row[config.AREA_CODE_COL]} {row[config.AREA_NAME_COL]}" for _, row in at_zero.iterrows()
        )
        marker = "IMPLAUSIBLE" if predictor.zero_is_implausible else "measured zero"
        lines.append(f"{predictor.name:<33}  {len(at_zero):>2} unit(s)  [{marker}]  {codes}")
        if predictor.zero_is_implausible:
            suspicious += len(at_zero)
    if lines:
        log.table("units measured at zero:", "\n".join(lines))
    else:
        log.info("no unit is at zero in any of the declared variables")

    if suspicious:
        # Loud on purpose. A zero in one of these variables is not a fact about
        # the city, so it points at the measurement rather than at the place.
        log.warn(
            "%d zero(s) fall in variables where zero should be impossible; "
            "this points at the measurement, not at the city, and must be resolved "
            "before the variable is used",
            suspicious,
        )

    not_measured = long_table[long_table[config.PREDICTOR_STATUS_COL] == config.NOT_MEASURED_STATUS]
    if len(not_measured):
        log.warn(
            "%d cell(s) could not be measured at all and carry no value: %s",
            len(not_measured),
            ", ".join(
                f"{row[config.AREA_CODE_COL]}/{row[config.PREDICTOR_COL]}" for _, row in not_measured.iterrows()
            ),
        )
    else:
        log.info(
            "every one of the %d cells was measured; every zero in the table is an "
            "observation of absence, not a failure to measure",
            len(long_table),
        )

    # -- the correlation matrix ---------------------------------------------
    labels = [config.STATIC_PREDICTORS_BY_NAME[name].label[:11] for name in correlation.columns]
    header = f"{'':<33}" + "".join(f"  {label:>11}" for label in labels)
    lines = [header, "-" * len(header)]
    for name in correlation.index:
        line = f"{name:<33}"
        for column in correlation.columns:
            line += f"  {correlation.loc[name, column]:>11.3f}"
        lines.append(line)
    log.table(
        f"{config.CORRELATION_METHOD} correlation among the {len(correlation)} static predictors:",
        "\n".join(lines),
    )

    # -- the pairs that matter for the model ---------------------------------
    pairs = high_correlation_pairs(correlation)
    if len(pairs):
        lines = [f"{'predictor A':<33}  {'predictor B':<33}  {'r':>7}", f"{'-' * 33}  {'-' * 33}  {'-' * 7}"]
        for _, row in pairs.iterrows():
            marker = "  (same source layer)" if row["SAME_SOURCE_LAYER"] else ""
            lines.append(
                f"{row['PREDICTOR_A']:<33}  {row['PREDICTOR_B']:<33}  "
                f"{row['CORRELATION']:>7.3f}{marker}"
            )
        lines.append("")
        lines.append(
            "These pairs measure close to the same thing across the thirty units. "
            "Putting both sides of one into the same model buys no information and "
            "makes the coefficients of each unstable."
        )
        if bool(pairs["SAME_SOURCE_LAYER"].any()):
            lines.append(
                "The pairs marked as sharing a source layer are variants of one variable, "
                "counted two ways. They are expected to agree, only one of them is ever in "
                "the model set, and they are not evidence of redundancy in the study."
            )
        log.table(
            f"pairs correlated above {config.CORRELATION_HIGH_THRESHOLD:.2f} in absolute value:",
            "\n".join(lines),
        )
    else:
        log.info(
            "no pair of predictors reaches %.2f in absolute correlation; none of them is "
            "redundant with another",
            config.CORRELATION_HIGH_THRESHOLD,
        )


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


def build(units: gpd.GeoDataFrame, log: RunLog) -> pd.DataFrame:
    long_table = build_long_table(units, log)
    log.dump(long_table, "07_static_predictors_long")
    return long_table
