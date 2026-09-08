# Adding a survey year to the exposure

The study's exposure is built from the household mobility survey: the desire
lines are constructed here rather than received, one per pair of zones, and each
gives every unit it crosses the share of its trips matching the share of its
length inside that unit. **All four years are implemented.**

**2011 was the last and the only one that did not fit.** Its two day types live in
two Access databases, so which kind of day a record belongs to is a property of the
file it came out of and no field of `MobilitySurvey` could say that. That was
reported rather than absorbed, the advisor took the decision, and the change was
made once: `trips` is now a tuple of `TripSource`, each pairing a table with the day
type its file carries; `AccessTable` is a third entry in a reader registry; and
`DayTypeFromSource` reads a tag the reader writes instead of opening a file itself.
**2015, 2019 and 2023 came out of the run identical over all 720 of their rows and
every column.** What the year cost, and the two controls nobody expected it to have,
are in [`implementing-2011.md`](implementing-2011.md), which was the plan and is now
the record.

**2015 was the third and it held again, at a lower price.** One declaration, two
registry entries — a `day_type_rule` reading the flag the delivery already wrote on
the record, and the third and last `duration_rule` — plus one new `SurveyZoning`
field for a zone that arrives in pieces. 2019 and 2023 come out of the run
**identical to the last decimal over all 480 of their rows**. What 2015 added to
the study is a second day type: its `DIA_NOHABIL` is a Saturday and only a
Saturday, so the day type is a dimension two of the three measured years carry
rather than a property of 2023, and D38's open question about it is now a real
question instead of a foregone one.

It also brought the strongest external control this stage has ever had. The
delivery publishes twenty origin-destination matrices — the artefact this pipeline
rebuilds — and the reading reproduces two of them **to the last decimal on both
kinds of day**. That check is what identified the zone sentinels: the readings
differed by 1,665 trips before they were set aside, and every disagreeing pair had
a `0` at one end.

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

0. **[`implementing-2011.md`](implementing-2011.md)**, if the year is 2011. It is
   the only year with a document of its own, because it is the only one that asks
   for a change to the machinery rather than a declaration.
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

**2015 needed a third duration rule and it is the last one expected.** Its
`HORA_INICIO` and `HORA_FIN` are `HH:MM:SS` strings, and it also ships
`DIFERENCIA_HORAS` in the same notation, which gave the derivation something to be
checked against exactly as 2019's `Aux_Duración` did — and it reproduces it on all
147,251 records rather than on all but one. `DurationFromTextClockColumns` is
written.

**And 2015 needed one thing this section did not predict, which is a field and not
a reader.** Its zoning has 948 features and 945 codes, because two zones arrive as
several detached polygons. `SurveyZoning.zone_delivered_in_parts` says so, and it
is off by default: a repeated code still stops the run for a year that has not
looked, because the reader cannot tell a multipart zone from two zones sharing a
number and the year that has read its `AREA` column is the one that can.

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

**2015 turned out to have something better, and 2011 has nothing.** This paragraph
said the cross-year comparison would be the only external check either year would
get. That was wrong about 2015: its delivery publishes the origin-destination
matrices themselves, and the reading reproduces two of them to the last decimal on
both kinds of day, mode by mode. That is a stronger control than 2019's per-UTAM
table, because it exercises the origin *and* the destination of every pair rather
than a household's own zone — and it is the check that found 2015's zone sentinels.

2011 has no such thing, so for that year the sentence stands as written.

---

## 7. Every mistake made so far, and what caught it

**Read this before starting.** Each of these was made, found and fixed, and each
would have been cheap to avoid and expensive to leave. They are ordered by how
easy they are to repeat.

### Comparing two years on a column whose meaning depends on the year

`compare_years` read `TRIPS_PER_AVERAGE_DAY` — what the file holds, and what the
balance closes on. But what it holds depends on `weight_expands_to`: 2023's
weekday rows carry 77.2 % of a weekday and 2019's carry all of one, so the
comparison measured a whole day against three quarters of one and made every 2023
mode look 23 % smaller than it is. Car came out at −35.0 % against a 35 %
threshold, one decimal from warning about an artefact of its own arithmetic.

**Why it survived:** the check was written when one year existed, and a comparison
with nothing to compare against cannot be wrong. It became wrong the instant a
second year declared a different expansion.

**What caught it:** all four modes falling by roughly the same amount. Four modes
measured independently do not collapse in unison; a uniform factor across all of
them is arithmetic and not a city.

**What to do:** anything that puts two years side by side — a table, a rate, an
interpolation, a model, a dashboard chart — reads `TRIPS_PER_DAY_OF_TYPE`. In
`exposure.py` that is `_COMPARABLE_TRIPS_COL`, declared with the other module
constants; use it rather than naming the column again. The run now warns whenever
the declared years disagree on what their factor expands to, and the exported
dictionary says which column is comparable, in capitals.

**And expect the same class of defect elsewhere.** The rule generalises: any
quantity computed *across* years from a column whose meaning `weight_expands_to`
controls is suspect, and no check written inside one year can see it.

