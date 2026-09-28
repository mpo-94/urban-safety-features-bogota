"""¿Qué cambia cuando los restos de offset no compiten contra las urbanas?

Una cantidad que no entra al offset se queda en la bolsa. Bajo el offset de
exposición del modo siguen compitiendo la exposición de la contraparte y la
población; bajo el de población, las dos exposiciones. Y compiten en condiciones
desiguales: una exposición explica el conteo casi por construcción, mientras que
una característica del entorno tiene que explicar lo que sobra después de ella.

La corrida reportada —`urban-only`, que es la de por defecto desde D52— las deja
fuera. Esta comprobación pone las dos corridas lado a lado y contesta cuatro
preguntas que no se pueden contestar mirando una sola:

  1. cuántas selecciones liberaron los restos, que es un conteo y no un orden;
  2. si el orden de las urbanas se sostiene, **medido dentro de cada
     especificación** y no sobre la corrida entera;
  3. cuánto del ajuste venía de los restos, medido por AIC en la misma celda, que
     es comparable porque son la misma respuesta, el mismo offset y la misma
     familia sobre las mismas treinta unidades;
  4. si alguna urbana cambia de signo al quedarse sin ellos.

**La segunda y la cuarta se miden por especificación por D53**, y no es un
detalle de método: medidas sobre la corrida entera daban «nada se mueve más de
dos puestos», y por especificación eso se cumple en cuatro de dieciocho. Una
cuenta que junta tres offsets promedia el eje que más se contradice, y entonces
la estabilidad que enseña es la del promedio y no la de ningún modelo.

Encuentra las dos corridas sola, por la columna que cada tabla lleva, y toma la
más reciente de cada conjunto. Desde la raíz del proyecto:

    .venv/Scripts/python.exe tools/comparar_candidatas.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from src import config  # noqa: E402

MODELOS = f"{config.ANALYSIS_PREFIX}__regression_models.parquet"
COEFICIENTES = f"{config.ANALYSIS_PREFIX}__regression_coefficients.parquet"

# Las columnas que identifican una celda: la misma respuesta, el mismo
# denominador y la misma familia sobre las mismas treinta unidades. Dos modelos
# que comparten las cinco se pueden comparar por AIC aunque hayan recorrido
# bolsas distintas, porque el AIC es de la verosimilitud y no de la búsqueda.
CELDA = ["DATASET", config.OFFSET_COL, "PAIR", config.YEAR_COL, config.FAMILY_COL]
# Y las que identifican una especificación, que es donde una cuenta de selección
# es legítima: dentro de ella sólo varían las parejas y los años.
ESPECIFICACION = ["DATASET", config.OFFSET_COL, config.FAMILY_COL]

FAMILIAS = (config.OLS_FAMILY, config.POISSON_FAMILY, config.NEGATIVE_BINOMIAL_FAMILY)
# Un signo se declara a partir de esta proporción de coeficientes del mismo lado.
# Por debajo, la variable no tiene signo, y marcar como vuelco a una que pasa de
# 48,8 % a 56,4 % sería inventar un hallazgo a partir de un empate.
DECISIVA = 0.60
# Por debajo de esto una proporción de signos no se mide: con tres coeficientes,
# dos del mismo lado ya dan el 67 %.
MINIMOS = 5


def ultima_corrida_de(conjunto: str) -> Path:
    """La corrida más reciente que declaró ese conjunto de candidatas.

    Se busca por la columna y no por el nombre de la carpeta: el nombre lleva la
    fecha y nada más, así que preguntarle a la tabla es la única forma de saber
    qué corrió sin abrir el registro.
    """
    candidatas = []
    anteriores = 0
    for directorio in sorted(config.RESULTS_DIR.glob("run_*"), reverse=True):
        tabla = directorio / config.DATA_SUBDIR / MODELOS
        if not tabla.exists():
            continue
        # Una corrida anterior a que el conjunto se declarara no lleva la
        # columna. Se salta y se cuenta, en vez de fallar: son corridas válidas
        # de su momento y lo único que pasa es que no se pueden comparar.
        if config.CANDIDATE_SET_COL not in pq.read_schema(tabla).names:
            anteriores += 1
            continue
        declarado = pd.read_parquet(tabla, columns=[config.CANDIDATE_SET_COL])
        if set(declarado[config.CANDIDATE_SET_COL].unique()) == {conjunto}:
            candidatas.append(directorio)
    if not candidatas:
        if anteriores:
            print(f"({anteriores} corrida(s) anteriores a la columna {config.CANDIDATE_SET_COL}, "
                  "que no se pueden comparar)")
        raise SystemExit(
            f"ninguna corrida declara {conjunto}. Se pide con\n"
            f"    .venv/Scripts/python.exe -m src.run_pipeline regressions "
            f"--candidates {config.CANDIDATE_SETS_BY_NAME[conjunto].cli}"
        )
    return candidatas[0]


def leer(directorio: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    datos = directorio / config.DATA_SUBDIR
    modelos = pd.read_parquet(datos / MODELOS)
    coeficientes = pd.read_parquet(datos / COEFICIENTES)
    return modelos, coeficientes[coeficientes["TERM"] != "INTERCEPT"]


def especificaciones(modelos: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Las combinaciones de conjunto, offset y familia que la corrida tiene."""
    return sorted({tuple(fila) for fila in modelos[ESPECIFICACION].itertuples(index=False)})


