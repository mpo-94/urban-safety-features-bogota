"""Does the floor fix the infeasible margins without breaking what already worked?

    .venv/Scripts/python.exe tools/piso_de_la_semilla.py

**Read only.** It builds the margins, disaggregates the thirteen years the regressions
read and fits all 52 blocks in memory, writing nothing but a temporary log. Takes about
four minutes. Nothing in `src/` imports it.

Twenty-five of the 52 blocks had margins no matrix with the seed's support admitted,
because the seeds are between 0.5 % and 1.4 % dense and keeping every zero of a sample
that sparse is keeping sampling noise as geography. The floor replaces each zero with
`config.RECONSTRUCTION_SEED_FLOOR` times the block's mean occupied cell, which completes
the support. Six checks, and the first is the one that decides:

  * **D60's identity is still exact, and no survey year needed the floor.** This is why
    the floor is applied only where the seed's own support cannot reach the margins: a
    floored seed carries more travel than the margins ask for, so fitting it scales
    everything down and a survey year would no longer come back as itself. Measured, the
    three survey years inside the window come back to 1e-11 trips a day with the floor
    untouched.

  * **All 52 blocks converge.** Fourteen need the floor; the other 38 reach their margins
    with the survey's own cells.

  * **What was invented**, which is the figure the thesis has to quote: 11,965 trips a day
    of 109,911,870, or 0.0109 %. The worst single block is 0.67 %.

  * **The worst unit error falls from 55.74 % to 0.0097 %.** That is what the floor was
    for. The aggregate error per unit was never the problem — it stayed under 0.8 % — and
    a cross-section reads the variation between units, which is exactly what a single unit
    off by half does not average away.

It also prints which blocks needed the floor and what each one opened, because the years
that needed it are cycling and motorcycling in the early segment and that is worth seeing
rather than taking on trust.

See D54, D60, `src/fitting.py` and `src/reconstruction.py`.
"""

import sys, time, logging
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import numpy as np
import pandas as pd
import config, exposure, fitting, interpolation, loading, population, predictors, reconstruction, surveys
from provenance import RunLog

fallos = []
def comprobar(titulo, pasa, detalle=""):
    print(f"  {'OK  ' if pasa else 'FALLA'}  {titulo}")
    if detalle:
        print(f"           {detalle}")
    if not pasa:
        fallos.append(titulo)

d = REPO / "results" / "_tools_piso"
d.mkdir(parents=True, exist_ok=True)
log = RunLog(d)
logging.getLogger().setLevel(logging.ERROR)

DIA = config.MODEL_EXPOSURE_DAY_TYPE
Z = surveys.ZONE_CODE_COL
units = predictors.prepare_units(loading.load_territorial_units(log))
panel, _, _ = population.build(units, log)
measured = interpolation.read_measured(log)
margenes = reconstruction.unit_margins(measured, panel, units, log)
anclas = measured.anchors_of(DIA)
print(f"piso {config.RECONSTRUCTION_SEED_FLOOR:.0e} del viaje medio por celda ocupada | "
      f"poda {config.RECONSTRUCTION_PRUNE_BELOW} viajes/dia | "
      f"tolerancia {fitting.DEFAULT_TOLERANCE:.0e}\n")

leidas = {}
for e in config.MOBILITY_SURVEYS:
    trips = surveys.read(e, log)
    leidas[e.year] = (trips, exposure.zone_area_shares(trips.zones, units, e, log))

filas, identidades = [], []
t_total = time.time()
# Desde D64 un anio descansa en dos encuestas. El recorrido pasa a ser por componente
# de la mezcla en vez de por anio, lo que mide mas y no menos: lo que se observa de
# cada semilla es exactamente lo que se observaba cuando habia una sola.
AN_SI = [(a, s) for a in config.REGRESSION_YEARS
         for s, _ in reconstruction.seeding_blend(a, anclas)]
for anio, siembra in AN_SI:
    sel = (margenes[config.YEAR_COL] == anio) & (margenes[config.DAY_TYPE_COL] == DIA)
    trips, shares = leidas[siembra]
    t0 = time.time()
    zm = reconstruction.zone_margins(trips, shares, margenes[sel], anio)
    f = reconstruction.fit_year(trips, zm)
    dt = time.time() - t0

    # La identidad, donde el anio es su propia semilla.
    if anio == siembra:
        clave = [config.ACTOR_TYPE_COL, config.DAY_TYPE_COL,
                 surveys.ZONE_ORIGIN_COL, surveys.ZONE_DESTINATION_COL]
        orig = trips.pairs[trips.pairs[config.DAY_TYPE_COL] == DIA]
        j = f.pairs.merge(orig, on=clave, how="outer", suffixes=("_aj", "_enc"),
                          indicator=True)
        identidades.append((
            anio,
            bool((j["_merge"] == "both").all()),
            float(np.max(np.abs(j[f"{surveys.TRIPS_COL}_aj"].fillna(0)
                                - j[f"{surveys.TRIPS_COL}_enc"].fillna(0)))),
            bool(f.fits[reconstruction._FLOORED_COL].any()),
        ))

    cuota = shares.rename(columns={exposure.ZONE_SHARE_COL: "cuota"})
    for _, fit in f.fits.iterrows():
        modo = fit[config.ACTOR_TYPE_COL]
        pedido = zm.table[zm.table[config.ACTOR_TYPE_COL] == modo].set_index(Z)[
            reconstruction.ZONE_AT_ORIGIN_COL]
        logrado = f.pairs[f.pairs[config.ACTOR_TYPE_COL] == modo].groupby(
            surveys.ZONE_ORIGIN_COL)[surveys.TRIPS_COL].sum()
        c = pd.DataFrame({"pedido": pedido, "logrado": logrado}).fillna(0.0)
        c = c.reset_index(names=Z).merge(cuota, on=Z, how="inner")
        c["pedido"] *= c["cuota"]; c["logrado"] *= c["cuota"]
        g = c.groupby(config.AREA_CODE_COL)[["pedido", "logrado"]].sum()
        peor = float(((g["logrado"] - g["pedido"]).abs()
                      / g["pedido"].where(g["pedido"] > 0, 1.0)).max())
        filas.append({
            "anio": anio, "modo": modo, "siembra": siembra, "s": dt / len(f.fits),
            "piso": bool(fit[reconstruction._FLOORED_COL]),
            "converge": bool(fit[reconstruction._CONVERGED_COL]),
            "iter_desc": int(fit[reconstruction._DISCOVERY_ITERATIONS_COL]),
            "iter": int(fit[reconstruction._ITERATIONS_COL]),
            "error": float(fit[reconstruction._MARGIN_ERROR_COL]),
            "celdas_sem": int(fit[reconstruction._SEED_CELLS_COL]),
            "celdas_aj": int(fit[reconstruction._FITTED_CELLS_COL]),
            "abiertas": int(fit[reconstruction._OPENED_CELLS_COL]),
            "inventado": float(fit[reconstruction._OPENED_TRIPS_COL]),
            "total": float(f.pairs[f.pairs[config.ACTOR_TYPE_COL] == modo][
                surveys.TRIPS_COL].sum()),
            "peor_unidad_%": peor * 100,
        })
