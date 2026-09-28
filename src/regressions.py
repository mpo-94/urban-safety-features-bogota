"""Cross-sectional regressions at every year that sustains one, on both datasets.

**A first step and not the methodology.** The anteproyecto declares a count GLM
on the unit-by-year panel, with Hausman deciding between fixed and random
effects, and that is still what the thesis estimates. What this stage produces is
what my advisor and the panel adviser asked for before the panel is built: least
squares and a count GLM at one year at a time, one regression per oriented pair
of road user types, on the observed and the rho-corrected datasets.

**Thirteen years and not the three it began with.** The three were the survey
years, 2015, 2019 and 2023, and they were chosen while the exposure existed only
where a survey had measured it. The interpolation carries the exposure across
every year between them, so the reason for stopping at three went away and the
window now runs from 2012 to 2024. The years are `config.REGRESSION_YEARS` and
nothing here counts them.

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

import collections
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
    from src import config, predictors
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import predictors  # type: ignore[no-redef]
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

# The coefficient divided by the standard deviation of the response of its own
# cell, which completes a standardisation that today is applied to the predictors
# only. Least squares alone: the GLM coefficient is already dimensionless and
# dividing it would break its meaning, so the column arrives null there. D51.
#
# The name contrasts with `COEFFICIENT_STANDARDISED`, and the contrast is the
# point — the two names side by side say what separates them.
FULLY_STANDARDISED_COL = "COEFFICIENT_FULLY_STANDARDISED"
RESPONSE_DEVIATION_COL = "RESPONSE_DEVIATION"


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
    candidate_set: str,
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

    # The unit's name, so a figure can label a row `03-Arborizadora` rather than
    # `UPL03` and a reader does not have to hold thirty codes in their head. It
    # comes from the predictor table, which is the only input that carries it.
    names = dict(zip(predictors[config.AREA_CODE_COL], predictors[config.AREA_NAME_COL]))
    table[config.AREA_NAME_COL] = table[config.AREA_CODE_COL].map(names)

    pool_sizes: dict[int, int] = {}
    for year in config.REGRESSION_YEARS:
        size = len(config.regression_pool_in(year, candidate_set))
        pool_sizes[size] = pool_sizes.get(size, 0) + 1

    log.record(
        "assemble the regression dataset",
        rows_in=len(grid),
        rows_out=len(table),
        changes=[],
        notes=[
            f"grid = {len(units)} units x {len(config.REGRESSION_PAIRS)} pairs x "
            f"{len(config.REGRESSION_YEARS)} years",
            f"{filled:,} unit-pair-year cell(s) had no casualty and carry a measured zero",
            f"candidate set: {candidate_set}, "
            f"{len(config.regression_candidate_pool(candidate_set))} column(s), of which "
            f"{len(set(config.regression_candidate_pool(candidate_set)) & set(config.OFFSET_QUANTITIES))}"
            " can serve as an offset",
            # The pool is not the same in every year, and that difference is the
            # whole reason the study has two stretches rather than one.
            "the pool holds "
            + ", ".join(
                f"{size} column(s) in {count} year(s)"
                for size, count in sorted(pool_sizes.items(), reverse=True)
            ),
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


def _scale_candidates(frame: pd.DataFrame, candidates: tuple[str, ...]) -> np.ndarray:
    """The candidate columns, with the scale quantities taken in logarithms.

    `config.LOG_SCALED_CANDIDATES` says which and why. The short version is that
    an offset is already the logarithm of one of these with its coefficient fixed
    at one, so a free predictor built the same way is the same variable with the
    constraint relaxed — and its coefficient is then an elasticity, comparable
    both with that one and with the exponent the safety-in-numbers literature
    reports. Raw, in a log-link model, the same column would assert exponential
    growth in trips, which is a different and much stronger claim.

    A zero or a negative would have no logarithm. These are trips and residents,
    so it does not happen; the check is here because if it ever did, a silent nan
    would remove that candidate from every search without saying so.
    """
    columns = []
    for name in candidates:
        values = frame[name].to_numpy(dtype=float)
        if name in config.LOG_SCALED_CANDIDATES:
            if np.any(values <= 0):
                raise ValueError(
                    f"{name} enters the design in logarithms and is zero or negative in "
                    f"{int((values <= 0).sum())} row(s); see config.LOG_SCALED_CANDIDATES"
                )
            values = np.log(values)
        columns.append(values)
    return np.column_stack(columns)


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
    raw = _scale_candidates(frame, candidates)
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
    inhabited in every year of the window.
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


def _over_deviation(value: float, deviation: float) -> float:
    """El valor dividido por la desviación de la respuesta, o nulo si no la hay.

    Nulo y no cero donde la familia no la estima: un cero en esa columna se
    leería como un coeficiente estandarizado que vale cero, que es una medición,
    y lo que pasa es que la cantidad no existe para esa familia.
    """
    if not np.isfinite(deviation) or deviation <= 0:
        return float("nan")
    return value / deviation


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
    candidate_set: str,
    log: RunLog,
) -> tuple[dict, list[dict], list[dict]] | None:
    """Everything one regression contributes: its model row, coefficients, predictions."""
    # The year's pool, not the general one: a variable whose layer does not reach
    # this year arrives empty, and a model built on it would be dropped silently
    # by the fit filter rather than never attempted. See config.regression_pool_in.
    candidates = offset.candidate_predictors(
        config.regression_pool_in(year, candidate_set))
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
    # On the same scale the fit saw, which for a log-scaled candidate is the
    # logarithm. Taking the deviation of the raw column instead would divide a
    # coefficient estimated per standard deviation of log(trips) by the standard
    # deviation of trips, and for a quantity in the hundreds of thousands that
    # rounds every elasticity to zero.
    raw = _scale_candidates(frame, tuple(best.predictors))
    deviations = raw.std(axis=0, ddof=0)

    # La desviación de la respuesta **que el ajuste vio**, que es la tasa en
    # mínimos cuadrados y no el conteo. Dividir por ella completa una
    # estandarización que hoy sólo se aplica a las variables, y sin ella los
    # 1 639 coeficientes de MCO se redondean a cero en las figuras: el modelo
    # ajusta siniestros por viaje, que vale del orden de una diezmilésima bajo la
    # exposición del modo y de 1e-11 bajo el producto de las dos.
    #
    # **Sólo mínimos cuadrados.** El coeficiente del GLM ya es adimensional —vive
    # en la escala logarítmica— y dividirlo rompería su significado, así que la
    # columna llega nula ahí y no cero, que se leería como una medición. D51.
    if family == config.OLS_FAMILY:
        response_deviation = float(np.std(response / np.exp(log_offset), ddof=0))
    else:
        response_deviation = float("nan")

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
        config.CANDIDATE_SET_COL: candidate_set,
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
        #
        # **For a log-scaled candidate the raw column is an elasticity**, not a
        # coefficient per trip, because the column the fit saw was the logarithm.
        # It is the same arithmetic and a different quantity, so the row carries a
        # flag rather than leaving a reader to infer it from the variable's name.
        deviation = deviations[position - 1] if position > 0 else float("nan")
        estimate = float(result.params[position])
        is_elasticity = name in config.LOG_SCALED_CANDIDATES
        coefficient_rows.append(
            {
                config.CANDIDATE_SET_COL: candidate_set,
                DATASET_COL: dataset,
                config.OFFSET_COL: offset.name,
                PAIR_NAME_COL: pair.name,
                config.YEAR_COL: year,
                config.FAMILY_COL: family,
                MODEL_ID_COL: model_id,
                "TERM": name,
                "COEFFICIENT_STANDARDISED": estimate,
                "COEFFICIENT": estimate / deviation if position > 0 and deviation > 0 else estimate,
                "COEFFICIENT_IS_ELASTICITY": is_elasticity,
                "STANDARD_ERROR": float(result.bse[position]),
                "P_VALUE": float(result.pvalues[position]),
                "CI_LOW": float(intervals[position, 0]),
                "CI_HIGH": float(intervals[position, 1]),
                # Los tres se dividen por el mismo número, que es lo que mantiene
                # al intervalo conteniendo a su estimación. Dividir sólo el punto
                # dejaría una figura cuyos bigotes no rodean su propio punto.
                RESPONSE_DEVIATION_COL: response_deviation,
                FULLY_STANDARDISED_COL: _over_deviation(estimate, response_deviation),
                "CI_LOW_FULLY_STANDARDISED": _over_deviation(
                    float(intervals[position, 0]), response_deviation),
                "CI_HIGH_FULLY_STANDARDISED": _over_deviation(
                    float(intervals[position, 1]), response_deviation),
                "SIGNIFICANT": bool(float(result.pvalues[position]) < config.REGRESSION_SIGNIFICANCE),
                "STARS": _significance(float(result.pvalues[position])),
            }
        )

    prediction_rows = [
        {
            config.CANDIDATE_SET_COL: candidate_set,
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
    estimated: fewer than half the cells at zero. A pair that fails in any year of
    the window is dropped from all of them, because a coefficient that exists in
    2019 and not in 2012 cannot be put in the year-by-year comparison the figures
    are built around — a row of the beta heatmap would then hold two kinds of
    blank, and the whole point of that figure is that it holds only one.

    It drops nothing today — the worst case is eleven zero units of thirty, car
    against motorcycle in 2012 — and it is here so that it would. Widening the
    window to thirteen years is what brought the worst case up from five: the
    threshold now sits in the early years rather than nowhere near anything.
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
    candidate_set: str,
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
                            frame, dataset, offset, pair, year, family, weights,
                            candidate_set, log,
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


def selection_frequency(
    coefficients: pd.DataFrame,
    models: pd.DataFrame,
    candidate_set: str,
) -> pd.DataFrame:
    """How often each variable was selected, over the models it could be selected in.

    The most defensible thing this stage produces, and the reason the search is
    worth running at all. A variable that wins in independent contexts — different
    pairs, years, datasets, offsets and families — is evidence. A field where the
    winner changes every time is noise, and the chapter has to say which of the
    two it is looking at.

    **Each variable gets its own denominator, and the denominator is a column.**
    An earlier version divided by the total number of models, which is only right
    for a variable that competed in all of them. Two kinds of candidate did not:
    an exposure or population quantity is in the bag only under the offsets that
    do not use it as the denominator, and with thirteen years vertical signage
    joins them, because its layer covers neither 2012-2014 nor 2024. Dividing by
    the total punishes whoever had fewer opportunities, and not by a little — the
    affected mode's exposure moved from ninth place to first when this was
    corrected. A share whose denominator changes from row to row and is not shown
    is the same defect wearing another face, so `AVAILABLE` is exported and drawn.

    `OFFSETS` is how many of the three had the variable in the bag at all. Where
    it says one, that row's share describes a single offset rather than the study.
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

    # Un recorrido por los modelos y no un producto de cardinalidades: el año
    # decide qué hay en la bolsa y el offset decide qué se lleva de ella, así que
    # la única cuenta que no se puede equivocar es preguntárselo a cada modelo.
    offsets = {offset.name: offset for offset in config.REGRESSION_OFFSETS}
    available: collections.Counter[str] = collections.Counter()
    for offset_name, year in zip(models[config.OFFSET_COL], models[config.YEAR_COL]):
        pool = config.regression_pool_in(int(year), candidate_set)
        available.update(offsets[offset_name].candidate_predictors(pool))
    general = config.regression_candidate_pool(candidate_set)
    in_offsets = {
        name: sum(
            1 for offset in config.REGRESSION_OFFSETS
            if name in offset.candidate_predictors(general)
        )
        for name in available
    }

    # Toda candidata tiene fila, incluida la que no ganó nunca: cero de 430 es un
    # resultado, y una variable ausente de la tabla no se distingue de una que no
    # estuvo en la bolsa.
    table = table.reindex(sorted(available)).fillna(0).astype(int)
    table["AVAILABLE"] = pd.Series(available).reindex(table.index)
    table["OFFSETS"] = pd.Series(in_offsets).reindex(table.index)
    table["MODELS"] = len(models)
    # La tabla de frecuencias es la única de las cuatro que no sale de `fit_cell`,
    # así que la columna se pone aquí. Sin ella, las dos corridas producen tablas
    # idénticas en forma y distintas en significado, y nadie las puede juntar.
    table[config.CANDIDATE_SET_COL] = candidate_set
    table["SELECTED_SHARE"] = table["SELECTED"] / table["AVAILABLE"]
    table.index.name = "TERM"
    return table.sort_values("SELECTED_SHARE", ascending=False).reset_index()

