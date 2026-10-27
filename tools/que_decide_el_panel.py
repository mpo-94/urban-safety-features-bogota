"""What the cross-sections can settle about the panel's specification, and what they cannot.

    .venv/Scripts/python.exe tools/que_decide_el_panel.py [run]

**Read only.** It reads a finished regression run and prints what each choice of the panel's
form — family, offset, dataset, selection method — can be decided on, with the figure that
decides it. Nothing in `src/` imports it.

**Not every AIC comparison is legitimate, and that is the first thing this measures around.**
Inside one count family the offset is a term and the response does not change, so comparing
offsets by AIC is sound. Between least squares and the GLMs it is not, because one fits the
rate and the others the count. Between the observed and the rho-corrected datasets it is not
either, because those are different values of the response. The dataset therefore cannot be
chosen on fit, and saying so is part of the answer rather than a gap in it.

**The family is settled by the data.** The dispersion statistic has a median of 3.94 and
exceeds the declared threshold in 97.4 % of the models that report one; the negative binomial
beats Poisson on AIC in 90.9 % of the cells where both fit, by a median of 23 points. Least
squares is out on a different ground: it fits the rate, so its R-squared on counts is negative
in a fifth of its cells even under its best offset.

**The offset is settled too, and it agrees with the anteproyecto.** The exposure of the
affected mode has the lowest AIC in 67.6 % of the negative binomial cells against 30.4 % for
resident population and 2.0 % for both exposures.

**And the denominator turns out to matter more than any predictor**, which is a result worth
reporting on its own: within the negative binomial the median R-squared on counts goes from
0.70 under the mode exposure to −0.62 under both exposures. No urban variable in this study
moves the fit by anything like that.

Two things the cross-sections hand the panel rather than settle. **Residual spatial structure
is real**: Moran's I on the residuals exceeds 0.1 in 41.2 % of the models and 0.2 in 22.1 %,
so the panel has to carry a spatial term or justify leaving it out. And **27.2 % of the models
come out flagged for collinearity**, which thirteen years of the same thirty units will not
dissolve.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config  # noqa: E402

DEFAULT_RUN = "run_20261009_084114"

# Lo que identifica una celda cuando se comparan familias entre sí: todo menos la familia.
CELL_WITHOUT_FAMILY = ["DATASET", "OFFSET", "PAIR", "YEAR", "SELECTION_METHOD"]
# Y lo mismo cuando se comparan offsets: todo menos el offset.
CELL_WITHOUT_OFFSET = ["DATASET", "PAIR", "YEAR", "SELECTION_METHOD"]


def count_r_squared(group: pd.DataFrame) -> float:
    """R-squared on counts, the same definition the figures use."""
    observed = group["OBSERVED"].to_numpy(dtype=float)
    predicted = group["PREDICTED"].to_numpy(dtype=float)
    total = float(((observed - observed.mean()) ** 2).sum())
    return float("nan") if total <= 0 else 1.0 - float(((observed - predicted) ** 2).sum()) / total


def family_evidence(models: pd.DataFrame) -> dict:
    """Dispersion, and the negative binomial against Poisson cell by cell."""
    with_dispersion = models[models["DISPERSION"].notna()]
    wide = models.pivot_table(
        index=CELL_WITHOUT_FAMILY, columns="FAMILY", values="AIC")
    both = wide.dropna(subset=[config.POISSON_FAMILY, config.NEGATIVE_BINOMIAL_FAMILY])
    advantage = both[config.POISSON_FAMILY] - both[config.NEGATIVE_BINOMIAL_FAMILY]
    return {
        "dispersion_median": with_dispersion["DISPERSION"].median(),
        "over_threshold": (with_dispersion["DISPERSION"] > config.OVERDISPERSION_THRESHOLD).mean(),
        "threshold": config.OVERDISPERSION_THRESHOLD,
        "cells_both": len(both),
        "negative_binomial_wins": (advantage > 0).mean(),
        "advantage_median": advantage.median(),
    }


def offset_evidence(models: pd.DataFrame, family: str) -> pd.Series:
    """Share of cells where each offset has the lowest AIC, inside one count family."""
    its = models[models["FAMILY"] == family]
    wide = its.pivot_table(index=CELL_WITHOUT_OFFSET, columns="OFFSET", values="AIC").dropna()
    return wide.idxmin(axis=1).value_counts(normalize=True)


def fit_by_offset(models: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    """Median R-squared on counts and share negative, by family and offset."""
    per_model = predictions.groupby("MODEL_ID").apply(count_r_squared, include_groups=False)
    joined = models.merge(per_model.rename("R2"), left_on="MODEL_ID", right_index=True)
    return joined.groupby(["FAMILY", "OFFSET"])["R2"].agg(
        models="size", median="median", share_negative=lambda column: (column < 0).mean())


def fit_by_pair(models: pd.DataFrame, predictions: pd.DataFrame,
                dataset: str, offset: str, family: str) -> pd.DataFrame:
    """Median R-squared on counts by pair and selection method, inside one specification.

    The medians by family and offset hide which pairs the model reaches and which it does not,
    and that is a property of the pair rather than of the specification, so it is read inside
    the one the panel inherits.
    """
    inside = models[(models["DATASET"] == dataset) & (models["OFFSET"] == offset)
                    & (models["FAMILY"] == family)]
    per_model = predictions[predictions["MODEL_ID"].isin(inside["MODEL_ID"])].groupby(
        "MODEL_ID").apply(count_r_squared, include_groups=False)
    joined = inside.merge(per_model.rename("R2"), left_on="MODEL_ID", right_index=True)
    return joined.groupby(["PAIR", "SELECTION_METHOD"])["R2"].median().unstack()


def what_the_panel_inherits(models: pd.DataFrame) -> dict:
    """The two things the cross-sections hand over instead of settling."""
    moran = models[models["MORANS_I"].notna()]
    return {
        "moran_median": moran["MORANS_I"].median(),
        "moran_over_01": (moran["MORANS_I"] > 0.1).mean(),
        "moran_over_02": (moran["MORANS_I"] > 0.2).mean(),
        "collinear": models["COLLINEAR"].mean(),
    }


def main() -> int:
    run = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RUN
    data = REPO / "results" / run / "data"
    if not data.is_dir():
        print(f"no such run: {data}")
        return 1
    models = pd.read_parquet(data / "analysis__regression_models.parquet")
    predictions = pd.read_parquet(data / "analysis__regression_predictions.parquet")
    print(f"run: {run}   {len(models)} models, {models['CONVERGED'].sum()} converged\n")

    family = family_evidence(models)
    print("=" * 86)
    print("FAMILY — settled by the data")
    print("=" * 86)
    print(f"  dispersion median {family['dispersion_median']:.2f};"
          f" above the declared threshold of {family['threshold']}"
          f" in {family['over_threshold']:.1%} of the models that report one")
    print(f"  negative binomial beats Poisson in {family['negative_binomial_wins']:.1%}"
          f" of the {family['cells_both']} cells where both fit,"
          f" by a median of {family['advantage_median']:.1f} AIC points")

    print("\n" + "=" * 86)
    print("OFFSET — settled inside each count family, which is the only legitimate comparison")
    print("=" * 86)
    for name in (config.NEGATIVE_BINOMIAL_FAMILY, config.POISSON_FAMILY):
        shares = offset_evidence(models, name)
        print(f"\n  {name}")
        for offset, share in shares.items():
            print(f"     lowest AIC with {offset:<16} {share:.1%}")

    print("\n" + "=" * 86)
    print("AND THE DENOMINATOR MOVES THE FIT MORE THAN ANY PREDICTOR")
    print("=" * 86)
    print(fit_by_offset(models, predictions).to_string(
        float_format=lambda value: f"{value:.3f}"))

    inherited = what_the_panel_inherits(models)
    print("\n" + "=" * 86)
    print("WHAT THE CROSS-SECTIONS HAND OVER RATHER THAN SETTLE")
    print("=" * 86)
    print(f"  Moran's I on the residuals: median {inherited['moran_median']:.3f},"
          f" above 0.1 in {inherited['moran_over_01']:.1%},"
          f" above 0.2 in {inherited['moran_over_02']:.1%}")
    print(f"  models flagged collinear: {inherited['collinear']:.1%}")
    print("\n  Neither is decided here. The first says the panel needs a spatial term or an"
          "\n  argument for leaving it out; the second will not dissolve by adding years to"
          "\n  the same thirty units.")

    print("\n" + "=" * 86)
    print("AND ONE CHOICE THE CROSS-SECTIONS CANNOT MAKE")
    print("=" * 86)
    print("  The dataset. Observed and rho-corrected are different values of the response, so"
          "\n  their AIC are not comparable. That choice rests on the argument in the panel"
          "\n  proposal, not on fit, and the proposal is better for saying so.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
