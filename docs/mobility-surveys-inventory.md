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

**2023 and 2019 have since been built and are no longer structural notes.** They
are declared in `config.SURVEY_2023` and `config.SURVEY_2019`, read by
`src/surveys.py`, measured by `src/exposure.py` and checked on run
`run_20260908_014143`; the decisions are D38. What those passes resolved is marked
below where it lands, and the entries for 2011 and 2015 are unchanged and still
unverified. Several things this document listed as unresolved have been answered
and three of its statements turned out to be wrong, which is said in full in
section 5.

**2019 is the year that made this document's method pay for itself, twice over.**
Its own data dictionary calls the trip table's `fecha` column "Fecha del viaje",
and it is not: it is the date the interview was carried out, and the trips are
those of the day before. And the survey turns out to measure **one kind of day
only**, so the day-type dimension this document assumed all four years would
support is a property of 2023 and not of the series. Both are in section 5.

**What the study needs from them.** Four modes — on foot, bicycle, motorcycle and
car — as **trips per day apportioned to each UPL**, for 2011, 2015, 2019 and 2023.
That is sixteen combinations. **Eight of them are measured**, the four modes of
2023 and the four of 2019. The delivered desire-lines layer that used to stand in
for all of this turned out to be an incomplete 2019, bicycle only, and the 2019
session **retired it** — after checking that all 160 of its origin-destination
pairs appear among the pairs the pipeline builds from that survey, which they do.

---

## 1. The delivery in one table

| | 2011 | 2015 | 2019 | 2023 |
|---|---|---|---|---|
| Trip file | `Mod_D_VIAJES2_BaseImputacion_Definitiva` | `VIAJES_ANONIMIZADOS.csv` | `ViajesEODH2019.csv` | `d. Modulo viajes.csv` |
| Format | Access `.accdb` | CSV `;` utf-8 | CSV `;` utf-8, decimal point | CSV `;` cp1252, decimal comma |
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
| Saturday | separate database, 4,035 records | `DIA_NOHABIL`, 17,730 records | **none observed**; `p32_sabado` is declared recurrence, 13,436 records | surveyed, 2,876 households |
| Reference day | day before the interview | flag on the record | day before the interview, one typical day only | day before the interview |
| Trip duration | unresolved | `HORA_INICIO`/`HORA_FIN` as `HH:MM:SS` | derived from two clock columns held as fractions of a day | `duracion_min`, in minutes |

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
| `BICYCLE` | `Bicicleta` — 611,473 | code 10 `BICICLETA` — 846,727 | `Bicicleta` + `Bicitaxi` — 1,207,248 | `BICICLETA` — 1,115,685 |
| `MOTORCYCLE` | `Moto` — 411,095 | code 7 `MOTO` — 832,786 | `Moto` — 915,314 | `MOTO` — 1,035,329 |
| `CAR` | `Privado` — 1,818,802 | code 6 `AUTO` — 1,831,397 | `Auto` — 2,291,877 | `AUTO` — 1,932,349 |

**All four modes exist in all four years.** The worry that 2011 might have no
walking came from its eight aggregated EMME matrices, which name only bicycle,
motorcycle, public transport and private vehicle. The household database does not
have that gap: `Pie` is its largest mode by far.

Three things about the mapping that are decisions and not lookups. All three are
now taken, and D38 carries the reasoning:

- **2023 splits walking in two**, over and under fifteen minutes, and both are
  walking. Adding them is the obvious reading and it is still a choice, because a
  study could reasonably exclude the very short trips.
  *Decided: both are in.* The short ones are 2,059,528 trips a day of the
  6,098,788. Excluding them would leave 2023 at 4.04 M against 2019's 6.94 M, and
  **2,984,881 trips a day of 2019's walking — 43.0 % of it — last under fifteen
  minutes** once its durations are derived from the reported times. The gap would
  be the category and not the city.

  **That last figure corrects one this document carried.** It said 3,351,414 and
  48.3 %, computed before the duration rule existed and therefore without rounding
  to the minute; unrounded, `(0.302083333333333 − 0.291666666666667) × 1440` is
  14.999999999 and a tenth of the walking falls on the wrong side of the
  threshold. Rounded, the figure agrees with the survey's own: indicator IND_104
  implies 2,988,986 short walks, 43.1 %, a tenth of a point away. Nothing decided
  here changes — both halves are in either way — but the wrong number was quoted
  in D38 and is corrected there too.
