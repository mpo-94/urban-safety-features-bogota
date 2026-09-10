# Verification report

What the pipeline produces, whether every check it makes passes, where each
record goes, and how the result differs from the pipeline it replaces.

Sections 1 to 6 come from a single end-to-end run of the pipeline, so every
figure quoted can be traced back to a file that run wrote. Sections 7 and 8 cover
ρ(t) and the completeness audit, each a separate route with a run of its own.
Section 10 covers the correction for the change in recording practice, which
produces a second dataset beside the observed one rather than replacing it.
Section 11 covers the tree variables and the tables the pipeline now emits as
LaTeX source. Section 12 covers the two sets of predictor figures and the check
that the printed correlation and the drawn one are the same numbers. Section 14
covers the population panel, which is what the predictors, the exposure and the
casualty counts are all divided by.

Travel exposure has two sections because it has two sources. **Section 15 is the
study's exposure**, built from the household mobility survey, per unit, year,
road user type and kind of day. **Section 13 is the delivered desire lines**,
which were the exposure until the surveys were read and are now kept as a
reference: several figures quoted elsewhere were measured on them, and a figure
whose source stopped being computed cannot be checked later. Both are measured on
every run of the `exposure` route and both are checked; only the first is a
variable. Either way, exposure belongs on the far side of a rate model and is
never in the predictor grid, the correlation matrix or either predictor figure
set.

| | |
|---|---|
| Scale | UPL (30 units, the study universe — see D7) |
| Study period | 2007–2024 (18 years) |
| Sources | fatality and injury point layers with 2024 from the updated extract (D19), vehicle table |
| Stages | loading → party resolution → matrix aggregation |
| Command | `python -m src.run_pipeline matrix` |
| Result | 22,680 matrix cells, 203,077 affected parties, 234,370 injured, 7,542 killed |
| Outcome | **every check passed** |

Two kinds of contrast appear throughout, always labelled: figures measured at
**locality scale**, which is the footprint the inherited pipeline ran on, and
figures measured on the **original extract**, before 2024 was replaced. Neither is
a target. A different footprint and a different extract both change what the
sources contain, so the counts differ by construction rather than by error, and
both remain reproducible by flipping one setting.

---

## 1. Verdict by check

Every check the pipeline performs, including the ones that pass. A check that
only speaks up on failure leaves no evidence it ran.

### Loading — the two baselines

Six counts characterise this stage, and they answer to two different baselines
(D15). Four are properties of the source files, which no territorial layer can
move: they are checked against the inherited run at any scale, and reproducing
them is what says loading changed none of the logic it inherited. The other two
count records falling outside every polygon, so they depend on the footprint of
the layer and are checked against the reference measured for the active scale.

| Check | Expected | Observed | Baseline | Verdict |
|---|---:|---:|---|---|
| Fatality records | 8,592 | 8,592 | updated extract, any scale | **Pass** |
| Injury records | 268,921 | 268,921 | updated extract, any scale | **Pass** |
| Concatenated casualties | 277,513 | 277,513 | updated extract, any scale | **Pass** |
| Vehicle table rows | 1,465,735 | 1,465,735 | updated extract, any scale | **Pass** |
| Fatalities with no territorial unit | 51 | 51 | updated extract, UPL | **Pass** |
| Injuries with no territorial unit | 1,224 | 1,224 | updated extract, UPL | **Pass** |

**Five of the six counts moved when 2024 was replaced**, and the baselines are
indexed by extract and scale for that reason. The vehicle table is the one that
does not: the update carries none of its own.

| Count | Legacy notebook | Original extract, UPL | Updated extract, UPL |
|---|---:|---:|---:|
| Fatality records | 8,548 | 8,548 | **8,592** |
| Injury records | 261,293 | 261,293 | **268,921** |
| Concatenated | 269,841 | 269,841 | **277,513** |
| Vehicle rows | 1,465,735 | 1,465,735 | 1,465,735 |
| Fatalities with no unit | 61 (locality) | 50 | **51** |
| Injuries with no unit | 1,344 (locality) | 1,186 | **1,224** |

The legacy column is the historical contrast: measured on the real execution of
the inherited notebook, at locality scale, on the original extract. This
implementation reproduces it exactly under those conditions, which is what says
loading changed none of the inherited logic. It is kept for that and is never a
target for another extract or another scale.

### Loading — structural checks

| Check | Result | Verdict |
|---|---|---|
| Unit layer carries the declared study universe | 30 of 30 | **Pass** |
| Unit codes are unique within the layer | no duplicates | **Pass** |
| Spatial join does not duplicate rows | 8,592 → 8,592 and 268,921 → 268,921 | **Pass** |
| Casualty years fall inside the study period | span 2007–2024, 0 rows outside | **Pass** |
| Every vehicle type in the source is mapped | all 28 raw types covered | **Pass** |
| Vehicle join keys are unique | no duplicated (crash, vehicle) pairs | **Pass** |

### Party resolution

| Check | Result | Verdict |
|---|---|---|
| Person code unique within a crash | 0 colliding pairs, 0 null | **Pass** — it was 4 pairs on the original extract, see §5 |
| Cross-layer duplication | 0 people appear in both layers | **Pass** — it was 4, see §5 |
| Attaching casualties to parties does not duplicate | 277,513 → 277,513 | **Pass** |
| Party keys unique within a crash | no collisions | **Pass** |
| Every surviving crash has a party with casualties | 172,993 of 172,993 | **Pass** |
| Person balance closes | 277,513 in, 243,038 out, 34,475 named | **Pass** |

### Matrix aggregation

| Check | Expected | Observed | Verdict |
|---|---|---|---|
| Affected parties in matrix equal what entered | 203,077 | 203,077 | **Pass** |
| Injured in matrix equal what entered | 234,370 | 234,370 | **Pass** |
| Killed in matrix equal what entered | 7,542 | 7,542 | **Pass** |
| No negative cell | 0 | 0 | **Pass** |
| No cell with fewer people than parties | 0 | 0 | **Pass** |
| Every unit of the layer is in the grid | 30 | 30 | **Pass** |
| Every year of the period is in the grid | 18 | 18 | **Pass** |
| Grid has the declared number of cells | 22,680 | 22,680 | **Pass** |

### Balance accounting

Every stage declares how many records entered, how many left, and a named cause
for each one gained or lost. The causes must account for the difference exactly;
a stage that does not balance stops the run. **All 16 stages balanced.**

---

## 2. The complete funnel

From the raw files to the matrix, with the cause of every change.

| Stage | In | Out | Change | Cause |
|---|---:|---:|---:|---|
| Load territorial units | 30 | 30 | 0 | — |
| Load fatalities | 8,592 | 8,592 | 0 | — |
| Locate fatalities | 8,592 | 8,592 | 0 | containment only, no snapping; 51 kept with no unit |
| Load injuries | 268,921 | 268,921 | 0 | — |
| Locate injuries | 268,921 | 268,921 | 0 | containment only, no snapping; 1,224 kept with no unit |
| Concatenate casualties | 8,592 | 277,513 | +268,921 | injury rows appended |
| Load vehicle table | 1,465,735 | 1,465,735 | 0 | — |
| Cross-layer duplication check | 277,513 | 277,513 | 0 | 0 people counted twice, reported |
| Build vehicle parties | 1,465,735 | 301,177 | −1,164,558 | −1,164,557 crashes with no casualty; −1 row with no vehicle code |
| Attach casualties to parties | 277,513 | 277,513 | 0 | — |
| Assemble party universe | 301,177 | 368,394 | +67,217 | casualties with no vehicle, each its own party |
| Two-party threshold | 368,394 | 318,696 | −49,698 | parties of the 15,375 crashes with more than two |
| Keep parties with casualties | 318,696 | 203,808 | −114,888 | parties that took part unharmed |
| Restrict to located parties | 203,808 | 203,077 | −731 | crash point outside every unit |
| Aggregate onto the grid | 203,077 | 22,680 | −180,397 | −188,070 collapsed into shared cells; +7,673 empty cells materialised as zero |

**People, separately.** 277,513 people entered. 34,475 were in crashes the
two-party threshold discarded; 1,126 more were in crashes that could not be
located. 234,370 injured and 7,542 killed reach the matrix, 241,912 in total.

Nothing is lost without a name anywhere in the chain.

**Where the integration enters the funnel.** It does not: it happens before it.
The `integrate` route rebuilds the layers, and the funnel above starts from what
it wrote, which is why the first rows read 8,592 and 268,921 rather than 8,548
and 261,293. Its own balance is in §9, with the 2024 rows leaving and entering
named separately.

**What the scale touches, and what it does not.** Every stage above the spatial
join is identical to the locality-scale run of the same extract: the party model,
the two-party threshold and the counterpart resolution do not know what a polygon
is. The whole difference between two scales is the rows that involve geography.

---

## 3. Comparison with the inherited pipeline

The early stages are meant to be identical, and are. Everything after them
differs deliberately. This section separates the two kinds of difference: those
that correct a defect, and those that follow from a different methodological
choice.

### Stage by stage

The inherited pipeline ran at locality scale, so the only like-for-like comparison
of anything geographic is against the locality-scale run of this implementation.
That is how the two rows below that depend on the footprint are read.

| Stage | Inherited | This pipeline | Same? |
|---|---|---|---|
| Read fatalities and injuries | 8,548 + 261,293 | 8,548 + 261,293 | Identical |
| Locate against the unit layer | 61 + 1,344 unlocated | 61 + 1,344 at locality, 50 + 1,186 at UPL | Identical where comparable |
| Concatenate | 269,841 | 269,841 | Identical |
| Read vehicle table | 1,465,735 | 1,465,735 | Identical |
| Severity origin after concatenation | lost — both layers flagged alike | preserved on every row | Different, defect corrected |
| Unit of the output row | one row per crash | one row per affected party | Different, methodology |
| Rows emitted | 179,110 crashes | 203,808 parties, covering 172,993 crashes | Different, both causes |
| Multi-party rule | 4,208 crashes removed | 15,375 crashes removed | Different, defect corrected |
| Unmapped vehicle types | became null, then silently dropped | routed to the residual category, reported | Different, defect corrected |
| Casualties with no vehicle | all called pedestrians | typed by role | Different, methodology |
| Grid coverage | only observed combinations | complete grid, 22,680 cells | Different, methodology |
| Distinguishes injured from killed | no | yes, three counts side by side | Different, defect corrected |

### Differences that correct a defect

**Severity origin was recoverable and is now kept.** The inherited code marked
fatalities and injuries with the same value at load and concatenated them, after
which no downstream step could tell them apart. Fatalities are 3% of records, so
merging them buried the outcome that matters most. This pipeline carries the
origin on every row and produces separate counts of injured and killed from the
same run.

**Unmapped vehicle types no longer delete records.** One vehicle type was absent
from the inherited mapping, which turned 388 rows into nulls, and a later
grouping dropped those nulls without any message. 25 crashes disappeared from the
study entirely. Here every value in the source is mapped, matching is done on
normalised text, and anything unrecognised reaches the residual category and is
reported: on this run, 5,658 parties whose type is blank in the source.

**The multi-party rule now counts parties.** The inherited pipeline removed 4,208
crashes on the original extract; this one removes 15,375 on the updated one and
15,014 on the original, so the gap is the rule and not the extract. That is not a
discrepancy but the same rule applied correctly. The inherited code deduplicated actor *types* before counting,
so a crash between two cars counted as one type and passed a threshold that is
about parties, where that crash is plainly two. The larger figure is the honest
one, and the research proposal, which quotes 4,208, needs correcting.

**The proximity fallback that never ran.** The inherited code appears to snap
unmatched points to the nearest unit within a tolerance. That branch never
executes: it looks for unmatched points in the result of a left join, which by
construction keeps every input row, so its set of unmatched points is always
empty. Every inherited figure therefore comes from plain containment. Had it run,
the tolerance was expressed in degrees while the join ran in geographic
coordinates, making it roughly 550 km rather than the 5 m it appears to be. This
pipeline does containment only, by choice, and reproduces those figures because
that is what the inherited code actually does.

### Differences that follow from a methodological choice

**One row per affected party instead of one per crash.** The inherited pipeline
collapsed each crash to a single row and then had to choose which party to record
as the casualty; the alphabetical order of the actor label decided it. Here both
sides of a crash emit their own row and no choice is needed. This is the largest
single difference and the reason the row counts are not comparable directly:
179,110 inherited rows are crashes, 203,808 rows here are parties.

**The counting unit is the party, with people counted alongside.** The inherited
casualty column summed people for pedestrians and cyclists but took a maximum for
everyone else, so the same column meant people in some rows and vehicles in
others. Here a party with casualties counts once whatever its occupancy, and the
person counts sit beside it in their own columns.

**A complete grid.** The inherited output contained only combinations it had
observed, making a true zero indistinguishable from a missing observation. The
matrix here is a full grid of 22,680 cells, 7,673 of them zero.

**Casualties with no recorded vehicle are typed by role.** The inherited code
called all 67,116 of them pedestrians. 2,031 are recorded as passengers or
drivers, whose vehicle simply was not captured.

### The orientation of the motorcycle–bicycle pair

This is where the inherited bias was most visible, and it inverts.

The inherited figures were measured before its own geographic restriction, so the
like-for-like comparison is against all affected parties, before the 701
unlocated ones leave. That column does not depend on the unit layer at all. The
matrix itself is shown too; the relationship is the same on either basis.

| | Inherited | In the matrix |
|---|---:|---:|
| Motorcyclist harmed, bicycle as counterpart | 8,129 | 4,083 |
| Cyclist harmed, motorcycle as counterpart | 1,881 | 5,767 |
| Ratio | **4.32x** | **0.71x** |

The inherited matrix records a motorcyclist as the harmed party four times more
often than a cyclist in collisions between the two. That is the wrong way round:
of the two, the cyclist is by far the more exposed. The ratio was not a finding
about Bogotá, it was an artefact of the letter B preceding the letter M in the
actor labels, since alphabetical order decided which party was written down as
the casualty.

With one row per affected party there is no choice to make and no order to
impose, and the relationship reverses to 0.70x — the cyclist is now the harmed
party more often, as physics would suggest. Nothing was tuned to produce this;
it falls out of removing the choice.

### Orientation check across the whole matrix

If the pair were oriented wrongly in general, pedestrians and bicycles would
appear as counterparts far more often than they should, since neither imposes
lethal risk on others.

| Counterpart | Affected parties | Share |
|---|---:|---:|
| CAR | 78,712 | 38.76% |
| MOTORCYCLE | 44,172 | 21.75% |
| SELF | 27,142 | 13.37% |
| PUBLIC_TRANSPORT | 21,946 | 10.81% |
| OTHER | 13,293 | 6.55% |
| PEDESTRIAN | 10,574 | 5.21% |
| BICYCLE | 7,238 | 3.56% |

Pedestrian and bicycle together are 8.77% of the matrix, the two smallest
columns. That is what a correctly oriented matrix looks like. The check is part
of the run and would raise a warning above 15%.

---

## 4. The matrix

Affected parties, all units and all years, rows are the harmed party and columns
the counterpart.

| | PEDESTRIAN | BICYCLE | MOTORCYCLE | CAR | PUBLIC_TRANSPORT | OTHER | SELF |
|---|---:|---:|---:|---:|---:|---:|---:|
| **PEDESTRIAN** | 0 | 1,166 | 19,907 | 19,464 | 7,031 | 4,766 | 24 |
| **BICYCLE** | 191 | 727 | 5,767 | 9,535 | 4,202 | 1,960 | 640 |
| **MOTORCYCLE** | 9,050 | 4,083 | 11,464 | 36,039 | 6,070 | 4,432 | 10,476 |
| **CAR** | 1,018 | 995 | 6,144 | 11,847 | 2,084 | 1,192 | 3,512 |
| **PUBLIC_TRANSPORT** | 251 | 202 | 500 | 1,302 | 1,984 | 434 | 11,646 |
| **OTHER** | 64 | 65 | 390 | 525 | 575 | 509 | 844 |

Largest cells: motorcyclist harmed by a car (36,039), pedestrian by a motorcycle
(19,907), pedestrian by a car (19,464). Smallest: residual harmed by a pedestrian
(64), pedestrian alone (24), pedestrian by a pedestrian (0).

The zero is structural rather than surprising: two pedestrians struck in one
crash, together with the vehicle that struck them, are three parties, and the
two-party rule removes the crash.

### People by year

For checking against published figures.

| Year | Parties | Injured | Killed | | Year | Parties | Injured | Killed |
|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 2007 | 10,474 | 11,266 | 370 | | 2016 | 10,344 | 11,644 | 511 |
| 2008 | 7,654 | 8,537 | 279 | | 2017 | 10,335 | 11,867 | 483 |
| 2009 | 6,823 | 7,823 | 317 | | 2018 | 12,702 | 14,777 | 449 |
| 2010 | 9,663 | 11,093 | 375 | | 2019 | 12,996 | 15,162 | 439 |
| 2011 | 9,538 | 10,922 | 395 | | 2020 | 9,800 | 11,179 | 337 |
| 2012 | 10,434 | 11,774 | 399 | | 2021 | 13,637 | 16,167 | 402 |
| 2013 | 9,817 | 11,309 | 372 | | 2022 | 15,808 | 18,648 | 471 |
| 2014 | 9,420 | 10,820 | 428 | | 2023 | 16,715 | 20,073 | 503 |
| 2015 | 10,229 | 11,486 | 468 | | **2024** | **16,688** | **19,823** | **544** |
| | | | | | **Total** | **203,077** | **234,370** | **7,542** |

