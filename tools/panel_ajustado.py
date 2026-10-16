"""Is the fitted panel a table that can be read beside D40's, and does it differ from it?

    .venv/Scripts/python.exe tools/panel_ajustado.py

**Read only.** It builds the fitted panel and D40's in memory from a finished exposure run
and compares them, writing nothing but a temporary log. Takes about eight minutes, most of
it the apportionment. Nothing in `src/` imports it.

Twelve checks in two halves. The first half is about the table: the fitted panel is a third
variant of the exposure panel and never a replacement (D42's rule), so it has to carry the
same columns in the same order, hold declared values in its variant and provenance columns,
be a complete grid, and concatenate with D40's panel without colliding on the key. A table
that cannot be joined to the others is of no use in the dashboard.

The second half is the question the variant exists to answer, and the answer is the
interesting one. **The two agree on the aggregate almost exactly and disagree about
individual units by a great deal.** The mean ratio of fitted to interpolated exposure is
1.000 for the car and the motorcycle, 1.002 for the bicycle and 0.990 for the pedestrian,
and the median is 1.0 in all four — while cycling in a single unit and year ranges from
0.49 to 2.35 of what D40 gives it.

That is the case for reconstructing the matrix, stated as a measurement rather than as an
argument: a rate interpolated per unit gives every unit its own curve and knows nothing
about where the travel goes, and the fitting is what puts that back. Had the two agreed
everywhere, the honest conclusion would have been that the extra assumption buys nothing,
and this is the script that would have said so.

See D54, D60, `src/reconstruction.py` and `tools/piso_de_la_semilla.py`.
"""

import sys, time, logging
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import numpy as np
import pandas as pd
import config, exposure, interpolation, loading, mobility_reports, population, predictors, reconstruction, surveys
from provenance import RunLog

fallos = []
def comprobar(titulo, pasa, detalle=""):
    print(f"  {'OK  ' if pasa else 'FALLA'}  {titulo}")
    if detalle:
        print(f"           {detalle}")
    if not pasa:
        fallos.append(titulo)

d = REPO / "results" / "_tools_panel"
d.mkdir(parents=True, exist_ok=True)
log = RunLog(d)
logging.getLogger().setLevel(logging.ERROR)

units = loading.load_territorial_units(log)
projected = predictors.prepare_units(units)
panel_poblacion, _, _ = population.build(projected, log)
measured = interpolation.read_measured(log)

print("leyendo las cinco encuestas...")
leidas = {e.year: surveys.read(e, log) for e in config.MOBILITY_SURVEYS}

t0 = time.time()
ajustado, ajustes = reconstruction.build(
    measured, panel_poblacion, projected, leidas, log)
print(f"panel ajustado en {time.time()-t0:.0f} s: {len(ajustado):,} filas, "
      f"{len(ajustes)} bloques\n")

# -- 1. Se puede leer como una sola tabla con el panel de D40 -------------
d40 = interpolation.build(measured, panel_poblacion, projected, log)
columnas_d40 = list(config.interpolated_exposure_columns())
comprobar("el panel ajustado lleva todas las columnas del de D40, en el mismo orden",
          list(ajustado.columns)[:len(columnas_d40)] == columnas_d40,
          f"{len(ajustado.columns)} columnas: las {len(columnas_d40)} de D40 mas "
          f"{', '.join(list(ajustado.columns)[len(columnas_d40):])}")

juntos = pd.concat([d40[columnas_d40], ajustado[columnas_d40]], ignore_index=True)
clave = [config.SCALE_COL, config.AREA_CODE_COL, config.YEAR_COL,
         config.ACTOR_TYPE_COL, config.DAY_TYPE_COL, config.EXPOSURE_VARIANT_COL]
comprobar("las dos variantes se pueden concatenar sin colisionar en la clave",
          not juntos.duplicated(clave).any(),
          f"{len(juntos):,} filas, {juntos[config.EXPOSURE_VARIANT_COL].nunique()} "
          f"variante(s), cero duplicados de "
          f"{', '.join(c for c in clave if c != config.SCALE_COL)}")

comprobar("la variante y la procedencia son valores declarados",
          set(ajustado[config.EXPOSURE_VARIANT_COL]) <= set(config.EXPOSURE_VARIANTS)
          and set(ajustado[config.EXPOSURE_PROVENANCE_COL]) <= set(config.EXPOSURE_PROVENANCES),
          f"variante {sorted(set(ajustado[config.EXPOSURE_VARIANT_COL]))}, "
          f"procedencia {sorted(set(ajustado[config.EXPOSURE_PROVENANCE_COL]))}")

# -- 2. La forma del panel -------------------------------------------------
esperadas = (len(config.REGRESSION_YEARS) * projected[config.AREA_CODE_COL].nunique()
             * 4 * len(config.RECONSTRUCTION_DAY_TYPES))
comprobar("el panel esta completo: un ano por unidad por modo por tipo de dia",
          len(ajustado) == esperadas,
          f"{len(ajustado):,} filas contra {esperadas:,} esperadas "
          f"({len(config.REGRESSION_YEARS)} anos x "
          f"{projected[config.AREA_CODE_COL].nunique()} unidades x 4 modos x "
          f"{len(config.RECONSTRUCTION_DAY_TYPES)} dia)")