- **Bicycle includes the motorised bicycle** in 2011 (codes 18 and 19 of
  `Aux_Modos`) and in 2015 (`BICICLETA, BICICLETA CON MOTOR`). 2023 lists
  `Bicicleta con motor como conductor` separately, 341 records, so there it is a
  choice rather than an inheritance.
  *Decided: it is in.* With the passenger category it is 364 records and 71,277
  trips a day, 6.39 % of 2023's bicycle travel; 2019 separates it too, at 1.15 %.
  Two arguments agree: 2011 and 2015 cannot offer the narrower category at all,
  and neither can the numerator — the crash source has only `BICICLETA` and
  `BICITAXI`, so a rider hurt on a motorised bicycle is recorded as a cyclist or
  a motorcyclist with no way to tell which.
- **Car is driver and passenger together** everywhere. In 2011 `Privado`
  aggregates codes 22 and 23; in 2023 `AUTO` covers `Vehículo privado como
  conductor` and `como pasajero`, plus `Auto compartido` and `Auto alquilado`.
  *Unchanged: they stay together.*
- **The bicitaxi is in `BICYCLE`, and only 2019 poses the question.** It is a
  mode of its own there, 163 records and 29,379.85 trips a day, 2.43 % of what
  that year measures as cycling; 2023 has no such label at all.
  *Decided: it is in.* The reason is the numerator, not the survey: the crash
  source maps `BICITAXI` to `BICYCLE`, so a rider hurt on one is already counted
  as a cyclist, and a denominator that excluded them would divide those
  casualties by an exposure that does not contain them. The cost is that the
  category is not identical across the two measured years, which is why its
  weight is recorded separately in section 15 of the verification report — the
  effect of the decision can be quantified without re-running the year.
  The scooter, `Patineta`, is **not** in: 108 records and 13,503 trips a day, and
  the casualty source has no scooter category for it to be paired with.

**Public transport is not a fifth mode, and that is a decision too.** The
matrix's `PUBLIC_TRANSPORT` counts the occupants of a bus in a crash; the survey's
counts the passengers of a system. Pairing them would look like a rate. In the
declaration it sits in `modes_not_measured` rather than simply being left out, so
that a label in neither list stops the run instead of vanishing in a groupby.

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

*Built for 2023 and 2019, and the measured cost of the decision is larger than
the table above suggests.* Over the four modes together the intra-zonal trips are
**1,841,452 a day in 2023, 20.0 %** of what that survey measures, and **1,987,946
in 2019, 21.5 %**; they are apportioned by area share over the units covering
their zone. On a typical weekday **1,055,074** of the 2023 pedestrian exposure
inside the thirty units arrives that way and **1,270,486** of the 2019, against
31,036 and 39,298 for cars. Discarding them would have taken roughly a third of
the walking out of the study in both years, and taken more of it from the units
built of large zones.

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
- ~~**2019 — day-of-week flags on the trip.**~~ **Resolved, and the decision it
  led to is that 2019 has no second day type at all.** The flags `p32_lunes` to
  `p32_domingo` are asked as *"¿Qué días de la semana realiza este viaje?"*, so
  they are declared recurrence and not a day anybody lived through — which this
  section already suspected. What it did not know is that there is nothing behind
  them either: **2019 surveyed one kind of day, the typical working day, and
  nothing else.** Five statements in its own delivery say so and the data agree.
  The full argument is in section 5; the consequence for this section is that a
  `DAY_TYPE` dimension the study assumed all four years would carry is a property
  of 2023 alone so far, and 2019's rows exist for `WEEKDAY` and are **absent**,
  not zero, for the other two.
