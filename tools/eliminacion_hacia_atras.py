"""How many variables does backward elimination leave standing, on the real cells?

    .venv/Scripts/python.exe tools/eliminacion_hacia_atras.py

**Read only.** It reads a finished casualty run, the exposure panel and the predictors,
runs backward elimination over all 1,872 cells in memory, and writes nothing but a
temporary log and a CSV beside it. Nothing in `src/` imports it.

The advisor proposed backward elimination on 2026-10-07 to replace the best-subset AIC
search, with the aside that it gives "the parameters that do explain the endogenous
variable (instead of 3 parameters)". The question that settles is whether it can end up
choosing **more** than the two or three the current search is capped at. It is measurable,
so it was measured before anything was implemented.

**It can, and it does in 48.1 % of the cells that fit.** The breakdown by family is the
real finding:

| Family | cells fitted | median | max | above three |
|---|---:|---:|---:|---:|
| Least squares | 624 | 2 | 7 | 13.9 % |
| Poisson | 624 | 6 | 11 | 83.0 % |
| Negative binomial | 17 | 3 | 5 | 23.5 % |

**The advisor's intuition holds in least squares**, which is where it was formed and what
her function fits: a median of two, and only 13.9 % above three.

**Poisson's six is not six variables explaining the data.** It is overdispersion:
Poisson's standard errors are too small when the counts are overdispersed, which is the
reason the pipeline switches family above OVERDISPERSION_THRESHOLD, so the p-values come
out too small and almost nothing is eliminated. It is a diagnosis of overdispersion
wearing the clothes of a selection.

**And the negative binomial would not fit in 607 of its 624 cells**, which is the family
the study leads with on overdispersed pairs. It estimates dispersion jointly with the
coefficients, and twelve predictors on twenty-nine observations do not converge in the 200
iterations `_fit_one` allows. Whether that is "cannot" or "needs more steps" is not
settled here, and the limit should be raised before anything is concluded from it.

Two implementation details worth keeping, because each cost a run to find. The negative
binomial of statsmodels estimates `alpha` as a parameter, so its `pvalues` carry one extra
entry that belongs to no variable. And a p-value that comes back NaN is not a large
p-value: it is a coefficient the design does not identify, which happens here because
twelve candidates on twenty-nine observations can make the covariance matrix singular even
when the fit reports convergence.

See `docs/regression-inventory.md` section 17, D59.
"""


import sys
import logging
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import numpy as np
import pandas as pd
import statsmodels.api as sm

import config
import regressions
from provenance import RunLog

ALFA = 0.05
indefinidos = [0]   # cuantas pasadas toparon con un coeficiente no identificado
d = REPO / "results" / "_tools_back"
d.mkdir(parents=True, exist_ok=True)
log = RunLog(d)
logging.getLogger().setLevel(logging.ERROR)


def eliminar_hacia_atras(familia, respuesta, diseno, log_offset, nombres, alfa=ALFA):
    """La funcion de la asesora, generalizada a las tres familias.

    La suya es `sm.OLS` sola. Aqui se delega en `regressions._fit_one`, que es el mismo
    ajuste que usa la busqueda actual, para que la comparacion sea entre metodos de
    seleccion y no entre dos maneras de ajustar.

    Devuelve los nombres que sobreviven, en orden de eliminacion inversa, y cuantos pasos
    tomo. Un `None` quiere decir que el estimador no pudo con el modelo completo, que con
    doce predictores y veintinueve observaciones no es raro.
    """
    vivos = list(nombres)
    pasos = 0
    while vivos:
        columnas = [nombres.index(v) for v in vivos]
        con_constante = np.column_stack([np.ones(len(respuesta)), diseno[:, columnas]])
        resultado = regressions._fit_one(familia, respuesta, con_constante, log_offset)
        if resultado is None or not regressions._converged(resultado):
            return None, pasos
        # La constante nunca se elimina: es el nivel, no una explicacion. Y se corta por
        # longitud y no con [1:], porque la binomial negativa de statsmodels estima alpha
        # junto con los coeficientes y la cuenta como un parametro mas: sus pvalues traen
        # una entrada de sobra al final, que no es de ninguna variable.
        todos = np.asarray(resultado.pvalues)
        p = pd.Series(todos[1:1 + len(vivos)], index=vivos)
        # **Un valor p que sale NaN no es un valor p grande: es un coeficiente que el
        # diseño no identifica.** Con doce candidatas y veintinueve observaciones la
        # matriz de covarianzas sale singular y statsmodels devuelve NaN aunque el ajuste
        # diga que convergio. Se cuentan y se botan primero, que es lo unico que se puede
        # hacer con una variable de la que no hay nada que decir — y la cuenta de cuantas
        # veces pasa es por si sola una respuesta a si doce candidatas caben aqui.
        degenerados = int(p.isna().sum())
        if degenerados:
            indefinidos[0] += 1
            p = p.fillna(1.0)
        if p.empty or p.max() <= alfa:
            return vivos, pasos
        vivos.remove(p.idxmax())
        pasos += 1
    return [], pasos


