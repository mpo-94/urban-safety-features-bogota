# Adding a survey year to the exposure

The study's exposure is built from the household mobility survey: the desire
lines are constructed here rather than received, one per pair of zones, and each
gives every unit it crosses the share of its trips matching the share of its
length inside that unit. **2023 and 2019 are implemented. 2015 and 2011 are not.**

**2019 was the year that tested this procedure and it held.** The shape did not
bend: the measurement, the four actor types, the table, the figures and the
balance are the same code, and 2023's numbers are unchanged to the last decimal.
Two things were added, both declarations rather than logic, and both are the same
registry mechanism the day type already used — a `duration_rule`, because three of
the four surveys state the duration three different ways, and a list of zone codes
that name no place. What 2019 cost in reading was almost all inspection, and it is
the part this document exists to make cheaper.

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

**Read the whole delivery, not the data files.** This is the lesson of 2019 and it
is worth more than any single check here. Its questionnaire
(`Formularios/190220_Módulo D_DPR (viajes).pdf`) states the reference day in the
words the interviewer read out; its glossary defines the terms the report uses;
and its indicator annex (`Anexos/Anexo D - …`) publishes the control totals, per
mode **and per UTAM**, that turn a belief about the expansion factor into a
demonstration. None of that is in the CSVs, and the CSVs alone would have left
three of the six declarations resting on inference. Inventory the folder first —
every file, with its size — then read the instrument, the methodology chapter, the
glossary and the annexes, and only then start answering the questions below.

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

**Which day the reported trips belong to, and whether the year has more than
one.** Every year says it differently and none of them says it in the trip record.
2023's technical sheet gives the reference period as the day *before* the
interview, so the dates are shifted back one day; taking the interview date would
have filed every Saturday trip under a Sunday.

**And do not assume the year has a day-type dimension at all.** 2019 does not: it
surveyed one typical working day and nothing else, which its questionnaire, its
glossary, its report and its published matrices all say, and which its own data
confirm — travel participation within a point and a half across all seven days of
fieldwork. Its `p32_lunes`..`p32_domingo` flags look like the answer and are not:
they are asked as *"¿Qué días de la semana realiza este viaje?"*, so they record
declared recurrence, and a Saturday built from them would omit by construction
every trip made only at weekends. A year with one day type declares
`DayTypeIsAlwaysOne` and quotes the statement that says so; its other day types are
then **absent** from the table, never zero.

**How the year states the trip duration**, and **verify it against something else
before trusting it**. Three of the four surveys state it three ways, so it is a
`duration_rule` and not a column name: 2023 gives `duracion_min` in minutes, 2019
gives a departure and an arrival as fractions of a day, 2015 gives them as
`HH:MM:SS` text. 2023's agrees with its own fifteen-minute walking split, 3 to 14
minutes on one side and 15 to 439 on the other. 2019's derivation reproduces the
delivery's own `Aux_Duración` file on all but one record and lands 0.10 % from the
published fifteen-minute split. A year with no duration cannot have its
origin-destination pairs checked for plausibility, and the run says so rather than
implying the year is clean.

**If the duration is derived, round it to the minute.** `(0.302083333333333 −
0.291666666666667) × 1440` is 14.999999999, and without rounding a tenth of 2019's
walking falls on the wrong side of the fifteen-minute threshold.

**Every value of the mode column, on every row.** Not the first row. Each label
is either mapped to one of the four actor types or declared as deliberately not
measured; one in neither stops the run. There is no `OTHER` to fall through to.

**The zoning**, and whether every zone code the trips name exists in it. 2011
ships no zoning at all, and whether the 2015 zoning serves it has to be shown and
not assumed.

**And whether the delivery uses a code to mean "no zone".** 2019 writes a `0` in
`zat_origen` on records that carry no municipality and no UTAM either — a sentinel
for an unanswered question, not a missing polygon — and one record names `1917`,
above the top of its own zoning's range. Codes like these go in
`zone_codes_meaning_no_zone`, with the reason written at the declaration, and are
counted in the balance beside the records with no zone at all. A code in neither
the zoning nor that list still stops the run, which is what keeps the list a
declaration rather than a catch-all.

---

## 2. Declare it

One `MobilitySurvey` in `src/config.py`, appended to `MOBILITY_SURVEYS`. Nothing
else changes: the reading, the geometry, the apportionment, the checks, the
dictionary and the figures all follow from it.

