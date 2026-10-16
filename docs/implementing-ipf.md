# Implementing IPF: what exists, what is missing, and the one decision that blocks it

**Started on 2026-10-07.** D54 declared iterative proportional fitting in the
anteproyecto and the pipeline does not do it; the anteproyecto was approved on 2026-10-07
and now carries a specific objective of its own for it, so the declaration has to become
code. This document is the inspection pass that precedes the work, in the same spirit as
`adding-a-survey-year.md`: look before declaring anything.

## What is declared

A year without a survey gets the origin-destination matrix that IPF produces from the
nearest survey's matrix, subject to origin and destination totals interpolated between
surveys and scaled by the annual population. The trips that begin, end or cross each unit
are then derived from that matrix.

## What already exists, and it is more than expected

**The survey O-D matrix is built and is a first-class object.** `surveys.SurveyTrips`
carries `pairs`: one row per actor type, day type, origin zone and destination zone, with
the expanded trips summed. That is the matrix, in long form, for each of the five surveys.

**The apportionment from pairs to units is built.** `exposure.apportion_survey` spreads
each pair over the units by the share of the centroid-to-centroid line falling in each,
and spreads the intra-zonal pairs by area share. Anything that produces a `pairs`-shaped
table can be fed to it and comes out as exposure per unit.

**The zone-to-unit geometry is built.** `exposure.zone_area_shares` already computes what
share of each survey zone falls in each unit, which is the bridge any zone-level work
needs.

**What is missing is only the fitting step and what feeds it**: there is no seed, no
margins and no iteration anywhere in `src/`.

## The obstacle, which is not the algorithm

IPF itself is twenty lines. The obstacle is that **the five surveys do not share a zone
system**, so there is nothing to interpolate margins over:

| Survey | Zoning | Zones |
|---|---|---:|
| 2005 | UPZ, más un anillo de municipios | 110 |
| 2011 | `ZATs_2012_MAG` (borrowed from 2012) | 945 |
| 2015 | `ZATs_2012_MAG` | 945 |
| 2019 | `ZAT` | 1,141 |
| 2023 | `ZAT2023` | 1,215 |

A margin for 2017 cannot be interpolated between a 2015 margin on 945 zones and a 2019
margin on 1,141 zones: the two vectors are not of the same thing, and no zone of one is
the same polygon as a zone of the other.

**The anteproyecto anticipates this and settles it in one sentence**: «Los cambios de
zonificación entre encuestas se resuelven llevando todas a la unidad de análisis antes de
interpolar.» The common system is the UPL, and there are thirty of them.

## The decision that has to be taken before any code

Bringing the matrices to the UPL makes the margins interpolable, but it forces a choice
about **what the fitted matrix is a matrix of**, and the three answers produce different
exposure numbers in every year, including the survey years.

### Option A — fit a 30×30 matrix between units

Each survey's `pairs` is collapsed to a unit-by-unit matrix using the zone-to-unit area
shares, the margins of the intermediate years are interpolated between those, IPF fits a
30×30, and the exposure per unit comes from the fitted matrix's margins.

**What it gains.** It is the literal reading of the anteproyecto, the margins are
interpolable by construction, and thirty by thirty is small enough that the fitting is
instant and auditable cell by cell.

**What it costs, and this is the part that decides it.** A trip from a zone on one side of
the city to a zone on the other currently contributes to **every unit its line crosses**,
which is how an arterial corridor gets exposure from traffic that neither starts nor ends
there. A unit-by-unit matrix has only an origin and a destination, so that through-travel
disappears unless it is reintroduced afterwards. **The exposure of a transit unit would
drop**, and the four modes would not drop equally: walking is short and local, car travel
is long and crosses.

### Option B — fit at zone level, with margins brought down from the unit

The margins are interpolated at UPL level, then disaggregated back onto the nearest
survey's zones in proportion to that survey's own zone margins, and IPF fits the
zone-level matrix. The fitted matrix then goes through the existing apportionment
unchanged.

**What it gains.** The through-travel survives, because the apportionment is the one that
already exists and it still spreads along lines. The exposure of the survey years comes
out identical to today's, so the change is confined to the years it is supposed to change.

**What it costs.** The disaggregation is an assumption: it holds that the *shape* of
travel within a unit does not change between surveys, only its level. That assumption is
exactly the one IPF is supposed to avoid making, so the method is weaker than its own
argument in the anteproyecto.

### Option C — fit at zone level, margins interpolated per zone within each pair of surveys

No common system at all: each inter-survey segment is fitted on the zoning of the survey
that seeds it, and the margins are interpolated only between surveys that share a zoning.

**What it gains.** No assumption about zone shape, no collapse to units.

**What it costs.** It only works where two consecutive surveys share a zoning, which is
true for 2011 and 2015 and for no other pair. 2005, 2019 and 2023 each bring their own.
Seven of the thirteen years of the window would have no fitted matrix.

## Decided on 2026-10-07: option B

Mateo took it the day this document was written, and it is recorded as **D60** with the
reasoning and the cost. What follows is the recommendation as it was put to him, kept
because the case for B is the case against A and C and that is worth having in one place.

**Option B**, on the grounds that it is the only one that changes what it is supposed to
change and nothing else. Option A silently removes through-travel from the exposure, which
is a bigger change than IPF itself and in the opposite direction from what the study is
about. Option C does not reach enough years to be the method the objective declares.

But B's cost is real and has to be written into the thesis rather than hidden: **the
within-unit shape of travel is held constant between surveys**, and the entropy argument
the anteproyecto makes for IPF applies to the fitting and not to that step.

**Settled: option B, D60.** The implementation follows the checks at the end of this
document, and the one that decides whether it is right is the cheapest: the exposure of
the five survey years has to come out identical to today's, because for those years
nothing is fitted and nothing is disaggregated.

## What the implementation costs once the decision is taken

**Every exposure number changes, and with it every offset**, so every cross-sectional
result is superseded the day this lands. D54 already records that. The regressions do not
need rewriting; they need rerunning, and the run that answers whether the exposure moved
enough to move a coefficient has to report the comparison against D40 rather than
replacing it silently.

## What has to be checked, whatever the option

- **The fitted matrix reproduces its margins**, to the tolerance the iteration is stopped
  at, and the run reports how many iterations each year took and which years did not
  converge.
