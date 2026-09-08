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

**2023, 2019 and 2015 have since been built and are no longer structural notes.**
They are declared in `config.SURVEY_2023`, `config.SURVEY_2019` and
`config.SURVEY_2015`, read by `src/surveys.py`, measured by `src/exposure.py` and
checked on run `run_20260908_044524`; the decisions are D38. What those passes
resolved is marked below where it lands, and the entry for 2011 is unchanged and
still unverified. Several things this document listed as unresolved have been
answered and three of its statements turned out to be wrong, which is said in full
in section 5.

**2015 is the year that gave the series its Saturday, and the year with the best
external control any of them has had.** Its own published origin-destination
matrices are reproduced **to the last decimal** on both kinds of day — 17,239,382.6867
and 15,712,253.8360 — which settles the expansion factor, the mode codes and the
zone sentinels in one measurement. And `DIA_NOHABIL` turns out to be a Saturday and
only a Saturday, so the day type is a dimension two of the three measured years
carry and not a property of 2023 alone.

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
| Weight | `F_EXP` | `PONDERADOR_CALIBRADO_VIAJES` **— declared**, confirmed against the published matrices | `f_exp` | `fexp_vj` |
| Expanded trips/day | 17,611,061 | 17,251,733 weekday + 15,730,551 Saturday | 18,996,286 | 16,390,908 |
| Origin/destination zone | `ZAT_ORIG` / `ZAT_DEST` | `ZAT_ORIGEN` / `ZAT_DESTINO` | `zat_origen` / `zat_destino` | `zat_ori` / `zat_des` |
| Zone nulls (origin) | 21,515 (17.6 %) | 43 (0.03 %) | 7,134 (5.3 %) | 0 |
| UPL in the trip record | no | no | no | **yes**, `upl_ori` / `upl_des` |
| Endpoint coordinates | no | **yes**, lat/lon | no | no |
| Zoning shapefile | **none delivered** | `ZATs_2012_MAG`, 948 zones | `ZAT` 1,141 + `UTAM` 141 | `ZAT2023` 1,215 + `UTAM2023` 142 |
| Saturday | separate database, 4,035 records | `DIA_NOHABIL`, 17,730 records — **it is a Saturday, and there is no Sunday** | **none observed**; `p32_sabado` is declared recurrence, 13,436 records | surveyed, 2,876 households |
| Reference day | day before the interview | flag on the record, and the flag *is* the day before the interview | day before the interview, one typical day only | day before the interview |
| Trip duration | unresolved | `HORA_INICIO`/`HORA_FIN` as `HH:MM:SS`, derived and **not** rounded | derived from two clock columns held as fractions of a day | `duracion_min`, in minutes |

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
| `PEDESTRIAN` | `Pie` — 8,136,778 | code 13 `PEATON` — 5,576,942 | `A pie` — 6,941,798 | `A PIE > 15 MIN` + `A PIE <15 MIN` — 6,098,788 |
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
- **The three years do not put the same floor under a walking trip, and 2019 is
  the odd one.** 2023 reports nothing shorter than three minutes and 2015 nothing
  real below it either — 0.22 % of its weekday walking sits under three minutes and
  it is the same 0.22 % that reports a duration of exactly zero, so its floor is
  three minutes too, which is what Tomo IV says it inherited from 2011. **2019 has
  no floor at all**: 1.46 % of its weekday walking, **101,168 trips a day**, lasts
  under three minutes, against 0.03 % of zero-length records.

  So 2019's pedestrian total carries about a point and a half of walking the other
  two years never collected. It is small enough not to change anything measured
  here — it is a twentieth of the gap the pedestrian Spearman is about — and it is
  written down because it is a difference between the instruments and not between
  the years, and because it points the same way as the 2015→2019 pedestrian rise:
  part of that rise is 2019 counting trips 2015 did not. Not correctable without
  imposing a floor on 2019 that its own publication does not use, which would
  make the study's walking disagree with the survey's.

