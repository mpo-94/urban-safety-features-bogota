"""The panel stage: the unit-by-year models the cross-sections were the first step towards.

**This file starts with its estimator and nothing else, on purpose.** The correlated random
effects model the thesis declares (section 4.8.3, D67) is a negative binomial with a normal
random intercept per unit, and statsmodels has no such estimator: its mixed GLMs are Bayesian
approximations and its negative binomial has no random effect. So the likelihood is written here,
integrated over the random intercept by Gauss-Hermite quadrature, and it is verified on its own —
against statsmodels where the two must coincide, on simulated data with known parameters, and on
the number of quadrature nodes — before anything reads the data with it. The design, the two
models and the validation on the last year come after, once the estimator has passed
(`deliverables/informes/panel-primer-intento.md`, decision 2).

The model, for the rows of unit u:

    y_ut ~ NB2(mu_ut, alpha),   log mu_ut = offset_ut + x_ut' beta + a_u,   a_u ~ N(0, sigma^2)

with NB2 the parametrisation statsmodels uses, Var(y) = mu + alpha mu^2. The unit's likelihood
is the integral over a_u of the product of its rows' probabilities and the normal density of a_u,
which has no closed form. It is taken by adaptive Gauss-Hermite quadrature: with a_u* the peak of
the unit's integrand, s_u its spread from the curvature there, and the Hermite nodes z_i and
weights w_i,

    a_ui = a_u* + sqrt(2) s_u z_i
    L_u  = sqrt(2) s_u sum_i w_i exp(z_i^2) phi(a_ui; 0, sigma) prod_t NB(y_ut; exp(offset_ut + x_ut' beta + a_ui), alpha)

The parameters are beta, log alpha and log sigma, so the optimiser never has to keep the two
scale parameters positive. `tools/verificar_estimador_panel.py` is what says the estimator works,
and why the quadrature is adaptive.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import optimize, special, stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.sandwich_covariance import cov_cluster

try:  # regular package import
    from src import config, loading, predictors, regressions
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import loading  # type: ignore[no-redef]
    import predictors  # type: ignore[no-redef]
    import regressions  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]

# Enough nodes that the log-likelihood stops moving at the scale of the unit effects measured
# here; the verification tool checks this on every fit it makes rather than trusting the number.
DEFAULT_QUADRATURE_NODES = 30
# The largest absolute component of the gradient at which a fit counts as converged.
GRADIENT_TOLERANCE = 1e-4
# At most this many Newton steps after BFGS, only while the gradient is above a tenth of the tolerance.
NEWTON_POLISH_STEPS = 20


@dataclass
class RandomInterceptFit:
    """A fitted negative binomial with a normal random intercept per unit."""

    names: tuple[str, ...]
    params: np.ndarray  # beta, then log alpha, then log sigma
    log_likelihood: float
    covariance: np.ndarray  # from the inverse Hessian
    covariance_clustered: np.ndarray  # sandwich on the unit scores
    converged: bool
    iterations: int
    nodes: int
    units: int
    observations: int
    message: str = ""
    posterior_exp_intercept: np.ndarray = field(default_factory=lambda: np.empty(0))

    @property
    def beta(self) -> np.ndarray:
        return self.params[:-2]

    @property
    def alpha(self) -> float:
        return float(np.exp(self.params[-2]))

    @property
    def sigma(self) -> float:
        return float(np.exp(self.params[-1]))

    @property
    def aic(self) -> float:
        return 2 * len(self.params) - 2 * self.log_likelihood

    @property
    def bic(self) -> float:
        return np.log(self.observations) * len(self.params) - 2 * self.log_likelihood

    def standard_errors(self, clustered: bool = True) -> np.ndarray:
        covariance = self.covariance_clustered if clustered else self.covariance
        return np.sqrt(np.clip(np.diag(covariance), 0.0, None))


class RandomInterceptNB:
    """The likelihood, its gradient and its fit, for one design.

    `groups` labels each row with its unit. Rows of a unit need not be contiguous; they are
    gathered once here so every evaluation is a sum over units.
    """

    def __init__(self, y, X, offset, groups, names=None, nodes: int = DEFAULT_QUADRATURE_NODES):
        self.y = np.asarray(y, dtype=float)
        self.X = np.asarray(X, dtype=float)
        self.offset = np.asarray(offset, dtype=float)
        codes, self.group_index = np.unique(np.asarray(groups), return_inverse=True)
        self.group_codes = codes
        self.n_groups = len(codes)
        self.names = tuple(names) if names is not None else tuple(f"x{j}" for j in range(self.X.shape[1]))
        if len(self.names) != self.X.shape[1]:
            raise ValueError("one name per column of the design")
        if not (len(self.y) == len(self.X) == len(self.offset) == len(self.group_index)):
            raise ValueError("the response, the design, the offset and the groups must have one row each")
        nodes_z, weights = np.polynomial.hermite.hermgauss(nodes)
        self.nodes = nodes
        self.node_z = nodes_z
        # Weights for an expectation under N(0, 1) once the node is scaled by sqrt(2).
        self.log_node_weight = np.log(weights / np.sqrt(np.pi))
        self.log_factorial = special.gammaln(self.y + 1.0)

    def _unit_modes(self, linear: np.ndarray, alpha: float, sigma: float, iterations: int = 50):
        """The peak of each unit's integrand in a, and the spread of the peak.

        **The nodes are adaptive, and they have to be.** With thirteen rows per unit and counts in
        the hundreds, the integrand is a narrow spike in a, and nodes fixed around zero straddle it:
        on the panel's shape the fixed-node log-likelihood moved by 2.5 between 20, 30 and 60
        nodes. Centring each unit's nodes on its own peak, at the width the curvature gives, is the
        standard remedy (the adaptive quadrature lme4 calls nAGQ). Newton on all units at once.
        """
        y = self.y
        a = np.zeros(self.n_groups)
        for _ in range(iterations):
            mu = np.exp(np.clip(linear + a[self.group_index], -50.0, 50.0))
            first = np.bincount(self.group_index, (y - mu) / (1.0 + alpha * mu), self.n_groups) - a / sigma**2
            second = (-np.bincount(self.group_index, mu * (1.0 + alpha * y) / (1.0 + alpha * mu) ** 2,
                                   self.n_groups) - 1.0 / sigma**2)
            step = -first / second
            a = a + np.clip(step, -2.0, 2.0)  # damped, so a far start cannot overshoot
            if np.max(np.abs(step)) < 1e-10:
                break
        mu = np.exp(np.clip(linear + a[self.group_index], -50.0, 50.0))
        second = (-np.bincount(self.group_index, mu * (1.0 + alpha * y) / (1.0 + alpha * mu) ** 2,
                               self.n_groups) - 1.0 / sigma**2)
        return a, 1.0 / np.sqrt(-second)

    # Row by node arrays: every row of the data evaluated at every node of its unit's intercept.
    def _node_terms(self, params: np.ndarray):
        beta, log_alpha, log_sigma = params[:-2], params[-2], params[-1]
        alpha, sigma = np.exp(log_alpha), np.exp(log_sigma)
        size = 1.0 / alpha  # the NB "r", the number of failures in the gamma-Poisson mixture
        linear = self.offset + self.X @ beta  # (rows,)
        mode, spread = self._unit_modes(linear, alpha, sigma)
        # The intercept at each node of each unit, centred on the unit's peak: (units, nodes).
        intercept = mode[:, None] + np.sqrt(2.0) * spread[:, None] * self.node_z[None, :]
        eta = linear[:, None] + intercept[self.group_index]  # (rows, nodes)
        # Clipped so a wild step of the optimiser gives a huge loss and not an overflow.
        mu = np.exp(np.clip(eta, -50.0, 50.0))
        y = self.y[:, None]
        log_pmf = (special.gammaln(y + size) - special.gammaln(size) - self.log_factorial[:, None]
                   + size * (np.log(size) - np.log(size + mu)) + y * (eta - np.log(size + mu)))
        # What the change of variable leaves on each node: the normal density of the intercept, the
        # e^{z^2} that undoes the Hermite weight, and the Jacobian sqrt(2) * spread.
        log_prior = -0.5 * np.log(2 * np.pi) - log_sigma - intercept**2 / (2 * sigma**2)
        log_change = (self.node_z**2)[None, :] + np.log(np.sqrt(2.0) * spread)[:, None]
        return alpha, size, sigma, intercept, mu, log_pmf, log_prior + log_change

    def _per_unit(self, params: np.ndarray):
        """Log-likelihood per unit, and the posterior weight of each node within each unit."""
        alpha, size, sigma, intercept, mu, log_pmf, log_node = self._node_terms(params)
        # Sum the rows of each unit at each node: (units, nodes).
        by_unit = np.zeros((self.n_groups, self.nodes))
        np.add.at(by_unit, self.group_index, log_pmf)
        # The Hermite weights carry e^{-z^2}; log_node_weight holds log(w / sqrt(pi)), so sqrt(pi)
        # goes back in to leave the plain weight.
        joint = by_unit + log_node + (self.log_node_weight + 0.5 * np.log(np.pi))[None, :]
        log_l = special.logsumexp(joint, axis=1)
        posterior = np.exp(joint - log_l[:, None])
        return log_l, posterior, (alpha, size, sigma, intercept, mu)

    def log_likelihood(self, params: np.ndarray) -> float:
        return float(self._per_unit(params)[0].sum())

    def unit_scores(self, params: np.ndarray) -> np.ndarray:
        """The gradient of each unit's log-likelihood, one row per unit."""
        log_l, posterior, (alpha, size, sigma, intercept, mu) = self._per_unit(params)
        y = self.y[:, None]
        # Derivatives at fixed node positions in a. The adaptive centre moves with the parameters,
        # but where the quadrature is exact the integral does not depend on where the nodes sit, so
        # this is the gradient of the integral; the verification checks it against differences of
        # the adaptive likelihood itself.
        # d log NB / d eta, at every row and node.
        d_eta = (y - mu) / (1.0 + alpha * mu)
        # d log NB / d size, then through size = exp(-log alpha).
        d_size = (special.digamma(y + size) - special.digamma(size) + np.log(size) + 1.0
                  - np.log(size + mu) - (size + y) / (size + mu))
        d_log_alpha = -size * d_size
        # sigma enters only through the normal density of the intercept: d/d log sigma of
        # -log sigma - a^2 / (2 sigma^2) is a^2 / sigma^2 - 1, per unit and node.
        d_log_sigma = intercept**2 / sigma**2 - 1.0  # (units, nodes)
        # Posterior weight of each row's node, taken from the row's unit.
        weight = posterior[self.group_index]  # (rows, nodes)
        scores = np.zeros((self.n_groups, len(params)))
        row_beta = (weight * d_eta).sum(axis=1)[:, None] * self.X  # (rows, k)
        np.add.at(scores[:, :-2], self.group_index, row_beta)
        np.add.at(scores[:, -2], self.group_index, (weight * d_log_alpha).sum(axis=1))
        scores[:, -1] = (posterior * d_log_sigma).sum(axis=1)
        return scores

    def gradient(self, params: np.ndarray) -> np.ndarray:
        return self.unit_scores(params).sum(axis=0)

    def hessian(self, params: np.ndarray, step: float = 1e-5) -> np.ndarray:
        """Central differences of the analytic gradient, symmetrised."""
        k = len(params)
        hessian = np.zeros((k, k))
        for j in range(k):
            shift = np.zeros(k)
            shift[j] = step * max(1.0, abs(params[j]))
            hessian[:, j] = (self.gradient(params + shift) - self.gradient(params - shift)) / (2 * shift[j])
        return (hessian + hessian.T) / 2

    def posterior_exp_intercept(self, params: np.ndarray) -> np.ndarray:
        """E[exp(a_u) | the unit's data], what a prediction for that unit multiplies by."""
        _, posterior, (_, _, _, intercept, _) = self._per_unit(params)
        return (posterior * np.exp(intercept)).sum(axis=1)

    def fit(self, start: np.ndarray, fixed_log_sigma: float | None = None,
            max_iterations: int = 2000) -> RandomInterceptFit:
        """Maximise the likelihood from `start`, optionally holding log sigma fixed.

        Holding it fixed is what the verification uses to take sigma towards zero, where the
        model must become the pooled negative binomial.
        """
        start = np.asarray(start, dtype=float)
        free = np.ones(len(start), dtype=bool)
        if fixed_log_sigma is not None:
            free[-1] = False
            start = start.copy()
            start[-1] = fixed_log_sigma

        def full(theta):
            params = start.copy()
            params[free] = theta
            return params

        result = optimize.minimize(
            lambda theta: -self.log_likelihood(full(theta)),
            start[free],
            jac=lambda theta: -self.gradient(full(theta))[free],
            method="BFGS",
            options={"maxiter": max_iterations, "gtol": 1e-6},
        )
        params = full(result.x)
        # Newton steps on the same likelihood when BFGS stops short of the tolerance. Its line search
        # gives up at the last decimals of a log-likelihood of thousands, and on the panel one fit of
        # 54 (motorcycle against car, both signages) stopped at a gradient of 1.7e-4. A step with the
        # curvature finishes what the line search left; it changes the optimiser's last metres, not
        # the estimator, and is halved until the likelihood does not fall.
        for _ in range(NEWTON_POLISH_STEPS):
            gradient = self.gradient(params)[free]
            if np.max(np.abs(gradient)) < GRADIENT_TOLERANCE / 10:
                break
            curvature = self.hessian(params)[np.ix_(free, free)]
            if not np.all(np.isfinite(curvature)):
                break
            step = np.linalg.lstsq(-curvature, gradient, rcond=None)[0]
            current = self.log_likelihood(params)
            for _ in range(30):
                candidate = params.copy()
                candidate[free] = params[free] + step
                if np.isfinite(self.log_likelihood(candidate)) and self.log_likelihood(candidate) >= current - 1e-9:
                    params = candidate
                    break
                step = step / 2
            else:
                break
        # BFGS often stops with "precision loss" when the line search can no longer improve a
        # log-likelihood of thousands at the last decimals; measured on the simulated panels, the
        # gradient is then below 1e-4 and the maximum is reached. Convergence is judged on the
        # gradient, not on the optimiser's flag.
        largest_gradient = float(np.max(np.abs(self.gradient(params)[free])))
        converged = bool(result.success) or largest_gradient < GRADIENT_TOLERANCE
        hessian = self.hessian(params)[np.ix_(free, free)]
        # A curvature that is not finite means the optimiser wandered off; the fit is reported as
        # not converged instead of stopping the run on a matrix that cannot be inverted.
        if not (np.all(np.isfinite(hessian)) and np.all(np.isfinite(params))):
            converged = False
            hessian = np.where(np.isfinite(hessian), hessian, 0.0) - np.eye(len(hessian))
        bread = np.linalg.pinv(-hessian)
        scores = self.unit_scores(params)[:, free]
        # The units are independent in the model, so the sandwich on unit scores is the
        # covariance clustered by unit; with 29 units it is reported beside the model's own.
        meat = scores.T @ scores
        covariance = np.full((len(params), len(params)), np.nan)
        clustered = np.full((len(params), len(params)), np.nan)
        covariance[np.ix_(free, free)] = bread
        clustered[np.ix_(free, free)] = bread @ meat @ bread
        return RandomInterceptFit(
            names=self.names + ("log_alpha", "log_sigma"),
            params=params,
            log_likelihood=self.log_likelihood(params),
            covariance=covariance,
            covariance_clustered=clustered,
            converged=converged,
            iterations=int(result.nit),
            nodes=self.nodes,
            units=self.n_groups,
            observations=len(self.y),
            message=f"{result.message} (largest gradient {largest_gradient:.1e})",
            posterior_exp_intercept=self.posterior_exp_intercept(params),
        )