comprobar("solo lleva el dia que los modelos leen",
          set(ajustado[config.DAY_TYPE_COL]) == set(config.RECONSTRUCTION_DAY_TYPES),
          f"{sorted(set(ajustado[config.DAY_TYPE_COL]))} contra las "
          f"{len(config.DAY_TYPES)} del panel de D40")

comprobar("nada nulo, nada negativo, y la tasa cuadra con el nivel",
          bool(ajustado[columnas_d40].notna().all().all()
               and (ajustado[config.TRIPS_PER_DAY_OF_TYPE_COL] >= 0).all()
               and np.allclose(
                   ajustado[config.INTERPOLATED_RATE_COL] * ajustado[config.POPULATION_COL],
                   ajustado[config.TRIPS_PER_DAY_OF_TYPE_COL], rtol=1e-12)),
          "la tasa por el numero de habitantes devuelve el nivel")

# -- 3. La identidad, en el panel ------------------------------------------
medidos = ajustado[ajustado[config.EXPOSURE_PROVENANCE_COL] == config.MEASURED_EXPOSURE]
anclas = measured.anchors_of(config.MODEL_EXPOSURE_DAY_TYPE)
anios_medidos = sorted(set(medidos[config.YEAR_COL]))
comprobar("los anos medidos del panel son los de encuesta dentro de la ventana",
          anios_medidos == [a for a in anclas if a in config.REGRESSION_YEARS],
          f"{anios_medidos}, que son los que se siembran en si mismos")

cl = [config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.DAY_TYPE_COL, config.YEAR_COL]
j = medidos.merge(measured.table, on=cl, suffixes=("_aj", "_hoy"))
peor = max(float(np.max(np.abs(j[f"{c}_aj"] - j[f"{c}_hoy"]))) for c in
           (config.TRIPS_PER_DAY_OF_TYPE_COL,
            config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL))
comprobar("y en esos anos el panel ajustado es la tabla medida",
          len(j) == len(medidos) and peor < 1e-6,
          f"{len(j)} filas, diferencia maxima {peor:.2e} viajes al dia")

# -- 4. La comparacion contra D40, que es para lo que existe la variante ---
print()
col = config.MODEL_EXPOSURE_COLUMN
a = ajustado.set_index(cl)[col]
b = d40[(d40[config.EXPOSURE_VARIANT_COL] == config.INTERPOLATED_VARIANT)].set_index(cl)[col]
c = pd.DataFrame({"ajustado": a, "d40": b}).dropna()
c["razon"] = c["ajustado"] / c["d40"].where(c["d40"] > 0, np.nan)
print(f"la exposicion ajustada contra la de D40, {len(c):,} celdas comunes:")
print(c.groupby(level=1)["razon"].describe()[["mean", "50%", "min", "max"]]
       .round(3).to_string())
sin_medir = c[~c.index.get_level_values(3).isin(anios_medidos)]
print(f"\nen los {len(sin_medir):,} anos construidos: mediana "
      f"{sin_medir['razon'].median():.4f}, "
      f"cuartiles {sin_medir['razon'].quantile(0.25):.3f}-"
      f"{sin_medir['razon'].quantile(0.75):.3f}, "
      f"rango {sin_medir['razon'].min():.3f}-{sin_medir['razon'].max():.3f}")
medidos_c = c[c.index.get_level_values(3).isin(anios_medidos)]
comprobar("en los anos medidos las dos variantes coinciden",
          bool(np.allclose(medidos_c["ajustado"], medidos_c["d40"], rtol=1e-9)),
          f"{len(medidos_c)} celdas, porque ninguna de las dos construye nada ahi")
comprobar("en los anos construidos el ajuste mueve la exposicion",
          float(sin_medir["razon"].std()) > 1e-6,
          f"desviacion de la razon {float(sin_medir['razon'].std()):.4f}; si fuera cero "
          f"el ajuste no aportaria nada y habria que decirlo")

# -- 5. La tabla de ajustes ------------------------------------------------
print()
print("lo que el piso hizo, por ano:")
pis = ajustes[ajustes[reconstruction._FLOORED_COL]]
inventado = float(pis[reconstruction._OPENED_TRIPS_COL].sum())
en_bloques = float(ajustes[reconstruction._BLOCK_TRIPS_COL].sum())
print(f"   {len(pis)} de {len(ajustes)} bloques; {inventado:,.0f} viajes al dia "
      f"inventados de {en_bloques:,.0f}, {inventado/en_bloques*100:.4f} %")
comprobar("lo inventado se queda tres ordenes por debajo de cualquier cifra del estudio",
          inventado / en_bloques < 1e-3,
          f"{inventado/en_bloques*100:.4f} % de los viajes de los bloques ajustados")
comprobar("la tabla de ajustes lleva un bloque por ano, modo y dia",
          len(ajustes) == len(config.REGRESSION_YEARS) * 4 * len(config.RECONSTRUCTION_DAY_TYPES),
          f"{len(ajustes)} bloques, todos con su ano y su encuesta sembradora")

print()
if fallos:
    print(f"{len(fallos)} comprobacion(es) fallan: {'; '.join(fallos)}")
    sys.exit(1)
print("las doce comprobaciones del panel pasan")
