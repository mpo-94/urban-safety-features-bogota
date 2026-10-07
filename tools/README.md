# Inspection tools

Scripts that measure the delivered data or the pipeline's own output, kept
separate from `src/` because nothing in the pipeline imports them and separate
from the thesis because a reader of this repository has to be able to run them.

**That last part is why this folder exists.** These checks used to live under
`deliverables/`, which is not published, and the design decisions they are the
evidence for point at them by name. A public document citing a script nobody can
reach is a citation that cannot be followed, which is the same defect as a figure
quoted without its run.

They read and never write. None of them is part of a route, none is imported by
anything, and deleting any of them would change no output — what would be lost is
the ability to reproduce a number a document quotes.

## Running them

From the project root, with the project's own environment:

```bash
.venv/Scripts/python.exe tools/flujos_vs_stock.py
.venv/Scripts/python.exe tools/respuesta.py [run]
.venv/Scripts/python.exe tools/vigencia.py
.venv/Scripts/python.exe tools/redigitalizacion_ciclorruta.py
```

Each prints a table and exits. `respuesta.py` takes the name of a run directory
and defaults to the one named in its own source, so a figure it produced can be
recomputed against the run it came from rather than against the newest one.

## What each one answers

| Script | Question | Evidence for |
|---|---|---|
| `flujos_vs_stock.py` | Is each annual file of a layer the state of the network that year, or what was built in it? | **D46** |
| `respuesta.py` | Does the response carry enough signal, pair by pair and year by year, to regress on the units that enter? | `regression-inventory.md` §2 |
| `vigencia.py` | What date is each static layer actually from, read off its own columns rather than its file name? | `regression-inventory.md` §4 |
| `redigitalizacion_ciclorruta.py` | How much of the cycleway's year-to-year change is network, and how much is the same segments re-drawn? | `verification-report.md` §23 |
| `comparar_candidatas.py` | Does the ranking of the urban variables survive when the offset leftovers do not compete against them? | `verification-report.md` §25, D50 |

`flujos_vs_stock.py` measures the three line layers that carry an annual series
together, with the cycleway among them **as a control**. That is deliberate: the
totals of a flow only say how anomalous they are when something that really is a
stock is printed beside them, and the first run of that check found zero files in
two folders and would have been read as zero kilometres without it. Those two
folder names carry an ñ that this filesystem stores decomposed, so the paths are
resolved through `config.resolve_source_path` and never through a plain glob.

`redigitalizacion_ciclorruta.py` exists because a panel model reads the change
between two annual snapshots as if it were construction, and in this series it
often is not: seven of the twelve steps carry re-measurement mixed in and one
cannot be read at all. It also found the defect that 2012 ships more than half
its geometry without an identifier — caught because its first version dropped
those rows silently and disagreed with the measured density.

`comparar_candidatas.py` reads two runs rather than a source layer, which is why
it is worth saying what it is for: the regressions let a quantity the offset did
not take go on competing, and a fifth of everything the search selects is one of
those. The comparison is the only way to tell whether the urban ranking is a
finding or an artefact of that company. It finds the two runs by the candidate
set each table declares, not by the folder name, and it compares AIC only inside
a cell — same response, same offset, same family, same units — because
that is the only place where two models from different candidate sets are
comparable at all.

`seleccion_por_aic.py` answers a question the fit figures raised once they
started printing an AIC in both families: least squares reports a negative AIC,
between -1,048 and -291, and a selection driven by minimising it deserves a check
rather than an assurance. It refits every declared subset of 104 cells in two
families, some 55,000 models, and asks two things that are not the same question.
Whether the sign breaks the ordering, which it does not. And whether the winner is
good on the scale the figure draws, which is where it found something: least
squares optimises the rate, because that is what it fits, and ranked on counts its
winner falls below the median model of its own cell in 14 of the 104.

It covers the negative binomial because taking the count family on faith would
leave the more important of the two unchecked. That family is much better and is
not perfect — median percentile 97.0 against 88.3 — and the reason it cannot be
perfect is worth knowing: the AIC maximises a penalised likelihood and R-squared
measures squared error, so in 80 of its 104 cells some model with a worse AIC
fits the drawn counts better, almost always by very little.

`exclusion_de_una_unidad.py` is the pre-flight for D56, written before the
pipeline was touched. Taking a unit out of the regressions is one line of filter
and three ways to break the run, and this finds them without a run: the
contiguity weights are built from the unit layer rather than from the regression
table, so filtering one and not the other either raises on a shape mismatch or,
worse, computes Moran against the wrong neighbours; `contiguity_weights` aborts
if any unit is left with no neighbour; and the eligibility threshold is a share,
so it survives the smaller denominator but moves, and a pair crossing it would
stop being modelled with nobody having decided that. For Torca all three are
clear — it borders only Toberin and Britalia, the minimum neighbour count stays
at one, and the worst pair improves from 0.367 to 0.345 against a maximum of
0.50. The unit is a constant at the top, so a second proposed exclusion is a
one-line change.

`efecto_de_la_exclusion.py` is the post-flight to the one above, and it
answers what moved rather than what would break, so it needs two finished runs
and runs after rather than before. It found the figure the committee will ask
for: removing one unit changed the selected model in **30.1 %** of the 1,868
cells — 40.9 % in least squares, 13.8 % in Poisson — which is what a best-subset
search over 220 or 286 candidates does on twenty-nine observations, and not a
property of the unit removed. The second half is the reassuring one and is the
reason the script exists at all: what the study actually reports, the selection
frequency within a specification, has a median Spearman of +0.943 across the
eighteen and moves no variable more than one place of twelve. D53's argument that
a count is read and not a winner stops being an argument there and becomes a
measurement.

## What is not here

Tools that work on the thesis document rather than on the data stay in
`deliverables/diseno/`, because that is what they operate on: the design and
colour variants, the vertical-spacing detector, the acronym and foreign-word
checkers, and the script that maps each predictor to the sources in the
bibliography. They are of no use without the document, and the document is not
published.
