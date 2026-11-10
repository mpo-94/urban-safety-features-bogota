"""Phase 4: Bogota set against the European determinants it replicates (D70).

The European study (klanjcicIdentifyingUrbanFeatures2022) explains the KSI rate of
each collision type across 24 cities with ordinary least squares on standardised
variables, choosing among every model of two and three covariates by AIC. This
module does the same across the 29 estimating units of Bogota, on the casualties of
2012-2024 summed per unit, and then classifies each European association that has an
equivalent here as reproduced, divergent, inconclusive or not selected, by the rule
D70 declared before the first estimate.

Three things are built here and nowhere else:

- **the modal shares** of walking and cycling per unit, counted at the origin over
  every mode of each survey, from the surveys of the window;
- **the accumulated design**: per unit, the summed population, the mean cycleway and
  the two shares, and per series and stratum, the summed casualties and their rate;
- **the models and the classification.**

The count model of D67.4, with the population as offset, is fitted on the subset the
standardised least squares selected and reported only as a check of direction; its
coefficient is a log rate ratio, not the European scale, so it classifies nothing.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from src import config, exposure, loading, predictors, regressions, surveys
from src.provenance import RunLog

MATRIX_FILES = {
    config.OBSERVED_DATASET: f"{config.ANALYSIS_PREFIX}__matrix_long.parquet",
    config.CORRECTED_DATASET: f"{config.ANALYSIS_PREFIX}__matrix_long__{config.CORRECTION_FILE_SUFFIX}.parquet",
}
DESIGN_FILE = f"{config.ANALYSIS_PREFIX}__regression_data.parquet"
CYCLEWAY = "CYCLEWAY_LENGTH_DENSITY"
POPULATION_SUM = "POPULATION_SUM"
RATE = "RATE_PER_MILLION"
TRIPS_ALL = "TRIPS_ALL_MODES_AT_ORIGIN"
SHARE_LEVEL_COL = "SHARE_LEVEL"
SURVEY_LEVEL = "SURVEY_YEAR"
WINDOW_LEVEL = "WINDOW_MEAN"


# ---------------------------------------------------------------------------
# The modal shares
# ---------------------------------------------------------------------------


def survey_shares(survey: config.MobilitySurvey, units, log: RunLog) -> pd.DataFrame:
    """Walking and cycling as shares of every weekday trip that begins in each unit.

    The survey's own readers do every step that has a rule: the sources, the
    weights, the mode labels, the day type and the zone codes. What is new is only
    that the modes the exposure does not follow stay in, because they are the
    denominator of a share (D67.4: public transport and taxi were 43 % of the trips
    in 2011). Each origin zone is given to the units by the share of its area, the
    rule the exposure uses for a trip's endpoint.
    """
    frame = surveys.read_sources(survey, log)
    weights = surveys.to_number(frame[survey.weight_column], survey.trips_decimal)
    frame = frame[weights.notna()].copy()
    frame[surveys.TRIPS_COL] = weights[weights.notna()]
    frame[config.ACTOR_TYPE_COL] = surveys.map_modes(frame, survey, log)
    day_type, _ = surveys.assign_day_type(frame, survey, log)
    frame = frame[day_type == config.MODEL_EXPOSURE_DAY_TYPE].copy()
    frame[surveys.ZONE_ORIGIN_COL] = surveys.zone_code_text(
        frame[survey.origin_zone_column], f"{survey.label} {survey.origin_zone_column}")

    by_zone = pd.DataFrame({
        TRIPS_ALL: frame.groupby(surveys.ZONE_ORIGIN_COL)[surveys.TRIPS_COL].sum(),
        config.WALKING_SHARE: frame[frame[config.ACTOR_TYPE_COL] == config.PEDESTRIAN]
        .groupby(surveys.ZONE_ORIGIN_COL)[surveys.TRIPS_COL].sum(),
        config.CYCLING_SHARE: frame[frame[config.ACTOR_TYPE_COL] == config.BICYCLE]
        .groupby(surveys.ZONE_ORIGIN_COL)[surveys.TRIPS_COL].sum(),
    }).fillna(0.0).reset_index().rename(columns={surveys.ZONE_ORIGIN_COL: surveys.ZONE_CODE_COL})

    zones = surveys.read_zoning(survey, log)
    shares = exposure.zone_area_shares(zones, units, survey, log)
    spread = by_zone.merge(shares, on=surveys.ZONE_CODE_COL, how="inner")
    for column in (TRIPS_ALL, config.WALKING_SHARE, config.CYCLING_SHARE):
        spread[column] = spread[column] * spread[exposure.ZONE_SHARE_COL]
    per_unit = spread.groupby(config.AREA_CODE_COL)[[TRIPS_ALL, config.WALKING_SHARE, config.CYCLING_SHARE]].sum()
    for column in (config.WALKING_SHARE, config.CYCLING_SHARE):
        per_unit[column] = per_unit[column] / per_unit[TRIPS_ALL]
    per_unit = per_unit.reset_index()
    per_unit[config.YEAR_COL] = survey.year
    log.info("%s: weekday trips at origin in the units %s; walking %.3f and cycling %.3f of them in the city",
             survey.label, f"{per_unit[TRIPS_ALL].sum():,.0f}",
             float((per_unit[config.WALKING_SHARE] * per_unit[TRIPS_ALL]).sum() / per_unit[TRIPS_ALL].sum()),
             float((per_unit[config.CYCLING_SHARE] * per_unit[TRIPS_ALL]).sum() / per_unit[TRIPS_ALL].sum()))
    return per_unit


def modal_shares(log: RunLog) -> pd.DataFrame:
    """The shares per unit and survey, and their mean over the surveys of the window."""
    # Projected as the exposure route projects them, so that a zone's share of a unit is an area in
    # square metres and not in square degrees.
    units = predictors.prepare_units(loading.load_territorial_units(log))
    declared = {s.year: s for s in config.MOBILITY_SURVEYS}
    missing = [y for y in config.CONTRAST_SURVEY_YEARS if y not in declared]
    if missing:
        raise ValueError(f"CONTRAST_SURVEY_YEARS names {missing}, which no declared survey covers")
    per_survey = pd.concat([survey_shares(declared[y], units, log) for y in config.CONTRAST_SURVEY_YEARS],
                           ignore_index=True)
    per_survey[SHARE_LEVEL_COL] = SURVEY_LEVEL
    mean = per_survey.groupby(config.AREA_CODE_COL)[[config.WALKING_SHARE, config.CYCLING_SHARE, TRIPS_ALL]].mean()
    mean = mean.reset_index()
    mean[config.YEAR_COL] = pd.NA
    mean[SHARE_LEVEL_COL] = WINDOW_LEVEL
    out = pd.concat([per_survey, mean], ignore_index=True)
    out[config.YEAR_COL] = out[config.YEAR_COL].astype("Int64")
    return out


# ---------------------------------------------------------------------------
# The accumulated design
# ---------------------------------------------------------------------------


def read_inputs(log: RunLog) -> dict[str, pd.DataFrame]:
    frames = {}
    for dataset, filename in MATRIX_FILES.items():
        run_dir = config.run_directory_holding(filename, config.CONTRAST_MATRIX_RUN)
        frames[dataset] = pd.read_parquet(run_dir / config.DATA_SUBDIR / filename)
        log.info("%s matrix read from %s", dataset, run_dir.name)
    run_dir = config.run_directory_holding(DESIGN_FILE, config.CONTRAST_DESIGN_RUN)
    frames["design"] = pd.read_parquet(run_dir / config.DATA_SUBDIR / DESIGN_FILE)
    log.info("regression design read from %s", run_dir.name)
    return frames


def accumulated_design(frames: dict[str, pd.DataFrame], shares: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """One row per set, stratum, series and estimating unit, with the covariates beside it."""
    design = frames["design"]
    years = list(config.REGRESSION_YEARS)
    per_unit = design.drop_duplicates([config.AREA_CODE_COL, config.YEAR_COL])
    per_unit = per_unit[per_unit[config.YEAR_COL].isin(years)]
    covariates = per_unit.groupby(config.AREA_CODE_COL).agg(
        **{POPULATION_SUM: (config.OFFSET_POPULATION, "sum"), CYCLEWAY: (CYCLEWAY, "mean"),
           config.AREA_NAME_COL: (config.AREA_NAME_COL, "first")})
    window = shares[shares[SHARE_LEVEL_COL] == WINDOW_LEVEL].set_index(config.AREA_CODE_COL)
    covariates = covariates.join(window[[config.WALKING_SHARE, config.CYCLING_SHARE]], how="left")
    if covariates[[config.WALKING_SHARE, config.CYCLING_SHARE]].isna().any().any():
        raise ValueError("an estimating unit has no modal share: no survey zone of the window reaches it")
    units = covariates.index.tolist()
    log.info("accumulated design: %d estimating units, %d to %d", len(units), years[0], years[-1])

    rows = []
    for dataset in MATRIX_FILES:
        matrix = frames[dataset]
        window_rows = matrix[matrix[config.YEAR_COL].isin(years) & matrix[config.AREA_CODE_COL].isin(units)]
        for series in config.CONTRAST_SERIES:
            cells = window_rows[(window_rows[config.PARTY_TYPE_COL] == series.affected)
                                & (window_rows[config.COUNTERPART_TYPE_COL] == series.counterpart)]
            summed = cells.groupby(config.AREA_CODE_COL)[list(config.CONTRAST_STRATA)].sum()
            for stratum in config.CONTRAST_STRATA:
                block = covariates.copy()
                block[stratum] = summed[stratum].reindex(block.index).fillna(0).astype(int)
                block = block.rename(columns={stratum: "CASUALTIES"})
                block[RATE] = block["CASUALTIES"] / block[POPULATION_SUM] * config.CONTRAST_RATE_PER
                block[config.DATASET_COL] = dataset
                block["STRATUM"] = stratum
                block["SERIES"] = series.label
                rows.append(block.reset_index())
    table = pd.concat(rows, ignore_index=True)
    for column in (*config.CONTRAST_CANDIDATES, RATE):
        z = table.groupby([config.DATASET_COL, "STRATUM", "SERIES"])[column].transform(
            lambda v: (v - v.mean()) / v.std(ddof=1))
        table[f"{column}_STD"] = z
    return table


# ---------------------------------------------------------------------------
# The models
# ---------------------------------------------------------------------------


@dataclass
class Fit:
    variables: tuple[str, ...]
    result: object
    aic: float


def subsets() -> list[tuple[str, ...]]:
    """Every model of two and of three covariates, as the European study searched (D70.5)."""
    return [c for k in (2, 3) for c in itertools.combinations(config.CONTRAST_CANDIDATES, k)]


def fit_standardised(block: pd.DataFrame, variables: tuple[str, ...]) -> Fit:
    """Ordinary least squares of the standardised rate on standardised covariates, with no intercept.

    Their equation is y = beta X on centred variables, so the intercept is zero by
    construction and is not estimated (section 4.3).
    """
    y = block[f"{RATE}_STD"].to_numpy(dtype=float)
    x = block[[f"{v}_STD" for v in variables]].to_numpy(dtype=float)
    result = sm.OLS(y, x).fit()
    return Fit(variables, result, float(result.aic))


def fit_count(block: pd.DataFrame, variables: tuple[str, ...]) -> tuple[str, object | None]:
    """The count model of D67.4 on the same covariates: Poisson, or negative binomial if overdispersed."""
    counts = block["CASUALTIES"].to_numpy(dtype=float)
    design = sm.add_constant(block[[f"{v}_STD" for v in variables]].to_numpy(dtype=float), has_constant="add")
    offset = np.log(block[POPULATION_SUM].to_numpy(dtype=float))
    poisson = regressions._fit_one(config.POISSON_FAMILY, counts, design, offset)
    if poisson is None:
        return config.POISSON_FAMILY, None
    dispersion = float(poisson.pearson_chi2 / poisson.df_resid)
    if dispersion > config.OVERDISPERSION_THRESHOLD:
        negative = regressions._fit_one(config.NEGATIVE_BINOMIAL_FAMILY, counts, design, offset)
        described = regressions._describe(negative, tuple(variables)) if negative is not None else None
        if described is not None:
            return config.NEGATIVE_BINOMIAL_FAMILY, negative
    return config.POISSON_FAMILY, poisson


def model_rows(table: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """Every standardised model of every set, stratum and series, and the count model of the selected one."""
    rows = []
    for (dataset, stratum, series), block in table.groupby([config.DATASET_COL, "STRATUM", "SERIES"], sort=False):
        fits = [fit_standardised(block, v) for v in subsets()]
        best = min(fits, key=lambda f: f.aic)
        for fit in fits:
            intervals = fit.result.conf_int(alpha=config.CONTRAST_SIGNIFICANCE)
            for position, variable in enumerate(fit.variables):
                rows.append({
                    config.DATASET_COL: dataset, "STRATUM": stratum, "SERIES": series,
                    "FAMILY": config.CONTRAST_OLS_STANDARDISED, "VARIABLES": "+".join(fit.variables),
                    "N_VARIABLES": len(fit.variables), "SELECTED": fit is best, "AIC": fit.aic,
                    "VARIABLE": variable, "COEFFICIENT": float(fit.result.params[position]),
                    "STD_ERROR": float(fit.result.bse[position]),
                    "CI_LOW": float(intervals[position, 0]), "CI_HIGH": float(intervals[position, 1]),
                    "P_VALUE": float(fit.result.pvalues[position]), "R2": float(fit.result.rsquared),
                    "UNITS": int(fit.result.nobs),
                })
        family, count = fit_count(block, best.variables)
        if count is not None:
            intervals = np.asarray(count.conf_int(alpha=config.CONTRAST_SIGNIFICANCE))
            for position, variable in enumerate(best.variables, start=1):
                rows.append({
                    config.DATASET_COL: dataset, "STRATUM": stratum, "SERIES": series, "FAMILY": family,
                    "VARIABLES": "+".join(best.variables), "N_VARIABLES": len(best.variables),
                    "SELECTED": True, "AIC": float(count.aic), "VARIABLE": variable,
                    "COEFFICIENT": float(np.asarray(count.params)[position]),
                    "STD_ERROR": float(np.asarray(count.bse)[position]),
                    "CI_LOW": float(intervals[position, 0]), "CI_HIGH": float(intervals[position, 1]),
                    "P_VALUE": float(np.asarray(count.pvalues)[position]), "R2": np.nan,
                    "UNITS": int(count.nobs),
                })
        else:
            log.warn("%s %s %s: the count model could not be fitted on %s", dataset, stratum, series,
                     "+".join(best.variables))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# The classification
# ---------------------------------------------------------------------------


def classify(level: bool, europe: config.EuropeanAssociation, beta: float, low: float, high: float,
             p_value: float) -> str:
    """The rule of D70.6, applied to one association that Bogota's selected model holds."""
    same_sign = np.sign(beta) == np.sign(europe.beta)
    significant = p_value < config.CONTRAST_SIGNIFICANCE
    if not same_sign:
        return config.CONTRAST_DIVERGENT if significant else config.CONTRAST_INCONCLUSIVE
    if level and (high < europe.low or low > europe.high):
        return config.CONTRAST_DIVERGENT
    return config.CONTRAST_REPRODUCED