import loading
import predictors as predictores_mod

matrices, exposicion, poblacion, predictores = regressions.read_inputs(log)
unidades = predictores_mod.prepare_units(loading.load_territorial_units(log))
unidades, predictores = regressions.exclude_units(unidades, predictores, log)
filas = []

conjunto = config.DEFAULT_CANDIDATE_SET
datos = {
    dataset: regressions.build_dataset(
        matriz, exposicion, poblacion, predictores, conjunto, log)
    for dataset, matriz in matrices.items()
}
for dataset, marco in datos.items():
    pares = regressions.eligible_pairs(marco, log)
    print(f"{dataset}: {len(pares)} parejas elegibles, "
          f"{marco[config.YEAR_COL].nunique()} años")
    if True:
        for offset in config.REGRESSION_OFFSETS:
            for pareja in pares:
                for anio in sorted(marco[config.YEAR_COL].unique()):
                    bloque = marco[
                        (marco[config.YEAR_COL] == anio)
                        & (marco[config.PAIR_COL] == pareja.name)
                    ]
                    if len(bloque) < 5:
                        continue
                    candidatas = offset.candidate_predictors(
                        config.regression_pool_in(anio, conjunto))
                    if not candidatas:
                        continue
                    respuesta = bloque[regressions.RESPONSE_COL].to_numpy(dtype=float)
                    log_offset = regressions._log_offset(bloque, offset)
                    # **Estandarizado, que es lo que `search` hace.** La primera
                    # version de esta medicion ajustaba el diseno crudo y por eso vio una
                    # binomial negativa que no converge: el arbolado toma valores en los
                    # miles mientras once de las doce viven por debajo de 400, y el
                    # optimizador no puede con esa diferencia de escala. El pipeline ya lo
                    # resuelve y la medicion no lo estaba haciendo.
                    crudo = regressions._scale_candidates(bloque, candidatas)
                    diseno, _, _ = regressions._standardise(crudo)
                    for familia in (config.OLS_FAMILY, config.POISSON_FAMILY,
                                    config.NEGATIVE_BINOMIAL_FAMILY):
                        vivos, pasos = eliminar_hacia_atras(
                            familia, respuesta, diseno, log_offset, list(candidatas))
                        filas.append({
                            "dataset": dataset, "offset": offset.name,
                            "pareja": pareja.name, "anio": anio, "familia": familia,
                            "candidatas": len(candidatas),
                            "sobreviven": np.nan if vivos is None else len(vivos),
                            "pasos": pasos,
                            "variables": "" if not vivos else ";".join(sorted(vivos)),
                        })

t = pd.DataFrame(filas)
t.to_csv(d / "backward.csv", index=False, encoding="utf-8")
print(f"pasadas con algun coeficiente no identificado: {indefinidos[0]:,}")
print(f"{len(t):,} celdas corridas, {int(t['sobreviven'].isna().sum())} que el "
      f"estimador no pudo ajustar con las doce candidatas dentro\n")

vivas = t.dropna(subset=["sobreviven"])
print("cuantas variables quedan en pie, por familia:")
print(vivas.groupby("familia")["sobreviven"].describe()
      [["count", "mean", "50%", "min", "max"]].round(2).to_string())
print()
print("reparto del numero de sobrevivientes (todas las familias juntas):")
reparto = vivas["sobreviven"].value_counts().sort_index()
for n, c in reparto.items():
    print(f"   {int(n):>2} variable(s): {c:>5} celdas  {c/len(vivas)*100:5.1f} %  "
          + "#" * int(c / len(vivas) * 60))
print()
mas_de_tres = int((vivas["sobreviven"] > 3).sum())
print(f"celdas donde sobreviven MAS de tres: {mas_de_tres} de {len(vivas)} "
      f"({mas_de_tres/len(vivas)*100:.1f} %)")
print(f"celdas donde sobrevive una o ninguna: "
      f"{int((vivas['sobreviven'] <= 1).sum())} ({(vivas['sobreviven'] <= 1).sum()/len(vivas)*100:.1f} %)")
print()
print("por familia, cuantas pasan de tres:")
for familia, bloque in vivas.groupby("familia"):
    print(f"   {familia:18s} {int((bloque['sobreviven'] > 3).sum()):>5} de {len(bloque):>5}  "
          f"({(bloque['sobreviven'] > 3).mean()*100:5.1f} %)")
