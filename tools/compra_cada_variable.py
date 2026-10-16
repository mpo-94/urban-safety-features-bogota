"""Do the extra variables backward elimination keeps actually buy anything?

    .venv/Scripts/python.exe tools/compra_cada_variable.py

**Read only.** It reads a finished casualty run and the panels, fits every subset of the
candidate pool up to the size backward elimination chose, and writes nothing but a
temporary log. Takes a few minutes. Nothing in `src/` imports it.

The question is whether a method that keeps three variables instead of one is telling you
that three work better. **Its stopping rule does not say that.** It says each surviving
coefficient is distinguishable from zero given the others are in, which is a statement
about each variable separately and not about the set compared against smaller sets. Two
things separate the two: backward elimination never reconsiders a dropped variable, so what
remains is where one path stopped rather than the winner of a comparison; and significance
and parsimony are different criteria.

So it was measured. Thirty cells per family, restricted to one to four survivors because
enumerating above four does not fit.

| | Least squares | Poisson |
|---|---:|---:|
| Cells with more than one variable | 15 of 23 | 10 of 12 |
| The chosen set is the best **of its own size** | **61 %** | 92 % |
| A **smaller** set wins on AIC | 13 % | 0 % |
| A **smaller** set wins on BIC | 20 % | 0 % |
| What the extra variables buy in AIC (median) | +2.95 | +4.97 |

**Almost always yes, and not for the reason the stopping rule gives.** In 87 % of the least
squares cells with more than one variable the extras do buy AIC; in 13 % they do not, and
under BIC that rises to 20 %.

**The number that matters most is the first row.** In 39 % of the least squares cells,
backward elimination did not find even the best set of its own size: a different set with
the same number of variables has a better AIC. That is path dependence measured — the
answer is not optimal even granting it its choice of size.

What follows for the plan is concrete: **the count of variables demonstrates nothing by
itself.** Demonstrating it requires fitting the smaller subsets and comparing, which is
what the exhaustive search already does. The two methods sit together well for that reason:
backward elimination proposes and the exhaustive search verifies.

R-squared cannot answer this and the figure leaves it out: it never falls when a variable
is added, so it would say more is always better by construction.

See `docs/regression-inventory.md` sections 17.3 and 17.4.
"""


import sys
import logging
import warnings
from itertools import combinations
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import numpy as np
import pandas as pd

import config
import loading
import predictors as predictores_mod
import regressions
from provenance import RunLog

ALFA = 0.05
MAX_K = 4          # hasta cuatro sobrevivientes: enumerar todo por encima no cabe
MUESTRA = 30

d = REPO / "results" / "_tools_compra"
d.mkdir(parents=True, exist_ok=True)
log = RunLog(d)
logging.getLogger().setLevel(logging.ERROR)

matrices, exposicion, poblacion, predictores = regressions.read_inputs(log)
unidades = predictores_mod.prepare_units(loading.load_territorial_units(log))
unidades, predictores = regressions.exclude_units(unidades, predictores, log)
conjunto = config.DEFAULT_CANDIDATE_SET
marco = regressions.build_dataset(
    matrices[config.OBSERVED_DATASET], exposicion, poblacion, predictores, conjunto, log)
pares = regressions.eligible_pairs(marco, log)


def ajustar(familia, respuesta, diseno, log_offset, columnas):
    """Un subconjunto, con su constante. Devuelve el resultado o None."""
    con_constante = np.column_stack([np.ones(len(respuesta)), diseno[:, list(columnas)]])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultado = regressions._fit_one(familia, respuesta, con_constante, log_offset)
    if resultado is None or not regressions._converged(resultado):
        return None
    return resultado


def eliminar(familia, respuesta, diseno, log_offset, n):
    """La eliminacion hacia atras, sobre indices de columna."""
    vivos = list(range(n))
    while vivos:
        resultado = ajustar(familia, respuesta, diseno, log_offset, vivos)
        if resultado is None:
            return None
        p = np.asarray(resultado.pvalues)[1:1 + len(vivos)]
        p = np.where(np.isfinite(p), p, 1.0)
        if p.max() <= ALFA:
            return vivos
        vivos.pop(int(np.argmax(p)))
    return []


rng = np.random.default_rng(3)
celdas = [(o, p, a) for o in config.REGRESSION_OFFSETS for p in pares
          for a in sorted(marco[config.YEAR_COL].unique())]
muestra = [celdas[i] for i in rng.choice(len(celdas), size=MUESTRA, replace=False)]

