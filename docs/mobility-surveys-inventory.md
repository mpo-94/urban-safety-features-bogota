# The mobility surveys, year by year

What the four delivered surveys actually contain, measured rather than read off
the column names. It exists because the exposure of the study will be built from
them, and because that work is split across sessions: this is what the next one
starts from.

**Scope of this pass.** Structure only — files, columns, mode labels, expansion
factors, zone keys, the share of trips that begin and end in the same zone, and
which days each survey covers. No geometry was built, nothing was declared in
`config.py`, and no result here has been through a pipeline check. Every figure
was computed from the delivered file in the session of 2026-09-05.

**What the study needs from them.** Four modes — on foot, bicycle, motorcycle and
car — as **trips per day apportioned to each UPL**, for 2011, 2015, 2019 and 2023.
The pipeline currently measures one of those sixteen combinations, from a
delivered desire-lines layer that these surveys replace.

---

## 1. The delivery in one table

| | 2011 | 2015 | 2019 | 2023 |
|---|---|---|---|---|
| Trip file | `Mod_D_VIAJES2_BaseImputacion_Definitiva` | `VIAJES_ANONIMIZADOS.csv` | `ViajesEODH2019.csv` | `d. Modulo viajes.csv` |
| Format | Access `.accdb` | CSV `;` utf-8 | CSV `;` utf-8 | CSV `;` cp1252 |
| Records | 122,361 | 147,251 | 134,497 | 100,174 |
| Columns | 34 | 33 | 36 | 47 |
| Mode column | `Modo_Principal` | `ID_MEDIO_PREDOMINANTE` | `modo_principal` | `modo_principal_agrupado` |
| Mode as | label | numeric code | label | label |
| Weight | `F_EXP` | **unresolved**, four candidates | `f_exp` | `fexp_vj` |
| Expanded trips/day | 17,611,061 | ~17.25 M (weekday) | 18,996,286 | 16,390,908 |
| Origin/destination zone | `ZAT_ORIG` / `ZAT_DEST` | `ZAT_ORIGEN` / `ZAT_DESTINO` | `zat_origen` / `zat_destino` | `zat_ori` / `zat_des` |
| Zone nulls (origin) | 21,515 (17.6 %) | 43 (0.03 %) | 7,134 (5.3 %) | 0 |
| UPL in the trip record | no | no | no | **yes**, `upl_ori` / `upl_des` |
| Endpoint coordinates | no | **yes**, lat/lon | no | no |
| Zoning shapefile | **none delivered** | `ZATs_2012_MAG`, 948 zones | `ZAT` 1,141 + `UTAM` 141 | `ZAT2023` 1,215 + `UTAM2023` 142 |
| Saturday | separate database, 4,035 records | `DIA_NOHABIL`, 17,730 records | `p32_sabado` flag, 13,436 records | surveyed, 2,876 households |

The exact paths are in `docs/data-layout.md`. Everything else published alongside
— the EMME model of 2011, the intercept surveys, the reports, the forms — is out
of scope.

---

## 2. The four modes, year by year

The four the study wants are on foot, bicycle, motorcycle and car, and they map
onto four of the actor types the casualty matrix already uses: `PEDESTRIAN`,
`BICYCLE`, `MOTORCYCLE`, `CAR`. **That is the condition for a rate to mean
anything** — exposure has to be counted in the same category the casualties are.

Every year labels them differently, so the mapping is per-year data against one
shared vocabulary. Trips per day, expanded, weekday only.

| Actor type | 2011 | 2015 | 2019 | 2023 |
|---|---|---|---|---|
| `PEDESTRIAN` | `Pie` — 8,136,778 | code 13 `PEATON` — 5,576,943 | `A pie` — 6,941,798 | `A PIE > 15 MIN` + `A PIE <15 MIN` — 6,098,788 |
| `BICYCLE` | `Bicicleta` — 611,473 | code 10 `BICICLETA` — 846,727 | `Bicicleta` — 1,177,868 | `BICICLETA` — 1,115,685 |
| `MOTORCYCLE` | `Moto` — 411,095 | code 7 `MOTO` — 832,786 | `Moto` — 915,314 | `MOTO` — 1,035,329 |
| `CAR` | `Privado` — 1,818,802 | code 6 `AUTO` — 1,831,397 | `Auto` — 2,291,877 | `AUTO` — 1,932,349 |

**All four modes exist in all four years.** The worry that 2011 might have no
walking came from its eight aggregated EMME matrices, which name only bicycle,
motorcycle, public transport and private vehicle. The household database does not
have that gap: `Pie` is its largest mode by far.

Three things about the mapping that are decisions and not lookups:

- **2023 splits walking in two**, over and under fifteen minutes, and both are
  walking. Adding them is the obvious reading and it is still a choice, because a
  study could reasonably exclude the very short trips.
- **Bicycle includes the motorised bicycle** in 2011 (codes 18 and 19 of
  `Aux_Modos`) and in 2015 (`BICICLETA, BICICLETA CON MOTOR`). 2023 lists
  `Bicicleta con motor como conductor` separately, 341 records, so there it is a
  choice rather than an inheritance.
