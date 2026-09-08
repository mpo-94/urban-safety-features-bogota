# Urban safety features in Bogotá

Undergraduate thesis project (*Trabajo de Grado*) for the degree of Physics
Engineering at Universidad EAFIT, Medellín, Colombia.

**Author:** Mateo Pineda Osorio
**Advisor:** Luis Eduardo Olmos Sánchez

## What this is

Road traffic casualties in Bogotá fall disproportionately on pedestrians,
cyclists and motorcyclists. This project asks which features of the urban
environment are associated with that burden, and whether the associations
reported for European cities hold at the intra-urban scale in a Latin American
city.

The central artifact is an **inter-mode casualty matrix**: for every pair of road
user types, how many casualties one type suffers in collisions involving the
other. Unlike the conventional count by mode of the victim, this makes explicit
which mode imposes the risk and which one receives it.

The matrix is built at the level of the **UPL** (*Unidad de Planeamiento Local*),
with **year** as the time dimension, covering **2007–2024**. The study universe
is the 30 UPL of the layer in use, which is the denominator of every coverage
figure reported here. The matrix is to be modelled against a set of urban
predictors — all of them built environment, measured from the delivered
cartography — with generalized linear models on panel data.

**The models do not exist yet.** What is built is everything they read: the
matrix in an observed and a corrected form, the static predictors, and a measure
of travel exposure. The sections below say which of those each route produces.

## Origin

The research question and an initial implementation came from the advisor. That
implementation was audited in detail before this work began, and several
methodological decisions were revised as a result: how casualties are assigned
to each party in a collision, what the unit of the matrix counts, and how
vehicle types are classified. This repository is the reimplementation that
follows from that review.

## Repository layout

```
src/     Pipeline implementation
docs/    Documentation
```

Raw crash and geospatial data are not distributed here. They come from public
sources published by the Secretaría Distrital de Movilidad de Bogotá and the
Distrital spatial data infrastructure.

Because `data/` is not distributed, **`docs/data-layout.md` is the record of what
it must contain and where** — one root per role the data plays, what each layer
is read by, and which delivered layers are deliberately read by nothing. It is
updated in the same commit as any move, since nothing else can catch a document
and a folder drifting apart.

## Installation

Requires Python 3.12; part of the geospatial stack has no wheels for later
versions. Create a virtual environment and install the pinned dependencies:

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running the pipeline

`src/run_pipeline.py` is the only entry point. Each invocation is a **route**: a
named path through the stages, which gets its own timestamped directory under
`results/` with the tables, the figures and the full log of that run.

```bash
python -m src.run_pipeline            # full pipeline; announces the route it picked
python -m src.run_pipeline matrix     # the same, named explicitly
python -m src.run_pipeline corrected  # the observed and corrected matrices, side by side
python -m src.run_pipeline parties    # stop after party resolution
python -m src.run_pipeline loading    # sources only: read, locate, verify
python -m src.run_pipeline map        # the reference map of the thirty units
python -m src.run_pipeline predictors # the static urban predictors and their figures
python -m src.run_pipeline population # the denominator: one number per unit and per year
python -m src.run_pipeline exposure   # travel exposure per unit, and its choropleth
python -m src.run_pipeline rho        # the ρ(t) diagnostic, beside the pipeline
python -m src.run_pipeline completeness   # does every month of every year have data?
python -m src.run_pipeline integrate  # rebuild the layers from the updated extract
python -m src.run_pipeline --help     # the routes available, with a line each
```

`predictors` is the other half of the study: the features of a unit that the
casualty rates are to be regressed against. It measures **thirteen static
variables over eleven layers** — five surfaces as a share of the unit, eight
point layers as a density over it — against every unit, and emits the wide table
the figures are drawn from, the long table the dashboard joins, a histogram per
variable, the Pearson correlation matrix and a master table figure of the thirty
units against the variables, shaded column by column because the variables are
not on a common scale.

