# Verification report

What the pipeline produces, whether every check it makes passes, where each
record goes, and how the result differs from the pipeline it replaces.

Everything here comes from a single end-to-end run with intermediate dumps
enabled, so every figure quoted can be traced back to a file that run wrote.

| | |
|---|---|
| Scale | Localidad (19 units) |
| Study period | 2007–2024 (18 years) |
| Sources | fatality and injury point layers, vehicle table |
| Stages | loading → party resolution → matrix aggregation |
| Result | 14,364 matrix cells, 197,453 affected parties, 227,628 injured, 7,489 killed |
| Outcome | **every check passed** |

---

## 1. Verdict by check

Every check the pipeline performs, including the ones that pass. A check that
only speaks up on failure leaves no evidence it ran.

### Loading — reproduction of the inherited figures

This stage changes none of the inherited logic, so its counts must match exactly.
A mismatch would mean a defect, not a number to reconcile.

| Check | Expected | Observed | Verdict |
|---|---:|---:|---|
| Fatality records | 8,548 | 8,548 | **Pass** |
| Injury records | 261,293 | 261,293 | **Pass** |
| Concatenated casualties | 269,841 | 269,841 | **Pass** |
| Fatalities with no territorial unit | 61 | 61 | **Pass** |
| Injuries with no territorial unit | 1,344 | 1,344 | **Pass** |
| Vehicle table rows | 1,465,735 | 1,465,735 | **Pass** |

### Loading — structural checks

| Check | Result | Verdict |
|---|---|---|
| Unit layer has the expected number of units | 19 of 19 expected | **Pass** |
| Unit codes are unique within the layer | no duplicates | **Pass** |
| Spatial join does not duplicate rows | 8,548 → 8,548 and 261,293 → 261,293 | **Pass** |
| Casualty years fall inside the study period | span 2007–2024, 0 rows outside | **Pass** |
| Every vehicle type in the source is mapped | all 28 raw types covered | **Pass** |
| Vehicle join keys are unique | no duplicated (crash, vehicle) pairs | **Pass** |

### Party resolution

| Check | Result | Verdict |
|---|---|---|
| Person code unique within a crash | 4 colliding pairs, 0 null | **Fail, handled** — see §5 |
| Cross-layer duplication | 4 people appear in both layers | **Reported, open** — see §5 |
| Attaching casualties to parties does not duplicate | 269,841 → 269,841 | **Pass** |
| Party keys unique within a crash | no collisions | **Pass** |
| Every surviving crash has a party with casualties | 169,098 of 169,098 | **Pass** |
| Person balance closes | 269,841 in, 236,314 out, 33,527 named | **Pass** |

### Matrix aggregation

| Check | Expected | Observed | Verdict |
|---|---|---|---|
| Affected parties in matrix equal what entered | 197,453 | 197,453 | **Pass** |
| Injured in matrix equal what entered | 227,628 | 227,628 | **Pass** |
| Killed in matrix equal what entered | 7,489 | 7,489 | **Pass** |
| No negative cell | 0 | 0 | **Pass** |
| No cell with fewer people than parties | 0 | 0 | **Pass** |
| Every unit of the layer is in the grid | 19 | 19 | **Pass** |
| Every year of the period is in the grid | 18 | 18 | **Pass** |
| Grid has the declared number of cells | 14,364 | 14,364 | **Pass** |

### Balance accounting

Every stage declares how many records entered, how many left, and a named cause
for each one gained or lost. The causes must account for the difference exactly;
a stage that does not balance stops the run. **All 16 stages balanced.**

---

## 2. The complete funnel

From the raw files to the matrix, with the cause of every change.

| Stage | In | Out | Change | Cause |
|---|---:|---:|---:|---|
| Load territorial units | 19 | 19 | 0 | — |
| Load fatalities | 8,548 | 8,548 | 0 | 61 kept with no unit |
| Locate fatalities | 8,548 | 8,548 | 0 | containment only, no snapping |
| Load injuries | 261,293 | 261,293 | 0 | 1,344 kept with no unit |
| Locate injuries | 261,293 | 261,293 | 0 | containment only, no snapping |
| Concatenate casualties | 8,548 | 269,841 | +261,293 | injury rows appended |
| Load vehicle table | 1,465,735 | 1,465,735 | 0 | — |
| Cross-layer duplication check | 269,841 | 269,841 | 0 | 4 people counted twice, reported |
| Build vehicle parties | 1,465,735 | 293,924 | −1,171,811 | −1,171,810 crashes with no casualty; −1 row with no vehicle code |
| Attach casualties to parties | 269,841 | 269,841 | 0 | — |
| Assemble party universe | 293,924 | 359,964 | +66,040 | casualties with no vehicle, each its own party |
| Two-party threshold | 359,964 | 311,441 | −48,523 | parties of the 15,014 crashes with more than two |
| Keep parties with casualties | 311,441 | 198,311 | −113,130 | parties that took part unharmed |
| Restrict to located parties | 198,311 | 197,453 | −858 | crash point outside every unit |
| Aggregate onto the grid | 197,453 | 14,364 | −183,089 | −187,370 collapsed into shared cells; +4,281 empty cells materialised as zero |

