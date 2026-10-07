"""Cuánta señal tiene la variable respuesta en cada pareja y cada año.

Una regresión no puede estimar nada si la respuesta es cero en la mayoría de sus
unidades. El anteproyecto ya declara el umbral: se modelan las parejas con menos de
la mitad de sus celdas en cero. Esto mide cuántas lo pasan, y se puede correr sin
implementar nada, porque la matriz ya existe.

**Cuenta sobre las unidades que entran en los modelos y no sobre las del estudio.**
Son dos conjuntos distintos desde D56, y la cuota de ceros se mueve al cambiar el
denominador: automóvil contra motocicleta en 2012 pasa de 0,367 a 0,345 justamente
porque la unidad excluida era una de sus celdas en cero. Medir aquí sobre las del
estudio daría un número que no es el que la etapa juzga.

    .venv/Scripts/python.exe tools/respuesta.py [corrida]
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

CORRIDA = sys.argv[1] if len(sys.argv) > 1 else "run_20260911_155328"
TABLA = f"results/{CORRIDA}/data/analysis__matrix_long.csv"

PAREJAS = [
    ("PEDESTRIAN", "MOTORCYCLE"), ("PEDESTRIAN", "CAR"),
    ("BICYCLE", "MOTORCYCLE"), ("BICYCLE", "CAR"),
    ("MOTORCYCLE", "MOTORCYCLE"), ("MOTORCYCLE", "CAR"),
    ("CAR", "MOTORCYCLE"), ("CAR", "CAR"),
]
NOMBRES = {"PEDESTRIAN": "peatón", "BICYCLE": "bici",
           "MOTORCYCLE": "moto", "CAR": "carro"}
AÑOS = (2015, 2019, 2023)
# Declaradas y no escritas: el día que se excluya una segunda unidad, esta cuenta y
# la de la etapa tienen que moverse juntas, o la herramienta deja de medir lo que la
# etapa decide. El total de la capa lo fija `expected_units`.
EXCLUIDAS = tuple(e.unit for e in config.REGRESSION_EXCLUDED_UNITS)
UNIDADES = config.active_scale().expected_units - len(EXCLUIDAS)

d = pd.read_csv(TABLA)
d = d[(d["SCALE"] == "UPL") & (d["DATASET"] == "OBSERVED")]
d = d[~d["AREA_CODE"].isin(EXCLUIDAS)]

print(f"corrida {CORRIDA}, conjunto observado, escala UPL")
print(f"sobre {UNIDADES} unidades: las del estudio menos "
      f"{', '.join(EXCLUIDAS) if EXCLUIDAS else 'ninguna'}")
print()
print(f"{'pareja':16s} {'año':>5s} {'unidades':>9s} {'ceros':>6s} "
      f"{'mediana':>8s} {'máximo':>7s} {'total':>7s}  ¿pasa?")
print("-" * 76)

resumen = {}
for i, j in PAREJAS:
    etiqueta = f"{NOMBRES[i]}-{NOMBRES[j]}"
    for año in AÑOS:
        sub = d[(d["PARTY_TYPE"] == i) & (d["COUNTERPART_TYPE"] == j)
                & (d["YEAR"] == año)]
        # Las unidades sin fila son ceros verdaderos: la malla es completa en el
        # export, pero si faltara alguna se cuenta como cero igualmente.
        valores = list(sub["AFFECTED_PARTIES"])
        valores += [0] * (UNIDADES - len(valores))
        s = pd.Series(valores)
        ceros = int((s == 0).sum())
        pasa = ceros < UNIDADES / 2
        resumen[(etiqueta, año)] = pasa
        print(f"{etiqueta:16s} {año:5d} {len(sub):9d} {ceros:6d} "
              f"{s.median():8.1f} {s.max():7.0f} {s.sum():7.0f}  "
              f"{'sí' if pasa else 'NO'}")

print("\nParejas que pasan el umbral en los tres años:")
for i, j in PAREJAS:
    etiqueta = f"{NOMBRES[i]}-{NOMBRES[j]}"
    if all(resumen[(etiqueta, a)] for a in AÑOS):
        print(f"   {etiqueta}")
print("\nParejas que fallan en algún año:")
for i, j in PAREJAS:
    etiqueta = f"{NOMBRES[i]}-{NOMBRES[j]}"
    fallan = [a for a in AÑOS if not resumen[(etiqueta, a)]]
    if fallan:
        print(f"   {etiqueta}: falla en {fallan}")