print(f"los trece anios en {time.time()-t_total:.0f} s\n")
t = pd.DataFrame(filas)
t["inventado_%"] = t["inventado"] / t["total"] * 100

comprobar("la identidad de D60 sigue siendo exacta en los anios de encuesta",
          all(ok and dif < 1e-6 and not piso for _, ok, dif, piso in identidades),
          "; ".join(f"{a}: {dif:.1e} viajes, piso={'si' if piso else 'no'}"
                    for a, ok, dif, piso in identidades))
comprobar("los 52 bloques convergen", bool(t["converge"].all()),
          f"{int(t['converge'].sum())} de {len(t)}; peor error de margen "
          f"{t['error'].max():.2e}")
comprobar("el piso solo se usa donde hace falta",
          int(t["piso"].sum()) < len(t),
          f"{int(t['piso'].sum())} de {len(t)} bloques lo necesitaron; los otros "
          f"{int((~t['piso']).sum())} alcanzan sus margenes con el soporte de la encuesta")
comprobar("lo inventado se queda muy por debajo de cualquier cifra del estudio",
          float(t["inventado"].sum() / t["total"].sum()) < 1e-3,
          f"{t['inventado'].sum():,.0f} de {t['total'].sum():,.0f} viajes al dia, "
          f"{t['inventado'].sum()/t['total'].sum()*100:.4f} % del total; peor bloque "
          f"{t['inventado_%'].max():.4f} %")
comprobar("ninguna unidad se equivoca de forma apreciable",
          float(t["peor_unidad_%"].max()) < 0.5,
          f"peor unidad {t['peor_unidad_%'].max():.4f} %, contra el 55,74 % sin piso; "
          f"mediana {t['peor_unidad_%'].median():.4f} %")
# El tamano no se juzga contra la semilla sino contra lo que el reparto ya hace: la
# encuesta de 2019 construye 27 437 lineas de deseo en unos diez segundos, asi que un
# bloque reconstruido con un numero de celdas de ese orden no le pide nada que no haga
# ya. Un multiplo de la semilla no dice nada por si solo, porque la semilla de la
# bicicleta de 2011 son 1 360 celdas y la del peaton de 2019 son 9 637.
# El reparto es lineal en el numero de lineas, asi que el doble de lineas es el doble
# de tiempo y nada mas. Dos veces lo que una encuesta ya construye es el limite: por
# encima de eso la etapa empieza a costar mas que todo lo demas junto y habria que
# subir la poda, que es la palanca prevista para ello.
LINEAS_DE_UNA_ENCUESTA = 27_437
comprobar("ningun bloque le pide al reparto mas del doble de lineas que una encuesta",
          int(t["celdas_aj"].max()) <= 2 * LINEAS_DE_UNA_ENCUESTA,
          f"el mayor es {int(t['celdas_aj'].max()):,} celdas ("
          f"{float((t['celdas_aj']/t['celdas_sem']).max()):.1f}x su semilla) contra las "
          f"{2*LINEAS_DE_UNA_ENCUESTA:,} que son el doble de las "
          f"{LINEAS_DE_UNA_ENCUESTA:,} que la encuesta de 2019 ya reparte")

print()
print("por anio y modo: piso (P), iteraciones, % inventado, peor unidad %")
for modo in sorted(t["modo"].unique()):
    b = t[t["modo"] == modo].set_index("anio")
    print(f"  {modo:11s} " + " ".join(
        f"{a}:{'P' if b.loc[a,'piso'] else '-'}{b.loc[a,'inventado_%']:.3f}%"
        for a in b.index))
print()
print("los bloques que necesitaron el piso:")
pis = t[t["piso"]].sort_values("inventado_%", ascending=False)
print(pis[["anio", "modo", "siembra", "iter_desc", "iter", "error", "celdas_sem",
           "celdas_aj", "abiertas", "inventado_%", "peor_unidad_%"]]
      .to_string(index=False, float_format=lambda v: f"{v:.4f}"))

print()
if fallos:
    print(f"{len(fallos)} comprobacion(es) fallan: {'; '.join(fallos)}")
    sys.exit(1)
print("las seis comprobaciones del piso pasan")
