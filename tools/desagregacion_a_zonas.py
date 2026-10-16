"""Does the disaggregation give back the survey when it is handed the survey?

    .venv/Scripts/python.exe tools/desagregacion_a_zonas.py

**Read only.** It builds the unit margins and two survey years in memory, disaggregates
them, and writes nothing but a temporary log. Nothing in `src/` imports it.

D60 brings a year's margins down to the thirty units, where the five surveys are
comparable, and then has to put them back on the zones of the survey that seeds the
year. That second step is the assumption the entropy argument does not cover, so what
can be checked about it has to be checked: eleven properties, each against a figure from
outside the function that produced it.

**The one that decides is the identity.** Disaggregating a survey year's own margins onto
its own zones has to return that survey's zone margins, cell by cell, because every
growth factor is one. It comes back to 1.5e-11 trips per day on margins of millions.

Two of the eleven exist because of defects this script found, and both were silent:

  * **The identity on one block.** The fitting runs per mode and kind of day, so the
    disaggregation is handed a subset of the seed's blocks. A block the seed carried and
    the targets did not was left with its inside at zero and its outside still held at
    the survey's level — a block of pure ring, whose two margins disagree because the
    ring is not symmetric between origins and destinations. It cost the identity 4.65 %.

  * **A day type the seed does not measure.** 2011 measured no Sunday, and 2011's Sunday
    margins are seeded from 2023. Handing them to 2011 returned all 120 unit-mode
    combinations as unplaceable, which is the word for something small and real and not
    for a stage wired to the wrong survey. It is an error now, and it says why.

The last check is the one the next step depends on: `fitting.unfittable_margins` has
nothing to say about any of the eight blocks, so the margins this produces are margins
some matrix actually has.

See D54, D60, `src/reconstruction.py` and `tools/ajuste_proporcional.py`.
"""

import sys, logging
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

d = REPO / "results" / "_tools_zonas"
d.mkdir(parents=True, exist_ok=True)
log = RunLog(d)
logging.getLogger().setLevel(logging.ERROR)

units = predictors.prepare_units(loading.load_territorial_units(log))
panel, _, _ = population.build(units, log)
measured = interpolation.read_measured(log)
margenes = reconstruction.unit_margins(measured, panel, units, log)

O, D = reconstruction.ZONE_AT_ORIGIN_COL, reconstruction.ZONE_AT_DESTINATION_COL
UO, UD = config.MARGIN_AT_ORIGIN_COL, config.MARGIN_AT_DESTINATION_COL
Z = surveys.ZONE_CODE_COL

# Se leen dos encuestas: 2011 siembra 2012-2013 y 2015 siembra 2014-2017.
leidas = {}
for anio in (2011, 2015):
    encuesta = next(s for s in config.MOBILITY_SURVEYS if s.year == anio)
    trips = surveys.read(encuesta, log)
    leidas[anio] = (trips, exposure.zone_area_shares(trips.zones, units, encuesta, log))
print(f"leidas {len(leidas)} encuestas\n")

# -- 1. La identidad -------------------------------------------------------
# Los margenes de 2011 sobre las zonas de 2011: el factor de crecimiento es 1 en las
# treinta unidades y la parte de afuera se sostiene, asi que el resultado es la semilla.
trips11, shares11 = leidas[2011]
# Los objetivos se filtran por el tipo de dia que la semilla mide: 2011 no midio
# domingo, y el domingo de 2011 se siembra en 2023. La funcion lo exige y lo dice.
def objetivos(anio, trips, solo_reconstruidos=False):
    dias = set(trips.universe_shares.index)
    if solo_reconstruidos:
        dias &= set(config.RECONSTRUCTION_DAY_TYPES)
    sel = (margenes[config.YEAR_COL] == anio) & margenes[config.DAY_TYPE_COL].isin(dias)
    return margenes[sel]

objetivo11 = objetivos(2011, trips11)
r = reconstruction.zone_margins(trips11, shares11, objetivo11, 2011, log)
semilla11 = reconstruction.seed_zone_margins(trips11.pairs)
clave = [config.ACTOR_TYPE_COL, config.DAY_TYPE_COL, Z]
j = r.table.merge(semilla11, on=clave, how="outer", indicator=True)
exacto = (
    (j["_merge"] == "both").all()
    and np.allclose(j[O], j["_SEED_AT_ORIGIN"], rtol=1e-12, atol=1e-9)
    and np.allclose(j[D], j["_SEED_AT_DESTINATION"], rtol=1e-12, atol=1e-9)
)
comprobar("desagregar un anio de encuesta sobre sus propias zonas devuelve la semilla",
          exacto,
          f"{len(j)} celdas, diferencia maxima "
          f"{max(np.max(np.abs(j[O]-j['_SEED_AT_ORIGIN'])), np.max(np.abs(j[D]-j['_SEED_AT_DESTINATION']))):.2e} "
          f"viajes al dia")