# ---------------------------------------------------------------------------
# The panel route: design, the two models, what each reports, and the validation
# ---------------------------------------------------------------------------
#
# Everything below follows the D67 amendment of 2026-10-27, committed before the first
# estimate. The design is the cross-sections' (the same rows, exposure and candidates, read
# from the run that exported it), extended with the horizontal marking and with the delays;
# nothing that decides what a cell counts is rebuilt here.

DESIGN_FILES = {
    config.CORRECTED_DATASET: f"{config.ANALYSIS_PREFIX}__regression_data__{config.CORRECTED_DATASET}.parquet",
    config.OBSERVED_DATASET: f"{config.ANALYSIS_PREFIX}__regression_data.parquet",
}
RESPONSE = "AFFECTED_PARTIES"
EXPOSURE = "EXPOSURE_AFFECTED"
CYCLEWAY = "CYCLEWAY_LENGTH_DENSITY"
VERTICAL = "VERTICAL_SIGNAGE_DENSITY"
HORIZONTAL = config.PANEL_HORIZONTAL_MARKING
# The ten that do not change in time: every candidate but the two with a series.
CONSTANTS = tuple(c for c in config.REGRESSION_URBAN_CANDIDATES if c not in (CYCLEWAY, VERTICAL))

FE_NB, FE_POISSON, CRE, MUNDLAK, REFERENCE = "FE_NB", "FE_POISSON", "CRE", "MUNDLAK", "REFERENCE"
WITHIN, BETWEEN, CONSTANT, YEAR_EFFECT = "WITHIN", "BETWEEN", "CONSTANT", "YEAR"
LEVEL_OBSERVED, LEVEL_CARRIED = "OBSERVED_TOTAL", "CARRIED_PREVIOUS_YEAR"
Z = 1.959963984540054  # the two-sided 95 % normal quantile


