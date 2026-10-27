"""How stable is what each selection method chooses when one unit leaves, measured the same way for both?

    .venv/Scripts/python.exe tools/estabilidad_de_la_seleccion.py [run] [--workers N]

**Read only on the run.** It reads the design the run exported and the unit layer, refits,
and writes its result beside the other tools' output in `results/_tools_estabilidad/`.
Nothing in `src/` imports it.

`efecto_de_la_exclusion.py` answered this question for the AIC search alone, because the two
runs it compares predate backward elimination, and the thesis presents both methods with the
same weight (Mateo, 2026-10-27). So this one leaves each of the twenty-nine units out in turn
and refits the specification the panel inherits — negative binomial, the affected mode's
exposure, the corrected dataset — with both methods, through `fit_cell`, the function the
pipeline itself calls. Nothing about the fit is reimplemented here: the frame is the one the
run exported, the weights come from `contiguity_weights` over the remaining polygons, and the
candidate pool is the year's.

It asks the two questions `efecto_de_la_exclusion.py` asks, per method:

  1. **Did the selected model change?** One cell is one pair and year; its winner is compared
     with the one the full twenty-nine produced.
  2. **Did what the study reports change?** The order of the twelve candidates by selection
     frequency inside the specification, compared by Spearman against the full order, and
     the largest number of places any candidate moved.

**Before measuring anything it refits the full twenty-nine and requires every cell to
reproduce the run**: the same variables chosen and the same AIC to the sixth decimal, for both
methods. If that fails, what follows would measure this script and not the pipeline.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src import config, loading, regressions
from src.provenance import RunLog

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_RUN = "run_20261009_084114"
DATASET = config.CORRECTED_DATASET
OFFSET_NAME = "MODE_EXPOSURE"
FAMILY = config.NEGATIVE_BINOMIAL_FAMILY
SCRATCH = ROOT / "results" / "_tools_estabilidad"
METHODS = (config.BEST_SUBSET_SELECTION, config.BACKWARD_ELIMINATION_SELECTION)


def _inputs(run: str, log: RunLog):
    """The design the run fitted, the units it fitted on, and the offset and pairs it used."""
    design = pd.read_parquet(ROOT / "results" / run / "data"
                             / f"{config.ANALYSIS_PREFIX}__regression_data__{DATASET}.parquet")
    units = loading.load_territorial_units(log)
    # The exported design is already the twenty-nine, so exclude_units would refuse it for not
    # carrying the excluded unit; the polygons are cut to the units the design carries instead,
    # in the layer's own order, which is what exclude_units leaves.
    units = units[units[config.AREA_CODE_COL].isin(design[config.AREA_CODE_COL])].reset_index(drop=True)
    if len(units) != design[config.AREA_CODE_COL].nunique():
        raise SystemExit("the unit layer does not carry every unit of the exported design")
    offset = next(o for o in config.REGRESSION_OFFSETS if o.name == OFFSET_NAME)
    pairs = regressions.eligible_pairs(design, log)
    return design, units, offset, pairs


def chosen_by_cell(design: pd.DataFrame, units, offset, pairs, log: RunLog,
                   left_out: str | None = None) -> pd.DataFrame:
    """Every cell of the specification refitted, with what each method chose and its AIC."""
    if left_out is not None:
        units = units[units[config.AREA_CODE_COL] != left_out].reset_index(drop=True)
        design = design[design[config.AREA_CODE_COL] != left_out]
    weights, codes = regressions.contiguity_weights(units)
    order = {code: position for position, code in enumerate(codes)}
    rows = []
    for pair in pairs:
        for year in config.REGRESSION_YEARS:
            frame = design[(design[regressions.PAIR_NAME_COL] == pair.name)
                           & (design[config.YEAR_COL] == year)]
            # Ordered as the weights are, exactly as fit_all orders it.
            frame = frame.sort_values(config.AREA_CODE_COL, key=lambda s: s.map(order), kind="stable")
            fitted = regressions.fit_cell(frame, DATASET, offset, pair, year, FAMILY, weights,
                                          config.DEFAULT_CANDIDATE_SET, log)
            if fitted is None:
                continue
            for model in fitted[0]:
                rows.append({"LEFT_OUT": left_out, "PAIR": pair.name, "YEAR": year,
                             "SELECTION_METHOD": model[config.SELECTION_METHOD_COL],
                             "PREDICTORS": model["PREDICTORS"], "AIC": model["AIC"]})
    return pd.DataFrame(rows)


def _worker(arguments: tuple[str, str | None]) -> pd.DataFrame:
    run, left_out = arguments
    # The search tries 286 subsets per cell and some overflow on the way to failing; the pipeline
    # drops those fits, and their warnings say nothing about the ones it keeps.
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    scratch = SCRATCH / (left_out or "todas")
    scratch.mkdir(parents=True, exist_ok=True)
    log = RunLog(run_dir=scratch)
    logging.getLogger().setLevel(logging.ERROR)
    log.logger.setLevel(logging.ERROR)
    design, units, offset, pairs = _inputs(run, log)
    try:
        return chosen_by_cell(design, units, offset, pairs, log, left_out)
    except ValueError as error:
        # contiguity_weights refuses a unit left without neighbours, because Moran's I is
        # undefined for it. Removing a unit that is another's only neighbour does that, and the
        # pipeline would refuse that run too; it is reported as not measurable, not patched.
        if left_out is None or "no neighbour" not in str(error):
            raise
        print(f"  leaving out {left_out} is not measurable: {error}".split(". ")[0])
        return pd.DataFrame(columns=["LEFT_OUT", "PAIR", "YEAR", "SELECTION_METHOD", "PREDICTORS", "AIC"])


def check_reproduces(full: pd.DataFrame, run: str) -> None:
    """The refit on all twenty-nine must be the run, cell by cell and method by method."""
    models = pd.read_parquet(ROOT / "results" / run / "data" / "analysis__regression_models.parquet")
    models = models[(models["DATASET"] == DATASET) & (models["OFFSET"] == OFFSET_NAME)
                    & (models["FAMILY"] == FAMILY)]
    key = ["PAIR", "YEAR", "SELECTION_METHOD"]
    joined = models[key + ["PREDICTORS", "AIC"]].merge(full, on=key, how="outer",
                                                       suffixes=("_run", "_refit"), indicator=True)
    unmatched = joined[joined["_merge"] != "both"]
    differs = joined[(joined["_merge"] == "both")
                     & ((joined["PREDICTORS_run"] != joined["PREDICTORS_refit"])
                        | ((joined["AIC_run"] - joined["AIC_refit"]).abs() > 1e-6))]
    if len(unmatched) or len(differs):
        raise SystemExit(f"the refit does not reproduce {run}: {len(unmatched)} cells present on "
                         f"one side only, {len(differs)} with another model")
    print(f"refit on all twenty-nine reproduces {run}: {len(joined)} models, both methods\n")


def frequency(chosen: pd.DataFrame) -> pd.Series:
    """How many cells chose each candidate, over the full candidate list so absences count."""
    terms = chosen["PREDICTORS"].str.split(", ").explode()
    terms = terms[terms.astype(bool)]
    return terms.value_counts().reindex(config.REGRESSION_URBAN_CANDIDATES, fill_value=0)


def summarise(full: pd.DataFrame, removed: pd.DataFrame) -> pd.DataFrame:
    """Per method: share of winners changed, and how far the frequency order moved."""
    rows = []
    for method in METHODS:
        base = full[full["SELECTION_METHOD"] == method].set_index(["PAIR", "YEAR"])["PREDICTORS"]
        base_frequency = frequency(full[full["SELECTION_METHOD"] == method])
        base_rank = base_frequency.rank(ascending=False, method="min")
        changed, compared, correlations, moves = 0, 0, [], []
        for unit, block in removed[removed["SELECTION_METHOD"] == method].groupby("LEFT_OUT"):
            after = block.set_index(["PAIR", "YEAR"])["PREDICTORS"]
            # Only cells both fits produced: a cell that fails without the unit is a failed fit,
            # not a different choice.
            common = base.index.intersection(after.index)
            changed += int((base[common] != after[common]).sum())
            compared += len(common)
            after_frequency = frequency(block)
            correlations.append(spearmanr(base_frequency, after_frequency).statistic)
            moves.append(int((after_frequency.rank(ascending=False, method="min") - base_rank).abs().max()))
        rows.append({"method": method, "cells_compared": compared, "winner_changed": changed,
                     "share_changed": changed / compared if compared else float("nan"),
                     "spearman_median": float(np.median(correlations)),
                     "spearman_min": float(np.min(correlations)),
                     "spearman_max": float(np.max(correlations)),
                     "largest_move_median": float(np.median(moves)),
                     "largest_move_max": int(np.max(moves)),
                     "units_left_out": len(correlations)})
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", nargs="?", default=DEFAULT_RUN)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    parser.add_argument("--units", type=int, default=None, help="leave out only the first N, to time it")
    arguments = parser.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)

    full = _worker((arguments.run, None))
    check_reproduces(full, arguments.run)

    design = pd.read_parquet(ROOT / "results" / arguments.run / "data"
                             / f"{config.ANALYSIS_PREFIX}__regression_data__{DATASET}.parquet")
    codes = sorted(design[config.AREA_CODE_COL].unique())
    if arguments.units:
        codes = codes[:arguments.units]
    with ProcessPoolExecutor(max_workers=arguments.workers) as pool:
        removed = pd.concat(pool.map(_worker, [(arguments.run, code) for code in codes]),
                            ignore_index=True)

    pd.concat([full, removed]).to_csv(SCRATCH / "elegidas_por_unidad_retirada.csv", index=False,
                                      encoding="utf-8")
    summary = summarise(full, removed)
    summary.to_csv(SCRATCH / "estabilidad_por_metodo.csv", index=False, encoding="utf-8")
    measured = removed["LEFT_OUT"].nunique()
    print(f"{DATASET}, {OFFSET_NAME}, {FAMILY}; one unit left out at a time, "
          f"{measured} of {len(codes)} units measurable\n")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
