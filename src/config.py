"""Single source of configuration for the casualty matrix pipeline.

Everything the legacy notebook hard-coded inline lives here: paths, the
territorial scale, the study period, coordinate reference systems, the vehicle
type mapping and the run-time switches. Importing this module has no side
effects — nothing is read, written or created until a function is called
explicitly.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Base directories
# ---------------------------------------------------------------------------
# Paths are anchored to the repository root so the pipeline behaves the same
# whether it is launched from the root, from src/, or from a notebook.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

CRASH_DATA_DIR = DATA_DIR / "data_siniestros_bogota"
GEO_DATA_DIR = DATA_DIR / "geo"

# ---------------------------------------------------------------------------
# Source files
# ---------------------------------------------------------------------------
# Fatalities and injuries arrive as two separate point layers, one row per
# affected person. The vehicle table lists every party of every crash, including
# the ones that suffered no casualty — which is what makes it possible to find a
# counterpart for each casualty.
FATALITIES_PATH = CRASH_DATA_DIR / "MUERTO" / "MUERTO.shp"
INJURIES_PATH = CRASH_DATA_DIR / "LESIONADO" / "LESIONADO.shp"
VEHICLES_PATH = CRASH_DATA_DIR / "vehiculo.csv"

# ---------------------------------------------------------------------------
# Territorial scale
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TerritorialScale:
    """A spatial aggregation level and the shapefile that defines it."""

    key: str
    label: str
    shapefile: Path
    code_column: str  # column holding the unit code in the source shapefile
    name_column: str  # column holding the unit name in the source shapefile
    expected_units: int  # official number of units, used as a loud sanity check


SCALES: dict[str, TerritorialScale] = {
    "locality": TerritorialScale(
        key="locality",
        label="Localidad",
        shapefile=GEO_DATA_DIR / "bog_loc_urbanarea" / "bog_loc_urbanarea.shp",
        code_column="Identifica",
        name_column="Nombre_de_",
        expected_units=19,
    ),
    "upz": TerritorialScale(
        key="upz",
        label="UPZ",
        shapefile=GEO_DATA_DIR / "bog_upz" / "bog_upz.shp",
        code_column="cod_upz",
        name_column="nom_upz",
        expected_units=111,
    ),
    "upl": TerritorialScale(
        key="upl",
        label="UPL",
        shapefile=GEO_DATA_DIR / "unidadplaneamientolocal" / "UnidadPlaneamientoLocal.shp",
        code_column="CODIGO_UPL",
        name_column="NOMBRE",
        # Decreto 555 de 2021 defines 33 UPL. The shapefile on disk only carries
        # 30 (UPL01, UPL02 and UPL06 are absent) — see step2_auditoria_04_escalas.
        # The mismatch is reported at load time instead of passing unnoticed.
        expected_units=33,
    ),
}

# Switching the whole pipeline to another scale means changing this one value.
ACTIVE_SCALE = "locality"


def active_scale() -> TerritorialScale:
    """The scale the pipeline is currently configured to run on."""
    return SCALES[ACTIVE_SCALE]


# ---------------------------------------------------------------------------
# Study period
# ---------------------------------------------------------------------------
FIRST_YEAR = 2007
LAST_YEAR = 2024
STUDY_YEARS = range(FIRST_YEAR, LAST_YEAR + 1)

# ---------------------------------------------------------------------------
# Coordinate reference systems
# ---------------------------------------------------------------------------
# Sources come in MAGNA-SIRGAS geographic coordinates; the unit shapefiles vary,
# so everything is harmonised to SOURCE_CRS before any spatial operation.
SOURCE_CRS = 4686  # MAGNA-SIRGAS, degrees

# Anything measured in metres (distances, lengths, areas) must happen here.
# EPSG:3116 is MAGNA-SIRGAS / Colombia Bogota zone.
PROJECTED_CRS = 3116

# ---------------------------------------------------------------------------
# Spatial join
# ---------------------------------------------------------------------------
# A casualty belongs to the unit that contains its point. Nothing else counts.
SPATIAL_JOIN_PREDICATE = "within"

# The legacy pipeline appears to snap unmatched points to the nearest polygon,
# but that branch never runs: it looks for unmatched points in the result of a
# left join, which always keeps every input row, so its "missing" set is always
# empty. Had it run, max_distance=5 in a geographic CRS would have meant 5
# degrees (~550 km), not 5 m. Here the fallback is off by default, and when
# enabled the threshold is applied in PROJECTED_CRS so the unit is really metres.
USE_NEAREST_FALLBACK = False
NEAREST_FALLBACK_MAX_DISTANCE_M = 5.0

# ---------------------------------------------------------------------------
# Canonical column and value names
# ---------------------------------------------------------------------------
# Added by the pipeline. AREA_* deliberately does not reuse the LOCALIDAD column
# that the source layers already carry: the legacy code overwrote that field with
# the geometric result and destroyed the original without trace.
AREA_CODE_COL = "AREA_CODE"
AREA_NAME_COL = "AREA_NAME"

# Records where the casualty severity came from. Deaths are ~3% of records, so
# merging the two sources under one flag buries them irrecoverably.
CASUALTY_SOURCE_COL = "CASUALTY_SOURCE"
FATALITY_SOURCE = "FATALITY"
INJURY_SOURCE = "INJURY"

# Join keys shared by the casualty layers and the vehicle table. The casualty
# layers spell the second one CODIGO_VEH; the vehicle table spells it
# CODIGO_VEHICULO.
CRASH_ID_COL = "FORMULARIO"
PARTY_ID_COL = "CODIGO_VEHICULO"
PARTY_ID_COL_IN_CASUALTIES = "CODIGO_VEH"

# ---------------------------------------------------------------------------
# Vehicle type mapping
# ---------------------------------------------------------------------------
PEDESTRIAN = "PEDESTRIAN"
BICYCLE = "BICYCLE"
MOTORCYCLE = "MOTORCYCLE"
CAR = "CAR"
PUBLIC_TRANSPORT = "PUBLIC_TRANSPORT"
OTHER = "OTHER"

ROAD_USER_TYPES = (PEDESTRIAN, BICYCLE, MOTORCYCLE, CAR, PUBLIC_TRANSPORT, OTHER)


def normalize_vehicle_type(value: str) -> str:
    """Reduce a raw vehicle type to the form used as a mapping key.

    Strips surrounding blanks, collapses internal runs of whitespace, drops the
    blanks that sometimes precede a comma or a period, removes diacritics and
    upper-cases. Applied to both sides of the mapping so a typing variation in
    the source ("Camión , furgón", "CAMION, FURGON") resolves to the same key
    instead of silently falling through.
    """
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    collapsed = " ".join(without_accents.split())
    return re.sub(r"\s+([,.])", r"\1", collapsed).upper()


# Classification principle: the category reflects how protected the occupant is,
# not what the vehicle is used for economically. A rider with no bodywork around
# them belongs with motorcycles whether the vehicle carries passengers, cargo or
# nothing at all; an occupant inside a closed passenger cabin belongs with cars
# or public transport depending on whether the service is mass transit.
#
# Two deliberate exceptions to that principle, declared rather than implied:
#   * TRACCION ANIMAL stays in OTHER because it belongs to neither the motorised
#     family nor the pedal family, so the protection criterion does not place it.
#   * NO IDENTIFICADO stays in OTHER because the vehicle is unknown, not because
#     its level of protection was assessed and found to be anything in
#     particular.
#
# Every value present in vehiculo.csv is listed, so nothing reaches the fallback
# silently. Anything not listed still lands in OTHER rather than becoming null,
# and the loader reports which raw values fell through and how many rows.
_VEHICLE_TYPE_MAP_SOURCE: dict[str, str] = {
    # No vehicle at all. Injected where a casualty has no vehicle of its own.
    "PEATON": PEDESTRIAN,
    # Pedal powered, occupant fully exposed.
    "BICICLETA": BICYCLE,
    "BICITAXI": BICYCLE,
    # Motorised, occupant with no bodywork around them.
    "MOTOCICLETA": MOTORCYCLE,
    "MOTOCICLO": MOTORCYCLE,
    "MOTOTRICICLO": MOTORCYCLE,
    "MOTOCARRO": MOTORCYCLE,
    "CUATRIMOTO": MOTORCYCLE,
    # Closed passenger cabin, private use.
    "AUTOMOVIL": CAR,
    "CAMIONETA": CAR,
    "CAMPERO": CAR,
    # Closed passenger cabin, mass transit.
    "BUS": PUBLIC_TRANSPORT,
    "BUSETA": PUBLIC_TRANSPORT,
    "MICROBUS": PUBLIC_TRANSPORT,
    "BUS ARTICULADO": PUBLIC_TRANSPORT,
    "BUS ALIMENTADOR": PUBLIC_TRANSPORT,
    # Heavy or industrial cabs, rail, and residual categories.
    "CAMION, FURGON": OTHER,
    "TRACTOCAMION": OTHER,
    "VOLQUETA": OTHER,
    "M. INDUSTRIAL": OTHER,
    "M. AGRICOLA": OTHER,
    "METRO": OTHER,
    "TREN": OTHER,
    "REMOLQUE": OTHER,
    "SEMI-REMOLQUE": OTHER,
    "OTRO": OTHER,
    # The source spells it AMBULACIA. Both spellings are mapped so a corrected
    # extract does not start dropping rows into the fallback.
    "AMBULACIA": OTHER,
    "AMBULANCIA": OTHER,
    # The two declared exceptions to the protection principle.
    "TRACCION ANIMAL": OTHER,
    "NO IDENTIFICADO": OTHER,
}


def _build_vehicle_type_map(source: dict[str, str]) -> dict[str, str]:
    """Key the mapping by normalized text, refusing ambiguous collisions.

    Two source keys may normalize to the same text only if they agree on the
    target category; disagreeing keys would make the result depend on dict order.
    """
    built: dict[str, str] = {}
    for raw_key, category in source.items():
        key = normalize_vehicle_type(raw_key)
        if key in built and built[key] != category:
            raise ValueError(
                f"vehicle type {raw_key!r} normalizes to {key!r}, which is already mapped to "
                f"{built[key]!r} and cannot also mean {category!r}"
            )
        built[key] = category
    return built


VEHICLE_TYPE_MAP: dict[str, str] = _build_vehicle_type_map(_VEHICLE_TYPE_MAP_SOURCE)

VEHICLE_TYPE_FALLBACK = OTHER

# ---------------------------------------------------------------------------
# Run-time switches
# ---------------------------------------------------------------------------
# When true, every stage writes its output to the run directory. Off by default
# because the intermediates are large and only useful when debugging.
DUMP_INTERMEDIATES = False

RUN_DIR_PREFIX = "run_"
RUN_DIR_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
LOG_FILENAME = "provenance.log"


def new_run_directory(now: dt.datetime | None = None, base: Path | None = None) -> Path:
    """Create and return a fresh timestamped directory for this run's outputs.

    Each execution gets its own folder instead of overwriting the previous one,
    so two runs can be compared side by side.
    """
    base = RESULTS_DIR if base is None else base
    stamp = (now or dt.datetime.now()).strftime(RUN_DIR_TIMESTAMP_FORMAT)
    run_dir = base / f"{RUN_DIR_PREFIX}{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


# ---------------------------------------------------------------------------
# Verification baseline
# ---------------------------------------------------------------------------
# Measured on the real execution of the legacy notebook and documented in
# docs/auditoria/auditoria_02_balance.md. Loading changes none of the legacy
# logic, so these counts must be reproduced exactly. A mismatch means a bug, not
# a number to be adjusted.
LEGACY_BASELINE_COUNTS: dict[str, int] = {
    "fatalities": 8_548,
    "injuries": 261_293,
    "concatenated": 269_841,
    "fatalities_without_area": 61,
    "injuries_without_area": 1_344,
    "vehicles": 1_465_735,
}