- **2015 cannot put the bicitaxi anywhere, and that is a limitation rather than
  a decision.** Its predominant-mode vocabulary folds the bicitaxi into `ILEGAL`
  together with the mototaxi, the informal car, the collective taxi and the
  unlicensed charter, and no split of that category is available at the trip
  level. Reading the stages of those trips says **86 records and 46,840 trips a
  day** used a bicitaxi, 3.0 % of what 2015 measures as cycling against 2.4 % in
  2019 — so the category is not identical across the two years and the size of the
  difference is about a thirtieth of one mode. Recovering it would mean taking the
  stage rather than the trip as the unit of analysis, which is a different study.
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

*Built for 2023, 2019 and 2015, and the measured cost of the decision is larger
than the table above suggests.* **2015 lands in the same place as the other two:
3,356,494 trips a day intra-zonal, 20.1 % of what it measures in the four modes,
against 21.5 % and 20.0 %.** Three surveys run by three administrations, three
zonings and three mode vocabularies agree within a point and a half on how much
travel never leaves one zone, which is the strongest evidence there is that the
share is a property of the city and not of a delivery.

 Over the four modes together the intra-zonal trips are
**1,841,452 a day in 2023, 20.0 %** of what that survey measures, and **1,987,946
in 2019, 21.5 %**; they are apportioned by area share over the units covering
their zone. On one typical weekday **1,366,277** of the 2023 pedestrian exposure
inside the thirty units arrives that way and **1,270,486** of the 2019 — 32.0 %
and 30.5 % of the walking — against 2.5 % and 2.2 % for cars. Discarding them
would have taken roughly a third of the walking out of the study in both years,
and taken more of it from the units built of large zones. (Both figures are on
`TRIPS_PER_DAY_OF_TYPE`, because they are two years side by side; see §6b.)

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
  The full argument is in section 5; the consequence for this section is that
  2019's rows exist for `WEEKDAY` and are **absent**, not zero, for the other two.

  *And what 2019 seemed to say about the series turned out to be about 2019.*
  While it was the only other year measured, its single day type made the
  `DAY_TYPE` dimension look like a property of 2023 alone. 2015 has a real
  Saturday, observed and separately weighted, so the dimension is carried by two
  of the three measured years, and the ragged case is a year with fewer day types
  rather than a year with more. See D38.
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

### ~~2015~~ Resolved, and its own published matrices are what resolved it

*Everything below was established from the 2015 delivery itself, reading all 103
of its files rather than the data alone. The questionnaire settled which day the
trips belong to, Tomo III counted the two subsamples, Tomo IV published the totals
and named the Saturday, and the twenty machine-readable matrices turned every
belief into a demonstration.*

**The expansion factor is `PONDERADOR_CALIBRADO_VIAJES`, and the four candidates
are told apart by arithmetic rather than by their names.** They stand in a fixed
relation to one another, which is what leaves only one of them capable of being the
published figure:

| Column | What it is | Weekday sum |
|---|---|---:|
| `FE_TOTAL` | the design weight, exactly `PI_K_I × PI_K_II × PI_K_III` on all 147,251 records | 20,074,158 |
| `PONDERADOR_CALIBRADO` | that weight calibrated to the DANE projections; on a trip it is the **person's** weight, identical to the one in `PERSONAS_ANONIMIZADO.csv` on every record | 14,358,944 |
| `FACTOR_AJUSTE` | an adjustment inside a household, which Tomo VII documents as expanding "los viajes de un hogar para completar el total de viajes del Hogar"; it sums to 113,157 over the file and is not a count of trips at all | 98,184 |
| `PONDERADOR_CALIBRADO_VIAJES` | `PONDERADOR_CALIBRADO × FACTOR_AJUSTE_TRANSMILENIO` on all 147,251 records, that last factor taking exactly two values — 1.0 on 652 records and 1.20293649023643 on the other 146,599 | **17,251,733** |

**And the survey publishes what it expanded to, twice over.** Tabla 43 of Tomo IV
gives the twelve modes of a working day and Tabla 119 the twelve of the Saturday,
and `PONDERADOR_CALIBRADO_VIAJES` reproduces **every one of the twenty-four**:
Transmilenio 2,289,878, TPC-SITP 3,899,706, Auto 1,831,396, Peatón 5,576,942,
Bicicleta 846,727, Moto 832,786 on the weekday; Peatón 3,988,607, Auto 2,663,785,
Bicicleta 723,004, Moto 704,289 on the Saturday. The totals are **17,251,733** and
**15,730,551**. No other candidate reproduces any of them.

