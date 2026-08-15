# Verification report

What the pipeline produces, whether every check it makes passes, where each
record goes, and how the result differs from the pipeline it replaces.

Sections 1 to 6 come from a single end-to-end run of the pipeline, so every
figure quoted can be traced back to a file that run wrote. Sections 7 and 8 cover
ρ(t) and the completeness audit, each a separate route with a run of its own.

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
| Multi-party rule | 4,208 crashes removed | 15,014 crashes removed | Different, defect corrected |
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
crashes; this one removes 15,014. That is not a discrepancy but the same rule
applied correctly. The inherited code deduplicated actor *types* before counting,
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
called all 66,037 of them pedestrians. 2,090 are recorded as passengers or
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
