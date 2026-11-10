"""What the dependence between the two cells of a pair does to the Hodge fit.

    .venv/Scripts/python.exe tools/dependencia_de_las_celdas.py

**Read only.** It reads the matrix and the rho table that `config.HODGE_MATRIX_SOURCE_RUN` and
`config.HODGE_RHO_SOURCE_RUN` name, calls `src/hodge.py` rather than repeating it, and writes nothing.

**The question.** The route weights each edge by the inverse of the variance of the log-ratio of two
*independent* Poisson counts, 1/H_ij + 1/H_ji. The two cells are not independent: a crash in which both
parties were hurt adds one to each. With the crashes of a pair split into three independent Poisson
counts (only the first side hurt, only the second, both), the covariance of the two cells is the
expected number of crashes with both hurt, K_ij, and the delta method gives

    Var(log H_ij - log H_ji) ~ 1/H_ij + 1/H_ji - 2 K_ij / (H_ij H_ji),

with the continuity correction added to both cells as the route adds it. The independent variance
overstates this one, and by more the larger the share of crashes with both hurt. Since that share
differs between pairs, the overstatement is not a common factor that the dispersion scaling absorbs:
it changes the relative weights. This script measures by how much the potentials, their errors, the
gradient share, the dispersion and the heterogeneity test move when the weights use the dependent
variance.

**Where K is known.** The rho route counts K for its nine pairs, which cover every edge among bicycle,
motorcycle, car and public transport but none with the "other vehicles" type. So the vehicle layer is
measured two ways: on the four types whose six edges all have K, exactly, and on all five types with
the four edges of "other" kept at the independent variance.

**The corrected set.** The rho correction adds, in crashes already counted, the second party the record
left out, so it leaves the number of crashes of a pair unchanged and turns crashes with one side hurt
into crashes with both. Its K is therefore H_ij + H_ji - n_ij, with n_ij the crashes of the observed
set; the script checks that this lies between the observed K and the smaller cell. In the reference
years 2023-2024 the two sets coincide and K is observed directly.
"""

from __future__ import annotations

import dataclasses
import sys

from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config, hodge  # noqa: E402

FOUR = (config.BICYCLE, config.MOTORCYCLE, config.CAR, config.PUBLIC_TRANSPORT)
FIVE = config.HODGE_LAYERS[config.HODGE_LAYER_VEHICLES]
C = config.HODGE_CONTINUITY


def read() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    tables = {}
    for dataset, filename in hodge.MATRIX_FILES.items():
        run_dir = config.run_directory_holding(filename, config.HODGE_MATRIX_SOURCE_RUN)
        tables[dataset] = pd.read_parquet(run_dir / config.DATA_SUBDIR / filename)
    print(f"matrix read from {run_dir.name}")
    run_dir = config.run_directory_holding(hodge.RHO_FILE, config.HODGE_RHO_SOURCE_RUN)
    rho = pd.read_parquet(run_dir / config.DATA_SUBDIR / hodge.RHO_FILE)
    print(f"rho table read from {run_dir.name}\n")
    return tables, rho


def pooled(long_table: pd.DataFrame, years) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """The city matrix and one matrix per unit, pooled over the years given."""
    cells = hodge.matrices(long_table[long_table[config.YEAR_COL].astype(int).isin(list(years))],
                           config.AFFECTED_PARTIES_COL)
    units: dict[str, np.ndarray] = {}
    for (unit, _), matrix in cells.items():
        units[unit] = units.get(unit, 0) + matrix
    return sum(units.values()), units


def crash_counts(rho: pd.DataFrame, level: str, years) -> dict[tuple[str, tuple[int, int]], tuple[float, float]]:
    """(area, (i, j)) -> (crashes with both hurt, crashes with at least one), i before j in ACTORS."""
    rows = rho[(rho[config.AGGREGATION_LEVEL_COL] == level) & rho[config.YEAR_COL].astype(int).isin(list(years))]
    summed = rows.groupby([config.AREA_CODE_COL, config.PAIR_FIRST_COL, config.PAIR_SECOND_COL])[
        [config.RHO_NUMERATOR_COL, config.RHO_DENOMINATOR_COL]].sum()
    out = {}
    for (area, first, second), row in summed.iterrows():
        i, j = sorted((hodge.INDEX[first], hodge.INDEX[second]))
        out[(area, (i, j))] = (float(row[config.RHO_NUMERATOR_COL]), float(row[config.RHO_DENOMINATOR_COL]))
    return out


