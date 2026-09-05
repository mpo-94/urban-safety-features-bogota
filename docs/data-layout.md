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
| `EXPOSURE_DIR` | `data/shp_properties_sorted/` | The layers travel exposure is measured on |
| `POPULATION_DIR` | `data/population/` | The demographic file the denominators come from |
| `INCOMING_DIR` | `data/incoming/` | Deliveries not yet merged into the sources above |
| `INTEGRATED_DIR` | `data/integrated/` | What the `integrate` route rebuilds from a delivery |

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
│   └── encuestas_movilidad/              mobility surveys 2011/2015/2019/2023, delivered
│       └── <year>/                       2026-09-05, inspected only for shape, not read
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

**The mobility survey delivery of 2026-09-05 is in `incoming/` and unread.** It
is meant to replace the single bicycle layer now used for exposure, and its shape
is not the shape of what it replaces. It holds **survey trip tables and the zoning
they are keyed on, and no desire lines at all**: a spreadsheet of trips per year
(`.xlsx` in 2015, 2019 and 2023; in 2011 a workbook plus eight aggregated matrices
in `.in` form, split by mode and by peak or off-peak), beside the ZAT or UTAM
polygons for that year. The desire lines the pipeline reads today were derived
from material of exactly this kind — each line runs between two zone centroids and
its records carry `zat_origen` and `zat_destin` — so the geometry would have to be
built here rather than declared.

Three things about it are already visible from the file listing alone and will
need answers:

- **The zoning changes between years.** `ZATs_2012_MAG` in 2011 and 2015 —
  byte-identical in both, same MD5 — then `ZONAS.zip` in 2019, then `ZAT2023` and
  `UTAM2023` in 2023. Trips are keyed on zones, and the zones are not the same set
  across the four years.
- **2011 may have no walking.** Its eight matrix files name four modes — bicycle,
  motorcycle, public transport and private vehicle — and none of them is on foot.
- **A technical sheet is filed under the wrong year.** The `2011/ZATs/` folder
  carries "Ficha Técnica de la Encuesta de Movilidad **2015**", and its shapefile
  is dated 2012. Either a misfile in the delivery or a reused zoning, and it has
  to be settled before any year label is trusted.

Where the files will finally live follows from all of that and is not decided.
Until then `EXPOSURE_DIR` still points into the predictor bundle.

**The current desire-lines layer is quoted in finished work** — D35, section 13 of
the verification report, and `deliverables/plan.md` all carry figures measured on
it. It must not be overwritten in place when the replacement is declared; the
superseded delivery has to remain reachable or those figures stop being
reproducible.

**Eight `.DS_Store` files** are scattered through the delivered folders. They are
Finder artefacts from the machine the data was prepared on, they are read by
nothing, and they are left where they are because they came with the delivery.
