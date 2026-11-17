"""Where the 2018 prediction test fails, unit by unit, for bicycle against motorcycle.

    .venv/Scripts/python.exe tools/prueba_2018_por_unidad.py

**Read only.** The panel route fits each model on 2012 to 2017 and predicts 2018, the year the cycleway
network grew most, and reports one R-squared per pair. For bicycle against motorcycle that R-squared is
close to zero. This tool says why, from the tables the route already exported, without estimating
anything:

- how much of the squared error each unit carries;
- what happened in the unit that carries most of it;
- the R-squared without that unit;
- the ceiling the pair's count noise puts on any R-squared, from the dispersion the model estimated.

Nothing in `src/` imports it, and it writes nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import patrones_del_panel as patrones  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PANEL_RUN = "run_20261116_172543"
PAIR, PANEL, DATASET, LEVEL = "BICYCLE__MOTORCYCLE", "PRINCIPAL", "RHO_CORRECTED", "OBSERVED_TOTAL"
MODELS = ("CRE", "CRE_WITHOUT_CYCLEWAY", "REFERENCE")


def r_squared(observed: pd.Series, predicted: pd.Series) -> float:
    return 1 - ((observed - predicted) ** 2).sum() / ((observed - observed.mean()) ** 2).sum()


def main() -> int:
    data = REPO / "results" / PANEL_RUN / "data"
    p = pd.read_parquet(data / "analysis__panel_growth_predictions.parquet")
    p = p[(p.DATASET == DATASET) & (p.PANEL == PANEL) & (p.LEVEL == LEVEL) & (p.PAIR == PAIR)]
    predicted = p.pivot_table(index="AREA_CODE", columns="MODEL", values="PREDICTED")
    observed = p.drop_duplicates("AREA_CODE").set_index("AREA_CODE").OBSERVED
    alpha = p[p.MODEL == "CRE"].ALPHA.iloc[0]

    print(f"{PAIR}, panel {PANEL.lower()}, {DATASET}, 2018 predicted from 2012-2017 ({PANEL_RUN})")
    for model in MODELS:
        print(f"  R-squared, {model}: {r_squared(observed, predicted[model]):.3f}")

    squared = (observed - predicted["CRE"]) ** 2
    worst = squared.idxmax()
    print(f"\n  the unit carrying most of the squared error: {worst}, {squared[worst]:.0f} of {squared.sum():.0f} "
          f"({100 * squared[worst] / squared.sum():.0f} %); predicted {predicted.loc[worst, 'CRE']:.1f}, "
          f"reference {predicted.loc[worst, 'REFERENCE']:.1f}, observed {observed[worst]:.0f}")
    rest = observed.drop(worst)
    for model in MODELS:
        print(f"  R-squared without it, {model}: {r_squared(rest, predicted[model].drop(worst)):.3f}")

    # What count noise alone leaves unexplained: the negative binomial variance at the model's means.
    mu = predicted["CRE"]
    noise = (mu + alpha * mu ** 2).sum()
    total = ((observed - observed.mean()) ** 2).sum()
    print(f"\n  mean count {observed.mean():.1f}; expected noise {noise:.0f} of a total variation {total:.0f}: "
          f"ceiling on R-squared about {1 - noise / total:.2f}")

    matrix = patrones.table("matrix", "analysis__matrix_long__rho_corrected")
    matrix = matrix[(matrix.SCALE == "UPL") & (matrix.PARTY_TYPE == "BICYCLE") & (matrix.COUNTERPART_TYPE == "MOTORCYCLE")
                    & (matrix.AREA_CODE == worst)].groupby("YEAR").AFFECTED_PARTIES.sum()
    trips = patrones.weekday_trips()["BICYCLE"].xs(worst, level="AREA_CODE")
    layers = patrones.table("predictors", "analysis__static_predictors_long")
    cycleway = layers[(layers.PREDICTOR == "CYCLEWAY_LENGTH_DENSITY") & (layers.AREA_CODE == worst)].set_index("YEAR").VALUE
    print(f"\n  {worst} by year: affected parties, weekday bicycle trips (thousands), cycleway (km/km2), rate per thousand trips")
    for year in range(2015, 2020):
        print(f"    {year}: {matrix[year]:.0f}  {trips[year] / 1000:.1f}  {cycleway[year]:.2f}  {1000 * matrix[year] / trips[year]:.2f}")

    g = pd.read_parquet(data / "analysis__panel_growth_coefficients.parquet")
    g = g[(g.PAIR == PAIR) & (g.PANEL == PANEL) & (g.DATASET == DATASET) & (g.MODEL == "CRE")
          & (g.TERM == "CYCLEWAY_LENGTH_DENSITY") & (g.ROLE == "WITHIN")]
    print(f"\n  the within effect learned on 2012-2017: {g.COEFFICIENT.iloc[0]:+.3f} (p {g.P_VALUE.iloc[0]:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
