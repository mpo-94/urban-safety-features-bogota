# Implementing 2011: the year that does not fit the shape

**Read [`adding-a-survey-year.md`](adding-a-survey-year.md) first.** That is the
procedure and it holds for 2011 as it held for the other three. This document is the
exception report the contract asks for: *"If a year cannot be made to fit that
without changing it, **stop and report it** rather than bending the shape."* 2011
cannot, in one respect, and this is that report.

It also carries what was measured about the delivery in advance, on 2026-09-08,
right after 2015 landed — so the session that implements 2011 does not spend its
first hour discovering the folder. The measurements live in
[`mobility-surveys-inventory.md`](mobility-surveys-inventory.md) §5; what is here is
the part that is a decision rather than a fact.

**Nothing in this document is declared.** The six things §6b requires must still be
established by the implementing session against the year's own documents. What is
below narrows the work; it does not do it.

---

## 1. What went right, so it is not re-litigated

Three of the four things that could have stopped 2011 are answered already, and by
measurement rather than by hope.

**The 2015 zoning serves.** 2011 ships no zoning at all. Its trips name 913 distinct
codes on the weekday and 607 on the Saturday, and **every one of them is in
`ZATs_2012_MAG`** — zero absent, carrying zero trips, in both databases. The
declaration is a `SurveyZoning` pointing at another year's file with the reason
written beside it, which is a case the dataclass was built for: the zoning is
declared beside the trips precisely so that a year which has to borrow one says so
instead of having it inferred at read time.

*It still has to be argued and not merely stated.* The file is named
`ZATs_2012_MAG` — 2012, a year after the survey — so the implementing session should
say why a 2012 zoning is the right frame for 2011 travel, and the 2011 report is
where that argument lives. The codes matching is necessary and it is not sufficient.

**The duration needs no new rule.** `Min_Inicio` and `Min_Fin` are whole minutes
from midnight, and that was verified against a second pair of columns rather than
read off the names: `Min_Inicio` equals `HR_INI × 60 + MIN_INI` on all 122,361
records. So `DurationFromClockColumns(start_column="Min_Inicio",
end_column="Min_Fin", minutes_per_unit=1.0)` reads it and the registry gains nothing.
The three duration rules that exist are the three that were needed.

**Two details of that, and both would be silent if got wrong.** The columns run 240
to 1,680, which is 04:00 to 04:00 the next day — the same reference window every one
of these surveys states in its questionnaire — so a trip after midnight is encoded
as 1,500 and not as 60. **`wrap_at_midnight` must therefore be off.** Left on it
would do nothing at all, because no difference is ever negative, and the declaration
would carry a claim about the data that is not true. And `round_to_minute` is
irrelevant rather than false here: the columns are already whole minutes, so either
value gives the same answer, and the honest declaration says nothing needs rounding
instead of pretending a choice was made.

**The join is one column.** Trip to household is `ORDEN`; trip to person is
`(ORDEN, ID_PERSO)`; all 122,361 trips find both. `F_EXP` is the *same number* on the
trip, the person and the household, which is simpler than 2015 and means the
household arithmetic for `weight_expands_to` needs no join at all.

---

## 2. The thing that does not fit: two day types, two files

Every year so far has been one file of trips, and the day type has been something
found **inside** it — an interview date joined from the household table in 2023, a
constant in 2019, a flag on the record in 2015. So `MobilitySurvey.trips` is a single
source, and `day_type_rule` is a rule that reads an already-loaded frame.

**2011 splits the day type across two Access databases.** `DiaTipico` holds 122,361
trip records over 15,592 households; `DiaSabado` holds 4,035 over 565. They are
different samples of different households, with the same schema and `_Sabado`
suffixes on the table names. The day itself is not ambiguous — both the household and
the trip carry a `DIA` column, 1–5 in the weekday file and 6 in every row of the
Saturday one, agreeing on every record — but **which day type a record belongs to is
a property of the file it came out of**, and no field of `MobilitySurvey` can say
that.

So 2011 needs two things the other three did not:

1. **A reader for Access**, where `trips` is a `DelimitedTable` today.
2. **More than one source per year**, each carrying a day type.

### The first is small, and it follows a pattern the module already has

`DelimitedTable` is a declaration of *how to read one table*. An `AccessTable(path,
table)` beside it, plus a registry in `surveys.py` mapping the declared type to a
reader, is the same mechanism the day type and the duration already use — a third
registry, not a second way of reading a file. `read_table` becomes a dispatcher over
two source types and everything downstream is untouched, because what it returns is a
`DataFrame` either way.

The connection is one line, and the driver is installed and verified:

```python
pyodbc.connect(r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + str(path.resolve()))
```

It needs the **64-bit** Access ODBC driver matched to the venv's 64-bit Python; a
32-bit driver would not have worked. `pyodbc` is installed and **not in
`requirements.txt`**, deliberately, because nothing declared reads it yet. **The
commit that first reads 2011 adds it**, which `data-layout.md` already says.

One caution the inspection turned up: `pandas.read_sql` warns on a raw `pyodbc`
connection, because it is not a SQLAlchemy connectable. It works and the warning is
noise — but a pipeline that prints warnings nobody reads is how a real one gets
missed, so the reader should either go through SQLAlchemy's `access+pyodbc` dialect
or fetch through the cursor and build the frame itself.

### The second is the actual decision, and it should not be taken alone

Three shapes are possible and they are not equally good.

**(a) `trips` becomes a mapping of source to day type.** `trips={source: day_type}`,
with the single-source years declaring one entry. 2011's day-type rule is then
`DayTypeFromSource()`, reading the mapping the loader already used. Honest, and it
puts the ragged case in the declaration where it can be seen.
*Cost:* it changes `MobilitySurvey.trips` for all four years and rewrites three
working declarations to say what they already say. That is a change to make once and
never again, which argues for making it deliberately rather than in a hurry.

**(b) A day-type rule that owns the second source.** `DayTypeFromSeparateDatabases`
declares the Saturday source, and its handler reads it and appends. Nothing changes
for the other three years.
*Cost:* it inverts the flow — a day-type handler would be loading trips, which is
exactly the "second reader" this design has been avoiding since 2023. It is the
smallest diff and the worst shape, and it should probably be rejected for that.

**(c) Two `MobilitySurvey` entries for one year.** Simplest to write, and it breaks
the table: the grid is built per year, `compare_years` groups by year, and two
declarations sharing `year=2011` would either collide or silently double-count.
Recorded so that nobody rediscovers it.

**My recommendation is (a), and it is a recommendation and not a decision.** It puts
the ragged dimension where the rest of the design already puts ragged things — in the
declaration, visible — and it is the only one of the three that would still be right
if a fifth survey arrived split some other way. But it touches three years that
currently reproduce their figures to the last decimal, so **the implementing session
must re-run and confirm 2015, 2019 and 2023 come out unchanged before anything
else**, exactly as the 2015 session did.

**Ask before building it.** It changes no number and no methodology, so it is not a
question about what the study counts — but it is a change to the one dataclass the
whole exposure stage rests on, and the project's rule is that the machinery is
written once and declared three times. Bending it at the fourth year is precisely the
case the contract asks to be reported rather than absorbed.

---

## 3. Three things that will be worse in 2011 than in any year before it

None of these is a defect to fix. They are properties of a 2011 survey, and the
implementing session should expect them, write them down, and not read them as
evidence that something was read wrongly.

**A sixth of the trips have no zone.** `ZAT_ORIG` or `ZAT_DEST` is empty on 21,515
weekday records, **16.1 % of the expanded trips**, against 6.1 % in 2019 and none in
2023. The field is empty rather than holding a code that names no place, so
`zone_codes_meaning_no_zone` does not apply and they land in the balance as records
with no zone at all. **Whether a sixth is acceptable is a question for the advisor**,
and the honest framing is that it is not obviously random: a household whose
interviewer failed to code a zone is not a random household. If it concentrates
anywhere, that is a finding about the year and belongs in the report.