Measuring a variable and putting it in a model are two decisions and the route
keeps them apart: everything declared is measured on every run, and **eight of
the thirteen enter the models.** The figures therefore come out in two sets, in
separate folders and with the set in every file name — the complete one, which
is the backing evidence because it holds the variables the models exclude, and
the model one, which is what the documents use. The correlation of the model set
is also emitted as a LaTeX table, so no figure in a deliverable is transcribed by
hand.

It also exports a data dictionary: one row per variable with its source layer as
the data names it, its file, its geometry, what it measures, in what units and
how it is computed. The measurement runs on that declaration — it locates every
layer and dispatches every computation through it — so a wrong entry stops the
run instead of misinforming a reader.

**The four layers that carry an annual series are not measured yet.** All four
are line layers, and the measurement they will use is written and registered;
what they still need is the year. The tables already carry the year column they
will fill.

`exposure` is a route of its own because exposure is not a predictor. A predictor
says what a place is built like; exposure says how much travel there is in it to
be hurt, which puts the two on opposite sides of a rate model.

It builds the origin-destination desire lines from the household mobility survey
rather than receiving them drawn. A declared survey is read, its own mode labels
are mapped to the four road user types the casualty matrix uses, its trips are
grouped by actor type, kind of day and pair of zones, and one line is drawn
between the two zone centroids of every pair. Each unit a line crosses gets the
share of that line's trips matching the share of its length inside the unit — a
line crosses several units, so the rule is not optional. A trip that begins and
ends in the same zone has no line at all and is spread over the units covering
that zone by area instead; those are 20% of the travel measured in 2023 and 22%
in 2019, and dropping them would take a third of the walking out of the study.

The table is long: one row per unit, year, actor type and kind of day. It joins
the casualty matrix on unit, year and actor type, and it has to be interpolated
over the years no survey covers, and both are natural in that shape. The mode is
therefore a column value and not part of a column name.

Adding a survey year is one `MobilitySurvey` in `src/config.py`. Two things a
year may also need are rules — for how it says which kind of day a trip was made
on, and for how it states the trip duration — because no two of the four surveys
say either the same way. Each was commissioned by a different city administration
and catalogues its data its own way, so nothing about a year's files can be
inherited from the year before while everything downstream of them has to come
out identical. **2023 and 2019 are built**; adding the second changed no
measurement and left the first's figures identical to the last decimal.
`docs/adding-a-survey-year.md` is the procedure, and §6b of
`docs/mobility-surveys-inventory.md` is the contract it has to satisfy.

A year need not have a kind of day at all. 2019 surveyed one typical working day
and nothing else, which its questionnaire, its glossary, its report and its
published matrices all say, so its Saturday and Sunday rows are **absent** from
the table rather than zero.

Records the geometry contradicts are dropped and counted. A record whose two
zones are further apart than its mode could have covered in the duration it
reports could not have happened however the trip ran, and the line drawn from it
is a line nobody travelled; that is a seventh of the walking in 2023 and a fifth
in 2019, and under 1.2% of every motorised mode in both. Each year declares how
it states its duration and the ceiling speeds are one table in the configuration,
so a year that reports no duration is not silently assumed clean — the run says
it was not checked.

The route checks, every run, that every trip the file weights is either measured
or named as deliberately set aside, and that what was apportioned to the units
plus what fell outside them equals what the file holds — per actor type and per
kind of day, not in aggregate, because an aggregate can close while two modes are
wrong in opposite directions.

Two figures come out per year, actor type and kind of day: a choropleth of the
trips each unit ends up with on a day of that kind, and the desire lines that put
them there. The second exists because this route draws its own input, so there is
no other way to see what was built — and it is what turned up the impossible
records above, by showing walking trips that crossed the whole city.

