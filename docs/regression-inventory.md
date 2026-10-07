# The inventory for the regressions

What exists for each year the regressions cover, what does not, and why. It is
the counterpart of [`mobility-surveys-inventory.md`](mobility-surveys-inventory.md)
for the stage that comes after the predictors: everything here was measured on
2026-09-21, against the delivered files, and every figure says how it was
obtained.

Sections 1 to 10 were written for three years and one candidate set. Sections 11
and 12 are what changed on 2026-09-25, when the window widened to thirteen years
and a second candidate set was added; where the two disagree, the later ones are
what runs.

Section 13 was a list of changes decided and not yet in the code. **It is empty:**
they were applied and run on 2026-09-28, and what the runs found is section 26 of
the verification report, which is what to quote from here on.

**It exists because the previous stage left a false impression.** The step2 audit
recorded four layers "with an annual series", and three of those four turned out
not to be what that phrase suggests. Two of them do not measure a quantity in any
year. Finding that out before building anything is what this document is for.

---

## 0. The design, in one page

**This is a first step and not the methodology.** The anteproyecto declares one
model — a count GLM on the UPL-by-year panel, with Hausman deciding between fixed
and random effects. That has not changed and it is still what the thesis
estimates. What my advisor and the panel adviser asked for, before the panel is
built, is this: least squares and a GLM one year at a time, on both casualty
datasets, with a table of coefficients and a figure of observed against predicted
for each pair. **The panel is the next stage, not an alternative being rejected
here.** D48 is the decision, and the chapter has to present this the same way.

One separate cross-section per year. One regression per pair of actor types, per
year: **thirty rows, one per unit.**

A cross-section is also what lets every candidate be estimated at all. A
fixed-effects model cannot estimate the coefficient of a variable that does not
change in time, so thirteen of the fifteen would be absorbed by the unit effect;
here there is no unit effect to absorb anything. The year-to-year comparison
survives, by putting separately estimated coefficients side by side.

The table below is the design as it now stands. It began with three years and one
candidate set; D50 widened the window and added the second set, and sections 1 and
12 hold both halves of that.

| | |
|---|---|
| Unit of observation | the territorial unit, thirty of them |
| Response | affected parties of type *i* whose counterpart was type *j* |
| Pairs | eight, listed in section 2 |
| Years | thirteen, 2012 to 2024 — D50 |
| Offsets | three, declared in section 3; the anteproyecto's is the first |
| Candidate predictors | fifteen, listed in section 5, less whatever the offset takes, and less the signage where its layer does not reach |
| Candidate sets | two — **urban only, which is what the study reports and what a run produces with no flag**, and with the offset leftovers, reachable as `--candidates with-leftovers`. D52, and section 12 for how they are built |
| Models per pair and year | 455, 364 or 286 according to the offset and the set |
| Families | least squares and generalised linear model |
| Datasets | observed and rho-corrected, **both, always** |

**The table is built eight times with thirty rows each, not thirty times with
eight rows.** Within one unit every predictor has the same value for all eight
pairs, because the predictors are properties of the unit; a regression run that
way has nothing to regress against.

---

## 1. Which years, and why these

> **Superseded on 2026-09-25 by D50, which widened the window to thirteen years,
> 2012 to 2024.** What follows is the record of the original choice and of the
> argument that made it right at the time. The years are
> `config.REGRESSION_YEARS` and nothing reads them from here.

> **Read `verification-report.md` §23 before reading a difference between two
> years.** The cycleway is one of the two predictors that vary in time, and its
> year-to-year change is not clean: seven of the twelve steps carry re-measurement
> mixed in and 2015-2016 cannot be read at all. It changes nothing for a
> cross-section, where each year stands alone, and a great deal for the panel.

**The three were 2015, 2019 and 2023**, the three most recent of the five years a
mobility survey covers, so the exposure was measured rather than interpolated in
all three. That was the only property separating them from any other year, and
while the exposure existed only where a survey had put it, it was decisive.

D40 removed the constraint by carrying the exposure across every year between the
surveys, and D49 patched the one block where that construction was known to be
wrong. A year without a survey stopped being a year without an exposure, and the
window opened to every year the casualty series and the predictors both reach.
D50 holds the measurement that the thirteen years sustain a regression each, and
what the four years without a signage layer do instead.

**2017 was considered and rejected.** It was proposed while two flow variables
were still thought to be usable, because those two start in 2017 and do not reach
2015. Once those two were dropped — section 5 — the only thing 2017 had over 2015
was gone, and 2015 has a measured exposure where 2017 would need an interpolated
one.

---

## 2. The response, and how much signal it carries

Eight oriented pairs, written as (affected, counterpart). They use four of the six
actor classes, which is the same subset the European study modelled; pedestrian
and cyclist columns are nearly empty in any casualty matrix because those actors
impose almost no risk on anyone else.

The cell is **oriented**: (motorcycle, car) and (car, motorcycle) are different
numbers, and both are in the set. That settles what the response is. It is the
count of **affected parties**, not of crashes — in a two-party crash where both
were hurt there is one crash and two affected parties, one in each cell.

**Affected parties and not persons, decided on 2026-09-21** and recorded in D3.
The matrix carries three counts in the same row — affected parties, persons
injured, persons killed — and the regressions estimate the first. The other two
stay in the tables: a model on deaths is a separate question, and the
measurement it would need first is how many of the 720 unit-pair-year cells hold
a zero, since deaths are about 3% of records.

A regression on thirty units estimates nothing if the response is zero in most of
them. The threshold the anteproyecto declares is fewer than half the cells at
zero. Measured on `run_20260911_155328`, observed dataset, unit scale:

| Pair | 2015 | 2019 | 2023 | zeros, worst year |
|---|---:|---:|---:|---:|
| pedestrian–motorcycle | 1365 | 1264 | 1216 | 0 |
| pedestrian–car | 1184 | 939 | 820 | 0 |
| bicycle–motorcycle | 270 | 454 | 642 | 1 |
| bicycle–car | 463 | 835 | 766 | 1 |
| motorcycle–motorcycle | 410 | 695 | 1780 | 1 |
| motorcycle–car | 1942 | 2564 | 3346 | 0 |
| car–motorcycle | 80 | 260 | 1364 | 5 |
| car–car | 577 | 587 | 764 | 2 |

**All eight pass in all three years.** The worst case is five zero units out of
thirty. Nothing has to be dropped for sparsity, which was the largest risk to the
whole exercise and is now closed.

Two movements in that table are worth carrying into the results. The pairs
involving motorcycles grow steeply — car–motorcycle multiplies by seventeen in
eight years — and pedestrian–car falls. That may be the city motorising, or it may
be the change in recording practice that rho measures, which is exactly why every
model runs on both datasets.

Reproduce with `tools/respuesta.py`.

---

## 3. The exposure, and the offsets

The exposure is built and checked: five survey years, 2005, 2011, 2015, 2019 and
2023, declared in `config` and measured on `run_20260910_154319`. All three
regression years are survey years.

**An offset is a term whose coefficient is fixed at one.** Several quantities can
be placed in it, because the logarithm of a product is the sum of the logarithms,
but doing so asserts a proportionality for each of them rather than estimating it.

**The anteproyecto fixes one: the exposure of the affected mode**, `E_i`, and the
coefficients then read as risk per trip of the mode that is hurt. Both Bogotá
antecedents do this — the pedestrian one uses walking trips, the cyclist one
bicycle-kilometres — and it is the first of the three declared here.

It is no longer the only one the code can express, because my advisor may ask for
the same regressions under a different denominator. An `OffsetSpec` names the
quantities whose logarithms it sums, and three are declared:

| Offset | Quantities | The coefficients then read as |
|---|---|---|
| `MODE_EXPOSURE` | `E_i` | risk per trip of the mode that is hurt — the anteproyecto's |
| `BOTH_EXPOSURES` | `E_i` × `E_j` | risk per trip, with the counterpart's volume held proportional |
| `POPULATION` | residents | burden per resident, comparable with the regional literature |

**A quantity that enters the offset leaves the candidate predictors.** Putting it
in both would estimate its coefficient and fix it at one at the same time. So the
candidate set is derived from the offset and never maintained by hand: fourteen
candidates and 455 models under the first and the third, thirteen and 364 under
the one that takes two quantities.

The pool is twelve urban variables and the three offset quantities. It was
thirteen urban variables until 2026-09-22, when the carriageway was excluded on
the evidence of the first run — it sat beside the sidewalk, which it correlates
with at 0.969, in 44 of 430 models. See D48.

That derivation is also what the second offset asserts and the first does not.
Forcing `E_j` into the offset claims an exponent of one for the counterpart's
volume, which the literature contradicts — the safety-in-numbers exponent is
around 0.4. Under `MODE_EXPOSURE` it is a candidate instead, and **its estimated
coefficient is a measurement of that exponent**. The two offsets therefore ask
different questions of the same data, which is the reason for running both rather
than choosing.

**The offset also changes the least squares response.** Least squares admits no
offset, so there the response is the count divided by the same product. Changing
the offset moves both families coherently, which is what keeps their coefficients
comparable in sign and significance.

**Three offsets are one run and not three.** They are a column of every exported
table, because the point of running three is to compare them, and three runs would
put them in three directories and leave the comparison to be done by hand.

### Which day, and why the weekday

The exposure panel is one number per unit, year, actor type **and kind of day**,
and the offset needs one number. The kind of day is not a detail: in 2019 the
city makes 1.94 million bicycle trips on a Sunday against 1.58 million on a
weekday, a difference of 23%, and the ranking between modes moves with it.

What settles it is not preference but which of the three is a measurement in all
three regression years. Counting the 120 unit-actor rows of each cell:

| Year | Weekday | Saturday | Sunday |
|---|---|---|---|
| 2015 | measured | measured | held |
| 2019 | measured | interpolated | held |
| 2023 | measured | measured | measured |

**The weekday is the only one measured in all three.** Sunday is carried from
elsewhere in two of the three years, so a Sunday offset would put a held value in
the denominator of two thirds of the study. Casualty exposure on a weekday is
also the quantity the two Bogotá antecedents use.

**Settled on 2026-09-21: the weekday alone.** A weighted week would carry more
of the travel that happens and would buy it by importing the held Sundays into
every year. The decision lives in `config.MODEL_EXPOSURE_DAY_TYPE`, so the
regression stage reads it rather than restating it.

The exposure variant, by contrast, is settled by arithmetic: across the 1,080
unit-actor-day rows of the three years, `INTERPOLATED` and `PANDEMIC_PATCHED`
differ by 0.000000. All three are survey years, so the pandemic patch reaches
none of them, and either column gives the same regression.

Least squares admits no offset, so there the response is a rate: the count divided
by the exposure. The two families therefore answer the same question on different
scales, and their coefficients compare in sign and significance, not in magnitude.
The coefficients table says which scale each row is on.

---

## 4. Which layers admit a quantity and which do not

This is the section that changed the plan. A cross-sectional regression needs the
**state** of the unit in that year: how much sidewalk there is, how many signs
there are. A flow — how much was built that year — is a different quantity, and it
carries reverse causality, because a city intervenes where it already has a
problem.

**Cycleway: already a quantity.** Each annual file is the network as it stood that
year, not what was built that year, which is why it grows from 161 km in 2012 to
474 in 2023.

**Vertical signage: computable.** The file named for 2016 is not a record of 2016.
All 67,265 of its records carry `ACCION = INVENTARIO` and installation dates
running from 1991-05-01 to 2015-12-04: it is the full inventory as of the end of
2015. The files from 2017 on are interventions, with install, remove, replace and
relocate. So the stock of any year follows from the inventory plus installs minus
removals. Replacements and relocations do not move the stock.

| End of year | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Signs | 67265 | 67265 | 69768 | 73197 | 74801 | 77333 | 77359 | 77634 | 77690 |

There is no intervention file for 2016, so that year is carried unchanged. That is
one unrecorded year, declared, and not a series invented.

This also explains the defect the audit found — negative densities. The legacy
code treated the inventory as "the year 2016" and everything after as a net
change, when the first is a stock and the rest a flow.

**Horizontal marking and school-zone marking: not possible, in any year.** They
carry only `AÑO`, equal to the file's year, with no prior inventory, no date per
segment and no record of anything wearing out. `MVINANTIGU`, which reads like
"antiquity", holds the road name: "AK 13", "AK 9". The accumulated total from 2017
is "what was added since 2017", which is not the stock, because the starting point
is missing and is nowhere in the data.

The year totals are the argument on their own, and they were measured again on
2026-09-21 with the cycleway beside them as the control:

| Year | Horizontal marking | School zones | Cycleway |
|---:|---:|---:|---:|
| 2017 | 436.0 km | 90.9 km | 316.4 km |
| 2018 | 349.7 | 97.6 | 362.6 |
| 2019 | 163.2 | 19.5 | 386.1 |
| 2020 | 511.4 | 82.4 | 400.9 |
| 2021 | 248.0 | 46.9 | 437.4 |
| 2022 | **1,064.5** | 139.4 | 446.7 |
| 2023 | 262.6 | **4.5** | 474.6 |

Read as a stock, Bogotá tripled its road marking in 2020, doubled it again in 2022
and lost three quarters of it in 2023. Markings do not leave an inventory in that
quantity — they wear and get repainted, which is what a flow of maintenance work
looks like. And school zones would mean the city held **4.5 kilometres** of
school-zone marking in 2023, across more than two thousand schools.

The identifiers say the same thing. Of the 23,947 road codes in horizontal marking
**85.3 % appear in exactly one year**, and of the 5,220 in school zones **94.3 %**
do; in neither layer is a single code present in all seven years. The cycleway,
measured identically, repeats 91.5 % of its codes across years.

Three independent attempts to recover 2015 for these two all failed, and the
numbers are recorded so nobody repeats them:

| Attempt | Result |
|---|---|
| Extrapolate the trend backward | R² of 0.064 and 0.058; 95 % intervals of [−918.6, +1,430.7] km and [−90.0, +280.4] km, both including negative kilometres |
| Use vertical signage as a correlate | r of −0.122 and +0.324; the two are not the same contract and the data say so |
| Reconstruct a stock from repeated segments | the single-year shares above: the flow is mostly new work and cannot stand in for what was already painted |

**So both are dropped, and the reason is not 2015.** That framing was wrong and is
worth correcting here, because it made the problem sound like a gap at one end of
the series: **no year of either layer is usable, 2019 and 2023 included.** The
delivery never contains an inventory, so there is no year whose total is the
marking in place, and the regressions would be missing these two variables in all
three of their years rather than in one.

What would change it is an inventory of marking in place, for any single year,
after which every other year follows by accumulating these same files onto it —
exactly as vertical signage is built from its 2016 `INVENTARIO`. That is a request
to the Secretaría Distrital de Movilidad and not a computation.

**D46 is the full record**, with the year-on-year swings, what was rejected and
why, including the option of using the flow itself as a predictor. Reproduce the
whole table with `tools/flujos_vs_stock.py`.

---

## 5. The predictors that enter

**Every layer enters. Nothing is excluded at this stage.** Decided on 2026-09-21,
after the panel session: the advisor reconsidered which variables to leave out of
the models, so the exclusion is deferred and will be made later, with reasons
given then. Until then the candidate set is everything measured.

This overrides `config.MODEL_PREDICTOR_NAMES`, which holds the eight that a
previous decision had kept. That constant stays as it is — it is what the figures
and tables of chapter 3 use to justify the three exclusions it records — and the
regression stage reads its own list, which is longer. **The two must not be
conflated**, and the day the exclusion is decided, it is that list that changes.

Eleven layers, plus the two survivors of section 4, plus the two quantities
section 3 keeps out of the offset. **Fifteen candidates.**

| | Variable | Kind |
|---|---|---|
| 1 | sidewalk area share | static |
| 2 | arterial road area share | static |
| 3 | roadway area share | static |
| 4 | urban park area share | static |
| 5 | bridge deck area share | static |
| 6 | SITP bus stop density | static |
| 7 | signalised intersection density | static |
| 8 | pedestrian crossing density | static |
| 9 | speed camera density | static |
| 10 | TransMilenio station density | static |
| 11 | tree density | static |
| 12 | **cycleway length per unit area** | series, **built** |
| 13 | **vertical signage density** | series, **built** |
| 14 | counterpart exposure | from the exposure stage |
| 15 | resident population | from the population panel |

All combinations of two or three: 105 + 455 = **560 models per pair, year, dataset
and family**, and 53,760 fits in total. Thirty observations do not support more
than three predictors; the European study faced the same limit with twenty-four
cities and resolved it the same way, selecting among combinations of two or three
by AIC.

