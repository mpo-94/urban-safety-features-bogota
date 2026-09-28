"""¿Qué parte del cambio anual de la ciclorruta es red y qué parte es cartografía?

La serie de ciclorruta llega como trece fotos anuales de la misma capa, y el
panel va a leer la diferencia entre dos fotos como si fuera obra. No siempre lo
es. Entre 2023 y 2024 la longitud total baja un \\qty{0.37}{\\percent} y la red en
realidad creció: lo que pasó es que mil cuatrocientos segmentos que estaban en
los dos años se volvieron a trazar más cortos.

Esta comprobación separa las dos cosas en los doce pares consecutivos. Para cada
par parte el cambio en tres:

  1. lo que se fue      códigos del año N ausentes en N+1;
  2. lo que llegó       códigos de N+1 ausentes en N;
  3. lo que se remidió  códigos en los dos años con longitud distinta.

Las dos primeras son red. La tercera no: un segmento presente en los dos años que
mide distinto no se construyó ni se demolió.

**La persistencia de identificadores es el guardarraíl.** Si una redigitalización
además renumeró los códigos, sus segmentos aparecen como baja y alta a la vez, y
esta descomposición no los distingue de obra real. Una persistencia alta es lo
que permite confiar en el reparto; una persistencia baja es también un resultado,
porque dice que ese escalón no es interpretable.

Aplica solo a la ciclorruta. La señalización vertical no se entrega como fotos
anuales sino como un inventario más movimientos, así que su serie se construye
sumando altas y bajas y no puede tener este problema; tendrá otros.

Desde la raíz del proyecto:

    .venv/Scripts/python.exe tools/redigitalizacion_ciclorruta.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from src import config  # noqa: E402

# El código del segmento. Es el que la capa repite año tras año, y sobre el que
# se mide la persistencia; CicCIV identifica el eje vial y agrupa varios
# segmentos, así que sirve de contraste pero no de llave.
CODIGO = "CicCodigo"
EJE = "CicCIV"

# Un metro. Por debajo de eso, una diferencia de longitud es ruido de coordenadas
# y no una remedición.
TOLERANCIA_M = 1.0


def lee(ruta: Path) -> dict:
    """Las longitudes por código, y cuánto de la capa se queda fuera de esa cuenta.

    **El total es sobre toda la capa y el reparto solo sobre lo que tiene código.**
    Separarlos importa: 2012 entrega \\num{1875} de sus \\num{3435} geometrías sin
    `CicCodigo`, que son \\qty{72.8}{\\kilo\\metre} de los \\qty{161.3}{\\kilo\\metre}
    que mide. Sumar solo lo codificado daría un total de la mitad y convertiría el
    salto a 2013 en un crecimiento que no existe; descartarlo en silencio es el
    defecto que esta comprobación existe para no cometer.
    """
    capa = gpd.read_file(ruta).to_crs(config.PROJECTED_CRS)
    capa = capa.assign(_L=capa.length)
    codificada = capa[capa[CODIGO].notna()]
    return {
        "por_codigo": codificada.groupby(CODIGO)._L.sum().to_dict(),
        "total_capa": float(capa._L.sum()),
        "geometrias": len(capa),
        "sin_codigo": int(capa[CODIGO].isna().sum()),
        "km_sin_codigo": float(capa[capa[CODIGO].isna()]._L.sum()) / 1000,
    }


def compara(antes: dict, despues: dict) -> dict:
    """El cambio entre dos años, partido en red y cartografía."""
    mapa_antes, mapa_despues = antes["por_codigo"], despues["por_codigo"]
    codigos_antes, codigos_despues = set(mapa_antes), set(mapa_despues)
    comunes = codigos_antes & codigos_despues

    se_fueron = sum(mapa_antes[c] for c in codigos_antes - codigos_despues)
    llegaron = sum(mapa_despues[c] for c in codigos_despues - codigos_antes)
    remedido = sum(mapa_despues[c] - mapa_antes[c] for c in comunes)

    cambiaron = [c for c in comunes if abs(mapa_despues[c] - mapa_antes[c]) > TOLERANCIA_M]
    return {
        # El total es de la capa entera; el reparto, de lo codificado. La
        # diferencia entre los dos es lo que la descomposición no alcanza a ver.
        "total_antes": antes["total_capa"],
        "total_despues": despues["total_capa"],
        "fuera_antes_km": antes["km_sin_codigo"],
        "fuera_despues_km": despues["km_sin_codigo"],
        "se_fueron_km": se_fueron / 1000,
        "llegaron_km": llegaron / 1000,
        "remedido_km": remedido / 1000,
        "comunes": len(comunes),
        "cambiaron": len(cambiaron),
        "acortados": sum(1 for c in cambiaron if mapa_despues[c] < mapa_antes[c]),
        "alargados": sum(1 for c in cambiaron if mapa_despues[c] > mapa_antes[c]),
        "persistencia": len(comunes) / len(codigos_antes) if codigos_antes else float("nan"),
    }


def veredicto(fila: dict) -> str:
    """Qué se puede leer de ese escalón, en una palabra.

    El orden importa: una persistencia baja invalida el reparto, así que se
    comprueba antes que nada. Después, la remedición se compara con el cambio
    neto: cuando pesa más que él, el signo del escalón lo decide la cartografía.
    """
    # Un año que entrega geometría sin código deja parte de su longitud fuera del
    # reparto, y entonces el veredicto no es sobre el escalón entero.
    if max(fila["fuera_antes_km"], fila["fuera_despues_km"]) > 1.0:
        return "parcial: un año entrega geometría sin código"
    if fila["persistencia"] < 0.90:
        return "no interpretable: los códigos se renumeraron"
    neto = fila["total_despues"] - fila["total_antes"]
    if abs(fila["remedido_km"] * 1000) > abs(neto):
        return "dominado por remedición"
    if abs(fila["remedido_km"]) > 0.5:
        return "red, con remedición apreciable"
    return "red"


def main() -> None:
    predictor = next(p for p in config.STATIC_PREDICTORS
                     if p.name == "CYCLEWAY_LENGTH_DENSITY")
    rutas = dict(predictor.declared_files())
    años = sorted(int(a) for a in rutas)

    print("LA CICLORRUTA AÑO A AÑO: qué parte del cambio es red y qué parte cartografía")
    print(f"la remedición se cuenta sobre códigos presentes en los dos años, "
          f"con tolerancia de {TOLERANCIA_M:.0f} m\n")

    # Lo que cada capa entrega sin código queda fuera del reparto, así que se dice
    # antes de repartir nada: un veredicto sobre la mitad de una capa no es un
    # veredicto sobre la capa.
    print("Geometría sin identificador, que la descomposición no alcanza:")
    huecos = False
    for año in años:
        datos = lee(rutas[str(año)])
        if datos["sin_codigo"]:
            huecos = True
            print(f"   {año}: {datos['sin_codigo']:,} de {datos['geometrias']:,} "
                  f"geometrías, {datos['km_sin_codigo']:.2f} km de "
                  f"{datos['total_capa'] / 1000:.2f}")
    if not huecos:
        print("   ninguna: todos los años codifican toda su geometría")
    print()

    cache: dict[int, dict] = {}
    filas = []
    for anterior, siguiente in zip(años, años[1:]):
        for año in (anterior, siguiente):
            if año not in cache:
                cache[año] = lee(rutas[str(año)])
        fila = compara(cache[anterior], cache[siguiente])
        fila["par"] = f"{anterior}-{siguiente}"
        fila["veredicto"] = veredicto(fila)
        filas.append(fila)
        cache.pop(anterior, None)  # dos años en memoria bastan

    cabecera = (f"{'par':>9} {'persist.':>9} {'km antes':>9} {'km después':>11} "
                f"{'neto':>8} {'llegó':>7} {'se fue':>8} {'remedido':>9} "
                f"{'segm.':>7}  veredicto")
    print(cabecera)
    print("-" * len(cabecera))
    for f in filas:
        neto = (f["total_despues"] - f["total_antes"]) / 1000
        print(f"{f['par']:>9} {100 * f['persistencia']:>8.1f}% "
              f"{f['total_antes'] / 1000:>9.2f} {f['total_despues'] / 1000:>11.2f} "
              f"{neto:>+8.2f} {f['llegaron_km']:>+7.2f} {-f['se_fueron_km']:>+8.2f} "
              f"{f['remedido_km']:>+9.2f} {f['cambiaron']:>7}  {f['veredicto']}")

    print()
    print("segm. = códigos presentes en los dos años cuya longitud cambió más de la "
          "tolerancia")
    print()
    for f in filas:
        if f["cambiaron"]:
            print(f"   {f['par']}: de {f['comunes']} códigos comunes, {f['cambiaron']} "
                  f"cambian de longitud ({f['acortados']} se acortan, "
                  f"{f['alargados']} se alargan)")

    print()
    sospechosos = [f for f in filas if f["veredicto"] != "red"]
    if sospechosos:
        print(f"{len(sospechosos)} de {len(filas)} escalones llevan cartografía mezclada:")
        for f in sospechosos:
            print(f"   {f['par']}  {f['veredicto']}")
    else:
        print("los doce escalones son red: ninguno está dominado por remedición")


if __name__ == "__main__":
    main()
