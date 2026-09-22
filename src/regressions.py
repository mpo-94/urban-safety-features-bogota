"""Cross-sectional regressions at three years, on both casualty datasets.

**A first step and not the methodology.** The anteproyecto declares a count GLM
on the unit-by-year panel, with Hausman deciding between fixed and random
effects, and that is still what the thesis estimates. What this stage produces is
what my advisor and the panel adviser asked for before the panel is built: least
squares and a count GLM at 2015, 2019 and 2023, one regression per oriented pair
of road user types, on the observed and the rho-corrected datasets.

Everything that needs variation within a unit over time belongs to the panel and
is deliberately absent. A cross-section has one row per unit and no such
variation, so there is no unit effect to absorb or to correlate: Hausman, fixed
effects and random effects are not omitted for convenience, they are undefined
here. See D48 and section 8 of `docs/regression-inventory.md`.

What the stage does do, and why each is not an addition to the request:

* **Poisson or negative binomial**, chosen on the estimated dispersion. A count
  GLM is one of the two, and fitting Poisson to overdispersed counts makes the
  standard errors too small, so every interval and every p-value would be wrong
  in the flattering direction.
* **A search over subsets of two and three candidates, selected by AIC.** Fifteen
  candidates cannot be fitted on thirty observations, and once there are 560 fits
  something has to end the search in the one model the figure draws.
* **Moran's I on the residuals**, which changes no coefficient and says whether
  the panel will need a spatial term.

The offset is declared rather than fixed, because my advisor may ask for the same
regressions under a different denominator. A quantity that enters the offset
leaves the candidate predictors, since putting it in both would estimate its
coefficient and fix it at one at the same time.

Run it on its own:

    python -m src.run_pipeline regressions
"""

from __future__ import annotations

import itertools
import shutil
import textwrap
import warnings
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")  # figures are written to disk, never displayed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

try:  # regular package import
    from src import config
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# Columns of the regression tables. The three identifying ones reuse the names and
# the values the matrix and the predictor tables already use, because the dashboard
# joins all of them and a table that cannot be joined is of no use there.
PAIR_NAME_COL = "PAIR"
AFFECTED_COL = "AFFECTED_TYPE"
COUNTERPART_COL = "COUNTERPART_TYPE"
RESPONSE_COL = "AFFECTED_PARTIES"
DATASET_COL = "DATASET"
MODEL_ID_COL = "MODEL_ID"


# The four tables this stage reads, each exported by a route of its own. Read
# from files rather than rebuilt in memory, for the reason `interpolation` gives
# for doing the same: rebuilding them would re-read five surveys and thirteen
# layers to produce tables this stage is not allowed to change, and it would make
# the regressions look like a second measurement of them. What it costs is that
# the run has to say which run each came from, and it does.
MATRIX_FILENAME = "analysis__matrix_long.parquet"
CORRECTED_MATRIX_FILENAME = "analysis__matrix_long__rho_corrected.parquet"
EXPOSURE_FILENAME = "analysis__exposure_by_unit_interpolated.parquet"
POPULATION_FILENAME = "analysis__population_by_unit_year.parquet"
PREDICTORS_FILENAME = "analysis__static_predictors_long.parquet"


def read_inputs(log: RunLog) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """The casualty matrices, the exposure, the population and the predictors.

    The two casualty datasets are returned as a mapping, because every result
    table carries the dataset as a column and the walk below runs them the same
    way. A run with no corrected matrix to read gets the observed one alone and
    says so — the corrected set is a separate route and forcing it here would be
    the wrong coupling — but it is a warning and not a silence, because "both
    datasets, always" is what the plan promises.
    """
    frames: dict[str, pd.DataFrame] = {}
    for dataset, filename in (
        (config.OBSERVED_DATASET, MATRIX_FILENAME),
        (config.CORRECTED_DATASET, CORRECTED_MATRIX_FILENAME),
    ):
        try:
            run_dir = config.run_directory_holding(filename)
        except FileNotFoundError:
            log.warn(
                "no run exports %s, so the %s dataset is not modelled; every result of "
                "this stage is meant to exist for both",
                filename,
                dataset,
            )
            continue
        frames[dataset] = pd.read_parquet(run_dir / config.DATA_SUBDIR / filename)
        log.info("%s casualty matrix read from %s", dataset, run_dir.name)

    if not frames:
        raise FileNotFoundError(
            "no run exports a casualty matrix; the regressions have no response to fit. "
            "Run the `corrected` route first"
        )

    reads = {}
    for name, filename in (
        ("exposure", EXPOSURE_FILENAME),
        ("population", POPULATION_FILENAME),
        ("predictors", PREDICTORS_FILENAME),
    ):
        run_dir = config.run_directory_holding(filename)
        reads[name] = pd.read_parquet(run_dir / config.DATA_SUBDIR / filename)
        log.info("%s read from %s", name, run_dir.name)

    return frames, reads["exposure"], reads["population"], reads["predictors"]


def build_dataset(
    matrix: pd.DataFrame,
    exposure: pd.DataFrame,
    population: pd.DataFrame,
    predictors: pd.DataFrame,
    log: RunLog,
) -> pd.DataFrame:
    """One row per unit, pair and year, with everything a model can read.

    The response, the three quantities an offset can be built from, and every
    candidate predictor. All three offset quantities are carried in their own
    columns whatever the run uses, so a reader can recompute any denominator from
    the table itself and the table does not change shape when an offset is added.

    The predictor block is the same for all eight pairs of a year, because the
    predictors are properties of the unit. So a year needs two inputs and not
    sixteen, and the join that spreads them across the pairs happens once.
    """
    units = sorted(predictors[config.AREA_CODE_COL].unique())
    grid = pd.DataFrame(
        [
            (unit, pair.name, pair.affected, pair.counterpart, year)
            for unit in units
            for pair in config.REGRESSION_PAIRS
            for year in config.REGRESSION_YEARS
        ],
        columns=[config.AREA_CODE_COL, PAIR_NAME_COL, AFFECTED_COL, COUNTERPART_COL, config.YEAR_COL],
    )

    table = grid.merge(
        _response(matrix),
        on=[config.AREA_CODE_COL, AFFECTED_COL, COUNTERPART_COL, config.YEAR_COL],
        how="left",
    )
    # A pair with no casualty in a unit and year is a zero, not a missing value.
    # It is the same rule D10 fixed for the matrix, and the reason the grid above
    # is built before anything is joined to it.
    filled = int(table[RESPONSE_COL].isna().sum())
    table[RESPONSE_COL] = table[RESPONSE_COL].fillna(0).astype("int64")

    exposure_by_actor = _exposure(exposure)
    for column, side in (
        (config.OFFSET_AFFECTED_EXPOSURE, AFFECTED_COL),
        (config.OFFSET_COUNTERPART_EXPOSURE, COUNTERPART_COL),
    ):
        table = table.merge(
            exposure_by_actor.rename(columns={config.ACTOR_TYPE_COL: side, "EXPOSURE": column}),
            on=[config.AREA_CODE_COL, side, config.YEAR_COL],
            how="left",
        )

    table = table.merge(_population(population), on=[config.AREA_CODE_COL, config.YEAR_COL], how="left")
    table = table.merge(_predictors(predictors), on=[config.AREA_CODE_COL, config.YEAR_COL], how="left")

    log.record(
        "assemble the regression dataset",
        rows_in=len(grid),
        rows_out=len(table),
        changes=[],
        notes=[
            f"grid = {len(units)} units x {len(config.REGRESSION_PAIRS)} pairs x "
            f"{len(config.REGRESSION_YEARS)} years",
            f"{filled:,} unit-pair-year cell(s) had no casualty and carry a measured zero",
            f"{len(config.REGRESSION_CANDIDATE_POOL)} candidate columns, of which "
            f"{len(config.OFFSET_QUANTITIES)} can serve as an offset",
        ],
    )
    return table


def _response(matrix: pd.DataFrame) -> pd.DataFrame:
    """The affected parties of each oriented pair, per unit and year.

    The matrix carries three counts in the same row and this reads the first.
    Persons injured and persons killed stay in their own table: a model on deaths
    is a separate question, and D3 settles that this stage estimates parties.
    """
    wanted = matrix[matrix[config.YEAR_COL].isin(config.REGRESSION_YEARS)]
    return (
        wanted[
            [
                config.AREA_CODE_COL,
                config.PARTY_TYPE_COL,
                config.COUNTERPART_TYPE_COL,
                config.YEAR_COL,
                config.AFFECTED_PARTIES_COL,
            ]
        ]
        .rename(
            columns={
                config.PARTY_TYPE_COL: AFFECTED_COL,
                config.COUNTERPART_TYPE_COL: COUNTERPART_COL,
                config.AFFECTED_PARTIES_COL: RESPONSE_COL,
            }
        )
        .reset_index(drop=True)
    )