**The tree census counts once, and it is the whole census.** Decided on
2026-09-21 and recorded in D32. Three variants are declared and measured — the
whole census, the census without P1 and the census by U codes — and they are
three counts of one layer, not three variables. Only the whole census enters a
model. The other two stay measured and exported as the evidence behind D32 and as
what a sensitivity check would read, and they enter nothing.

### What including everything costs, and the instrument that makes it visible

The instruction is to keep every layer, and the cost of that is known and
measured: **eleven of the fifty-five pairs of static variables already exceed 0.7
in absolute correlation**, the extremes being sidewalk against roadway at 0.969
and the signal network against TransMilenio stations at 0.901.

Two variables that correlated in one model of thirty observations do not give two
readable coefficients: they give one effect split arbitrarily between them, often
with opposite signs and wide intervals. That is not an argument for excluding them
here — the decision is to keep them — but it is an argument for not letting it
happen silently.

**So the run flags it instead of preventing it.** Every selected model records
whether it contains a pair above the declared correlation threshold, and the
models table carries that flag. A coefficient that comes from a flagged model is
read differently, and the chapter can say how many of the selected models are in
that situation. The flag costs nothing and turns a hidden defect into a reported
quantity.

### The vintage of each static layer, which has to be declared

Only two of the eleven delivered static layers say when they were captured.

| Layer | What it declares |
|---|---|
| arterial roads | `FECHA_CAPT` = 2021-12-29, one single date for all 33,015 records |
| tree census | `Fecha_Actu` from 2005-09-15 to 2022-09-24 |
| the other nine | nothing |

**The arterial road layer is a December 2021 cut**, used as a predictor of 2015.
That is a six-year backward reach and it must be written down rather than
discovered by a reader.

**The tree census cannot be dated, and it looked as though it could.** `Fecha_Actu`
is an update date, not a planting date, and two measurements say so. Seventy-one
per cent of the 1,475,041 trees carry a date between 2005 and 2007, with 52.3 % in
2007 alone and 0.1 % in 2008; and the correlation between the date and the tree's
height is −0.190, when a planting date would make recent trees systematically
shorter. Filtering by date would have claimed the city gained 22 % more trees
between 2015 and 2022, when what happened is that the census was finished.

**The nine undated layers are the same number in all three years by construction.**
That does not hurt a cross-section, where they are a legitimate photograph of the
city explaining differences between units. It limits what can be said *between*
years: if eleven of the fifteen candidates are identical across the three models, the
only things that can move a coefficient are the cycleway, the signage, the
exposure, the population and the response. A reader must not be allowed to conclude that "the
effect of sidewalk changed between 2015 and 2023" when the sidewalk is the same
number all three times.

Reproduce with `tools/vigencia.py`.

### What cites each variable

The body of chapter 3 has to say why each variable is measured. This is where each
one is already supported, measured against the vault's reference notes and the
text of chapter 2.

| Variable | Source |
|---|---|
| sidewalk | `stokerPedestrianSafetyBuilt2015`, cited in 2.2 |
| arterial road | `zewdieRoadTrafficInjuries2024`, large-road density, rate ratio 1.30 |
| SITP bus stop | `zewdieRoadTrafficInjuries2024`, bus stop density, 0.89 on deaths |
| signalised intersection | `zewdieRoadTrafficInjuries2024`, 0.90 on deaths |
| pedestrian crossing | `stokerPedestrianSafetyBuilt2015`, "marked crossings with raised medians" |
| speed camera | `martinezRoadSafetyChallenges2019`, section 4.2.2, technology interventions, and `ITF2019`, speed enforcement through speed cameras |
| TransMilenio station | `vergel-tovarExaminingRelationshipRoad2020`, cited in 2.5.3 |
| tree density | `zewdieRoadTrafficInjuries2024`, street trees, 0.83 on injuries |
| cycleway | `aldredCyclingInjuryRisk2018` and `zewdieRoadTrafficInjuries2024`, whose null result is itself the warning about aggregation |
| vertical signage | `pratiUsingDataMining2017`, road signage with importance 0.08 in the decision tree |

**Every variable has a source and every source is already in the bibliography and
already cited in the thesis.** Three of them — crossing, camera and signage — had
no mention in the vault's reference notes and were found in the full texts; their
notes should record the finding so the next search does not repeat this one.

Reproduce with `deliverables/diseno/fuentes_variables.py`, which stays with the
thesis because it reads the vault and chapter 2 rather than the data. See
section 10.

---

## 6. What has to be built

The machinery is further along than it looks. `measure_line_layer`,
`split_lines_by_unit` and `usable_lines` are implemented in `predictors.py` and
`LINE_LENGTH_METHOD` is already bound in the dispatch table; the long table
already carries a `YEAR` column, null for a snapshot; `SNAPSHOT_COVERAGE` and
`ANNUAL_SERIES_COVERAGE` are declared, with a comment saying the series layers are
declared the same way when they arrive; and `verify` already checks that a
snapshot carries no year.

Two things were missing, and they were not the same size.

**The cycleway is built**, on 2026-09-21, and it is the first variable in the
study with a year. All thirteen delivered files are declared and measured. Each
was checked to be a stock and not a flow before anything was declared, by three
tests that agree. The long table goes from 390 rows to 780 and no figure of any
deliverable changed. See D45.

What it cost, which is the estimate the signage work should be planned against:
`source_files` and `source_citation` on `StaticPredictor` with their validation,
a `year` parameter through the three measurement functions, the year loop in
`measure`, a per-variable grid in `build_long_table`, an optional year on
`wide_table`, a year in the summary statistics, and five checks. No new route and
no new module.

**The vertical signage is built**, on 2026-09-22, and with it **every one of the
fifteen candidates exists**. It needed a declaration the cycleway's could not
express — an inventory as of a year, plus one file of movements per year — and a
measurement method rather than the file-per-year mapping, because a removal
cannot be matched to the record it removes. The city totals reconcile with the
control to the record. See D47 and section 20 of the verification report.

What it was before that: Before measuring anything, the stock has
to be built: assign the inventory to units, then accumulate installs minus
removals per unit and year. Only then does the point density run.

The declaration extends `StaticPredictor` rather than forking it, because the long
table, the dictionary, the figures and the checks already know how to handle that
declaration. `source_files`, a year-to-file map null on a snapshot, **now exists**
and `__post_init__` already rejects a snapshot that declares it and a series that
does not. What the signage adds is `stock_builder`, the name of a function that
accumulates state, declared only by it. `measure()` keeps dispatching on `method`;
what changes is who hands it the layer.

**This is not a new route.** The `predictors` route already does this and will
produce thirteen variables instead of eleven. The regressions *are* a new route,
because they read three stages that today run separately.

Order was **cycleway first**, because it exercised the year threading through the
long table, the figures and the dictionary using machinery that already existed;
signage second, when the only new thing is the stock builder. That order held: the
year cost the work listed above and the signage should now be a stock builder and
a declaration. If it needs anything else, the design was wrong, and noticing that
at the second of four is cheap.

### The subtlety to carry

`REUBICAR` can move a sign between units. If the record holds only the new
location, the unit it left keeps counting a sign it lost. The magnitude is small —
about a hundred relocations in seven years against a stock of 77,000 — but it has
to be measured and reported, not assumed away.

---

## 7. Verification

The strongest check is one the pipeline cannot produce for itself. These six were
measured on 2026-09-21 with scripts independent of the pipeline, and the pipeline
reaches them by another route, by summing thirty units:

| Control | Value | Pipeline, summed over the thirty units |
|---|---:|---:|
| cycleway 2015, city | 163.1 km | 163.1 km, **reconciled** |
| cycleway 2019 | 386.1 km | 385.7 km, **reconciled** |
| cycleway 2023 | 474.6 km | 474.2 km, **reconciled** |
| vertical signage stock 2015 | 67,265 | 66,012 inside the units, **reconciled** |
| stock 2019 | 74,801 | 73,420, **reconciled** |
| stock 2023 | 77,690 | 76,167, **reconciled** |

### What stops the run

1. The stock reconciles with its own movement: per unit and year,
   `stock(t) − stock(t−1) = installs(t) − removals(t)`, to the record.
2. The response reconciles with `analysis__matrix_long.csv`. It is a join, not a
   second count.
3. The grid is complete: thirty rows per pair and year, 720 rows and not one more.
4. The exposure exists and is not zero. A zero offset is an undefined logarithm.
5. No predictor is null. A measured zero is a fact; a null is a measurement that
   did not happen, and confusing the two is the defect this pipeline exists not to
   repeat.
6. A series fills `YEAR` in every row and a snapshot in none. The second half is
   already checked; the first is new.
7. Every model records n = 30.

### What is reported loudly and does not stop

**The unit footprint does not cover the whole city.** The sum over thirty units
falls short of the city total, correctly, because 18.27 km² of urban area lies
outside the units. What has to be reported is how much falls outside each year,
and that it does not move: three per cent one year and twelve the next is a
defect. **Built and reporting**: the cycleway captures between 99.87% and 100.00%
of its layer across the thirteen years, a spread of 0.13 points, and a spread above
five points is a warning.

**The 2014 cycleway file is a byte-for-byte copy of 2013**, and the year is
declared with that repetition declared beside it, so every run states it. An
undeclared repetition is a warning instead, and so is a declared one that stops
being true.

**Relocations**, quantified rather than assumed.

**The 2015 cycleway may be the 2013 network.** Measured, the two years differ by
62 metres over the whole city, and one unit accounts for all of it. Read beside
2014, which is the same file as 2013, the delivery looks like one state of the
network labelled three times. It is exported as 2015 because that is what the
delivery calls it, but a cycleway coefficient estimated at 2015 may be reading a
2013 network against 2015 casualties.

**Settled on 2026-09-21**: the years keep their own labels, 2013, 2014 and 2015,
and the text says they carry the same values where it matters. The repetition is
declared in `config.CYCLEWAY_REPEATED_YEARS` and reported on every run, so it is
stated rather than discovered. See section 19 of the verification report.

**Units with no cycleway**, because a variable that is zero in many units has
little variance, and that has to be known before its coefficient is interpreted.

### Two checks on the method

**The null model is the floor.** Every selected model is compared against the one
carrying only the offset, and the run reports how many fail to beat it. A model
that does not beat the null means the urban variables add nothing for that pair,
which is a result to publish. It is also what makes the observed-against-predicted
figure interpretable: with an offset, the fitted values inherit the exposure, so
that figure comes out nearly straight even when the coefficients do nothing. The
null model's cloud is drawn beside it, and what separates the two is what the
coefficients contributed.

**The declared set is walked whole and not exceeded.** The run reports exactly 560
models per pair, year, dataset and family. More means someone added a variable;
fewer means someone pruned. It is the mechanical answer to what the jury warned
about, a multiplication of specifications turning into a search for favourable
results.

### The check that defends the chapter

Selecting the best of 560 models on thirty observations overfits the selection
itself. The European study had the same problem and it is not a defect introduced
here, but it has to be faced.

The answer needs no extra data: **report the distribution of the selection.** If
the winning combination differs every time across eight pairs, three years and two
datasets, the selection is noise and the chapter must say so. If one variable
keeps winning in independent contexts, that is evidence, and far more convincing
than any single p-value. That table — which variable won how many times — is
likely the most defensible result the chapter will have, and it falls out of what
is computed anyway.

---

## 8. Which parts of the declared methodology this step applies

Settled on 2026-09-22 and recorded as D48. The anteproyecto's Phase 2 is written
for the panel, so most of it is about a dimension this step does not have. What
follows is the whole list, with what happens to each and why, because this is what
the methodology chapter has to be able to say.

| Declared in the anteproyecto | Here | Why |
|---|---|---|
| Pair threshold: fewer than half the cells at zero | **reported** | Already measured; all eight pairs pass in all three years, so it drops nothing |
| Poisson against negative binomial by overdispersion | **applied** | Not ceremony: see below |
| AIC and BIC between non-nested specifications | **applied** | Forced by fifteen candidates on thirty rows |
| Moran's I on the residuals | **applied** | Defined on a cross-section, and it informs the panel |
| 95 % intervals, significance at p < 0.05 | **applied, with a caveat** | How a coefficient is reported |
| Hausman | **deferred** | Panel |
| Fixed against random effects | **deferred** | Panel |
| Correlated random effects | **deferred** | Panel |

### The three that are deferred are deferred structurally

Hausman, fixed effects, random effects and correlated random effects all exist to
separate variation *between* units from variation *within* a unit over time. **A
cross-section has no within-unit variation**: each unit contributes one row. There
is no unit effect to absorb or to correlate. They are not left out for
convenience — applying them here would not give a poor answer, it would give an
impossible one.

### Two that look optional and are not

**Poisson against negative binomial.** A count GLM is one of the two, so choosing
is answering a question the request itself poses rather than adding a criterion to
it. And the choice is not cosmetic: fitting Poisson to overdispersed counts makes
the standard errors **too small**, and then every interval and every p-value in
the table is wrong in the direction that flatters the result. The run fits
Poisson, reads the dispersion and refits as negative binomial above the declared
threshold, and the models table records which family each row came from.

**Selection among subsets by AIC.** Forced by the data and not chosen. Fifteen
candidates against thirty observations cannot be fitted together: half as many
degrees of freedom as parameters, with pairs correlated at 0.884. The usual limit
of about ten observations per predictor gives three, which is why the search runs
over combinations of two and three. And once there are 560 fits, **something has
to end the search in one model** — and that one model is what the observed-against-
predicted figure draws. Without a criterion there is no model to plot.

### One that is kept for the stage after this one

**Moran's I** is not a panel diagnostic. It is defined on a cross-section, and the
thirty units are contiguous. It changes no coefficient; what it says is whether
the residuals carry spatial structure. That is what has to be known **before** the
panel is built: if the cross-section is spatially autocorrelated, the panel will
need a spatial term, and finding out now costs one line per model instead of a
rebuild later. The anteproyecto's own limitations already anticipate it.

### The p-values are not honest p-values

The best of 560 models is selected and the significance of the winner is then
reported, which inflates significance by construction. This is a known defect of
the method and the European study being replicated carries it too. **It is not
fixed by more computation.** It is fixed by saying so, which is why the
coefficients table carries the caveat beside the column and the selection
frequency table exists: a variable that wins in independent contexts is better
evidence than any single p-value in the table beside it.

---

## 9. What the run exports

**Built on 2026-09-22.** What follows was the plan and is now the description;
section 21 of the verification report is what the first run produced.

Four tables, because they have four different grains, and a table at the wrong
grain either repeats values or leaves holes.

| Table | One row per | Carries |
|---|---|---|
| `analysis__regression_data` | unit × pair × year | the response, every offset quantity and the fifteen candidates |
| `analysis__regression_coefficients` | variable × model | the estimate, its standard error, its interval and its p-value |
| `analysis__regression_models` | model | which variables won, AIC, BIC, n, family, dispersion, Moran's I on residuals, the collinearity flag |
| `analysis__regression_predictions` | unit × model | observed, predicted, residual |

Each with its `__rho_corrected` counterpart. **A model is identified by pair,
year, family and offset**, and all four are columns, so the three offsets and the
two families are blocks of one table that can be compared rather than separate
runs that cannot. They join on the columns `analysis__matrix_long.csv` already
uses, which is a requirement and not a preference: the dashboard joins these and a
table that cannot be joined is of no use there.

`analysis__regression_data` carries **every** offset quantity in its own column —
the affected mode's exposure, the counterpart's, the population — rather than one
column holding whichever the run used. A reader can then recompute any of the
three denominators from the table itself, and the table does not change shape when
an offset is added.

Figures are a tree whose path is the question they answer. **The year is in the
file name and not in a folder**, because it is the dimension that gets compared
rather than fixed: three years of one combination belong together, and putting
the year first scattered that comparison across three folders while piling
eighteen variants into each.

```
figures/regressions/
├── principal/                     the combination the study reports, copied
│     ajuste__<año>.png            · coeficientes__<año>.png
│     betas.png · modelos.png · LEEME.txt
├── variantes/<conjunto>/<offset>/<familia>/
│     ajuste__<año>.png · betas.png · modelos.png
├── variantes/<conjunto>/<familia>/
│     coeficientes__<año>.png      the three offsets at once
├── entradas/
│     predictoras__<año>.png       · respuestas__<conjunto>__<año>.png
└── resumen/
      frecuencia_seleccion.png
```

