"""Single source of configuration for the casualty matrix pipeline.

Everything the legacy notebook hard-coded inline lives here: paths, the
territorial scale, the study period, coordinate reference systems, the vehicle
type mapping and the run-time switches. Importing this module has no side
effects — nothing is read, written or created until a function is called
explicitly.
"""

from __future__ import annotations

import datetime as dt
import math
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
#
# The RAW_ paths are the extract this work started from and are never written to
# by anything here.
RAW_FATALITIES_PATH = CRASH_DATA_DIR / "MUERTO" / "MUERTO.shp"
RAW_INJURIES_PATH = CRASH_DATA_DIR / "LESIONADO" / "LESIONADO.shp"
VEHICLES_PATH = CRASH_DATA_DIR / "vehiculo.csv"

# ---------------------------------------------------------------------------
# Updated 2024 extract
# ---------------------------------------------------------------------------
# A later extract of 2024 arrived covering the whole year, where the injury layer
# of the original one stops in mid-September. The integration route rebuilds both
# casualty layers with every 2024 row replaced by that extract, writing the
# result beside the sources rather than over them.
#
# The general criterion, which will apply again the next time an update arrives:
# where two extracts describe the same record, the more recent one prevails. See
# D19.
INCOMING_2024_PATH = DATA_DIR / "incoming" / "afectados_2024.csv"
INTEGRATED_DIR = DATA_DIR / "integrated"
INTEGRATED_FATALITIES_PATH = INTEGRATED_DIR / "fatalities__2024_updated_extract.parquet"
INTEGRATED_INJURIES_PATH = INTEGRATED_DIR / "injuries__2024_updated_extract.parquet"

# The incoming file holds both severities in one table. This column tells them
# apart: present means the person died. Verified against the previous extract —
# all 543 people already known to be fatalities carry it, and no person known to
# be an injury does, apart from six who died after that extract was taken.
# It is a rule about this file, not about the format: in the original fatality
# layer the same column is null on 35% of the rows.
INCOMING_FATALITY_MARKER_COL = "MUERTE_POS"

# The year the updated extract replaces, whole.
REPLACED_YEAR = 2024

# Geometry in the incoming file is WKT with no CRS declared anywhere. This is the
# one the points actually agree with: 95% of the people present in both extracts
# land on exactly the same coordinates under it.
INCOMING_GEOMETRY_COL = "geometry"
INCOMING_CRS = 4686

# The single line to revert the integration. False sends every stage back to the
# original extract; nothing else in the code has to change, because the paths
# below are what the whole pipeline reads.
USE_UPDATED_2024 = True

FATALITIES_PATH = INTEGRATED_FATALITIES_PATH if USE_UPDATED_2024 else RAW_FATALITIES_PATH
INJURIES_PATH = INTEGRATED_INJURIES_PATH if USE_UPDATED_2024 else RAW_INJURIES_PATH

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
DATE_SOURCE_COL = "FECHA_OCUR"

# ---------------------------------------------------------------------------
# Source completeness
# ---------------------------------------------------------------------------
# A month holding less than this share of the median month of its own year is
# reported. Judged against the year itself because the layers grow over eighteen
# years, so any fixed count would either excuse the recent years or condemn the
# early ones. It is a reporting threshold: nothing is ever filtered on it.
COMPLETENESS_THIN_SHARE = 0.5

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
PREDICTORS_FIGURES_SUBDIR = "predictors"
INTERMEDIATE_SUBDIR = "intermediate"

# File name prefixes. A table meant for models and a table meant for reading are
# never interchangeable, so the name says which it is before anyone opens it.
# A third kind exists: a table that describes the variables rather than measuring
# anything, which is neither of the two and is named apart from both.
ANALYSIS_PREFIX = "analysis"
PRESENTATION_PREFIX = "presentation"
REFERENCE_PREFIX = "reference"

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

# Used to report how much of the grid rests on few crashes, and for nothing else.
# It is not a filter and not a mark on any figure: no value is hidden, dropped or
# drawn differently for being thin. The denominator travels beside rho in every
# row of the exported table and in the panel titles, and the reader decides.
RHO_SPARSE_DENOMINATOR = 10

# A year-on-year change in rho above this is called out by name in the report. It
# is a reporting threshold, not a test: rho is a diagnostic to be looked at, and
# this only decides what gets pointed at first.
RHO_JUMP_THRESHOLD = 0.10

# -- the city series in a shape LaTeX can plot ------------------------------
# A document that draws its own rho figure needs the series as a file, or every
# value ends up retyped into the source and drifts from the run that produced it.
# Two things separate this file from the CSV beside it, and both come from its
# only reader being pgfplots rather than the dashboard:
#
#   the pair separator is an underscore, because pgfplots addresses a column by
#   name inside a key-value list, where a hyphen is fragile;
#
#   an undefined rho is written out as a word rather than left as an empty field,
#   because an empty field between two separators reads as a zero, and a year in
#   which a pair had no crash at all is not a year in which nobody was hurt.
RHO_PGFPLOTS_PAIR_SEPARATOR = "_"
RHO_PGFPLOTS_MISSING = "nan"
RHO_PGFPLOTS_DECIMALS = 6

# ---------------------------------------------------------------------------
# The correction for the change in recording practice
# ---------------------------------------------------------------------------
# rho showed that before 2018 the source recorded one casualty per crash, and that
# from 2018 it records every affected party. The crash entered the system either
# way: what was missing was the casualty of the second party, almost always the
# protected one. So the correction does not inflate a pair's cell as a whole. It
# reclassifies crashes that today carry a single affected party into crashes with
# two, and promotes the party that was already in the universe without casualties.
#
# See D28 (the mechanism and the reference window), D29 (how the deficit is split
# between the two sides) and D30 (why 2007 cannot be corrected).

# The reference window: the years rho has been measured to have settled in. It is
# not 2022-2024. 2022 is the last year of the climb -- every pair rises into it,
# seven of nine rise out of it into 2023, and only from 2023 does the series go
# flat. Including it would drag the reference below the level the practice
# actually reached, and would do so in the pairs that had already arrived as well.
# The full argument, with the tests that were run and the ones that cannot settle
# it, is in D28.
CORRECTION_REFERENCE_YEARS: tuple[int, ...] = (2023, 2024)

# 2007 is out of the corrected set entirely. Not because rho cannot be computed
# for it, but because that year does not distinguish the two parties of a
# vehicle-vehicle crash at all (see D18), so it cannot support an inter-mode
# matrix, corrected or otherwise.
CORRECTION_EXCLUDED_YEARS: tuple[int, ...] = (2007,)

# The two datasets a run produces. The label travels in a column of every exported
# table, so a model fed the wrong one is not reading a filename to find out.
DATASET_COL = "DATASET"
OBSERVED_DATASET = "OBSERVED"
CORRECTED_DATASET = "RHO_CORRECTED"

# The suffix that separates the corrected files from the observed ones. The
# observed files keep the names they already have, so nothing downstream that
# reads them breaks; the corrected ones are new files with a name that says what
# they are.
CORRECTION_FILE_SUFFIX = "rho_corrected"

# Columns of the correction plan, which is exported so the correction can be
# audited cell by cell rather than believed.
CORRECTION_SIDE_COL = "PROMOTED_SIDE"          # which side of the pair was added
CORRECTION_POOL_COL = "RECLASSIFIED_FROM"      # the outcome the crash was recorded as
CORRECTION_DEFICIT_COL = "CRASHES_RECLASSIFIED"
CORRECTION_PARTIES_COL = "PARTIES_ADDED"
CORRECTION_INJURED_COL = "PERSONS_INJURED_ADDED"
CORRECTION_KILLED_COL = "PERSONS_KILLED_ADDED"
CORRECTION_RHO_OBSERVED_COL = "RHO_OBSERVED"
CORRECTION_RHO_REFERENCE_COL = "RHO_REFERENCE"
CORRECTION_RHO_CORRECTED_COL = "RHO_CORRECTED"