def label_es(variable: str) -> str:
    return (config.PANEL_HORIZONTAL_MARKING_LABEL_ES if variable == HORIZONTAL
            else config.predictor_label_es(variable))


def read_design(log: RunLog) -> tuple[dict[str, pd.DataFrame], str]:
    """The cross-sections' design for both sets, from the most recent run that exported it."""
    frames, runs = {}, set()
    for dataset, filename in DESIGN_FILES.items():
        run_dir = config.run_directory_holding(filename)
        frames[dataset] = pd.read_parquet(run_dir / config.DATA_SUBDIR / filename)
        runs.add(run_dir.name)
        log.info("%s design read from %s", dataset, run_dir.name)
    if len(runs) != 1:
        raise ValueError(f"the two designs come from different runs: {sorted(runs)}")
    return frames, runs.pop()


def estimating_units(design: pd.DataFrame, log: RunLog):
    """The polygons of the units the design carries, in the layer's order, with their area."""
    units = predictors.prepare_units(loading.load_territorial_units(log))
    kept = units[units[config.AREA_CODE_COL].isin(design[config.AREA_CODE_COL])].reset_index(drop=True)
    if len(kept) != design[config.AREA_CODE_COL].nunique():
        raise ValueError("the unit layer does not carry every unit of the design")
    return kept


