"""Does the weekday-only path hold, end to end, before the fitting is built on it?

    .venv/Scripts/python.exe tools/camino_del_dia_habil.py

**Read only.** It builds the unit margins and the five surveys in memory, disaggregates
the thirteen years the regressions read, and asks `fitting` whether it could reach what it
would be given. It writes nothing but a temporary log, and fits nothing.

Two decisions of 2026-10-07 changed the path the reconstruction walks: the fitting is
scoped to the weekday (`config.RECONSTRUCTION_DAY_TYPES`) and the part of a margin falling
outside the thirty units is scaled by the city rather than held
(`config.OUTSIDE_MARGIN_RULE`). Everything checked before them was checked on three day
types and under the other rule, so none of it covered the path that would actually run.
Verifying a path before building on it is cheap; finding out afterwards is not.

Three groups of questions:

  **A. The unit margins do not depend on the other kinds of day.** If they did, scoping to
  the weekday would be a change of result dressed up as a simplification. They do not: the
  2,400 weekday rows are identical built alone or built beside the Saturday and the Sunday,
  because the reconciliation groups by year, mode and day type and so never looks across
  them. It also reports what the scoping does to the worst correction — 1.68 % over the
  whole table, a Saturday, against 0.22 % among the weekday rows the fitting is handed.

  **B. The disaggregation holds under the city rule, over thirteen years.** The identity at
  2015, 2019 and 2023 comes back to 4e-12 trips per day; no zero of a seed turns positive;
  no cell is negative; the two margins agree in all 52 blocks; and the zone-level
  correction stays the smaller of the two.

  **C. The fitting can reach what it will be given.** `unfittable_margins` has nothing to
  say about any of the 87,320 margins of the 52 blocks, and nothing at all is unplaceable
  — the units with no seed travel were Saturday cases. It also prints the size of each
  fitting, the largest being 13,029 non-zero cells on 887 zones.

See D54, D60, `src/reconstruction.py`, `tools/desagregacion_a_zonas.py`.
"""

import sys, logging
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

d = REPO / "results" / "_tools_barrido"
d.mkdir(parents=True, exist_ok=True)
log = RunLog(d)
logging.getLogger().setLevel(logging.ERROR)

DIA = config.MODEL_EXPOSURE_DAY_TYPE
O, D = reconstruction.ZONE_AT_ORIGIN_COL, reconstruction.ZONE_AT_DESTINATION_COL
UO, UD = config.MARGIN_AT_ORIGIN_COL, config.MARGIN_AT_DESTINATION_COL
fO, fD = (config.MARGIN_AT_ORIGIN_RECONCILIATION_COL,
          config.MARGIN_AT_DESTINATION_RECONCILIATION_COL)
Z = surveys.ZONE_CODE_COL

print(f"regla de afuera: {config.OUTSIDE_MARGIN_RULE}")
print(f"tipos de dia de la reconstruccion: {config.RECONSTRUCTION_DAY_TYPES}")
print(f"dia que leen los modelos: {config.MODEL_EXPOSURE_DAY_TYPE}\n")

units = predictors.prepare_units(loading.load_territorial_units(log))
panel, _, _ = population.build(units, log)
measured = interpolation.read_measured(log)
margenes = reconstruction.unit_margins(measured, panel, units, log)

# == A. El punto 1 no depende de los otros tipos de dia ====================
print("A. los margenes por unidad, con y sin los otros tipos de dia")
recortada = interpolation.MeasuredExposure(
    table=measured.table[measured.table[config.DAY_TYPE_COL] == DIA].copy(),
    city_totals=measured.city_totals,
    source_run=measured.source_run,
)
solo = reconstruction.unit_margins(recortada, panel, units, log)
hab = margenes[margenes[config.DAY_TYPE_COL] == DIA].reset_index(drop=True)
clave_u = [config.AREA_CODE_COL, config.YEAR_COL, config.ACTOR_TYPE_COL]
j = hab.merge(solo, on=clave_u, suffixes=("_todos", "_solo"))
igual = all(
    np.allclose(j[f"{c}_todos"], j[f"{c}_solo"], rtol=1e-12)
    for c in (UO, UD, fO, fD, config.MARGIN_AT_ORIGIN_RATE_COL)
)
comprobar("los margenes del dia habil son los mismos construidos solos o con los tres",
          len(j) == len(hab) == len(solo) and igual,
          f"{len(j)} filas comparadas; la reconciliacion agrupa por anio, modo y tipo "
          f"de dia, asi que el habil nunca mira los otros")

peor_u = float((hab[[fO, fD]] - 1.0).abs().max().max())
comprobar("la peor reconciliacion de unidad del habil esta bajo el umbral",
          peor_u <= config.MARGIN_RECONCILIATION_LIMIT,
          f"{peor_u*100:.4f} % en el habil, contra el 1,6828 % que el sabado tiene y "
          f"que es el que fija el umbral del {config.MARGIN_RECONCILIATION_LIMIT*100:.0f} %")

# == B y C. El punto 2 y el ajuste, sobre los trece anios ==================
print()
print("B y C. la desagregacion y el ajuste, sobre los trece anios del habil")
anclas = measured.anchors_of(DIA)
leidas = {}
for encuesta in config.MOBILITY_SURVEYS:
    trips = surveys.read(encuesta, log)
    leidas[encuesta.year] = (trips, exposure.zone_area_shares(trips.zones, units, encuesta, log))

resumen = []
problemas_ajuste = 0
ceros_roto = 0
negativos = 0
desajuste_peor = 0.0
recon_peor = 0.0
movido_peor = 0.0
no_colocado = 0.0
colocado_total = 0.0
identidades = []

