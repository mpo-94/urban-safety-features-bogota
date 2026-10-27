"""Does the random-intercept negative binomial in src/panel.py estimate what it claims?

    .venv/Scripts/python.exe tools/verificar_estimador_panel.py [--replicas N]

**Read only; it touches no data.** Every dataset here is simulated, with the panel's own shape —
twenty-nine units seen thirteen times, year effects, an offset and a covariate that changes within
the unit — so each answer is known before the estimator runs. It is the check the estimator has
to pass before the panel stage reads Bogotá with it (`deliverables/informes/panel-primer-intento.md`,
decision 2), and it fails loudly rather than printing a number to be judged.

Four checks, each one a way the estimator could be wrong without raising:

  1. **The gradient.** The analytic gradient against central differences of the likelihood. A
     wrong derivative still converges, to the wrong place.
  2. **The pooled limit.** Holding sigma at 1e-6 the random intercept vanishes and the model is the
     pooled negative binomial, so the log-likelihood and the coefficients must match statsmodels'
     `NegativeBinomial` on the same design.
  3. **The quadrature.** The log-likelihood at the fitted parameters with 20, 30 and 60 nodes must
     agree; if it moves, 30 nodes are too few for unit effects of this size.
  4. **Recovery.** Over many simulated panels the estimates must centre on the true values, and
     the 95 % intervals of the within slope must cover it about 95 % of the time.

**What it found on 2026-10-27, and what it changed in src/panel.py.** Nodes fixed around zero gave
a log-likelihood that moved by 2.5 between 20, 30 and 60 nodes, so the quadrature became adaptive.
BFGS flagged half the fits as failed with a gradient below 1e-5, so convergence is judged on the
gradient. And with twenty-nine units the coefficient of a constant variable covers at 0.91 rather
than 0.95, because maximum likelihood underestimates sigma on few groups; with 120 units it covers
at 0.95. The within slope is unbiased and covers at 0.93 either way.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import statsmodels.api as sm

from src.panel import RandomInterceptNB

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UNITS, YEARS = 29, 13
TRUE_ALPHA, TRUE_SIGMA = 0.15, 0.5
# Intercept, then twelve year effects, then one time-varying covariate and one constant one.
TRUE_COVARIATES = np.array([-0.20, 0.30])


def simulate(rng: np.random.Generator):
    """One panel with the shape of Bogotá's: offsets of the size of the exposure, year effects."""
    unit = np.repeat(np.arange(UNITS), YEARS)
    year = np.tile(np.arange(YEARS), UNITS)
    year_effect = np.r_[0.0, rng.normal(0, 0.1, YEARS - 1)]
    varying = rng.normal(0, 1, UNITS)[unit] * 0.7 + rng.normal(0, 1, UNITS * YEARS) * 0.7
    constant = rng.normal(0, 1, UNITS)[unit]
    offset = np.log(rng.uniform(2e4, 2e5, UNITS))[unit] + rng.normal(0, 0.05, UNITS * YEARS)
    intercept = -7.0
    dummies = np.zeros((UNITS * YEARS, YEARS - 1))
    dummies[year > 0, year[year > 0] - 1] = 1.0
    X = np.column_stack([np.ones(UNITS * YEARS), dummies, varying, constant])
    beta = np.r_[intercept, year_effect[1:], TRUE_COVARIATES]
    a = rng.normal(0, TRUE_SIGMA, UNITS)[unit]
    mu = np.exp(offset + X @ beta + a)
    # NB2 as a gamma-Poisson mixture: shape 1/alpha, mean mu.
    y = rng.poisson(rng.gamma(1.0 / TRUE_ALPHA, mu * TRUE_ALPHA))
    return y, X, offset, unit, beta


def start_from_pooled(y, X, offset):
    pooled = sm.NegativeBinomial(y, X, offset=offset).fit(disp=0, maxiter=500)
    return np.r_[pooled.params[:-1], np.log(pooled.params[-1]), np.log(0.3)], pooled