comprobar("y no deja nada sin colocar en un anio de encuesta",
          len(r.unplaceable) == 0,
          f"{len(r.unplaceable)} unidad(es) sin semilla donde el objetivo pide algo")
comprobar("y su reconciliacion de zona es exactamente 1",
          abs(r.worst_reconciliation) < 1e-12,
          f"peor factor {r.worst_reconciliation:+.2e}")

# -- 1b. La identidad sobre un solo bloque -------------------------------
# El ajuste corre por bloque, asi que la desagregacion recibe un subconjunto de los
# bloques de la semilla. La identidad tiene que seguir saliendo: un bloque que la
# semilla lleva y los objetivos no se recorta, en vez de quedarse con la parte interior
# en cero y la de afuera sostenida. Eso costaba 4,65 % a la identidad.
solo_laboral = objetivo11[objetivo11[config.DAY_TYPE_COL] == "WEEKDAY"]
r1 = reconstruction.zone_margins(trips11, shares11, solo_laboral, 2011)
s1 = semilla11[semilla11[config.DAY_TYPE_COL] == "WEEKDAY"]
j1 = r1.table.merge(s1, on=clave, how="outer", indicator=True)
comprobar("la identidad se mantiene cuando se pide un solo tipo de dia",
          (j1["_merge"] == "both").all()
          and np.allclose(j1[O], j1["_SEED_AT_ORIGIN"], rtol=1e-12, atol=1e-9)
          and abs(r1.worst_reconciliation) < 1e-12,
          f"{len(j1)} celdas, reconciliacion {r1.worst_reconciliation:+.2e}; "
          f"el sabado de la semilla se recorta y no se vacia")

# -- 1c. Las dos reglas de afuera coinciden en un anio de encuesta -------
# El factor de la ciudad es exactamente 1 cuando el objetivo es la propia encuesta, asi
# que sostener la parte de afuera y escalarla por la ciudad son lo mismo. Si difieren,
# algun bloque se esta escalando por un factor que no es el suyo.
totales = {}
for regla in config.OUTSIDE_MARGIN_RULES:
    config.OUTSIDE_MARGIN_RULE = regla
    totales[regla] = float(
        reconstruction.zone_margins(trips11, shares11, objetivo11, 2011).table[O].sum())
config.OUTSIDE_MARGIN_RULE = "HELD"
comprobar("en un anio de encuesta las dos reglas de afuera dan lo mismo",
          np.isclose(totales["HELD"], totales["CITY"], rtol=1e-12),
          f"HELD {totales['HELD']:,.1f} contra CITY {totales['CITY']:,.1f}")

# -- 2. Un anio construido ------------------------------------------------
print()
r13 = reconstruction.zone_margins(trips11, shares11, objetivos(2013, trips11, True), 2013, log)
print(f"2013 sembrado en {r13.seed_year}: {len(r13.table):,} celdas, "
      f"{r13.table[Z].nunique()} zonas")

ceros = semilla11.merge(r13.table, on=clave, how="inner")
sin_semilla = ceros["_SEED_AT_ORIGIN"] == 0
comprobar("un cero de la semilla sigue siendo cero en el anio construido",
          bool((ceros.loc[sin_semilla, O] == 0).all()),
          f"{int(sin_semilla.sum())} celdas de origen en cero, todas conservadas")

g = r13.table.groupby([config.ACTOR_TYPE_COL, config.DAY_TYPE_COL])[[O, D]].sum()
dif = (g[O] - g[D]).abs() / g[D].where(g[D] > 0, 1.0)
comprobar("los dos margenes de zona suman lo mismo en cada bloque",
          float(dif.max()) < 1e-12,
          f"{len(g)} bloques, peor diferencia relativa {float(dif.max()):.2e}")

# La reconciliacion de zona se juzga por viajes movidos y no por el peor factor: un
# componente de cuarenta viajes puede necesitar que le partan el margen por la mitad sin
# que eso signifique nada, y el componente que lleva casi toda la matriz no puede moverse
# un uno por ciento sin que signifique mucho.
comprobar("la reconciliacion por componente mueve una parte despreciable de los viajes",
          r13.share_of_trips_reconciled < 1e-3,
          f"{r13.share_of_trips_reconciled*100:.4f} % de los viajes movidos; el peor "
          f"componente suelto necesita {r13.worst_reconciliation*100:.1f} % y es de los "
          f"que llevan dos o tres zonas")

