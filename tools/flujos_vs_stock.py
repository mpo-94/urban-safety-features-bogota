"""Las dos capas de demarcación, medidas con las mismas pruebas que la ciclorruta.

Es la evidencia de D46. La ciclorruta pasó tres pruebas y por eso se mide; estas
dos tienen que pasar las mismas o quedar fuera con los números a la vista, y el
informe que las excluya se escribe desde aquí y no desde el recuerdo de una
sesión. La ciclorruta se mide otra vez al final, como control: sin algo que sí
sea stock al lado, las cifras de un flujo no dicen de qué tamaño es la anomalía.

Las tres pruebas:
  1. la longitud total por año: un stock crece, un flujo oscila;
  2. cuántos identificadores aparecen en un solo año: un stock los repite;
  3. si el conjunto de un año contiene al del anterior.

Y una cuarta, que solo tiene sentido si las tres anteriores dicen "flujo":
  4. si la serie permite estimar hacia atrás el stock de 2015. No lo permite, y
     aunque lo permitiera, extrapolar un flujo da un flujo.

Desde la raíz del proyecto:

    python tools/flujos_vs_stock.py
"""

import glob
import io
import os
import re
import sys

import geopandas as gpd
import numpy as np

import sys
from pathlib import Path

# El script se corre desde la raíz del proyecto y necesita importar `src`, que no
# está instalado como paquete. Añadir la raíz al camino aquí es lo que hace que
# la invocación documentada arriba funcione sin preparar nada antes.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config

sys.stdout.reconfigure(encoding="utf-8")

PROYECTADO = 3116  # MAGNA-SIRGAS / Bogotá, metros

CAPAS = [
    ("Demarcación horizontal", "lines/Señalizacion_Horizontal"),
    ("Zonas escolares", "lines/Señalizacion_Horizontal_ZonasEscolares"),
    ("Ciclorruta (control: es stock)", "lines/ciclo_lines"),
]

CLAVES = ("CIV", "CicCodigo")  # el identificador que cada entrega usa


def anio_de(ruta):
    return int(re.search(r"(20\d{2})", os.path.basename(ruta)).group(1))


for titulo, relativo in CAPAS:
    # El nombre de dos de estas carpetas lleva una n con tilde que el disco
    # guarda descompuesta, asi que la ruta se resuelve como la resuelve el
    # pipeline en vez de con un glob que no la encuentra.
    carpeta = config.resolve_source_path(config.PREDICTORS_DIR / relativo)
    archivos = sorted((str(p) for p in carpeta.glob("*.shp")), key=anio_de)
    print("=" * 78)
    print(f"{titulo}   ({len(archivos)} archivos)")
    print("=" * 78)

    por_anio = {}
    for ruta in archivos:
        capa = gpd.read_file(ruta)
        km = float(capa.to_crs(epsg=PROYECTADO).geometry.length.sum() / 1000.0)
        clave = next((c for c in CLAVES if c in capa.columns), None)
        ids = set(capa[clave].dropna().astype(str)) if clave else set()
        por_anio[anio_de(ruta)] = (len(capa), km, ids, clave)

    anios = sorted(por_anio)
    print(f"{'año':>6} {'tramos':>9} {'km':>11} {'Δ km':>10} {'ids':>8}  clave")
    previo = None
    for a in anios:
        n, km, ids, clave = por_anio[a]
        delta = "" if previo is None else f"{km - previo:+10.1f}"
        print(f"{a:>6} {n:>9,} {km:>11,.1f} {delta:>10} {len(ids):>8,}  {clave}")
        previo = km

    todos = set().union(*(v[2] for v in por_anio.values()))
    if todos:
        veces = {i: sum(1 for v in por_anio.values() if i in v[2]) for i in todos}
        unicos = sum(1 for n in veces.values() if n == 1)
        print()
        print(f"  identificadores distintos: {len(todos):,}")
        print(f"    en un solo año: {unicos:,} ({100 * unicos / len(todos):.1f}%)")
        print(f"    en todos los {len(anios)} años: {sum(1 for n in veces.values() if n == len(anios)):,}")

        print("  ¿cada año contiene al anterior?")
        for x, y in zip(anios, anios[1:]):
            a, b = por_anio[x][2], por_anio[y][2]
            perdidos = len(a - b)
            print(f"    {x} -> {y}: {'contiene' if not perdidos else f'pierde {perdidos:,}'}"
                  f", gana {len(b - a):,}")

    # Cuarta prueba: regresión lineal de los kilómetros anuales contra el año,
    # para ver si la serie permitiría estimar 2015 hacia atrás.
    x = np.array(anios, dtype=float)
    y = np.array([por_anio[a][1] for a in anios], dtype=float)
    if len(x) >= 3:
        pendiente, corte = np.polyfit(x, y, 1)
        ajuste = pendiente * x + corte
        ss_res = float(((y - ajuste) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")
        # Intervalo de predicción a 95% para 2015, con n-2 grados de libertad.
        n = len(x)
        s = np.sqrt(ss_res / (n - 2))
        objetivo = 2015.0
        se = s * np.sqrt(1 + 1 / n + (objetivo - x.mean()) ** 2 / ((x - x.mean()) ** 2).sum())
        t = 2.571 if n == 7 else 2.201  # t de Student al 95%, dos colas
        pred = pendiente * objetivo + corte
        print()
        print(f"  extrapolación lineal a {int(objetivo)}: R2 = {r2:.3f}, "
              f"pendiente {pendiente:+.1f} km/año")
        print(f"    predicción {pred:,.1f} km, intervalo 95% "
              f"[{pred - t * se:,.1f}, {pred + t * se:,.1f}]")
        if pred - t * se < 0:
            print("    el intervalo incluye kilómetros negativos")
    print()
