# 2011: the year that did not fit, and what it cost to make it

**This was a plan and is now a record.** It was written on 2026-09-08, before 2011
was implemented, to report the one place where the fourth year could not be made to
fit the shape the first three did — and to hand the implementing session what had
already been measured of the delivery. The year was implemented the same day, on
run `run_20260908_101110`. What follows is what happened, kept in place of the plan
because 2011 is the only year with a document of its own and because two of the
things the plan expected turned out to be wrong.

Read [`adding-a-survey-year.md`](adding-a-survey-year.md) for the procedure and
[`mobility-surveys-inventory.md`](mobility-surveys-inventory.md) §6b for the
contract. This is the exception report those two ask for.

---

## 1. What the machinery had to gain, and what it did not

**One thing did not fit and it was reported rather than absorbed.** Every year
before 2011 is one file of trips, and the day type is something found *inside* it —
an interview date joined from the household table in 2023, a constant in 2019, a
flag on the record in 2015. 2011 splits its two day types across two Access
databases: `DiaTipico` holds 122,361 trip records over 15,592 households and
`DiaSabado` 4,035 over 565, different samples of different households with the same
schema. Which kind of day a record belongs to is a property of the file it came out
of, and no field of `MobilitySurvey` could say that.

**The decision was the advisor's and it is the shape the plan recommended, made
concrete.** `MobilitySurvey.trips` is now a tuple of `TripSource`, and a
`TripSource` pairs one table with the day type that file carries — or with `None`,
which means the file holds more than one kind of day and the year's `day_type_rule`
says which. The reader tags every row with the source it came out of and
`DayTypeFromSource` reads the tag. Three things follow, and all three were the
point:

- **The ragged fact is in the declaration**, next to the path it is a fact about,
  where it can be read.
- **No day-type handler opens a file.** The alternative — a rule that declared the
  Saturday database and went and loaded it — was the smallest diff and the worst
  shape, and it is the second reader this design has refused since 2023.
- **The three years delivered as one file did not change meaning.** They declare a
  one-entry tuple with no day type on it and their rules decide as before.

*The plan's option (a) was right in substance and wrong in form.* It proposed
`trips={source: day_type}`, a mapping. That does not close: 2023's single file
carries three day types and 2015's carries two, so their value would have to be
`None` and the field would mean two different things at once. Putting the day type
on the source rather than in a mapping is the same idea with one meaning.

**The second addition is a reader and it went in as a registry entry.**
`AccessTable(path, table)` sits beside `DelimitedTable`, and `read_table` became a
dispatcher over `surveys._TABLE_READERS` — the third registry in the module, after
the day type and the duration. `pyodbc` is imported inside the reader rather than at
the top of the module, so the other three years still run where the Access driver is
absent, and `requirements.txt` gains it in this commit as `data-layout.md` said it
would. The rows are fetched through the cursor rather than handed to
`pandas.read_sql`, which warns on a raw `pyodbc` connection; a pipeline that prints
warnings nobody reads is how a real one gets missed.

**A third change was not foreseen and it is small.** The zone code is now spelled by
one function on both sides of every join. It had been spelled two ways that happened
to agree: the zoning cast its float code to an integer string, and the trips were
cast straight to text. That works while the trips carry text, and 2011's arrive as a
double — `903.0` against the zoning's `903`, which is one zone to a reader and two
keys to a join that would then match nothing at all. `surveys.zone_code_text` does
both sides, a code that is not a number keeps its text so that it still reaches the
check that refuses unknown codes, and a code with a fraction stops the run.

**And a column was added to the exposure table**, `SAMPLE_SUPPORT`; §3 says why it
is a column of its own rather than a third value of `VALUE_STATUS`.

**Nothing else moved. 2015, 2019 and 2023 come out of the run identical over all 720
of their rows and every one of their columns**, compared against
`run_20260908_052802` rather than merely re-checked. That was the condition on
touching the dataclass and it was met.

---

## 2. The controls, which are better than this document expected

The plan said 2011 would be the worst-verified year, with a single city total from a
neighbouring survey and published matrices covering three of its four modes. Both
halves of that were wrong.

