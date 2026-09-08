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

**2023 has since been built and is no longer a structural note.** It is declared
in `config.SURVEY_2023`, read by `src/surveys.py`, measured by `src/exposure.py`
and checked on run `run_20260907_231531`; the decisions are D38. What that pass
resolved is marked below where it lands, and the entries for 2011, 2015 and 2019
are unchanged and still unverified. Two of the things this document listed as
unresolved were answered by it and one of its statements turned out to be wrong,
which is said in full in section 5.

**What the study needs from them.** Four modes — on foot, bicycle, motorcycle and
car — as **trips per day apportioned to each UPL**, for 2011, 2015, 2019 and 2023.
That is sixteen combinations. **Four of them are measured**, the four modes of
2023; the delivered desire-lines layer that used to stand in for all of this
turned out to be an incomplete 2019, bicycle only, and is now a reference the 2019
session retires.

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

Three things about the mapping that are decisions and not lookups. All three are
now taken, and D38 carries the reasoning:

- **2023 splits walking in two**, over and under fifteen minutes, and both are
  walking. Adding them is the obvious reading and it is still a choice, because a
  study could reasonably exclude the very short trips.
  *Decided: both are in.* The short ones are 2,059,528 trips a day of the
  6,098,788. Excluding them would leave 2023 at 4.04 M against 2019's 6.94 M, and
  48.3 % of 2019's walking — 3,351,414 trips a day — lasts under fifteen minutes
  once its durations are computed from the reported times. The gap would be the
  category and not the city.
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

*Built for 2023, and the measured cost of the decision is larger than the table
above suggests.* Over the four modes together the intra-zonal trips are
**1,841,452 a day, 18.1 %** of what the survey measures, and they are apportioned
by area share over the units covering their zone. On a typical weekday
**1,055,074** of the pedestrian exposure inside the thirty units arrives that
way, against 31,036 for cars, 29,180 for bicycles and 8,048 for motorcycles.
Discarding them would have taken a quarter of the walking out of the study and
taken more of it from the units built of large zones.

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

- **2019 stores its clock times as fractions of a day.** `hora_inicio_viaje` and
  `p31_hora_llegada` hold `0.333333333333333` for eight in the morning, the way a
  spreadsheet stores a time. Every datetime parser refuses them and returns
  nothing at all, so a duration computed from them is empty rather than wrong —
  which is the good failure. The trap is the one before it: searching the column
  list for a duration matches `p34_aplicacion_durante_viaje`, because "durante"
  contains "dura", and that column is about an app. It parses, it summarises, and
  every number out of it is meaningless.

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

| What | Field | Where 2023 got it |
|---|---|---|
| Which file holds the trips, and how it is encoded | `trips` | cp1252, `;`, comma decimals, spaces inside three column names |
| Which column is the expansion factor | `weight_column` | `fexp_vj`, confirmed against the published total |
| What one unit of it expands to | `weight_expands_to` | an average day of the collection period, from the household factors summing to the universe once over all seven reference days |
| A published total to check the reconstruction against | `published_total` | 16,390,908, reproduced exactly |
| How the year says which kind of day a trip was made on | `day_type_rule` | the household's interview date, shifted back one day |
| Which column is the trip duration | `duration_minutes_column` | `duracion_min`, verified against the fifteen-minute walking split before it was trusted |

Plus the mode map and the modes deliberately not measured, which between them
must account for **every** label the file carries: one in neither stops the run.

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

The 2023 baseline, typical weekday, inside the thirty units — this is what 2019
will be read against:

| Actor type | Trips/day | Share of the four | Per inhabitant |
|---|---:|---:|---:|
| `PEDESTRIAN` | 3,300,984 | 57.2 % | 0.420 |
| `CAR` | 1,244,327 | 21.5 % | 0.158 |
| `MOTORCYCLE` | 632,338 | 11.0 % | 0.080 |
| `BICYCLE` | 597,033 | 10.3 % | 0.076 |

And what it set aside, as a share of what it measured: **9.4 % impossible for
their mode, 20.0 % intra-zonal, 18.4 % falling outside the thirty units.** A year
departing sharply from those proportions is a year whose duration column, mode map
or zoning is not doing what it was declared to do.

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

*Built.* `config.MobilitySurvey` is the declaration and `MOBILITY_SURVEYS` the
list; `src/surveys.py` reads one and `src/exposure.py` measures it. **What a new
year has to supply beyond a declaration is one thing and one only: how it says
which kind of day a trip was made on.** That is an interview date in 2023, a flag
on the record in 2015, day-of-week flags in 2019 and a separate database in 2011,
and no amount of declaration flattens four different mechanisms into one. It is
therefore a small rule object dispatched through a registry in `surveys.py`, so a
year adds a rule beside the others rather than a second way of reading a file. A
year whose rule is not written fails with a message naming itself.

**Interpolation will meet the ρ correction.** The four measured years sit in very
different places in the history of casualty recording: 2011 and 2015 before the
change, 2019 in the middle of the ramp, 2023 inside the reference window. That
does not invalidate an interpolation, and the final report will have to address
it. Noted here so it is not discovered during the interpolation session.