- **A survey year fitted against its own margins comes back as itself.** That is the
  identity test, and a fitting that fails it is wrong whatever else it does.
- **The total trips of a fitted year equal the interpolated total**, which is the margin
  constraint stated as a single number a reader can check.
- **No cell is negative and no margin is zero where the survey had travel**, because a
  zero margin makes the fitting undefined and the current code already refuses a zero
  denominator elsewhere for the same reason.
- **The exposure of the five survey years is unchanged** under Option B, which is the
  check that says the change stayed where it belongs.

---

## Hecho el 2026-10-07: el núcleo del ajuste

**`src/fitting.py`.** Sólo el ajuste: no sabe de encuestas, unidades, años ni modos, y eso
es deliberado. La aritmética cabe en una lectura y se puede probar contra casos cuya
respuesta se conoce de antemano, que es lo que hace `tmp/probar_fitting.py`.

| Prueba | Resultado |
|---|---|
| Un ajuste contra los propios márgenes devuelve la semilla | **exacto**, una iteración, diferencia 0 |
| Reproduce unos márgenes pedidos | 7 iteraciones, peor error relativo 5,6·10⁻¹¹ |
| Un cero de la semilla sigue siendo cero | 490 celdas, todas conservadas |
| Semilla uniforme da el producto exterior sobre el total | exacto |
| Márgenes que no suman lo mismo | error, con las dos sumas en el mensaje |
| Patrón de ceros imposible | error, y nombra la fila culpable |
| Un margen de cero | se satisface en vez de fallar |
| A 1 215 zonas, la encuesta mayor | 6 iteraciones en **0,02 s** |

**La primera es la de identidad que D60 declara como la que decide**, y sale exacta a
cero: un año de encuesta ajustado contra sus propios márgenes es la semilla sin tocar.

**Tres cosas se levantan como error en vez de devolverse.** Márgenes que no cuadran entre
sí, un negativo en cualquier parte, y un patrón de ceros que hace inalcanzables los
márgenes. Las tres son defectos de lo que se entrega al ajuste y no fallos de la
iteración, y devolver una matriz en cualquiera de ellas sería dar una respuesta
silenciosamente equivocada. La tercera nombra la fila o la columna culpable, hasta seis, en
lugar de parar en la primera.

**Lo que no hace, y hay que recordarlo al conectarlo:** no puede inventar un viaje donde la
semilla no vio ninguno, porque las dos operaciones son multiplicaciones. Eso es la virtud
del método y a la vez lo que obliga a comprobar el patrón de ceros antes de iterar.

### Lo que falta, en orden

1. ~~**Los márgenes por unidad y año.**~~ **Hecho el 2026-10-07**, y la respuesta a
   cuánto se reutiliza de D40 fue: todo. La sección al final de este documento es el
   registro.
2. ~~**La desagregación a zonas.**~~ **Hecho el 2026-10-07**, con una pregunta abierta
   —qué pasa con la parte del margen que cae fuera de las treinta unidades— que está al
   final de este documento con las cifras de las dos respuestas.
3. **Conectar con `apportion_survey`.** Hecho el 2026-10-07 y **no se tocó**, como estaba
   previsto. La identidad de D60 sale de punta a punta. Pero el ajuste descubrió que
   **25 de los 52 bloques tienen márgenes infactibles**, y qué hacer con eso es una
   decisión abierta al final de este documento.
4. ~~**La variante en el panel.**~~ **Hecho el 2026-10-07**, D62: `EXPOSURE_VARIANT =
   FITTED` al lado de las otras dos, con la comparación que la ruta imprime.
5. ~~**Las comprobaciones de la corrida.**~~ **Hecho el 2026-10-07**: once comprobaciones
   y veinte figuras en dos conjuntos. El registro está al final de este documento.

---

## Hecho el 2026-10-07: los márgenes por unidad y año

**`src/reconstruction.py`**, la etapa que usa el ajuste. `unit_margins` entrega una fila
por unidad, año, modo y tipo de día con lo que la unidad genera y lo que atrae, y
`reconcile` hace que los dos márgenes de cada año construido cuadren entre sí. Lo
comprueba `tools/margenes_para_el_ajuste.py`, once veces, cada una contra una cifra que
viene de fuera de la función que la produjo.

### Lo que no hubo que escribir, que es la mayor parte

**Los dos márgenes por unidad ya los mide el pipeline.** `apportion_survey` reparte cada
viaje por área de la zona de su origen y por la de su destino, además de repartirlo a lo
largo de la línea, y las dos asignaciones salen exportadas desde antes: son
`TRIPS_PER_AVERAGE_DAY_AT_ORIGIN` y `TRIPS_PER_AVERAGE_DAY_AT_DESTINATION` en
`analysis__exposure_by_unit`, para las cinco encuestas, treinta unidades, cuatro modos y
tres tipos de día. No se mide nada nuevo aquí. Lo nuevo es llevarlos a los doce años que
ninguna encuesta alcanzó, y eso lo hace `interpolation.fill_series` sin un solo cambio.

**Se reutiliza a propósito y no por comodidad.** Los dos paneles —el de D40 y el ajustado—
se van a comparar, y si cada uno hubiera interpolado sus insumos con un esquema distinto,
la comparación mediría la diferencia entre los esquemas igual que la que hace el ajuste.
Un esquema, una diferencia.

### Las tres decisiones que la implementación obligó a tomar

**1. Los márgenes van en la base por día de tipo y no en la de día promedio.** La columna
de la que se leen está en día promedio, que es la escala de la matriz de la encuesta, pero
D38 sólo permite una base para comparar años: 2023 agrupó los tres tipos de día en una
sola muestra y su cuota del universo es 0,772 en el laboral contra 1,0 en las otras cuatro
encuestas, de modo que sus cifras de día promedio son un 23 % menores que las de 2019 por
esa única razón. Una interpolación es una comparación entre años. La cuota de la encuesta
que siembra devuelve el margen a la escala de su matriz en el momento de ajustar, donde la
encuesta se conoce, y se cancela exacta.