comprobar("ninguna celda negativa",
          bool((r13.table[[O, D]] >= 0).all().all()),
          f"{int((r13.table[[O, D]] == 0).sum().sum())} celdas en cero")

# -- 3. El ajuste acepta lo que se le entrega -----------------------------
print()
import fitting
problemas_totales = 0
for (actor, dia), bloque in r13.table.groupby([config.ACTOR_TYPE_COL, config.DAY_TYPE_COL]):
    zonas = sorted(bloque[Z].unique())
    indice = {z: i for i, z in enumerate(zonas)}
    p = trips11.pairs
    p = p[(p[config.ACTOR_TYPE_COL] == actor) & (p[config.DAY_TYPE_COL] == dia)]
    semilla = np.zeros((len(zonas), len(zonas)))
    for o, de, v in zip(p[surveys.ZONE_ORIGIN_COL], p[surveys.ZONE_DESTINATION_COL],
                        p[surveys.TRIPS_COL]):
        if o in indice and de in indice:
            semilla[indice[o], indice[de]] += v
    b = bloque.set_index(Z)
    filas = b.loc[zonas, O].to_numpy()
    cols = b.loc[zonas, D].to_numpy()
    # Los dos margenes tienen que cuadrar exacto para el ajuste; aqui cuadran por
    # construccion salvo el error de punto flotante, que se absorbe en el destino.
    cols = cols * (filas.sum() / cols.sum())
    problemas = fitting.unfittable_margins(semilla, filas, cols)
    problemas_totales += len(problemas)
    if problemas:
        print(f"   {actor} {dia}: {len(problemas)} margen(es) inalcanzable(s) -> "
              f"{problemas[0][:90]}")
comprobar("el ajuste puede alcanzar todos los margenes que la desagregacion entrega",
          problemas_totales == 0,
          f"{problemas_totales} margen(es) inalcanzable(s) en los ocho bloques")

# -- 4. Un anio que cambia de zonificacion -------------------------------
print()
trips15, shares15 = leidas[2015]
r17 = reconstruction.zone_margins(trips15, shares15, objetivos(2017, trips15, True), 2017, log)
print(f"2017 sembrado en {r17.seed_year}: {len(r17.table):,} celdas")
# Desde D64 no hay empate que declarar: 2017 esta exactamente entre 2015 y 2019 y
# descansa en las dos a partes iguales. Lo que se comprueba ya no es que gane una,
# sino que la mezcla sea simetrica — que es lo que dejo sin uso a config.SEED_ON_TIE.
mezcla17 = reconstruction.seeding_blend(2017, (2011, 2015, 2019, 2023))
comprobar("2017 descansa en 2015 y 2019 a partes iguales, sin empate que declarar",
          mezcla17 == ((2015, 0.5), (2019, 0.5)),
          f"mezcla de 2017 = {mezcla17}")

# -- 4b. Entregar un tipo de dia que la semilla no mide es un error ------
try:
    reconstruction.zone_margins(trips11, shares11,
                                margenes[margenes[config.YEAR_COL] == 2011], 2011)
    comprobar("un tipo de dia que la semilla no mide se levanta como error", False,
              "no levanto nada, y las 120 combinaciones del domingo habrian salido "
              "como no colocables")
except ValueError as e:
    comprobar("un tipo de dia que la semilla no mide se levanta como error",
              "sunday" in str(e), str(e)[:110])

# -- 5. Lo que la regla de afuera decide ---------------------------------
print()
fuera = {}
for regla in config.OUTSIDE_MARGIN_RULES:
    config.OUTSIDE_MARGIN_RULE = regla
    rr = reconstruction.zone_margins(trips11, shares11,
                                     objetivos(2013, trips11, True), 2013)
    fuera[regla] = float(rr.table[O].sum())
config.OUTSIDE_MARGIN_RULE = "HELD"
print("total del margen de origen de 2013, por regla:")
for regla, v in fuera.items():
    print(f"   {regla:5s}  {v:,.0f} viajes al dia")
print(f"   la diferencia entre las dos reglas es "
      f"{(fuera['CITY']/fuera['HELD']-1)*100:+.2f} % del total")

print()
if fallos:
    print(f"{len(fallos)} comprobacion(es) fallan: {'; '.join(fallos)}")
    sys.exit(1)
print("las once comprobaciones de la desagregacion pasan")
