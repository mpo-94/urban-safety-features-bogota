"""Is the blended panel the exposure of a blended matrix, or an average of two exposures?

    .venv/Scripts/python.exe tools/mezcla_de_semillas.py

**Read only.** It fits 2012, 2013 and 2014 from both of the surveys that frame them and
writes nothing but a temporary log. Takes about three minutes. Nothing in `src/` imports
it.

D64 blends at the unit level because it cannot blend anywhere earlier: the four weekday
surveys are keyed on three zonings — 2011 and 2015 share `ZATs_2012_MAG`, 2019 has its
own 1,141 zones and 2023 its own 1,215 — so a cell of 2015 and a cell of 2019 are not
the same object. That raises the question this tool answers.

**The claim is that the apportionment is linear in the trips**, so that

    w · apportion(F1) + (1-w) · apportion(F2)  ==  apportion(w · F1 + (1-w) · F2)

where F1 and F2 are the two fitted matrices. The left side is what the pipeline builds.
If the identity holds, the blended panel is the exposure of one well-defined matrix — the
mixture of the two fitted ones — and not an average of two answers to different questions.

**It can only be checked where the two seeds share a zoning**, because the right-hand
side needs the two matrices added cell by cell. That is 2011 with 2015, which frames
2012, 2013 and 2014. The identity is a property of `exposure._spread` and not of those
years, so checking it there settles it for the pairs where only the left side exists.

**What this does not check, and what an earlier description of it got wrong:** blending
the two *seeds* and fitting the result is a different method and does not give the same
answer, because iterative proportional fitting is not linear — IPF(w·S1 + (1-w)·S2) is
not w·IPF(S1) + (1-w)·IPF(S2). The tool measures that gap too, at the end, so the size of
what was not chosen is on the record rather than assumed to be small.

See D64, `src/reconstruction.py` and `docs/implementing-ipf.md`.
"""

import sys, logging, dataclasses
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import numpy as np
import pandas as pd
import config, exposure, interpolation, loading, population, predictors, reconstruction, surveys
from provenance import RunLog

fallos = []


def comprobar(titulo, pasa, detalle=""):
    print(f"  {'OK  ' if pasa else 'FALLA'}  {titulo}")
    if detalle:
        print(f"           {detalle}")
    if not pasa:
        fallos.append(titulo)


d = REPO / "results" / "_tools_mezcla"
d.mkdir(parents=True, exist_ok=True)
log = RunLog(d)
logging.getLogger().setLevel(logging.ERROR)

DIA = config.MODEL_EXPOSURE_DAY_TYPE
ANOS = (2012, 2013, 2014)
PAR = (2011, 2015)

units = predictors.prepare_units(loading.load_territorial_units(log))
panel, _, _ = population.build(units, log)
measured = interpolation.read_measured(log)
margenes = reconstruction.unit_margins(measured, panel, units, log)
anclas = measured.anchors_of(DIA)

leidas = {}
for e in config.MOBILITY_SURVEYS:
    if e.year in PAR:
        trips = surveys.read(e, log)
        leidas[e.year] = (trips, exposure.zone_area_shares(trips.zones, units, e, log))

# -- 0. Las dos encuestas comparten de verdad las zonas -------------------
print("\n0. La condicion que hace posible la comprobacion\n")
z11 = set(leidas[2011][0].zones[surveys.ZONE_CODE_COL])
z15 = set(leidas[2015][0].zones[surveys.ZONE_CODE_COL])
comprobar("2011 y 2015 estan en la misma zonificacion",
          z11 == z15,
          f"{len(z11):,} zonas en 2011 y {len(z15):,} en 2015; "
          f"{len(z11 & z15):,} comunes, {len(z11 ^ z15)} distintas")

CLAVE = [config.ACTOR_TYPE_COL, config.DAY_TYPE_COL,
         surveys.ZONE_ORIGIN_COL, surveys.ZONE_DESTINATION_COL]
CANT = [surveys.TRIPS_COL, surveys.TRIPS_OVER_15MIN_COL]
UNIDAD = [config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]
# En base de dia medio: es donde el reparto es lineal sin division de por medio. La
# conversion a dia-tipo divide cada componente por la cuota de universo de su propia
# encuesta, que es una decision aparte y documentada en `blend_components`.
MEDIDAS = [config.TRIPS_PER_AVERAGE_DAY_COL, surveys.TRIPS_OVER_15MIN_COL,
           config.TRIPS_AT_ORIGIN_COL, config.TRIPS_AT_DESTINATION_COL]


def ajustar(anio, siembra):
    trips, shares = leidas[siembra]
    objetivo = margenes[(margenes[config.YEAR_COL] == anio)
                        & (margenes[config.DAY_TYPE_COL] == DIA)]
    zm = reconstruction.zone_margins(trips, shares, objetivo, anio, log)
    return reconstruction.fit_year(trips, zm, log)