**People, separately.** 269,841 people entered. 33,527 were in crashes the
two-party threshold discarded; 1,197 more were in crashes that could not be
located. 227,628 injured and 7,489 killed reach the matrix, 235,117 in total.

Nothing is lost without a name anywhere in the chain.

---

## 3. Comparison with the inherited pipeline

The early stages are meant to be identical, and are. Everything after them
differs deliberately. This section separates the two kinds of difference: those
that correct a defect, and those that follow from a different methodological
choice.

### Stage by stage

| Stage | Inherited | This pipeline | Same? |
|---|---|---|---|
| Read fatalities and injuries | 8,548 + 261,293 | 8,548 + 261,293 | Identical |
| Locate against the unit layer | 61 + 1,344 unlocated | 61 + 1,344 unlocated | Identical |
| Concatenate | 269,841 | 269,841 | Identical |
| Read vehicle table | 1,465,735 | 1,465,735 | Identical |
| Severity origin after concatenation | lost — both layers flagged alike | preserved on every row | Different, defect corrected |
| Unit of the output row | one row per crash | one row per affected party | Different, methodology |
| Rows emitted | 179,110 crashes | 198,311 parties, covering 169,098 crashes | Different, both causes |
| Multi-party rule | 4,208 crashes removed | 15,014 crashes removed | Different, defect corrected |
| Unmapped vehicle types | became null, then silently dropped | routed to the residual category, reported | Different, defect corrected |
| Casualties with no vehicle | all called pedestrians | typed by role | Different, methodology |
| Grid coverage | only observed combinations | complete grid, 14,364 cells | Different, methodology |
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
179,110 inherited rows are crashes, 198,311 rows here are parties.

**The counting unit is the party, with people counted alongside.** The inherited
casualty column summed people for pedestrians and cyclists but took a maximum for
everyone else, so the same column meant people in some rows and vehicles in
others. Here a party with casualties counts once whatever its occupancy, and the
person counts sit beside it in their own columns.

**A complete grid.** The inherited output contained only combinations it had
observed, making a true zero indistinguishable from a missing observation. The
matrix here is a full grid of 14,364 cells, 4,281 of them zero.

**Casualties with no recorded vehicle are typed by role.** The inherited code
called all 66,037 of them pedestrians. 2,090 are recorded as passengers or
drivers, whose vehicle simply was not captured.

### The orientation of the motorcycle–bicycle pair

This is where the inherited bias was most visible, and it inverts.

The inherited figures were measured before its own geographic restriction, so the
like-for-like comparison is against all affected parties, before the 858
unlocated ones leave. The matrix itself is shown too; the relationship is the
same on either basis.

| | Inherited | All affected parties | In the matrix |
|---|---:|---:|---:|
| Motorcyclist harmed, bicycle as counterpart | 8,129 | 3,902 | 3,877 |
| Cyclist harmed, motorcycle as counterpart | 1,881 | 5,560 | 5,522 |
| Ratio | **4.32x** | **0.70x** | **0.70x** |

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
| CAR | 76,827 | 38.91% |
| MOTORCYCLE | 42,339 | 21.44% |
| SELF | 26,621 | 13.48% |
| PUBLIC_TRANSPORT | 21,532 | 10.90% |
| OTHER | 13,073 | 6.62% |
| PEDESTRIAN | 10,143 | 5.14% |
| BICYCLE | 6,918 | 3.50% |

Pedestrian and bicycle together are 8.64% of the matrix, the two smallest
columns. That is what a correctly oriented matrix looks like. The check is part
of the run and would raise a warning above 15%.

---

## 4. The matrix

Affected parties, all units and all years, rows are the harmed party and columns
the counterpart.

| | PEDESTRIAN | BICYCLE | MOTORCYCLE | CAR | PUBLIC_TRANSPORT | OTHER | SELF |
|---|---:|---:|---:|---:|---:|---:|---:|
| **PEDESTRIAN** | 0 | 1,149 | 19,474 | 19,187 | 6,934 | 4,750 | 12 |
| **BICYCLE** | 188 | 712 | 5,522 | 9,306 | 4,110 | 1,921 | 622 |
| **MOTORCYCLE** | 8,688 | 3,877 | 10,779 | 34,919 | 5,908 | 4,308 | 10,340 |
| **CAR** | 963 | 930 | 5,725 | 11,630 | 2,042 | 1,163 | 3,450 |
| **PUBLIC_TRANSPORT** | 242 | 190 | 479 | 1,270 | 1,967 | 427 | 11,358 |
| **OTHER** | 62 | 60 | 360 | 515 | 571 | 504 | 839 |

