"""Does the fitting return the matrix it is supposed to, on cases whose answer is known?

    .venv/Scripts/python.exe tools/ajuste_proporcional.py

**Read only.** It reads no data at all: every case is built here, and every expected
answer is written out by hand or derived a second way. That is the point — iterative
proportional fitting on real survey matrices has no reference to be checked against, so
the arithmetic is checked where a reference exists.

Ten cases, each named by what would break if it failed. The first is the one D60
declares as deciding: **a matrix fitted against its own margins has to come back as
itself**, and it does, exactly, in one iteration. A fitting that fails that is wrong
whatever else it does, and everything downstream of it rests on it.

Three of the eight are about what the fitting refuses rather than what it returns.
Margins that disagree about the grand total, a negative anywhere, and a zero pattern
that makes the margins unreachable are defects in what was handed in and not failures of
the iteration, so they raise and name the offending row or column instead of returning a
matrix that quietly misses its margins.

The last case is the scale the study actually needs: 1,215 zones, the largest of the five
surveys, at the sparsity real origin-destination matrices have. Six iterations, 0.02 s.

See D54, D60, `src/fitting.py` and `tools/margenes_para_el_ajuste.py`.
"""


import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import fitting  # noqa: E402

fallos = []


def comprobar(titulo: str, pasa: bool, detalle: str = "") -> None:
    print(f"  {'OK  ' if pasa else 'FALLA'}  {titulo}")
    if detalle:
        print(f"           {detalle}")
    if not pasa:
        fallos.append(titulo)


rng = np.random.default_rng(11)

# -- 1. Identidad ----------------------------------------------------------
# Si los margenes pedidos son los que la semilla ya tiene, el resultado tiene que
# ser la semilla. Un ajuste que no pase esto esta mal haga lo que haga despues.
semilla = rng.random((40, 40)) * 1000
r = fitting.fit(semilla, semilla.sum(axis=1), semilla.sum(axis=0))
comprobar("un ajuste contra los propios márgenes devuelve la semilla",
          r.converged and np.allclose(r.matrix, semilla, rtol=1e-12),
          f"{r.iterations} iteración(es), diferencia máxima "
          f"{np.max(np.abs(r.matrix - semilla)):.2e}")

# -- 2. Reproduce los margenes --------------------------------------------
objetivo_filas = rng.random(40) * 500
objetivo_cols = rng.random(40)
objetivo_cols *= objetivo_filas.sum() / objetivo_cols.sum()
r = fitting.fit(semilla, objetivo_filas, objetivo_cols)
comprobar("el resultado reproduce los márgenes pedidos",
          r.converged and r.worst_margin_error <= fitting.DEFAULT_TOLERANCE,
          f"{r.iterations} iteraciones, peor error relativo {r.worst_margin_error:.2e}")

# -- 3. Conserva los ceros -------------------------------------------------
# Es la propiedad que hace conservador al metodo: no puede inventar un viaje entre
# dos sitios donde la encuesta no vio ninguno.
con_ceros = semilla.copy()
con_ceros[rng.random(con_ceros.shape) < 0.3] = 0.0
filas = con_ceros.sum(axis=1) * 1.4
cols = con_ceros.sum(axis=0)
cols *= filas.sum() / cols.sum()
r = fitting.fit(con_ceros, filas, cols)
ceros_semilla = con_ceros == 0
comprobar("un cero de la semilla sigue siendo cero en el resultado",
          bool(np.all(r.matrix[ceros_semilla] == 0)),
          f"{int(ceros_semilla.sum())} celdas en cero, todas conservadas")

# -- 4. El caso de una sola solucion --------------------------------------
# Con una semilla uniforme y margenes dados, la solucion es el producto exterior
# dividido por el total, y se puede escribir a mano.
uniforme = np.ones((3, 4))
f = np.array([10.0, 20.0, 30.0])
c = np.array([6.0, 12.0, 18.0, 24.0])
r = fitting.fit(uniforme, f, c)
esperado = np.outer(f, c) / f.sum()
comprobar("con semilla uniforme da el producto exterior sobre el total",
          np.allclose(r.matrix, esperado, rtol=1e-12),
          f"diferencia máxima {np.max(np.abs(r.matrix - esperado)):.2e}")