No folder holds more than nine files, against thirty-eight in the first version.
`principal/` is a copy of one leaf so that nobody navigates a tree to see a
result, and its `LEEME.txt` says which combination and why: the observed dataset,
the anteproyecto's offset, and the family the dispersion endorses in 143 of 144
models.

**`betas.png` is the figure that answers what the regressions found**, and it is
what my advisor and the panel adviser asked for when they asked for the
coefficients. One row per candidate variable, one column per pair and year, and
in each cell the standardised coefficient of that variable in that model —
**blank where it was not selected**, which is itself the finding for a variable
whose row is nearly empty. Diverging colour centred on zero, so the sign reads
before the magnitude: a row that holds one colour across the grid is a variable
that keeps its sign in every context it survives into.

**The coefficient panel holds all three offsets at once**, one colour each, so
how far a coefficient moves when the denominator changes is visible in one
picture rather than by holding three files side by side.

**The tables are drawn on an image grid and never with `matplotlib.table`.** That
sizes its columns by how many there are and not by what is in them, so a heading
longer than its share is drawn over its neighbour and a long cell spills across
the one beside it — which is what made the first selected-model table
unreadable. Long cells wrap and the rows grow to fit.

**The figures carry results, not attestations.** An earlier version of this plan
proposed four table-figures showing that each methodological commitment had been
honoured. Three were ceremony and were dropped on 2026-09-22: the pair threshold
is one sentence, since all eight pass in all three years; the family choice is a
column of the models table; and whether the declared set was walked exhaustively
is a check on the run, not something an advisor should have to look at. They are
in section 7 as checks, where they belong.

**`table_selection_frequency.png` stays because it is a result.** Which variable
won how many times across the forty-eight combinations of pair, year, dataset and
family. If the winner changes every time, the selection is noise and the chapter
has to say so; if one variable wins in independent contexts, that is evidence, and
more convincing than any single p-value in the tables beside it.

**The predictor block is the same for all eight pairs of a year**, because the
predictors are properties of the unit. So a year needs two input tables, not
sixteen: one of predictors and one of responses, read together.

The panel puts the eight pairs in two rows of four, vulnerable victims above and
motorised below, in the order the pairs are listed in section 2. **Each panel
carries its own axis scale and the caption says so**: pedestrian–motorcycle had
1365 affected parties in 2015 and car–motorcycle 80, so a shared scale would
crush half the panels into the origin. It is the rule `plan.md` already fixed for
more than one matrix on a page.

The fit figure draws the 45-degree line as the reference, never a line fitted to
the cloud. The coefficient figure draws the vertical line at zero, so that an
interval crossing it is visible without reading the table.

**Each figure names its family and its offset in the file name**, for the same
reason both predictor figure sets carry their set: two figures about to sit side
by side must not be told apart by which one lacks a suffix.

**The coefficients table-figure carries the caveat about its own p-values**, in a
note under it and not only in the documentation. A table read on its own must not
let a reader take a starred coefficient for a finding that survived a test, when
it is the winner of a search over 560 models.

---

## 10. How to reproduce every figure here

All of these run from the project root, read only, and write nothing:

    .venv/Scripts/python.exe tools/respuesta.py
    .venv/Scripts/python.exe tools/vigencia.py
    .venv/Scripts/python.exe tools/flujos_vs_stock.py

They are in `tools/`, which is published, **because this document is published
and a citation nobody can follow is not a citation.** They were under
`deliverables/` until 2026-09-21 and moved for that reason; `tools/README.md`
says what each one answers.

One check stays with the thesis and cannot move:

    .venv/Scripts/python.exe deliverables/diseno/fuentes_variables.py

It maps each predictor to the works in the bibliography that discuss it, and it
reads the vault of reference notes and the text of chapter 2. Those are the
thesis, not the pipeline, and they are not published — so moving the script would
put it where a reader could open it and still not run it. It is named here so the
asymmetry is a stated fact rather than something that looks like an oversight.

The measurements of the series at city level, the extrapolation attempts and the
stock reconstruction were made in the session of 2026-09-21. Their numbers are in
sections 2 and 4, `flujos_vs_stock.py` reproduces all of them in one table, and
the checks of section 7 reach them again by another route, which is the point of
making them external controls.

---

## 11. Las figuras con trece transversales, decididas antes de correr

Acordado el 2026-09-25, figura por figura, para que la corrida sea una sola.
Aprobado e implementado el mismo día; la última subsección dice dónde quedó cada
pieza.

### El principio

El árbol de `figures/` está pensado para que una persona lo recorra, y se
conserva. Lo que cambia es que cada hoja pasa de tres archivos a trece, y que hay
años en los que la señalización vertical no existe. Esa ausencia **se tiene que
poder distinguir de una variable que sí estaba y no se seleccionó**, porque son
dos cosas distintas y un lector no puede separarlas mirando la figura.

### `coeficientes/` — un PNG por año, con el tramo declarado en el título

Sigue siendo un archivo por año, sin carpeta por ventana. La ventana A son 2012,
2013, 2014 **y 2024**, que no son contiguos: una carpeta con esos cuatro y otra
con los nueve del medio se recorre peor que trece archivos en orden. El año ya
está en el nombre y ordena solo.

El título gana una tercera línea que dice **qué había en la bolsa**, no qué se
eligió:

| Años | Tercera línea |
| --- | --- |
| 2015-2023 | `con serie este año: ciclorruta y señalización vertical` |
| 2012-2014 | `con serie este año: solo ciclorruta — la señalización vertical empieza en 2015` |
| 2024 | `con serie este año: solo ciclorruta — la señalización vertical termina en 2023` |

El motivo se nombra y es distinto en cada extremo: en 2012-2014 la capa todavía
no empieza, en 2024 ya terminó.

### `entradas/` — tres carpetas, una figura por año en cada una

Treinta y nueve archivos planos no se recorren. El árbol queda:

```
entradas/
├── predictoras/          predictoras__2012.png … predictoras__2024.png
└── respuestas/
    ├── corregido-rho/    respuestas__2012.png … respuestas__2024.png
    └── observado/        respuestas__2012.png … respuestas__2024.png
```

Las predictoras no se parten por conjunto de siniestralidad porque son
propiedades de la unidad y no dependen de él. Y **el archivo deja de repetir lo
que ya dice la carpeta**: dentro de `respuestas/corregido-rho/` sobra el
`__corregido-rho__` del nombre, igual que `ajuste__2023.png` vive dentro de una
carpeta que ya dice familia, conjunto y offset.

**La aclaración del tramo va solo en `predictoras/`, y añadida a la nota al pie
que esa figura ya tiene**, no como tercera línea del título: la figura ya lleva
pie propio y una línea arriba competiría con él.

**En `respuestas/` no va.** Esa figura muestra partes afectadas por unidad y
pareja; qué predictoras tienen serie ese año no tiene relación con ella, y
ponerlo mandaría al lector a buscar una conexión que no existe.

Una consecuencia menor, para que no sorprenda: con una columna menos las celdas
se ensanchan, así que la tabla de 2014 no alinea con la de 2019 si se abren una
al lado de la otra. Es inevitable al quitar una columna.

### Las unidades, en el encabezado de cada columna

**Defecto encontrado el 2026-09-25 y que no tiene que ver con los años nuevos.**
En `predictoras__<año>.png` conviven en la misma fila `0.055` y `2433`, y la
figura no dice que el primero es una proporción del área y el segundo son árboles
por kilómetro cuadrado. Sin esa información el segundo se lee como un conteo, que
es exactamente lo que pasó al revisarla.

Las doce variables **ya están por unidad de área** — se verificó multiplicando
cada valor por el área de su unidad y comprobando que devuelve el entero del
conteo original — así que no hay nada que corregir en la medición. Lo que falta
es decirlo en la figura:

```
   Andén          Vía arterial      Cruces peatonales    Arbolado completo    Ciclorruta
prop. del área   prop. del área         por km²              por km²          km por km²
```

Cuatro son proporción del área, siete son puntos por km² y la ciclorruta es km de
línea por km². Con la unidad en el encabezado la figura se explica sola y la nota
al pie puede quedarse con lo suyo, que es cómo leer el color.

**La unidad va como una línea más de la etiqueta de columna, y el nombre se
rellena a dos líneas antes de añadirla**, de modo que todas las unidades quedan a
la misma altura tengan el nombre una palabra o dos. Se probó la alternativa de
dibujarla aparte, más pequeña y en gris, y se descartó: una etiqueta de marca de
eje admite un solo estilo, así que la unidad hay que anotarla a una altura fija
mientras las etiquetas bajan lo que necesiten, y las dos se pisan en los nombres
de dos palabras. El arreglo exigiría medir el renderizado, que es frágil.

Hay que mirar si la tabla maestra de predictoras del otro grupo de figuras tiene
el mismo problema.

### `parejas/` — las dos figuras que cruzan los años, una por pareja

`betas.png` y `modelos.png` llevaban las ocho parejas a la vez. Con trece años
eso son 104 columnas en el mapa de calor y 104 filas en la tabla, y ninguna de
las dos se lee. Pasan a una carpeta por pareja:

```
<familia>/<conjunto>/<offset>/
├── ajustes/            ajuste__2012.png … ajuste__2024.png
└── parejas/
    ├── peaton-motocicleta/    betas.png, modelos.png
    ├── peaton-automovil/      betas.png, modelos.png
    └── …                      las ocho
```

Las columnas que identificaban el bloque —pareja, familia, offset, conjunto—
salen de las filas y se van al título, donde se dicen una vez en lugar de
repetirse en cada una. Los nombres de carpeta están en `config.PAIR_SLUGS`, junto
a los de familia, conjunto y offset, porque una ruta que se escribe a mano en la
figura es una ruta que se puede escribir distinto en dos sitios.

### El aspa, en la celda del año que no tiene capa

En el mapa de betas, una celda vacía significa «compitió y no entró», y hay
cuatro columnas donde la señalización vertical no compitió en absoluto. Las dos
ausencias se ven igual y significan lo contrario, así que la segunda **se marca
con un aspa dentro de la celda**.

Dentro y no de esquina a esquina: a media celda las diagonales de dos años
vecinos se tocan y se leen como una cinta continua en vez de como dos cruces. El
aspa se dibuja al 0,34 del ancho, que es lo que la separa de sus vecinas.

La fila sigue estando aunque la variable no gane nunca, con el nombre en gris.
Una versión anterior listaba solo las seleccionadas alguna vez, y entonces una
variable que compitió trece años y perdió los trece desaparecía, indistinguible
de una que nunca estuvo en la bolsa.

### `modelos.png` — los años como filas y una columna de «Candidatas»

Los años pasan a ser las filas y las columnas se mantienen. La primera columna es
nueva y cuenta **cuántas variables compitieron ese año**, que es lo que el aspa
hace en la otra figura. Allá hay una celda que marcar; aquí la ausencia se
manifiesta como un nombre que no aparece en una lista, y eso no se ve: sin la
cuenta, comparar 2014 con 2019 no permite distinguir «no estaba disponible» de
«compitió y no ganó». Además vale por sí sola, porque es el tamaño del espacio
que la búsqueda recorrió.

### `frecuencia_seleccion.png` — cada variable sobre su propia bolsa

> **Corregido de nuevo el 2026-09-28 — D53 y sección 13.5.** Lo que sigue arregla
> el denominador de esta figura y ese arreglo sigue en pie, pero la figura entera
> se retira: contaba sobre los 1 868 modelos de la corrida, y eso promedia tres
> offsets y tres familias que se contradicen. La reemplazan dieciocho figuras, una
> por especificación. La regla del denominador propio se conserva íntegra en cada
> una de ellas.

**Defecto encontrado el 2026-09-25, y que la tabla de hoy ya tiene.** La figura
divide las veces que una variable fue elegida entre el total de modelos, y eso
solo es correcto para una variable que compitió en todos. Dos clases de candidata
no lo hicieron: una cantidad de exposición o de población está en la bolsa
únicamente bajo los offsets que no la usan como denominador, y con trece años la
señalización vertical se les une, porque su capa no cubre 2012-2014 ni 2024.

Dividir entre el total castiga a quien tuvo menos oportunidades, y no un poco: al
corregirlo sobre la corrida de tres años, «Exposición afectado» pasa del puesto 9
al 1. Es el mismo error que ya se había cazado al medir los restos de offset,
cometido en otra parte del mismo paso.

La corrección es el denominador propio, y **el denominador va a la vista**: un
porcentaje cuyo divisor cambia de fila en fila y no se muestra es el mismo
defecto con otra cara. La tabla gana dos columnas:

| Columna | Qué dice |
| --- | --- |
| `De cuántos pudo` | en cuántos modelos esa variable estuvo en la bolsa |
| `Offsets` | en cuántos de los tres compitió: 3 las urbanas, menos los restos |

`Offsets` se lee así: donde diga 1, el porcentaje de esa fila describe **ese
offset y no el estudio**, porque la variable solo pudo competir cuando el offset
no la estaba usando de denominador. Donde diga 3, el porcentaje habla de toda la
corrida.

La columna se añadió por una preocupación concreta y la responde: que un resto de
offset termine ganando por encima de las variables urbanas sin que la figura deje
ver que compitió en condiciones distintas.

### Dónde quedó implementado

Todo lo anterior está en `src/regressions.py` y en `src/config.py` desde el
2026-09-25. El árbol lo arma `render_figures`; las rutas por pareja salen de
`config.PAIR_SLUGS`; la línea que declara el tramo de un año la da
`config.series_available_in`, que la escribe una vez y la usan las dos figuras
que la llevan; la unidad de cada columna sale de `config.predictor_unit_es`, que
traduce el `value_unit` del método de medición en lugar de declararla variable
por variable; y el denominador propio lo calcula `selection_frequency`, que por
eso pasó a recibir también la tabla de modelos.

Dos comprobaciones nuevas en `verify` sostienen lo que las figuras dibujan: que
ninguna candidata de la bolsa del año llega nula, que ninguna que no esté en esa
bolsa llega con valor —un cero ahí se leería como una ausencia medida— y que
ningún coeficiente pertenece a un año que su capa no alcanza. La tercera se probó
falseando un coeficiente de señalización en 2012: la comprobación falla y nombra
al culpable.

---

## 12. La corrida limpia, decidida antes de correrla

Acordada el 2026-09-25, después de la corrida de trece años. La decisión de
fondo es D50; aquí está lo que se implementó y qué se comprobó antes de lanzar.

### Qué es

La misma ruta con una bandera:

```
.venv/Scripts/python.exe -m src.run_pipeline regressions --candidates urban-only
```

Sin la bandera corre `with-leftovers`, que es la que el estudio reporta. La
bandera va declarada en la ruta, en un campo `options` del `Route`, y no como un
`if` sobre el nombre de la ruta: la siguiente que necesite una opción añade una
línea en vez de otra rama.

Se prefirió la bandera sobre una ruta nueva porque **las dos corridas son el
mismo procedimiento con una declaración distinta**. Dos rutas paralelas son dos
cosas que mantener sincronizadas, y lo que se quiere es exactamente lo contrario:
que solo pueda cambiar el conjunto de candidatas.

### Qué cuesta y qué declara

| | Con restos | Solo urbanas |
| --- | ---: | ---: |
| Candidatas por año, con señalización | 14 / 13 / 14 según el offset | 12 en los tres |
| Candidatas por año, sin señalización | 13 / 12 / 13 | 11 en los tres |
| Especificaciones por celda | 455 / 364 / 455 | 286 en los tres |
| Declaradas en total | 745 056 | 497 376 |

El 67 % del trabajo de la otra, unos dieciséis minutos.

### La columna que distingue las dos corridas

`CANDIDATE_SET` es la primera columna de identificación de modelos,
coeficientes, predicciones y frecuencia de selección. Sin ella las dos corridas
producen tablas **idénticas en forma y distintas en significado**, con los mismos
nombres de archivo, y ni el tablero ni la comparación podrían separarlas.

`MODEL_ID` se dejó como estaba —`conjunto|offset|pareja|año|familia`— para no
cambiarle el formato de un identificador al tablero, que lo consume. La
consecuencia es que juntar las dos corridas exige emparejar por `CANDIDATE_SET` y
`MODEL_ID`, no por `MODEL_ID` solo.

### Qué dice la figura

**Todas las figuras cuyo contenido depende del conjunto lo dicen en el
subtítulo**, corra el que corra, no solo la corrida que no es la de siempre:

```
GLM binomial negativa · offset: exposición del modo afectado · conjunto: observado
 · candidatas: solo urbanas
```

