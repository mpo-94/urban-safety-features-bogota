"""Do the margins the fitting will be given hold every property it takes for granted?

    .venv/Scripts/python.exe tools/margenes_para_el_ajuste.py

**Read only.** It builds the margin table in memory from a finished exposure run and the
population panel, and writes nothing but a temporary log. Nothing in `src/` imports it.

Iterative proportional fitting is twenty lines and it will accept almost anything. What
decides whether the reconstructed matrix means anything is what it is handed, and this
checks each of those properties against a figure that comes from outside the function
that produced it — the measured exposure table, the survey declarations, or arithmetic
done here a second way.

Eleven checks, each named by what would break if it failed. Three are worth naming here
because the numbers they print are cited in `docs/implementing-ipf.md` and in D60:

  * **The reconciliation.** The two margins of a year disagree about the grand total and
    no matrix has both. The worst correction is 1.68 %, the Saturday motorcycle of 2013,
    and `config.MARGIN_RECONCILIATION_LIMIT` sits just above it at 2 %.

  * **2005's pedestrian margin does not anchor.** It counts only walking of fifteen
    minutes or more where the other four surveys count all of it: 0.163 trips per
    inhabitant against 0.737 in 2011, a factor of 4.5. The exclusion is declared on the
    column in `config.MOBILITY_SURVEYS`, and this is the measurement that says the
    declaration earns its place.

  * **A margin is not an exposure.** UPL04 on the Saturday of 2011 has 1,351 cycling
    trips of exposure and a margin of zero at both ends: travel crossing it, none of it
    local. That difference is why D60 fits at zone level rather than between units.

See D54, D60, `src/reconstruction.py` and `src/fitting.py`.
"""

import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import numpy as np
import pandas as pd
import config, interpolation, loading, population, predictors, reconstruction
from provenance import RunLog

fallos = []
def comprobar(titulo, pasa, detalle=""):
    print(f"  {'OK  ' if pasa else 'FALLA'}  {titulo}")
    if detalle:
        print(f"           {detalle}")
    if not pasa:
        fallos.append(titulo)

d = REPO / "results" / "_tools_margenes"
d.mkdir(parents=True, exist_ok=True)
log = RunLog(d)
units = loading.load_territorial_units(log)
panel, _, _ = population.build(units, log)
measured = interpolation.read_measured(log)
m = reconstruction.unit_margins(measured, panel, predictors.prepare_units(units), log)

O, D = config.MARGIN_AT_ORIGIN_COL, config.MARGIN_AT_DESTINATION_COL
rO, rD = config.MARGIN_AT_ORIGIN_RATE_COL, config.MARGIN_AT_DESTINATION_RATE_COL
fO, fD = (config.MARGIN_AT_ORIGIN_RECONCILIATION_COL,
          config.MARGIN_AT_DESTINATION_RECONCILIATION_COL)
print()
print(f"tabla: {len(m)} filas, {m['YEAR'].min()}-{m['YEAR'].max()}, "
      f"{m['AREA_CODE'].nunique()} unidades")
print(m["EXPOSURE_PROVENANCE"].value_counts().to_string())
print()

# -- 1. Los anios de encuesta llevan la cifra de la encuesta -------------------
# Contra la tabla medida, no contra si misma: el margen por dia de tipo tiene que
# ser la columna de dia promedio dividida por la cuota del universo.
t = measured.table
esperado = t.assign(
    O_esp=t[config.TRIPS_AT_ORIGIN_COL] / t[config.DAY_TYPE_UNIVERSE_SHARE_COL],
    D_esp=t[config.TRIPS_AT_DESTINATION_COL] / t[config.DAY_TYPE_UNIVERSE_SHARE_COL],
)[["AREA_CODE", "YEAR", "ACTOR_TYPE", "DAY_TYPE", "O_esp", "D_esp"]]
j = m.merge(esperado, on=["AREA_CODE", "YEAR", "ACTOR_TYPE", "DAY_TYPE"], how="inner")
comprobar("los anios de encuesta reproducen la tabla medida sobre la cuota del universo",
          len(j) == len(esperado)
          and np.allclose(j[O], j["O_esp"], rtol=1e-12)
          and np.allclose(j[D], j["D_esp"], rtol=1e-12),
          f"{len(j)} filas comparadas, diferencia maxima "
          f"{max(np.max(np.abs(j[O]-j['O_esp'])), np.max(np.abs(j[D]-j['D_esp']))):.2e}")

