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
    # Number of units the study universe is declared on at this scale. It is the
    # denominator of every coverage figure, so the loader checks the layer against
    # it and stops if they disagree.
    expected_units: int


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
        # The study universe is the 30 UPL this layer carries. Decreto 555 de 2021
        # defines 33; the three absent ones (UPL01, UPL02 and UPL06) are the rural
        # units, where the urban predictors are undefined anyway. See D7. Thirty is
        # the denominator of every coverage figure, so a layer that does not carry
        # exactly thirty units is a different layer and the loader stops.
        expected_units=30,
    ),
}

# The scale of the study. Everything downstream — the grid, the predictors, the
# panel — is built on it, and switching it means changing this one value.
ACTIVE_SCALE = "upl"


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
VEHICLE_ID_COL = "CODIGO_VEHICULO"
VEHICLE_ID_COL_IN_CASUALTIES = "CODIGO_VEH"
PERSON_ID_COL = "CODIGO_ACC"
ROLE_COL = "CONDICION"  # PEATON, CONDUCTOR, PASAJERO, MOTOCICLISTA, CICLISTA...
PEDESTRIAN_ROLE = "PEATON"
CRASH_CLASS_SOURCE_COL = "CLASE_ACC"
YEAR_SOURCE_COL = "ANO_OCURRE"

# ---------------------------------------------------------------------------
# Party resolution
# ---------------------------------------------------------------------------
# Columns of the one-row-per-affected-party table.
PARTY_ID_COL = "PARTY_ID"
PARTY_TYPE_COL = "PARTY_TYPE"
COUNTERPART_TYPE_COL = "COUNTERPART_TYPE"
AFFECTED_PARTIES_COL = "AFFECTED_PARTIES"  # always 1; the party is the unit
PERSONS_INJURED_COL = "PERSONS_INJURED"
PERSONS_KILLED_COL = "PERSONS_KILLED"
CRASH_CLASS_COL = "CRASH_CLASS"
YEAR_COL = "YEAR"

# Counterpart of a party in a crash where no other party was recorded, such as a
# motorcycle hitting a lamp post. The study being replicated counts these too.
SELF_COUNTERPART = "SELF"

# Same criterion as the European study being replicated. Counts every recorded
# party, whether or not it suffered casualties: with three or more parties the
# counterpart of a given casualty is ambiguous.
MAX_PARTIES_PER_CRASH = 2

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

# When a casualty names no vehicle, the role recorded on the form is the only
# thing left to go on. Under the same principle as the mapping above — the
# category reflects how protected the occupant is — a role settles the question
# only when it implies the level of protection by itself:
#
#   * A motorcyclist or a cyclist is exposed whatever the particular machine was,
#     so the role alone places them.
#   * A driver or a passenger may be protected or not depending on what they were
#     travelling in, so the role does not place them: the vehicle is still
#     unknown and the record goes to the residual category.
#
# A role absent from this mapping, including no role at all, goes to the residual
# category and is reported separately rather than classified on a guess.
ROLE_TO_ACTOR_TYPE: dict[str, str] = {
    "PEATON": PEDESTRIAN,
    "MOTOCICLISTA": MOTORCYCLE,
    "CICLISTA": BICYCLE,
    "CONDUCTOR": OTHER,
    "PASAJERO": OTHER,
}

# Roles that the mapping above resolves to a real mode rather than the residual
# category; used only to report how much the rule recovers.
ROLES_RESOLVING_TO_A_MODE = ("MOTOCICLISTA", "CICLISTA")

# ---------------------------------------------------------------------------
# Casualty matrix
# ---------------------------------------------------------------------------
# The scale travels with every row: unit codes are not unique across scales (the
# code "19" is both a UPZ and a locality), so the pair scale plus code is the
# only safe key for anything downstream.
SCALE_COL = "SCALE"

# Fixed order for rows and columns, declared here rather than left to whatever
# the grouping returns, so two runs can be compared line by line. Ordered from
# the least protected road user to the most, with the residual category last and
# the single-party marker after it.
MATRIX_ROW_ORDER = (PEDESTRIAN, BICYCLE, MOTORCYCLE, CAR, PUBLIC_TRANSPORT, OTHER)
MATRIX_COLUMN_ORDER = MATRIX_ROW_ORDER + (SELF_COUNTERPART,)

# The three counts the matrix carries, all from the same run.
MATRIX_COUNTS: dict[str, str] = {
    "parties": AFFECTED_PARTIES_COL,
    "injured": PERSONS_INJURED_COL,
    "killed": PERSONS_KILLED_COL,
}

