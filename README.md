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

The matrix is built at the level of the **UPL** (*Unidad de Planeamiento Local*,
33 units), with **year** as the time dimension, covering **2007–2024**. It is
then modelled together with a set of urban predictors (road infrastructure,
modal share, socioeconomic conditions) using generalized linear models on panel
data.

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

## Status

Work in progress.