# The three outcomes a two-party crash can have once the two sides keep their own
# affected flag instead of being reduced to their conjunction. A is the less
# protected side of the pair, B the more protected, in the canonical order rho
# already uses.
OUTCOME_COL = "OUTCOME"
OUTCOME_ONLY_A = "ONLY_A"
OUTCOME_ONLY_B = "ONLY_B"
OUTCOME_BOTH = "BOTH"
OUTCOME_NEITHER = "NEITHER"

# rho of the corrected set has to land on the reference by construction. It cannot
# land on it exactly, because the target is a whole number of crashes and the
# reference is a ratio, so the check allows the rounding of one crash: a deviation
# above 1/n means an error, not a rounded target.
CORRECTION_RHO_TOLERANCE_CRASHES = 1.0

# ---------------------------------------------------------------------------
# Urban predictors
# ---------------------------------------------------------------------------
# The other half of the study: the features of a unit that the casualty rates are
# to be regressed against. Fifteen layers exist; eleven are a single snapshot with
# no year and four carry an annual series.
#
# What is implemented here are the ten static ones. The four with a series
# (cycleways and the three signage layers) come later, and the long table below is
# shaped so they slot into it without a schema change: every row already carries a
# YEAR column, null for a snapshot and filled for a series.
#
# The eleventh snapshot, the origin-destination desire lines, is deliberately out.
# Its length column is not in kilometres: the legacy code multiplies the length of
# each line by the survey expansion factor of its own record and writes the result
# back over the kilometres under the same name. Because the factor varies from
# record to record that is a transformation and not a rescaling, so the variable
# is neither kilometres nor trips, and its row of the correlation matrix could not
# be interpreted. It stays out until my advisor says what it was meant to measure.
# See D21.
PREDICTORS_DIR = DATA_DIR / "shp_properties_sorted"

# -- the geometry of a source layer -----------------------------------------
# The code is in English and the delivered data is in Spanish, so there is no way
# to walk from ARTERIAL_ROAD_AREA_SHARE back to the avenidas_corregidas layer and
# from there to the file it came out of, except by reading the measurement and
# deducing it. Everything below closes that chain and, more importantly, makes
# the code depend on it: the path is built from the declaration, the measurement
# is dispatched by it, and the geometry is checked against the file when it is
# read. A wrong entry stops the run instead of misinforming a reader, which is
# the one property a comment can never have.
AREA_GEOMETRY = "area"
POINT_GEOMETRY = "point"
LINE_GEOMETRY = "line"

# The folder each geometry lives in, exactly as the delivered data is arranged.
# This is what turns a declared layer name into a path, so a typo in the name
# raises a missing file rather than measuring something else.
GEOMETRY_FOLDERS: dict[str, str] = {
    AREA_GEOMETRY: "areas",
    POINT_GEOMETRY: "points",
    LINE_GEOMETRY: "lines",
}

# The geometry types each kind admits, checked against the layer at the moment it
# is read. MultiPoint is in the point list because the TransMilenio layer records
# a station as a collection of platforms, which the measurement explodes.
GEOMETRY_TYPES: dict[str, tuple[str, ...]] = {
    AREA_GEOMETRY: ("Polygon", "MultiPolygon"),
    POINT_GEOMETRY: ("Point", "MultiPoint"),
    LINE_GEOMETRY: ("LineString", "MultiLineString"),
}

# The family is the geometry as the exported tables label it, and it is what the
# rest of the pipeline groups by. It follows from the geometry rather than being
# declared twice, so the two can never disagree.
AREA_FAMILY = "AREA"
POINT_FAMILY = "POINT"
LINE_FAMILY = "LINE"

GEOMETRY_FAMILIES: dict[str, str] = {
    AREA_GEOMETRY: AREA_FAMILY,
    POINT_GEOMETRY: POINT_FAMILY,
    LINE_GEOMETRY: LINE_FAMILY,
}

# -- how a variable is measured ---------------------------------------------
# A method is the operation that turns a layer into one number per unit. The
# sentence describing it lives here, beside the units it produces, and not on
# each variable: the key a variable declares is the same key that selects the
# function which runs, so the sentence cannot end up describing something the
# code does not do. That is the failure the legacy notebook had, where a text
# cell described an ordering rule the code never implemented.
AREA_SHARE_METHOD = "area_share"
POINT_DENSITY_METHOD = "point_density"


@dataclass(frozen=True)
class MeasurementMethod:
    """One way of measuring a layer against a unit, with what it yields."""

    name: str
    geometry: str  # the geometry this method can measure
    measure_unit: str  # unit of the raw magnitude, before normalising
    value_unit: str  # unit after dividing by the area of the unit
    computation: str  # one sentence: what the code actually does


MEASUREMENT_METHODS: dict[str, MeasurementMethod] = {
    AREA_SHARE_METHOD: MeasurementMethod(
        name=AREA_SHARE_METHOD,
        geometry=AREA_GEOMETRY,
        measure_unit="km2",
        value_unit="share of unit area",
        computation=(
            "repair invalid polygons, intersect the layer with the unit in EPSG:3116, "
            "add the area of every fragment falling inside the unit, and divide that "
            "surface by the area of the unit"
        ),
    ),
    POINT_DENSITY_METHOD: MeasurementMethod(
        name=POINT_DENSITY_METHOD,
        geometry=POINT_GEOMETRY,
        measure_unit="count",
        value_unit="points per km2",
        computation=(
            "explode multi-part features into one point each, keep the points contained "
            "in the unit in EPSG:3116, count them, and divide the count by the area of "
            "the unit"
        ),
    ),
}

# -- keeping part of a layer ------------------------------------------------
# Every other layer is measured whole: the file is the feature. The tree census
# is not, because it records trees wherever they stand and two of the three tree
# variables are about a subset of them. The rule that selects the subset is
# declared here, beside the variable, for the same reason the measurement method
# is: the code dispatches on this object, the run log reports what it removed,
# and the data dictionary exports the sentence. A rule written only in a comment
# can drift away from the code that runs; this one cannot.
#
# A rule is written one of two ways and never both. Naming what goes out suits a
# criterion that removes one thing from an otherwise complete layer; naming what
# stays suits a criterion that keeps a known set and would silently admit any new
# value the source invents. Which form a rule takes is itself a statement about
# how much the declaration trusts the source.
@dataclass(frozen=True)
class SourceFilter:
    """A rule that keeps part of a source layer and drops the rest."""

    column: str  # the attribute the rule reads, spelled as the delivered file spells it
    keeps: str  # one sentence: what is left once the rule has run
    rationale: str  # why what it drops is not what the variable measures
    # Exactly one of the two is set. Both empty would be a rule that does
    # nothing; both set would be two rules pretending to be one.
    excluded_values: tuple[str, ...] = ()  # these go, everything else stays
    included_values: tuple[str, ...] = ()  # these stay, everything else goes

    def __post_init__(self) -> None:
        if not self.column:
            raise ValueError("a source filter must name the column it reads")
        if bool(self.excluded_values) == bool(self.included_values):
            raise ValueError(
                f"the filter on {self.column!r} must either name what it excludes or name what "
                "it includes, and exactly one of the two: a rule with neither filters nothing, "
                "and a rule with both is two rules"
            )

    @property
    def declared_values(self) -> tuple[str, ...]:
        """The values the rule names, whichever way round it is written.

        Every one of them has to be present in the column, or the rule is not
        doing what it says. That check is the same in both directions, so it
        reads the values through here rather than branching on the form.
        """
        return self.excluded_values or self.included_values

    def keeps_value(self, value: str) -> bool:
        """Does a row carrying this value survive the rule?"""
        if self.excluded_values:
            return value not in self.excluded_values
        return value in self.included_values

    @property
    def description(self) -> str:
        """The rule as one line, for the dictionary and the run log."""
        verb = "drop" if self.excluded_values else "keep only"
        return f"{verb} {self.column} in {{{', '.join(self.declared_values)}}}: {self.keeps}"