- **2023 — the survey ran on all seven days.** Household interview dates run from
  2023-03-29 to 2023-10-20, with 2,876 households interviewed on Saturdays and
  2,990 on Sundays. The day type has to be derived by joining the trips to the
  household's `fecha`.

  **Resolved: the trips are those of the day before the interview.** The
  technical sheet gives the reference period as the mobility "del día
  inmediatamente anterior al que se realiza la encuesta", so an interview on a
  Sunday reports a Saturday and the interview dates above are shifted back one
  day. What comes out is **17,554 weekday households, 2,990 Saturday and 2,211
  Sunday** — note that the Saturday count is the Sunday interviews and not the
  Saturday ones, which is exactly the error this would have been.

  **And the expansion factor does not expand one day type.** The household
  factors sum to 3,623,413 against the 3,667,331 households the technical sheet
  declares, over all seven reference days together. So summing the trip factor
  within one day type gives that day type's share of an average day and not the
  trips of one such day, and the share of the universe its households cover is
  what converts between them: 77.2 %, 13.2 % and 9.6 %. Both readings are
  exported. See D38 for what the rescaled figures then say, which is not
  credible and is a property of the survey.

**2011's Saturday is too thin to carry a UPL-level estimate and should be
expected to fail.** Its 4,035 records expand to 14,022,328 trips, so one record
stands for roughly 3,500 trips; the 72 bicycle records expand to 310,079. Spread
over 30 units and four modes that is about 34 records per cell before any zone
apportionment. The number will exist and it will not mean anything, and the run
should say so rather than publishing it quietly.

---

## 5. What is unresolved, per year

### ~~2019~~ Resolved, and it answers a question this document did not know it was asking

*Everything below was established from the 2019 delivery itself, reading all 47
of its files rather than the data alone. The questionnaire, the glossary and the
published indicator annex each answered something the CSV could not.*

**The expansion factor is `f_exp` and it expands to one typical day.** Indicator
IND_102 of the delivery's `Anexo D` publishes the trips of a typical day by mode
to the decimal — A Pie 6,941,797.7696855096, Auto 2,291,876.6158069298, Bicicleta
1,177,867.7319962301, Moto 915,313.85802032996 — and the sum of `f_exp` over the
trip file reproduces all sixteen exactly, **18,996,285.55** in all. Paragraph 4.5
of the Etapa V report states it in words: *"En un día típico, se realizan
18,996,286 viajes en el área de estudio"*. The figure this document carried was a
sum of our own; it is now a published control.

**And the whole sample expands the universe once.** The household factor `Factor`
sums to **2,995,531.78** against the 2,995,531.78 households indicator IND_5
publishes for the study area — a ratio of 1.000000. With one kind of day in the
survey, one unit of `f_exp` therefore already is a trip on that day and nothing
needs rescaling, which is the opposite of 2023. This is the field the contract in
§6b says must never be inherited, and here is why: inheriting 2023's answer would
have divided every 2019 figure by 0.77 and left it looking entirely plausible.

**2019 covers one kind of day, and this is the finding that changes the series.**
Five independent statements in the delivery agree:

- the trip module of the questionnaire is addressed *"para las personas del hogar
  con 5 años o más que se desplazaron el día anterior"* and reads *"los
  desplazamientos que realizó el día de ayer, desde las 4 a.m. de ayer a las 4
  a.m. de hoy"*;
- the cartilla's glossary defines a *viajero* as a person reporting at least one
  trip *"el día anterior a la realización de la encuesta"*;
- the report states the total as *"en un día típico"*;
- the published origin-destination matrices — **the very artefact this pipeline
  rebuilds** — come only *"en un día típico"*, with peak and off-peak hours as the
  sole further breakdown and no Saturday or Sunday matrix anywhere;