# -- 2. Los anios de encuesta no se reconcilian -------------------------------
anclado = pd.Series(False, index=m.index)
for dia in m["DAY_TYPE"].unique():
    anclado |= (m["DAY_TYPE"] == dia) & m["YEAR"].isin(measured.anchors_of(dia))
enc = m[anclado]
con = m[~anclado]
comprobar("solo lo que una encuesta midio de su propio tipo de dia lleva factor 1",
          bool((enc[fO] == 1.0).all() and (enc[fD] == 1.0).all()),
          f"{len(enc)} filas ancladas, {len(con)} construidas; el sabado de 2019 y el domingo de 2011 cuentan como construidos porque ninguna encuesta los midio")

# -- 3. Los anios construidos cuadran los dos totales -------------------------
g = con.groupby(["YEAR", "ACTOR_TYPE", "DAY_TYPE"])[[O, D]].sum()
dif = (g[O] - g[D]).abs() / g[D].where(g[D] > 0, 1.0)
comprobar("en todo anio construido los dos margenes suman lo mismo",
          float(dif.max()) < 1e-12,
          f"{len(g)} grupos, peor diferencia relativa {float(dif.max()):.2e}")

# -- 4. La reconciliacion es pequena y acotada -------------------------------
# El umbral no es una preferencia: 2 % es config.MARGIN_RECONCILIATION_LIMIT, y esta
# puesto justo encima de lo que los datos de hoy producen. Lo que la correccion mide
# es que una suma de curvas log-lineales por unidad no es la curva de la suma, asi
# que crece con lo desigual que sea el movimiento de las unidades entre dos encuestas.
peor = float((con[[fO, fD]] - 1.0).abs().max().max())
comprobar("ninguna reconciliacion pasa del umbral declarado",
          peor <= config.MARGIN_RECONCILIATION_LIMIT,
          f"peor correccion {peor*100:.4f} % contra el umbral "
          f"{config.MARGIN_RECONCILIATION_LIMIT*100:.1f} %")

# -- 5. La reconciliacion conserva el total de los dos juntos -----------------
# El objetivo es la media, asi que la suma de los dos margenes no se mueve.
antes = con[O] / con[fO] + con[D] / con[fD]
comprobar("la suma de los dos margenes no la mueve la reconciliacion",
          np.allclose(antes.groupby([con["YEAR"], con["ACTOR_TYPE"], con["DAY_TYPE"]]).sum(),
                      (con[O] + con[D]).groupby(
                          [con["YEAR"], con["ACTOR_TYPE"], con["DAY_TYPE"]]).sum(),
                      rtol=1e-12),
          "el objetivo es la media de los dos totales")

# -- 6. Nada negativo, nada nulo ---------------------------------------------
comprobar("ningun margen negativo y ningun nulo",
          bool((m[[O, D]] >= 0).all().all() and m[[O, D]].notna().all().all()),
          f"{int((m[[O, D]] == 0).sum().sum())} celdas en cero, que son observaciones")

# -- 7. El peaton de 2005 no ancla ------------------------------------------
# 2005 cuenta solo la caminata larga, asi que su margen de peaton no puede anclar:
# 2006-2010 tienen que sostenerse de 2011. Se compara la TASA y no el nivel, porque
# lo que se sostiene es la tasa y el nivel se mueve con la poblacion de cada anio.
p = m[(m["ACTOR_TYPE"] == "PEDESTRIAN") & (m["DAY_TYPE"] == "WEEKDAY")]
tasa = p.pivot_table(index="AREA_CODE", columns="YEAR", values=rO)
# 2005 no entra: su fila lleva la tasa que la encuesta midio, no la sostenida, por
# la misma razon por la que lleva su nivel medido. Lo sostenido es 2006-2010.
sostenido = all(np.allclose(tasa[y], tasa[2011], rtol=1e-12) for y in range(2006, 2011))
comprobar("la tasa de peaton de 2006-2010 se sostiene de la de 2011",
          sostenido,
          f"las 30 unidades llevan su tasa de 2011 en los cinco anios; la de 2005, "
          f"{float(tasa[2005].mean()):.3f} viajes por habitante contra "
          f"{float(tasa[2011].mean()):.3f} en 2011, se queda en su propia fila")