# Desde D64 un anio descansa en dos encuestas. El recorrido pasa a ser por componente
# de la mezcla en vez de por anio, lo que mide mas y no menos: lo que se observa de
# cada semilla es exactamente lo que se observaba cuando habia una sola.
AN_SI = [(a, s) for a in config.REGRESSION_YEARS
         for s, _ in reconstruction.seeding_blend(a, anclas)]
for anio, siembra in AN_SI:
    sel = (margenes[config.YEAR_COL] == anio) & (margenes[config.DAY_TYPE_COL] == DIA)
    objetivo = margenes[sel]
    trips, shares = leidas[siembra]
    r = reconstruction.zone_margins(trips, shares, objetivo, anio)
    semilla_zonas = reconstruction.seed_zone_margins(trips.pairs)
    semilla_zonas = semilla_zonas[semilla_zonas[config.DAY_TYPE_COL] == DIA]

    # los ceros de la semilla
    cmp = semilla_zonas.merge(r.table, on=[config.ACTOR_TYPE_COL, config.DAY_TYPE_COL, Z])
    ceros_roto += int(((cmp["_SEED_AT_ORIGIN"] == 0) & (cmp[O] > 0)).sum())
    ceros_roto += int(((cmp["_SEED_AT_DESTINATION"] == 0) & (cmp[D] > 0)).sum())
    negativos += int((r.table[[O, D]] < 0).sum().sum())

    g = r.table.groupby(config.ACTOR_TYPE_COL)[[O, D]].sum()
    desajuste_peor = max(desajuste_peor,
                         float(((g[O] - g[D]).abs() / g[D].where(g[D] > 0, 1.0)).max()))
    recon_peor = max(recon_peor, r.worst_reconciliation)
    movido_peor = max(movido_peor, r.share_of_trips_reconciled)
    no_colocado += float(r.unplaceable["TRIPS_PER_DAY"].sum())
    colocado_total += float(r.table[O].sum())

    # la identidad, donde el anio es su propia semilla
    if anio == siembra:
        dif = float(np.max(np.abs(cmp[O] - cmp["_SEED_AT_ORIGIN"])))
        identidades.append((anio, dif))

    # el ajuste: puede alcanzar estos margenes?
    for modo in sorted(r.table[config.ACTOR_TYPE_COL].unique()):
        bloque = r.table[r.table[config.ACTOR_TYPE_COL] == modo]
        zonas = sorted(bloque[Z].unique())
        indice = {z: i for i, z in enumerate(zonas)}
        p = trips.pairs
        p = p[(p[config.ACTOR_TYPE_COL] == modo) & (p[config.DAY_TYPE_COL] == DIA)]
        m = np.zeros((len(zonas), len(zonas)))
        for o, de, v in zip(p[surveys.ZONE_ORIGIN_COL], p[surveys.ZONE_DESTINATION_COL],
                            p[surveys.TRIPS_COL]):
            if o in indice and de in indice:
                m[indice[o], indice[de]] += v
        b = bloque.set_index(Z)
        filas = b.loc[zonas, O].to_numpy()
        cols = b.loc[zonas, D].to_numpy()
        cols = cols * (filas.sum() / cols.sum())
        malos = fitting.unfittable_margins(m, filas, cols)
        problemas_ajuste += len(malos)
        if malos:
            print(f"      {anio} {modo}: {malos[0][:88]}")
        resumen.append({"anio": anio, "modo": modo, "siembra": siembra,
                        "zonas": len(zonas), "celdas_semilla": int((m > 0).sum()),
                        "inalcanzables": len(malos)})

t = pd.DataFrame(resumen)
print()
comprobar("la identidad se mantiene en los anios de encuesta del tramo",
          all(dif < 1e-6 for _, dif in identidades),
          "; ".join(f"{a}: {dif:.2e} viajes" for a, dif in identidades))
comprobar("ningun cero de la semilla se vuelve positivo", ceros_roto == 0,
          f"{ceros_roto} celda(s) rotas en los trece anios")
comprobar("ninguna celda negativa", negativos == 0, f"{negativos} celda(s)")
comprobar("los dos margenes de zona cuadran en los 52 bloques",
          desajuste_peor < 1e-12, f"peor diferencia relativa {desajuste_peor:.2e}")
comprobar("la reconciliacion por componente mueve una parte despreciable",
          movido_peor < 1e-3,
          f"peor anio: {movido_peor*100:.4f} % de los viajes movidos, contra "
          f"{peor_u*100:.4f} % de correccion a escala de unidad")
comprobar("el ajuste alcanza todos los margenes de los 52 bloques",
          problemas_ajuste == 0,
          f"{problemas_ajuste} margen(es) inalcanzable(s) de "
          f"{int(t['zonas'].sum())*2} margenes en total")
comprobar("lo no colocable es despreciable",
          no_colocado / colocado_total < 1e-4,
          f"{no_colocado:,.1f} de {colocado_total:,.0f} viajes al dia, "
          f"{no_colocado/colocado_total*100:.6f} %")

print()
print("el tamano de cada ajuste, por anio y modo:")
print(t.pivot_table(index="anio", columns="modo", values="celdas_semilla",
                    aggfunc="first").to_string())
print()
print(f"zonas por anio: " + ", ".join(
    f"{a}:{int(v)}" for a, v in t.groupby('anio')['zonas'].first().items()))
print(f"siembra por anio: " + ", ".join(
    f"{a}->{int(v)}" for a, v in t.groupby('anio')['siembra'].first().items()))

print()
if fallos:
    print(f"{len(fallos)} comprobacion(es) fallan: {'; '.join(fallos)}")
    sys.exit(1)
print("las ocho comprobaciones del barrido pasan")