- the chapter comparing 2019 against 2011 and 2015 lists every difference between
  the three surveys — study area, walking threshold, representativeness, mode
  grouping, population source — and never mentions the reference day.

The data agree. Travel participation runs **79.1 % to 80.6 %** and trips per
person **1.967 to 2.061** across all seven days the fieldwork ran, and the trip
motives are flat too — about 10 % of trips are for study on every one of them,
which no real Sunday looks like.

**The duration is derived, not read.** 2019 reports a departure and an arrival and
no duration; both are stored as fractions of a day. The difference, times 1,440
and rounded to the minute, reproduces the delivery's own
`Aux_DuraciónEODH2019.csv` on **134,496 of its 134,497 rows** — the exception
being a trip from 9:00 to 12:00 that the auxiliary file records as 81 minutes
instead of 180, so the disagreement is a defect in that file. Checked against a
second published figure, walking of fifteen minutes or more comes out at
3,956,916.53 trips a day against the 3,952,811.54 of indicator IND_104, 0.10 %
apart.

**The zoning is `ZAT.shp`, 1,141 zones, EPSG:4686**, the same projection as the
study's cartography. Two codes the trips name are not in it: `0`, a sentinel for
an unanswered zone on records that carry no municipality and no UTAM either, and
`1917` on a single record, above the top of the zoning's own range of 1 to 1908.
Both are declared as naming no place and counted with the records that have no
zone at all.

**The whole reading was checked against a published sub-city table.** Indicator
IND_64 gives the trips of each of the 134 UTAM. Grouping our reading by the
household's UTAM under the indicator's own rule — walking of fifteen minutes or
more, every other mode of any duration — **132 of the 134 agree within 0.01 %,
130 of them to the last decimal**, and the total over them is 15,965,583 against
15,961,478. That single check exercises the expansion factor, the mode labels, the
derived duration and the household key at once, which no city total can.

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

### ~~2023 — the delivered desire lines carry a tenth of the trips~~ Resolved, and against the wrong year

*This section was written before the comparison was made and its central guess
was wrong. Kept because the reasoning is what led to the test that disproved it.*

What it said: the delivered layer's **113,269.31 bicycle trips per day** against
2023's **1,115,685** made the layer about 10 % of the survey, and a tenth of the
trips concentrated in 181 pairs is what selecting the largest pairs looks like —
which would have made the exposure variable a measure of principal corridors.

**The layer is not from 2023 at all. It is from 2019.** All 181 records match an
exact `(zat_origen, zat_destino, f_exp)` triple among the 7,863 bicycle trips of
the 2019 survey, and their endpoints sit on the 2019 zoning's centroids at a
median 0.046 m against 2.148 m for the 2023 zoning. It carries 9.6 % of 2019's
1,177,868 daily bicycle trips — the same tenth, of a different year.

**And the selection was not by volume.** Its 160 distinct pairs rank from 1st to
792nd among 2019's 5,045 inter-zonal bicycle pairs; only 61 are in the top 160,
and the pairs ranked 3rd, 6th, 9th and 10th are absent. No threshold on the
expansion factor, on days per week or on pair volume reproduces the set. The one
rule it clearly follows is that every intra-zonal pair is dropped, which is
forced — a trip that begins and ends in one zone has no line — and which is 9.3 %
of 2019's bicycle travel.

What it is instead is an unexplained sample that does not preserve the ranking:
against the 2023 survey's own bicycle exposure it correlates at **Spearman
0.362** over the thirty units. That is a stronger reason to replace it than the
one this section feared. D35 and D38 carry it.

The note about validation was right: the construction reproduces the survey's own
total and not the layer's, and the comparison against the layer is a diagnosis of
what the layer was.