```python
SURVEY_2015 = MobilitySurvey(
    year=2015,
    label="Mobility survey 2015",
    label_es="Encuesta de movilidad 2015",
    trips=DelimitedTable(path=..., encoding=..., decimal=...),
    zoning=SurveyZoning(shapefile=..., code_column=...),
    weight_column=...,                  # 2015 has four candidates; read Tomo VII
    origin_zone_column="ZAT_ORIGEN",
    destination_zone_column="ZAT_DESTINO",
    mode_column="ID_MEDIO_PREDOMINANTE",
    duration_rule=...,                  # or None, and the run will say so
    mode_map={...},                     # every label that becomes an actor type
    modes_not_measured=(...),           # every label deliberately left out
    day_type_rule=...,                  # the year's own way of saying it
    zone_codes_meaning_no_zone=(...),   # codes that name no place, with the reason
    weight_expands_to=...,              # established, never inherited
    published_total=...,                # what the reconstruction is checked against
    published_total_source="...",
    measures="...",
)
```

**Two things a year may need beyond plain fields**, and both are rule objects
declared in `config.py` and dispatched through a registry in `surveys.py`:

- **the day type**, because the surveys do it four ways — an interview date in
  2023, one kind of day and no other in 2019, a flag on the record in 2015, a
  separate database in 2011 — through `surveys._DAY_TYPE_HANDLERS`;
- **the duration**, because three of them do it three ways — minutes in 2023, two
  fractions of a day in 2019, `HH:MM:SS` text in 2015 — through
  `surveys._DURATION_HANDLERS`.

Add one beside the others; do not add a second way of reading a file. A declared
rule with no handler fails with a message naming itself, which is the behaviour
that keeps the gap visible.

**2015 will need a third duration rule and it is the last one expected.** Its
`HORA_INICIO` and `HORA_FIN` are `HH:MM:SS` strings, and it also ships
`DIFERENCIA_HORAS` in the same notation, which gives the derivation something to
be checked against exactly as 2019's `Aux_Duración` did.

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

**A warning is the start of an investigation, not the end of one.** 2019 fired the
Spearman check on pedestrians at 0.662 and it took four separate tests to
establish that the reading was right: the per-UTAM control against the published
annex, the count of zones each zoning puts in each unit, the area each zoning
assigns to each unit, and the correlation split into its inter- and intra-zonal
halves. Only after all four came back clean was it recorded as a disagreement
between the two surveys rather than a defect. **Do that work before writing the
year down**, and write down what it found either way — a warning nobody chased is
worse than no warning, because it looks like it was chased.

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

## 6. What 2019 had that the others do not — done

*Kept as a record of how it went, because the check it describes is the strongest
one this stage has ever had and a later session should know it was made.*

**The delivered desire-lines layer was an incomplete 2019.** 181 lines, bicycle
only, and every one of its records matches an exact
`(zat_origen, zat_destino, f_exp)` triple among the 7,863 bicycle trips of the
2019 survey. It carried 9.6 % of that year's cycling and ordered the thirty units
at Spearman 0.362 against the 2023 survey — an unexplained sample that did not
preserve the ranking, which is why it stopped being the variable. See D35 and D38.

**It was validated before it was retired, and it passed.** The layer is a subset
of the same records the survey holds, so every one of its origin-destination pairs
had to appear among the pairs the pipeline builds from that survey, with no pair
attributed more trips than the survey holds for it. Both hold: **160 of 160 pairs
present, none over-attributed**, compared on the records the two readings share.
Two independent readings of one source agreeing on 160 pairs is the strongest
confirmation the survey reader can get.

The comparison also showed that **the plausibility test removes 15 of those 160
pairs**, 7.9 % of the layer's trips, so the delivered layer carried records this
study judges impossible — and the fifteen come in symmetric pairs, one household's
outbound and return trip.

`BICYCLE_DESIRE_LINES` then left `EXPOSURE_LAYERS`; the `delivered_2019_bicycle/`
figure folder and the `reference__delivered_*` tables stopped being produced; and
the `exposure` route now runs that half only when a layer is declared, so nothing
is left behind measuring an empty table. The declaration stays in `config.py`
naming the file, and section 13 of the verification report stays in place, because
figures quoted from it have to remain reproducible.

**2015 and 2011 have no equivalent.** There is no delivered layer left to check
them against, so the cross-year comparison of section 3 is the only external check
those years will get, which makes reading it carefully more important and not
less.