def horizontal_marking(units, log: RunLog) -> pd.DataFrame:
    """Painted kilometres per square kilometre, per unit and year, and their sum from 2017.

    Measured with the pipeline's own line measurement, the one `tools/demarcacion_por_unidad.py`
    uses, so the two can be checked against each other. A unit with nothing painted in a year is
    a zero, not a gap: every unit appears every year.
    """
    rows = []
    base = units[[config.AREA_CODE_COL, config.AREA_UNIT_KM2_COL]]
    for year in config.PANEL_HORIZONTAL_MARKING_YEARS:
        measured = predictors.measure_line_layer(config.PANEL_HORIZONTAL_MARKING_LAYER, units, log, year)
        year_table = base.merge(measured, on=config.AREA_CODE_COL, how="left").fillna(
            {config.PREDICTOR_MEASURE_COL: 0.0})
        year_table[config.YEAR_COL] = year
        rows.append(year_table)
    table = pd.concat(rows, ignore_index=True).sort_values([config.AREA_CODE_COL, config.YEAR_COL])
    table["KM_PAINTED"] = table[config.PREDICTOR_MEASURE_COL]
    table["FLOW"] = table["KM_PAINTED"] / table[config.AREA_UNIT_KM2_COL]
    table["CUMULATIVE"] = table.groupby(config.AREA_CODE_COL)["FLOW"].cumsum()
    return table[[config.AREA_CODE_COL, config.YEAR_COL, "KM_PAINTED", "FLOW", "CUMULATIVE"]].reset_index(drop=True)


def unit_year_variables(design: pd.DataFrame, marking: pd.DataFrame) -> pd.DataFrame:
    """Every variable the panel reads, one row per unit and year, in natural units and delayed.

    - The cycleway is the mean of the year and the previous one (D67); 2012 has no previous year
      and enters with its own value (the amendment).
    - The vertical signage of year t is the stock at the close of t - 1 (D47 dates each value at
      its year's close).
    - The horizontal marking of year t is what was painted from 2017 to the close of t - 1, the
      stock less the unknown 2016 stock that the unit effect absorbs, if what was painted is new.
    - The ten constants as they are.
    """
    columns = [config.AREA_CODE_COL, config.YEAR_COL, CYCLEWAY, VERTICAL, *CONSTANTS]
    per_unit = design[columns].drop_duplicates()
    if per_unit.duplicated([config.AREA_CODE_COL, config.YEAR_COL]).any():
        raise ValueError("a unit-year carries different predictor values in different pairs")
    per_unit = per_unit.sort_values([config.AREA_CODE_COL, config.YEAR_COL]).reset_index(drop=True)
    grouped = per_unit.groupby(config.AREA_CODE_COL)
    # Shifts are only valid between consecutive years, so the years are checked to be complete.
    if not (grouped[config.YEAR_COL].diff().dropna() == 1).all():
        raise ValueError("the design's years are not consecutive within every unit")
    previous_cycleway = grouped[CYCLEWAY].shift(1)
    per_unit[CYCLEWAY] = np.where(previous_cycleway.notna(), (per_unit[CYCLEWAY] + previous_cycleway) / 2,
                                  per_unit[CYCLEWAY])
    per_unit[VERTICAL] = grouped[VERTICAL].shift(1)
    lagged = marking[[config.AREA_CODE_COL, config.YEAR_COL, "CUMULATIVE", "FLOW"]].copy()
    lagged[config.YEAR_COL] = lagged[config.YEAR_COL] + 1  # the close of t - 1 accompanies year t
    lagged = lagged.rename(columns={"CUMULATIVE": HORIZONTAL, "FLOW": HORIZONTAL + "_FLOW"})
    return per_unit.merge(lagged, on=[config.AREA_CODE_COL, config.YEAR_COL], how="left")


@dataclass
class PanelData:
    """One panel of one set: its rows, and each variable's mean and deviation over them."""

    spec: config.PanelSpec
    dataset: str
    rows: pd.DataFrame  # one row per pair, unit and year, with standardised copies ("Z_" prefix)
    mean: dict[str, float]
    sd: dict[str, float]
    remaining_share: dict[str, float]  # variance left after unit and year means, natural units


def two_way_remaining_share(table: pd.DataFrame, column: str) -> float:
    """The share of a variable's variance left once unit and year means are removed.

    The panel is balanced inside its years, so one pass of each demeaning is exact.
    """
    x = table[column].astype(float)
    unit = x.groupby(table[config.AREA_CODE_COL]).transform("mean")
    year = x.groupby(table[config.YEAR_COL]).transform("mean")
    remaining = x - unit - year + x.mean()
    total = float(((x - x.mean()) ** 2).sum())
    return float((remaining**2).sum()) / total if total > 0 else 0.0


def build_panel(design: pd.DataFrame, variables: pd.DataFrame, spec: config.PanelSpec, dataset: str,
                log: RunLog) -> PanelData:
    """The rows of one panel, checked to be the full grid, and standardised over its unit-years."""
    used = [*spec.varying, *CONSTANTS]
    keep = [config.AREA_CODE_COL, config.YEAR_COL, "PAIR", RESPONSE, EXPOSURE]
    rows = design[keep][design[config.YEAR_COL].isin(spec.years)].merge(
        variables, on=[config.AREA_CODE_COL, config.YEAR_COL], how="left")
    units = design[config.AREA_CODE_COL].nunique()
    pairs = design["PAIR"].nunique()
    expected = units * len(spec.years) * pairs
    missing = int(rows[used].isna().any(axis=1).sum())
    log.record(
        f"build the {spec.key} panel, {dataset}",
        rows_in=expected,
        rows_out=len(rows) - missing,
        changes=[(len(rows) - missing - expected, "unit-years with a variable missing")],
        notes=[f"{units} units x {len(spec.years)} years ({spec.first_year}-{spec.last_year}) x {pairs} pairs; "
               f"time-varying: {', '.join(spec.varying)}"],
    )
    if missing or len(rows) != expected:
        raise ValueError(f"the {spec.key} panel is not the full grid: {len(rows)} rows, {missing} incomplete")
    if (rows[EXPOSURE] <= 0).any():
        raise ValueError(f"the {spec.key} panel has a non-positive exposure, which has no logarithm")
    per_unit_year = rows.drop_duplicates([config.AREA_CODE_COL, config.YEAR_COL])
    mean = {v: float(per_unit_year[v].mean()) for v in used}
    # Population deviation over the panel's unit-years, as the cross-sections standardise (D65).
    sd = {v: float(per_unit_year[v].std(ddof=0)) for v in used}
    for v in used:
        rows["Z_" + v] = (rows[v] - mean[v]) / sd[v]
    remaining = {v: two_way_remaining_share(per_unit_year, v) for v in spec.varying}
    return PanelData(spec, dataset, rows.sort_values(["PAIR", config.AREA_CODE_COL, config.YEAR_COL])
                     .reset_index(drop=True), mean, sd, remaining)


# -- the designs of the two models ------------------------------------------------------------