- **Car is driver and passenger together** everywhere. In 2011 `Privado`
  aggregates codes 22 and 23; in 2023 `AUTO` covers `Vehículo privado como
  conductor` and `como pasajero`, plus `Auto compartido` and `Auto alquilado`.

The mode taxonomies are not otherwise comparable across years. 2019 has sixteen
labels and 2011 twelve; TransMilenio, SITP and the feeder services are split
differently in every one of them. That does not matter for the four the study
wants, and it would matter a great deal for any fifth.

---

## 3. Intra-zonal trips: the finding that changes the design

A trip whose origin and destination are the same zone has **no desire line**: one
centroid, zero length. The decision already taken is to assign such a trip whole
to the units containing that zone, apportioned by area rather than given to the
majority unit, so that intra-zonal and inter-zonal trips are governed by one rule
instead of two.

This pass measured how much rides on that decision. Share of expanded trips whose
origin and destination fall in the same ZAT, weekday:

| Actor type | 2011 | 2015 | 2019 | 2023 |
|---|---:|---:|---:|---:|
| `PEDESTRIAN` | 33.1 % | 28.3 % | 25.5 % | 39.3 % / 21.6 % |
| `BICYCLE` | 18.8 % | 21.7 % | 9.3 % | 6.0 % |
| `MOTORCYCLE` | 9.4 % | 5.8 % | 2.5 % | 2.3 % |
| `CAR` | 9.9 % | 5.2 % | 3.6 % | 3.6 % |

The two figures for 2023 pedestrians are the under-fifteen-minute and
over-fifteen-minute categories, in that order.

**Between a fifth and two fifths of all walking is intra-zonal in every year.**
Dropping those trips would not be a small loss of precision: it would remove a
quarter to a third of pedestrian exposure, systematically, in exactly the mode
whose casualties this study is most concerned with. It would also bias the result
by place, since a unit made of large zones would lose more than one made of small
ones.

The same argument holds with less force for bicycles, and is nearly irrelevant
for cars and motorcycles.

---

## 4. Days of the week

The decision taken is to count typical weekday and Saturday **separately**, as a
`DAY_TYPE` dimension of the exposure table, and to decide later whether to
average them or drop Saturday. Every year distinguishes the two, and no two do it
the same way:

- **2011 — two separate databases.** `DiaTipico` with 122,361 trip records and
  `DiaSabado` with 4,035. Different samples of different households.
- **2015 — a flag on the record.** `DIA_HABIL` on 129,521 records and
  `DIA_NOHABIL` on 17,730. There is also a peak/off-peak split for each.
- **2019 — day-of-week flags on the trip.** `p32_lunes` to `p32_domingo` say on
  which days the reported trip is made: Saturday on 13,436 records, Sunday on
  8,349. **This is not the same measurement as the other three.** It says a
  weekday-reported trip also happens on Saturdays; it does not report a Saturday
  the respondent lived through.
- **2023 — the survey ran on all seven days.** Household interview dates run from
  2023-03-29 to 2023-10-20, with 2,876 households on Saturdays and 2,990 on
  Sundays. The day type has to be derived by joining the trips to the household's
  `fecha`, and the technical sheet has to say whether the trips reported are for
  the interview day or the day before.

**2011's Saturday is too thin to carry a UPL-level estimate and should be
expected to fail.** Its 4,035 records expand to 14,022,328 trips, so one record
stands for roughly 3,500 trips; the 72 bicycle records expand to 310,079. Spread
over 30 units and four modes that is about 34 records per cell before any zone
apportionment. The number will exist and it will not mean anything, and the run
should say so rather than publishing it quietly.

---

## 5. What is unresolved, per year

### 2015 — which column is the expansion factor

Four candidates, and the file cannot settle it. Weekday sums:

| Column | Weekday sum | Non-weekday sum |
|---|---:|---:|
| `PONDERADOR_CALIBRADO` | 14,358,944 | 13,076,793 |
| `PONDERADOR_CALIBRADO_VIAJES` | 17,251,733 | 15,730,551 |
| `FE_TOTAL` | 20,074,158 | 17,898,664 |
| `FACTOR_AJUSTE` | 113,157 over the whole file | — |

`PONDERADOR_CALIBRADO_VIAJES` lands between the 2011 figure of 17.6 M and the
2019 figure of 19.0 M, which is what a plausible 2015 daily total looks like. That
is circumstantial and not evidence. **`Tomo VII_BBDD_EODH_V2.pdf` in the same
delivery documents the database and has to be read before this is declared.** The
same document should say whether the non-weekday sum is a Saturday, a Sunday, or
both together, which the flag name does not distinguish.

### 2011 — no zoning was delivered