**2024 is the year that changed, and only it.** Every other year is identical to
the run on the original extract, which is what replacing one year should do. 2024
goes from 11,221 parties to 16,688, from 13,179 injured to 19,823 and from 501
killed to 544, and lands beside 2023 rather than a third below it. The 33% fall
was the missing four months, not a change in the city.

The 2020 dip and the 2023 peak are the expected shape. The low 2008–2009 figures
match a known weakness of the source in its early years.

### Grid coverage

7,673 of 22,680 cells are zero (33.83%). No unit and no year is empty throughout.
Emptiness tracks size and centrality: Torca, on the northern edge, is 55.16%
empty, followed by Tibabuyes at 48.41% and Porvenir at 46.69%; the fullest are
Centro Histórico at 23.54%, Tabora at 23.81% and Kennedy at 25.13%. 2007 is the
emptiest year at 52%, after which the series settles between 25% and 39%.

**This is the figure that moved most with the scale, and it bears on the model.**
The same casualties cut into 30 units instead of 19 take the share of empty cells
from 29.80% to 33.83%, +4.03 points for 58% more units. Completing 2024 moved it
by a third of a point, from 34.17%: a fuller year fills cells that were empty only
because the records were missing, and 2024 goes from 31% to 25% empty. A third of
the grid at zero is a property of the data at this resolution rather than a defect,
but it is enough that the choice of count distribution for the panel has to be made
deliberately, and made on this grid. At UPZ, with 111 units, it would be far
higher again.

---

## 5. What was fulfilled, and what was not

Against the recorded decisions.

### Fulfilled

| Decision | Evidence |
|---|---|
| D1 one row per affected party | 203,808 party rows; both sides of a crash emit their own |
| D2 party as counting unit, people alongside | three counts in every row of the matrix |
| D3 severity origin preserved | injured and killed reported separately at every stage |
| D4 vehicle classification by occupant protection | all 28 source types mapped; 5,658 unrecognised parties reported, none dropped |
| D5 two-party threshold, measured | 15,375 crashes and 34,475 people removed, composition reported |
| D6 containment only, no snapping | 1,275 casualties kept unlocated and reported |
| D7 the universe is the 30 UPL of the layer | 30 of 30 units present, all 30 in the grid |
| D8 person identity follows the data | the source person code is unique now, so it is used; the fallback reversed itself |
| D9 actor type from role | 65,022 pedestrians, 2,071 to residual, 63 unlisted reported; 61 placed by a role that implies the mode |
| D10 complete grid | 22,680 cells, 7,673 zeros materialised |
| D11 unlocated parties leave at aggregation | 731 parties, cause named, 5 of them from moved geometry |
| D12 figures from exported tables, shared log scale | 57 heatmaps, each read back from its own CSV |
| D13 analysis and presentation tables separated | file names carry the distinction |
| D15 UPL scale, legacy figures as historical contrast | source counts and footprint counts checked against the baseline of their own extract and scale |
| D16 one entry point with routes | this run is `run_pipeline matrix`; `loading`, `parties`, `rho`, `completeness` and `integrate` are routes of their own |
| D17 ρ(t) from the party universe, denominator always beside it | 5,022 cells, 275 undefined rather than zero, no cut by size in the data or in the figures — see §7 |
| D19 the most recent extract prevails | 2024 replaced whole, balance in §9, sources on disk untouched |
| D20 sources checked for coverage | every layer-year-month counted, see §8 |

### Not fulfilled, or only partly

**D3 is complete for the pipeline but its central question is open.** Injured and
killed are carried separately, which is what the decision required. How the
models should aggregate them — combined, separately, or both — is not settled and
is for my advisor.

**D7 is settled and this run is the first on the decided universe.** The study
universe is the 30 UPL of the layer; Decreto 555 defines 33, and the three absent
ones are the rural units, where the urban predictors are undefined anyway. Thirty
is the denominator of every coverage figure in this report. The loader no longer
warns about a shortfall — there is none — and instead stops the run if the layer
does not carry exactly the declared universe.

**D18 is open, and ρ is what found it.** The 2007 vehicle table does not
distinguish the two parties of a vehicle–vehicle crash: 98.6% of that year's
two-vehicle crashes carry a single vehicle class between them, against 13–20% in
every other year. It costs the counterpart of vehicle–vehicle crashes in 2007,
not the casualty counts. What to do with that year is for my advisor.

**D8 resolved itself, and the limitation with it.** Party identifiers used to come
from row position, because the source person code was not unique within a crash.
On the updated extract it is: 0 colliding pairs and 0 nulls over 277,513 records,
so the pipeline uses the source code and party identifiers are now comparable
across runs. Nothing was edited to bring that about — the check picks the
identifier from what it measures on each run, and the fallback returns if a future
source stops being unique.

**The four people counted twice are gone.** They appeared in both the fatality and
the injury layer, and all four were 2024 records; the updated extract carries each
of them once. The check reports zero. It stays in the run for the same reason it
was built: a future extract in which the number grows would inflate the person
counts, and it has to be visible the moment it happens.

**D14 was reverted.** Pictogram-labelled figures were built, reviewed and
removed; pipeline figures are text-labelled. Recorded rather than deleted.

### Not yet started

Urban predictors and the panel models. The audit of the inherited predictor stage
is complete and documented, and the reimplementation has not begun.

---

## 6. Outputs

One directory per run, named by timestamp, so runs accumulate instead of
overwriting one another. Every route produces one, whether it goes all the way to
the matrix or stops at loading; a partial run leaves the same audit trail as a
complete one.

| Location | Contents | Purpose |
|---|---|---|
| `provenance.log` | full log with the funnel and every check | the audit trail of the run |
| `data/analysis__matrix_long.{csv,parquet}` | 22,680 rows, the complete grid | **the table the models consume** |
| `data/presentation__crosstab_{count}__all_years.csv` | 3 files, aggregate matrices | reading and reporting |
| `data/by_year/presentation__crosstab_{count}__{year}.csv` | 54 files | per-year matrices |
| `figures/parties/`, `figures/injured/`, `figures/killed/` | 19 heatmaps each | one per year plus an aggregate, shared colour scale within each count |
| `intermediate/` | 6 stages, parquet and CSV | the state after each stage, for inspection; off by default |

The long table is the only one meant for analysis. The cross-tabulations are the
same numbers reshaped for reading, and the file name prefix says which is which
so that nothing is fed to a model from a presentation table by accident.

Heatmaps use a logarithmic colour scale with the values printed on the cells,
because the counts span from single digits to thirty-five thousand and a linear
ramp would collapse everything except the dominant cell. Cells with no
observation are drawn in flat grey rather than at the bottom of the ramp, so a
true zero cannot be read as a small value. Within each count the per-year figures
share one colour scale; the aggregate figure has its own, since eighteen years
and one year are not on the same ruler.

---

## 7. The ρ(t) diagnostic

A separate route (`python -m src.run_pipeline rho`) with its own run directory.
It is not a stage of the pipeline: nothing downstream consumes it, and it reads
the party universe before the parties without casualties are dropped, so it is
computed from the sources rather than from the matrix. The design is D17.

| | |
|---|---|
| What it measures | share of two-party crashes of a pair in which **both** parties suffered casualties |
| Pairs | 9 unordered pairs; at least one side motorcycle, car or public transport |
| Levels | per UPL and year, and the whole city by year, in one table |
| Result | 5,022 cells, 111,398 crashes, 4,747 values defined and 275 undefined |
| Outcome | **every check passed** |

### Funnel

| Stage | In | Out | Change | Cause |
|---|---:|---:|---:|---|
| Collapse parties into two-party crashes | 318,696 | 145,703 | −172,993 | −27,290 parties of single-party crashes; −145,703 second party folded into its crash |
| Restrict to the nine pairs | 145,703 | 111,731 | −33,972 | −14,235 residual category; −18,570 same type on both sides; −1,167 no motorcycle, car or public transport |
| Restrict to located crashes | 111,731 | 111,398 | −333 | point outside every territorial unit |
| Aggregate onto the unit grid | 111,398 | 4,860 | −106,538 | −106,807 collapsed into cells; +269 empty cells kept with ρ undefined |
| Aggregate for the whole city | 111,398 | 162 | −111,236 | −111,242 collapsed by year and pair; +6 combinations with no crash |
| Assemble the table | 4,860 | 5,022 | +162 | city rows, marked `CITY` |

### Checks

| Check | Result | Verdict |
|---|---|---|
| Numerator never exceeds denominator | 0 rows above | **Pass** |
| ρ within [0, 1] where defined | 4,747 defined, 0 outside | **Pass** |
| ρ defined exactly where the denominator is not zero | 275 empty cells, 0 disagreements | **Pass** |
| Units sum to the city total, year by year | 18 years, 0 disagreeing | **Pass** |
| Every crash counted once, in one pair only | 111,398 in, 111,398 counted | **Pass** |
| Grid has the declared number of cells | 5,022 of 5,022 | **Pass** |

### What it found

**ρ rises across the whole series, on every pair, and the completed 2024 does not
change that.** Pedestrian–motorcycle goes from 0.218 in 2007 to 0.837 in 2023,
bicycle–motorcycle from 0.468 in 2008 to 0.871, motorcycle–car from 0.057 to
0.403. A near-fourfold rise in the probability that both parties of a collision
are recorded as casualties is not a change in the physics of collisions. The two
regimes are unchanged by the update: flat from 2008 to 2016, climbing from 2018.
It bears directly on whether a count model can treat 2007 and 2023 as the same
measurement.

**The truncated 2024 was not biased in ρ, only thin.** Its denominators grew by
about half when the four missing months arrived — motorcycle–car from 2,213
crashes to 3,342 — and the values barely moved: no pair shifts by more than 0.019,
and 2024 stays just below 2023 on seven of the nine pairs. A missing third of a
year cost precision, not position.

**2007 does not distinguish the two parties of a vehicle–vehicle crash.** Six of
the nine pairs have no crash at all that year. See D18: it is open, and it is
reported by name on every run.

**The unit grid is thin.** 1,958 of 4,860 unit-year cells (40.29%) rest on fewer
than ten crashes, and 269 on none at all. Nothing is filtered on it and nothing is
marked for it in the figures either; the denominator travels beside ρ everywhere
it is shown.

**The city value is not the average of the units.** Pooled, the city is 0.200
against 0.179 for the mean of the unit-year cells, and the gap reaches 0.101 on
bicycle–motorcycle. They are different quantities and the table says which is
which in its own column.

### Outputs

| Location | Contents |
|---|---|
| `data/analysis__rho_long.{csv,parquet}` | 5,022 rows, both levels, ρ with its numerator and denominator |
| `data/presentation__rho_city_rho__by_year.csv` | city ρ, years by pairs |
| `data/presentation__rho_city_denominators__by_year.csv` | the crashes behind each of those values |
| `figures/rho/rho_city__by_pair.png` | the nine pairs for the city, one panel each |
| `figures/rho/rho_city__denominators.png` | their denominators, same layout, logarithmic |
| `figures/rho/by_unit/rho_units__{pair}.png` | 9 figures, 30 panels each, city curve behind every panel |

Every point of every series is drawn identically. The only gap in a line is a year
whose denominator is zero, where ρ does not exist. There is no cut by number of
events, in the data or by eye.


---

## 8. Source completeness

`python -m src.run_pipeline completeness`. The pipeline verified its own
arithmetic in detail and nothing about whether the sources cover the period they
claim to, which is how a third of 2024 went missing without any check noticing
(D20). This counts the records of every layer, year and month and flags the months
that are empty or below half the median month of their own year.

**On the integrated sources, one month is flagged:**

| Layer | Year | Month | Records | Median month of that year | Share |
|---|---:|---:|---:|---:|---:|
| INJURY | 2020 | April | 408 | 1,059 | 38.5% |

That is the strict quarantine: a real drop, not a gap. **No year has an empty
final month.**

**On the original extract, it names the defect it was built for:** September 2024
at 10.1% of the median, and October, November and December empty — the last three
months of the year, which is what a truncated extract looks like.

**Its blind spot.** A year that is uniformly under-reported passes, because every
month is thin in the same way and the median moves with them. 2008 and 2009 are
that shape: 10,241 and 9,116 records against 14,148 in 2007, with no single month
flagged. The year-on-year change column is printed beside the monthly table for
that reason, and it shows −27.6%, −11.0% and then +40.3% in 2010.

The route exports `data/analysis__monthly_completeness.csv`, one row per layer,
year and month, with the flags.

---

## 9. The integration of the updated 2024 extract

`python -m src.run_pipeline integrate`. It reads the original sources, writes the
rebuilt layers to `data/integrated/`, and never writes over anything. What the
rest of the pipeline reads is decided by `USE_UPDATED_2024` in the configuration —
one line to revert.

| Stage | In | Out | Change | Cause |
|---|---:|---:|---:|---|
| Read the updated extract | 23,266 | 23,266 | 0 | 599 fatalities and 22,667 injuries in one table, 12,976 crashes |
| Replace 2024 [FATALITY] | 8,548 | 8,592 | +44 | −555 rows of 2024 from the original extract; +599 from the updated one |
| Replace 2024 [INJURY] | 261,293 | 268,921 | +7,628 | −15,039 rows of 2024 from the original extract; +22,667 from the updated one |

The net is not the story, so the causes are kept apart from it:

| Declared separately | Fatalities | Injuries |
|---|---:|---:|
| People absent from the updated extract altogether, accepted (D19) | 12 | 16 |
| People still present but under the other severity | 0 | 6 |
| People new to the study | 54 | 7,650 |
| People arriving from the other layer | 2 | 0 |
| Incoming rows outside every UPL | 4 | 128 |
| …of which located under the previous extract and not under this one | 1 | 4 |

The six who changed severity are people the original extract recorded as injured
and the updated one records as dead, with a date of death after the original was
taken. Four of them were among the people who appeared in both layers, which is
why that count is now zero.

### Checks on the conversion

The incoming file is a CSV with geometry as text and identifiers typed
differently from the shapefiles. Each of those is a way to lose records in
silence, so each is converted explicitly and verified.

| Check | Result | Verdict |
|---|---|---|
| Every column matches the type of the layer it joins | 14 mismatches found and fixed before anything was written | **Pass** |
| Converted person codes still match the previous extract | 543 of 555 fatalities, 15,017 of 15,039 injuries | **Pass** |
| Vehicle reference still resolves | 99.51% of incoming casualties, against 100.00% in 2023 | **Pass** |
| The incoming file covers only the replaced year | 2024 only | **Pass** |

The first row is not a formality. The person code arrives as an integer where the
layer holds text, and a merge on mismatched types does not raise — it matches
nothing. That is exactly what happened once while the file was being inspected,
which is why the check exists and why it stops the run rather than warning.

---

## 10. The correction for the change in recording practice

`python -m src.run_pipeline corrected`, run `run_20260830_140246`. One run
produces **both** datasets from one reading of the sources and one party
universe, so they differ by the correction and by nothing else (D31).

| | Observed | Corrected |
|---|---:|---:|
| Years | 2007–2024 | 2008–2024 (D30) |
| Matrix cells | 22,680 | 21,420 |
| Affected parties | 203,077 | 216,155 |
| People injured | 234,370 | 251,852 |
| People killed | 7,542 | 7,325 |
| `DATASET` column | `OBSERVED` | `RHO_CORRECTED` |

The two totals are not directly comparable, because 2007 is in the first and not
in the second. Against the shared years the correction adds **23,552 affected
parties, 28,748 injured and 153 killed**, and that is what the balance check
tests.

### What was decided before anything was corrected

The reference window was the open question, and the obvious answer was wrong.
2022–2024 looked like the settled period; 2022 turns out to be the last year of
the climb. The full argument is D28. In short: the sign test that first raised
the suspicion cannot settle it, because a permutation treating the year effect as
shared between pairs cannot return a p-value below 1/6 whatever the data show. The
question is settled instead by the shape of the ramp, measured as the common
year-on-year increment of logit ρ across the nine pairs.

| Step | Common increment | In sd of a settled year | Pairs rising |
|---|---:|---:|---:|
| 2021 → 2022 | +0.376 | +2.20 | 9 of 9 |
| 2022 → 2023 | +0.166 | +0.97 | 7 of 9 |
| 2023 → 2024 | −0.030 | −0.18 | 3 of 9 |

A year followed by a further climb has not reached the plateau. The window is
**2023–2024**, and the reference is the pooled numerator over the pooled
denominator, not the mean of the annual ρ.

### The five checks the design promises

| Check | Result | Verdict |
|---|---|---|
| Corrected ρ equals the reference in every corrected pair-year | 133 pair-years, worst excess over the one-crash tolerance −2.02 × 10⁻⁴ | **Pass** |
| No crash reclassified inside the reference window | 0 in 2023–2024 | **Pass** |
| The excluded year is absent from the corrected matrix | none present; span 2008–2024 | **Pass** |
| No cell of the corrected matrix is below the observed one | 0 cells fell, over 21,420 shared cells and 3 counts | **Pass** |
| Parties: corrected exceeds observed by exactly the plan | +23,552 observed, +23,552 planned | **Pass** |
| Injured: corrected exceeds observed by exactly the plan | +28,748 observed, +28,748 planned | **Pass** |
| Killed: corrected exceeds observed by exactly the plan | +153 observed, +153 planned | **Pass** |

