"""Does the panel route's run agree with the measurements that already existed?

    .venv/Scripts/python.exe tools/verificar_panel.py [run]

**Read only.** It reads a finished `panel` run and the regression design it was built from, and calls
the measurements `tools/` already had, so that each check sets the pipeline against something it did
not compute itself. Defaults to the most recent panel run. It fails loudly rather than printing
numbers to be judged.

  1. **The horizontal marking.** The kilometres the route measured per unit and year against
     `demarcacion_por_unidad.measure`, which measures the same layer independently.
  2. **The delays.** Every unit-year of the panel against the raw design: the cycleway as the
     mean of the year and the previous one, the vertical signage as the previous year's value, the
     horizontal as the sum painted up to the previous year.
  3. **What is left to each variable.** The route's share of variance left by unit and year
     effects against `variacion_para_el_panel.variance_shares` on the same rows.
  4. **Holm.** Recomputed per variable over the eight pairs with statsmodels.
  5. **The level of the held-out year.** With it fixed by the observed total, every model's
     predicted total equals the observed one.
  6. **The two models agree where they should.** The within effects of fixed effects, of the
     correlated model, of Poisson with fixed effects and of the pooled Mundlak version, compared
     pair by pair. Not required to be equal with a log link (D67); reported, and failed only if a
     sign flips between fixed effects and the correlated model on an effect that either declares
     significant.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

from src import config, panel
from src.provenance import RunLog
import demarcacion_por_unidad as demarcacion  # noqa: E402
import variacion_para_el_panel as variacion  # noqa: E402


def latest_panel_run() -> str:
    return config.run_directory_holding(f"{config.ANALYSIS_PREFIX}__panel_models.parquet").name


def read(run: str, name: str) -> pd.DataFrame:
    return pd.read_parquet(ROOT / "results" / run / "data" / f"{config.ANALYSIS_PREFIX}__panel_{name}.parquet")


def main() -> int:
    run = sys.argv[1] if len(sys.argv) > 1 else latest_panel_run()
    print(f"panel run: {run}\n")
    failures = []

    marking = read(run, "marking")
    scratch = ROOT / "results" / "_tools_verificar_panel"
    scratch.mkdir(parents=True, exist_ok=True)
    log = RunLog(run_dir=scratch)
    log.logger.setLevel(logging.ERROR)
    independent = demarcacion.measure(log)
    independent = independent[independent["LAYER"] == "HORIZONTAL_MARKING_PAINTED"]
    joined = marking.merge(independent[[config.AREA_CODE_COL, "YEAR", config.PREDICTOR_MEASURE_COL]],
                           on=[config.AREA_CODE_COL, "YEAR"], how="left")
    gap = float((joined["KM_PAINTED"] - joined[config.PREDICTOR_MEASURE_COL]).abs().max())
    print(f"1. horizontal marking: {len(joined)} unit-years, largest gap against "
          f"demarcacion_por_unidad {gap:.2e} km")
    if gap > 1e-6 or joined[config.PREDICTOR_MEASURE_COL].isna().any():
        failures.append("the route's marking does not match demarcacion_por_unidad")

    rows = read(run, "panel_rows")
    design, _ = panel.read_design(log)
    raw = design[config.CORRECTED_DATASET][[config.AREA_CODE_COL, "YEAR", panel.CYCLEWAY, panel.VERTICAL]] \
        .drop_duplicates().sort_values([config.AREA_CODE_COL, "YEAR"])
    raw["PREV_CYCLEWAY"] = raw.groupby(config.AREA_CODE_COL)[panel.CYCLEWAY].shift(1)
    raw["EXPECTED_CYCLEWAY"] = np.where(raw["PREV_CYCLEWAY"].notna(),
                                        (raw[panel.CYCLEWAY] + raw["PREV_CYCLEWAY"]) / 2, raw[panel.CYCLEWAY])
    raw["EXPECTED_VERTICAL"] = raw.groupby(config.AREA_CODE_COL)[panel.VERTICAL].shift(1)
    cumulative = marking.sort_values([config.AREA_CODE_COL, "YEAR"]).assign(YEAR=lambda t: t["YEAR"] + 1)
    expected = raw.merge(cumulative[[config.AREA_CODE_COL, "YEAR", "CUMULATIVE"]],
                         on=[config.AREA_CODE_COL, "YEAR"], how="left")
    corrected = rows[rows["DATASET"] == config.CORRECTED_DATASET].drop_duplicates(["PANEL", config.AREA_CODE_COL, "YEAR"])
    checked = corrected.merge(expected, on=[config.AREA_CODE_COL, "YEAR"], suffixes=("", "_RAW"))
    worst = {
        "cycleway": float((checked[panel.CYCLEWAY] - checked["EXPECTED_CYCLEWAY"]).abs().max()),
        "vertical": float((checked[panel.VERTICAL] - checked["EXPECTED_VERTICAL"]).abs().max(skipna=True)),
        "horizontal": float((checked[panel.HORIZONTAL] - checked["CUMULATIVE"]).abs().max(skipna=True)),
    }
    print(f"2. delays, over {len(checked)} panel unit-years: largest gaps " +
          ", ".join(f"{k} {v:.2e}" for k, v in worst.items()))
    if max(worst.values()) > 1e-9:
        failures.append("a delayed variable does not match the raw design")

    variables = read(run, "variables")
    print("3. variance left by unit and year effects, route against variance_shares:")
    for spec in config.PANEL_SPECS:
        unit_years = corrected[corrected["PANEL"] == spec.key]
        shares = variacion.variance_shares(unit_years, spec.varying).set_index("variable")["two_way_share"]
        ours = variables[(variables["PANEL"] == spec.key) & (variables["DATASET"] == config.CORRECTED_DATASET)] \
            .set_index("TERM")["REMAINING_SHARE"]
        for v in spec.varying:
            print(f"   {spec.key:9s} {v:32s} route {100 * ours[v]:6.2f} %   tool {100 * shares[v]:6.2f} %")
            if abs(ours[v] - shares[v]) > 1e-6:
                failures.append(f"the remaining share of {v} in {spec.key} differs from variance_shares")

    coefficients = read(run, "coefficients")
    worst_holm = 0.0
    for _, block in coefficients.groupby(["DATASET", "PANEL", "MODEL", "TERM", "ROLE"]):
        valid = block["P_VALUE"].notna()
        if valid.sum():
            again = multipletests(block.loc[valid, "P_VALUE"], method="holm")[1]
            worst_holm = max(worst_holm, float(np.max(np.abs(again - block.loc[valid, "P_HOLM"]))))
    print(f"4. Holm recomputed with statsmodels: largest gap {worst_holm:.2e}")
    if worst_holm > 1e-12:
        failures.append("Holm does not reproduce")

    validation = read(run, "validation")
    fixed = validation[validation["LEVEL"] == panel.LEVEL_OBSERVED]
    gap = float((fixed["PREDICTED_TOTAL"] - fixed["OBSERVED_TOTAL"]).abs().max())
    print(f"5. held-out year with the observed total: largest gap between predicted and observed totals {gap:.2e}")
    if gap > 1e-6:
        failures.append("the level of the held-out year does not reproduce the observed total")

    within = coefficients[(coefficients["ROLE"] == panel.WITHIN) & (coefficients["DATASET"] == config.CORRECTED_DATASET)]
    wide = within.pivot_table(index=["PANEL", "PAIR", "TERM"], columns="MODEL", values="COEFFICIENT")
    significant = within.pivot_table(index=["PANEL", "PAIR", "TERM"], columns="MODEL", values="P_VALUE") < 0.05
    print("6. within effects, largest absolute gap against fixed effects (NB), per model:")
    for model in (panel.CRE, panel.FE_POISSON, panel.MUNDLAK):
        print(f"   {model:10s} {float((wide[model] - wide[panel.FE_NB]).abs().max()):.4f}   "
              f"same sign in {int((np.sign(wide[model]) == np.sign(wide[panel.FE_NB])).sum())} of {len(wide)}")
    flips = wide[(np.sign(wide[panel.CRE]) != np.sign(wide[panel.FE_NB]))
                 & (significant[panel.CRE] | significant[panel.FE_NB])]
    if len(flips):
        print(flips.to_string())
        failures.append("fixed effects and the correlated model disagree in sign on a significant within effect")

    if failures:
        print("\nFAILED: " + "; ".join(failures))
        return 1
    print("\nall six checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