**The strongest external control this study has ever had is the twenty matrices,
and it comes out exact.** `Documentos/MATRICES EODH/` publishes the
origin-destination matrices — the very artefact this pipeline rebuilds — and
reading the trip file reproduces them **to the last decimal on both kinds of day**:
17,239,382.6867 against 17,239,382.6867 and 15,712,253.8360 against
15,712,253.8360. Mode by mode too, in `matriz_medio_habil` and
`matriz_medio_nohabil`: bicycle 846,727.0479, private car 1,829,032.5781, taxi
703,911.6228 on the weekday, and all five modes of the Saturday, every one of them
exact.

**That check is also what found the first zone sentinel**, which is why a matrix
is worth more than a city total. Before it was set aside the two readings differed
by 1,665.4631 trips on the weekday, and **every disagreeing pair had a `0` at one
end**: 16 records, all of them in Soacha, which is this delivery's way of writing
a zone nobody resolved. The consultant had dropped them and said so nowhere.

**The second sentinel is `1000`, and the matrices keep it where this study cannot.**
It is not a defect: it is the survey's code for a place outside the eighteen
municipalities, carrying municipality 19 *"Otro"* and coordinates 0,0, on 2,229
records and 279,009 trips a day. The consultant left it in their matrices as a
pseudo-zone, which is reasonable for a table of flows between codes and impossible
for a study that has to put a trip on a map: no zoning holds a polygon for it. So
the agreement above is under the matrices' own exclusion rule — no zone, and the
sentinel `0` — and the two readings then diverge by exactly zone 1000, on purpose:
59,115 trips a day on the weekday and 89,642 on the Saturday, in the four measured
modes. **That divergence is the reason to state the rule rather than say "once the
codes naming no place are set aside"**, which would claim agreement on the one
record the two readings decide differently.

**The duration is derived from two `HH:MM:SS` columns and it is exact.**
`HORA_INICIO` and `HORA_FIN`, the questionnaire's *"hora militar"*, with 503
records crossing midnight. The derivation reproduces the delivery's own
`DIFERENCIA_HORAS` on **all 147,251 records** — no defective row, unlike 2019's
auxiliary file — and it reproduces both of the survey's published fifteen-minute
walking splits: **1,976,421** trips a day under fifteen minutes on the weekday
against a published 1,976,421, and **1,037,074.9** on the Saturday against
1,037,075. The all-mode weekday total counting only walks of fifteen minutes or
more comes to 15,275,312.1 against a published 15,275,312.

**And 2015 does not round it, where 2019 must.** Rounding to the minute repairs a
storage defect 2019 has and 2015 does not — a fraction of a day comes back as
14.999999999 for a quarter of an hour. Here the clock is exact, so rounding would
*introduce* the error rather than remove it: it pushes 619 Saturday walking trips
above fifteen minutes that the survey itself counts below, and the published
Saturday figure stops being reproduced. It changes nothing downstream — the
plausibility test rejects the same 1,096 records either way and **not one record
changes side** — so the choice costs the study nothing and buys an exact external
check.

**One unit of the factor is a trip on one day of the record's own kind**, which is
2019's answer and not 2023's, and the households say so without ambiguity. The
weekday subsample's household weights sum to **2,967,290** over 24,622 households
and the Saturday's to **3,045,530** over 3,591; the person weights to 9,059,251 and
9,023,719. Each day type's subsample expands to the whole universe on its own.
Three and a half thousand households carrying as much weight as twenty-five
thousand is what that looks like from outside, and reading it as 2023's would have
left the Saturday an eighth of what it is.

**The zoning is `ZATs/ZATs_2012_MAG.shp`, EPSG:4686**, and it holds **948 features
over 945 zones**: codes 794 and 806 arrive as two and three detached polygons. They
are pieces of one zone rather than two zones sharing a number, and the delivery's
own arithmetic says so — its per-feature `AREA` column sums to the area of the
union in both cases, 8.36 + 7.17 km² and 29.33 + 0.34 + 3.04 km². Both are
peripheral zones north of the city and no trip in the file names either. The code
column is `Zona_Num_N`; `id` is the shapefile's own row number and matches nothing.