# The emplacement column of the tree census, and the two code sets the variants
# are built on. Neither is a criterion the study endorses: the layer arrived with
# no dictionary for this column, and what each code turned out to mean was
# measured rather than looked up. See D32 for the measurements and for why the
# variable that enters the models uses no criterion at all.
TREE_EMPLACEMENT_COL = "Tipo_Empla"

# The single largest code, 21% of the census. It was taken for the park
# emplacement and is not one.
PARK_TREE_EMPLACEMENTS: tuple[str, ...] = ("P1",)

# The fifteen U codes, enumerated rather than matched on their first letter.
# A prefix rule would silently admit a code the source had not used before, and
# this variable exists precisely to put a defined set of trees in front of my
# advisor. A new code appearing stops the run instead, which is the outcome that
# gets looked at.
URBAN_TREE_EMPLACEMENTS: tuple[str, ...] = (
    "U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8",
    "U9", "U10", "U11", "U12", "U13", "U14", "U15",
)

TREES_WITHOUT_PARK_FILTER = SourceFilter(
    column=TREE_EMPLACEMENT_COL,
    excluded_values=PARK_TREE_EMPLACEMENTS,
    keeps="every tree of the census except the largest single emplacement code",
    rationale=(
        "P1 was read as the park emplacement, on the reasoning that a tree inside a park "
        "produces none of the visual narrowing the variable stands for; measured against "
        "the delivered layers it is not the park code, which is why this is a variant and "
        "not the variable that enters the models"
    ),
)

URBAN_TREES_FILTER = SourceFilter(
    column=TREE_EMPLACEMENT_COL,
    included_values=URBAN_TREE_EMPLACEMENTS,
    keeps="the trees carrying one of the fifteen U emplacement codes",
    rationale=(
        "the U codes are the ones the profiling puts next to a carriageway, so this is the "
        "closest a code-based criterion gets to the mechanism; it is a variant because the "
        "codes are undocumented and the fifteen do not all behave alike"
    ),
)

# -- how much time a variable covers ----------------------------------------
# All ten implemented here are a single snapshot with no year, and the long table
# carries a null YEAR for every one of them. The constant exists because the four
# layers with an annual series are declared the same way when they arrive, and
# the check that a snapshot carries no year is what keeps the two apart.
SNAPSHOT_COVERAGE = "snapshot"
ANNUAL_SERIES_COVERAGE = "annual series"
TIME_COVERAGES: tuple[str, ...] = (SNAPSHOT_COVERAGE, ANNUAL_SERIES_COVERAGE)


@dataclass(frozen=True)
class StaticPredictor:
    """One urban feature layer, measured once against every unit.

    The whole declaration of a variable: what it is called in the code, in the
    figures and in the data, where it comes from, what it measures and how. The
    measurement reads its source through `path`, dispatches on `method` and
    checks `geometry` against the file, so this is the description the pipeline
    runs on rather than a description of it.
    """

    name: str  # canonical name: the value in the long table, the column in the wide one
    label: str  # short form, for figure axes where the canonical name is too long
    # The same short form in Spanish. The figures and tables of the body of the
    # thesis are read by a Colombian jury and are labelled in Spanish, so the
    # translation is part of the declaration rather than a lookup table kept
    # somewhere else and forgotten when a variable is added.
    label_es: str
    source_layer: str  # the layer as the delivered data names it, in Spanish
    source_file: str  # the file inside that layer's folder
    geometry: str
    method: str
    measures: str  # one line: what the number is, for the run log and the docs
    time_coverage: str
    # True where a unit of zero would mean the measurement failed rather than that
    # the feature is absent. An urban planning unit with no roadway is not a fact
    # about Bogotá. Reported loudly; never corrected automatically.
    zero_is_implausible: bool
    # Set only where the variable is measured on part of its layer. Defaulted so
    # that the nine variables measured whole say nothing about a rule they do not
    # have, and the one that has a rule states it.
    source_filter: SourceFilter | None = None

    def __post_init__(self) -> None:
        """Reject a declaration that contradicts itself, at import time.

        Cheap and worth doing here: an inconsistent entry then fails before any
        layer is read, rather than half way through a run that has already spent
        minutes on the layers declared correctly.
        """
        if self.geometry not in GEOMETRY_FOLDERS:
            raise ValueError(f"{self.name}: unknown geometry {self.geometry!r}")
        if self.method not in MEASUREMENT_METHODS:
            raise ValueError(f"{self.name}: unknown measurement method {self.method!r}")
        if self.time_coverage not in TIME_COVERAGES:
            raise ValueError(f"{self.name}: unknown time coverage {self.time_coverage!r}")
        if self.measurement.geometry != self.geometry:
            raise ValueError(
                f"{self.name}: method {self.method!r} measures {self.measurement.geometry} "
                f"geometry, but the layer is declared as {self.geometry}"
            )

    @property
    def path(self) -> Path:
        """Where the source file is, built from the declared layer and geometry."""
        return PREDICTORS_DIR / GEOMETRY_FOLDERS[self.geometry] / self.source_layer / self.source_file

    @property
    def family(self) -> str:
        """The geometry as the exported tables label it."""
        return GEOMETRY_FAMILIES[self.geometry]

    @property
    def measurement(self) -> MeasurementMethod:
        """The method that measures this variable, with its units and its sentence."""
        return MEASUREMENT_METHODS[self.method]

    @property
    def measure_unit(self) -> str:
        return self.measurement.measure_unit

    @property
    def value_unit(self) -> str:
        return self.measurement.value_unit

    @property
    def computation(self) -> str:
        return self.measurement.computation

    @property
    def filter_description(self) -> str:
        """The selection rule as one line, or a statement that there is none.

        Never blank: a reader of the dictionary has to be able to tell a variable
        measured on its whole layer from one measured on part of it, and an empty
        cell would leave the two looking the same.
        """
        if self.source_filter is None:
            return "none: the whole layer is measured"
        return self.source_filter.description


