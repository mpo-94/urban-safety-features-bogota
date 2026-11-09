"""How far the Hodge potential follows the mass of each vehicle, read from a run of the hodge route.

    .venv/Scripts/python.exe tools/recta_de_masa.py [run]

**Read only.** It reads `analysis__hodge_potential` from one run of the `hodge` route (D69) and
writes nothing. Without an argument it takes the most recent run that exported that table.

Momentum conservation makes the change of speed of each vehicle in a two-vehicle crash inversely
proportional to its mass, so the potential of a vehicle type should fall with the logarithm of its
mass: Pi_c = beta_0 - beta_mass log mass_c + eps_c. This fits that line, on the layer without the
pedestrian, where the exposure cancels on every edge (D69, the two layers), over the four vehicle
types with a reference mass. The masses are a declared assumption and not a measurement. To see how
much the slope depends on them, the fit is repeated with 2,000 sets of masses each moved at random
by up to 30 % up or down.

The pedestrian is read apart, as an upper bound: its potential minus the car's, from the layer with
all six types, against what the vehicles' line predicts for 70 kg with the same reference.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config  # noqa: E402

# Reference masses, a declared assumption: the bicycle and the motorcycle with their rider, a light
# car and a city bus. «Other» has no defined mass and stays out of the line, though it is in the flow.
REFERENCE_MASS_KG = {"BICYCLE": 85.0, "MOTORCYCLE": 220.0, "CAR": 1300.0, "PUBLIC_TRANSPORT": 12000.0}
PEDESTRIAN_MASS_KG = 70.0
DRAWS, SPREAD, SEED = 2000, 0.30, 20261106


def mass_line(potential: dict[str, float], masses: dict[str, float]) -> tuple[float, float, float]:
    """beta_mass, beta_0 and R^2 of Pi = beta_0 - beta_mass log mass, by least squares."""
    x = np.log([masses[a] for a in masses])
    y = np.array([potential[a] for a in masses])
    design = np.column_stack([np.ones_like(x), -x])
    (intercept, slope), *_ = np.linalg.lstsq(design, y, rcond=None)
    fitted = design @ np.array([intercept, slope])
    r2 = 1 - np.sum((y - fitted) ** 2) / np.sum((y - y.mean()) ** 2)
    return float(slope), float(intercept), float(r2)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    filename = f"{config.HODGE_POTENTIAL_FILENAME}.parquet"
    run_dir = config.run_directory_holding(filename, sys.argv[1] if len(sys.argv) > 1 else None)
    table = pd.read_parquet(run_dir / config.DATA_SUBDIR / filename)
    city = table[table[config.HODGE_LEVEL_COL] == config.HODGE_CITY_ALL_YEARS]
    print(f"read from {run_dir.name}\n")

    rows = []
    for (dataset, count), group in city.groupby([config.DATASET_COL, config.HODGE_COUNT_COL]):
        layer = lambda name: group[group[config.HODGE_LAYER_COL] == name].set_index(config.ROAD_USER_TYPE_COL)  # noqa: E731
        vehicles = layer(config.HODGE_LAYER_VEHICLES)["POTENTIAL"]
        everyone = layer(config.HODGE_LAYER_ALL)["POTENTIAL_VS_REFERENCE"]
        potential = {a: float(vehicles[a]) for a in REFERENCE_MASS_KG}
        slope, intercept, r2 = mass_line(potential, REFERENCE_MASS_KG)
        rng = np.random.default_rng(SEED)
        slopes = [mass_line(potential, {a: m * rng.uniform(1 - SPREAD, 1 + SPREAD)
                                        for a, m in REFERENCE_MASS_KG.items()})[0] for _ in range(DRAWS)]
        bound = float(everyone[config.PEDESTRIAN])
        predicted = -slope * (np.log(PEDESTRIAN_MASS_KG) - np.log(REFERENCE_MASS_KG[config.CAR]))
        rows.append({"dataset": dataset, "count": count, "beta_mass": round(slope, 3), "r2": round(r2, 3),
                     "beta_mass_p05": round(float(np.percentile(slopes, 5)), 3),
                     "beta_mass_p95": round(float(np.percentile(slopes, 95)), 3),
                     "pedestrian_bound": round(bound, 3), "pedestrian_predicted": round(float(predicted), 3)})
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
