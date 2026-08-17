"""Static urban predictors measured against every territorial unit.

The other half of the study. The casualty matrix says how much harm happened
where; these variables say what the place is like. Ten of them are implemented
here, all single snapshots with no year: five surfaces measured as a share of the
unit, and five point layers measured as a density over it.

The four layers that carry an annual series — cycleways and the three signage
layers — are not here yet. Nothing in this module is shaped around the absence of
a time dimension: the long table carries a YEAR column already, null for a
snapshot, and a series slots into it without a schema change.

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

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")  # figures are written to disk, never displayed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:  # regular package import
    from src import config
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# Working columns, private to the measurement. They never reach an exported
# table, so they are named apart from the configured ones to make that obvious.
_FEATURE_COL = "_FEATURE"
_FRAGMENT_AREA_COL = "_FRAGMENT_AREA_KM2"


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
    raw = gpd.read_file(predictor.path)
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
            f"source={predictor.path.name}, {predictor.measures}",
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
    raw = gpd.read_file(predictor.path)
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
            f"source={predictor.path.name}, {predictor.measures}",
            f"{len(joined):,} of {len(points):,} points fall inside a unit "
            f"({100 * len(joined) / len(points):.2f}%)" if len(points) else "layer has no points",
        ],
    )

    measured = joined.groupby(config.AREA_CODE_COL).size()
    return measured.rename(config.PREDICTOR_MEASURE_COL).reset_index()


def measure(predictor: config.StaticPredictor, units: gpd.GeoDataFrame, log: RunLog) -> pd.DataFrame:
    """The raw magnitude of one predictor per unit, for the units it reaches."""
    if predictor.family == config.AREA_FAMILY:
        return measure_area_layer(predictor, units, log)
    if predictor.family == config.POINT_FAMILY:
        return measure_point_layer(predictor, units, log)
    raise ValueError(f"predictor {predictor.name!r} has unknown family {predictor.family!r}")


# ---------------------------------------------------------------------------
# The long table
# ---------------------------------------------------------------------------


def build_long_table(
    units: gpd.GeoDataFrame,
    log: RunLog,
    scale: config.TerritorialScale | None = None,
) -> pd.DataFrame:
    """Measure every predictor against every unit, on a complete grid.

    Thirty units by ten variables, always. A unit the layer does not reach gets a
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
    units_by_family = long_table[config.PREDICTOR_FAMILY_COL].map(config.FAMILY_UNITS)
    long_table[config.PREDICTOR_MEASURE_UNIT_COL] = units_by_family.str[0]
    long_table[config.PREDICTOR_VALUE_UNIT_COL] = units_by_family.str[1]

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
            "since all ten are single snapshots",
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
    """Pearson correlation among the ten variables, in the declared order."""
    values = wide[list(config.STATIC_PREDICTOR_NAMES)]
    return values.corr(method=config.CORRELATION_METHOD)


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
            rows.append({"PREDICTOR_A": first, "PREDICTOR_B": second, "CORRELATION": value})
    table = pd.DataFrame(rows, columns=["PREDICTOR_A", "PREDICTOR_B", "CORRELATION"])
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
                config.PREDICTOR_VALUE_UNIT_COL: config.predictor_units(predictor.family)[1],
                "UNITS_MEASURED": int(measured.sum()),
                "UNITS_NOT_MEASURED": int((~measured).sum()),
                "UNITS_AT_ZERO": int((values.fillna(-1) == 0).sum()),
                "MINIMUM": float(values.min()),
                "MEDIAN": float(values.median()),
                "MAXIMUM": float(values.max()),
                "MEAN": float(values.mean()),
                "STD_DEV": float(values.std()),
                "TOTAL_MEASURE": float(subset[config.PREDICTOR_MEASURE_COL].sum()),
                config.PREDICTOR_MEASURE_UNIT_COL: config.predictor_units(predictor.family)[0],
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

    pairs_path = data_dir / f"{config.PRESENTATION_PREFIX}__static_predictors_high_correlation.csv"
    high_correlation_pairs(correlation).to_csv(pairs_path, index=False, encoding="utf-8")
    paths["high_correlation"] = pairs_path

    summary_path = data_dir / f"{config.PRESENTATION_PREFIX}__static_predictors_summary.csv"
    summary_statistics(long_table).to_csv(summary_path, index=False, encoding="utf-8")
    paths["summary"] = summary_path

    log.info("exported 2 analysis tables and 3 presentation tables to %s/", config.DATA_SUBDIR)
    return paths


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def histogram_edges(values: np.ndarray) -> np.ndarray:
    """Equal-width bin edges over the observed range, by the declared rule.

    Degenerate ranges are handled rather than left to produce a figure with one
    infinitely narrow bar: if every unit holds the same value the histogram is a
    single bin around it.
    """
    low, high = float(np.min(values)), float(np.max(values))
    if not np.isfinite(low) or not np.isfinite(high) or low == high:
        centre = low if np.isfinite(low) else 0.0
        span = abs(centre) * 0.05 or 0.5
        return np.array([centre - span, centre + span])
    return np.linspace(low, high, config.histogram_bin_count(len(values)) + 1)