# Order is fixed here rather than taken from a directory listing, so the wide
# table, the correlation matrix and the figures come out in the same order on
# every run and two runs can be diffed line by line. Areas first, then points.
STATIC_PREDICTORS: tuple[StaticPredictor, ...] = (
    StaticPredictor(
        name="SIDEWALK_AREA_SHARE",
        label="Sidewalk",
        label_es="Andén",
        source_layer="andenes_x_localidad",
        source_file="andenes_x_localidad.shp",
        geometry=AREA_GEOMETRY,
        method=AREA_SHARE_METHOD,
        measures="share of the unit covered by sidewalk surface",
        time_coverage=SNAPSHOT_COVERAGE,
        # A unit with no sidewalk at all would mean the layer did not reach it.
        zero_is_implausible=True,
    ),
    StaticPredictor(
        name="ARTERIAL_ROAD_AREA_SHARE",
        label="Arterial road",
        label_es="Vía arterial",
        source_layer="avenidas_corregidas",
        source_file="avenidas_corregidas.shp",
        geometry=AREA_GEOMETRY,
        method=AREA_SHARE_METHOD,
        measures="share of the unit covered by arterial road surface",
        time_coverage=SNAPSHOT_COVERAGE,
        # Every UPL is crossed by at least one arterial; none is small enough to
        # sit between them.
        zero_is_implausible=True,
    ),
    StaticPredictor(
        name="ROADWAY_AREA_SHARE",
        label="Roadway",
        label_es="Calzada",
        source_layer="calzada_x_localidad",
        source_file="calzada_x_localidad.shp",
        geometry=AREA_GEOMETRY,
        method=AREA_SHARE_METHOD,
        measures="share of the unit covered by carriageway surface",
        time_coverage=SNAPSHOT_COVERAGE,
        # The clearest case of the three: a unit with no carriageway is not a
        # place, it is a failed intersection.
        zero_is_implausible=True,
    ),
    StaticPredictor(
        name="URBAN_PARK_AREA_SHARE",
        label="Urban park",
        label_es="Parque urbano",
        source_layer="parques_urb",
        source_file="parques_urb.shp",
        geometry=AREA_GEOMETRY,
        method=AREA_SHARE_METHOD,
        measures="share of the unit covered by urban park",
        time_coverage=SNAPSHOT_COVERAGE,
        # A unit with no park is unusual but perfectly possible.
        zero_is_implausible=False,
    ),
    StaticPredictor(
        name="BRIDGE_AREA_SHARE",
        label="Bridge",
        label_es="Puente",
        source_layer="puentes",
        source_file="puentes.shp",
        geometry=AREA_GEOMETRY,
        method=AREA_SHARE_METHOD,
        measures="share of the unit covered by bridge deck",
        time_coverage=SNAPSHOT_COVERAGE,
        zero_is_implausible=False,
    ),
    StaticPredictor(
        name="SITP_BUS_STOP_DENSITY",
        label="SITP bus stops",
        label_es="Paraderos SITP",
        source_layer="Paraderos_SITP",
        source_file="Paraderos_SITP.shp",
        geometry=POINT_GEOMETRY,
        method=POINT_DENSITY_METHOD,
        measures="SITP bus stops per square kilometre",
        time_coverage=SNAPSHOT_COVERAGE,
        zero_is_implausible=False,
    ),
    StaticPredictor(
        name="SIGNALISED_INTERSECTION_DENSITY",
        label="Signalised junctions",
        label_es="Semáforos",
        source_layer="Red_Semaforica",
        source_file="Red_Semaforica.shp",
        geometry=POINT_GEOMETRY,
        method=POINT_DENSITY_METHOD,
        measures="traffic-light controlled intersections per square kilometre",
        time_coverage=SNAPSHOT_COVERAGE,
        zero_is_implausible=False,
    ),
    StaticPredictor(
        name="PEDESTRIAN_CROSSING_DENSITY",
        label="Pedestrian crossings",
        label_es="Cruces peatonales",
        source_layer="crossings",
        source_file="crossings.shp",
        geometry=POINT_GEOMETRY,
        method=POINT_DENSITY_METHOD,
        measures="pedestrian crossings per square kilometre, extracted from OpenStreetMap",
        time_coverage=SNAPSHOT_COVERAGE,
        # Not a claim that every unit has crossings on the ground, but that an
        # OSM extraction returning none for a whole UPL is an extraction gap.
        zero_is_implausible=True,
    ),
    StaticPredictor(
        name="SPEED_CAMERA_DENSITY",
        label="Speed cameras",
        label_es="Cámaras",
        source_layer="camaras_salvavidas_bogota",
        source_file="Camaras_Salvavidas_Bogota.shp",
        geometry=POINT_GEOMETRY,
        method=POINT_DENSITY_METHOD,
        measures="speed enforcement cameras per square kilometre",
        time_coverage=SNAPSHOT_COVERAGE,
        # 92 cameras over 30 units: most units having none is the expected shape.
        zero_is_implausible=False,
    ),
    StaticPredictor(
        name="TRANSMILENIO_STATION_DENSITY",
        label="TransMilenio stations",
        label_es="TransMilenio",
        source_layer="estacion_localidad",
        source_file="estacion_localidad.shp",
        geometry=POINT_GEOMETRY,
        method=POINT_DENSITY_METHOD,
        measures="TransMilenio trunk stations per square kilometre",
        time_coverage=SNAPSHOT_COVERAGE,
        # The trunk network does not reach every unit, which is a fact about the
        # network rather than a gap in the layer.
        zero_is_implausible=False,
    ),
    # Last of the points and last of the list, because they arrived last.
    # Appending leaves every column of the wide table and every row of the
    # correlation matrix where it was, so a run made after these existed still
    # diffs line by line against one made before them.
    #
    # Three variables over one layer, and only the first enters the models. The
    # census records trees wherever they stand, and how much of it belongs in a
    # variable about streets depends on what the emplacement codes mean, which
    # the delivered layer does not say. Measuring all three and putting the
    # figures side by side is what lets that be decided on evidence rather than
    # on a reading of a code. The two variants follow the pattern parks,
    # carriageway and bridge deck already follow: measured on every run, out of
    # the model set, and there to be compared against.
    StaticPredictor(
        name="TREE_DENSITY",
        label="Trees, all",
        label_es="Arbolado completo",
        source_layer="arbolado_urbano",
        source_file="arbolado_urbano.shp",
        geometry=POINT_GEOMETRY,
        method=POINT_DENSITY_METHOD,
        measures="trees per square kilometre, the whole census",
        # Fecha_Actu is not a time series. It records when a tree was last
        # surveyed, and the 2005-2007 census stamps that date on trees of every
        # age, so the column dates the survey and not the tree. The layer is one
        # snapshot of uneven recency, which is a limitation of the variable and
        # not a series it could be resolved into. See D32.
        time_coverage=SNAPSHOT_COVERAGE,
        # 1.5 million trees over 30 units: a unit with none of them would mean
        # the census did not reach it, not that the unit has no trees.
        zero_is_implausible=True,
    ),
    StaticPredictor(
        name="TREE_DENSITY_WITHOUT_P1",
        label="Trees, without P1",
        label_es="Arbolado sin P1",
        source_layer="arbolado_urbano",
        source_file="arbolado_urbano.shp",
        geometry=POINT_GEOMETRY,
        method=POINT_DENSITY_METHOD,
        measures="trees per square kilometre, the census without the P1 emplacement",
        time_coverage=SNAPSHOT_COVERAGE,
        zero_is_implausible=True,
        source_filter=TREES_WITHOUT_PARK_FILTER,
    ),
    StaticPredictor(
        name="TREE_DENSITY_U_CODES",
        label="Trees, U codes",
        label_es="Arbolado códigos U",
        source_layer="arbolado_urbano",
        source_file="arbolado_urbano.shp",
        geometry=POINT_GEOMETRY,
        method=POINT_DENSITY_METHOD,
        measures="trees per square kilometre, only the fifteen U emplacement codes",
        time_coverage=SNAPSHOT_COVERAGE,
        # The narrowest of the three and the only one where a zero would be
        # plausible on the ground, since a unit could genuinely hold none of a
        # narrow code set. Left flagged anyway: at this scale it would still be
        # worth looking at.
        zero_is_implausible=True,
        source_filter=URBAN_TREES_FILTER,
    ),
)

STATIC_PREDICTOR_NAMES: tuple[str, ...] = tuple(p.name for p in STATIC_PREDICTORS)
STATIC_PREDICTORS_BY_NAME: dict[str, StaticPredictor] = {p.name: p for p in STATIC_PREDICTORS}


# -- which of them enter the models -----------------------------------------
# Measuring a layer and putting the variable in a model are two decisions, and
# they are kept apart on purpose: everything declared above is measured on every
# run, and the exclusions below take effect only where a model set is asked for.
# That is what makes it possible to answer why a variable was dropped, because
# the number that justifies dropping it is still in the same table as the ones
# that stayed. A variable removed from the measurement could not be defended.
@dataclass(frozen=True)
class PredictorExclusion:
    """One variable that is measured but kept out of the models, and why."""

    predictor: str
    reason: str