**2. El peatón de 2005 no ancla ninguno de los dos márgenes.** Las dos asignaciones de
extremo se construyen de los mismos viajes que `TRIPS_PER_DAY_OF_TYPE`, así que heredan el
mismo defecto en el mismo modo: 2005 cuenta sólo la caminata de quince minutos o más.
Medido, **0,163 viajes por habitante contra 0,737 en 2011**, un factor de 4,5. A diferencia
de la exposición, aquí no hay una columna estrecha gemela a la que pasarse, así que lo que
queda es que el margen de peatón empiece en 2011 y que 2006-2010 se sostengan de él. Es
perder un anclaje en un modo, y es la pérdida correcta: un anclaje que mide otra categoría
es peor que ninguno. La exclusión queda declarada sobre la columna en
`config.MOBILITY_SURVEYS`, donde ya estaba la de la exposición, y no decidida en el código
que la lee.

**3. Los dos márgenes de un año no suman lo mismo, y ninguna matriz tiene los dos.** Hay
que reconciliarlos y hay dos causas distintas, las dos reales:

- **En un año de encuesta**, un viaje cuyo origen cae en una unidad y cuyo destino cae
  fuera del área de estudio o en una astilla de frontera entra en un margen y no en el
  otro. Va del 0,016 % al 1,242 % sobre las cinco encuestas.
- **En un año construido llega al 3,4 %**, y sale de interpolar por unidad. La suma de
  treinta curvas log-lineales no es la curva log-lineal de su suma: el sábado de la
  motocicleta de 2013 queda un 13,3 % por debajo de lo que daría la curva de la ciudad en
  el origen y un 10,5 % por debajo en el destino, y la brecha entre esas dos faltas es el
  desajuste.

**El desajuste está repartido y no concentrado, y eso es lo que dice que la reconciliación
no tapa un defecto.** Las treinta unidades tienen su tasa de 2013 entre la de 2011 y la de
2015, en los dos márgenes; la unidad que más aporta pone dos quintos del neto; y los
aportes se cancelan en los dos sentidos. Lo que la corrección absorbe es un costo conocido
de interpolar por unidad, que D40 ya documenta como el precio de no entregar a las treinta
unidades la misma curva de ciudad.

**Se escala cada margen a la media de los dos totales.** Ninguno queda privilegiado y
ninguno se mueve más de la mitad del desajuste. Preferir el origen era defendible —la
generación es la mejor medida de las dos— pero habría puesto toda la corrección sobre la
atracción, que es el margen que ya carga el supuesto por habitante más débil. El factor
que multiplicó cada fila se queda en la tabla, como el de la pandemia: dividiendo se
recupera el margen interpolado. La peor corrección es del **1,68 %** y
`config.MARGIN_RECONCILIATION_LIMIT` queda en 2 %, justo encima de lo que los datos de hoy
producen, que es donde un umbral sirve: hoy no dice nada y hablará el día que una encuesta
nueva o una unidad nueva ensanchen el reparto.

### El defecto que apareció al comprobar, y por qué importa

**Un año de encuesta no es un año medido en todo tipo de día.** La primera versión de
`reconcile` dejaba sin reconciliar toda fila cuyo año estuviera en la lista de años de
encuesta, y 2019 es año de encuesta y ninguna encuesta midió un sábado en 2019. Así
quedaban **240 filas construidas sin reconciliar**, y un ajuste al que se le entregaran
habría parado con márgenes que no cuadran. Los anclajes llegan ahora por tipo de día, que
es como los lleva D40 en `series_window` por exactamente la misma razón: el sábado y el
domingo no existen antes de 2011 y el laboral sí existe en 2005.

### Lo que el margen no es, y conviene no olvidarlo al conectar

**Un margen no es una exposición.** La exposición de una unidad es lo que la alcanza por
cualquier ruta, incluido un viaje que la cruza sin detenerse; un margen cuenta sólo los
viajes que empiezan o terminan allí. UPL04, sábado de 2011, bicicleta: **1 351 viajes al
día de exposición y margen cero en los dos extremos**. Travesía, y nada local. Esa
diferencia es la razón por la que D60 ajusta sobre las zonas y no entre unidades, y una
celda la enseña mejor que el argumento.

Un margen de cero es por tanto una observación y no un hueco. Se deja como está, son 98
de 6 720 celdas, y 57 de ellas obligan a rellenar su segmento linealmente porque el cero
deja el logaritmo indefinido en un extremo. La corrida lo cuenta y no lo suaviza.

### La tabla

6 720 filas: 1 080 medidas, 2 730 interpoladas y 2 940 sostenidas, sobre 2005-2024 para el
laboral y 2007-2024 para el sábado y el domingo. Las columnas son
`config.unit_margin_columns()`, la misma identidad que el panel interpolado para que se
puedan leer una al lado de la otra.

**El nombre del archivo está declarado y la tabla todavía no se exporta**, a propósito.
Escribirla ahora sería añadir una salida a la ruta `interpolation` que nada lee, que es uno
de los defectos que la auditoría del código heredado dejó en la lista de lo que no se
reproduce. Se exporta cuando el punto 3 conecte la etapa a una ruta. Nada queda bloqueado
por eso: `tools/margenes_para_el_ajuste.py` construye la tabla en memoria, que es además
como hay que comprobarla, porque así no puede estar comprobando una corrida vieja.

### Lo que sigue

Los puntos 2 a 5 de la lista de arriba, sin cambios: la desagregación a zonas, la conexión
con `apportion_survey`, la variante en el panel y las comprobaciones de la corrida.

---

## Hecho el 2026-10-07: la desagregación a zonas

**`reconstruction.zone_margins`**, con `seeding_blend` y `seed_zone_margins` delante.
Once comprobaciones en `tools/desagregacion_a_zonas.py`, y la que decide sale exacta.

### El mecanismo, en una línea de aritmética

Un factor de crecimiento por unidad. Los márgenes de zona de la encuesta que siembra,
repartidos a las unidades por cuota de área, dan lo que esa encuesta vio generar y atraer
a cada unidad; la razón entre el margen de este año y ése es el factor de la unidad; y
cada zona se escala por la suma de los factores de las unidades en que está, ponderada por
cuánto de ella cae en cada una. Para una zona `z` con cuota `s[z,u]` en la unidad `u`:

```
m[z] = m0[z] · ( Σ_u s[z,u]·g[u]  +  (1 − Σ_u s[z,u])·g_afuera )
```

**La identidad está dentro de la fórmula y no añadida al lado.** En un año de encuesta
`g[u] = 1` en las treinta unidades y el paréntesis vale uno, así que el resultado es la
semilla. Medido: **1,5·10⁻¹¹ viajes al día** de diferencia máxima sobre márgenes de
millones, que es el error de punto flotante y nada más.