def sumar_matrices(pa, pb, wa, wb):
    """w_a*A + w_b*B celda a celda, sobre la union de las celdas de las dos.

    Las dos tienen que estar en la misma zonificacion, que es lo que el punto 0
    comprueba antes de llamar aqui.
    """
    pa, pb = pa[CLAVE + CANT].copy(), pb[CLAVE + CANT].copy()
    for c in CANT:
        pa[c] = pa[c] * wa
        pb[c] = pb[c] * wb
    return pd.concat([pa, pb]).groupby(CLAVE, as_index=False)[CANT].sum()


print("\n1. Repartir y mezclar, contra mezclar y repartir\n")
print(f"  {'anio':<6}{'pesos':<22}{'celdas':>10}{'peor dif.':>14}{'relativa':>12}")
for anio in ANOS:
    mezcla = reconstruction.seeding_blend(anio, anclas)
    if len(mezcla) != 2:
        continue
    (y1, w1), (y2, w2) = mezcla
    f1, f2 = ajustar(anio, y1), ajustar(anio, y2)

    # Camino de la izquierda: el del pipeline.
    izquierda = reconstruction.blend_components(
        [(y1, w1, reconstruction.apportion(f1, units, log)),
         (y2, w2, reconstruction.apportion(f2, units, log))], mezcla)

    # Camino de la derecha: sumar las dos matrices ajustadas y repartir una sola vez.
    # La copia lleva la semilla de la primera porque `apportion` necesita un SurveyTrips;
    # lo unico que se le toma es la geometria de las zonas, que las dos comparten.
    sumada = sumar_matrices(f1.pairs, f2.pairs, w1, w2)
    como_una = reconstruction.FittedYear(
        seed=f1.seed, year=anio, pairs=sumada, fits=f1.fits)
    derecha = reconstruction.apportion(como_una, units, log)

    juntas = izquierda.merge(derecha, on=UNIDAD, suffixes=("_izq", "_der"))
    peor, peor_rel = 0.0, 0.0
    for c in MEDIDAS:
        dif = np.abs(juntas[f"{c}_izq"] - juntas[f"{c}_der"])
        escala = np.maximum(np.abs(juntas[f"{c}_der"]), 1.0)
        peor = max(peor, float(dif.max()))
        peor_rel = max(peor_rel, float((dif / escala).max()))
    pesos = f"{y1}:{w1:.2f}  {y2}:{w2:.2f}"
    print(f"  {anio:<6}{pesos:<22}{len(juntas):>10,}{peor:>14.2e}{peor_rel:>12.2e}")
    comprobar(f"{anio}: los dos caminos dan el mismo reparto",
              peor_rel < 1e-9,
              f"peor diferencia {peor:.2e} viajes/dia, {peor_rel:.2e} relativa")

print("\n2. Lo que NO se eligio: mezclar las semillas y ajustar despues\n")
print("  El ajuste proporcional iterativo no es lineal, asi que este camino da otra cosa.")
print("  Se mide para que el tamano de la diferencia este en el acta y no supuesto.\n")
print(f"  {'anio':<6}{'celdas':>10}{'mediana razon':>16}{'p95 razon':>12}{'peor unidad':>14}")
for anio in ANOS:
    mezcla = reconstruction.seeding_blend(anio, anclas)
    if len(mezcla) != 2:
        continue
    (y1, w1), (y2, w2) = mezcla
    t1, s1 = leidas[y1]
    t2, _ = leidas[y2]
    semilla = sumar_matrices(t1.pairs, t2.pairs, w1, w2)
    # `replace` y no el constructor: enumerar los campos a mano se rompe en cuanto
    # `SurveyTrips` gana uno, que es justo lo que paso la primera vez que esto corrio.
    # Los recuentos que vienen de la primera encuesta no los lee nada de aqui abajo.
    mezclada = dataclasses.replace(
        t1, pairs=semilla,
        universe_shares=t1.universe_shares * w1 + t2.universe_shares * w2)
    objetivo = margenes[(margenes[config.YEAR_COL] == anio)
                        & (margenes[config.DAY_TYPE_COL] == DIA)]
    zm = reconstruction.zone_margins(mezclada, s1, objetivo, anio, log)
    otra = reconstruction.apportion(reconstruction.fit_year(mezclada, zm, log), units, log)

    f1, f2 = ajustar(anio, y1), ajustar(anio, y2)
    nuestra = reconstruction.blend_components(
        [(y1, w1, reconstruction.apportion(f1, units, log)),
         (y2, w2, reconstruction.apportion(f2, units, log))], mezcla)
    juntas = nuestra.merge(otra, on=UNIDAD, suffixes=("_nue", "_otr"))
    c = config.TRIPS_PER_AVERAGE_DAY_COL
    vivas = juntas[juntas[f"{c}_otr"] > 0]
    razon = vivas[f"{c}_nue"] / vivas[f"{c}_otr"]
    print(f"  {anio:<6}{len(vivas):>10,}{float(razon.median()):>16.4f}"
          f"{float(razon.quantile(0.95)):>12.4f}"
          f"{float(np.max(np.abs(np.log(razon)))):>14.4f}")

print()
print(f"{'TODO BIEN' if not fallos else str(len(fallos)) + ' FALLO(S): ' + '; '.join(fallos)}")
