# Adding an exposure layer

Exposure is how much travel of a given mode passes through a unit. The pipeline
measures one such layer today — bicycle desire lines from the mobility survey —
and the module is written so that a second one is a declaration plus a run,
never a new module. This is the procedure for adding it.

It applies to any layer built the same way: a geometry per surveyed trip, or per
origin-destination pair, carrying a survey expansion factor. That is a common
shape and the trap in it is always the same one, so the order below starts with
inspection and only reaches code once the file has been understood.

Read [D35](design-decisions.md) for why the allocation rule is what it is, and
[D21](design-decisions.md) for what the first attempt got wrong.

---

## 1. Inspect before declaring anything

**Never take a column's name as evidence of what it holds.** The desire lines
arrived with the kilometre-trips of the legacy pipeline written into a column
called `len_km`, and 674,158 of them were reported for a layer 1,219 km long. A
name is an assertion with nothing behind it; a sum compared against a figure from
outside the file is evidence.

Work through these, and write the answers down before touching the configuration.

**What the file is.** Format, geometry type, record count, every column with its
type, its nulls, its unique values and an example. The coordinate reference
system, and whether the file declares it or has to be told.

**Which column is the expansion factor, resolved by arithmetic and not by name.**
Compute three sums and compare each against something known from outside:

- the candidate factor on its own, which should land on a plausible number of
  trips for the city;
- the geometric length on its own, which should land near whatever the layer is
  documented to measure;
- the length times the factor, which is a third quantity again.

Only one assignment of names to columns makes all three plausible at once.

**Whether the file already carries the product.** The desire lines ship both
`f_exp` and `ResultadoExp`, and the second is the first already multiplied out.
A layer that has done the expansion for you will be expanded twice if you assume
otherwise, and the result will look entirely reasonable.

**What period the factor expands.** A day, a week, a year. On the desire lines
this was only settled by noticing that the day-of-week flags sum to the column
named `ViajesSemana`, which therefore counts days and not trips. Get this wrong
and every number in the thesis is off by a factor of five.

**What the factor is attached to.** One record, one origin-destination pair, one
zone? If it is attached to a pair and several records share that pair, summing
over records multiplies the pair's weight by the number of records.

**Whether the geometry means anything.** Measure sinuosity: the length of each
feature over the straight distance between its endpoints. If it is 1.000, the
geometry is a chord that nobody travelled and an allocation by share of length is
spreading a trip along a line the survey never observed. That does not disqualify
the layer, but it is a limitation that has to travel with every number drawn from
it, and it is the reason the alternative allocations exist.

**What the mode column says, on every row.** Not on the first row.

**What year the layer is.** If nothing in the file says, that is an open question
for the advisor and not something to infer from the file's modification date.

**Whether the layer is complete or a selection.** Look for an identifier that
betrays a parent table — the desire lines carry `ORIG_FID` running to 7212 over
181 rows, which is how it became clear the delivered file is a subset. A selected
subset may not measure what the whole would.

---

## 2. Declare it

Everything the measurement needs is one `SurveyLineLayer` in `src/config.py`, and
one entry appended to `EXPOSURE_LAYERS`. Nothing else changes: the columns, the
dictionary, the figures and the checks all follow from the declaration.

```python
WALKING_DESIRE_LINES = SurveyLineLayer(
    name="WALKING_TRIPS",
    label="Walking trips",
    label_es="Viajes a pie",
    source_layer="...",           # the folder, exactly as the data names it
    source_file="....shp",
    mode="WALKING",               # leads every column name this layer produces
    mode_column="modo_princ",     # spelled as the .dbf spells it, truncation included
    mode_value="A pie",
    weekly_weight_column="ResultadoE",
    daily_weight_column="f_exp",
    origin_x_column="Xo", origin_y_column="Yo",
    destination_x_column="Xd", destination_y_column="Yd",
    measures="...",
    time_coverage=SNAPSHOT_COVERAGE,
)

EXPOSURE_LAYERS = (BICYCLE_DESIRE_LINES, WALKING_DESIRE_LINES)
```

Three things about the declaration are load-bearing.

**Column names are spelled the way the delivered `.dbf` spells them,** truncation
included. The shapefile format cuts a field name to ten characters, so
`ResultadoExp` arrives as `ResultadoE` and `modo_principal` as `modo_princ`. The
untruncated names survive in the ESRI metadata that ships beside the file, and
the run raises if a declared column is not there.

**Accented paths are stored decomposed.** The delivered folders write `í` as an
`i` followed by a combining acute, and a path written normally in Python is a
different byte string that does not open. `config.resolve_source_path` normalises
that difference and only that one; nothing needs to be done except be unsurprised
when a path that looks right does not exist.