**The Emme matrices are not a control at all.** `Matrices Finales/` holds eight Emme
text matrices and the plan expected them to check three modes. They are not the
household survey's matrices: the year's own matrix training deck describes them as
*ajustadas*, built from the intercept surveys and the traffic counts, corrected for
double counting, adjusted by a Pij factor and a select-link assignment in Emme, with
the household survey contributing only the origin-destination pairs the intercept
surveys missed — and even those re-expanded with the intercept factor, because *"la
expansión de hogares no permite utilizar directamente los viajes de esa matriz"*.
Bicycle goes from 69,648 to 15,538 trips in that process. They are a different
artefact from the one this pipeline rebuilds, and using them as a control would have
compared two things that were never meant to agree.

**Four real controls exist instead, and three of them are per mode.**

| What | Published | Read | Where |
|---|---:|---:|---|
| Weekday trips | 17,611,061 | 17,611,061.27 | Tomo I, indicator 18 |
| Saturday trips | 14,022,327 | 14,022,327.55 | Tomo I, indicator 27 |
| Weekday households | 2,444,256 | 2,444,259.6 | Tomo I, indicator 1 |
| Saturday households | 2,148,884 | 2,149,087.2 | Tomo I, indicator 1 |

The household figure is the sum of Bogotá's 2,148,884 and the 295,372 of the
seventeen municipal cabeceras. **The Saturday reproduces Bogotá's alone**, and that
is not a coincidence: Tomo II states *"la muestra para el día sábado se diseñó solo
para Bogotá"*. The two day types therefore expand to **different territories**,
which no other year does, and each expands to its own universe once — so
`weight_expands_to` is `DAY_OF_TYPE`, demonstrated rather than inherited.

**Both published modal splits are reproduced, mode by mode, on both kinds of day.**
Tomo I's Figura 18 gives the weekday split — walking 46 %, TPC 20 %, car 10 %,
TransMilenio 9 %, taxi 4 %, bicycle 3 %, motorcycle 2 % — and the reading gives
46.2, 20.4, 10.3, 8.5, 3.5, 3.5 and 2.3. Figura 21 gives the Saturday's — walking
34 %, TPC 23 %, car 21 %, TransMilenio 9 %, taxi 6 %, motorcycle 4 %, bicycle 2 % —
against 33.9, 22.9, 20.9, 8.2, 6.3, 3.5 and 2.2.

**The duration rule is checked against a published figure, exactly as 2019's and
2015's were.** Tomo I publishes a second split with the walking trips of under
fifteen minutes removed: walking 28 %, TPC 27 %, car 14 %, TransMilenio 12 %,
bicycle 5 %, taxi 5 %, motorcycle 3 %. Derived from `Min_Inicio` and `Min_Fin` the
reading gives **28.3, 27.2, 13.8, 11.3, 4.6, 4.7 and 3.1**. That is the whole figure
reproduced from a quantity the file does not state.

**And the strongest one is record for record.** The delivery ships a worked example
of the matrix-adjustment step, `Ejemplos Capacitación/03_Ejemplo Capacitación
Matrices_FE_Hogares.xlsx`, whose first sheet is the consultant's own extract of the
household survey's private-vehicle trips in the morning peak: 1,434 records with
`F_EXP`, `ZAT_ORIG` and `ZAT_DEST`. Filtering the database on `Modo_Principal =
Privado` and `PICO_AM = 1` gives **1,434 records whose weights sum to
176,849.2748766211 against the workbook's 176,849.2748766211, a difference of
exactly zero**, and 1,415 of the 1,434 agree on origin, destination and weight
together. The nineteen that do not have the same weight and a different destination
zone — a handful of zones recoded between the version the training example was cut
from and the version delivered. One extract of one file by two readers, agreeing on
every weight and on all but nineteen destinations, is the strongest confirmation
this reader can get for a year, and it settles the weight column, the mode label and
both zone columns at once.

