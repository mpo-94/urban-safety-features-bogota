# Mapping the casualties, and giving every year a master table

**Nothing here is built.** This is the specification for the next session, written
in the session that measured what it rests on, so that the work can start from
facts rather than from assumptions about the sources.

Three things are being built and only the third is large:

1. **A defect in the matrix heatmaps**, where the colour of the printed number is
   chosen the wrong way round.
2. **A master table per count and year**, as an exported table and as a figure.
3. **A map per count and year** that places every casualty where it happened.

The unit of the study does not change, nothing about the matrix's own numbers
changes, and no decision already taken is reopened.

---

## 0. Where to start

1. `CLAUDE.md`.
2. **This document**, all of it. Section 2 is what was measured about the sources
   and it is the part that stops the work being built on a wrong assumption.
3. **D1 to D11** in [`design-decisions.md`](design-decisions.md) — what the matrix
   counts and what a party is.
4. **D28 to D31** for the ρ correction, because the corrected set gets two of the
   three things above and not the third.
5. Section 15 of [`verification-report.md`](verification-report.md) for the
   exposure figures' conventions, which these figures should not contradict.

**The reference run for the matrix is `run_20260901_092654`**, which holds both
casualty datasets.

---

## 1. The defect, which is three lines

`src/matrix.py`, in `_draw_heatmap`:

```python
colour = "white" if norm(value) > 0.55 else "black"
```

The colormap is `config.HEATMAP_COLORMAP`, which is **viridis**: low values are
dark purple and high values are bright yellow. So the cell with the largest count
comes out pale and gets white text, and a cell holding 1 comes out dark and gets
black text. Both ends are wrong at once, which is why it reads as a scale problem
and is not one.

**The fix is to take the colour the cell was actually painted and decide from its
luminance**, which works for any colormap and cannot be inverted by changing one:

```python
red, green, blue, _ = image.cmap(image.norm(value))
luminance = 0.299 * red + 0.587 * green + 0.114 * blue
colour = "#ffffff" if luminance < 0.55 else "#1a1a1a"
```

`src/interpolation_figures.py` does exactly this in `_draw_heatmap`, and the two
should end up sharing one helper rather than carrying two copies of the rule.

Applies to every matrix figure of both datasets, and to the master table figure
below.

---

## 2. What the sources actually hold, measured on 2026-09-11

**Do not take any of this from a column name.** Each line below was measured on
`MUERTO.shp` and `LESIONADO.shp` as this repository reads them, through
`config.FATALITIES_PATH` and `config.INJURIES_PATH`.

### The month is not in the column called `MES_OCURRE`

`MES_OCURRE` is **null in every row of both sources** — 8,592 of 8,592 and 268,921
of 268,921. It is not sparse; it is empty.

`FECHA_OCUR` parses to a date in **100 %** of the rows of both sources, and its
year agrees with `ANO_OCURRE` in **100 %** of them. Every month from 1 to 12 is
present in every year checked, including 2024, which arrives from the updated
extract rather than from the shapefile, and the distribution is what a year looks
like: January lowest at 7.2 %, the rest between 7.8 % and 8.9 %.

**So the month comes from `FECHA_OCUR`**, which is already declared as
`config.DATE_SOURCE_COL` and already parsed by `src/completeness.py`. This is the
same trap this project has hit before with `len_km` and with `p34_aplicacion_durante_viaje`, and it is worth one sentence in the run.

### A crash has exactly one coordinate and exactly one month

Of the **182,426** distinct crashes in the injuries source, **zero** carry more
than one coordinate and **zero** carry more than one month. So both can be
attached to a crash with a `first` aggregation, exactly as the territorial unit
already is, and the check that says so is cheap.

The coordinate is **of the crash and not of the person**: 268,921 injury rows sit
on 129,176 distinct points, because a crash with four casualties is four rows at
one point. That is a property and not a defect, and it decides how the map is
drawn — see section 5.

### How much there is to draw

| | Rows | Per year |
|---|---:|---|
| `MUERTO` | 8,592 | 317 (2008) to 599 (2024), median **488** |
| `LESIONADO` | 268,921 | 8,766 (2009) to 22,961 (2023), median **13,453** |

**Two orders of magnitude between the two**, which is the single most important
fact for the map: a density surface over thirteen thousand points is a map, and
the same surface over four hundred is a picture of sampling noise.

### The coordinate reference system

Both sources are **EPSG:4686** (MAGNA-SIRGAS, geographic) and the pipeline
harmonises to it. **Any density has to be computed in metres**, so the points must
be projected before anything is binned or smoothed; in degrees a "300 m radius" is
not the same distance north-south as east-west at this latitude. The bounding box
of the injury points is about 24 km east-west by 58 km north-south, but that
includes the rural south — the thirty units are roughly 15 by 30 km.

