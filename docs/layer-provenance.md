# Where each delivered layer came from

Chapter 3 has to say where every variable's data comes from, and it has to cite
it. Until 2026-09-22 it could not: **provenance was the one thing the study never
wrote down.**

That was not an oversight in a document but a gap in the declaration itself.
`config.StaticPredictor` has eleven fields — `source_layer`, `source_file`,
`geometry`, `method`, `measures`, `time_coverage` and the rest — and none of
them says where the layer came from. `data-layout.md` records where each file
sits under `data/`, which is a different question. And no entry of
`references.bib` covered any predictor layer.

**Thirteen entries close it**, and [the table](#the-assignment-and-where-it-belongs)
assigns one to every layer the pipeline reads.

The sections before that table are the inspection they were found from: what
each delivered layer says about **itself**, in its metadata sidecars, its
lineage strings and its columns. They are kept because a citation that names the
wrong dataset is caught by comparing it against the file, which is how one of
the first eleven was caught, and because the two caveats that survive are only
legible next to the evidence.

---

## What is cited today, and what is not

Seven entries of `references.bib` identify a source of data:

| Entry | Covers | Cited in the text? |
|---|---|---|
| `Anuarios_de_siniestralidadOMB` | the crash records | yes |
| `DecretoPOTBogota` | the 30 UPL | yes |
| `EncuestasMovilidad` | the five mobility surveys | not yet |
| `ColombiaCensoNacional` | the DANE census microdata | not yet |
| `PoblacionBogotaDC` | population by unit, 2005–2035 | not yet |
| `RUNTRNA` | the vehicle registry | not yet |
| `VisionCiudadLibro` | the SDM map book | not yet |

Those cover the response, the spatial frame, and **both quantities that enter
the models from outside the predictor bundle** — the exposure, which is built
from the surveys, and the resident population.

They covered none of the thirteen predictor layers, which is the gap the thirteen
entries of 2026-09-22 close. The table at the end of this document is the
assignment; everything between here and there is the evidence it was built on.

---

## The thirteen predictor layers, by how much the delivery tells us

Of the fifteen candidates in `regression-inventory.md`, two come from cited
sources. The other thirteen are layers in `data/shp_properties_sorted/`, and
they fall into three groups.

### A. The data names its own source — three layers

These carry a filled-in metadata form or an administrative column, and the
origin can be read off them rather than guessed.

| Layer | Variable | What it declares |
|---|---|---|
| `points/Paraderos_SITP` | SITP bus stop density | ISO metadata, credit: **Secretaría Distrital de Movilidad, Oficina de Información Sectorial**. Created 2019-11-19, published 2019-12-19. Abstract and eight keywords filled in. |
| `points/Red_Semaforica` | signalised intersection density | ISO metadata, title *Red Semafórica de Bogotá D.C*, owner: **Oficina de Tecnologías de la Información y las Comunicaciones, SDM**, contact `simur@movilidadbogota.gov.co`, Cl. 13 #37-35. Created 2019-11-19, published 2019-12-19. |
| `areas/avenidas_corregidas` | arterial road area share | Not in a metadata file but in the records: all 33,015 carry `NORMATIVA_` = *"En el marco del Decreto 555 del 29 de diciembre de 2021 — Por el cual se adopta la revisión general del Plan de Ordenamiento Territorial de Bogotá"*, with `FECHA_ACTO` and `FECHA_CAPT` both 2021-12-29. |

All three resolved. The two SDM point layers turned out to be published on
Datos Abiertos Bogotá under the titles their metadata already carried, and the
arterial layer under two entries rather than one, for the reason given below.

### B. A trail that names an institution — three layers

No metadata form, but the ESRI lineage or the source path survived the
delivery, and it names where the file was built.

| Layer | Variable | The trail |
|---|---|---|
| `points/arbolado_urbano` | the three tree variables | Its source is a geodatabase connection, not a file: a geodatabase called `Geodata`, reached as an administrator account whose name ends in `jbb`. Those initials point at the **Jardín Botánico José Celestino Mutis**, which is the entity that keeps Bogotá's tree census. Suggestive, not established. |
| `points/camaras_salvavidas_bogota` | speed camera density | Built under an `SDM\2022\Camaras_Salvavidas` folder, exported from a feature class named `Camaras_Salvavidas_5Feb2020`. **SDM**, and a vintage of February 2020 that the file name states and nothing else confirms. |
| `points/Señalizacion_Vertical` | vertical signage density (series) | Built under `…\SDM 2023\8. Agosto 2023\0.0. LIBRO DE MAPAS_Julio_Agosto\4. SEÑALIZACION\1. Señalización_Vertical\`. Lineage: `Append 'Diseno Señal Vertical' SENAL_VERTICAL_DIC2022`. |

**That path is the decisive one, and it settled all three signage layers at
once.** *Libro de mapas* is the SDM's own map book, and its
*Señalización, Semaforización y PMT* page publishes vertical signage, horizontal
marking and school-zone marking together. `SenalizacionSemaforizacionPMT` cites
that page and covers the three, including the two that carry no stock.

The page is an ArcGIS Experience application and returns nothing to a plain HTTP
fetch, so it cannot be checked from here; it was verified in a browser.

### C. Nothing at all — seven layers

Empty metadata form or no form, and no column that names an origin.

| Layer | Variable | What is there instead |
|---|---|---|
| `areas/andenes_x_localidad` | sidewalk area share | A QGIS 3.26.2 form with every field blank. Columns `Nombre_de_`, `Identifica` are the **locality** layer's: the file arrived already joined to the 19 localities, so it is derived and not raw. |
| `areas/calzada_x_localidad` | roadway area share | Same empty form. Columns `CalFuncion`, `CalCIV`, `CalCodigo` are the nomenclature of the **Malla Vial Integral** — `CIV` is its road identification code — plus the same locality join. |
| `areas/parques_urb` | urban park area share | Empty QGIS 3.22.12 form. Columns `ID_PARQUE`, `TIPOPARQUE`, `ESTRATO` look like a parks inventory, and `urban_area` and `area_div` are derived columns added downstream. |
| `areas/puentes` | bridge deck area share | Empty form. Columns `PueCodigo`, `PueTipo`, `PueUbicaci` are Malla Vial nomenclature again. |
| `points/crossings` | pedestrian crossing density | Empty form. Four columns, `field_1, x, y, count`, in EPSG:4326, beside a `crossings2.csv` holding the same four. It is an **OpenStreetMap** extraction, which `config` states in `measures` and chapter 2 repeats — but the query, the date and the download are recorded nowhere. |
| `points/estacion_localidad` | TransMilenio station density | **No metadata file of any kind**, only a `.qpj`. 145 MultiPoint features in EPSG:4326; `numero_est … troncal_es` plus `NOMBRE`, `CODIGO_LOC` from a locality join. |
| `lines/ciclo_lines` | cycleway length per unit area (series) | **No metadata file of any kind**, for any of the thirteen years. Columns `CicCodigo`, `CicCIV`, `CicTSuperf` are Malla Vial nomenclature; the projection is an unnamed MAGNA-SIRGAS origin, which tells us who built it and not who published it. |

**Five of the seven carried Malla Vial or locality nomenclature**, and that was
the lead that resolved them: `CIV`, `Cal*`, `Pue*`, `Cic*` and `MVI*` all belong
to the Malla Vial Integral, the joint inventory of the Secretaría Distrital de
Movilidad, the Instituto de Desarrollo Urbano and Catastro Distrital. Four of
them are published individually by the IDU on Datos Abiertos and are cited
there; the arterial layer is cited against the integral inventory at IDECA.

**OpenStreetMap stayed the awkward one.** It is the only source that is not an
institution publishing a dated product, and an OSM layer with no extraction date
and no query cannot be reproduced by a reader. `OSMBogotaCiudad` cites the
project's own page for the city, on the advisor's instruction, and the text
states the extraction as undated — a limitation to write down rather than to
hide.

---

## The rest of the bundle, for completeness

Delivered, not part of the thirteen, and here so that the list is the whole
delivery and not the convenient part of it.

| Layer | Status | What the delivery says |
|---|---|---|
| `lines/Señalizacion_Horizontal` | delivered, blocked on 2015 | Map book, `2. Señalización_Horizontal`. ArcGIS lineage from a `2017_DEM.shp`. Cited, along with the other two, under `SenalizacionSemaforizacionPMT`. |
| `lines/Señalizacion_Horizontal_ZonasEscolares` | delivered, blocked on 2015 | Map book, `3. Señalización_Horizontal_ZonasEscolares`, from a `2017_ZE.shp`. Same. |
| `areas/luminarias_upz` | delivered, undeclared | Built under a `DatosTematicos\UAESP\Datos\SHP` folder: the **Unidad Administrativa Especial de Servicios Públicos**, the entity responsible for public lighting. |
| `areas/indiceseguridadnocturna` | delivered, undeclared | Built under `SDM\PGI\Entrega_IDECA_2019\Safetipin`, title `Índice_Seguridad_Upz_2019`. An **SDM delivery to IDECA**, from **Safetipin** data, 2019. The clearest trail in the whole bundle, on a layer no variable reads. |
| `lines/Líneas de deseo Matriz Origen Destino` | retired | Built on someone's personal laptop, under a `Documents\Shapes\Ciclistas` folder. No institution anywhere. It is a 9.6 % sample of the 2019 survey, so `EncuestasMovilidad` covers what it contains, and no run reads it. |

---

## The assignment, and where it belongs

**One key per layer.** Thirteen were added to `references.bib` on 2026-09-22.
Eleven are catalogue entries of Datos Abiertos Bogotá, which is the answer to
where the bundle came from: the layers were downloaded from the city's open data
portal and were not produced for this study. The other two are IDECA and
OpenStreetMap. Only the arterial layer takes two keys, and only because it is a
join of two sources.

| Layer | Citation key | Publisher the entry names |
|---|---|---|
| `areas/andenes_x_localidad` | `AndenBogotaDC` | Instituto de Desarrollo Urbano |
| `areas/calzada_x_localidad` | `CalzadaBogotaDC` | Instituto de Desarrollo Urbano |
| `areas/puentes` | `PuenteBogotaDC` | Instituto de Desarrollo Urbano |
| `lines/ciclo_lines` | `CiclorrutaBogotaDC` | Instituto de Desarrollo Urbano |
| `areas/avenidas_corregidas` | `MallaVialArterial` + `DecretoPOTBogota` | IDECA, custodians SDM, IDU and Catastro — **see below** |
| `areas/parques_urb` | `ParquesPOTBogota` | Secretaría Distrital de Planeación — **to confirm** |
| `points/Paraderos_SITP` | `ParaderosSITPBogota` | Secretaría Distrital de Movilidad |
| `points/Red_Semaforica` | `RedSemaforicaBogota` | Secretaría Distrital de Movilidad |
| `points/camaras_salvavidas_bogota` | `CamarasSalvavidasBogota` | Secretaría Distrital de Movilidad |
| `points/estacion_localidad` | `EstacionesTroncalesTRANSMILENIO` | Empresa de Transporte del Tercer Milenio |
| `points/arbolado_urbano` | `ArboladoUrbanoBogota` | Jardín Botánico José Celestino Mutis |
| `points/crossings` | `OSMBogotaCiudad` | OpenStreetMap, relation 7426387 |
| `points/Señalizacion_Vertical` | `SenalizacionSemaforizacionPMT` | SDM map book |
| `lines/Señalizacion_Horizontal` | `SenalizacionSemaforizacionPMT` | same, and delivered without stock |
| `lines/Señalizacion_Horizontal_ZonasEscolares` | `SenalizacionSemaforizacionPMT` | same, and delivered without stock |
| `areas/luminarias_upz`, `areas/indiceseguridadnocturna` | — | only if either is ever declared |

**Every layer the models read now has a key.** One entry covers the three
signage series at once — the map book's *Señalización, Semaforización y PMT*
page — including the two that carry no stock and are not measured.

**The four IDU entries confirm the nomenclature lead.** `Cal*`, `Pue*`, `Cic*`
and the `CIV` code all belong to the road inventory the Instituto de Desarrollo
Urbano publishes, which is what group C's column names pointed at. That part of
the guess held.

### The arterial layer rests on two sources, and both are cited

`MallaVialArterial` was repointed on 2026-09-22 to IDECA's
**`Malla Vial Integral. Bogotá D.C.`**, and that is the right resource: its own
description lists *malla vial arterial principal* and *arterial complementaria*
among the classifications it carries, and names the custodians as the joint work
of the Secretaría Distrital de Movilidad, the Instituto de Desarrollo Urbano and
Catastro Distrital. The first six columns of the delivered layer —
`CalFuncion`, `CalTSuperf`, `CalCodigo`, `CalCIV`, `CalAncho`, `CalLongitu` —
are that inventory's own attributes.

**But the file is a join of two sources, and the column list shows it.** It
carries `SHAPE_Leng` and `SHAPE_Area` twice, the second pair renamed
`SHAPE_Le_1` and `SHAPE_Ar_1`, which is what happens when two feature classes
each bringing its own shape fields are joined. The second block —
`PERFIL_TIP`, `CLASIFICAC`, `FUNCIONALI`, `ACTO_ADMIN`, `NORMATIVA_`,
`FECHA_ACTO` — is not the road inventory but the POT's arterial declaration,
stamped `Decreto 555 del 29 de diciembre de 2021` on all 33,015 records.

So the geometry comes from the Malla Vial Integral and the classification that
selects the arterial subset comes from the decree, which is what the folder name
`avenidas_corregidas` was recording all along. **Chapter 3 cites both**,
`MallaVialArterial` and `DecretoPOTBogota`, and both are already in the file.

That the layer is the arterial network and not another one is settled by the
data: `PERFIL_TIP` is `A-0`, `A-1`, `A-2`, `A-3` or `A-3E` on 32,224 of the
33,015 records, with `RP`, `RS` and `RT` on the rural remainder; `FUNCIONALI`
takes only `Arterial de Integración Regional` and `Rural de Integración
Regional`; and `NOMBRE` holds 592 corridors led by Avenida Caracas, Avenida
Boyacá and Avenida Ciudad de Quito.

### Two caveats to carry into chapter 3

**`OSMBogotaCiudad` cites the project, not the extraction.** The entry is
OpenStreetMap relation 7426387, the city boundary object, dated 2026-09-01 —
which is when the entry was made and not when the crossings were extracted. That
date is not recorded anywhere and cannot be recovered, so the sentence that
introduces the variable says the extraction is undated. This is the advisor's
instruction: cite the project's own page rather than chase a per-layer origin.

**`ParquesPOTBogota` describes a POT product and the layer looks pre-POT.** The
delivered file is keyed on 112 UPZ codes, the unit Decreto 555 replaced with the
UPL, and carries an `ESTRATO` column of 1 to 6 plus `Rural`; unlike the arterial
layer it stamps the decree nowhere. Its 5,291 features are typed `PARQUE
VECINAL` (3,477), `PARQUE DE BOLSILLO` (1,653), `PARQUE ZONAL` (91), `PARQUE
METROPOLITANO` (35), `ESCENARIO DEPORTIVO` (14) and two `PROPUESTO` categories
(21), which is a planning hierarchy and does fit. Comparing the feature count
against the portal's would settle it in a minute. It is recorded rather than
chased because the advisor's position is that a per-layer provenance does not
have to be pinned down, and this is the one row where the entry and the file
disagree about a date rather than about what the layer is.

The entry is the Secretaría Distrital de Planeación's parks layer of the POT,
whose abstract opens *"En el marco del Decreto 555 de 2021"*. The delivered
layer does not look like a POT product:

- it is keyed on **112 UPZ codes**, the unit the POT of 2021 replaced with the
  UPL, and it carries an `ESTRATO` column with values 1 to 6 and `Rural`;
- unlike `avenidas_corregidas`, which stamps `NORMATIVA_`, `ACTO_ADMIN` and
  `FECHA_ACTO` on every record, it carries no trace of the decree at all;
- its 5,291 features are typed `PARQUE VECINAL` (3,477), `PARQUE DE BOLSILLO`
  (1,653), `PARQUE ZONAL` (91), `PARQUE METROPOLITANO` (35), `ESCENARIO
  DEPORTIVO` (14) and two `PROPUESTO` categories (21).

That typology is the IDRD's park hierarchy and the `PROPUESTO` categories do
point at a planning layer, so the entry is not obviously wrong — but UPZ and
estrato are pre-POT, and the question is settled by comparing the feature count
against whatever the portal's dataset reports, not by the abstract.

### The field that makes this stick

A markdown table drifts from the code the moment either changes. The place this
belongs is the declaration:

```python
source_citation: str  # the references.bib key of the layer's published source
```

on `StaticPredictor`, beside `source_layer` and `source_file`, validated in
`__post_init__` like every other field. A layer declared without one then
**fails at import**, before any measurement runs, rather than reaching chapter 3
as a variable nobody can cite.

Once it exists, the exported data dictionary carries the key alongside
`SOURCE_LAYER` and `SOURCE_FILE`, and the table of sources in chapter 3 is
generated from the declaration like every other table that names the variables.
The document and the pipeline then cannot disagree about where the data came
from, which is the same reason `label_es` lives in the declaration and not in a
lookup kept somewhere else.

**The field is not added until the keys exist**, because a required field with
nothing to put in it either blocks every run or gets a placeholder, and a
placeholder that says nothing is worse than a gap that is written down.

---

## How this was established

Every claim above is read off the delivered files: the ESRI `.shp.xml` and
QGIS `.qmd` sidecars, the ArcGIS lineage strings, the source paths, the
projection definitions and the attribute columns.

**A path or a column name is a lead, not a fact.** An account name ending in
`jbb` is very probably the Jardín Botánico and `CalCIV` is very probably the
Malla Vial, but neither file says so, and the study's own rule is that a name is
never evidence of what something holds. Group A was established from the files;
groups B and C were where to look, and the portal settled them.

**The machine paths are quoted without their machines.** The ESRI metadata keeps
the full path of the computer each layer was built on, and those paths carry
officials' names, equipment names and one internal address. This repository is
public. What proves an origin is the institution and the folder — `SDM`,
`UAESP`, `LIBRO DE MAPAS`, `Entrega_IDECA_2019` — so that is what is quoted, and
the rest is left in the delivery where it belongs.