**Its numbering is nearly the same set as 2019's and 2023's, and not quite.** 932
of the 945 codes are in both of the later zonings, and for those the 2015 polygon
of a code covers a median **95.9 %** of the 2019 polygon of the same code — the
same places under the same numbers. Thirteen codes are 2015's alone, and the later
zonings carry several hundred more, running to 1908 and 1950 where 2015 stops at
999. What matters for the pipeline is narrower than that and it holds: the **area
each zoning assigns to each of the thirty units agrees to 0.60 % at worst**, and to
under a tenth of a per cent for most of them.

**The mode is a numeric code and the trap the earlier pass recorded is real.**
`ID_MEDIO_PREDOMINANTE` holds the `PREDOMINANCIA` column of
`MEDIO_PREDOMINANTE.xls` — 13 `PEATON`, 10 `BICICLETA, BICICLETA CON MOTOR`, 7
`MOTO`, 6 `AUTO` — and not that table's `CODIGO`, which holds space-separated lists
like `3 4 5 6`. Tomo VII's own foreign key says as much: *fk_id_predominancia
(id_modo_predominante) ref medio_predominante (predominancia)*. All twelve codes
occur in the file and each one is either mapped or declared out.

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

- **2015 delivers two of its zones in pieces.** `ZATs_2012_MAG.shp` has 948
  features and 945 codes: 794 arrives as two detached polygons and 806 as three.
  They are one zone each rather than zones sharing a number, and what shows it is
  the delivery's own `AREA` column, which is per feature and sums to the area of
  the union in both cases. A reader that refuses repeated codes cannot tell that
  case from a real collision, which is why it is declared per year rather than
  dissolved on sight.

- **2015 has two zone codes that name no place, and one of them is not an error.**
  `0` is the familiar sentinel — 16 records, all in Soacha. `1000` is the survey's
  own code for a destination outside the eighteen municipalities it covers: 2,229
  records, 279,009 trips a day, municipality 19 *"Otro"*, coordinates 0,0. It
  appears in the published matrices as a pseudo-zone, so a reader checking against
  those has to keep it there and a reader building geometry has to set it aside.

- **2015's `ETAPAS.xls` is neither utf-8 nor cp1252.** It fails as utf-8 on byte
  0xc2 and as cp1252 on byte 0x81. The trip file in the same folder is pure ASCII
  and decodes under either. Nothing in the pipeline reads the stages, and that is
  the only reason it does not matter — but it is why the encoding is declared per
  table and not per delivery.

- **One 2015 household's row is displaced by a column.** In
  `ENCUESTAS_ANONIMIZADO.csv`, `ENCUESTADOR_FECHA` holds the UTC offset,
  `ENCUESTADOR_HORA` holds the date, `DIA_SEMANA` holds a `1` and `FECHA_UPLOAD`
  holds the interviewer's name. Its eight trips carry perfectly good day-type
  flags, so nothing is lost — but a day-type rule reading the interview date would
  stop the whole run over it.

- **The 2023 zoning and the study's cartography disagree along every shared
  edge.** Their overlay gives 1,511 fragments of which 593 are slivers, and
  without a threshold a single zone is split across as many as seven units by
  fragments of a few square metres. With one, 907 zones are inside the study area
  and only 11 are genuinely divided. D38 has the threshold and why it sits where
  it does.

---

## 6b. The contract for the sessions that implement 2019, 2015 and 2011

**Three of the four are done. Only 2011 is left.**

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