def puestos(coeficientes: pd.DataFrame, modelos: pd.DataFrame, conjunto: str,
            especificacion: tuple[str, str, str]) -> pd.Series:
    """El puesto de cada urbana dentro de una especificación, por proporción.

    Por proporción y no por cuenta cruda, que es como lo calcula la figura: la
    señalización vertical compite en menos modelos que las demás.
    """
    from src import regressions  # noqa: PLC0415  (import tardío: tools no arranca src)

    dataset, offset, familia = especificacion
    m = modelos[(modelos["DATASET"] == dataset) & (modelos[config.OFFSET_COL] == offset)
                & (modelos[config.FAMILY_COL] == familia)]
    c = coeficientes[(coeficientes["DATASET"] == dataset)
                     & (coeficientes[config.OFFSET_COL] == offset)
                     & (coeficientes[config.FAMILY_COL] == familia)]
    frecuencia = regressions.selection_frequency(c, m, conjunto).set_index("TERM")
    cuota = frecuencia["SELECTED_SHARE"].reindex(config.REGRESSION_URBAN_CANDIDATES).fillna(0.0)
    return cuota.rank(ascending=False, method="min").astype(int)


def lado(valores: pd.Series) -> str:
    """Positiva, negativa o sin signo, con un mínimo de base para decirlo."""
    if len(valores) < MINIMOS:
        return "pocos"
    parte = float((valores > 0).mean())
    if parte >= DECISIVA:
        return "positiva"
    if parte <= 1 - DECISIVA:
        return "negativa"
    return "sin signo"