The first check cannot be exact and says so: the target is a whole number of
crashes and the reference is a ratio, so ρ can miss it by up to the value of one
crash. The tolerance is one crash and the worst case sits inside it.

The corrected matrix passes the same eight structural checks the observed one
does — totals against what entered, no negative cell, no cell with fewer people
than parties, all 30 units present, all 17 years present, and exactly 21,420 cells.

### Where the correction lands

| Year | Crashes | Reclassified | Share | Parties added |
|---|---:|---:|---:|---:|
| 2008 | 3,949 | 1,179 | 29.9% | +15.4% |
| 2009 | 3,825 | 1,074 | 28.1% | +15.7% |
| 2010 | 5,412 | 1,706 | 31.5% | +17.7% |
| 2011 | 5,516 | 1,713 | 31.1% | +18.0% |
| 2012 | 6,074 | 1,985 | 32.7% | +19.0% |
| 2013 | 6,153 | 2,040 | 33.2% | +20.8% |
| 2014 | 5,957 | 1,876 | 31.5% | +19.9% |
| 2015 | 6,635 | 2,145 | 32.3% | +21.0% |
| 2016 | 6,815 | 2,219 | 32.6% | +21.5% |
| 2017 | 6,649 | 1,954 | 29.4% | +18.9% |
| 2018 | 7,498 | 1,790 | 23.9% | +14.1% |
| 2019 | 7,353 | 1,741 | 23.7% | +13.4% |
| 2020 | 5,438 | 1,010 | 18.6% | +10.3% |
| 2021 | 7,075 | 697 | 9.9% | +5.1% |
| 2022 | 7,990 | 423 | 5.3% | +2.7% |
| 2023 | 8,142 | 0 | 0.0% | 0.0% |
| 2024 | 8,087 | 0 | 0.0% | 0.0% |

The profile is the one the mechanism predicts: flat and large across the years
before the change, decaying through the ramp, nothing in the reference window.
The correction reaches all 30 units and 3,460 pair-year-unit cells.

### Which party gets added, and why that is a check rather than a choice

The side the reclassified crashes are drawn from is decided by the composition of
the reference period (D29), not by any rule about who should be added. What comes
out of that arithmetic is that the added party is almost always the protected one:

| Actor type | Parties added | Injured | Killed |
|---|---:|---:|---:|
| Car | 13,828 | 16,343 | 18 |
| Motorcycle | 8,403 | 10,386 | 132 |
| Public transport | 1,201 | 1,899 | 0 |
| Bicycle | 120 | 120 | 3 |
| Pedestrian | 0 | 0 | 0 |
| **Total** | **23,552** | **28,748** | **153** |

That agrees with what the diagnostic concluded by a different route, and it is
the strongest single piece of evidence that the correction is doing what it
claims. No pedestrian is ever added, which is not an oversight: the sources have
no record of an unhurt pedestrian, so a pedestrian can only enter the data as a
casualty. The same fact means ρ for the three pedestrian pairs is conditioned on
the pedestrian having been hurt, and is not the same quantity as ρ for a pair of
vehicles. The two must not be read side by side.

### What is assumed, and what would overturn it

Three things are assumed rather than shown, and all three are recorded in D28 and
D29:

- **The change of practice was homogeneous between units.** 40.9 % of the unit
  cells carry fewer than ten crashes, so a per-unit factor cannot be estimated.
  The reference is a city figure applied to every unit.
- **The plateau is real.** It rests on two years. If a later extract shows ρ still
  moving after 2024, the window is wrong and every figure above moves with it.
- **People per added party follow the reference period.** The mean is taken per
  actor type over the reference window; the deaths are allocated once per actor
  type rather than group by group, because rounding them group by group destroyed
  9 % of them.

The correction is an estimate and the pipeline treats it as one: the observed
dataset is never replaced, the plan is exported cell by cell, and the reference
window is a single constant so revising it costs one edit and one run.

---

## 11. The tree variables

Run `run_20260831_011423`, route `predictors`, command
`python -m src.run_pipeline predictors`. **Every check passed.** Three variables
come off one layer: `TREE_DENSITY`, which enters the models, and
`TREE_DENSITY_WITHOUT_P1` and `TREE_DENSITY_U_CODES`, which are measured for
comparison and stay out. The decision and the evidence behind it are D32.

### Funnel

The tree census is the first layer measured on part of itself rather than whole,
so each selection appears in the funnel as its own stage and the balance closes
on the layer as delivered.

| Stage | In | Out | Cause of the difference |
|---|---:|---:|---|
| measure `TREE_DENSITY` | 1,475,041 | 1,430,548 | −44,493 points falling outside every unit |
| select `TREE_DENSITY_WITHOUT_P1` | 1,475,041 | 1,163,036 | −312,005 features with `Tipo_Empla` = `P1` |
| measure `TREE_DENSITY_WITHOUT_P1` | 1,163,036 | 1,155,532 | −7,504 points falling outside every unit |
| select `TREE_DENSITY_U_CODES` | 1,475,041 | 442,742 | −1,032,299 features carrying none of the fifteen U codes |
| measure `TREE_DENSITY_U_CODES` | 442,742 | 442,147 | −595 points falling outside every unit |

Every value the selections send away is named individually in the log, one cause
per emplacement code, so the twenty codes the U rule excludes are itemised rather
than rolled into a single unmatched count.

96.98% of the census falls inside a unit, in line with the other point layers,
which run from 98.18% to 100%. The narrower a variant is the higher its coverage
gets, which is what it should do: 99.35% without P1 and 99.87% for the U codes,
because the codes furthest from the built-up city are the first to go.

### What the three variables look like

Trees per square kilometre, over the thirty units.

| Variable | Minimum | Median | Maximum | Units at zero |
|---|---:|---:|---:|---:|
| `TREE_DENSITY` | 901.55 | 3,405.41 | 7,937.46 | 0 |
| `TREE_DENSITY_WITHOUT_P1` | 388.52 | 2,945.03 | 5,584.85 | 0 |
| `TREE_DENSITY_U_CODES` | 248.94 | 1,070.97 | 2,386.79 | 0 |

All three carry `zero_is_implausible` and none of them fires.

### The grid grew by three variables and nothing else moved

| Check | Result |
|---|---|
| Grid cells | 390 of 390 (30 units × 13 predictors) |
| Every predictor covers every unit | 13 predictors, 30 units each |
| Every declared source file exists | 13 of 13 |
| Snapshots carry no year | 13 snapshot variables, 0 rows with a year |
| Dictionary and measured variables are the same set | 13 declared, 13 measured |
| Correlation is symmetric, diagonal 1, range within [−1, 1] | 13 × 13 |

### The correlation structure of the model set is unchanged

The model set is eight variables: the thirteen measured, less carriageway
(collinear with sidewalk at 0.969), bridge deck (excluded by my advisor), urban
park (superseded by the tree census, D32) and the two tree variants.

| | Before the swap | After the swap |
|---|---|---|
| Pairs at or above 0.70 in absolute value | 5 | 5 |
| Largest | 0.901, signalised junctions × TransMilenio | 0.901, signalised junctions × TransMilenio |
| Largest correlation of the green variable | 0.243, parks × sidewalk | 0.308, trees × TransMilenio |

`TREE_DENSITY` against `URBAN_PARK_AREA_SHARE` is 0.383. Both stay measured, so
that figure can be recomputed from `analysis__static_predictors_wide.csv` of any
run.

`TREE_DENSITY` against `TREE_DENSITY_WITHOUT_P1` is 0.944 and appears in the
table of pairs above the threshold. That is two counts of the same objects rather
than a redundancy in the study, and the table marks it: the
`SAME_SOURCE_LAYER` column is true exactly for pairs that share a source layer,
and the run report says so in words underneath.

### Emitted tables

Four casualty matrices and one correlation table leave the pipeline as LaTeX
source rather than as figures to transcribe (D33). Each carries its run in a
comment on the second line, and each was checked against the table it was built
from before the run was allowed to finish.

| File | Route | Check |
|---|---|---|
| `presentation__matrix_persons__observed.tex` | `corrected` | totals 241,912, matches the long table |
| `presentation__matrix_parties__observed.tex` | `corrected` | totals 203,077, matches the long table |
| `presentation__matrix_persons__rho_corrected.tex` | `corrected` | totals 259,177, matches the long table |
| `presentation__matrix_parties__rho_corrected.tex` | `corrected` | totals 216,155, matches the long table |
| `presentation__model_correlation.tex` | `predictors` | read back from disk, checked to be the model set, symmetric, diagonal 1 |

The matrices come from run `run_20260830_201503`, route `corrected`, which also
passed every check of section 10. All five are included by the informe de avance,
which no longer holds a transcribed number.

---

## 12. The two sets of predictor figures

Run `run_20260831_060432`, route `predictors`. **Every check passed.** The
figures are drawn twice, for two sets of variables, and two measured variables
are drawn in neither. The decision is D34.

| Set | Variables | Folder | Files |
|---|---:|---|---:|
| complete | 11 | `figures/predictors__complete/` | 13 |
| model | 8 | `figures/predictors__model/` | 10 |

Each set holds one histogram per variable, its correlation heat map and its
master table, so the file counts are the variable count plus two. Every file
carries its set as a suffix, `histogram__TREE_DENSITY__model.png` and so on, so
no figure of one set can be mistaken for the same figure of the other.

`TREE_DENSITY_WITHOUT_P1` and `TREE_DENSITY_U_CODES` are measured, exported and
reported, and appear in no figure. They are alternative counts of the same census
as `TREE_DENSITY` and exist as the evidence behind D32, which is a thing to quote
from a table rather than a column to read in a heat map. The exported dictionary
says so per variable, in its `FIGURE_SETS` column, which reads `none` for these
two.

The complete set is eleven and not thirteen for that reason: it is every measured
variable once each, across the eleven source layers.

### The printed correlation and the drawn one are the same numbers

The correlation of the model set exists on two routes. The exported model
correlation is computed from the declared model set and becomes the LaTeX the
documents include. The figure is drawn from the full correlation restricted to
the model set. A Pearson correlation between two columns does not depend on which
other columns are present, so the two must agree exactly, and the run now checks
it rather than assuming it.

| Check | Result |
|---|---|
| the model correlation matches the full one restricted to the model set | **OK**, 8 variables, largest difference 0.00e+00 |

This is worth a check of its own because it is the one disagreement that would
leave nothing else out of place: a figure and a table in the same document,
saying different things, with every other check on both routes passing.

The emitted table was also compared against
`correlacion_modelo__run_20260831_011423.tex`, the copy the informe de avance
includes in its frame 10. The two are identical apart from the comment naming the
run, so no figure in the deck needed correcting.

One cosmetic difference between the two did turn up and was fixed: the heat map
printed a small negative correlation as `-0.00` where the LaTeX table already
printed `0.00`. The two are read side by side, and a signed zero reads as a
quantity that is not zero. Both now drop the sign of a value that rounds to
nothing.

---

## 13. Travel exposure from the delivered desire lines

> **This is no longer the study's exposure, and the layer is now retired.**
> Section 15 is the exposure, and it is built from the mobility surveys. The layer
> left `config.EXPOSURE_LAYERS` when 2019 was implemented: it is not read on any
> run from `run_20260908_005529` onward, and it no longer produces
> `reference__delivered_desire_lines_by_unit.csv` or a figure.
>
> **This section stays exactly as it was**, because the figures in it are quoted
> in finished work and have to remain checkable. Every number below is from
> `run_20260901_091802` and was unchanged on `run_20260907_231531`, which is how
> the replacement was checked; `config.BICYCLE_DESIRE_LINES` still names the file,
> so any of them can be recomputed by hand.
>
> Three things about the layer are now known that were open when this was written:
> it is a sample of the **2019** survey and not of 2023, its selection was not by
> volume, and **all 160 of its origin-destination pairs appear among the pairs the
> pipeline builds from the 2019 survey**, with no pair attributed more trips than
> the survey holds for it. That last one is why the layer was kept until 2019
> landed rather than deleted when it was superseded: two independent readings of
> one source agreeing on 160 pairs is the strongest confirmation the survey reader
> could get, and it could only be made once both existed. Section 15 has it in
> full. All three are in D38 and D35.

Run `run_20260901_091802`, route `exposure`, command
`python -m src.run_pipeline exposure`. **Every check passed.** The
origin-destination desire lines of the mobility survey give each unit a measure
of how much cycling passes through it. It is not a predictor and is not in the
predictor grid, the correlation matrix or either figure set: in a rate model it
sits on the other side. The decision is D35, which also closes D21.

The layer holds **181 lines, all of mode `Bicicleta`**, summing to 556,997.58
trips per week and 113,269.31 per day. A line gives each unit it crosses the
share of its trips that matches the share of its length inside that unit.

### Funnel

| Stage | In | Out | Cause of the difference |
|---|---:|---:|---|
| load territorial units | 30 | 30 | — |
| apportion `BICYCLE_TRIPS` over the units | 181 | 579 | −3 lines falling outside every unit, +401 fragments where a line crosses a boundary |
| assemble the exposure table | 29 | 30 | +1 unit no line reaches, materialised as a measured zero |

**178 of the 181 lines reach a unit.** A line crosses 3 units in the median and
as many as 10, and only 37 of the 178 stay inside a single unit, which is why the
apportionment is not optional: attributing a whole trip to one unit would be a
choice among as many as ten.

1,087.56 km of the layer's 1,219.26 km fall inside the units, 89.20%.

### The balance closes on all three quantities

What the units account for plus what falls outside them equals what the file
holds. The check is written that way, and not as allocated equals total, because
part of the layer genuinely leaves the study area: the lines run to municipios
outside Bogotá.

| Quantity | Allocated to units | Outside every unit | Sum | The layer |
|---|---:|---:|---:|---:|
| Trips per week | 530,018.5282 | 26,979.0521 | 556,997.5804 | 556,997.5804 |
| Trips per day | 107,844.3591 | 5,424.9465 | 113,269.3056 | 113,269.3056 |
| Kilometres | 1,087.5609 | 131.6974 | 1,219.2583 | 1,219.2583 |

95.2% of the weekly trips fall inside the thirty units.

The opposite failure has its own check. The shares of one line over the units it
crosses cannot exceed the whole of it, so anything above 1 means two unit
polygons overlap and a trip is being counted twice. The largest covered share is
**1.000000004**, against a tolerance of 1.000001. The tolerance is deliberately
not machine epsilon: a line split into as many as ten fragments, summed and
divided by its own length, lands a few parts per billion above one without
anything being wrong, while an overlap between two cadastral polygons would show
up in percentage points.

### Verdict by check

| Check | Result | Verdict |
|---|---|---|
| Every unit of the layer has exactly one row | 30 rows for 30 units | **Pass** |
| The table carries exactly the declared columns, in the declared order | 15 against 15 declared | **Pass** |
| Every declared quantity is present under its mode-prefixed name | 0 missing | **Pass** |
| Trips per week allocated plus outside equals the layer | 530,018.5282 + 26,979.0521 = 556,997.5804 | **Pass** |
| Trips per day allocated plus outside equals the layer | 107,844.3591 + 5,424.9465 = 113,269.3056 | **Pass** |
| Kilometres allocated plus outside equals the layer | 1,087.5609 + 131.6974 = 1,219.2583 | **Pass** |
| No line is allocated more than once over | largest covered share 1.000000004, tolerance 1.000001 | **Pass** |
| No negative trip count | 0 negative | **Pass** |
| Weekly over daily lies between 1 and 7 in every unit | observed 4.737 to 5.545 days per week | **Pass** |
| The declared endpoints are the ends of the geometry | largest gap 0.000000 m | **Pass** |
| The per-km² column is the variable over the area of its unit | compared to 1 × 10⁻¹² | **Pass** |
| The per-inhabitant column is the variable over `POPULATION_2023` | compared to 1 × 10⁻¹² | **Pass** |
| A unit no line reaches carries a zero and the status `MEASURED` | 1 unit at zero, UPL07 | **Pass** |
| Every exported file is on disk and none is empty | 2 of 2 | **Pass** |

Two of these are worth naming for what they would catch. **Weekly over daily
between 1 and 7** is the check that the two expansion columns are what D35 says
they are: if `ResultadoExp` were not `f_exp` times a number of days in the week,
the ratio would leave that range. The observed 4.737 to 5.545 is the working-week
pattern the layer is built around. **The declared endpoints against the
geometry** compares the `Xo`, `Yo`, `Xd`, `Yd` columns with the first and last
vertex of each line, because the origin and destination allocations are computed
from those columns and would otherwise be trusted on their name alone.

### What the exported table holds

One row per unit, 30 rows and 15 columns, `analysis__exposure_by_unit.csv` and
its parquet twin, with `reference__exposure_dictionary.csv` beside them naming
every column, its unit and how it was computed. `YEAR` is null on every row: the
layer is a snapshot and declares no year.

