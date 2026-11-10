"""Does the Hodge route's method recover a published mass exponent? A check on someone else's matrix.

    .venv/Scripts/python.exe tools/hodge_evans_frick.py

**Read only.** It reads nothing from `data/` or `results/` and writes nothing: the matrix it works
on is printed in a paper, and is transcribed below.

Evans and Frick (1993, table 4, p. 222) give the driver deaths of the first vehicle in two-vehicle
crashes with the second, between nine vehicle types, in the United States from 1975 to 1989. With a
different procedure, fitting fine mass ratios, they measure that the light car's relative risk grows
as the mass ratio to the power u = 3.53 (table 1, p. 215). If the method of `src/hodge.py` measures
what D69 says it measures, the Hodge potential of the three car classes, the only ones whose mean
mass the paper publishes, has to fall on a line against log mass with a slope close to that u.

The decomposition is called from `src/hodge.py`, with the same continuity correction and weights as
the route, and is not repeated here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config, hodge  # noqa: E402

TYPES = ["moped", "motorcycle", "light car", "medium car", "heavy car", "pickup", "van",
         "medium truck", "heavy truck"]
# Rows: the vehicle whose driver died; columns: the other vehicle (Evans and Frick 1993, table 4).
TABLE_4 = np.array([
    [19, 25, 139, 202, 205, 253, 74, 39, 76],
    [9, 917, 3368, 4767, 5353, 5662, 1157, 605, 1779],
    [1, 81, 4180, 7229, 8454, 8343, 1961, 1078, 6759],
    [1, 56, 2351, 4558, 6641, 5845, 1290, 961, 6128],
    [1, 35, 1095, 2736, 4511, 3851, 823, 810, 5302],
    [1, 20, 1177, 2131, 2900, 4257, 672, 724, 5398],
    [0, 2, 210, 393, 494, 538, 127, 135, 958],
    [0, 1, 32, 52, 68, 74, 8, 86, 303],
    [0, 1, 153, 209, 245, 301, 59, 112, 1525],
], dtype=float)
# Mean masses of the three car classes, the only ones the paper publishes (p. 222), in kilograms.
CAR_MASS_KG = {2: 1014.0, 3: 1428.0, 4: 1833.0}
PUBLISHED_U = 3.53


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    # The transcription checked against two ratios the text gives in words (p. 223).
    if round(TABLE_4[1, 4] / TABLE_4[4, 1]) != 153 or round(TABLE_4[2, 8] / TABLE_4[8, 2]) != 44:
        raise SystemExit("the transcription does not give the two ratios the paper quotes")
    flow = hodge.edge_flow(TABLE_4, tuple(range(len(TYPES))), config.HODGE_CONTINUITY)
    result = hodge.fit(flow, len(TYPES))
    for name, potential in zip(TYPES, result.potential):
        print(f"   {name:<13} {potential:+.3f}")
    x = np.log([CAR_MASS_KG[i] for i in CAR_MASS_KG])
    y = np.array([result.potential[i] for i in CAR_MASS_KG])
    slope = -np.polyfit(x, y, 1)[0]
    print(f"\ngradient share {result.gradient_share:.4f} over {len(flow.edges)} edges")
    print(f"slope of the potential against log mass over the three car classes: {slope:.2f} "
          f"(the paper measures u = {PUBLISHED_U})")


if __name__ == "__main__":
    main()