def _indicators(values: pd.Series, levels: list, prefix: str) -> pd.DataFrame:
    """One column per level but the first, which the intercept carries."""
    return pd.DataFrame({f"{prefix}[{level}]": (values == level).astype(float).to_numpy()
                         for level in levels[1:]}, index=values.index)


def fe_design(rows: pd.DataFrame, varying: tuple[str, ...], units: list, years: list) -> pd.DataFrame:
    """Intercept, an indicator per unit and per year, and the standardised time-varying variables."""
    parts = [pd.DataFrame({"INTERCEPT": 1.0}, index=rows.index),
             _indicators(rows[config.AREA_CODE_COL], units, "UNIT"),
             _indicators(rows[config.YEAR_COL], years, "YEAR")]
    if varying:
        parts.append(rows[["Z_" + v for v in varying]].rename(columns=lambda c: c[2:]))
    return pd.concat(parts, axis=1)


def unit_means(rows: pd.DataFrame, varying: tuple[str, ...]) -> pd.DataFrame:
    """Each unit's mean of each standardised time-varying variable, over the rows given."""
    return rows.groupby(config.AREA_CODE_COL)[["Z_" + v for v in varying]].mean()


def cre_design(rows: pd.DataFrame, varying: tuple[str, ...], means: pd.DataFrame, years: list) -> pd.DataFrame:
    """Intercept, year indicators, within deviations, unit means and the ten constants.

    `means` are computed on the training rows only, so a held-out year never enters the term that
    compares units.
    """
    parts = [pd.DataFrame({"INTERCEPT": 1.0}, index=rows.index), _indicators(rows[config.YEAR_COL], years, "YEAR")]
    unit_mean = means.reindex(rows[config.AREA_CODE_COL]).set_index(rows.index)
    for v in varying:
        parts.append(pd.DataFrame({f"W[{v}]": rows["Z_" + v] - unit_mean["Z_" + v],
                                   f"B[{v}]": unit_mean["Z_" + v]}, index=rows.index))
    parts.append(rows[["Z_" + c for c in CONSTANTS]].rename(columns=lambda c: f"C[{c[2:]}]"))
    return pd.concat(parts, axis=1)


@dataclass
class ModelFit:
    """What the panel keeps of one fitted model."""

    model: str
    names: list[str]
    params: pd.Series  # the linear coefficients, by name
    cov_clustered: pd.DataFrame
    cov_model: pd.DataFrame
    log_likelihood: float
    parameters: int  # counted as AIC counts them, dispersion and sigma included
    observations: int
    alpha: float
    sigma: float
    converged: bool
    message: str
    fitted: np.ndarray  # the conditional mean of every row
    unit_scale: pd.Series | None = None  # CRE: E[exp(a_u) | data], by unit

    @property
    def aic(self) -> float:
        return 2 * self.parameters - 2 * self.log_likelihood

    @property
    def bic(self) -> float:
        return np.log(self.observations) * self.parameters - 2 * self.log_likelihood


def _largest_score(result) -> float:
    try:
        return float(np.max(np.abs(result.model.score(result.params))))
    except Exception:  # noqa: BLE001 - a model whose score cannot be evaluated has not converged
        return float("inf")


def fit_negative_binomial(y, X: pd.DataFrame, offset, groups, model: str) -> ModelFit:
    """The pooled NB2 with an offset, with errors clustered by unit: the random-intercept estimator
    with sigma held at 1e-6.

    **Not statsmodels' NegativeBinomial, and the reason was measured.** With 29 unit and 12 year
    indicators it returned NaN in the first pair tried (pedestrian against motorcycle, main panel)
    by Newton and by BFGS. Held at sigma near zero the estimator above is exactly the pooled
    negative binomial, which `tools/verificar_estimador_panel.py` checks against statsmodels to six
    decimals of log-likelihood; its analytic gradient converges where statsmodels' did not.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        poisson = sm.GLM(y, X, family=sm.families.Poisson(), offset=offset).fit()
    names = list(X.columns)
    k = len(names)
    estimator = RandomInterceptNB(y, X.to_numpy(), offset, groups, names=names)
    start = np.r_[poisson.params.to_numpy(), np.log(0.1), np.log(POOLED_SIGMA)]
    fit = estimator.fit(start, fixed_log_sigma=np.log(POOLED_SIGMA))
    return ModelFit(
        model=model, names=names, params=pd.Series(fit.beta, index=names),
        cov_clustered=pd.DataFrame(fit.covariance_clustered[:k, :k], index=names, columns=names),
        cov_model=pd.DataFrame(fit.covariance[:k, :k], index=names, columns=names),
        log_likelihood=fit.log_likelihood, parameters=k + 1, observations=len(y),
        alpha=fit.alpha, sigma=float("nan"), converged=fit.converged, message=fit.message,
        fitted=np.exp(np.asarray(offset) + X.to_numpy() @ fit.beta))


# Sigma for the pooled fits: small enough that the random intercept vanishes, as the verification
# tool's pooled-limit check uses it.
POOLED_SIGMA = 1e-6


def fit_poisson_fe(y, X: pd.DataFrame, offset, groups) -> ModelFit:
    """Poisson with the same indicators: the fixed-effects estimator with no incidental-parameter bias."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.GLM(y, X, family=sm.families.Poisson(), offset=offset)
        plain = model.fit()
        clustered = model.fit(cov_type="cluster", cov_kwds={"groups": np.asarray(groups)})
    names = list(X.columns)
    return ModelFit(
        model=FE_POISSON, names=names, params=plain.params, cov_clustered=clustered.cov_params(),
        cov_model=plain.cov_params(), log_likelihood=float(plain.llf), parameters=len(names),
        observations=len(y), alpha=0.0, sigma=float("nan"), converged=bool(plain.converged),
        message="", fitted=np.asarray(plain.fittedvalues))


def fit_cre(y, X: pd.DataFrame, offset, groups, start_from: ModelFit) -> ModelFit:
    """The random-intercept negative binomial of the top of this module, started from Mundlak."""
    estimator = RandomInterceptNB(y, X.to_numpy(), offset, groups, names=list(X.columns))
    start = np.r_[start_from.params.to_numpy(), np.log(max(start_from.alpha, 1e-4)), np.log(0.3)]
    fit = estimator.fit(start)
    names = list(X.columns)
    k = len(names)
    scale = pd.Series(fit.posterior_exp_intercept, index=estimator.group_codes)
    linear = np.asarray(offset) + X.to_numpy() @ fit.beta
    fitted = np.exp(linear) * scale.reindex(np.asarray(groups)).to_numpy()
    return ModelFit(
        model=CRE, names=names, params=pd.Series(fit.beta, index=names),
        cov_clustered=pd.DataFrame(fit.covariance_clustered[:k, :k], index=names, columns=names),
        cov_model=pd.DataFrame(fit.covariance[:k, :k], index=names, columns=names),
        log_likelihood=fit.log_likelihood, parameters=len(fit.params), observations=fit.observations,
        alpha=fit.alpha, sigma=fit.sigma, converged=fit.converged, message=fit.message, fitted=fitted,
        unit_scale=scale)