# Layout inside a run directory.
DATA_SUBDIR = "data"
BY_YEAR_SUBDIR = "by_year"
FIGURES_SUBDIR = "figures"
INTERMEDIATE_SUBDIR = "intermediate"

# File name prefixes. A table meant for models and a table meant for reading are
# never interchangeable, so the name says which it is before anyone opens it.
ANALYSIS_PREFIX = "analysis"
PRESENTATION_PREFIX = "presentation"

# ---------------------------------------------------------------------------
# rho(t): share of two-party crashes in which both parties suffered casualties
# ---------------------------------------------------------------------------
# A diagnostic, not a product of the matrix. Whether both parties come out of a
# crash with casualties is close to physical, so an abrupt change between two
# consecutive years points at how casualties were recorded rather than at the
# crashes themselves.
#
# It is computed from the party universe before the parties without casualties
# are dropped: the denominator counts crashes where only one party was affected,
# and the matrix cannot tell those from crashes where both were.

# The nine pairs. At least one side must be a motorcycle, a car or public
# transport — the modes that impose the risk — and the other side is any of the
# five modes. A mode with itself is excluded, because the question "were both
# parties affected" says nothing about the interaction between two modes when
# there is only one mode involved. The residual category is out: it is a bag of
# unlike vehicles, and a rate over it would average things that have nothing in
# common.
RHO_PRIMARY_TYPES = (MOTORCYCLE, CAR, PUBLIC_TRANSPORT)
RHO_SECONDARY_TYPES = (PEDESTRIAN, BICYCLE, MOTORCYCLE, CAR, PUBLIC_TRANSPORT)

# Canonical order inside a pair, from the least protected road user to the most.
# The pair is unordered — a motorcycle hit by a car and a car hit by a motorcycle
# are the same crash and the same question — so each pair gets exactly one
# representation and there is no orientation to get wrong.
RHO_PAIR_ORDER = (PEDESTRIAN, BICYCLE, MOTORCYCLE, CAR, PUBLIC_TRANSPORT)
RHO_PAIR_SEPARATOR = "-"


def _build_rho_pairs() -> tuple[tuple[str, str], ...]:
    """The nine unordered pairs, in a fixed order, derived rather than listed.

    Written out by hand this would be a list that has to be kept in agreement
    with the two rules above; derived, the rules are the only thing to maintain.
    """
    rank = {actor: position for position, actor in enumerate(RHO_PAIR_ORDER)}
    pairs = set()
    for primary in RHO_PRIMARY_TYPES:
        for secondary in RHO_SECONDARY_TYPES:
            if primary == secondary:
                continue
            pairs.add(tuple(sorted((primary, secondary), key=rank.__getitem__)))
    return tuple(sorted(pairs, key=lambda pair: (rank[pair[0]], rank[pair[1]])))


RHO_PAIRS: tuple[tuple[str, str], ...] = _build_rho_pairs()


def rho_pair_label(first: str, second: str) -> str:
    """The single text representation of an unordered pair."""
    return f"{first}{RHO_PAIR_SEPARATOR}{second}"


RHO_PAIR_LABELS: tuple[str, ...] = tuple(rho_pair_label(*pair) for pair in RHO_PAIRS)

# Columns of the rho table. Scale, unit and year deliberately reuse the names and
# the values of the matrix table, because the dashboard joins the two.
AGGREGATION_LEVEL_COL = "AGGREGATION_LEVEL"
UNIT_LEVEL = "UNIT"
CITY_LEVEL = "CITY"

# City rows carry a code of their own rather than a null, so the unit column is
# never empty and a join against the matrix cannot match them by accident. The
# level column is what a reader filters on; this is what keeps the key honest.
CITY_AREA_CODE = "BOGOTA"
CITY_AREA_NAME = "Bogotá D.C."

PAIR_COL = "PAIR"
PAIR_FIRST_COL = "PAIR_TYPE_A"  # the two sides, in canonical order, so the pair
PAIR_SECOND_COL = "PAIR_TYPE_B"  # can be joined to the matrix without splitting text
RHO_NUMERATOR_COL = "CRASHES_BOTH_AFFECTED"
RHO_DENOMINATOR_COL = "CRASHES_TOTAL"
RHO_COL = "RHO"

# Below this many crashes in the denominator, rho is noise. Nothing is filtered
# on it — the denominator travels next to rho in every row and every figure, and
# the reader decides — but the run reports how much of the grid is that thin.
RHO_SPARSE_DENOMINATOR = 10

# A year-on-year change in rho above this is called out by name in the report. It
# is a reporting threshold, not a test: rho is a diagnostic to be looked at, and
# this only decides what gets pointed at first.
RHO_JUMP_THRESHOLD = 0.10

# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
FIGURE_DPI = 150
HEATMAP_COLORMAP = "viridis"
# Cells with no observation at all are drawn in this colour instead of the bottom
# of the colour ramp, so that a true zero cannot be mistaken for a small value on
# a logarithmic scale.
HEATMAP_EMPTY_COLOR = "#eeeeee"

# rho figures are small multiples: one panel per pair for the city, one panel per
# unit for a given pair. Each panel therefore draws one series and, where it
# helps, one reference — so identity never rests on telling nine hues apart,
# which is not something a reader should be asked to do.
RHO_SERIES_COLOR = "#1b6ca8"
RHO_REFERENCE_COLOR = "#9e9e9e"
# Points whose denominator is below RHO_SPARSE_DENOMINATOR are drawn hollow. The
# value is not hidden or dropped; it is marked as thin where it is read.
RHO_SPARSE_MARKER_FACE = "#ffffff"
RHO_GRID_COLOR = "#e3e3e3"

# ---------------------------------------------------------------------------
# Run-time switches
# ---------------------------------------------------------------------------
# When true, every stage writes its output to the run directory. Off by default
# because the intermediates are large and only useful when debugging; the entry
# point can turn them on for a single run without this file being edited.
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
# Verification baselines
# ---------------------------------------------------------------------------
# Two different things live in this section and must not be read as one.
#
# LEGACY_BASELINE_COUNTS is a *historical contrast*. These counts were measured
# on the real execution of the legacy notebook, documented in
# docs/auditoria/auditoria_02_balance.md, and that execution ran at LOCALITY
# scale. They are the evidence that the reimplementation reproduced the pipeline
# it replaces, and they are kept for that reason alone, not as a target for the
# current scale.
#
# SCALE_BASELINE_COUNTS is the *live reference*: the same measures taken on the
# scale the study actually runs on, so that a future run which shifts is caught
# immediately. It is what a run is verified against from now on.
LEGACY_BASELINE_COUNTS: dict[str, int] = {
    "fatalities": 8_548,
    "injuries": 261_293,
    "concatenated": 269_841,
    "fatalities_without_area": 61,
    "injuries_without_area": 1_344,
    "vehicles": 1_465_735,
}

# The scale the legacy figures above were measured on. Outside it, the two
# footprint-dependent counts are not comparable to them.
LEGACY_BASELINE_SCALE = "locality"

# Counts that no territorial layer can change: they are properties of the source
# files themselves, so they must reproduce the legacy figures exactly whatever
# scale is active. A mismatch here means a bug, not a number to be adjusted.
SCALE_INDEPENDENT_CHECKS = ("fatalities", "injuries", "concatenated", "vehicles")

# Counts that depend on the footprint of the unit layer, because they count the
# records that fall outside every polygon. Two layers covering different
# territory necessarily disagree on them, so they are checked against the
# baseline of the active scale — never across scales.
SCALE_DEPENDENT_CHECKS = ("fatalities_without_area", "injuries_without_area")

# Footprint-dependent counts per scale, measured on this implementation. A scale
# with no entry here has no baseline yet: the run reports its figures as a first
# measurement instead of failing, and they belong in this table afterwards.
#
# Locality is deliberately absent: on that scale the legacy figures above are the
# baseline, and repeating them here would be one number in two places, free to
# drift apart without anything noticing.
SCALE_BASELINE_COUNTS: dict[str, dict[str, int]] = {
    # The live reference of the study. Measured on the UPL layer, whose footprint
    # is not the union of the localities, so these are lower than the legacy
    # figures rather than a correction of them.
    "upl": {
        "fatalities_without_area": 50,
        "injuries_without_area": 1_186,
    },
}

# ---------------------------------------------------------------------------
# Legacy reference figures, for divergence reporting only
# ---------------------------------------------------------------------------
# From the same measured run. These are NOT targets: the party model deliberately
# departs from the legacy pipeline, and the figures below carry the orientation
# bias it is meant to remove. They exist so the size and direction of the
# departure can be quantified and reported, never to be matched.
#
# They were taken before the legacy pipeline restricted itself geographically, so
# unlike the footprint counts above they do not depend on the unit layer and stay
# comparable whatever scale is active.
LEGACY_REFERENCE: dict[str, int] = {
    # One row per crash in the legacy export, not per affected party.
    "exported_rows": 179_110,
    "crashes_in_scope": 184_112,
    # Cells of the legacy matrix that made the orientation bias visible: a
    # motorcyclist recorded as harmed with a bicycle as counterpart four times
    # more often than the reverse.
    "motorcycle_row_bicycle_counterpart": 8_129,
    "bicycle_row_motorcycle_counterpart": 1_881,
}
