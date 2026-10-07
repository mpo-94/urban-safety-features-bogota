"""Does the AIC search select the model the fit figure then shows as the best one?

    .venv/Scripts/python.exe tools/seleccion_por_aic.py

**Read only.** It reads a finished run and refits the same candidate subsets outside the
pipeline; it writes nothing, and it imports from the pipeline only the configuration and
the fitting helpers it is checking.

The question came from the fit figures, once they started printing an AIC in both
families. Least squares reports a negative AIC, between -1,048 and -291, and a selection
driven by minimising it deserves a check rather than an assurance. Inside that worry
there are two questions with different answers:

  1. **Is the arithmetic sound?** Does minimising a negative AIC select the model that
     maximises the likelihood under the same penalty, or does the sign break the order?

  2. **Is it optimising the thing the figure draws?** Least squares admits no offset, so
     it is fitted on the rate, while the figure draws counts. The count families fit the
     count directly, so for them the two should agree. That is a claim about the data,
     not about the formula, and both families are measured here rather than assumed.

The second question is the reason this covers the negative binomial too. Taking on faith
that the count family is fine would leave the more important of the two unchecked, since
the negative binomial is the family the study reports.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import config  # noqa: E402
import regressions as R  # noqa: E402

# La corrida que se lee, sobreescribible por la linea de ordenes: las cifras de la
# declaracion de D59 se vuelven a medir cada vez que cambia lo que entra en los modelos.
RUN = sys.argv[1] if len(sys.argv) > 1 else "run_20261002_094610"
DATASET = "RHO_CORRECTED"
OFFSET = "MODE_EXPOSURE"
FAMILIES = (config.NEGATIVE_BINOMIAL_FAMILY, config.OLS_FAMILY)


def r_squared(observed: np.ndarray, predicted: np.ndarray) -> float:
    total = float(((observed - observed.mean()) ** 2).sum())
    if total <= 0:
        return float("nan")
    return 1 - float(((observed - predicted) ** 2).sum()) / total


def every_model(frame: pd.DataFrame, candidates: tuple[str, ...], family: str) -> list[dict]:
    """Every declared subset, with its AIC and its R-squared on the count scale.

    The prediction is built the way the pipeline builds the one it exports: `predict`
    and never `fittedvalues`, because the discrete negative binomial's `fittedvalues` is
    the linear predictor; and multiplied back by the exposure for least squares only,
    which is what puts both families on counts. Getting that wrong would make this check
    disagree with the figure it exists to check.

    `r2_fitted` is the R-squared on the scale each family actually minimises: the rate
    for least squares, the count for the others. It is what separates a selection that is
    doing its job from one that is not.
    """
    offset_spec = next(o for o in config.REGRESSION_OFFSETS if o.name == OFFSET)
    response = frame[R.RESPONSE_COL].to_numpy(dtype=float)
    log_offset = R._log_offset(frame, offset_spec)
    exposure = np.exp(log_offset)
    standardised, _, _ = R._standardise(R._scale_candidates(frame, candidates))
    position = {name: i for i, name in enumerate(candidates)}

    out: list[dict] = []
    for size in config.REGRESSION_SUBSET_SIZES:
        for combination in itertools.combinations(candidates, size):
            design = sm.add_constant(standardised[:, [position[n] for n in combination]])
            result = R._fit_one(family, response, design, log_offset)
            if result is None:
                continue
            described = R._describe(result, combination)
            if described is None:
                continue
            raw = np.asarray(result.predict(), dtype=float)
            if family == config.OLS_FAMILY:
                predicted_count = raw * exposure
                fitted_scale = r_squared(response / exposure, raw)
            else:
                predicted_count = raw
                fitted_scale = r_squared(response, raw)
            out.append({
                "variables": combination,
                "size": len(combination),
                "aic": described.aic,
                "r2_fitted": fitted_scale,
                "r2_count": r_squared(response, predicted_count),
            })
    return out


def percentile_of(value: float, population: list[float]) -> float:
    """Share of the population the value beats, in percent. Higher is better."""
    array = np.asarray(population, dtype=float)
    return float((array < value).mean() * 100)


def check_arithmetic(models: list[dict], family: str) -> None:
    """At a fixed number of predictors, the AIC order and the fit order must agree.

    With the count of predictors held constant the penalty is a constant too, so
    minimising the AIC is maximising the likelihood. If the sign of the AIC broke
    anything it would break here, and it would break in every cell rather than in some.
    """
    print(f"   {config.FAMILY_LABELS_ES[family]}")
    for size in sorted({m["size"] for m in models}):
        same = [m for m in models if m["size"] == size]
        by_aic = min(same, key=lambda m: m["aic"])
        by_fit = max(same, key=lambda m: m["r2_fitted"])
        agree = by_aic["variables"] == by_fit["variables"]
        print(f"      {size} predictors, {len(same):3d} models: lowest AIC "
              f"{by_aic['aic']:9.1f}   best fit on its own scale {by_fit['aic']:9.1f}   "
              f"same model: {'yes' if agree else 'NO'}")
    best, worst = min(models, key=lambda m: m["aic"]), max(models, key=lambda m: m["aic"])
    print(f"      AIC runs {best['aic']:.1f} to {worst['aic']:.1f}; the lowest fits its "
          f"own scale at R2 {best['r2_fitted']:.4f} against {worst['r2_fitted']:.4f} "
          f"for the highest")


def survey(data: pd.DataFrame, family: str) -> pd.DataFrame:
    rows = []
    for pair in config.REGRESSION_PAIRS:
        for year in config.REGRESSION_YEARS:
            frame = data[(data.PAIR == pair.name) & (data.YEAR == year)]
            if frame.empty:
                continue
            models = every_model(frame, config.regression_candidates_in(year), family)
            if len(models) < 10:
                continue
            winner = min(models, key=lambda m: m["aic"])
            rows.append({
                "pair": pair.label_es,
                "year": year,
                "models": len(models),
                "fitted_pct": percentile_of(winner["r2_fitted"],
                                            [m["r2_fitted"] for m in models]),
                "count_pct": percentile_of(winner["r2_count"],
                                           [m["r2_count"] for m in models]),
                "count_best": max(m["r2_count"] for m in models),
                "count_won": winner["r2_count"],
            })
    return pd.DataFrame(rows)


def main() -> None:
    path = REPO / "results" / RUN / "data" / f"analysis__regression_data__{DATASET}.csv"
    data = pd.read_csv(path)

    print(f"run {RUN} | {config.DATASET_LABELS_ES[DATASET]} | "
          f"offset {config.OFFSET_LABELS_ES[OFFSET]}\n")

    print("1. The arithmetic, at a fixed number of predictors")
    first = data[(data.PAIR == config.REGRESSION_PAIRS[0].name) & (data.YEAR == 2024)]
    for family in FAMILIES:
        check_arithmetic(every_model(first, config.regression_candidates_in(2024), family),
                         family)
    print()

    print("2. Where the AIC winner lands among all the models of its own cell")
    print("   percentile, 100 = best. Two scales: the one the family minimises, and the")
    print("   count scale the fit figure draws.\n")
    for family in FAMILIES:
        table = survey(data, family)
        gap = table["count_best"] - table["count_won"]
        print(f"   {config.FAMILY_LABELS_ES[family]}  "
              f"({len(table)} cells, {int(table['models'].sum()):,} models refitted)")
        for column, label in (("fitted_pct", "on the scale it minimises"),
                              ("count_pct", "on the count scale, which the figure draws")):
            series = table[column]
            print(f"      {label:42s} median {series.median():6.1f}   "
                  f"worst {series.min():6.1f}   below its own median: "
                  f"{int((series < 50).sum()):3d} of {len(series)}")
        print(f"      count R2 given up by following the AIC: median {gap.median():.3f}, "
              f"worst {gap.max():.3f}")
        print(f"      cells where the AIC winner also maximises the count R2: "
              f"{int((gap < 1e-9).sum())} of {len(table)}")

        worst = table.nsmallest(3, "count_pct")
        for _, row in worst.iterrows():
            print(f"         worst cell: {row['pair'][:24]:24s} {int(row['year'])}   "
                  f"count percentile {row['count_pct']:5.1f}   "
                  f"R2 won {row['count_won']:7.3f}   best available {row['count_best']:6.3f}")
        print()


if __name__ == "__main__":
    main()