The trips carry `ZAT_ORIG` and `ZAT_DEST` over 912 distinct zones and there is no
shapefile anywhere in the 2011 folder. The 2015 delivery carries
`ZATs_2012_MAG` with 948 zones, and its name suggests the zoning the 2011 model
used. **Whether the 2011 codes fall inside that set has to be shown and not
assumed**, and if they do not, 2011 has no geometry at all.

`ZAT_ORIG` is also null on 21,515 records, 17.6 % of them — by far the worst zone
coverage of the four years, and enough to matter.

### 2023 — the delivered desire lines carry a tenth of the trips

The layer the pipeline uses today reports **113,269.31 bicycle trips per day**
over its 181 lines. The 2023 survey expands to **1,115,685 bicycle trips per
day**. The delivered lines therefore carry about **10 % of the bicycle travel the
survey measured**.

That is the strongest evidence yet on D35's open question — what the 181 lines
were a selection of. A tenth of the trips concentrated in 181 origin-destination
pairs is what selecting the largest pairs looks like, and if that is what
happened, the current exposure variable measures principal corridors and not
exposure. **It is not proof.** Confirming it means matching the 181 pairs against
the survey's own pairs and checking whether they are the largest ones, which is
work for the session that builds 2023.

It also means the validation this session hoped for is not a simple equality. Our
construction from the survey should reproduce the survey's total, not the layer's,
and the comparison against the layer is a diagnosis of what the layer was.

### All years — which day the expansion factor expands to

The current pipeline's check on the delivered layer — weekly over daily between 1
and 7 — observes 4.737 to 5.545, which says the daily factor there expands to a
**working day**. Whether each survey's own factor does the same has to be resolved
by arithmetic per year, not inherited.

---

## 6. Traps found in this pass

Recorded because each of them would have produced a wrong number silently, and
because they are the reason this pass exists.

- **2015's `.xls` lookup tables are not Excel files.** `MEDIO_PREDOMINANTE.xls`
  and its two dozen siblings are semicolon-separated text with a `.xls`
  extension. `pandas.read_excel` refuses them; `read_csv` reads them.
- **2015's mode code is not the code the lookup is keyed on.**
  `ID_MEDIO_PREDOMINANTE` holds the `PREDOMINANCIA` column of
  `MEDIO_PREDOMINANTE.xls`, not its `CODIGO` column — and `CODIGO` holds
  space-separated lists like `3 4 5 6`. Joining on the obvious column matches
  nothing.
- **2023's numbers are text.** `fexp_vj` arrives as `6,2 `, with a comma decimal
  separator and a trailing space, so it parses as an object column and sums to
  zero without complaint. Several other numeric columns are wrapped in spaces,
  and three column *names* are too: ` hora_ini `, ` duracion_min `.
- **2023 is cp1252 and the other two CSVs are utf-8.** Reading 2023 as utf-8
  fails on an invalid continuation byte; reading it as utf-8 with
  `errors="replace"` would not.
- **2011's usable trip table is not the one named for trips.**
  `MOD_D_VIAJES_Tipico` has 100,846 rows, one column per stage, a single `ZAT`
  for the household and no origin or destination zone.
  `Mod_D_VIAJES2_BaseImputacion_Definitiva` has 122,361 rows and carries
  `Modo_Principal`, `ZAT_ORIG`, `ZAT_DEST` and `F_EXP`. The second is the one to
  read, and it holds more rows than the first because it includes imputed trips —
  which is itself a fact to declare rather than absorb.
- **The 2023 zoning is in a different CRS from every other zoning delivered.**
  `ZAT2023` is EPSG:3116; the 2015 and 2019 zonings and the study's own
  cartography are EPSG:4686.

---

## 7. Consequences for the design

**The exposure table goes long.** One row per unit, year, mode and day type, with
the quantities as columns — not wide over the mode as it is today. Four modes by
two day types by four years is 32 combinations, which as columns would be
unreadable; more importantly the table has to join to a casualty matrix keyed on
unit, year and actor type, and it has to be interpolated over the year across the
fourteen unmeasured ones. Both are natural in long form and awkward in wide.

**A `TRIPS_PER_DAY` column and a `DAY_TYPE` row beat a `TRIPS_PER_TYPICAL_WEEKDAY`
column.** Making the day a dimension removes the need to put it in a name.

**A missing combination is not a zero.** If a year has no usable Saturday — 2011
is the candidate — the rows must be absent or marked, never filled with zeros.
This is D10 applied to a dimension that is ragged by construction.

**One reader, four declarations.** The session that implements 2023 writes the
machinery: reading a declared survey, mapping its modes to the four actor types,
splitting by day type, building the lines between zone centroids, apportioning by
length share, and adding the intra-zonal trips by area share. The three sessions
after it add a declaration each and nothing else. If the second year needs a
second reader, the design was wrong and it is cheaper to notice then than at the
fourth.

**Interpolation will meet the ρ correction.** The four measured years sit in very
different places in the history of casualty recording: 2011 and 2015 before the
change, 2019 in the middle of the ramp, 2023 inside the reference window. That
does not invalidate an interpolation, and the final report will have to address
it. Noted here so it is not discovered during the interpolation session.
