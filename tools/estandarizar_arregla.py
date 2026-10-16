"""Does standardising the design fix the negative binomial's convergence?

    .venv/Scripts/python.exe tools/estandarizar_arregla.py

**Read only.** Nothing in `src/` imports it; it writes a temporary log.

The tree census takes values between 901 and 7,937 while eleven of the twelve candidates
live between 0.00005 and 356, and `_scale_candidates` takes logarithms of the three offset
quantities and standardises nothing. In a log-link likelihood maximised by a quasi-Newton
method that leaves the optimiser hunting for a coefficient of order 1e-4 in one coordinate
and order 1 in the others.

If that is the cause, standardising the columns before fitting should fix it, and it should
change no result: rescaling a predictor linearly only rescales its coefficient, and the
likelihood, the AIC and the p-values do not move.

**Both halves confirmed.** With all twelve candidates in, the raw design converges in 5 of
60 cells and the standardised design in 52 of 60. Where both fit, the log-likelihood
differs by at most 1.6e-08: it is the same model.

The implication reaches past backward elimination — the current search fits raw designs
too — and the change belongs inside `_fit_one` with a back-transform of the coefficients.
See `docs/regression-inventory.md` sections 17.9 to 17.11.
"""

import sys, logging, warnings
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import numpy as np, pandas as pd, statsmodels.api as sm
import config, loading, predictors as pm, regressions
from provenance import RunLog
d = REPO / "results" / "_tools_estandarizar"; d.mkdir(parents=True, exist_ok=True)
log = RunLog(d); logging.getLogger().setLevel(logging.ERROR)
matrices, expo, pobl, preds = regressions.read_inputs(log)
unidades = pm.prepare_units(loading.load_territorial_units(log))
unidades, preds = regressions.exclude_units(unidades, preds, log)
conj = config.DEFAULT_CANDIDATE_SET
marco = regressions.build_dataset(matrices[config.OBSERVED_DATASET], expo, pobl, preds, conj, log)
pares = regressions.eligible_pairs(marco, log)
rng = np.random.default_rng(13)
celdas = [(o, p, a) for o in config.REGRESSION_OFFSETS for p in pares
          for a in sorted(marco[config.YEAR_COL].unique())]
muestra = [celdas[i] for i in rng.choice(len(celdas), size=60, replace=False)]

def ajustar(y, X, off):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            nb = sm.NegativeBinomial(y, X, offset=off).fit(disp=0, maxiter=2_000)
        except Exception:
            return None
    return nb if regressions._converged(nb) else None

crudo = est = 0
iguales = []
for off, pareja, anio in muestra:
    b = marco[(marco[config.YEAR_COL] == anio) & (marco[config.PAIR_COL] == pareja.name)]
    cand = off.candidate_predictors(config.regression_pool_in(anio, conj))
    y = b[regressions.RESPONSE_COL].to_numpy(dtype=float)
    o = regressions._log_offset(b, off)
    col = regressions._scale_candidates(b, cand)
    X1 = np.column_stack([np.ones(len(y)), col])
    Z = (col - col.mean(axis=0)) / np.where(col.std(axis=0) > 0, col.std(axis=0), 1.0)
    X2 = np.column_stack([np.ones(len(y)), Z])
    a, bb = ajustar(y, X1, o), ajustar(y, X2, o)
    crudo += int(a is not None); est += int(bb is not None)
    # Si los dos ajustan, la verosimilitud tiene que ser la misma: es el mismo modelo.
    if a is not None and bb is not None:
        iguales.append(abs(float(a.llf) - float(bb.llf)))

print(f"sobre {len(muestra)} celdas, con las doce candidatas dentro:\n")
print(f"   diseño crudo:          {crudo:>3} de {len(muestra)} convergen  ({crudo/len(muestra)*100:5.1f} %)")
print(f"   diseño estandarizado:  {est:>3} de {len(muestra)} convergen  ({est/len(muestra)*100:5.1f} %)")
print()
if iguales:
    print(f"donde los dos ajustan ({len(iguales)} celdas), la verosimilitud difiere a lo sumo "
          f"en {max(iguales):.2e}")
    print("   es el mismo modelo: reescalar un predictor solo reescala su coeficiente")