---

## 3. The seam: `parties.crash_attributes`

`src/parties.py` already has the function this work needs:

```python
def crash_attributes(casualties: pd.DataFrame) -> pd.DataFrame:
    """Year, crash type and territorial unit, once per crash. ...
    Shared by everything that needs to place a crash in space and time..."""
```

**The month and the point belong there and nowhere else.** Adding them gives both
new artefacts what they need, for both datasets, through the path that already
guarantees the matrix and ρ put the same crash in the same cell. The alternative —
carrying geometry through party resolution — would change a function that has
nothing to do with either.

`config.CRASH_ID_COL` is `FORMULARIO`, and the party table already carries it, so
nothing upstream has to change shape.

**One thing to be careful about.** `crash_attributes` resolves the unit by sorting
nulls last and taking the first non-null, because a crash's victims were verified
to agree except where one could not be located. The month and the point were
measured to agree with no exception at all, so they take `first` without the sort
— and the check in section 7 is what keeps that true as the sources are updated.

---

## 4. The master tables

Two artefacts from one new exported table.

### The table that is exported

One row per **unit, year, month and dataset**, with the three counts as columns:

| Column | |
|---|---|
| `DATASET` | `OBSERVED` or `RHO_CORRECTED`, as every other table of the study spells it |
| `SCALE`, `AREA_CODE`, `AREA_NAME` | the identity the other tables share |
| `YEAR`, `MONTH` | `MONTH` is 1 to 12, from `FECHA_OCUR` |
| `AFFECTED_PARTIES`, `PERSONS_INJURED`, `PERSONS_KILLED` | the three counts `config.MATRIX_COUNTS` declares |

**It does not carry the pair.** The party type and the counterpart are what the
matrix is for; this table answers "how many events of each kind happened here and
when", which is a different question and a much smaller table: 30 units × 18 years
× 12 months = **6,480 rows** for the observed set and 6,120 for the corrected one,
which starts in 2008 (D30).

The grid is complete: a unit-month with no casualty is a **zero and not an absent
row** (D10).

It goes in `data/` with the other tables, because it is meant to be read by the
final report's LaTeX as well as by the figure below, and because `data/` is what
other things read.

### The figure

One per count, per year, per dataset, in the style of the predictors' master table
(`_draw_master_table` in `src/predictors.py`): every cell printed **and** shaded, so
the number is exact and the colour is comparable.

**Rows are the thirty units and columns are the twelve months**, plus a total row
and a total column, and the grand total in the corner. Rows are the units because
thirty rows by twelve columns is the shape that reads on a page and because it is
the shape the predictors' table already has, so the two look like they belong to
one study. For `all_years` the columns are the eighteen years instead of the twelve
months, and the totals mean the same thing.

**The shading covers the body and not the totals.** A total is an order of
magnitude above the cells it sums, so putting it on the same ramp would leave the
body flat; the totals are printed on a neutral background and say so in the note
under the title. Inside the body one ramp covers the whole table, because unlike
the predictors' columns every cell here is the same quantity in the same unit.

**The scale is shared across the years of one count**, the way the matrix figures
already share theirs, so that two years can be compared by looking at them. The
note under the title says what the ramp spans.

---

## 5. The map

**One map per count, per year, plus `all_years`, for the observed dataset only.**

### What it shows

Every casualty of that count, placed at the coordinate of its crash. Not a
choropleth: the counting by unit is what the master table beside it does, and a
map that repeated it would say the same thing twice.

Because the coordinate is of the crash and the count is of parties or persons,
**the density is weighted by the count the folder is about**. A crash that injured
four people contributes four to `injured/` and one to `parties/` at the same point,
which is what makes the three maps of one year different from one another rather
than three drawings of the same dots.

### How to draw it, and what to decide by looking

Two layers, always both:

- a **density surface** computed in metres and clipped to the thirty units;
- the **points themselves** over it, at low alpha.

That combination degrades in the right direction. With thirteen thousand injured
in a year the surface carries the figure; with 488 killed the points do, and the
surface is nearly flat — which is the honest picture, because a smooth surface over
488 points invents structure that is not there.

**What is not decided and should be decided by drawing it once**, on one year and
one count, before the other hundred are drawn:

- **Hexbin or kernel density.** Hexbin invents nothing and shows the grid; a kernel
  smooths across the Cerros and past the edge of the city, and looks like what
  people expect a heat map to look like. Draw both on the same year and choose.
- **The cell size or the bandwidth**, in metres, declared in `config.py` and printed
  in the figure's note. It has to be one value shared by every year of a count, or
  two years stop being comparable; `all_years` may take a finer one, since it has
  eighteen times the points.
