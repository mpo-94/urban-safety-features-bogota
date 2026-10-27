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

from dataclasses import dataclass, field

import numpy as np
from scipy import optimize, special

# Enough nodes that the log-likelihood stops moving at the scale of the unit effects measured
# here; the verification tool checks this on every fit it makes rather than trusting the number.
DEFAULT_QUADRATURE_NODES = 30
# The largest absolute component of the gradient at which a fit counts as converged.
GRADIENT_TOLERANCE = 1e-4


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
        # BFGS often stops with "precision loss" when the line search can no longer improve a
        # log-likelihood of thousands at the last decimals; measured on the simulated panels, the
        # gradient is then below 1e-4 and the maximum is reached. Convergence is judged on the
        # gradient, not on the optimiser's flag.
        largest_gradient = float(np.max(np.abs(self.gradient(params)[free])))
        converged = bool(result.success) or largest_gradient < GRADIENT_TOLERANCE
        hessian = self.hessian(params)[np.ix_(free, free)]
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