MODEL_EXCLUSIONS: tuple[PredictorExclusion, ...] = (
    PredictorExclusion(
        predictor="ROADWAY_AREA_SHARE",
        reason=(
            "correlates at 0.969 with SIDEWALK_AREA_SHARE, which is collinearity and not "
            "two measurements; the sidewalk variable is the one the study argues about"
        ),
    ),
    PredictorExclusion(
        predictor="BRIDGE_AREA_SHARE",
        reason="my advisor does not consider bridge deck relevant to casualty rates among vulnerable users",
    ),
    PredictorExclusion(
        predictor="URBAN_PARK_AREA_SHARE",
        reason=(
            "superseded by TREE_DENSITY, which carries the same argument about green "
            "surroundings through the mechanism the literature actually measures; the two "
            "are only weakly related, so this is a choice of construct and not of "
            "collinearity (D32)"
        ),
    ),
    PredictorExclusion(
        predictor="TREE_DENSITY_WITHOUT_P1",
        reason=(
            "a variant of TREE_DENSITY built on one emplacement code, measured so the three "
            "criteria can be compared on their figures; only one of the three enters (D32)"
        ),
    ),
    PredictorExclusion(
        predictor="TREE_DENSITY_U_CODES",
        reason=(
            "a variant of TREE_DENSITY built on the fifteen U emplacement codes, measured so "
            "the three criteria can be compared on their figures; only one of the three "
            "enters (D32)"
        ),
    ),
)

MODEL_EXCLUSION_REASONS: dict[str, str] = {e.predictor: e.reason for e in MODEL_EXCLUSIONS}

# Checked here rather than trusted: an exclusion naming a variable that does not
# exist would silently exclude nothing, and the model set would quietly grow by
# one without anybody noticing.
for _excluded in MODEL_EXCLUSION_REASONS:
    if _excluded not in STATIC_PREDICTORS_BY_NAME:
        raise ValueError(f"model exclusion names {_excluded!r}, which is not a declared predictor")

# The order is the declared order with the excluded ones taken out, so the model
# set reads down the same list as everything else.
MODEL_PREDICTOR_NAMES: tuple[str, ...] = tuple(
    name for name in STATIC_PREDICTOR_NAMES if name not in MODEL_EXCLUSION_REASONS
)
MODEL_PREDICTORS: tuple[StaticPredictor, ...] = tuple(
    STATIC_PREDICTORS_BY_NAME[name] for name in MODEL_PREDICTOR_NAMES
)

# Whether a variable is in the model set is a column of the exported dictionary,
# with the reason beside it, so the table answers the question on its own.
IN_MODEL_COL = "IN_MODEL_SET"
MODEL_EXCLUSION_REASON_COL = "MODEL_EXCLUSION_REASON"
SOURCE_FILTER_COL = "SOURCE_FILTER"
FIGURE_SETS_COL = "FIGURE_SETS"


# -- which of them appear in the figures -------------------------------------
# Measuring a variable, putting it in a model and drawing it are three separate
# decisions, and this is the third. Everything declared above is measured and
# exported on every run whatever happens here; the figures are a narrower thing,
# because a figure has a reader and a reader has to be able to tell what the
# picture is claiming.
#
# Two variables are measured but never drawn. They are alternative counts of the
# tree census, kept because they are the evidence for choosing the whole census
# over a subset of it (D32), and that evidence lives in the data tables where it
# can be quoted. In a figure they would be three tree columns side by side, three
# of which are the same layer, and every reader would spend their attention
# working out which one counts. The answer to "why the whole census" is a
# paragraph and a table, not a column in a heat map.
FIGURE_EXCLUSIONS: tuple[PredictorExclusion, ...] = (
    PredictorExclusion(
        predictor="TREE_DENSITY_WITHOUT_P1",
        reason=(
            "an alternative count of the same census as TREE_DENSITY; it stays in the data "
            "tables as the evidence behind D32 and would only crowd a figure"
        ),
    ),
    PredictorExclusion(
        predictor="TREE_DENSITY_U_CODES",
        reason=(
            "an alternative count of the same census as TREE_DENSITY; it stays in the data "
            "tables as the evidence behind D32 and would only crowd a figure"
        ),
    ),
)

FIGURE_EXCLUSION_REASONS: dict[str, str] = {e.predictor: e.reason for e in FIGURE_EXCLUSIONS}

for _excluded in FIGURE_EXCLUSION_REASONS:
    if _excluded not in STATIC_PREDICTORS_BY_NAME:
        raise ValueError(f"figure exclusion names {_excluded!r}, which is not a declared predictor")


@dataclass(frozen=True)
class FigureSet:
    """One set of variables the predictor figures are drawn for.

    The figures come in sets rather than in one run because they answer to two
    different readers. Both sets are produced on every run, from the same tables,
    and nothing but the list of columns differs between them.
    """

    name: str  # the suffix every folder and every file of the set carries
    label: str  # how the set names itself in a figure title
    purpose: str  # one line: who reads this set and what for
    predictor_names: tuple[str, ...]

    def __post_init__(self) -> None:
        unknown = [name for name in self.predictor_names if name not in STATIC_PREDICTORS_BY_NAME]
        if unknown:
            raise ValueError(f"figure set {self.name!r} names undeclared predictors: {', '.join(unknown)}")
        if not self.predictor_names:
            raise ValueError(f"figure set {self.name!r} has no variables in it")

    @property
    def folder(self) -> str:
        """The subdirectory this set's figures are written to."""
        return f"{PREDICTORS_FIGURES_SUBDIR}__{self.name}"

    @property
    def predictors(self) -> tuple[StaticPredictor, ...]:
        return tuple(STATIC_PREDICTORS_BY_NAME[name] for name in self.predictor_names)


# Everything measured except the two alternative counts of the tree census.
COMPLETE_FIGURE_PREDICTOR_NAMES: tuple[str, ...] = tuple(
    name for name in STATIC_PREDICTOR_NAMES if name not in FIGURE_EXCLUSION_REASONS
)

# Both sets are drawn on every run. The complete one is the evidence and the
# model one is what the documents print, and each would be misleading without the
# other: the model set cannot show why carriageway was dropped, because the 0.969
# against sidewalk that justifies dropping it only exists in a matrix that still
# has carriageway in it.
FIGURE_SETS: tuple[FigureSet, ...] = (
    FigureSet(
        name="complete",
        label="every measured variable",
        purpose=(
            "the backing evidence: it holds the variables the model set excludes, so the "
            "reason each was excluded can be read off the figure that excluded it"
        ),
        predictor_names=COMPLETE_FIGURE_PREDICTOR_NAMES,
    ),
    FigureSet(
        name="model",
        label="the variables that enter the models",
        purpose="what the deliverables print: the specification the study actually estimates",
        predictor_names=MODEL_PREDICTOR_NAMES,
    ),
)

FIGURE_SETS_BY_NAME: dict[str, FigureSet] = {figure_set.name: figure_set for figure_set in FIGURE_SETS}

# Columns of the predictor tables. Scale, unit and year deliberately reuse the
# names and the values of the matrix and rho tables, because the dashboard joins
# all three on them.
PREDICTOR_COL = "PREDICTOR"
PREDICTOR_FAMILY_COL = "PREDICTOR_FAMILY"
PREDICTOR_MEASURE_COL = "MEASURE"  # raw magnitude: km2 of surface, or number of points
PREDICTOR_MEASURE_UNIT_COL = "MEASURE_UNIT"
PREDICTOR_VALUE_COL = "VALUE"  # the magnitude normalised by the area of the unit
PREDICTOR_VALUE_UNIT_COL = "VALUE_UNIT"
PREDICTOR_STATUS_COL = "VALUE_STATUS"
AREA_UNIT_KM2_COL = "AREA_UNIT_KM2"