**And the layer is now retired, after the comparison it made possible.** All 160
of its origin-destination pairs appear among the pairs the pipeline builds from
the 2019 survey, with no pair attributed more trips than the survey holds for it.
Two independent readings of one source agreeing on 160 pairs is the strongest
confirmation the survey reader could get, and it was taken before the layer went.
One thing the comparison also shows: **the plausibility test removes 15 of those
160 pairs outright**, 8,905.8 of the layer's 113,269.3 trips a day, so the
delivered layer carried records this study judges impossible. Its declaration
stays in `config.BICYCLE_DESIRE_LINES` and section 13 of the verification report
stays in place, because figures measured on it are quoted in finished work.

### All years — which day the expansion factor expands to

The current pipeline's check on the delivered layer — weekly over daily between 1
and 7 — observes 4.737 to 5.545, which says the daily factor there expands to a
**working day**. Whether each survey's own factor does the same has to be resolved
by arithmetic per year, not inherited.

*Resolved for two years, and they answer differently, which is the whole point of
not inheriting it.* 2023's factor represents the universe once over all seven
reference days together, so a day type's sum is that day's share of an average
day. 2019's represents it once over one typical day, so its sum already is that
day's trips. The arithmetic that settles it is the same in both cases and it is
the household weights against the published household count: 3,623,413 against
3,667,331 in 2023, 2,995,531.78 against 2,995,531.78 in 2019. Had 2019 inherited
2023's reading, every one of its figures would have been 23 % too small and every
one of them would have looked entirely reasonable.

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

- **2019 stores its clock times as fractions of a day.** `hora_inicio_viaje` and
  `p31_hora_llegada` hold `0.333333333333333` for eight in the morning, the way a
  spreadsheet stores a time. Every datetime parser refuses them and returns
  nothing at all, so a duration computed from them is empty rather than wrong —
  which is the good failure. The trap is the one before it: searching the column
  list for a duration matches `p34_aplicacion_durante_viaje`, because "durante"
  contains "dura", and that column is about an app. It parses, it summarises, and
  every number out of it is meaningless.

- **And the duration derived from them has to be rounded.** `(0.302083333333333
  − 0.291666666666667) × 1440` is 14.999999999 and not 15, so a fifteen-minute
  walk falls on the wrong side of every threshold in the study. Rounding to the
  minute is what makes the derivation agree with the survey's own auxiliary file
  and with its published fifteen-minute split; without it the walking above
  fifteen minutes comes out at 3,590,383 instead of 3,956,917, a tenth of the
  mode lost to floating point.

- **2019's `fecha` column is not the date of the trip, whatever its dictionary
  says.** `Anexo B` describes it as "Fecha del viaje". It is the date the
  interview was carried out — it equals the household's own `p5_fecha` on 78 % of
  records — and the trips are those of the day before, which the questionnaire
  states outright. Taking it at its word would file every trip one day late. It
  happens not to matter for 2019, which has one day type either way, and it would
  have mattered a great deal for a year that did not.

- **2019's numbers use the decimal point and 2023's the comma.** `f_exp` arrives
  as `54.2865603523867`. A reader that replaced commas with points regardless
  would pass this file by accident and mangle any year that used thousands
  separators, so the separator is declared per delivery rather than assumed.

- **The 2019 delivery mixes encodings.** `ViajesEODH2019.csv` and the other trip
  tables are utf-8, and it is worth stating because the sibling year is cp1252 —
  but `Aux_CódigoMunipios.csv` in the same folder is not utf-8 at all. Nothing
  reads it, and that is the only reason it does not matter.

- **The 2023 zoning and the study's cartography disagree along every shared
  edge.** Their overlay gives 1,511 fragments of which 593 are slivers, and
  without a threshold a single zone is split across as many as seven units by
  fragments of a few square metres. With one, 907 zones are inside the study area
  and only 11 are genuinely divided. D38 has the threshold and why it sits where
  it does.

---

## 6b. The contract for the sessions that implement 2019, 2015 and 2011