@dataclass
class PairFits:
    """The models of one pair in one panel: on every year, and on the training years."""

    pair: str
    fe: ModelFit
    poisson: ModelFit
    mundlak: ModelFit
    cre: ModelFit
    # The validation: each model fitted without the held-out year, and its prediction of it.
    predictions: pd.DataFrame


def fit_pair(panel: PanelData, pair: str, log: RunLog) -> PairFits:
    rows = panel.rows[panel.rows["PAIR"] == pair].reset_index(drop=True)
    spec = panel.spec
    units = sorted(rows[config.AREA_CODE_COL].unique())
    years = list(spec.years)
    y = rows[RESPONSE].to_numpy(dtype=float)
    offset = np.log(rows[EXPOSURE].to_numpy(dtype=float))
    groups = rows[config.AREA_CODE_COL].to_numpy()

    X_fe = fe_design(rows, spec.varying, units, years)
    fe = fit_negative_binomial(y, X_fe, offset, groups, FE_NB)
    poisson = fit_poisson_fe(y, X_fe, offset, groups)
    X_cre = cre_design(rows, spec.varying, unit_means(rows, spec.varying), years)
    mundlak = fit_negative_binomial(y, X_cre, offset, groups, MUNDLAK)
    cre = fit_cre(y, X_cre, offset, groups, mundlak)
    predictions = validate(rows, spec, units, log)
    return PairFits(pair, fe, poisson, mundlak, cre, predictions)


def _level(base: np.ndarray, observed_total: float) -> float:
    """The log level that makes the predicted total equal the observed one."""
    return float(np.log(observed_total / np.exp(base).sum()))


def validate(rows: pd.DataFrame, spec: config.PanelSpec, units: list, log: RunLog) -> pd.DataFrame:
    """Fit every model without the held-out year and predict it, under the two level rules.

    The year indicator of the held-out year cannot be estimated, so its level is either fixed by
    the observed total of the pair (what is evaluated is then how the model shares that total
    among the units) or carried from the year before. The correlated model predicts with each
    unit's posterior intercept from the training years, and its unit means are computed on them.
    """
    holdout = config.PANEL_HOLDOUT_YEAR
    train = rows[rows[config.YEAR_COL] < holdout].reset_index(drop=True)
    test = rows[rows[config.YEAR_COL] == holdout].reset_index(drop=True)
    years = sorted(train[config.YEAR_COL].unique())
    y_train = train[RESPONSE].to_numpy(dtype=float)
    off_train = np.log(train[EXPOSURE].to_numpy(dtype=float))
    g_train = train[config.AREA_CODE_COL].to_numpy()
    off_test = np.log(test[EXPOSURE].to_numpy(dtype=float))
    observed = test[RESPONSE].to_numpy(dtype=float)
    total = float(observed.sum())
    previous = f"YEAR[{holdout - 1}]"

    out = []

    def record(model: str, base: np.ndarray, carried: float, alpha: float, converged: bool):
        for level, shift in ((LEVEL_OBSERVED, _level(base, total)), (LEVEL_CARRIED, carried)):
            predicted = np.exp(base + shift)
            out.append(pd.DataFrame({
                config.AREA_CODE_COL: test[config.AREA_CODE_COL], config.YEAR_COL: holdout,
                "MODEL": model, "LEVEL": level, "OBSERVED": observed, "PREDICTED": predicted,
                "ALPHA": alpha, "CONVERGED": converged}))

    def fe_base(fit: ModelFit, varying: tuple[str, ...]) -> np.ndarray:
        X = fe_design(test, varying, units, years)
        return off_test + X.to_numpy() @ fit.params.reindex(X.columns).fillna(0.0).to_numpy()

    X_fe = fe_design(train, spec.varying, units, years)
    fe = fit_negative_binomial(y_train, X_fe, off_train, g_train, FE_NB)
    record(FE_NB, fe_base(fe, spec.varying), float(fe.params.get(previous, 0.0)), fe.alpha, fe.converged)

    X_ref = fe_design(train, (), units, years)
    ref = fit_negative_binomial(y_train, X_ref, off_train, g_train, REFERENCE)
    record(REFERENCE, fe_base(ref, ()), float(ref.params.get(previous, 0.0)), ref.alpha, ref.converged)

    means = unit_means(train, spec.varying)
    X_cre = cre_design(train, spec.varying, means, years)
    mundlak = fit_negative_binomial(y_train, X_cre, off_train, g_train, MUNDLAK)
    cre = fit_cre(y_train, X_cre, off_train, g_train, mundlak)
    X_test = cre_design(test, spec.varying, means, years)
    scale = cre.unit_scale.reindex(test[config.AREA_CODE_COL]).to_numpy()
    base = off_test + X_test.to_numpy() @ cre.params.reindex(X_test.columns).fillna(0.0).to_numpy() + np.log(scale)
    record(CRE, base, float(cre.params.get(previous, 0.0)), cre.alpha, cre.converged)
    return pd.concat(out, ignore_index=True)


def nb_log_likelihood(observed: np.ndarray, predicted: np.ndarray, alpha: float) -> float:
    """The NB2 log-likelihood of counts under predicted means, with the model's own dispersion."""
    size = 1.0 / max(alpha, 1e-10)
    return float(stats.nbinom.logpmf(observed, size, size / (size + predicted)).sum())


# -- what each model reports -------------------------------------------------------------------

def _terms(fit: ModelFit) -> list[tuple[str, str, str]]:
    """(column, variable, role) of every coefficient the tables report."""
    out = []
    for name in fit.names:
        if name.startswith("W["):
            out.append((name, name[2:-1], WITHIN))
        elif name.startswith("B["):
            out.append((name, name[2:-1], BETWEEN))
        elif name.startswith("C["):
            out.append((name, name[2:-1], CONSTANT))
        elif name.startswith("YEAR["):
            out.append((name, name[5:-1], YEAR_EFFECT))
        elif not name.startswith("UNIT[") and name != "INTERCEPT":
            out.append((name, name, WITHIN))  # fixed effects: what it estimates is the within effect
    return out