| Column | Unit | What it is |
|---|---|---|
| `SCALE`, `AREA_CODE`, `AREA_NAME`, `AREA_UNIT_KM2` | — | identity of the unit, spelled as every other table spells it |
| `YEAR` | — | null, the layer being a snapshot |
| `POPULATION_2023` | inhabitants | the denominator of the column below, from the population panel |
| `BICYCLE_TRIPS_PER_WEEK_BY_LENGTH_SHARE` | trips per week | **the variable** |
| `BICYCLE_TRIPS_PER_DAY_BY_LENGTH_SHARE` | trips per day | the same apportionment applied to `f_exp` |
| `BICYCLE_TRIPS_PER_WEEK_AT_ORIGIN` | trips per week | alternative allocation |
| `BICYCLE_TRIPS_PER_WEEK_AT_DESTINATION` | trips per week | alternative allocation |
| `BICYCLE_LINE_KM_INSIDE` | km | alternative allocation, carrying no trip count |
| `BICYCLE_LINES_TOUCHING` | count | how many lines reach the unit |
| `BICYCLE_TRIPS_PER_WEEK_PER_KM2` | trips per week per km² | the variable over the area of the unit |
| `BICYCLE_TRIPS_PER_WEEK_PER_INHABITANT_2023` | trips per week per inhabitant | descriptive only, never a series |
| `VALUE_STATUS` | — | `MEASURED` on all 30 units |

Every quantity carries its mode in the name, so a second exposure layer adds
columns instead of colliding with these.

The two population columns were null when this route was first built and are not
any more: the census integrated in section 14 fills them. They carry **2023** in
their names because that is the year the layer declares — the ArcGIS export in
its metadata, the only date the desire lines have — and because the population is
a series while the trips are a snapshot, so the rate has to name the year of its
denominator. Bicycle trips per inhabitant of 2023 run from 0.00 to 0.21 per week,
median 0.05. **The column is descriptive and enters no model with a time
dimension**, and the run says so as a warning on every execution: a snapshot over
a moving denominator would vary from year to year on the denominator alone. The
models take their denominator from the population panel instead. See D36.

| Quantity | Minimum | Median | Maximum |
|---|---:|---:|---:|
| Trips per week | 0.00 | 13,198.84 | 61,687.33 |
| Trips per day | 0.00 | 2,525.58 | 12,940.14 |
| Line km inside | 0.00 | 27.02 | 88.81 |
| Lines touching | 0 | 17.5 | 49 |
| Trips per week per km² | 0.00 | 983.07 | 9,103.10 |

The three most exposed units are **UPL16 Edén** with 61,687 trips per week,
**UPL28 Rincón de Suba** with 49,058 and **UPL15 Porvenir** with 43,149. Edén is
also the densest at 9,103 trips per week per km², so the ranking is not an
artefact of unit size.

### The four allocation rules, compared by rank

Spearman rank correlation over the thirty units, the variable first. The three
alternatives are exported so that the sensitivity of a result to the rule can be
shown rather than asserted; none of them is a model variable and the dictionary
marks each as an alternative.

| | By length share | At origin | At destination | Line km inside |
|---|---:|---:|---:|---:|
| **By length share** | 1.000 | 0.813 | 0.798 | 0.781 |
| **At origin** | 0.813 | 1.000 | 0.973 | 0.498 |
| **At destination** | 0.798 | 0.973 | 1.000 | 0.525 |
| **Line km inside** | 0.781 | 0.498 | 0.525 | 1.000 |

Two things follow. **Origin and destination agree with each other at 0.973** and
disagree with the variable at 0.80, which is what a difference of concept looks
like rather than a difference of method: both endpoint rules say where trips
begin and end, close to where people live and work, and the variable says how
much cycling passes through a place. **The kilometres alone correlate 0.781 with
the variable and only 0.50 with the endpoint rules**, so the apportionment is not
merely a restatement of how much line a unit contains: the trip counts carry
information the geometry does not.

The endpoints are not all inside the study area. 173 of the 181 origins fall in a
unit (95.6%), carrying 534,638 of the 556,998 weekly trips, and 169 of the
destinations (93.4%), carrying 523,190. That is a further reason the endpoint
rules are alternatives and not candidates: each of them discards a different
handful of lines entirely.

### Torca is an observed zero

**No bicycle desire line reaches UPL07 Torca at all.** It is the only unit at
zero, it carries `MEASURED` like every other, and it is the largest unit of the
study at 53.82 km². A zero and a missing value are made to look different in
every place the number appears: the row says `MEASURED`, and on the choropleth
the unit keeps the bottom of the ramp — zero is a value and belongs on the
scale — with a hatch of its own, because at the bottom of a ramp reaching sixty
thousand an exact zero and a unit with two thousand trips are the same pale
colour. A unit that could not be measured would leave the ramp for a grey and a
coarser hatch instead; none exists in this run, so that legend entry is not
drawn.

### Two limitations the number carries

**The lines are straight.** Sinuosity — length over the straight distance between
the endpoints — is exactly 1.000 on all 181 lines, at the minimum, the median and
the maximum. Each line runs from the centroid of an origin zone to the centroid
of a destination zone in a single segment, so it is not a route: it does not
follow any street, and the units it is measured as crossing are the units the
straight line crosses, not the ones a cyclist would ride through. The
apportionment is exact arithmetic on a geometry that is itself an abstraction of
the trip.

**The 181 lines are a selection from a table of at least 7,212, and the criterion
is not known.** `ORIG_FID` runs from 156 to 7,212 with 181 distinct values, so
the file was exported from a parent table of at least 7,212 features, roughly
forty times its size. Nothing in the file or in its ESRI metadata says how those
rows were chosen. If the selection was by volume, the variable measures the
principal corridors rather than exposure, and the two are not the same quantity.
The layer also declares no year: the metadata dates its own export in ArcGIS in
November 2023 and says nothing about the survey behind it.

Both are questions for my advisor and neither is answerable from the delivered
data. Until they are answered the exposure can be described in the Datos chapter
with its limits declared, and no result rests on it.

---

## 14. The population panel

Run `run_20260901_092902`, route `population`, command
`python -m src.run_pipeline population`. **Every check passed.** This is the
denominator: a casualty count becomes a rate only when it is divided by the
people who were there to be hurt. The decision is D36, which fills the socket D35
declared and changes its key from the unit to the unit and the year.

The source is `osb_demografia-poblacion-upl.csv`, one row per unit, year, sex and
single year of age. **175,956 rows, no nulls, no duplicates on that key**, over
the 33 units of Decreto 555 de 2021 and the years 2005 to 2035.

### Funnel

| Stage | In | Out | Cause of the difference |
|---|---:|---:|---|
| load territorial units | 30 | 30 | — |
| read the population file | 175,956 | 175,956 | the declared columns only; the life-course and age-band labels are groupings of the age already read |
| add the population over sex and age | 175,956 | 1,023 | −174,933 rows to the sum: one row per unit and year in place of one per sex and age within it |
| restrict the population to the study | 1,023 | 540 | −483 unit-years outside the study: 3 units the cartography does not carry, and the years outside 2007–2024 |

The file as delivered holds 233,245,334 person-years over its 33 units and 31
years. The study's window over its 30 units holds 132,448,396 of them.

### The grid is full, and a hole would stop the run

**30 units × 18 years = 540 cells, every one of them filled.** The panel is built
as the complete grid first and the file joined onto it, so a unit-year the file
did not cover would arrive as a null the check can see rather than as a row that
is simply absent.

That it is a failure and not a warning is deliberate, and the asymmetry with the
predictors is the point: a predictor missing for one unit-year leaves a hole a
reader notices, while a denominator missing for one unit-year silently removes
that cell from every model built on it, and nothing in the output would say which
cell went.

### Verdict by check

| Check | Result | Verdict |
|---|---|---|
| The table carries exactly the declared columns, in the declared order | 5 against 5 declared | **Pass** |
| One row per unit and year, with no unit and no year missing | 540 rows against 30 units × 18 years | **Pass** |
| Every unit-year of the study has a population | 0 cells with none | **Pass** |
| No population is zero or negative | 0 cells at or below zero | **Pass** |
| The table holds exactly the people the file holds for those units and years | 132,448,396 against 132,448,396 | **Pass** |
| The file has one row per unit, year, sex and age | 0 duplicate rows | **Pass** |
| Every unit name in the file matches the cartography character for character | 30 of 30 matched | **Pass** |
| The units the file adds to the study are the declared ones | UPL01, UPL02, UPL06 against the three declared | **Pass** |
| Every exported file is on disk and none is empty | 2 of 2 | **Pass** |

Two of these carry more than they look like. **The balance** is what says the sum
over sex and age neither dropped a row nor counted one twice: every person in a
study cell of the file is in the table exactly once. **The name check** is what
says the join is right at all. The join runs on the code, so the code cannot be
the evidence for it — the file numbers its units 1 to 33 and the cartography
spells them `UPL01` to `UPL33`, and a mapping that is merely well-formed would
still join the wrong places together. The names were delivered independently of
the cartography and all thirty agree character for character, accents included.
Any one of them disagreeing stops the run.

### What the denominator looks like

| | 2007 | 2024 |
|---|---:|---:|
| The 30 units together | 6,869,136 | 7,892,809 |
| Smallest unit | — | 120,770 (UPL07 Torca) |
| Largest unit | — | 440,572 (UPL11 Engativá) |
| Median unit | — | 261,151 |

The city of the study grows 14.9 % across the period. **What the units do
individually is the argument for keeping the year**, and it is not a summary of
that 14.9 %:

| | Change 2007 → 2024 |
|---|---|
| Smallest | **−28.5 %**, UPL33 Barrios Unidos (189,810 → 135,762) |
| Largest | **+557.9 %**, UPL07 Torca (18,357 → 120,770) |
| Median | +16.5 % |
| Units that lost population | 7 of 30 |

A denominator averaged into one number per unit would put the same figure under a
2008 casualty count and a 2024 one in a place where six times as many people now
live, and it would do it while being collinear with the unit effect and dropping
out of the model altogether. Torca is also the unit no bicycle desire line
reaches and the largest of the thirty by area, so it is the unit where every
choice of this kind lands hardest.

### The three units the study does not have, in people

The file covers the 33 UPL of Decreto 555 de 2021 and the delivered cartography
covers 30. The three it adds are the rural units, where the urban predictors are
largely undefined. **This is the first place the study universe can be measured
in people rather than in polygons.**

| Unit | 2007 | 2024 |
|---|---:|---:|
| UPL01 Sumapáz | 4,947 | 3,305 |
| UPL02 Cuenca del Tunjuelo | 9,188 | 19,888 |
| UPL06 Cerros Orientales | 1,298 | 2,658 |
| **Together** | **15,433** | **25,851** |
| **Share of the city the file describes** | **0.224 %** | **0.326 %** |

Across 2007–2024 the three never exceed **0.33 %** of the city. The study covers
99.7 % of Bogotá's population, and it is exported year by year in
`presentation__population_outside_the_study.csv`. It confirms the universe rather
than qualifying it.

The warning is raised where the file is read and not where the summary is
printed, so a route that only borrows one year of the population — `exposure`
does — carries it too. The same applies to the open question below. A caveat that
appears only when somebody asks for the summary is a caveat that stops being
seen.

The file spells the first of them `Sumapáz`, with an accent the official name
does not carry. It is reported as the file spells it.

### What is open, and it is not answerable from the file

**Which years are measured and which are projected or backcast.** The file spans
2005 to 2035. No census covers that, so some of those years are projections, and
the ones before 2018 are probably backcasts of one. Nothing in the file or
shipped beside it says which is which.

**The shape of the series is not evidence for it.** A smooth curve is what a
projection and an interpolated census both look like, and reading provenance off
one would be inference presented as fact. The run says so on every execution
rather than letting the panel look more solid than it is.

It matters for the study period rather than for the arithmetic. If 2007–2017 is
backcast from the 2018 census, the denominator of the first eleven years is a
model and not a count, and that belongs in the same paragraph as the ρ
correction: both are places where the data before 2018 are of a different kind
from the data after it. To be confirmed against the source before any document
says which years are which.

---

## 15. Travel exposure from the mobility survey

Run `run_20260908_101110`, route `exposure`, command
`python -m src.run_pipeline exposure`. **Every check passed.** This is the
study's exposure: how much travel of each of four road user types passes through
each unit, per survey year and per kind of day, built from the household mobility
survey rather than received as finished desire lines. The decision is D38, which
supersedes D35 for the variable and part of D36 for the denominator.

**All four years are measured: 2011, 2015, 2019 and 2023.** The table is 960 rows —
240 for 2011 and 2015 over two day types each, 120 for 2019 over one and 360 for
2023 over three.

**2011 is the one year that could not be a declaration alone**, and it is the case
§6b of the inventory exists to catch. Its two day types live in two Access databases,
so the day type is a property of the file a record came out of and no field of
`MobilitySurvey` could say that. It was reported rather than absorbed, the advisor
took the decision, and the change was made once. What it cost is below and in
`docs/implementing-2011.md`.

**Adding 2019 changed no measurement.** The reading, the geometry, the
apportionment, the balance, the checks and the figures are the same code, and
every 2023 figure in this section is identical to what it was on
`run_20260907_231531`. What 2019 added to the machinery is two things, both of
them declarations rather than logic: a duration expressed as a rule instead of a
column name, because three of the four surveys state it three different ways, and
a list of zone codes that name no place. Both are dispatched exactly as the day
type already was.

**Adding 2015 changed no measurement either, and this time it was verified against
the previous run row by row: 2019 and 2023 come out identical to the last decimal
over all 480 of their rows and every column.** What 2015 added is three
declarations — the third and last duration rule, for two `HH:MM:SS` columns; a
day-type rule reading a flag the delivery already wrote on each record; and a
`SurveyZoning` field saying that a repeated zone code means one zone delivered in
pieces. One check had to change, and it had been wrong since it was written: see
below.

**What 2015 adds to the study is a second day type.** Its `DIA_NOHABIL` is a
Saturday and only a Saturday, so the day type is a dimension two of the three
measured years carry rather than a property of 2023 alone, which is what it looked
like after 2019.

**Adding 2011 changed the declaration and no measurement, and that was verified the
same way: 2015, 2019 and 2023 come out identical to the last decimal over all 720 of
their rows and every column**, compared against `run_20260908_052802` rather than
merely re-checked. What 2011 added is four things:

- **`MobilitySurvey.trips` is a tuple of `TripSource`**, each pairing a table with
  the day type that file carries, or with `None` where the file holds more than one
  and the year's rule decides. `DayTypeFromSource` reads the tag the reader writes.
  No day-type handler opens a file, which was the condition on the change.
- **`AccessTable` beside `DelimitedTable`**, dispatched through
  `surveys._TABLE_READERS` — the third registry in the module. `pyodbc` is imported
  inside the reader so the other three years still run where the driver is absent,
  and `requirements.txt` gains it in the same commit.
- **`SAMPLE_SUPPORT`, a twentieth column on the exposure table**, saying whether the
  sample behind a row reaches the scale of one unit. It is separate from
  `VALUE_STATUS` because that column says whether there is a number and every
  derived-column check filters on it.
- **One function spells the zone code on both sides of the join.** It had been
  spelled twice by two pieces of code that agreed for three years and would not have
  agreed with 2011, whose zone codes come out of a database as doubles.

### 2011, and the year that had to be argued rather than declared

**Two published totals, and both are reproduced.** `F_EXP` sums to **17,611,061.27**
on the weekday against Tomo I's 17,611,061, and to **14,022,327.55** on the Saturday
against its 14,022,327. The weekday figure is quoted again by the 2015 delivery's
Tomo I, so it is confirmed by two publications.

**Both published modal splits are reproduced, mode by mode, on both kinds of day.**
Tomo I's Figura 18 gives the weekday split and Figura 21 the Saturday's:

| Mode | Weekday published | Read | Saturday published | Read |
|---|---:|---:|---:|---:|
| A pie | 46 % | 46.2 % | 34 % | 33.9 % |
| TPC | 20 % | 20.4 % | 23 % | 22.9 % |
| Automóvil | 10 % | 10.3 % | 21 % | 20.9 % |
| TransMilenio | 9 % | 8.5 % | 9 % | 8.2 % |
| Taxi | 4 % | 3.5 % | 6 % | 6.3 % |
| Bicicleta | 3 % | 3.5 % | 2 % | 2.2 % |
| Moto | 2 % | 2.3 % | 4 % | 3.5 % |

**The duration rule is verified against a published figure, as 2019's and 2015's
were.** `Min_Inicio` and `Min_Fin` are whole minutes from midnight, and that was
established against a second pair of columns rather than read off the names:
`Min_Inicio` equals `HR_INI × 60 + MIN_INI` and `Min_Fin` equals
`P18HF_D × 60 + P18MF_D` on all 122,361 weekday records and all 4,035 Saturday ones.
The columns run 240 to 1,680, which is 04:00 to 04:00 the next day — the window the
questionnaire states — so nothing wraps and `wrap_at_midnight` is off; rounding is
irrelevant rather than false, because the columns are already whole minutes. Tomo I
publishes a second modal split with the walking trips of under fifteen minutes
removed, and the derivation reproduces the whole figure: **walking 28.3 % against a
published 28 %, TPC 27.2 % against 27, car 13.8 % against 14, TransMilenio 11.3 %
against 12, taxi 4.7 % against 5, bicycle 4.6 % against 5, motorcycle 3.1 % against
3.**