Tres propiedades salen de que sea un escalamiento, y las tres se quieren. **Un cero de la
semilla sigue siendo cero**, que es exigible y no sólo ordenado: el ajuste no puede poner
un viaje en una celda que la semilla dejó vacía, de modo que un margen que se lo pidiera
sería inalcanzable. **Una zona a caballo entre dos unidades la gobiernan las dos**, en
proporción a cuánto de ella cae en cada una, que es la misma regla con la que se
repartieron sus viajes en primer lugar — 290 de las 853 zonas alcanzables de 2015 están a
caballo, así que es el caso común y no una esquina. Y la parte de afuera queda en manos de
una regla declarada, que es la pregunta abierta de abajo.

### La semilla se elige por tipo de día, no por año

`seeding_blend(año, anclajes)` recibe los anclajes del tipo de día porque «las encuestas
alrededor de este año» son tres preguntas distintas: el sábado tiene encuesta en 2011, 2015
y 2023, y el domingo sólo en 2023. **El sábado de 2019 descansa en 2015 y 2023 mientras el
laboral de 2019 descansa en sí mismo.** El bucle recorre años y tipos de día juntos o se
equivoca.

### Y desde el 2026-10-09 son dos encuestas y no una

Esta sección describía la regla de la encuesta más cercana, con un empate que había que
declarar en `config.SEED_ON_TIE` para 2013, 2017 y 2021. **D64 la reemplazó**, y lo que la
reemplazó no fue una preferencia sino una medición: la forma de la matriz cambiaba de golpe
en 2014, 2018 y 2022, y como la exposición de una unidad cuenta el tránsito que la atraviesa
además del que empieza en ella, ese escalón llegaba al dato. El panel brincaba 2,55 veces su
propio cambio anual en esos tres años.

Ahora un año descansa en las dos encuestas que lo enmarcan, con peso lineal en el año, y el
empate desaparece en vez de resolverse: un año exactamente entre dos encuestas es mitad de
cada una. La constante quedó sin uso y se borró.

**Mezclar no es promediar dos respuestas, y la diferencia está en dónde se mezcla.** Las
cuatro encuestas laborales están en tres zonificaciones —2011 y 2015 comparten
`ZATs_2012_MAG` con sus 945 ZAT, 2019 tiene 1 141 propias y 2023 tiene 1 215— así que una
celda de 2015 y una de 2019 no son el mismo objeto y las semillas no se pueden sumar. El año
se ajusta dos veces, **las dos contra los mismos márgenes**, y los dos resultados se combinan
después del reparto, que es el primer sitio donde las dos cosas hablan de las mismas treinta
unidades. Que los dos ajustes vayan contra los mismos márgenes es lo que hace la mezcla
segura: una combinación convexa de dos matrices con los mismos márgenes los tiene también,
así que la identidad de D60 no se toca.

Lo comprueba `tools/mezcla_de_semillas.py` en 2012, 2013 y 2014, que son los años donde las
dos semillas comparten zonificación y por tanto el único sitio donde la comprobación se puede
hacer. **Los dos caminos coinciden a 3,2·10⁻¹⁶ relativo**, así que el panel mezclado es la
exposición de una matriz y no el promedio de dos exposiciones.

Y lo que la mezcla consiguió, medido en `tools/costura_de_la_semilla.py` sobre la corrida
`run_20261009_043126`: **el brinco en 2014, 2018 y 2022 es 1,17 veces el de los demás años,
contra el 1,18 de D40 y contra el 2,55 de antes.** La curvatura media sobre el salto medio
pasó de 1,146 a 0,493. Los tres años que la curvatura todavía señala —2016, 2020 y 2024— son
el año siguiente a cada ancla de D40, y contra D40 salen en razón 1,00, 1,02 y 1,01: vienen
de que la tasa interpolada cambia de pendiente en su ancla, y llegan por los márgenes.

### Lo que no se puede colocar se reporta y no se absorbe

Si la encuesta que siembra no vio viajes de un modo en ninguna parte de una unidad, el
margen de esa unidad para este año no tiene zona a la que ir: el factor es indefinido y
ninguna redistribución lo arregla, porque todas las celdas de sus filas en la semilla son
cero. Esos viajes se cuentan en `unplaceable` y se descartan. Repartirlos por área en su
lugar inventaría viajes que la encuesta nunca vio, que es lo único que este método existe
para no hacer. **En 2013 sembrado en 2011 no hay ninguno**, y el ajuste no tiene nada que
objetar a los ocho bloques: `fitting.unfittable_margins` devuelve la lista vacía.

### La segunda reconciliación, y por qué su tamaño es una comprobación

Las zonas llevan dos partes que las unidades no: lo que cae fuera de toda unidad y lo que
no se pudo colocar. Esas difieren entre origen y destino, así que los dos totales de zona
vuelven a desajustarse y hay que escalarlos otra vez a su media. **Tiene que ser la menor
de las dos correcciones**, y lo es: 0,144 % en 2013 contra el 1,68 % del nivel de unidad.
Si alguna vez fuera la mayor, la primera no habría servido para nada.

### Los dos defectos que aparecieron al comprobar, los dos silenciosos

**Un bloque de la semilla que los objetivos no piden quedaba vacío por dentro y sostenido
por fuera.** El ajuste corre por modo y tipo de día, así que la desagregación recibe un
subconjunto de los bloques de la semilla. Entregarle a 2011 un objetivo de sólo laboral
dejaba su sábado con la parte interior en cero —sin objetivo, nada pedido, factor cero— y
la parte exterior todavía al nivel de la encuesta. El resultado es un bloque de puro
anillo, y como el anillo no es simétrico entre orígenes y destinos sus dos márgenes no
cuadran: **le costaba 4,65 % a la identidad**. La semilla se recorta ahora a lo que los
objetivos preguntan.

**Un tipo de día que la semilla no mide devolvía 120 combinaciones «sin colocar».** 2011 no
midió domingo y el domingo de 2011 se siembra en 2023; entregárselo a 2011 no daba ningún
error, daba las treinta unidades por cuatro modos como no colocables. «Sin colocar» es la
palabra para algo pequeño y real, no para una etapa conectada a la encuesta equivocada.
Ahora se levanta como error y dice por qué.