def coefficient_rows(panel: PanelData, fits: PairFits) -> list[dict]:
    rows = []
    for fit in (fits.fe, fits.poisson, fits.mundlak, fits.cre):
        for column, variable, role in _terms(fit):
            b = float(fit.params[column])
            se = float(np.sqrt(max(fit.cov_clustered.loc[column, column], 0.0)))
            se_model = float(np.sqrt(max(fit.cov_model.loc[column, column], 0.0)))
            p = float(2 * stats.norm.sf(abs(b / se))) if se > 0 else float("nan")
            rows.append({
                "DATASET": panel.dataset, "PANEL": panel.spec.key, "PAIR": fits.pair, "MODEL": fit.model,
                "TERM": variable, "ROLE": role, "COEFFICIENT": b, "SE_CLUSTERED": se, "SE_MODEL": se_model,
                "P_VALUE": p, "CI_LOW": b - Z * se, "CI_HIGH": b + Z * se,
                "PERCENT": 100 * np.expm1(b), "PERCENT_LOW": 100 * np.expm1(b - Z * se),
                "PERCENT_HIGH": 100 * np.expm1(b + Z * se),
                "SD_NATURAL": panel.sd.get(variable, float("nan")), "CONVERGED": fit.converged,
            })
    return rows


def hausman_rows(panel: PanelData, fits: PairFits) -> list[dict]:
    """Within against between, inside the correlated model, on its clustered covariance."""
    rows = []
    cov = fits.cre.cov_clustered
    for variable in panel.spec.varying:
        w, b = f"W[{variable}]", f"B[{variable}]"
        difference = float(fits.cre.params[w] - fits.cre.params[b])
        variance = float(cov.loc[w, w] + cov.loc[b, b] - 2 * cov.loc[w, b])
        statistic = difference**2 / variance if variance > 0 else float("nan")
        rows.append({"DATASET": panel.dataset, "PANEL": panel.spec.key, "PAIR": fits.pair, "TERM": variable,
                     "WITHIN": float(fits.cre.params[w]), "BETWEEN": float(fits.cre.params[b]),
                     "STATISTIC": statistic, "P_VALUE": float(stats.chi2.sf(statistic, 1)),
                     "CONVERGED": fits.cre.converged})
    return rows


def moran_rows(panel: PanelData, fits: PairFits, weights: np.ndarray, codes: tuple[str, ...]) -> list[dict]:
    """Moran's I of each unit's mean residual, with a permutation p-value, for both main models."""
    rows = []
    data = panel.rows[panel.rows["PAIR"] == fits.pair].reset_index(drop=True)
    rng = np.random.default_rng(config.PANEL_RANDOM_SEED)
    for fit in (fits.fe, fits.cre):
        residual = data[RESPONSE].to_numpy(dtype=float) - fit.fitted
        per_unit = pd.Series(residual).groupby(data[config.AREA_CODE_COL].to_numpy()).mean().reindex(codes)
        values = per_unit.to_numpy()
        observed = regressions.morans_i(values, weights)
        permuted = np.array([regressions.morans_i(rng.permutation(values), weights)
                             for _ in range(config.PANEL_MORAN_PERMUTATIONS)])
        p = (1 + int((permuted >= observed).sum())) / (1 + config.PANEL_MORAN_PERMUTATIONS)
        rows.append({"DATASET": panel.dataset, "PANEL": panel.spec.key, "PAIR": fits.pair, "MODEL": fit.model,
                     "MORANS_I": observed, "P_VALUE": p})
    return rows


def model_rows(panel: PanelData, fits: PairFits) -> list[dict]:
    return [{"DATASET": panel.dataset, "PANEL": panel.spec.key, "PAIR": fits.pair, "MODEL": fit.model,
             "OBSERVATIONS": fit.observations, "PARAMETERS": fit.parameters,
             "LOG_LIKELIHOOD": fit.log_likelihood, "AIC": fit.aic, "BIC": fit.bic, "ALPHA": fit.alpha,
             "SIGMA": fit.sigma, "CONVERGED": fit.converged, "MESSAGE": fit.message}
            for fit in (fits.fe, fits.poisson, fits.mundlak, fits.cre)]


def validation_rows(panel: PanelData, fits: PairFits) -> list[dict]:
    rows = []
    for (model, level), block in fits.predictions.groupby(["MODEL", "LEVEL"]):
        observed, predicted = block["OBSERVED"].to_numpy(), block["PREDICTED"].to_numpy()
        total = float(((observed - observed.mean()) ** 2).sum())
        rows.append({"DATASET": panel.dataset, "PANEL": panel.spec.key, "PAIR": fits.pair, "MODEL": model,
                     "LEVEL": level, "LOG_LIKELIHOOD": nb_log_likelihood(observed, predicted,
                                                                          float(block["ALPHA"].iloc[0])),
                     "MEAN_ABSOLUTE_ERROR": float(np.abs(observed - predicted).mean()),
                     "R2": 1 - float(((observed - predicted) ** 2).sum()) / total if total > 0 else float("nan"),
                     "PREDICTED_TOTAL": float(predicted.sum()), "OBSERVED_TOTAL": float(observed.sum()),
                     "CONVERGED": bool(block["CONVERGED"].iloc[0])})
    return rows


def fieller(a: float, b: float, var_a: float, var_b: float, cov_ab: float) -> tuple[float, float, bool]:
    """The Fieller interval of a / b at 95 %, and whether it is bounded.

    It is the set of r with (a - r b)^2 <= z^2 (var_a - 2 r cov_ab + r^2 var_b). Bounded only when
    the denominator is itself distinguishable from zero, b^2 > z^2 var_b; otherwise the set is the
    whole line or its complement and no interval can be given.
    """
    q = Z**2
    A = b**2 - q * var_b
    B = -2 * (a * b - q * cov_ab)
    C = a**2 - q * var_a
    if A <= 0:
        return float("nan"), float("nan"), False
    disc = B**2 - 4 * A * C
    if disc < 0:
        return float("nan"), float("nan"), False
    root = np.sqrt(disc)
    return float((-B - root) / (2 * A)), float((-B + root) / (2 * A)), True