**The strongest control 2011 has is record for record, and it is in the delivery's
own training folder.** `Ejemplos Capacitación/03_Ejemplo Capacitación
Matrices_FE_Hogares.xlsx` holds the consultant's extract of the household survey's
private-vehicle trips in the morning peak: 1,434 records with `F_EXP`, `ZAT_ORIG`
and `ZAT_DEST`. Filtering the database on `Modo_Principal = Privado` and
`PICO_AM = 1` gives **1,434 records whose weights sum to 176,849.2748766211 against
the workbook's 176,849.2748766211, a difference of exactly zero**, with 1,415 of
them agreeing on origin, destination and weight together and every one of the 1,434
agreeing on the weight to six decimals. The nineteen that differ carry the same
weight and a different destination zone — a handful of zones recoded between the
version the example was cut from and the version delivered. One file read by two
people, agreeing on every weight, settles the weight column, the mode label and both
zone columns at once.

**A fifth control is a neighbouring survey recounting this one.** Tabla 43 of the
2015 delivery's Tomo IV reads the 2011 database and publishes, for the study region
on a weekday: PEATON 8,136,778, TRANSMILENIO 1,494,082, OTROS 106,151, total
17,611,061 — identical to the trip on all four. The modes its own footnote says it
recomputed under 2015's hierarchy differ by tenths of a per cent.

**The Emme matrices are not a control and it matters that this was checked.** The
eight matrices of `Matrices Finales/` look like the artefact this pipeline rebuilds
and are not: the year's matrix training deck describes them as built from the
intercept surveys and the traffic counts, corrected for double counting and adjusted
in Emme, with the household survey contributing only the pairs interception missed
and even those re-expanded with the intercept factor, since *"la expansión de
hogares no permite utilizar directamente los viajes de esa matriz"*. Bicycle goes
from 69,648 to 15,538 trips in that process.

**One unit of the factor is a trip on one day of the record's own kind**, and 2011
is the year where the two day types expand to **different territories**. The weekday
households' `F_EXP` sums to **2,444,260** against the 2,444,256 households Tomo I
declares for the study region — 2,148,884 in Bogotá plus 295,372 in the seventeen
municipal cabeceras — and the Saturday's to **2,149,087** against Bogotá's 2,148,884
alone, because Tomo II says *"la muestra para el día sábado se diseñó solo para
Bogotá"*. `F_EXP` is the same number on the trip, the person and the household, on
all 122,361 records.

**The day type is the database, and the delivery's dictionary contradicts itself
about it.** Module A of the database manual calls `DIA` the day of the interview and
module D calls it the day of the trip, which the questionnaire puts a day apart.
`DIA` equals the weekday of the date beside it on all 16,157 households, which
settles nothing. Behaviour settles it: across the five values of the weekday file
the households make **7.02 to 7.43 trips** and **10.4 % to 11.6 %** of those trips
are for study, so none of the five is a Sunday; the Saturday file has **2.3 %** for
study, 9.8 % shopping and 9.4 % recreation, so the sixth is not a Friday.

**A sixth of 2011's trips cannot be placed, and they are exactly the imputed
records.** `DONANTE` and `ID_DONANTE_VJ` are set on 21,515 weekday records and 440
Saturday ones, and those are **exactly** the records with no `ZAT_ORIG` and no
`ZAT_DEST` — zero imputed records carry a zone, zero unimputed records lack one, in
both databases, and the zone is absent at both ends together or at neither. Tomo III
explains it: 8,218 people travelled and did not answer the trip module, and the
consultant imputed their trips from a donor of similar occupation, stratum, locality
and day without imputing a geography. The unimputed table carries no origin or
destination zone at all, so there is nothing to recover. In the four measured modes
that is **12,733 records, 2,452,373 trips a day**, counted in the balance beside
every other trip that cannot be placed.

**2011's Saturday is measured, exported and marked.** Its 120 rows carry
`SAMPLE_SUPPORT = CITY_LEVEL_ONLY`, and the marking is the consultant's statement
rather than our judgement: Tomo III expanded and analysed the Saturday *"a nivel de
ciudad y estrato socioeconómico"* where the weekday was analysed *"a nivel de
UPZ"*, its non-response imputation used the code `TL` for every locality together
because there was no sample by locality, and Tomo I adds that *"el nivel de error de
esta estimación es mayor que para el día hábil"*. Seven of the 240 Saturday rows come
out at zero, three of them whole units with no cycling. **It behaves like a
Saturday**, which is the check that would have caught a misread file: inside the
thirty units and against its own weekday, walking falls 29 % and cycling 18 % while
car travel rises 89 %, where 2015's falls 32 % and 17 % and rises 50 %.

**The sliver threshold keeps its value on a measured indifference, the third year to
do so.** 2011 borrows 2015's zoning, so the overlay is the same and there is no gap
in it — 1,285 fragments, the largest below the cut at 0.0994 % of its zone and the
smallest above it at 0.1007 %. Swept from a ten-thousandth to a hundredth, **the
largest per-unit figure moves 0.41 %** and the pedestrian one 0.33 %, against
0.096 % for 2015 and 0.16 % for 2019 on the identical geometry. The sweep had to be
re-run rather than cited: two years sharing a zoning share the gap and not the
indifference.

### 2015, and the control that makes it the best-verified year

**The expansion factor was one of four candidates and the survey's own publications
choose between them.** `PONDERADOR_CALIBRADO_VIAJES` — which is
`PONDERADOR_CALIBRADO`, the person's calibrated weight, times a
`FACTOR_AJUSTE_TRANSMILENIO` taking only two values, 1.0 on 652 records and
1.20293649023643 on the other 146,599 — reproduces **all twenty-four published mode
totals**: the twelve of Tabla 43 of Tomo IV for the working day and the twelve of
Tabla 119 for the Saturday. `FE_TOTAL` is the uncalibrated design weight
(`PI_K_I × PI_K_II × PI_K_III` on every record), `PONDERADOR_CALIBRADO` is the
person weight, and `FACTOR_AJUSTE` sums to 113,157 over the whole file and is not a
count of trips at all. None of the three reproduces anything published.

**And the delivery publishes the origin-destination matrices themselves, which is
the strongest external control this stage has ever had.** `matriz_habil.xlsx` and
`matriz_nohabil.xlsx` are the artefact this pipeline rebuilds, and the reading
reproduces them **to the last decimal on both kinds of day**:

| | Published | Reconstructed |
|---|---:|---:|
| `matriz_habil`, all modes | 17,239,382.6867 | 17,239,382.6867 |
| `matriz_nohabil`, all modes | 15,712,253.8360 | 15,712,253.8360 |
| `matriz_medio_nohabil`, bicycle | 723,004.4120 | 723,004.4120 |
| `matriz_medio_nohabil`, private car | 2,663,784.8537 | 2,663,784.8537 |
| `matriz_medio_habil`, bicycle | 846,727.0479 | 846,727.0479 |
| `matriz_medio_habil`, private car | 1,829,032.5781 | 1,829,032.5781 |

**That check is also what found the first zone sentinel.** Before it was set aside
the two readings differed by 1,665.4631 trips on the weekday, and **every
disagreeing pair had a `0` at one end** — 16 records, all in Soacha. The consultant
had dropped them and documented it nowhere. It is a better check than a city total
for exactly that reason: a total can close while individual pairs are wrong.

**The agreement is under the matrices' own exclusion rule, and the second sentinel
is where the two readings part company on purpose.** `1000` is not a defect but a
code for a place outside the eighteen municipalities surveyed, and the consultant
kept it in their matrices as a pseudo-zone — reasonable for a table of flows
between codes, impossible for a study that has to put a trip on a map. So the
figures above exclude the records with no zone and the sentinel `0`, as the
matrices do, and the pipeline additionally sets aside zone 1000: **59,115 trips a
day on the weekday and 89,642 on the Saturday**, in the four measured modes. Saying
the matrices are reproduced "once the codes naming no place are set aside" would
have claimed agreement on the one record the two readings decide differently.

**The derived duration is verified twice and neither check needs rounding.**
`HORA_INICIO` and `HORA_FIN` are `HH:MM:SS` text with 503 records crossing
midnight, and the gap reproduces the delivery's own `DIFERENCIA_HORAS` on **all
147,251 records** — where 2019's rule reproduces its auxiliary file on all but one.
It also reproduces both published fifteen-minute walking splits: **1,976,421** trips
a day under fifteen minutes on the weekday against a published 1,976,421, and
**1,037,074.9** on the Saturday against 1,037,075. Rounding to the minute, which
2019 must do because it stores a clock as a fraction of a day, would move 619
Saturday walking trips across the threshold here and break the second of those. It
changes nothing else — the plausibility test rejects the same 1,096 records either
way and not one record changes side — so 2015 declares `round_to_minute` off.

**One unit of the factor is a trip on one day of the record's own kind**, which is
2019's answer and not 2023's. Each day type's subsample expands to the whole
universe on its own: the household weights sum to **2,967,290** over the 24,622
weekday households and **3,045,530** over the 3,591 Saturday ones, and the person
weights to 9,059,251 and 9,023,719.

**And `DIA_NOHABIL` is a Saturday**, established from the interview date rather than
from the flag's name. 2015 asks about the day before the interview, and the flag is
set on exactly the 3,591 households interviewed on a **Sunday** and on no other. Had
it been about the interview day, the 4,237 Saturday interviews would have carried
it; they do not, because they report a Friday. **No household was interviewed on a
Monday**, so the survey has no Sunday reference day at all. Tomo IV titles its
chapter on them *"Indicadores día sábado"*. The date and the flag agree on all
147,251 records; the flag is what the pipeline reads, because it is what the
consultant grouped by when publishing the matrices, and because one household's row
in the household file is displaced by a column and its date is unreadable.

### What the sources give, and what is set aside

The 2011 databases hold 126,396 records between them, the 2023 trip module 100,174,
the 2019 one 134,497 and the 2015 one 147,251. Every one of them is accounted for.

| | 2011 records | 2011 trips/day | 2015 records | 2015 trips/day | 2019 records | 2019 trips/day | 2023 records | 2023 trips/day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| The four measured modes | 62,040 | 15,898,463.7 | 79,225 | 16,670,116.4 | 67,941 | 9,262,670.3 | 56,711 | 9,221,240.5 |
| Modes deliberately outside the study | 47,342 | 12,165,497.4 | 65,897 | 15,814,747.3 | 52,571 | 7,640,049.7 | 37,835 | 6,208,757.0 |
| Impossible for the mode that reported them | 4,281 | 1,117,054.4 | 1,096 | 324,435.1 | 9,623 | 1,397,746.3 | 5,344 | 960,910.3 |
| No expansion factor, dropped | 0 | — | 0 | — | 0 | — | 284 | — |
| Records with no origin or destination zone | 12,733 | 2,452,373.4 | 1,033 | 172,985.5 | 4,362 | 695,819.3 | 0 | 0.0 |
| **The file** | **126,396** | **31,633,388.8** | **147,251** | **32,982,284.3** | **134,497** | **18,996,285.6** | **100,174** | **16,390,907.8** |

**The two largest file totals belong to the two years that hold two whole days, and
neither is a bigger city.** 2011's and 2015's factors expand to one day of the
record's own kind, so each file holds a whole weekday *and* a whole Saturday —
17,611,061 plus 14,022,327 for 2011, and 17,251,733 plus 15,730,551 for 2015. 2019's
holds one typical day and 2023's holds an average day of its collection period. This
is exactly why nothing may be compared across years on the column the balance closes
on; see the cross-year table below.

**2011's row for the records with no zone is the largest in the table and it is not
a coding failure.** They are exactly the imputed records, and the consultant did not
impute a geography for them; the paragraph above has the demonstration.

The two sides of the trips column are different groupings of the same values, so
that check is a check and not a restatement: a mode lost between the mapping and
the totals would show there and nowhere else.

**2015's published total is two external controls added together**, because the
file holds two whole days and neither alone is what it contains: 17,251,733 trips
on a working day, which Tabla 59 of Tomo IV publishes outright, plus 15,730,551 on
the Saturday, which is the sum of the twelve modes of Tabla 119. Both halves are
reproduced mode by mode.

**2019's published total is an external control and 2023's is our own sum.** The
2019 delivery publishes the trips of a typical day by mode in indicator IND_102 of
its `Anexo D`, to the decimal, and states the total in words at paragraph 4.5 of
the Etapa V report — *"En un día típico, se realizan 18,996,286 viajes en el área
de estudio"*. The sum of `f_exp` reproduces all sixteen mode figures exactly. For
2023 the declared total is the sum of `fexp_vj` over the trip module itself, which
is weaker and is labelled as such in the configuration.

**And the whole 2019 reading was checked against a published sub-city table**,
which is stronger than any city total. Indicator IND_64 gives the trips of each of
the 134 UTAM. Grouping our reading by the household's UTAM under the indicator's
own rule — walking of fifteen minutes or more, every other mode of any duration —
**132 of the 134 agree within 0.01 %, 130 of them to the last decimal**, and the
total over them is 15,965,583 against 15,961,478. That single comparison exercises
the expansion factor, the mode labels, the derived duration and the household key
at once.

**The 284 records without an expansion factor are dropped and the run says so.**
The survey's own published total is the sum that excludes them, so they sit
outside the universe the file describes rather than leaving a hole in it, and
imputing a weight would be inventing trips.

The four modes, against each survey's own figures. 2015 first, whose twelve
predominant-mode codes are published one by one in Tabla 43 and Tabla 119 — the
figures below are the two days added, because that is what the file holds:

| Actor type | Source code and label | As the survey expands them | Measured, after the removals |
|---|---|---:|---:|
| `PEDESTRIAN` | 13 `PEATON` | 9,565,549 | 9,228,447 |
| `CAR` | 6 `AUTO` | 4,495,181 | 4,415,221 |
| `BICYCLE` | 10 `BICICLETA, BICICLETA CON MOTOR` | 1,569,731 | 1,551,243 |
| `MOTORCYCLE` | 7 `MOTO` | 1,537,075 | 1,475,206 |

**The walking floor is not the same in the four years, and it is 2019 that
differs.** 2023 reports no walk shorter than three minutes; 2015 reports none
either, once its zero-length records are separated out — 0.22 % of its weekday
walking is under three minutes and the same 0.22 % reports exactly zero, so the
floor is three minutes, the one Tomo IV says it took from 2011. **2011's own floor
is three minutes and its questionnaire states it**: *"para viajes realizados
completamente a pie incluya siempre los viajes al trabajo y estudio; para otros
propósitos solo aquellos cuya duración sea mayor a 3 minutos"*, and 0.43 % of its
weekday walking comes in under three minutes. **2019 has no
floor**: 1.46 % of its weekday walking, 101,168 trips a day, lasts under three
minutes. That is about a point and a half of 2019's pedestrian total that the other
three years never collected, and part of the 2015→2019 pedestrian rise is it. It is
not corrected, because imposing a floor on 2019 that its own publication does not
use would make this study's walking disagree with the survey's — but every
pedestrian comparison across those two years carries this sentence.

**2015 cannot put the bicitaxi anywhere, and that is a limitation and not a
decision.** Its `ILEGAL` code folds the bicitaxi in with the mototaxi, the informal
car, the collective taxi and the unlicensed charter, and nothing at the trip level
splits them. Reading the stages of those trips says **86 records and 46,840 trips a
day** used a bicitaxi — 3.0 % of what 2015 measures as cycling, against the 2.43 %
2019's own label carries. So the category is not identical across the two years and
the difference is about a thirtieth of one mode. Recovering it would mean taking the
stage rather than the trip as the unit of analysis, which is a different study.

Then 2019, whose sixteen labels are published one by one in indicator IND_102:

| Actor type | Source labels | As the survey expands them | Measured, after the removals |
|---|---|---:|---:|
| `PEDESTRIAN` | `A pie` | 6,941,798 | 5,289,067 |
| `CAR` | `Auto` | 2,291,877 | 2,109,417 |
| `BICYCLE` | `Bicicleta` + `Bicitaxi` | 1,207,248 | 1,054,216 |
| `MOTORCYCLE` | `Moto` | 915,314 | 809,971 |

And 2023, whose eleven labels group public transport where 2019 splits it five
ways:

| Actor type | Source labels | As the survey expands them | Measured, after the removals |
|---|---|---:|---:|
| `PEDESTRIAN` | `A PIE > 15 MIN` + `A PIE <15 MIN` | 6,098,788 | 5,209,139 |
| `CAR` | `AUTO` | 1,932,348 | 1,922,091 |
| `BICYCLE` | `BICICLETA` | 1,115,685 | 1,062,086 |
| `MOTORCYCLE` | `MOTO` | 1,035,329 | 1,027,925 |

Every mode label either survey carries is mapped to an actor type or declared as
deliberately not measured, and a label in neither stops the run. There is no
`OTHER` to fall through to: the study measures four modes and an unrecognised
label is a question for a person.

**The bicitaxi is inside 2019's `BICYCLE`, and its weight is recorded here so the
decision can be quantified later without re-running the year: 163 records,
29,379.85 trips a day, 2.43 % of what 2019 measures as cycling.** It is in because
the numerator already puts it there — the crash source maps `BICITAXI` to
`BICYCLE`, so a rider hurt on one is counted as a cyclist, and a denominator
excluding them would divide those casualties by an exposure that does not contain
them. 2023 has no bicitaxi label at all, so the category is not identical between
the two years, and that is the cost.

The scooter is not in. 2019's `Patineta` is 108 records and 13,503 trips a day,
and the casualty source has no scooter category for it to be paired with.

What 2015 set aside, in the modes it does not measure — again both days together:

| 2015 label | Trips/day | | 2015 label | Trips/day |
|---|---:|---|---|---:|
| TPC-SITP | 7,651,108 | | Intermunicipal | 379,090 |
| Transmilenio | 4,406,524 | | Alimentador | 357,140 |
| Taxi | 1,540,329 | | Ilegal/informal | 254,741 |
| Especial | 983,612 | | Otros | 242,202 |

And what 2019 set aside:

| 2019 label | Trips/day | | 2019 label | Trips/day |
|---|---:|---|---|---:|
| TransMilenio | 2,489,738 | | Intermunicipal | 353,530 |
| SITP Zonal | 1,511,470 | | Alimentador | 274,341 |
| SITP Provisional | 952,341 | | Otro | 219,906 |
| Transporte público individual | 681,994 | | Patineta | 13,503 |
| Transporte informal | 652,295 | | Cable | 949 |
| Transporte Escolar | 489,984 | | | |

### The records the geometry contradicts

**9,623 records in 2019 and 5,344 in 2023 name two zones further apart than their
mode could have covered in the duration they report, and are dropped.** The test
compares the shortest distance between the two zone polygons — the best case the
traveller could possibly have had — against a generous ceiling speed times the
record's own duration: 6 km/h on foot, 25 by bicycle, 80 for the two motor modes.

| Actor type | 2019 trips/day removed | Share of the mode | 2023 trips/day removed | Share |
|---|---:|---:|---:|---:|
| `PEDESTRIAN` | 1,297,400 | 18.7 % | 889,649 | 14.6 % |
| `BICYCLE` | 73,007 | 6.0 % | 53,600 | 4.8 % |
| `CAR` | 16,365 | 0.7 % | 10,257 | 0.5 % |
| `MOTORCYCLE` | 10,975 | 1.2 % | 7,404 | 0.7 % |
| **All four** | **1,397,746** | | **960,910** | |

It was found by drawing the 2023 desire lines and looking at them: the pedestrian
map was a tangle of lines crossing the whole city, for a mode whose trip-weighted
median line is 1.3 km. The extreme record is **82.3 km in 15 minutes**, and it is
not a centroid artefact — those two polygons are 61.8 km apart at their nearest
points and do not touch.

**The two years fail it in the same shape**, which is the evidence that the
threshold catches a real defect rather than ordinary variation: overwhelmingly a
pedestrian problem in both, under 1.2 % of every motorised mode in both, on two
surveys commissioned by different administrations and read through different
column names.

The duration was verified in both years before it was used, and 2019's had to be
built first.

- **2023 reads `duracion_min` directly.** It runs 3 to 14 minutes on the
  under-fifteen walking category and 15 to 439 on the over-fifteen one, so it
  agrees with a column derived independently of it.
- **2019 reports no duration at all.** It reports a departure and an arrival, both
  stored as fractions of a day — `hora_inicio_viaje` holds 0.333333333333333 for
  eight in the morning — so every datetime parser refuses them. The difference
  times 1,440, wrapped over midnight and **rounded to the minute**, is what the
  pipeline uses. It reproduces the delivery's own `Aux_DuraciónEODH2019.csv` on
  **134,496 of 134,497 records**; the exception is a trip from 9:00 to 12:00 that
  the auxiliary file records as 81 minutes instead of 180, so the defect is
  there. Checked against a second published figure, walking of fifteen minutes or
  more comes out at 3,956,916.53 trips a day against the 3,952,811.54 of indicator
  IND_104, 0.10 % apart.

**The rounding is not cosmetic.** `(0.302083333333333 − 0.291666666666667) × 1440`
is 14.999999999, not 15. Without rounding, 2019's walking above fifteen minutes
comes out at 3,590,383 instead of 3,956,917 — a tenth of the mode lost to floating
point, on the wrong side of a threshold.

**The trap that this avoided is worth recording.** Searching 2019's column list
for a duration matches `p34_aplicacion_durante_viaje`, because "durante" contains
"dura". That column is about whether the traveller used a mobile app. It parses,
it summarises, and every number out of it is meaningless.

**The ranking of the units does not move**, before or after. What moves is the
pedestrian line kilometres inside the units, from 28,184 to 8,025, because the
removed lines were long by construction — and the pedestrian figure goes from
lines crossing the city to short local structure, which is what walking looks
like. That the three motorised modes lose under one per cent between them is
evidence the threshold is not catching ordinary variation.

The removal is a named cause in the balance and not a filter applied before
counting, so the file's total still closes over it. See D38 for what is given up:
if the error was in the mode rather than the zones, a real trip has been removed
rather than reclassified.

### The kind of day

**2011 says it a fourth way: the day type is which of two databases a record came
out of.** `DiaTipico` holds 122,361 trips over 15,592 households and `DiaSabado`
4,035 over 565 — different samples of different households in separate files with
the same schema — so nothing on a record says which kind of day it is and no rule
reading an already-loaded frame can see it. That is why `MobilitySurvey.trips` is a
tuple of `TripSource`, each pairing a table with the day type its file carries.

**Which day each file holds was settled against behaviour, because the delivery's
own dictionary contradicts itself.** Module A of the database manual calls `DIA`
"día de la semana de realización de la encuesta" and module D calls it "día de la
semana en que se hizo el viaje" — the interview day and the trip day, which the
questionnaire puts a day apart with *"las actividades que realizó el día de ayer…
desde las 4 a.m. de ayer a las 4 a.m. de hoy"*. `DIA` equals the weekday of the
date beside it on all 16,157 households, which settles nothing by itself. What
settles it is what the records do: across the five values of the weekday file the
households make **7.02 to 7.43 trips** and **10.4 % to 11.6 %** of those trips are
for study, so none of the five is a Sunday; the Saturday file has **2.3 %** for
study, 9.8 % shopping and 9.4 % recreation, so the sixth is not a Friday. Tomo III
agrees in words: the survey ran *"encuestas de día típico (entre semana)"* and
*"encuestas de día atípico (sábado)"* and expanded the two separately.

**And 2011's two day types expand to different territories**, which no other year
does. The weekday households' `F_EXP` sums to 2,444,260 against the 2,444,256
households Tomo I declares for Bogotá plus the seventeen municipal cabeceras; the
Saturday's to 2,149,087 against Bogotá's 2,148,884 alone, because Tomo II says
*"la muestra para el día sábado se diseñó solo para Bogotá"*. Inside the thirty
units, which are all in Bogotá, that is largely absorbed — what falls outside is
measured rather than redistributed — but it is a difference of universe and not of
sample, and a document comparing the two has to say so.

**2019 surveyed one kind of day and no other, so it has no day-type dimension at
all.** Its block of the table is 30 units × 4 modes × 1 day type = 120 rows, and
`SATURDAY` and `SUNDAY` are absent from it rather than zero — D10 applied to a
dimension ragged by construction. Five statements in its own delivery say so:

- the questionnaire's trip module is addressed *"para las personas del hogar con
  5 años o más que se desplazaron el día anterior"* and reads *"los
  desplazamientos que realizó el día de ayer, desde las 4 a.m. de ayer a las 4
  a.m. de hoy"*;
- the cartilla's glossary defines a *viajero* as a person reporting at least one
  trip *"el día anterior a la realización de la encuesta"*;
- the report states the total as *"en un día típico"*;
- the published origin-destination matrices — the artefact this pipeline rebuilds
  — come only *"en un día típico"*, with peak and off-peak hours as the sole
  further breakdown and **no Saturday or Sunday matrix anywhere**;
- the chapter comparing 2019 against 2011 and 2015 lists every difference between
  the three surveys and never mentions the reference day.

The data agree. Across all seven days the fieldwork ran, travel participation
stays between **79.1 % and 80.6 %** and trips per person between **1.967 and
2.061**, and about 10 % of trips are for study on every one of them — which no
real Sunday looks like.

**The day-of-week flags are not a substitute and were declined.** `p32_lunes` to
`p32_domingo` are asked as *"¿Qué días de la semana realiza este viaje?"*, so they
are declared recurrence; 13,436 records carry the Saturday flag. A `SATURDAY` row
built from them would look exactly like 2023's and measure something else, and it
would omit by construction every trip made only at weekends, since such a trip was
never reported at all.

**2019's `fecha` column is the interview date, not the trip date, whatever its
dictionary says.** `Anexo B` calls it "Fecha del viaje"; it equals the household's
own `p5_fecha` on 78 % of records, and the questionnaire says the trips are
yesterday's. It happens not to matter here, because the year has one day type
either way, and it would have mattered a great deal for a year that did not.

**2023's day type comes from the household's interview date, shifted back one
day.** The technical sheet gives the reference period as the day immediately
before the interview. The sample that results:

| Day type | Households | Share of the surveyed universe |
|---|---:|---:|
| `WEEKDAY` | 17,554 | 0.7722 |
| `SATURDAY` | 2,990 | 0.1320 |
| `SUNDAY` | 2,211 | 0.0957 |

The shares are there because 2023's expansion factors represent the universe
**once over all seven reference days**, not once per day: its household factors
sum to 3,623,413 against the 3,667,331 the technical sheet declares. So the trip
factor summed within one day type gives that day type's share of an average day,
and the share above is what converts it into the trips of one such day. Both
columns are exported and the share travels with them, so either can be derived
from the other in the table it appears in.

**2019 answers that question differently, and the arithmetic that settles it is
the same.** Its household factor `Factor` sums to **2,995,531.78** against the
2,995,531.78 households indicator IND_5 publishes for the study area — a ratio of
1.000000. The whole sample represents the universe once, over a single kind of
day, so one unit of `f_exp` already is a trip on that day: the universe share is
1, no rescaling happens, and `TRIPS_PER_AVERAGE_DAY` and `TRIPS_PER_DAY_OF_TYPE`
hold the same number for that year.

**This is the field that must never be inherited, and 2019 shows why.** Had it
taken 2023's answer, every 2019 figure would have been divided by 0.77 and every
one of them would have looked entirely reasonable.

### From zones to units

| | 2019 | 2023 |
|---|---:|---:|
| Zones in the survey's zoning | 1,141 | 1,215 |
| Zones reaching at least one unit | 918 | 907 |
| Of those, divided between more than one unit | 246 | 11 |
| Sliver fragments discarded | 229 | 593 |
| Total area discarded | 395,860.00 m² | 4,762.90 m² |

The threshold is a thousandth of a zone's area in both years, and **the argument
that justifies it holds for 2023 and not for 2019**:

| | 2019 | 2023 |
|---|---:|---:|
| Largest fragment dropped, as a share of its zone | 0.0993 % | 0.0353 % |
| Smallest fragment kept | 0.1002 % | 1.7340 % |
| Kept fragments under 5 % of their zone | 264 | 5 |

For 2023 there is a gap of a factor of 49 between the two populations, so any
threshold between a ten-thousandth and a hundredth gives the identical answer.
**For 2019 the distribution runs continuously across the cut** — 0.0993 % below
against 0.1002 % above — because that zoning's boundaries do not nest inside the
UPL and its overlay is a spectrum of partial overlaps rather than slivers plus
splits.

**So for 2019 the threshold is arbitrary, and what that costs was measured rather
than argued.** Swept across the same two orders of magnitude, the largest per-unit
pedestrian figure moves **0.16 %**, Niza moves 0.2 %, and the city total moves
1,017 trips a day out of 4.16 million. The fragments in the continuum are numerous
but tiny, so they carry almost no travel. The threshold stays where it is for a
different reason in each year: an empirical gap in 2023, a measured indifference
in 2019.

**2019's overlay with the study's cartography is coarser and the numbers say so.**
It discards eighty times the area 2023 does and leaves 246 zones straddling a unit
boundary against 11. Both zonings are EPSG:4686 against 2023's EPSG:3116, and both
draw the same city, but the 2019 ZAT boundaries were not drawn to nest inside the
UPL. That is a difference in the delivery and not in the rule, and it is handled
by the same area apportionment: a zone lying across two units gives each the share
of its area that falls there.

**It is not what makes the two years disagree about walking.** Where they disagree
most — Suba — the two zonings are nearly identical: 8 zones against 8 in
Tibabuyes, 14 against 14 in Rincón de Suba, 28 against 28 in Niza, and the area
each assigns to each unit differs by under a tenth of a per cent. Over the thirty
units the largest difference in assigned area is 0.82 %.

For 2019, 27,437 desire lines were built between zone centroids, 178,248 km in all
with a median of 4.16 km, from 31,134 inter-zonal groupings of actor type, day
type and zone pair, and 1,078 intra-zonal groupings have no line and are spread by
area share instead. For 2023, 21,467 lines, 145,460 km, median 4.26 km, from
26,316 inter-zonal groupings and 1,197 intra-zonal ones.

### Funnel

| Stage | In | Out | Cause of the difference |
|---|---:|---:|---|
| read the 2011 mobility survey | 126,396 | 19,696 | −47,342 in modes outside the study, −12,733 with no usable origin or destination zone, −4,281 impossible for their mode, −42,344 to grouping into actor type, day type and zone pair |
| read the 2015 mobility survey | 147,251 | 26,396 | −65,897 in modes outside the study, −1,033 with no usable origin or destination zone, −1,096 impossible for their mode, −52,829 to grouping into actor type, day type and zone pair |
| read the 2019 mobility survey | 134,497 | 32,212 | −52,571 in modes outside the study, −4,362 with no usable origin or destination zone, −9,623 impossible for their mode, −35,729 to grouping into actor type, day type and zone pair |
| read the 2023 mobility survey | 100,174 | 27,513 | −284 with no expansion factor, −37,835 in modes outside the study, −5,344 impossible for their mode, −29,198 to grouping into actor type, day type and zone pair |
| apportion the 2011 survey over the units | 19,696 | 236 | −19,460 zone pairs replaced by one row per unit, actor type and day type |
| apportion the 2015 survey over the units | 26,396 | 240 | −26,156 zone pairs replaced by one row per unit, actor type and day type |
| apportion the 2019 survey over the units | 32,212 | 120 | −32,092 zone pairs replaced by one row per unit, actor type and day type |
| apportion the 2023 survey over the units | 27,513 | 360 | −27,153 zone pairs replaced by one row per unit, actor type and day type |
| assemble the long exposure table | 956 | 960 | +4 combinations no trip reached, materialised as measured zeros |

**2011 and 2015 produce 240 rows each, 2019 produces 120 and 2023 produces 360**,
because they have two day types, one and three. The table holds all three shapes at
once: a reader filtering it to Saturdays gets 2011, 2015 and 2023, and one filtering
to Sundays gets 2023 alone. Both are the truth, and both are legible only because
the missing combinations are absent rather than zero.

**2011's apportionment comes out at 236 rows and not 240**, which is what the
completion step is for: four combinations of unit, actor type and day type that no
line reached at all are materialised as measured zeros rather than left out. Seven
rows in the finished table carry a zero, and **every one of them is 2011's
Saturday** — Torca has no walking and no motorcycle, Tibabuyes and Porvenir no
motorcycle, and Tunjuelito, Rafael Uribe and San Cristóbal no cycling. They are
observations and not gaps, and they are what a sample of 4,035 records spread over
thirty units looks like; all seven are marked `CITY_LEVEL_ONLY`.

### The zone codes that name no place

2023's trips carry a zone on every record. 2015's and 2019's do not. **2015 has two
such codes and only one of them is a defect:**

| | Records | Trips/day |
|---|---:|---:|
| No zone at all | 50 | 23,201.5 |
| Zone code `0`, a zone nobody resolved — every one of them in Soacha | 10 | 1,027.4 |
| Zone code `1000`, a place outside the eighteen municipalities surveyed | 973 | 148,756.6 |
| **Unplaceable, all causes** | **1,033** | **172,985.5** |

`1000` is not an error at all: every record carrying it names municipality 19,
*"Otro"*, and gives coordinates 0,0. It is how the survey writes a destination
elsewhere in the country, it appears in the published matrices as a pseudo-zone, and
no zoning could hold a polygon for it. `0` is the familiar sentinel, and the
consultant dropped those records from their own matrices without saying so — which
is how we found them. Together they are 1.0 % of what 2015 measures in the four
modes.

And 2019, where there are two distinct cases:

| | Records | Trips/day |
|---|---:|---:|
| No zone at all | 3,994 | 641,071.0 |
| Zone code `0`, this delivery's "not answered" | 367 | 54,567.7 |
| Zone code `1917`, above the zoning's own range of 1–1908 | 1 | 180.6 |
| **Unplaceable, all causes** | **4,362** | **695,819.3** |

Both codes appear on records that carry no municipality and no UTAM either, so
neither is a zone the shapefile is missing. Both are declared in
`zone_codes_meaning_no_zone` and counted in the balance beside the records with no
zone at all, because that is where they belong: they cannot be put on the map
either. Together they are 6.1 % of what 2019 measures in the four modes. A code in
neither the zoning nor the declared list still stops the run.

### The balance closes, per actor type and per day type

What was apportioned to the units plus what fell outside them equals what the
file holds. It is checked on each combination of actor type and day type rather
than in aggregate — twelve for 2023, eight each for 2011 and 2015 and four for
2019 — because an aggregate over four modes can close while two of them are wrong
in opposite directions. **The largest gap over the thirty-two is 0.000000 trips.**