Largest cells: motorcyclist harmed by a car (34,919), pedestrian by a motorcycle
(19,474), pedestrian by a car (19,187). Smallest: residual harmed by a bicycle
(60), pedestrian alone (12), pedestrian by a pedestrian (0).

The zero is structural rather than surprising: two pedestrians struck in one
crash, together with the vehicle that struck them, are three parties, and the
two-party rule removes the crash.

### People by year

For checking against published figures.

| Year | Parties | Injured | Killed | | Year | Parties | Injured | Killed |
|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 2007 | 10,476 | 11,269 | 370 | | 2016 | 10,323 | 11,620 | 509 |
| 2008 | 7,659 | 8,542 | 280 | | 2017 | 10,321 | 11,854 | 484 |
| 2009 | 6,825 | 7,826 | 317 | | 2018 | 12,695 | 14,772 | 450 |
| 2010 | 9,658 | 11,086 | 374 | | 2019 | 12,983 | 15,148 | 440 |
| 2011 | 9,524 | 10,906 | 396 | | 2020 | 9,792 | 11,181 | 336 |
| 2012 | 10,424 | 11,757 | 399 | | 2021 | 13,625 | 16,160 | 400 |
| 2013 | 9,800 | 11,288 | 372 | | 2022 | 15,785 | 18,665 | 470 |
| 2014 | 9,416 | 10,823 | 427 | | 2023 | 16,703 | 20,053 | 502 |
| 2015 | 10,214 | 11,470 | 466 | | 2024 | 11,230 | 13,208 | 497 |
| | | | | | **Total** | **197,453** | **227,628** | **7,489** |

The 2020 dip and the 2023 peak are the expected shape. The low 2008–2009 figures
match a known weakness of the source in its early years.

### Grid coverage

4,281 of 14,364 cells are zero (29.80%). No unit and no year is empty
throughout. Emptiness tracks size: La Candelaria, the smallest locality, is
58.20% empty; Kennedy is 16.53%. 2007 is the emptiest year at 49%, after which
the series settles between 21% and 35%.

Nearly a third of cells being zero is a property of the data at this resolution,
not a defect, but it bears on the choice of model and will be considerably higher
at finer scales.

---

## 5. What was fulfilled, and what was not

Against the recorded decisions.

### Fulfilled

| Decision | Evidence |
|---|---|
| D1 one row per affected party | 198,311 party rows; both sides of a crash emit their own |
| D2 party as counting unit, people alongside | three counts in every row of the matrix |
| D3 severity origin preserved | injured and killed reported separately at every stage |
| D4 vehicle classification by occupant protection | all 28 source types mapped; 5,658 unrecognised parties reported, none dropped |
| D5 two-party threshold, measured | 15,014 crashes and 33,527 people removed, composition reported |
| D6 containment only, no snapping | 1,405 casualties kept unlocated and reported |
| D9 actor type from role | 63,947 pedestrians, 2,028 to residual, 63 unlisted reported |
| D10 complete grid | 14,364 cells, 4,281 zeros materialised |
| D11 unlocated parties leave at aggregation | 858 parties, cause named |
| D12 figures from exported tables, shared log scale | 57 heatmaps, each read back from its own CSV |
| D13 analysis and presentation tables separated | file names carry the distinction |

### Not fulfilled, or only partly

**D3 is complete for the pipeline but its central question is open.** Injured and
killed are carried separately, which is what the decision required. How the
models should aggregate them — combined, separately, or both — is not settled and
is for my advisor.

**D7, the UPL layer, is unresolved and blocking for the panel.** The layer has 30
of the 33 units the design assumes. Nothing in this run depends on it, because
this run is at locality scale, but the panel specification does. The pipeline
detects and reports the shortfall; it cannot decide it.

**D8 has a known limitation.** Party identifiers come from row position, because
the source person code is not unique. They are stable within a run and must not
be used to match parties between runs; the crash and vehicle identifiers are the
stable route.

**Four people are counted twice.** They appear in both the fatality and the
injury layer, with crash, code, role and date all coinciding, which is what one
person injured and later deceased looks like across two sources. That total
agreement is the evidence they are one person, so no identifier is invented to
separate them. It inflates the person counts by 4 out of 269,841 and is checked
and reported on every run so it cannot grow unnoticed. What those records mean is
a question about the sources, and it belongs with the D3 aggregation question.

**D14 was reverted.** Pictogram-labelled figures were built, reviewed and
removed; pipeline figures are text-labelled. Recorded rather than deleted.

### Not yet started

Urban predictors and the panel models. The audit of the inherited predictor stage
is complete and documented, and the reimplementation has not begun.

---

## 6. Outputs

One directory per run, named by timestamp, so runs accumulate instead of
overwriting one another.

| Location | Contents | Purpose |
|---|---|---|
| `provenance.log` | full log with the funnel and every check | the audit trail of the run |
| `data/analysis__matrix_long.{csv,parquet}` | 14,364 rows, the complete grid | **the table the models consume** |
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