**Read this before opening a survey folder**, and
[`adding-a-survey-year.md`](adding-a-survey-year.md) for the order to work in.
This section is what must hold; that one is what to do.

Each of the four surveys was
commissioned by a different city administration, and each names and catalogues
its data its own way — different column names, different mode vocabularies,
different ways of saying which day a trip was made on, and in 2015's case four
candidate weight columns with nothing in the file to choose between them. None of
that is knowable in advance. What *is* fixed is everything downstream of it, and
keeping the two apart is the whole design.

### What does not change, and must not

These are the same for every year, and a session that finds itself editing any of
them has misread the problem:

- **The measurement.** Group the trips by actor type, day type and pair of zones;
  draw one line between the two zone centroids; give each unit the share of that
  line's trips matching the share of its length inside the unit. A trip that
  begins and ends in one zone has no line and is spread over that zone's units by
  area. What falls outside the thirty units is measured, not redistributed.
- **The four actor types**, `PEDESTRIAN`, `BICYCLE`, `MOTORCYCLE` and `CAR`,
  named as the casualty matrix names them. Public transport is deliberately not a
  fifth.
- **The shape of the table.** One row per unit, year, actor type and day type,
  with the columns `config.survey_exposure_columns()` declares, in that order.
- **The figures.** Two per combination — a choropleth of `TRIPS_PER_DAY_OF_TYPE`
  and the desire lines behind it — at the same size, the same ramp, the same
  clipping to the study area, the same 95 % drawing threshold, and the same
  colour-bar treatment. One file each unless the bar-less copy is asked for.
- **Where they are written.** `figures/exposure/<year>/<mode>/<kind>/`, with the
  year and mode repeated in the file name because figures get copied into LaTeX
  projects. A new year adds `figures/exposure/2019/` and touches nothing else.
- **The balance.** Every trip the file weights is either measured or named as set
  aside, and what was apportioned plus what fell outside equals what the file
  holds, per actor type and per day type.

If a year cannot be made to fit that without changing it, **stop and report it**
rather than bending the shape. The point of four years is that they are
comparable.

### What must be established from that year's own files

Six things, each a field of `config.MobilitySurvey`, none of which may be
inherited from another year. Every one of them can be wrong in a way that still
produces entirely plausible numbers, which is why they are declared rather than
inferred and why the cross-year comparison below exists.

| What | Field | Where 2023 got it | Where 2019 got it |
|---|---|---|---|
| Which file holds the trips, and how it is encoded | `trips` | cp1252, `;`, comma decimals, spaces inside three column names | utf-8, `;`, **decimal point** |
| Which column is the expansion factor | `weight_column` | `fexp_vj`, confirmed against the published total | `f_exp`, confirmed the same way |
| What one unit of it expands to | `weight_expands_to` | an average day of the collection period, from the household factors summing to the universe once over all seven reference days | **one typical day**, from the household factors summing to the published household universe at a ratio of 1.000000 |
| A published total to check the reconstruction against | `published_total` | 16,390,908, reproduced exactly | 18,996,285.55 from `Anexo D` IND_102, reproduced to the decimal on all sixteen modes |
| How the year says which kind of day a trip was made on | `day_type_rule` | the household's interview date, shifted back one day | it does not: **one kind of day, and no other** |
| How the year states the trip duration | `duration_rule` | `duracion_min`, in minutes, verified against the fifteen-minute walking split before it was trusted | derived from two clock columns held as fractions of a day, verified against the delivered `Aux_Duración` file and against IND_104 |

Plus the mode map and the modes deliberately not measured, which between them
must account for **every** label the file carries: one in neither stops the run.
And, where a delivery uses a code to mean "no zone", `zone_codes_meaning_no_zone`,
so that a code nobody decided about still stops the run.

