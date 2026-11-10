"""The Hodge potential of the 24 European cities, set beside Bogota's (D70.8).

    .venv/Scripts/python.exe tools/hodge_klanjcic.py [hodge_run]

**Read only.** It reads `tools/klanjcic_2018_figura_s1.txt`, the transcription of the European
study's casualty matrices, and `analysis__hodge_potential` from one run of the hodge route (the most
recent without an argument), and writes nothing.

The European matrices count persons killed or seriously injured in 2018 and have no pedestrian
column, so the decomposition is made on the vehicles: bicycle, motorcycle, car, bus, truck and
other. It is the route's own decomposition, called from `src/hodge.py`, on the sum of the 24 cities.
The potential is read against the car, as in Bogota, and the mass line uses the reference masses of
`tools/recta_de_masa.py`, with the bus as Bogota's public transport and a heavy truck at 15,000 kg,
an added assumption.

Bogota's side is the corrected set, without the pedestrian, in deaths and in affected parties.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config, hodge  # noqa: E402
from tools.recta_de_masa import DRAWS, REFERENCE_MASS_KG, SEED, SPREAD, mass_line  # noqa: E402

TRANSCRIPTION = Path(__file__).resolve().parent / "klanjcic_2018_figura_s1.txt"
ROWS = ["PEDESTRIAN", "BICYCLE", "MOTORCYCLE", "CAR", "BUS", "TRUCK", "OTHER"]
COLUMNS = ["NONE", "BICYCLE", "MOTORCYCLE", "CAR", "BUS", "TRUCK", "OTHER"]
VEHICLES = ["BICYCLE", "MOTORCYCLE", "CAR", "BUS", "TRUCK", "OTHER"]
MASS_KG = {"BICYCLE": REFERENCE_MASS_KG["BICYCLE"], "MOTORCYCLE": REFERENCE_MASS_KG["MOTORCYCLE"],
           "CAR": REFERENCE_MASS_KG["CAR"], "BUS": REFERENCE_MASS_KG["PUBLIC_TRANSPORT"], "TRUCK": 15000.0}


def read_cities() -> dict[str, np.ndarray]:
    cities: dict[str, list[list[int]]] = {}
    current = None
    for line in TRANSCRIPTION.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line[0].isalpha():
            current = line
            cities[current] = []
        else:
            cities[current].append([int(x) for x in line.split()])
    if len(cities) != 24 or any(len(m) != 7 or any(len(r) != 7 for r in m) for m in cities.values()):
        raise SystemExit("the transcription does not hold 24 matrices of 7 x 7")
    return {name: np.array(rows) for name, rows in cities.items()}


def vehicle_matrix(full: np.ndarray) -> np.ndarray:
    """Rows and columns of the vehicles only, in the order of VEHICLES."""
    rows = [ROWS.index(v) for v in VEHICLES]
    cols = [COLUMNS.index(v) for v in VEHICLES]
    return full[np.ix_(rows, cols)].astype(float)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    cities = read_cities()
    europe = vehicle_matrix(sum(cities.values()))
    flow = hodge.edge_flow(europe, tuple(range(len(VEHICLES))), config.HODGE_CONTINUITY)
    result = hodge.fit(flow, len(VEHICLES))
    car = VEHICLES.index("CAR")
    print(f"Europe, 24 cities, KSI 2018: {int(sum(m.sum() for m in cities.values()))} persons, "
          f"{len(flow.edges)} edges, gradient share {result.gradient_share:.4f}")
    for index, name in enumerate(VEHICLES):
        value, error = hodge.contrast(result, index, car)
        print(f"   {name.lower():<11} {value:+.3f} ({error:.3f})")
    potential = {v: float(result.potential[VEHICLES.index(v)]) for v in MASS_KG}
    slope, _, r2 = mass_line(potential, MASS_KG)
    rng = np.random.default_rng(SEED)
    slopes = [mass_line(potential, {v: m * rng.uniform(1 - SPREAD, 1 + SPREAD) for v, m in MASS_KG.items()})[0]
              for _ in range(DRAWS)]
    print(f"   mass line: slope {slope:.2f} ({np.percentile(slopes, 5):.2f} to {np.percentile(slopes, 95):.2f} "
          f"with the masses moved), R2 {r2:.2f}")

    filename = f"{config.HODGE_POTENTIAL_FILENAME}.parquet"
    run_dir = config.run_directory_holding(filename, sys.argv[1] if len(sys.argv) > 1 else None)
    table = pd.read_parquet(run_dir / config.DATA_SUBDIR / filename)
    city = table[(table[config.HODGE_LEVEL_COL] == config.HODGE_CITY_ALL_YEARS)
                 & (table[config.DATASET_COL] == config.CORRECTED_DATASET)
                 & (table[config.HODGE_LAYER_COL] == config.HODGE_LAYER_VEHICLES)]
    print(f"\nBogota, corrected set without the pedestrian ({run_dir.name}), against the car:")
    for count in (config.PERSONS_KILLED_COL, config.AFFECTED_PARTIES_COL):
        rows = city[city[config.HODGE_COUNT_COL] == count].set_index(config.ROAD_USER_TYPE_COL)
        values = ", ".join(f"{a.lower()} {rows.loc[a, 'POTENTIAL_VS_REFERENCE']:+.3f}"
                           for a in ("BICYCLE", "MOTORCYCLE", "PUBLIC_TRANSPORT", "OTHER"))
        vehicles = rows["POTENTIAL"]
        slope_b = mass_line({a: float(vehicles[a]) for a in REFERENCE_MASS_KG}, REFERENCE_MASS_KG)[0]
        print(f"   {count:<17} {values}; mass slope {slope_b:.2f}")


if __name__ == "__main__":
    main()
