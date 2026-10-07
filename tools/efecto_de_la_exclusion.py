"""What removing one unit from the regressions actually changed, measured on two runs.

    .venv/Scripts/python.exe tools/efecto_de_la_exclusion.py [run_before] [run_after]

**Read only.** It compares two finished runs and writes nothing. Defaults to the run the
study reported on thirty units and the first run on twenty-nine.

`exclusion_de_una_unidad.py` is the pre-flight — what would break. This is the
post-flight: what moved. They answer different questions and run at different times.

It asks two, and they do not have the same answer:

  1. **Did the selected model change?** One cell is one dataset, offset, pair, year and
     family, and its winner is the lowest AIC among 220 or 286 candidates. Removing an
     observation from twenty-nine or thirty is a large perturbation for a search that
     fine, so this is where instability shows if there is any.

  2. **Did what the study reports change?** Not the same thing. D53 says the study reads
     how often a variable is selected **within one specification**, not which model won a
     cell. A count over 104 cells can be stable while its summands are not, and whether it
     is has to be measured rather than hoped for.

Both runs must share a candidate set, which is checked rather than assumed: comparing two
sets would attribute to the excluded unit a change that came from the candidate list.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import config  # noqa: E402

BEFORE = "run_20260928_112330"
AFTER = "run_20261002_094610"
CELL = ["DATASET", "OFFSET", "PAIR", "YEAR", "FAMILY"]


def models_of(run: str) -> tuple[pd.DataFrame, str]:
    frame = pd.read_csv(REPO / "results" / run / "data" / "analysis__regression_models.csv")
    sets = frame["CANDIDATE_SET"].unique()
    if len(sets) != 1:
        raise ValueError(f"{run} mixes candidate sets: {sets}")
    return frame, str(sets[0])


def as_set(column: pd.Series) -> pd.Series:
    """The winner's predictors as a set.

    Compared as a set and not as the stored string: the order inside `PREDICTORS` is the
    order the configuration declares, not a decision of the model, so comparing the text
    would count differences that are not there.
    """
    return column.fillna("").apply(
        lambda s: frozenset(part.strip() for part in s.split(";") if part.strip()))


def frequencies_of(run: str) -> pd.DataFrame:
    """How many times each variable enters a winner, per specification."""
    coefficients = pd.read_csv(
        REPO / "results" / run / "data" / "analysis__regression_coefficients.csv")
    coefficients = coefficients[coefficients["TERM"] != "INTERCEPT"]
    return (coefficients.groupby(["DATASET", "OFFSET", "FAMILY", "TERM"])
            .size().rename("times").reset_index())


def main() -> None:
    before_run = sys.argv[1] if len(sys.argv) > 1 else BEFORE
    after_run = sys.argv[2] if len(sys.argv) > 2 else AFTER

    before, set_before = models_of(before_run)
    after, set_after = models_of(after_run)
    if set_before != set_after:
        raise ValueError(
            f"the two runs do not share a candidate set: {set_before} against {set_after}; "
            "the comparison would attribute to the excluded unit a change that came from "
            "the candidate list")

    print(f"{before_run} ({before['N_OBSERVATIONS'].iloc[0]} units) against "
          f"{after_run} ({after['N_OBSERVATIONS'].iloc[0]} units)")
    print(f"candidate set: {set_before}\n")

    joined = before.merge(after, on=CELL, suffixes=("_before", "_after"), how="inner")
    same = as_set(joined["PREDICTORS_before"]) == as_set(joined["PREDICTORS_after"])
    print(f"1. The selected model, over {len(joined):,} cells")
    print(f"   unchanged      {int(same.sum()):6,}  ({same.mean() * 100:5.1f} %)")
    print(f"   changed        {int((~same).sum()):6,}  ({(~same).mean() * 100:5.1f} %)\n")
    print(f"   {'family':<24} {'cells':>7} {'changed':>8} {'%':>7}")
    for family in joined["FAMILY"].unique():
        block = joined[joined["FAMILY"] == family]
        moved = ~(as_set(block["PREDICTORS_before"]) == as_set(block["PREDICTORS_after"]))
        print(f"   {config.FAMILY_LABELS_ES[family][:24]:<24} {len(block):7,} "
              f"{int(moved.sum()):8,} {moved.mean() * 100:6.1f} %")

    frequency = frequencies_of(before_run).merge(
        frequencies_of(after_run), on=["DATASET", "OFFSET", "FAMILY", "TERM"],
        suffixes=("_before", "_after"), how="outer").fillna(0)

    rhos, same_first, specifications = [], 0, 0
    for _, block in frequency.groupby(["DATASET", "OFFSET", "FAMILY"]):
        if len(block) < 3:
            continue
        specifications += 1
        rhos.append(spearmanr(block["times_before"], block["times_after"]).statistic)
        same_first += int(block.nlargest(1, "times_before")["TERM"].iloc[0]
                          == block.nlargest(1, "times_after")["TERM"].iloc[0])
    rho = np.array(rhos)

    print(f"\n2. What the study reports: the order of the candidates by selection "
          f"frequency,\n   within each of the {specifications} specifications")
    print(f"   Spearman: median {np.median(rho):+.3f}, between {rho.min():+.3f} "
          f"and {rho.max():+.3f}")
    print(f"   specifications above 0.8: {int((rho > 0.8).sum())} of {specifications}")
    print(f"   same most-selected variable: {same_first} of {specifications}\n")

    totals = pd.concat(
        [frequencies_of(before_run).groupby("TERM")["times"].sum(),
         frequencies_of(after_run).groupby("TERM")["times"].sum()],
        axis=1, keys=["before", "after"]).fillna(0)
    totals["places"] = (totals["before"].rank(ascending=False)
                        - totals["after"].rank(ascending=False)).abs()
    totals = totals.sort_values("before", ascending=False)
    print(f"   {'variable':<26} {'before':>7} {'after':>7} {'places':>7} {'change':>8}")
    for term, row in totals.iterrows():
        change = (row["after"] - row["before"]) / row["before"] * 100 if row["before"] else float("nan")
        print(f"   {config.predictor_label_es(term)[:26]:<26} {int(row['before']):7,} "
              f"{int(row['after']):7,} {int(row['places']):7} {change:7.0f} %")
    print(f"\n   Spearman of the totals: "
          f"{spearmanr(totals['before'], totals['after']).statistic:+.3f}   "
          f"largest move: {int(totals['places'].max())} place(s) of {len(totals)}")


if __name__ == "__main__":
    main()