**A fifth control is a neighbouring survey recounting this one.** Tabla 43 of the
2015 delivery's Tomo IV reads the 2011 database itself and publishes, for the study
region on a weekday: PEATON 8,136,778, TRANSMILENIO 1,494,082, OTROS 106,151, total
17,611,061 — identical to the trip on all four. The modes where its footnote says it
recomputed the hierarchy differ by tenths of a per cent: AUTO 1,818,499 against
1,818,802, BICICLETA 611,343 against 611,473, MOTO 410,613 against 411,095.

---

## 3. The three things the plan expected to be worse, and what they turned out to be

### The sixth of the trips with no zone is the imputation, not a failed interviewer

The plan said `ZAT_ORIG` or `ZAT_DEST` is empty on 21,515 weekday records and that
*"a household whose interviewer failed to code a zone is not a random household"*.
That framing is wrong and the truth is cleaner.

**The unzoned records are exactly the imputed ones.** `DONANTE` and `ID_DONANTE_VJ`
are set on 21,515 weekday records and 440 Saturday ones, and those are exactly the
records with no zone — zero imputed records carry a zone, zero unimputed records
lack one, in both databases, and the zone is absent at both ends together or at
neither. Tomo III explains it: 8,218 people travelled and did not answer the trip
module, and the consultant imputed the number and the characteristics of their trips
from a donor of similar occupation, stratum, locality and day. They did not impute a
geography. So the field is empty because nobody ever filled it, and there is nothing
to recover: the unimputed table, `MOD_D_VIAJES_Tipico`, carries no origin or
destination zone at all.

There is therefore no decision to take. The records are counted in the balance
beside every other trip that cannot be placed, which is what the machinery already
does, and the run says so on every execution: **12,733 records of the four measured
modes, 2,452,373 trips a day**. What has to be written down, and is, is that 2011's
exposure rests on the directly reported trips and that the imputation the consultant
performed to remove a non-response bias is undone for this study's geography,
because geography is the one thing it did not impute.

### The Saturday is as thin as expected, and the survey says so itself

4,035 records over 565 households expanding to 14,022,328 trips: one record stands
for about 3,475 trips, and over thirty units and four modes a cell holds roughly 34
records before any zone apportionment. Seven of the 240 Saturday cells come out at
zero, three of them whole units with no cycling at all.

**The decision was the advisor's: measure it and mark it.** What makes that a
marking rather than a judgement of ours is that the consultant said the same thing
three times. Tomo III expanded and analysed the Saturday *"a nivel de ciudad y
estrato socioeconómico"* where the weekday was analysed *"a nivel de UPZ"*; the
non-response imputation for the Saturday used the code `TL`, every locality
together, because there was no sample by locality; and Tomo I adds that *"el nivel
de error de esta estimación es mayor que para el día hábil"*.

**It is marked in a column of its own and not in `VALUE_STATUS`, and that is a
correction to what was agreed.** The option put to the advisor said a new
`VALUE_STATUS` value. Implementing it showed that would be wrong: `VALUE_STATUS`
answers "is there a number here", every check in the run filters on
`MEASURED` meaning "rows that have a number in them", and a third value would have
silently dropped 120 rows out of each of those checks. Whether the sample reaches
the scale of one unit is a different question and it gets a different column,
`SAMPLE_SUPPORT`, with `SUPPORTS_UNIT` and `CITY_LEVEL_ONLY`. The decision — publish
it, marked — is unchanged; only the mechanism is.

**And the Saturday behaves like a Saturday**, which is worth recording because it is
the one thing that would have said the file was misread. Against its own weekday,
inside the thirty units, walking falls 29 % and cycling 18 % while car travel rises
89 %; 2015's Saturday falls 32 % and 17 % and rises 50 %. Motorcycle is the
exception, rising 43 % where 2015's falls 23 %, and it rests on 135 records.

### The published matrices do not cover walking, and it did not matter

The plan was right that no pedestrian matrix exists in the delivery. It stopped
mattering when the Emme matrices turned out not to be a control for any mode, and
when Tomo I's two modal splits turned out to be one.

---

## 4. The 46 % gap in walking, chased to the bottom

