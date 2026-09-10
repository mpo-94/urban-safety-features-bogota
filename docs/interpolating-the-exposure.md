# Interpolating the exposure over the years no survey covers

**Both halves are built.** D39 landed on `run_20260909_214626` and D40 on
`run_20260910_031907`, and this document is no longer a specification: it is what
was built, what it is checked against, and what building it changed. **Section 8 is
the last of those** and it is the part a reader who knows the decisions should start
from. Section 16 of [`verification-report.md`](verification-report.md) is the
measured record of the run.

**Read [D39 and D40](design-decisions.md) first.** They are the decisions; this is
what was built and what it is checked against. It is the counterpart of
[`adding-a-survey-year.md`](adding-a-survey-year.md) for the stage that comes after
the four years are read.

The exposure is measured in 2011, 2015, 2019 and 2023. The casualty series runs
2007–2024 observed and 2008–2024 corrected. **Fourteen of the eighteen years have no
survey**, and the panel the models are fitted on needs all of them.

---

## 0. Where to start

Read in this order, before touching anything:

1. `CLAUDE.md`.
2. **This document**, all of it. Section 2 is the method, section 3 is what stops
   it being wrong, and section 6 is the list of ways this stage can be built so it
   passes every check and still be useless.
3. **[D39 and D40](design-decisions.md)** — the decisions, and what they rejected.
4. **[D36](design-decisions.md)** for the population panel this reads, and
   **[D38](design-decisions.md)** for the table it reads.
5. **[`mobility-surveys-inventory.md`](mobility-surveys-inventory.md)** §6b and §7.
6. **[`verification-report.md`](verification-report.md)** §15 for the figures the
   result is checked against.

**The reference run is `run_20260908_101110`**: 960 rows, 34 checks, none failed.
Everything already measured in this document comes from it, except the figures
about the fifteen-minute column, which come from **`run_20260909_214626`** — 960
rows, 40 checks, none failed: the same table with that column added and every
earlier row unchanged to the last decimal. D40 is built on the second.

**Two things get built and the first has to come first**, because the second reads
what the first writes:

- **D39's second pedestrian column, in the `exposure` route. Built** on
  `run_20260909_214626`: 960 rows, 21 columns, 40 checks, none failed. The
  measured table carries `TRIPS_PER_DAY_OF_TYPE_OVER_15MIN`, produced by running
  the apportionment again with the duration filter applied to the pedestrian
  records — **not** by rescaling the existing column, for the reason section 2
  gives with numbers. The four city totals it had to reproduce came out to the
  trip, **2011 3,733,664 | 2015 3,600,522 | 2019 3,956,917 | 2023 4,104,040**,
  the full column did not move, and **all 960 rows are identical to
  `run_20260908_101110` on every column they already had** rather than only the
  720 that were required to be. What building it revealed is in section 7, and
  section 3 of this document is where it matters: the monotone series is the
  region's, and inside the thirty units the same column turns at 2019.
- **D40's interpolation, in a route of its own. Built** on `run_20260910_021628`:
  6,480 rows, 17 checks, none failed, `src/interpolation.py` and the route
  `interpolation`, reading the two tables of `run_20260910_021307` and the
  population panel and no survey at all. Sections 1 to 4 are what it does; section 8
  is what building it settled and what it found.

---

## 1. What the stage produces

One row per unit, year, actor type and day type, over the **whole** window
2007–2024, with the measured years in it unchanged and every other year
constructed. It is a separate table from `analysis__exposure_by_unit`, not a
replacement: that one is the record of what the surveys measure and it must stay
readable on its own, exactly as the corrected casualty set never replaces the
observed one (D31).

It came out at **6,480 rows**: 30 units × 4 actor types × 3 day types × 18 years,
of which 960 are measured and 5,520 constructed.

Columns, beyond the identity the other tables already share:

| Column | What it holds |
|---|---|
| `POPULATION` | from the annual panel, D36 |
| `TRIPS_PER_DAY_OF_TYPE` | the level, measured or constructed |
| `TRIPS_PER_DAY_OF_TYPE_OVER_15MIN` | the same on D39's pedestrian definition; identical to the first for the three modes that have only one definition |
| `TRIPS_PER_DAY_OF_TYPE_PER_INHABITANT` | the rate the interpolation actually runs on |
| `TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_PER_INHABITANT` | the same rate on the narrower definition, interpolated separately |
| `EXPOSURE_PROVENANCE` | `MEASURED`, `INTERPOLATED` or `HELD` |
| `YEARS_TO_NEAREST_SURVEY` | 0 at a survey year and nowhere else; 1–2 between two of them on the weekday, up to 4 on the Saturday's long gap, up to 16 on the Sunday |
| `SAMPLE_SUPPORT` | carried through from the survey year the value rests on, and the weaker of the two where it rests on two |