**Los dos los encontró la misma comprobación**, la identidad, y ninguno se habría visto en
el resultado: el primero cambia un número por otro número plausible y el segundo llena una
tabla de diagnóstico que nadie habría leído como un defecto.

### El hallazgo de medir el anillo

**La parte del margen que cae fuera de las treinta unidades crece con el tiempo**, y es la
huella de la encuesta y no la ciudad: la bicicleta pasa del 17,3 % en 2005 al 26,2 % en
2015 y se queda ahí, y el peatón del 5,6 % al 19,3 %. Las encuestas de 2015 en adelante
cubren más municipios del anillo que las de 2005 y 2011. No es un problema para el método
—cada año se siembra en una encuesta y hereda su huella— pero sí explica por qué la regla
de afuera pesa distinto en los tramos tempranos y en los tardíos.

| Encuesta | Bicicleta | Automóvil | Motocicleta | Peatón |
|---|---:|---:|---:|---:|
| 2005 | 17,3 % | 7,5 % | 8,5 % | 5,6 % |
| 2011 | 16,4 % | 5,6 % | 8,4 % | 9,4 % |
| 2015 | 26,2 % | 9,1 % | 16,7 % | 19,3 % |
| 2019 | 25,7 % | 14,3 % | 18,0 % | 21,4 % |
| 2023 | 25,2 % | 15,1 % | 17,1 % | 18,9 % |

### La pregunta abierta: qué pasa con la parte de afuera

`config.OUTSIDE_MARGIN_RULE`, declarada y no fijada, porque cambia lo que la matriz
reconstruida cuenta. **Un viaje de Soacha a Bogotá no tiene margen de unidad que lo
escale**, porque el estudio no mide nada sobre cómo creció el viaje del anillo. Las dos
respuestas son supuestos:

- **HELD** lo deja en el nivel de la encuesta que siembra. Dice que el anillo no cambió,
  lo que además lo convierte en una fracción decreciente de una matriz que crece.
- **CITY** lo escala por lo que se movieron las treinta unidades juntas, de modo que el
  anillo crece exactamente como Bogotá.

**Medido sobre los dieciocho años, los tres tipos de día y los cuatro modos, 216 celdas:
la mediana de la diferencia es 0,40 % del margen y la peor es 9,47 %** (motocicleta,
laboral, 2009). Siete celdas pasan del 5 % y treinta y tres del 2 %. En los años medidos de
su propio tipo de día las dos reglas coinciden **exactas**, porque el factor de la ciudad es
uno; la decisión sólo mueve años construidos, que es donde debe moverlos.

Por defecto queda HELD, que es la que no añade crecimiento que nadie midió. Es Mateo quien
la decide.

---

## Hecho el 2026-10-07: el ajuste, el reparto, y el obstáculo que apareció

Dos decisiones de Mateo de ese día cambiaron el camino antes de construirlo: el ajuste se
acota al día hábil (`config.RECONSTRUCTION_DAY_TYPES`, derivada de
`MODEL_EXPOSURE_DAY_TYPE`) y la parte del margen que cae fuera de las treinta unidades se
escala por la ciudad (`config.OUTSIDE_MARGIN_RULE = "CITY"`). Lo verificado hasta entonces
corría con los tres tipos de día y bajo la otra regla, así que nada de eso cubría el camino
que iba a correr; `tools/camino_del_dia_habil.py` lo verificó primero, en ocho
comprobaciones, y entre ellas la que importaba: **los márgenes del día hábil son idénticos
construidos solos o al lado del sábado y el domingo**, porque la reconciliación agrupa por
año, modo y tipo de día y nunca mira a los otros. Acotar no es un cambio de resultado
disfrazado de simplificación.

### La identidad de D60, ahora de punta a punta

`fit_year` y `apportion`. Un año de encuesta ajustado contra sus propios márgenes y
repartido sobre las unidades da **celda por celda la exposición que el pipeline ya
exporta**: en 2015 y en 2023, en ocho columnas —las dos bases, las dos asignaciones de
extremo, lo intrazonal, los kilómetros de línea y la cuota del universo— con una diferencia
máxima de 10⁻¹⁰ viajes al día. El ajuste converge en **una** iteración, que es lo que tiene
que hacer cuando los márgenes son los de la semilla.

**2023 es la prueba que vale, no 2015.** Es la única encuesta con cuota del universo
distinta de uno (0,7722 en el laboral), así que es la única que pasa por la conversión de
base; si esa conversión estuviera invertida, 2015 cuadraría y 2023 no.

**`exposure.apportion_survey` no se tocó.** Es la función que decide qué llega a una
unidad, y una segunda implementación de esa decisión sería una segunda respuesta a la
pregunta del estudio. Un año reconstruido llega a sus unidades por el mismo camino que un
año medido; lo único que necesita es entregarse con la forma con la que llega una encuesta.
La semilla se copia con su matriz reemplazada y **sus totales recalculados**, porque un
`SurveyTrips` cuyo `file_total` describe otra matriz que su `pairs` es el defecto que la
auditoría del código heredado registra como sobrescribir una columna de origen con un valor
derivado bajo el mismo nombre.

La columna por día de tipo la devuelven los mismos multiplicadores que el ajuste aplicó a
la columna completa, recuperados celda por celda: el IPF escala la celda `(i, j)` por
`R[i]·C[j]`, así que la razón entre la matriz ajustada y la semilla los recupera donde la
semilla es positiva, y aplicarlos a la columna estrecha es el mismo ajuste corrido sobre
ella. No es reescalar un total, que es lo que D39 rechaza: cada columna pasa después por el
reparto por su cuenta. Lo que sí supone es que **la fracción de cada celda que es caminata
larga no cambia entre encuestas**, y no mueve nada en los tres modos motorizados, cuyas dos
columnas son un número escrito dos veces.

### El obstáculo: los márgenes son infactibles, y hay que decidir qué hacer

**25 de los 52 bloques no convergen.** No por lentitud: 2 000 y 50 000 iteraciones dejan
exactamente el mismo error, 0,6706, en la bicicleta de 2017.

**Son infactibles, y está probado por flujo máximo.** En ese bloque faltan **1 966 viajes
al día de 899 651, el 0,219 %**, que ninguna matriz con ese soporte puede colocar. La
condición de existencia del IPF no es que los totales cuadren ni que cuadren los
componentes conexos: es una condición de factibilidad de transporte —para todo conjunto de
orígenes, lo que se les pide no puede pasar de lo que se pide a los destinos que
alcanzan—. Cuadrar los componentes es el caso particular en que el conjunto es un
componente entero, así que es necesario y no suficiente. El bloque de 2017 lo cumple y es
infactible.