| What | Field | Where 2023 got it | Where 2019 got it | Where 2015 got it |
|---|---|---|---|---|
| Which file holds the trips, and how it is encoded | `trips` | cp1252, `;`, comma decimals, spaces inside three column names | utf-8, `;`, **decimal point** | pure ASCII, `;`, decimal point — while a sibling file in the same folder decodes as neither utf-8 nor cp1252 |
| Which column is the expansion factor | `weight_column` | `fexp_vj`, confirmed against the published total | `f_exp`, confirmed the same way | **`PONDERADOR_CALIBRADO_VIAJES`** of four candidates, confirmed against twenty-four published mode totals and two published matrices |
| What one unit of it expands to | `weight_expands_to` | an average day of the collection period, from the household factors summing to the universe once over all seven reference days | **one typical day**, from the household factors summing to the published household universe at a ratio of 1.000000 | **one day of the record's own kind**, from each day type's household factors summing to the universe separately: 2,967,290 over 24,622 households and 3,045,530 over 3,591 |
| A published total to check the reconstruction against | `published_total` | 16,390,908, reproduced exactly | 18,996,285.55 from `Anexo D` IND_102, reproduced to the decimal on all sixteen modes | 32,982,284 = 17,251,733 weekday (Tomo IV Tabla 59) + 15,730,551 Saturday (Tabla 119), and the two published matrices reproduced **to the last decimal** |
| How the year says which kind of day a trip was made on | `day_type_rule` | the household's interview date, shifted back one day | it does not: **one kind of day, and no other** | a flag the delivery wrote on the record, `DIA_HABIL`/`DIA_NOHABIL`, which the interview date proves is a **Saturday** and agrees with on all 147,251 records |
| How the year states the trip duration | `duration_rule` | `duracion_min`, in minutes, verified against the fifteen-minute walking split before it was trusted | derived from two clock columns held as fractions of a day, verified against the delivered `Aux_Duración` file and against IND_104 | derived from two `HH:MM:SS` columns, reproducing the delivered `DIFERENCIA_HORAS` on every record and both published fifteen-minute splits — and **not rounded**, because its clock is exact |

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

The baseline, **one typical weekday**, inside the thirty units. This is what 2011
will be read against, and it is what 2019 and 2015 were read against. The Spearman
column compares each year with the one before it in the table:

| Actor type | 2015 trips/day | Share | Per inhab. | 2019 trips/day | Share | Per inhab. | Spearman 15→19 | 2023 trips/day | Share | Per inhab. | Spearman 19→23 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `PEDESTRIAN` | 4,459,658 | 59.9 % | 0.615 | 4,160,690 | 55.8 % | 0.554 | **0.554** | 4,274,636 | 57.2 % | 0.544 | **0.662** |
| `CAR` | 1,631,914 | 21.9 % | 0.225 | 1,827,723 | 24.5 % | 0.243 | 0.975 | 1,611,352 | 21.5 % | 0.205 | 0.947 |
| `BICYCLE` | 633,406 | 8.5 % | 0.087 | 787,563 | 10.6 % | 0.105 | 0.726 | 773,132 | 10.3 % | 0.098 | 0.886 |
| `MOTORCYCLE` | 714,894 | 9.6 % | 0.099 | 680,233 | 9.1 % | 0.091 | 0.902 | 818,851 | 11.0 % | 0.104 | 0.893 |

**2015 also carries a Saturday**, which no other measured year does: 6,567,176
trips a day in the four modes inside the units against 7,439,872 on the weekday,
88.3 % of it. Both columns hold the same number for 2015, because its factor
already expands to one day of the record's own kind.

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
| 2015 | **1.9 %** | 20.1 % | 16.0 % |
| 2019 | 13.1 % | 21.5 % | 19.5 % |
| 2023 | 9.4 % | 20.0 % | 18.4 % |

A year departing sharply from those proportions is a year whose duration rule,
mode map or zoning is not doing what it was declared to do. **2019 does not**: no
mode share moves ten points, no trip rate moves 35 %, and the two years set aside
almost the same fractions for the same three reasons.

**2015 departs sharply on one of the three, and it was chased to the bottom.** It
loses 1.9 % to the plausibility test where 2019 loses 13.1 % and 2023 9.4 %, and
the gap is in walking: 3.3 % against 19.7 % and 14.6 %. Four measurements say the
low figure is the delivery and not the declaration.

1. **It is not the durations.** The three years' walking durations are distributed
   much alike, and 2015 rejects an order of magnitude less in *every* band — 1.8 %
   of its fifteen-to-thirty-minute walks against 16.5 % in 2019 and 13.4 % in 2023.
2. **It is not the zoning's coarseness.** The median zone is 0.410 km² in 2015,
   0.412 in 2019 and 0.421 in 2023.
