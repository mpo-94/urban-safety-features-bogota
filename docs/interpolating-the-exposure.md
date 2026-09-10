# Interpolating the exposure over the years no survey covers

**Read [D39 and D40](design-decisions.md) first.** They are the decisions; this is
what to build and what to check it against. It is the counterpart of
[`adding-a-survey-year.md`](adding-a-survey-year.md) for the stage that comes after
the four years are read.

The exposure is measured in 2011, 2015, 2019 and 2023. The casualty series runs
2007–2024 observed and 2008–2024 corrected. **Fourteen of the eighteen years have no
survey**, and the panel the models are fitted on needs all of them.

---

## 1. What the stage produces

One row per unit, year, actor type and day type, over the **whole** window
2007–2024, with the measured years in it unchanged and every other year
constructed. It is a separate table from `analysis__exposure_by_unit`, not a
replacement: that one is the record of what the surveys measure and it must stay
readable on its own, exactly as the corrected casualty set never replaces the
observed one (D31).

Columns, beyond the identity the other tables already share:

| Column | What it holds |
|---|---|
| `TRIPS_PER_DAY_OF_TYPE` | the level, measured or constructed |
| `TRIPS_PER_DAY_OF_TYPE_OVER_15MIN` | the same on D39's pedestrian definition; identical to the first for the three modes that have only one definition |
| `TRIPS_PER_INHABITANT` | the rate the interpolation actually runs on |
| `POPULATION` | from the annual panel, D36 |
| `EXPOSURE_PROVENANCE` | `MEASURED`, `INTERPOLATED` or `HELD` |
| `YEARS_TO_NEAREST_SURVEY` | 0 at a survey year, 1–2 between them, 1–4 outside |
| `SAMPLE_SUPPORT` | carried through from the survey year the value rests on |

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

**Do it twice, once per pedestrian definition**, or once over a table that already
carries both quantities. Nothing else in the procedure changes: the three other
modes have one definition and both columns hold the same number for them.

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

## 5. What is open when this is built

- **Whether the held block enters the models.** Four of eighteen years with no
  behavioural variation, only demographic.
- **Whether 2005 is implemented.** Settled by the check in section 3.
- **Whether the anchored version replaces this one.** D40 defers it and says why.
- **What the Saturday series does across its twelve-year gap**, and whether a
  Sunday series exists at all.
- **Which casualty set the window follows**, 2007–2024 or 2008–2024. The table is
  built over the wider one so that the choice stays a filter.