**1,322,429 trips a day fall outside the thirty units in 2011, 8.3 % of the four
modes, 2,663,069 in 2015, 16.0 %, 1,806,461 in 2019, 19.5 %, and 1,697,260 in 2023,
18.4 %.** That is the neighbouring municipalities each survey also covers plus the
three rural units the study does not have. It is measured and reported, not
absorbed, which is what lets the check be an equality — and three of the four years
landing within three and a half points of each other on that share is itself
evidence that no zoning is misaligned against the units. **2011 is the low one
because its trips are the shortest**, and a short trip leaves the thirty units less
often; it uses 2015's zoning, so the difference cannot be the geometry.

### The intra-zonal trips, and why they are not dropped

**3,356,494 trips a day are intra-zonal in 2015, 20.1 % of the four measured modes,
1,987,946 in 2019, 21.5 %, and 1,841,452 in 2023, 20.0 %.** Three surveys run by
three administrations over three zonings agree within a point and a half on how
much travel never leaves one zone, which is the best evidence there is that the
share is a property of the city and not of a delivery. They begin and end in the same zone, so
they have no desire line at all, and they are spread over the units covering that
zone in proportion to area rather than discarded.

**2011 is the exception at 5,200,361 trips a day, 32.7 %, and it is the same fact
seen a fourth time.** It is not the zoning, which it shares with 2015, and it is not
only the mode mix: its intra-zonal share is higher than 2015's in every mode, 38.0 %
against 28.4 % on foot and 11.9 % against 5.3 % by car in the raw files. It is that
2011 reports shorter trips in every mode — a median of 10 minutes against 17 on
foot, 15 against 25 by bicycle, 30 against 40 by motorcycle, 30 against 45 by car —
and a shorter trip stays inside its zone. Split at fifteen minutes, the two years'
walking figures nearly meet: 49.1 % against 45.4 % below and 25.1 % against 19.0 %
above.

On a typical weekday, inside the thirty units:

| Actor type | 2011 trips/day | Of which intra-zonal | Line km | 2015 trips/day | Of which intra-zonal | Line km | 2019 trips/day | Of which intra-zonal | Line km | 2023 trips/day | Of which intra-zonal | Line km |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `PEDESTRIAN` | 5,477,038 | 2,204,160 | 9,388 | 4,459,658 | 920,824 | 22,885 | 4,160,690 | 1,270,486 | 13,040 | 4,274,636 | 1,366,277 | 8,025 |
| `CAR` | 1,371,125 | 152,243 | 47,039 | 1,631,914 | 27,831 | 53,998 | 1,827,723 | 39,298 | 81,864 | 1,611,352 | 40,190 | 39,028 |
| `BICYCLE` | 324,701 | 70,216 | 4,465 | 633,406 | 37,382 | 10,949 | 787,563 | 52,491 | 18,391 | 773,132 | 37,787 | 12,434 |
| `MOTORCYCLE` | 269,182 | 29,821 | 10,513 | 714,894 | 13,157 | 31,191 | 680,233 | 12,830 | 35,104 | 818,851 | 10,421 | 27,510 |

And 2015's Saturday, which no other measured year has: 3,041,250 walking trips a
day of which 539,096 intra-zonal, 2,453,344 car, 549,075 motorcycle and 523,507
bicycle. It carries 6,567,176 trips in the four modes against the weekday's
7,439,872, 88.3 % of it — and the two columns hold the same number for 2015,
because its factor already expands to one whole day of each kind.

The trip counts are on `TRIPS_PER_DAY_OF_TYPE` because the table puts two years
side by side. The kilometres are not a trip count and do not scale with the
expansion factor, so they are as measured.

**Between a fifth and a third of the pedestrian exposure arrives through the
intra-zonal route in every year** — 20.6 % in 2015, 30.5 % in 2019 and 32.0 % in
2023. Dropping those trips
would not have been a small loss of precision: it would have removed that third
systematically, and removed more of it from units built of large zones than from
units built of small ones.

The pedestrian kilometres are the smallest of the four in all four years despite
the mode being by far the largest in trips, which is what a mode of short local
journeys should look like. That it holds on four surveys, read through four sets of
column names and a duration derived three different ways, is the strongest evidence
available that the plausibility test measures what it was built to measure. **2011
is the sharpest case of it**: 9,388 pedestrian kilometres against 47,039 by car,
where its walking is 74 % of the trips and its car travel 18 %.

**2015's pedestrian kilometres are the highest of the four at 22,885, and the
reason is the filter and not the walking.** It is not that 2015 builds more lines:
it builds 8,836 pedestrian lines on a typical weekday against 2019's 8,952 and
2023's 5,914. It is that far fewer of them are removed — 3.3 % of its walking
against 19.7 % and 14.6 % — and what the test removes is the long tail. So 2015
keeps long-ish walking lines the other years discard, and its kilometres inside
the units come to 2.72 per line reaching a unit against 1.64 in 2019 and 2023.
**2011 is the same argument from the other end**: it removes 9.0 % of its walking,
its walking is by far the shortest of the four years at a median of 10 minutes, and
it comes out with 9,388 pedestrian kilometres — fewer than 2019's 13,040 on a
larger number of walking trips.

The two statements about distance are not in tension and it is worth being explicit,
because they look it. *Before* the filter 2015's walking pairs are much closer
together — 1.45 km at the ninetieth percentile against 7.07 km in 2019 — which is
why so few of them fail. *After* it, 2019 has had its tail cut off and 2015 has not,
because 2015 barely had one. Fewer removals, not longer walks.

### The checks

| Check | Result |
|---|---|
| The table carries exactly the declared columns, in the declared order | OK, 19 of 19 |
| Every row names a unit of the study | OK, 30 of 30 |
| No combination of unit, year, actor type and day type appears twice | OK, 0 duplicated |
| 2015: the grid of unit, actor type and day type is complete | OK, 240 rows of 240 |
| 2019: the grid of unit, actor type and day type is complete | OK, 120 rows of 120 |
| 2023: the grid of unit, actor type and day type is complete | OK, 360 rows of 360 |
| 2015: apportioned plus outside equals the file, per actor type and day | OK, 8 combinations, largest gap 0.000000 |
| 2019: apportioned plus outside equals the file, per actor type and day | OK, 4 combinations, largest gap 0.000000 |
| 2023: apportioned plus outside equals the file, per actor type and day | OK, 12 combinations, largest gap 0.000000 |
| 2015: the four measured modes add to the file's own total for them | OK, 16,670,116.39 |
| 2019: the four measured modes add to the file's own total for them | OK, 9,262,670.29 |
| 2023: the four measured modes add to the file's own total for them | OK, 9,221,240.50 |
| 2015: every trip the file weights is measured or named as set aside | OK, 32,982,284.3 |
| 2019: every trip the file weights is measured or named as set aside | OK, 18,996,285.6 |
| 2023: every trip the file weights is measured or named as set aside | OK, 16,390,907.8 |
| 2015: nothing is apportioned more than once over | OK, largest share 1.000000015 |
| 2019: nothing is apportioned more than once over | OK, largest share 1.000000059 |
| 2023: nothing is apportioned more than once over | OK, largest share 1.000000128 |
| 2011: the grid of unit, actor type and day type is complete | OK, 240 of 240 |
| 2011: apportioned plus outside equals the file, per actor type and day | OK, 8 combinations, largest gap 0.000000 |
| 2011: the four measured modes add to the file's own total for them | OK, 15,898,463.68 |
| 2011: every trip the file weights is measured or named as set aside | OK, 31,633,388.8 |
| 2011: nothing is apportioned more than once over | OK, largest share 1.000000007 |
| The intra-zonal trips are a part of the variable, never more | OK, 0 rows in any year |
| No negative trip count | OK |
| Trips per day of type is trips per average day over the universe share | OK to 1e-12 over 960 rows |
| The universe shares of a year are what its expansion implies | OK, 1.000000000000 in all four |
| The per-km² column is the variable over the area of its own unit | OK to 1e-12 |
| The per-inhabitant column is the variable over the population of the same year | OK to 1e-12, 0 rows without a population |
| A combination no trip reaches carries a zero and the status MEASURED | OK, 7 rows at zero, all of them 2011's Saturday |
| Every exported file is on disk and none is empty | OK, 2 of 2 |

**One check had to be rewritten and it had been wrong since it was written.** It
read *the universe shares of a year add to one*, which is true of a year whose
factor spreads the universe across all its reference days — each day type gets a
fraction and the fractions partition it — and false of a year whose factor already
expands to one day of the record's own kind, where every share is one on its own.
2019 passed it only because a single day type makes 1.0 sum to 1.0 by accident.
**2015 is the first year with more than one day type *and* a factor that expands to
one day of each**, so its two shares are 1.0 and 1.0, they sum to two, and the check
failed a year that was right. It now asks what the year's own `weight_expands_to`
implies. This is the second defect of exactly this shape — a check written inside
one year's assumptions, broken by the next — and both are recorded in section 7 of
`docs/adding-a-survey-year.md`.

The tolerance on "apportioned more than once" is deliberately not machine
epsilon. A line is split into as many as ten fragments whose lengths are summed
and divided by the whole, and that arithmetic lands a few parts per billion over
one without anything being wrong; what the check is looking for is two unit
polygons overlapping, which shows up as percentage points.

### One year against the other

`compare_years` puts each survey beside the one before it, and with four years
implemented it is a check rather than a baseline. **One typical weekday**, inside
the thirty units, on `TRIPS_PER_DAY_OF_TYPE`. Each Spearman compares that year with
the one to its left:

| Actor type | 2011 trips/day | Share | Per inhab. | 2015 trips/day | Share | Per inhab. | Spearman 11→15 | 2019 trips/day | Share | Per inhab. | Spearman 15→19 | 2023 trips/day | Share | Per inhab. | Spearman 19→23 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `PEDESTRIAN` | 5,477,038 | 73.6 % | 0.768 | 4,459,658 | 59.9 % | 0.615 | 0.782 | 4,160,690 | 55.8 % | 0.554 | **0.554** | 4,274,636 | 57.2 % | 0.544 | **0.662** |
| `CAR` | 1,371,125 | 18.4 % | 0.192 | 1,631,914 | 21.9 % | 0.225 | 0.972 | 1,827,723 | 24.5 % | 0.243 | 0.975 | 1,611,352 | 21.5 % | 0.205 | 0.947 |
| `BICYCLE` | 324,701 | 4.4 % | 0.046 | 633,406 | 8.5 % | 0.087 | **0.474** | 787,563 | 10.6 % | 0.105 | 0.726 | 773,132 | 10.3 % | 0.098 | 0.886 |
| `MOTORCYCLE` | 269,182 | 3.6 % | 0.038 | 714,894 | 9.6 % | 0.099 | 0.741 | 680,233 | 9.1 % | 0.091 | 0.902 | 818,851 | 11.0 % | 0.104 | 0.893 |

**What 2015, 2019 and 2023 say about the city is coherent.** Cycling rises 21 % per
inhabitant between 2015 and 2019 and falls back 7 % by 2023; the motorcycle falls
slightly and then rises 15 %; walking drifts down across all three. The largest
per-inhabitant move among those three is bicycle 2015→2019 at +21 %, well inside
the 35 % threshold, and no mode share moves ten points in either step.

**2011 against 2015 fires four warnings and all four survived investigation.** The
pedestrian share moves −13.7 points, cycling per inhabitant +92 %, motorcycle
+161 %, and cycling orders the units at Spearman 0.474. Three of the four are
confirmed by the 2015 delivery's own reading of the 2011 file: Tabla 43 of its Tomo
IV gives the same three city-level changes at −13.9 points, +38.50 % and +102.82 %,
and calls the motorcycle the largest change in the survey. The difference between
those and the figures above is the funnel — **2011 delivers a smaller share of its
own city totals to the thirty units than any other year**, and by a mode-dependent
amount:

| Share of the survey's own weekday total inside the units | 2011 | 2015 | 2019 | 2023 |
|---|---:|---:|---:|---:|
| `PEDESTRIAN` | 67.3 % | 80.0 % | 59.9 % | 70.1 % |
| `BICYCLE` | 53.1 % | 74.8 % | 65.2 % | 69.3 % |
| `MOTORCYCLE` | 65.5 % | 85.8 % | 74.3 % | 79.1 % |
| `CAR` | 75.4 % | 89.1 % | 79.7 % | 83.4 % |

Two facts about 2011 explain the whole column: the sixth of its records the
consultant imputed carries no geography, and it reports shorter trips than any other
year in every mode, which makes the plausibility test reject more of them. **This is
a property of the table a reader has to know**, because a mode's level inside the
units is depressed relative to its own city total by a year-specific and
mode-specific amount, which is why the cross-year check warns where the published
city-level comparison does not.

**The bicycle ranking is a finding about the city and not about the reading, and
three tests say so.** The two years share a zoning — 2011 borrows 2015's — so the
zoning cannot be the cause. The allocation rules agree with each other inside 2011,
at 0.944 against the origin and 0.931 against the destination. And the raw files say
the same thing with no pipeline at all: summing each survey's own expansion factor
over its cycling trips by origin zone, one zoning for both, no lines, no
apportionment and no duration filter, gives Spearman **0.485** against the
pipeline's 0.474. The pattern is legible — cycling falls in the south-western
periphery (Patio Bonito −50 %, Suba −48 %, Tibabuyes −33 %) and rises in the centre
and north (Chapinero +824 %, Teusaquillo +518 %, Barrios Unidos +328 %, Niza
+320 %) — and **2019 and 2023 hold the higher levels**, so 2011 is the odd year of
four rather than 2015 the odd year of two. Two things are true at once and the study
cannot separate them: cycling did reorganise across the city in those four years,
and 2011's cycling rests on 3,526 zoned records spread over thirty units.

**The pedestrian series is not interpolable on the full definition and is on the
fifteen-minute one, which is what D39 decides.** Measured on the same reading the
run makes, outside the pipeline on 2026-09-09, one weekday and the whole surveyed
region:

| | Every walking trip | Index | Fifteen minutes or more | Index |
|---|---:|---:|---:|---:|
| 2011 | 8,136,778 | 100 | 3,733,664 | 100 |
| 2015 | 5,576,943 | 69 | 3,600,522 | 96 |
| 2019 | 6,941,798 | 85 | 3,956,917 | 106 |
| 2023 | 6,203,098 | 76 | 4,104,040 | 110 |

The full column swings 46 % and changes direction twice; the fifteen-minute column
rises monotonically after 2015 and its whole range is 14 %. **The second column is
not yet in the exposure table** — D39 adds it and D40 is what will read it.

**And it has to be apportioned again rather than rescaled**, which was measured
before it was asserted. Counted at the origin zone under both definitions, each
unit's share of city walking correlates at Spearman 0.972, 0.976, 0.972 and 0.982
across the four years — the ranking barely moves — while the ratio between the two
shares runs **0.68 to 1.45 across the thirty units**. A rescaled column would
reproduce all four city totals exactly and be wrong by up to a half on an
individual unit. The measurement understates the difference, because it counts at
the origin and therefore cannot see the part where the two definitions diverge
most: short walks are about twice as intra-zonal as long ones, 49.1 % against
25.1 % in 2011 and 45.4 % against 19.0 % in 2015, and an intra-zonal trip is spread
over a zone's units by area while an inter-zonal one is spread along a line.

**How far a unit's rate moves between two adjacent surveys, which is the price of
interpolating per unit.** Over the weekday and the four modes, the number of
unit × mode × step combinations moving by more than a factor of two:

| Step | `PEDESTRIAN` | `BICYCLE` | `MOTORCYCLE` | `CAR` |
|---|---:|---:|---:|---:|
| 2011 → 2015 | 4 | 16 | 22 | 3 |
| 2015 → 2019 | 3 | 6 | 1 | 2 |
| 2019 → 2023 | 4 | 1 | 1 | 1 |

**64 of 360, and 41 of the 64 are on the 2011 → 2015 step** — the same segment that
carries the instrument change in walking, the imputation without geography and the
smallest share of city totals reaching the units. The widest single step is
Chapinero's cycling rate at 8.85×, followed by Teusaquillo at 6.12× and Usaquén at
5.48×, all three cycling and all three on that segment. Part of it is real:
Chapinero's higher level is held by 2019 and 2023. D40 requires the interpolation to
print this table on every run and leaves open whether the trajectories need
shrinking toward the city's.

**2011's walking is 46 % above 2015's and the gap is entirely below fifteen
minutes.** It is not a reading — Tabla 43 of the 2015 delivery gives 8,136,778 for
2011, to the trip. Split at fifteen minutes the two years agree within 4 % above it,
3,733,664 against 3,600,521, and differ by a factor of 2.2 below it, 4,403,115
against 1,976,421. The instruments differ exactly there: 2011's questionnaire asks
for a short walk outright and tells the interviewer not to ask about stages for one,
where 2015's states no floor and records walking as a stage with its own minute
counter. The 2015 delivery's own arithmetic agrees — pedestrian **stages** fall 17 %
where pedestrian **trips** fall 31 %.

**The column matters and this table is on the corrected one.** The comparison used
to read `TRIPS_PER_AVERAGE_DAY`, which is what the file holds and what the balance
closes on — but what it holds depends on what the year's factor expands to. 2023's
weekday rows carry 77.2 % of a weekday and 2019's carry all of one, so on that
column every 2023 mode came out about 23 % below 2019: pedestrian −24 %, bicycle
−28 %, car −35 %, motorcycle −12 %. Car sat one decimal from tripping the 35 %
threshold on an artefact of the comparison's own arithmetic, and four independently
measured modes falling in unison was the tell. The defect could not exist while one
year was implemented and appeared the moment a second declared a different
`weight_expands_to`. Mode shares and the Spearman are ratios and ranks, so neither
was affected. See D38.