**Two of the six are rules dispatched through a registry rather than plain
fields, and 2019 is why the second one is.** The day type was always going to be:
four surveys state it four ways. The duration turned out to be as well — 2023
gives minutes, 2019 gives two fractions of a day, and 2015 gives `HORA_INICIO`
and `HORA_FIN` as `HH:MM:SS` text — so it was promoted to `duration_rule` at the
second year, which is exactly where section 7 said such a thing should be noticed
if it was going to happen. Neither is a second reader; both are a small object
beside the others in `config.py` and one entry in a registry in `surveys.py`.

**Verify a column against something outside itself before trusting it.** That is
the rule the whole project runs on and it earned its keep three times here. The
2023 factor arrives as text with a comma decimal and a trailing space, so read the
obvious way it sums to zero without complaining. 2019 stores clock times as
fractions of a day, and a column search for a duration matches
`p34_aplicacion_durante_viaje` because "durante" contains "dura" — it parses, it
summarises, and every number from it is meaningless. And the delivered desire
lines dated themselves 2023 in their own metadata while being a sample of the 2019
survey.

### How the year is checked against the years already measured

`exposure.compare_years` runs at the end of the route and prints two tables: what
each survey measures per mode, and what each sets aside. With one year they are a
baseline; from the second onwards they are the check.

**This is the check that catches a misread declaration**, because nothing inside
a year can. Bogotá does not remake its travel between two surveys, so a mode share
that moves fifteen points, a per-inhabitant trip rate that doubles, or a ranking of
the thirty units that stops agreeing with the previous survey is a misread column
long before it is a finding about the city. All three warn and none fails: a real
change of that size is possible and the run cannot tell the two apart, so it
refuses to let one pass unremarked instead of pretending to judge it.

The baseline, **one typical weekday**, inside the thirty units. This is what 2015
and 2011 will be read against, and it is what 2019 was read against:

| Actor type | 2019 trips/day | Share | Per inhab. | 2023 trips/day | Share | Per inhab. | Spearman |
|---|---:|---:|---:|---:|---:|---:|---:|
| `PEDESTRIAN` | 4,160,690 | 55.8 % | 0.554 | 4,274,636 | 57.2 % | 0.544 | **0.662** |
| `CAR` | 1,827,723 | 24.5 % | 0.243 | 1,611,352 | 21.5 % | 0.205 | 0.947 |
| `BICYCLE` | 787,563 | 10.6 % | 0.105 | 773,132 | 10.3 % | 0.098 | 0.886 |
| `MOTORCYCLE` | 680,233 | 9.1 % | 0.091 | 818,851 | 11.0 % | 0.104 | 0.893 |

**These are `TRIPS_PER_DAY_OF_TYPE` and they have to be.** It is the only column
two years are comparable on, because what `TRIPS_PER_AVERAGE_DAY` holds depends on
what that year's factor expands to: 2023's weekday rows carry 77.2 % of a weekday
and 2019's carry all of one. Comparing the two on that column compares a whole day
against three quarters of one, and it makes every 2023 mode look 23 % smaller than
it is. That is what `compare_years` did until the second year exposed it — a
mistake that could not exist while one year was implemented, because a comparison
with nothing to compare against cannot be wrong.

The corrected figures say something a reader can check against the city: walking
and cycling roughly flat, motorcycle up 15 %, car down 16 %. On the wrong column
all four modes fell by about the same 23 %, which should have been the tell —
four modes measured independently do not collapse in unison.

And what each set aside, as a share of what it measured:

| | Impossible for their mode | Intra-zonal | Outside the thirty units |
|---|---:|---:|---:|
| 2019 | 13.1 % | 21.5 % | 19.5 % |
| 2023 | 9.4 % | 20.0 % | 18.4 % |

A year departing sharply from those proportions is a year whose duration rule,
mode map or zoning is not doing what it was declared to do. **2019 does not**: no
mode share moves ten points, no trip rate moves 35 %, and the two years set aside
almost the same fractions for the same three reasons.