**Two rates rather than one**, because the procedure runs twice and each level has
to be recoverable from its own rate; and both are named for the column they divide,
because the measured table already carries a per-inhabitant column computed on
`TRIPS_PER_AVERAGE_DAY`. Section 8 has the rest of what the specification did not
settle.

**The identity columns keep the names and the values the matrix, ρ and the
predictor tables use.** The whole point of this table is to be joined to them.

---

## 2. The method, in the order it has to happen

1. **Read the measured table** and keep `TRIPS_PER_DAY_OF_TYPE` — never
   `TRIPS_PER_AVERAGE_DAY`, which means a different quantity in 2023 than in the
   other three years. This is the mistake section 7 of `adding-a-survey-year.md`
   records first, and it applies with more force here than anywhere: an
   interpolation is the definition of putting two years side by side.
2. **Divide by the population of the same unit and the same year** to get the rate.
   The measured years have a population in the table already.
3. **Interpolate the rate log-linearly** between adjacent survey years. For a year
   `t` between surveys `a` and `b`:
   `rate(t) = rate(a) × (rate(b) / rate(a)) ^ ((t − a) / (b − a))`.
   A rate of exactly zero at either end makes the logarithm undefined — 2011's
   Saturday has seven such cells — so those are interpolated linearly, and the run
   says how many were.
4. **Hold the rate flat outside the measured range**: 2007–2010 take 2011's rate,
   2024 takes 2023's.
5. **Recover the level** as `rate(t) × POPULATION(unit, t)`.
6. **Mark every cell** with its provenance and its distance to the nearest survey.

**Do it twice, once per pedestrian definition.** Nothing else in the procedure
changes: the three other modes have one definition and both columns hold the same
number for them.

**And the second pedestrian column is a second measurement, not a rescaling of the
first.** This is the one place the temptation is real and cheap: the city-level
ratio between the two definitions is known for each year, so it looks as though the
per-unit column could be obtained by multiplying. **It cannot.** Counted at the
origin zone, each unit's share of city walking under the two definitions correlates
at Spearman 0.97–0.98 — the ranking barely moves — but the ratio between the two
shares runs **0.68 to 1.45 across the units**, so a single scale factor would be
wrong by up to a fifth or a half on an individual unit. And that measurement
*understates* the difference, because it ignores the part where the two definitions
diverge most: **short walks are about twice as intra-zonal as long ones** — 49.1 %
against 25.1 % in 2011, 45.4 % against 19.0 % in 2015 — and an intra-zonal trip is
spread over a zone's units by area while an inter-zonal one is spread along a line.
The two definitions go through different spatial operators in different
proportions. The fifteen-minute column therefore comes from running the
apportionment again with the duration filter applied to the pedestrian records, in
the `exposure` route, and it lands in the measured table before this stage reads it.

**The day type is a dimension of this and not a complication.** A year's Saturday
interpolates against the other years' Saturdays and never against their weekdays.
2019 has no Saturday at all, so the Saturday series has three anchors — 2011, 2015
and 2023 — and its longest segment is the **eight years from 2015 to 2023**, twice
any weekday segment. One of its three anchors, 2011's, is marked `CITY_LEVEL_ONLY`
and another, 2023's, is the one D38 says behaves implausibly once rescaled. The run
has to say so and the report has to repeat it: **the Saturday series is three
anchors of three different qualities across a longer span.** 2023 also has a Sunday
and no other year does, so a Sunday series would rest on a single anchor:
**`SUNDAY` is held flat across the whole window or left out**, and that is a
decision for a person rather than a default.

---

## 3. What to check it against

**Inside the stage:**

- every measured year comes out **identical to the measured table**, to the last
  decimal, on every column it shares — the interpolation must not move an
  observation;
- the grid is complete over the window: 30 units × 4 actor types × the day types
  each year supports × 18 years, with nothing materialised for a day type no
  neighbouring survey has;
- no negative and no null level anywhere it should have one;
- `TRIPS_PER_INHABITANT × POPULATION` reproduces the level to 1e-12;
- the provenance column has exactly four `MEASURED` years per series, and
  `YEARS_TO_NEAREST_SURVEY` is zero on exactly those.

