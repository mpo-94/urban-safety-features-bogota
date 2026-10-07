"""What breaks when a unit leaves the regressions, checked before the pipeline is touched.

    .venv/Scripts/python.exe tools/exclusion_de_una_unidad.py

**Read only.** It reads the unit layer and a finished run, and writes nothing. It takes
the unit to exclude from the constant below, so a second proposed exclusion is a one-line
change and not a new script.

Dos cosas que no son evidentes leyendo D56 y que abortarían o falsearían la corrida:

  1. **La matriz de contigüidad.** `fit_all` la construye desde el GeoDataFrame de
     unidades, no desde la tabla de regresión, y `morans_i` hace `centred @ weights @
     centred`. Si los residuos pasan a 29 y los pesos siguen en 30x30, revienta. Y
     `contiguity_weights` lanza ValueError si alguna unidad queda sin vecinos, así que
     hay que saber si quitar Torca aísla a alguien.

  2. **El umbral de elegibilidad.** Es una proporción y no un conteo, así que no se
     rompe al cambiar el denominador; pero la proporción sí se mueve, y si alguna pareja
     cruza el máximo declarado, deja de modelarse y la corrida pierde una pareja sin que
     nadie lo haya decidido.
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import config          # noqa: E402
import regressions as R  # noqa: E402

FUERA = "UPL07"
RUN = "run_20260928_112330"


def vecindad() -> None:
    # Leido del shapefile y no por , que pide un RunLog y
    # con el crearia una carpeta de corrida: esto es una comprobacion de solo lectura.
    escala = config.active_scale()
    units = gpd.read_file(escala.shapefile).rename(columns={
        escala.code_column: config.AREA_CODE_COL,
        escala.name_column: config.AREA_NAME_COL,
    })
    weights, codes = R.contiguity_weights(units)
    posicion = {c: i for i, c in enumerate(codes)}
    nombres = dict(zip(units[config.AREA_CODE_COL], units[config.AREA_NAME_COL]))

    fila = weights[posicion[FUERA]]
    vecinos = [codes[j] for j in range(len(codes)) if fila[j] > 0]
    print(f"1. Contigüidad\n   {FUERA} {nombres[FUERA]} limita con "
          f"{len(vecinos)}: {', '.join(nombres[c] for c in vecinos)}")

    # La matriz sin Torca, reconstruida como la reconstruiría el pipeline.
    restantes = units[units[config.AREA_CODE_COL] != FUERA]
    nuevos, codigos_nuevos = R.contiguity_weights(restantes)
    print(f"   la matriz pasa de {weights.shape} a {nuevos.shape}")

    # ¿Alguien queda aislado? `contiguity_weights` lanza ValueError si sí, así que
    # llegar hasta aquí ya lo descarta; se cuenta igual para dejar la cifra escrita.
    conteos_antes = {c: int((weights[posicion[c]] > 0).sum()) for c in codes if c != FUERA}
    pos_nueva = {c: i for i, c in enumerate(codigos_nuevos)}
    conteos_despues = {c: int((nuevos[pos_nueva[c]] > 0).sum()) for c in codigos_nuevos}
    perdieron = {c: (conteos_antes[c], conteos_despues[c])
                 for c in codigos_nuevos if conteos_despues[c] < conteos_antes[c]}
    print(f"   unidades que pierden un vecino: {len(perdieron)}")
    for c, (antes, despues) in perdieron.items():
        marca = "  <-- QUEDA AISLADA" if despues == 0 else ""
        print(f"      {nombres[c]:24s} {antes} -> {despues}{marca}")
    minimo = min(conteos_despues.values())
    print(f"   mínimo de vecinos tras la exclusión: {minimo}"
          f"{'  OK' if minimo > 0 else '  ABORTA LA CORRIDA'}")


def elegibilidad() -> None:
    print(f"\n2. Umbral de elegibilidad "
          f"(máximo declarado {config.REGRESSION_MAX_ZERO_SHARE:.2f})\n")
    for nombre, etiqueta in (("RHO_CORRECTED", "corregido con rho"),
                             ("OBSERVED", "observado")):
        ruta = REPO / "results" / RUN / "data" / f"analysis__regression_data__{nombre}.csv"
        if not ruta.exists():
            continue
        datos = pd.read_csv(ruta)
        print(f"   conjunto {etiqueta}")
        print(f"   {'pareja':<26} {'peor con 30':>12} {'peor con 29':>12}   veredicto")
        for par in config.REGRESSION_PAIRS:
            bloque = datos[datos.PAIR == par.name]
            peores = []
            for sin_torca in (False, True):
                b = bloque[bloque.AREA_CODE != FUERA] if sin_torca else bloque
                cuotas = [float((b[b.YEAR == a][R.RESPONSE_COL] == 0).mean())
                          for a in config.REGRESSION_YEARS
                          if len(b[b.YEAR == a])]
                peores.append(max(cuotas) if cuotas else 1.0)
            antes, despues = peores
            pasa_antes = antes < config.REGRESSION_MAX_ZERO_SHARE
            pasa_despues = despues < config.REGRESSION_MAX_ZERO_SHARE
            if pasa_antes and not pasa_despues:
                veredicto = "SE CAE al quitar Torca"
            elif not pasa_antes and pasa_despues:
                veredicto = "entra al quitar Torca"
            else:
                veredicto = "igual: " + ("pasa" if pasa_despues else "no pasa")
            print(f"   {par.label_es[:26]:<26} {antes:12.3f} {despues:12.3f}   {veredicto}")
        print()


if __name__ == "__main__":
    vecindad()
    elegibilidad()
