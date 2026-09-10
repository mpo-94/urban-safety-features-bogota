# What `data/` holds, and where

`data/` is not distributed with this repository and never will be: the crash
records and part of the cartography are not mine to redistribute. That makes this
file the only record of what the pipeline needs in order to run, and of where each
file has to sit for it to be found.

**It is written against `src/config.py` and has to stay that way.** Every path
below is built from a root declared at the top of that file, and the run reports
loudly when a declared file is not on disk. If the two ever disagree, the code is
right and this document is stale.

---

## The rule: one root per role

Data is filed by **the role it plays in the study**, not by its format and not by
the shape of the delivery it arrived in. The roles are the study's own vocabulary,
and each has a root declared in `config.py`:

| Root | Folder | What it holds |
|---|---|---|
| `CARTOGRAPHY_DIR` | `data/geo/` | The territorial units and the two other divisions |
| `CASUALTIES_DIR` | `data/data_siniestros_bogota/` | The delivered crash records |
| `PREDICTORS_DIR` | `data/shp_properties_sorted/` | The urban layers the predictors are measured on |
| `EXPOSURE_DIR` | `data/shp_properties_sorted/` | The delivered desire lines, retired when 2019 landed and read by nothing |
| `SURVEYS_DIR` | `data/incoming/encuestas_movilidad/` | The mobility surveys the study's exposure is built from |
| `POPULATION_DIR` | `data/population/` | The demographic file the denominators come from |
| `INCOMING_DIR` | `data/incoming/` | Deliveries not yet merged into the sources above |
| `INTEGRATED_DIR` | `data/integrated/` | What the `integrate` route rebuilds from a delivery |

**`SURVEYS_DIR` points inside `data/incoming/` and that is not a contradiction.**
The rule below is that a delivery leaves `incoming/` once it has been inspected
and declared, and **all four now are**. They stay where they are for a different
reason than before: the four are one source with four vintages, they are read
across each other — 2011 declares the zoning that sits in the 2015 folder — and the
shape they finally want has not been decided. **Moving them is now a decision that
can be taken rather than one that is blocked**, and it should be taken with the
folder that will hold them in mind, not one year at a time.

**`PREDICTORS_DIR` and `EXPOSURE_DIR` point at the same folder today, and they are
still two roots.** The desire lines were delivered inside the bundle of predictor
layers, which is a fact about the delivery and not about the data: exposure is not
a predictor, it sits on the other side of a rate model, and a path that reached it
through the predictor root said the opposite of what the rest of the pipeline is
careful to say. Separating the declaration means the day the files move it is one
line of configuration. See D35 and D37.

`EXPOSURE_DIR` now reaches nothing the pipeline reads, because the one layer ever
declared under it was retired when the 2019 survey replaced it. The root stays for
the same reason it was separated in the first place: the day another exposure layer
arrives, it must not have to come in through the predictor root.

**`data/integrated/` is the one place under `data/` that is not raw.** The
`integrate` route writes it and every other route reads it as an input, which is
why it is here and not under `results/`. Nothing else in `data/` is ever written
by the pipeline.

---

## The tree

```
data/
├── data_siniestros_bogota/          casualties, as delivered
│   ├── MUERTO/MUERTO.shp                fatalities, one row per affected person
│   ├── LESIONADO/LESIONADO.shp          injuries, one row per affected person
│   ├── vehiculo.csv                     one row per party, casualties or not
│   └── accidente.csv, actor_vial.csv, causa.csv, via.csv, and .zip/.parquet copies
│                                        delivered, and read by nothing
├── geo/
│   ├── unidadplaneamientolocal/UnidadPlaneamientoLocal.shp    the 30 UPL: the study universe
│   ├── bog_upz/bog_upz.shp                                    111 UPZ, for the other scale
│   └── bog_loc_urbanarea/bog_loc_urbanarea.shp                localities, the legacy footprint
├── incoming/
│   ├── afectados_2024.csv                the updated 2024 extract, already integrated
│   └── encuestas_movilidad/              the five mobility survey publications, 2026-09-05,
│       └── <year>/                       1.8 GB, 546 files; all five years declared and read
├── integrated/                           written by `integrate`, read by everything else
│   ├── fatalities__2024_updated_extract.parquet
│   └── injuries__2024_updated_extract.parquet
├── population/
│   └── osb_demografia-poblacion-upl.csv  one row per unit, year, sex and age
└── shp_properties_sorted/                the predictor bundle, filed by geometry
    ├── areas/
    ├── lines/
    └── points/
```

