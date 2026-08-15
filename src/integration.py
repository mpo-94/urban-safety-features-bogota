"""Rebuild the casualty layers with 2024 taken from the updated extract.

A later extract of 2024 arrived. The original injury layer stops in mid-September
of that year, so the 2024 the pipeline had was two thirds of a year presented as
a whole one. The criterion, which will apply again the next time an update
arrives, is that where two extracts describe the same record the more recent one
prevails (D19).

This route rewrites both casualty layers with every 2024 row replaced, writing
the result to data/integrated/ and leaving the sources on disk untouched. What
the pipeline reads is decided by one switch in the configuration.

The incoming file is a CSV holding both severities together, with geometry as
text and identifiers typed differently from the shapefiles. Each of those is a
way to lose records silently, so each is converted explicitly and then checked:
the run stops if a dtype does not match the layer it is joining, if the person
identifiers stop matching the previous extract, or if the vehicle reference stops
resolving.

Run it:

    python -m src.run_pipeline integrate
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely import wkt

try:  # regular package import
    from src import config
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


def _as_text_key(values: pd.Series) -> pd.Series:
    """Render an identifier as the shapefiles store it: text, no trailing '.0'.

    The incoming file reads CODIGO_ACC as int64 and the shapefiles hold it as
    text. Comparing the two without this returns no matches at all, and a merge
    on them silently produces nothing rather than failing — which is exactly what
    happened while inspecting the file, and the reason every key here is
    converted through one function and verified afterwards.
    """
    text = values.astype("string")
    return text.str.replace(r"\.0$", "", regex=True).str.strip()


def _align_to_layer(incoming: pd.DataFrame, layer: gpd.GeoDataFrame, log: RunLog, label: str) -> gpd.GeoDataFrame:
    """Give the incoming rows exactly the schema of the layer they will join.

    The layer defines the columns and their types; anything the incoming file
    carries beyond them is dropped rather than appended, because a column that
    exists for one year of eighteen invites being read as if it existed for all
    of them.
    """
    aligned = pd.DataFrame(index=incoming.index)
    for column in layer.columns:
        if column == "geometry":
            continue
        target = layer[column].dtype
        source = incoming[column]
        if pd.api.types.is_datetime64_any_dtype(target):
            # The incoming file writes ISO instants with a Z; the layers hold
            # naive timestamps. Converted through UTC so the parse is
            # unambiguous, then stripped of the zone to match.
            converted = pd.to_datetime(source, errors="coerce", utc=True).dt.tz_localize(None)
        elif pd.api.types.is_string_dtype(target) or target == object:
            converted = _as_text_key(source)
        else:
            converted = source

        # The layer decides the type, down to the resolution of a timestamp and
        # the flavour of a string dtype. Anything left over is a mismatch the
        # check below turns into a stopped run rather than a silent no-match.
        aligned[column] = converted.astype(target)

    mismatched = {
        column: (str(aligned[column].dtype), str(layer[column].dtype))
        for column in aligned.columns
        if aligned[column].dtype != layer[column].dtype
    }
    if mismatched:
        raise TypeError(
            f"{label}: columns whose type does not match the layer they join: {mismatched}. "
            "A mismatched key does not raise on merge, it silently matches nothing."
        )

    geometry = gpd.GeoSeries(
        incoming[config.INCOMING_GEOMETRY_COL].map(wkt.loads).values, crs=config.INCOMING_CRS
    ).to_crs(layer.crs)
    aligned = gpd.GeoDataFrame(aligned, geometry=geometry.values, crs=layer.crs)

    dropped = sorted(set(incoming.columns) - set(layer.columns) - {config.INCOMING_GEOMETRY_COL})
    log.info("%s: dropped %d column(s) absent from the layer: %s", label, len(dropped), dropped)
    return aligned[list(layer.columns)]


def _account_for_people(
    aligned: gpd.GeoDataFrame,
    previous: gpd.GeoDataFrame,
    incoming_people: set[str],
    previous_people: set[str],
    log: RunLog,
    label: str,
) -> list[str]:
    """Say what happened to every person of the replaced year, one cause each.

    Four things can happen to a person when the extract changes, and lumping them
    together would hide the only one that is a real loss:

    * they stay in this layer;
    * they are gone from the updated extract altogether — the accepted loss;
    * they are still there but under the other severity, which is what someone
      injured who later died looks like;
    * they arrive, either new to the study or moved in from the other layer.

    The overlap doubles as the check on the identifier conversion: a silent cast
    failure looks exactly like a clean replacement of an unrelated set of people,
    so an empty overlap stops the run.
    """
    was_here = set(previous[config.PERSON_ID_COL])
    is_here = set(aligned[config.PERSON_ID_COL])

    stayed = was_here & is_here
    if was_here and not stayed:
        raise ValueError(
            f"{label}: none of the {len(aligned):,} incoming people match the "
            f"{len(previous):,} of the previous extract. The identifier conversion is wrong."
        )

    left = was_here - is_here
    gone = left - incoming_people
    changed_severity = left & incoming_people
    arrived = is_here - was_here
    from_other_layer = arrived & previous_people
    brand_new = arrived - previous_people

    log.info(
        "%s: of %d people of %d in the previous extract, %d stay, %d are gone, %d moved severity",
        label,
        len(was_here),
        config.REPLACED_YEAR,
        len(stayed),
        len(gone),
        len(changed_severity),
    )
    return [
        f"{len(gone)} person(s) are absent from the updated extract altogether and leave with it; "
        f"accepted, not recovered (D19)",
        f"{len(changed_severity)} person(s) are still in the updated extract but under the other "
        f"severity, which is what an injured person who later died looks like",
        f"{len(brand_new)} person(s) are new to the study, {len(from_other_layer)} arrived from the "
        f"other layer",
    ]


def _check_vehicle_reference(incoming: pd.DataFrame, log: RunLog) -> None:
    """The vehicle reference must resolve against the vehicle table as it did before.

    The actor type of a casualty comes from the vehicle it rode, so a reference
    that stops resolving would not lose a single row: it would quietly retype
    every 2024 casualty as a party of its own. Compared against the same rate on
    the year before, which the update does not touch.
    """
    vehicles = pd.read_csv(config.VEHICLES_PATH, low_memory=False)
    keys = set(
        zip(
            vehicles[config.CRASH_ID_COL].astype("string"),
            pd.to_numeric(vehicles[config.VEHICLE_ID_COL], errors="coerce"),
        )
    )

    def rate(frame: pd.DataFrame) -> tuple[int, int]:
        referencing = frame[frame[config.VEHICLE_ID_COL_IN_CASUALTIES].notna()]
        pairs = zip(
            referencing[config.CRASH_ID_COL].astype("string"),
            pd.to_numeric(referencing[config.VEHICLE_ID_COL_IN_CASUALTIES], errors="coerce"),
        )
        return sum(pair in keys for pair in pairs), len(referencing)

    resolved, referencing = rate(incoming)
    previous_year = gpd.read_file(config.RAW_INJURIES_PATH)
    previous_year = previous_year[previous_year[config.YEAR_SOURCE_COL] == config.REPLACED_YEAR - 1]
    before_resolved, before_referencing = rate(previous_year)

    share = resolved / referencing if referencing else 0.0
    share_before = before_resolved / before_referencing if before_referencing else 0.0
    log.info(
        "vehicle reference resolves for %d of %d incoming casualties (%.2f%%); "
        "on %d it was %.2f%%",
        resolved,
        referencing,
        100 * share,
        config.REPLACED_YEAR - 1,
        100 * share_before,
    )
    # Half the previous rate is far outside anything the data varies by; it is
    # the signature of a broken key, not of a worse year.
    if share < 0.5 * share_before:
        raise ValueError(
            f"the vehicle reference resolves for {100 * share:.2f}% of the incoming casualties "
            f"against {100 * share_before:.2f}% the year before; the key conversion is wrong"
        )


def _report_newly_unlocated(
    aligned: gpd.GeoDataFrame, previous: gpd.GeoDataFrame, log: RunLog
) -> list[str]:
    """How many records fall outside every unit, and how many did not before.

    The updated extract moves some points, which is accepted (D19). This says how
    much of the unlocated set is a consequence of that move rather than of the
    data being new, so the figure is not read as a regression of the pipeline.
    """
    units = gpd.read_file(config.active_scale().shapefile).to_crs(epsg=config.SOURCE_CRS)
    code = config.active_scale().code_column

    def unit_of(frame: gpd.GeoDataFrame) -> pd.Series:
        points = gpd.GeoDataFrame(geometry=frame.geometry.to_crs(epsg=config.SOURCE_CRS))
        joined = gpd.sjoin(points, units[[code, "geometry"]], how="left", predicate="within")
        joined = joined[~joined.index.duplicated(keep="first")]
        return joined[code]

    now = unit_of(aligned)
    now.index = aligned[config.PERSON_ID_COL].values
    before = unit_of(previous)
    before.index = previous[config.PERSON_ID_COL].values

    shared = now.index.intersection(before.index)
    newly = int((before.loc[shared].notna() & now.loc[shared].isna()).sum())
    recovered = int((before.loc[shared].isna() & now.loc[shared].notna()).sum())
    outside = int(now.isna().sum())

    return [
        f"{outside} of the {len(aligned):,} incoming rows fall outside every "
        f"{config.active_scale().label}",
        f"of those, {newly} were located under the previous extract and are not under this one, "
        f"which is the moved geometry showing up; {recovered} went the other way",
    ]


def build_layer(
    incoming: pd.DataFrame,
    layer: gpd.GeoDataFrame,
    label: str,
    incoming_people: set[str],
    previous_people: set[str],
    log: RunLog,
) -> gpd.GeoDataFrame:
    """One casualty layer with its replaced year swapped for the updated extract."""
    aligned = _align_to_layer(incoming, layer, log, label)
    previous = layer[layer[config.YEAR_SOURCE_COL] == config.REPLACED_YEAR]
    kept = layer[layer[config.YEAR_SOURCE_COL] != config.REPLACED_YEAR]

    notes = _account_for_people(aligned, previous, incoming_people, previous_people, log, label)

    rebuilt = pd.concat([kept, aligned], ignore_index=True)
    rebuilt = gpd.GeoDataFrame(rebuilt, geometry="geometry", crs=layer.crs)

    notes.extend(_report_newly_unlocated(aligned, previous, log))

    log.record(
        f"replace {config.REPLACED_YEAR} [{label}]",
        rows_in=len(layer),
        rows_out=len(rebuilt),
        changes=[
            (-len(previous), f"rows of {config.REPLACED_YEAR} from the original extract"),
            (len(aligned), f"rows of {config.REPLACED_YEAR} from the updated extract"),
        ],
        notes=notes,
    )
    return rebuilt


def integrate(log: RunLog) -> dict[str, int]:
    """Build both layers and write them beside the sources, never over them."""
    incoming = pd.read_csv(config.INCOMING_2024_PATH, low_memory=False)
    years = sorted(incoming[config.YEAR_SOURCE_COL].dropna().astype(int).unique())
    if years != [config.REPLACED_YEAR]:
        raise ValueError(
            f"the incoming file covers {years}, but this route replaces {config.REPLACED_YEAR} only"
        )

    is_fatal = incoming[config.INCOMING_FATALITY_MARKER_COL].notna()
    log.record(
        "read the updated extract",
        rows_in=len(incoming),
        rows_out=len(incoming),
        notes=[
            f"source={config.INCOMING_2024_PATH.name}, one row per affected person, "
            f"both severities in one table",
            f"{int(is_fatal.sum())} rows carry {config.INCOMING_FATALITY_MARKER_COL} and are "
            f"fatalities; {int((~is_fatal).sum())} do not and are injuries",
            f"{incoming[config.CRASH_ID_COL].nunique():,} crashes",
        ],
    )

    _check_vehicle_reference(incoming, log)

    config.INTEGRATED_DIR.mkdir(parents=True, exist_ok=True)
    incoming_people = set(_as_text_key(incoming[config.PERSON_ID_COL]))

    layers = {
        config.FATALITY_SOURCE: gpd.read_file(config.RAW_FATALITIES_PATH),
        config.INJURY_SOURCE: gpd.read_file(config.RAW_INJURIES_PATH),
    }
    # The people of the replaced year across both layers, so that someone moving
    # from one severity to the other is not counted as a departure and an arrival.
    previous_people = {
        person
        for layer in layers.values()
        for person in layer.loc[layer[config.YEAR_SOURCE_COL] == config.REPLACED_YEAR,
                                config.PERSON_ID_COL]
    }

    written: dict[str, int] = {}
    for label, part, out_path in (
        (config.FATALITY_SOURCE, incoming[is_fatal], config.INTEGRATED_FATALITIES_PATH),
        (config.INJURY_SOURCE, incoming[~is_fatal], config.INTEGRATED_INJURIES_PATH),
    ):
        layer = layers[label]
        rebuilt = build_layer(
            part.reset_index(drop=True), layer, label, incoming_people, previous_people, log
        )
        rebuilt.to_parquet(out_path)
        log.info("wrote %s (%d rows)", out_path.relative_to(config.PROJECT_ROOT), len(rebuilt))
        written[label] = len(rebuilt)

    log.info(
        "the sources on disk are untouched; set USE_UPDATED_2024 = False in config to go back to them"
    )
    return written
