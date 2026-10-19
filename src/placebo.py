"""The placebo regression of completeness on the urban candidates (D68).

The approved anteproyecto promises, in its Phase 1, that a placebo regression of
completeness on the urban variables says whether the correction is needed to read their
coefficients. Completeness is rho, the share of two-party crashes recorded with both
parties affected, so the regression is of rho on each candidate.

It is binomial, on the crashes behind each unit cell, with one standardised candidate at a
time, year effects and errors clustered by unit. Year effects take away the city's own
drift, which is the change of practice ρ was built to see; what is left is whether units
with more of a feature recorded differently. It runs over the units and the candidates the
regressions read, taken from the design table the regressions export, so the placebo and
the models cannot disagree about who is in.

**Why the counts and not the shrunk value of D68's empirical Bayes.** Where a pair shows
no spread between units beyond noise, every shrunk cell is the city value of its year, the
year effects absorb all of it, and a regression on it returns a coefficient of zero with a
standard error of zero. That is the shrinkage speaking. The counts carry the same
information weighted by the same crashes and let noise be noise.

**Why several windows.** rho is not only recording: a fast street can hurt both parties
more often for physical reasons. An association present while the recording was stable that
fades once it settles belongs to the form; one that stays in the reference window may belong
to the street. The corrected set is fitted over the whole window, to say how much of an
association the correction removes.

It reads three tables other routes export and rebuilds none of them:

    the rho table                analysis__rho_long             route rho
    the correction plan          analysis__correction_plan      route corrected
    the regression design        analysis__regression_data      route regressions

Run it with:

    python -m src.run_pipeline placebo
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

try:  # regular package import
    from src import config
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


RHO_FILENAME = f"{config.ANALYSIS_PREFIX}__rho_long.parquet"
PLAN_FILENAME = f"{config.ANALYSIS_PREFIX}__correction_plan.csv"
CITY_CORRECTION_FILENAME = f"{config.ANALYSIS_PREFIX}__correction_city.csv"
DESIGN_FILENAME = f"{config.ANALYSIS_PREFIX}__regression_data.parquet"


def read_inputs(log: RunLog) -> dict[str, pd.DataFrame]:
    """The three tables, each from the most recent run that holds it, and which run that was."""
    frames: dict[str, pd.DataFrame] = {}
    for name, filename in (("rho", RHO_FILENAME), ("plan", PLAN_FILENAME),
                           ("city", CITY_CORRECTION_FILENAME), ("design", DESIGN_FILENAME)):
        run_dir = config.run_directory_holding(filename)
        path = run_dir / config.DATA_SUBDIR / filename
        frames[name] = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        log.info("%s read from %s", name, run_dir.name)
    return frames


def unit_cells(frames: dict[str, pd.DataFrame], log: RunLog) -> dict[str, pd.DataFrame]:
    """The unit cells of rho for both sets, on the estimating units.

    The corrected cell keeps its denominator and gains in its numerator the crashes the
    correction plan reclassifies there: a reclassified crash moves from one affected party to
    two and stays the same crash. Read from the plan, never recomputed.
    """
    rho = frames["rho"]
    cells = rho[rho[config.AGGREGATION_LEVEL_COL] == config.UNIT_LEVEL][[
        config.AREA_CODE_COL, config.YEAR_COL, config.PAIR_COL,
        config.RHO_NUMERATOR_COL, config.RHO_DENOMINATOR_COL]].copy()
    cells[config.YEAR_COL] = cells[config.YEAR_COL].astype(int)
    key = [config.PAIR_COL, config.YEAR_COL, config.AREA_CODE_COL]
    added = frames["plan"].groupby(key)[config.CORRECTION_DEFICIT_COL].sum().rename("_added")
    corrected = cells.merge(added.reset_index(), on=key, how="left")
    corrected["_added"] = corrected["_added"].fillna(0).astype(int)
    corrected[config.RHO_NUMERATOR_COL] = corrected[config.RHO_NUMERATOR_COL] + corrected["_added"]

    estimating = set(frames["design"][config.AREA_CODE_COL])
    out = {}
    for dataset, frame in ((config.OBSERVED_DATASET, cells), (config.CORRECTED_DATASET, corrected)):
        kept = frame[frame[config.AREA_CODE_COL].isin(estimating)].copy()
        log.record(
            f"keep the estimating units, {dataset}",
            rows_in=len(frame),
            rows_out=len(kept),
            changes=[(len(kept) - len(frame), "unit cells of the units the regressions leave out (D56)")],
        )
        out[dataset] = kept
    out["_corrected_all_units"] = corrected
    return out


def _holm(p_values: pd.Series) -> pd.Series:
    """Holm's step-down adjustment over every test of one window and one set."""
    order = p_values.sort_values().index
    m = len(order)
    adjusted = np.maximum.accumulate([(m - i) * p_values[j] for i, j in enumerate(order)])
    return pd.Series(np.minimum(adjusted, 1.0), index=order).reindex(p_values.index)