**The mode is not decoration.** It leads every column this layer produces, which
is what stops two exposure layers from colliding. `TRIPS_PER_WEEK` was a correct
name for exactly as long as there was one layer.

---

## 3. How the columns come out

One row per unit, and a block of columns per layer. The table is wide over modes
rather than long over them, because the panel it joins is keyed on unit and year:
an exposure table with a row per unit and mode would need a filter before every
join.

For a layer declaring `mode="BICYCLE"`:

| Column | Unit | What it is |
|---|---|---|
| `BICYCLE_TRIPS_PER_WEEK_BY_LENGTH_SHARE` | trips/week | **the variable** |
| `BICYCLE_TRIPS_PER_DAY_BY_LENGTH_SHARE` | trips/day | the same allocation of the daily factor |
| `BICYCLE_TRIPS_PER_WEEK_AT_ORIGIN` | trips/week | alternative allocation |
| `BICYCLE_TRIPS_PER_WEEK_AT_DESTINATION` | trips/week | alternative allocation |
| `BICYCLE_LINE_KM_INSIDE` | km | alternative allocation |
| `BICYCLE_LINES_TOUCHING` | count | how many lines reach the unit |
| `BICYCLE_TRIPS_PER_WEEK_PER_KM2` | trips/week/km² | the variable over the area |
| `BICYCLE_TRIPS_PER_WEEK_PER_INHABITANT` | trips/week/person | the variable over the population |

`POPULATION` and `VALUE_STATUS` belong to the unit and take no mode prefix: a
unit has one population whichever mode is measured against it.

The naming rule, in one line: **mode, then what is counted, then over what
period.** A column that does not say whether it counts a day or a week is the
same defect as a column called `len_km` holding kilometre-trips, and a column
that does not say which mode is a collision waiting for the next layer.

The alternative allocations are **never model variables.** They exist so the
sensitivity of a result to the allocation rule can be shown rather than asserted,
and the exported dictionary flags them with `IS_ALTERNATIVE_ALLOCATION`.

---

## 4. What the run checks

Every check below runs per layer, so a second layer adds its own rows to the
table of results rather than being averaged into the first one's.

**The balance, which is the one that matters.** What was allocated to the units
plus what fell outside them equals what the file holds — separately for trips per
week, trips per day and kilometres. The shares of a line that leaves the study
area add to less than one, so the check is not that the allocated total equals
the layer total; the part falling outside is measured, not absorbed.

**No line is allocated more than once over.** The largest share of any line
covered by the units must not exceed one by more than a millionth. Above that
means two unit polygons overlap and a trip is being given to both. The tolerance
is deliberately not machine epsilon: summing ten fragment lengths and dividing by
the whole lands a few parts per billion over without anything being wrong.

**Weekly over daily lies between one and seven.** The two columns are the same
allocation of two different expansions, so their ratio is the average number of
days a week a trip is made. Anything outside that range means the two weight
columns are not what they were declared to be.

**The declared endpoints are the ends of the geometry.** The origin and
destination allocations use coordinate attributes of the record; if those ever
disagreed with the geometry, those columns would be measuring a different set of
lines from the one the variable measures.

**Every declared quantity is in the table under its mode-prefixed name,** and the
table carries exactly the declared columns in the declared order. This is the
check that catches a collision between two layers, which would otherwise be
silent: two layers writing the same column name would leave one in the file and
no trace of the other.

**A unit no line reaches carries a zero and the status `MEASURED`.** Torca
receives no bicycle desire line at all, and that is an observation about Torca,
not a gap. Only a unit with no usable area is `NOT_MEASURED`, with nulls.

**The per-km² column is the variable over the area of its own unit.**

If a new layer needs a check that none of these covers — a weight that should sum
to a published control total, say — add it in `exposure.verify`, inside the
per-layer loop, so every future layer gets it too.

---

## 5. The figure

Each layer gets a choropleth of its variable, in two files that differ only by
the scale bar, drawn by `maps.render_choropleth`. Nothing needs to be written for
it: the caption comes from `label_es`, so the layer must declare its Spanish name.

A measured zero keeps the bottom of the colour ramp and gains a hatch of its own,
because at the bottom of a ramp running to sixty thousand an exact zero is the
same pale colour as several units that are not zero. A unit that could not be
measured leaves the ramp for a grey with a coarser, diagonal hatch. Both legend
entries are drawn only when a unit is actually in them.

---

## 6. Finally

Run `python -m src.run_pipeline exposure` and read the log rather than the exit
code: the checks print as a table, and the report prints the layer totals, the
most exposed units, the units at zero, and the rank correlation between the
allocation rules.

Then write the decision down. What the layer turned out to be, which allocation
was chosen and what was rejected, what the limitations are, and what is still
open about the source. D35 is the model to follow.
