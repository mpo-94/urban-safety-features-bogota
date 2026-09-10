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
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Base directories
# ---------------------------------------------------------------------------
# Paths are anchored to the repository root so the pipeline behaves the same
# whether it is launched from the root, from src/, or from a notebook.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

# -- one root per role the data plays ---------------------------------------
# Every source path in this file is built from one of these and never from
# another role's root. The roles are the study's own vocabulary — cartography,
# casualties, predictors, exposure, population — so a path says what its file is
# for before anyone opens it.
#
# Two of them point at the same folder today, and that is the point of declaring
# them apart. The desire lines were delivered inside the bundle of predictor
# layers, which is a fact about the delivery and not about the data: exposure is
# not a predictor (D35), and a path that reached it through PREDICTORS_DIR said
# the opposite of what the rest of the pipeline takes care to say. Separating the
# declaration costs nothing now and makes moving the files a one-line change.
CARTOGRAPHY_DIR = DATA_DIR / "geo"
CASUALTIES_DIR = DATA_DIR / "data_siniestros_bogota"
PREDICTORS_DIR = DATA_DIR / "shp_properties_sorted"
EXPOSURE_DIR = DATA_DIR / "shp_properties_sorted"
POPULATION_DIR = DATA_DIR / "population"

# Deliveries not yet merged into the sources above, and what is rebuilt from
# them. These two are the one place under data/ that is not raw: `integrated`
# holds what the `integrate` route writes, and it is there rather than under
# results/ because every other route reads it as an input.
INCOMING_DIR = DATA_DIR / "incoming"
INTEGRATED_DIR = DATA_DIR / "integrated"