# Y el nivel de 2005 sigue siendo el medido, que es lo que D40 exige de un anio
# que midio la columna sin ser comparable en ella.
medido_2005 = float(
    t[(t["ACTOR_TYPE"] == "PEDESTRIAN") & (t["YEAR"] == 2005)][
        config.TRIPS_AT_ORIGIN_COL].sum())
en_tabla_2005 = float(p[p["YEAR"] == 2005][O].sum())
comprobar("y el nivel de 2005 es el que la encuesta midio, no el reconstruido",
          np.isclose(medido_2005, en_tabla_2005, rtol=1e-12),
          f"{en_tabla_2005:,.0f} viajes, contra los {float(p[p['YEAR']==2011][O].sum()):,.0f} "
          f"de 2011: la caminata larga de 2005 no se confunde con toda la de 2011")

# -- 8. La bicicleta de 2005 si ancla ---------------------------------------
b = m[(m["ACTOR_TYPE"] == "BICYCLE") & (m["DAY_TYPE"] == "WEEKDAY")]
prov = b.set_index("YEAR")["EXPOSURE_PROVENANCE"].groupby(level=0).first()
comprobar("la bicicleta de 2006-2010 se interpola, porque 2005 si la ancla",
          prov.get(2006) == config.INTERPOLATED_EXPOSURE
          and prov.get(2005) == config.MEASURED_EXPOSURE,
          f"2005 {prov.get(2005)}, 2006 {prov.get(2006)}, 2012 {prov.get(2012)}")

# -- 9. Los dias que ninguna encuesta midio antes de 2011 --------------------
sab = m[m["DAY_TYPE"] == "SATURDAY"]["YEAR"]
dom = m[m["DAY_TYPE"] == "SUNDAY"]["YEAR"]
comprobar("ni el sabado ni el domingo se inventan antes de la ventana",
          int(sab.min()) == config.STUDY_YEARS.start and int(dom.min()) == config.STUDY_YEARS.start,
          f"sabado desde {int(sab.min())}, domingo desde {int(dom.min())}, "
          f"laboral desde {int(m[m['DAY_TYPE']=='WEEKDAY']['YEAR'].min())}")

# -- 10. El margen no es la exposicion --------------------------------------
# La celda que lo demuestra: UPL04, 2011, sabado, bicicleta. Exposicion 1 351 y
# margen cero en los dos extremos.
c = m[(m["AREA_CODE"] == "UPL04") & (m["YEAR"] == 2011)
      & (m["DAY_TYPE"] == "SATURDAY") & (m["ACTOR_TYPE"] == "BICYCLE")]
exp = t[(t["AREA_CODE"] == "UPL04") & (t["YEAR"] == 2011)
        & (t["DAY_TYPE"] == "SATURDAY") & (t["ACTOR_TYPE"] == "BICYCLE")]
comprobar("una unidad que solo tiene travesia lleva margen cero y exposicion no",
          float(c[O].iloc[0]) == 0.0 and float(exp["TRIPS_PER_AVERAGE_DAY"].iloc[0]) > 0,
          f"margen {float(c[O].iloc[0]):.1f}, exposicion "
          f"{float(exp['TRIPS_PER_AVERAGE_DAY'].iloc[0]):,.1f} viajes al dia")

print()
for col in (O, D):
    s = m.groupby("YEAR")[col].sum()
    print(f"{col}, total de la ciudad por anio (laboral+sabado+domingo):")
    print("   " + "  ".join(f"{y}:{v/1e6:.2f}M" for y, v in s.items()))
print()
if fallos:
    print(f"{len(fallos)} comprobacion(es) fallan: {'; '.join(fallos)}")
    sys.exit(1)
print("las once comprobaciones de los margenes pasan")
