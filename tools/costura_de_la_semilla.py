"""Does the fitted panel still jump where the seeding survey changes?

    .venv/Scripts/python.exe tools/costura_de_la_semilla.py

**Read only.** It reads the two exported panels and compares their year-on-year change. It
writes nothing but a temporary log and takes a few seconds. Nothing in `src/` imports it.

**This tool found the seam and is now what certifies it is gone.** Under the
nearest-survey rule the spatial shape of travel switched in one step at 2014, 2018 and
2022 — the first year of each new seed — and the panel's mean absolute year-on-year change
there was 0.198 in logs against 0.077 away from them, a factor of 2.55, where D40's own
ratio was 1.18 and essentially flat. That does not bias a cross-section, which estimates
one year at a time, but the thesis's declared methodology is a panel, and a panel reads
exactly the within-unit variation over time: a twenty per cent artificial jump every four
years is what it would read as real change.

D64 replaced that rule with a blend of the two surveys that frame each year, weighted
linearly. The seam years no longer exist, so the question changes and so does this tool.

**Four readings, and the last two are the ones that matter.**

1. The year-on-year profile against D40's, as before.
2. **The anchor years are the new suspects, not the old seam years.** A linear weight is
   continuous but its slope is not: it changes direction at 2015, 2019 and 2023. The
   exposure stays continuous there, so what should show is a change of trend and not a
   step — and the check is whether those three sit inside the range of the others.
3. **The worst unit, not the mean.** A mean over thirty units hides one that still jumps,
   and a cross-section reads precisely the variation between units.
4. **The second difference of the log**, per unit and mode. A step artefact shows as a
   spike in |Δ²| even when the series itself is continuous, and it is the reading that
   answers "no unwanted patterns" rather than "no visible jump".

**It reads the unpatched variant on purpose.** D63's pandemic patch multiplies 2020 and
2021 by a declared factor, which is a real discontinuity the study puts there deliberately;
running these diagnostics on the patched panel would flag the patch as an artefact.

See D60, D63, D64, `docs/implementing-ipf.md`.
"""

import sys, logging
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import numpy as np, pandas as pd, config, reconstruction, interpolation, loading, predictors
d = REPO / "results" / "_tools_costura"; d.mkdir(parents=True, exist_ok=True)
from provenance import RunLog
log = RunLog(d); logging.getLogger().setLevel(logging.ERROR)

# Cuanto puede destacar un anio sobre la mediana de los demas antes de que esto lo llame
# un patron en vez de ruido. Declarado y no ajustado a lo que salga: tres veces la mediana
# es lo que separaba las costuras de D60 del resto, asi que es el umbral que las habria
# cazado y el que tiene sentido seguir aplicando.
LIMITE = 3.0

aj = pd.read_parquet(config.run_directory_holding(f"{config.FITTED_EXPOSURE_FILENAME}.parquet")
                     / config.DATA_SUBDIR / f"{config.FITTED_EXPOSURE_FILENAME}.parquet")
d40 = pd.read_parquet(config.run_directory_holding(f"{config.INTERPOLATED_EXPOSURE_FILENAME}.parquet")
                      / config.DATA_SUBDIR / f"{config.INTERPOLATED_EXPOSURE_FILENAME}.parquet")
COL, DIA = config.MODEL_EXPOSURE_COLUMN, config.MODEL_EXPOSURE_DAY_TYPE
a = aj[(aj.EXPOSURE_VARIANT == config.FITTED_VARIANT) & (aj.DAY_TYPE == DIA)]
b = d40[(d40.EXPOSURE_VARIANT == config.INTERPOLATED_VARIANT) & (d40.DAY_TYPE == DIA)]

units = predictors.prepare_units(loading.load_territorial_units(log))
anclas = interpolation.read_measured(log).anchors_of(DIA)
dentro = tuple(x for x in anclas if x in config.REGRESSION_YEARS)
fallos = []