def resolve_source_path(declared: Path) -> Path:
    """The delivered file, found even where its name is spelled decomposed.

    The desire lines arrive in a folder called "Líneas de deseo Matriz Origen
    Destino", and the filesystem stores that í as an i followed by a combining
    acute, while a Python source file spells it as the single precomposed
    character. The two are one name to a reader and two different byte strings to
    `exists`, so a path copied faithfully out of the delivered data can be right
    and still not open.

    The alternative — pasting decomposed characters into the declarations — hides
    the problem in a character nobody can see and invites the next reader to
    "correct" it back. So the lookup is made insensitive to that difference and to
    nothing else: case, spacing and every other character still have to match, and
    an ambiguous match is an error rather than a guess.

    Only the four line layers with accented names need this today. It is applied
    to every source path anyway, because a rule that runs on one path and not the
    others is a rule waiting to be forgotten.
    """
    if declared.exists():
        return declared

    parts = declared.parts
    resolved = Path(parts[0])
    for part in parts[1:]:
        candidate = resolved / part
        if candidate.exists():
            resolved = candidate
            continue

        wanted = unicodedata.normalize("NFC", part)
        siblings = sorted(resolved.iterdir()) if resolved.is_dir() else []
        matches = [
            entry for entry in siblings if unicodedata.normalize("NFC", entry.name) == wanted
        ]
        if len(matches) != 1:
            found = "nothing" if not matches else f"{len(matches)} entries"
            raise FileNotFoundError(
                f"{declared} does not exist: looking for {part!r} inside {resolved}, "
                f"exact match failed and normalising the accents matched {found}"
            )
        resolved = matches[0]
    return resolved

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
RAW_FATALITIES_PATH = CASUALTIES_DIR / "MUERTO" / "MUERTO.shp"
RAW_INJURIES_PATH = CASUALTIES_DIR / "LESIONADO" / "LESIONADO.shp"
VEHICLES_PATH = CASUALTIES_DIR / "vehiculo.csv"

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
INCOMING_2024_PATH = INCOMING_DIR / "afectados_2024.csv"
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
        shapefile=CARTOGRAPHY_DIR / "bog_loc_urbanarea" / "bog_loc_urbanarea.shp",
        code_column="Identifica",
        name_column="Nombre_de_",
        expected_units=19,
    ),
    "upz": TerritorialScale(
        key="upz",
        label="UPZ",
        shapefile=CARTOGRAPHY_DIR / "bog_upz" / "bog_upz.shp",
        code_column="cod_upz",
        name_column="nom_upz",
        expected_units=111,
    ),
    "upl": TerritorialScale(
        key="upl",
        label="UPL",
        shapefile=CARTOGRAPHY_DIR / "unidadplaneamientolocal" / "UnidadPlaneamientoLocal.shp",
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


def population_years() -> tuple[int, ...]:
    """Every year the population panel has to cover, which is not only the study's.

    The denominator is needed wherever a rate is formed, and a rate is formed at
    every survey year as well as at every year of the window. Four of the five
    surveys sit inside 2007-2024 and 2005 does not, so a panel built over the
    window alone would have nothing to divide that year's trips by — and it would
    fail at the moment of forming the rate rather than at the moment of building
    the panel, which is far from where the cause is.

    The census file covers 2005-2035, so every year this returns is in it. Declared
    as a function rather than a constant because it depends on which surveys are
    declared, and a fifth one was added after the window was fixed.
    """
    return tuple(sorted(set(STUDY_YEARS) | {survey.year for survey in MOBILITY_SURVEYS}))

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

# What each type is called in a figure that goes into the thesis. Declared beside
# the types rather than written into whichever module draws first, so two figures
# cannot name the same road user two ways.
ROAD_USER_LABELS_ES: dict[str, str] = {
    PEDESTRIAN: "Peatones",
    BICYCLE: "Bicicleta",
    MOTORCYCLE: "Motocicleta",
    CAR: "Automóvil",
    PUBLIC_TRANSPORT: "Transporte público",
    OTHER: "Otros",
}


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
# What is implemented here are the eleven static ones. The four with a series
# (cycleways and the three signage layers) come later, and the long table below is
# shaped so they slot into it without a schema change: every row already carries a
# YEAR column, null for a snapshot and filled for a series.
#
# The eleventh snapshot, the origin-destination desire lines, is not a predictor
# at all and is declared further down, under Exposure. It describes how the city
# is used rather than what it is built of, which puts it on the other side of the
# model: it is a candidate offset, not a covariate. Keeping it out of this list is
# what keeps it out of the correlation matrix and the figure sets, where a row for
# it would suggest it competes with the thirteen. See D21 and D35.
# The root itself is declared at the top of this file, with the other roles.

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
# The first line method. No static predictor declares it yet: it exists because
# the four layers with an annual series are line layers, and because the exposure
# module needs the same splitting of a line by unit for a different purpose. One
# implementation, two callers, so the kilometres of a cycleway inside a unit and
# the kilometres of a desire line inside a unit cannot end up measured two
# slightly different ways.
LINE_LENGTH_METHOD = "line_length"


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
    LINE_LENGTH_METHOD: MeasurementMethod(
        name=LINE_LENGTH_METHOD,
        geometry=LINE_GEOMETRY,
        measure_unit="km",
        value_unit="line km per km2",
        computation=(
            "repair unusable geometries, intersect the layer with the unit in EPSG:3116, "
            "add the length of every fragment falling inside the unit, and divide those "
            "kilometres by the area of the unit"
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

# Whether the sample behind a row can carry a figure at the scale of one unit.
# This is a different question from VALUE_STATUS and it needs a column of its own:
# VALUE_STATUS says whether there is a number, and every check that filters on
# MEASURED means "rows that have a number in them". A row can have a perfectly
# well computed number and still rest on a sample the survey itself only ever
# claimed at the scale of the city.
#
# 2011's Saturday is the case, and it is the survey's own statement rather than
# our judgement: its 4,035 records were expanded and analysed "a nivel de ciudad y
# estrato socioeconómico" where the weekday was analysed at UPZ. The rows are built
# and exported like any other, because the measurement is real and the city total
# is usable; what the column stops is a reader treating one of the thirty numbers
# as an estimate of the same kind as the rest.
SAMPLE_SUPPORT_COL = "SAMPLE_SUPPORT"
SAMPLE_SUPPORTS_UNIT = "SUPPORTS_UNIT"
SAMPLE_CITY_LEVEL_ONLY = "CITY_LEVEL_ONLY"


# -- delivered and not declared ---------------------------------------------
# Two layers arrived in the predictor bundle and no variable reads either of
# them. They are recorded here because "delivered and not used" and "never
# delivered" are different facts and a folder cannot tell them apart — the same
# reason D10 materialises a zero rather than leaving a row out. Without this
# record a later session finds two folders nothing points at and has to guess
# whether they were rejected or forgotten.
#
# Neither is rejected. Both are candidates that have not been through the
# argument a variable has to survive, and both would need a decision about scale
# before they could be: one is keyed on UPZ, which does not nest inside the 30
# units, and the other is a perception index rather than a count of anything.
#
# Both were moved into `areas` on 2026-09-05, from the two places the bundle put
# them: `luminarias_upz` sat beside the geometry folders as a layer among them,
# and `indiceseguridadnocturna` sat under `mean`, which is not a geometry at all
# but the measurement the advisor had in mind for it. That hint is kept here,
# where it can be read, instead of in a folder name that contradicts the scheme
# the code dispatches on.
@dataclass(frozen=True)
class UndeclaredLayer:
    """A delivered layer that no variable reads, and what would have to be settled first."""

    folder: str
    geometry: str
    holds: str
    keyed_on: str
    delivered_at: str  # where the bundle put it, before it was filed by geometry
    suggested_measure: str  # what the delivery implies, where it implies anything
    open_question: str  # what has to be decided before it could become a variable

    @property
    def path(self) -> Path:
        return PREDICTORS_DIR / GEOMETRY_FOLDERS[self.geometry] / self.folder


UNDECLARED_PREDICTOR_LAYERS: tuple[UndeclaredLayer, ...] = (
    UndeclaredLayer(
        folder="luminarias_upz",
        geometry=AREA_GEOMETRY,
        holds="street lighting counted by lamp technology (LED, Mh, Na) and in total",
        keyed_on="CODIGO_UPZ",
        delivered_at="shp_properties_sorted/luminarias_upz",
        suggested_measure="",
        open_question=(
            "counted over the 111 UPZ, which do not nest inside the 30 units; using it "
            "would need the same apportionment decision the UPZ population needed and "
            "did not get. See D36"
        ),
    ),
    UndeclaredLayer(
        folder="indiceseguridadnocturna",
        geometry=AREA_GEOMETRY,
        holds="a night-time safety perception index, with its component scores",
        keyed_on="UPlCodigo",
        delivered_at="shp_properties_sorted/mean/indiceseguridadnocturna",
        suggested_measure="mean over the unit, which is what the delivered folder name says",
        open_question=(
            "it is perceived safety and not built environment, so it measures something "
            "closer to an outcome than to a cause and would need an argument of its own "
            "before it could sit beside the thirteen"
        ),
    ),
)


# ---------------------------------------------------------------------------
# Population
# ---------------------------------------------------------------------------
# The denominator of every rate the study will estimate: one number per unit and
# per year. It arrives as a demographic file with one row per unit, year, sex and
# single year of age, and the pipeline adds it up to (unit, year) and to nothing
# coarser.
#
# **Keyed on the year and not on the unit alone**, which is a modelling decision
# and not a convenience. A denominator constant within a unit is collinear with
# that unit's fixed effect and drops out of the model, taking the normalisation
# with it. The variation it would discard is not noise: between 2007 and 2024 a
# unit's population moves by anything from -28.5% to +557.9%. And the series is a
# superset of the snapshot — it can always be collapsed to one number per unit,
# and one number per unit can never be expanded into a series. See D36.
#
# **What is measured and what is estimated is not in the file.** The years run
# from 2005 to 2035, which is wider than any census, so some of them are
# projections and some are probably backcasts. Which is which cannot be read off
# the file, and reading it off the shape of the series would be inference dressed
# as provenance. It is an open question for my advisor and nothing here assumes
# an answer. See D36.
POPULATION_COL = "POPULATION"


@dataclass(frozen=True)
class PopulationSource:
    """The population file, declared column by column and read through it.

    Same discipline as a predictor layer: the columns are named here, the reader
    holds the file to that declaration, and a delivery that renames one fails at
    the read rather than measuring something else. The names are spelled as the
    file spells them, accents and all.
    """

    path: Path
    separator: str
    # The file is delivered with a byte order mark, which utf-8-sig strips and
    # plain utf-8 leaves glued to the first column name.
    encoding: str
    year_column: str
    code_column: str
    name_column: str
    count_column: str
    # The columns the count is broken down by, and which the aggregation adds
    # away. Declared rather than implied so the funnel can say how many rows one
    # unit-year was assembled from, and so a delivery that gains a third
    # breakdown is a visible change rather than a silently different total.
    breakdown_columns: tuple[str, ...]
    # The file numbers its units 1 to 33; the unit layer spells them UPL01 to
    # UPL33. The rule is written out because a raw 7 and a UPL07 are the same
    # unit, and a join on the wrong one of them matches nothing at all rather
    # than matching wrongly, which is the failure that hides longest.
    code_prefix: str
    code_digits: int
    describes: str

    def unit_code(self, raw: int) -> str:
        return f"{self.code_prefix}{int(raw):0{self.code_digits}d}"


POPULATION_SOURCE = PopulationSource(
    path=POPULATION_DIR / "osb_demografia-poblacion-upl.csv",
    separator=";",
    encoding="utf-8-sig",
    year_column="ANO",
    code_column="CODIGO_UPL",
    name_column="NOMBRE_UPL",
    count_column="POBLACION",
    breakdown_columns=("SEXO", "EDAD"),
    code_prefix="UPL",
    code_digits=2,
    describes=(
        "one row per territorial unit, year, sex and single year of age, with the "
        "unit numbered as an integer and the population as a whole number"
    ),
)

# The units the file carries that the study does not. Decreto 555 de 2021 defines
# 33 UPL and the delivered cartography holds 30; the three missing ones are the
# rural units, where the urban predictors are undefined. They are named here so
# the run can report what the study leaves out in people rather than in polygons,
# which is the measured confirmation that the universe is 30 and not a shortfall.
# A delivery whose extra units differ from these is reported rather than passed
# over: it would mean the file and the cartography no longer describe the same
# division of the city.
POPULATION_UNITS_OUTSIDE_STUDY: tuple[str, ...] = ("UPL01", "UPL02", "UPL06")

# One row per unit and year, in this order. Identity, then the count. There is no
# status column: a unit-year is either in the file or the run fails, because a
# denominator that is quietly absent for one cell of the panel would take that
# cell out of every model without saying so.
POPULATION_TABLE_COLUMNS: tuple[str, ...] = (
    SCALE_COL,
    AREA_CODE_COL,
    AREA_NAME_COL,
    YEAR_COL,
    POPULATION_COL,
)


def population_column(year: int) -> str:
    """The name one year of population takes outside the population table.

    In that table the year is a column and the count is `POPULATION`, which is
    the right shape for a panel. Anywhere the year is not a column — the exposure
    table, which is one row per unit — the count has to carry its year in its
    name instead, or it becomes a population of nowhere in particular. This is
    the same rule the trip columns follow, applied to the denominator.
    """
    return f"{POPULATION_COL}_{year}"


# ---------------------------------------------------------------------------
# Exposure
# ---------------------------------------------------------------------------
# How much travel of a given mode passes through a unit. This is not an urban
# predictor and is deliberately not declared as one: a predictor says what the
# street is like, and exposure says how much traffic there is to be hurt. In a
# rate model the two go on opposite sides, so putting exposure in the predictor
# correlation matrix would invite a reader to compare it with variables it does
# not compete with. See D35.
#
# The source is the origin-destination desire lines of the mobility survey. Each
# line runs from the centroid of an origin zone to the centroid of a destination
# zone and carries the survey's own expansion of that trip. Two expansions
# arrive on every record and they are not the same quantity:
#
#   f_exp         the expansion factor: how many real trips one surveyed trip
#                 stands for on a day. Almost every record is made five days a
#                 week, so the sum over the layer is a working day's trips.
#   ResultadoExp  f_exp multiplied by the number of days per week the trip is
#                 made, which the day flags of the record confirm. It is a count
#                 of trips per week, and it is the quantity the layer is built
#                 around.
#
# The distinction is the whole reason this section is written the way it is. The
# legacy pipeline multiplied a length by f_exp and wrote the product back over a
# column called len_km, so a sum of kilometre-trips was exported and read as
# kilometres of infrastructure. Nothing here can repeat that: every quantity has
# its own column, the unit and the period are in the column's name, and no column
# is ever overwritten by something derived from it.
@dataclass(frozen=True)
class SurveyLineLayer:
    """A line layer whose records carry a survey expansion factor.

    Declared with the same discipline as a predictor: the path is built from the
    declaration, the columns are read through it, and the run checks the file
    against it rather than trusting either. The column names are spelled the way
    the delivered .dbf spells them, truncation included, because that is what
    has to match at read time; the untruncated name is in the comment beside it.
    """

    name: str
    label: str  # short form in English, for the code and the logs
    label_es: str  # short form in Spanish, for the figures and the documents
    source_layer: str
    source_file: str
    mode: str  # the travel mode this layer covers, as the exported tables label it
    mode_column: str  # the column that states the mode on every record
    mode_value: str  # the one value that column is allowed to hold
    weekly_weight_column: str  # trips per week represented by the record
    daily_weight_column: str  # trips per day represented by the record
    origin_x_column: str
    origin_y_column: str
    destination_x_column: str
    destination_y_column: str
    measures: str  # one line: what the variable is, for the log and the dictionary
    time_coverage: str
    # The year of population the per-inhabitant column divides by. The layer
    # itself carries no year, so the rate has to name the year of its denominator
    # or it says nothing: dividing an undated numerator by a population that
    # moves would make the rate change with the denominator alone. 2023 is the
    # only date attached to this file — the ArcGIS export in its metadata — and
    # it is a property of the layer rather than a setting of the module, because
    # a second layer would come with a date of its own. See D36.
    population_reference_year: int = LAST_YEAR
    # The survey this layer actually came from, once that was established rather
    # than guessed. It is deliberately not the same as `population_reference_year`
    # above, and the difference is the point: that one is 2023 because the ArcGIS
    # export in the metadata is dated 2023, and this one is 2019 because all 181
    # records match an exact triple in the 2019 survey. The per-inhabitant column
    # therefore divides 2019 trips by 2023 residents, and it is left that way on
    # purpose — it is descriptive, it enters no model, and renaming it would break
    # the traceability of figures already quoted. See D36 and D38. Carrying both
    # here is what keeps that discrepancy visible instead of buried in prose.
    established_year: int | None = None
    geometry: str = LINE_GEOMETRY

    @property
    def path(self) -> Path:
        return EXPOSURE_DIR / GEOMETRY_FOLDERS[self.geometry] / self.source_layer / self.source_file

    @property
    def figures_subdir(self) -> str:
        """The folder this layer's figures go in, under the exposure figures root.

        Named for what the layer is rather than for what it measures, because it
        is no longer the study's exposure and the tree should not suggest it is.
        It sorts after the year folders, which is where a superseded artefact
        belongs, and when the survey it came from is implemented the whole folder
        goes with it.
        """
        year = self.established_year if self.established_year is not None else "undated"
        return f"delivered_{year}_{self.mode.lower()}"

    def column(self, suffix: str) -> str:
        """The name one measured quantity takes in the exported table.

        The mode leads, so two exposure layers measured against the same units
        produce two sets of columns that sit side by side without colliding and
        without either having to be read from a separate file. It also means a
        column cannot exist without saying which mode it counts, which is the
        failure this naming exists to prevent: `TRIPS_PER_WEEK` was correct only
        for as long as there was one layer.

        A suffix may also ask for the layer's own population year, which is how
        the per-inhabitant column ends up naming the year it divides by instead
        of leaving a reader to assume one. Filling it here rather than at each
        call site means the column name and the number underneath it come from
        the same declaration and cannot drift apart.
        """
        return f"{self.mode}_{suffix.format(population_year=self.population_reference_year)}"

    @property
    def attribute_columns(self) -> tuple[str, ...]:
        """Every attribute the measurement reads, and nothing else."""
        return (
            self.mode_column,
            self.weekly_weight_column,
            self.daily_weight_column,
            self.origin_x_column,
            self.origin_y_column,
            self.destination_x_column,
            self.destination_y_column,
        )


BICYCLE_DESIRE_LINES = SurveyLineLayer(
    name="BICYCLE_TRIPS",
    label="Bicycle trips",
    label_es="Viajes en bicicleta",
    source_layer="Líneas de deseo Matriz Origen Destino",
    source_file="Líneas de deseo viajes en bicicleta.shp",
    mode="BICYCLE",
    # The .dbf truncates every name to ten characters. modo_principal, ResultadoExp,
    # zat_destino and the rest arrive shortened, and the untruncated names survive
    # only in the ESRI metadata that ships beside the shapefile.
    mode_column="modo_princ",  # modo_principal
    mode_value="Bicicleta",
    weekly_weight_column="ResultadoE",  # ResultadoExp
    daily_weight_column="f_exp",
    origin_x_column="Xo",
    origin_y_column="Yo",
    destination_x_column="Xd",
    destination_y_column="Yd",
    measures="bicycle trips per week apportioned to the unit by the share of the line's length inside it",
    # The layer declares no year anywhere, and the file dates its own export in
    # ArcGIS rather than the survey behind it. Treated as a snapshot of unknown
    # date until my advisor says which survey it is. See D35.
    time_coverage=SNAPSHOT_COVERAGE,
    # November 2023 is what that ArcGIS export is dated, and it was the closest
    # thing to a date the layer had when this was written. It fixes the
    # denominator of the per-inhabitant column and appears in that column's name.
    # It is now known to be the wrong year and is kept anyway; see D36.
    population_reference_year=2023,
    # And this is the right one, established after the fact: every one of the 181
    # records matches an exact (zat_origen, zat_destino, f_exp) triple among the
    # 7,863 bicycle trips of the 2019 survey, and the endpoints sit on the 2019
    # zoning's centroids at a median 0.046 m against 2.148 m for the 2023 zoning.
    # See D38.
    established_year=2019,
)

# -- what the exposure table holds ------------------------------------------
# One row per unit, and every quantity in its own column with three things in the
# name: the mode, what is counted, and over what period. Nothing is called
# "trips" on its own — a column that does not say whether it counts a day or a
# week is the same mistake as a column called len_km holding kilometre-trips —
# and nothing is called "trips per week" on its own either, because the next
# exposure layer would want that name for a different mode and one of the two
# would have to lose.
#
# So a column name is built, not written down: the quantity declares the part
# that describes it and the layer contributes the mode. A second layer therefore
# cannot collide with this one, and it cannot be added without saying which mode
# it is. The table stays one row per unit and gains a column per quantity per
# mode, which is the shape a panel joins against.
@dataclass(frozen=True)
class ExposureQuantity:
    """One number the exposure measurement produces, per mode.

    `means` is a template rather than a sentence because the two expansion
    columns are named by the layer, not by this module. Filling it from the
    declaration is what makes the exported dictionary name the column the number
    actually came out of, instead of a name that was true of the first layer.
    """

    suffix: str
    unit: str
    means: str  # formatted with the layer, so it names that layer's own columns
    # True for the allocations exported beside the variable to be compared with
    # it. They are never model variables, and the dictionary says so.
    is_alternative: bool = False

    def describe(self, layer: SurveyLineLayer) -> str:
        return self.means.format(
            weekly=layer.weekly_weight_column,
            daily=layer.daily_weight_column,
            mode=layer.mode.lower(),
            population_year=layer.population_reference_year,
        )


EXPOSURE_QUANTITIES: tuple[ExposureQuantity, ...] = (
    ExposureQuantity(
        suffix="TRIPS_PER_WEEK_BY_LENGTH_SHARE",
        unit="trips per week",
        means="the variable: each line's {weekly} apportioned to the unit by the share of "
              "the line's length falling inside it",
    ),
    ExposureQuantity(
        suffix="TRIPS_PER_DAY_BY_LENGTH_SHARE",
        unit="trips per day",
        means="the same apportionment applied to {daily}, which expands one surveyed trip "
              "to a day rather than to a week",
    ),
    ExposureQuantity(
        suffix="TRIPS_PER_WEEK_AT_ORIGIN",
        unit="trips per week",
        means="alternative allocation: the whole of a line's {weekly} counted in the unit "
              "containing its origin",
        is_alternative=True,
    ),
    ExposureQuantity(
        suffix="TRIPS_PER_WEEK_AT_DESTINATION",
        unit="trips per week",
        means="alternative allocation: the whole of a line's {weekly} counted in the unit "
              "containing its destination",
        is_alternative=True,
    ),
    ExposureQuantity(
        suffix="LINE_KM_INSIDE",
        unit="km",
        means="alternative allocation: the length of {mode} desire line inside the unit, "
              "carrying no trip count at all",
        is_alternative=True,
    ),
    ExposureQuantity(
        suffix="LINES_TOUCHING",
        unit="count",
        means="how many lines of the layer reach the unit, whatever share of them it holds",
    ),
    ExposureQuantity(
        suffix="TRIPS_PER_WEEK_PER_KM2",
        unit="trips per week per km2",
        means="the variable over the area of the unit",
    ),
    ExposureQuantity(
        suffix="TRIPS_PER_WEEK_PER_INHABITANT_{population_year}",
        unit="trips per week per inhabitant",
        means="descriptive only: the variable over the {population_year} population of the unit. "
              "The trips carry no year, so this is a ratio of a snapshot to one year's residents "
              "and never a series; see D36",
    ),
)

# The four the module refers to by name, so a rename is caught by the interpreter
# rather than by a column that silently stops existing.
TRIPS_WEEKLY_SUFFIX = "TRIPS_PER_WEEK_BY_LENGTH_SHARE"
TRIPS_DAILY_SUFFIX = "TRIPS_PER_DAY_BY_LENGTH_SHARE"
TRIPS_WEEKLY_AT_ORIGIN_SUFFIX = "TRIPS_PER_WEEK_AT_ORIGIN"
TRIPS_WEEKLY_AT_DESTINATION_SUFFIX = "TRIPS_PER_WEEK_AT_DESTINATION"
LINE_KM_INSIDE_SUFFIX = "LINE_KM_INSIDE"
LINES_TOUCHING_SUFFIX = "LINES_TOUCHING"
TRIPS_WEEKLY_PER_KM2_SUFFIX = "TRIPS_PER_WEEK_PER_KM2"
TRIPS_WEEKLY_PER_PERSON_SUFFIX = "TRIPS_PER_WEEK_PER_INHABITANT_{population_year}"

# Every exposure layer the pipeline measures. Adding one means adding it here and
# nothing else: the columns, the dictionary, the figures and the checks all
# follow from the declaration. See docs/adding-an-exposure-layer.md.
#
# **Empty, and that is the finished state and not a gap.** The one layer ever
# declared here was BICYCLE_DESIRE_LINES, and it was retired when 2019 landed:
# it is a 9.6% sample of that survey, bicycle only, and the study now builds
# those lines from the survey itself for four years and four modes. Its
# declaration stays above because D35, section 13 of the verification report and
# deliverables/plan.md all quote figures measured on it, and a declaration that
# names the file is what lets those figures be recomputed by hand.
#
# It was not removed on trust. Before it went, all 160 of its origin-destination
# pairs were found among the pairs the pipeline builds from the 2019 survey, with
# no pair attributed more trips than the survey holds for it — two independent
# readings of one source agreeing, which is the strongest confirmation the survey
# reader could get. See D38.
EXPOSURE_LAYERS: tuple[SurveyLineLayer, ...] = ()


def exposure_columns(layers: tuple[SurveyLineLayer, ...] | None = None) -> tuple[str, ...]:
    """The exported table's columns, in order, for the declared layers.

    Identity first, then every quantity of every layer in declaration order, then
    the status. Built rather than listed so that a run of two layers cannot come
    out with the columns of one of them.
    """
    layers = EXPOSURE_LAYERS if layers is None else layers
    return (
        SCALE_COL,
        AREA_CODE_COL,
        AREA_NAME_COL,
        AREA_UNIT_KM2_COL,
        YEAR_COL,
        # One population column per distinct reference year among the layers, and
        # not one called POPULATION: the year a layer divides by belongs to that
        # layer, so two layers dated differently need two denominators and a
        # single undated column could only hold one of them.
        *exposure_population_columns(layers),
        *(
            layer.column(quantity.suffix)
            for layer in layers
            for quantity in EXPOSURE_QUANTITIES
        ),
        PREDICTOR_STATUS_COL,
    )


def exposure_population_years(layers: tuple[SurveyLineLayer, ...] | None = None) -> tuple[int, ...]:
    """The population years the declared layers divide by, ascending and distinct."""
    layers = EXPOSURE_LAYERS if layers is None else layers
    return tuple(sorted({layer.population_reference_year for layer in layers}))


def exposure_population_columns(
    layers: tuple[SurveyLineLayer, ...] | None = None,
) -> tuple[str, ...]:
    """The population columns of the exposure table, one per distinct year."""
    return tuple(population_column(year) for year in exposure_population_years(layers))

# What every apportioned total is checked against. The shares of one line over
# the units it crosses add to less than one whenever part of it leaves the study
# area, so the check is not that the apportioned total equals the layer total but
# that the apportioned part plus the part falling outside does. Floating point
# over a few hundred fragments needs a tolerance, and a relative one is the only
# kind that means the same thing on a count of trips and on a length in km.
EXPOSURE_BALANCE_RTOL = 1e-9

# How much of a line the units may account for before it counts as double
# counting. The shares of one line cannot exceed the whole of it, so anything
# above one means two unit polygons overlap and a trip is being given to both.
#
# The threshold is not machine epsilon and must not be: a line is split into as
# many as ten fragments whose lengths are summed and then divided by the whole,
# and that arithmetic lands a few parts per billion above one on this layer
# without anything being wrong. What the check is looking for is a unit boundary
# genuinely overlapping another, which shows up as percentage points and not as
# the ninth decimal. A millionth of a line's length is far below any overlap that
# could exist in a cadastral layer and far above the noise of the sum.
EXPOSURE_MAX_OVER_COVERAGE = 1e-6

# A line of zero length has no shares to compute and would divide by zero. None
# exists in the delivered layer; the guard is here because the failure would
# otherwise be a silent NaN in one unit rather than a message.
EXPOSURE_MIN_LINE_LENGTH_M = 1e-9

# -- where the figures go ---------------------------------------------------
EXPOSURE_FIGURES_SUBDIR = "exposure"

# The desire-line maps take a prefix of their own rather than a suffix, so a file
# says which of the two kinds it is even after it has been copied out of the tree
# below and into a LaTeX project, which is what `deliverables/plan.md` requires
# of every figure.
EXPOSURE_LINES_FIGURE_PREFIX = "desire_lines"

# Four years, four modes, three day types and two kinds of figure come to 192
# files, so they are filed rather than listed. Year, then mode, then kind:
#
#   figures/exposure/2023/bicycle/choropleth/exposure__2023_bicycle_weekday.pdf
#   figures/exposure/2023/bicycle/desire_lines/desire_lines__2023_bicycle_weekday.pdf
#
# The year is the outer level because it is the unit of work and of provenance:
# a session implements one survey and creates one folder without touching the
# others. The mode is next because a choropleth and the desire lines behind it
# explain each other and are read together. The kind is last, and every figure in
# the tree sits under one of the two — the delivered layer included — so that
# `**/choropleth/*.pdf` matches every choropleth of every year and nothing else.
#
# **The names in the tree are repeated in the file names on purpose.** A figure
# is copied into the document's own folder before LaTeX can see it, so a file
# called `bicycle_weekday.pdf` would arrive there with its year stripped off by
# the move. Redundant in the tree, self-identifying out of it.
#
# The scale-bar variant stays a suffix and never a folder. It is the same figure
# rendered twice, and making it a directory would mean adding or removing a scale
# bar changes the path in the `.tex` instead of one word in the file name.
EXPOSURE_CHOROPLETH_SUBDIR = "choropleth"
EXPOSURE_LINES_SUBDIR = "desire_lines"


def exposure_figure_dir(base: Path, year: int, mode: str, kind: str) -> Path:
    """Where one survey's figures of one mode and kind are written."""
    return base / str(year) / mode.lower() / kind

# Sequential and single-hue, because the quantity has a floor at zero and no
# meaningful midpoint: a diverging ramp would invent one. Deliberately neither
# the viridis of the casualty heatmaps nor the Blues of the master table, so the
# three figures do not look like each other at a glance. ColorBrewer YlGnBu is
# ordered by lightness as well as by hue, which is what makes it readable in
# greyscale and to a colour-blind reader.
MAP_CHOROPLETH_COLORMAP = "YlGnBu"

# Zero is an observation here, not an absence: Torca receives no desire line at
# all, and that is a fact about cycling in Torca. So it keeps the bottom of the
# ramp — it is a value and belongs on the scale — and is marked with a hatch on
# top of that fill.
#
# The hatch is what the fill alone cannot do. At the bottom of a ramp covering
# nought to sixty thousand, an exact zero and a unit with two thousand trips are
# the same pale yellow, so a legend patch showing that colour would claim the
# colour means zero when six other units share it. The hatch belongs to the zero
# and to nothing else, which is what makes the legend entry true.
#
# A unit that could not be measured is a different case again and must never look
# like either: it leaves the ramp altogether for a grey of its own, with a hatch
# that is coarser and diagonal so the two are told apart in greyscale as well as
# in colour. Both entries are drawn only when a unit is actually in them.
MAP_CHOROPLETH_ZERO_HATCH = "....."
MAP_CHOROPLETH_MISSING_COLOR = "#d9d9d9"
MAP_CHOROPLETH_MISSING_HATCH = "////"

# Above this share of the ramp the number printed inside a unit switches from
# dark to light. Measured against the fill's own luminance rather than fixed per
# figure, so it holds wherever the ramp is changed.
MAP_CHOROPLETH_LIGHT_TEXT_BELOW_LUMINANCE = 0.55
MAP_CHOROPLETH_LIGHT_LABEL_COLOR = "#f7f7f7"

# The legend of the choropleth, in Spanish because the figure goes into the
# thesis. The colour bar carries the scale; these two entries carry the cases the
# bar cannot express, and each is drawn only when a unit is actually in it.
MAP_CHOROPLETH_ZERO_LABEL_ES = "Cero observado"
MAP_CHOROPLETH_MISSING_LABEL_ES = "Sin dato"

# Width of the colour bar relative to the map, and where it sits. Horizontal and
# under the map: the city's footprint is taller than it is wide, so a vertical
# bar beside it would stretch the figure into a shape no page wants.
MAP_COLORBAR_LOCATION = "bottom"
MAP_COLORBAR_SIZE = "3.5%"
MAP_COLORBAR_PAD = 0.18

# The tick labels of the colour bar are set on a diagonal. The bar is only as wide
# as the city's footprint, which is narrow, and the values on it run to six
# figures: written horizontally they overlap into a smear. Thinning the ticks
# instead would leave a scale with too few numbers to place a colour on, and
# shrinking the type would make them unreadable in print.
MAP_COLORBAR_LABEL_ROTATION = 45

# -- the desire-line map -----------------------------------------------------
# The other half of every exposure figure: the choropleth says how much travel
# each unit ends up with, and this says which lines put it there. Nothing else in
# the pipeline draws its own input, and this one earns it — the lines are built
# here rather than delivered, so a reader has no other way to see what was built.
#
# The units are drawn as an outline with no fill and, unlike every other map in
# the pipeline, **without their numbers**. A number inside a unit is unreadable
# under a few thousand crossing lines, and a label nobody can read is worse than
# no label: it says the figure was not looked at.
MAP_DESIRE_LINE_COLOR = "#1f6f8b"
MAP_DESIRE_UNIT_FACE_COLOR = "#f4f4f2"

# Width and opacity both grow with the trips a line carries, and both grow as the
# square root of them. The reason is the spread: on a typical weekday the median
# pedestrian line carries 233 trips and the heaviest 7,474, a range of 32 to 1.
# Drawn linearly the heaviest line would be thirty times the median and would
# cover the city, and the median would be a hairline; drawn uniformly the map
# would show which pairs were surveyed rather than where the travel is, and the
# heaviest tenth of the lines carries between a third and a half of all the trips.
# A square root is the usual compromise for encoding a magnitude as a width, and
# it keeps both ends of the range on the page.
MAP_DESIRE_LINE_MIN_WIDTH = 0.08
MAP_DESIRE_LINE_MAX_WIDTH = 1.6
MAP_DESIRE_LINE_MIN_ALPHA = 0.05
MAP_DESIRE_LINE_MAX_ALPHA = 0.55

# The frame is the city, and the lines are clipped to it. Bogotá is 23 km across
# and the lines run to Zipaquirá and Facatativá, 154 km apart, so a map framed on
# the lines would put the study area in 15% of its width; and drawing them whole
# inside a frame this size cuts them at its edge, which reads as a rendering fault
# rather than as a statement. Clipping settles it the way the measurement already
# did: the apportionment counts the fraction of a line inside a unit and ignores
# the rest, so a figure drawing the rest showed what no number uses.
MAP_DESIRE_FRAME_MARGIN = 0.02

# How much of a mode's travel the drawn lines have to account for. The rest are
# left out of the figure and stay in the data.
#
# The distribution is long-tailed: on a typical weekday about 30% of the lines
# carry only 5% of the trips, and drawing them costs legibility for almost no
# information. Ranked by trips and cut at 95% cumulative coverage, roughly 70% of
# the lines are drawn.
#
# **It applies to the drawing and never to the measurement**, and that separation
# is the whole point. Truncating the data instead would delete real exposure to
# make a figure tidier, and the literal reading of a 95th-percentile rule — drop
# the lines above it — would delete between a fifth and a third of every mode's
# travel, taking the busiest corridors first. Those are the places with the most
# exposure. See D38.
MAP_DESIRE_LINE_TRIP_COVERAGE = 0.95

# The colour bar of the choropleths is shared across the day types of one mode
# and never across modes. Sharing it within a mode is what makes the three days
# comparable at a glance, which is the whole point of having the day as a
# dimension; sharing it across modes would put bicycle and motorcycle at a fifth
# of a ramp scaled by walking, and neither map would have a readable pattern.
MAP_CHOROPLETH_SHARE_SCALE_ACROSS_DAY_TYPES = True


# ---------------------------------------------------------------------------
# Mobility surveys
# ---------------------------------------------------------------------------
# Exposure built from the survey itself rather than received as finished desire
# lines. The layer the pipeline read before this arrived as 181 lines already
# drawn; the four surveys arrive as trip records and the zoning those records are
# keyed on, so the geometry is built here. See D38.
#
# What is declared per year is everything the years differ in, and the years
# differ in almost everything: encoding, decimal separator, the name of every
# column, the labels the modes carry, and how the survey says which kind of day a
# trip was made on. What is *not* declared per year is anything the measurement
# does — building the lines, apportioning them, adding the intra-zonal trips,
# checking the balance — because that is the same operation four times and
# writing it twice is how two years end up measured slightly differently.
SURVEYS_DIR = INCOMING_DIR / "encuestas_movilidad"

# The kind of day a trip was made on. A dimension of the exposure table and not a
# suffix on its column names: a column called TRIPS_PER_SATURDAY would need a
# twin for every other quantity, and the table has to be filtered by day type
# before it joins anything anyway. See D38.
WEEKDAY_TYPE = "WEEKDAY"
SATURDAY_TYPE = "SATURDAY"
SUNDAY_TYPE = "SUNDAY"
DAY_TYPES: tuple[str, ...] = (WEEKDAY_TYPE, SATURDAY_TYPE, SUNDAY_TYPE)

# What each is called in a figure that goes into the thesis. "Día típico" and not
# "día hábil": the survey's own vocabulary is the working-day mobility of a
# representative day, and a holiday that falls on a Tuesday is in this category
# too.
DAY_TYPE_LABELS_ES: dict[str, str] = {
    WEEKDAY_TYPE: "día típico",
    SATURDAY_TYPE: "sábado",
    SUNDAY_TYPE: "domingo",
}

# Monday is 0 in the weekday numbering every date library uses, so these are the
# two that are not a working day. Declared rather than written as literals at the
# point of use, because "5 and 6" reads as a magic pair and "Saturday and Sunday"
# does not.
SATURDAY_WEEKDAY_NUMBER = 5
SUNDAY_WEEKDAY_NUMBER = 6


@dataclass(frozen=True)
class DelimitedTable:
    """One delivered text table, with everything needed to read it as numbers.

    Every field here is something a delivery got wrong at least once. 2023 is
    cp1252 where 2015 and 2019 are utf-8, and reading it as utf-8 fails on an
    invalid continuation byte. Its numbers are text with a comma decimal
    separator and a trailing space, so `fexp_vj` parses as an object column and
    sums to zero without complaining. Three of its column *names* are wrapped in
    spaces too. None of that is visible from the column names, which is why it is
    declared and checked rather than discovered.
    """

    path: Path
    separator: str = ";"
    encoding: str = "utf-8"
    decimal: str = ","
    # Strip surrounding whitespace from column names and from every text value.
    # On by default because the one delivery inspected so far needs it and the
    # cost on one that does not is nothing.
    strip_whitespace: bool = True


@dataclass(frozen=True)
class AccessTable:
    """One table inside a delivered Microsoft Access database.

    2011 is the only year that arrives this way, and it arrives this way twice:
    the weekday and the Saturday are separate databases with the same schema and
    `_Sabado` suffixes on the table names. Everything the other three years put in
    a CSV is already typed here, so there is no separator, no encoding and no
    decimal separator to declare — the driver hands back numbers as numbers, which
    is why `decimal` is the point and never gets used.

    The database also holds eighty-odd other tables, so which one carries the
    trips has to be named. The one to read is not the one named for trips:
    `MOD_D_VIAJES_Tipico` has 100,846 rows, one column per stage and no origin or
    destination zone, while `Mod_D_VIAJES2_BaseImputacion_Definitiva` has 122,361
    and carries `ZAT_ORIG`, `ZAT_DEST` and `Modo_Principal`. The second is the
    imputed base, and the delivery's own manual says it is the one to consult for
    a total of trips because it is the one that carries an expansion factor for
    every person who travelled.
    """

    path: Path
    table: str
    # Kept so that a source can be asked for its decimal separator without the
    # caller having to know which kind of table it is. The driver returns typed
    # numbers, so nothing is ever parsed with it.
    decimal: str = "."
    # The same stripping the delimited reader does, applied to the text columns
    # the driver returns. Harmless here and kept for one reason: the two readers
    # must not differ in what they do to a value, or a year would be measured
    # differently for having been delivered in a different container.
    strip_whitespace: bool = True


@dataclass(frozen=True)
class TripSource:
    """One delivered table of trips, and the day type every record in it carries.

    A year is usually one file, and which kind of day a trip was made on is found
    inside it — an interview date joined from the household table in 2023, one
    kind of day and no other in 2019, a flag on the record in 2015. Those years
    declare a single source with `day_type` left at None and the day type is
    decided by the `day_type_rule`, exactly as before.

    2011 is the year this exists for. Its weekday and its Saturday are different
    samples of different households in **two separate Access databases**, so which
    kind of day a record belongs to is a property of the file it came out of and
    of nothing on the record. That fact has nowhere else to live: a rule reading an
    already-loaded frame cannot see it, and a rule that went and loaded the second
    file itself would make a day-type handler into a second reader, which is the
    one thing this design has refused since 2023.

    So the day type is declared beside the file it is a fact about, the reader tags
    each row with the source it came from, and `DayTypeFromSource` reads the tag.
    The flow is unchanged: the reader reads, the rule decides.
    """

    table: DelimitedTable | AccessTable
    # The day type every record of this source carries, when that is a property of
    # the file. None means the file carries more than one kind of day, or one that
    # is stated some other way, and the year's `day_type_rule` says which.
    day_type: str | None = None


@dataclass(frozen=True)
class SurveyZoning:
    """The zones a survey's origins and destinations are keyed on.

    A survey's trips carry zone codes and nothing else, so the zoning is what
    turns a trip into a place. It is declared beside the trips rather than found
    next to them: 2011 ships no zoning at all, and a year whose geometry has to be
    borrowed from another year must say so in the configuration instead of having
    it inferred at read time.
    """

    shapefile: Path
    code_column: str
    # The delivered CRS is trusted but not assumed to be the study's: the 2023
    # zoning is EPSG:3116 where the 2015 and 2019 zonings and the study's own
    # cartography are EPSG:4686. The reader reprojects; this is here so a file
    # that declares no CRS at all can be told what it is instead of silently
    # being read as degrees.
    crs_if_undeclared: int | None = None
    # Whether a zone may arrive as several features carrying one code, which is
    # the delivery saying "these polygons are one zone" and not "two zones share a
    # number". Off by default, so a repeated code still stops the run for a year
    # that has not looked: two different zones numbered alike is a real defect and
    # the reader cannot tell the two cases apart on its own.
    #
    # 2015 declares it on, and the delivery's own arithmetic is what says so: its
    # `AREA` column is per feature, and for both repeated codes the features' areas
    # sum to the area of their union — 794 as 8.36 + 7.17 km2 and 806 as 29.33 +
    # 0.34 + 3.04. They are detached pieces of two peripheral zones north of the
    # city, no trip in the file names either of them, and dissolving them by code
    # is the only reading under which the shapefile can be read at all.
    zone_delivered_in_parts: bool = False


@dataclass(frozen=True)
class ZoningFromUpzAndRing:
    """A zoning assembled at run time instead of read from a delivery.

    2005 ships no zoning of its own and none of the three it codes its trips on is
    obtainable: the EMME zoning it was designed around exists only inside a
    proprietary model file, and the JICA one is older still. What it does carry is a
    UPZ code for every end inside Bogota, and the study already has a UPZ layer.

    So the zoning is the UPZ of Bogota with one polygon added for each of the
    seventeen municipalities of the ring, those built by `surveys.ring_municipalities`
    out of the 2015 delivery. Without them a trip with one end outside the city
    cannot be drawn at all and is lost whole rather than falling partly outside, and
    the measured cost of that is section 9 of `docs/implementing-2005.md`: eighteen
    per cent of the trips and, on Torca, five sixths of its motorised travel.

    Nothing of it is written to disk. `data/` is the record of what arrived; a
    zoning whose sources are declared is traceable where a shapefile appearing under
    `data/` with no provenance would not be.
    """

    upz_layer: Path
    upz_code_column: str
    # Prefixed so that a UPZ numbered 9 and a municipality numbered 609 cannot
    # collide in a column that now carries two code systems at once.
    upz_prefix: str = "UPZ"
    municipality_prefix: str = ""
    describes: str = ""


@dataclass(frozen=True)
class ZoneOutsideTheCity:
    """A second zone code, for the ends the survey's main zoning does not reach.

    Four of the five years state each end of a trip in one column and one code
    system. 2005 states it in two: a UPZ for everything inside Bogota, and — in a
    different column, on a different zoning — the municipality's own zone number for
    everything outside. The dictionary is explicit that the first is empty for the
    municipalities, and the records agree without a single exception on either end.

    So the code is composed rather than read: the main column where it has a value,
    this one where it does not and names one of the declared places. A record with
    neither is unplaceable, which is where it belongs and is the same category as
    2011's imputed sixth.
    """

    origin_column: str
    destination_column: str
    # The codes this column may legitimately carry, and what each of them is. A
    # code in neither this list nor the main zoning still stops the run, which is
    # what keeps it a declaration rather than a catch-all.
    codes: dict[int, str]
    stated_by: str


@dataclass(frozen=True)
class ColumnNotComparable:
    """A column this year measures that cannot be put beside another year's.

    Keyed by column and narrowed to the actor types it applies to, because a
    column may be comparable for three modes and not for the fourth. 2005 is the
    case and the reason is exact: it collected no walk under fifteen minutes, so
    its `TRIPS_PER_DAY_OF_TYPE` holds long walking for the **pedestrian** and
    holds exactly what every other year holds for the bicycle, the motorcycle and
    the car — in those three the two columns are one number written twice, in
    every year, by construction.

    Declaring it for the column alone would have held the bicycle's full series
    flat back to 2011 while its fifteen-minute series interpolated from 2005, and
    the two would have parted company on three modes that have only one
    definition. The check that says those two columns are equal on those three
    modes is what caught it.
    """

    actor_types: tuple[str, ...]
    because: str


@dataclass(frozen=True)
class PublishedTotalOverSubset:
    """The publication summed a part of the file, and this says which part.

    Every other year publishes a total over everything its expansion factor
    weights, so the run checks the sum of the whole file against it. 2005's
    publication covers the households surveyed in Bogota and not the whole
    surveyed region, which is a different universe and not a different reading:
    the sum over that subset reproduces the published figure to a tenth of a trip
    in nine and a half million.

    Declared rather than absorbed, because a check made on a different subset from
    the one the publication made is a check that passes or fails for the wrong
    reason.
    """

    column: str
    # The subset is the records where that column has a value. The one case is
    # 2005, whose `ID_UPZ` is empty for exactly the municipality households.
    where_present: bool
    describes: str


@dataclass(frozen=True)
class DayTypeFromHouseholdDate:
    """The day type comes from the household's interview date, shifted back.

    2023 surveys a household once, on one date, and its technical sheet states
    the reference period as the mobility "del día inmediatamente anterior al que
    se realiza la encuesta". So the day a trip was made is the day *before* the
    interview, and an interview on a Sunday reports a Saturday.

    The same table carries the household expansion factor, which is the other
    thing this rule has to supply. The weights are calibrated so that the whole
    sample — all seven reference days together — represents the universe once,
    not so that each day's subsample represents it. Summing the trip factor over
    one day type therefore gives that day type's contribution to an average day
    of the collection period and not the trips of one such day, and the share of
    the universe those households cover is what converts between the two. Both
    quantities are exported; see D38 for why neither is dropped.
    """

    households: DelimitedTable
    # The column both tables carry, which is what lets a trip find its household.
    join_column: str
    date_column: str
    weight_column: str
    # How many days back from the interview the reported trips were made. One in
    # 2023; a survey that asked about the interview day itself would declare zero.
    days_before: int = 1
    # Latin American dates are day-first and pandas guesses otherwise often
    # enough to matter. Declared, because a silent month/day swap moves a
    # Saturday to a weekday without failing.
    day_first: bool = True


@dataclass(frozen=True)
class DayTypeFromRecordFlags:
    """The day type is a flag the delivery already wrote on the trip.

    2015 is the year this was written for. Its trip record carries `DIA_HABIL`
    and `DIA_NOHABIL`, one of them set and never both, and the two account for
    every one of the 147,251 records — 129,521 and 17,730.

    Reading the flag rather than deriving the day is a decision and not a
    shortcut, because 2015 does carry an interview date and it was tested. The
    date agrees with the flag on **every** record: shifted back one day, as that
    year's questionnaire requires, it reproduces `DIA_HABIL`/`DIA_NOHABIL` on all
    147,251. Two things then make the flag the better source. The delivery has one
    household whose row is displaced by a column — `ENCUESTADOR_FECHA` holds the
    UTC offset, `ENCUESTADOR_HORA` holds the date, `FECHA_UPLOAD` holds the
    interviewer's name — so a rule reading the date stops the run over one
    corrupted record while the flag on its eight trips is perfectly good. And the
    flag is what the consultant themselves grouped by: the published matrices are
    reproduced from it to the last decimal, which no derived column can claim.

    What the flag means was established from the date and not from its name.
    `DIA_NOHABIL` is set on exactly the 3,591 households interviewed on a Sunday,
    and 2015 asks about the day before the interview, so the day it names is a
    **Saturday**. No household was interviewed on a Monday, so no reference day of
    the survey is a Sunday, and 2015 has two day types rather than three. Had the
    flag been about the interview day instead, the 4,237 Saturday interviews would
    have carried it and they do not.
    """

    # Column name -> the day type a set value in it means. Every record must have
    # exactly one of them set: a record with none has no day and a record with two
    # would be counted twice.
    flags: dict[str, str]
    # What in the year's own documents says which day the flag names, quoted in
    # the log on every run. Required for the same reason DayTypeIsAlwaysOne needs
    # it: the column name says "not a working day" and does not say which one, and
    # a Saturday that is really a Sunday is invisible in every figure downstream.
    stated_by: str = ""


@dataclass(frozen=True)
class DayTypeIsAlwaysOne:
    """The survey measured one kind of day, so every record carries that one.

    This is a rule and not the absence of one. A year that surveyed a single kind
    of day has to say so, because the alternative — leaving the day type
    unstated — is indistinguishable in the table from a year whose day types were
    never resolved, and the two mean opposite things.

    2019 is the year it was written for, and five independent statements in its
    own delivery agree. The questionnaire's trip module is addressed "para las
    personas del hogar con 5 años o más que se desplazaron el día anterior" and
    reads "los desplazamientos que realizó el día de ayer, desde las 4 a.m. de
    ayer a las 4 a.m. de hoy". The cartilla's glossary defines a *viajero* as a
    person reporting at least one trip on that previous day. The report states
    the total as "en un día típico, se realizan 18,996,286 viajes". The published
    origin-destination matrices — the very artefact this pipeline rebuilds — come
    only "en un día típico", with peak and off-peak hours as the sole further
    breakdown and no Saturday or Sunday matrix anywhere. And the chapter
    comparing 2019 against 2011 and 2015 lists every difference between the three
    surveys without mentioning the reference day, because there is none.

    The data agree with the documents: travel participation runs 79.1% to 80.6%
    and trips per person 1.967 to 2.061 across all seven days the fieldwork ran,
    and the trip motives are flat too — around 10% of trips are for study on
    every one of them, which no real Sunday looks like.

    The day-of-week flags `p32_lunes`..`p32_domingo` are not an alternative. The
    questionnaire asks them as "¿Qué días de la semana realiza este viaje?", so
    they are declared recurrence and not an observed day: a trip reported on a
    Wednesday and flagged for Saturdays is not a Saturday anybody lived through,
    and building a Saturday out of them would silently omit every trip made only
    at weekends, since such a trip was never reported at all.
    """

    day_type: str = WEEKDAY_TYPE
    # What in the year's own documents says so, quoted in the log on every run.
    # Required, because "the survey only covers one day" is a claim about
    # somebody else's fieldwork and it should never rest on an undocumented
    # belief.
    stated_by: str = ""


@dataclass(frozen=True)
class DayTypeFromSource:
    """The day type is a property of the file the record came out of.

    2011 is the year this was written for and the fourth way the four surveys
    state one thing. Its `DiaTipico` database holds 122,361 trips over 15,592
    households and its `DiaSabado` database 4,035 over 565 — different samples of
    different households, in separate files, with the same schema.

    The rule carries no mapping of its own. Each `TripSource` declares the day type
    its file holds, next to the path, and this reads the tag the reader put on
    every row. Keeping the mapping on the source rather than here is what stops the
    two from drifting apart: a file added to a year would otherwise have to be
    named in two places and could be named in only one.

    The day the file names was not taken from the file name. Both databases carry a
    `DIA` column, 1 to 5 in one and 6 in the other, and it equals the weekday of
    the date beside it on every one of the 16,157 households. The delivery's own
    dictionary contradicts itself about what that date is — module A calls `DIA`
    the day of the *interview* and module D calls it the day the trip was made —
    so it was settled against behaviour instead: on all five values of the weekday
    file the households make 7.02 to 7.43 trips and 10.4% to 11.6% of those trips
    are for study, while the Saturday file has 2.3% for study, 9.8% shopping and
    9.4% recreation. None of the five is a Sunday and the sixth is not a Friday.
    """

    # What in the year's own documents says which day each file holds, quoted in
    # the log on every run, for the same reason DayTypeIsAlwaysOne needs it: the
    # file name is not evidence, and a Saturday that is really a Friday would be
    # invisible in every figure downstream.
    stated_by: str = ""


# What a year's expansion factor expands one surveyed trip to. This is the field
# that must never be inherited from another year, and it is declared rather than
# derived because getting it wrong is invisible: every figure stays plausible and
# every one of them is out by the ratio between the two readings.
#
# AVERAGE_DAY means the factors represent the whole population once over all the
# reference days the survey covers together, so summing within one kind of day
# gives that kind of day's share of an average day and the share of the universe
# its households cover is what turns it into the trips of one such day. That is
# 2023, and it was established from the file: the household factors sum to
# 3,623,413 against the 3,667,331 households the technical sheet declares, over
# all seven reference days.
#
# DAY_OF_TYPE means the factors already expand to one day of the kind the record
# belongs to, so no rescaling happens and the universe share of every day type is
# one. Three of the four years are this: 2019, whose household factors sum to its
# published universe at a ratio of 1.000000 over a single kind of day; 2015, whose
# two day types each reproduce the universe separately; and 2011, whose weekday
# reproduces 2,444,256 households and whose Saturday reproduces Bogotá's 2,148,884
# on its own. 2023 is the only AVERAGE_DAY year, and had the others inherited its
# answer every figure of theirs would have been plausible and wrong.
WEIGHT_EXPANDS_TO_AVERAGE_DAY = "average day of the collection period"
WEIGHT_EXPANDS_TO_DAY_OF_TYPE = "one day of the record's own day type"
WEIGHT_EXPANSIONS: tuple[str, ...] = (
    WEIGHT_EXPANDS_TO_AVERAGE_DAY,
    WEIGHT_EXPANDS_TO_DAY_OF_TYPE,
)

# -- how long a trip took ----------------------------------------------------
# The duration is what makes an origin-destination pair checkable, and no two
# surveys state it the same way. Declared as a rule object and dispatched through
# a registry in `surveys.py`, for the same reason the day type is: a year adds a
# small rule beside the others rather than a second way of reading a file, and a
# declared rule with no handler fails with a message naming itself.
@dataclass(frozen=True)
class DurationFromMinutesColumn:
    """The trip duration is one column, already in minutes.

    2023's `duracion_min`, and the simplest case there is. It was still verified
    against something outside itself before it was trusted: it runs 3 to 14
    minutes on the under-fifteen walking category and 15 to 439 on the
    over-fifteen one, which is a column derived independently of it.
    """

    column: str


@dataclass(frozen=True)
class DurationFromClockColumns:
    """The trip duration is the gap between two clock columns.

    2019 reports no duration at all. It reports a departure and an arrival, and
    it stores them the way a spreadsheet does — `hora_inicio_viaje` holds
    0.333333333333333 for eight in the morning — so every datetime parser refuses
    them and returns nothing. A duration read from either column alone is empty
    rather than wrong, which is the good failure; the bad one is searching the
    column list for a duration and matching `p34_aplicacion_durante_viaje`,
    because "durante" contains "dura". That column is about a mobile app, it
    parses, it summarises, and every number out of it is meaningless.

    The derivation was checked against two things outside itself. The delivery
    publishes `Aux_DuraciónEODH2019.csv`, and this rule reproduces its `duracion`
    on 134,496 of its 134,497 rows — the exception being a trip from 9:00 to
    12:00 that the auxiliary file records as 81 minutes instead of 180, so the
    disagreement is a defect in that file rather than in this. And walking of
    fifteen minutes or more comes out at 3,956,916.53 trips a day against the
    3,952,811.54 the survey publishes in indicator IND_104, a tenth of a per cent
    apart.

    This is a rule rather than a column name because the years genuinely differ:
    2023 gives minutes, 2019 gives two fractions of a day, and 2015 gives
    `HORA_INICIO` and `HORA_FIN` as `HH:MM:SS` text. Three surveys, three ways of
    saying one quantity — the same shape the day type already has, and the reason
    it is dispatched through a registry instead of being widened into a field
    with three optional halves.
    """

    start_column: str
    end_column: str
    # How a clock time is stored. A fraction of a day in 2019; the constant is
    # what the reader multiplies by to reach minutes.
    minutes_per_unit: float = 1440.0
    # A trip that arrives at a smaller clock value than it left crossed midnight,
    # and the day wraps. 189 of 2019's records do. Declared because a year whose
    # times carry the date would not want it.
    wrap_at_midnight: bool = True
    # Round the result to the minute. The survey's own auxiliary file holds whole
    # minutes, and without this a 15-minute trip stored as two fractions comes out
    # at 14.999999999 and falls on the wrong side of every threshold.
    round_to_minute: bool = True


@dataclass(frozen=True)
class DurationFromTextClockColumns:
    """The trip duration is the gap between two `HH:MM:SS` clock columns.

    2015's `HORA_INICIO` and `HORA_FIN`, written the way a clock is read. It is
    the third of the three ways the surveys state one quantity, and the last one
    expected: 2023 gives minutes outright, 2019 gives two fractions of a day, and
    this gives two strings.

    It is a separate rule from `DurationFromClockColumns` rather than a flag on
    it because the two share no arithmetic. That one reads a number and scales it;
    this one splits text on colons and has no scale factor to get wrong. Folding
    them together would mean one handler with a branch on how its own input is
    stored, which is the shape the registry exists to avoid.

    **Verified twice before it was trusted, and both checks are exact.** The
    delivery ships `DIFERENCIA_HORAS` in the same notation, and this derivation
    reproduces it on **all 147,251 records** with nothing left over — no defective
    row, unlike 2019's auxiliary file. And the survey publishes the walking split
    at fifteen minutes for each of its two day types: 1,976,421 trips a day under
    fifteen minutes on a weekday and 1,037,075 on a Saturday, and the derivation
    reproduces both to the trip.

    **And that is why this year does not round.** Rounding to the minute exists to
    repair a storage defect 2019 has and 2015 does not: a fraction of a day comes
    back as 14.999999999 for a quarter of an hour and falls on the wrong side of
    every threshold, so 2019 rounds and its figures only agree with its publication
    once it does. Here the clock is exact, the derivation is exact, and rounding
    would *introduce* the error rather than remove it — it moves 619 Saturday
    walking trips above fifteen minutes that the survey itself counts below, and
    the published Saturday figure stops being reproduced. The field stays on the
    rule because the next delivery may need it; 2015 declares it off and says why.
    """

    start_column: str
    end_column: str
    # A trip arriving at a smaller clock value than it left crossed midnight and
    # its gap has to wrap; 503 of 2015's records do. Declared because a delivery
    # whose clock columns carry the date would not want it.
    wrap_at_midnight: bool = True
    # Minutes in the day the clock wraps over. Named rather than written as 1440
    # at the point of use, so the wrap and the notation are visibly the same idea.
    minutes_per_day: float = 1440.0
    # Off for 2015, and the docstring says why. On for a delivery whose clock is
    # stored as something that cannot represent a whole minute exactly.
    round_to_minute: bool = False


# -- the second pedestrian definition ----------------------------------------
# Walking is the one mode the four surveys do not measure the same way, so it is
# measured twice and the series is read on the narrower of the two. A trip on
# foot lasting at least this many minutes is in the second definition; anything
# shorter is in the first and not in the second. The other three modes have one
# definition and carry the same number in both columns.
#
# The threshold is not ours, which is the whole reason it is fifteen. It is the
# split the 2011 report publishes as its own second modal partition, the split
# the 2015 delivery publishes for each of its two day types, the split 2023
# builds into its two walking labels, and the definition the 2005 survey used for
# the entire mode. Any other number would forfeit every one of those published
# controls and would have to be argued from nothing.
#
# What forced it: the full column swings 46% across the four years and changes
# direction twice, while this one moves 14% in all and rises monotonically after
# 2015. The difference is the instrument and not the city — 2011's questionnaire
# asks for the short walk outright and 2015's states no floor — and an
# interpolation cannot be laid over a quantity whose definition changes between
# two of its anchors. See D39.
PEDESTRIAN_LONG_WALK_MIN_MINUTES = 15.0

# -- records the geometry contradicts ---------------------------------------
# The fastest each mode is allowed to have travelled, straight line, before the
# record is treated as impossible rather than merely surprising. They are
# deliberately generous: 6 km/h is a brisk walk sustained for the whole trip and
# 80 km/h is well above what Bogotá's traffic allows, so a record that fails is
# not unusual, it is wrong.
#
# The test is against the **shortest distance between the two zone polygons**,
# which is the best case the traveller could possibly have had — not between the
# centroids. A record that fails could not have been made however the trip ran
# inside its zones.
#
# It exists because a fifth of the 2023 pedestrian trips fail it. The extreme is
# 82.3 km in 15 minutes, and it is not a centroid artefact: those two zones are
# 61.8 km apart at their nearest points and do not touch. Something in the record
# is wrong — the mode, the zones, or both — and the file does not say which. What
# is certain is that the desire line drawn from it is a line nobody travelled,
# and that line spreads pedestrian exposure across units the walker never entered.
MODE_SPEED_CEILING_KMH: dict[str, float] = {
    PEDESTRIAN: 6.0,
    BICYCLE: 25.0,
    MOTORCYCLE: 80.0,
    CAR: 80.0,
}

# -- one year against the years already measured -----------------------------
# Every survey was run by a different administration and catalogues its data its
# own way, so each year is read through its own declaration. That is a lot of
# independent decisions per year — which column is the factor, what it expands
# to, how the day type is stated, what the mode labels are — and any one of them
# can be wrong in a way that still produces plausible-looking numbers.
#
# What catches that is not another check inside the year. It is the comparison
# against the years already measured: Bogotá does not remake its travel between
# two surveys, so a mode share that moves fifteen points, or a per-inhabitant
# trip rate that doubles, or a ranking of the units that stops agreeing with the
# previous survey, is a reading error long before it is a finding about the city.
#
# These are the thresholds at which the run says so. They are warnings and never
# failures: a real change of that size is possible and the run cannot tell the
# two apart. What it can do is refuse to let one pass unremarked.
EXPOSURE_YEAR_MODE_SHARE_JUMP = 0.10  # share of the four modes, in points
EXPOSURE_YEAR_TRIP_RATE_JUMP = 0.35  # trips per inhabitant, relative
EXPOSURE_YEAR_RANK_AGREEMENT_FLOOR = 0.70  # Spearman of the units, mode by mode

# How far the reconstructed total may sit from the survey's own published one
# before the run stops. Tight, because this is a sum of the same column the
# publication summed: anything beyond rounding means the file was read
# differently from the way it was published.
SURVEY_CONTROL_TOTAL_RTOL = 1e-6


@dataclass(frozen=True)
class MobilitySurvey:
    """One year of the household mobility survey, as exposure is built from it.

    The declaration is the whole of what a year contributes. Adding 2019, 2015 or
    2011 is one of these and nothing else — the reading, the mode mapping, the
    geometry, the apportionment, the checks and the figures all follow from it.
    If a year ever needs a second reader, the design was wrong.
    """

    year: int
    label: str  # short form in English, for the code and the logs
    label_es: str  # short form in Spanish, for the figures and the documents
    # Where the trips are, as one source or several. A tuple rather than a single
    # table because 2011 splits its two day types across two Access databases and
    # no rule reading an already-loaded frame can see which file a row came from.
    # The three years delivered as one file declare a one-entry tuple and nothing
    # about them changes; see `TripSource`.
    trips: tuple[TripSource, ...]
    zoning: SurveyZoning | ZoningFromUpzAndRing
    weight_column: str  # trips per day the record stands for
    origin_zone_column: str
    destination_zone_column: str
    mode_column: str
    # How the year states how long a trip took, as a rule rather than a column
    # name, because three of the four surveys state it three different ways:
    # 2023 gives minutes outright, 2019 gives a departure and an arrival stored
    # as fractions of a day, 2015 gives them as `HH:MM:SS` text. It is what makes
    # an origin-destination pair checkable — without it there is no way to say a
    # pair is too far apart for the mode, and the run says so rather than passing
    # a check it could not make. None means the year reports no duration at all.
    #
    # It is also what splits walking into D39's two definitions, and that is the
    # stricter of the two obligations: a year that measures PEDESTRIAN and leaves
    # this None stops the run, because the series is read on the fifteen-minute
    # column and there is no way to build it without a duration. None is therefore
    # only open to a year that measures no walking at all.
    duration_rule: (
        DurationFromMinutesColumn | DurationFromClockColumns | DurationFromTextClockColumns | None
    )
    # Every value of the mode column that becomes one of the study's four actor
    # types. Two source labels may map to the same type: 2023 splits walking at
    # fifteen minutes and both halves are walking.
    mode_map: dict[str, str]
    # Every value of the mode column that is deliberately not measured. It exists
    # so that a label in neither mapping stops the run instead of vanishing in a
    # groupby, which is D4's rule applied to a source that has its own vocabulary
    # every year. Public transport is here rather than in the map because the
    # casualty matrix's PUBLIC_TRANSPORT counts the occupants of a bus and the
    # survey counts the passengers of a system, and those are not the same
    # denominator.
    modes_not_measured: tuple[str, ...]
    day_type_rule: (
        DayTypeFromHouseholdDate | DayTypeIsAlwaysOne | DayTypeFromRecordFlags | DayTypeFromSource
    )
    measures: str  # one line: what the variable is, for the log and the dictionary
    # Zone codes that name no place *for this study*, whether because the delivery
    # uses them as a sentinel for a missing answer, because they are a capture
    # error, or — the case 2005 adds — because the code names a real place the
    # zoning available to us does not carry. Records carrying one are counted in
    # the balance beside the records with no zone at all, which is where they
    # belong: they cannot be put on the map either. The three causes are different
    # and the reason written at each declaration is what keeps them apart.
    #
    # Declared per year and per code, with the reason written at the declaration,
    # because this is the one list that can quietly swallow a real zone. A code
    # in neither the zoning nor this list still stops the run, which is what keeps
    # it a declaration rather than a catch-all.
    zone_codes_meaning_no_zone: tuple[str, ...] = ()
    # What one unit of `weight_column` expands a surveyed trip to. Declared per
    # year and never inherited: two of the four surveys have not had this
    # established yet, and a year read under the wrong one produces figures that
    # are all plausible and all wrong by the same factor.
    weight_expands_to: str = WEIGHT_EXPANDS_TO_AVERAGE_DAY
    # The survey's own published total for `weight_column`, and where it was read
    # from. The run reconstructs it and stops if the two disagree, which is what
    # turns "we think this column is the expansion factor" into a fact. None means
    # no control total has been found for the year, and the run says so rather
    # than passing a check it did not make.
    published_total: float | None = None
    published_total_source: str = ""
    # Day types this year measured but whose sample cannot carry a figure at the
    # scale of a unit, keyed to what in the delivery says so. The rows are built
    # and exported like any other — the measurement is real and the city total is
    # usable — and they are marked in the table so that nothing reads them as an
    # estimate of the same kind as the rest.
    #
    # 2011's Saturday is why this exists. It is 4,035 records over 565 households
    # expanding to 14,022,328 trips, so one record stands for about 3,475 of them
    # and a cell holds roughly 34 records over thirty units and four modes. The
    # decision to mark rather than drop is the advisor's; what makes it a marking
    # and not a judgement of ours is that the consultant said the same thing.
    day_types_below_unit_resolution: dict[str, str] = field(default_factory=dict)
    # Units of this year whose sample or whose zoning cannot carry a figure at the
    # scale of that unit, keyed to what says so. The same idea as the field above
    # and a different key: that one marks a whole kind of day, this one marks one
    # place. 2005 is why it exists — its zoning reaches Torca badly enough that its
    # walking there comes out at a fifth of what a fine zoning gives — and the
    # marking covers all four of that unit's modes rather than the one it shows on,
    # because the cause is the unit and not the mode.
    units_below_unit_resolution: dict[str, str] = field(default_factory=dict)
    # Columns of the exposure table this year measures but must not anchor an
    # interpolation on, keyed to the reason. 2005 is the case and the only one:
    # it collected no walk under fifteen minutes, so its TRIPS_PER_DAY_OF_TYPE is a
    # narrower universe for the pedestrian than every other year's, and an
    # interpolation laid across that boundary would read the definitional
    # difference as growth. Measured, it would read a rise of 34% a year through
    # 2007-2010 where the comparable column reads 18%.
    #
    # **The value is still exported.** The measured table is the record of what the
    # surveys say and 2005 did measure walking; what a null would have said is that
    # there is no figure, which is false. What is not true is that the figure is
    # comparable, and that is what this declares. See D39.
    not_comparable_on: dict[str, ColumnNotComparable] = field(default_factory=dict)
    # A second zone code for the ends the main zoning cannot reach, or None where
    # one column states the zone as it does for four of the five years.
    zone_outside_the_city: ZoneOutsideTheCity | None = None
    # Which part of the file the published total covers, or None where it covers
    # all of it as it does for four of the five years.
    published_total_covers: PublishedTotalOverSubset | None = None
    # The motive value marking a leg that ends at a transfer point rather than at a
    # destination, or None for a year that counts a journey once. 2005 is the only
    # year that does not: it counts each leg as a trip, and a walking leg with this
    # motive is the walk to the stop, which D38 already decided is not pedestrian
    # exposure. Dropped, and named in the balance like every other removal.
    transfer_motive: tuple[str, int] | None = None
    # The shortest walk this year is taken to have collected, or None for a year
    # that states no floor. 2005 declares walks above fifteen minutes and delivers
    # a residue of 4.7% below it; applying the floor as a removal is what makes its
    # pedestrian column exactly D39's, rather than nearly it.
    pedestrian_floor_minutes: float | None = None

    @property
    def zoning_label(self) -> str:
        """What the zoning is called, whether it was delivered or built.

        Four years name a shapefile and one builds its zoning at run time, so the
        log, the dictionary and the report ask for this instead of reaching for a
        path that one of the five does not have.
        """
        if isinstance(self.zoning, ZoningFromUpzAndRing):
            return f"a zoning built at run time ({self.zoning.describes})"
        return self.zoning.shapefile.name

    @property
    def modes_declared(self) -> tuple[str, ...]:
        """Every label the declaration accounts for, mapped or deliberately not."""
        return tuple(self.mode_map) + self.modes_not_measured

    @property
    def trips_decimal(self) -> str:
        """The decimal separator every source of this year's trips is written with.

        One value rather than one per source, because it is used after the sources
        have been read and concatenated, where a row no longer says which file it
        came from. Two sources disagreeing about it is a case that does not exist
        and would be silently wrong if it did, so it stops the run instead of
        picking one.
        """
        separators = {source.table.decimal for source in self.trips}
        if len(separators) > 1:
            raise ValueError(
                f"{self.label} declares {len(self.trips)} trip sources that do not agree on "
                f"the decimal separator ({', '.join(sorted(separators))}). The columns are "
                "converted after the sources are concatenated, so one of the two would be "
                "parsed with the other's separator and would come out wrong without failing"
            )
        return separators.pop()

    @property
    def trips_label(self) -> str:
        """What the sources are called, for the log and the dictionary."""
        return ", ".join(source.table.path.name for source in self.trips)

    @property
    def actor_types(self) -> tuple[str, ...]:
        """The study's actor types this survey measures, in the matrix's order."""
        measured = set(self.mode_map.values())
        return tuple(actor for actor in ROAD_USER_TYPES if actor in measured)


# The processed database of the 2023 survey. The delivery also publishes an
# unprocessed one and an XLSX copy of both; this is the one file that is read and
# the others must not be read instead.
_EODH_2023 = SURVEYS_DIR / "2023" / "2.PublicacionSIMUR" / "EODH"

SURVEY_2023 = MobilitySurvey(
    year=2023,
    label="Mobility survey 2023",
    label_es="Encuesta de movilidad 2023",
    # One source, and the day type is inside it — the household's interview date.
    trips=(
        TripSource(
            table=DelimitedTable(
                path=_EODH_2023 / "05_Base datos procesada" / "CSV" / "d. Modulo viajes.csv",
                encoding="cp1252",
            ),
        ),
    ),
    zoning=SurveyZoning(
        shapefile=_EODH_2023 / "03_Zonificacion" / "b. Shapefile ZAT" / "ZAT2023" / "ZAT2023.shp",
        code_column="ZAT",
    ),
    weight_column="fexp_vj",
    origin_zone_column="zat_ori",
    destination_zone_column="zat_des",
    mode_column="modo_principal_agrupado",
    duration_rule=DurationFromMinutesColumn(column="duracion_min"),
    mode_map={
        # 2023 is the only year that splits walking, and both halves are walking.
        # Excluding the short ones would leave 4.04 M trips a day against 2019's
        # 6.94 M, and 43.0% of 2019's walking lasts under fifteen minutes — the
        # gap would be the category and not the city. See D38.
        "A PIE > 15 MIN": PEDESTRIAN,
        "A PIE <15 MIN": PEDESTRIAN,
        # Includes the motorised bicycle, which this year lists separately under
        # modo_principal_desagrupado and 2011 and 2015 cannot separate at all. The
        # numerator cannot separate it either: the crash source has no such
        # category, only BICICLETA and BICITAXI. See D38.
        "BICICLETA": BICYCLE,
        "MOTO": MOTORCYCLE,
        # Driver and passenger together, plus shared, rented and electric cars.
        "AUTO": CAR,
    },
    modes_not_measured=(
        "TRANSPORTE PÚBLICO",
        "TAXI OCUPADO",
        "TRANSPORTE ESCOLAR",
        "ESPECIAL OCUPADO",
        "INFORMAL",
        "OTRO",
    ),
    day_type_rule=DayTypeFromHouseholdDate(
        households=DelimitedTable(
            path=_EODH_2023 / "05_Base datos procesada" / "CSV" / "a. Modulo hogares.csv",
            encoding="cp1252",
        ),
        join_column="key_hg",
        date_column="fecha",
        weight_column="fexp_hg",
    ),
    measures="trips per day apportioned to the unit by the share of the desire line's length "
             "inside it, with the intra-zonal trips apportioned by area share",
    # Established from the file rather than assumed: the household factors sum to
    # 3,623,413 against the 3,667,331 households the technical sheet declares, over
    # all seven reference days together. So one factor is a trip on an average day
    # of the collection period, and a day type's own figure needs the rescaling.
    weight_expands_to=WEIGHT_EXPANDS_TO_AVERAGE_DAY,
    # The sum of fexp_vj over the whole trip module. It excludes the 284 records
    # that carry no factor, which is why those are dropped rather than imputed.
    published_total=16_390_908.0,
    published_total_source="EODH 2023, sum of fexp_vj over d. Modulo viajes.csv",
)

# The 2019 delivery. It publishes its records twice, as CSV and as XLSX; the CSV
# is what is read and the XLSX copy must not be read instead.
_EODH_2019 = SURVEYS_DIR / "2019" / "Encuesta de Movilidad 2019"

SURVEY_2019 = MobilitySurvey(
    year=2019,
    label="Mobility survey 2019",
    label_es="Encuesta de movilidad 2019",
    # One source, and it holds one kind of day: 2019 surveyed a typical working
    # day and nothing else, which is what `day_type_rule` says below.
    trips=(
        TripSource(
            table=DelimitedTable(
                path=_EODH_2019 / "BD EODH2019 FINAL v14022020" / "Archivos CSV"
                / "ViajesEODH2019.csv",
                # utf-8 where 2023 is cp1252, and the decimal separator is the point where
                # 2023's is the comma. Neither is visible from the column names and both
                # were checked: the file decodes as utf-8 and fails as cp1252 on byte 0x8d,
                # and f_exp arrives as 54.2865603523867.
                encoding="utf-8",
                decimal=".",
            ),
        ),
    ),
    zoning=SurveyZoning(
        shapefile=_EODH_2019 / "Zonificación (shapefiles)" / "ZONAS" / "ZONAS" / "ZAT.shp",
        code_column="ZAT",
    ),
    weight_column="f_exp",
    origin_zone_column="zat_origen",
    destination_zone_column="zat_destino",
    mode_column="modo_principal",
    # 2019 reports no duration. It reports a departure and an arrival as fractions
    # of a day, and the rule that turns them into minutes reproduces the survey's
    # own Aux_DuraciónEODH2019.csv on every record but one. See the rule.
    duration_rule=DurationFromClockColumns(
        start_column="hora_inicio_viaje",
        end_column="p31_hora_llegada",
    ),
    mode_map={
        # 2019 does not split walking, so this is every walking trip whatever its
        # length — which is the definition all four years can measure. Its own
        # under-fifteen-minute half is 2,984,881 trips a day, 43.0% of the mode,
        # against the 43.1% the survey's indicator IND_104 implies.
        "A pie": PEDESTRIAN,
        "Bicicleta": BICYCLE,
        # The pedal-powered taxi, 163 records and 29,379.85 trips a day, 2.5% of
        # the year's cycling. It is here because the numerator already puts it
        # here: the crash source maps BICITAXI to BICYCLE, so a rider hurt on one
        # is counted as a cyclist, and leaving it out of the denominator would
        # count those casualties against an exposure that excludes them. 2023 has
        # no bicitaxi label at all, so the category is not identical across the
        # two years and the verification report carries its weight separately, to
        # let the effect of this be quantified without re-running the year.
        "Bicitaxi": BICYCLE,
        "Moto": MOTORCYCLE,
        "Auto": CAR,
    },
    modes_not_measured=(
        # Public transport, split five ways by this survey where 2023 groups it.
        # Not a fifth mode, for the reason in D38.
        "TransMilenio",
        "SITP Zonal",
        "SITP Provisional",
        "Alimentador",
        "Cable",
        "Intermunicipal",
        "Transporte publico individual",
        "Transporte informal",
        "Transporte Escolar",
        # The scooter, 108 records and 13,503 trips a day. Outside the four modes
        # and it has no counterpart in the casualty source either, which carries
        # no scooter category to be hurt on.
        "Patineta",
        "Otro",
    ),
    # 2019 surveyed one kind of day and its own delivery says so five times over.
    day_type_rule=DayTypeIsAlwaysOne(
        day_type=WEEKDAY_TYPE,
        stated_by=(
            "EODH 2019: the trip module asks about \"el día de ayer\" from 4 a.m. to 4 a.m.; "
            "the report states \"en un día típico, se realizan 18,996,286 viajes\"; and the "
            "published origin-destination matrices come only \"en un día típico\", with no "
            "Saturday or Sunday matrix anywhere in the publication"
        ),
    ),
    measures="trips per day apportioned to the unit by the share of the desire line's length "
             "inside it, with the intra-zonal trips apportioned by area share",
    # A 0 in zat_origen or zat_destino on records that carry no municipality and
    # no UTAM either, so it is this delivery's way of writing "not answered" and
    # not a zone the shapefile is missing: 367 records of the measured modes.
    #
    # 1917 is a single record and a different thing — a code above the zoning's
    # own range, which runs 1 to 1908, on a record whose municipality and UTAM are
    # both empty. It is a capture error, it is declared here rather than left to
    # stop the run over 180.6 trips a day, and it is named so that a reader can
    # see it was decided and not overlooked.
    zone_codes_meaning_no_zone=("0", "1917"),
    # Established from the file against the survey's own published universe, and
    # it is not 2023's answer. The household factors sum to 2,995,531.78 against
    # the 2,995,531.78 households indicator IND_5 publishes for the study area —
    # a ratio of 1.000000. The whole sample represents the universe once, over a
    # single kind of day, so one factor already expands a trip to one day of that
    # kind and nothing needs rescaling. 2023's summed to 3,623,413 against
    # 3,667,331 spread over seven reference days, which is why it needs it.
    weight_expands_to=WEIGHT_EXPANDS_TO_DAY_OF_TYPE,
    # Published by the Secretaría, not summed by us. Indicator IND_102 of the
    # delivery's Anexo D gives the trips of a typical day by mode to the decimal —
    # A Pie 6,941,797.7696855096, Auto 2,291,876.6158069298, Bicicleta
    # 1,177,867.7319962301, Moto 915,313.85802032996 — and the report states the
    # total in words at paragraph 4.5.
    published_total=18_996_285.5520,
    published_total_source=(
        "EODH 2019, Anexo D indicator IND_102, sum over the sixteen modes; stated as "
        "18,996,286 trips \"en un día típico\" at paragraph 4.5 of the Etapa V report"
    ),
)

# The 2015 delivery. It publishes its records twice, as CSV under `Base de Datos
# Completa/` and as XLSX under `Tablas Maestras Normalizadas/`; the CSV is what is
# read and the XLSX copy must not be read instead.
_EODH_2015 = SURVEYS_DIR / "2015" / "Encuesta de Movilidad 2015"

SURVEY_2015 = MobilitySurvey(
    year=2015,
    label="Mobility survey 2015",
    label_es="Encuesta de movilidad 2015",
    # One source carrying both day types, and a flag on the record says which.
    trips=(
        TripSource(
            table=DelimitedTable(
                path=_EODH_2015 / "Base de Datos Completa" / "VIAJES_ANONIMIZADOS.csv",
                # The file is pure ASCII, so both utf-8 and cp1252 decode it and neither
                # can be wrong. utf-8 is declared because that is what the rest of the
                # delivery is, and because a sibling file in the same folder — ETAPAS.xls,
                # which nothing here reads — is neither: it fails as utf-8 on byte 0xc2
                # and as cp1252 on byte 0x81. The encoding is a property of a file and not
                # of a delivery, which is why it is declared per table.
                encoding="utf-8",
                decimal=".",
            ),
        ),
    ),
    zoning=SurveyZoning(
        shapefile=_EODH_2015 / "ZATs" / "ZATs_2012_MAG.shp",
        # Not `id`, which is the shapefile's own 0-based row number and lines up
        # with nothing the trips carry. `Zona_Num_N` is the ZAT code, delivered as
        # a float over 948 features and 945 distinct values.
        code_column="Zona_Num_N",
        zone_delivered_in_parts=True,
    ),
    # One of four candidates, and the only one the survey's own publications
    # reproduce. See the notes on `weight_expands_to` and `published_total`.
    weight_column="PONDERADOR_CALIBRADO_VIAJES",
    origin_zone_column="ZAT_ORIGEN",
    destination_zone_column="ZAT_DESTINO",
    # A numeric code, and it keys on the `PREDOMINANCIA` column of
    # `MEDIO_PREDOMINANTE.xls` and not on that table's `CODIGO`, which holds
    # space-separated lists like "3 4 5 6" and joins to nothing. The lookup is one
    # of two dozen `.xls` files in the delivery that are semicolon-separated text:
    # `read_excel` refuses them and `read_csv` reads them.
    mode_column="ID_MEDIO_PREDOMINANTE",
    # HORA_INICIO and HORA_FIN as HH:MM:SS text, the third and last of the three
    # ways the four surveys state a duration. It reproduces the delivery's own
    # DIFERENCIA_HORAS on all 147,251 records and both of the survey's published
    # fifteen-minute walking splits to the trip. See the rule for why it does not
    # round where 2019 must.
    duration_rule=DurationFromTextClockColumns(
        start_column="HORA_INICIO",
        end_column="HORA_FIN",
    ),
    # The keys are `PREDOMINANCIA` codes; the names beside them are the lookup's.
    mode_map={
        # PEATON. 2015 counts a walk of three minutes or more, the threshold it
        # inherited from 2011 so the two could be compared; it does not split the
        # mode at fifteen minutes the way 2023 does, though it publishes that
        # split as an indicator. Every walking trip the file holds is in, which is
        # the definition all four years can measure.
        "13": PEDESTRIAN,
        # "BICICLETA, BICICLETA CON MOTOR" — the motorised bicycle is inside the
        # category and 2015 cannot separate it, which is one of the two reasons
        # D38 keeps it inside BICYCLE for the years that can.
        "10": BICYCLE,
        # MOTO, driver and passenger together.
        "7": MOTORCYCLE,
        # AUTO, driver and passenger together.
        "6": CAR,
    },
    modes_not_measured=(
        # Public transport, split four ways by this survey. Not a fifth mode, for
        # the reason in D38: the matrix counts the occupants of a bus in a crash
        # and the survey counts the passengers of a system.
        "1",  # Transmilenio
        "2",  # TPC-SITP
        "3",  # INTERMUNICIPAL
        "4",  # ALIMENTADOR
        "5",  # TAXI
        "8",  # ESPECIAL, school and company transport
        # ILEGAL, the informal modes together. This one costs the study something
        # and the cost is measured rather than assumed: the bicitaxi lives here in
        # 2015, where 2019 gives it a label of its own and D38 puts it in BICYCLE.
        # The stages of these trips say 86 records and 46,840 trips a day used
        # one, 3.0% of what this year measures as cycling, against 2.4% in 2019 —
        # so the category is not identical across the years and the difference is
        # about a thirtieth of one mode. Recovering it would mean taking the stage
        # rather than the trip as the unit of analysis, which is a different study.
        "9",
        "12",  # OTROS: lorry, animal traction, train, and the unclassifiable
    ),
    # A flag the delivery already wrote on every record, and what it names was
    # established from the interview date rather than from the column's name.
    day_type_rule=DayTypeFromRecordFlags(
        flags={"DIA_HABIL": WEEKDAY_TYPE, "DIA_NOHABIL": SATURDAY_TYPE},
        stated_by=(
            "EODH 2015: the trip module is addressed to \"las personas del hogar con 5 años o "
            "más que viajaron el día anterior\" and asks for \"los viajes que hizo entre las "
            "4:00 a.m. del día de ayer y las 4:00 a.m. del día de hoy\", so the reported day "
            "is the day before the interview; DIA_NOHABIL is set on exactly the 3,591 "
            "households interviewed on a Sunday and on no other, which makes the day it names "
            "a Saturday, and Tomo IV titles its chapter on them \"INDICADORES DÍA SÁBADO\". "
            "No household was interviewed on a Monday, so the survey has no Sunday at all"
        ),
    ),
    measures="trips per day apportioned to the unit by the share of the desire line's length "
             "inside it, with the intra-zonal trips apportioned by area share",
    # Two codes name no place, and the consultant's own matrices are what show it:
    # both published totals are reproduced to the last decimal once these are set
    # aside, and not otherwise.
    #
    # 0 appears on 16 records, all of them in Soacha, and is this delivery's way of
    # writing a zone that was never resolved — the same sentinel 2019 uses, in a
    # different delivery by a different administration.
    #
    # 1000 is not a defect at all. It is the survey's code for a place outside the
    # eighteen municipalities it covers: every record carrying it names
    # municipality 19, "Otro", and its coordinates are 0,0. 2,229 records and
    # 279,009 trips a day, 0.85% of the file. The zoning has no polygon for it and
    # never could, so it is counted with the records that cannot be placed rather
    # than being left to fail a lookup.
    zone_codes_meaning_no_zone=("0", "1000"),
    # Established from the file, and 2015 answers as 2019 does rather than as 2023
    # does — which is why the field exists. Each day type's subsample expands to
    # the whole universe on its own: the household weights sum to 2,967,290 over
    # the 24,622 households whose reference day was a weekday and to 3,045,530
    # over the 3,591 whose reference day was the Saturday, and the person weights
    # to 9,059,251 and 9,023,719. Three and a half thousand households carrying as
    # much weight as twenty-five thousand is what a factor that already expands to
    # one day of its own kind looks like; read as 2023's, the Saturday would have
    # come out an eighth of what it is.
    weight_expands_to=WEIGHT_EXPANDS_TO_DAY_OF_TYPE,
    # The sum of the two day types the survey publishes separately, because the
    # file holds both and neither alone is its total. Tomo IV gives 17,251,733
    # trips on a working day in Tabla 59, and the twelve modes of Tabla 119 sum to
    # 15,730,551 on the Saturday; PONDERADOR_CALIBRADO_VIAJES reproduces both,
    # mode by mode, and the three other candidate columns reproduce neither.
    published_total=32_982_284.0,
    published_total_source=(
        "EODH 2015, Tomo IV: 17,251,733 trips on a working day (Tabla 59) and 15,730,551 on a "
        "Saturday (sum of the twelve modes of Tabla 119, chapter 4 \"Indicadores día sábado\"); "
        "the published matrices matriz_habil and matriz_nohabil are reproduced to the last "
        "decimal under their own exclusion rule, which is the records with no zone and the "
        "sentinel 0 — they keep zone 1000 as a pseudo-zone and this study cannot, so the two "
        "readings agree on the file and diverge there on purpose"
    ),
)



# -- the ring of municipalities, derived and never delivered -----------------
# 2005 codes an end outside Bogota with the zone number Tabla 4.1 of the 2011
# delivery's Tomo II gives each of the seventeen municipalities of the city's first
# perimeter ring. UPZ stops at the city line, so without a polygon for each of them
# a trip with one end outside cannot be drawn at all and is lost whole — which is
# what §9 and §10 of `docs/implementing-2005.md` measure and what this fixes.
#
# **The polygons are built at run time and no shapefile of them is written.** They
# are derived from three files of the 2015 delivery that are already declared — its
# ZAT geometry, its table of which ZAT belongs to which municipality, and its master
# table of municipality names and DANE codes — so the layer is traceable to its
# sources rather than appearing under `data/` with a provenance nobody can
# reconstruct. `data/` is the record of what arrived; this is a construction.
#
# It works because the two surveys cover the same seventeen municipalities: the set
# Tabla 4.1 names and the set `MUNICIPIO.xls` carries are identical, so the join is
# by name and one to one. What comes out is the urban area of each — Zipaquira at
# 8.6 km2, Facatativa at 6.2 — which is what both surveys measured, with Soacha the
# exception at 183.8 km2 because 2015 covers the whole of it with thirty-four zones.
RING_ZAT_TO_MUNICIPALITY = _EODH_2015 / "Base de Datos Completa" / "ZAT_LOCALIDAD.xls"
RING_MUNICIPALITY_NAMES = _EODH_2015 / "Base de Datos Completa" / "MUNICIPIO.xls"

# Both of those are semicolon-delimited text with a `.xls` extension, which is the
# same trap this project has met before and the reason the extension is never taken
# as evidence of a format.
RING_TABLE_SEPARATOR = ";"

# Name as `MUNICIPIO.xls` spells it, against the zone number the 2005 survey gives
# it. Tomo II writes Mosquera with a z; the master table does not, and the master
# table is the one the join runs on.
RING_MUNICIPALITY_ZONES: dict[str, int] = {
    "COTA": 609,
    "CHIA": 610,
    "FUNZA": 611,
    "MOSQUERA": 612,
    "SOPO": 613,
    "CAJICA": 614,
    "TOCANCIPA": 615,
    "TABIO": 616,
    "ZIPAQUIRA": 617,
    "GACHANCIPA": 618,
    "TENJO": 619,
    "MADRID": 620,
    "BOJACA": 621,
    "FACATATIVA": 622,
    "SOACHA": 624,
    "SIBATE": 626,
    "LA CALERA": 635,
}

# The 2011 delivery. 357 files, of which 323 are an Emme model that is out of
# scope. The survey itself is two Access databases, a questionnaire, three volumes
# of the final report, two database manuals and two training decks.
_EODH_2011 = SURVEYS_DIR / "2011" / "Encuesta de Movilidad 2011"
_EODH_2011_DB = _EODH_2011 / "120927_Base de Datos EODH 2011"

SURVEY_2011 = MobilitySurvey(
    year=2011,
    label="Mobility survey 2011",
    label_es="Encuesta de movilidad 2011",
    # The only year delivered in two files, and the reason `trips` is a tuple. The
    # weekday and the Saturday are separate samples of separate households, so
    # which kind of day a record belongs to is a property of the database it came
    # out of and of nothing on the record.
    trips=(
        TripSource(
            table=AccessTable(
                path=_EODH_2011_DB / "120927_ConsultaEODH2011_DiaTipico (1).accdb",
                # Not MOD_D_VIAJES_Tipico, which is named for trips and is not the
                # one to read: 100,846 rows, one column per stage, one ZAT for the
                # household and no origin or destination zone at all.
                table="Mod_D_VIAJES2_BaseImputacion_Definitiva",
            ),
            day_type=WEEKDAY_TYPE,
        ),
        TripSource(
            table=AccessTable(
                path=_EODH_2011_DB / "120927_ConsultaEODH2011_DiaSabado (1).accdb",
                table="Mod_D_VIAJES2_BaseImputacion_Definitiva_Sabado",
            ),
            day_type=SATURDAY_TYPE,
        ),
    ),
    # 2011 ships no zoning of any kind, so it borrows the one delivered with 2015 —
    # and the borrowing is not an approximation. `ZATs_2012_MAG` **is** the 2011
    # survey's own zoning: chapter 2 of this year's Tomo II is the zoning proposal,
    # built on Catastro's March 2011 cadastre, and the year's matrix training deck
    # records the result as "se pasó de tener 863 zonas a 945 zonas" — the 945
    # codes the file carries. The trips name 913 distinct codes on the weekday and
    # 607 on the Saturday and every one of them is in it. The file reached this
    # study inside the following delivery and is named for the year it was
    # published rather than the year it was drawn.
    zoning=SurveyZoning(
        shapefile=_EODH_2015 / "ZATs" / "ZATs_2012_MAG.shp",
        code_column="Zona_Num_N",
        zone_delivered_in_parts=True,
    ),
    weight_column="F_EXP",
    origin_zone_column="ZAT_ORIG",
    destination_zone_column="ZAT_DEST",
    # Holds `Aux_Modos.Modo_Agregado`, the label, and not that table's `Codigo`.
    # The main mode is the one highest in the survey's own hierarchy, which Tomo I
    # states as "masivo, público, intermunicipal, taxi, privado, informal y otras
    # modalidades" — so a trip made by bus and taxi is a public-transport trip.
    mode_column="Modo_Principal",
    # Min_Inicio and Min_Fin are whole minutes from midnight, verified against a
    # second pair of columns rather than read off the names: Min_Inicio equals
    # HR_INI x 60 + MIN_INI and Min_Fin equals P18HF_D x 60 + P18MF_D on all
    # 122,361 weekday records and all 4,035 Saturday ones.
    duration_rule=DurationFromClockColumns(
        start_column="Min_Inicio",
        end_column="Min_Fin",
        minutes_per_unit=1.0,
        # Off, and this is a claim about the data rather than a default. The
        # columns run 240 to 1,680, which is 04:00 to 04:00 the next day — the
        # reference window this year's questionnaire states, "desde las 4 a.m. de
        # ayer a las 4 a.m. de hoy" — so a trip arriving after midnight is encoded
        # as 1,500 and not as 60, and nothing wraps. Left on it would do nothing at
        # all, because no difference is ever negative, and the declaration would
        # carry a statement about the file that is not true.
        wrap_at_midnight=False,
        # Irrelevant rather than false: the columns are already whole minutes, so
        # either value gives the same answer on every record. Declared off because
        # the honest reading is that nothing needs rounding, not that a choice was
        # made. What the derivation is checked against is the year's own published
        # figure: excluding walks under fifteen minutes, Tomo I's Figura 19 puts
        # walking at 28% of what is left, cycling at 5%, private vehicle at 14%,
        # TPC at 27% and TransMilenio at 12%; this rule gives 28.3, 4.6, 13.8, 27.2
        # and 11.3.
        round_to_minute=False,
    ),
    mode_map={
        # A pie. The instrument counts every walking trip to work or study whatever
        # its length, and walking trips for other purposes over three minutes; it
        # also tells the interviewer not to ask about stages for a trip made wholly
        # on foot. 0.43% of this year's walking lasts under three minutes.
        "Pie": PEDESTRIAN,
        # Bicicleta aggregates codes 18 and 19 of Aux_Modos, the bicycle and the
        # motorised bicycle, and 2011 cannot separate them — which is one of the
        # two reasons D38 keeps the motorised bicycle inside BICYCLE for the years
        # that can.
        "Bicicleta": BICYCLE,
        # Moto aggregates codes 20 and 21, driver and passenger.
        "Moto": MOTORCYCLE,
        # Privado aggregates codes 22 and 23, driver and passenger.
        "Privado": CAR,
    },
    modes_not_measured=(
        # Public transport, split four ways by this survey. Not a fifth mode, for
        # the reason in D38.
        "TPC",
        "TM",
        "Alimentador",
        "Intermunicipal",
        "Taxi",
        "Escolar",
        # Informal, and it costs this year what ILEGAL costs 2015: the bicitaxi and
        # the mototaxi are inside it, so a mode D38 puts in BICYCLE is not
        # separable at the trip level. Reading the stage columns says the bicitaxi
        # is 86 records and 11,354 trips a day, 1.9% of what this year measures as
        # cycling, against 3.0% in 2015 and 2.4% in 2019; the mototaxi is 8 records
        # and 1,032 trips, 0.25% of its motorcycle travel. 2011 is now the second
        # year with this limitation rather than the exception.
        "Informal",
        # Camión, bus privado, tracción animal, tren and the unclassifiable.
        "Otro",
    ),
    day_type_rule=DayTypeFromSource(
        stated_by=(
            "EODH 2011: the trip module is addressed \"para las personas del hogar con 5 años "
            "o más que viajaron el día anterior\" and reads \"las actividades que realizó el "
            "día de ayer... desde las 4 a.m. de ayer a las 4 a.m. de hoy\"; Tomo III states "
            "that the survey ran \"encuestas de día típico (entre semana)\" and \"encuestas de "
            "día atípico (sábado)\" and expanded the two separately; and Tomo I reports the "
            "Saturday on its own, \"en un sábado se hacen 14.022.327 viajes\". The DIA column "
            "of each database agrees: 1 to 5 in DiaTipico and 6 in DiaSabado, on every record"
        ),
    ),
    measures="trips per day apportioned to the unit by the share of the desire line's length "
             "inside it, with the intra-zonal trips apportioned by area share",
    # None, and that is measured rather than assumed: no record of either database
    # carries a 0 or a 1000 or any other code outside the zoning's range. The
    # records that cannot be placed carry no zone at all, at both ends together,
    # and they are exactly the imputed ones — see below.
    zone_codes_meaning_no_zone=(),
    # Established from the file against this year's own published universes, and it
    # is 2019's and 2015's answer rather than 2023's. Each day type's subsample
    # expands to its whole universe on its own: the weekday households' F_EXP sums
    # to 2,444,260 against the 2,444,256 households Tomo I declares for the study
    # area (2,148,884 in Bogotá plus 295,372 in the seventeen municipal cabeceras),
    # and the Saturday's to 2,149,087 against Bogotá's 2,148,884 alone. The two
    # universes are different territories on purpose: Tomo II says "la muestra para
    # el día sábado se diseñó solo para Bogotá". F_EXP is the same number on the
    # trip, the person and the household, on all 122,361 records.
    weight_expands_to=WEIGHT_EXPANDS_TO_DAY_OF_TYPE,
    # The sum of the two day types the survey publishes separately, because the two
    # databases hold both and neither alone is its total.
    published_total=31_633_388.0,
    published_total_source=(
        "EODH 2011, Tomo I: 17,611,061 trips on a working day (indicator 18, \"en la zona de "
        "estudio en un día hábil se realizan 17.611.061 viajes\") and 14,022,327 on a Saturday "
        "in Bogotá (indicator 27); the modal split of both is reproduced mode by mode, and the "
        "weekday total is quoted again by the 2015 delivery's Tomo I"
    ),
    day_types_below_unit_resolution={
        SATURDAY_TYPE: (
            "EODH 2011, Tomo III: the Saturday was expanded and its results analysed \"a nivel "
            "de ciudad y estrato socioeconómico\" where the weekday was analysed \"a nivel de "
            "UPZ\", and its non-response imputation used the code TL, every locality together, "
            "because there was no sample by locality; Tomo I adds that \"el nivel de error de "
            "esta estimación es mayor que para el día hábil\". 4,035 records over 565 "
            "households expand to 14,022,328 trips, so one record stands for about 3,475 of "
            "them and a cell holds roughly 34 records over thirty units and four modes"
        ),
    },
)



# The 2005 delivery. Four files, which is everything the Alcaldia publishes about
# this survey: the microdata as an Access database, a dictionary, a later study that
# validated its matrices against traffic counts, and the results presentation. The
# whole inspection pass is `docs/implementing-2005.md`; what follows is only what
# that pass established.
_EODH_2005 = SURVEYS_DIR / "2005" / "Encuesta  de Movilidad 2005"

SURVEY_2005 = MobilitySurvey(
    year=2005,
    label="Mobility survey 2005",
    label_es="Encuesta de movilidad 2005",
    # An Access database, like 2011, so the reader it needs already exists. Its four
    # tables are household, vehicles, persons and trips; MODULOD is the trips.
    trips=(TripSource(table=AccessTable(path=_EODH_2005 / "Encuesta.mdb", table="MODULOD")),),
    # 2005 ships no zoning and none of the three it codes its trips on can be
    # obtained: the EMME zoning it was designed around survives only inside a
    # proprietary model file and the JICA one is older still. So the zoning is
    # built — see ZoningFromUpzAndRing, and section 12 of implementing-2005.md for
    # what the ring recovers.
    zoning=ZoningFromUpzAndRing(
        upz_layer=CARTOGRAPHY_DIR / "bog_upz" / "bog_upz.shp",
        upz_code_column="cod_upz",
        describes=(
            "the UPZ of Bogota plus the seventeen municipalities of the first perimeter ring, "
            "the second dissolved out of the 2015 delivery and stamped with the zone number "
            "Tabla 4.1 of the 2011 Tomo II gives each of them"
        ),
    ),
    weight_column="FACTRED_FI",
    origin_zone_column="D29_UPZ",
    destination_zone_column="D32_UPZ",
    # The UPZ column is empty for exactly the municipality households, which the
    # dictionary states and the records confirm with no exception on either end.
    zone_outside_the_city=ZoneOutsideTheCity(
        origin_column="D29_EMME",
        destination_column="D32_EMME",
        codes={zone: name for name, zone in RING_MUNICIPALITY_ZONES.items()},
        stated_by=(
            "EODH 2005, Descripcion Encuesta: ID_UPZ is \"Ubicacion de la encuesta de acuerdo a "
            "las UPZ. Para las encuestas de los municipios este campo se encuentra vacio\"; and "
            "Tabla 4.1 of the 2011 delivery's Tomo II gives each municipality of the ring the "
            "zone number the 2005 survey codes it with"
        ),
    ),
    mode_column="D35_MEDIO",
    duration_rule=DurationFromMinutesColumn(column="TIEMPO_VIA"),
    mode_map={
        # The dictionary lists sixteen labels in order and the records carry sixteen
        # values. 2005 splits the private vehicle into driver and passenger, which no
        # other year does and which this adds back together, and it has no ILEGAL or
        # Informal aggregate at all — so unlike 2011 and 2015 it buries no bicitaxi.
        "1": PEDESTRIAN,
        "2": BICYCLE,
        "3": MOTORCYCLE,
        "4": CAR,
        "5": CAR,
    },
    modes_not_measured=(
        # Public transport, split six ways by this year. Not a fifth mode, for D38's
        # reason: the matrix counts the occupants of a bus and the survey counts the
        # passengers of a system.
        "6",   # Taxi
        "7",   # TransMilenio
        "8",   # Bus alimentador
        "9",   # Bus
        "10",  # Buseta
        "11",  # Microbus
        "12",  # Transporte intermunicipal
        "13",  # Bus privado / De compania
        "14",  # Bus escolar
        "15",  # Camion
        "16",  # Otro
    ),
    # One kind of day and no other, and by construction rather than by chance: the
    # presentation's slide 32 says the module asked about "los desplazamientos
    # realizados el dia anterior, y en caso de ser sabado, domingo o lunes sobre el
    # dia jueves", so every reference day of the survey is a weekday.
    day_type_rule=DayTypeIsAlwaysOne(
        day_type=WEEKDAY_TYPE,
        stated_by=(
            "EODH 2005, Presentacion Encuesta STT, slide 32: the trip module asked about \"los "
            "desplazamientos realizados el dia anterior, y en caso de ser sabado, domingo o "
            "lunes sobre el dia jueves\", so the reference day is a weekday by construction and "
            "the survey has no Saturday and no Sunday to distinguish"
        ),
    ),
    weight_expands_to=WEIGHT_EXPANDS_TO_DAY_OF_TYPE,
    published_total=9_689_027.0,
    published_total_source=(
        "EODH 2011, Tomo II, paragraph 4.26: \"el numero total de viajes reportado en la "
        "encuesta de movilidad para el area de estudio en el ano 2005 fue de 9.689.027\". The "
        "2011 Tomo III's \"aproximadamente 9.700.000\" is that figure rounded"
    ),
    published_total_covers=PublishedTotalOverSubset(
        column="ID_UPZ",
        where_present=True,
        describes="the households surveyed in Bogota, which is what that publication summed",
    ),
    # 2005 counts each leg of a journey as a trip, and D34_MOTI marks the ones that
    # end at a transfer point. A walking leg with that motive is the walk to the
    # stop, which D38 already decided is not pedestrian exposure; the other four
    # years do not count it and this one should not either. It is 2.14% of what
    # these four modes weigh.
    # UPZ 89. The 2005 records number their UPZ as their era did and the layer this
    # study has is a later vintage: it carries 111 codes over a range of 1 to 117,
    # missing 4, 5, 6, 7, 8 and 89, and the trips name the last of those. It is a
    # real place with no polygon here rather than a code that means nothing, which
    # is a third cause of the same consequence, and it is 74 records at the origin
    # and 66 at the destination — 4,367 trips a day, 0.14% of what this year
    # measures in the four modes.
    zone_codes_meaning_no_zone=("UPZ89",),
    transfer_motive=("D34_MOTI", 7),
    # The survey declares walks above fifteen minutes and delivers a residue of 4.7%
    # of the mode's weight below it. Applying the floor is what makes this year's
    # pedestrian column exactly D39's rather than nearly it.
    pedestrian_floor_minutes=PEDESTRIAN_LONG_WALK_MIN_MINUTES,
    # And having applied it, this year's TRIPS_PER_DAY_OF_TYPE for the pedestrian is
    # a narrower universe than every other year's, because 2005 never collected a
    # short walk at all. The value is exported — the measured table is the record of
    # what the surveys say — and it is declared not to be comparable, so that no
    # interpolation is laid across the boundary. See D39.
    not_comparable_on={
        # Named rather than referenced because the column constants are declared
        # below the surveys, with the quantities they belong to.
        # `check_declared_columns` further down proves the name is a real one.
        "TRIPS_PER_DAY_OF_TYPE": ColumnNotComparable(
            # The pedestrian and no other. For the three motorised modes this
            # column and the fifteen-minute one are one number written twice, in
            # every year, so 2005 anchors both of them exactly as it anchors
            # anything else.
            actor_types=(PEDESTRIAN,),
            because=(
                "2005 collected no walk under fifteen minutes, so this column holds long "
                "walking for this year and all walking for the other four. Anchoring an "
                "interpolation on it would read the difference of definition as growth: "
                "measured, 34% a year through 2007-2010 where "
                "TRIPS_PER_DAY_OF_TYPE_OVER_15MIN reads 18%"
            ),
        ),
    },
    # Torca. Its motorised travel and its cycling come back once the ring is in
    # place, and its walking does not: it is short, local and stays inside expansion
    # land the urban UPZ layer barely covers, and it comes out at a fifth of what a
    # fine zoning gives. All four of its modes are marked and not the one it shows
    # on, because the cause is the unit and not the mode.
    units_below_unit_resolution={
        "UPL07": (
            "measured on 2015, which has both zonings: read on UPZ and the ring rather than on "
            "its own ZAT, Torca's walking comes out at 0.22 of its ZAT figure where its "
            "motorcycle is 1.02, its car 1.07 and its bicycle 1.18. See section 12 of "
            "docs/implementing-2005.md"
        ),
    },
    measures=(
        "trips per day of the four measured modes, on one typical weekday of 2005, apportioned "
        "to the unit by the share of each desire line's length inside it"
    ),
)

# Every survey the pipeline measures. A year is added here and nowhere else.
MOBILITY_SURVEYS: tuple[MobilitySurvey, ...] = (
    SURVEY_2005,
    SURVEY_2011,
    SURVEY_2015,
    SURVEY_2019,
    SURVEY_2023,
)

# -- how a zone reaches a unit ----------------------------------------------
# The survey's zoning and the study's cartography are different files drawing the
# same boundaries with different pencils, so their overlay produces slivers: 583
# of the 1,511 fragments of the 2023 zoning weigh less than a millionth of their
# zone and together carry 12.3 m² over the whole city, the largest of them 3.88 m².
# Left in, they scatter a trip across as many as seven units that the zone does
# not actually touch.
#
# The threshold sits inside an empirical gap rather than at a round number. No
# sliver exceeds 0.035% of its zone and the smallest genuine split is 1.73% of
# one — a factor of 49 between the two — so anything from a ten-thousandth to a
# hundredth gives the identical answer: 907 zones inside the study area, 896 of
# them wholly within one unit and 11 genuinely divided between two.
ZONE_UNIT_MIN_AREA_SHARE = 1e-3

# What a discarded sliver becomes. Nothing: the shares of a zone are left as they
# come out, so they sum to one where the zone lies wholly inside the study area
# and to less than one where part of it is in Soacha, in a rural unit, or in a
# sliver that was dropped. Renormalising would fold the boundary noise into the
# units and leave the balance unable to tell the two kinds of "outside" apart.
ZONE_UNIT_RENORMALISE = False

# -- what the exposure table holds -------------------------------------------
# The table is LONG: one row per unit, year, actor type and day type, with the
# quantities as columns. The delivered-layer table was wide over the mode, which
# was right while exposure was one undated snapshot of one mode. It stopped being
# right for two reasons at once. The table has to join a casualty matrix keyed on
# unit, year and actor type, which is a join on three columns the long shape has
# and the wide one encodes in its column names; and it has to be interpolated
# over the fourteen years no survey covers, which is a group-by in the long shape
# and a loop over column names in the wide one. See D38.
#
# The mode therefore leaves the column names. It was there to stop two exposure
# layers colliding in a table that had one row per unit; in a table with a row
# per mode there is nothing to collide.
ACTOR_TYPE_COL = "ACTOR_TYPE"
DAY_TYPE_COL = "DAY_TYPE"


@dataclass(frozen=True)
class SurveyExposureQuantity:
    """One number the survey measurement produces, per unit, year, mode and day."""

    name: str
    unit: str
    means: str
    # True for the allocations exported beside the variable to be compared with
    # it. They are never model variables, and the dictionary says so.
    is_alternative: bool = False


# The variable, and the same allocation of the rescaled expansion beside it.
# Both are exported because neither answers the other's question: the first sums
# across day types to exactly what the file holds, which is what the balance is
# checked against, and the second is the only one of the two that can be compared
# between a weekday and a Saturday. See D38.
TRIPS_PER_AVERAGE_DAY_COL = "TRIPS_PER_AVERAGE_DAY"
TRIPS_PER_DAY_OF_TYPE_COL = "TRIPS_PER_DAY_OF_TYPE"
TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL = "TRIPS_PER_DAY_OF_TYPE_OVER_15MIN"
DAY_TYPE_UNIVERSE_SHARE_COL = "DAY_TYPE_UNIVERSE_SHARE"
INTRAZONAL_TRIPS_COL = "INTRAZONAL_TRIPS_PER_AVERAGE_DAY"
TRIPS_AT_ORIGIN_COL = "TRIPS_PER_AVERAGE_DAY_AT_ORIGIN"
TRIPS_AT_DESTINATION_COL = "TRIPS_PER_AVERAGE_DAY_AT_DESTINATION"
DESIRE_LINE_KM_COL = "DESIRE_LINE_KM_INSIDE"
OD_PAIRS_TOUCHING_COL = "OD_PAIRS_TOUCHING"
TRIPS_PER_KM2_COL = "TRIPS_PER_AVERAGE_DAY_PER_KM2"
TRIPS_PER_INHABITANT_COL = "TRIPS_PER_AVERAGE_DAY_PER_INHABITANT"

SURVEY_EXPOSURE_QUANTITIES: tuple[SurveyExposureQuantity, ...] = (
    SurveyExposureQuantity(
        name=TRIPS_PER_AVERAGE_DAY_COL,
        unit="trips per day",
        means="the variable: the survey's own expansion of the trips of this actor type made "
              "on a day of this type, apportioned to the unit by the share of each desire "
              "line's length inside it, with the intra-zonal trips apportioned by area share. "
              "Summed over the day types it is what the file holds, which is what the balance "
              "check compares against. WHAT IT COUNTS DEPENDS ON THE YEAR: where the survey's "
              "factor spreads the universe over several reference days it is that day type's "
              "share of an average day, and where the factor expands to one day of the "
              "record's own kind it is that whole day. So it is NOT comparable between day "
              "types, and NOT comparable between years — use TRIPS_PER_DAY_OF_TYPE for either "
              "comparison. See D38",
    ),
    SurveyExposureQuantity(
        name=TRIPS_PER_DAY_OF_TYPE_COL,
        unit="trips per day",
        means="the same apportionment divided by DAY_TYPE_UNIVERSE_SHARE, which counts the "
              "trips of one day of this type rather than this day type's share of an average "
              "day. THIS IS THE ONLY COLUMN COMPARABLE ACROSS DAY TYPES AND ACROSS YEARS, "
              "because it counts one day of its own kind whatever each year's expansion "
              "factor happens to expand to. Anything that puts two years side by side — a "
              "chart, a rate, an interpolation, a model — has to read this one; reading the "
              "other made every 2023 mode look 23% smaller than 2019 until it was caught. "
              "See D38",
    ),
    SurveyExposureQuantity(
        name=TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL,
        unit="trips per day",
        means="the same quantity on the narrower pedestrian definition: only the walking that "
              "lasts fifteen minutes or more, apportioned again through the same two spatial "
              "operators rather than rescaled from the column beside it. Identical to "
              "TRIPS_PER_DAY_OF_TYPE for BICYCLE, MOTORCYCLE and CAR, which have one "
              "definition each. THE PEDESTRIAN SERIES IS READ ON THIS COLUMN, because the full "
              "one measures a category the four surveys disagree about: 2011 asks for the short "
              "walk outright and 2015 states no floor, so the full column swings 46% across the "
              "four years where this one moves 14%. The full column stays beside it because the "
              "crash source cannot separate a short walk from a long one either, so it is the "
              "one whose denominator matches the numerator's category. Exported only per day of "
              "type, because putting two years side by side is the only thing this definition "
              "exists for; divide by DAY_TYPE_UNIVERSE_SHARE for the other basis. See D39",
    ),
    SurveyExposureQuantity(
        name=DAY_TYPE_UNIVERSE_SHARE_COL,
        unit="share",
        means="the share of the surveyed universe covered by the households whose reference "
              "day was of this type. It is the same for every unit and actor type of a year "
              "and day type, and it is here so the two trip columns can be derived from each "
              "other in the table they appear in",
    ),
    SurveyExposureQuantity(
        name=INTRAZONAL_TRIPS_COL,
        unit="trips per day",
        means="how much of TRIPS_PER_AVERAGE_DAY arrived through the area share rather than "
              "through a desire line, because its origin and destination are the same zone and "
              "it therefore has no line. It is a part of the variable and not an addition to it",
    ),
    SurveyExposureQuantity(
        name=TRIPS_AT_ORIGIN_COL,
        unit="trips per day",
        means="alternative allocation: the whole of a trip counted in the unit its origin zone "
              "falls in, owing nothing to the geometry between the endpoints",
        is_alternative=True,
    ),
    SurveyExposureQuantity(
        name=TRIPS_AT_DESTINATION_COL,
        unit="trips per day",
        means="alternative allocation: the whole of a trip counted in the unit its destination "
              "zone falls in",
        is_alternative=True,
    ),
    SurveyExposureQuantity(
        name=DESIRE_LINE_KM_COL,
        unit="km",
        means="alternative allocation: the kilometres of desire line of this actor type and day "
              "type inside the unit, carrying no trip count at all. One line per "
              "origin-destination pair, so it measures the corridors and not the traffic on them",
        is_alternative=True,
    ),
    SurveyExposureQuantity(
        name=OD_PAIRS_TOUCHING_COL,
        unit="count",
        means="how many origin-destination pairs of this actor type and day type reach the "
              "unit, whatever share of them it holds",
    ),
    SurveyExposureQuantity(
        name=TRIPS_PER_KM2_COL,
        unit="trips per day per km2",
        means="the variable over the area of the unit",
    ),
    SurveyExposureQuantity(
        name=TRIPS_PER_INHABITANT_COL,
        unit="trips per day per inhabitant",
        means="the variable over the population of the same unit in the same year. Unlike the "
              "delivered layer's per-inhabitant column this one is a rate and not a "
              "description, because the numerator now carries the year its denominator is "
              "read at; see D36 and D38",
    ),
)


def check_declared_columns() -> None:
    """Every column a survey declares itself not comparable on must be a real one.

    `not_comparable_on` is keyed by column name and the names are written in the
    survey declarations, which sit above the block that defines the column
    constants. A name that drifted from the column it means would silently stop
    excluding anything, which is the failure this whole field exists to prevent —
    so it is checked once, at import, against the table's own declaration.
    """
    columns = set(survey_exposure_columns())
    for survey in MOBILITY_SURVEYS:
        unknown = sorted(set(survey.not_comparable_on) - columns)
        if unknown:
            raise ValueError(
                f"{survey.label} declares itself not comparable on {', '.join(unknown)}, which "
                "the exposure table does not carry. A name that does not match a column "
                "excludes nothing and says it excluded something"
            )


def survey_exposure_columns() -> tuple[str, ...]:
    """The long exposure table's columns, in order.

    Identity first — and the identity is now four columns, because the row is a
    unit in a year for one actor type on one kind of day — then the population,
    then every quantity, then the status. Built rather than listed so that the
    table and the dictionary that reads it cannot disagree.
    """
    return (
        SCALE_COL,
        AREA_CODE_COL,
        AREA_NAME_COL,
        AREA_UNIT_KM2_COL,
        YEAR_COL,
        ACTOR_TYPE_COL,
        DAY_TYPE_COL,
        # One column, not one per year. The numerator carries a year now, so the
        # denominator is read at that year and the name has nothing left to
        # disambiguate. This is what supersedes POPULATION_2023. See D36 and D38.
        POPULATION_COL,
        *(quantity.name for quantity in SURVEY_EXPOSURE_QUANTITIES),
        PREDICTOR_STATUS_COL,
        # Last, beside the status it is deliberately not part of. See
        # SAMPLE_SUPPORT_COL for why it is a second column and not a third value
        # of the first.
        SAMPLE_SUPPORT_COL,
    )


# ---------------------------------------------------------------------------
# Exposure between survey years
# ---------------------------------------------------------------------------
# The surveys sit at 2011, 2015, 2019 and 2023 and the casualty series runs
# 2007-2024, so fourteen of the eighteen years have no survey and the panel the
# models are fitted on needs all of them. D40 fills them by interpolating the
# RATE — that unit's trips over that unit's population — and recovering the level
# from the annual population panel, because the level is the product of two
# things known with very different confidence: how many people live in a unit,
# which the census panel gives every year, and how much each of them travels,
# which four surveys give four times.
#
# The interpolated table sits BESIDE the measured one and never replaces it, for
# the same reason the corrected casualty set sits beside the observed one (D31).
# A reader who wants to know what the surveys said reads
# `analysis__exposure_by_unit`; a model that needs eighteen years reads this one
# and carries the provenance column with it.
#
# See D40 and docs/interpolating-the-exposure.md, whose section 6 is the list of
# ways this stage can pass every check and still be useless.

# Which run's exported exposure table the interpolation reads. None means the most
# recent run that exported one, which is what a session normally wants; a run id
# pins it, which is what reproducing a figure quoted in a document wants. Either
# way the run says which one it read, because a constructed table whose input
# cannot be identified is traceable to nothing.
INTERPOLATION_SOURCE_RUN: str | None = None

# What each survey measures over the WHOLE SURVEYED REGION, per mode and day type,
# before this study sets anything aside. The `exposure` route writes it and the
# `interpolation` route reads it, because every figure any of the four deliveries
# publishes is stated on that footprint and none of them is stated on the thirty
# units. Comparing a per-unit figure against a published one without coming back to
# this table compares two different territories — and the share of a mode that
# reaches the units differs by mode and by year, so the error it hides is not even
# constant.
SURVEY_CITY_TOTALS_FILENAME = f"{REFERENCE_PREFIX}__survey_city_totals"


EXPOSURE_PROVENANCE_COL = "EXPOSURE_PROVENANCE"
MEASURED_EXPOSURE = "MEASURED"          # a survey year: the value is the survey's
INTERPOLATED_EXPOSURE = "INTERPOLATED"  # between two surveys
HELD_EXPOSURE = "HELD"                  # before the first survey or after the last
EXPOSURE_PROVENANCES = (MEASURED_EXPOSURE, INTERPOLATED_EXPOSURE, HELD_EXPOSURE)

# How far the row is from the nearest year that measured it. Zero on a survey year
# and nowhere else. It is in the table so a model can weight by it or drop the held
# block without re-running anything, and so that fourteen constructed years cannot
# be read as fourteen observations.
YEARS_TO_NEAREST_SURVEY_COL = "YEARS_TO_NEAREST_SURVEY"

# The rate the interpolation actually runs on, and its second pedestrian
# definition. Named for the column they divide rather than TRIPS_PER_INHABITANT,
# because the measured table already carries a per-inhabitant column computed on
# TRIPS_PER_AVERAGE_DAY and the two tables are joined to each other. Two columns
# with one name and two meanings is the failure D38 records about
# TRIPS_PER_AVERAGE_DAY, and a name is the cheapest place to prevent it.
INTERPOLATED_RATE_COL = "TRIPS_PER_DAY_OF_TYPE_PER_INHABITANT"
INTERPOLATED_RATE_OVER_15MIN_COL = "TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_PER_INHABITANT"

# A rate of exactly zero at either end of a segment makes the logarithm undefined,
# so that segment is interpolated linearly instead and the run says how many cells
# took that branch. 2011's Saturday has seven such cells, which is what a sample of
# 4,035 records spread over thirty units and four modes looks like; they are
# observations and not gaps, so the segment is filled rather than left out.
#
# There is no epsilon here on purpose. Nudging a zero to 1e-9 to keep the logarithm
# defined would turn "nobody cycled here on a Saturday" into a rate that rises by
# orders of magnitude across the segment, which is arithmetic inventing a trend out
# of an observed zero.

# What happens to a day type only one survey measured. 2023 is the only year with a
# Sunday, so a Sunday series has one anchor and no trajectory at all: every year of
# it is 2023's rate moved by that unit's population.
#
# Held rather than dropped, because a table that holds it filters down to one that
# does not and the reverse is impossible — the same argument D36 made for the
# population panel over the snapshot. What makes it safe rather than misleading is
# that the rows say what they are: HELD on seventeen of the eighteen years, resting
# on a single anchor, and the run warns about it by name on every execution.
INTERPOLATION_HOLDS_SINGLE_ANCHOR_DAY_TYPES = True

# -- how far a unit's rate moves between two adjacent surveys ----------------
# The interpolation is per unit, so each series inherits its own unit's sampling
# noise, and the thirty units are not equally well sampled. This is the price of
# per-unit interpolation and the run reports it on every execution: how many
# unit x mode x step combinations move by more than this factor between adjacent
# surveys, and the widest steps by name.
#
# It reports and does not fail. A rate that really did multiply by nine in four
# years is possible — Chapinero's cycling is one, and 2019 and 2023 hold the higher
# level — so the run cannot tell a real change from sampling noise. What is not
# acceptable is producing three constructed years on top of a step like that
# without saying so. Whether the trajectories need shrinking toward the city's is a
# question for a person, asked with this table in hand.
EXPOSURE_STEP_FACTOR = 2.0
EXPOSURE_WIDEST_STEPS_REPORTED = 10


@dataclass(frozen=True)
class PublishedYear:
    """Figures a survey published that this study never read the records of.

    The 2005 survey is not on disk and not implemented. What is on disk is the 2011
    delivery's own comparison against it, and that is enough to test the one
    assumption the interpolation makes outside its measured range: that the rate was
    flat before 2011. Declared here rather than typed into a report, so the
    comparison is made by the run against numbers that carry their source.
    """

    year: int
    label: str
    source: str
    # What the figures count, in one line. The 2005/2011 comparison is made on trips
    # including walking of fifteen minutes or more and excluding shorter ones, which
    # is exactly D39's second pedestrian column — and that is why the comparison is
    # possible at all.
    definition: str
    total_trips_per_weekday: float
    # Share of that total, per actor type of this study. Only the modes the source
    # actually pins are here: a mode it does not state is absent rather than
    # guessed, and the run reports it as not comparable.
    mode_shares: dict[str, float]
    # What the same source publishes for the survey the study did read, so the
    # comparison has a control: if our reading of 2011 does not reproduce the 2011
    # column of that table, the 2005 column cannot be compared against anything.
    control_year: int
    control_total_trips_per_weekday: float
    control_mode_shares: dict[str, float]
    caveats: tuple[str, ...] = ()
    # How coarsely the source states its shares. The two modal splits are pie charts
    # labelled in whole per cent, so every share carries half a point of rounding —
    # which is nothing on a mode at 46 % and is half the value on a mode at 1 %. The
    # run turns it into a band around every growth factor rather than quoting a point
    # estimate the source cannot support.
    share_rounding: float = 0.005


# Chapter 5 of Tomo III of the 2011 delivery, which was written to compare the two
# surveys and is the only place either delivery states 2005's figures at all.
# Everything in it is a weekday of the study region counting walking of fifteen
# minutes or more and nothing shorter — the 2005 survey collected no shorter walk,
# which is why the chapter exists in that form.
PUBLISHED_2005 = PublishedYear(
    year=2005,
    label="Encuesta de movilidad 2005",
    source=(
        "EODH 2011, Tomo III, chapter 5 (Comparacion de indicadores de las encuestas de "
        "movilidad 2005-2011): the totals from paragraph 5.14, the modal splits read off "
        "Figura 5.16 (2005) and Figura 5.17 (2011) on page 265, which state all ten modes "
        "where paragraphs 5.15 and 5.16 state only six"
    ),
    definition=(
        "one weekday of the study region, all modes, including walking of fifteen minutes or "
        "more and excluding shorter walks — the same partition D39's second pedestrian column "
        "counts"
    ),
    total_trips_per_weekday=9_700_000.0,
    # All four modes of this study, from Figura 5.16. The prose of the chapter pins
    # only three of them and says of the fourth that "el vehiculo privado se mantiene
    # entre el rango del 14% y el 16%" across the two years; the chart says which end
    # of that range belongs to which year, and it is 16 % in 2005 falling to 14 % in
    # 2011 rather than a flat 15 % in both. Reading the chart also recovers the
    # bicycle, which the prose never states at all.
    mode_shares={
        PEDESTRIAN: 0.14,
        BICYCLE: 0.03,
        MOTORCYCLE: 0.01,
        CAR: 0.16,
    },
    control_year=2011,
    control_total_trips_per_weekday=13_200_000.0,
    control_mode_shares={
        PEDESTRIAN: 0.28,
        BICYCLE: 0.05,
        MOTORCYCLE: 0.03,
        CAR: 0.14,
    },
    caveats=(
        "the chapter states that 2005 counted a transfer as a trip of its own where 2011 counts "
        "it as part of one, so 2005's total is inflated relative to 2011's and the real growth "
        "between them is larger than the published totals imply",
        "the chapter says outright that the walking of the two surveys was collected differently "
        "even at the same fifteen-minute threshold, so the pedestrian row is the weakest of the "
        "four; MOTORCYCLE and CAR are subject to neither that nor the transfer rule above",
        "the 2015 delivery's Tomo IV states that a direct comparison with 2005 is not possible "
        "and publishes 2005 figures only as reference values, which is why this comparison "
        "decides whether to implement 2005 rather than anchoring anything",
        "the shares are read off pie charts labelled in whole per cent, so each carries half a "
        "point of rounding; on MOTORCYCLE at 1 % that is half the value, which is why every "
        "growth factor is reported as a band and not as a point",
        "these are the figures the 2011 delivery published about 2005 and not the 2005 survey "
        "itself, which is neither on disk nor implemented; what a reading of its own records "
        "would support is a different question and a larger one",
    ),
)

# The mobility index the same chapter publishes, per socioeconomic stratum: trips
# per person on a weekday, on the same fifteen-minute partition, in 2005 and in
# 2011. It is the closest thing the source has to the quantity D40 holds flat,
# because it is a rate and not a level — and it is what says the held rate is an
# assumption rather than a measurement.
PUBLISHED_2005_TRIPS_PER_PERSON: dict[str, tuple[float, float]] = {
    "estrato 1": (0.95, 1.48),
    "estrato 2": (1.08, 1.58),
    "estrato 3": (1.27, 1.68),
    "estrato 4": (1.51, 2.12),
    "estrato 5": (2.01, 2.31),
    "estrato 6": (1.92, 2.31),
}


INTERPOLATED_EXPOSURE_QUANTITIES: tuple[SurveyExposureQuantity, ...] = (
    SurveyExposureQuantity(
        name=TRIPS_PER_DAY_OF_TYPE_COL,
        unit="trips per day",
        means="the level, measured where the year is a survey year and constructed everywhere "
              "else. Read EXPOSURE_PROVENANCE before reading this: fourteen of the eighteen "
              "years are constructed, and a model fitted on all eighteen without knowing which "
              "is fourteen observations of an assumption. Same definition as the column of the "
              "same name in analysis__exposure_by_unit, and identical to it on the four "
              "measured years",
    ),
    SurveyExposureQuantity(
        name=TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL,
        unit="trips per day",
        means="the same on D39's narrower pedestrian definition, walking of fifteen minutes or "
              "more, and identical to the column beside it for BICYCLE, MOTORCYCLE and CAR. "
              "THE PEDESTRIAN SERIES IS READ ON THIS ONE, because a fifteen-year interpolation "
              "cannot be laid over a quantity whose definition changes between two of its four "
              "anchors. It is interpolated on its own rate and never scaled out of the column "
              "beside it, for the same reason it was apportioned again rather than rescaled. "
              "See D39",
    ),
    SurveyExposureQuantity(
        name=INTERPOLATED_RATE_COL,
        unit="trips per day per inhabitant",
        means="THE QUANTITY THAT IS ACTUALLY INTERPOLATED: this unit's trips of this actor type "
              "on this kind of day, over this unit's population in this year. Between two "
              "surveys it moves log-linearly, a constant proportional change per year; outside "
              "the measured range it is held flat. The level above is this times POPULATION, "
              "which is why a unit whose population grew forty per cent between two surveys has "
              "a level that moves and a rate that need not. See D40",
    ),
    SurveyExposureQuantity(
        name=INTERPOLATED_RATE_OVER_15MIN_COL,
        unit="trips per day per inhabitant",
        means="the same rate on the narrower pedestrian definition, interpolated separately, "
              "because the ratio between the two definitions is not constant across the four "
              "years and interpolating one of them and scaling the other would put a moving "
              "ratio through a fixed one",
    ),
)

# -- the panel against the casualty series ----------------------------------
# One equation and two unknowns. A casualty count is roughly exposure times risk,
# the casualties are known for all eighteen years and the exposure for four, so in
# every constructed year something has to be assumed about one of the two factors.
# D40 assumes the exposure is smooth and lets the risk take whatever fluctuation is
# left; assuming the risk is smooth and letting the exposure take it is the mirror
# image of the same underidentified system, not a different kind of error.
#
# **Which of the two is actually smoother is an empirical question**, and measured
# between adjacent surveys it is close to a tie once the recording change is taken
# out: on the corrected casualty set the exposure moves more in 7 of the 12 city
# steps and the risk in 5. So D40's assumption is not better supported than its
# mirror; it is one of two defensible choices, and this table is what makes the cost
# of that choice visible.
#
# It is a DIAGNOSTIC and it enters no model. The reason is not circularity — D40's
# own construction is circular in the same sense — but which quantity each version
# contaminates. D40 assumes the shape of the denominator, which is a nuisance
# parameter. Building the exposure from an assumed risk trajectory assumes the shape
# of the thing the study exists to estimate, and a model fitted on it would find
# part of what was put in. Two further obstacles are specific to this study and are
# recorded in D41: the matrix is two-sided, so a casualty of one type depends on the
# exposure of its counterpart as well as its own; and inverting the observed set
# would inject the recording change into the exposure, while inverting the corrected
# one would leave the two casualty datasets without a common denominator, which is
# what D31 exists to preserve.
EXPOSURE_DIAGNOSTIC_FILENAME = f"{REFERENCE_PREFIX}__exposure_against_casualties"

# The risk the interpolated panel implies: casualties of this type in this unit and
# year over the exposure the panel carries. Its unit is arbitrary — casualties per
# trip-per-weekday per year — and it is comparable across years of one unit and
# mode, which is all the diagnostic asks of it.
IMPLIED_RISK_COL = "IMPLIED_RISK"
# The same quantity carried across the constructed years by the rule D40 applies to
# the exposure: log-linear between survey years, held flat outside them. Identical
# to the column above on a survey year, by construction.
SMOOTH_RISK_COL = "SMOOTH_RISK"
# The exposure that would follow from assuming the risk is smooth: casualties over
# SMOOTH_RISK.
IMPLIED_EXPOSURE_COL = "IMPLIED_TRIPS_PER_DAY_OF_TYPE_OVER_15MIN"
# The diagnostic itself, and it reads two ways because they are the same number:
# how far the implied exposure sits from the interpolated one, and how far the
# implied risk departs from a smooth path. One is the other, because
# (C / smooth risk) / E = (C / E) / smooth risk = implied risk / smooth risk.
EXPOSURE_RATIO_COL = "IMPLIED_OVER_INTERPOLATED"

# Above this factor a constructed year is reported by name: the panel is absorbing
# more than this much of the movement into the risk rather than into the exposure.
# It is a reporting threshold and nothing fails on it.
EXPOSURE_DIAGNOSTIC_FACTOR = 1.5


def exposure_diagnostic_columns() -> tuple[str, ...]:
    """The diagnostic table's columns, in order.

    No day type: a casualty count is annual and carries no kind of day, so the
    weekday exposure is what it is paired against and the pairing is declared
    rather than implied by a column that would look like a dimension.
    """
    return (
        SCALE_COL,
        AREA_CODE_COL,
        AREA_NAME_COL,
        YEAR_COL,
        ACTOR_TYPE_COL,
        DATASET_COL,
        AFFECTED_PARTIES_COL,
        TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL,
        IMPLIED_RISK_COL,
        SMOOTH_RISK_COL,
        IMPLIED_EXPOSURE_COL,
        EXPOSURE_RATIO_COL,
        EXPOSURE_PROVENANCE_COL,
        YEARS_TO_NEAREST_SURVEY_COL,
    )


def interpolated_exposure_columns() -> tuple[str, ...]:
    """The interpolated exposure table's columns, in order.

    The same identity as `survey_exposure_columns`, spelled the same way and
    valued the same way, because the whole point of this table is to be joined to
    the measured one, to the casualty matrix and to the predictor tables. Then the
    denominator, then the two levels and the two rates, then the three columns that
    say what kind of number each row holds.

    `VALUE_STATUS` is deliberately not here. In the measured table it answers "is
    there a number in this row"; in this one every row has a number and the
    question a reader actually has is a different one — was it measured or was it
    constructed — which is `EXPOSURE_PROVENANCE`. Carrying a column that is
    `MEASURED` on all 6,480 rows beside a column that is `MEASURED` on 1,440 of
    them would be two words for two different things one letter apart.
    """
    return (
        SCALE_COL,
        AREA_CODE_COL,
        AREA_NAME_COL,
        AREA_UNIT_KM2_COL,
        YEAR_COL,
        ACTOR_TYPE_COL,
        DAY_TYPE_COL,
        POPULATION_COL,
        *(quantity.name for quantity in INTERPOLATED_EXPOSURE_QUANTITIES),
        EXPOSURE_PROVENANCE_COL,
        YEARS_TO_NEAREST_SURVEY_COL,
        # Carried through from the survey year the value rests on, so a row built
        # on top of 2011's Saturday says so as loudly as 2011's Saturday does.
        SAMPLE_SUPPORT_COL,
    )

check_declared_columns()


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
# Width follows from the footprint of the city, which is much taller than it is
# wide, so at 9 inches a map comes out about 13 by 23 cm.
#
# It was 5, which made a figure the size of a postcard. Because these are vector
# figures the size is not about resolution — it is the ratio between the map and
# the type, which is fixed in points: enlarging the figure shrinks the unit
# numbers and the colour bar relative to the territory, and the bar gains room for
# more ticks, from four to seven. The figures are read on screen while the study
# is being built, and that is what this value is set for. A figure sized for a
# page or a slide is a different setting and belongs to the deliverable that wants
# it; see D38.
MAP_FIGURE_HEIGHT_IN = 9.0

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
# **The figure that carries a scale bar is the one with the plain name.** It used
# to be the other way round, with the bar-less file unmarked and its twin
# suffixed, from when both were emitted every run and the bar-less one was the
# presentation copy. Now only one is emitted by default and the suffix would
# distinguish it from nothing, so the standard figure takes the plain name and the
# optional extra is the one that carries a mark.
MAP_NO_SCALEBAR_SUFFIX = "__no_scalebar"

# Whether the bar-less copy is written beside it. Off: a map for a slide is a
# thing that will be wanted occasionally and produced by flipping this and
# re-running, which takes seconds and leaves a file the next run reproduces.
#
# The alternative anyone reaches for is opening the PDF and deleting the scale
# bar by hand. It does not work well — the figure is vector, so the bar is an
# object to hunt down in Illustrator rather than a layer to hide — and, more to
# the point, the edit is gone the next time the route runs. Every other generated
# artefact in this pipeline is reproducible from a run, and a figure that has been
# retouched is not.
MAP_EMIT_NO_SCALEBAR_VARIANT = False

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


def run_directory_holding(filename: str, run: str | None = None) -> Path:
    """The run whose `data/` holds `filename`: the one named, or the most recent.

    A route that reads another route's exported table has to say which run it
    read, because a constructed table whose input cannot be identified is
    traceable to nothing and every figure in this study carries its run. Named
    runs sort chronologically by construction, so "the most recent" is the last of
    the sorted matches and needs no timestamp parsing.

    It raises rather than returning None, and the message says which route to run,
    because the alternative is a stage that quietly builds nothing.
    """
    if run is not None:
        candidate = RESULTS_DIR / run / DATA_SUBDIR / filename
        if not candidate.exists():
            raise FileNotFoundError(
                f"{run} does not hold {DATA_SUBDIR}/{filename}. It is named in config as the "
                "run to read; either it was deleted or the route that writes that file never "
                "ran in it"
            )
        return RESULTS_DIR / run
    matches = sorted(RESULTS_DIR.glob(f"{RUN_DIR_PREFIX}*/{DATA_SUBDIR}/{filename}"))
    if not matches:
        raise FileNotFoundError(
            f"no run under {RESULTS_DIR.name}/ holds {DATA_SUBDIR}/{filename}. Run the route "
            "that writes it first"
        )
    return matches[-1].parent.parent


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