**And one the run has to report rather than pass or fail: how far each unit's rate
moves between two adjacent surveys.** The interpolation is per unit, so it inherits
whatever sampling noise the unit's own records carry, and the thirty units are not
equally well sampled. Measured over the weekday and the four modes, on the
fifteen-minute column the series is read on, **67 of the 360 unit × mode × step
combinations move by more than a factor of two**, and they are not spread evenly:

| Step | `PEDESTRIAN` | `BICYCLE` | `MOTORCYCLE` | `CAR` |
|---|---:|---:|---:|---:|
| 2011 → 2015 | 6 | 16 | 22 | 3 |
| 2015 → 2019 | 4 | 6 | 1 | 2 |
| 2019 → 2023 | 4 | 1 | 1 | 1 |

**Forty-seven of the sixty-seven are on the 2011 → 2015 step**, which is the segment
already known to carry an instrument change in walking, an imputation without
geography, and a smaller share of its city totals reaching the units than 2015
delivers on every one of the four modes.
The widest single step is Chapinero's cycling rate at **8.85×**, and log-linear
interpolation spreads that as a 72 % rise every year through 2012, 2013 and 2014.

*On the full pedestrian column the same table gives 4 / 3 / 4 for walking, 64 in
all and 45 on the first step, and the other three modes are identical — walking is
the whole difference between the two versions, and the run prints both figures for
that reason. The 41 this document carried until 2026-09-10 was an arithmetic slip:
the table beside it summed to 45 even then.*

**The run prints this table and the widest ten steps on every execution.** It does
not fail: a rate that really did multiply by nine in four years is possible, and
Chapinero's cycling is a case where 2019 and 2023 hold the higher level, so the
change is at least partly real. What is not acceptable is producing three
constructed years on top of a step like that without saying so. **Whether the
per-unit trajectories need shrinking toward the city trajectory is a question for a
person, and it should be asked with this table in hand rather than answered by
smoothing quietly.**

**Against something outside the stage** — and this is the check that matters,
because everything above can pass on an interpolation of the wrong column:

- **the 2007–2010 block against the published 2005 figures.** This is the test D40
  defers 2005 on. The 2011 report publishes the 2005-comparable partition; if the
  held rate carried back to 2007 lands far from what 2005 published, the 2005
  survey is worth implementing and there is a number saying so.
- **the city total per mode per year against any annual series that exists.**
  Motorcycle and car registrations, TransMilenio ridership. Not to anchor the
  interpolation — D40 defers that — but to see whether the interpolated curve and
  the annual curve disagree in shape. A disagreement is the argument for building
  the anchored version.
- **the interpolated years against the crash series itself.** If the exposure of a
  mode moves smoothly through a year in which its casualties jump, that is either a
  real change in risk or an exposure that is not tracking the city. Both are worth
  knowing before a model is fitted.

---

## 4. Where it goes and what it must not disturb

A route of its own, after `exposure` and before whatever fits the models. It reads
the exported exposure table and the population panel and writes one more table; it
must not re-read a survey, and it must not change `analysis__exposure_by_unit`.

**The measured table is the record and the interpolated one is a construction**, and
the two live side by side for the same reason the observed and corrected casualty
sets do (D31). A reader who wants to know what the surveys said reads the first; a
model that needs eighteen years reads the second and carries the provenance column
with it.

---

## 5. What is open now that it is built

- **Whether the per-unit trajectories need shrinking toward the city's.** The table
  in section 3 is what the question gets asked with, and the run prints it. The unit
  is the point of the whole exercise, so the answer must not be to interpolate the
  city and hand every unit the same curve — but a rate that moves 8.85× on a step
  that is partly an artefact is not a trajectory either.
- **Whether the held block enters the models.** Four of eighteen years on the
  weekday with no behavioural variation, only demographic — and section 8 says the
  measurement now argues against them.
- **Whether the constructed years 2020, 2021 and 2022 enter them either, and
  whether they are patched before they do.** This was not open before the stage was
  built and it is now: section 8 has the reason and D41 has the table that isolates
  them.
- **Whether 2005 is implemented.** The check in section 3 has been made and section
  8 has its answer; what is left is a decision about a session's work, not a
  measurement.
- **Whether the anchored version replaces this one.** D40 defers it and says why.
  It needs one external annual series per mode and none of them is on disk.
- **What the Saturday series does across its eight-year gap**, and **what a Sunday
  series that rests on one anchor is for**. The Sunday is in the table, held flat
  and marked, so the decision is now a filter rather than a re-run.
- **Which casualty set the window follows**, 2007–2024 or 2008–2024. The table is
  built over the wider one so that the choice stays a filter.

---

## 6. The ways this stage can pass every check and still be wrong