Se dice «candidatas» y no «conjunto» porque esa palabra ya está ocupada por el
conjunto de siniestralidad, y un subtítulo con dos conjuntos obliga a adivinar
cuál es cuál. La figura que existe para desambiguar dos corridas no puede
introducir una ambigüedad nueva al hacerlo.

Se marcan las cinco que dependen del conjunto —ajustes, coeficientes, betas,
modelos y frecuencia— y **no se marcan las de `entradas/`**, que son las mismas
en las dos corridas: las predictoras por unidad y las partes afectadas no
dependen de quién compite. Marcarlas sugeriría una diferencia que no existe.

Marcar siempre y no solo la corrida limpia tiene un motivo: una figura que calla
obliga a recordar cuál era el valor por defecto el día en que se dibujó, y eso no
se recuerda.

### La columna «Offsets» aparece solo donde informa

En la corrida limpia los tres offsets comparten bolsa, así que «en cuántos de los
tres compitió» vale 3 en las doce filas. Una columna de un solo valor repetido se
lee como una medición y no lo es, así que se dibuja solo cuando varía —la misma
regla que `modelos.png` ya aplica a su columna «Dispersión»— y la nota al pie
pierde con ella las dos frases que allí describen algo que no ocurre.

`De cuántos pudo` **no** sigue esa regla y se dibuja siempre: no es una propiedad
de la variable sino el denominador del porcentaje que tiene al lado, y un
porcentaje cuyo divisor no se ve es el defecto que esa columna vino a corregir.

### Qué se comprobó antes de lanzar

Diecisiete comprobaciones en tres tandas, ninguna de las cuales ajusta un modelo
completo.

**Sobre la declaración**, diez: que las dos bolsas difieran exactamente en las
tres cantidades de offset en los trece años; que la bolsa urbana sea idéntica a
la lista de candidatas del año; que sin restos los tres offsets compartan bolsa y
con restos no; que las especificaciones por celda den 286 y 220; que el total con
restos reproduzca **las 745 056 que declaró la corrida de trece años**, que es lo
que demuestra que enrutar el conjunto por trece sitios no cambió nada de lo que
ya corría; que olvidar el conjunto sea un `TypeError` y no una corrida silenciosa
con la bolsa equivocada; y que un conjunto inventado sea un `KeyError`.

**Sobre una corrida de humo** con los dos conjuntos —una pareja, un offset, una
familia, trece años—, cinco por conjunto: los 26 modelos; que las declaradas sean
las del año; que los restos compitan donde deben y en ningún sitio donde no; que
las tres tablas digan de qué corrida son; y que no haya ninguna elasticidad donde
no hay cantidad logaritmada libre.

**Dentro de `verify`**, dos nuevas que corren en cada corrida: que las tres
tablas declaren el conjunto de la corrida y solo ese, y que ninguna cantidad de
offset haya competido cuando el conjunto es el urbano.

### Lo que la corrida de humo ya adelantó

Sobre 26 modelos de una sola pareja, un offset y una familia, que es poco y se
dice: las 24 selecciones que se llevaban los dos restos **no se reparten
proporcionalmente**. El andén pasa de 6 a 14 y la vía arterial de 4 a 10,
mientras que TransMilenio baja de 10 a 8 y el arbolado y la señalización de 4 a
2. Esas tres estaban ganando *en compañía* de los restos y no en su lugar.

Si eso se sostiene en la corrida completa es lo que contesta
`tools/comparar_candidatas.py`.

---

## 13. Los cambios del 2026-09-28, aplicados

**Esta sección era una lista de trabajo y está vacía.** Se llenó entre el 25 y el
28 de septiembre con cinco cambios, se acordaron uno por uno, se implementaron en
ocho pasos con una verificación en cada uno, y se corrió. Lo que queda aquí es el
puntero, para que nadie busque en una lista cerrada.

**Lo que se hizo y por qué está en las decisiones**: D51 el beta estandarizado de
mínimos cuadrados, D52 el conjunto urbano como el que reporta el estudio, y D53
qué cuenta como contexto independiente. Las dos cosas que no necesitaron decisión
propia —el tercer conjunto de figuras, el de las doce, y los tres boxplots de
dispersión que pidió la asesora del panel— están descritas en D53 y en la sección
26 del informe de verificación.

**Lo que las corridas dieron está en la sección 26 del informe de verificación**,
que es la que hay que citar de aquí en adelante. Las corridas son
`run_20260928_112330`, la que el estudio reporta, y `run_20260928_114216`, la de
robustez con los restos de offset.

### 13.1 Lo que quedó propuesto sobre los tres boxplots, y sin aplicar

**D55, del 2026-10-01: dejar Torca fuera de las tres figuras de dispersión.** Es
una candidata y no una decisión: `src/regressions.py` no cambió. Torca es el mínimo
de ocho de las doce variables y está pegada al suelo en once, y quitándola el bigote
inferior se desplaza 2,54 desviaciones estándar sumadas sobre siete variables,
contra 0,11 de la siguiente unidad. **Saldría de las figuras y no del estudio.**

Lo que hay que tener presente si se retoma, y que está medido en D55: no arregla los
paneles de cámaras y de TransMilenio, porque ahí el cero lo comparten seis y siete
unidades; en la figura de serie anual el piso sólo sube desde 2017; y cambia el orden
de la figura estandarizada, que ordena por ancho de caja. **Si se aplica, las figuras
de las once predictoras de la etapa anterior tienen que aplicarlo también**: dejar a
Torca fuera de un conjunto y dentro del otro sería peor que cualquiera de las dos
opciones.

La prueba de que ninguno de los cinco cambios tocó el ajuste está ahí también: la
corrida con restos reproduce clavadas las cuatro cifras de `run_20260925_090146`.

### Si esta sección vuelve a llenarse

Se llena igual: una entrada por cambio, con qué, por qué, dónde toca y cómo se
verifica; nada se implementa hasta que Mateo la cierre; y al cerrarla se ejecuta
en pasos, cada uno con su verificación, antes de correr nada. Ese esquema funcionó
y las dos veces que algo falló fue una verificación mal escrita y no el código.

## 14. Lo que la asesora del panel pidió el 2026-10-01, y dónde quedó

**Estado al 2026-10-02: tres figuras hechas en la carpeta temporal, ninguna en el
*pipeline*, y Mateo ya decidió que las tres entren.** Falta un cambio de diseño
acordado, redactar el correo, implementar y correr.

### Lo que pidió, y lo que de eso es recuperable

Vio `betas.png` y dijo tres cosas: que quiere **la tabla completamente poblada**, que
quiere saber **el mecanismo exacto** por el que salen elegidas unas variables y no
otras —preguntó en concreto por qué unos años salen con tres y otros con dos—, y que
quiere **una tabla con los valores (beta, R², AIC, BIC) de cada variable** para que la
razón de la selección sea explícita.

**La tercera, tal como está dicha, mezcla dos niveles.** Beta es propiedad de la
variable dentro de un modelo; R², AIC y BIC son propiedades **del modelo**. «El AIC de
la vía arterial» no existe: existen los 66 modelos que la contienen. La lectura que sí
tiene sentido, y que es la que se implementó, es **el AIC del mejor modelo que la
contiene**.

### El mecanismo, para poder explicarlo sin volver a leer el código

`search()` en `src/regressions.py` ajusta **todas las combinaciones de dos y de tres**
de la lista declarada —`config.REGRESSION_SUBSET_SIZES = (2, 3)`— y se queda con la de
menor AIC. Ni pasos hacia adelante, ni interacciones, ni transformaciones.

- Con doce candidatas: **66 pares + 220 tríos = 286 modelos**. Con once: **220**.
- Cada variable aparece en **66** de los 286 —o 55 de los 220—.
- **Por qué dos o tres y no más:** treinta unidades.
- **Por qué a veces tres y a veces dos:** el AIC penaliza cada parámetro con dos
  puntos, así que una tercera variable sólo gana si mejora el logaritmo de la
  verosimilitud en más de uno. En la corrida reportada gana con tres en **1 462 de
  1 868 celdas (78 %)** y con dos en **406 (22 %)**.
- **Una corrida ajusta 489 448 modelos y guarda 1 868**: uno por celda, el ganador. El
  **99,6 % de lo que se calcula se descarta**, y por eso las cifras que ella pide no
  hay que calcularlas, hay que dejar de botarlas.

### Las tres figuras, hechas y validadas

En una carpeta temporal fuera del repositorio, replicando la ruta de la corrida:

| | Dónde | Qué es |
| --- | --- | --- |
| Dispersión sin Torca | `sin_torca\...\predictoras\dispersion\` | las tres de D55 |
| Tabla por variable | `tabla_variables\...\peatones-motocicleta\por_anio\variables__{2017,2023}.png` | doce filas, el mejor modelo de cada variable |
| Betas poblada | `tabla_variables\...\peatones-motocicleta\betas__tabla_completa.png` | la cuadrícula con las 152 celdas llenas |

**Validación:** la búsqueda reproducida fuera del *pipeline* da **el mismo ganador y el
mismo AIC** que el guardado, 222,5 en 2017 y 246,4 en 2023, y el R² del ganador
coincide con el del *pipeline* hasta la tercera cifra.

**Tres errores propios en el camino, los tres vistos mirando y no por una
comprobación:** el R² salía −4,67 idéntico en las doce filas por usar `fittedvalues` en
vez de `predict` —en la binomial negativa discreta `fittedvalues` es el predictor
lineal, y el propio código lo advierte en un comentario—; la figura salía blanca porque
el arreglo de sombreado se construyó y **nunca se pasó** a `_grid_table`; y un guardado
falló por tener el archivo abierto.

### Lo que la tabla por variable destapó, y que no se ve en ninguna figura actual

- **2017: la selección fue casi un empate.** El ganador tiene AIC 222,5 y el mejor
  modelo de la señalización vertical 222,6. Y el R² de ése es 0,83 contra 0,82 del
  ganador: **el AIC eligió un modelo que ajusta algo peor**, porque AIC no es R².
- **2023: Semáforos tiene beta +0,45\*\*, el mayor de la tabla, y no aparece en la
  figura de betas.** Su modelo pierde por 0,4 puntos. Y la ciclorruta consigue R² 0,66
  contra el 0,64 del ganador.
- En la betas poblada, **la fila de Semáforos es roja los trece años y nunca ganó**, y
  TransMilenio es rojo desde 2012 aunque sólo gane desde 2021: lo que empieza en 2021
  es su selección, no su efecto.

### La dispersión de los coeficientes, medida el 2026-10-02

Sobre los 66 modelos de cada variable, en la pareja peatones-motocicleta:

- **El beta del ganador no es un valor extremo**: cae en el percentil 33, 17 y 3 en
  2017, y 76 y 24 en 2023. Ponerlo al lado de medianas no engaña en magnitud.
- **Pero la dispersión es grande y crece.** En 2017 los rangos van de 0,07 a 0,35; en
  2023, de 0,13 a 0,85. La vía arterial en 2023 va de **−0,251 a +0,600** según
  compañía.
- **En 2023, nueve de las doce cambian de signo** entre sus 66 modelos. Las tres que
  no son cámaras, TransMilenio y parque urbano — y dos de esas tres son las que
  ganaron. No es casualidad: una variable cuyo efecto no depende de la compañía aporta
  información propia, y eso es lo que el AIC premia.

### Lo acordado, lo pendiente y lo abierto

**Acordado el 2026-10-02:** en la betas poblada, **no** encerrar entre paréntesis las no
seleccionadas. Los betas son de la misma naturaleza, así que el paréntesis marcaba lo
que no era. En su lugar se **recuadra en negro la celda de las seleccionadas**, que es
lo que de verdad las distingue: son las que el estudio reporta. Requiere añadir un
parámetro `boxed_cells` a `_grid_table`, que hoy sólo tiene `crossed_cells`.

**Pendiente de implementar en el *pipeline*, ya decidido que entra:** las tres figuras
de dispersión sin Torca (D55), la tabla por variable y año, y la betas poblada. Con
ellas, **la exclusión de Torca alcanza también a las figuras de las once predictoras**,
por la razón escrita en D55.

**Volumen a decidir:** la tabla por variable es una por año y por celda. Para la
especificación que el estudio reporta son **104 figuras**; para las dieciocho serían
**1 872**, más de lo que la corrida entera produce hoy. La recomendación es generarlas
sólo para la reportada.

**Abierto, y Mateo no lo entendió todavía:** marcar en la celda las variables cuyo
signo no es estable entre sus 66 modelos. El argumento es que una mediana de +0,11
calculada sobre valores que van de −0,25 a +0,60 se lee como «ligeramente positivo»,
que es una afirmación que los 66 modelos no sostienen, mientras que una de −0,27 sobre
valores todos negativos sí significa algo. Las dos salen como un número en una celda y
el lector no puede distinguirlas.

**Lo que sigue después:** redactar el correo a la asesora con copia a Olmos —qué cambió
en los boxplots, cómo funciona la selección, qué figuras van adjuntas, y que el
resultado de la corrida irá por Teams en un ZIP—, implementar, y correr.

### 14.1 La trampa de mínimos cuadrados, que ya mordió una vez

**Esto va primero porque es lo que rompe la implementación si se pasa por alto, y de
una forma que no salta a la vista.**

Mínimos cuadrados **ajusta la tasa**, porque no admite offset: la respuesta es el
conteo dividido por el mismo producto que el GLM pone en su offset. Su coeficiente está
por tanto en unidades de tasa y vale del orden de una diezmilésima. El GLM ajusta el
conteo y su coeficiente ya es adimensional.

**D51 resolvió esto para la figura**: `_plotted_coefficient(family)` devuelve
`COEFFICIENT_FULLY_STANDARDISED` para mínimos cuadrados —el coeficiente dividido además
por la desviación de la respuesta, vía `_over_deviation`— y `COEFFICIENT_STANDARDISED`
para los GLM. Antes de D51, **los 1 639 coeficientes de mínimos cuadrados salían
redondeados a «0,00»** y el signo sobrevivía sólo como el guion de un «-0.00».

Medido el 2026-10-02 sobre la celda `PEDESTRIAN__MOTORCYCLE` de 2023, con sus 792
coeficientes por familia:

| | Coeficiente crudo | El que la figura dibuja | Crudos que darían «0,00» |
| --- | ---: | ---: | ---: |
| Mínimos cuadrados | mediana 6,0 × 10⁻⁵ | mediana 0,262 | **792 de 792** |
| GLM binomial negativa | mediana 0,111 | mediana 0,111 | 13 de 792 |

Hay un factor de unos cuatro mil entre las dos escalas, que es uno sobre la desviación
de la tasa.

**El prototipo del 2026-10-02 tiene este defecto latente.** Toma `res.params[i + 1]`,
el coeficiente crudo, que en el GLM coincide con lo dibujado y en mínimos cuadrados no.

**Y el daño sería peor que el de D51, no igual.** Entonces se vaciaba la tabla entera y
el defecto era evidente. Ahora **las celdas recuadradas vienen del CSV, que ya guarda la
cantidad correcta**, y sólo las no recuadradas saldrían en crudo: una tabla donde las
seleccionadas se ven bien y todas las demás son «0,00», que se lee como «ninguna de las
que no entró vale nada». Una conclusión falsa, y de las que no se notan.

**La regla, para no volver a tropezar:** toda cantidad que se vaya a dibujar en una
figura de coeficientes pasa por la misma bifurcación por familia que usa el dibujo. Si
el código calcula un resumen —una mediana, un rango, un percentil— y no pregunta por la
familia antes, está mal aunque el GLM salga bien.

### 14.2 Los cambios aprobados el 2026-10-02, listos para implementar

Aprobados los cinco. **Se implementan después de redactar el correo a la asesora.**

> **Los puntos 1 y 2 quedaron reemplazados el 2026-10-02 por D56**, que saca a Torca de
> las regresiones en vez de sacarla de unas figuras. Se dejan escritos porque el punto 1
> sigue describiendo la redacción de los pies, que hay que cambiar igual, y porque el
> punto 2 ya no aplica: las figuras de las once predictoras **conservan las treinta**.
> Lo que hay que implementar está en **14.3**.

**1. Las tres figuras de dispersión, sin Torca.** D55. Un filtro al principio de
`_render_dispersion` más la redacción: los tres sitios que dicen «Treinta unidades» o
«las mismas treinta unidades», los tres títulos, y una frase en cada pie. El generador
provisional de `tmp/dispersion_sin_torca.py` es la referencia del texto.

**2. La exclusión de Torca alcanza también a las figuras de las once predictoras.**
Histogramas, matriz de correlación y tabla maestra de
`config.COMPLETE_FIGURE_PREDICTOR_NAMES`, por `predictors.render_figure_set`. La razón
está en D55: dejarla fuera de un conjunto y dentro del otro es peor que cualquiera de
las dos opciones. **No se tocan** los modelos, los coeficientes, la frecuencia de
selección ni las figuras de observado contra predicho: Torca no sale del estudio.

**3. La tabla de betas, poblada, con recuadro.** Las celdas que hoy están vacías llevan
**la mediana del coeficiente sobre los modelos de ese año que contienen esa variable**,
55 o 66 según el año. **Sin paréntesis**: los betas son de la misma naturaleza y el
paréntesis marcaba lo que no era. Lo que distingue a las seleccionadas es **un recuadro
negro en la celda**, que además deja ver el color de fondo. Reemplaza a `betas.png` o
convive con ella, a decidir al implementar.

**4. La tabla por variable y año.** Doce filas, una por candidata, ordenadas por AIC;
cada fila es **el mejor modelo que contiene esa variable**, con la beta que la variable
tiene en ése, y el AIC, el BIC y el R² de ése, más las acompañantes. Las filas del
modelo ganador van sombreadas y comparten AIC porque son el mismo modelo. Ruta:
`parejas/<pareja>/por_anio/variables__<año>.png`, que reutiliza el patrón `por_anio/`
que ya existe en `entradas/predictoras/`.

**5. `boxed_cells` en `_grid_table`.** Un parámetro hermano de `crossed_cells` que
dibuja un rectángulo negro en las celdas indicadas. Con él, las doce líneas de envoltura
de `tmp/betas_pobladas.py` desaparecen.

#### Lo que hay que respetar al implementarlo

- **La bifurcación por familia de 14.1**, en la mediana de la tabla de betas y en la
  columna de beta de la tabla por variable.
- **AIC y BIC no se comparan entre familias**: el de mínimos cuadrados está en la tasa
  y el de los GLM en el conteo. El pie de `modelos.png` ya lo dice y la tabla nueva
  tiene que repetirlo.
- **`predict` y no `fittedvalues`** para cualquier R², porque en la binomial negativa
  discreta `fittedvalues` es el predictor lineal. Para mínimos cuadrados, además, hay
  que multiplicar por la exposición para volver a conteos, como ya hace el código.
- **El volumen.** La tabla por variable es una por celda. Para la especificación que el
  estudio reporta son 104 figuras; para las dieciocho, 1 872, más de lo que la corrida
  entera produce hoy. **Mateo decidió que el cambio aplica a todas las
  especificaciones**, así que hay que resolver el volumen al implementar: o se generan
  las 1 872, o se declara un subconjunto y se dice cuál en el pie.
- **La validación que ya pasó y que hay que repetir:** la búsqueda reproducida fuera
  del *pipeline* dio el mismo ganador y el mismo AIC que el guardado —222,5 en 2017 y
  246,4 en 2023— y el R² del ganador coincidió hasta la tercera cifra. Cualquier
  reimplementación tiene que seguir dando eso.

#### Lo que queda abierto y no se implementa

Marcar las celdas cuyo signo no es estable entre los modelos que contienen esa
variable. **Mateo decidió no incluirlo por ahora.** El argumento, por si se retoma: en
2023, nueve de las doce variables cambian de signo según compañía, y una mediana de
+0,11 sobre valores que van de −0,251 a +0,600 se lee como «ligeramente positivo»,
que es una afirmación que los modelos no sostienen. Las tres que no cambian de signo
son cámaras, TransMilenio y parque urbano, y dos de esas tres son las que ganaron.

### 14.3 Los dos cambios del 2026-10-02, decididos y sin implementar

Decididos por Mateo. **D56 y D57** en `docs/design-decisions.md`.

#### A. Torca sale de las regresiones

**`UPL07`, Torca, no entra en la etapa de regresión.** Los modelos se ajustan sobre
**veintinueve unidades**. El resto del *pipeline* la conserva entera: la matriz, ρ, las
predictoras, la exposición, la población y los mapas siguen con las treinta.

**La justificación que va al documento es la trayectoria de la población, no la
dispersión.** La población de Torca se multiplica por **4,61** entre 2012 y 2024 —26 206
a 120 770— contra una mediana de 1,09 y un 1,35 de la siguiente unidad. Como toda
especificación divide por una exposición o por la población, el denominador ahí no hace
lo que hace en las demás, y en trece años Torca no es dos veces la misma unidad. Excluir
una unidad por tener valores bajos es objetable; excluirla porque su denominador quintuplica
no lo es. El detalle está en D56.

**Dónde va el filtro: `build_dataset`, en la línea 174**, donde nacen las unidades de la
rejilla:

```python
units = sorted(predictors[config.AREA_CODE_COL].unique())
```

Ahí, y en ningún otro sitio. Es el único punto por el que pasan todas las unidades de la
etapa, así que filtrando ahí la rejilla, los ceros medidos, el conteo de
`eligible_pairs`, la búsqueda, los coeficientes, la frecuencia de selección y las
figuras ven las mismas veintinueve. **Un filtro más abajo dejaría el umbral de
elegibilidad juzgado sobre treinta y todo lo demás sobre veintinueve**, que es
exactamente la incoherencia que D56 existe para evitar.

**Hace falta una constante declarada**, al lado del universo del estudio y con su razón
escrita, no un literal `"UPL07"` dentro de la función. El día que se proponga una
segunda unidad el cambio tiene que ser añadir un elemento a una lista.

**Y hay que registrarlo en la bitácora de la corrida.** `log.record` de ese paso ya
cuenta la rejilla como `n unidades x 8 parejas x 13 años`; tiene que decir además qué
unidad se excluyó y por qué, para que una corrida vieja y una nueva se distingan sin
leer el código.

**Qué más hay que cambiar, y esto es lo que se olvida:**

- **Cada pie de figura de regresión que diga «treinta»**, que son los mismos sitios que
  14.2 listaba para las tres de dispersión, más los de observado contra predicho, más la
  tabla maestra de modelos. El número es ahora veintinueve **en las figuras de
  regresión y sólo en ellas**.
- **Las figuras de las once predictoras conservan las treinta**, al contrario de lo que
  pedía el punto 2 de 14.2. Describen los datos y no la estimación, y ahora los dos
  conjuntos son de verdad distintos.
- **Los grados de libertad.** Veintinueve filas y hasta tres predictoras más la
  constante. Sigue estando bien, pero el margen es menor y conviene que la bitácora lo
  diga.

**Todo lo citado de `run_20260928_112330` queda superado el día que esto corra.** Cada
coeficiente, cada AIC, cada R², cada Moran y cada selección cambian al quitar una
observación. **Los ganadores también pueden cambiar**: en 2017 el margen con el
subcampeón era de 0,2 puntos de AIC.

#### B. R² y AIC en los cuatro paneles de ajuste

Hoy los paneles de observado contra predicho muestran **R² en mínimos cuadrados** y
**AIC en los GLM**, y Moran en los dos. Pasan a mostrar **R² y AIC en todos**.

El sitio es la bifurcación de `_render_fit`:

```python
if family == config.OLS_FAMILY:
    goodness = _count_r_squared(observed, predicted)
    label = f"R² {goodness:.3f}".replace("-", "−")