def _draw_histogram(values: np.ndarray, predictor: config.StaticPredictor, out_path: Path) -> None:
    edges = histogram_edges(values)
    counts, _ = np.histogram(values, bins=edges)

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.bar(
        edges[:-1],
        counts,
        width=np.diff(edges),
        align="edge",
        color=config.HISTOGRAM_BAR_COLOR,
        edgecolor=config.HISTOGRAM_BAR_EDGE_COLOR,
        linewidth=0.8,
    )

    # The count above each bar, because with thirty observations the exact number
    # of units in a bin is the whole content of the figure and reading it off a
    # short axis is guesswork.
    for left, width, count in zip(edges[:-1], np.diff(edges), counts):
        if count:
            ax.text(left + width / 2, count, f"{int(count)}", ha="center", va="bottom", fontsize=9)

    _, value_unit = config.predictor_units(predictor.family)
    ax.set_xlabel(f"{predictor.label} ({value_unit})")
    ax.set_ylabel(f"{config.active_scale().label} units")
    ax.set_title(f"{predictor.name}\n{predictor.measures}", fontsize=10)
    ax.set_ylim(0, max(counts.max() * 1.18, 1))
    ax.set_yticks(range(0, int(counts.max()) + 1, max(1, int(counts.max()) // 6)))
    ax.grid(axis="y", color=config.RHO_GRID_COLOR, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    ax.annotate(
        f"n = {len(values)} units | {len(edges) - 1} equal-width bins ({config.HISTOGRAM_BIN_RULE})",
        xy=(0.5, -0.22),
        xycoords="axes fraction",
        ha="center",
        fontsize=8,
        color="#666666",
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)


def _draw_correlation(correlation: pd.DataFrame, out_path: Path) -> None:
    values = correlation.to_numpy(dtype=float)
    labels = [config.STATIC_PREDICTORS_BY_NAME[name].label for name in correlation.columns]

    fig, ax = plt.subplots(figsize=(9.0, 7.6))
    # Centred on zero and symmetric, so that +0.4 and -0.4 are equally far from
    # the neutral colour: the sign is as much of the finding as the magnitude.
    image = ax.imshow(values, cmap=config.CORRELATION_COLORMAP, vmin=-1.0, vmax=1.0, aspect="auto")

    ax.set_xticks(range(len(labels)), labels, rotation=40, ha="right", fontsize=9)
    ax.set_yticks(range(len(labels)), labels, fontsize=9)
    ax.set_title(
        f"Pearson correlation among the {len(labels)} static predictors "
        f"({len(correlation)} x {len(correlation)}, n = {config.active_scale().expected_units} "
        f"{config.active_scale().label} units)",
        fontsize=11,
    )

    for row, col in itertools.product(range(len(labels)), range(len(labels))):
        value = values[row, col]
        # White on the saturated ends of the ramp, black in the pale middle.
        colour = "white" if abs(value) > 0.6 else "black"
        ax.text(col, row, f"{value:.2f}", ha="center", va="center", fontsize=8, color=colour)

    bar = fig.colorbar(image, ax=ax, shrink=0.85)
    bar.set_label(f"{config.CORRELATION_METHOD} correlation coefficient")
    fig.tight_layout()
    fig.savefig(out_path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def render_figures(paths: dict[str, Path], log: RunLog) -> int:
    """Ten histograms and one correlation heatmap, drawn from the exported tables.

    Read back from disk rather than recomputed from memory, as everywhere else in
    the pipeline: what is seen and what is analysed are then the same numbers by
    construction rather than by care.
    """
    figures_dir = log.run_dir / config.FIGURES_SUBDIR / config.PREDICTORS_FIGURES_SUBDIR
    figures_dir.mkdir(parents=True, exist_ok=True)

    wide = pd.read_csv(paths["wide"])
    written = 0
    for predictor in config.STATIC_PREDICTORS:
        values = wide[predictor.name].to_numpy(dtype=float)
        usable = values[np.isfinite(values)]
        if len(usable) != len(values):
            log.warn(
                "%s: %d unit(s) have no value and are absent from the histogram",
                predictor.name,
                len(values) - len(usable),
            )
        _draw_histogram(usable, predictor, figures_dir / f"histogram__{predictor.name}.png")
        written += 1

    correlation = pd.read_csv(paths["correlation"], index_col=0)
    correlation = correlation.reindex(
        index=list(config.STATIC_PREDICTOR_NAMES), columns=list(config.STATIC_PREDICTOR_NAMES)
    )
    _draw_correlation(correlation, figures_dir / "correlation__static_predictors.png")
    written += 1

    log.info(
        "wrote %d figures under %s/%s/",
        written,
        config.FIGURES_SUBDIR,
        config.PREDICTORS_FIGURES_SUBDIR,
    )
    return written


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(long_table: pd.DataFrame, units: gpd.GeoDataFrame, log: RunLog) -> bool:
    """Check the tables against the grid they claim to be and against arithmetic."""
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
        log.info("no unit is at zero in any of the ten variables")

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
            lines.append(f"{row['PREDICTOR_A']:<33}  {row['PREDICTOR_B']:<33}  {row['CORRELATION']:>7.3f}")
        lines.append("")
        lines.append(
            "These pairs measure close to the same thing across the thirty units. "
            "Putting both sides of one into the same model buys no information and "
            "makes the coefficients of each unstable."
        )
        log.table(
            f"pairs correlated above {config.CORRELATION_HIGH_THRESHOLD:.2f} in absolute value:",
            "\n".join(lines),
        )
    else:
        log.info(
            "no pair of predictors reaches %.2f in absolute correlation; none of the ten is "
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