Two trip columns come out, not one, and the difference matters where a year has
more than one kind of day. 2023's expansion factor represents the population once
over all seven reference days, so summing it within one kind of day gives that
day's share of an average day and not the trips of one such day.
`TRIPS_PER_AVERAGE_DAY` is the first, `TRIPS_PER_DAY_OF_TYPE` the second, and
`DAY_TYPE_UNIVERSE_SHARE` converts between them in the table itself. 2019's
factor already expands to its one day, so for that year the two columns coincide
and the share is one — which is why each year declares this and none inherits it. Three alternative allocations are exported
beside the variable and none is a model variable: they exist so the sensitivity
of a result to the allocation rule can be shown rather than asserted.

The delivered desire-lines layer the pipeline read before the surveys arrived is
**retired**. It turned out to be a 9.6% sample of the 2019 survey, and once that
year was built there was no reason to keep measuring a tenth of something the
pipeline reads in full. It was checked against the survey first, which is the
strongest confirmation this stage has: all 160 of its origin-destination pairs
appear among the pairs built from the survey, with none attributed more trips
than the survey holds — two independent readings of one source agreeing exactly.
The route measures a delivered layer only when one is declared, and none is.
`docs/adding-an-exposure-layer.md` is the procedure for a layer of that kind,
starting with what to verify in the file before declaring anything.

`population` builds the denominator. Casualty counts become rates only when
divided by the people who were there to be hurt, and that number is a panel:
**30 units by 18 years, 540 cells, and a missing cell stops the run.** It is
keyed on the year and not on the unit alone because a denominator that does not
move within a unit is collinear with that unit's fixed effect and drops out of
the model — and because the movement is large, from −28.5 % to +557.9 % between
2007 and 2024 depending on the unit.

The route also measures what the study leaves out. The source covers the 33 UPL
of Decreto 555 de 2021 and the delivered cartography carries 30; the three it
adds are the rural units, and they are **0.33 % of the city in 2024**. That
figure is reported on every run and exported year by year, because it is the
measured answer to why the universe is 30 units rather than 33.

Which of the file's years are measured and which are projected or backcast is not
in the file, and the run says so rather than guessing.

`corrected` produces **two datasets in one run**: the observed matrix and one
corrected for the change in recording practice that ρ revealed. The correction
never replaces the observed data — both sets get the same tables, matrices and
figures, and what separates them is a suffix on every file name and a column on
every row. Producing them together from one reading of the sources is what makes
them comparable cell by cell, which is what the route then checks.

`map` draws the reference map of the thirty units, from the same layer every
other stage reads rather than from a second copy of the cartography. Four colours
suffice for no two neighbours to share one, and identity is carried by the number
inside each unit. It writes two files that differ only by the scale bar.

`rho` is not a stage of the pipeline: it measures, for each pair of road user
types, the share of two-party crashes in which both parties suffered casualties,
which is a diagnostic of how casualties were recorded over the years. It reads
the party universe before the parties without casualties are dropped, so it
computes its own run from the sources and never reuses another one's output.

`completeness` counts the records of every layer, year and month and reports the
months that are empty or far below the rest of their year. It exists because a
source can be missing a third of a year without any arithmetic check noticing.

`integrate` is a build step rather than an analysis. A later extract of 2024
arrived covering the whole year, where the original injury layer stops in
mid-September; the route rebuilds both casualty layers with that year replaced,
writes them to `data/integrated/`, and leaves the original files untouched. Which
of the two every other route reads is decided by `USE_UPDATED_2024` in
`src/config.py`, so reverting the integration is one line.

Every stage writes its own output to `intermediate/` when dumps are on. They are
off by default because they are large; turn them on for a single run without
editing anything:

```bash
python -m src.run_pipeline parties --dump-intermediates
python -m src.run_pipeline matrix --no-dump-intermediates
```

The territorial scale, the study period and every other setting live in
`src/config.py`. Data are read from `data/` and nothing is ever written outside
the run directory.

## Status

Work in progress.