Lo que se corrigió en el camino, porque hacía falta de todos modos:

- **`fitting` ya no da el visto bueno falso.** `inconsistent_components` comprueba la
  condición por componente, que la primera versión no miraba, y `fit` la levanta como
  error. Eso solo arregló el automóvil (converge en 212 iteraciones); los otros tres
  siguen.
- **La reconciliación de zona pasó a ser por componente conexo** y reemplaza a la global,
  porque cuadrar cada pieza implica cuadrar el total. En el día hábil mueve el **0,0841 %**
  de los viajes. Las piezas que necesitan una corrección grande son las de dos o tres
  zonas, así que la cifra que vale es la de viajes movidos y no el peor factor; una pieza
  de cuarenta viajes puede necesitar que le partan el margen por la mitad sin que eso
  signifique nada.
- **`fitting.infeasible_by`** responde la pregunta exacta por flujo máximo, como
  diagnóstico y no como guardia: cuesta mucho más que una iteración y en una semilla sin
  ceros la respuesta siempre es cero. Se llama cuando un bloque no converge, para
  distinguir «no existe tal matriz» de «la iteración necesitaba más pasos», que tienen
  remedios opuestos.

### A qué escala falla, que es lo que decide si importa

| | mediana | máximo |
|---|---:|---:|
| error agregado del margen por unidad | 0,000 % | **0,774 %** |
| error de **una** unidad sola | 0,000 % | **55,74 %** |

**El agregado es intachable y una unidad sola se equivoca en 55,7 %.** Eso importa y el
agregado no, porque las regresiones leen justamente la variación entre unidades: un error
que se promedia a cero sobre las treinta es exactamente el que no se promedia dentro de una
sección cruzada. Los bloques afectados son de bicicleta (ocho de trece años) y de
motocicleta (cinco); el automóvil y el peatón quedan por debajo del 0,07 %.

### De dónde sale, y es lo que convierte esto en una decisión y no en un defecto

**Las semillas tienen entre 0,5 % y 1,4 % de densidad.**

| Encuesta | Bicicleta | Automóvil | Motocicleta | Peatón |
|---|---:|---:|---:|---:|
| 2005 (110 zonas) | 7,26 % | 25,05 % | 4,21 % | 8,02 % |
| 2011 (945) | 0,56 % | 1,26 % | 0,46 % | 1,07 % |
| 2015 (945) | 0,59 % | 1,23 % | 0,73 % | 1,31 % |
| 2019 (1 141) | 0,64 % | 1,40 % | 0,59 % | 0,99 % |
| 2023 (1 215) | 0,50 % | 0,74 % | 0,53 % | 0,64 % |

A esa densidad, **un cero de la semilla casi nunca significa que nadie viaje ahí**:
significa que la muestra de unos miles de hogares no vio ese viaje en su día de referencia.
Conservar cada cero es conservar ruido de muestreo como si fuera geografía, y es lo que
hace infactibles los márgenes. La virtud que D60 le atribuye al método —que no puede
inventar un viaje que la encuesta no vio— es a esta densidad una restricción mucho más
fuerte de lo que parecía al declararla.

### Lo que un piso costaría, medido

Un piso sustituye los ceros exactos por un valor pequeño, completa el soporte y vuelve
factible cualquier margen. Medido sobre el peor bloque, la bicicleta de 2017, con el piso
expresado como fracción del viaje medio por celda ocupada (352,89 al día):

| Piso | Viajes inventados | Converge | Iteraciones | Peor unidad |
|---|---:|---|---:|---:|
| ninguno | 0 % | no | — | **55,74 %** |
| 10⁻⁶ | **0,017 %** | 6·10⁻⁷ | 5 000 | **0,00 %** |
| 10⁻⁴ | 1,739 % | sí | 919 | 0,00 % |
| 10⁻³ | 17,39 % | sí | 381 | 0,00 % |

**El piso de 10⁻⁶ inventa diecisiete viajes de cada cien mil** y lleva el peor error de
unidad de 55,74 % a cero. Tres órdenes de magnitud por debajo de cualquier cifra que el
estudio reporte.

Y el argumento del anteproyecto lo respalda en vez de estorbarlo: **con semilla uniforme el
IPF se reduce al modelo de máxima entropía**, que es la referencia que el anteproyecto cita
desde la mecánica estadística. Una semilla con piso es «la encuesta más ε veces uniforme»,
es decir una mezcla de las dos cosas que el anteproyecto nombra, abrumadoramente la
encuesta.

**Lo que cuesta y hay que escribirlo:** deja de ser cierto que el ajuste no invente viajes
que la encuesta no vio. Inventa el 0,017 % de ellos, y la matriz ajustada tiene un valor
positivo en toda celda.

### La decisión abierta

Qué hacer con los 25 bloques infactibles. Las cuatro respuestas, con lo que cada una
cuesta:

1. **Un piso en la semilla.** Inventa 0,017 % de los viajes al valor de 10⁻⁶ y resuelve el
   problema entero. Es la recomendación.
2. **Engrosar la zonificación de la semilla** hasta que la matriz sea bastante densa. No
   inventa nada, y acorta las líneas: a menos zonas, menos travesía, que es lo que D60
   rechazó al descartar ajustar entre unidades.
3. **Proyectar los márgenes al punto factible más cercano**, por programación lineal. No
   inventa viajes y mueve los márgenes en una cantidad medida. Es maquinaria mayor.
4. **Aceptar el incumplimiento** y reportarlo. Cuesta una unidad con el 55,7 % de error, y
   es la que la sección cruzada lee.

Pendiente de Mateo. Nada del punto 3 se da por terminado hasta que se decida, porque la
variante del panel del punto 4 se construye con lo que salga de aquí.

---

## Resuelto el 2026-10-07: el piso, el panel, y la ruta

La pregunta abierta de arriba la decidió Mateo: **piso de 10⁻⁶**, registrado como **D61**
con las cifras y los tres números declarados. El panel y su comparación contra D40 son
**D62**. La ruta es `python -m src.run_pipeline reconstruction` y la corrida que lo produjo
es `run_20261007_131052`.

