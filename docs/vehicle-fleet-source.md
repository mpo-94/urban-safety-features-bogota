# The vehicle registry: what it holds, and why it is not a denominator

**Status: examined, declared, and outside the pipeline.** Nothing in `src/` reads these
files and nothing in the study is computed from them. This document exists so that the
final report can cite the source at all, because a deliverable cites from `docs/` and not
from a folder of `data/` that is never committed.

**Decided on 2026-09-29**: the registry enters the thesis as an examined source and not as
an input. My advisor has something planned with it outside the models as they stand, and
that is a different question from the one this pipeline answers.

Measured on 2026-10-06 from the files themselves, not read off the column names.

## What the delivery is

`data/incoming/parque automotor/`, nine files and one notebook. The one that matters is
**`CRECIMIENTO_DEL_PARQUE_AUTOMOTOR_RUNT2.0_20260810.csv`**, 15.1 MB, **191,293 rows and
nine columns**, published by the RUNT with a cut of **July 2026**.

| Column | Distinct | What it holds |
|---|---:|---|
| `NOMBRE_DEPARTAMENTO` | 32 | the department |
| `NOMBRE_MUNICIPIO` | 288 | **the municipality of registration**, which is the whole problem |
| `NOMBRE_SERVICIO` | 5 | particular, public, official, «no registra», others |
| `ESTADO_DEL_VEHICULO` | 2 | active or inconsistent |
| `NOMBRE_DE_LA_CLASE` | 98 | the vehicle class |
| `FECHA DE REGISTRO` | 125 | the year of registration, 1900 to 2026 |
| `CANTIDAD` | 3,591 | the count the row carries |

It is a count table and not a record per vehicle: a row is a combination of the other
eight fields with its total in `CANTIDAD`.

The other files are my advisor's derivations, built in `parque_automotor_bogota.ipynb`
(corrected on 2026-10-24: this document first called them mine). They carry what the raw
extract does not: `bogota_perfil_edad.csv` gives the cohorts by year of registration with a
Weibull survival curve, `bogota_serie_2000_2026.csv` separates the registered fleet from the
circulating one and gives its mean age, `bogota_tasas_motorizacion.csv` holds an assumed
population and a rate per thousand for nineteen municipalities, and
`bogota_soacha_escenarios_2000_2026.csv` adds Soacha four ways. None of the assumptions has a
published source yet.

**`tools/parque_automotor.py` rebuilds every derived column from the raw extract** with the
parameters the notebook declares, and they match to rounding: the cohorts exactly, the survival
and the stocks within 10⁻¹⁰. Two things the rebuild found. The Bogotá row of the rates file
counts one light vehicle more than the series, because it keeps the registration year 1900, the
extract's code for no year, which the series drops. And the scenario file keeps a single D: the
notebook names both of its D scenarios, ψ = 0.30 and ψ = 0.50, with the same letter, so the
second overwrites the first and the file holds ψ = 0.50. The tool rebuilds both.

## What it says about Bogotá

**2,797,684 vehicles registered in Bogotá**, of which **2,790,629 are active** and 7,055
are marked inconsistent. The twelve largest classes of the ninety-eight, over the active
ones:

| Class | |
|---|---:|
| Automóvil | 1,361,376 |
| Camioneta | 596,071 |
| **Motocicleta** | **515,400** |
| Campero | 256,572 |
| Camión | 22,252 |
| Bus | 16,788 |
| Microbús | 8,494 |
| Buseta | 2,868 |
| Cuatrimoto | 2,504 |
| Motocarro | 1,838 |
| Volqueta | 1,625 |
| Tractocamión | 705 |

By service: 2,602,935 particular, 116,149 public, 76,095 official, 2,453 «no registra» and
52 others.

**Its classes almost trace the study's six actor types**, which is exactly what makes it
look like the denominator the motorised modes are missing.

## Why it cannot be that denominator

Two reasons, and they are independent: fixing either one would leave the other standing.

### The granularity is the municipality

There is no field below `NOMBRE_MUNICIPIO`, so there is no way down to the thirty UPL. The
study's unit is the UPL and every exposure it uses is stated on it; a quantity stated on
the whole city cannot be a denominator for a model whose variation is between units.

### The municipality of registration is not the municipality of circulation

This is the one that would survive even a finer geography, and the extract shows it
plainly. The ten municipalities with the most registered vehicles:

| Municipality | Registered |
|---|---:|
| Bogotá | 2,797,684 |
| **Envigado** | **901,406** |
| Cali | 851,148 |
| Sabaneta | 799,893 |
| **Funza** | **746,691** |
| Girón | 511,691 |
| Medellín | 422,455 |
| Soacha | 408,405 |
| Florida | 303,091 |
| Manizales | 298,078 |

**Envigado registers more vehicles than Cali**, and Envigado has of the order of two
hundred thousand inhabitants against Cali's two million. Medellín, the second city of the
country, sits below Envigado, Sabaneta and Funza, three of its neighbours or of Bogotá's.

The rate makes it unarguable. From `bogota_tasas_motorizacion.csv`, which carries each
municipality's population beside its fleet:

| Municipality | Population | Motorcycles | Per 1,000 |
|---|---:|---:|---:|
| **Funza** | 95,000 | 530,291 | **5,582** |
| Madrid | 100,000 | 178,890 | 1,789 |
| Tenjo | 22,000 | 35,241 | 1,602 |
| El Rosal | 25,000 | 39,152 | 1,566 |
| Mosquera | 115,000 | 120,317 | 1,046 |
| Bogotá | 8,000,000 | 474,064 | 59 |

**Funza has 5,582 motorcycles per thousand inhabitants**, which is not a city where
everyone owns five motorcycles: it is a registration address. The file's own
`motos_local` and `motos_exceso` columns split the two, which is Mateo's reading of the
same defect.

## What it is good for

**Context of motorisation, not a denominator.** `bogota_serie_2000_2026.csv` separates the
registered fleet from the circulating one with an attrition model and gives a mean age, and
that is a legitimate thing to cite when the final report describes how the city motorised
over the study period. It is not a quantity any model divides by. Since 2026-10-24 the annex
book shows the extract and the four derived files in its chapter on population and the vehicle
fleet, with the figures of `tools/parque_automotor.py`.

## Corrected here, because it was wrong where it was first written

Section 0j of `deliverables/plan.md` recorded, on 2026-09-29, that «Envigado tiene 901 406
vehículos y Sabaneta 799 893, **los dos más que Cali**, que tiene 851 148». Measured:
Envigado does exceed Cali, **Sabaneta does not** — 799,893 against 851,148. The point the
sentence was making survives and is in fact stronger with Funza, which the sentence did not
use: a municipality of ninety-five thousand people registering three quarters of a million
vehicles.

The class counts recorded there are also the totals including the inconsistent rows, where
the ones above are the active ones. The difference is 7,055 vehicles over the city, which
changes nothing and is stated so that two documents do not disagree without a reason.

## What has to happen before this is cited

Nothing further: this document is what a deliverable cites. **`docs/data-layout.md`
describes where the files live**, which it did not until 2026-10-06. If the files move, both
documents move in the same commit.