def classification(models: pd.DataFrame) -> pd.DataFrame:
    rows = []
    standardised = models[models.FAMILY == config.CONTRAST_OLS_STANDARDISED]
    count = models[models.FAMILY != config.CONTRAST_OLS_STANDARDISED]
    for europe in config.EUROPEAN_ASSOCIATIONS:
        for dataset in MATRIX_FILES:
            for stratum in config.CONTRAST_STRATA:
                key = ((standardised[config.DATASET_COL] == dataset) & (standardised.STRATUM == stratum)
                       & (standardised.SERIES == europe.series.label))
                chosen = standardised[key & standardised.SELECTED & (standardised.VARIABLE == europe.candidate)]
                full = standardised[key & (standardised.N_VARIABLES == 3) & (standardised.VARIABLE == europe.candidate)]
                level = stratum == config.CONTRAST_LEVEL_STRATUM
                source = chosen if len(chosen) else full
                row = source.iloc[0]
                status = (classify(level, europe, row.COEFFICIENT, row.CI_LOW, row.CI_HIGH, row.P_VALUE)
                          if len(chosen) else config.CONTRAST_NOT_SELECTED)
                check = count[(count[config.DATASET_COL] == dataset) & (count.STRATUM == stratum)
                              & (count.SERIES == europe.series.label) & (count.VARIABLE == europe.candidate)]
                rows.append({
                    "CANDIDATE": europe.candidate, "SERIES": europe.series.label,
                    config.PAIR_FIRST_COL: europe.series.affected, config.PAIR_SECOND_COL: europe.series.counterpart,
                    config.DATASET_COL: dataset, "STRATUM": stratum,
                    "COMPARISON": "LEVEL" if level else "DIRECTION",
                    "EUROPE_BETA": europe.beta, "EUROPE_CI_LOW": europe.low, "EUROPE_CI_HIGH": europe.high,
                    "BOGOTA_BETA": row.COEFFICIENT, "BOGOTA_CI_LOW": row.CI_LOW, "BOGOTA_CI_HIGH": row.CI_HIGH,
                    "BOGOTA_P_VALUE": row.P_VALUE, "BOGOTA_MODEL": row.VARIABLES,
                    "SELECTED_IN_BOGOTA": bool(len(chosen)),
                    "MAGNITUDE_RATIO": row.COEFFICIENT / europe.beta,
                    "COUNT_MODEL_FAMILY": check.FAMILY.iloc[0] if len(check) else None,
                    "COUNT_MODEL_COEFFICIENT": check.COEFFICIENT.iloc[0] if len(check) else np.nan,
                    "STATUS": status,
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Export, checks and report
# ---------------------------------------------------------------------------


NOTES = {
    config.CONTRAST_SHARES_FILENAME: (
        "# Walking and cycling as shares of every weekday trip beginning in the unit, all modes of the "
        "survey in the denominator, origin zones given to units by area; WINDOW_MEAN averages the surveys "
        "of the window (D70.4).\n"),
    config.CONTRAST_DESIGN_FILENAME: (
        "# The accumulated cross-section of Phase 4: casualties and population summed over 2012-2024 on "
        "the 29 estimating units, the cycleway averaged over the window, and every variable standardised "
        "within its set, stratum and series (D70).\n"),
    config.CONTRAST_MODELS_FILENAME: (
        "# OLS_STANDARDISED rows are the European study's scale: OLS of the standardised rate on "
        "standardised covariates, no intercept, every model of two and three covariates, SELECTED by AIC. "
        "The count-family rows refit the selected subset with the population as offset and are a check "
        "of direction only (D70.1).\n"),
    config.CONTRAST_CLASSIFICATION_FILENAME: (
        "# Each European association with an equivalent here, classified by D70.6: in LEVEL on deaths, "
        "in DIRECTION on the injured. NOT_SELECTED means Bogota's AIC-selected model leaves the variable "
        "out; its coefficient is then the three-covariate model's, for direction only.\n"),
}


def export(tables: dict[str, pd.DataFrame], log: RunLog) -> dict[str, Path]:
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, frame in tables.items():
        path = data_dir / f"{name}.csv"
        with open(path, "w", encoding="utf-8", newline="") as handle:
            frame.to_csv(handle, index=False)
            handle.write(NOTES[name])
        frame.to_parquet(path.with_suffix(".parquet"))
        paths[name] = path
    log.info("exported the four Phase 4 tables to %s/", config.DATA_SUBDIR)
    return paths


def _synthetic_checks() -> list[tuple[str, bool, str]]:
    checks = []
    rng = np.random.default_rng(20261109)
    n = 5000
    x = rng.normal(size=(n, 2))
    y = 0.5 * x[:, 0] - 0.3 * x[:, 1] + rng.normal(scale=0.5, size=n)
    block = pd.DataFrame({f"{RATE}_STD": (y - y.mean()) / y.std(ddof=1)})
    for i, name in enumerate(config.CONTRAST_CANDIDATES[:2]):
        block[f"{name}_STD"] = (x[:, i] - x[:, i].mean()) / x[:, i].std(ddof=1)
    fit = fit_standardised(block, config.CONTRAST_CANDIDATES[:2])
    expected = np.array([0.5, -0.3]) / y.std(ddof=1)
    worst = float(np.max(np.abs(fit.result.params - expected)))
    checks.append(("a known standardised beta is recovered", worst < 0.02, f"worst difference {worst:.3f}"))

    europe = config.EUROPEAN_ASSOCIATIONS[0]  # -0.49 [-0.80, -0.17]
    cases = [
        ((True, -0.3, -0.6, 0.0, 0.06), config.CONTRAST_REPRODUCED),
        ((True, -1.5, -1.9, -1.1, 0.001), config.CONTRAST_DIVERGENT),
        ((True, 0.4, 0.1, 0.7, 0.01), config.CONTRAST_DIVERGENT),
        ((True, 0.2, -0.2, 0.6, 0.3), config.CONTRAST_INCONCLUSIVE),
        ((False, -1.5, -1.9, -1.1, 0.001), config.CONTRAST_REPRODUCED),
        ((False, 0.2, -0.2, 0.6, 0.3), config.CONTRAST_INCONCLUSIVE),
    ]
    wrong = [args for args, want in cases if classify(args[0], europe, *args[1:]) != want]
    checks.append(("the classification rule gives each declared case its label", not wrong, f"{len(wrong)} wrong"))
    return checks


def verify(tables: dict[str, pd.DataFrame], frames: dict[str, pd.DataFrame], log: RunLog) -> bool:
    checks = _synthetic_checks()
    shares = tables[config.CONTRAST_SHARES_FILENAME]
    window = shares[shares[SHARE_LEVEL_COL] == WINDOW_LEVEL]
    within = bool(window[config.WALKING_SHARE].between(0, 1).all() and window[config.CYCLING_SHARE].between(0, 1).all()
                  and ((window[config.WALKING_SHARE] + window[config.CYCLING_SHARE]) <= 1).all())
    checks.append(("every share lies in [0, 1] and walking plus cycling does not pass 1", within, ""))
    per_survey = shares[shares[SHARE_LEVEL_COL] == SURVEY_LEVEL]
    checks.append(("every survey of the window gives every unit a share",
                   per_survey.groupby(config.YEAR_COL)[config.AREA_CODE_COL].nunique().eq(30).all()
                   and set(per_survey[config.YEAR_COL]) == set(config.CONTRAST_SURVEY_YEARS),
                   str(per_survey.groupby(config.YEAR_COL)[config.AREA_CODE_COL].nunique().to_dict())))

    design = tables[config.CONTRAST_DESIGN_FILENAME]
    units = design[config.AREA_CODE_COL].nunique()
    excluded = {e.unit for e in config.REGRESSION_EXCLUDED_UNITS}
    checks.append(("the design holds the 29 estimating units and none of the excluded",
                   units == 29 and not (set(design[config.AREA_CODE_COL]) & excluded), f"{units} units"))
    # The record balance: the casualties summed here are those of the matrix in the window and units.
    years = list(config.REGRESSION_YEARS)
    gaps = []
    for dataset in MATRIX_FILES:
        matrix = frames[dataset]
        matrix = matrix[matrix[config.YEAR_COL].isin(years) & ~matrix[config.AREA_CODE_COL].isin(excluded)]
        for series in config.CONTRAST_SERIES:
            cells = matrix[(matrix[config.PARTY_TYPE_COL] == series.affected)
                           & (matrix[config.COUNTERPART_TYPE_COL] == series.counterpart)]
            for stratum in config.CONTRAST_STRATA:
                held = design[(design[config.DATASET_COL] == dataset) & (design.STRATUM == stratum)
                              & (design.SERIES == series.label)]["CASUALTIES"].sum()
                gaps.append(int(cells[stratum].sum()) - int(held))
    checks.append(("the design holds every casualty of the matrix in the window and the units",
                   all(g == 0 for g in gaps), f"gaps {sorted(set(gaps))}"))
    population = frames["design"].drop_duplicates([config.AREA_CODE_COL, config.YEAR_COL])
    population = population[population[config.YEAR_COL].isin(years)][config.OFFSET_POPULATION].sum()
    held = design.drop_duplicates(config.AREA_CODE_COL)[POPULATION_SUM].sum()
    checks.append(("the summed population is the design table's", abs(population - held) < 1e-6,
                   f"{held:,.0f} of {population:,.0f}"))
    # The threshold of D67: fewer than half the units at zero, on deaths.
    deaths = design[design.STRATUM == config.CONTRAST_LEVEL_STRATUM]
    zeros = deaths.groupby([config.DATASET_COL, "SERIES"])["CASUALTIES"].apply(lambda v: int((v == 0).sum()))
    checks.append(("every series passes D67's threshold on deaths", bool((zeros < units / 2).all()),
                   f"most units at zero: {int(zeros.max())} of {units}"))
    standard = design.groupby([config.DATASET_COL, "STRATUM", "SERIES"])[f"{RATE}_STD"].agg(["mean", "std"])
    checks.append(("every standardised variable has mean zero and deviation one",
                   bool((standard["mean"].abs() < 1e-9).all() and ((standard["std"] - 1).abs() < 1e-9).all()), ""))

    models = tables[config.CONTRAST_MODELS_FILENAME]
    ols = models[models.FAMILY == config.CONTRAST_OLS_STANDARDISED]
    per_cell = ols.drop_duplicates([config.DATASET_COL, "STRATUM", "SERIES", "VARIABLES"]).groupby(
        [config.DATASET_COL, "STRATUM", "SERIES"]).size()
    expected_cells = len(MATRIX_FILES) * len(config.CONTRAST_STRATA) * len(config.CONTRAST_SERIES)
    checks.append(("every set, stratum and series fits the four models of two and three covariates",
                   len(per_cell) == expected_cells and bool((per_cell == len(subsets())).all()),
                   f"{len(per_cell)} cells"))
    selected = ols[ols.SELECTED].drop_duplicates([config.DATASET_COL, "STRATUM", "SERIES"])
    minimum = ols.groupby([config.DATASET_COL, "STRATUM", "SERIES"]).AIC.min()
    agree = selected.set_index([config.DATASET_COL, "STRATUM", "SERIES"]).AIC.sub(minimum).abs().max()
    checks.append(("the selected model is the one with the smallest AIC", float(agree) < 1e-9, ""))
    counted = models[models.FAMILY != config.CONTRAST_OLS_STANDARDISED].drop_duplicates(
        [config.DATASET_COL, "STRATUM", "SERIES"])
    checks.append(("every selected model has its count-model check", len(counted) == expected_cells,
                   f"{len(counted)} of {expected_cells}"))
    classes = tables[config.CONTRAST_CLASSIFICATION_FILENAME]
    checks.append(("one classification per association, set and stratum",
                   len(classes) == len(config.EUROPEAN_ASSOCIATIONS) * len(MATRIX_FILES) * len(config.CONTRAST_STRATA),
                   f"{len(classes)} rows"))

    width = max(len(name) for name, _, _ in checks)
    lines = [f"{'check'.ljust(width)}  {'result':>8}  detail", f"{'-' * width}  {'-' * 8}  ------"]
    for name, ok, detail in checks:
        lines.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("contrast verification:", "\n".join(lines))
    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("contrast verification FAILED")
    return passed


def report(tables: dict[str, pd.DataFrame], log: RunLog) -> None:
    classes = tables[config.CONTRAST_CLASSIFICATION_FILENAME]
    lines = []
    for row in classes.itertuples():
        lines.append(f"{row.CANDIDATE:<24} {row.SERIES:<22} {getattr(row, config.DATASET_COL):<14} "
                     f"{row.STRATUM:<16} Europe {row.EUROPE_BETA:+.2f}  Bogota {row.BOGOTA_BETA:+.2f} "
                     f"[{row.BOGOTA_CI_LOW:+.2f}, {row.BOGOTA_CI_HIGH:+.2f}] p={row.BOGOTA_P_VALUE:.3f} "
                     f"({row.BOGOTA_MODEL})  -> {row.STATUS}")
    log.table("Phase 4 classification:", "\n".join(lines))