### Lo que resolvió el piso, y lo que no era obvio

**Se aplica sólo donde el soporte de la encuesta no alcanza los márgenes**, y eso no es una
optimización: una semilla con piso lleva más viajes de los que los márgenes piden, así que
ajustarla escala todo hacia abajo y un año de encuesta ya no volvería a salir él mismo.
Medido, **catorce de cincuenta y dos bloques lo necesitaron, ninguno de encuesta**, y la
identidad de D60 vuelve a 9·10⁻¹¹ viajes al día.

**El piso sólo sirve para averiguar qué celdas hacen falta.** Una semilla sin ceros da una
matriz densa —998 001 celdas con 999 zonas, y el reparto construiría una línea por cada
una— así que la primera pasada va con tolerancia floja, se poda, y la segunda ajusta sobre
lo que queda. El soporte podado resulta factible y de una a veinte veces el de la semilla.

| | Sin piso | Con piso |
|---|---:|---:|
| Bloques que convergen | 27 de 52 | **52 de 52** |
| Peor error de **una** unidad | **55,74 %** | **0,0097 %** |
| Viajes inventados | 0 | 11 965 de 109 911 870, **0,0109 %** |

### Los tres números, medidos y no elegidos

`RECONSTRUCTION_SEED_FLOOR = 1e-6` — a 10⁻⁴ converge en un quinto de las pasadas e inventa
1,74 %; la convergencia más lenta es el precio del número más pequeño.
`RECONSTRUCTION_PRUNE_BELOW = 0.01` viajes al día — lo que sobrevive conserva el 99,96 % al
99,99 % de los viajes ajustados y cuesta a los márgenes entre 0,0086 % y 0,043 %.
`fitting.DEFAULT_TOLERANCE = 1e-4` — puesta en el suelo de ruido del paso siguiente, que es
esa poda; más estricta mide por debajo del error de la operación que viene después.

### Lo que hubo que arreglar porque la comprobación estaba mal

**La condición de existencia no es que cuadren los componentes conexos.** Es de
factibilidad de transporte: para todo conjunto de orígenes, lo que se les pide no puede
pasar de lo que se pide a los destinos que alcanzan. Cuadrar los componentes es el caso
particular, así que daba el visto bueno al bloque de la bicicleta de 2017, que es
infactible por 1 966 viajes de 899 651 — probado por flujo máximo y no inferido de que no
convergiera: 2 000 y 50 000 iteraciones dejan el mismo error.

`fitting.infeasible_by` responde la pregunta exacta, **como diagnóstico y no como
guardia**: cuesta mucho más que una iteración y en una semilla con piso la respuesta
siempre es cero. Se llama cuando un bloque no converge, para distinguir «no existe tal
matriz» de «la iteración necesitaba más pasos», que tienen remedios opuestos.

### El panel, y el resultado

`analysis__fitted_exposure_by_unit`, 1 560 filas, con las columnas de D40 en el mismo orden
más `SEED_SURVEY_YEAR`. Y `reference__fitted_blocks` al lado, un bloque por año y modo, que
es donde está lo que el piso abrió: un grano distinto y por tanto una tabla distinta.

**Las dos variantes coinciden en el agregado y discrepan mucho por unidad.** La razón de la
exposición ajustada a la de D40 tiene mediana 0,999 en los cuatro modos y rango 0,493–2,348
en la bicicleta. Ésa es la justificación del método, enunciada como medición: **una tasa
interpolada por unidad le da a cada unidad su propia curva y no sabe nada de a dónde van
los viajes**, y el ajuste es lo que devuelve eso. Si las dos hubieran coincidido en todas
partes, la conclusión honesta habría sido que el supuesto extra no compra nada, y es la
razón por la que la comparación la imprime la ruta y no la deja a un documento.

### Lo que falta

El punto 5 de la lista de arriba, que es lo que la ruta ya reporta en nueve comprobaciones
y lo que todavía no: **ninguna figura**. Y la decisión que no es de medición: **qué variante
reportan las regresiones**. Hoy leen `INTERPOLATED`, y moverlo mueve todo resultado de
sección cruzada, así que es de Mateo con los dos paneles en la mano.

---

## Hecho el 2026-10-07: el parche de pandemia, que faltaba

**No estaba, y la ausencia era una decisión mía equivocada.** `reconstruction.build` ponía
`PANDEMIC_PATCH_FACTOR = 1.0` en las 1 560 filas con un comentario diciendo que D49 no
aplicaba a esta variante. Sí aplica, y el panel ajustado con parche es la exposición sobre
la que el estudio estima. Es **D63**, y la corrida es `run_20261007_141706`.

El panel lleva ahora dos variantes, 3 120 filas: `FITTED` y `FITTED_PANDEMIC_PATCHED`. La
sin parchar se queda al lado por la razón que D42 da de su propia pareja.

**El parche se aplica exacto y no aproximado**, y por eso no hace falta un segundo ajuste:
su factor es un número por modo y año, el mismo para todas las unidades, y el reparto es
lineal en los viajes, así que multiplicar la exposición de una unidad es la misma
aritmética que multiplicar cada celda de la matriz y repartir otra vez. **La corrida lo
comprueba en vez de afirmarlo** —el nivel parchado contra el sin parchar por su propio
factor, que sale exactamente cero— porque si un factor llegara a depender de la unidad el
atajo dejaría de ser exacto en silencio.

**Los factores se recalculan del panel ajustado y no se toman prestados de D40**, porque un
factor es el choque de Google dividido por la altura de la curva de ciudad del propio panel
en ese año. Tres modos coinciden en milésimas y **el peatón difiere un 6 % y un 9 %**: 0,534
contra 0,567 en 2020 y 0,741 contra 0,810 en 2021. No es redondeo, es que el panel ajustado
espera otro 2021 de caminata que el de D40.

**El obstáculo fue silencioso.** `interpolation._city_series` filtraba por
`EXPOSURE_VARIANT == INTERPOLATED` como constante; con el panel ajustado devolvía vacío y
`pandemic_factors` se negaba a parchar avisando de un panel «que no llega a 2019» — el fallo
que su propio docstring llama peor que no parchar. La variante es ahora parámetro de las
tres funciones, y no se duplicó nada de `interpolation`.