def selection_frequency_by_specification(
    coefficients: pd.DataFrame,
    models: pd.DataFrame,
    candidate_set: str,
) -> pd.DataFrame:
    """La misma cuenta, una vez por especificación, apilada en una sola tabla.

    **Una especificación es una familia, un conjunto de siniestralidad y un
    offset.** Dentro de ella lo único que varía son las ocho parejas y los trece
    años, que sí son contextos independientes. Cruzar esa frontera no suma: se
    midió que el orden de las doce se mueve hasta siete puestos de doce entre
    offsets, así que una cuenta que los junte promedia justo lo que más discrepa.
    D53.

    Sustituye a la fila única por variable que se exportaba antes. Esa no se
    conserva: un tablero que la encontrara la dibujaría, y es lo que D53 retira.
    """
    keys = [DATASET_COL, config.OFFSET_COL, config.FAMILY_COL]
    bloques = []
    for (dataset, offset, family), block in models.groupby(keys, sort=False):
        terms = coefficients[
            (coefficients[DATASET_COL] == dataset)
            & (coefficients[config.OFFSET_COL] == offset)
            & (coefficients[config.FAMILY_COL] == family)
        ]
        frequency = selection_frequency(terms, block, candidate_set)
        frequency.insert(0, config.FAMILY_COL, family)
        frequency.insert(0, config.OFFSET_COL, offset)
        frequency.insert(0, DATASET_COL, dataset)
        bloques.append(frequency)
    return pd.concat(bloques, ignore_index=True)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export(
    data: dict[str, pd.DataFrame],
    tables: dict[str, pd.DataFrame],
    candidate_set: str,
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

    frequency = selection_frequency_by_specification(
        tables["coefficients"], tables["models"], candidate_set)
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
    candidate_set: str,
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
        # Dos comprobaciones opuestas y las dos necesarias, porque con trece años
        # una candidata puede no existir. Dentro de la bolsa del año, un nulo es
        # una medición que no ocurrió. Fuera de ella, un valor presente es peor
        # que un nulo: un cero entraría al modelo como una ausencia medida, que
        # es justo la confusión que el aspa de las figuras existe para deshacer.
        missing_inside = 0
        present_outside = 0
        for year in config.REGRESSION_YEARS:
            block = frame[frame[config.YEAR_COL] == year]
            pool = list(config.regression_pool_in(year, candidate_set))
            missing_inside += int(block[pool].isna().sum().sum())
            outside = [
                name for name in config.regression_candidate_pool(candidate_set)
                if name not in pool
            ]
            present_outside += int(block[outside].notna().sum().sum()) if outside else 0
        checks.append(
            (
                f"no candidate of the year is null in {dataset}",
                missing_inside == 0,
                f"{missing_inside} null cell(s); a measured zero is a fact and a null is a "
                "measurement that did not happen",
            )
        )
        checks.append(
            (
                f"a candidate outside its years carries nothing in {dataset}",
                present_outside == 0,
                f"{present_outside} cell(s) with a value where the layer does not reach; "
                "a zero there would be read as a measured absence",
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
    # Per offset AND per year: the pool is not the same in every year, so one
    # count for the whole offset would expect models that were never declared.
    expected_declared = 0
    for offset in config.REGRESSION_OFFSETS:
        for year in config.REGRESSION_YEARS:
            candidates = offset.candidate_predictors(
                config.regression_pool_in(year, candidate_set))
            per_cell = sum(
                len(list(itertools.combinations(candidates, size)))
                for size in config.REGRESSION_SUBSET_SIZES
            )
            cells = len(models[
                (models[config.OFFSET_COL] == offset.name)
                & (models[config.YEAR_COL] == year)
            ])
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

    # Ninguna variable aparece en un modelo de un año en el que no existía. Es la
    # otra mitad de la comprobación de arriba: aquella mira los datos y ésta mira
    # el resultado, y sólo ésta se rompería si la búsqueda pidiera la bolsa
    # general en lugar de la del año.
    terms = coefficients[coefficients["TERM"] != "INTERCEPT"]
    out_of_reach = terms[
        [
            term not in config.regression_pool_in(int(year), candidate_set)
            for term, year in zip(terms["TERM"], terms[config.YEAR_COL])
        ]
    ]
    checks.append(
        (
            "no coefficient belongs to a year its layer does not reach",
            len(out_of_reach) == 0,
            f"{len(terms) - len(out_of_reach):,} of {len(terms):,}"
            + (
                f"; {out_of_reach['TERM'].iloc[0]} in {int(out_of_reach[config.YEAR_COL].iloc[0])}"
                if len(out_of_reach)
                else ""
            ),
        )
    )

    # Las tres tablas dicen de qué corrida son, y dicen lo mismo. Una columna que
    # llegara vacía o con dos valores haría imposible juntar las dos corridas, que
    # es para lo que la corrida limpia existe.
    declared_set = {
        name: set(frame[config.CANDIDATE_SET_COL].unique())
        for name, frame in (
            ("models", models),
            ("coefficients", coefficients),
            ("predictions", predictions),
        )
    }
    one_set = all(values == {candidate_set} for values in declared_set.values())
    checks.append(
        (
            "every exported row carries the candidate set of the run",
            one_set,
            candidate_set if one_set else f"{declared_set}",
        )
    )

    # Y si el conjunto es el urbano, ninguna cantidad de offset compitió. Es la
    # comprobación que define la corrida limpia: sin ella, que la bolsa fuera la
    # correcta se quedaría en que el registro lo dijera.
    if not config.CANDIDATE_SETS_BY_NAME[candidate_set].admits_offset_quantities:
        leftovers = terms[terms["TERM"].isin(config.OFFSET_QUANTITIES)]
        checks.append(
            (
                "no offset quantity competed",
                len(leftovers) == 0,
                f"{len(terms) - len(leftovers):,} term(s), none of them a quantity"
                if len(leftovers) == 0
                else f"{len(leftovers)} row(s), first {leftovers['TERM'].iloc[0]}",
            )
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


def _count_r_squared(observed: np.ndarray, predicted: np.ndarray) -> float:
    """R² on the scale the fit figure draws, which is counts.

    Least squares is fitted on the rate, because it admits no offset, and the
    figure multiplies the prediction back by the exposure so that its axes are in
    casualties. That leaves two possible R² for the same model, and they are not
    close: across the eight pairs of one cell they differ by 0.36 on average,
    because exposure spans a factor of 171 between units and multiplying back is
    therefore not a neutral operation.

    This is the one on the counts, because a number printed on a scatter has to
    describe that scatter. It goes negative where the model does worse than the
    mean, and where it does, the scatter shows it.
    """
    observed = np.asarray(observed, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    total = float(((observed - observed.mean()) ** 2).sum())
    if total <= 0:
        return float("nan")
    return 1 - float(((observed - predicted) ** 2).sum()) / total


def _plotted_coefficient(family: str) -> tuple[str, str, str]:
    """Qué tres columnas dibuja una figura de coeficientes, según la familia.

    Mínimos cuadrados ajusta la tasa, así que su coeficiente está en unidades de
    tasa y vale del orden de una diezmilésima: los 1 639 se redondean a 0,00 en
    la figura y el signo sobrevive sólo como el guion de un «-0.00». Se dibuja
    entonces el que además divide por la desviación de la respuesta. El GLM no lo
    necesita, porque su coeficiente ya es adimensional. D51.

    Los tres extremos salen juntos o el intervalo dejaría de contener a su punto.
    """
    if family == config.OLS_FAMILY:
        return (FULLY_STANDARDISED_COL,
                "CI_LOW_FULLY_STANDARDISED", "CI_HIGH_FULLY_STANDARDISED")
    return "COEFFICIENT_STANDARDISED", "CI_LOW", "CI_HIGH"


def _coefficient_quantity_es(family: str) -> str:
    """Qué dice una celda, dicho en el subtítulo, porque no es lo mismo en las dos."""
    if family == config.OLS_FAMILY:
        return "desviaciones estándar de la tasa por desviación de la variable"
    return "cambio en el logaritmo del conteo por desviación de la variable"


def _candidate_label(candidate_set: str) -> str:
    """Cómo se nombra el conjunto de candidatas en el subtítulo de una figura.

    **«Candidatas» y no «conjunto»**, que es la palabra que ya lleva el conjunto
    de siniestralidad. Un subtítulo con dos conjuntos obliga a adivinar cuál es
    cuál, y la figura que existe para desambiguar dos corridas no puede introducir
    una ambigüedad nueva al hacerlo.

    Va en todas las figuras cuyo contenido depende del conjunto, corra el que
    corra, y no solo en la corrida que no es la de siempre. Una figura que calla
    obligaría a recordar cuál era el valor por defecto el día que se dibujó.
    """
    return config.CANDIDATE_SETS_BY_NAME[candidate_set].label_es


def _panel_grid(title: str) -> tuple[plt.Figure, np.ndarray]:
    """Two rows of four, which is how the eight pairs are read.

    Vulnerable victims above and motorised below, in the order the configuration
    declares them. My advisor asked for this shape, and it is also the only one
    that fits eight panels on a page without any of them going illegible.
    """
    figure, axes = plt.subplots(2, 4, figsize=(16, 8))
    figure.suptitle(title, fontsize=13)
    return figure, axes.reshape(-1)


def _text_colour(rgba: tuple[float, ...]) -> str:
    """Black or white, whichever contrasts more against that fill.

    Relative luminance as WCAG defines it: each channel linearised, then
    weighted. White is chosen only where the cell is genuinely dark.

    An earlier version decided by distance from the middle of the scale, which is
    right for the diverging map of the coefficients — both ends are dark — and
    wrong for the sequential blue of the input tables, where the low end is almost
    white. Low values were printed in white on near-white and vanished; one unit's
    whole row was unreadable. Measuring the colour works for either scale, so
    there are not two rules for somebody to keep in step.
    """
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgba[:3]]
    luminance = 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
    return "white" if luminance < 0.179 else "#222222"


def _fit_panel(
    predictions: pd.DataFrame,
    models: pd.DataFrame,
    dataset: str,
    offset: str,
    family: str,
    year: int,
    candidate_set: str,
    out_path: Path,
) -> None:
    """Observed against predicted, one panel per pair.

    **Each panel carries its own scale and the caption says so.** In 2015
    pedestrian-motorcycle had 1,365 affected parties and car-motorcycle 80, so a
    shared scale would crush half the panels into the origin.

    The reference is the 45-degree line and never a line fitted to the cloud: the
    question is how far the model is from the observation, and a fitted line would
    answer a different one while looking like this one.

    **The points take the colour of their offset**, so two of these from different
    denominators are told apart before the title is read.
    """
    colour = config.OFFSET_COLORS[offset]
    figure, axes = _panel_grid(
        f"Observado contra predicho · {year} · {config.FAMILY_LABELS_ES[family]}\n"
        f"offset: {config.OFFSET_LABELS_ES[offset]} · conjunto: {config.DATASET_LABELS_ES[dataset]}"
        f" · candidatas: {_candidate_label(candidate_set)} · cada panel con su propia escala"
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
        axis.scatter(observed, predicted, s=26, color=colour, zorder=2)
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
        if not len(row):
            continue

        # Each family carries the figure its own search minimises, and they are
        # not the same quantity. Least squares fits the rate, so its AIC is on the
        # rate and a single AIC printed on a panel says nothing a reader can use;
        # R² on the counts describes the cloud that is actually drawn. The count
        # families fit the count, so the figure and their AIC already agree.
        if family == config.OLS_FAMILY:
            goodness = _count_r_squared(observed, predicted)
            # A negative R² is not a small value. It is a model that predicts
            # worse than the mean of the thirty units would have, and on a grid of
            # eight panels that has to be visible without reading the number.
            label = f"R² {goodness:.3f}".replace("-", "−")
            # Not `colour`: that is the scatter's, set once from the offset, and
            # assigning to it here repainted every panel after the first.
            label_colour = config.REGRESSION_FAILING_COLOR if goodness < 0 else "#555555"
        else:
            label, label_colour = f"AIC {float(row['AIC'].iloc[0]):.0f}", "#555555"
        axis.text(0.03, 0.97, label, transform=axis.transAxes, va="top",
                  fontsize=8, color=label_colour)

        # Moran in both families, because it is a property of the residuals rather
        # than of the estimator: the same pair marked under two estimators says the
        # clustering is in the city and not in the method, which is what the panel
        # stage needs to know.
        morans = float(row["MORANS_I"].iloc[0])
        beyond = abs(morans) > config.MORAN_REPORTING_THRESHOLD
        axis.text(
            0.03, 0.90, f"Moran {morans:.3f}".replace("-", "−"),
            transform=axis.transAxes, va="top", fontsize=8,
            color=config.REGRESSION_FLAGGED_COLOR if beyond else "#555555",
        )
    figure.tight_layout()
    figure.savefig(out_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(figure)


def _coefficient_panel(
    coefficients: pd.DataFrame,
    dataset: str,
    family: str,
    year: int,
    candidate_set: str,
    out_path: Path,
) -> None:
    """The selected coefficients of all three offsets, one panel per pair.

    **The three offsets are one figure and not three.** They differ only in the
    denominator, so putting them on the same axis shows directly how far a
    coefficient moves when the denominator changes — which is the question the
    three offsets exist to answer.

    It is the only figure that shows how **wide** an interval is. The heatmap says
    whether a coefficient's interval crosses zero, by the absence of a star; only
    this one says whether it was estimated tightly or barely at all.

    **The label and the position of a point are built together**, which is not
    cosmetic. They were not: labels were placed at whole numbers while points
    advanced by 0.6 extra between offset groups, so from the second group on, a
    coefficient was drawn beside the name of a different variable.

    **The third line of the title says which of the series candidates the year
    had.** With thirteen cross-sections, a reader who opens the 2014 panel and
    the 2019 panel has no way of telling that vertical signage could enter one
    and not the other, and the absence of a variable then reads as «it was not
    selected» when what happened is that it did not exist.
    """
    figure, axes = _panel_grid(
        f"Coeficientes estandarizados · {year} · {config.FAMILY_LABELS_ES[family]}\n"
        f"conjunto: {config.DATASET_LABELS_ES[dataset]} · candidatas: "
        f"{_candidate_label(candidate_set)} · un color por offset · intervalo del 95 %\n"
        f"variables {config.series_available_in(year)}\n"
        f"cada punto: {_coefficient_quantity_es(family)}"
    )
    valor_col, bajo_col, alto_col = _plotted_coefficient(family)
    colours = config.OFFSET_COLORS

    for axis, pair in zip(axes, config.REGRESSION_PAIRS):
        axis.set_title(pair.label_es, fontsize=10)
        axis.axvline(0, color="#888888", linewidth=1, zorder=1)

        positions: list[float] = []
        labels: list[str] = []
        height = 0.0
        for offset in config.REGRESSION_OFFSETS:
            rows = coefficients[
                (coefficients[DATASET_COL] == dataset)
                & (coefficients[config.OFFSET_COL] == offset.name)
                & (coefficients[config.FAMILY_COL] == family)
                & (coefficients[config.YEAR_COL] == year)
                & (coefficients[PAIR_NAME_COL] == pair.name)
                & (coefficients["TERM"] != "INTERCEPT")
            ]
            if not len(rows):
                continue
            for _, row in rows.iterrows():
                axis.hlines(
                    height, row[bajo_col], row[alto_col],
                    color=colours[offset.name], linewidth=2, zorder=2,
                )
                axis.scatter(
                    row[valor_col], height,
                    s=28, color=colours[offset.name], zorder=3,
                )
                positions.append(height)
                labels.append(config.predictor_label_es(row["TERM"]))
                height += 1
            # The gap between groups no longer touches the labels, because they
            # are placed at the positions kept above and not at whole numbers.
            height += 0.7

        if not positions:
            axis.text(0.5, 0.5, "sin modelo", ha="center", va="center", transform=axis.transAxes)
            axis.set_xticks([])
            axis.set_yticks([])
            continue
        axis.set_yticks(positions, labels, fontsize=7.5)
        axis.set_ylim(max(positions) + 0.6, min(positions) - 0.6)
        axis.tick_params(axis="y", length=0)

    handles = [
        plt.Line2D([], [], color=colours[offset.name], linewidth=3,
                   label=config.OFFSET_LABELS_ES[offset.name])
        for offset in config.REGRESSION_OFFSETS
    ]
    figure.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=9)
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    figure.savefig(out_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(figure)


# -- tables drawn as a grid, never with matplotlib's own table ---------------
# `axis.table` sizes its columns by their count and not by what is in them, so a
# heading longer than its share is drawn over its neighbour and a long cell spills
# across the one beside it. Both happened. These draw on an image grid instead,
# the way the predictor master table does: the text sits at a cell centre, the
# grid fills the axes, and nothing can overflow because nothing is laid out by
# matplotlib.


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
    column_groups: list[tuple[str, int, int]] | None = None,
    title_pad: float = 30,
    wrap: int | None = None,
    dim_rows: set[int] | None = None,
    crossed_cells: list[tuple[int, int]] | None = None,
) -> None:
    """A table of text on a grid, optionally shaded, filling its own canvas.

    `crossed_cells` marks a cell with an X: not a low value but a cell where
    nothing was measured, which an empty cell cannot say on its own.
    """
    row_count, column_count = len(rows), len(columns)
    if wrap:
        text = [[textwrap.fill(cell, wrap) for cell in row] for row in text]
    tallest = max((cell.count("\n") + 1 for row in text for cell in row), default=1)
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

    normalise = matplotlib.colors.Normalize(vmin=low, vmax=high)
    for row, column in itertools.product(range(row_count), range(column_count)):
        value = painted[row, column]
        colour = (
            _text_colour(cmap(normalise(value)))
            if shading is not None and np.isfinite(value)
            else "#222222"
        )
        axis.text(column, row, text[row][column], ha="center", va="center",
                  fontsize=7, color=colour)

    # El aspa, metida dentro de la celda. De esquina a esquina, las diagonales de
    # dos celdas vecinas se tocan y se leen como una cinta continua en lugar de
    # como dos cruces separadas.
    inset = 0.34
    for row, column in crossed_cells or []:
        axis.plot([column - inset, column + inset], [row - inset, row + inset],
                  color=config.GRID_CROSS_COLOR, linewidth=1.2, zorder=3)
        axis.plot([column - inset, column + inset], [row + inset, row - inset],
                  color=config.GRID_CROSS_COLOR, linewidth=1.2, zorder=3)

    axis.set_xticks(range(column_count), columns, fontsize=8)
    axis.xaxis.set_ticks_position("top")
    # The tick marks pointed into the space the column labels occupy and marked
    # nothing the label did not already say. They were half of what covered the
    # years in the coefficient map.
    axis.tick_params(axis="x", length=0, pad=4)
    axis.tick_params(axis="y", length=0)

    if column_groups:
        # The group name once above its own columns, instead of repeated in every
        # one and cut off by the column width, and high enough to leave the
        # column labels a band of their own.
        for label, start, stop in column_groups:
            axis.annotate(label, xy=((start + stop) / 2, -2.30), xycoords="data",
                          ha="center", va="bottom", fontsize=8.5, annotation_clip=False)
            axis.annotate("", xy=(start - 0.42, -1.95), xytext=(stop + 0.42, -1.95),
                          xycoords="data",
                          arrowprops={"arrowstyle": "-", "color": "#bbbbbb", "linewidth": 0.9},
                          annotation_clip=False)

    axis.set_yticks(range(row_count), rows, fontsize=7.5)
    if dim_rows:
        # A greyed name marks a row that competed and never won. Without it an
        # empty row cannot be told from a variable that was not in the search.
        for position, label in enumerate(axis.get_yticklabels()):
            if position in dim_rows:
                label.set_color("#999999")

    axis.set_xticks(np.arange(-0.5, column_count, 1), minor=True)
    axis.set_yticks(np.arange(-0.5, row_count, 1), minor=True)
    axis.grid(which="minor", color="#cccccc" if shading is None else "white", linewidth=0.9)
    axis.tick_params(which="minor", length=0)
    for spine in axis.spines.values():
        spine.set_visible(False)

    axis.set_title(title, fontsize=11, pad=title_pad)
    if note:
        # Measured rather than guessed: the note is wrapped to the width the axes
        # actually occupy, so it stays inside the table whether the table has five
        # columns or twenty-four. A fixed character count fixed one and broke the
        # other.
        figure.canvas.draw()
        width = axis.get_window_extent().transformed(figure.dpi_scale_trans.inverted()).width
        characters = max(40, int(width * 72 / (config.FIGURE_NOTE_FONTSIZE * 0.55)))
        axis.annotate(
            textwrap.fill(note, characters),
            xy=(-0.5, row_count - 0.25), xycoords="data", va="top",
            fontsize=config.FIGURE_NOTE_FONTSIZE, color="#555555", annotation_clip=False,
        )
    figure.savefig(out_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(figure)


def _beta_heatmap(
    coefficients: pd.DataFrame,
    dataset: str,
    offset: config.OffsetSpec,
    family: str,
    pair: config.ActorPair,
    candidate_set: str,
    out_path: Path,
) -> None:
    """Todos los betas de una pareja a lo largo de los años, como una sola imagen.

    **Esta es la figura que responde qué encontraron las regresiones.** Una fila
    por candidata, una columna por año, y en cada celda el coeficiente
    estandarizado de esa variable en ese modelo.

    **Cada celda dice una de tres cosas, y distinguirlas es el diseño entero:**

    - con cifra, la variable entró en el modelo de ese año;
    - vacía, compitió ese año y no entró, porque cada modelo lleva dos o tres
      variables sobre treinta unidades;
    - con aspa, no tenía capa ese año, así que no compitió.

    Sin la tercera, 2014 y 2019 se ven iguales en la fila de señalización vertical
    y significan cosas opuestas: una es un resultado y la otra una ausencia de
    dato. El aspa se mete dentro de la celda y no va de esquina a esquina, porque
    a media celda las diagonales de dos años vecinos se tocan y se leen como una
    cinta continua en lugar de como dos cruces.

    **Toda candidata tiene su fila, incluidas las que no ganaron nunca.** Una
    versión anterior listaba solo las seleccionadas alguna vez, así que una
    variable que compitió en todos los modelos y perdió siempre desaparecía,
    indistinguible de una que nunca estuvo en la búsqueda. La primera es un
    resultado: su nombre va en gris y su fila vacía.

    Color divergente centrado en cero, así que el signo se lee antes que la
    magnitud: una fila que sostiene un color a lo largo de los años es una
    variable que mantiene su signo en todos los contextos en los que sobrevive.
    """
    block = coefficients[
        (coefficients[DATASET_COL] == dataset)
        & (coefficients[config.OFFSET_COL] == offset.name)
        & (coefficients[config.FAMILY_COL] == family)
        & (coefficients[PAIR_NAME_COL] == pair.name)
        & (coefficients["TERM"] != "INTERCEPT")
    ]
    valor_col, _, _ = _plotted_coefficient(family)
    # La bolsa más ancha de todos los años, para que la figura tenga las mismas
    # filas en los trece y dos años se puedan comparar poniéndolos al lado.
    variables = list(offset.candidate_predictors(
        config.regression_candidate_pool(candidate_set)))
    if not variables:
        return
    years = list(config.REGRESSION_YEARS)
    selected = set(block["TERM"])

    shading = np.full((len(variables), len(years)), np.nan)
    text = [["" for _ in years] for _ in variables]
    crossed: list[tuple[int, int]] = []
    lookup = block.set_index([config.YEAR_COL, "TERM"])
    for row, name in enumerate(variables):
        for column, year in enumerate(years):
            if name not in config.regression_pool_in(year, candidate_set):
                crossed.append((row, column))
                continue
            try:
                entry = lookup.loc[(year, name)]
            except KeyError:
                continue
            estimate = float(entry[valor_col])
            stars = entry["STARS"]
            shading[row, column] = estimate
            text[row][column] = f"{estimate:.2f}{'' if pd.isna(stars) else stars}"

    span = config.predictor_year_span("VERTICAL_SIGNAGE_DENSITY")
    _grid_table(
        text=text,
        columns=[str(year) for year in years],
        rows=[config.predictor_label_es(name) for name in variables],
        dim_rows={index for index, name in enumerate(variables) if name not in selected},
        crossed_cells=crossed,
        title=(
            f"Coeficientes estandarizados por año · {pair.label_es}\n"
            f"{config.FAMILY_LABELS_ES[family]} · offset: "
            f"{config.OFFSET_LABELS_ES[offset.name]} · conjunto: "
            f"{config.DATASET_LABELS_ES[dataset]} · candidatas: "
            f"{_candidate_label(candidate_set)}\n"
            f"cada celda: {_coefficient_quantity_es(family)}"
        ),
        note=(
            "Aspa: la variable no tenía capa ese año, así que no compitió — no es que "
            f"no se seleccionara. La señalización vertical va de {span[0]} a {span[1]}. "
            "Celda vacía: compitió y no entró, porque cada modelo lleva sólo 2 o 3 "
            "variables sobre 30 unidades. Nombre en gris y fila entera vacía: la "
            "variable compitió en todos los años y no ganó ninguno. "
            "Color divergente centrado en cero, así que el signo se lee antes que la "
            "magnitud. Sin asterisco, el intervalo del 95 % contiene el cero. "
            "* p<0,05  ** p<0,01  *** p<0,001 — inflados por la selección: son el "
            "ganador de una búsqueda sobre todos los subconjuntos declarados."
        ),
        out_path=out_path,
        shading=shading,
        colormap=config.DIVERGING_COLORMAP,
        centre_on_zero=True,
        column_width=1.05,
    )


def _overlap(pairs: str) -> str:
    """How alike the two most alike variables of a model are, if any.

    The field holds `A~B=0.969; C~D=0.711`, so the highest absolute value is what
    a reader needs. Shown as the number rather than as a yes: in the same space,
    it says both that there is a problem and how bad — and 0.71 and 0.97 are very
    different situations that a yes could not tell apart.
    """
    if not isinstance(pairs, str) or not pairs.strip():
        return "—"
    values = [abs(float(part.split("=")[-1])) for part in pairs.split("; ") if "=" in part]
    return f"{max(values):.2f}" if values else "—"


def _models_table(
    models: pd.DataFrame,
    dataset: str,
    offset: str,
    family: str,
    pair: config.ActorPair,
    candidate_set: str,
    out_path: Path,
) -> None:
    """El modelo elegido de una pareja en cada año, y cuánto vale.

    Un bloque a la vez —un conjunto, un offset, una familia y una pareja— porque
    todas las parejas juntas sobre trece años son ciento cuatro filas que nadie
    recorre, y las columnas que identifican el bloque pasan entonces al título en
    vez de repetirse en cada fila.

    **La primera columna cuenta las candidatas de ese año**, y hace aquí lo que el
    aspa hace en la figura de betas. Allá hay una celda que marcar; aquí la
    ausencia se manifiesta como un nombre que no aparece en una lista, y eso no se
    ve: sin la cuenta, comparar 2014 con 2019 no permite distinguir «no estaba
    disponible» de «compitió y no ganó». Además vale por sí sola, porque es el
    tamaño del espacio que la búsqueda recorrió.

    La nota explica las cinco mediciones. Explicaba dos a medias y la comparación
    contra el nulo nada, que es justo la columna por la que preguntó primero un
    lector sin estadística.
    """
    block = models[
        (models[DATASET_COL] == dataset)
        & (models[config.OFFSET_COL] == offset)
        & (models[config.FAMILY_COL] == family)
        & (models[PAIR_NAME_COL] == pair.name)
    ]
    if block.empty:
        return
    spec = next(o for o in config.REGRESSION_OFFSETS if o.name == offset)
    # La dispersión se estima sobre el ajuste de Poisson y es nula en los demás,
    # así que la columna aparece sólo donde tiene algo. Una columna de `nan` es
    # peor que ninguna: se lee como una medición que falló.
    show_dispersion = bool(block["DISPERSION"].notna().any())
    columns = ["Candidatas", "Variables seleccionadas", "AIC", "BIC"]
    if show_dispersion:
        columns.append("Dispersión")
    columns += ["Moran", "Solapamiento", "Mejor que\nsin variables"]

    rows: list[str] = []
    text: list[list[str]] = []
    for year in config.REGRESSION_YEARS:
        entry = block[block[config.YEAR_COL] == year]
        rows.append(str(year))
        available = str(len(spec.candidate_predictors(
            config.regression_pool_in(year, candidate_set))))
        if entry.empty:
            text.append([available, "sin modelo"] + [""] * (len(columns) - 2))
            continue
        row = entry.iloc[0]
        names = ", ".join(
            config.predictor_label_es(name) for name in row["PREDICTORS"].split(", ") if name
        )
        cells = [available, names, f"{row['AIC']:.1f}", f"{row['BIC']:.1f}"]
        if show_dispersion:
            cells.append(f"{row['DISPERSION']:.2f}" if np.isfinite(row["DISPERSION"]) else "—")
        cells += [
            f"{row['MORANS_I']:.3f}",
            _overlap(row["COLLINEAR_PAIRS"]),
            "sí" if row["BEATS_NULL"] else "NO",
        ]
        text.append(cells)

    span = config.predictor_year_span("VERTICAL_SIGNAGE_DENSITY")
    _grid_table(
        text=text,
        columns=columns,
        rows=rows,
        title=(
            f"Modelos seleccionados por año · {pair.label_es}\n"
            f"{config.FAMILY_LABELS_ES[family]} · offset: "
            f"{config.OFFSET_LABELS_ES[offset]} · conjunto: "
            f"{config.DATASET_LABELS_ES[dataset]} · candidatas: "
            f"{_candidate_label(candidate_set)}"
        ),
        note=(
            "Candidatas: cuántas variables compitieron ese año. Son una menos donde la "
            f"señalización vertical no tiene capa, que es fuera de {span[0]}-{span[1]}."
            "   ·   "
            "AIC y BIC califican el ajuste y sólo se comparan dentro de una misma familia y "
            "un mismo offset; más bajo es mejor.   ·   Moran mide si las unidades vecinas "
            "quedan con residuales parecidos: por encima de 0,2 el corte transversal deja "
            "estructura espacial que el modelo de panel tendrá que recoger.   ·   "
            "Solapamiento: qué tan parecidas son las dos variables más parecidas del modelo. "
            f"Por encima de {config.CORRELATION_HIGH_THRESHOLD:.2f} la regresión no puede "
            "saber cuál de las dos es la responsable y reparte el efecto entre ellas, así que "
            "la predicción sigue valiendo pero el coeficiente de cada una por separado no.   "
            "·   Mejor que sin variables: si el modelo ajusta mejor que uno con sólo el "
            "offset y ninguna variable del entorno. Un «NO» significa que esas dos o tres "
            "características urbanas no aportan sobre la sola exposición."
        ),
        out_path=out_path,
        column_width=1.75,
        wrap=28,
    )


def _unit_label(code: str, names: dict[str, str]) -> str:
    """`03-Arborizadora`: the number without its prefix, and the name beside it.

    A column of codes alone made a reader hold thirty of them in their head to
    know which unit a row was about.
    """
    return f"{code.removeprefix('UPL')}-{names.get(code, '')}"


def render_figures(
    data: dict[str, pd.DataFrame],
    tables: dict[str, pd.DataFrame],
    candidate_set: str,
    log: RunLog,
) -> int:
    """Every figure, in a tree whose path is the question it answers.

    `principal/<familia>/<conjunto>/<offset>/` holds what a reader opens: the fit,
    the coefficients and the models of one combination. `coeficientes/` holds the
    panel that carries all three offsets at once and therefore belongs to no
    single one of them. `principal/entradas/` holds what went in, which depends on
    neither offset nor family.

    The year is in the file name and not in a folder, because it is the dimension
    that gets compared rather than fixed.
    """
    root = log.run_dir / config.FIGURES_SUBDIR / "regressions"
    principal = root / "principal"
    written = 0
    families = (config.OLS_FAMILY, config.POISSON_FAMILY, config.NEGATIVE_BINOMIAL_FAMILY)

    for family in families:
        for dataset in data:
            branch = principal / config.FAMILY_PATHS[family] / config.DATASET_SLUGS[dataset]
            for offset in config.REGRESSION_OFFSETS:
                folder = branch / config.OFFSET_SLUGS[offset.name]

                # Los ajustes en su carpeta: uno por año, trece archivos que se
                # recorren en orden.
                ajustes = folder / "ajustes"
                ajustes.mkdir(parents=True, exist_ok=True)
                for year in config.REGRESSION_YEARS:
                    _fit_panel(
                        tables["predictions"], tables["models"], dataset, offset.name,
                        family, year, candidate_set, ajustes / f"ajuste__{year}.png",
                    )
                    written += 1

                # Y una carpeta por pareja con sus dos figuras. Antes eran dos
                # archivos que cubrían las ocho parejas a la vez; con trece años
                # eso son 104 columnas en el mapa de betas y 104 filas en la tabla
                # de modelos, y ninguna de las dos se lee.
                for pair in config.REGRESSION_PAIRS:
                    carpeta = folder / "parejas" / config.PAIR_SLUGS[pair.name]
                    carpeta.mkdir(parents=True, exist_ok=True)
                    _beta_heatmap(
                        tables["coefficients"], dataset, offset, family, pair,
                        candidate_set, carpeta / "betas.png",
                    )
                    _models_table(
                        tables["models"], dataset, offset.name, family, pair,
                        candidate_set, carpeta / "modelos.png",
                    )
                    written += 2

                # Y la frecuencia de selección de esa especificación, al lado de
                # `ajustes/` y `parejas/`: las tres son los tres cortes posibles
                # de los mismos 104 modelos. Ajustes corta por año, parejas por
                # pareja, y ésta no corta, resume. D53.
                written += _render_summary(
                    tables, dataset, offset.name, family, candidate_set, folder)

            # The coefficient panel carries all three offsets at once, so its path
            # stops at the dataset: it belongs to none of them.
            folder = root / "coeficientes" / config.FAMILY_PATHS[family] / config.DATASET_SLUGS[dataset]
            folder.mkdir(parents=True, exist_ok=True)
            for year in config.REGRESSION_YEARS:
                _coefficient_panel(
                    tables["coefficients"], dataset, family, year, candidate_set,
                    folder / f"coeficientes__{year}.png",
                )
                written += 1

    written += _render_inputs(data, log, principal / "entradas")

    # Las dos que cruzan familias y offsets, que por eso no caben en ninguna de
    # sus carpetas. Una por conjunto de siniestralidad: el corregido con rho
    # existe para contrastar y no para reportar, así que sumarlos describiría
    # medio estudio con datos que el estudio no reporta.
    for dataset in data:
        written += _render_comparison(
            tables, dataset, candidate_set,
            principal / "comparacion" / config.DATASET_SLUGS[dataset])
    _write_readme(tables, candidate_set, principal)

    log.info("wrote %d regression figures under %s/regressions/", written, config.FIGURES_SUBDIR)
    return written


def _column_header(name: str) -> str:
    """El nombre de una candidata sobre su unidad, en tres líneas fijas.

    **El nombre se reparte siempre en dos líneas antes de añadir la unidad**, de
    modo que todas las unidades quedan a la misma altura tengan el nombre una
    palabra o dos. Sin eso, la unidad de «Andén» sube una línea respecto a la de
    «Vía arterial» y la fila de unidades deja de leerse como una fila.

    Se probó la alternativa de dibujar la unidad aparte, más pequeña y en gris, y
    se descartó: una etiqueta de marca de eje admite un solo estilo, así que la
    unidad habría que anotarla a una altura fija mientras las etiquetas bajan lo
    que necesiten, y las dos se pisan en los nombres de dos palabras.
    """
    words = config.predictor_label_es(name).split(" ")
    wrapped = words[0] + "\n" + " ".join(words[1:])
    return f"{wrapped}\n{config.predictor_unit_es(name)}"


# -- la dispersión de las explicativas ---------------------------------------
# El estilo de caja va declarado una vez porque lo comparten las tres figuras de
# dispersión, y una caja dibujada distinta en una de ellas se leería como si
# midiera otra cosa.
_BOX_STYLE = {
    "patch_artist": True,
    "boxprops": {"facecolor": config.BOX_FACE_COLOR,
                 "edgecolor": config.REGRESSION_POINT_COLOR, "linewidth": 1.2},
    "medianprops": {"color": config.REGRESSION_POINT_COLOR, "linewidth": 2},
    "whiskerprops": {"color": config.REGRESSION_POINT_COLOR, "linewidth": 1.2},
    "capprops": {"color": config.REGRESSION_POINT_COLOR, "linewidth": 1.2},
    "flierprops": {"marker": "o", "markersize": 4, "markerfacecolor": "none",
                   "markeredgecolor": config.REGRESSION_POINT_COLOR, "markeredgewidth": 1.1},
}

_BOX_NOTE = (
    "La caja va del primer al tercer cuartil, así que contiene la mitad central de las "
    "unidades; la raya de dentro es la mediana. Los bigotes llegan al dato más lejano "
    "dentro de vez y media el ancho de la caja, y lo que queda fuera se dibuja suelto: "
    "son los atípicos por la regla de Tukey."
)


def _tukey_outliers(values: np.ndarray) -> np.ndarray:
    """Qué observaciones caen fuera, que es lo que un boxplot dibuja suelto."""
    first, third = np.percentile(values, [25, 75])
    spread = third - first
    return (values < first - 1.5 * spread) | (values > third + 1.5 * spread)


def _figure_note(figure, text: str) -> None:
    figure.text(0.5, 0.01, text, ha="center", va="bottom",
                fontsize=config.FIGURE_NOTE_FONTSIZE, color=config.FIGURE_NOTE_COLOR,
                wrap=True)


def _render_dispersion(per_unit: pd.DataFrame, names: dict[str, str], folder: Path) -> int:
    """Las tres figuras de dispersión de las variables explicativas.

    Pedidas por la asesora del panel a través de Olmos — «un boxplot de la
    dispersión de estas»— y las tres entran porque cada una contesta algo que las
    otras dos no: la primera compara las doce formas entre sí, la segunda
    conserva las unidades reales y nombra las atípicas, y la tercera es la única
    que enseña que la caja de la ciclorruta no sólo sube sino que se ensancha.

    **Una fila por unidad y no una por fila de la tabla.** La tabla de regresión
    tiene 3 120 filas y 30 unidades, porque una predictora está repetida 104
    veces; sin deduplicar, las tres figuras afirmarían 3 120 observaciones donde
    hay 30. El deduplicado llega hecho en `per_unit`.
    """
    folder.mkdir(parents=True, exist_ok=True)
    year = config.PREDICTOR_FIGURE_YEAR
    block = per_unit[per_unit[config.YEAR_COL] == year].sort_values(config.AREA_CODE_COL)
    variables = list(config.REGRESSION_URBAN_CANDIDATES)
    codes = block[config.AREA_CODE_COL].to_numpy()

    about_year = (
        f"Treinta unidades, {year}. Diez de las doce no cambian en el tiempo, así que sólo "
        "la ciclorruta y la señalización vertical dependen del año; se usa "
        f"{year} porque es el más reciente en el que las doce están medidas."
    )

    # -- una: las doce en un eje, estandarizadas ----------------------------
    # El pipeline centra y escala cada columna antes de ajustar, así que este eje
    # es el que el modelo ve y no una normalización inventada para que quepan.
    standardised = {}
    for name in variables:
        values = block[name].to_numpy(dtype=float)
        standardised[name] = (values - values.mean()) / values.std(ddof=0)
    spread = {name: float(np.subtract(*np.percentile(standardised[name], [75, 25])))
              for name in variables}
    order = sorted(variables, key=lambda name: spread[name])

    figure, axis = plt.subplots(figsize=(11.0, 6.4))
    axis.axvline(0, color=config.GRID_CROSS_COLOR, linewidth=1, zorder=1)
    axis.boxplot([standardised[name] for name in order],
                 orientation="horizontal", widths=0.62, **_BOX_STYLE)
    axis.set_yticks(range(1, len(order) + 1),
                    [config.predictor_label_es(name) for name in order], fontsize=9.5)
    axis.set_xlabel("desviaciones estándar respecto a la media de la variable", fontsize=9)
    axis.tick_params(axis="y", length=0)
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.set_title(
        f"Dispersión de las variables explicativas · {year}\n"
        "las doce en la escala en la que los modelos se ajustan", fontsize=12.5)
    _figure_note(
        figure,
        _BOX_NOTE + "   " + about_year
        + " Cada variable está centrada en su media y dividida por su desviación estándar, "
          "que es la transformación que el ajuste aplica antes de estimar. Ordenadas por el "
          "ancho de la caja: abajo las de mitad central más apretada, que son justamente las "
          "que tienen unas pocas unidades muy por encima del resto.")
    figure.tight_layout(rect=(0, 0.10, 1, 1))
    figure.savefig(folder / f"estandarizadas__{year}.png",
                   dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(figure)

    # -- dos: doce paneles, cada uno en sus unidades ------------------------
    figure, axes = plt.subplots(4, 3, figsize=(12.6, 9.6))
    for axis, name in zip(axes.ravel(), variables):
        values = block[name].to_numpy(dtype=float)
        axis.boxplot(values, orientation="horizontal", widths=0.5, **_BOX_STYLE)
        outside = _tukey_outliers(values)
        # Los nombres en una línea dentro del panel y no uno sobre cada punto:
        # con cinco atípicas, tres de ellas casi pegadas, las etiquetas
        # individuales se montan unas sobre otras y no se lee ninguna.
        if outside.any():
            ordered = np.argsort(values[outside])
            listed = ", ".join(names[code] for code in codes[outside][ordered])
            axis.text(0.0, 0.97, f"atípicas: {listed}", transform=axis.transAxes,
                      ha="left", va="top", fontsize=7,
                      color=config.REGRESSION_POINT_COLOR)
        axis.set_title(f"{config.predictor_label_es(name)}\n"
                       f"{config.predictor_unit_es(name)}", fontsize=9.5)
        axis.set_yticks([])
        axis.tick_params(axis="x", labelsize=8)
        for side in ("top", "right", "left"):
            axis.spines[side].set_visible(False)
        axis.set_ylim(0.55, 1.75)
    figure.suptitle(f"Dispersión de las variables explicativas · {year}\n"
                    "cada una en sus propias unidades", fontsize=13)
    _figure_note(
        figure,
        _BOX_NOTE + "   " + about_year
        + " Cada panel tiene su propio eje porque las doce no comparten escala. Las unidades "
          "atípicas van nombradas en cada panel, en el orden en que aparecen de izquierda a "
          "derecha.")
    figure.tight_layout(rect=(0, 0.055, 1, 0.94))
    figure.savefig(folder / f"en_sus_unidades__{year}.png",
                   dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(figure)

    # -- tres: las dos con serie, una caja por año --------------------------
    with_series = [name for name in variables if config.predictor_year_span(name) is not None]
    figure, axes = plt.subplots(len(with_series), 1, figsize=(11.0, 7.2))
    for axis, name in zip(np.atleast_1d(axes), with_series):
        first_year, last_year = config.predictor_year_span(name)
        years = [year for year in config.REGRESSION_YEARS if first_year <= year <= last_year]
        axis.boxplot(
            [per_unit[per_unit[config.YEAR_COL] == each][name].to_numpy(dtype=float)
             for each in years],
            orientation="vertical", widths=0.6, **_BOX_STYLE)
        axis.set_xticks(range(1, len(years) + 1), [str(each) for each in years], fontsize=9)
        axis.set_ylabel(config.predictor_unit_es(name), fontsize=9)
        axis.set_title(f"{config.predictor_label_es(name)} · {first_year}-{last_year}",
                       fontsize=11)
        axis.tick_params(axis="y", labelsize=8)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
    figure.suptitle("Las dos variables explicativas con serie anual\n"
                    "una caja por año, sobre las mismas treinta unidades", fontsize=13)
    _figure_note(
        figure,
        _BOX_NOTE
        + "   Las otras diez no cambian en el tiempo y no admiten esta figura. Lo que se lee "
          "aquí no es cuánta red hay sino cómo se reparte entre unidades: una caja que sube y "
          "se ensancha es red que crece de forma desigual.")
    figure.tight_layout(rect=(0, 0.07, 1, 0.93))
    figure.savefig(folder / "con_serie_anual.png", dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(figure)

    return 3


def _render_inputs(data: dict[str, pd.DataFrame], log: RunLog, folder: Path) -> int:
    """What went in, which depends on no offset and no family — except one thing.

    The predictors are properties of the unit: the same block for every pair, and
    for both casualty datasets. **The responses are not**, and an earlier version
    drew them from whichever dataset came first without saying which, so the
    rho-corrected responses were shown nowhere. There is one per dataset now and
    the title names it.

    **Two folders and not one.** Thirteen years turn what used to be four files
    into thirty-nine, and a reader looking for a response then reads past
    thirteen predictor tables to find it. `predictoras/` holds one file per year;
    `respuestas/<conjunto>/` holds one per year as well, and the dataset moves
    out of the file name because the folder already carries it.

    **The year decides the columns.** A year without a signage layer has no
    column for it, rather than a column of blanks, so the absence shows on the
    figure itself. One consequence, so it does not surprise: with one column
    fewer the cells widen, and 2014 does not align with 2019 if the two are
    opened side by side.
    """
    # `predictoras/` gana un nivel. Con las tablas por año, los doce histogramas,
    # la correlación, la tabla maestra y los tres boxplots serían veintinueve
    # archivos de cuatro clases distintas revueltos en una carpeta.
    predictors_dir = folder / "predictoras"
    by_year = predictors_dir / "por_anio"
    by_year.mkdir(parents=True, exist_ok=True)
    written = 0
    first = next(iter(data.values()))
    names = dict(zip(first[config.AREA_CODE_COL], first[config.AREA_NAME_COL]))
    per_unit = first.drop_duplicates(subset=[config.AREA_CODE_COL, config.YEAR_COL])

    for year in config.REGRESSION_YEARS:
        candidates = config.regression_candidates_in(year)
        block = first[first[config.YEAR_COL] == year].drop_duplicates(subset=config.AREA_CODE_COL)
        values = block[list(candidates)].to_numpy(dtype=float)
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
        decimals = [
            config.predictor_decimals(float(np.nanmax(values[:, index])))
            for index in range(values.shape[1])
        ]
        _grid_table(
            text=[
                [f"{value:.{decimals[index]}f}" for index, value in enumerate(row)]
                for row in values
            ],
            columns=[_column_header(name) for name in candidates],
            rows=[_unit_label(code, names) for code in block[config.AREA_CODE_COL]],
            title=f"Predictoras por unidad · {year}",
            note="Mismo bloque para las ocho parejas y para los dos conjuntos: son "
                 "propiedades de la unidad. Color por columna, de su propio mínimo a su "
                 "propio máximo, así que compara hacia abajo y no hacia los lados. "
                 "La segunda línea del encabezado es la unidad: todas están por unidad "
                 "de área, cuatro como proporción de ella y las demás por kilómetro "
                 f"cuadrado. Variables {config.series_available_in(year)}.",
            out_path=by_year / f"predictoras__{year}.png",
            shading=shading,
            column_width=1.05,
        )
        written += 1

    # El tercer conjunto de figuras, el de las doce que compiten, dibujado en el
    # año declarado. Va aquí y no en la etapa de predictoras porque es ésta la
    # que tiene un año, y con un año la ciclorruta y la señalización entran como
    # las demás en vez de quedar fuera del dibujo. D53 y sección 13.4.
    figure_year = config.PREDICTOR_FIGURE_YEAR
    wide = per_unit[per_unit[config.YEAR_COL] == figure_year].sort_values(config.AREA_CODE_COL)
    candidate_names = list(config.CANDIDATE_FIGURE_SET.predictor_names)
    correlation = wide[candidate_names].corr(method=config.CORRELATION_METHOD.lower())
    written += predictors.render_figure_set(
        config.CANDIDATE_FIGURE_SET, wide, correlation, log, figures_dir=predictors_dir)

    written += _render_dispersion(per_unit, names, predictors_dir / "dispersion")

    for dataset, frame in data.items():
        responses_dir = folder / "respuestas" / config.DATASET_SLUGS[dataset]
        responses_dir.mkdir(parents=True, exist_ok=True)
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
                rows=[_unit_label(code, names) for code in wide.index],
                title=f"Partes afectadas por unidad y pareja · {year} · "
                      f"conjunto {config.DATASET_LABELS_ES[dataset]}",
                note="Un cero es una observación de ausencia, no un dato que falte. Color por "
                     "columna: cada pareja contra su propio máximo.",
                out_path=responses_dir / f"respuestas__{year}.png",
                shading=shading,
                column_width=1.05,
            )
            written += 1
    return written


def _render_summary(
    tables: dict[str, pd.DataFrame],
    dataset: str,
    offset: str,
    family: str,
    candidate_set: str,
    folder: Path,
) -> int:
    """La frecuencia de selección **dentro de una especificación**, no sobre todo.

    Una especificación es una familia, un conjunto de siniestralidad y un offset.
    Dentro de ella lo único que varía son las ocho parejas y los trece años, que
    sí son contextos independientes; cruzar esa frontera no suma. Se midió que el
    orden de las doce se mueve hasta siete puestos de doce entre offsets, así que
    una cuenta que los junte promedia justo lo que más discrepa — y la figura que
    lo hacía llamaba evidencia al promedio. D53.

    La columna «Offsets» no aparece aquí, porque dentro de un bloque hay un solo
    offset y una columna de un valor repetido no es una medición.

    `De cuántos pudo` se dibuja siempre porque es el divisor del porcentaje que
    tiene al lado, y un porcentaje cuyo divisor no se ve no se puede comprobar:
    la señalización vertical compite en nueve de los trece años y por eso su
    denominador es 72 donde el de las demás es 104.
    """
    folder.mkdir(parents=True, exist_ok=True)
    models = tables["models"]
    coefficients = tables["coefficients"]
    block_models = models[
        (models[DATASET_COL] == dataset)
        & (models[config.OFFSET_COL] == offset)
        & (models[config.FAMILY_COL] == family)
    ]
    if block_models.empty:
        return 0
    block_terms = coefficients[
        (coefficients[DATASET_COL] == dataset)
        & (coefficients[config.OFFSET_COL] == offset)
        & (coefficients[config.FAMILY_COL] == family)
    ]
    frequency = selection_frequency(block_terms, block_models, candidate_set)
    total = len(block_models)

    columns = ["Veces\nelegida", "De cuántos\npudo", "% de los\nque pudo",
               "Signo +", "Signo −", "Significativa"]

    text: list[list[str]] = []
    for _, row in frequency.iterrows():
        cells = [f"{int(row['SELECTED'])}", f"{int(row['AVAILABLE'])}"]
        cells += [
            f"{100 * row['SELECTED_SHARE']:.1f}%",
            f"{int(row['POSITIVE'])}",
            f"{int(row['NEGATIVE'])}",
            f"{int(row['SIGNIFICANT'])}",
        ]
        text.append(cells)

    _grid_table(
        text=text,
        columns=columns,
        rows=[config.predictor_label_es(name) for name in frequency["TERM"]],
        title=(
            f"Frecuencia de selección · {total} modelos\n"
            f"{config.FAMILY_LABELS_ES[family]} · offset: "
            f"{config.OFFSET_LABELS_ES[offset]} · conjunto: "
            f"{config.DATASET_LABELS_ES[dataset]} · candidatas: "
            f"{_candidate_label(candidate_set)}"
        ),
        note="Los modelos de esta tabla comparten familia, respuesta, denominador y bolsa "
             "de candidatas: lo único que varía entre ellos son las ocho parejas y los "
             f"{len(config.REGRESSION_YEARS)} años. Por eso una variable que gana aquí gana "
             "en contextos que de verdad son independientes, y por eso la cuenta no cruza "
             "la frontera de la especificación: entre offsets el orden de las doce se mueve "
             "hasta siete puestos de doce.   ·   Cada una se divide entre los modelos en "
             "los que pudo ser elegida, y ese divisor va a la vista: la señalización "
             "vertical sólo está en la bolsa en los años cuya capa existe.   ·   Un signo "
             "que se sostiene vale más que cualquiera de los valores p, que están inflados "
             "por la selección.",
        out_path=folder / "frecuencia_seleccion.png",
        column_width=1.35,
    )
    return 1


def _families_compared(tables: dict[str, pd.DataFrame]) -> tuple[float, float, int, int, float]:
    """Las cinco cifras con las que el LÉEME defiende que Poisson es evidencia.

    Se miden aquí y no se escriben a mano. Estaban escritas a mano, de la corrida
    de tres años, y un archivo generado que cita cifras de otra corrida es peor
    que uno que no cite ninguna: dice ser el de esta.

    Los coeficientes de las dos familias se comparan emparejados por la celda a la
    que pertenecen —conjunto, offset, pareja, año y término—, porque cada familia
    elige su propio modelo y sólo los términos que las dos eligieron son
    comparables.
    """
    coefficients = tables["coefficients"]
    keys = [DATASET_COL, config.OFFSET_COL, PAIR_NAME_COL, config.YEAR_COL, "TERM"]
    poisson = coefficients[coefficients[config.FAMILY_COL] == config.POISSON_FAMILY]
    negative = coefficients[coefficients[config.FAMILY_COL] == config.NEGATIVE_BINOMIAL_FAMILY]
    paired = poisson.merge(negative, on=keys, suffixes=("_P", "_NB"))

    moved = float(
        (paired["COEFFICIENT_STANDARDISED_P"] - paired["COEFFICIENT_STANDARDISED_NB"])
        .abs().median()
    )
    wider = float((paired["STANDARD_ERROR_NB"] / paired["STANDARD_ERROR_P"]).median())
    models = tables["models"]
    dispersion = models[models[config.FAMILY_COL] == config.POISSON_FAMILY]["DISPERSION"]
    return (
        moved,
        wider,
        int(paired["SIGNIFICANT_P"].sum()),
        int(paired["SIGNIFICANT_NB"].sum()),
        float(dispersion.median()),
    )


def _render_comparison(
    tables: dict[str, pd.DataFrame],
    dataset: str,
    candidate_set: str,
    folder: Path,
) -> int:
    """Las dos figuras que cruzan familias, y que por eso no caben en ninguna.

    La primera contesta con qué familia quedarse. La segunda, si la conclusión
    depende de la especificación, que es lo que el capítulo necesita saber antes
    de reportar un coeficiente sin condicionarlo.

    **Van por conjunto de siniestralidad y no juntándolos.** El corregido con rho
    existe para contrastar y no para reportar, así que una figura que los sume
    describe medio estudio con datos que el estudio no reporta.

    **Y van por offset y no promediándolos**, que es lo que las hace legibles:
    bajo el offset de ambas exposiciones, mínimos cuadrados da un R² de conteos
    mediano de −8,83 y cien de sus 104 modelos lo tienen negativo, mientras que
    bajo el de población da 0,67 y sólo uno. Una tabla que promediara los tres
    enseñaría una cifra intermedia que no le pasa a ningún modelo.
    """
    folder.mkdir(parents=True, exist_ok=True)
    families = (config.OLS_FAMILY, config.POISSON_FAMILY, config.NEGATIVE_BINOMIAL_FAMILY)
    cell = [DATASET_COL, config.OFFSET_COL, PAIR_NAME_COL, config.YEAR_COL, config.FAMILY_COL]

    models = tables["models"][tables["models"][DATASET_COL] == dataset].copy()
    predictions = tables["predictions"][tables["predictions"][DATASET_COL] == dataset]
    coefficients = tables["coefficients"][
        (tables["coefficients"][DATASET_COL] == dataset)
        & (tables["coefficients"]["TERM"] != "INTERCEPT")
    ]
    if models.empty:
        return 0

    # El R² sobre conteos es lo único comparable entre las tres familias, porque
    # el pipeline devuelve las tres predicciones en escala de conteo: mínimos
    # cuadrados multiplica su tasa ajustada por el offset.
    fitted = {
        key: _count_r_squared(group["OBSERVED"].to_numpy(), group["PREDICTED"].to_numpy())
        for key, group in predictions.groupby(cell)
    }
    models["R2_COUNTS"] = [fitted[key] for key in map(tuple, models[cell].values)]

    # -- una: con qué familia quedarse --------------------------------------
    rows, text = [], []
    for offset in config.REGRESSION_OFFSETS:
        for family in families:
            block = models[(models[config.OFFSET_COL] == offset.name)
                           & (models[config.FAMILY_COL] == family)]
            if block.empty:
                continue
            drawn = predictions[(predictions[config.OFFSET_COL] == offset.name)
                                & (predictions[config.FAMILY_COL] == family)]
            impossible = int((drawn["PREDICTED"] < 0).sum())
            dispersion = block["DISPERSION"].median()
            if family == config.OLS_FAMILY:
                assumption = "no supone\ndistribución"
            elif family == config.POISSON_FAMILY:
                assumption = f"NO: dispersión\n{dispersion:.2f} y supone 1"
            else:
                assumption = "sí: estima la\ndispersión"
            rows.append(f"{config.OFFSET_SHORT_LABELS_ES[offset.name]}\n"
                        f"{config.FAMILY_SHORT_LABELS_ES[family]}")
            text.append([
                f"{len(block)}",
                f"{impossible:,} de {len(drawn):,}".replace(",", ".") if impossible else "ninguna",
                assumption,
                f"{block['R2_COUNTS'].median():.3f}",
                f"{int((block['R2_COUNTS'] < 0).sum())}",
                f"{int(block['BEATS_NULL'].sum())} de {len(block)}",
                f"{int((block['MORANS_I'].abs() > config.MORAN_REPORTING_THRESHOLD).sum())}",
            ])

    # El AIC de las dos familias de conteo sí se compara, y es lo que zanja entre
    # ellas. Se mide aquí para decirlo con cifras y no de memoria.
    left = models[models[config.FAMILY_COL] == config.POISSON_FAMILY].set_index(cell[:4])["AIC"]
    right = models[
        models[config.FAMILY_COL] == config.NEGATIVE_BINOMIAL_FAMILY].set_index(cell[:4])["AIC"]
    shared = left.index.intersection(right.index)
    gap = (right.loc[shared] - left.loc[shared]).astype(float)

    _grid_table(
        text=text,
        columns=["Modelos", "Predicciones\nimposibles", "¿Se cumple\nsu supuesto?",
                 "R² de conteos\nmediano", "R² < 0", "Mejor que\nsin variables", "Moran > 0,2"],
        rows=rows,
        title=(f"Con qué familia quedarse · conjunto: {config.DATASET_LABELS_ES[dataset]}\n"
               f"candidatas: {_candidate_label(candidate_set)}"),
        note="Se lee en este orden y no por la mejor cifra. Primero: ¿puede el modelo "
             "producir algo imposible? Mínimos cuadrados ajusta la tasa y predice conteos "
             "negativos, así que es una aproximación lineal y no un modelo de la respuesta. "
             "Segundo: ¿se cumple su supuesto? Poisson supone que la dispersión vale uno y "
             "no vale uno, así que sus errores estándar salen pequeños y sus intervalos y "
             "valores p están mal en la dirección favorable. Sólo tercero, cuánto ajusta."
             "   ·   Leída por el R² se elige Poisson, y sería un error: lo que está roto "
             "en Poisson no es el ajuste sino la incertidumbre.   ·   El AIC no compara "
             "mínimos cuadrados con las otras dos, porque ajusta otra variable. Entre "
             "Poisson y la binomial negativa sí, y la binomial negativa gana en "
             f"{int((gap < 0).sum())} de {len(shared)} celdas de este conjunto, con una "
             f"diferencia mediana de {gap.median():.1f}.   ·   Se separa por offset porque "
             "el orden entre familias cambia con el denominador.",
        out_path=folder / "familias.png",
        column_width=1.55,
        wrap=16,
    )

    # -- dos: si la conclusión depende de la especificación -----------------
    columns, counts = [], []
    for offset in config.REGRESSION_OFFSETS:
        for family in families:
            block = coefficients[(coefficients[config.OFFSET_COL] == offset.name)
                                 & (coefficients[config.FAMILY_COL] == family)]
            columns.append(f"{config.OFFSET_SHORT_LABELS_ES[offset.name]}\n"
                           f"{config.FAMILY_SHORT_LABELS_ES[family]}")
            counts.append(block["TERM"].value_counts())

    agreement = (pd.DataFrame(counts).T
                 .reindex(config.REGRESSION_URBAN_CANDIDATES).fillna(0).astype(int))
    agreement.columns = columns
    # Ordenadas por el total, que es el único orden que no privilegia una columna.
    agreement = agreement.loc[agreement.sum(axis=1).sort_values(ascending=False).index]
    ranks = agreement.rank(ascending=False, method="min").astype(int)
    values = agreement.to_numpy(dtype=float)
    highest = np.where(values.max(axis=0) > 0, values.max(axis=0), 1.0)

    _grid_table(
        text=[[f"{int(value)}\n{rank}.º" for value, rank in zip(row, row_ranks)]
              for row, row_ranks in zip(values, ranks.to_numpy())],
        columns=columns,
        rows=[config.predictor_label_es(name) for name in agreement.index],
        title=(f"¿Cambia la conclusión según la especificación? · conjunto: "
               f"{config.DATASET_LABELS_ES[dataset]}\n"
               "veces que cada variable fue elegida, y su puesto, en cada una de las nueve"),
        note="Los encabezados van abreviados: «modo afectado» es la exposición del modo "
             "afectado, «ambos modos» la de los dos modos multiplicadas y «población» la "
             "población residente.   ·   El color es la cuenta de la columna contra su "
             "propio máximo, así que compara hacia abajo.   ·   Una fila de color parejo es "
             "una variable cuya importancia no depende de cómo se especifique el modelo, y "
             "es la que el capítulo puede reportar sin condicionar. Una fila que cambia de "
             "color entre columnas es una variable cuyo resultado depende del denominador o "
             "de la familia, y eso hay que decirlo al reportarla.",
        out_path=folder / "acuerdo.png",
        shading=values / highest,
        colormap=config.MASTER_TABLE_COLORMAP,
        column_width=1.55,
    )
    return 2


def _write_readme(
    tables: dict[str, pd.DataFrame],
    candidate_set: str,
    folder: Path,
) -> None:
    """What is where, which path the study reports, and which run this is.

    The candidate set goes at the top and not in a footnote. Every figure in the
    folder says it in its own subtitle, but this file is what somebody reads
    first, and the two runs are otherwise indistinguishable from the outside:
    same tree, same file names, same number of figures.
    """
    moved, wider, significant_p, significant_nb, dispersion = _families_compared(tables)
    # Formateadas antes del bloque de texto, y no dentro de él. Escribir
    # `f"…{x:.3f}".replace(".", ",")` en medio de una concatenación implícita
    # aplica el reemplazo a **todos los literales pegados antes**, que es como
    # cuatro puntos de este archivo se volvieron comas.
    moved_es = f"{moved:.3f}".replace(".", ",")
    wider_es = f"{wider:.2f}".replace(".", ",")
    dispersion_es = f"{dispersion:.2f}".replace(".", ",")
    # Millares con punto, que es lo que lee quien lee el resto del archivo. El
    # separador de Python es la coma y en español eso son decimales: «1,941»
    # dice uno coma nueve cuatro uno donde quiere decir mil novecientos cuarenta y uno.
    poisson_es = f"{significant_p:,}".replace(",", ".")
    negative_es = f"{significant_nb:,}".replace(",", ".")
    primary = (
        f"{config.FAMILY_PATHS[config.PRIMARY_FAMILY]}/"
        f"{config.DATASET_SLUGS[config.PRIMARY_DATASET]}/"
        f"{config.OFFSET_SLUGS[config.PRIMARY_OFFSET]}/"
    )
    folder.mkdir(parents=True, exist_ok=True)
    # Las dos frases van por separado porque son dos cosas distintas, y hasta D52
    # parecían una sola: cuál reporta el estudio lo dice el conjunto por defecto,
    # y qué preguntas no tienen respuesta aquí lo dice si admite los restos.
    declarado = config.CANDIDATE_SETS_BY_NAME[candidate_set]
    # Envuelto y no cortado a mano: la etiqueta se interpola en medio de la frase,
    # así que su longitud decide dónde cae el corte y escribirlo a mano deja una
    # línea corta en cuanto la etiqueta cambia de largo.
    cual_es = (
        "Es la que el estudio reporta.\n"
        if candidate_set == config.DEFAULT_CANDIDATE_SET
        else textwrap.fill(
            "NO es la que el estudio reporta, que es la de candidatas "
            f"{_candidate_label(config.DEFAULT_CANDIDATE_SET)}. Al citarla hay que "
            "nombrarla, o un lector la tomará por el resultado del estudio.",
            width=72,
        ) + "\n"
    )
    que_no_contesta = (
        ""
        if declarado.admits_offset_quantities
        else "\nAquí ninguna cantidad de offset compite, así que dos preguntas no\n"
             "tienen respuesta en esta corrida: ningún coeficiente es una elasticidad,\n"
             "y la exposición del modo afectado no aparece en ningún modelo del offset\n"
             "de población. Las dos salen de la corrida con with-leftovers.\n"
             "La comparación entre las dos la hace tools/comparar_candidatas.py.\n"
    )
    (folder / "LEEME.txt").write_text(
        f"ESTA CORRIDA: candidatas {_candidate_label(candidate_set)}\n"
        "\n"
        + cual_es
        + que_no_contesta
        + "\n"
        "CÓMO ESTÁ ORGANIZADO\n"
        "\n"
        "  <familia>/<conjunto>/<offset>/\n"
        "      ajustes/                      un ajuste por año\n"
        "      parejas/<pareja>/             betas y modelos de esa pareja\n"
        "  entradas/predictoras/             una tabla de predictoras por año\n"
        "  entradas/respuestas/<conjunto>/   las partes afectadas, por año\n"
        "  frecuencia_seleccion.png          qué variable gana más veces, sobre todo\n"
        "\n"
        "Las dos figuras que cruzan los años —betas y modelos— van por pareja y no\n"
        "todas juntas: con trece años, las ocho parejas a la vez son 104 columnas en\n"
        "el mapa de betas y 104 filas en la tabla de modelos, y ninguna se lee.\n"
        "\n"
        "Los paneles de coeficientes están fuera de esta carpeta, en coeficientes/,\n"
        "porque cada uno lleva los tres offsets a la vez y no pertenece a ninguno.\n"
        "\n"
        "LA COMBINACIÓN QUE EL ESTUDIO REPORTA\n"
        "\n"
        f"  {primary}\n"
        "\n"
        "  conjunto observado      el corregido con rho existe para contrastar,\n"
        "                          no para reportar\n"
        "  exposición del modo     es el offset que declara el anteproyecto\n"
        "  binomial negativa       es la familia que respalda la sobredispersión\n"
        "\n"
        "POISSON ESTÁ COMO EVIDENCIA, NO COMO RESULTADO\n"
        "\n"
        "Los coeficientes de las dos familias del GLM casi no se mueven: la\n"
        f"diferencia mediana es de {moved_es}. Lo que se mueve es la confianza. El\n"
        f"error estándar de la binomial negativa es {wider_es} veces el de Poisson, y\n"
        f"por eso Poisson declara significativos {poisson_es} de los coeficientes\n"
        f"que las dos familias comparten, donde la binomial negativa declara\n"
        f"{negative_es}. {significant_p - significant_nb} que Poisson daba por "
        "establecidos no lo están.\n"
        "\n"
        "La columna Dispersión de poisson/.../parejas/<pareja>/modelos.png es la\n"
        "medición que lo justifica: uno significa que Poisson es correcto, y la\n"
        f"mediana es {dispersion_es}.\n"
        "\n"
        "LOS VALORES p NO SON VALORES p HONESTOS\n"
        "\n"
        "Se elige el mejor de cientos de modelos y después se reporta la\n"
        "significancia del ganador, lo cual la infla por construcción. Lo que sí\n"
        "vale es un signo que se sostiene en contextos independientes, que es lo\n"
        "que muestra frecuencia_seleccion.png.\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def report(tables: dict[str, pd.DataFrame], candidate_set: str, log: RunLog) -> None:
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

    # Aquí se imprimía la frecuencia de selección sobre toda la corrida. **Ya no**:
    # esa cuenta promedia offsets y familias cuyos resultados se contradicen —el
    # orden de las doce se mueve hasta siete puestos de doce entre offsets—, así
    # que decirla en el registro afirmaría lo que D53 retira de las figuras. La
    # cuenta vive ahora en dieciocho figuras y en la tabla exportada, una por
    # especificación, que es donde es legítima.
    #
    # Lo que ocupa su sitio es la comparación entre familias, que es lo que un
    # lector del registro necesita para saber si la corrida salió sana.
    families = (config.OLS_FAMILY, config.POISSON_FAMILY, config.NEGATIVE_BINOMIAL_FAMILY)
    cell = [DATASET_COL, config.OFFSET_COL, PAIR_NAME_COL, config.YEAR_COL, config.FAMILY_COL]
    predictions = tables["predictions"]
    fitted = {
        key: _count_r_squared(group["OBSERVED"].to_numpy(), group["PREDICTED"].to_numpy())
        for key, group in predictions.groupby(cell)
    }
    counts_r2 = np.array([fitted[key] for key in map(tuple, models[cell].values)])

    header = (
        f"{'dataset':<10}  {'offset':<16}  {'family':<18}  {'impossible':>10}  "
        f"{'median R2':>9}  {'R2 < 0':>6}  {'beat null':>9}"
    )
    lines = [header, "-" * len(header)]
    for dataset in models[DATASET_COL].unique():
        for offset in config.REGRESSION_OFFSETS:
            for family in families:
                mask = (
                    (models[DATASET_COL] == dataset)
                    & (models[config.OFFSET_COL] == offset.name)
                    & (models[config.FAMILY_COL] == family)
                )
                block = models[mask]
                if block.empty:
                    continue
                drawn = predictions[
                    (predictions[DATASET_COL] == dataset)
                    & (predictions[config.OFFSET_COL] == offset.name)
                    & (predictions[config.FAMILY_COL] == family)
                ]
                scores = counts_r2[mask.to_numpy()]
                lines.append(
                    f"{dataset:<10}  {offset.name:<16}  {family:<18}  "
                    f"{int((drawn['PREDICTED'] < 0).sum()):>10}  "
                    f"{np.median(scores):>9.3f}  {int((scores < 0).sum()):>6}  "
                    f"{int(block['BEATS_NULL'].sum()):>9}"
                )
    log.table(
        "which family to keep, by dataset and offset — read in this order: whether the "
        "model can predict something impossible, then whether its assumption holds "
        "(the dispersion above), and only then how well it fits:",
        "\n".join(lines),
    )

    log.warn(
        "the p-values of this run are the winner of a search over every declared subset, "
        "so they are inflated by the selection itself and are not honest p-values. The "
        "European study being replicated has the same defect. What is worth reading "
        "instead is how often a variable is selected **within one specification** — one "
        "family, one dataset, one offset — which is what the eighteen selection-frequency "
        "figures and the exported table hold. Across specifications it is not a count but "
        "a comparison, and that is what principal/comparacion/ is for. D53"
    )