def _exposure(exposure: pd.DataFrame) -> pd.DataFrame:
    """Travel of each actor type in each unit and year, on the declared basis.

    One kind of day and one column, both declared and neither chosen here. The
    weekday is the only kind measured in all three regression years, and the
    fifteen-minute column is the one the pedestrian series is read on and is
    identical to its neighbour for the other three modes.

    One variant too, and that one is settled by arithmetic rather than declared:
    all three regression years are survey years, so the pandemic patch of D42
    reaches none of them and the two variants hold the same numbers — measured as
    a maximum difference of zero across the 1,080 unit-actor-day rows of the three
    years. The filter is here because without it every row would be joined twice.
    """
    wanted = exposure[
        exposure[config.YEAR_COL].isin(config.REGRESSION_YEARS)
        & (exposure[config.DAY_TYPE_COL] == config.MODEL_EXPOSURE_DAY_TYPE)
        & (exposure[config.EXPOSURE_VARIANT_COL] == config.INTERPOLATED_VARIANT)
    ]
    return (
        wanted[[config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.YEAR_COL, config.MODEL_EXPOSURE_COLUMN]]
        .rename(columns={config.MODEL_EXPOSURE_COLUMN: "EXPOSURE"})
        .reset_index(drop=True)
    )


def _population(population: pd.DataFrame) -> pd.DataFrame:
    """Residents of each unit in each year."""
    wanted = population[population[config.YEAR_COL].isin(config.REGRESSION_YEARS)]
    return (
        wanted[[config.AREA_CODE_COL, config.YEAR_COL, config.POPULATION_COL]]
        .rename(columns={config.POPULATION_COL: config.OFFSET_POPULATION})
        .reset_index(drop=True)
    )


def _predictors(predictors: pd.DataFrame) -> pd.DataFrame:
    """One row per unit and year, one column per candidate predictor.

    A variable without a year is spread across all three; a variable with one is
    taken at that year. Reshaped here rather than by `predictors.wide_table`,
    because that function answers for one year at a time and this needs the three
    stacked so the join below is a single operation.
    """
    wanted = predictors[predictors[config.PREDICTOR_COL].isin(config.REGRESSION_URBAN_CANDIDATES)]
    frames = []
    for year in config.REGRESSION_YEARS:
        has_year = wanted[config.YEAR_COL].notna()
        block = wanted[~has_year | (wanted[config.YEAR_COL] == year)]
        wide = block.pivot(
            index=config.AREA_CODE_COL,
            columns=config.PREDICTOR_COL,
            values=config.PREDICTOR_VALUE_COL,
        ).reindex(columns=list(config.REGRESSION_URBAN_CANDIDATES))
        wide[config.YEAR_COL] = year
        frames.append(wide.reset_index())
    return pd.concat(frames, ignore_index=True)

# ---------------------------------------------------------------------------
# Fitting
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fitted:
    """One fitted model, reduced to what the tables need.

    Held as a plain record rather than as the estimator's own result object,
    because 226,800 of those would be kept alive at once and only four numbers of
    each are ever read during the search.
    """

    predictors: tuple[str, ...]
    aic: float
    bic: float
    loglikelihood: float
    parameters: int
    converged: bool
    # Present only on the model that wins its search, filled in afterwards.
    result: object | None = None