else:
    label, label_colour = f"AIC {float(row['AIC'].iloc[0]):.0f}", "#555555"
```

**El comentario que hay ahí mismo es la advertencia que hay que atender, no borrar:**
mínimos cuadrados ajusta la tasa, así que su AIC está en la tasa, y el del GLM está en
el conteo. Imprimir los dos sin decirlo hace que dos cifras parezcan comparables cuando
no lo son, y eso es peor que mostrar una sola. **El pie tiene que repetir lo que ya dice
`modelos.png`: el AIC compara dentro de una familia y un offset, nunca entre ellos.**

**El R² sí compara entre los cuatro paneles**, porque está sobre conteos en los dos
casos: mínimos cuadrados multiplica su predicción por la exposición antes de comparar.
Esa es la razón de que sea lo correcto para poner en todas partes, y conviene que el pie
lo diga en una frase.

**Y `predict`, no `fittedvalues`**, para el R² de la binomial negativa: `fittedvalues`
devuelve el predictor lineal y da un R² de −4,67 idéntico en toda la columna. Es el error
de 14.1 y ya mordió una vez.

**Moran sale, decidido el 2026-10-02.** No se dibuja. Sigue en
`analysis__regression_models.csv`, en el informe de verificación y en la tabla maestra de
modelos, así que la etapa del panel lo tiene donde lo va a leer; lo que desaparece es una
cifra impresa sobre una nube.

#### Lo que vieron las dos figuras preliminares

En `tmp/ajustes_r2_aic/`, las dos de 2024 que Mateo señaló, con
`tmp/ajuste_r2_y_aic.py`. El cambio funciona y deja a la vista una cosa que el pie tiene
que responder.

**El AIC de mínimos cuadrados es negativo**, entre −1 048 y −291 en toda la corrida,
porque ajusta la tasa y la tasa es pequeña. Quien sepa que un AIC más bajo es mejor leerá
−398 como el mejor panel de los ocho.

**Y en 2024 ese panel es el peor.** Peatones-Automóvil tiene el AIC más bajo de sus ocho,
−398, y el R² más bajo de sus ocho, −0,794, dibujado en rojo. Las dos cifras apuntan en
sentidos opuestos sobre el mismo panel, y la nube le da la razón al R².

**No es un defecto del cambio: son dos cantidades que responden preguntas distintas.**
Medido sobre las 39 figuras de cada familia, el rho de Spearman entre R² y AIC a lo largo
de los ocho paneles tiene mediana **+0,02 en la binomial negativa y −0,14 en mínimos
cuadrados**, y las dos ordenan **al revés en cerca de la mitad de las figuras**, 20 de 39
y 19 de 39.

**Y el fondo es que el AIC entre los ocho paneles no es una comparación.** Cada panel es
una pareja distinta, o sea otra respuesta sobre otros datos, y el AIC sólo compara
modelos ajustados a las mismas observaciones. El de un panel informa frente a los otros
candidatos **de esa pareja**, que la figura no muestra. Ya pasaba en los GLM, que siempre
han impreso AIC; el cambio dobla la superficie y añade los valores negativos.

**Por eso la figura lleva una tercera línea de título**, que es parte del cambio:

> R² sobre conteos, que es la nube dibujada · AIC en la escala que cada familia ajusta, y
> sólo comparable contra otros modelos de la misma pareja

**El R² sí compara entre las cuatro familias**, porque está sobre conteos en todas:
mínimos cuadrados multiplica su predicción por la exposición antes de comparar.

### 14.4 El AIC negativo de mínimos cuadrados, verificado

La pregunta la hizo Mateo al ver las figuras preliminares de D57: si el AIC de mínimos
cuadrados sale negativo, ¿cómo sabemos que la búsqueda no está eligiendo las peores
variables por una cuestión de aritmética? `tools/seleccion_por_aic.py` la
responde reajustando fuera del *pipeline* todos los subconjuntos declarados de 104
celdas, 27 632 modelos.

Dentro de esa pregunta hay dos, y tienen respuestas distintas.

#### La aritmética está bien, y no por casualidad

**El signo no puede romper un `argmin`.** El código compara `described.aic < best.aic`,
sin valor absoluto, así que ordena igual con cifras negativas que con positivas. Y el AIC
negativo tiene una causa entendida: mínimos cuadrados ajusta la tasa, la tasa es del
orden de una diezmilésima, y la verosimilitud de una densidad continua sobre valores
pequeños es grande y positiva, de modo que `2k − 2·logL` sale muy por debajo de cero.

**Comprobado además sobre los datos.** A igual número de predictoras el penalizador es
una constante, así que minimizar el AIC tiene que ser maximizar el ajuste; si el signo
estropeara algo, estropearía justo ahí. No lo hace:

| predictoras | modelos | AIC más bajo | mejor ajuste a la tasa | ¿el mismo modelo? |
|---|---:|---:|---:|:--:|
| 2 | 55 | −373,9 (R² 0,2401) | −373,9 (R² 0,2401) | sí |
| 3 | 165 | −376,0 (R² 0,3374) | −376,0 (R² 0,3374) | sí |

Y a lo largo de toda la celda, el AIC más bajo tiene R² sobre la tasa de 0,3374 contra
0,0320 del más alto. **El mecanismo elige el mejor, no el peor.**

#### Pero optimiza la tasa, y el estudio lee conteos

Ésta es la parte que sí encontró algo. El percentil del ganador entre todos los modelos
de su celda, sobre las 104:

| ordenado por | mediana | media | peor | en el decil superior | por debajo de su propia mediana |
|---|---:|---:|---:|---:|---:|
| R² sobre la **tasa**, que es lo que ajusta | 99,5 | 98,1 | 88,8 | 103 de 104 | 0 |
| R² sobre el **conteo**, que es lo que dibuja | 88,3 | 77,8 | **5,9** | 48 de 104 | **14** |

**Sobre lo que ajusta es casi óptimo**: ninguna celda por debajo de su mediana y 103 de
104 en el decil superior. Sobre conteos no, y el desacuerdo no es uniforme: la mediana de
R² sobre conteos que se cede por seguir el AIC es 0,078, pero el peor caso es 2,255.

Las cinco celdas donde más se separan:

| pareja | año | percentil tasa | percentil conteo | R² del ganador | R² del mejor |
|---|---:|---:|---:|---:|---:|
| Automóvil-Automóvil | 2015 | 99,7 | 5,9 | **−0,335** | 0,688 |
| Automóvil-Automóvil | 2014 | 99,5 | 6,4 | **−1,705** | 0,551 |
| Bicicleta-Motocicleta | 2024 | 99,5 | 10,5 | 0,277 | 0,633 |
| Motocicleta-Motocicleta | 2023 | 99,7 | 14,7 | 0,716 | 0,848 |
| Bicicleta-Motocicleta | 2012 | 99,5 | 15,9 | 0,309 | 0,557 |

**Dos de ellas publican un R² negativo teniendo disponible uno de 0,69 y de 0,55.** Son
las dos que un lector de la figura señalaría, y la respuesta correcta no es que el
modelo sea malo sino que está ajustando otra cosa.

#### Por qué pasa, y qué no es

**No es un defecto corregible dentro de mínimos cuadrados ordinarios.** Es la
consecuencia aritmética de que el método no admite offset: la única manera de meter la
exposición es dividir la respuesta por ella, y entonces la suma de cuadrados pesa a todas
las unidades por igual en el espacio de la tasa. En el espacio del conteo esas mismas
unidades pesan por la exposición al cuadrado, y la exposición abarca un factor de 171
entre unidades. Las dos sumas de cuadrados no se minimizan con el mismo modelo, y no hay
razón para que lo hagan.

**Tampoco invalida nada de lo publicado.** Lo que el estudio reporta es el GLM; mínimos
cuadrados entra porque la asesora del panel lo pidió junto al GLM, y el conteo de
selección de D53 se cuenta dentro de una especificación y nunca entre ellas, así que
ninguna cifra mezcla las dos familias.

#### La binomial negativa, que no se podía dar por supuesta

La primera versión de esta comprobación medía sólo mínimos cuadrados, porque la pregunta
venía de su AIC negativo. Eso dejaba sin verificar la familia que el estudio reporta, así
que `tools/seleccion_por_aic.py` mide las dos. **El GLM sale mucho mejor, y no sale
perfecto.**

| | mediana del percentil | peor | bajo su propia mediana | es el máximo exacto |
|---|---:|---:|---:|---:|
| GLM binomial negativa | 97,0 | 14,1 | 3 de 104 | 24 de 104 |
| Mínimos cuadrados | 88,3 | 5,9 | 14 de 104 | 8 de 104 |

En la binomial negativa el R² que se cede por seguir el AIC tiene mediana **0,024** y
peor caso 0,351 —Motocicleta-Motocicleta 2014, 0,089 contra 0,422 disponible—, contra
0,078 y 2,255 en mínimos cuadrados.

**Y hay una razón de fondo por la que ni siquiera el GLM puede dar el máximo.** A tres
predictoras, el modelo de AIC más bajo de esa celda (265,4) **no es** el de mejor R²
(266,7). No es un defecto: el AIC maximiza una verosimilitud con penalización, el R² mide
error cuadrático, y la binomial negativa estima además su propio parámetro de dispersión.
Son dos criterios distintos, así que coinciden a menudo y no por construcción. En
mínimos cuadrados sí coinciden a tamaño fijo, porque ahí la verosimilitud es función
decreciente de la suma de cuadrados y nada más.

**En 80 de 104 celdas del GLM existe un modelo con peor AIC y mejor R² sobre conteos.**
Casi siempre por muy poco, y en tres casos por bastante.

#### Decidido: se declara

**Mateo decidió el 2026-10-02 declararlo y no cambiar el mecanismo.** Ni seleccionar por
R², que rompería la simetría entre familias, ni pesar por la exposición, que dejaría de
ser mínimos cuadrados ordinarios.

**Lo que la declaración tiene que decir, y lo que no puede decir.** No puede decir que la
figura muestre el mejor ajuste posible, porque está medido que no: en 80 de 104 celdas
del GLM y en 96 de 104 de mínimos cuadrados existe otro modelo con mejor R² sobre
conteos. Lo que sí es cierto, y es lo que va:

> La figura muestra el ajuste del modelo que la búsqueda seleccionó por AIC, que no es
> el de mejor R² de su celda. El AIC elige por verosimilitud penalizada y el R² mide
> error cuadrático: son criterios distintos y no tienen por qué coincidir. En la binomial
> negativa el ajuste cedido tiene mediana de 0,024 de R²; en mínimos cuadrados, que ajusta
> la tasa mientras la figura dibuja conteos, la mediana es 0,078 y hay catorce celdas de
> ciento cuatro en que el modelo seleccionado queda por debajo de la mediana de su celda.

Va al pie de las figuras de ajuste y al capítulo de metodología. **Las cifras se vuelven
a medir sobre veintinueve unidades** antes de escribirlas en un entregable.

---

## 15. Lo que entra en la próxima corrida limpia

La lista completa, al 2026-10-02. Nada de esto está implementado. Lo que no aparezca
aquí no cambia.

### 15.1 Lo que cambia los números

**1. Torca fuera de las regresiones.** D56. Filtro en `build_dataset`, donde nacen las
unidades de la rejilla, por constante declarada y no por literal, y registrado en
`log.record` de ese paso. Los modelos pasan a veintinueve unidades. **Todo coeficiente,
AIC, BIC, R², Moran y selección cambian**, y el ganador de una celda puede cambiar.

### 15.2 Lo que cambia las figuras

**2. Los paneles de ajuste llevan R² y AIC, y Moran sale.** D57. La bifurcación por
familia de `_fit_panel` desaparece: las dos cifras en las dos familias, R² arriba y AIC
debajo, el R² negativo en rojo como hasta ahora. Moran deja de dibujarse y **sigue
exportado** en `analysis__regression_models.csv`, en el informe de verificación y en la
tabla maestra. La tercera línea de título es parte del cambio:

> R² sobre conteos, que es la nube dibujada · AIC en la escala que cada familia ajusta, y
> sólo comparable contra otros modelos de la misma pareja

Referencia: `tmp/ajuste_r2_y_aic.py`, aprobado el 2026-10-02.

**3. La tabla de betas poblada reemplaza a `betas.png`.** Punto 3 de 14.2, y la
decisión de reemplazo es del 2026-10-02. **Mismo archivo y misma ruta**,
`parejas/<pareja>/betas.png`: nada que apunte a esa figura se rompe, y no quedan dos
imágenes del mismo coeficiente que puedan verse distintas. Las celdas vacías llevan la
mediana del coeficiente sobre los modelos de ese año que contienen la variable, **sin
paréntesis**; lo que marca a las seleccionadas es un recuadro negro.
**Aplica a todas las especificaciones, mínimos cuadrados incluido**, y ahí es donde
muerde la trampa de 14.1.

**4. La tabla por variable y año, en las dieciocho especificaciones.** Punto 4 de 14.2.
Doce filas ordenadas por AIC, cada una el mejor modelo que contiene esa variable, con su
beta, su AIC, su BIC, su R² y sus acompañantes. Ruta
`parejas/<pareja>/por_anio/variables__<año>.png`.

**El volumen quedó decidido el 2026-10-02: las dieciocho.** Tres familias por dos
conjuntos por tres offsets, y dentro de cada una las ocho parejas y los trece años:

| | |
|---|---:|
| especificaciones | 3 × 2 × 3 = **18** |
| figuras por especificación | 8 × 13 = 104 |
| **figuras nuevas** | **1 872** |

Para dimensionarlo: la corrida entera produce hoy **678** figuras. Con esto pasa a unas
2 550, y `figures/` pasa de 128 MB a unos 420 MB a 157 KB por tabla. No toca el
repositorio, porque `results/` no se versiona.

**Y aquí está lo que decide si esto es barato o es imposible.** La tabla necesita, por
celda, **el mejor modelo que contiene cada candidata**: doce modelos en vez de uno. Eso
**no se recalcula**. La búsqueda ya los ajusta todos —una corrida ajusta 489 448 modelos
y guarda 1 868— así que lo que hay que cambiar es qué se guarda, no qué se calcula:
`search` devuelve, además del ganador, el mejor por cada candidata. Son unas 22 500 filas
retenidas en lugar de 1 872, y cero ajustes nuevos.

**Implementarlo recorriendo las candidatas y reajustando por fuera multiplicaría la
corrida por doce**, y es el error que esta nota existe para evitar.

**5. `boxed_cells` en `_grid_table`.** Punto 5 de 14.2. Hermano de `crossed_cells`.

**6. La redacción de los pies que dicen «treinta».** En las figuras de regresión pasan a
veintinueve: las tres de dispersión, las de observado contra predicho y la tabla maestra
de modelos. **Las figuras de las once predictoras conservan las treinta**, porque
describen los datos y no la estimación.

### 15.3 Lo que no entra, y por qué

- **Marcar las celdas de signo inestable.** Mateo decidió dejarlo fuera. El argumento,
  por si se retoma, está al final de 14.2.
- **Excluir las tres predictoras que `MODEL_PREDICTOR_NAMES` deja fuera.** Olmos aplazó
  la exclusión en la sesión de panel; la constante existe y las regresiones no la leen.
  Sección 5.
- **IPF.** D54, declarada y sin implementar.
- **Cualquier cambio en la selección por AIC.** Decidido el 2026-10-02: se declara y no
  se cambia el mecanismo. Lo que sí entra es la frase, en el pie de las figuras de ajuste
  y en la metodología; la redacción está en 14.4.
- **Por qué los paraderos SITP pierden un tercio de sus selecciones al quitar Torca.**
  **Pendiente declarado**, a resolver cuando los ocho pasos estén hechos y no antes: el
  paso 3 deja disponibles los modelos no ganadores, que es lo que hace falta para
  contestarlo. 16.1 tiene las cuatro cosas que habría que mirar. Mientras tanto, esa
  frecuencia no se cita en un entregable.

### 15.4 Qué verificar después de correr

- **Que la bitácora diga veintinueve** y nombre la unidad excluida.
- **Que la tabla maestra siga teniendo `MORANS_I`** pese a que ninguna figura lo dibuje.
- **Que ninguna mediana de la tabla de betas de mínimos cuadrados se redondee a 0,00**,
  que es cómo se manifiesta la trampa de 14.1.
- **Que `tools/seleccion_por_aic.py` vuelva a dar la misma conclusión** sobre
  veintinueve unidades: la aritmética no debería moverse y los percentiles sí un poco.
- **Que los ganadores se comparen contra los de `run_20260928_112330`** y se anote
  cuántas celdas cambiaron de modelo, porque es la cifra que el comité va a pedir cuando
  se pregunte qué hizo quitar una unidad.

### 15.5 Lo que la comprobación previa encontró, y dónde va el filtro

`tools/exclusion_de_una_unidad.py`, escrito antes de tocar nada. Dos cosas habrían
abortado la corrida y una la habría falseado en silencio.

#### El filtro va en un punto y afecta a dos objetos

`run_pipeline.py` carga `units` en la línea 303 y lo pasa a `fit_all` y a `verify`;
`predictor_table` va por otro lado a `build_dataset`. **Los dos tienen que perder a
Torca**, y el sitio donde eso es una sola decisión es justo después de cargarlos, antes
de construir los conjuntos.

**Qué pasa si sólo se filtra uno**, que es el error fácil:

- **Sólo las predictoras.** `fit_all` construye los pesos de contigüidad desde `units`,
  que seguiría en 30, y `morans_i` hace `centred @ weights @ centred` con 29 residuos
  contra una matriz de 30 × 30. Revienta. Ruidosamente, que es lo bueno.
- **Sólo `units`.** La rejilla se sigue construyendo sobre treinta y la exclusión no
  ocurre, salvo en Moran, que pasaría a calcularse contra los vecinos equivocados.

**`loading.load_territorial_units` no se toca.** Su guarda de treinta unidades es sobre
la capa y tiene que seguir fallando si la capa cambia; lo que se excluye se excluye
después, dentro de la etapa, que es también lo que mantiene a las otras rutas en treinta.

#### La comprobación de `verify` se ajusta sola, y su rótulo no

La línea 1179 compara `models["N_OBSERVATIONS"] != len(units)`, contra la longitud y no
contra un literal, **así que pasa sola si `units` se filtró y falla si no**. Es la red que
atrapa una implementación a medias. Lo que sí hay que cambiar es el rótulo, que dice
«every model was fitted on exactly the thirty units» y tiene que leer la cifra.

#### Torca no aísla a nadie

`contiguity_weights` lanza `ValueError` si alguna unidad se queda sin vecinos, lo que
abortaría la corrida. No pasa:

| | |
|---|---|
| Torca limita con | Toberín y Britalia, nada más |
| Toberín | 3 vecinos → 2 |
| Britalia | 4 → 3 |
| mínimo tras la exclusión | **1 vecino**, ninguna aislada |

#### Ninguna pareja se cae del umbral

`eligible_pairs` juzga con una **proporción** y no con un conteo, así que no se rompe al
cambiar el denominador. Pero la proporción se mueve, y una pareja que cruzara el máximo
dejaría de modelarse sin que nadie lo hubiera decidido. Peor año de cada pareja contra el
máximo declarado de 0,50, en el conjunto observado:

| pareja | con 30 | con 29 |
|---|---:|---:|
| Automóvil-Motocicleta | 0,367 | **0,345** |
| Bicicleta-Motocicleta | 0,100 | 0,103 |
| Motocicleta-Motocicleta | 0,067 | 0,034 |
| Automóvil-Automóvil | 0,067 | 0,069 |
| el resto | ≤ 0,033 | ≤ 0,034 |

Las ocho siguen pasando con holgura, y la peor mejora en vez de empeorar: Torca era una
de las celdas en cero de automóvil contra motocicleta.

#### El texto que queda desfasado

Trece sitios en `src/regressions.py` dicen «thirty» o «treinta», y tres en `tools/`. Los
que importan porque los lee alguien: el *docstring* de `eligible_pairs`, la cabecera de su
tabla de bitácora, el rótulo de `verify`, el pie de la figura de dispersión —«sobre las
mismas treinta unidades»— y el de `comparar_candidatas.py`, que compara dos corridas
«sobre las mismas treinta unidades» y a partir de ahora compara veintinueve.

**Los que hablan del diseño y no de esta corrida se quedan**: que doce candidatas no caben
sobre treinta observaciones, o que la capa trae treinta unidades, siguen siendo ciertos.

## 16. El plan de implementación, paso a paso

Escrito el 2026-10-02, con todo decidido y nada implementado. **Siete pasos, y cada uno
se verifica antes de empezar el siguiente.** El orden no es negociable en un punto: el
paso 3 produce el dato que consumen el 4 y el 5, así que va antes.

**La corrida que importa es `--candidates urban-only`**, que es la que sale sin pedir
nada y la que va a Olmos y a la asesora. Los cambios no distinguen conjunto de
candidatas, así que `with-leftovers` los recibe igual; lo que no puede pasar es que la
verificación se haga sobre ella.

```
.venv/Scripts/python.exe -m src.run_pipeline regressions
```

### Paso 0 — Dos rótulos que D52 dejó al revés — HECHO el 2026-10-02

Ninguno es consecuencia de estos cambios. Se arreglan aquí porque el paso 1 los va a
tener delante y porque un rótulo falso en código publicado no debe sobrevivir a una
sesión que lo vio. **Los dos dicen lo mismo y lo dicen invertido**: que la corrida que el
estudio reporta es la de robustez.

**1. El `--help` de `--candidates`, en `run_pipeline.py`.** Decía que `urban-only` «is a
robustness run and it estimates no elasticity». Desde D52 `urban-only` **es la corrida
que el estudio reporta** y la de robustez es `with-leftovers`. El comentario de
`config.DEFAULT_CANDIDATE_SET` siempre lo tuvo bien y `_write_readme` también —separa
desde D52 cuál reporta el estudio de qué preguntas no tienen respuesta—, así que lo único
que no se siguió fue este texto.

Reescrito separando las dos frases, como hace `_write_readme`: cuál reporta el estudio, y
a qué precio. **En ASCII**, porque era el único texto de `--help` del archivo con un
carácter fuera de ASCII y la consola de Windows lo imprimía como un signo de
interrogación.

**2. El bloque de D50 que enumera las dos corridas**, en `design-decisions.md`. Dice que
«`with-leftovers` is the run the study reports … still the default» y que `urban-only` es
una comprobación de robustez. Era cierto cuando se escribió y D52 lo invirtió sin
marcarlo. **No se reescribe**: la asimetría que describe sigue siendo el punto, y lo que
cada corrida no puede contestar no cambió cuando cambiaron los papeles. Lleva encima una
nota que manda a D52 y dice que los dos nombres se leen al revés, igual que la que D55
lleva desde que la reemplazó D56.

**Verificación, hecha.**

- `python -m src.run_pipeline --help` nombra `urban-only` como la del estudio y
  `with-leftovers` como la de las elasticidades.
- Ninguna cadena de `help=` del archivo tiene caracteres fuera de ASCII. Se comprueba
  sobre las cadenas, no con un `grep` de la palabra: el texto nuevo lleva un comentario
  que explica el defecto y contiene la frase que se corrigió, así que buscar la frase
  encuentra la explicación y no el defecto.
- Quien abra D50 por el índice ve la nota antes que la lista.

### Paso 1 — Torca sale de las regresiones (D56) — HECHO el 2026-10-02

**Una constante declarada**, junto al universo del estudio y con su razón escrita —la
población se multiplica por 4,61 entre 2012 y 2024 contra una mediana de 1,09—, no un
literal dentro de una función. Hermana en espíritu de `POPULATION_UNITS_OUTSIDE_STUDY`,
que ya existe y significa otra cosa: aquélla son unidades fuera del estudio, ésta es una
unidad dentro del estudio y fuera de la estimación. El nombre tiene que impedir
confundirlas.

**El filtro se aplica una vez y alcanza dos objetos.** En `run_pipeline.py`, después de
`loading.load_territorial_units` y de `read_inputs`, y antes de `build_dataset`: a
`units` y a `predictor_table`. Las razones están medidas en 15.5 y se repiten aquí porque
son la trampa del paso: filtrar sólo las predictoras revienta en `morans_i` por forma;
filtrar sólo `units` no excluye nada salvo en Moran, que pasa a calcularse contra los
vecinos equivocados **sin error**.

**`loading.load_territorial_units` no se toca.** Su guarda de treinta es sobre la capa y
tiene que seguir fallando si la capa cambia.

**La bitácora tiene que decirlo.** `log.record` del ensamblado ya cuenta la rejilla; añade
qué unidad se excluyó y por qué, para que una corrida vieja y una nueva se distingan sin
leer el código.

**Verificación.**

- La bitácora dice `29 units x 8 pairs x 13 years` y nombra a Torca.
- `verify` pasa entero. Su comprobación de `N_OBSERVATIONS != len(units)` se ajusta sola
  si el filtro llegó a `units`, y falla si no: **es la red que atrapa media
  implementación, y verla pasar es parte del paso.**
- `analysis__regression_models.csv`: `N_OBSERVATIONS` vale 29 en todas las filas, y
  `MORANS_I` es finito en todas.
- `UPL07` no aparece en ninguna tabla de la carpeta `data/` de la corrida salvo donde
  deba: la matriz, ρ, la exposición, la población y las predictoras la conservan.
- Las ocho parejas siguen modelándose. `tools/exclusion_de_una_unidad.py` lo predijo
  —la peor pasa de 0,367 a 0,345 contra un máximo de 0,50— y la bitácora lo confirma.

#### Hecho, y qué hizo falta además de lo planeado

**Corrida `run_20261002_094610`**, `urban-only`, dieciocho minutos. Las seis
comprobaciones pasan y `verify` pasa entero: sus veinte comprobaciones en OK, incluida
«every model was fitted on exactly the 29 units that enter», que es la que delata media
implementación.

Cómo quedó: `UnitExclusion` y `REGRESSION_EXCLUDED_UNITS` en `config`, siguiendo el
patrón de `PredictorExclusion`; `regressions.exclude_units`, que filtra los dos objetos y
falla si una unidad declarada no está en ambos; y una línea en `run_pipeline.py` entre
cargar y construir.

**Tres rótulos se corrigieron aquí y no en el paso 7**, porque son de lo que este paso
vuelve falso y dejarlos habría hecho que la verificación del propio paso imprimiera
«the thirty units» mostrando 29: el *docstring* de `eligible_pairs`, la cabecera de su
tabla de bitácora —que ahora lee la cifra en vez de escribirla— y el rótulo de `verify`.

**Un defecto propio, atrapado antes de correr.** La primera versión pasaba `changes=[]` a
`log.record` con treinta entrando y veintinueve saliendo. `log.record` exige que los
cambios expliquen la diferencia de filas, así que **habría detenido la corrida**. Ahora
pasa un delta firmado por unidad excluida, que es lo que hace cerrar el balance.

Lo predicho por `tools/exclusion_de_una_unidad.py` se cumplió: ninguna unidad quedó
aislada y `CAR__MOTORCYCLE`, la peor del umbral, salió en 0,34 contra el 0,345 previsto.

### 16.1 Lo que quitar una unidad movió, que es más de lo que esperábamos

`tools/efecto_de_la_exclusion.py`, sobre las dos corridas del mismo conjunto de
candidatas. Es la cifra que §15.4 pedía y que el comité va a pedir.

#### El ganador de una celda no es un objeto estable

**Cambió en 563 de 1 868 celdas, el 30,1 %.**

| familia | celdas | cambian | |
|---|---:|---:|---:|
| Mínimos cuadrados | 624 | 255 | **40,9 %** |
| GLM binomial negativa | 620 | 222 | 35,8 % |
| GLM Poisson | 624 | 86 | 13,8 % |

**No es un defecto de la implementación ni una consecuencia de Torca en particular.** Es
lo que le pasa a una búsqueda por AIC sobre 220 o 286 candidatos con veintinueve o
treinta observaciones: el paisaje del AIC es plano cerca del mínimo, y quitar una
observación basta para que gane otro. Poisson se mueve mucho menos porque no estima un
parámetro de dispersión y sus diferencias de AIC son mayores, así que su mínimo está
mejor separado.

**Esto pertenece a la metodología y no a una nota al pie.** Dice que el modelo ganador de
una celda es una elección entre casi-empates, que es exactamente lo que D59 ya declara
sobre el R² y lo que D53 dio por supuesto sin medirlo.

#### Lo que el estudio reporta sí es estable, y ahora está medido

D53 dice que lo que se lee es **cuántas veces se selecciona una variable dentro de una
especificación**, no qué ganó una celda. Esa distinción deja de ser un argumento y pasa a
ser una medición:

- El orden de las doce candidatas por frecuencia tiene **rho de Spearman de mediana
  +0,943** dentro de cada especificación, entre +0,818 y +0,988, y **las dieciocho están
  por encima de 0,8**.
- La variable más seleccionada es la misma en 14 de las 18.
- Sobre el total, **rho +0,986 y ningún desplazamiento mayor de un puesto de doce**. Las
  cuatro primeras no se mueven: andén, cruces peatonales, vía arterial, cámaras.

**Un recuento sobre 104 celdas es estable aunque sus sumandos no lo sean**, y ésa es la
razón de D53 escrita con cifras en vez de con un argumento.

#### La que sí se movió — PENDIENTE, se resuelve al terminar los ocho pasos

**Paraderos SITP pierde un 34 % de sus selecciones**, de 307 a 202, y es la única con un
cambio de esa magnitud. Baja un puesto. Parque urbano pierde un 16 %, arbolado gana un
14 % y señalización vertical un 17 %; el resto se mueve menos de un diez por ciento.

**Que una variable dependa en un tercio de una sola unidad de veintinueve no lo explica
la inestabilidad general.** Si el ganador cambia en el 30 % de las celdas por un paisaje
de AIC plano, los cambios deberían repartirse entre las doce candidatas, y aquí hay una
que se lleva una parte desproporcionada. Eso apunta a algo de la variable y no de la
búsqueda.

**Mateo lo dejó marcado el 2026-10-02 como pendiente a resolver cuando los ocho pasos
estén hechos**, no antes: resolverlo ahora obligaría a rehacerlo cuando los pasos 3 a 7
cambien lo que la corrida guarda, y el paso 3 en particular deja disponibles los modelos
no ganadores, que es justo lo que hace falta para contestarlo bien.

**Qué habría que mirar, para no empezar de cero:**

- **Si Torca era atípica en la variable misma.** La densidad de paraderos de una unidad
  de borde en expansión no tiene por qué parecerse a la del resto, y si lo era, su
  ausencia cambia la desviación con que se estandariza y por tanto el coeficiente de
  todas las unidades.
- **Con quién competía.** Si los paraderos ganaban casi siempre en compañía de una
  variable concreta, y esa pareja dependía de Torca, la pérdida está en la pareja y no en
  la variable.
- **En qué especificaciones cayó.** 34 % sobre el total puede ser una caída repartida o
  un desplome en dos o tres de las dieciocho, y las dos cosas significan lo contrario.
- **Si cae también la frecuencia en la corrida `with-leftovers`**, donde compite contra
  las cantidades del offset. Si allí no cae, la causa está en la competencia y no en la
  unidad.

**Hasta que esto se resuelva, no citar la frecuencia de selección de los paraderos SITP
en un entregable.** Las otras once no tienen este problema.

### Paso 2 — Los paneles de ajuste: R² y AIC, sin Moran (D57, D59) — HECHO el 2026-10-02

**`_panel_grid` gana un parámetro `note`**, hermano del que `_grid_table` ya tiene. La
declaración de D59 es un párrafo y no cabe en un título que ya lleva tres líneas; sin
zona de pie no hay dónde ponerla, y ése es el motivo del parámetro.

**La bifurcación por familia de `_fit_panel` desaparece.** R² arriba, AIC debajo, en las
tres familias. El R² negativo sigue en rojo, porque no es un valor pequeño sino un modelo
que predice peor que la media. Moran deja de dibujarse.

**El título lleva su tercera línea** y el pie lleva la declaración de D59, las dos
aprobadas y transcritas en 14.3 y en D59.

**Verificación.**

- Ninguna figura de `ajustes/` contiene la palabra Moran. Se comprueba sobre la figura
  generada, no sobre el código.
- `MORANS_I` sigue en `analysis__regression_models.csv` y en la tabla maestra de modelos,
  que es donde la etapa del panel lo va a leer.
- Las dos figuras de 2024 de la corrida nueva se parecen a las preliminares de
  `tmp/ajustes_r2_aic/` en todo menos en las cifras, que cambian porque ahora son 29
  unidades.
- El R² de la binomial negativa se calcula con `predict` y no con `fittedvalues`. Si
  saliera −4,67 idéntico en toda una columna, es eso.

#### Hecho, y qué salió distinto de lo planeado

**Corrida `run_20261002_101820`**, veintidós minutos. Las 234 figuras de ajuste —dieciocho
especificaciones por trece años— con R² arriba, AIC debajo y sin Moran. `MORANS_I` sigue
en las 1 868 filas de la tabla de modelos y las 144 tablas maestras se siguen generando.

**`_panel_grid` no necesitó el parámetro `note` que el plan pedía.** Ya existía
`_figure_note(figure, texto)`, que es lo mismo y lo usan las figuras de dispersión. Se
reutiliza, con `tight_layout(rect=(0, 0.10, 1, 1))` para dejarle sitio, que es el mismo
rectángulo que usan ellas.

**Las cifras de D59 se midieron sobre veintinueve antes de escribirlas**, en vez de poner
las de treinta y volver en el paso 8. Para eso `tools/seleccion_por_aic.py` toma ahora la
corrida por la línea de órdenes:

| | 30 unidades | 29 unidades |
|---|---:|---:|
| binomial negativa, mediana de R² cedida | 0,024 | **0,026** |
| mínimos cuadrados, mediana de R² cedida | 0,078 | **0,073** |
| celdas por debajo de su propia mediana | 14 de 104 | **12 de 104** |

**Cinco rótulos de figura más**, que el paso 1 volvió falsos y que son de figuras y no de
prosa, así que se arreglaron aquí y no en el paso 7: el *docstring* y el pie de
`_render_dispersion`, el `suptitle` de la figura de series anuales, y los dos de
`_beta_heatmap`. Los tres primeros **leen ahora la cifra de los datos en vez de
escribirla**, que es lo que los había dejado atrás. Los de `_beta_heatmap` quedaron sin
cifra, porque la tabla de coeficientes no lleva el código de unidad y no hay de dónde
leerla; su pie se reescribe entero en el paso 5.

**Un fallo del verificador, no del *pipeline*.** La primera comprobación dio «78 de 234» y
el *pipeline* estaba bien: `FAMILY_PATHS` da `minimos-cuadrados` para una familia y
`glm/binomial-negativa` para otra, o sea uno y dos segmentos de ruta, así que un patrón
de profundidad fija sólo encontraba mínimos cuadrados. Con `rglob` salen las 234. **Es la
tercera vez que un número que empeora resulta ser el instrumento**, y la regla de
`contar-nunca-desde-el-shell` vale igual para un glob.

### Paso 3 — Dejar de botar los modelos que ya se ajustan — HECHO el 2026-10-02

**Es el paso que hace posibles el 4 y el 5, y el único con riesgo de coste.** La tabla
poblada y la tabla por variable necesitan, por celda, **el mejor modelo que contiene cada
candidata**. Esos modelos ya se ajustan: una corrida ajusta 489 448 y guarda 1 868.

**`search` devuelve, además del ganador y del nulo, el mejor por cada candidata.** Un
diccionario de nombre a `Fitted`, llenado dentro del bucle que ya existe, sin un solo
ajuste nuevo.

> **Corregido el 2026-10-02, al llegar al paso 5: esto no basta.** Tal como estaba escrito,
> este paso afirmaba que las dos figuras necesitan «el mejor modelo que contiene cada
> candidata», y eso es cierto para la tabla por variable del paso 6 y **falso para la tabla
> de betas**, que según 14.2 y 15.2 lleva **la mediana sobre los 55 o 66 modelos** que
> contienen la variable. Son dos cantidades distintas: el mejor modelo dice dónde la
> variable rinde más, la mediana dice cuánto vale cuando entra. `search` acumula además
> cada coeficiente en una lista por candidata —sigue sin ajustar nada nuevo— y `fit_cell`
> guarda la mediana, el mínimo, el máximo y cuántos modelos la contienen. De ahí sale una tabla más, al lado de `models`, `coefficients` y
`predictions`, con una fila por celda y candidata: unas 22 500 en vez de 1 872.

**Implementarlo recorriendo las candidatas y reajustando por fuera multiplica la corrida
por doce.** Es el error que este paso existe para no cometer.

**La bifurcación por familia de 14.1 vive aquí**, no en las figuras: la tabla guarda el
coeficiente crudo y el que se dibuja, como ya hace `coefficients`, para que ninguna
figura tenga que acordarse.

**Verificación.**

- La tabla nueva tiene exactamente una fila por celda y candidata disponible ese año:
  doce en los años con señalización vertical y once en los cuatro que no la alcanzan.
- **Ninguna fila tiene AIC menor que el del ganador de su celda.** Si alguna lo tuviera,
  el ganador no sería el ganador y el error está en el paso 3 o en la búsqueda.
- Para las dos o tres candidatas que sí entraron, el AIC de la fila **es** el del ganador,
  porque el mejor modelo que las contiene es ése.
- **El tiempo de corrida no se dispara.** Se mide contra el de la corrida anterior; un
  factor cercano a doce significa que se está reajustando.

#### Hecho, y lo que la tabla trajo consigo

**Corrida `run_20261002_111025`.** `search` devuelve `per_candidate` llenado dentro del
bucle que ya existía, `fit_cell` arma las filas y `export` escribe
`analysis__regression_candidate_models.csv`, 8,8 MB y **21 842 filas**.

**El coste es el que se prometió.** La corrida pasa de 22,2 a **22,4 minutos**, un uno
por ciento, y la bitácora lo dice en sus propios términos: «21 834 per-candidate best
model(s) retained out of the same 489 503 fits, with no refitting». Una prueba de humo
antes de correr había medido 220 modelos en 0,60 s, idéntico a los 0,6 s de antes del
cambio.

**`verify` gana cuatro comprobaciones** y las cuatro pasan: el recuento exacto, que
ninguna candidata le gane al ganador, que toda seleccionada tenga modelo, y que el mejor
modelo de una seleccionada **sea** el ganador —5 202 de 5 202, contra los 5 202 términos
de la tabla de modelos—.

#### Las ocho filas sin modelo, que no se saltan

La primera corrida dio 21 834 de 21 842. Las ocho faltantes son todas de `CAR__CAR` con
el offset de ambas exposiciones y binomial negativa, en celdas donde el estimador no
ajusta 204 de 220 especificaciones, o 273 de 286; para cruces peatonales, paraderos SITP
y parque urbano, todos los modelos que las contienen están entre los fallos.

**La ausencia es legítima y saltársela no.** En una tabla que lee una figura, «no se pudo
ajustar ningún modelo» y «no fue seleccionada» habrían quedado indistinguibles, que es el
defecto que D10 arregló para la matriz. La fila se emite con la identidad,
`HAS_FITTED_MODEL = False` y **ninguna cifra**, para que nada pueda leerse como una
medición, y el paso 6 podrá marcar esas celdas como el mapa de betas marca las aspas.

La cuarta comprobación salió de aquí: **toda candidata seleccionada tiene que tener
modelo**. Una seleccionada sin él no sería un vacío sino una contradicción, porque el
ganador mismo la contiene.

#### La trampa de 14.1, ahora con su cifra exacta

De los coeficientes de mínimos cuadrados de esta tabla, **7 296 de 7 296 se redondearían
a «0,00»** en una tabla de dos decimales. El que la figura va a dibujar, el totalmente
estandarizado, lo hace en 104.

**Por eso la bifurcación vive en la tabla y no en las figuras.** `COEFFICIENT_FULLY_STANDARDISED`
llega llena en las 7 296 filas de mínimos cuadrados y **nula en las 14 538 de los GLM**,
que es D51: el coeficiente del GLM ya es adimensional y dividirlo rompería su
significado, así que llega nulo y no cero, que se leería como una medición.

#### Comprobado además, fuera de `verify`

- Las ocho filas sin modelo no llevan cifra en ninguna de sus siete columnas numéricas.
- El beta de una seleccionada **coincide exactamente** con el de la tabla de coeficientes
  que el estudio ya reportaba: 5 202 de 5 202, diferencia máxima cero.
- El R² sobre conteos de una fila seleccionada **es el que el panel de ajuste imprime**:
  200 modelos comprobados, diferencia máxima 3·10⁻¹⁶.

### Paso 4 — `boxed_cells` en `_grid_table` — HECHO el 2026-10-02

Un parámetro hermano de `crossed_cells` que dibuja un rectángulo negro en las celdas
indicadas, por encima del relleno y sin taparlo. Con él desaparecen las doce líneas de
envoltura de `tmp/betas_pobladas.py`.

**Verificación.** Una figura cualquiera con celdas marcadas: el recuadro se ve, el color
de fondo se sigue viendo debajo, y el aspa y el recuadro no se estorban si coinciden.

#### Hecho

Un parámetro hermano de `crossed_cells`, y con él desaparecen las doce líneas de
envoltura de `tmp/betas_pobladas.py`.

**Es un contorno y no un relleno**, y eso es el diseño: el color dice el signo y la
magnitud, el recuadro dice cuál eligió la búsqueda, y un lector tiene que poder leer los
dos a la vez.

**Va por dentro del borde de la celda y no sobre él.** Sobre el borde caería encima de la
retícula blanca que separa las celdas, y dos celdas recuadradas vecinas compartirían un
trazo: se leerían como un bloque de dos en lugar de como dos marcas. Por dentro, cada una
conserva su cuadro, que es lo que la prueba comprobó en horizontal y en vertical.

**`GRID_BOX_COLOR` es casi negro, al contrario que `GRID_CROSS_COLOR`**, que es gris. No
es una elección de gusto: el aspa dice «aquí no hay nada» y tiene que ceder el paso a las
cifras de alrededor, y el recuadro dice «ésta es la cifra» y tiene que ganarle a la
cuadrícula y al color de fondo.

**`import matplotlib.patches` explícito.** `import matplotlib` a secas no trae el
submódulo, y `matplotlib.patches.Rectangle` habría fallado sólo el día que una tabla
recuadrara una celda — es decir, en el paso 5 y no aquí.

#### Qué se probó, y a qué escala

En `tmp/paso4/`, con `tmp/verifica_paso4.py` y `tmp/paso4_escala.py`. El recuadro se puso
a propósito encima de cada cosa que podía estorbarlo: sombra oscura y sombra clara, una
celda con aspa, dos vecinas en horizontal y dos en vertical, y una fila atenuada. Ninguna
combinación rompe el dibujo ni tapa la cifra.

**Y luego a la escala de verdad**, doce candidatas por trece años con dos o tres
recuadros por columna, que es la forma que tendrá la figura del paso 5. Una tabla de
cuatro columnas no prueba nada sobre una de trece: la celda es mucho más pequeña y el
grosor que se lee bien en una se lee como un borrón en la otra. A escala real el
recuadro se distingue contra el azul más oscuro y contra el rojo profundo con texto
blanco, y las vecinas conservan su cuadro.

**La llamada sin el parámetro se probó aparte**, porque es como la hacen todas las
figuras de hoy. Y la corrida `run_20261002_113737` lo confirmó del modo más fuerte que
hay: **las 678 figuras salieron idénticas byte a byte** a las de la corrida del paso 3,
con cero comprobaciones en fallo. Añadir el parámetro no movió un píxel de lo que ya
existía.

### Paso 5 — `betas.png` pasa a ser la tabla poblada (D58 y punto 3 de 14.2) — HECHO el 2026-10-02

**Reemplaza, no convive.** Decidido por Mateo el 2026-10-02. Mismo archivo y misma ruta,
`parejas/<pareja>/betas.png`, así que nada que apunte a esa figura se rompe y no hay dos
imágenes del mismo coeficiente que puedan verse distintas.

Lo que cambia dentro de `_beta_heatmap`:

- Las celdas hoy vacías llevan **la mediana del coeficiente sobre los modelos de ese año
  que contienen esa variable**, 55 o 66 según el año. **Sin paréntesis**: es la misma
  clase de cantidad y el paréntesis marcaba lo que no era.
- Lo que distingue a las seleccionadas es **el recuadro negro** del paso 4.
- El aspa se queda tal cual: la variable no tenía capa ese año.
- El pie cambia entero, porque el que hay explica una celda vacía que ya no existe.
- **La fuente de datos deja de ser sólo `coefficients`** y pasa a ser también la tabla
  del paso 3.

**Verificación.**

- **Ninguna celda de mínimos cuadrados se redondea a «0,00».** Es la trampa de 14.1 y
  ésta es la figura donde muerde: las recuadradas vienen del CSV y saldrían bien, así que
  sólo las demás serían cero, y eso se lee como «lo que no entró no vale nada».
- El número de celdas recuadradas de una figura coincide con el número de términos que
  `coefficients` tiene para esa pareja y especificación.
- No queda ninguna celda vacía salvo donde el modelo de ese año no pudo ajustarse.
- La figura de la binomial negativa con offset de exposición del modo se parece a
  `tmp/tabla_variables/.../betas__tabla_completa.png`, salvo en las cifras.

#### Hecho

**Corrida `run_20261002_120408`**, cero comprobaciones en fallo. **Sólo cambiaron las 144
`betas.png`** —dieciocho especificaciones por ocho parejas— y las otras 534 figuras
salieron idénticas byte a byte.

**Los 5 202 recuadros cuadran con los 5 202 términos seleccionados**, figura por figura:
144 comparadas, cero diferencias, entre 28 y 39 recuadros por figura.

#### Lo que la celda dice ahora, que son cuatro cosas y antes eran tres

- **cifra y recuadro**, entró, y es el coeficiente que el estudio reporta;
- **cifra sin recuadro**, compitió y no entró, y es la mediana sobre los modelos que la
  contienen;
- **raya**, ningún modelo que la contuviera pudo ajustarse;
- **aspa**, no tenía capa ese año.

La tercera no se dibuja con un aspa aunque también sea una ausencia: «no había capa» y
«no se pudo ajustar» son cosas distintas y juntarlas mentiría sobre la segunda.

**Lo que esto resuelve y que la figura anterior no podía:** una fila entera en gris decía
que la variable compitió siempre y no ganó nunca, y se leía como «no vale nada». Ahora
lleva sus trece medianas. En la binomial negativa de peatones contra motocicleta, la fila
de semáforos sostiene entre +0,10 y +0,23 en los trece años **sin ganar ni uno**, y eso
es un resultado que antes era una fila en blanco.

#### `_plotted_median`, hermana de `_plotted_coefficient`

La bifurcación de D51 la decide una función y no cada figura. Existe aparte y no como un
cuarto valor de aquélla porque aquélla devuelve tres columnas que salen juntas —el punto
y los dos extremos de su intervalo— y **una mediana de coeficientes no tiene intervalo**:
no hay contraste detrás, y por eso tampoco lleva asterisco.

**Medido sobre la corrida:** de las 7 296 medianas de mínimos cuadrados, **las 7 296 se
redondearían a «0,00»** en su escala cruda, y 105 en la que la figura dibuja. En los GLM
la columna dividida llega **nula en las 14 538**, que es D51. Si una figura hubiera
elegido la columna por su cuenta, mínimos cuadrados habría pintado bien las celdas
recuadradas y todas las demás en cero, que se lee como «lo que no entró no vale nada».

#### Tres columnas que no dibuja nadie todavía

`COEFFICIENT_MIN_STANDARDISED`, `COEFFICIENT_MAX_STANDARDISED` y
`SIGN_CHANGES_ACROSS_MODELS` entran en la tabla aunque ninguna figura las use: marcar los
signos inestables se propuso y Mateo lo dejó fuera. Los valores ya estaban en la mano y
tirarlos es lo que este paso existe para dejar de hacer, y son exactamente lo que hace
falta para el pendiente de los paraderos SITP de 16.1.

**Lo que dicen ya, de paso: 14 361 de 21 834 candidatas cambian de signo** según con
quién estén en el modelo. Es el 66 %, y da la medida de qué significa una mediana ahí.

### Paso 6 — La tabla por variable y año, en las dieciocho (D58) — HECHO el 2026-10-02

`render_figures` ya recorre familia × conjunto × offset × pareja, que son las dieciocho
especificaciones por sus ocho parejas. Añadir la figura es añadir el bucle de años
dentro: 18 × 8 × 13 = **1 872**.

Doce filas, una por candidata, ordenadas por AIC; cada fila es el mejor modelo que la
contiene, con su beta, su AIC, su BIC, su R² y sus acompañantes. Las filas del modelo
ganador van sombreadas y comparten AIC porque son el mismo modelo. Ruta
`parejas/<pareja>/por_anio/variables__<año>.png`, que reutiliza el patrón `por_anio/` de
`entradas/predictoras/`.

**El pie repite que AIC y BIC no se comparan entre familias**, igual que hace
`modelos.png`.

**Verificación.**

- `find ... -name 'variables__*.png' | wc -l` da **1 872**.
- Ninguna fila se sale de su celda. Ya pasó una vez, en 2023, con la fila de semáforos.
- Las figuras de 2017 y 2023 de la especificación de ejemplo se parecen a las de
  `tmp/tabla_variables/`, salvo en las cifras.
- `figures/` pesa del orden de 420 MB y la corrida produce unas 2 550 figuras.

#### Hecho

**Corrida `run_20261002_131557`**, cero comprobaciones en fallo. **1 872 de 1 872**, y de
la corrida anterior no cambió ni una figura: las cuatro de diferencia son las cuatro
nuevas y ninguna otra se movió.

`_variables_table` lee `candidate_models` y no reajusta nada. La llamada va dentro del
bucle de parejas que ya recorría las dieciocho especificaciones, así que añadir la figura
fue añadir los trece años.

#### El coste, que es el precio de las dieciocho

| | antes | después |
|---|---:|---:|
| corrida | 22,4 min | **39,9 min** |
| figuras | 678 | **2 550** |
| `figures/` | 128 MB | **434 MB** |

Medido antes de lanzarla: 0,56 s por figura, que sobre 1 872 son dieciocho minutos. No
hay forma de bajarlo sin reducir el alcance.

#### Las cuatro celdas sin modelo, que ahora tienen figura

La primera corrida dio **1 868 de 1 872**. Las cuatro son celdas donde **ninguna** de las
220 o 286 especificaciones pudo ajustarse: automóvil contra automóvil bajo las dos
exposiciones, binomial negativa, 2014 y 2015, en los dos conjuntos. La bitácora ya avisa
de cada una.

**El criterio de verificación estaba mal, no el *pipeline*.** 1 872 es 18 × 8 × 13, pero
la tabla de modelos tiene 1 868 filas justamente por esas cuatro. Es la cuarta vez en esta
sesión que un número que parece empeorar resulta ser el instrumento.

**Aun así se dibujan.** Una carpeta con doce años en vez de trece deja al lector deducir
el motivo, y `_fit_panel` ya pone «sin modelo» en su panel para el mismo caso. La figura
dice que no hay nada y explica por qué —el estimador no convergió, o lo hizo sin errores
estándar, que es lo mismo que no ajustar porque el coeficiente llegaría sin intervalo ni
valor p— y aclara que la pareja sí tiene datos ese año y que las otras dos familias sí la
ajustan. Con eso el recuento es exactamente 1 872 y la comprobación deja de necesitar una
excepción.

**Un error de orden que hubo que corregir:** la primera versión del marcador no llegaba a
dibujarse nunca. La función miraba primero la tabla por candidata, y una celda sin ningún
modelo tampoco tiene filas ahí, así que salía por la guarda equivocada. Ahora mira la
tabla de modelos primero, y el comentario lo dice para que nadie las reordene.

#### Lo que la figura enseña y ninguna otra enseñaba

En peatones contra motocicleta de 2023, binomial negativa con exposición del modo: el
ganador son dos variables —cámaras y TransMilenio— y **el margen con la siguiente fila es
de 0,3 puntos de AIC**. La selección de ese año es casi un empate, y de las figuras
anteriores no había forma de saberlo.

El pie gana además la frase que 15.2 exigía y que `modelos.png` ya decía: **AIC y BIC
están en la escala que esa familia ajusta y no se comparan con los de otra.**

### Paso 7 — El texto que dice «treinta» — HECHO el 2026-10-02

Los cinco sitios que un lector ve, listados en 15.5: el *docstring* de `eligible_pairs`,
la cabecera de su tabla de bitácora, el rótulo de `verify`, el pie de la figura de
dispersión y el de `tools/comparar_candidatas.py`.

**Los que hablan del diseño se quedan.** Que doce candidatas no caben sobre treinta
observaciones, o que la capa trae treinta unidades, siguen siendo ciertos. **El universo
del estudio sigue siendo treinta**; lo que cambia es sobre cuántas se estima.

**Verificación.** `grep -rn "thirty\|treinta" src/ tools/` y revisar uno por uno que cada
superviviente se refiera al diseño o a la capa, nunca a la estimación.

#### Hecho

**Corrida `run_20261002_141517`**, cero comprobaciones en fallo y **las 2 550 figuras
idénticas byte a byte** a las del paso 6, que es lo que tenía que pasar si este paso tocó
sólo prosa.

#### El que importaba no era un rótulo

**`contiguity_weights` afirmaba tres cosas sobre las treinta** —«thirty polygons», «none
of the thirty is isolated» y, dentro del mensaje de error, «the thirty are known to be
contiguous»— y la matriz se construye **después** del filtro, así que las tres hablaban de
otra cosa. Ahora dice lo que D56 le hizo al grafo: Torca limitaba sólo con Toberín y
Britalia, esas dos perdieron un vecino y el mínimo del resto bajó a uno. Y manda a
`tools/exclusion_de_una_unidad.py`, que es la comprobación previa de si una exclusión
propuesta aísla a alguien.

Los otros siete de `src/regressions.py`: el *docstring* del módulo —que además decía
«quince candidatas», cifra muerta desde D52—, los dos de `_describe` sobre cuándo la
binomial negativa lleva alpha a la frontera, el de colinealidad y dos cosméticos.

#### `tools/respuesta.py` tenía un defecto, no un rótulo

Medía la cuota de ceros con `UNIDADES = 30` escrito a mano, así que daba un número
**distinto del que la etapa juzga**: 0,367 contra 0,345 en automóvil contra motocicleta.
Una herramienta cuyas cifras cita la sección 2 de este documento y que contestaba sobre
otro conjunto.

Ahora lee `config.REGRESSION_EXCLUDED_UNITS`, filtra las mismas unidades y declara en su
cabecera sobre cuántas cuenta. `comparar_candidatas.py` y `tools/README.md` dejan de
prometer «las mismas treinta unidades».

#### Lo que sobrevive, a propósito

Cuatro menciones en `regressions.py`: tres son el texto de `exclude_units` explicando
precisamente la diferencia, y una cuenta archivos. **Y todo lo de las demás rutas se
queda** —`casualty_maps`, `exposure`, `interpolation`, `maps`, `matrix`, `population`,
`predictors`, `rho`, `surveys`— porque siguen trabajando sobre treinta. No es un descuido:
es la distinción que D56 existe para mantener, y borrarla de ahí sería el error contrario.

### Paso 8 — La corrida limpia — HECHO el 2026-10-02

```
.venv/Scripts/python.exe -m src.run_pipeline regressions
```

sin `--candidates`, que es `urban-only`, que es la que va a Olmos y a la asesora. Después,
si se quiere, `--candidates with-leftovers` para la de robustez.

#### Hecho

**No se repitió la corrida.** `run_20261002_141517`, la del paso 7, ya salió del código
final: `src/regressions.py` se modificó por última vez a las 14:12:53 y la corrida empezó
a las 14:15:17. Repetirla habría producido un gemelo idéntico, que es precisamente lo que
el paso 7 acababa de comprobar byte a byte.

| | |
|---|---|
| **La que el estudio reporta** | `run_20261002_141517`, solo urbanas, 40,1 min, **23 comprobaciones todas en OK** |
| **La de robustez** | `run_20261002_145959`, con restos de offset, 48,7 min, 22 todas en OK |

La de robustez **hubo que construirla**, no bastaba con conservar una: todas las de ese
conjunto eran de treinta unidades, y `comparar_candidatas.py` compara AIC sólo dentro de
una celda —misma respuesta, mismo offset, misma familia, mismas unidades—, así que
enfrentar una corrida de veintinueve contra una de treinta es exactamente la comparación
que esa herramienta existe para rechazar. Con las dos sobre veintinueve corre, y reproduce
la medición en que se apoya D52: **los restos se llevan 1 123 de 5 412 términos
seleccionados, el 20,8 %**.

#### Las comprobaciones, hechas

- **Los ganadores contra `run_20260928_112330`** dan exactamente lo mismo que el paso 1
  midió: 30,1 % de celdas cambiadas, rho +0,986 en la frecuencia. Eso confirma de paso que
  los pasos 2 a 7 no movieron ninguna cifra, sólo figuras y prosa.
- **`tools/seleccion_por_aic.py` sobre la corrida final** da 0,026, 0,073 y 12 de 104, que
  son **los tres números impresos en el pie de las figuras de ajuste**. Se midieron sobre
  veintinueve antes de escribirlos.
- **La bitácora cierra y `verify` pasa entero**, las 23 comprobaciones.
- **La sección 27 del informe de verificación** recoge la corrida, y la 26 queda marcada
  como superada con una nota que manda a ella.

---

Lo que hay que mirar está en 15.4, y se repite aquí lo que no se puede omitir:

- **La bitácora cierra**, el balance de registros cuadra y `verify` pasa entero.
- **Comparar los ganadores contra `run_20260928_112330`** y anotar cuántas celdas
  cambiaron de modelo. Es la cifra que el comité va a pedir cuando pregunte qué hizo
  quitar una unidad, y no se puede reconstruir después sin volver a correr la vieja.
- **Volver a pasar `tools/seleccion_por_aic.py`** sobre la corrida nueva: la aritmética no
  debería moverse y los percentiles sí un poco. **Las cifras de la declaración de D59 se
  reescriben con las de veintinueve unidades** antes de que ninguna llegue a un
  entregable.
- **Anotar el número de la corrida** en el informe de verificación, en una sección nueva,
  y decir qué sustituye.