filas = []
for familia in (config.OLS_FAMILY, config.POISSON_FAMILY):
    for offset, pareja, anio in muestra:
        bloque = marco[(marco[config.YEAR_COL] == anio)
                       & (marco[config.PAIR_COL] == pareja.name)]
        candidatas = offset.candidate_predictors(
            config.regression_pool_in(anio, conjunto))
        respuesta = bloque[regressions.RESPONSE_COL].to_numpy(dtype=float)
        log_offset = regressions._log_offset(bloque, offset)
        # Estandarizado, que es lo que `search` hace antes de ajustar. Medir sobre
        # el diseno crudo es medir un problema que el pipeline no tiene.
        diseno, _, _ = regressions._standardise(
            regressions._scale_candidates(bloque, candidatas))
        n = len(candidatas)

        elegidas = eliminar(familia, respuesta, diseno, log_offset, n)
        if elegidas is None or not (1 <= len(elegidas) <= MAX_K):
            continue
        k = len(elegidas)
        suyo = ajustar(familia, respuesta, diseno, log_offset, elegidas)
        if suyo is None:
            continue

        # Todos los subconjuntos de tamano 1..k de la misma bolsa.
        mejor_por_tamano = {}
        for tamano in range(1, k + 1):
            mejor = None
            for combinacion in combinations(range(n), tamano):
                resultado = ajustar(familia, respuesta, diseno, log_offset, combinacion)
                if resultado is None:
                    continue
                if mejor is None or resultado.aic < mejor[0]:
                    mejor = (float(resultado.aic), float(resultado.bic), combinacion)
            mejor_por_tamano[tamano] = mejor

        propio = mejor_por_tamano.get(k)
        menores = [v for t, v in mejor_por_tamano.items() if t < k and v is not None]
        mejor_menor = min(menores, key=lambda v: v[0]) if menores else None
        filas.append({
            "familia": familia, "offset": offset.name, "pareja": pareja.name,
            "anio": anio, "k": k,
            "aic_elegido": float(suyo.aic), "bic_elegido": float(suyo.bic),
            "aic_mejor_de_su_tamano": propio[0] if propio else np.nan,
            "es_el_mejor_de_su_tamano": bool(
                propio and set(propio[2]) == set(elegidas)),
            "aic_mejor_mas_chico": mejor_menor[0] if mejor_menor else np.nan,
            "bic_mejor_mas_chico": mejor_menor[1] if mejor_menor else np.nan,
            "k_mejor_mas_chico": len(mejor_menor[2]) if mejor_menor else np.nan,
        })

t = pd.DataFrame(filas)
# Escrito, no solo impreso: los numeros de esta tabla se citan en la seccion 17.3
# y una cifra citada que no se puede volver a abrir no se puede comprobar.
t.to_csv(d / "compra_cada_variable.csv", index=False, encoding="utf-8")
print(f"tabla en {d / 'compra_cada_variable.csv'}")
print(f"{len(t)} celdas con entre 1 y {MAX_K} sobrevivientes, de {MUESTRA} por familia\n")

for familia, bloque in t.groupby("familia"):
    uno = bloque[bloque["k"] == 1]
    varias = bloque[bloque["k"] > 1].dropna(subset=["aic_mejor_mas_chico"])
    print(f"{familia}: {len(bloque)} celdas, {len(varias)} con mas de una variable")
    if len(bloque):
        print(f"   el conjunto elegido es el mejor de su propio tamano en "
              f"{int(bloque['es_el_mejor_de_su_tamano'].sum())} de {len(bloque)} "
              f"({bloque['es_el_mejor_de_su_tamano'].mean()*100:.0f} %)")
    if len(varias):
        gana_chico_aic = varias["aic_mejor_mas_chico"] < varias["aic_elegido"]
        gana_chico_bic = varias["bic_mejor_mas_chico"] < varias["bic_elegido"]
        print(f"   un conjunto MAS CHICO tiene mejor AIC en "
              f"{int(gana_chico_aic.sum())} de {len(varias)} "
              f"({gana_chico_aic.mean()*100:.0f} %)")
        print(f"   un conjunto MAS CHICO tiene mejor BIC en "
              f"{int(gana_chico_bic.sum())} de {len(varias)} "
              f"({gana_chico_bic.mean()*100:.0f} %)")
        ganancia = varias["aic_mejor_mas_chico"] - varias["aic_elegido"]
        print(f"   lo que las variables de mas compran en AIC: mediana "
              f"{ganancia.median():+.2f}, rango {ganancia.min():+.1f} a {ganancia.max():+.1f}")
        print(f"      (positivo = el conjunto elegido es mejor que cualquiera mas chico)")
    print()