def check_gradient(model: RandomInterceptNB, params: np.ndarray) -> float:
    analytic = model.gradient(params)
    numeric = np.zeros_like(params)
    for j in range(len(params)):
        step = 1e-6 * max(1.0, abs(params[j]))
        up, down = params.copy(), params.copy()
        up[j] += step
        down[j] -= step
        numeric[j] = (model.log_likelihood(up) - model.log_likelihood(down)) / (2 * step)
    return float(np.max(np.abs(analytic - numeric) / np.maximum(1.0, np.abs(numeric))))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replicas", type=int, default=200)
    arguments = parser.parse_args()
    warnings.filterwarnings("ignore")
    rng = np.random.default_rng(20261027)
    failures = []

    y, X, offset, unit, beta = simulate(rng)
    model = RandomInterceptNB(y, X, offset, unit)
    start, pooled = start_from_pooled(y, X, offset)

    gradient_error = check_gradient(model, start + rng.normal(0, 0.05, len(start)))
    print(f"1. gradient, largest relative difference against central differences: {gradient_error:.2e}")
    if gradient_error > 1e-4:
        failures.append("the analytic gradient does not match the likelihood")

    limit = model.fit(start, fixed_log_sigma=np.log(1e-6))
    gap_ll = abs(limit.log_likelihood - pooled.llf)
    gap_beta = float(np.max(np.abs(limit.beta - pooled.params[:-1])))
    gap_alpha = abs(limit.alpha - pooled.params[-1])
    print(f"2. pooled limit: log-likelihood {limit.log_likelihood:.6f} against statsmodels {pooled.llf:.6f}; "
          f"largest coefficient gap {gap_beta:.2e}, alpha gap {gap_alpha:.2e}")
    if gap_ll > 1e-4 or gap_beta > 1e-3 or gap_alpha > 1e-3:
        failures.append("with sigma at zero the model is not the pooled negative binomial")

    fitted = model.fit(start)
    by_nodes = {nodes: RandomInterceptNB(y, X, offset, unit, nodes=nodes).log_likelihood(fitted.params)
                for nodes in (20, 30, 60)}
    spread = max(by_nodes.values()) - min(by_nodes.values())
    print("3. quadrature: log-likelihood at the fit with "
          + ", ".join(f"{n} nodes {v:.6f}" for n, v in by_nodes.items()) + f"; spread {spread:.2e}")
    if spread > 1e-3:
        failures.append("the log-likelihood depends on the number of nodes")

    truth = np.r_[TRUE_COVARIATES, np.log(TRUE_ALPHA), np.log(TRUE_SIGMA)]
    labels = ("varying", "constant", "log alpha", "log sigma")
    estimates, covered_model, covered_clustered, converged = [], [], [], 0
    for _ in range(arguments.replicas):
        y, X, offset, unit, beta = simulate(rng)
        model = RandomInterceptNB(y, X, offset, unit)
        start, _ = start_from_pooled(y, X, offset)
        fit = model.fit(start)
        converged += fit.converged
        values = fit.params[-4:]
        estimates.append(values)
        covered_model.append(np.abs(values - truth) <= 1.96 * fit.standard_errors(clustered=False)[-4:])
        covered_clustered.append(np.abs(values - truth) <= 1.96 * fit.standard_errors(clustered=True)[-4:])
    estimates = np.array(estimates)
    covered_model, covered_clustered = np.array(covered_model), np.array(covered_clustered)
    print(f"4. recovery over {arguments.replicas} simulated panels, {converged} converged; "
          "95 % coverage with the model's errors and with the clustered ones:")
    for j, label in enumerate(labels):
        bias = estimates[:, j].mean() - truth[j]
        # The Monte Carlo error of the mean, so a bias is judged against what the replicas can see.
        noise = estimates[:, j].std() / np.sqrt(len(estimates))
        print(f"   {label:10s} true {truth[j]:+.3f}  mean {estimates[:, j].mean():+.3f}  "
              f"bias {bias:+.3f} (±{2 * noise:.3f})  sd {estimates[:, j].std():.3f}  "
              f"coverage {covered_model[:, j].mean():.3f} / {covered_clustered[:, j].mean():.3f}")
        # Both slopes must be unbiased; the varying one, which is the within effect the panel is
        # for, must also be covered. The constant one learns from twenty-nine units only, and with
        # them maximum likelihood underestimates sigma and so the constant's errors: measured on
        # 2026-10-27, its coverage is 0.913 with 29 units and 0.947 with 120, and sigma's bias goes
        # from -0.071 to -0.017. That is the method on few groups, not a defect, so it is reported
        # and declared in the thesis rather than failed on.
        if j < 2 and abs(bias) > 3 * noise + 0.005:
            failures.append(f"the {label} coefficient is biased")
        if j == 0 and covered_model[:, j].mean() < 0.92:
            failures.append(f"the {label} coefficient's intervals do not cover")
    if converged < 0.95 * arguments.replicas:
        failures.append("too many simulated fits did not converge")

    if failures:
        print("\nFAILED: " + "; ".join(failures))
        return 1
    print("\nall four checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
