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
be hurt, which puts the two on opposite sides of a rate model. It reads the
origin-destination desire lines of the mobility survey, where every line carries
the survey's own expansion of the trip it stands for, and gives each unit a line
crosses the share of that line's trips matching the share of its length inside
the unit. A line crosses three units in the median, so the rule is not optional.

Every quantity comes out in its own column with its unit and its period in the
name — trips per week and trips per day are different numbers from different
columns of the source, and the layer's own length column is in degrees. Three
alternative allocations are exported beside the variable, and none of them is a
model variable: they are there so the sensitivity of a result to the rule can be
shown rather than asserted. The route checks, every run, that what was allocated
to the units plus what fell outside them equals what the file holds.

The exposure columns carry the mode in their names —
`BICYCLE_TRIPS_PER_WEEK_BY_LENGTH_SHARE` — so a second layer adds columns instead
of colliding with the first. Adding one is a declaration and a run;
`docs/adding-an-exposure-layer.md` is the procedure, starting with what to verify
in the file before declaring anything.

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
