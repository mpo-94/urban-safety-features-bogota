# Adding a survey year to the exposure

The study's exposure is built from the household mobility survey: the desire
lines are constructed here rather than received, one per pair of zones, and each
gives every unit it crosses the share of its trips matching the share of its
length inside that unit. **2023 is implemented. 2019, 2015 and 2011 are not.**

This is the order to do one in. It is a procedure and not a note because the same
work happens three more times, and because the trap is always the same one: each
survey was commissioned by a different city administration and names and
catalogues its data its own way, so nothing about a year's files can be inherited
from the year before — while everything downstream of them has to come out
identical.

Read first, in this order:

1. **[`mobility-surveys-inventory.md`](mobility-surveys-inventory.md) §6b** — the
   contract. What must not change, the six things that must be established from
   the year's own files, and the 2023 baseline the result is checked against.
2. The same document's per-year sections for the year you are doing, especially
   **§5**, which lists what that year leaves unresolved, and **§6**, the traps.
3. **[D38](design-decisions.md)** for why the design is what it is.

---

## 1. Inspect before declaring anything

**Never take a column's name as evidence of what it holds.** Everything below was
established against something outside the column itself, and every one of them
had already gone wrong once when it was.

Write the answers down before touching `config.py`. If any of them cannot be
answered from the delivered files, that is a question for the advisor and not a
default to pick.

**Which column is the expansion factor.** Sum each candidate and compare against
the survey's own published total. 2015 has four candidates and nothing in the
file chooses between them; its documentation
(`Tomo VII_BBDD_EODH_V2.pdf`) has to be read.

**What one unit of it expands to.** A day of what? 2023's represents the whole
population once over all seven reference days together, so summing within one
kind of day gives that day's share of an average day and not the trips of one
such day — and the share of the universe those households cover is what converts
between them. A year whose factor already expands to one day of the record's own
kind declares that instead and skips the conversion. Establish it from the
household weights: sum them, and see whether the whole sample or each day's
subsample reproduces the declared universe.

**Which day the reported trips belong to.** Every year says it differently and
none of them says it in the trip record. 2023's technical sheet gives the
reference period as the day *before* the interview, so the dates are shifted back
one day; taking the interview date would have filed every Saturday trip under a
Sunday. Find the statement in that year's own technical documentation.

**Which column is the trip duration**, and **verify it against something else
before trusting it**. 2023's `duracion_min` agrees with its own fifteen-minute
walking split, 3 to 14 minutes on one side and 15 to 439 on the other, which is
what made it usable. A year with no duration cannot have its origin-destination
pairs checked for plausibility, and the run says so rather than implying the year
is clean.

**Every value of the mode column, on every row.** Not the first row. Each label
is either mapped to one of the four actor types or declared as deliberately not
measured; one in neither stops the run. There is no `OTHER` to fall through to.

**The zoning**, and whether every zone code the trips name exists in it. 2011
ships no zoning at all, and whether the 2015 zoning serves it has to be shown and
not assumed.

---

## 2. Declare it

One `MobilitySurvey` in `src/config.py`, appended to `MOBILITY_SURVEYS`. Nothing
else changes: the reading, the geometry, the apportionment, the checks, the
dictionary and the figures all follow from it.

```python
SURVEY_2019 = MobilitySurvey(
    year=2019,
    label="Mobility survey 2019",
    label_es="Encuesta de movilidad 2019",
    trips=DelimitedTable(path=..., encoding="utf-8"),
    zoning=SurveyZoning(shapefile=..., code_column="ZAT"),
    weight_column="f_exp",
    origin_zone_column="zat_origen",
    destination_zone_column="zat_destino",
    mode_column="modo_principal",
    duration_minutes_column=...,        # or None, and the run will say so
    mode_map={...},                     # every label that becomes an actor type
    modes_not_measured=(...),           # every label deliberately left out
    day_type_rule=...,                  # the year's own way of saying it
    weight_expands_to=...,              # established, never inherited
    published_total=...,                # what the reconstruction is checked against
    published_total_source="...",
    measures="...",
)
```

