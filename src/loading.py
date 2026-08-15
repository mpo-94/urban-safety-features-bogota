"""Source loading and territorial assignment.

Reads the two casualty layers and the vehicle table, assigns every casualty to a
territorial unit by spatial join, and concatenates the casualties into a single
set. Every stage reports how many records went in, how many came out, and the
named cause of each difference; the run aborts if a balance fails to close.

Run this stage on its own:

    python -m src.run_pipeline loading
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

try:  # regular package import
    from src import config
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_territorial_units(log: RunLog, scale: config.TerritorialScale | None = None) -> gpd.GeoDataFrame:
    """Load the polygons of the active scale, harmonised to the source CRS."""
    scale = scale or config.active_scale()
    units = gpd.read_file(scale.shapefile)

    missing = [c for c in (scale.code_column, scale.name_column) if c not in units.columns]
    if missing:
        raise KeyError(f"{scale.label} shapefile {scale.shapefile.name} lacks column(s) {missing}")

    units = units.rename(columns={scale.code_column: config.AREA_CODE_COL, scale.name_column: config.AREA_NAME_COL})
    units = units[[config.AREA_CODE_COL, config.AREA_NAME_COL, "geometry"]]
    units = units.to_crs(epsg=config.SOURCE_CRS)

    notes = [f"scale={scale.label}, source={scale.shapefile.name}, crs harmonised to EPSG:{config.SOURCE_CRS}"]
    if len(units) != scale.expected_units:
        # The unit roster is the denominator of every coverage figure the study
        # reports. A layer that does not carry the declared universe is a
        # different layer, not a smaller one, so the run stops instead of
        # silently rebasing every figure on whatever happens to be on disk.
        raise ValueError(
            f"{scale.label} layer {scale.shapefile.name} carries {len(units)} units, but the study "
            f"universe at this scale is declared as {scale.expected_units}. Either the layer changed "
            f"or expected_units is wrong; both are decisions, not defaults."
        )
    notes.append(f"{len(units)} units, matching the declared study universe")

    duplicated = int(units[config.AREA_CODE_COL].duplicated().sum())
    if duplicated:
        raise ValueError(f"{scale.label} layer has {duplicated} duplicated unit codes; a join would fan out")

    log.record("load territorial units", rows_in=len(units), rows_out=len(units), notes=notes)
    return units


def load_casualty_layer(path: Path, source_label: str, log: RunLog) -> gpd.GeoDataFrame:
    """Load one casualty point layer, tagging every row with its origin.

    The origin column is written here and never dropped: the legacy pipeline
    merged fatalities and injuries under an identical flag, which made the
    distinction unrecoverable downstream.
    """
    layer = gpd.read_file(path)
    layer = layer.to_crs(epsg=config.SOURCE_CRS)
    layer[config.CASUALTY_SOURCE_COL] = source_label

    invalid_geometry = int(layer.geometry.isna().sum() + layer.geometry.is_empty.sum())
    notes = [f"source={path.name}, one row per affected person, origin tagged {source_label}"]
    if invalid_geometry:
        log.warn("%s: %d rows have no usable geometry and cannot be located", path.name, invalid_geometry)
        notes.append(f"{invalid_geometry} rows without usable geometry")

    log.record(f"load casualties [{source_label}]", rows_in=len(layer), rows_out=len(layer), notes=notes)
    return layer


def assign_territorial_unit(
    points: gpd.GeoDataFrame,
    units: gpd.GeoDataFrame,
    log: RunLog,
    stage: str,
) -> gpd.GeoDataFrame:
    """Attach the code and name of the unit that contains each point.

    Points falling outside every unit keep a null code: they are reported, not
    dropped, and not snapped anywhere unless the nearest fallback is enabled.
    """
    rows_in = len(points)
    joined = gpd.sjoin(points, units, how="left", predicate=config.SPATIAL_JOIN_PREDICATE)
    joined = joined.drop(columns="index_right", errors="ignore")

    changes: list[tuple[int, str]] = []
    ambiguous = int(joined.index.duplicated().sum())
    if ambiguous:
        # Only possible where unit polygons overlap. Reported and resolved
        # deterministically rather than left to row order.
        log.warn("%s: %d point(s) fall inside more than one unit; keeping the lowest unit code", stage, ambiguous)
        changes.append((ambiguous, "points matching more than one unit (overlapping polygons)"))
        joined = joined.sort_values(config.AREA_CODE_COL, kind="stable")
        joined = joined[~joined.index.duplicated(keep="first")].sort_index()
        changes.append((-ambiguous, "ambiguous matches resolved to the lowest unit code"))

    unassigned = int(joined[config.AREA_CODE_COL].isna().sum())

    if config.USE_NEAREST_FALLBACK and unassigned:
        # Distance is only meaningful in the projected CRS, so the fallback runs
        # there and the threshold is genuinely metres.
        pending = points.loc[joined[config.AREA_CODE_COL].isna()].to_crs(epsg=config.PROJECTED_CRS)
        nearest = gpd.sjoin_nearest(
            pending,
            units.to_crs(epsg=config.PROJECTED_CRS),
            how="left",
            max_distance=config.NEAREST_FALLBACK_MAX_DISTANCE_M,
        ).drop(columns="index_right", errors="ignore")
        nearest = nearest[~nearest.index.duplicated(keep="first")]
        for column in (config.AREA_CODE_COL, config.AREA_NAME_COL):
            joined.loc[nearest.index, column] = nearest[column]
        recovered = unassigned - int(joined[config.AREA_CODE_COL].isna().sum())
        log.info(
            "%s: nearest fallback within %.1f m recovered %d of %d unassigned points",
            stage,
            config.NEAREST_FALLBACK_MAX_DISTANCE_M,
            recovered,
            unassigned,
        )
        unassigned -= recovered

    notes = [
        f"predicate={config.SPATIAL_JOIN_PREDICATE}, nearest fallback="
        f"{'on' if config.USE_NEAREST_FALLBACK else 'off'}",
    ]
    if unassigned:
        log.warn("%s: %d point(s) fall outside every unit and stay unassigned", stage, unassigned)
        notes.append(f"{unassigned} rows kept with a null territorial unit (outside every polygon)")

    log.record(stage, rows_in=rows_in, rows_out=len(joined), changes=changes, notes=notes)
    return joined


def load_casualties(
    log: RunLog,
    scale: config.TerritorialScale | None = None,
    units: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    """Load both casualty layers, locate them, and concatenate them.

    Returns one row per affected person, carrying its severity origin and its
    territorial unit. Pass `units` when the caller has already loaded the layer,
    so a run reads the same shapefile once instead of once per caller.
    """
    units = load_territorial_units(log, scale) if units is None else units

    fatalities = load_casualty_layer(config.FATALITIES_PATH, config.FATALITY_SOURCE, log)
    fatalities = assign_territorial_unit(fatalities, units, log, "assign unit [FATALITY]")
    log.dump(fatalities, "01_fatalities_located")

    injuries = load_casualty_layer(config.INJURIES_PATH, config.INJURY_SOURCE, log)
    injuries = assign_territorial_unit(injuries, units, log, "assign unit [INJURY]")
    log.dump(injuries, "02_injuries_located")

    # The two layers differ in schema: MUERTE_POS and FECHA_POST only exist for
    # fatalities, so injury rows get nulls there. ignore_index gives the combined
    # set a single continuous index instead of two overlapping ones.
    casualties = pd.concat([fatalities, injuries], ignore_index=True)
    casualties = gpd.GeoDataFrame(casualties, geometry="geometry", crs=fatalities.crs)

    fatality_only_columns = sorted(set(fatalities.columns) - set(injuries.columns))
    log.record(
        "concatenate casualties",
        rows_in=len(fatalities),
        rows_out=len(casualties),
        changes=[(len(injuries), f"injury rows appended to fatality rows [{config.INJURY_SOURCE}]")],
        notes=[
            f"columns present only in fatalities, null for injuries: {fatality_only_columns}",
            f"severity origin preserved in {config.CASUALTY_SOURCE_COL}",
        ],
    )

    observed = casualties["ANO_OCURRE"].dropna().astype(int)
    if len(observed):
        outside = int(((observed < config.FIRST_YEAR) | (observed > config.LAST_YEAR)).sum())
        log.info(
            "casualty years span %d-%d; study period is %d-%d; %d row(s) outside it",
            observed.min(),
            observed.max(),
            config.FIRST_YEAR,
            config.LAST_YEAR,
            outside,
        )

    log.dump(casualties, "03_casualties")
    return casualties


def load_vehicles(log: RunLog) -> pd.DataFrame:
    """Load the party table: every vehicle of every crash, casualty or not.

    low_memory=False makes pandas infer each column from the whole file instead
    of chunk by chunk, which avoids the mixed-dtype warning without altering any
    value.
    """
    vehicles = pd.read_csv(config.VEHICLES_PATH, low_memory=False)

    notes = [f"source={config.VEHICLES_PATH.name}, one row per party (including parties without casualties)"]

    duplicated_keys = int(vehicles.duplicated(subset=[config.CRASH_ID_COL, config.VEHICLE_ID_COL]).sum())
    if duplicated_keys:
        log.warn(
            "vehicle table has %d duplicated (%s, %s) keys; a merge on them would fan out",
            duplicated_keys,
            config.CRASH_ID_COL,
            config.VEHICLE_ID_COL,
        )
        notes.append(f"{duplicated_keys} duplicated join keys")

    # Check the mapping covers the source now, at read time, rather than
    # discovering an unmapped value after a groupby has already dropped it.
    # Both sides are compared on normalized text, so a typing variation in the
    # source does not read as a missing category.
    raw_types = sorted(vehicles["CLASE"].dropna().unique())
    unmapped = [raw for raw in raw_types if config.normalize_vehicle_type(raw) not in config.VEHICLE_TYPE_MAP]
    if unmapped:
        affected = int(vehicles["CLASE"].isin(unmapped).sum())
        log.warn(
            "vehicle types absent from VEHICLE_TYPE_MAP will fall back to %s: %s (%d rows)",
            config.VEHICLE_TYPE_FALLBACK,
            unmapped,
            affected,
        )
        notes.append(f"{len(unmapped)} unmapped vehicle type(s) affecting {affected} rows: {unmapped}")
    else:
        notes.append(f"all {len(raw_types)} raw vehicle types are covered by VEHICLE_TYPE_MAP")

    # Raw values that only match once normalized are the ones the legacy
    # character-for-character lookup would have dropped.
    rescued = [raw for raw in raw_types if raw != config.normalize_vehicle_type(raw)]
    if rescued:
        affected = int(vehicles["CLASE"].isin(rescued).sum())
        log.info(
            "%d raw vehicle type(s) match only after normalization, covering %d rows: %s",
            len(rescued),
            affected,
            rescued,
        )
        notes.append(f"{len(rescued)} raw type(s) matched only after normalization, affecting {affected} rows")

    null_types = int(vehicles["CLASE"].isna().sum())
    if null_types:
        notes.append(f"{null_types} rows have a null CLASE in the source")

    log.record("load vehicles", rows_in=len(vehicles), rows_out=len(vehicles), notes=notes)
    log.dump(vehicles, "04_vehicles")
    return vehicles


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def loading_counts(casualties: pd.DataFrame, vehicles: pd.DataFrame) -> dict[str, int]:
    """The six figures that characterise the loading stage."""
    source = casualties[config.CASUALTY_SOURCE_COL]
    no_area = casualties[config.AREA_CODE_COL].isna()
    return {
        "fatalities": int((source == config.FATALITY_SOURCE).sum()),
        "injuries": int((source == config.INJURY_SOURCE).sum()),
        "concatenated": len(casualties),
        "fatalities_without_area": int((no_area & (source == config.FATALITY_SOURCE)).sum()),
        "injuries_without_area": int((no_area & (source == config.INJURY_SOURCE)).sum()),
        "vehicles": len(vehicles),
    }


def verify_loading(
    casualties: pd.DataFrame,
    vehicles: pd.DataFrame,
    log: RunLog,
    scale: config.TerritorialScale | None = None,
) -> tuple[bool, str]:
    """Check the loading stage against the baseline that applies to it.

    Two kinds of check, from two different sources, reported side by side:

    * Four of the six counts are properties of the source files and no
      territorial layer can move them. They are checked against the legacy run at
      any scale, and reproducing them is what says loading changed none of the
      inherited logic.
    * The other two count records falling outside every polygon, so they depend
      on the footprint of the layer. Layers covering different territory
      necessarily disagree on them. At locality scale they are the historical
      contrast against the legacy pipeline; at any other scale they are checked
      against the baseline measured for that scale, and reported as a first
      measurement — not a failure — if none is declared yet.

    A mismatch is reported as a failure; it is never reconciled by adjusting the
    computation.
    """
    scale = scale or config.active_scale()
    observed = loading_counts(casualties, vehicles)

    at_legacy_scale = scale.key == config.LEGACY_BASELINE_SCALE
    scale_baseline = config.SCALE_BASELINE_COUNTS.get(scale.key, {})

    # (expected, where the expectation comes from) per check. None means nothing
    # to compare against yet.
    expectations: dict[str, tuple[int | None, str]] = {}
    for key in config.SCALE_INDEPENDENT_CHECKS:
        expectations[key] = (config.LEGACY_BASELINE_COUNTS[key], "legacy, scale-independent")
    for key in config.SCALE_DEPENDENT_CHECKS:
        if at_legacy_scale:
            expectations[key] = (config.LEGACY_BASELINE_COUNTS[key], f"legacy, {scale.label} footprint")
        elif key in scale_baseline:
            expectations[key] = (scale_baseline[key], f"{scale.label} baseline")
        else:
            expectations[key] = (None, f"no {scale.label} baseline declared")

    # Reported in the order of the baseline table so two runs read alike.
    ordered = [key for key in config.LEGACY_BASELINE_COUNTS if key in expectations]

    width = max(len(key) for key in ordered)
    origin_width = max(len(origin) for _, origin in expectations.values())
    lines = [
        f"{'check'.ljust(width)}  {'expected':>12}  {'observed':>12}  {'baseline'.ljust(origin_width)}  result",
        f"{'-' * width}  {'-' * 12}  {'-' * 12}  {'-' * origin_width}  ------",
    ]
    all_ok = True
    unmeasured: list[str] = []
    for key in ordered:
        expected, origin = expectations[key]
        got = observed[key]
        if expected is None:
            unmeasured.append(f"{key}={got:,}")
            result, shown = "FIRST MEASUREMENT", "-"
        else:
            ok = got == expected
            all_ok &= ok
            result, shown = ("OK" if ok else "MISMATCH"), f"{expected:,}"
        lines.append(
            f"{key.ljust(width)}  {shown:>12}  {got:>12,}  {origin.ljust(origin_width)}  {result}"
        )

    report = "\n".join(lines)
    log.table(f"loading verification at {scale.label} scale:", report)

    if unmeasured:
        log.warn(
            "no footprint baseline declared for %s; measured %s. Record them in "
            "SCALE_BASELINE_COUNTS so the next run is checked against them",
            scale.label,
            ", ".join(unmeasured),
        )
    if all_ok:
        log.info(
            "verification passed: %d count(s) match their baseline%s",
            len(ordered) - len(unmeasured),
            f", {len(unmeasured)} measured for the first time" if unmeasured else "",
        )
    else:
        log.warn("verification FAILED: the loading stage diverges from its baseline")
    return all_ok, report