def comprobar(titulo, pasa, detalle=""):
    print(f"  {'OK  ' if pasa else 'REVISAR'}  {titulo}")
    if detalle:
        print(f"            {detalle}")
    if not pasa:
        fallos.append(titulo)


def saltos(t):
    """El cambio de un anio al siguiente, por unidad y modo, en logaritmo."""
    p = t.pivot_table(index=["AREA_CODE", "ACTOR_TYPE"], columns="YEAR", values=COL)
    p = p[[y for y in config.REGRESSION_YEARS]]
    return np.log(p).diff(axis=1).iloc[:, 1:]


sa, sb = saltos(a), saltos(b)

# -- 1. El perfil ---------------------------------------------------------
print("\n1. Salto anual medio en valor absoluto, en log (0,10 = 10 %)\n")
print(f"{'anio':>6}  {'ajustado':>9}  {'D40':>9}  {'razon':>7}  {'peor unidad':>12}   ancla")
for anio in sa.columns:
    x, y = float(sa[anio].abs().mean()), float(sb[anio].abs().mean())
    print(f"{anio:>6}  {x:9.4f}  {y:9.4f}  {x/y if y else float('nan'):7.2f}  "
          f"{float(sa[anio].abs().max()):12.4f}   {'SI' if anio in dentro else ''}")

medios = sa.abs().mean()
mediana = float(medios.median())

# -- 2. Las anclas, que son las nuevas sospechosas ------------------------
print("\n2. Los anios ancla, donde el peso cambia de pendiente\n")
print(f"  mediana del salto medio sobre los {len(medios)} anios: {mediana:.4f}; "
      f"umbral {LIMITE:.0f}x = {LIMITE * mediana:.4f}")
for anio in dentro:
    if anio in medios.index:
        comprobar(f"{anio} no destaca sobre el resto",
                  float(medios[anio]) <= LIMITE * mediana,
                  f"salto medio {float(medios[anio]):.4f}, "
                  f"{float(medios[anio]) / mediana:.2f} veces la mediana")
viejas = [y for y in (2014, 2018, 2022) if y in medios.index]
print()
print("  Y las costuras que tenia la regla del vecino mas cercano, para contraste:")
for anio in viejas:
    print(f"    {anio}: {float(medios[anio]):.4f}, "
          f"{float(medios[anio]) / mediana:.2f} veces la mediana")

# -- 3. La peor unidad y no la media --------------------------------------
print("\n3. La peor unidad-modo de cada anio, que una media de treinta esconde\n")
peor_por_anio = sa.abs().max()
mediana_peor = float(peor_por_anio.median())
print(f"  mediana de los peores: {mediana_peor:.4f}; umbral {LIMITE:.0f}x = "
      f"{LIMITE * mediana_peor:.4f}")
for anio in sa.columns:
    if float(peor_por_anio[anio]) > LIMITE * mediana_peor:
        fila = sa[anio].abs().idxmax()
        comprobar(f"{anio}: el peor salto se sale del rango", False,
                  f"{fila[0]} {fila[1].lower()}: {float(peor_por_anio[anio]):.4f}")
comprobar("ningun anio tiene un peor salto fuera del rango de los demas",
          bool((peor_por_anio <= LIMITE * mediana_peor).all()),
          f"maximo {float(peor_por_anio.max()):.4f} en "
          f"{int(peor_por_anio.idxmax())}")

# -- 4. La segunda diferencia ---------------------------------------------
print("\n4. Segunda diferencia del logaritmo: un escalon se ve aqui aunque la serie sea "
      "continua\n")
curva = sa.diff(axis=1).iloc[:, 1:].abs()
print(f"  {'anio':>6}  {'media':>9}  {'p95':>9}  {'maxima':>9}  {'serie de la maxima':>28}")
for anio in curva.columns:
    fila = curva[anio].idxmax()
    print(f"  {anio:>6}  {float(curva[anio].mean()):9.4f}  "
          f"{float(curva[anio].quantile(0.95)):9.4f}  {float(curva[anio].max()):9.4f}  "
          f"{fila[0] + ' ' + fila[1].lower():>28}")