def ratio_rows(panel: PanelData, fits: PairFits) -> list[dict]:
    """Vertical over horizontal in natural units: kilometres of marking per one sign, per km²."""
    if not {VERTICAL, HORIZONTAL} <= set(panel.spec.varying):
        return []
    rows = []
    for fit, prefix in ((fits.fe, ""), (fits.cre, "W")):
        v = f"{prefix}[{VERTICAL}]" if prefix else VERTICAL
        h = f"{prefix}[{HORIZONTAL}]" if prefix else HORIZONTAL
        # A standardised coefficient divided by its deviation is the coefficient per natural unit.
        sv, sh = panel.sd[VERTICAL], panel.sd[HORIZONTAL]
        a, b = float(fit.params[v]) / sv, float(fit.params[h]) / sh
        cov = fit.cov_clustered
        low, high, bounded = fieller(a, b, cov.loc[v, v] / sv**2, cov.loc[h, h] / sh**2, cov.loc[v, h] / (sv * sh))
        rows.append({"DATASET": panel.dataset, "PANEL": panel.spec.key, "PAIR": fits.pair, "MODEL": fit.model,
                     "VERTICAL_PER_SIGN": a, "HORIZONTAL_PER_KM": b, "RATIO": a / b if b != 0 else float("nan"),
                     "LOW": low, "HIGH": high, "BOUNDED": bounded, "CONVERGED": fit.converged})
    return rows


def holm(table: pd.DataFrame, keys: list[str], column: str = "P_VALUE") -> pd.Series:
    """Holm over the eight pairs, within every other key: per variable, panel and model."""
    adjusted = pd.Series(np.nan, index=table.index)
    for _, block in table.groupby(keys, dropna=False):
        valid = block[column].notna()
        if valid.any():
            adjusted.loc[block.index[valid]] = multipletests(block.loc[valid, column], method="holm")[1]
    return adjusted


def variables_rows(panel: PanelData) -> list[dict]:
    return [{"DATASET": panel.dataset, "PANEL": panel.spec.key, "TERM": v, "MEAN": panel.mean[v],
             "SD_NATURAL": panel.sd[v], "REMAINING_SHARE": panel.remaining_share.get(v, 0.0),
             "TIME_VARYING": v in panel.spec.varying} for v in (*panel.spec.varying, *CONSTANTS)]


def run(log: RunLog) -> dict[str, pd.DataFrame]:
    """Every panel, pair and model the amendment declares, and the tables they report."""
    designs, source_run = read_design(log)
    units = estimating_units(designs[config.CORRECTED_DATASET], log)
    weights, codes = regressions.contiguity_weights(units)
    marking = horizontal_marking(units, log)
    out: dict[str, list] = {name: [] for name in
                            ("coefficients", "models", "hausman", "moran", "validation", "predictions",
                             "ratio", "variables", "panel_rows")}
    jobs = [(config.CORRECTED_DATASET, pair.name) for pair in config.REGRESSION_PAIRS]
    jobs.append((config.OBSERVED_DATASET, config.PANEL_SENSITIVITY_PAIR))
    for spec in config.PANEL_SPECS:
        panels = {}
        for dataset in sorted({d for d, _ in jobs}):
            variables = unit_year_variables(designs[dataset], marking)
            panels[dataset] = build_panel(designs[dataset], variables, spec, dataset, log)
            out["variables"] += variables_rows(panels[dataset])
            out["panel_rows"].append(panels[dataset].rows.assign(DATASET=dataset, PANEL=spec.key))
        for dataset, pair in jobs:
            panel = panels[dataset]
            fits = fit_pair(panel, pair, log)
            out["coefficients"] += coefficient_rows(panel, fits)
            out["models"] += model_rows(panel, fits)
            out["hausman"] += hausman_rows(panel, fits)
            out["moran"] += moran_rows(panel, fits, weights, codes)
            out["validation"] += validation_rows(panel, fits)
            out["predictions"].append(fits.predictions.assign(DATASET=dataset, PANEL=spec.key, PAIR=pair))
            out["ratio"] += ratio_rows(panel, fits)
            log.info("%s %s %s: FE %s, CRE %s", dataset, spec.key, pair,
                     "converged" if fits.fe.converged else "NOT converged",
                     "converged" if fits.cre.converged else "NOT converged")
    tables = {name: (pd.concat(rows, ignore_index=True) if rows and isinstance(rows[0], pd.DataFrame)
                     else pd.DataFrame(rows)) for name, rows in out.items()}
    coefficients = tables["coefficients"]
    coefficients["P_HOLM"] = holm(coefficients, ["DATASET", "PANEL", "MODEL", "TERM", "ROLE"])
    tables["hausman"]["P_HOLM"] = holm(tables["hausman"], ["DATASET", "PANEL", "TERM"])
    tables["moran"]["P_HOLM"] = holm(tables["moran"], ["DATASET", "PANEL", "MODEL"])
    tables["moran"]["ASKS_FOR_SPATIAL_TERM"] = tables["moran"]["P_HOLM"] < config.PANEL_MORAN_ALPHA
    tables["marking"] = marking
    for table in tables.values():
        table.attrs["source_run"] = source_run
    return tables


def verify(tables: dict[str, pd.DataFrame], log: RunLog) -> list[str]:
    """What the run must satisfy or fail loudly; returns the failures, empty when all hold."""
    failures = []
    models = tables["models"]
    for (dataset, panel_key, model), block in models.groupby(["DATASET", "PANEL", "MODEL"]):
        failed = int((~block["CONVERGED"]).sum())
        if failed:
            log.warn("%s %s %s: %d of %d pairs did not converge", dataset, panel_key, model, failed, len(block))
        if model in (FE_NB, CRE) and failed > len(block) / 2:
            failures.append(f"{model} fails in more than half the pairs of {panel_key} ({dataset})")
    observed_level = tables["validation"][tables["validation"]["LEVEL"] == LEVEL_OBSERVED]
    gap = (observed_level["PREDICTED_TOTAL"] - observed_level["OBSERVED_TOTAL"]).abs().max()
    if gap > 1e-6:
        failures.append(f"with the level fixed by the observed total the totals differ by {gap}")
    ratio = tables["ratio"]
    if len(ratio) and ((ratio["RATIO"] - ratio["VERTICAL_PER_SIGN"] / ratio["HORIZONTAL_PER_KM"]).abs() > 1e-9).any():
        failures.append("the ratio does not equal the quotient of its two coefficients")
    return failures


def export(tables: dict[str, pd.DataFrame], log: RunLog) -> None:
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        path = data_dir / f"{config.ANALYSIS_PREFIX}__panel_{name}.csv"
        table.to_csv(path, index=False, encoding="utf-8")
        table.to_parquet(path.with_suffix(".parquet"))
    log.info("panel tables written to %s, from the design of %s", data_dir,
             tables["models"].attrs.get("source_run", "?"))