**Nothing crosses the mode-share or trip-rate thresholds.** No share moves ten
points; the largest per-inhabitant move between 2019 and 2023 is car at −15.7 %,
well inside the 35 % threshold. Those two years also set aside almost the same
fractions for the same three reasons — 13.1 % against 9.4 % impossible, 21.5 %
against 20.0 % intra-zonal, 19.5 % against 18.4 % outside the units.

**2015 departs on one of those three and it was chased to the bottom rather than
noted.** It sets aside only **1.9 %** as impossible against 13.1 % and 9.4 %, and
the gap is in walking: 3.3 % against 19.7 % and 14.6 % on the same denominator. It
is not the durations — the three years' walking durations are distributed much
alike and 2015 rejects an order of magnitude less in *every* band, 1.8 % of its
fifteen-to-thirty-minute walks against 16.5 % and 13.4 %. It is not the coarseness
of the zoning — the median zone is 0.410 km² in 2015, 0.412 in 2019 and 0.421 in
2023. It is that 2015's zone pairs are genuinely closer together: at the ninetieth
percentile the two zones of a walking record are 1.45 km apart against 7.07 km in
2019 and 3.63 km in 2023, and the test only ever removes the far tail.

**And 2015 is the one year that can be checked against itself on this**, because it
reports the latitude and longitude of both endpoints and the pipeline never uses
them. Those coordinates say **2.8 %** of its walking records imply a straight-line
speed above 6 km/h; the zone test rejects **1.8 %**. Two independent readings agree,
and the zone test comes out the more forgiving of the two — which is exactly right
for a test comparing the nearest points of two polygons against one comparing the
reported endpoints. The low figure is a better-geocoded delivery, and it is also the
closest thing this study has to a direct validation of the plausibility test itself.

Its other two proportions are ordinary: 20.1 % intra-zonal, within a point and a
half of both other years, and 16.0 % outside the thirty units against 19.5 % and
18.4 %.

**2015 trips the rank check on the same mode 2019 and 2023 trip it on, and it is
the same finding.** Pedestrian exposure orders the thirty units at Spearman
**0.554** between 2015 and 2019, against 0.726 for bicycle, 0.902 for motorcycle and
0.975 for car. Four tests, and none of them makes it the pipeline's:

| Test | Result |
|---|---|
| The reading against the survey's own published matrices | exact to the last decimal on both day types and mode by mode |
| Area each zoning assigns to each of the thirty units | differs by **0.60 %** at worst, under 0.1 % for most |
| The three allocation rules against each other, within 2015 | variable vs at-origin 0.986, vs at-destination 0.985 |
| The raw files, one zoning for both years, no pipeline at all | Spearman **0.708**, and the same units moving the same way |

The last is the decisive one, as it was for 2019. Summing each survey's own
expansion factor over its walking trips by origin zone, with one zoning used for
both years and no lines, no apportionment and no duration filter, gives Porvenir
+187 %, Tibabuyes +131 %, Torca +108 %, Patio Bonito +66 %, Suba +56 %, Fontibón
−47 % and Barrios Unidos −41 % — the same units and the same directions the
pipeline reports.

The units that move are the ones that were being built between the two surveys:
Porvenir and Patio Bonito are the Bosa and Kennedy expansions, Tibabuyes is Suba's,
and Torca's whole figure is 5,938 trips a day so its rank is noise. **Tibabuyes is
also the unit that falls 71 % between 2019 and 2023**, so the north-west is
unstable in both directions across three surveys — which is what the 2019 pass
concluded about it, now on a third year.

**One thing does trip the check: pedestrian exposure orders the thirty units at
Spearman 0.662, below the 0.70 floor.** It warns and does not fail, which is
correct, and it was investigated rather than accepted. Five tests, and none of
them makes it the pipeline's:

| Test | Result |
|---|---|
| The reading against the survey's published per-UTAM table (IND_64) | 132 of 134 within 0.01 %, 130 to the last decimal |
| Zones each zoning puts in the units that move | 8 vs 8 in Tibabuyes, 14 vs 14 in Rincón, 28 vs 28 in Niza |
| Area each zoning assigns to each unit | differs by 0.82 % at worst over the thirty, under 0.1 % in Suba |
| The three allocation rules against each other | Tibabuyes −71 %, −70 %, −70 %; Niza +146 %, +155 %, +145 % |
| The sliver threshold swept over two orders of magnitude | largest per-unit move 0.16 %, Niza 0.2 % |
| The raw trip files, no pipeline at all | Tibabuyes' share of city walking −56 %, Rincón −44 %, Suba −41 %, Niza +90 % |

The last one settles it. Summing each survey's own expansion factor over its
walking trips by origin zone, with one zoning used for both years — they number
the same polygons the same way, median 1 m between the two centroids of a code —
and with no desire lines, no apportionment, no day-type rescaling and no duration
filter, the same units move in the same direction by a similar amount. **The
disagreement is already in the two files.**

The pipeline's figures are larger than the raw ones (−71 % against −56 % in
Tibabuyes, +146 % against +90 % in Niza) because the plausibility filter and the
line apportionment act on top of it, but the sign and the geography are the
survey's.

So it is what the two samples say about walking in Suba, and **the study cannot
tell a real change from sampling variation there.** It is recorded here because a
reader comparing a pedestrian rate for Tibabuyes across the two years will see
them differ by a factor of three and deserves to know it was pursued.

Per unit, on the comparable column, the units that move most:

| Unit | 2019 trips/day | 2023 trips/day | Change | Rank 2019 → 2023 |
|---|---:|---:|---:|---|
| UPL27 Niza | 64,963 | 160,044 | **+146 %** | 29 → 10 |
| UPL33 Barrios Unidos | 74,053 | 117,401 | +59 % | 27 → 19 |
| UPL17 Bosa | 214,831 | 312,912 | +46 % | 3 → 1 |
| UPL08 Britalia | 83,653 | 113,699 | +36 % | 26 → 20 |
| UPL13 Tintal | 128,440 | 173,320 | +35 % | 18 → 8 |
| … | | | | |
| UPL12 Fontibón | 85,782 | 57,164 | −33 % | 25 → 27 |
| UPL28 Rincón de Suba | 179,952 | 106,866 | −41 % | 7 → 21 |
| UPL09 Suba | 96,928 | 46,361 | −52 % | 23 → 29 |
| UPL10 Tibabuyes | 179,095 | 51,140 | **−71 %** | 8 → 28 |
| UPL07 Torca | 9,771 | 1,750 | −82 % | 30 → 30 |

The city total moves **+2.7 %**, from 4,160,690 to 4,274,636. What the two surveys
disagree about is where the walking is, not how much of it there is.

### The delivered layer, validated and then retired

The layer of section 13 is an incomplete 2019 — 181 lines, bicycle only — so it is
a subset of the same records this survey holds. Before it was retired, the two
readings were compared on the records they share:

| | |
|---|---:|
| Distinct origin-destination pairs in the layer | 160 |
| Of those, present among the pairs built from the 2019 survey | **160** |
| Pairs where the layer attributes more trips than the survey holds | **0** |
| The layer's share of the survey's inter-zonal bicycle travel | 11.2 % |

**Two independent readings of one source agreeing on 160 pairs** — one received as
finished geometry, one built from the trip records — is the strongest confirmation
the survey reader could get, and it is the reason the layer was kept until 2019
landed instead of being deleted when it was superseded.

The comparison says one more thing. **The plausibility test removes 15 of those
160 pairs outright**, 8,905.8 of the layer's 113,269.3 trips a day and 7.9 % of
it, and part of a sixteenth. The delivered layer therefore carried records this
study judges impossible for the mode that reported them, and the fifteen come in
symmetric pairs — a there-and-back between the same two zones — which is what one
household's outbound and return trip looks like.

### What it says about the city

The bicycle ranking on a typical 2023 weekday runs Kennedy (56,149), Patio Bonito
(42,618) and Bosa (37,915) at the top and Usme-Entrenubes (1,455), San Cristóbal
(3,181) and Lucero (3,837) at the bottom — the flat south-west against the
southern hillsides. In 2019 it runs Tabora (53,932), Bosa (52,341) and Edén
(48,463) at the top, with the southern hillsides at the bottom in the same order.
In 2015 it runs Rincón de Suba (49,537), Puente Aranda (40,545) and Bosa (38,688),
with the same hillsides at the bottom. That is not a check, and it is the kind of
external agreement that would have been worth worrying about had it been absent.

**2015's Saturday is the first one the study can look at that is not 2023's.** Its
car travel rises by half against its own weekday — 2,453,344 trips a day against
1,631,914 — while walking falls 32 % and cycling 17 %. Tomo IV says the same thing
in words about the whole region: car trips up "aproximadamente el 45 %" on a
Saturday and walking down 29 %. That the two agree matters more than it looks,
because 2023's Saturday rescaled to the universe says a Saturday carries as much
travel as a weekday, which nobody believes. 2015's does not have to be rescaled —
its factor already expands to one whole day of each kind — and it shows the
weekend pattern anyone would expect. Whether that makes 2023's Saturday usable is
one of the two questions D38 leaves open.

### The figures

Two per combination of year, actor type and day type — a choropleth and the
desire lines behind it. **Sixty-four figures**: twenty-four for 2023, sixteen each
for 2011 and 2015 and eight for 2019, which follows from their three, two, two and
one day types. None from the delivered layer: its folder went with it.

```
figures/exposure/
├── 2011/
│   ├── bicycle/
│   │   ├── choropleth/     2 files, the typical weekday and the Saturday
│   │   └── desire_lines/   2 files, the typical weekday and the Saturday
│   ├── car/  motorcycle/  pedestrian/
├── 2015/
│   ├── bicycle/
│   │   ├── choropleth/     2 files, the typical weekday and the Saturday
│   │   └── desire_lines/   2 files, the typical weekday and the Saturday
│   ├── car/  motorcycle/  pedestrian/
├── 2019/
│   ├── bicycle/
│   │   ├── choropleth/     1 file, the typical weekday
│   │   └── desire_lines/   1 file, the typical weekday
│   ├── car/  motorcycle/  pedestrian/
└── 2023/
    ├── bicycle/
    │   ├── choropleth/     3 files, one per day type
    │   └── desire_lines/   3 files, one per day type
    ├── car/  motorcycle/  pedestrian/
```

**A year folder holds as many files as the year has day types**, which is the tree
saying something true about the surveys rather than about the code.

**One file per figure, and it carries the scale bar.** Both variants used to be
written every run; the bar-less copy is now behind
`MAP_EMIT_NO_SCALEBAR_VARIANT`, off by default, and the standard figure takes the
plain name because a suffix on the only file distinguishes it from nothing. Every
map in the pipeline goes through one helper for that rule, the reference map
included.

**A map is 9 inches tall**, about 13 by 23 cm, where it used to be 5 and came out
postcard-sized. These are vector figures, so what the size buys is the ratio
between the map and the type: the unit numbers shrink relative to the territory
and the colour bar gains room for seven ticks where it had four.

Every figure sits under one of the two kind folders, so a recursive match on
`*/choropleth/*.pdf` returns all sixteen choropleths and `*/desire_lines/*.pdf`
all sixteen line maps. The file names repeat the year and mode the tree already
gives, because a figure is copied out of this tree into the document's own folder
before LaTeX can see it and would otherwise arrive stripped of its identity.

**The choropleth shows `TRIPS_PER_DAY_OF_TYPE`.** A map titled "viajes por día"
has to carry the trips of a day, and in 2023 the variable counts a day type's
share of an average day, which on a Saturday map is six times too small for no
reason except the size of the subsample. The consequence is visible and is meant
to be: the Sunday map is the most intense of the three in all four modes, so the
figure says plainly that the day-type dimension of 2023 does not hold up rather
than hiding it in a column nobody plots. For 2019 the two columns coincide, so the
choice does not arise and the map carries the survey's own figure unchanged.

**The colour ramp is shared across the day types of one mode and never across
modes.** In 2023 the ceiling of each ramp is the mode's maximum over its three
days, which is set by the Sunday in every mode; in 2019 there is one day, so each
map fills its own ramp. In the worst 2023 case — bicycle on a typical weekday —
the map uses 53 % of its ramp; sharing across modes instead would draw bicycle and
motorcycle at a fifth of a ramp scaled by walking.

The 2019 maps run 9,771 to 249,436 trips a day for walking, 939 to 53,932 for
cycling, 6,089 to 54,441 for motorcycles and 3,699 to 192,694 for cars. Neither
year has an observed zero on any survey map: every unit is reached by every mode.
The one observed zero in this whole stage was Torca on the delivered layer, which
is section 13's and is exactly the kind of thing 181 lines produce and 27,437 do
not.

| Actor type | Ramp ceiling, trips per day | Weekday map's own maximum |
|---|---:|---:|
| `PEDESTRIAN` | 346,846 | 312,912 |
| `BICYCLE` | 143,737 | 72,710 |
| `MOTORCYCLE` | 89,569 | 70,957 |

**The desire-line map exists because this pipeline draws its own input.** The
units are outlined without their numbers, which no other map here does: a label
under three thousand crossing lines is unreadable. The frame is the city and not
the lines — they run to Zipaquirá and Facatativá, 154 km apart against Bogotá's
23 — so lines leaving the study area simply leave the frame. Width and opacity
grow as the square root of the trips a line carries, and the heaviest are drawn
last.

Lines drawn per mode and day in 2023, which is also the clearest statement of how
thin its weekend is:

| Actor type | Typical weekday | Saturday | Sunday |
|---|---:|---:|---:|
| `PEDESTRIAN` | 5,914 | 1,445 | 1,062 |
| `MOTORCYCLE` | 3,814 | 836 | 577 |
| `BICYCLE` | 3,151 | 613 | 438 |

And in 2019, where the one day type carries the whole sample:

| Actor type | Lines built | Reaching the units | Drawn, to 95 % of the trips |
|---|---:|---:|---:|
| `CAR` | 12,854 | 12,123 | 9,227 |
| `PEDESTRIAN` | 8,952 | 7,964 | 5,286 |
| `BICYCLE` | 4,668 | 3,909 | 2,894 |
| `MOTORCYCLE` | 4,660 | 4,198 | 3,160 |

Only the inter-zonal trips have a line; the intra-zonal ones are on the
choropleth and cannot be here, and the caption says so.

### The delivered layer, measured against it

The delivered layer's bicycle variable and the survey's 2023 bicycle weekday
variable correlate at **Spearman 0.362** across the thirty units. Kennedy, the
survey's most cycled unit, is sixteenth in the delivered layer; Edén, the layer's
first, is sixth in the survey. The two do not order the same thirty places the
same way, which is the practical reason the layer could not stay as the variable.

That comparison was made against the wrong year, and knowingly: the layer is a
sample of **2019**, and 2019 is now measured. Against the year it actually comes
from, the check that matters is not a correlation but an identity, and it is above
— all 160 of its origin-destination pairs are present among the survey's, with
none over-attributed.

The comparison mixes two things — the layer is 2019 and the survey 2023 — and
four years of change in Bogotá's cycling cannot produce a rank correlation of
0.362. The layer being a 9.6 % sample with an unreconstructable selection rule
can.

### The alternative allocations

Exported beside the variable and never model variables, so that the sensitivity
of a result to the allocation rule can be shown rather than asserted. Spearman
against the variable, typical weekday 2023:

| Actor type | At origin | At destination | Line km inside |
|---|---:|---:|---:|
| `PEDESTRIAN` | 0.995 | 0.993 | 0.429 |
| `CAR` | 0.949 | 0.959 | 0.894 |
| `MOTORCYCLE` | 0.786 | 0.794 | 0.825 |
| `BICYCLE` | 0.857 | 0.884 | 0.691 |

The endpoint rules agree with each other far more closely than either agrees with
the variable, and how closely they agree with it varies by mode — pedestrians
travel short distances and are apportioned near their endpoints anyway,
motorcycles do not. The rules are different variables and not two scales of one,
which is why the choice had to be made on an argument.

**The lines are straight, and that limitation carries over from D35 unchanged.**
The kilometres inside a unit are a share of a chord nobody rode. Any document
quoting this variable says so.

### What is open

**Which day type the models take**, and **whether a day-type comparison is
supportable at all.** Rescaled to the universe, the 2023 region makes 1.778 trips
per person on a weekday, 1.802 on a Saturday and 1.749 on a Sunday. Bogotá does not
travel as much on a Sunday as on a Tuesday. The run warns about it on every
execution.

**2015 answers the second half of that and reopens the first.** Its Saturday needs
no rescaling — the factor already expands to one whole day of each kind — and it
shows the pattern anyone would expect: car up 50 % against its own weekday, walking
down 32 %, cycling down 17 %, and Tomo IV says the same of the whole region in
words. So the flat 2023 week is a property of that delivery rather than of the
city's travel, which is what this paragraph said would have to be established
before any document compared the two days. But 2015 also means a Saturday series
has two points rather than one, so "publish the weekday alone because it is the only
day the series shares" is no longer forced. **Whether a Saturday measured well in
2015 and badly in 2023 belongs in one series is a decision for my advisor.** D38 has
both.