**Y las regresiones leen esto desde ahora.** `config.MODEL_EXPOSURE_VARIANT` es el único
sitio que dice qué construcción reporta el estudio y `config.model_exposure_table()` deriva
la tabla; `regressions` tenía el nombre del archivo escrito como literal y el filtro de
variante puesto una segunda vez, así que los dos coincidían por casualidad. En consecuencia
**`regressions` corre después de `reconstruction` y ya no después de `interpolation`**, y lo
dice en vez de fallar con un archivo ausente genérico.

---

## Hecho el 2026-10-07: el punto 5, las figuras

Veinte figuras en dos conjuntos, y ninguno duplica al otro. **`src/reconstruction_figures.py`**
dibuja las cuatro que contestan lo nuevo, y las dieciséis restantes son las seis familias de
`interpolation_figures` apuntadas a este panel.

### Las cuatro propias, en `figures/reconstruction/`

| | Figura | La pregunta que contesta |
|---|---|---|
| 00 | `comparacion__razon_por_unidad` | **Dónde** discrepan las dos construcciones: 30 unidades × 13 años, un panel por modo |
| 00 | `comparacion__distribucion` | **Cuánto** discrepan: la mediana está a una milésima de 1 y las colas llegan a la mitad y al doble |
| 01 | `mapa__razon_por_unidad` | Si la discrepancia tiene estructura espacial o es ruido |
| 02 | `ajuste__bloques` | Qué hizo el ajuste: lo que el piso inventó por bloque, y qué encuesta siembra cada año |

**El lenguaje visual es el de `interpolation_figures` y no un segundo.** Su `draw_heatmap`
se importa en vez de reimplementarse porque ya resolvía las cuatro cosas que una razón
necesita: rampa divergente en log2, de modo que doblar y partir por la mitad disten lo
mismo del centro; escala fijada por un percentil de las desviaciones y no por la mayor de
ellas; gris para lo ausente, que si no se confundiría con el centro de la rampa, que es
blanco; y marcas en las columnas verdaderas por construcción. Dos figuras de un estudio con
dos rampas son dos figuras que un lector tiene que aprender dos veces.

El percentil es **99 y no el 95 de la interpolación**, decidido por Mateo tras ver las dos:
a 95 la figura saturaba 68 de sus 1 560 celdas y escondía justo las que más dicen, y a 99
recorta 16.

**El mapa es la única excepción al reúso.** `maps.render_choropleth` dibuja la cartografía
de referencia con rampa **secuencial** y escribe un mapa por archivo, y una razón centrada
en uno pide rampa divergente y los cuatro modos juntos. Adaptarla habría cambiado una
función verificada por una figura que no es el mapa de referencia.

### Las dieciséis heredadas, en `figures/reconstruction_panel/`

`interpolation_figures` tenía los nombres de las variantes de D40 escritos en siete sitios,
así que el panel ajustado —que es el que leen los modelos— se quedaba sin serie de ciudad,
sin serie por unidad y sin hoja de procedencia. Ahora el par se declara en
`config.EXPOSURE_VARIANT_PAIRS` y se deriva con `config.variant_pair_of`, y `draw` recibe la
carpeta donde escribe.

**Se verificó regenerando las veintidós figuras de D40 antes y después: salen byte a byte
idénticas.** La comparación se hizo contra la versión de `git HEAD` y en la misma carpeta de
corrida, porque el sello lleva el nombre de la corrida y dos nombres distintos habrían hecho
diferir los veintidós archivos por una razón que no es la que se estaba midiendo.

**Y el reúso dejó una frase mintiendo, que es el costo que un módulo compartido hay que
vigilar.** El subtítulo de la serie decía «abajo la tasa que es lo que en realidad se
interpola», cierto de D40 y falso del panel ajustado, donde lo que se interpola son los
márgenes de la matriz y la tasa es lo que salió del reparto. Ahora cada panel dice la suya.

### Lo que las figuras enseñaron y las tablas no decían

**Hay una costura donde cambia la encuesta que siembra.** El peatón sale azul en 2012-2013 y
rojo en 2014 en casi las treinta unidades, y 2014 es el primer año sembrado en 2015 en vez
de en 2011. Medido sobre el propio panel ajustado, no sobre la razón:

| | salto anual medio, en costura | fuera de costura | razón |
|---|---:|---:|---:|
| **Ajustado** | **0,198** | 0,077 | **2,55** |
| D40 | 0,102 | 0,087 | 1,18 |

En 2014, 2018 y 2022 el cambio año a año del panel ajustado es el doble del de D40 y 2,5
veces el suyo propio fuera de esas costuras. Es una propiedad del método —2013 se construye
con la matriz de 2011 y 2014 con la de 2015, así que la forma espacial del viaje cambia de
golpe— y **no sesga una sección cruzada, que estima un año a la vez. Sí importa para el
panel**, que es la metodología de la tesis y que lee justamente la variación dentro de una
unidad a lo largo del tiempo: un brinco artificial del veinte por ciento cada cuatro años es
lo que ese modelo leería como cambio real.

Hay al menos una salida —mezclar las dos encuestas que enmarcan un tramo en vez de saltar de
una a la otra, que es lo que la regla de «la encuesta más cercana» renuncia a hacer— pero
cambia lo que la matriz cuenta y es decisión de Mateo. **Queda anotado aquí para que no
llegue a la etapa de panel sin haberse discutido.**

### Anclar y sembrar no son lo mismo

Lo preguntó Mateo y conviene que quede escrito, porque es fácil confundirlos. **Anclar** es
aportar un valor a la curva que se interpola; **sembrar** es aportar la matriz que el ajuste
escala. Una encuesta puede anclar y no sembrar nunca.

Anclan las cinco encuestas, salvo el peatón, donde 2005 está excluida porque contó sólo la
caminata de quince minutos o más: 0,163 viajes por habitante contra 0,737 en 2011. Su margen
de peatón se sostiene de 2011 hacia atrás en vez de interpolarse.

Siembran 2005 los años 2007-2008, 2011 los 2009-2013, 2015 los 2014-2017, 2019 los 2018-2021
y 2023 los 2022-2024. **2005 no siembra ningún año que el estudio use**, porque el panel se
construye sobre 2012-2024. Si alguna vez se ensanchara la ventana hacia atrás habría que
decir que 2007 y 2008 se sembrarían en una zonificación de 110 UPZ en vez de 945 ZAT, con
densidad del 4 al 25 % en vez del 0,5 %.