2011 measures 8,136,778 walking trips on a weekday against 2015's 5,576,942 — a
46 % difference and, before this pass, the largest unexplained gap anywhere in the
series. It is explained, and the explanation is specific.

**It is not our reading.** Tabla 43 of the 2015 delivery's Tomo IV gives 8,136,778
for 2011, to the trip, read by a different consultant out of the same database.

**It is entirely in the walks of under fifteen minutes.**

| | 2011 | 2015 | difference |
|---|---:|---:|---:|
| Walking, weekday | 8,136,778 | 5,576,942 | −31 % |
| of which 15 minutes or more | 3,733,664 | 3,600,521 | −4 % |
| of which under 15 minutes | 4,403,115 | 1,976,421 | −55 % |

The 2011 figures are derived from `Min_Inicio` and `Min_Fin` and reproduce Tomo I's
published split; 2015's under-fifteen figure is its own published one. **The two
surveys agree on long walking within 4 % and disagree on short walking by a factor
of 2.2.**

**The instruments differ exactly there.** 2011's questionnaire carries an
instruction beside its walking code: *"Para viajes realizados completamente a pie
incluya siempre los viajes al trabajo y estudio. Para otros propósitos solo aquellos
cuya duración sea mayor a 3 minutos"*, and it tells the interviewer not to ask about
stages for a trip made wholly on foot — so a short walk is both explicitly asked for
and cheap to record. 2015's trip module states no floor and no such prompt, defines
a trip only as *"un desplazamiento dentro o fuera de la ciudad/municipio con un
origen, un destino y un motivo específico"*, and records walking as a stage with its
own minute counter, *"¿Cuánto tiempo en minutos caminó para llegar a __?"* — which
pushes a short walk into being a stage of the next trip rather than a trip of its
own.

**And the delivery's own arithmetic points the same way.** Tabla 43 counts stages as
well as trips: pedestrian **stages** fall 17 % between the two surveys while
pedestrian **trips** fall 31 %. People were still walking in 2015; more of that
walking was recorded inside a motorised trip. The 2015 consultant says so in words —
*"los viajes peatonales que disminuyen notoriamente como viajes, pero mantienen un
comportamiento similar en etapas"*.

**A second, wider difference runs alongside it and is worth stating on its own: 2011
reports shorter trips than 2015 in every mode.** The median trip is 10 minutes
against 17 on foot, 15 against 25 by bicycle, 30 against 40 by motorcycle and 30
against 45 by car. Congestion did worsen sharply between the two surveys and part of
that is real, but a walking median going from 10 to 17 minutes is not a change in
the city. Two things in this study follow from it directly, and neither is a defect:

- **2011 is more intra-zonal in every mode** — 38.0 % of its walking against 28.4 %
  in 2015 on the same zoning, 11.9 % of its car travel against 5.3 %. Split at
  fifteen minutes the walking figures nearly meet, 49.1 % against 45.4 % below and
  25.1 % against 19.0 % above, so most of the aggregate difference is the mix of
  short and long trips rather than a difference in how a trip was coded.
- **2011 loses more to the plausibility test**, 6.6 % against 2015's 1.9 %, because
  that test asks whether the two zones are further apart than the mode could cover
  *in the duration reported*, and 2011's durations are shorter.

---

## 5. What came out, and the four warnings the cross-year check raised

The baseline is in the inventory's §6b and is not repeated here. What belongs here
is the year's own funnel and the warnings, because a warning nobody chased is worse
than no warning.

**2011 delivers a smaller share of its city totals to the thirty units than any
other year**, and the share differs by mode:

| Share of the survey's own weekday total inside the units | 2011 | 2015 | 2019 | 2023 |
|---|---:|---:|---:|---:|
| `PEDESTRIAN` | 67.3 % | 80.0 % | 59.9 % | 70.1 % |
| `BICYCLE` | 53.1 % | 74.8 % | 65.2 % | 69.3 % |
| `MOTORCYCLE` | 65.5 % | 85.8 % | 74.3 % | 79.1 % |
| `CAR` | 75.4 % | 89.1 % | 79.7 % | 83.4 % |

