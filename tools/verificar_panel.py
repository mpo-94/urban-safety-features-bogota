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
     horizontal as the sum painted up to the previous year, and its flow as what was painted in
     the previous year alone.
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
  7. **Significance and the rule** (amendment of 2026-11-03). The stars and the dagger recounted
     from the p-values, and the model choice recomputed from the coefficient and validation tables
     by a path of its own, against the route's rule tables.
  8. **The growth-year test** (amendment of 2026-11-04). The observed total of 2018 against the
     affected parties of the main panel's rows; the level fixed by it reproduced; the error and the
     R² recomputed from the unit predictions; the training years; Holm and the stars recounted on
     the cycleway effect learned in them.
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
    expected = raw.merge(cumulative[[config.AREA_CODE_COL, "YEAR", "CUMULATIVE", "FLOW"]],
                         on=[config.AREA_CODE_COL, "YEAR"], how="left")
    corrected = rows[rows["DATASET"] == config.CORRECTED_DATASET].drop_duplicates(["PANEL", config.AREA_CODE_COL, "YEAR"])
    checked = corrected.merge(expected, on=[config.AREA_CODE_COL, "YEAR"], suffixes=("", "_RAW"))
    worst = {
        "cycleway": float((checked[panel.CYCLEWAY] - checked["EXPECTED_CYCLEWAY"]).abs().max()),
        "vertical": float((checked[panel.VERTICAL] - checked["EXPECTED_VERTICAL"]).abs().max(skipna=True)),
        "horizontal": float((checked[panel.HORIZONTAL] - checked["CUMULATIVE"]).abs().max(skipna=True)),
        "horizontal flow": float((checked[panel.HORIZONTAL_FLOW] - checked["FLOW"]).abs().max(skipna=True)),
    }
    print(f"2. delays, over {len(checked)} panel unit-years: largest gaps " +
          ", ".join(f"{k} {v:.2e}" for k, v in worst.items()))
    if max(worst.values()) > 1e-9:
        failures.append("a delayed variable does not match the raw design")

    variables = read(run, "variables")
    print("3. variance left by unit and year effects, route against variance_shares:")
    for spec in config.PANEL_ESTIMATED_SPECS:
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

    # The levels are typed here rather than read from config, so a change there shows as a failure.
    recounted = sum((coefficients["P_VALUE"] < level).astype(int) for level in (0.10, 0.05, 0.01))
    dagger = coefficients["P_HOLM"] < 0.10
    print(f"7. stars recounted at 10, 5 and 1 %: {int((recounted != coefficients['STARS']).sum())} differ; "
          f"daggers at 10 % after Holm: {int((dagger != coefficients['HOLM_DAGGER']).sum())} differ")
    if (recounted != coefficients["STARS"]).any() or (dagger != coefficients["HOLM_DAGGER"]).any():
        failures.append("the stars or the dagger do not follow the declared levels")
    reported = [spec.key for spec in config.PANEL_SPECS]
    mine = within[within["PANEL"].isin(reported)]
    by_model = {m: mine[mine["MODEL"] == m].set_index(["PANEL", "PAIR", "TERM"]) for m in (panel.FE_NB, panel.CRE)}
    gap_se = ((by_model[panel.CRE]["COEFFICIENT"] - by_model[panel.FE_NB]["COEFFICIENT"]).abs()
              / by_model[panel.FE_NB]["SE_CLUSTERED"])
    converged = by_model[panel.CRE]["CONVERGED"] & by_model[panel.FE_NB]["CONVERGED"]
    first = bool(((gap_se < 1.0) & converged).all())
    held = validation[(validation["DATASET"] == config.CORRECTED_DATASET)
                      & (validation["LEVEL"] == panel.LEVEL_OBSERVED) & validation["PANEL"].isin(reported)]
    sums = held.pivot_table(index="PANEL", columns="MODEL", values="LOG_LIKELIHOOD", aggfunc="sum")
    not_worse = int((sums[panel.CRE] >= sums[panel.FE_NB]).sum())
    chosen = panel.CRE if first and not_worse >= 2 else panel.FE_NB
    choice = read(run, "choice").iloc[0]
    rule_within = read(run, "rule_within")
    print(f"   condition 1: {len(gap_se)} within effects, largest gap {gap_se.max():.3f} SE, holds: {first} "
          f"(route: {bool(choice['CONDITION_WITHIN'])}, {len(rule_within)} rows)")
    print(f"   condition 2: correlated not worse in {not_worse} of {len(sums)} panels "
          f"(route: {int(choice['PANELS_CRE_NOT_WORSE'])})")
    print(f"   chosen: {chosen} (route: {choice['CHOSEN_MODEL']})")
    if (chosen != choice["CHOSEN_MODEL"] or first != bool(choice["CONDITION_WITHIN"])
            or not_worse != int(choice["PANELS_CRE_NOT_WORSE"]) or len(rule_within) != len(gap_se)
            or abs(float(gap_se.max()) - float(choice["LARGEST_DIFFERENCE_IN_SE"])) > 1e-12):
        failures.append("the rule recomputed does not give the route's choice")

    # 8. The growth-year test, with the test year and the training years typed here rather than read.
    gp, gv, gc = read(run, "growth_predictions"), read(run, "growth_validation"), read(run, "growth_coefficients")
    main_rows = rows[(rows["DATASET"] == config.CORRECTED_DATASET) & (rows["PANEL"] == "PRINCIPAL")
                     & (rows["YEAR"] == 2018)]
    totals = main_rows.groupby("PAIR")["AFFECTED_PARTIES"].sum()
    gap_total = float((gv.set_index("PAIR")["OBSERVED_TOTAL"] - totals.reindex(gv["PAIR"]).to_numpy()).abs().max())
    fixed_growth = gv[gv["LEVEL"] == panel.LEVEL_OBSERVED]
    gap_level = float((fixed_growth["PREDICTED_TOTAL"] - fixed_growth["OBSERVED_TOTAL"]).abs().max())
    worst_measure = 0.0
    for (pair, model, level), block in gp.groupby(["PAIR", "MODEL", "LEVEL"]):
        o, p = block["OBSERVED"].to_numpy(), block["PREDICTED"].to_numpy()
        mine = gv[(gv["PAIR"] == pair) & (gv["MODEL"] == model) & (gv["LEVEL"] == level)].iloc[0]
        r2 = 1 - ((o - p) ** 2).sum() / ((o - o.mean()) ** 2).sum()
        worst_measure = max(worst_measure, abs(np.abs(o - p).mean() - mine["MEAN_ABSOLUTE_ERROR"]),
                            abs(r2 - mine["R2"]))
    years_ok = bool((gc["FIRST_YEAR"] == 2012).all() and (gc["LAST_YEAR"] == 2017).all()
                    and (gp["YEAR"] == 2018).all())
    worst_growth_holm = 0.0
    for _, block in gc[gc["CONVERGED"]].groupby(["MODEL", "TERM", "ROLE"]):
        again = multipletests(block["P_VALUE"], method="holm")[1]
        worst_growth_holm = max(worst_growth_holm, float(np.max(np.abs(again - block["P_HOLM"]))))
    if gc.loc[~gc["CONVERGED"], "P_HOLM"].notna().any():
        failures.append("a growth-test fit that did not converge entered Holm")
    recounted_growth = sum((gc["P_VALUE"] < level).astype(int) for level in (0.10, 0.05, 0.01))
    print(f"8. growth test: {gp['PAIR'].nunique()} pairs, models {sorted(gp['MODEL'].unique())}; "
          f"2018 totals against the panel rows, largest gap {gap_total:.2e}; level reproduced to {gap_level:.2e}; "
          f"error and R² recomputed to {worst_measure:.2e}; years 2012-2017 -> 2018: {years_ok}; "
          f"Holm to {worst_growth_holm:.2e}; stars differ in {int((recounted_growth != gc['STARS']).sum())}")
    if (gap_total > 1e-9 or gap_level > 1e-6 or worst_measure > 1e-9 or not years_ok or worst_growth_holm > 1e-12
            or (recounted_growth != gc["STARS"]).any() or gp["PAIR"].nunique() != 8):
        failures.append("the growth-year test does not reproduce")

    if failures:
        print("\nFAILED: " + "; ".join(failures))
        return 1
    print("\nall eight checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