**The one thing a year may need beyond a declaration** is a rule for how it states
the day type, because four surveys do it four ways: an interview date in 2023, a
flag on the record in 2015, day-of-week flags in 2019, a separate database in
2011. Those are declared as small rule objects in `config.py` and dispatched
through `surveys._DAY_TYPE_HANDLERS`. Add one beside the others; do not add a
second way of reading a file. A declared rule with no handler fails with a message
naming itself, which is the behaviour that keeps the gap visible.

---

## 3. Run it, and read the log rather than the exit code

```
python -m src.run_pipeline exposure
```

The checks print as a table. What has to pass:

- **every trip the file weights is measured or named as set aside** — the four
  modes, plus the modes outside the study, plus the impossible ones, plus the
  unzoned, equal the file's own total. The two sides are different groupings of
  the same column, so it is a check and not a restatement;
- **apportioned plus outside equals the file, per actor type and per day type** —
  not in aggregate, because an aggregate over four modes can close while two of
  them are wrong in opposite directions;
- **the reconstruction reproduces the published total**;
- the grid is complete, nothing is apportioned twice, the derived columns are the
  divisions their names claim.

Then read the two tables `compare_years` prints at the end. **This is the check
that catches a misread declaration**, because nothing inside a year can: the
balance closes just as neatly on a wrong column as on a right one. A mode share
moving more than ten points, a per-inhabitant trip rate moving more than 35 %, or
two years ordering the thirty units below Spearman 0.70 is a misreading long
before it is a finding about the city. All three warn and none fails.

---

## 4. What the year must produce, unchanged

If any of this comes out differently, the declaration is wrong — not the shape.

- One row per unit, year, actor type and day type, in the columns
  `config.survey_exposure_columns()` declares, in that order.
- Two figures per combination, filed as
  `figures/exposure/<year>/<mode>/<kind>/`, with the year and mode repeated in
  the file name.
- The choropleth showing `TRIPS_PER_DAY_OF_TYPE`, on a ramp shared across the day
  types of that mode and never across modes.
- The desire lines clipped to the study area, drawn down to 95 % of the trips,
  width and opacity as the square root of the trips, units outlined without their
  numbers.

---

## 5. Finish by writing it down

A session ends in a file. Update, in the same commit as the code:

- **`docs/mobility-surveys-inventory.md`** — mark what the year resolved, correct
  anything it disproved, and add its row to the baseline in §6b;
- **`docs/design-decisions.md`** — a new decision if the year forced one, or an
  amendment to D38 if it only confirmed it;
- **`docs/verification-report.md`** §15 — the year's funnel, balance and figures;
- **`docs/data-layout.md`** — the files now read;
- **`deliverables/plan.md`** — what the year changes for the documents, in
  Spanish, and remember it is not in version control.

**And report the divergences rather than resolving them quietly.** A year that
disagrees with the anteproyecto, or with another year, is material for the thesis:
a jury comparing the documents will ask, and the answer is that working with the
data revealed something that could not be known beforehand.

---

## 6. What 2019 has that the others do not

**The delivered desire-lines layer is an incomplete 2019.** 181 lines, bicycle
only, and every one of its records matches an exact
`(zat_origen, zat_destino, f_exp)` triple among the 7,863 bicycle trips of the
2019 survey. It carries 9.6 % of that year's cycling and orders the thirty units
at Spearman 0.362 against the 2023 survey — an unexplained sample that does not
preserve the ranking, which is why it stopped being the variable. See D35 and D38.

That makes 2019's session the one that **retires it**, and the retirement has a
prerequisite worth more than the tidiness: it is a validation nothing else in the
study offers.

**Before removing it, check that the pipeline's own 2019 bicycle lines contain
it.** The delivered layer is a subset of the same records the survey holds, so
every one of its 160 origin-destination pairs must appear among the pairs built
from the survey, and the trips it attributes to each must be no more than the
survey's own total for that pair. Two independent readings of one source agreeing
on 160 pairs is the strongest confirmation the survey reader can get — and if
they disagree, the disagreement is a defect in whichever is wrong, found before
anything rests on it.

Only then remove `BICYCLE_DESIRE_LINES` from `EXPOSURE_LAYERS`, delete the
`delivered_2019_bicycle/` figure folder and the `reference__delivered_*` tables,
and say so in D35 and in section 13 of the verification report — which stays in
place as the record of what was measured on it, because figures quoted from it
have to remain reproducible.