3. **It is that 2015's zone pairs are genuinely closer together.** At the ninetieth
   percentile the two zones of a walking record are 1.45 km apart in 2015 against
   7.07 km in 2019 and 3.63 km in 2023. The far tail is what the test removes, and
   2015 barely has one.
4. **And 2015 is the only year that can be checked against itself on this.** It
   reports the latitude and longitude of both endpoints, which the pipeline does
   not use. Those coordinates say **2.8 %** of its walking records imply a
   straight-line speed above 6 km/h; the zone-based test rejects **1.8 %**. Two
   independent readings agree, and the zone test comes out the more forgiving of
   the two, exactly as it is designed to.

So 2015 has fewer impossible records because it was better geocoded, not because
the test stopped working. The other three departures are ordinary: intra-zonal
within a point and a half of both other years, and less falling outside the thirty
units because its zoning stops at the edge of the surveyed region rather than
reaching further out.

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

**2015 trips the same check on the same mode, and it is the same finding.**
Pedestrian exposure orders the thirty units at Spearman **0.554** between 2015 and
2019, against 0.726 for bicycle, 0.902 for motorcycle and 0.975 for car. Three of
the four tests that cleared 2019 were run again and a fourth was available only
here.

1. **The reading reproduces the survey's own published matrices**, to the last
   decimal on both day types and mode by mode. That is a stronger control than the
   per-UTAM table 2019 was checked against, because it exercises the origin *and*
   the destination of every pair rather than a household's own zone.
2. **The two zonings put the same territory in each unit.** The area they assign
   agrees to **0.60 %** at worst over the thirty, and to under a tenth of a per
   cent for most. They divide it differently — 22 zones in Torca where 2019 has 62,
   16 in Tibabuyes where 2019 has 8 — but they divide the same ground.
3. **The allocation rules agree with each other.** Within 2015 the variable
   correlates at 0.986 with the trips counted at the origin and 0.985 at the
   destination, so the desire lines are not doing it.
4. **The raw files say the same thing with no pipeline at all.** Summing each
   survey's own expansion factor over its walking trips by origin zone, with one
   zoning for both years and no lines, no apportionment and no duration filter,
   gives Spearman **0.708** and the same units moving the same way: Porvenir
   +187 %, Tibabuyes +131 %, Torca +108 %, Patio Bonito +66 %, Suba +56 %,
   Fontibón −47 %, Barrios Unidos −41 %.

The disagreement is concentrated in the units that were being built between the
two surveys — Porvenir, Patio Bonito and Tibabuyes are the Bosa, Kennedy and Suba
expansions — and in Torca, whose figure is 5,938 trips a day and whose rank is
noise. **Tibabuyes is the same unit that falls 71 % between 2019 and 2023**, so
the north-west is unstable in both directions across three surveys, which is what
the 2019 pass concluded about it and what a third year now supports.

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
and `SUNDAY` simply do not appear for it.

The table now has all three shapes in it: 2015 is 240 rows over two day types,
2019 is 120 over one, 2023 is 360 over three. A reader filtering to Saturdays gets
2015 and 2023, and a reader filtering to Sundays gets 2023 alone — which is the
truth in both cases, and is only legible because the absent rows are absent rather
than zero.

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

*Both predictions held at the third year, exactly as written.* 2015 added
`DayTypeFromRecordFlags` and `DurationFromTextClockColumns`, one entry each in the
two registries, and the reading, the geometry, the apportionment, the checks and
the figures were untouched: **2019 and 2023 come out of the run identical to the
last decimal, over all 480 of their rows and every column.** The third year cost
one more thing the first two had not needed — a `SurveyZoning` field saying that a
repeated zone code means one zone delivered in pieces — and that is a fact about a
shapefile rather than a second way of reading one.

That the second of the two surfaced at the second year rather than the fourth is
exactly what this section asked for. It is not a second reader and the design did
not have to bend: it is the same mechanism the day type already used, applied to
the one other field that turns out to vary by administration.

**Interpolation will meet the ρ correction.** The four measured years sit in very
different places in the history of casualty recording: 2011 and 2015 before the
change, 2019 in the middle of the ramp, 2023 inside the reference window. That
does not invalidate an interpolation, and the final report will have to address
it. Noted here so it is not discovered during the interpolation session.