def _standardise(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Centre and scale each column, returning the means and deviations used.

    Not cosmetic and not a modelling choice. The candidates run from area shares
    around 0.001 to signage densities around 600, and on that spread the negative
    binomial's joint estimation of alpha and the coefficients does not converge
    for a good share of the combinations. Standardising fixes the conditioning.

    **The coefficients it produces are per standard deviation**, so the exported
    table carries them back-transformed as well: dividing by the deviation is
    exact for a model linear in its predictor, and gives the coefficient per unit
    of the variable that a reader of chapter 3 will want.
    """
    means = values.mean(axis=0)
    deviations = values.std(axis=0, ddof=0)
    # A column with no spread would divide by zero. It cannot explain anything
    # either, so it is left centred and the fit sees a column of zeros, which the
    # estimator drops or renders insignificant rather than failing on.
    safe = np.where(deviations > 0, deviations, 1.0)
    return (values - means) / safe, means, safe


def _fit_one(
    family: str,
    response: np.ndarray,
    design: np.ndarray,
    log_offset: np.ndarray,
) -> object | None:
    """Fit one specification, or return None if the estimator could not.

    A failure is not an error here. Thirty observations and three correlated
    predictors can produce a singular design or a likelihood that does not
    converge, and the honest response is to leave that combination out of the
    search rather than to stop a run over one of 560.
    """
    with warnings.catch_warnings():
        # Convergence and separation warnings are the expected noise of a search
        # this size. What matters is whether the result converged, which is read
        # from the result itself below, not from whether a warning was raised.
        warnings.simplefilter("ignore")
        try:
            if family == config.OLS_FAMILY:
                # Least squares admits no offset, so the response is the rate: the
                # count over the same product the GLM puts in its offset. The two
                # families then answer the same question on different scales.
                return sm.OLS(response / np.exp(log_offset), design).fit()
            if family == config.POISSON_FAMILY:
                return sm.GLM(
                    response, design, family=sm.families.Poisson(), offset=log_offset
                ).fit()
            if family == config.NEGATIVE_BINOMIAL_FAMILY:
                # The discrete model, not GLM with a fixed alpha. It estimates the
                # dispersion jointly with the coefficients and counts it as a
                # parameter, which is what puts its AIC on the same footing as
                # Poisson's. GLM with alpha supplied reports one parameter fewer
                # and its AIC is two points optimistic for that reason alone.
                return sm.NegativeBinomial(response, design, offset=log_offset).fit(
                    disp=0, maxiter=200
                )
        except (np.linalg.LinAlgError, ValueError, ZeroDivisionError):
            return None
    raise ValueError(f"unknown family {family!r}")


def _converged(result: object) -> bool:
    """Whether the estimator says it converged, for the ones that say.

    Least squares and the GLMs solve in closed form or by a fixed iteration and
    report nothing; the negative binomial maximises a likelihood and reports
    `mle_retvals`. Absence of the field is not failure, so it reads as converged.
    """
    retvals = getattr(result, "mle_retvals", None)
    if not isinstance(retvals, dict):
        return True
    return bool(retvals.get("converged", True))


def _describe(result: object, predictors: tuple[str, ...]) -> Fitted | None:
    """Reduce an estimator's result to the record the search compares.

    **A fit with no usable standard errors is not a fit and does not compete.**
    The negative binomial maximises alpha jointly with the coefficients, and on
    thirty observations it sometimes drives alpha to a boundary: the likelihood
    then stops being bounded, the Hessian is not invertible, and the result comes
    back with coefficients, no standard errors and an AIC that is not comparable
    with anything — one such model reported 28,502 where its neighbours were near
    130, and another −27 where a count model of thirty observations cannot go.

    Left in, those win or lose searches on a number that means nothing, and they
    reach the table as coefficients with no interval and no p-value, which is
    worse than no row at all. This is the check in `verify` that found them, and
    rejecting them here is where it gets fixed.
    """
    try:
        aic, bic, llf = float(result.aic), float(result.bic), float(result.llf)
        errors = np.asarray(result.bse, dtype=float)
    except (AttributeError, ValueError, TypeError):
        return None
    if not np.isfinite(aic) or not np.isfinite(llf):
        return None
    if errors.size == 0 or not np.all(np.isfinite(errors)):
        return None
    if not _converged(result):
        return None
    return Fitted(
        predictors=predictors,
        aic=aic,
        bic=bic,
        loglikelihood=llf,
        parameters=int(len(result.params)),
        converged=True,
        result=result,
    )


def search(
    frame: pd.DataFrame,
    family: str,
    offset: config.OffsetSpec,
    candidates: tuple[str, ...],
) -> tuple[Fitted | None, Fitted | None, int, int]:
    """Walk every declared subset and return the best by AIC, with the null model.

    Returns the selected model, the null model it has to beat, how many
    specifications were fitted and how many the estimator could not fit. The null
    is the intercept and the offset alone: it is the floor a selected model must
    improve on, and a selection that does not beat it is a result worth reporting
    rather than a failure to hide.

    **The search never leaves the declared set.** Every combination of two and
    three candidates, in the order the configuration declares them, and nothing
    else — no stepwise walk, no interaction terms, no transformations. That is
    what makes "the criteria were fixed before estimating" a checkable statement.
    """
    response = frame[RESPONSE_COL].to_numpy(dtype=float)
    log_offset = _log_offset(frame, offset)
    raw = frame[list(candidates)].to_numpy(dtype=float)
    standardised, _, deviations = _standardise(raw)
    position = {name: index for index, name in enumerate(candidates)}

    null_result = _fit_one(family, response, np.ones((len(frame), 1)), log_offset)
    null = _describe(null_result, ()) if null_result is not None else None

    best: Fitted | None = None
    attempted = 0
    failed = 0
    for size in config.REGRESSION_SUBSET_SIZES:
        for combination in itertools.combinations(candidates, size):
            attempted += 1
            design = sm.add_constant(standardised[:, [position[name] for name in combination]])
            result = _fit_one(family, response, design, log_offset)
            described = _describe(result, combination) if result is not None else None
            if described is None:
                failed += 1
                continue
            if best is None or described.aic < best.aic:
                best = described
    return best, null, attempted, failed


def _log_offset(frame: pd.DataFrame, offset: config.OffsetSpec) -> np.ndarray:
    """The logarithm of the product of the offset's quantities.

    A quantity of zero has no logarithm and would make the model undefined, so it
    is caught here with the unit named rather than surfacing as a fit that quietly
    produced nothing. It has not happened: every unit travels and every unit is
    inhabited in all three years.
    """
    product = np.ones(len(frame), dtype=float)
    for quantity in offset.quantities:
        values = frame[quantity].to_numpy(dtype=float)
        if np.any(values <= 0):
            units = frame.loc[values <= 0, config.AREA_CODE_COL].tolist()
            raise ValueError(
                f"offset {offset.name}: {quantity} is zero or negative in "
                f"{', '.join(units)}; a zero denominator has no logarithm and the "
                "model would be undefined there"
            )
        product = product * values
    return np.log(product)

# ---------------------------------------------------------------------------
# Spatial structure of the residuals
# ---------------------------------------------------------------------------


def contiguity_weights(units: gpd.GeoDataFrame) -> tuple[np.ndarray, tuple[str, ...]]:
    """Row-standardised queen contiguity over the units, and their order.

    Two units are neighbours when their boundaries touch at all, a point included.
    Built here rather than taken from a library so the pipeline keeps its one
    geospatial dependency, and because the rule is one line of predicate: thirty
    polygons make this cheap however it is done.

    Row-standardised, so each unit's neighbours carry equal weight summing to one
    and Moran's I stays in its familiar range. A unit with no neighbour would give
    a row of zeros; none of the thirty is isolated, and the check below says so
    rather than trusting it.
    """
    projected = units.to_crs(epsg=config.PROJECTED_CRS)
    codes = tuple(projected[config.AREA_CODE_COL])
    geometries = list(projected.geometry)
    weights = np.zeros((len(codes), len(codes)), dtype=float)
    for i, left in enumerate(geometries):
        for j, right in enumerate(geometries):
            if i != j and left.touches(right):
                weights[i, j] = 1.0

    isolated = [codes[i] for i in range(len(codes)) if weights[i].sum() == 0]
    if isolated:
        raise ValueError(
            f"units with no neighbour: {', '.join(isolated)}. Moran's I is undefined "
            "for an isolated unit, and the thirty are known to be contiguous, so this "
            "means the layer changed rather than that the city did"
        )
    return weights / weights.sum(axis=1, keepdims=True), codes


def morans_i(values: np.ndarray, weights: np.ndarray) -> float:
    """Moran's I of a vector over a row-standardised weights matrix.

    Positive means neighbouring units carry similar residuals, which is the
    finding that matters here: it says the model has left spatial structure
    behind, and therefore that the panel this step precedes will need a term for
    it. Near zero means the residuals are scattered.
    """
    centred = values - values.mean()
    denominator = float(np.sum(centred**2))
    if denominator == 0:
        return float("nan")
    numerator = float(centred @ weights @ centred)
    # The weights are row-standardised, so their total is the number of units and
    # the usual n/S0 factor is one. Written out anyway: a later change to the
    # weighting would otherwise silently drop a factor.
    scale = len(values) / float(weights.sum())
    return scale * numerator / denominator


# ---------------------------------------------------------------------------
# One cell: a dataset, an offset, a pair, a year and a family
# ---------------------------------------------------------------------------


def _significance(p_value: float) -> str:
    """The usual stars, so a table can be read without reading every number."""
    if not np.isfinite(p_value):
        return ""
    for threshold, mark in ((0.001, "***"), (0.01, "**"), (config.REGRESSION_SIGNIFICANCE, "*")):
        if p_value < threshold:
            return mark
    return ""


def _collinear_pairs(frame: pd.DataFrame, predictors: tuple[str, ...]) -> list[tuple[str, str, float]]:
    """The pairs inside one model that exceed the declared correlation threshold.

    Reported and never prevented. Two correlated variables in one model of thirty
    observations do not give two readable coefficients; they give one effect split
    arbitrarily between them. The run does not drop the model for it — the
    instruction is that every candidate competes — it marks it, so a coefficient
    that comes from such a model is read differently.
    """
    found = []
    for left, right in itertools.combinations(predictors, 2):
        correlation = float(frame[left].corr(frame[right]))
        if np.isfinite(correlation) and abs(correlation) >= config.CORRELATION_HIGH_THRESHOLD:
            found.append((left, right, correlation))
    return found


def fit_cell(
    frame: pd.DataFrame,
    dataset: str,
    offset: config.OffsetSpec,
    pair: config.ActorPair,
    year: int,
    family: str,
    weights: np.ndarray,
    log: RunLog,
) -> tuple[dict, list[dict], list[dict]] | None:
    """Everything one regression contributes: its model row, coefficients, predictions."""
    candidates = offset.candidate_predictors(config.REGRESSION_CANDIDATE_POOL)
    best, null, attempted, failed = search(frame, family, offset, candidates)
    if best is None:
        log.warn(
            "%s / %s / %s / %d / %s: no specification could be fitted out of %d",
            dataset, offset.name, pair.name, year, family, attempted,
        )
        return None

    result = best.result
    response = frame[RESPONSE_COL].to_numpy(dtype=float)
    log_offset = _log_offset(frame, offset)
    raw = frame[list(best.predictors)].to_numpy(dtype=float)
    deviations = raw.std(axis=0, ddof=0)

    # Least squares models the rate, so its fitted values are a rate and are
    # multiplied back to counts. The GLMs model the count directly. Putting both
    # on the count scale is what lets one figure hold the eight panels of a year
    # whatever family drew them.
    # `predict` and never `fittedvalues`, and the difference is not cosmetic. A
    # GLM's `fittedvalues` is the mean, with the inverse link already applied; the
    # discrete negative binomial's is the **linear predictor**, so reading it gives
    # numbers around −7 where the counts run from 3 to 101. `predict` returns the
    # conditional mean for both, which is what a figure of observed against
    # predicted is asking for. The check below refuses a negative count for this
    # exact reason: a figure caught it once and a check should catch it next time.
    if family == config.OLS_FAMILY:
        predicted = np.asarray(result.predict(), dtype=float) * np.exp(log_offset)
    else:
        predicted = np.asarray(result.predict(), dtype=float)
    residuals = response - predicted

    dispersion = float("nan")
    if family == config.POISSON_FAMILY:
        dispersion = float(result.pearson_chi2 / result.df_resid)

    collinear = _collinear_pairs(frame, best.predictors)
    model_id = f"{dataset}|{offset.name}|{pair.name}|{year}|{family}"

    model_row = {
        DATASET_COL: dataset,
        config.OFFSET_COL: offset.name,
        PAIR_NAME_COL: pair.name,
        config.YEAR_COL: year,
        config.FAMILY_COL: family,
        MODEL_ID_COL: model_id,
        "PREDICTORS": ", ".join(best.predictors),
        "N_PREDICTORS": len(best.predictors),
        "N_OBSERVATIONS": len(frame),
        "AIC": best.aic,
        "BIC": best.bic,
        "LOG_LIKELIHOOD": best.loglikelihood,
        "NULL_AIC": null.aic if null else float("nan"),
        "BEATS_NULL": bool(null is not None and best.aic < null.aic),
        "DISPERSION": dispersion,
        "MORANS_I": morans_i(residuals, weights),
        "COLLINEAR": bool(collinear),
        "COLLINEAR_PAIRS": "; ".join(
            f"{left}~{right}={value:.3f}" for left, right, value in collinear
        ),
        "SPECIFICATIONS_FITTED": attempted - failed,
        "SPECIFICATIONS_DECLARED": attempted,
        "CONVERGED": best.converged,
    }

    intervals = np.asarray(result.conf_int(alpha=1 - config.REGRESSION_CONFIDENCE), dtype=float)
    names = ["INTERCEPT", *best.predictors]
    coefficient_rows = []
    for position, name in enumerate(names):
        if position >= len(result.params):
            break
        # Back to the variable's own units. The fit is on standardised columns for
        # conditioning, and dividing by the deviation is exact for a model linear
        # in its predictor. Both are exported: the standardised one compares two
        # variables to each other, the raw one says what a kilometre buys.
        deviation = deviations[position - 1] if position > 0 else float("nan")
        estimate = float(result.params[position])
        coefficient_rows.append(
            {
                DATASET_COL: dataset,
                config.OFFSET_COL: offset.name,
                PAIR_NAME_COL: pair.name,
                config.YEAR_COL: year,
                config.FAMILY_COL: family,
                MODEL_ID_COL: model_id,
                "TERM": name,
                "COEFFICIENT_STANDARDISED": estimate,
                "COEFFICIENT": estimate / deviation if position > 0 and deviation > 0 else estimate,
                "STANDARD_ERROR": float(result.bse[position]),
                "P_VALUE": float(result.pvalues[position]),
                "CI_LOW": float(intervals[position, 0]),
                "CI_HIGH": float(intervals[position, 1]),
                "SIGNIFICANT": bool(float(result.pvalues[position]) < config.REGRESSION_SIGNIFICANCE),
                "STARS": _significance(float(result.pvalues[position])),
            }
        )

    prediction_rows = [
        {
            DATASET_COL: dataset,
            config.OFFSET_COL: offset.name,
            PAIR_NAME_COL: pair.name,
            config.YEAR_COL: year,
            config.FAMILY_COL: family,
            MODEL_ID_COL: model_id,
            config.AREA_CODE_COL: code,
            "OBSERVED": float(observed),
            "PREDICTED": float(fitted),
            "RESIDUAL": float(observed - fitted),
        }
        for code, observed, fitted in zip(frame[config.AREA_CODE_COL], response, predicted)
    ]
    return model_row, coefficient_rows, prediction_rows

# ---------------------------------------------------------------------------
# The whole walk
# ---------------------------------------------------------------------------


def eligible_pairs(table: pd.DataFrame, log: RunLog) -> tuple[config.ActorPair, ...]:
    """The pairs whose response carries enough signal to regress on thirty units.

    The threshold is the anteproyecto's and was fixed before anything was
    estimated: fewer than half the cells at zero. A pair that fails in any of the
    three years is dropped from all of them, because a coefficient that exists in
    2019 and not in 2015 cannot be put in the three-year comparison the figures
    are built around.

    It drops nothing today — the worst case is five zero units of thirty — and it
    is here so that it would, and so the run states the measurement rather than
    leaving the threshold as a sentence in a document.
    """
    lines = [f"{'pair':<26} " + " ".join(f"{year:>6}" for year in config.REGRESSION_YEARS) + "   verdict"]
    lines.append("-" * len(lines[0]))
    kept = []
    for pair in config.REGRESSION_PAIRS:
        block = table[table[PAIR_NAME_COL] == pair.name]
        shares = []
        for year in config.REGRESSION_YEARS:
            cells = block[block[config.YEAR_COL] == year]
            shares.append(float((cells[RESPONSE_COL] == 0).mean()) if len(cells) else 1.0)
        passes = max(shares) < config.REGRESSION_MAX_ZERO_SHARE
        if passes:
            kept.append(pair)
        lines.append(
            f"{pair.name:<26} " + " ".join(f"{share:>6.2f}" for share in shares)
            + ("   kept" if passes else "   DROPPED: over the threshold")
        )
    log.table(
        f"share of the thirty cells at zero, against the declared maximum of "
        f"{config.REGRESSION_MAX_ZERO_SHARE:.2f}:",
        "\n".join(lines),
    )
    if len(kept) < len(config.REGRESSION_PAIRS):
        log.warn(
            "%d of %d pairs are below the zero-cell threshold and are not modelled",
            len(config.REGRESSION_PAIRS) - len(kept),
            len(config.REGRESSION_PAIRS),
        )
    return tuple(kept)


def fit_all(
    datasets: dict[str, pd.DataFrame],
    units: gpd.GeoDataFrame,
    log: RunLog,
) -> dict[str, pd.DataFrame]:
    """Every cell of every dataset, offset, pair, year and family.

    One run and not one per offset, because the whole point of declaring three is
    to compare them and three runs would put them in three directories.
    """
    weights, codes = contiguity_weights(units)
    order = {code: position for position, code in enumerate(codes)}

    models: list[dict] = []
    coefficients: list[dict] = []
    predictions: list[dict] = []
    cells = 0

    for dataset, table in datasets.items():
        pairs = eligible_pairs(table, log)
        for offset in config.REGRESSION_OFFSETS:
            for pair in pairs:
                for year in config.REGRESSION_YEARS:
                    frame = table[
                        (table[PAIR_NAME_COL] == pair.name) & (table[config.YEAR_COL] == year)
                    ]
                    # Ordered as the weights matrix is, or Moran's I would be
                    # computed against the wrong neighbours — a defect that
                    # produces a plausible number and no error.
                    frame = frame.sort_values(
                        config.AREA_CODE_COL, key=lambda s: s.map(order), kind="stable"
                    )
                    for family in (
                        config.OLS_FAMILY,
                        config.POISSON_FAMILY,
                        config.NEGATIVE_BINOMIAL_FAMILY,
                    ):
                        cells += 1
                        fitted = fit_cell(
                            frame, dataset, offset, pair, year, family, weights, log
                        )
                        if fitted is None:
                            continue
                        model_row, coefficient_rows, prediction_rows = fitted
                        models.append(model_row)
                        coefficients.extend(coefficient_rows)
                        predictions.extend(prediction_rows)

    tables = {
        "models": pd.DataFrame(models),
        "coefficients": pd.DataFrame(coefficients),
        "predictions": pd.DataFrame(predictions),
    }
    log.record(
        "fit every declared specification",
        rows_in=cells,
        rows_out=len(tables["models"]),
        changes=[(len(tables["models"]) - cells, "cells where no specification could be fitted")],
        notes=[
            f"{cells:,} cells = {len(datasets)} dataset(s) x {len(config.REGRESSION_OFFSETS)} "
            f"offset(s) x pairs x {len(config.REGRESSION_YEARS)} years x 3 families",
            f"{int(tables['models']['SPECIFICATIONS_DECLARED'].sum()):,} specifications declared, "
            f"{int(tables['models']['SPECIFICATIONS_FITTED'].sum()):,} fitted",
            f"{int(tables['models']['BEATS_NULL'].sum()):,} of {len(tables['models']):,} selected "
            "models beat their own null",
        ],
    )
    return tables


def selection_frequency(coefficients: pd.DataFrame) -> pd.DataFrame:
    """How often each variable was selected, and how often with a sign.

    The most defensible thing this stage produces, and the reason the search is
    worth running at all. A variable that wins in independent contexts — different
    pairs, years, datasets, offsets and families — is evidence. A field where the
    winner changes every time is noise, and the chapter has to say which of the
    two it is looking at.
    """
    terms = coefficients[coefficients["TERM"] != "INTERCEPT"]
    grouped = terms.groupby("TERM")
    table = pd.DataFrame(
        {
            "SELECTED": grouped.size(),
            "SIGNIFICANT": grouped["SIGNIFICANT"].sum(),
            "POSITIVE": grouped["COEFFICIENT"].apply(lambda s: int((s > 0).sum())),
            "NEGATIVE": grouped["COEFFICIENT"].apply(lambda s: int((s < 0).sum())),
        }
    )
    table["MODELS"] = len(terms[MODEL_ID_COL].unique())
    table["SELECTED_SHARE"] = table["SELECTED"] / table["MODELS"]
    return table.sort_values("SELECTED", ascending=False).reset_index()

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export(
    data: dict[str, pd.DataFrame],
    tables: dict[str, pd.DataFrame],
    log: RunLog,
) -> dict[str, Path]:
    """The four tables, per dataset, plus the selection frequency over all of them.

    The data table is written once per casualty dataset because its response
    differs between them; the three result tables carry the dataset as a column,
    because a model of one and a model of the other are rows of the same
    comparison and separating them would make that comparison a manual join.
    """
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    for dataset, frame in data.items():
        suffix = "" if dataset == config.OBSERVED_DATASET else f"__{dataset}"
        path = data_dir / f"{config.ANALYSIS_PREFIX}__regression_data{suffix}.csv"
        frame.to_csv(path, index=False, encoding="utf-8")
        frame.to_parquet(path.with_suffix(".parquet"))
        paths[f"data__{dataset}"] = path

    for name in ("models", "coefficients", "predictions"):
        path = data_dir / f"{config.ANALYSIS_PREFIX}__regression_{name}.csv"
        tables[name].to_csv(path, index=False, encoding="utf-8")
        tables[name].to_parquet(path.with_suffix(".parquet"))
        paths[name] = path

    frequency = selection_frequency(tables["coefficients"])
    path = data_dir / f"{config.PRESENTATION_PREFIX}__regression_selection_frequency.csv"
    frequency.to_csv(path, index=False, encoding="utf-8")
    paths["selection_frequency"] = path

    log.info(
        "exported %d analysis tables and 1 presentation table to %s/",
        len(paths) - 1,
        config.DATA_SUBDIR,
    )
    return paths


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(
    data: dict[str, pd.DataFrame],
    tables: dict[str, pd.DataFrame],
    units: gpd.GeoDataFrame,
    log: RunLog,
) -> bool:
    """Check the tables against the grid they claim to be, and against arithmetic."""
    checks: list[tuple[str, bool, str]] = []
    models = tables["models"]
    coefficients = tables["coefficients"]
    predictions = tables["predictions"]

    for dataset, frame in data.items():
        expected = len(units) * len(config.REGRESSION_PAIRS) * len(config.REGRESSION_YEARS)
        checks.append(
            (
                f"the {dataset} data grid is complete",
                len(frame) == expected,
                f"{len(frame):,} of {expected:,}",
            )
        )
        nulls = int(frame[list(config.REGRESSION_CANDIDATE_POOL)].isna().sum().sum())
        checks.append(
            (
                f"no candidate is null in {dataset}",
                nulls == 0,
                f"{nulls} null cell(s); a measured zero is a fact and a null is a "
                "measurement that did not happen",
            )
        )
        positive = int((frame[list(config.OFFSET_QUANTITIES)] <= 0).sum().sum())
        checks.append(
            (
                f"every offset quantity in {dataset} is positive",
                positive == 0,
                f"{positive} non-positive value(s); a zero denominator has no logarithm",
            )
        )

    # Every model reports n = 30, which is the whole design: one row per unit.
    wrong_n = models[models["N_OBSERVATIONS"] != len(units)]
    checks.append(
        (
            "every model was fitted on exactly the thirty units",
            len(wrong_n) == 0,
            f"{len(models) - len(wrong_n)} of {len(models)}",
        )
    )

    # The declared set was walked whole and not exceeded. The two counts differ
    # only by specifications the estimator could not fit, which are reported.
    declared = int(models["SPECIFICATIONS_DECLARED"].sum())
    fitted = int(models["SPECIFICATIONS_FITTED"].sum())
    expected_declared = 0
    for offset in config.REGRESSION_OFFSETS:
        candidates = offset.candidate_predictors(config.REGRESSION_CANDIDATE_POOL)
        per_cell = sum(
            len(list(itertools.combinations(candidates, size)))
            for size in config.REGRESSION_SUBSET_SIZES
        )
        cells = len(models[models[config.OFFSET_COL] == offset.name])
        expected_declared += per_cell * cells
    checks.append(
        (
            "the declared set was walked whole and not exceeded",
            declared == expected_declared,
            f"{declared:,} declared against {expected_declared:,} expected; {fitted:,} fitted, "
            f"{declared - fitted:,} the estimator could not fit",
        )
    )

    # Predictions reconcile with the data they came from: the observed column of a
    # model has to be the response of its own cell, summed the same way.
    joined = predictions.merge(
        models[[MODEL_ID_COL, DATASET_COL, PAIR_NAME_COL, config.YEAR_COL]],
        on=[MODEL_ID_COL, DATASET_COL, PAIR_NAME_COL, config.YEAR_COL],
        how="left",
    )
    keys = [DATASET_COL, PAIR_NAME_COL, config.YEAR_COL]
    observed_totals = joined.groupby(keys)["OBSERVED"].sum()
    source_totals = pd.concat(
        [frame.assign(**{DATASET_COL: dataset}) for dataset, frame in data.items()],
        ignore_index=True,
    ).groupby(keys)[RESPONSE_COL].sum()
    # Counted rather than assumed. A cell where the estimator could fit nothing
    # contributes no model and no prediction, which is reported elsewhere and is
    # not a reason for this check to fail: what it asks is whether the predictions
    # that exist carry their own cell's response, not how many there are.
    models_per_cell = models.groupby(keys).size()
    expected = source_totals.reindex(observed_totals.index).to_numpy(dtype=float) * (
        models_per_cell.reindex(observed_totals.index).to_numpy(dtype=float)
    )
    reconciles = bool(np.allclose(observed_totals.to_numpy(dtype=float), expected, rtol=1e-9))
    complete = int((models_per_cell == len(config.REGRESSION_OFFSETS) * 3).sum())
    checks.append(
        (
            "the predictions carry the response of their own cell",
            reconciles,
            f"{len(observed_totals)} cell(s); {complete} of them carry all "
            f"{len(config.REGRESSION_OFFSETS) * 3} models",
        )
    )

    # A coefficient row per term of every model, intercept included.
    expected_terms = int(models["N_PREDICTORS"].sum()) + len(models)
    checks.append(
        (
            "one coefficient row per term of every model",
            len(coefficients) == expected_terms,
            f"{len(coefficients):,} of {expected_terms:,}",
        )
    )

    # An interval that does not contain its own estimate would mean the two came
    # from different places.
    inside = (
        (coefficients["CI_LOW"] <= coefficients["COEFFICIENT_STANDARDISED"])
        & (coefficients["COEFFICIENT_STANDARDISED"] <= coefficients["CI_HIGH"])
    )
    checks.append(
        (
            "every interval contains its own estimate",
            bool(inside.all()),
            f"{int(inside.sum()):,} of {len(coefficients):,}",
        )
    )

    within = coefficients["P_VALUE"].between(0, 1) | coefficients["P_VALUE"].isna()
    checks.append(
        ("every p-value lies in [0, 1]", bool(within.all()), f"{int(within.sum()):,} of {len(coefficients):,}")
    )

    # A count model cannot predict a negative count, and one that appears to is
    # not a bad fit but a wrong reading: the discrete estimators return the linear
    # predictor where the GLMs return the mean. This check exists because that
    # happened, and the figure found it before any check did.
    counts = predictions[predictions[config.FAMILY_COL] != config.OLS_FAMILY]
    negative = counts[counts["PREDICTED"] < 0]
    checks.append(
        (
            "no count model predicts a negative count",
            len(negative) == 0,
            f"{len(counts) - len(negative):,} of {len(counts):,}"
            + (
                f"; lowest {float(negative['PREDICTED'].min()):.3f} in "
                f"{negative[config.FAMILY_COL].iloc[0]}"
                if len(negative)
                else ""
            ),
        )
    )

    # Least squares models a rate and can predict a negative one, which is a
    # property of the family and not a defect. Reported so the chapter can say how
    # often, because a fitted rate below zero is a sign the linear model is being
    # asked to do something a count model does better.
    rates = predictions[predictions[config.FAMILY_COL] == config.OLS_FAMILY]
    below = int((rates["PREDICTED"] < 0).sum())
    if below:
        log.info(
            "%d of %d least squares predictions fall below zero, which a linear model "
            "on a rate can do and a count model cannot; it is one of the reasons the "
            "GLM is the family the study reports",
            below,
            len(rates),
        )

    finite_moran = models["MORANS_I"].abs() <= 2
    checks.append(
        (
            "Moran's I lies in a possible range",
            bool(finite_moran.fillna(True).all()),
            f"observed {models['MORANS_I'].min():.3f} to {models['MORANS_I'].max():.3f}",
        )
    )

    width = max(len(name) for name, _, _ in checks)
    lines = [f"{'check'.ljust(width)}  {'result':>8}  detail", f"{'-' * width}  {'-' * 8}  ------"]
    for name, ok, detail in checks:
        lines.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("regression verification:", "\n".join(lines))
    return all(ok for _, ok, _ in checks)

# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
# For my advisor and for me, not for a deliverable. They are labelled in Spanish
# like everything a person on this project reads, and each names its family and
# its offset in the file name: two figures about to sit side by side must not be
# told apart by which one lacks a suffix.


def _panel_grid(title: str) -> tuple[plt.Figure, np.ndarray]:
    """Two rows of four, which is how the eight pairs are read.

    Vulnerable victims above and motorised below, in the order the configuration
    declares them. My advisor asked for this shape, and it is also the only one
    that fits eight panels on a page without any of them going illegible.
    """
    figure, axes = plt.subplots(2, 4, figsize=(16, 8))
    figure.suptitle(title, fontsize=13)
    return figure, axes.reshape(-1)


def _fit_panel(
    predictions: pd.DataFrame,
    models: pd.DataFrame,
    dataset: str,
    offset: str,
    family: str,
    year: int,
    out_path: Path,
) -> None:
    """Observed against predicted, one panel per pair.

    **Each panel carries its own scale and the caption says so.** In 2015
    pedestrian-motorcycle had 1,365 affected parties and car-motorcycle 80, so a
    shared scale would crush half the panels into the origin.

    The reference is the 45-degree line and never a line fitted to the cloud: the
    question is how far the model is from the observation, and a fitted line would
    answer a different one while looking like this one.
    """
    figure, axes = _panel_grid(
        f"Observado contra predicho · {year} · {config.FAMILY_LABELS_ES[family]}\n"
        f"offset: {config.OFFSET_LABELS_ES[offset]} · conjunto: {config.DATASET_LABELS_ES[dataset]}"
        " · cada panel con su propia escala"
    )
    for axis, pair in zip(axes, config.REGRESSION_PAIRS):
        rows = predictions[
            (predictions[DATASET_COL] == dataset)
            & (predictions[config.OFFSET_COL] == offset)
            & (predictions[config.FAMILY_COL] == family)
            & (predictions[config.YEAR_COL] == year)
            & (predictions[PAIR_NAME_COL] == pair.name)
        ]
        axis.set_title(pair.label_es, fontsize=10)
        if rows.empty:
            axis.text(0.5, 0.5, "sin modelo", ha="center", va="center", transform=axis.transAxes)
            axis.set_xticks([])
            axis.set_yticks([])
            continue
        observed = rows["OBSERVED"].to_numpy(dtype=float)
        predicted = rows["PREDICTED"].to_numpy(dtype=float)
        top = max(observed.max(), predicted.max(), 1.0) * 1.05
        axis.plot([0, top], [0, top], color="#888888", linewidth=1, zorder=1)
        axis.scatter(observed, predicted, s=26, color=config.REGRESSION_POINT_COLOR, zorder=2)
        axis.set_xlim(0, top)
        axis.set_ylim(min(0, predicted.min() * 1.05), top)
        axis.set_xlabel("observado")
        axis.set_ylabel("predicho")

        row = models[
            (models[DATASET_COL] == dataset)
            & (models[config.OFFSET_COL] == offset)
            & (models[config.FAMILY_COL] == family)
            & (models[config.YEAR_COL] == year)
            & (models[PAIR_NAME_COL] == pair.name)
        ]
        if len(row):
            axis.text(
                0.03, 0.97, f"AIC {float(row['AIC'].iloc[0]):.0f}",
                transform=axis.transAxes, va="top", fontsize=8, color="#555555",
            )
    figure.tight_layout()
    figure.savefig(out_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(figure)


def _coefficient_panel(
    coefficients: pd.DataFrame,
    dataset: str,
    family: str,
    year: int,
    out_path: Path,
) -> None:
    """The selected coefficients of all three offsets, one panel per pair.

    **The three offsets are one figure and not three.** They differ only in the
    denominator, so putting them on the same axis shows directly how far a
    coefficient moves when the denominator changes — which is the question the
    three offsets exist to answer, and which three separate files could only be
    answered by holding them side by side.

    Standardised coefficients, because a panel puts variables of wildly different
    units together and only the standardised ones can be compared by eye. The
    exported table carries both scales.

    The vertical at zero is drawn so an interval that crosses it is visible
    without reading a number.
    """
    figure, axes = _panel_grid(
        f"Coeficientes estandarizados · {year} · {config.FAMILY_LABELS_ES[family]}\n"
        f"conjunto: {config.DATASET_LABELS_ES[dataset]} · un color por offset"
        " · intervalo del 95 %"
    )
    offsets = list(config.REGRESSION_OFFSETS)
    colours = config.OFFSET_COLORS

    for axis, pair in zip(axes, config.REGRESSION_PAIRS):
        axis.set_title(pair.label_es, fontsize=10)
        axis.axvline(0, color="#888888", linewidth=1, zorder=1)

        labels: list[str] = []
        position = 0.0
        drew = False
        for offset in offsets:
            rows = coefficients[
                (coefficients[DATASET_COL] == dataset)
                & (coefficients[config.OFFSET_COL] == offset.name)
                & (coefficients[config.FAMILY_COL] == family)
                & (coefficients[config.YEAR_COL] == year)
                & (coefficients[PAIR_NAME_COL] == pair.name)
                & (coefficients["TERM"] != "INTERCEPT")
            ]
            for _, row in rows.iterrows():
                axis.hlines(
                    position, row["CI_LOW"], row["CI_HIGH"],
                    color=colours[offset.name], linewidth=2, zorder=2,
                )
                axis.scatter(
                    row["COEFFICIENT_STANDARDISED"], position,
                    s=28, color=colours[offset.name], zorder=3,
                )
                labels.append(config.predictor_label_es(row["TERM"]))
                position += 1
                drew = True
            # A blank line between offsets, so three blocks read as three and not
            # as one list of nine.
            if len(rows):
                position += 0.6
                labels.append("")

        if not drew:
            axis.text(0.5, 0.5, "sin modelo", ha="center", va="center", transform=axis.transAxes)
            axis.set_xticks([])
            axis.set_yticks([])
            continue
        axis.set_yticks(range(len(labels)), labels, fontsize=7)
        axis.set_ylim(len(labels) - 0.4, -0.6)

    handles = [
        plt.Line2D([], [], color=colours[offset.name], linewidth=3,
                   label=config.OFFSET_LABELS_ES[offset.name])
        for offset in offsets
    ]
    figure.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=9)
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    figure.savefig(out_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(figure)


# -- tables drawn as a grid, never with matplotlib's own table ---------------
# `axis.table` sizes its columns by their count and not by what is in them, so a
# heading longer than its share is drawn over its neighbour and a long cell spills
# across the one beside it. Both happened, and the whole of PREDICTORS was
# unreadable. These draw on an image grid instead, the way the predictor master
# table does: the text sits at a cell centre, the grid fills the axes, and nothing
# can overflow because nothing is laid out by matplotlib.


def _grid_table(
    text: list[list[str]],
    columns: list[str],
    rows: list[str],
    title: str,
    note: str,
    out_path: Path,
    shading: np.ndarray | None = None,
    colormap: str = config.MASTER_TABLE_COLORMAP,
    centre_on_zero: bool = False,
    column_width: float = 1.4,
    column_fontsize: float = 8,
    column_groups: list[tuple[str, int, int]] | None = None,
    title_pad: float = 26,
    wrap: int | None = None,
) -> None:
    """A table of text on a grid, optionally shaded, filling its own canvas."""
    row_count, column_count = len(rows), len(columns)
    # A cell longer than its column would be drawn over its neighbour, which is
    # what `matplotlib.table` did and what this exists to avoid. Wrapping is done
    # here rather than by shrinking the font, because a list of three variable
    # names in six-point type is not readable either. The rows grow to fit.
    if wrap:
        text = [[textwrap.fill(cell, wrap) for cell in row] for row in text]
    tallest = max(
        (cell.count(chr(10)) + 1 for row in text for cell in row),
        default=1,
    )
    figure, axis = plt.subplots(
        figsize=(
            max(4.0, 1.9 + column_width * column_count),
            max(2.0, 1.5 + 0.26 * row_count * tallest),
        )
    )

    if shading is None:
        painted = np.zeros((row_count, column_count))
        cmap = matplotlib.colors.ListedColormap(["white"])
        low, high = 0.0, 1.0
    else:
        painted = shading
        cmap = plt.get_cmap(colormap).copy()
        cmap.set_bad(config.HEATMAP_EMPTY_COLOR)
        finite = painted[np.isfinite(painted)]
        span = float(np.abs(finite).max()) if len(finite) else 1.0
        low, high = (-span, span) if centre_on_zero else (0.0, 1.0)

    axis.imshow(np.ma.masked_invalid(painted), cmap=cmap, vmin=low, vmax=high, aspect="auto")

    for row, column in itertools.product(range(row_count), range(column_count)):
        value = painted[row, column]
        dark = np.isfinite(value) and shading is not None and abs(value - (low + high) / 2) > (
            (high - low) * 0.32
        )
        axis.text(
            column, row, text[row][column], ha="center", va="center",
            fontsize=7, color="white" if dark else "#222222",
        )

    axis.set_xticks(range(column_count), columns, fontsize=column_fontsize)
    axis.xaxis.set_ticks_position("top")
    if column_groups:
        # The group name once above its own columns, instead of repeated in every
        # one of them and cut off by the column width. This is what the pair and
        # year heading needed: eight names rather than twenty-four.
        for label, start, stop in column_groups:
            axis.annotate(
                label,
                xy=((start + stop) / 2, -1.55),
                xycoords="data",
                ha="center",
                va="bottom",
                fontsize=8.5,
                annotation_clip=False,
            )
            axis.annotate(
                "", xy=(start - 0.45, -1.2), xytext=(stop + 0.45, -1.2), xycoords="data",
                arrowprops={"arrowstyle": "-", "color": "#bbbbbb", "linewidth": 0.8},
                annotation_clip=False,
            )
    axis.set_yticks(range(row_count), rows, fontsize=7.5)
    axis.set_xticks(np.arange(-0.5, column_count, 1), minor=True)
    axis.set_yticks(np.arange(-0.5, row_count, 1), minor=True)
    axis.grid(which="minor", color="#cccccc", linewidth=0.8)
    axis.tick_params(which="minor", length=0)
    for spine in axis.spines.values():
        spine.set_visible(False)

    axis.set_title(title, fontsize=11, pad=title_pad)
    if note:
        # Placed in data coordinates, just under the last row. An earlier version
        # put it at a fraction far below the axes and `bbox_inches="tight"`
        # stretched the canvas down to reach it, which is where half an image of
        # white space came from.
        axis.annotate(
            note,
            xy=(-0.5, row_count - 0.2),
            xycoords="data",
            va="top",
            fontsize=7,
            color="#555555",
            annotation_clip=False,
        )
    figure.savefig(out_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(figure)


def _beta_heatmap(
    coefficients: pd.DataFrame,
    dataset: str,
    offset: str,
    family: str,
    out_path: Path,
) -> None:
    """Every beta of a whole block, as one picture.

    **This is the figure that answers what the regressions found.** One row per
    candidate variable, one column per pair and year, and in each cell the
    standardised coefficient of that variable in that model — blank where the
    variable was not selected, which is itself the finding for a variable whose
    row is nearly empty.

    Diverging colour centred on zero, so sign reads before magnitude: a row that
    is blue all the way across is a variable that keeps the same sign in every
    context it survives into, and that is worth more than any one p-value in a
    search this size.

    Standardised, because the rows are variables measured in shares, densities and
    kilometres and no other scale lets them share a ramp.
    """
    block = coefficients[
        (coefficients[DATASET_COL] == dataset)
        & (coefficients[config.OFFSET_COL] == offset)
        & (coefficients[config.FAMILY_COL] == family)
        & (coefficients["TERM"] != "INTERCEPT")
    ]
    variables = [
        name
        for name in config.REGRESSION_CANDIDATE_POOL
        if name in set(block["TERM"])
    ]
    cells = [
        (pair, year) for pair in config.REGRESSION_PAIRS for year in config.REGRESSION_YEARS
    ]
    if not variables:
        return

    shading = np.full((len(variables), len(cells)), np.nan)
    text = [["" for _ in cells] for _ in variables]
    lookup = block.set_index([PAIR_NAME_COL, config.YEAR_COL, "TERM"])
    for row, name in enumerate(variables):
        for column, (pair, year) in enumerate(cells):
            try:
                entry = lookup.loc[(pair.name, year, name)]
            except KeyError:
                continue
            estimate = float(entry["COEFFICIENT_STANDARDISED"])
            shading[row, column] = estimate
            text[row][column] = f"{estimate:.2f}{entry['STARS']}"

    _grid_table(
        text=text,
        columns=[str(year) for _, year in cells],
        # The pair named once above its own three years instead of repeated
        # in each and cut off by the column width: eight names, not twenty-four.
        column_groups=[
            (pair.label_es, index * len(config.REGRESSION_YEARS),
             index * len(config.REGRESSION_YEARS) + len(config.REGRESSION_YEARS) - 1)
            for index, pair in enumerate(config.REGRESSION_PAIRS)
        ],
        title_pad=42,
        rows=[config.predictor_label_es(name) for name in variables],
        title=(
            f"Coeficientes estandarizados por pareja y año · {config.FAMILY_LABELS_ES[family]}\n"
            f"offset: {config.OFFSET_LABELS_ES[offset]} · conjunto: "
            f"{config.DATASET_LABELS_ES[dataset]}"
        ),
        note=(
            "Celda vacía: la variable no fue seleccionada en ese modelo. Color divergente "
            "centrado en cero, así que el signo se lee antes que la magnitud.\n"
            "* p<0,05  ** p<0,01  *** p<0,001 — inflados por la selección: son el ganador "
            "de una búsqueda sobre todos los subconjuntos declarados."
        ),
        out_path=out_path,
        shading=shading,
        colormap=config.DIVERGING_COLORMAP,
        centre_on_zero=True,
        column_width=0.72,
    )


def _models_table(models: pd.DataFrame, dataset: str, offset: str, family: str, out_path: Path) -> None:
    """The selected model of every pair and year, with what it is worth.

    One block at a time — a dataset, an offset and a family — because all of them
    at once was a hundred and forty-four rows that nobody could read, and the
    columns that identify the block are then the title instead of four repeated
    columns.
    """
    block = models[
        (models[DATASET_COL] == dataset)
        & (models[config.OFFSET_COL] == offset)
        & (models[config.FAMILY_COL] == family)
    ]
    if block.empty:
        return
    # Dispersion is estimated on the Poisson fit and is null for the others, so
    # the column appears only where it holds something. A column of `nan` is worse
    # than no column: it reads as a measurement that failed.
    show_dispersion = bool(block["DISPERSION"].notna().any())
    columns = ["Variables seleccionadas", "AIC", "BIC"]
    if show_dispersion:
        columns.append("Dispersión")
    columns += ["Moran", "Colineal", "¿gana al nulo?"]

    rows: list[str] = []
    text: list[list[str]] = []
    for pair in config.REGRESSION_PAIRS:
        for year in config.REGRESSION_YEARS:
            entry = block[(block[PAIR_NAME_COL] == pair.name) & (block[config.YEAR_COL] == year)]
            rows.append(f"{pair.label_es}  {year}")
            if entry.empty:
                text.append(["sin modelo"] + [""] * (len(columns) - 1))
                continue
            row = entry.iloc[0]
            names = ", ".join(
                config.predictor_label_es(name) for name in row["PREDICTORS"].split(", ") if name
            )
            cells = [names, f"{row['AIC']:.1f}", f"{row['BIC']:.1f}"]
            if show_dispersion:
                cells.append(f"{row['DISPERSION']:.2f}" if np.isfinite(row["DISPERSION"]) else "-")
            cells += [
                f"{row['MORANS_I']:.3f}",
                "sí" if row["COLLINEAR"] else "no",
                "sí" if row["BEATS_NULL"] else "NO",
            ]
            text.append(cells)

    _grid_table(
        text=text,
        columns=columns,
        rows=rows,
        title=(
            f"Modelos seleccionados · {config.FAMILY_LABELS_ES[family]}\n"
            f"offset: {config.OFFSET_LABELS_ES[offset]} · conjunto: "
            f"{config.DATASET_LABELS_ES[dataset]}"
        ),
        note=(
            "AIC compara sólo dentro de una misma familia y un mismo offset. Moran sobre los "
            "residuales: por encima de 0,2 el corte deja estructura espacial que el panel "
            "tendrá que recoger.\n"
            "Colineal: el modelo contiene un par de variables correlacionado por encima de "
            f"{config.CORRELATION_HIGH_THRESHOLD:.2f}, y entonces un coeficiente es un efecto "
            "repartido entre dos."
        ),
        out_path=out_path,
        column_width=1.75,
        wrap=28,
    )


def render_figures(
    data: dict[str, pd.DataFrame],
    tables: dict[str, pd.DataFrame],
    log: RunLog,
) -> int:
    """Every figure, in a tree whose path is the question it answers.

    `principal/` holds the one combination the study reports, so nobody has to
    navigate to see a result. `variantes/<conjunto>/<offset>/<familia>/` holds the
    rest, and the path reads as a sentence. `entradas/` holds what went in, which
    depends on none of those three. `resumen/` holds what is true across all of
    them.

    The year is in the file name and not in a folder, because it is the dimension
    that gets compared rather than fixed: three years of one combination belong
    together, and putting the year first scattered that comparison across three
    folders while piling eighteen variants into each.
    """
    root = log.run_dir / config.FIGURES_SUBDIR / "regressions"
    written = 0
    families = (config.OLS_FAMILY, config.POISSON_FAMILY, config.NEGATIVE_BINOMIAL_FAMILY)

    for dataset in data:
        for offset in config.REGRESSION_OFFSETS:
            for family in families:
                folder = (
                    root / "variantes" / config.DATASET_SLUGS[dataset]
                    / config.OFFSET_SLUGS[offset.name] / config.FAMILY_SLUGS[family]
                )
                folder.mkdir(parents=True, exist_ok=True)
                for year in config.REGRESSION_YEARS:
                    _fit_panel(
                        tables["predictions"], tables["models"], dataset, offset.name,
                        family, year, folder / f"ajuste__{year}.png",
                    )
                    written += 1
                _beta_heatmap(
                    tables["coefficients"], dataset, offset.name, family,
                    folder / "betas.png",
                )
                _models_table(
                    tables["models"], dataset, offset.name, family, folder / "modelos.png",
                )
                written += 2

        # The coefficient panel holds all three offsets at once, so it belongs to
        # the dataset and the family and not to any one offset.
        for family in families:
            folder = root / "variantes" / config.DATASET_SLUGS[dataset] / config.FAMILY_SLUGS[family]
            folder.mkdir(parents=True, exist_ok=True)
            for year in config.REGRESSION_YEARS:
                _coefficient_panel(
                    tables["coefficients"], dataset, family, year,
                    folder / f"coeficientes__{year}.png",
                )
                written += 1

    written += _render_inputs(data, root / "entradas")
    written += _render_summary(tables, root / "resumen")
    written += _copy_primary(root, log)

    log.info("wrote %d regression figures under %s/regressions/", written, config.FIGURES_SUBDIR)
    return written


def _render_inputs(data: dict[str, pd.DataFrame], folder: Path) -> int:
    """What went in, which depends on no offset, family or dataset — except one.

    The predictors are properties of the unit and are the same block for every
    pair, year excepted, and the same for both casualty datasets. **The responses
    are not**, and an earlier version of this drew them from whichever dataset came
    first and did not say which: the rho-corrected responses differ and were never
    shown anywhere. There is one per dataset now, and the title names it.
    """
    folder.mkdir(parents=True, exist_ok=True)
    written = 0
    first = next(iter(data.values()))
    for year in config.REGRESSION_YEARS:
        block = first[first[config.YEAR_COL] == year].drop_duplicates(subset=config.AREA_CODE_COL)
        values = block[list(config.REGRESSION_URBAN_CANDIDATES)].to_numpy(dtype=float)
        # Shaded column by column, from each variable's own minimum to its own
        # maximum: a share of a unit and a density per square kilometre have
        # nothing to say to each other on a shared ramp.
        shading = np.full(values.shape, np.nan)
        for index in range(values.shape[1]):
            column = values[:, index]
            low, high = float(np.nanmin(column)), float(np.nanmax(column))
            shading[:, index] = (
                (column - low) / (high - low)
                if high > low
                else np.full_like(column, config.MASTER_TABLE_FLAT_COLUMN_POSITION)
            )
        _grid_table(
            text=[
                [f"{value:.{config.predictor_decimals(float(np.nanmax(values[:, i])))}f}"
                 for i, value in enumerate(row)]
                for row in values
            ],
            columns=[config.predictor_label_es(name).replace(" ", "\n")
                     for name in config.REGRESSION_URBAN_CANDIDATES],
            rows=list(block[config.AREA_CODE_COL]),
            title=f"Predictoras por unidad · {year}",
            note="Mismo bloque para las ocho parejas y para los dos conjuntos: son "
                 "propiedades de la unidad. Color por columna, de su propio mínimo a su "
                 "propio máximo, así que compara hacia abajo y no hacia los lados.",
            out_path=folder / f"predictoras__{year}.png",
            shading=shading,
            column_width=1.05,
        )
        written += 1

    for dataset, frame in data.items():
        for year in config.REGRESSION_YEARS:
            block = frame[frame[config.YEAR_COL] == year]
            wide = block.pivot(
                index=config.AREA_CODE_COL, columns=PAIR_NAME_COL, values=RESPONSE_COL
            ).reindex(columns=[pair.name for pair in config.REGRESSION_PAIRS])
            values = wide.to_numpy(dtype=float)
            shading = np.full(values.shape, np.nan)
            for index in range(values.shape[1]):
                column = values[:, index]
                high = float(np.nanmax(column))
                shading[:, index] = column / high if high > 0 else 0.0
            _grid_table(
                text=[[f"{int(value)}" for value in row] for row in values],
                columns=[pair.label_es.replace("-", "\n") for pair in config.REGRESSION_PAIRS],
                rows=list(wide.index),
                title=f"Partes afectadas por unidad y pareja · {year} · "
                      f"conjunto {config.DATASET_LABELS_ES[dataset]}",
                note="Un cero es una observación de ausencia, no un dato que falte. Color por "
                     "columna: cada pareja contra su propio máximo.",
                out_path=folder / f"respuestas__{config.DATASET_SLUGS[dataset]}__{year}.png",
                shading=shading,
                column_width=1.05,
            )
            written += 1
    return written


def _render_summary(tables: dict[str, pd.DataFrame], folder: Path) -> int:
    """What holds across every combination."""
    folder.mkdir(parents=True, exist_ok=True)
    frequency = selection_frequency(tables["coefficients"])
    total = int(frequency["MODELS"].iloc[0])
    _grid_table(
        text=[
            [
                f"{int(row['SELECTED'])}",
                f"{100 * row['SELECTED_SHARE']:.1f}%",
                f"{int(row['POSITIVE'])}",
                f"{int(row['NEGATIVE'])}",
                f"{int(row['SIGNIFICANT'])}",
            ]
            for _, row in frequency.iterrows()
        ],
        columns=["Veces\nelegida", "% de los\nmodelos", "Signo +", "Signo −", "Significativa"],
        rows=[config.predictor_label_es(name) for name in frequency["TERM"]],
        title=f"Frecuencia de selección de cada variable · {total} modelos",
        note="Una variable que gana en contextos independientes —parejas, años, conjuntos, "
             "offsets y familias distintos— es evidencia. Si la ganadora cambia cada vez, la "
             "selección es ruido.\nUn signo que se sostiene vale más que cualquiera de los "
             "valores p de las tablas, que están inflados por la selección.",
        out_path=folder / "frecuencia_seleccion.png",
        column_width=1.25,
    )
    return 1


def _copy_primary(root: Path, log: RunLog) -> int:
    """Copy the combination the study reports into a folder of its own.

    Six files duplicated, which is cheap, so that somebody who wants the result
    does not have to navigate a tree to find it. The note beside them says which
    combination it is and why that one.
    """
    source = (
        root / "variantes" / config.DATASET_SLUGS[config.PRIMARY_DATASET]
        / config.OFFSET_SLUGS[config.PRIMARY_OFFSET] / config.FAMILY_SLUGS[config.PRIMARY_FAMILY]
    )
    coefficients_source = (
        root / "variantes" / config.DATASET_SLUGS[config.PRIMARY_DATASET]
        / config.FAMILY_SLUGS[config.PRIMARY_FAMILY]
    )
    folder = root / "principal"
    folder.mkdir(parents=True, exist_ok=True)

    copied = 0
    for origin in (source, coefficients_source):
        if not origin.is_dir():
            continue
        for path in sorted(origin.glob("*.png")):
            shutil.copyfile(path, folder / path.name)
            copied += 1

    (folder / "LEEME.txt").write_text(
        "Estas figuras son una copia de\n"
        f"  variantes/{config.DATASET_SLUGS[config.PRIMARY_DATASET]}/"
        f"{config.OFFSET_SLUGS[config.PRIMARY_OFFSET]}/"
        f"{config.FAMILY_SLUGS[config.PRIMARY_FAMILY]}/\n\n"
        "Es la combinación que el estudio reporta, y no es cuestión de gusto:\n\n"
        "  conjunto observado        el corregido con rho existe para contrastar,\n"
        "                            no para reportar\n"
        "  offset de exposición      es el que declara el anteproyecto\n"
        "  del modo afectado\n"
        "  binomial negativa         es la familia que respalda la sobredispersión,\n"
        "                            en 143 de 144 modelos de Poisson\n\n"
        "Las otras diecisiete combinaciones están completas en variantes/.\n",
        encoding="utf-8",
    )
    log.info("copied %d figures into principal/ from the combination the study reports", copied)
    return copied


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def report(tables: dict[str, pd.DataFrame], log: RunLog) -> None:
    """What the run found, said out loud rather than left in a file."""
    models = tables["models"]

    header = (
        f"{'dataset':<10}  {'offset':<16}  {'family':<18}  {'models':>6}  "
        f"{'beat null':>9}  {'collinear':>9}  {'median AIC':>10}"
    )
    lines = [header, "-" * len(header)]
    for (dataset, offset, family), block in models.groupby(
        [DATASET_COL, config.OFFSET_COL, config.FAMILY_COL], sort=False
    ):
        lines.append(
            f"{dataset:<10}  {offset:<16}  {family:<18}  {len(block):>6}  "
            f"{int(block['BEATS_NULL'].sum()):>9}  {int(block['COLLINEAR'].sum()):>9}  "
            f"{block['AIC'].median():>10.1f}"
        )
    log.table("selected models, by dataset, offset and family:", "\n".join(lines))

    # The dispersion is what chooses the family, so it is reported on its own.
    poisson = models[models[config.FAMILY_COL] == config.POISSON_FAMILY]
    over = poisson[poisson["DISPERSION"] > config.OVERDISPERSION_THRESHOLD]
    log.info(
        "%d of %d Poisson models are overdispersed above %.2f (median %.2f, maximum %.2f); "
        "the negative binomial is the family to read wherever they are",
        len(over),
        len(poisson),
        config.OVERDISPERSION_THRESHOLD,
        float(poisson["DISPERSION"].median()),
        float(poisson["DISPERSION"].max()),
    )

    spatial = models[models["MORANS_I"].abs() > config.MORAN_REPORTING_THRESHOLD]
    if len(spatial):
        log.warn(
            "%d of %d selected models leave residuals with Moran's I beyond %.2f, up to "
            "%.3f. The cross-section has spatial structure left in it, which is what the "
            "panel that follows this step will have to carry a term for",
            len(spatial),
            len(models),
            config.MORAN_REPORTING_THRESHOLD,
            float(models["MORANS_I"].abs().max()),
        )
    else:
        log.info(
            "no selected model leaves residuals beyond Moran's I of %.2f; the "
            "cross-section carries no spatial structure the panel would have to absorb",
            config.MORAN_REPORTING_THRESHOLD,
        )

    frequency = selection_frequency(tables["coefficients"])
    header = f"{'variable':<34}  {'selected':>8}  {'% of models':>11}  {'+':>4}  {'-':>4}  {'sig':>5}"
    lines = [header, "-" * len(header)]
    for _, row in frequency.iterrows():
        lines.append(
            f"{row['TERM']:<34}  {int(row['SELECTED']):>8}  {100 * row['SELECTED_SHARE']:>10.1f}%  "
            f"{int(row['POSITIVE']):>4}  {int(row['NEGATIVE']):>4}  {int(row['SIGNIFICANT']):>5}"
        )
    log.table(
        f"how often each variable was selected, across {int(frequency['MODELS'].iloc[0])} models:",
        "\n".join(lines),
    )

    log.warn(
        "the p-values above are the winner of a search over every declared subset, so "
        "they are inflated by the selection itself and are not honest p-values. The "
        "European study being replicated has the same defect. What is worth reading is "
        "the table immediately above: a variable that wins in independent contexts"
    )