Section 3 catches arithmetic. These are the ones it cannot, because each of them
produces a table that closes, balances and reproduces every measured year.

**Interpolating `TRIPS_PER_AVERAGE_DAY`.** It means a different quantity in 2023
than in the other three years, so an interpolation over it is a curve through two
different units of measurement. Every internal check passes. This is the first
entry in section 7 of [`adding-a-survey-year.md`](adding-a-survey-year.md) and it
applies here with more force than anywhere else in the pipeline, because an
interpolation is the definition of putting two years side by side. **Read
`TRIPS_PER_DAY_OF_TYPE`, or `TRIPS_PER_DAY_OF_TYPE_OVER_15MIN` for the pedestrian
series.**

**Rescaling the full pedestrian column into the fifteen-minute one.** Section 2
has the measurement: the per-unit ratio between the two runs 0.68 to 1.45, and that
understates it because short walks are about twice as intra-zonal as long ones and
therefore go through a different spatial operator. A rescaled column would
reproduce every city total in section 0 exactly and be wrong on individual units by
up to a half. **The check that catches it is per unit and not per city.**

**Interpolating the city and handing every unit the same curve.** It would be
smooth, it would reproduce the city totals, and it would destroy the only thing the
table is for. The study is thirty units; a panel whose within-unit variation is
identical everywhere carries no spatial information between survey years.

**Smoothing the per-unit trajectories quietly.** The opposite failure, and it is
tempting because section 3's volatility table is uncomfortable: 67 of 360 steps
move by more than a factor of two. Shrinking them toward the city trajectory is a
legitimate method and it is **a decision for a person**, not something to apply
because the output looked jumpy. Report the table, ask, and do what is decided.

**Letting a constructed year look measured.** `EXPOSURE_PROVENANCE` and
`YEARS_TO_NEAREST_SURVEY` are not decoration. Fourteen of the eighteen years are
constructed, and a model fitted on all eighteen without knowing which is fourteen
observations of an assumption.

**Overwriting the measured table.** `analysis__exposure_by_unit` is the record of
what the surveys say. The interpolated table sits beside it, as the corrected
casualty set sits beside the observed one (D31).

**Extrapolating a trend backwards from the 2011 → 2015 step.** D40 already forbids
it and section 3 says why it would be worst there specifically: 47 of the 67 widest
per-unit steps are on that segment, and the segment carries an instrument change in
walking, an imputation without geography, and a smaller share of its city totals
reaching the units than 2015 delivers on every one of the four modes.


---

## 7. What building D39 changed here

The first half is built and it moved one thing in this document. Everything else
in sections 1 to 6 stands as written.

**The monotone pedestrian series is the region's, and the panel is not the
region.** D39 was decided on the whole surveyed region, where the fifteen-minute
column indexes 100 / 96 / 106 / 110 against the full column's 100 / 69 / 85 / 76.
Inside the thirty units the same column indexes **100 / 118 / 97 / 113** — a range
of 21 points instead of 14, turning at 2019 instead of rising. The full column
inside the units indexes 100 / 81 / 76 / 78, so the narrower one is still the
better of the two and the decision holds; what is no longer true is that it is
smooth.

**What accounts for it is the funnel and not the definition.** The share of the
region's fifteen-minute walking that reaches the units is 68.7 % in 2011, 83.7 %
in 2015, 63.0 % in 2019 and 70.3 % in 2023, tracking the full column's 67.3 /
80.0 / 59.9 / 68.9 almost exactly. 2015 keeps most of its walking because the
plausibility test removes 3.3 % of it and 2019 keeps least because that test
removes 18.7 % of its own — a property of two deliveries, sitting on two adjacent
anchors of the series.

**So the 2015 → 2019 segment of the pedestrian series carries a step of its own**,
in the same way section 3 already says the 2011 → 2015 segment does. Section 3's
volatility table was measured on the full pedestrian column; it has to be
recomputed on the column the series is actually read on, and the pedestrian row of
it is the one that will move.

**And the second column is one column, not two.** It is exported per day of type
only, because that is the only basis two years can be compared on and comparing
years is the whole reason the definition exists. `DAY_TYPE_UNIVERSE_SHARE` is in
the table, so the other basis is one division away for anyone who wants it.


---

## 8. What building D40 changed, and the two things it found

Section 16 of [`verification-report.md`](verification-report.md) is the measured
record. This is what a reader who knows the decisions needs from it.

### Three things the specification did not settle and the implementation had to