# Columns of the exported data dictionary. PREDICTOR, PREDICTOR_FAMILY and the
# two unit columns are the same names carrying the same values as in the tables
# above, so the dictionary joins to the measurements on the variable name.
PREDICTOR_LABEL_COL = "PREDICTOR_LABEL"
SOURCE_LAYER_COL = "SOURCE_LAYER"
SOURCE_FILE_COL = "SOURCE_FILE"
SOURCE_PATH_COL = "SOURCE_PATH"
GEOMETRY_COL = "GEOMETRY"
MEASURES_COL = "MEASURES"
COMPUTATION_COL = "COMPUTATION"
TIME_COVERAGE_COL = "TIME_COVERAGE"
ZERO_IMPLAUSIBLE_COL = "ZERO_IS_IMPLAUSIBLE"

# A cell is MEASURED when the unit was measured, whatever came out — a unit with
# no bridge is a valid observation of zero. NOT_MEASURED is for a unit the
# computation could not reach at all, which must never be read as a zero. The two
# are indistinguishable in the legacy output, where an absent row means either.
MEASURED_STATUS = "MEASURED"
NOT_MEASURED_STATUS = "NOT_MEASURED"


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
FIGURE_DPI = 150
HEATMAP_COLORMAP = "viridis"
# Cells with no observation at all are drawn in this colour instead of the bottom
# of the colour ramp, so that a true zero cannot be mistaken for a small value on
# a logarithmic scale.
HEATMAP_EMPTY_COLOR = "#eeeeee"

# ---------------------------------------------------------------------------
# Tables compiled as LaTeX rather than drawn
# ---------------------------------------------------------------------------
# The casualty matrices and the correlation of the model set go into the
# deliverables as native tables, never as an image: a table projected on a screen
# stays legible at any size, keeps its text selectable, takes the typeface of the
# document it lands in, and is corrected by changing one figure in the source. A
# screenshot has to be redrawn whole every time a number moves, and the numbers
# move on every run.
#
# Emitting them here rather than typing them into the document is the same
# argument one step further. A number copied by hand is a number that can be
# copied wrongly, and there is no way to tell afterwards which run it came from.
LATEX_TABLE_SUFFIX = ".tex"

# Shading runs from nothing to this share of the colour and never past it. The
# ceiling is legibility, not statistics: above roughly this point black text stops
# reading when projected, and turning the text white does not rescue the cell,
# because the accent colour never gets dark enough to carry white text well.
# Because the ceiling is fixed rather than taken from the data, the rule means the
# same thing in a table of counts and in a divergent one where a large negative
# value is as dark as a large positive one.
LATEX_SHADE_CEILING = 70

LATEX_POSITIVE_COLOR = "ColorEnfasis"  # the accent of the template
LATEX_NEGATIVE_COLOR = "ColorAlrt"  # its counterpart, for the negative half
LATEX_LABEL_COLOR = "ColorNav"  # headers and stubs
LATEX_DIAGONAL_COLOR = "black!35"  # the diagonal, which says nothing and should not draw the eye

# Counts span four orders of magnitude, so shading them in proportion would leave
# every cell but a handful indistinguishable from white. The square root spreads
# the small values apart while keeping the order intact, which is what the shading
# is for: it ranks cells, and the figure printed in the cell gives the magnitude.
LATEX_COUNT_SHADE_EXPONENT = 0.5

# Bold marks the pairs at or above CORRELATION_HIGH_THRESHOLD, and it is the only
# thing that does. Keeping it apart from the shading matters: the shading is a
# legibility ramp with a fixed ceiling and the bold is the statistical statement,
# so sharing one threshold between them would make each answer the other's
# question.
LATEX_CORRELATION_DECIMALS = 2

# Pictograms instead of words, as the template's example matrix does: six row
# labels and seven column labels of text would not fit at a legible size, and the
# actor types are exactly the set that has conventional icons.
LATEX_ACTOR_ICONS: dict[str, str] = {
    PEDESTRIAN: r"\faWalking",
    BICYCLE: r"\faBicycle",
    MOTORCYCLE: r"\faMotorcycle",
    CAR: r"\faCar",
    PUBLIC_TRANSPORT: r"\faBus",
    OTHER: r"\faEllipsisH",
    SELF_COUNTERPART: r"\faUndo",
}

# The two matrices the deliverables show, and what each one adds up. Persons is
# the only place in the pipeline where injured and killed are summed, and it is
# done here, at the edge, so the tables stay separate everywhere else.
LATEX_MATRIX_TABLES: dict[str, tuple[tuple[str, ...], str]] = {
    "persons": (("injured", "killed"), "Personas afectadas: heridos y muertos."),
    "parties": (("parties",), "Partes afectadas."),
}

# Each dataset names itself in the file name. The observed set is not left unnamed
# the way it is in the CSV exports: those keep the names they have always had so
# that the dashboard does not break, but nothing yet reads these, and two files
# about to sit side by side in a presentation must not be told apart by which one
# lacks a suffix.
LATEX_DATASET_SUFFIXES: dict[str, str] = {
    OBSERVED_DATASET: "observed",
    CORRECTED_DATASET: CORRECTION_FILE_SUFFIX,
}

# rho figures are small multiples: one panel per pair for the city, one panel per
# unit for a given pair. Each panel therefore draws one series and, where it
# helps, one reference — so identity never rests on telling nine hues apart,
# which is not something a reader should be asked to do.
#
# Every point of a series is drawn identically. The only gap in a line is a year
# with no crash of that pair, where rho does not exist.
RHO_SERIES_COLOR = "#1b6ca8"
RHO_REFERENCE_COLOR = "#9e9e9e"
RHO_GRID_COLOR = "#e3e3e3"

# -- the map of the territorial units ---------------------------------------
# D24 kept maps out of the pipeline, on the grounds that a map brings its own
# decisions about classification and colour and those had nowhere to be settled.
# D26 reverses that: the decisions are settled here, and the reason is that both
# documents need the reader to see the geography before any result means
# anything. Drawn from the same layer every other stage reads, so the figure
# shows the study universe by construction rather than because someone filtered
# a second copy correctly.
#
# It is a reference map, not a thematic one. It shows the shape of the territory
# and how it is divided, and the fill carries no information at all: it says
# only that this unit is not that one. Everything below follows from that.
MAP_FIGURES_SUBDIR = "map"

# Vector, unlike every other figure the pipeline writes. The others are dense
# with text and marks that a raster at 150 dpi renders adequately; this one is
# projected on a wall and is almost all edges, and edges are what rasterising
# ruins.
MAP_FIGURE_FORMAT = "pdf"
MAP_FIGURE_HEIGHT_IN = 5.0  # width follows from the footprint of the city

# Two polygons are neighbours if their boundaries come within this distance, in
# the metric CRS. Exact touching would be the right test on a topologically
# clean layer; a metre of tolerance costs nothing and survives the slivers a
# layer digitised from several sources tends to carry.
MAP_ADJACENCY_TOLERANCE_M = 1.0

# The four colour theorem: four are enough for no two units sharing a border to
# share a colour, and on a reference map the convention is to use the fewest
# colours rather than the most. Thirty would be a qualitative palette used for
# something that is not categorical data, and thirty hues that mean nothing are
# thirty hues of noise.
#
# ColorBrewer Pastel2, which is the pastel form of Set2, the qualitative scheme
# in that family built to survive colour blindness. Six entries are declared for
# the two the heuristic might need beyond four; the run reports how many it
# actually used. Nothing here is saturated, because the map is background.
MAP_PALETTE = ("#b3e2cd", "#fdcdac", "#cbd5e8", "#f4cae4", "#e6f5c9", "#fff2ae")