### Why `shp_properties_sorted/` is filed by geometry

Because the code dispatches on it: `GEOMETRY_FOLDERS` turns a layer's declared
geometry into the folder it is read from, so a layer declared as an area and
delivered as points fails at the path rather than being measured wrongly. That
scheme earns its keep here and nowhere else in `data/`.

It is not a check on the file's contents. Both `predictors.py` and `exposure.py`
compare the geometry types actually present against the declaration when they read
a layer, so the folder is a path segment and the verification happens elsewhere.

---

## The layers inside the predictor bundle

Thirteen variables are measured over eleven layers. The declaration in
`config.STATIC_PREDICTORS` is authoritative; this is the arrangement on disk.

| Folder | Geometry | Read by |
|---|---|---|
| `areas/andenes_x_localidad` | area | sidewalk area share |
| `areas/avenidas_corregidas` | area | arterial road area share |
| `areas/calzada_x_localidad` | area | carriageway area share |
| `areas/parques_urb` | area | urban park area share |
| `areas/puentes` | area | bridge deck area share |
| `points/Paraderos_SITP` | point | SITP bus stop density |
| `points/Red_Semaforica` | point | signalised intersection density |
| `points/crossings` | point | pedestrian crossing density |
| `points/camaras_salvavidas_bogota` | point | speed camera density |
| `points/estacion_localidad` | point | TransMilenio station density |
| `points/arbolado_urbano` | point | the three tree variables |
| `lines/Líneas de deseo Matriz Origen Destino` | line | **nothing, since 2019 landed** — the retired exposure layer |

### Delivered and not read

Four line layers carry an annual series and are **delivered and pending**, waiting
on the year rather than on a way of being measured:
`lines/ciclo_lines`, `lines/Señalizacion_Horizontal`,
`lines/Señalizacion_Horizontal_ZonasEscolares` and `points/Señalizacion_Vertical`.

Two more are **delivered and not declared**, and are recorded in
`config.UNDECLARED_PREDICTOR_LAYERS` so that a later session finds a reason rather
than an unexplained folder. The `predictors` route prints them on every run and
says whether each is still on disk.

| Folder | What it holds | Why it is not a variable |
|---|---|---|
| `areas/luminarias_upz` | street lighting by lamp technology | keyed on the 111 UPZ, which do not nest inside the 30 units |
| `areas/indiceseguridadnocturna` | a night-time safety perception index | perceived safety is closer to an outcome than to a cause |

Both were moved into `areas/` on 2026-09-05. The bundle had put `luminarias_upz`
beside the geometry folders as a layer among them, and `indiceseguridadnocturna`
under a folder called `mean`, which is not a geometry but the measurement the
delivery implied for it. That hint is kept in the configuration record, where it
can be read, rather than in a folder name that contradicts the scheme the code
dispatches on.

---

## Adding data

**Put a new delivery in `data/incoming/`, in a folder of its own, and leave the
existing sources alone.** A delivery that overwrites a folder in place keeps every
route running and silently changes the numbers they produce, which is the one
failure that leaves nothing out of place to notice. The files move out of
`incoming/` once they have been inspected and declared.

Then declare it. Nothing is read that is not declared:

- a predictor layer goes in `config.STATIC_PREDICTORS`;
- a mobility survey goes in `config.MOBILITY_SURVEYS` — the procedure is
  `docs/adding-a-survey-year.md`, and it starts with inspection because every
  survey was commissioned by a different administration and catalogues its data
  its own way;
- a delivered exposure layer goes in `config.EXPOSURE_LAYERS` — the procedure is
  `docs/adding-an-exposure-layer.md`, and it starts with inspection because the
  first time round a column name lied;
- anything delivered and deliberately not read goes in
  `config.UNDECLARED_PREDICTOR_LAYERS` with the reason, so the folder is not a
  mystery later.

Update this file in the same commit as the move. `data/` is not in version
control, so nothing else can catch the two drifting apart.

---

## Known and provisional

**The mobility survey publications are in `incoming/`, and three of the four are
now read.** They are the four complete publications from the Alcaldía de Bogotá,
placed on 2026-09-05, replacing an earlier partial delivery. They replace the
single bicycle layer used for exposure until now, and their shape is not the
shape of what they replace: they hold **survey trip records and the zoning those
records are keyed on, and no desire lines at all.**