### Writing a check that only one shape of year can pass

`the universe shares of a year add to one` was true of every year that existed when
it was written. It stopped being true at the third. A year whose factor spreads the
universe over all its reference days gives each day type a fraction of it and the
fractions sum to one — that is 2023. A year whose factor already expands to one day
of the record's own kind converts nothing, so each share is one on its own; 2019
passed only because it has a single day type and 1.0 sums to 1.0 by accident.

**2015 is the first year with more than one day type *and* a factor that expands to
one day of each**, so its shares are 1.0 and 1.0 and they sum to two. Correctly. The
check failed a year that was right.

**Why it survived:** the combination did not exist. Neither of the first two years
could have produced it, and a check that no available input can break looks like a
check that works.

**What caught it:** running the year. The check is inside the run and it failed
loudly, which is the behaviour that made it cheap — five minutes rather than a
figure quoted in a deliverable.

**What to do:** it now asks what the year's own `weight_expands_to` implies —
that the shares partition the universe, or that each of them covers it once. And
the general form is the one already recorded above: **anything a check asserts about
day types, universes or trip columns has to be conditioned on `weight_expands_to`,
because that field is what those quantities mean.** This is the second entry in this
section with the same root and it will not be the last; 2011 has yet to declare
which of the two it is.

### Printing a sentence about one day type for a year that has two

The same run said of 2015 that "the year carries no second day type to compare it
against" — a sentence written for 2019, which has one, printed for a year that has
two. It was true of every year that had reached that branch before.

**What caught it:** reading the log rather than the exit code, which is what
section 3 of this document exists to insist on. The run passed every check while
printing it.

**What to do:** a sentence about a year's day types is conditioned on how many it
has, exactly as a sentence about its weighting is conditioned on
`weight_expands_to`.

### Deriving a duration without rounding it

2019's `(0.302083333333333 − 0.291666666666667) × 1440` is 14.999999999, so an
unrounded derivation puts a fifteen-minute walk under fifteen minutes. That moved
a tenth of the year's walking across the threshold — 3,590,383 trips instead of
3,956,917 — and the wrong figure reached D38 and the inventory before it was
caught.

**What caught it:** the survey publishes the same split. Ours was 48.3 % against a
published 43.1 %, and rounding closed the gap to a tenth of a point.

**What to do:** round a derived duration to the minute, and check it against a
published figure rather than against its own plausibility.

**And 2015 is the year that shows the second half of that sentence is the rule and
the first half is the remedy.** Its clock columns are exact `HH:MM:SS` text, so
there is no floating-point loss to repair, and rounding *introduces* the error the
rounding exists to remove: it moves 619 Saturday walking trips above fifteen
minutes that the survey itself counts below, and the published Saturday figure
stops being reproduced. Unrounded, both of that year's published fifteen-minute
splits come out exactly. So `round_to_minute` is a declared field and 2015 declares
it off — after measuring that it changes nothing else, the plausibility test
rejecting the same 1,096 records either way with **not one record changing side**.
Check against the published figure; round only if that is what makes the two
agree.

### Spelling one key in two places that happen to agree

Zone codes are text on both sides of every join. The zoning cast its float code to
an integer and then to text; the trips were cast straight to text. Two pieces of
code, one convention, and they agreed for three years because those three years
deliver their zone codes as text that already reads as an integer.

2011 delivers its zone codes out of a database, as a double. `903.0` against the
zoning's `903` is one zone to a reader and two keys to a join — and a join on a key
that matches nothing does not fail, it returns nothing, so the year would have come
out with every trip unplaceable or, worse, with a subset that happened to match.

**Why it survived:** it was never wrong. Nothing in the three implemented years
could make the two spellings disagree, so the duplication looked like a coincidence
rather than a defect.

**What caught it:** running the fourth year, which stopped on the check that
refuses zone codes the zoning does not have. The good failure, and only because
that check exists.

**What to do:** one function spells the key, and both sides call it —
`surveys.zone_code_text`. The general form is the one this section keeps
rediscovering: **a rule implemented twice is a rule that holds until the input that
distinguishes the two implementations arrives**, and the years are exactly the
sequence of inputs designed to find those.

### Overloading a column that half the checks filter on

2011's Saturday had to be marked as resting on a sample the survey itself only ever
claimed at the scale of the city. The obvious place was a third value of
`VALUE_STATUS`, and that is what was put to the advisor and agreed.

It is the wrong place. `VALUE_STATUS` answers "is there a number here" —
`MEASURED` against `NOT_MEASURED` — and every derived-column check in the run
filters on `MEASURED` meaning "rows that have a number in them". A third value
would have silently removed 120 rows from each of those checks, which is the
opposite of what marking a row is for.

**Why it nearly happened:** the two facts sound alike in prose. "This row is not
fully trustworthy" reads as a status, and there was already a status column.

**What caught it:** reading what the existing filters mean before adding the value,
rather than after. Cheap here and expensive one run later.