- **The colormap.** The repository uses viridis for the matrices; a density over a
  light basemap usually reads better on `inferno` or `magma`. Whatever is chosen,
  the number of colours has to survive being printed.
- **The figure size and the resolution.** The thirty units are about 15 by 30 km, so
  the current figure sizes are too small to show a corridor. Both may need to go up.

A **logarithmic or quantile ramp** is not optional: crash counts per cell are
extremely skewed, a few intersections carry an enormous share, and a linear ramp
would show one red cell and nothing else.

### What goes on every one of them

Scale bar of 5 km, north arrow and the thirty units drawn over the surface, which
is what `src/maps.py` already puts on the exposure choropleths. Reuse it rather
than drawing a second set of conventions.

And **a note in every caption saying what the map is not**: a map of counts is not
a map of danger. The Caracas, the Boyacá and the Primera de Mayo will light up
because that is where the travel is, not necessarily where a trip is most
dangerous. The study has exposure per unit, mode and year, so a rate map is
possible and is a different figure; these maps carry counts and must say so.

### Why the corrected set gets no map

Decided on 2026-09-11. The correction promotes parties that were already in the
party universe of crashes that already happened, so it **adds no coordinate**: the
corrected map would be the same points with slightly different weights. That is a
real difference and not a null one — `parties` and `injured` do change — but it is
not worth a hundred more figures, and the corrected set keeps the matrices and the
tables, which is where the correction is visible as a number.

---

## 6. The output tree

Under each run directory:

```
data/
  analysis__casualties_by_unit_month.{csv,parquet}     both datasets, one table
figures/
  parties/<year>/            matrix, master table, map
  parties/all_years/         the same three
  injured/<year>/ ...
  killed/<year>/ ...
  parties__rho_corrected/<year>/     matrix and master table, no map
  ...
```

That is 3 counts × 19 folders for the observed set and 3 × 18 for the corrected
one, since the corrected set has no 2007 (D30).

**The matrices move.** They are `figures/<count>/heatmap_<count>__<year>.png` today
and would become `figures/<count>/<year>/`. Nothing outside the repository reads
them, and the file name should keep the year in it even inside a folder named for
that year, because a figure saved out of its folder has to keep saying what it is.

---

## 7. The checks the work is not finished without

- **A crash has one coordinate and one month.** Measured today at zero exceptions
  over 182,426 crashes; it becomes a check so that it stays true.
- **The master table adds up to the matrix.** Summed over months and over pairs,
  the new table's three counts equal the long matrix's, per unit and year, exactly.
  This is the check that matters: two tables of the same events that disagree are
  worse than one.
- **The grid is complete.** 30 units × 12 months × the years of that dataset, with
  zeros where nothing happened.
- **Every casualty on a map is inside the units**, and the number of points drawn
  plus the number set aside equals what the year holds. The matrix already drops
  parties whose crash falls outside every unit and names them in the balance; the
  map has to account for the same ones the same way.
- **The totals of the figure are the totals of the table**, not a second sum
  computed while drawing.
- **Every figure is on disk and none is empty**, as every other route checks.

---

## 8. How this can pass every check and still be wrong

- **A density map of counts read as a map of risk.** The single most likely
  misreading, and the one a committee will make out loud. It is handled by the
  caption and by never quoting one of these maps as evidence about where cycling
  is dangerous.
- **A bandwidth chosen to make the map look good.** It is a parameter with no right
  answer, so it is declared in `config.py`, printed in the figure, and the same for
  every year of a count. Choosing it per year would make two maps look comparable
  while being drawn to different rulers, which is the mistake the matrix figures
  already avoid with their shared colour scale.
- **Weighting by rows instead of by the count.** Drawing one dot per source row
  would weight `parties/` by how many people were hurt, which is the difference
  between the three counts and the reason the study keeps them apart (D2, D3).
- **The month taken from `MES_OCURRE`** because it is called that. It is empty.
- **Two tables of the same events that disagree.** The master table and the matrix
  come from one resolution of parties or they will drift; hence the check above.
- **A map drawn from a different set of crashes than the table beside it.** Both
  must come from the same frame in the same run, and the map must say which run
  drew it, as every other figure of this study does.

---

## 9. What is a decision for a person

- **Hexbin or kernel, the bandwidth, the colormap and the figure size.** To be
  decided by drawing one and looking, not in advance.
- **Whether the master table figure is also emitted as LaTeX**, the way the
  correlation matrix and the casualty matrices already are. The exported table
  makes it possible; whether the final report wants eighteen of them is a question
  about the document and not about the pipeline.
- **Whether a rate map is worth building afterwards** — casualties per inhabitant or
  per trip, by unit — now that the exposure panel exists. It answers the question
  the count map cannot, and it is a different figure with a different caveat.