def main() -> int:
    con_restos = ultima_corrida_de(config.WITH_OFFSET_LEFTOVERS)
    solo_urbanas = ultima_corrida_de(config.URBAN_ONLY_CANDIDATES)
    print(f"con restos de offset : {con_restos.name}")
    print(f"solo urbanas         : {solo_urbanas.name}  (la que el estudio reporta)")

    modelos_con, coef_con = leer(con_restos)
    modelos_sin, coef_sin = leer(solo_urbanas)

    # -- 1. El presupuesto que los restos liberan, que es un conteo ----------
    restos = [n for n in config.OFFSET_QUANTITIES if n in set(coef_con["TERM"])]
    liberadas = int(coef_con["TERM"].isin(restos).sum())
    total_con = len(coef_con)
    print()
    print(f"1. Los restos se llevaban {liberadas:,} de {total_con:,} términos seleccionados "
          f"({100 * liberadas / total_con:.1f} %).")
    print("   Es un conteo y no un orden, así que no le afecta nada de lo de abajo. Es la")
    print("   pata sobre la que se apoya D52.")

    # -- 2. El orden, dentro de cada especificación --------------------------
    filas = []
    for especificacion in especificaciones(modelos_sin):
        con = puestos(coef_con, modelos_con, config.WITH_OFFSET_LEFTOVERS, especificacion)
        sin = puestos(coef_sin, modelos_sin, config.URBAN_ONLY_CANDIDATES, especificacion)
        movimiento = (con - sin).abs()
        filas.append({
            "conjunto": config.DATASET_LABELS_ES[especificacion[0]],
            "offset": config.OFFSET_SHORT_LABELS_ES[especificacion[1]],
            "familia": config.FAMILY_SHORT_LABELS_ES[especificacion[2]],
            "máximo": int(movimiento.max()),
            "≥3": int((movimiento >= 3).sum()),
            "la que más": config.predictor_label_es(movimiento.idxmax()),
            "cambia la 1.ª": "sí" if con.idxmin() != sin.idxmin() else "no",
        })
    resumen = pd.DataFrame(filas)
    print()
    print("2. Cuánto se mueve el puesto de las doce urbanas, por especificación")
    print()
    print(resumen.to_string(index=False))
    print()
    print(f"   Máximo sobre las {len(resumen)} especificaciones: {resumen['máximo'].max()} "
          f"puestos de {len(config.REGRESSION_URBAN_CANDIDATES)}.")
    print(f"   Nada se mueve más de dos puestos en {int((resumen['máximo'] <= 2).sum())} "
          f"de {len(resumen)}; la mediana del máximo es {resumen['máximo'].median():.1f}.")
    print(f"   La primera cambia en {int((resumen['cambia la 1.ª'] == 'sí').sum())} "
          f"de {len(resumen)}.")
    print("   Sobre la corrida entera esto daría estabilidad, y esa estabilidad es la del")
    print("   promedio de tres offsets que se contradicen. Ver D53.")

    # -- 3. Cuánto del ajuste venía de los restos ----------------------------
    izquierda = modelos_con.set_index(CELDA)["AIC"]
    derecha = modelos_sin.set_index(CELDA)["AIC"]
    comunes = izquierda.index.intersection(derecha.index)
    diferencia = (derecha.loc[comunes] - izquierda.loc[comunes]).astype(float)
    igual = int((diferencia.abs() < 1e-9).sum())
    peor = int((diferencia > 1e-9).sum())
    print()
    print(f"3. AIC en las {len(comunes):,} celdas que las dos corridas resolvieron")
    print()
    print(f"   El mismo modelo gana en {igual:,} ({100 * igual / len(comunes):.1f} %): los restos")
    print("   estaban en la bolsa y no entraban, así que quitarlos no cambió nada.")
    print(f"   La reportada ajusta peor en {peor:,} ({100 * peor / len(comunes):.1f} %), "
          f"mediana de esas {diferencia[diferencia > 1e-9].median():+.2f}.")
    minimo = float(diferencia.min())
    if minimo >= -1e-9:
        print(f"   Ninguna celda ajusta mejor con menos candidatas: mínimo {minimo:+.6f}.")
        print("   Tiene que ser así —las especificaciones de la reportada son un subconjunto")
        print("   estricto—, y una celda negativa querría decir que una de las dos búsquedas")
        print("   no recorrió lo que declaró.")
    else:
        print(f"   DEFECTO: {int((diferencia < -1e-9).sum())} celda(s) ajustan mejor con menos")
        print(f"   candidatas, lo que es imposible. Mínimo {minimo:+.6f}.")

    # -- 4. Los signos, también por especificación ---------------------------
    vuelcos = []
    comparadas = 0
    for especificacion in especificaciones(modelos_sin):
        dataset, offset, familia = especificacion
        for variable in config.REGRESSION_URBAN_CANDIDATES:
            lados, bases = [], []
            for coeficientes in (coef_con, coef_sin):
                serie = coeficientes[
                    (coeficientes["DATASET"] == dataset)
                    & (coeficientes[config.OFFSET_COL] == offset)
                    & (coeficientes[config.FAMILY_COL] == familia)
                    & (coeficientes["TERM"] == variable)
                ]["COEFFICIENT_STANDARDISED"]
                lados.append(lado(serie))
                bases.append(len(serie))
            if "pocos" in lados:
                continue
            comparadas += 1
            if set(lados) == {"positiva", "negativa"}:
                vuelcos.append((variable, especificacion, lados, bases))

    print()
    print(f"4. Signos: {comparadas} comparaciones variable x especificación con al menos "
          f"{MINIMOS} coeficientes de cada lado")
    print()
    if not vuelcos:
        print("   Ninguna se da la vuelta.")
    else:
        print(f"   {len(vuelcos)} se dan la vuelta:")
        for variable, (dataset, offset, familia), lados, bases in vuelcos:
            print(f"     {config.predictor_label_es(variable):<22} "
                  f"{config.DATASET_LABELS_ES[dataset]:<18} "
                  f"{config.OFFSET_SHORT_LABELS_ES[offset]:<14} "
                  f"{config.FAMILY_SHORT_LABELS_ES[familia]:<18} "
                  f"{lados[0]} ({bases[0]}) -> {lados[1]} ({bases[1]})")
        print()
        print("   Una que se dé la vuelta sobre una base pequeña y cerca del umbral es un")
        print("   empate que se repartió distinto; una rotunda por los dos lados es un signo")
        print("   que depende de contra quién compite, y el capítulo no puede reportarlo")
        print("   sin decirlo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