def both_hurt(matrix: np.ndarray, edge: tuple[int, int], counts, area: str, corrected: bool) -> float | None:
    """K for one edge, or None where the rho route does not count that pair."""
    if (area, edge) not in counts:
        return None
    k_observed, n = counts[(area, edge)]
    if not corrected:
        return k_observed
    i, j = edge
    k = matrix[i, j] + matrix[j, i] - n
    smaller = min(matrix[i, j], matrix[j, i])
    assert k_observed - 1e-6 <= k <= smaller + 1e-6, (area, edge, k_observed, k, smaller)
    return float(k)


def dependent(flow: hodge.Flow, matrix: np.ndarray, counts, area: str, corrected: bool) -> hodge.Flow:
    """The same flow with the weight of the dependent variance where K is known."""
    weights = flow.weight.copy()
    for position, edge in enumerate(flow.edges):
        k = both_hurt(matrix, edge, counts, area, corrected)
        if k is None:
            continue
        a, b = flow.forward[position] + C, flow.backward[position] + C
        variance = 1 / a + 1 / b - 2 * k / (a * b)
        weights[position] = 1 / variance
    return dataclasses.replace(flow, weight=weights)


def summary(flow: hodge.Flow, actors) -> dict:
    result = hodge.fit(flow)
    dispersion = result.residual_sum / result.residual_df
    reference = hodge.INDEX[config.HODGE_REFERENCE_ACTOR]
    out = {"gradient share": round(100 * result.gradient_share, 2), "dispersion": round(dispersion, 1)}
    for actor in actors:
        if actor == config.HODGE_REFERENCE_ACTOR:
            continue
        value, error = hodge.contrast(result, hodge.INDEX[actor], reference)
        out[actor] = f"{value:+.3f} ({error * np.sqrt(dispersion):.3f})"
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    tables, rho = read()
    every_year = sorted(int(y) for y in tables[config.CORRECTED_DATASET][config.YEAR_COL].unique())
    cases = {
        "corrected, all years": (config.CORRECTED_DATASET, every_year, True),
        "observed, all years": (config.OBSERVED_DATASET, every_year, False),
        "observed, 2023-2024": (config.OBSERVED_DATASET, config.CORRECTION_REFERENCE_YEARS, False),
    }

    print("1. Per edge of the four vehicle types, city: share of crashes with both hurt and the ratio of the")
    print("   dependent variance to the independent one.")
    rows = []
    for name, (dataset, years, corrected) in cases.items():
        city, _ = pooled(tables[dataset], years)
        counts = crash_counts(rho, config.CITY_LEVEL, years)
        flow = hodge.edge_flow(city, tuple(hodge.INDEX[a] for a in FOUR), C)
        for position, edge in enumerate(flow.edges):
            k = both_hurt(city, edge, counts, config.CITY_AREA_CODE, corrected)
            a, b = flow.forward[position] + C, flow.backward[position] + C
            independent = 1 / a + 1 / b
            n = flow.forward[position] + flow.backward[position] - k
            rows.append({"case": name, "pair": f"{hodge.ACTORS[edge[0]]}-{hodge.ACTORS[edge[1]]}",
                         "hurt first": int(flow.forward[position]), "hurt second": int(flow.backward[position]),
                         "both": round(k), "share both": round(k / n, 3),
                         "variance ratio": round((independent - 2 * k / (a * b)) / independent, 3)})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n2. City potential against the car, error scaled by the dispersion in brackets.")
    rows = []
    for name, (dataset, years, corrected) in cases.items():
        city, _ = pooled(tables[dataset], years)
        counts = crash_counts(rho, config.CITY_LEVEL, years)
        for layer, actors in (("four types", FOUR), ("five types", FIVE)):
            flow = hodge.edge_flow(city, tuple(hodge.INDEX[a] for a in actors), C)
            for weighting, chosen in (("independent", flow),
                                      ("dependent", dependent(flow, city, counts, config.CITY_AREA_CODE, corrected))):
                rows.append({"case": name, "layer": layer, "weights": weighting, **summary(chosen, actors)})
    print(pd.DataFrame(rows).fillna("").to_string(index=False))

    print("\n3. The heterogeneity test, vehicle layer, parties. The first and the third case are the two")
    print("   declared tests of D69.")
    rows, per_actor = [], []
    for name, (dataset, years, corrected) in cases.items():
        _, units = pooled(tables[dataset], years)
        counts = crash_counts(rho, config.UNIT_LEVEL, years)
        for layer, actors in (("four types", FOUR), ("five types", FIVE)):
            vertices = tuple(hodge.INDEX[a] for a in actors)
            flows = {unit: hodge.edge_flow(m, vertices, C) for unit, m in units.items()}
            for weighting, chosen in (("independent", flows),
                                      ("dependent", {unit: dependent(flow, units[unit], counts, unit, corrected)
                                                     for unit, flow in flows.items()})):
                test = hodge.heterogeneity_test(chosen, dataset, config.AFFECTED_PARTIES_COL,
                                                config.HODGE_HETEROGENEITY_LAYER, config.HODGE_WINDOW_REFERENCE)
                overall = test[test[config.ROAD_USER_TYPE_COL] == "ALL"].iloc[0]
                rows.append({"case": name, "layer": layer, "weights": weighting, "units": int(overall.UNITS),
                             "chi2": round(overall.STATISTIC, 1), "df": int(overall.DF),
                             "chi2/df": round(overall.STATISTIC / overall.DF, 2),
                             "p chi2": round(overall.P_VALUE_CHI2, 3), "dispersion": round(overall.DISPERSION, 2),
                             "F": round(overall.F, 2), "p F": round(overall.P_VALUE_F, 4)})
                if layer == "five types":
                    for _, row in test[test[config.ROAD_USER_TYPE_COL] != "ALL"].iterrows():
                        per_actor.append({
                            "case": name, "weights": weighting, "actor": row[config.ROAD_USER_TYPE_COL],
                            "city mean": round(row.MEAN_VS_REFERENCE, 3),
                            "sd across units": round(row.SD_ACROSS_UNITS, 3),
                            "rms error": round(row.RMS_STD_ERROR, 3), "Q/df": round(row.STATISTIC / row.DF, 2),
                            "p F": round(row.P_VALUE_F, 4)})
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n   Per actor type, five types: the unit contrasts against the car and how far they spread.")
    print(pd.DataFrame(per_actor).to_string(index=False))

    print("\n4. The delta-method variance against a simulation: three independent Poisson counts with the")
    print("   means of the city edges in 2023-2024, 200 000 draws each.")
    city, _ = pooled(tables[config.OBSERVED_DATASET], config.CORRECTION_REFERENCE_YEARS)
    counts = crash_counts(rho, config.CITY_LEVEL, config.CORRECTION_REFERENCE_YEARS)
    generator = np.random.default_rng(20261110)
    rows = []
    for edge in hodge.edge_flow(city, tuple(hodge.INDEX[a] for a in FOUR), C).edges:
        i, j = edge
        k = both_hurt(city, edge, counts, config.CITY_AREA_CODE, False)
        only_first, only_second = city[i, j] - k, city[j, i] - k
        draws = [generator.poisson(m, 200_000) for m in (only_first, only_second, k)]
        first, second = draws[0] + draws[2], draws[1] + draws[2]
        simulated = np.var(np.log(first + C) - np.log(second + C))
        a, b = city[i, j] + C, city[j, i] + C
        rows.append({"pair": f"{hodge.ACTORS[i]}-{hodge.ACTORS[j]}", "simulated": f"{simulated:.2e}",
                     "dependent formula": f"{1 / a + 1 / b - 2 * k / (a * b):.2e}",
                     "independent formula": f"{1 / a + 1 / b:.2e}"})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n5. Is what differs between units the record? Observed 2023-2024, five types, dependent weights:")
    print("   each unit's contrast against the car, and the share of the crashes of that pair with both hurt.")
    _, units = pooled(tables[config.OBSERVED_DATASET], config.CORRECTION_REFERENCE_YEARS)
    counts = crash_counts(rho, config.UNIT_LEVEL, config.CORRECTION_REFERENCE_YEARS)
    vertices = tuple(hodge.INDEX[a] for a in FIVE)
    car = hodge.INDEX[config.CAR]
    records = []
    for unit, matrix in units.items():
        result = hodge.fit(dependent(hodge.edge_flow(matrix, vertices, C), matrix, counts, unit, False))
        if result.components != 1:
            continue
        for actor in (config.BICYCLE, config.MOTORCYCLE):
            value, error = hodge.contrast(result, hodge.INDEX[actor], car)
            edge = tuple(sorted((hodge.INDEX[actor], car)))
            k, n = counts.get((unit, edge), (np.nan, np.nan))
            records.append({"unit": unit, "actor": actor, "contrast": value, "error": error,
                            "share both": k / n if n else np.nan, "crashes": n})
    frame = pd.DataFrame(records).dropna()
    for actor, group in frame.groupby("actor"):
        weights = 1 / group["error"] ** 2
        x, y = group["share both"], group["contrast"]
        mx, my = np.average(x, weights=weights), np.average(y, weights=weights)
        r = np.average((x - mx) * (y - my), weights=weights) / np.sqrt(
            np.average((x - mx) ** 2, weights=weights) * np.average((y - my) ** 2, weights=weights))
        slope = np.average((x - mx) * (y - my), weights=weights) / np.average((x - mx) ** 2, weights=weights)
        print(f"   {actor:<11} units {len(group)}, share both from {x.min():.2f} to {x.max():.2f}, "
              f"weighted correlation {r:+.2f}, slope {slope:+.2f} per unit of share")


if __name__ == "__main__":
    main()