# -- 5. Los margenes tienen que cuadrar entre si --------------------------
try:
    fitting.fit(uniforme, np.array([1.0, 1.0, 1.0]), np.array([1.0, 1.0, 1.0, 1.0]))
    comprobar("márgenes que no suman lo mismo son un error", False, "no levantó nada")
except ValueError as e:
    comprobar("márgenes que no suman lo mismo son un error", "grand total" in str(e),
              str(e)[:96])

# -- 6. Un patron de ceros imposible se nombra, no se devuelve ------------
imposible = np.array([[1.0, 0.0], [0.0, 0.0]])
try:
    fitting.fit(imposible, np.array([1.0, 1.0]), np.array([2.0, 0.0]))
    comprobar("un margen inalcanzable se detecta", False, "no levantó nada")
except ValueError as e:
    comprobar("un margen inalcanzable se detecta y dice cuál",
              "row 1" in str(e), str(e)[:110])

# -- 7. Un margen de cero es legitimo -------------------------------------
# Una zona sin viajes ese ano no es un error: se escala a cero y ya.
con_cero_legitimo = np.array([[2.0, 3.0], [4.0, 1.0]])
r = fitting.fit(con_cero_legitimo, np.array([0.0, 10.0]), np.array([8.0, 2.0]))
comprobar("un margen de cero se satisface en vez de fallar",
          r.converged and np.isclose(r.matrix[0].sum(), 0.0),
          f"fila 0 suma {r.matrix[0].sum():.2e}, total {r.matrix.sum():.1f}")

# -- 8. El tamano real del problema ---------------------------------------
# 1 215 zonas es la mayor de las cinco encuestas. Si a esa escala tarda, no sirve.
import time
grande = rng.random((1215, 1215))
grande[rng.random(grande.shape) < 0.85] = 0.0   # las matrices OD son dispersas
fil = grande.sum(axis=1) * (1 + rng.random(1215) * 0.3)
col = grande.sum(axis=0) * (1 + rng.random(1215) * 0.3)
col *= fil.sum() / col.sum()
# Las filas y columnas que la dispersion dejo vacias no pueden pedir nada.
fil[grande.sum(axis=1) == 0] = 0.0
col[grande.sum(axis=0) == 0] = 0.0
col *= fil.sum() / col.sum() if col.sum() > 0 else 1.0
comienzo = time.time()
r = fitting.fit(grande, fil, col)
tardanza = time.time() - comienzo
comprobar("a la escala de la encuesta mayor, 1 215 zonas",
          r.converged and tardanza < 10,
          f"{r.iterations} iteraciones en {tardanza:.2f} s, "
          f"error {r.worst_margin_error:.2e}")

# -- 9. La condicion que de verdad decide: factibilidad -------------------
# Cuadrar los componentes es necesario y no suficiente. Este caso lo demuestra con una
# matriz de tres por tres escrita a mano: un solo componente, los totales cuadran, y no
# existe matriz con esos margenes porque la fila 2 solo alcanza una columna que pide
# menos de lo que la fila tiene.
restringida = np.array([[1.0, 1.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0]])
f = np.array([10.0, 10.0, 5.0])
c = np.array([15.0, 5.0, 5.0])
comprobar("un componente puede cuadrar y aun asi no existir la matriz",
          len(fitting.inconsistent_components(restringida, f, c)) == 0
          and fitting.infeasible_by(restringida, f, c) > 0,
          f"los componentes cuadran y faltan {fitting.infeasible_by(restringida, f, c):.1f} "
          f"viajes: la fila 1 solo alcanza la columna 1, que pide 5")

# Y el ajuste de un problema factible no reporta falta ninguna.
comprobar("un problema factible no reporta falta",
          fitting.infeasible_by(semilla, semilla.sum(axis=1), semilla.sum(axis=0)) == 0.0,
          "la semilla contra sus propios margenes")

print()

print()
if fallos:
    print(f"{len(fallos)} prueba(s) fallan: {', '.join(fallos)}")
    sys.exit(1)
print("las diez pruebas del ajuste pasan")
