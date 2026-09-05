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
| `EXPOSURE_DIR` | `data/shp_properties_sorted/` | The delivered desire lines, now a reference and not the variable |
| `SURVEYS_DIR` | `data/incoming/encuestas_movilidad/` | The mobility surveys the study's exposure is built from |
| `POPULATION_DIR` | `data/population/` | The demographic file the denominators come from |
| `INCOMING_DIR` | `data/incoming/` | Deliveries not yet merged into the sources above |
| `INTEGRATED_DIR` | `data/integrated/` | What the `integrate` route rebuilds from a delivery |

**`SURVEYS_DIR` points inside `data/incoming/` and that is not a contradiction.**
The rule below is that a delivery leaves `incoming/` once it has been inspected
and declared, and 2023 now is both. It stays where it is because the other three
years are not, and moving one year of a four-year delivery out of the folder its
siblings sit in would file the same source two ways. The four move together, once
2011, 2015 and 2019 are declared and the shape they finally want is known.

**`PREDICTORS_DIR` and `EXPOSURE_DIR` point at the same folder today, and they are
still two roots.** The desire lines were delivered inside the bundle of predictor
layers, which is a fact about the delivery and not about the data: exposure is not
a predictor, it sits on the other side of a rate model, and a path that reached it
through the predictor root said the opposite of what the rest of the pipeline is
careful to say. Separating the declaration means the day the files move it is one
line of configuration. See D35 and D37.

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
│   └── encuestas_movilidad/              the four mobility survey publications, 2026-09-05,
│       └── <year>/                       inspected for shape only; 1.8 GB, 546 files
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
| `lines/Líneas de deseo Matriz Origen Destino` | line | **exposure**, not a predictor |

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
- an exposure layer goes in `config.EXPOSURE_LAYERS` — the procedure is
  `docs/adding-an-exposure-layer.md`, and it starts with inspection because the
  first time round a column name lied;
- anything delivered and deliberately not read goes in
  `config.UNDECLARED_PREDICTOR_LAYERS` with the reason, so the folder is not a
  mystery later.

Update this file in the same commit as the move. `data/` is not in version
control, so nothing else can catch the two drifting apart.

---

## Known and provisional

**The mobility survey publications are in `incoming/`, and 2023 of them is now
read.** They are the four complete publications from the Alcaldía de Bogotá,
placed on 2026-09-05, replacing an earlier partial delivery. They replace the
single bicycle layer used for exposure until now, and their shape is not the
shape of what they replace: they hold **survey trip records and the zoning those
records are keyed on, and no desire lines at all.**

The desire lines the pipeline read before this were derived from material of
exactly this kind — each line runs between two zone centroids and its records
carry `zat_origen` and `zat_destin` — so the geometry is built rather than
declared. That stage now exists: `src/surveys.py` reads a declared survey and
`src/exposure.py` builds the lines and apportions them. See D38.

**Three files of 2023 are read and nothing else in the four folders is.**
`config.SURVEY_2023` names the trip module, the household module — which is where
the day type comes from, and only there — and the ZAT zoning. Everything else in
the 2023 publication, and all of 2011, 2015 and 2019, is delivered and not yet
declared.

What each year holds for that purpose, out of everything published:

| Year | Household trip records | Zoning |
|---|---|---|
| 2011 | `120927_ConsultaEODH2011_DiaTipico (1).accdb`, table `Mod_D_VIAJES2_BaseImputacion_Definitiva` | **none delivered** |
| 2015 | `Base de Datos Completa/VIAJES_ANONIMIZADOS.csv`, 35 MB | `ZATs_2012_MAG.shp`, 948 zones |
| 2019 | `BD EODH2019 FINAL v14022020/Archivos CSV/ViajesEODH2019.csv`, 23 MB | `ZONAS/`, `ZAT.shp` 1,141 and `UTAM.shp` 141 |
| 2023 | `05_Base datos procesada/CSV/d. Modulo viajes.csv`, 59 MB **— declared** | `ZAT2023.shp` 1,215 **— declared**; `UTAM2023.shp` 142 |

2023 also reads `05_Base datos procesada/CSV/a. Modulo hogares.csv`, which the
table above does not list because it holds no trips. It is where the interview
date and the household expansion factor are, and therefore where the day type of
every trip comes from. A year's day-type source belongs in its declaration
alongside its trips, and this is the note that says why a second file appears
there.

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

- **2011 carries no zoning of any kind**, so its trips cannot become geometry
  from its own folder. Whether the 2015 zoning serves is an open question, not an
  assumption.
- **2011 is an Access database** where the others are CSV. `pyodbc` reads it
  through the 64-bit Access ODBC driver installed on this machine, with the
  environment's 64-bit Python. It is installed but **not yet in
  `requirements.txt`**, because nothing declared reads it yet; the commit that
  first reads 2011 adds it.

Each year also publishes its records twice, as CSV and as XLSX, and 2023 publishes
both a raw and a processed database. The table above names the one file per year
that is to be read; the others are duplicates and must not be read instead.

Where the files will finally live follows from all of that. Until then
`EXPOSURE_DIR` still points into the predictor bundle.

**The delivered desire-lines layer is quoted in finished work** — D35, section 13
of the verification report, and `deliverables/plan.md` all carry figures measured
on it. It must not be overwritten or removed; the superseded delivery has to
remain reachable or those figures stop being reproducible.

It is still read on every `exposure` run for exactly that reason, and its table
is now written as `reference__delivered_desire_lines_by_unit.csv` rather than as
the analysis table. It also turned out to be worth keeping for a second reason:
it is a 9.6 % sample of the **2019** survey, which is how its year was finally
established. See D38.

**Eight `.DS_Store` files** are scattered through the delivered folders. They are
Finder artefacts from the machine the data was prepared on, they are read by
nothing, and they are left where they are because they came with the delivery.
