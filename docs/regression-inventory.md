# The inventory for the regressions

What exists for each of the three regression years, what does not, and why. It is
the counterpart of [`mobility-surveys-inventory.md`](mobility-surveys-inventory.md)
for the stage that comes after the predictors: everything here was measured on
2026-09-21, against the delivered files, and every figure says how it was
obtained.

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
built, is this: least squares and a GLM at 2015, 2019 and 2023, on both casualty
datasets, with a table of coefficients and a figure of observed against predicted
for each pair. **The panel is the next stage, not an alternative being rejected
here.** D48 is the decision, and the chapter has to present this the same way.

Three separate cross-sections. One regression per pair of actor types, per year:
**thirty rows, one per unit.**

A cross-section is also what lets every candidate be estimated at all. A
fixed-effects model cannot estimate the coefficient of a variable that does not
change in time, so thirteen of the fifteen would be absorbed by the unit effect;
here there is no unit effect to absorb anything. The year-to-year comparison
survives, by putting three separately estimated coefficients side by side.

| | |
|---|---|
| Unit of observation | the territorial unit, thirty of them |
| Response | affected parties of type *i* whose counterpart was type *j* |
| Pairs | eight, listed in section 2 |
| Years | 2015, 2019, 2023 |
| Offsets | three, declared in section 3; the anteproyecto's is the first |
| Candidate predictors | fifteen, listed in section 5, less whatever the offset takes |
| Models per pair and year | 560 under the first offset, 455 under the other two |
| Families | least squares and generalised linear model |
| Datasets | observed and rho-corrected, **both, always** |

**The table is built eight times with thirty rows each, not thirty times with
eight rows.** Within one unit every predictor has the same value for all eight
pairs, because the predictors are properties of the unit; a regression run that
way has nothing to regress against.

---

## 1. Why these three years

They are the three most recent of the five years a mobility survey covers, so the
exposure is measured rather than interpolated in all three. That is the only
property that separates them from any other year, and it is the decisive one:
every predictor that survives section 5 exists in every year from 2012 onward.

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
candidate set is derived from the offset and never maintained by hand: fifteen
candidates and 560 models under the first, fourteen and 455 under the other two.

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