**One thing does trip the check, and it survived investigation.** Pedestrian
exposure orders the thirty units at Spearman **0.662** between the two years,
below the 0.70 floor, while the other three modes sit between 0.886 and 0.947.
The disagreement is concentrated in the north-west: Tibabuyes falls 71 %, Suba
52 %, Rincón de Suba 41 %, while Niza rises 146 % and Barrios Unidos 59 %.

Five tests were run against it and none of them makes it the pipeline's.

1. **The reading reproduces the survey's own published sub-city table** — 132 of
   the 134 UTAM of indicator IND_64 within 0.01 %, 130 to the last decimal.
2. **The two zonings put the same number of zones in those units** — 8 against 8
   in Tibabuyes, 14 against 14 in Rincón, 28 against 28 in Niza — and assign each
   unit the same area to within a tenth of a per cent, 0.82 % at worst over the
   thirty.
3. **The three allocation rules agree with each other.** Tibabuyes falls 71 % by
   length share, 70 % counted at the origin and 70 % at the destination; Niza
   rises 146 %, 155 % and 145 %. The desire lines are not doing it.
4. **The sliver threshold does not move it.** Swept across two orders of
   magnitude the largest per-unit pedestrian figure moves 0.16 %, and Niza 0.2 %.
5. **The raw trip files say the same thing with no pipeline at all.** Summing each
   survey's own expansion factor over its walking trips by origin zone, with one
   zoning used for both years and no desire lines, no apportionment, no day-type
   rescaling and no duration filter, Tibabuyes' share of city walking falls 56 %,
   Rincón's 44 %, Suba's 41 %, and Niza's rises 90 %.

So it is what the two samples say about walking in Suba, and the study cannot tell
a real change from sampling variation there. The run warns and does not fail,
which is the correct behaviour and not a shortcoming.

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

**A missing combination is not a zero.** If a year has no usable Saturday the
rows must be absent or marked, never filled with zeros. This is D10 applied to a
dimension that is ragged by construction — and **2019 is the year that made it
real**, before 2011 ever got the chance: it surveyed one kind of day, so its
block of the table is 30 units × 4 modes × 1 day type = 120 rows, and `SATURDAY`
and `SUNDAY` simply do not appear for it. A reader who filtered the table to
Saturdays would get 2023 and nothing else, which is the truth.

**One reader, four declarations.** The session that implements 2023 writes the
machinery: reading a declared survey, mapping its modes to the four actor types,
splitting by day type, building the lines between zone centroids, apportioning by
length share, and adding the intra-zonal trips by area share. The three sessions
after it add a declaration each and nothing else. If the second year needs a
second reader, the design was wrong and it is cheaper to notice then than at the
fourth.

*Built, and tested by the second year.* `config.MobilitySurvey` is the
declaration and `MOBILITY_SURVEYS` the list; `src/surveys.py` reads one and
`src/exposure.py` measures it. Adding 2019 changed no reading, no geometry, no
apportionment, no check and no figure — the shape held.

**What a new year supplies beyond a declaration is two things, and this section
predicted one of them.** The day type was the expected one: an interview date in
2023, one kind of day and no other in 2019, a flag on the record in 2015 and a
separate database in 2011. The duration is the one that was not: 2023 gives
minutes, 2019 gives a departure and an arrival as fractions of a day, and 2015
gives them as `HH:MM:SS` text. Both are now small rule objects dispatched through
a registry in `surveys.py`, so a year adds a rule beside the others rather than a
second way of reading a file, and a year whose rule is not written fails with a
message naming itself.

That the second of the two surfaced at the second year rather than the fourth is
exactly what this section asked for. It is not a second reader and the design did
not have to bend: it is the same mechanism the day type already used, applied to
the one other field that turns out to vary by administration.

**Interpolation will meet the ρ correction.** The four measured years sit in very
different places in the history of casualty recording: 2011 and 2015 before the
change, 2019 in the middle of the ramp, 2023 inside the reference window. That
does not invalidate an interpolation, and the final report will have to address
it. Noted here so it is not discovered during the interpolation session.