The gap against 2015 is the two facts above: the imputed trips that carry no
geography, and the shorter durations that fail the plausibility test more often. It
matters for reading the table, because a mode's level inside the units is depressed
relative to its own city total by a year-specific and mode-specific amount — which
is why the cross-year comparison warns where the published city-level comparison
does not.

**Four warnings fired between 2011 and 2015 and all four survived investigation.**

1. **`PEDESTRIAN` moves −13.7 points of the four-mode share.** The 2015 delivery
   publishes the same comparison and gives −13.9 points over all twelve modes,
   *"en viajes, de 46,2 % a 32,3 %"*. Section 4 is what it is.
2. **`BICYCLE` trips per inhabitant move +92 %.** The city totals move +38.5 %, which
   the 2015 delivery publishes as +38.50 %; the rest is 2011 delivering 53.1 % of its
   cycling to the units against 2015's 74.8 %.
3. **`MOTORCYCLE` trips per inhabitant move +161 %.** The city totals move +102.8 %,
   which the 2015 delivery publishes as +102.82 % and calls out as the largest change
   in the survey — motorcycle travel doubled in Bogotá between 2011 and 2015. The
   rest is the same funnel.
4. **`BICYCLE` orders the units at Spearman 0.474.** This one is a finding about the
   city and not about the reading, and three tests say so. The two years share a
   zoning — 2011 borrows 2015's — so the zoning cannot be the cause. The allocation
   rules agree with each other inside 2011, at 0.944 against the origin and 0.931
   against the destination. And **the raw files say the same thing with no pipeline
   at all**: summing each survey's own expansion factor over its cycling trips by
   origin zone, one zoning for both, no lines, no apportionment and no duration
   filter, gives Spearman **0.485**. The pattern is legible — cycling falls in the
   south-western periphery (Patio Bonito −50 %, Suba −48 %, Tibabuyes −33 %) and
   rises in the centre and north (Chapinero +824 %, Teusaquillo +518 %, Barrios
   Unidos +328 %, Niza +320 %) — and **2019 and 2023 hold the higher levels**, so
   2011 is the odd year of four rather than 2015 the odd year of two. Two things are
   true at once and the study cannot separate them: cycling did reorganise across
   the city in those four years, and 2011's cycling rests on 3,526 zoned records
   spread over thirty units.

**The sliver threshold keeps its value on a measured indifference, the third year to
do so.** 2011 borrows 2015's zoning, so the overlay is the same one and there is no
empirical gap in it: 1,285 fragments, the largest below the cut at 0.0994 % of its
zone and the smallest above it at 0.1007 %, running continuously across. Swept from
a ten-thousandth to a hundredth, **the largest per-unit figure moves 0.41 %** and the
pedestrian one 0.33 %, against 0.096 % for 2015 and 0.16 % for 2019. Larger than
either, because 2011 puts more of its travel in the peripheral zones the fragments
touch, and still far too small to be what any figure rests on.

---

## 6. What is left open, and it is for a person

**Whether the Saturday enters a model.** It is measured, marked and exported, and
the series now has three Saturdays — 2011, 2015 and 2023. One of the three is
marked as not reaching the unit and one of the other two, 2023's, needs rescaling to
be read as a Saturday at all and then says a Saturday carries as much travel as a
Tuesday. D38 keeps this open and 2011 does not close it.

**Whether the two day types of 2011 can be compared to each other at all.** They
expand to different territories: the weekday to Bogotá plus seventeen municipal
cabeceras and the Saturday to Bogotá alone. Inside the thirty units, which are all
in Bogotá, that difference is largely absorbed — what falls outside is measured
rather than redistributed — but it is a difference of universe and not of sample,
and it should be said in the report rather than discovered by a reader.

**Whether a year that loses a sixth of its trips to an imputation without geography
can carry the same weight as one that does not.** The record balance closes and the
figure is honest, and the question is whether 2011 belongs in a panel on the same
footing as 2015, 2019 and 2023 or whether the models should carry something that
says it does not. That is a modelling decision and it is not taken here.
