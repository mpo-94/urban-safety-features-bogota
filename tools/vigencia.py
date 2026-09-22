"""De cuándo es cada capa estática.

Las once variables estáticas son un corte único sin año declarado. Usarlas como
predictor de 2015 y de 2023 a la vez supone que no cambiaron, y ese supuesto hay
que poder decir sobre qué fecha se hace.

Busca la fecha donde puede estar de verdad: en columnas que sean de tipo fecha, y
en columnas cuyo nombre la anuncie y cuyo contenido la confirme. No se fía de
encontrar cuatro dígitos en cualquier sitio, porque los identificadores están
llenos de números que parecen años.

    .venv/Scripts/python.exe tools/vigencia.py
"""

import datetime as dt
import glob
import os
import re
import sys

import geopandas as gpd
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = "data/shp_properties_sorted"
CAPAS = [
    ("andenes", "areas/andenes_x_localidad"),
    ("avenidas", "areas/avenidas_corregidas"),
    ("calzada", "areas/calzada_x_localidad"),
    ("parques", "areas/parques_urb"),
    ("puentes", "areas/puentes"),
    ("paraderos SITP", "points/Paraderos_SITP"),
    ("red semafórica", "points/Red_Semaforica"),
    ("cruces peatonales", "points/crossings"),
    ("cámaras", "points/camaras_salvavidas_bogota"),
    ("estaciones TM", "points/estacion_localidad"),
    ("arbolado", "points/arbolado_urbano"),
]

SUENA_A_FECHA = re.compile(r"fecha|date|ano|año|year|captur|actualiz|vigen",
                           re.IGNORECASE)


def informa(nombre, capa, base, mod):
    print(f"   {base[:44]:44s} {len(capa):8d} registros   copiado el {mod}")
    encontrado = False
    for col in capa.columns:
        if col == "geometry":
            continue
        s = capa[col]
        es_fecha = pd.api.types.is_datetime64_any_dtype(s)
        suena = bool(SUENA_A_FECHA.search(col))
        if not (es_fecha or suena):
            continue
        v = s.dropna()
        if not len(v):
            continue
        encontrado = True
        if es_fecha:
            distintas = v.dt.date.nunique()
            print(f"      «{col}»: {str(v.min())[:10]} a {str(v.max())[:10]}, "
                  f"{distintas} fecha(s) distinta(s)")
        else:
            top = v.astype(str).value_counts().head(4).to_dict()
            print(f"      «{col}» (texto): {top}")
    if not encontrado:
        print("      ninguna columna dice de cuándo es el dato")
    print(f"      columnas: {[c for c in capa.columns if c != 'geometry'][:14]}")


for nombre, sub in CAPAS:
    archivos = sorted(glob.glob(os.path.join(RAIZ, sub, "*.shp")))
    print(f"\n{nombre}")
    if not archivos:
        print(f"   sin .shp en {sub}")
        continue
    for f in archivos:
        mod = dt.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d")
        informa(nombre, gpd.read_file(f), os.path.basename(f), mod)