# One colour for every border and a hairline width. With the fill doing the
# separating there is nothing left for the stroke to do, so it gets out of the
# way; the previous version had it carrying the work and needed two colours and
# three times the width to do it.
MAP_BOUNDARY_COLOR = "#7c8288"
MAP_BOUNDARY_WIDTH = 0.5

# The identifying number inside each unit, without the UPL prefix and without a
# leading zero. Not padded on purpose: the narrowest unit is 6.52 km2 and the
# label has to fit inside it, so a character that carries no information is a
# character that does not go in. The run checks that every label fits inside its
# own polygon and names the ones that do not.
# The size is the largest the geometry allows, not a matter of taste. The fit
# test compares a text box with a polygon in data coordinates, so it depends on
# the ratio of font to figure and not on either alone, which means the largest
# font that fits is also the largest the number will be once a document scales
# the figure down. On this layer that ceiling is between 7 and 8 points against
# a five inch figure: 8 puts three labels over their own borders.
MAP_LABEL_COLOR = "#2b2f33"
MAP_LABEL_FONT_PT = 7.0

# The label sits at the pole of inaccessibility: the interior point furthest
# from the boundary. Both it and representative_point are guaranteed to land
# inside the polygon, which is what rules the centroid out, but only this one
# also asks for room around itself, and room is what a label needs.
#
# On this layer the difference decides the figure. representative_point leaves
# as little as 438 m of clearance, on a unit shaped like an L where it lands in
# the neck; the pole never drops below 932 m. At 6.5pt that is five labels
# spilling over their own borders against none.
#
# The tolerance is how precisely the pole is located. Ten metres on a city
# 23 km across is far below anything the eye resolves, and asking for less only
# spends iterations.
MAP_LABEL_ANCHOR_TOLERANCE_M = 10.0

# Where the north arrow and the scale bar sit. Both come from libraries rather
# than being drawn by hand: matplotlib-map-utils for the arrow, which is what
# the GeoPandas documentation points at, and matplotlib-scalebar for the bar,
# which needs a projected CRS to state a real distance and therefore fixes the
# CRS the map is drawn in.
#
# Both are drawn in the colour of the labels and nothing else, with the arrow's
# two-tone form and drop shadow turned off. They orient the reader and are not
# the subject: the default arrow is a black and white figure with a heavy N and
# it ends up the loudest thing on a map whose whole job is to sit quietly.
# The arrow goes upper left. Bogotá's footprint leans to the north east, so the
# upper right corner is over the city and the arrow sat on top of Torca; the
# upper left is empty at that latitude.
MAP_NORTH_ARROW_LOCATION = "upper left"
MAP_NORTH_ARROW_SCALE = 0.22

# The scale bar is drawn in a second copy of the figure rather than in the only
# one. A map reproduced at the width of a page can carry it and one shrunk into
# a slide cannot: at that size the bar's own label falls below anything a
# projector resolves, and it earns its place by supporting a claim about
# distance, which the slide does not make. Both files come out of every run, so
# switching between them is a matter of which one a document includes and never
# of editing this line and running again.
MAP_SCALEBAR_LOCATION = "lower right"
MAP_SCALEBAR_LENGTH_FRACTION = 0.32
MAP_SCALEBAR_SUFFIX = "__scalebar"

# -- predictor histograms ---------------------------------------------------
# With thirty observations the choice of bins decides a good deal of what the
# histogram looks like, so it is declared here rather than left to the plotting
# library, and the same rule applies to all ten figures.
#
# The rule: bin edges fall on round numbers. The width of a bin is a step taken
# from the 1-2-2.5-5 ladder scaled to the magnitude of the variable — 0.02,
# 0.25, 5, 50 — and the edges are the multiples of that step that cover the
# observed range. The step chosen is the one whose bin count comes closest to
# six, among those that stay inside HISTOGRAM_BIN_COUNT_LIMITS; ties go to the
# finer step, which shows more of the shape.
#
# Round edges are not cosmetic. The axis of a histogram is labelled at round
# values whatever the bars do, so edges at 0.098 and 0.197 put every bar between
# two labels and leave the reader interpolating to find out what a bar covers.
# With this rule the ticks *are* the edges, so a bar starts and ends on a printed
# number and the range it counts can be read off directly.
#
# Six is still the target, for the reason Sturges' rule was picked to give it:
# thirty observations over six bins averages five per bin, and finer binning at
# this n produces a comb of ones and zeros that reads as structure where there is
# only sampling. What changed is that six is now a target rather than a result —
# rounding the edges means the count lands between four and ten depending on how
# the range of a variable sits against the ladder.
#
# Bins are equal width and the ladder is the same for every variable, so the ten
# figures are still drawn to one rule and can be read against each other. This is
# not the data-dependent binning D23 rejects: Freedman-Diaconis sets the width
# from the spread of the data, while here only the *magnitude* of the variable
# picks a rung of a fixed ladder.
HISTOGRAM_BIN_RULE = "round edges: 1-2-2.5-5 step, targeting 6 bins"
HISTOGRAM_TARGET_BIN_COUNT = 6
HISTOGRAM_BIN_COUNT_LIMITS = (4, 10)  # inclusive; outside this the step is rejected
HISTOGRAM_STEP_MANTISSAS = (1.0, 2.0, 2.5, 5.0)
HISTOGRAM_BAR_COLOR = "#1b6ca8"
HISTOGRAM_BAR_EDGE_COLOR = "#ffffff"

# A bin with no unit in it is drawn as a hatched stub of this height, measured as
# a fraction of the tallest bar, instead of being left blank. A blank bin and a
# bin outside the axis look the same, and the empty bins are findings here: the
# gap between the park-poor units and the three park-rich ones is the shape of
# that variable, not a defect of the figure.
HISTOGRAM_EMPTY_BIN_COLOR = "#c9d6e0"
HISTOGRAM_EMPTY_BIN_STUB_FRACTION = 0.025


def histogram_bin_step(low: float, high: float) -> float:
    """Width of a histogram bin covering [low, high], from the declared ladder.

    Every rung of the ladder is tried; the ones whose bin count falls outside the
    limits are discarded, and of the rest the count nearest the target wins. A
    tie is broken towards the finer step: two candidates equally far from six
    bins are equally defensible, and the one with more bins hides less.
    """
    span = high - low
    if span <= 0 or not math.isfinite(span):
        raise ValueError(f"a histogram needs a positive finite range, got [{low}, {high}]")

    # Five decades around the span cover every rung that could possibly produce a
    # bin count in range, from far too fine to far too coarse.
    lowest_exponent = math.floor(math.log10(span)) - 2
    ladder = sorted(
        mantissa * 10.0**exponent
        for exponent in range(lowest_exponent, lowest_exponent + 5)
        for mantissa in HISTOGRAM_STEP_MANTISSAS
    )

    minimum_bins, maximum_bins = HISTOGRAM_BIN_COUNT_LIMITS
    best_step: float | None = None
    best_key: tuple[int, float] | None = None
    for step in ladder:
        bins = len(histogram_bin_edges(low, high, step)) - 1
        if not minimum_bins <= bins <= maximum_bins:
            continue
        key = (abs(bins - HISTOGRAM_TARGET_BIN_COUNT), step)
        if best_key is None or key < best_key:
            best_key, best_step = key, step

    # No rung fits only if the limits are set to an impossible window; falling
    # back to equal parts of the range keeps a figure on the page rather than
    # failing the run over a plotting parameter.
    return best_step if best_step is not None else span / HISTOGRAM_TARGET_BIN_COUNT


def histogram_bin_edges(low: float, high: float, step: float) -> tuple[float, ...]:
    """Multiples of `step` covering [low, high], rounded to kill float noise.

    Edges are computed as integer multiples and then rounded, because 3 * 0.1
    lands at 0.30000000000000004 and an axis labelled with that is worse than no
    axis at all.
    """
    first = math.floor(low / step)
    last = math.ceil(high / step)
    if last == first:  # the range sits exactly on one multiple
        last += 1
    decimals = max(0, -math.floor(math.log10(step)) + 1)
    return tuple(round((first + index) * step, decimals) for index in range(last - first + 1))