def fit(cells: dict[str, pd.DataFrame], design: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """Every declared window, set, pair and candidate, one regression each."""
    by_unit_year = design.drop_duplicates([config.AREA_CODE_COL, config.YEAR_COL])
    rows = []
    for window in config.PLACEBO_WINDOWS:
        candidates = config.placebo_candidates(window.years)
        for dataset in window.datasets:
            frame = cells[dataset]
            frame = frame[frame[config.YEAR_COL].isin(window.years)
                          & (frame[config.RHO_DENOMINATOR_COL] > 0)]
            frame = frame.merge(by_unit_year[[config.AREA_CODE_COL, config.YEAR_COL, *candidates]],
                                on=[config.AREA_CODE_COL, config.YEAR_COL], how="inner")
            for pair in config.RHO_PAIR_LABELS:
                group = frame[frame[config.PAIR_COL] == pair]
                k = group[config.RHO_NUMERATOR_COL].to_numpy(float)
                n = group[config.RHO_DENOMINATOR_COL].to_numpy(float)
                response = np.column_stack([k, n - k])
                year_effects = pd.get_dummies(group[config.YEAR_COL], prefix="y", drop_first=True, dtype=float)
                for name in candidates:
                    x = group[name].astype(float)
                    row = {config.PLACEBO_WINDOW_COL: window.name, config.DATASET_COL: dataset,
                           config.PAIR_COL: pair, config.PLACEBO_CANDIDATE_COL: name,
                           config.PLACEBO_CELLS_COL: len(group),
                           config.PLACEBO_UNITS_COL: group[config.AREA_CODE_COL].nunique(),
                           "FIRST_YEAR": window.years[0], "LAST_YEAR": window.years[-1]}
                    # Named rather than skipped: a pair with every crash on one side of the
                    # outcome, or a candidate that does not vary, has no coefficient to give.
                    if len(group) == 0 or k.sum() in (0, n.sum()) or x.std(ddof=0) == 0:
                        rows.append({**row, config.PLACEBO_COEFFICIENT_COL: np.nan,
                                     config.PLACEBO_STD_ERROR_COL: np.nan, config.PLACEBO_P_VALUE_COL: np.nan})
                        continue
                    regressors = pd.concat([((x - x.mean()) / x.std(ddof=0)).rename(name), year_effects], axis=1)
                    model = sm.GLM(response, sm.add_constant(regressors.to_numpy()),
                                   family=sm.families.Binomial()).fit(
                        cov_type="cluster", cov_kwds={"groups": group[config.AREA_CODE_COL].to_numpy()})
                    rows.append({**row, config.PLACEBO_COEFFICIENT_COL: float(model.params[1]),
                                 config.PLACEBO_STD_ERROR_COL: float(model.bse[1]),
                                 config.PLACEBO_P_VALUE_COL: float(model.pvalues[1])})
    table = pd.DataFrame(rows)
    table[config.PLACEBO_P_HOLM_COL] = np.nan
    for _, group in table.groupby([config.PLACEBO_WINDOW_COL, config.DATASET_COL]):
        defined = group[config.PLACEBO_P_VALUE_COL].dropna()
        table.loc[defined.index, config.PLACEBO_P_HOLM_COL] = _holm(defined)
    log.info("placebo: %d regressions over %d windows", int(table[config.PLACEBO_P_VALUE_COL].notna().sum()),
             len(config.PLACEBO_WINDOWS))
    return table


def export(table: pd.DataFrame, log: RunLog) -> dict[str, Path]:
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{config.PLACEBO_FILENAME}.csv"
    # The table says under itself what its p-values are, as the regression tables do.
    with open(path, "w", encoding="utf-8", newline="") as handle:
        table.to_csv(handle, index=False)
        handle.write(
            "# Binomial regressions of rho on one standardised candidate at a time, with year "
            "effects and errors clustered by unit. COEFFICIENT is the change in the log-odds of "
            "both parties being recorded per standard deviation. P_VALUE_HOLM adjusts over every "
            "test of the same WINDOW and DATASET. rho is not only recording, so read the windows "
            "against each other (D68).\n"
        )
    table.to_parquet(path.with_suffix(".parquet"))
    log.info("exported the placebo table to %s/", config.DATA_SUBDIR)
    return {"placebo": path}


def verify(table: pd.DataFrame, cells: dict[str, pd.DataFrame], frames: dict[str, pd.DataFrame],
           log: RunLog) -> bool:
    checks: list[tuple[str, bool, str]] = []

    corrected = cells["_corrected_all_units"]
    over = int((corrected[config.RHO_NUMERATOR_COL] > corrected[config.RHO_DENOMINATOR_COL]).sum())
    checks.append(("no corrected numerator exceeds its denominator", over == 0, f"{over} cell(s) above"))

    # The plan and the rho table come from two routes. If they describe the same crashes,
    # the corrected unit cells summed over the city give back the corrected rho the
    # correction itself reports, pair-year by pair-year.
    city = frames["city"]
    summed = corrected.groupby([config.PAIR_COL, config.YEAR_COL])[
        [config.RHO_NUMERATOR_COL, config.RHO_DENOMINATOR_COL]].sum().reset_index().rename(
        columns={config.RHO_NUMERATOR_COL: "_k", config.RHO_DENOMINATOR_COL: "_n"})
    joined = city.merge(summed, on=[config.PAIR_COL, config.YEAR_COL], how="inner")
    rebuilt = joined["_k"] / joined["_n"]
    worst = float((rebuilt - joined[config.CORRECTION_RHO_CORRECTED_COL]).abs().max())
    # The correction's city table counts the crashes of the pair; ours must count the same.
    same_denominators = bool((joined["_n"] == joined[config.RHO_DENOMINATOR_COL]).all())
    checks.append((
        "the plan and the rho table rebuild the correction's own city rho",
        worst < 1e-12 and len(joined) == len(city) and same_denominators,
        f"{len(joined)} of {len(city)} pair-years, worst difference {worst:.1e}",
    ))

    units_in = {d: cells[d][config.AREA_CODE_COL].nunique() for d in (config.OBSERVED_DATASET, config.CORRECTED_DATASET)}
    design_units = frames["design"][config.AREA_CODE_COL].nunique()
    checks.append(("the placebo runs on the units the regressions read",
                   all(n == design_units for n in units_in.values()),
                   f"{design_units} in the design, {units_in}"))

    expected = sum(len(w.datasets) * len(config.RHO_PAIR_LABELS) * len(config.placebo_candidates(w.years))
                   for w in config.PLACEBO_WINDOWS)
    checks.append(("one row per declared window, set, pair and candidate", len(table) == expected,
                   f"{len(table)} of {expected}"))

    defined = table[config.PLACEBO_P_VALUE_COL].notna()
    p = table.loc[defined, config.PLACEBO_P_VALUE_COL]
    holm = table.loc[defined, config.PLACEBO_P_HOLM_COL]
    checks.append(("every p-value and every Holm value lies in [0, 1], Holm never below its p",
                   bool(p.between(0, 1).all() and holm.between(0, 1).all() and (holm >= p - 1e-15).all()),
                   f"{int(defined.sum())} defined, {int((~defined).sum())} with no coefficient to give"))
    positive_se = bool((table.loc[defined, config.PLACEBO_STD_ERROR_COL] > 0).all())
    checks.append(("every defined coefficient has a positive standard error", positive_se,
                   "a zero would mean a regressand with no variation left"))

    width = max(len(name) for name, _, _ in checks)
    lines = [f"{'check'.ljust(width)}  {'result':>8}  detail", f"{'-' * width}  {'-' * 8}  ------"]
    for name, ok, detail in checks:
        lines.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("placebo verification:", "\n".join(lines))
    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("placebo verification FAILED")
    return passed


def report(table: pd.DataFrame, log: RunLog) -> None:
    """How many tests clear 0.05 against chance, per window and set, and which survive Holm."""
    lines = []
    for (window, dataset), group in table.groupby([config.PLACEBO_WINDOW_COL, config.DATASET_COL], sort=False):
        defined = group[group[config.PLACEBO_P_VALUE_COL].notna()]
        below = int((defined[config.PLACEBO_P_VALUE_COL] < 0.05).sum())
        survive = defined[defined[config.PLACEBO_P_HOLM_COL] < 0.05]
        lines.append(f"{window:<10} {dataset:<14} {len(defined):>4} tests, {below:>3} below 0.05 "
                     f"({0.05 * len(defined):.1f} by chance), {len(survive)} after Holm")
        for row in survive.itertuples():
            lines.append(f"    {getattr(row, config.PAIR_COL):<28} {getattr(row, config.PLACEBO_CANDIDATE_COL):<34} "
                         f"{getattr(row, config.PLACEBO_COEFFICIENT_COL):+.3f} "
                         f"({getattr(row, config.PLACEBO_STD_ERROR_COL):.3f})")
    log.table("placebo, what clears the bar:", "\n".join(lines))