The desire lines the pipeline read before this were derived from material of
exactly this kind — each line runs between two zone centroids and its records
carry `zat_origen` and `zat_destin` — so the geometry is built rather than
declared. That stage now exists: `src/surveys.py` reads a declared survey and
`src/exposure.py` builds the lines and apportions them. See D38.

**Nine files are read across the four folders and nothing else is.**
`config.SURVEY_2023` names the trip module, the household module — which is where
its day type comes from, and only there — and the ZAT zoning. `config.SURVEY_2019`
names its trip module and its ZAT zoning, and needs nothing else: its day type is
the same for every record and its duration is derived from two columns of the trip
file. `config.SURVEY_2015` needs two as well, its trip file and its ZAT zoning:
its day type is a flag the delivery already wrote on every trip record and its
duration is derived from two columns of the same file. `config.SURVEY_2011` names
**three**: two Access databases, one per kind of day, and the 2015 folder's ZAT
zoning, which is its own. Everything else in the four publications is delivered and
not declared.

What each year holds for that purpose, out of everything published:

| Year | Household trip records | Zoning |
|---|---|---|
| 2011 | `120927_ConsultaEODH2011_DiaTipico (1).accdb` table `Mod_D_VIAJES2_BaseImputacion_Definitiva`, **and** `…_DiaSabado (1).accdb` table `Mod_D_VIAJES2_BaseImputacion_Definitiva_Sabado` **— both declared** | **none in its own folder**; it declares the 2015 folder's `ZATs_2012_MAG`, which is the 2011 survey's own zoning **— declared** |
| 2015 | `Base de Datos Completa/VIAJES_ANONIMIZADOS.csv`, 35 MB **— declared** | `ZATs/ZATs_2012_MAG.shp`, 948 features over 945 zones **— declared** |
| 2019 | `BD EODH2019 FINAL v14022020/Archivos CSV/ViajesEODH2019.csv`, 23 MB **— declared** | `Zonificación (shapefiles)/ZONAS/ZONAS/ZAT.shp` 1,141 **— declared**; `UTAM.shp` 141 |
| 2023 | `05_Base datos procesada/CSV/d. Modulo viajes.csv`, 59 MB **— declared** | `ZAT2023.shp` 1,215 **— declared**; `UTAM2023.shp` 142 |

**The 2015 zoning is 948 features and 945 zones, and the reader is told so.** Codes
794 and 806 arrive as two and three detached polygons, which the delivery's own
per-feature `AREA` column shows to be pieces of one zone rather than zones sharing
a number. `config.SURVEY_2015` declares `zone_delivered_in_parts`, and the pieces
are dissolved by code at read time. No other year declares it, and for them a
repeated code still stops the run.

**Six files of the 2015 delivery were read for verification and are read by
nothing.** `Documentos/Tomo IV_Indicadores_Fe de erratas_enero 2017.pdf` publishes
the per-mode totals of the working day (Tabla 43), of the Saturday (Tabla 119) and
the trips-per-household table (Tabla 59) the reconstruction is checked against, plus
the fifteen-minute walking splits. `Documentos/MATRICES EODH/matriz_habil.xlsx`,
`matriz_nohabil.xlsx`, `matriz_medio_habil.xlsx` and `matriz_medio_nohabil.xlsx` are
the published origin-destination matrices the reading reproduces to the last
decimal. `Documentos/FORMULARIO_DE_LA_ENCUESTA_2015.pdf` is the questionnaire that
settles which day the trips belong to. They are named here because the figures they
establish are quoted in `docs/design-decisions.md` and in section 15 of the
verification report, and a quoted figure whose source is not written down cannot be
checked later.

**`ENCUESTAS_ANONIMIZADO.csv` is deliberately not read**, and it is the 2015
counterpart of 2019's `Aux_Duración`. It was used once, to establish what
`DIA_NOHABIL` means — its interview dates, shifted back a day, reproduce the flag on
all 147,251 trip records and show that the day is a Saturday — and to establish what
the expansion factor expands to, from the household weights. Reading it in the
pipeline would be a second source for a day type the trip file already carries, and
it has a defect of its own: one household's row is displaced by a column, so its
interview date is unreadable.

2023 also reads `05_Base datos procesada/CSV/a. Modulo hogares.csv`, which the
table above does not list because it holds no trips. It is where the interview
date and the household expansion factor are, and therefore where the day type of
every trip comes from. A year's day-type source belongs in its declaration
alongside its trips, and this is the note that says why a second file appears
there. **2019 needs no such second file**, because it surveyed one kind of day and
every record carries it.

