"""HodgeRank on the inter-mode casualty matrix (D69).

For two actor types i and j, the cell H_ij counts the parties of type i hurt in
two-party crashes whose other party was of type j, and H_ji counts the same crashes
from the other side. Whatever the pair shares (how often the two meet, where, at
what speed) is common to both cells and cancels in their ratio, so the edge flow

    Y_ij = log(H_ij + c) - log(H_ji + c)

says only who takes the damage. Combinatorial Hodge theory (Jiang et al. 2011)
splits a flow on a graph into a gradient, Y_ij = phi_i - phi_j with one potential
per actor type, and a remainder no potential can explain. A high potential is an
actor type that takes the damage.

The fit is weighted least squares with the inverse-variance weight of the
log-ratio of two Poisson counts, w = 1 / (1/(H_ij + c) + 1/(H_ji + c)). That
weight makes the least-squares potential the large-sample Bradley-Terry estimate
and gives it a covariance, the pseudo-inverse of the weighted Laplacian, so every
potential carries a standard error.

The route reads the matrix another route exported and writes four tables:
potentials at four aggregation levels, the edges and the triangles of the city,
and the test of whether the units differ. It computes no interpretation: the mass
line, the external sources and the prose live with the documents that use them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src import config
from src.provenance import RunLog

MATRIX_FILES = {
    config.OBSERVED_DATASET: f"{config.ANALYSIS_PREFIX}__matrix_long.parquet",
    config.CORRECTED_DATASET: f"{config.ANALYSIS_PREFIX}__matrix_long__{config.CORRECTION_FILE_SUFFIX}.parquet",
}
RHO_FILE = f"{config.ANALYSIS_PREFIX}__rho_long.parquet"

ACTORS: tuple[str, ...] = tuple(config.MATRIX_ROW_ORDER)
INDEX = {actor: position for position, actor in enumerate(ACTORS)}


# ---------------------------------------------------------------------------
# The decomposition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Flow:
    """The edge flow of one matrix on one set of vertices."""

    edges: tuple[tuple[int, int], ...]  # (i, j) with i before j in ACTORS
    flow: np.ndarray
    weight: np.ndarray
    forward: np.ndarray  # H_ij, before the correction
    backward: np.ndarray  # H_ji


@dataclass(frozen=True)
class Fit:
    """The gradient part of a flow and what it leaves."""

    potential: np.ndarray  # NaN for a vertex no edge reaches
    covariance: np.ndarray  # of the potential, in the gauge of zero mean per component
    gradient: np.ndarray
    residual: np.ndarray
    gradient_share: float  # 1 - weighted residual / weighted flow; NaN with no flow
    residual_sum: float  # weighted sum of squared residuals
    residual_df: int  # edges minus free potentials
    components: int


def edge_flow(matrix: np.ndarray, vertices: tuple[int, ...], continuity: float) -> Flow:
    """The flow on every edge between two vertices that has at least one crash.

    An edge with a zero on one side keeps its comparison thanks to the correction; an
    edge with no crash on either side has nothing to compare and is left out rather
    than entered as a tie.
    """
    edges, flow, weight, forward, backward = [], [], [], [], []
    for position, i in enumerate(vertices):
        for j in vertices[position + 1:]:
            h_ij, h_ji = matrix[i, j], matrix[j, i]
            if h_ij + h_ji == 0:
                continue
            edges.append((i, j))
            flow.append(np.log(h_ij + continuity) - np.log(h_ji + continuity))
            weight.append(1.0 / (1.0 / (h_ij + continuity) + 1.0 / (h_ji + continuity)))
            forward.append(h_ij)
            backward.append(h_ji)
    return Flow(tuple(edges), np.array(flow), np.array(weight), np.array(forward), np.array(backward))


def _components(edges: tuple[tuple[int, int], ...]) -> list[set[int]]:
    """The connected components of the vertices the edges reach."""
    parent: dict[int, int] = {}

    def root(v: int) -> int:
        while parent.setdefault(v, v) != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for i, j in edges:
        parent[root(i)] = root(j)
    groups: dict[int, set[int]] = {}
    for v in list(parent):
        groups.setdefault(root(v), set()).add(v)
    return list(groups.values())


def laplacian(flow: Flow, size: int) -> tuple[np.ndarray, np.ndarray]:
    """The weighted graph Laplacian and the weighted divergence of the flow.

    The potential solves L phi = b (Jiang et al. 2011, theorem 3, with the sign
    flipped so that a high potential takes the damage).
    """
    lap = np.zeros((size, size))
    div = np.zeros(size)
    for (i, j), y, w in zip(flow.edges, flow.flow, flow.weight):
        lap[i, i] += w
        lap[j, j] += w
        lap[i, j] -= w
        lap[j, i] -= w
        div[i] += w * y
        div[j] -= w * y
    return lap, div


def fit(flow: Flow, size: int = len(ACTORS)) -> Fit:
    """The weighted least-squares potential.

    The pseudo-inverse picks, in each connected component, the potential of zero
    mean; for one connected graph that is the usual gauge. With inverse-variance
    weights it is also the covariance of that potential.
    """
    lap, div = laplacian(flow, size)
    covariance = np.linalg.pinv(lap)
    potential = covariance @ div
    reached = sorted({v for edge in flow.edges for v in edge})
    unreached = [v for v in range(size) if v not in reached]
    potential[unreached] = np.nan
    gradient = np.array([potential[i] - potential[j] for i, j in flow.edges])
    residual = flow.flow - gradient
    residual_sum = float(np.sum(flow.weight * residual ** 2))
    total = float(np.sum(flow.weight * flow.flow ** 2))
    components = _components(flow.edges)
    free = len(reached) - len(components)
    return Fit(
        potential=potential,
        covariance=covariance,
        gradient=gradient,
        residual=residual,
        gradient_share=1.0 - residual_sum / total if total > 0 else np.nan,
        residual_sum=residual_sum,
        residual_df=len(flow.edges) - free,
        components=len(components),
    )


def contrast(result: Fit, actor: int, reference: int) -> tuple[float, float]:
    """phi_actor - phi_reference and its standard error, which the gauge does not touch."""
    value = result.potential[actor] - result.potential[reference]
    if np.isnan(value):
        return np.nan, np.nan
    c = result.covariance
    variance = c[actor, actor] + c[reference, reference] - 2 * c[actor, reference]
    return float(value), float(np.sqrt(max(variance, 0.0)))


def triangles(flow: Flow) -> list[tuple[int, int, int, float]]:
    """The curl of every triangle whose three edges carry a flow.

    The curl Y_ij + Y_jk + Y_ki is zero for any gradient, so it measures the cycle
    directly and needs no fit.
    """
    value = {edge: y for edge, y in zip(flow.edges, flow.flow)}

    def oriented(a: int, b: int) -> float | None:
        if (a, b) in value:
            return value[(a, b)]
        if (b, a) in value:
            return -value[(b, a)]
        return None

    vertices = sorted({v for edge in flow.edges for v in edge})
    out = []
    for p, i in enumerate(vertices):
        for q, j in enumerate(vertices[p + 1:], start=p + 1):
            for k in vertices[q + 1:]:
                sides = (oriented(i, j), oriented(j, k), oriented(k, i))
                if all(side is not None for side in sides):
                    out.append((i, j, k, float(sum(sides))))
    return out


# ---------------------------------------------------------------------------
# Reading the matrix
# ---------------------------------------------------------------------------


def read_inputs(log: RunLog) -> dict[str, pd.DataFrame]:
    """The two matrix tables and the rho table, each from the run config names."""
    frames: dict[str, pd.DataFrame] = {}
    for dataset, filename in MATRIX_FILES.items():
        run_dir = config.run_directory_holding(filename, config.HODGE_MATRIX_SOURCE_RUN)
        frames[dataset] = pd.read_parquet(run_dir / config.DATA_SUBDIR / filename)
        log.info("%s matrix read from %s", dataset, run_dir.name)
    run_dir = config.run_directory_holding(RHO_FILE, config.HODGE_RHO_SOURCE_RUN)
    frames["rho"] = pd.read_parquet(run_dir / config.DATA_SUBDIR / RHO_FILE)
    log.info("rho table read from %s", run_dir.name)
    return frames


def matrices(long_table: pd.DataFrame, count: str, log: RunLog | None = None) -> dict[tuple[str, int], np.ndarray]:
    """One 6 x 6 matrix per unit and year, rows hurt and columns counterpart.

    The column without counterpart is left out: a one-party crash compares nothing.
    Every unit-year of the table gets a matrix, zero included, so a year with no
    crash in a unit is a true zero and not a missing cell.
    """
    two_party = long_table[long_table[config.COUNTERPART_TYPE_COL].isin(ACTORS)]
    if log is not None:
        log.record(
            f"two-party cells of the {long_table[config.DATASET_COL].iloc[0]} matrix, {count}",
            rows_in=len(long_table),
            rows_out=len(two_party),
            changes=[(len(two_party) - len(long_table), "cells of the column without counterpart")],
        )
    cube = two_party.pivot_table(
        index=[config.AREA_CODE_COL, config.YEAR_COL, config.PARTY_TYPE_COL],
        columns=config.COUNTERPART_TYPE_COL, values=count, aggfunc="sum", fill_value=0,
    ).reindex(columns=list(ACTORS), fill_value=0)
    out = {}
    for (area, year), block in cube.groupby(level=[0, 1]):
        block = block.droplevel([0, 1]).reindex(index=list(ACTORS), fill_value=0)
        out[(area, int(year))] = block.to_numpy(dtype=float)
    return out


def aggregate(cells: dict[tuple[str, int], np.ndarray]) -> dict[tuple[str, str, int | None], np.ndarray]:
    """The four levels: every unit-year, every city-year, every unit pooled, the city pooled."""
    out: dict[tuple[str, str, int | None], np.ndarray] = {}
    zero = np.zeros((len(ACTORS), len(ACTORS)))
    for (area, year), matrix in cells.items():
        out[(config.HODGE_UNIT_YEAR, area, year)] = matrix
        key_city_year = (config.HODGE_CITY_YEAR, config.CITY_AREA_CODE, year)
        key_unit = (config.HODGE_UNIT_ALL_YEARS, area, None)
        key_city = (config.HODGE_CITY_ALL_YEARS, config.CITY_AREA_CODE, None)
        for key in (key_city_year, key_unit, key_city):
            out[key] = out.get(key, zero) + matrix
    return out


# ---------------------------------------------------------------------------
# The route's tables
# ---------------------------------------------------------------------------


@dataclass
class Tables:
    potential: pd.DataFrame
    edges: pd.DataFrame
    triangles: pd.DataFrame
    heterogeneity: pd.DataFrame
    # Kept for the checks, never exported.
    city_matrices: dict[tuple[str, str], np.ndarray]
    unit_flows: dict[tuple[str, str, str], dict[str, Flow]]


def compute(frames: dict[str, pd.DataFrame], log: RunLog) -> Tables:
    reference = INDEX[config.HODGE_REFERENCE_ACTOR]
    potential_rows, edge_rows, triangle_rows = [], [], []
    city_matrices: dict[tuple[str, str], np.ndarray] = {}
    unit_flows: dict[tuple[str, str, str], dict[str, Flow]] = {}
    reference_flows: dict[tuple[str, str, str], dict[str, Flow]] = {}

    for dataset in MATRIX_FILES:
        long_table = frames[dataset]
        names = long_table.drop_duplicates(config.AREA_CODE_COL).set_index(config.AREA_CODE_COL)[config.AREA_NAME_COL]
        scale = long_table[config.SCALE_COL].iloc[0]
        years = sorted(int(y) for y in long_table[config.YEAR_COL].unique())
        for count in config.HODGE_COUNTS:
            cells = matrices(long_table, count, log if count == config.AFFECTED_PARTIES_COL else None)
            levels = aggregate(cells)
            # The reference window, where the correction changes nothing, pooled per unit for
            # the second heterogeneity test (D69). Only the observed set needs it: there the two
            # sets coincide.
            if dataset == config.OBSERVED_DATASET:
                reference_cells: dict[str, np.ndarray] = {}
                for (area, year), matrix in cells.items():
                    if year in config.CORRECTION_REFERENCE_YEARS:
                        reference_cells[area] = reference_cells.get(area, 0) + matrix
            city_matrices[(dataset, count)] = levels[(config.HODGE_CITY_ALL_YEARS, config.CITY_AREA_CODE, None)]
            for layer, actors in config.HODGE_LAYERS.items():
                vertices = tuple(INDEX[a] for a in actors)
                unit_flows[(dataset, count, layer)] = {}
                if dataset == config.OBSERVED_DATASET:
                    reference_flows[(dataset, count, layer)] = {
                        area: edge_flow(matrix, vertices, config.HODGE_CONTINUITY)
                        for area, matrix in reference_cells.items()}
                for (level, area, year), matrix in levels.items():
                    flow = edge_flow(matrix, vertices, config.HODGE_CONTINUITY)
                    if level == config.HODGE_UNIT_ALL_YEARS:
                        unit_flows[(dataset, count, layer)][area] = flow
                    result = fit(flow)
                    dispersion = result.residual_sum / result.residual_df if result.residual_df > 0 else np.nan
                    common = {
                        config.DATASET_COL: dataset, config.SCALE_COL: scale, config.HODGE_LEVEL_COL: level,
                        config.AREA_CODE_COL: area,
                        config.AREA_NAME_COL: config.CITY_AREA_NAME if area == config.CITY_AREA_CODE else names[area],
                        config.YEAR_COL: year,
                        "FIRST_YEAR": year if year is not None else years[0],
                        "LAST_YEAR": year if year is not None else years[-1],
                        config.HODGE_LAYER_COL: layer, config.HODGE_COUNT_COL: count,
                    }
                    for actor in actors:
                        value, error = contrast(result, INDEX[actor], reference)
                        potential_rows.append({
                            **common, config.ROAD_USER_TYPE_COL: actor,
                            "POTENTIAL": result.potential[INDEX[actor]],
                            "POTENTIAL_VS_REFERENCE": value, "STD_ERROR_VS_REFERENCE": error,
                            "GRADIENT_SHARE": result.gradient_share, "EDGES": len(flow.edges),
                            "COMPONENTS": result.components,
                            "COMPARISONS": float(np.sum(flow.forward + flow.backward)),
                            "DISPERSION": dispersion,
                        })
                    if level in (config.HODGE_CITY_ALL_YEARS, config.HODGE_CITY_YEAR):
                        for (i, j), y, w, f, b, g, r in zip(flow.edges, flow.flow, flow.weight, flow.forward,
                                                           flow.backward, result.gradient, result.residual):
                            edge_rows.append({
                                **common, config.PAIR_FIRST_COL: ACTORS[i], config.PAIR_SECOND_COL: ACTORS[j],
                                "COUNT_FIRST_HURT": f, "COUNT_SECOND_HURT": b, "FLOW": y, "WEIGHT": w,
                                "GRADIENT": g, "RESIDUAL": r,
                            })
                    if level == config.HODGE_CITY_ALL_YEARS:
                        for i, j, k, curl in triangles(flow):
                            triangle_rows.append({**common, "TYPE_A": ACTORS[i], "TYPE_B": ACTORS[j],
                                                  "TYPE_C": ACTORS[k], "CURL": curl})

    potential = pd.DataFrame(potential_rows)
    potential[config.YEAR_COL] = potential[config.YEAR_COL].astype("Int64")
    edges = pd.DataFrame(edge_rows)
    edges[config.YEAR_COL] = edges[config.YEAR_COL].astype("Int64")
    triangle_table = pd.DataFrame(triangle_rows)
    triangle_table[config.YEAR_COL] = triangle_table[config.YEAR_COL].astype("Int64")
    heterogeneity = pd.concat(
        [heterogeneity_test(flows, dataset, count, layer, config.HODGE_WINDOW_ALL_YEARS)
         for (dataset, count, layer), flows in unit_flows.items()]
        + [heterogeneity_test(flows, dataset, count, layer, config.HODGE_WINDOW_REFERENCE)
           for (dataset, count, layer), flows in reference_flows.items()],
        ignore_index=True,
    )
    return Tables(potential, edges, triangle_table, heterogeneity, city_matrices, unit_flows)


def heterogeneity_test(flows: dict[str, Flow], dataset: str, count: str, layer: str, window: str) -> pd.DataFrame:
    """Do the units differ in potential beyond what sampling explains?

    Two nested fits on the edges of every unit pooled over the window: one potential
    per unit, and one potential common to all units. The weighted residual each adds
    is chi-squared under the Poisson variance, so their difference tests the common
    potential with (units - 1) x (free potentials) degrees of freedom. Crash counts
    are often more variable than Poisson, which would inflate that statistic, so the
    test that decides divides it by the within-unit residual, the cycles no potential
    explains, and reads an F. Units whose graph is not connected are left out, since
    their potentials are not comparable across components.

    One row for the whole test and one per actor type, the latter a Cochran Q on that
    type's contrast against the reference across units.

    Two rows decide, and they have to agree. The corrected set over the window is the set
    the study reports, but the correction brings each unit toward the city's reference
    rho, which pulls the unit potentials together: there the between-unit statistic falls
    well below its degrees of freedom, which sampling alone does not do. The observed set
    in the reference years, which the correction leaves untouched, is the test that the
    correction cannot have shaped.
    """
    reference = INDEX[config.HODGE_REFERENCE_ACTOR]
    connected = {area: flow for area, flow in flows.items() if fit(flow).components == 1}
    left_out = len(flows) - len(connected)
    size = len(ACTORS)

    separate_sum = separate_df = 0.0
    total_lap, total_div = np.zeros((size, size)), np.zeros(size)
    per_unit = {}
    for area, flow in connected.items():
        result = fit(flow)
        per_unit[area] = result
        separate_sum += result.residual_sum
        separate_df += result.residual_df
        lap, div = laplacian(flow, size)
        total_lap += lap
        total_div += div
    common_potential = np.linalg.pinv(total_lap) @ total_div
    common_sum = 0.0
    edge_count = 0
    for flow in connected.values():
        common_gradient = np.array([common_potential[i] - common_potential[j] for i, j in flow.edges])
        common_sum += float(np.sum(flow.weight * (flow.flow - common_gradient) ** 2))
        edge_count += len(flow.edges)
    vertices = sorted({v for flow in connected.values() for edge in flow.edges for v in edge})
    common_df = edge_count - (len(vertices) - 1)
    between = common_sum - separate_sum
    between_df = common_df - separate_df
    chi_p = float(stats.chi2.sf(between, between_df)) if between_df > 0 else np.nan
    dispersion = separate_sum / separate_df if separate_df > 0 else np.nan
    f_value = (between / between_df) / dispersion if between_df > 0 and dispersion > 0 else np.nan
    f_p = float(stats.f.sf(f_value, between_df, separate_df)) if not np.isnan(f_value) else np.nan
    declared = (layer == config.HODGE_HETEROGENEITY_LAYER and count == config.AFFECTED_PARTIES_COL
                and (dataset, window) in config.HODGE_HETEROGENEITY_TESTS)
    base = {config.DATASET_COL: dataset, "WINDOW": window, config.HODGE_LAYER_COL: layer,
            config.HODGE_COUNT_COL: count, "DECLARED_TEST": declared, "UNITS": len(connected),
            "UNITS_LEFT_OUT": left_out}
    rows = [{
        **base, config.ROAD_USER_TYPE_COL: "ALL",
        "STATISTIC": between, "DF": between_df, "P_VALUE_CHI2": chi_p,
        "DISPERSION": dispersion, "F": f_value, "DF_RESIDUAL": separate_df, "P_VALUE_F": f_p,
        "I2": max(0.0, (between - between_df) / between) if between > 0 else 0.0,
        "UNITS_DIFFER": bool(f_p < config.HODGE_HETEROGENEITY_ALPHA) if not np.isnan(f_p) else None,
    }]
    for actor_index in vertices:
        if actor_index == reference:
            continue
        values, errors = [], []
        for result in per_unit.values():
            value, error = contrast(result, actor_index, reference)
            if not np.isnan(value) and error > 0:
                values.append(value)
                errors.append(error)
        values, errors = np.array(values), np.array(errors)
        weights = 1.0 / errors ** 2
        mean = float(np.sum(weights * values) / np.sum(weights))
        q = float(np.sum(weights * (values - mean) ** 2))
        df = len(values) - 1
        rows.append({
            **base, config.ROAD_USER_TYPE_COL: ACTORS[actor_index],
            "STATISTIC": q, "DF": df, "P_VALUE_CHI2": float(stats.chi2.sf(q, df)) if df > 0 else np.nan,
            "DISPERSION": dispersion,
            "F": (q / df) / dispersion if df > 0 and dispersion > 0 else np.nan,
            "DF_RESIDUAL": separate_df,
            "P_VALUE_F": float(stats.f.sf((q / df) / dispersion, df, separate_df)) if df > 0 and dispersion > 0 else np.nan,
            "I2": max(0.0, (q - df) / q) if q > 0 else 0.0,
            "UNITS_DIFFER": None,
            "MEAN_VS_REFERENCE": mean, "SD_ACROSS_UNITS": float(np.std(values, ddof=1)),
            "RMS_STD_ERROR": float(np.sqrt(np.mean(errors ** 2))),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Export, checks and report
# ---------------------------------------------------------------------------


NOTES = {
    config.HODGE_POTENTIAL_FILENAME: (
        "# HodgeRank potentials of the casualty matrix (D69). POTENTIAL has zero mean over the actor "
        "types of its graph; POTENTIAL_VS_REFERENCE is the difference against CAR and does not depend "
        "on that choice. STD_ERROR_VS_REFERENCE assumes Poisson counts: multiply it by the square root "
        "of DISPERSION where that exceeds 1. In the ALL_ACTORS layer the pedestrian potential is an "
        "upper bound, because an unhurt pedestrian is almost never recorded; read WITHOUT_PEDESTRIAN "
        "for anything interpreted. Continuity correction 0.5 on every edge with a crash.\n"
    ),
    config.HODGE_EDGES_FILENAME: (
        "# One row per edge with a crash. FLOW = log(COUNT_FIRST_HURT + 0.5) - log(COUNT_SECOND_HURT + "
        "0.5), positive when the first type takes the damage; GRADIENT is the part the potential "
        "explains and RESIDUAL the rest (D69).\n"
    ),
    config.HODGE_TRIANGLES_FILENAME: (
        "# The curl Y_AB + Y_BC + Y_CA of every triangle of the city graph; zero for a pure gradient (D69).\n"
    ),
    config.HODGE_HETEROGENEITY_FILENAME: (
        "# Do the units differ in potential beyond sampling? ALL rows compare one potential per unit "
        "with one common potential; P_VALUE_F divides by the within-unit residual and is the one that "
        "decides, on the row with DECLARED_TEST true (D69). Per-type rows are Cochran Q tests on the "
        "contrast against CAR.\n"
    ),
}


def export(tables: Tables, log: RunLog) -> dict[str, Path]:
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, frame in ((config.HODGE_POTENTIAL_FILENAME, tables.potential),
                        (config.HODGE_EDGES_FILENAME, tables.edges),
                        (config.HODGE_TRIANGLES_FILENAME, tables.triangles),
                        (config.HODGE_HETEROGENEITY_FILENAME, tables.heterogeneity)):
        path = data_dir / f"{name}.csv"
        with open(path, "w", encoding="utf-8", newline="") as handle:
            frame.to_csv(handle, index=False)
            handle.write(NOTES[name])
        frame.to_parquet(path.with_suffix(".parquet"))
        paths[name] = path
    log.info("exported the four Hodge tables to %s/", config.DATA_SUBDIR)
    return paths


def _synthetic_checks() -> list[tuple[str, bool, str]]:
    """Three tests on matrices whose answer is known, run before the data are trusted."""
    checks = []
    size = len(ACTORS)
    vertices = tuple(range(size))

    # A known potential. Counts built as the Bradley-Terry expectation of a large
    # symmetric exposure give back that potential up to the correction's bias.
    truth = np.array([1.5, 1.0, 0.8, 0.0, -0.9, -1.6])
    exposure = 1e7
    matrix = np.zeros((size, size))
    for i in range(size):
        for j in range(size):
            if i != j:
                matrix[i, j] = exposure * np.exp(truth[i]) / (np.exp(truth[i]) + np.exp(truth[j]))
    result = fit(edge_flow(matrix, vertices, config.HODGE_CONTINUITY))
    worst = float(np.max(np.abs((result.potential - result.potential.mean()) - (truth - truth.mean()))))
    checks.append(("a known potential is recovered", worst < 1e-5 and result.gradient_share > 1 - 1e-9,
                   f"worst difference {worst:.1e}, gradient share {result.gradient_share:.10f}"))

    # An injected cycle. With equal weights a cycle is orthogonal to every gradient,
    # so it must leave the potential untouched and show up whole in the curl.
    flow = edge_flow(matrix, vertices, config.HODGE_CONTINUITY)
    equal = Flow(flow.edges, flow.flow.copy(), np.ones(len(flow.edges)), flow.forward, flow.backward)
    cycled_flow = equal.flow.copy()
    loop = 0.3
    for position, edge in enumerate(equal.edges):
        if edge in ((0, 1), (1, 2)):
            cycled_flow[position] += loop
        elif edge == (0, 2):
            cycled_flow[position] -= loop  # the cycle 0 -> 1 -> 2 -> 0 runs against this edge
    cycled = Flow(equal.edges, cycled_flow, equal.weight, equal.forward, equal.backward)
    before, after = fit(equal), fit(cycled)
    shift = float(np.max(np.abs(after.potential - before.potential)))
    # The curl added by the cycle, net of the base's: the correction makes the base flow
    # a gradient only up to about 1e-8, so its own curl is not exactly zero.
    curl = ({(i, j, k): c for i, j, k, c in triangles(cycled)}[(0, 1, 2)]
            - {(i, j, k): c for i, j, k, c in triangles(equal)}[(0, 1, 2)])
    checks.append(("an injected cycle leaves the potential alone and appears in the curl",
                   shift < 1e-10 and abs(curl - 3 * loop) < 1e-12 and after.gradient_share < 1,
                   f"potential moved {shift:.1e}, added curl {curl:.12f} against {3 * loop}"))

    # The correction. A zero on one side keeps the edge with a finite flow; no crash
    # on either side drops it.
    sparse = np.zeros((size, size))
    sparse[0, 1] = 7
    sparse[2, 3] = 0
    small = edge_flow(sparse, vertices, config.HODGE_CONTINUITY)
    kept = small.edges == ((0, 1),)
    finite = bool(np.isfinite(small.flow).all()) and abs(small.flow[0] - np.log(7.5 / 0.5)) < 1e-12
    checks.append(("a one-sided edge enters with a finite flow and an empty one stays out", kept and finite,
                   f"edges {small.edges}, flow {small.flow}"))
    return checks


def verify(tables: Tables, frames: dict[str, pd.DataFrame], log: RunLog) -> bool:
    checks = _synthetic_checks()

    # The decomposition is orthogonal: gradient and residual are perpendicular in the
    # weighted inner product, which is what makes the gradient share a share.
    worst = 0.0
    for flows in tables.unit_flows.values():
        for flow in flows.values():
            result = fit(flow)
            if result.components == 1 and len(flow.edges):
                inner = abs(float(np.sum(flow.weight * result.gradient * result.residual)))
                worst = max(worst, inner / max(float(np.sum(flow.weight * flow.flow ** 2)), 1e-12))
    checks.append(("gradient and residual are orthogonal in every connected unit graph", worst < 1e-9,
                   f"worst relative inner product {worst:.1e}"))

    # The identity of the two sides. In every pair the two cells count the same crashes:
    # H_ij + H_ji - K_ij = n_ij, with n the crashes with at least one party hurt and K
    # those with both, as the rho route counts them from the party universe.
    rho = frames["rho"]
    rho = rho[rho[config.AGGREGATION_LEVEL_COL] == config.CITY_LEVEL]
    observed_years = set(frames[config.OBSERVED_DATASET][config.YEAR_COL].astype(int))
    rho = rho[rho[config.YEAR_COL].astype(int).isin(observed_years)]
    pairs = rho.groupby([config.PAIR_FIRST_COL, config.PAIR_SECOND_COL])[
        [config.RHO_NUMERATOR_COL, config.RHO_DENOMINATOR_COL]].sum()
    city = tables.city_matrices[(config.OBSERVED_DATASET, config.AFFECTED_PARTIES_COL)]
    gaps = []
    for (first, second), row in pairs.iterrows():
        i, j = INDEX[first], INDEX[second]
        gaps.append(city[i, j] + city[j, i] - row[config.RHO_NUMERATOR_COL] - row[config.RHO_DENOMINATOR_COL])
    checks.append(("both sides of every pair count the same crashes as rho does",
                   len(gaps) == len(config.RHO_PAIRS) and all(g == 0 for g in gaps),
                   f"{len(gaps)} pairs, gaps {sorted(set(gaps))}"))

    # The record balance: the city matrices hold every two-party cell that was read.
    for dataset in MATRIX_FILES:
        table = frames[dataset]
        for count in config.HODGE_COUNTS:
            read = int(table.loc[table[config.COUNTERPART_TYPE_COL].isin(ACTORS), count].sum())
            held = int(tables.city_matrices[(dataset, count)].sum())
            checks.append((f"the city matrix holds every two-party count read, {dataset} {count}",
                           read == held, f"{held} of {read}"))

    # Levels close: summing the city-year potentials' inputs is checked through the
    # matrices above; here every level has the rows it should.
    potential = tables.potential
    expected_units = {d: frames[d][config.AREA_CODE_COL].nunique() for d in MATRIX_FILES}
    expected_years = {d: frames[d][config.YEAR_COL].nunique() for d in MATRIX_FILES}
    actors_per_layer = sum(len(a) for a in config.HODGE_LAYERS.values())
    expected_rows = sum((1 + expected_years[d] + expected_units[d] + expected_units[d] * expected_years[d])
                        for d in MATRIX_FILES) * len(config.HODGE_COUNTS) * actors_per_layer
    checks.append(("one potential row per level, place, year, layer, count and actor type",
                   len(potential) == expected_rows, f"{len(potential)} of {expected_rows}"))

    city_rows = potential[potential[config.HODGE_LEVEL_COL] == config.HODGE_CITY_ALL_YEARS]
    gauge = city_rows.groupby([config.DATASET_COL, config.HODGE_LAYER_COL, config.HODGE_COUNT_COL])["POTENTIAL"].sum()
    checks.append(("the city potentials have zero mean", bool((gauge.abs() < 1e-9).all()),
                   f"worst sum {gauge.abs().max():.1e}"))
    complete = bool((city_rows["COMPONENTS"] == 1).all())
    checks.append(("the city graph is connected in every set, layer and count", complete, ""))
    vehicles = potential[potential[config.HODGE_LAYER_COL] == config.HODGE_LAYER_VEHICLES]
    checks.append(("the vehicle layer holds no pedestrian",
                   not (vehicles[config.ROAD_USER_TYPE_COL] == config.PEDESTRIAN).any(), ""))

    declared = tables.heterogeneity[tables.heterogeneity["DECLARED_TEST"]
                                    & (tables.heterogeneity[config.ROAD_USER_TYPE_COL] == "ALL")]
    checks.append(("both declared heterogeneity tests ran and returned a p-value",
                   len(declared) == len(config.HODGE_HETEROGENEITY_TESTS)
                   and declared["P_VALUE_F"].between(0, 1).all(), f"{len(declared)} row(s)"))

    width = max(len(name) for name, _, _ in checks)
    lines = [f"{'check'.ljust(width)}  {'result':>8}  detail", f"{'-' * width}  {'-' * 8}  ------"]
    for name, ok, detail in checks:
        lines.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("hodge verification:", "\n".join(lines))
    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("hodge verification FAILED")
    return passed


def report(tables: Tables, log: RunLog) -> None:
    """The city potentials and the verdict of the declared test."""
    city = tables.potential[(tables.potential[config.HODGE_LEVEL_COL] == config.HODGE_CITY_ALL_YEARS)
                            & (tables.potential[config.HODGE_COUNT_COL] == config.AFFECTED_PARTIES_COL)]
    lines = []
    for (dataset, layer), group in city.groupby([config.DATASET_COL, config.HODGE_LAYER_COL], sort=False):
        lines.append(f"{dataset} {layer}: gradient share {group['GRADIENT_SHARE'].iloc[0]:.4f}, "
                     f"dispersion {group['DISPERSION'].iloc[0]:.2f}")
        for row in group.itertuples():
            lines.append(f"    {getattr(row, config.ROAD_USER_TYPE_COL):<18} "
                         f"{row.POTENTIAL_VS_REFERENCE:+.3f} ({row.STD_ERROR_VS_REFERENCE:.3f})")
    log.table("city potentials against the car, parties:", "\n".join(lines))

    declared = tables.heterogeneity[tables.heterogeneity["DECLARED_TEST"]
                                    & (tables.heterogeneity[config.ROAD_USER_TYPE_COL] == "ALL")]
    for row in declared.itertuples():
        log.info("heterogeneity, %s %s %s parties: chi2 = %.1f on %d (p = %.3g); F = %.2f on %d and %d "
                 "(p = %.3g), within-unit dispersion %.2f, I2 %.2f, %d units (%d left out)",
                 getattr(row, config.DATASET_COL), row.WINDOW, getattr(row, config.HODGE_LAYER_COL),
                 row.STATISTIC, row.DF, row.P_VALUE_CHI2, row.F, row.DF, row.DF_RESIDUAL, row.P_VALUE_F,
                 row.DISPERSION, row.I2, row.UNITS, row.UNITS_LEFT_OUT)
    differ = set(declared["UNITS_DIFFER"])
    if differ == {False}:
        log.info("verdict: the units do not differ beyond sampling in either test; the unit potential "
                 "stays descriptive and the asymmetry belongs to the city (D69)")
    elif differ == {True}:
        log.info("verdict: the units differ in both tests; the unit potential is a candidate response (D69)")
    else:
        log.warn("verdict: the two declared tests disagree; the decision of D69 does not follow from "
                 "this run and has to be taken up again")