def predictor_decimals(magnitude: float) -> int:
    """Decimals that keep about three significant digits at `magnitude`.

    The ten variables span four orders of magnitude, from bridge deck at 0.0001
    of a unit to 355 crossings per km2. One decimal count for all of them either
    prints 355.3447 or rounds bridge deck to 0.00. This picks the count from the
    top of each variable's own range, which is what makes a table of three
    hundred numbers readable.
    """
    if not math.isfinite(magnitude) or magnitude <= 0:
        return 2
    if magnitude >= 100:
        return 0
    if magnitude >= 10:
        return 1
    if magnitude >= 1:
        return 2
    if magnitude >= 0.1:
        return 3
    return 4


# -- predictor correlation matrix -------------------------------------------
# Diverging and centred on zero, because the sign of a correlation matters as
# much as its magnitude: two variables that move against each other and two that
# move together must not land on similar colours.
CORRELATION_METHOD = "pearson"
CORRELATION_COLORMAP = "RdBu_r"

# Pairs above this in absolute value are named in the report. Two variables that
# correlate this strongly measure close to the same thing, and putting both into
# the same model is what this number exists to prevent. It is a reporting
# threshold: nothing is dropped from any table because of it.
CORRELATION_HIGH_THRESHOLD = 0.7

# -- predictor master table -------------------------------------------------
# The thirty units against the ten variables, every cell printed and coloured.
# The colour of a cell is computed inside its own column, from that variable's
# minimum to its maximum, because the ten variables are not on one scale: a
# global ramp would paint every share of a unit at the bottom of the ramp and
# every crossing density at the top, and the figure would show nothing but which
# family a column belongs to.
#
# This is the opposite of D12's rule for the casualty heatmaps, where one scale
# is shared precisely so cells can be compared across the figure. The two figures
# are answering different questions, and the danger here is a reader carrying
# D12's habit over: hence the note printed on the figure itself, and the per
# column range printed under each column, which says what the darkest cell means
# in that column and nowhere else.
#
# A single-hue sequential ramp, deliberately not the viridis of the casualty
# heatmaps and not the diverging ramp of the correlation matrix, so the figure
# does not look like either at a glance.
MASTER_TABLE_COLORMAP = "Blues"
# Fraction of a column's range above which the printed value switches to white.
MASTER_TABLE_LIGHT_TEXT_ABOVE = 0.62
# Where a whole column is flat, every cell sits at this point of the ramp: a
# constant variable has no high or low, and painting it all white or all dark
# would suggest one.
MASTER_TABLE_FLAT_COLUMN_POSITION = 0.5

# The technical name printed under the readable one on the axes of the
# correlation matrix and the master table. It is the column name in the exported
# tables, so anyone reading a figure can go straight to the right column of the
# CSV instead of guessing which label became which name.
FIGURE_TECHNICAL_LABEL_COLOR = "#6b6b6b"
FIGURE_TECHNICAL_LABEL_SIZE = 6.0
FIGURE_READABLE_LABEL_SIZE = 9.0


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
# A loading count depends on two things, and the baselines are indexed by both.
#
#   * Which EXTRACT of the sources the run reads. Replacing 2024 with the updated
#     extract moves five of the six counts; only the vehicle table is untouched.
#   * Which SCALE it runs on, for the two counts that measure how many records
#     fall outside every polygon, since two layers covering different territory
#     disagree on them by construction.
#
# Three sets of numbers therefore live here, and they say different things:
#
#   LEGACY_BASELINE_COUNTS is a *historical contrast*, measured on the real
#   execution of the legacy notebook (docs/auditoria/auditoria_02_balance.md),
#   which ran at LOCALITY scale on the ORIGINAL extract. It is the evidence that
#   the reimplementation reproduced the pipeline it replaces. It is kept for that
#   reason alone and is never a target for any other extract or scale.
#
#   SOURCE_BASELINE_COUNTS holds the counts that come from the source files
#   themselves, per extract. No territorial layer can move them.
#
#   SCALE_BASELINE_COUNTS holds the counts that depend on the footprint of the
#   unit layer, per extract and scale.
#
# The last two are the *live reference*: what a run is actually verified against.
# The original extract has no entry in either, on purpose — there its numbers are
# the legacy ones, and repeating them would be one value in two places, free to
# drift apart with nothing to notice.
LEGACY_BASELINE_COUNTS: dict[str, int] = {
    "fatalities": 8_548,
    "injuries": 261_293,
    "concatenated": 269_841,
    "fatalities_without_area": 61,
    "injuries_without_area": 1_344,
    "vehicles": 1_465_735,
}

# The scale and the extract the legacy figures above were measured on. Outside
# either, they are not comparable and are not used.
LEGACY_BASELINE_SCALE = "locality"

# Which extract a run reads. Follows the switch above, so the baselines cannot be
# checked against the wrong extract by forgetting to change a second setting.
ORIGINAL_EXTRACT = "original extract"
UPDATED_2024_EXTRACT = f"{REPLACED_YEAR} updated extract"
LEGACY_BASELINE_EXTRACT = ORIGINAL_EXTRACT

ACTIVE_EXTRACT = UPDATED_2024_EXTRACT if USE_UPDATED_2024 else ORIGINAL_EXTRACT

# Counts that no territorial layer can change: they are properties of the source
# files themselves, so they must reproduce the legacy figures exactly whatever
# scale is active. A mismatch here means a bug, not a number to be adjusted.
SCALE_INDEPENDENT_CHECKS = ("fatalities", "injuries", "concatenated", "vehicles")

# Counts that depend on the footprint of the unit layer, because they count the
# records that fall outside every polygon. Two layers covering different
# territory necessarily disagree on them, so they are checked against the
# baseline of the active scale — never across scales.
SCALE_DEPENDENT_CHECKS = ("fatalities_without_area", "injuries_without_area")

# Counts that come from the source files, per extract. Measured on this
# implementation. The original extract is absent because there they are the
# legacy figures above.
SOURCE_BASELINE_COUNTS: dict[str, dict[str, int]] = {
    UPDATED_2024_EXTRACT: {
        # 8,548 - 555 + 599: the 2024 rows of the original extract leave, the
        # 2024 rows of the updated one enter.
        "fatalities": 8_592,
        # 261,293 - 15,039 + 22,667. The big move: the original injury layer
        # stops in mid-September 2024.
        "injuries": 268_921,
        "concatenated": 277_513,
        # Untouched. The update carries no vehicle table of its own, and the one
        # on disk already covers 99.5% of its crashes.
        "vehicles": 1_465_735,
    },
}

# Footprint-dependent counts per extract and scale, measured on this
# implementation. A combination with no entry here has no baseline yet: the run
# reports its figures as a first measurement instead of failing, and they belong
# in this table afterwards.
SCALE_BASELINE_COUNTS: dict[str, dict[str, dict[str, int]]] = {
    ORIGINAL_EXTRACT: {
        # Measured on the UPL layer, whose footprint is not the union of the
        # localities, so these are lower than the legacy figures rather than a
        # correction of them. Kept as the reference of the extract they belong
        # to, so reverting the integration reverts to a checked baseline too.
        "upl": {
            "fatalities_without_area": 50,
            "injuries_without_area": 1_186,
        },
    },
    UPDATED_2024_EXTRACT: {
        # The live reference of the study. Up from 50 and 1,186 on the original
        # extract: the updated 2024 carries four more months of records, and five
        # of its rows moved outside every unit when their geometry changed.
        "upl": {
            "fatalities_without_area": 51,
            "injuries_without_area": 1_224,
        },
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
