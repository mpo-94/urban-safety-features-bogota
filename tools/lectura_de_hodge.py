"""The figures the final report reads off a Hodge run: separations, the yearly series and the unit order.

    .venv/Scripts/python.exe tools/lectura_de_hodge.py [run]

**Read only.** It reads the potential and edge tables the `hodge` route exported, by default from
`run_20261110_010654`, the run of the amended D69 the report quotes, and writes nothing. It refits
nothing either: the city covariance comes from `hodge.fit` on the exported flows and weights, which
is the route's own fit on the same numbers.

It prints four things:
1. **Separations.** How far apart pedestrian, bicycle and motorcycle are on the city graph with all
   six types, each gap over its error scaled by the dispersion. A gap below two errors is an
   estimate and not a separation.
2. **The yearly series.** The bicycle against the car per year in both sets, and the smallest yearly
   gradient share, on the vehicle layer.
3. **The unit order.** How many units keep the city's full order of actor types, and how many keep
   its blocks: bicycle and motorcycle above the car, public transport and the other vehicles below.
4. **The pedestrian's death bound.** Its error scaled by the dispersion, and how many of those errors
   separate it from the mass line's prediction of `tools/recta_de_masa.py`.
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from src import config, hodge  # noqa: E402
from recta_de_masa import PEDESTRIAN_MASS_KG, REFERENCE_MASS_KG, mass_line  # noqa: E402

RUN = "run_20261110_010654"
PARTIES, COR, OBS = config.AFFECTED_PARTIES_COL, config.CORRECTED_DATASET, config.OBSERVED_DATASET
VEHICLES, ALL = config.HODGE_LAYER_VEHICLES, config.HODGE_LAYER_ALL


def city_fit(edges: pd.DataFrame, dataset: str, count: str, layer: str) -> hodge.Fit:
    e = edges[(edges[config.DATASET_COL] == dataset) & (edges[config.HODGE_COUNT_COL] == count)
              & (edges[config.HODGE_LEVEL_COL] == config.HODGE_CITY_ALL_YEARS) & (edges[config.HODGE_LAYER_COL] == layer)]
    flow = hodge.Flow(
        tuple((hodge.INDEX[a], hodge.INDEX[b]) for a, b in zip(e[config.PAIR_FIRST_COL], e[config.PAIR_SECOND_COL])),
        e.FLOW.to_numpy(float), e.WEIGHT.to_numpy(float), e.COUNT_FIRST_HURT.to_numpy(float),
        e.COUNT_SECOND_HURT.to_numpy(float))
    return hodge.fit(flow)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    run = sys.argv[1] if len(sys.argv) > 1 else RUN
    data = ROOT / "results" / run / config.DATA_SUBDIR
    potential = pd.read_parquet(data / f"{config.HODGE_POTENTIAL_FILENAME}.parquet")
    edges = pd.read_parquet(data / f"{config.HODGE_EDGES_FILENAME}.parquet")
    print(f"read from {run}\n")

    print("1. Gaps on the city graph with all six types, parties, over the error scaled by the dispersion:")
    for dataset in (COR, OBS):
        result = city_fit(edges, dataset, PARTIES, ALL)
        scale = np.sqrt(max(result.residual_sum / result.residual_df, 1.0))
        gaps = []
        for a, b in combinations((config.PEDESTRIAN, config.BICYCLE, config.MOTORCYCLE), 2):
            value, error = hodge.contrast(result, hodge.INDEX[a], hodge.INDEX[b])
            gaps.append(f"{a.lower()}-{b.lower()} {value:+.3f} = {abs(value) / (error * scale):.1f} errors")
        print(f"   {dataset}: " + "; ".join(gaps))

    print("\n2. Bicycle against the car per year, vehicle layer, parties, and the smallest yearly gradient share:")
    yearly = potential[(potential[config.HODGE_LEVEL_COL] == config.HODGE_CITY_YEAR)
                       & (potential[config.HODGE_COUNT_COL] == PARTIES) & (potential[config.HODGE_LAYER_COL] == VEHICLES)]
    for dataset in (OBS, COR):
        rows = yearly[yearly[config.DATASET_COL] == dataset]
        bicycle = rows[rows[config.ROAD_USER_TYPE_COL] == config.BICYCLE].set_index(config.YEAR_COL)["POTENTIAL_VS_REFERENCE"]
        print(f"   {dataset}: " + ", ".join(f"{int(y)} {v:.2f}" for y, v in bicycle.items()))
        print(f"   {dataset}: smallest gradient share "
              f"{100 * rows.groupby(config.YEAR_COL)['GRADIENT_SHARE'].first().min():.1f} %")

    print("\n3. Units that keep the city's order, parties:")
    for dataset in (COR, OBS):
        for layer in (VEHICLES, ALL):
            rows = potential[(potential[config.DATASET_COL] == dataset) & (potential[config.HODGE_COUNT_COL] == PARTIES)
                             & (potential[config.HODGE_LAYER_COL] == layer)]
            city = rows[rows[config.HODGE_LEVEL_COL] == config.HODGE_CITY_ALL_YEARS].set_index(
                config.ROAD_USER_TYPE_COL)["POTENTIAL"]
            order = list(city.sort_values(ascending=False).index)
            units = rows[rows[config.HODGE_LEVEL_COL] == config.HODGE_UNIT_ALL_YEARS]
            full = sum(list(g.set_index(config.ROAD_USER_TYPE_COL)["POTENTIAL"].sort_values(ascending=False).index)
                       == order for _, g in units.groupby(config.AREA_CODE_COL))
            print(f"   {dataset}, {layer}: {full} of {units[config.AREA_CODE_COL].nunique()} keep the full order")
        units = potential[(potential[config.DATASET_COL] == dataset) & (potential[config.HODGE_COUNT_COL] == PARTIES)
                          & (potential[config.HODGE_LAYER_COL] == VEHICLES)
                          & (potential[config.HODGE_LEVEL_COL] == config.HODGE_UNIT_ALL_YEARS)]
        blocks = 0
        for _, g in units.groupby(config.AREA_CODE_COL):
            u = g.set_index(config.ROAD_USER_TYPE_COL)["POTENTIAL_VS_REFERENCE"]
            blocks += bool(u[config.BICYCLE] > 0 and u[config.MOTORCYCLE] > 0
                           and u[config.PUBLIC_TRANSPORT] < 0 and u[config.OTHER] < 0)
        print(f"   {dataset}: {blocks} units keep the blocks (bicycle and motorcycle above the car, the rest below)")

    print("\n4. The pedestrian's death bound against the mass line, corrected set:")
    city = potential[(potential[config.HODGE_LEVEL_COL] == config.HODGE_CITY_ALL_YEARS)
                     & (potential[config.DATASET_COL] == COR) & (potential[config.HODGE_COUNT_COL] == config.PERSONS_KILLED_COL)]
    vehicles = city[city[config.HODGE_LAYER_COL] == VEHICLES].set_index(config.ROAD_USER_TYPE_COL)
    slope, intercept, _ = mass_line({a: float(vehicles.loc[a, "POTENTIAL"]) for a in REFERENCE_MASS_KG}, REFERENCE_MASS_KG)
    predicted = (intercept - slope * np.log(PEDESTRIAN_MASS_KG)) - (intercept - slope * np.log(REFERENCE_MASS_KG[config.CAR]))
    bound = city[(city[config.HODGE_LAYER_COL] == ALL) & (city[config.ROAD_USER_TYPE_COL] == config.PEDESTRIAN)].iloc[0]
    error = bound.STD_ERROR_VS_REFERENCE * np.sqrt(max(bound.DISPERSION, 1.0))
    print(f"   bound {bound.POTENTIAL_VS_REFERENCE:.3f}, predicted {predicted:.3f}, scaled error {error:.3f}, "
          f"distance {(bound.POTENTIAL_VS_REFERENCE - predicted) / error:.1f} errors")


if __name__ == "__main__":
    main()
