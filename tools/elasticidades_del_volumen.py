"""How casualties grow with travel, read from the run where the offset leftovers compete.

    .venv/Scripts/python.exe tools/elasticidades_del_volumen.py [run]

**Read only.** It reads one regression run with the candidate set `with-leftovers` and writes
nothing. Without an argument it takes the most recent run that declares that set.

The reported run (`urban-only`, D52) lets no exposure compete, so it holds no elasticity. The
robustness run lets the quantities the offset did not use compete in logarithm (D52,
`config.LOG_SCALED_CANDIDATES`), and its coefficient on one of them is then an elasticity: the
percentage change in the expected count per one per cent change in that quantity. That is the
number the safety-in-numbers literature reports, an exponent close to 0.4.

Two readings come out of it, and they are different quantities, which is why they are kept apart:

1. **Under the affected mode's exposure as offset, in a pair whose two sides are different
   modes**, the counterpart's exposure is a second quantity, and its coefficient says how the
   count grows with the traffic of the other mode at a fixed exposure of one's own.
2. **In a pair whose two sides are the same mode** (car against car, motorcycle against
   motorcycle), the counterpart's exposure *is* the affected mode's exposure. The offset already
   holds it with its coefficient fixed at one, so the competing coefficient frees that
   restriction, and the exponent the data support is one plus it. This is checked by arithmetic
   on the data table before it is read, and not taken from the column names.

A third reading is the plainest comparison with the literature: under the **population** offset
the affected mode's exposure competes, and its coefficient is the exponent of casualties per
resident on travel.

**Every count is made inside one specification**, one dataset, one offset and one family (D53),
and separately for the two selection procedures, which are reported with the same weight. A
coefficient exists only where the procedure selected the quantity, so every summary says how many
of the cell's years it comes from; a median over the years where the variable entered is the
median of a selected sample and reads as such.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from src import config  # noqa: E402

MODELS = f"{config.ANALYSIS_PREFIX}__regression_models.parquet"
COEFFICIENTS = f"{config.ANALYSIS_PREFIX}__regression_coefficients.parquet"
DATA_CORRECTED = f"{config.ANALYSIS_PREFIX}__regression_data__RHO_CORRECTED.parquet"

# The specification the panel inherits (D67): negative binomial on the corrected set.
FAMILY = config.NEGATIVE_BINOMIAL_FAMILY
DATASET = "RHO_CORRECTED"
SAME_MODE_PAIRS = ("CAR__CAR", "MOTORCYCLE__MOTORCYCLE")


def latest_with_leftovers() -> Path:
    """The most recent run whose tables declare the with-leftovers set, found by the column."""
    for directory in sorted(config.RESULTS_DIR.glob("run_*"), reverse=True):
        table = directory / config.DATA_SUBDIR / MODELS
        if not table.exists() or config.CANDIDATE_SET_COL not in pq.read_schema(table).names:
            continue
        declared = pd.read_parquet(table, columns=[config.CANDIDATE_SET_COL])
        if set(declared[config.CANDIDATE_SET_COL].unique()) == {config.WITH_OFFSET_LEFTOVERS}:
            return directory
    raise SystemExit("no run declares with-leftovers; run the regressions route with "
                     "--candidates with-leftovers")


def check_same_mode_columns(data: pd.DataFrame) -> None:
    """In a same-mode pair the two exposure columns must be the same numbers, or reading 2 is wrong."""
    for pair in SAME_MODE_PAIRS:
        rows = data[data["PAIR"] == pair]
        if rows.empty:
            raise SystemExit(f"{pair} is not in the data table")
        gap = np.abs(rows["EXPOSURE_COUNTERPART"] - rows["EXPOSURE_AFFECTED"]).max()
        if gap > 1e-9 * rows["EXPOSURE_AFFECTED"].abs().max():
            raise SystemExit(f"{pair}: the counterpart exposure differs from the affected one by "
                             f"{gap}; the same-mode reading does not hold")
    print("same-mode pairs: the counterpart exposure equals the affected exposure in every row "
          f"of {', '.join(SAME_MODE_PAIRS)}\n")


def summary(coefficients: pd.DataFrame, models: pd.DataFrame, offset: str, term: str,
            shift: float = 0.0) -> pd.DataFrame:
    """One row per pair and procedure: years modelled, years selected, median and range.

    `shift` is added to every coefficient, which is how the same-mode exponent 1 + beta is shown.
    """
    cell = (models["DATASET"] == DATASET) & (models[config.OFFSET_COL] == offset) \
        & (models[config.FAMILY_COL] == FAMILY)
    modelled = models[cell].groupby(["SELECTION_METHOD", "PAIR"]).size().rename("years_modelled")
    picked = coefficients[(coefficients["DATASET"] == DATASET)
                          & (coefficients[config.OFFSET_COL] == offset)
                          & (coefficients[config.FAMILY_COL] == FAMILY)
                          & (coefficients["TERM"] == term)].copy()
    if not picked["COEFFICIENT_IS_ELASTICITY"].all():
        raise SystemExit(f"{term} under {offset} is not flagged as an elasticity in every row")
    picked["value"] = picked["COEFFICIENT"] + shift
    stats = picked.groupby(["SELECTION_METHOD", "PAIR"]).agg(
        years_selected=("value", "size"),
        median=("value", "median"),
        low=("value", "min"),
        high=("value", "max"),
        significant=("SIGNIFICANT", "sum"),
    )
    return modelled.to_frame().join(stats, how="left").fillna({"years_selected": 0}).round(3)


def main() -> int:
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_with_leftovers()
    if not run.is_absolute():
        run = config.RESULTS_DIR / run.name
    data_dir = run / config.DATA_SUBDIR
    models = pd.read_parquet(data_dir / MODELS)
    coefficients = pd.read_parquet(data_dir / COEFFICIENTS)
    print(f"run: {run.name}   specification: {DATASET}, {FAMILY}\n")

    check_same_mode_columns(pd.read_parquet(data_dir / DATA_CORRECTED))

    pd.set_option("display.width", 160)
    # The affected mode's exposure is the primary offset, the anteproyecto's and the panel's.
    mode = config.PRIMARY_OFFSET

    print("1. Counterpart exposure under the affected mode's exposure, pairs of two different modes")
    table = summary(coefficients, models, mode, "EXPOSURE_COUNTERPART")
    print(table[~table.index.get_level_values("PAIR").isin(SAME_MODE_PAIRS)].to_string(), "\n")

    print("2. Same-mode pairs: the exponent the data support on the own exposure, 1 + beta")
    print(table[table.index.get_level_values("PAIR").isin(SAME_MODE_PAIRS)].to_string(), "\n")
    print(summary(coefficients, models, mode, "EXPOSURE_COUNTERPART", shift=1.0)
          .loc[lambda t: t.index.get_level_values("PAIR").isin(SAME_MODE_PAIRS)].to_string(), "\n")

    print("3. Affected mode's exposure under the population offset")
    print(summary(coefficients, models, "POPULATION", "EXPOSURE_AFFECTED").to_string(), "\n")

    # How much of what the search selected went to the leftovers, inside this specification.
    for offset in (mode, "POPULATION"):
        spec = coefficients[(coefficients["DATASET"] == DATASET)
                            & (coefficients[config.OFFSET_COL] == offset)
                            & (coefficients[config.FAMILY_COL] == FAMILY)
                            & (coefficients["TERM"] != "INTERCEPT")]
        for method, rows in spec.groupby("SELECTION_METHOD"):
            share = rows["COEFFICIENT_IS_ELASTICITY"].mean()
            print(f"{offset:15s} {method:22s} selected terms {len(rows):5d}, "
                  f"of which leftovers {rows['COEFFICIENT_IS_ELASTICITY'].sum():4d} ({share:.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
