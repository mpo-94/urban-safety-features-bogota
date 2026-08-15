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
figure reported here. The matrix is then modelled together with a set of urban
predictors (road infrastructure, modal share, socioeconomic conditions) using
generalized linear models on panel data.

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
python -m src.run_pipeline parties    # stop after party resolution
python -m src.run_pipeline loading    # sources only: read, locate, verify
python -m src.run_pipeline --help     # the routes available, with a line each
```

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