**The Saturday will not mean anything.** 4,035 records expanding to 14,022,328 trips
is one record standing for about 3,475 of them. Over 30 units and four modes that is
roughly 34 records a cell before any zone apportionment. D38 already says a
combination like that should be marked rather than published quietly, and 2011 is the
year that makes it real. **It should probably be measured and marked, or excluded —
not silently averaged in.** That is a decision for the advisor, and it interacts with
the day-type question 2015 reopened.

**The published matrices do not cover walking.** `Matrices Finales/` holds eight Emme
text matrices — `Bicicleta`, `Moto`, `TP`, `VP`, each peak and off-peak — and
`120927_Matrices_Proposito.xlsx` holds them by purpose. **There is no pedestrian
matrix anywhere in the delivery.** So the check that made 2015 the best-verified year
covers three of 2011's four modes and not the one the study cares most about. The
cross-year comparison of §6b is therefore the main external check on 2011's walking,
which makes reading it carefully more important and not less — and 2011's walking is
already the odd one in the series, at 8,136,778 trips a day against 2015's 5,576,942.
**That gap is 46 % and it is the largest unexplained difference anywhere in the
series. Expect to spend real time on it.**

---

## 4. Where a control total will come from

**One exists before the 2011 documents are opened.** `F_EXP` over the weekday trips
sums to **17,611,061.3**, and Tomo I of the *2015* delivery quotes 17'611.061 as the
2011 weekday projection. A neighbouring survey publishing the previous one's total is
a real external control and it costs nothing to use.

It is not enough on its own: it is a single city figure, and 2015 showed how much a
per-pair or per-mode control catches that a total does not. What to read, in this
order:

| Question | Where it should be |
|---|---|
| Which column is the expansion factor, and what it expands to | `Manual base de datos Encuesta de Hogares.pdf`, and `120927_Capacitación Bases de Datos_EODH.pdf` |
| The household and person universes, to settle `weight_expands_to` | the same two, and `120927_InformeFinal_Tomo I.pdf` |
| Which day the reported trips belong to | `110719_Formulario_EM_Bogota 26 de julio.pdf`, the questionnaire — this is what settled 2019 and 2015 |
| Published totals per mode | `120927_InformeFinal_Tomo I.pdf` and `TomoII` |
| How the expansion factor was built | `Ejemplos Capacitación/03_Ejemplo Capacitación Matrices_FE_Hogares.xlsx`, a worked example of exactly that |
| What the fieldwork did | `120927_InformeFinal_ManualEncuestasDomiciliarias.pdf` |

**And a per-zone control is available even though no per-zone table is published.**
The household `ZAT` has no nulls at all across 15,592 households, so the reading can
be grouped by the household's own zone the way 2019's was grouped by its UTAM. That
is a check against the survey's own structure rather than against a published figure,
so it is weaker — but it exercises the weight, the mode labels and the household key
at once, which no city total does.

---

## 5. What must come out unchanged

The same list as every year, and it is why the shape is worth defending:

- **2015, 2019 and 2023 identical to the last decimal**, over all 720 of their rows
  and every column, verified against the run before the change rather than merely
  re-checked. This matters more for 2011 than for any year before it, because
  recommendation (a) touches the dataclass all three depend on.
- One row per unit, year, actor type and day type, in the columns
  `config.survey_exposure_columns()` declares, in that order.
- Two figures per combination, under `figures/exposure/2011/<mode>/<kind>/`.
- The balance closing per actor type and per day type, not in aggregate.
- `compare_years` read on `TRIPS_PER_DAY_OF_TYPE` and never on
  `TRIPS_PER_AVERAGE_DAY`.

And when it is done, the same documents are updated in the same commit: this one
retired or rewritten, the inventory, `design-decisions.md`, `verification-report.md`
§15, `data-layout.md` — plus `requirements.txt`, which gains `pyodbc`, and
`deliverables/plan.md`, which is in Spanish and is not in version control.