**The 2019 zoning folder is nested twice and that is how it was delivered.** The
path really is `Zonificación (shapefiles)/ZONAS/ZONAS/ZAT.shp`, with `ZONAS`
repeated, beside a `ZONAS.zip` holding the same thing. The folder name carries an
accented character, which matters on this platform: a shell that normalises it
differently will not find the directory, and the configuration builds the path
from `Path` components rather than from a string for that reason.

**Four files of the 2019 delivery were read for verification and are read by
nothing.** `Anexos/Anexo D - Valores absolutos de indicadores/03_Anexo D_Movilidad.xlsx`
holds the published per-mode and per-UTAM totals the reconstruction is checked
against, `01_Anexo D_Muestra.xlsx` and `02_Anexo D_Socioeconomicos.xlsx` the
sample and household universes, and `Formularios/190220_Módulo D_DPR (viajes).pdf`
is the questionnaire that settles which day the trips belong to. They are named
here because the figures they establish are quoted in `docs/design-decisions.md`
and in section 15 of the verification report, and a quoted figure whose source is
not written down cannot be checked later.

**`Aux_DuraciónEODH2019.csv` is deliberately not read.** It holds the survey's own
computed trip duration and it was used once, to verify that the pipeline's
derivation from the two clock columns reproduces it — which it does on 134,496 of
134,497 records. Reading it in the pipeline would be a second reader for a
quantity the trip file already carries, and it has a defect of its own: one trip
from 9:00 to 12:00 recorded as 81 minutes rather than 180.

Each year also has a Saturday or non-weekday counterpart, encoded a different way
in every one of them; `docs/mobility-surveys-inventory.md` has the detail.

Everything else published alongside — the EMME model of 2011, the intercept
surveys, the reports, the forms, the indicator annexes — is out of scope and
stays where it is.

**`docs/mobility-surveys-inventory.md` is what these files actually contain**,
measured rather than read off the column names: record counts, mode labels and
their trip totals, expansion factors, zone keys, the share of trips that never
leave one zone, and what each year leaves unresolved. It was written before any
of this was declared, and the session that declares a year starts from it.

Two things about the delivery belong here rather than there:

- **2011 carries no zoning in its own folder, and the file it borrows is its own.**
  Its trips name 913 distinct codes on the weekday and 607 on the Saturday and every
  one of them is in `ZATs_2012_MAG` — necessary, and not sufficient, because a file
  named for 2012 framing 2011 travel needed an argument. It has one: **chapter 2 of
  the 2011 delivery's own Tomo II is the zoning proposal**, built on Catastro
  Distrital's March 2011 cadastre, and that year's matrix training deck records the
  result as *"se pasó de tener 863 zonas a 945 zonas"* — the 945 codes the file
  carries. It is the 2011 survey's zoning, published with the following survey and
  named for the year it was published. The declaration points at the 2015 folder and
  says so.
- **2011 is two Access databases** where the others are one CSV, and the second one
  is not a duplicate: the weekday and the Saturday are separate samples of separate
  households in separate files. That is where the fourth year did not fit the
  shape, and it is why `MobilitySurvey.trips` is a tuple of sources. See
  `docs/implementing-2011.md`. **2005 is a third Access database**, and the one
  place a driver's spelling of a number mattered: it delivers a mode code as `13.0`
  where the delimited years deliver `13`.
- **`pyodbc` reads them** through the 64-bit Access ODBC driver installed on this
  machine, with the environment's 64-bit Python; a 32-bit driver would not have
  worked. **It is now in `requirements.txt`**, added in the commit that first read
  2011, as this document said it would be. The driver itself is not a Python package
  and cannot be: a machine without it can run the three delimited years and will
  stop with an ODBC error on 2011 and on 2005.