**Two rates and not one.** Section 1 named a single `TRIPS_PER_INHABITANT`. There
are two, because the procedure runs twice — once per pedestrian definition — and
each level has to be recoverable from its own rate rather than from the other's.
They are named for the column they divide.

**The Sunday is held flat.** Section 2 said `SUNDAY` is held across the window or
left out and that it is a decision for a person rather than a default. It is held,
for D36's reason: a table that holds it filters down to one that does not and the
reverse is impossible. Its 2,040 constructed rows all say `HELD` and sit at up to
sixteen years from their only survey, and the run warns about them by name.
**Whether it belongs in a model is still open**, and it is now a filter rather than
a re-run.

**No epsilon for the zero rates.** Twenty-one cells of each column are filled
linearly because a rate of exactly zero makes the logarithm undefined — the three
constructed years of 2011 → 2015 on top of the seven zero cells of 2011's Saturday.
Nudging a zero to keep the logarithm alive would invent a trend out of an observed
zero. The cost is that the guarantee that the fifteen-minute column stays inside
the full one, which log-linear interpolation provides, does not hold on those
cells — so it became a check rather than an argument, and it passes.

### The 2005 test was made and the held block does not survive it well

The figures are in chapter 5 of Tomo III of the 2011 delivery, the chapter written
to compare the two surveys, and it counts trips *"incluyendo los viajes a pie
mayores o iguales a quince (15) minutos"* — D39's column and nothing else, which is
why D39 had to come first. They are declared in `config.PUBLISHED_2005` with the
citation beside them, so the run makes the comparison rather than a report quoting
it.

**Read the figures, not only the prose.** The chapter's paragraphs pin three modes
and leave the car as a range across both years; **Figura 5.16 and Figura 5.17 on
page 265 draw both modal splits in full** and settle it — car 16 % in 2005 falling
to 14 % in 2011, and a bicycle of 3 % rising to 5 % that the prose never mentions.
On the prose alone the car appeared to grow 1.36× and it actually grows 1.19×.

**Do it over the region and not over the units.** Every published figure is stated
on the whole surveyed region, and the share of a mode that reaches the thirty units
differs by mode and by year — 53 % of 2011's cycling against 75 % of its car travel
— so a per-unit composition compared against a published one measures the funnel.
The `exposure` route exports `reference__survey_city_totals` for this. It transfers
to the panel because holding a rate flat holds the composition with it: inside the
units the held block's 2007 composition is within 0.10 points of the anchor's.

**The control is eight tenths of a point on four modes**: 56.0 / 10.0 / 6.0 / 28.0
published against 56.8 / 9.3 / 6.3 / 27.7 measured. **The test is 15 to 19 points on
the two modes that turn over**: the held block carries 56.8 / 9.3 / 6.3 / 27.7
against a published 2005 of 41.2 / 8.8 / 2.9 / 47.1. As growth, against the 1.06×
the held rate allows: walking 2.72×, bicycle 2.27×, motorcycle 4.08×, car 1.19×,
and all four survive the rounding of the charts — though the car survives it by
five per cent, which is inconclusive on its own. And the same chapter publishes
trips per person for both years, by stratum, rising 15 % to 56 % where the held
block asserts no change at all.

**So the held block is the weakest part of the panel and it is weak in a direction
the data can name.** Whether that is worth implementing 2005 is a decision about a
session's work. What D40 promised was a number instead of an impression, and this
is the number.

### And a second weak block the specification did not anticipate

The interpolated curve was compared against the one annual series this study
already has, its own casualty count. **The disagreement is 2020**: pedestrian
casualties halve while the interpolated pedestrian exposure rises 4 %, because 2020
sits on a straight line between 2019 and 2023 and a log-linear interpolation cannot
see a pandemic.

**2020, 2021 and 2022 are the second-weakest block in the panel**, and unlike the
held one their weakness has a date. No external series is needed to know it, which
is worth saying because the anchored version of D40 — one measured annual series
per mode — is exactly what would fix it.

**That comparison is now a table rather than an observation, and it is D41.** The
panel implies a risk for every unit, mode and year; carrying that implied risk
across the constructed years by this document's own rule and dividing the casualties
by it gives the exposure the opposite assumption would produce. The ratio between
the two is exported as `reference__exposure_against_casualties` and it is a
**diagnostic that enters no model**. What it found: outside the held block and the
pandemic the two assumptions disagree on **4 % of the constructed cells**, and
inside them on a fifth. The interpolation is not being rescued by luck in the
ordinary years, and the two weak blocks are weak for reasons that show up
independently of how they were found. Whether 2020–2022 are patched by the mirror
assumption is open, and D41's last section is where that question lives.