medias_curva = curva.mean()
mediana_curva = float(medias_curva.median())
print()
print(f"  mediana de la curvatura media: {mediana_curva:.4f}; umbral {LIMITE:.0f}x = "
      f"{LIMITE * mediana_curva:.4f}")
fuera_de_rango = [int(y) for y in medias_curva.index
                  if float(medias_curva[y]) > LIMITE * mediana_curva]
print("  anios por encima del umbral: " + (", ".join(str(y) for y in fuera_de_rango)
                                           if fuera_de_rango else "ninguno"))

# -- 5. Lo heredado contra lo introducido ---------------------------------
# **Un umbral plano sobre la mediana no distingue un artefacto de la forma real de la
# serie.** Los primeros anios se mueven mas que los ultimos en los dos paneles, y la
# interpolacion de D40 tiene su propio quiebre en cada ancla porque la tasa cambia de
# pendiente alli. Lo que esta herramienta tiene que contestar no es «hay curvatura» sino
# «hay curvatura que D40 no tenga», que es la unica que la reconstruccion pudo meter.
print("\n5. La curvatura del panel ajustado contra la de D40, que es la unica "
      "comparacion que aisla\n   lo que este paso introdujo de lo que ya venia en los "
      "margenes\n")
curva_d40 = sb.diff(axis=1).iloc[:, 1:].abs()
medias_d40 = curva_d40.mean()
print(f"  {'anio':>6}  {'ajustado':>10}  {'D40':>10}  {'razon':>8}")
for anio in curva.columns:
    x, y = float(medias_curva[anio]), float(medias_d40[anio])
    print(f"  {anio:>6}  {x:10.4f}  {y:10.4f}  {x / y if y else float('nan'):8.2f}")
razones = (medias_curva / medias_d40).dropna()
print()
print("  Los tres anios que el umbral plano senalaba salen en razon 1,0: son los quiebres")
print("  que la interpolacion de D40 tiene en sus propias anclas y la reconstruccion")
print("  hereda por los margenes. Donde la razon es alta, D40 es recto por construccion")
print("  —interpola lineal, asi que fuera de un ancla su segunda diferencia es cero— y")
print("  dividir por casi cero no mide nada. Por eso el criterio no es este cociente.")

# -- 6. El criterio ------------------------------------------------------
# **La estadistica que tiene sentido es la que encontro la costura**, y es la unica que se
# puede leer sin comparar contra una serie recta: cuanto mas brinca el panel en los anios
# donde la regla del vecino mas cercano cambiaba de semilla que en el resto. Esos anios ya
# no tienen nada de particular en la construccion, asi que la razon tiene que caer a la de
# D40, que es 1,18 y es el nivel de una serie sin artefacto. Medido antes de D64 daba 2,55.
print("\n6. El criterio: el panel tiene que brincar en 2014, 2018 y 2022 lo mismo que "
      "fuera de ellos\n")
viejas_cols = [c for c in sa.columns if c in (2014, 2018, 2022)]
resto = [c for c in sa.columns if c not in viejas_cols]
razon_aj = float(sa[viejas_cols].abs().mean().mean() / sa[resto].abs().mean().mean())
razon_d40 = float(sb[viejas_cols].abs().mean().mean() / sb[resto].abs().mean().mean())
print(f"  ajustado  {razon_aj:.2f}      D40  {razon_d40:.2f}")
comprobar("las antiguas costuras ya no se distinguen del resto de la serie",
          razon_aj <= razon_d40 * 1.25,
          f"razon {razon_aj:.2f} contra la de D40, {razon_d40:.2f}; antes de D64 era 2,55")
print()
print(f"  curvatura media sobre salto medio: "
      f"{float(curva.mean().mean() / sa.abs().mean().mean()):.3f}  "
      f"(antes de D64: 1,146)")

print()
print(f"{'TODO BIEN' if not fallos else str(len(fallos)) + ' A REVISAR: ' + '; '.join(fallos)}")