- **The fifth survey is 2005, and it is declared, read and implemented**, as of
  2026-09-10. It is under `data/` at
  `SURVEYS_DIR / "2005" / "Encuesta  de Movilidad 2005"` — note the two spaces in
  that folder name, which is how it arrived. Four files, which is everything the
  Alcaldía publishes: `Encuesta.mdb` (the microdata, Access, 57 MB),
  `Descripcion Encuesta.DOC` (the dictionary),
  `BM_58 STT VM Informe FinalVersion3.doc` (a later matrix-validation study, not the
  survey's results report) and `Presentacion Encuesta STT.ppt` (the results
  presentation).

  **The three Office files are legacy binary formats and were converted by hand into
  `convertidos/` beside them**, as `.docx`, `.pptx` and `.pdf`. The originals stay
  untouched: that folder is the record of what was delivered and the conversions are
  ours. [`implementing-2005.md`](implementing-2005.md) is that year's record: sections
  1 to 12 are the inspection pass that preceded the implementation and section 13 is
  what building it cost.

  **Two things it reads live outside its own folder**, which is the exception to how
  every other year is filed. Its zoning is not delivered with it: the pipeline builds
  one at run time from `geo/bog_upz/bog_upz.shp` and from the seventeen ring
  municipalities dissolved out of the **2015** delivery's zoning, written to no disk.
  And the figures its reading is controlled against are in the **2011** delivery's
  Tomo III, below.

  What was already under `data/` before that, and still matters, is the chapter that
  publishes 2005's figures second-hand: **chapter 5 of
  `2011/Encuesta de Movilidad 2011/120927_InformeFinal_TomoIII.pdf`**, titled
  *"Comparación de indicadores de las encuestas de movilidad 2005-2011"*. Those
  figures are declared in `config.PUBLISHED_2005` and the `interpolation` route
  compares this study's reading against them on every execution — 2005 and 2011 both,
  the second being the control on the control — so that document is a source the
  pipeline quotes and not only background reading. Paragraph 4.26 of Tomo II is the
  other one: it states the 9,689,027 daily trips that settled which of 2005's two
  expansion factors is the count-adjusted one.
- **The eight Emme matrices of `Matrices Finales/` are out of scope and are not a
  control**, which is worth stating because they look like one. The year's matrix
  training deck describes them as built from the intercept surveys and the traffic
  counts, corrected for double counting and adjusted in Emme, with the household
  survey contributing only the origin-destination pairs interception missed — and
  those re-expanded with the intercept factor, since *"la expansión de hogares no
  permite utilizar directamente los viajes de esa matriz"*. They are a different
  artefact from the one the pipeline rebuilds.
- **Six files of the 2011 delivery were read for verification and are read by
  nothing.** `120927_InformeFinal_Tomo I.pdf` publishes the two day totals, the two
  modal splits, the fifteen-minute split and the two household universes;
  `120927_InformeFinal_TomoII.pdf` carries the zoning chapter and the statement that
  the Saturday sample covers Bogotá only; `120927_InformeFinal_TomoIII.pdf` carries
  the imputation and the two expansion procedures; `Manual base de datos Encuesta de
  Hogares.pdf` is the field dictionary and says which trip module to read;
  `110719_Formulario_EM_Bogota 26 de julio.pdf` is the questionnaire, which states
  the reference day and the three-minute floor on walking; and `Ejemplos
  Capacitación/03_Ejemplo Capacitación Matrices_FE_Hogares.xlsx` is the worked
  example whose 1,434 private-vehicle peak records the reading reproduces with a
  bit-identical total. They are named here because figures they establish are quoted
  in `docs/design-decisions.md` and in section 15 of the verification report.

Each year also publishes its records twice, as CSV and as XLSX, and 2023 publishes
both a raw and a processed database. The table above names the one file per year
that is to be read; the others are duplicates and must not be read instead.

Where the files will finally live follows from all of that. Until then
`EXPOSURE_DIR` still points into the predictor bundle.

**The delivered desire-lines layer is no longer read, and its file must stay
where it is.** D35, section 13 of the verification report and
`deliverables/plan.md` all carry figures measured on it, so the delivery has to
remain reachable or those figures stop being reproducible — but the layer left
`config.EXPOSURE_LAYERS` when 2019 was implemented and no run touches it any more.

It was validated before it went, which is why it was kept this long: it is a 9.6 %
sample of the **2019** survey, and all 160 of its origin-destination pairs appear
among the pairs the pipeline builds from that survey, with none over-attributed.
`config.BICYCLE_DESIRE_LINES` still names the file so a quoted figure can be
recomputed by hand. See D38 and D35.

Because of that, `EXPOSURE_DIR` currently points at a folder nothing reads. It
stays declared: exposure is not a predictor, and the day another exposure layer
arrives it should not have to reach it through the predictor root.

**Eight `.DS_Store` files** are scattered through the delivered folders. They are
Finder artefacts from the machine the data was prepared on, they are read by
nothing, and they are left where they are because they came with the delivery.