**What to do:** a new fact gets a new column unless it answers the *same question*
the existing one answers. `SAMPLE_SUPPORT` is separate from `VALUE_STATUS` and the
dictionary says in as many words that they are different questions.

### Taking a delivered artefact for the thing the pipeline rebuilds

2011 ships eight Emme origin-destination matrices, and the plan for that year
expected them to be the per-mode control that made 2015 the best-verified year.
They are not a control at all. The year's matrix training deck describes them as
built from the intercept surveys and the traffic counts, corrected for double
counting, adjusted by a Pij factor and a select-link assignment — with the
household survey contributing only the pairs interception missed and even those
re-expanded with the intercept factor, because *"la expansión de hogares no permite
utilizar directamente los viajes de esa matriz"*. Bicycle goes from 69,648 to
15,538 trips in that process.

Checking against them would have compared two artefacts that were never meant to
agree, and every disagreement would have looked like a defect in the reading.

**What caught it:** reading the deck that explains how they were built, before
using them. It is thirty-six slides and it is the only document in the delivery
that says so.

**What to do:** before a delivered table is used as a control, find the document
that says how it was made. 2015's matrices are a control because they are the
survey's own expansion of the survey's own records; 2011's are not, and nothing
about the file names distinguishes the two cases.

### Assuming a threshold's justification is general

`ZONE_UNIT_MIN_AREA_SHARE` sits at a thousandth because the 2023 overlay has an
empirical gap: no sliver above 0.035 % of its zone, no genuine split below 1.73 %.
D38 stated that as though it were a property of the rule. It is a property of the
2023 zoning. **On 2019 the fragment sizes run continuously across the cut** —
0.0993 % below against 0.1002 % above — because that zoning does not nest inside
the UPL.

**What caught it:** re-running the measurement on the new year instead of citing
the old one.

**What to do:** every year must show one of two things — an empirical gap, or a
measured indifference. Sweep the threshold across two orders of magnitude and
report how far the per-unit figures move. For 2019 it was 0.16 %, which is why the
constant stayed. A year that shows neither needs an argument of its own.

**And 2011 adds the twist that nearly made this mistake a second time.** It borrows
2015's zoning, so its overlay is the same overlay and its fragment distribution is
the same distribution, to the last figure. It is tempting to cite the sweep with
it. That is wrong: the overlay is a property of the zoning and the cartography, and
how much the threshold *moves a figure* is a property of how the year's travel sits
on the fragments. 2011's largest per-unit figure moves **0.41 %** where 2015's moves
0.096 %, four times as much on the identical geometry, because 2011 puts more of its
travel in the peripheral zones the fragments touch. **Two years sharing a zoning
share the gap and not the indifference.** Re-run the sweep.

### Believing a data dictionary

2019's `Anexo B` calls the trip table's `fecha` column "Fecha del viaje". It is
the date of the **interview**; the trips are the previous day's. Taking the
dictionary at its word would have filed every trip one day late.

**What caught it:** the questionnaire, which states the reference period in the
words the interviewer read out, plus a test on the data — among trips the
respondent makes on exactly one weekday, 1,884 of 3,448 match `fecha` minus a day
against 190 matching `fecha` itself.

**What to do:** the delivered dictionary is a claim like any other. The instrument
outranks it.

**2011's dictionary contradicts itself, which is the sharper version of the same
thing.** Module A of its database manual calls `DIA` "día de la semana de
realización de la encuesta" and module D calls it "día de la semana en que se hizo
el viaje" — the interview day and the trip day, which the questionnaire puts a day
apart. Taking module A at its word would have filed the whole `DiaSabado` database
under Friday and a fifth of the weekday one under Sunday. What settled it was not
another document but the data's own behaviour: across the five values of the weekday
file the households make 7.02 to 7.43 trips and 10.4 % to 11.6 % of those trips are
for study, so none of the five is a Sunday; the Saturday file has 2.3 % for study,
9.8 % shopping and 9.4 % recreation, so the sixth is not a Friday. **When two claims
in one delivery disagree, measure the thing they are claims about.**

### Asking before finishing the reading

The 2019 session nearly put a decision to the advisor with the questionnaire, the
glossary and the indicator annex still unopened — the three files that between
them answered it. He stopped it.

**What to do:** inventory the folder, every file with its size, then read the
instrument, the methodology chapter, the glossary and the indicator annexes.
*Then* formulate the question, if there is still one.

### Printing a statement about one year's weighting for a year it does not fit

The run warned, for 2019, that "the expansion factor represents the universe once
over all seven reference days" — which is true of 2023 and false of 2019.

**What to do:** any sentence the run prints about what the factor expands to must
be conditioned on `weight_expands_to`, not written once for the year in front of
you.

### And the one from the inventory pass, still the best example

Searching a column list for a duration matches `p34_aplicacion_durante_viaje`,
because "durante" contains "dura". It parses, it summarises, and every number out
of it is meaningless.
