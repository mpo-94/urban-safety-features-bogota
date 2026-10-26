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

Most print a table and exit in seconds. Four do not and it is worth knowing before
starting one: `margenes_para_el_ajuste.py` takes about a minute,
`desagregacion_a_zonas.py` and `camino_del_dia_habil.py` two or three,
`piso_de_la_semilla.py` four, and `panel_ajustado.py` eight — they read the five
mobility surveys and fit fifty-two matrices.

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
| `seleccion_por_aic.py` | Does minimising a negative AIC select the model the fit figure then shows as the best one? | **D59** |
| `exclusion_de_una_unidad.py` | What would break if one unit left the regressions, before the pipeline is touched? | **D56** |
| `efecto_de_la_exclusion.py` | What actually moved once it did? | **D56**, `verification-report.md` §27 |
| `ajuste_proporcional.py` | Does the fitting return the matrix it should on cases whose answer is known in advance? | **D54**, **D60**, **D61** |
| `margenes_para_el_ajuste.py` | Do the margins the fitting is given hold every property it takes for granted? | **D60** |
| `desagregacion_a_zonas.py` | Does bringing a year's margins back onto the seeding survey's zones give the survey back when it is handed the survey? | **D60** |
| `camino_del_dia_habil.py` | Does the weekday-only path hold end to end, before the fitting is built on it? | **D60** |
| `piso_de_la_semilla.py` | Does the floor fix the infeasible margins without breaking D60's identity? | **D61** |
| `panel_ajustado.py` | Can the fitted panel be read beside D40's, and does it differ from it? | **D62** |
| `costura_de_la_semilla.py` | Does the fitted panel jump where the seeding survey changes? It found the seam and now certifies it is gone | **D64**, `implementing-ipf.md` |
| `mezcla_de_semillas.py` | Is the blended panel the exposure of a blended matrix, or an average of two exposures? | **D64** |
| `eliminacion_hacia_atras.py` | How many variables does the advisor's backward elimination leave standing, and in which families can it run at all? | `regression-inventory.md` §17 |
| `compra_cada_variable.py` | Do the extra variables backward elimination keeps actually buy anything, in AIC or BIC? | `regression-inventory.md` section 17.3 |
| `estandarizar_arregla.py` | How much does `_standardise` buy, which until now the code asserted without measuring? | `regression-inventory.md` section 17.12 |
| `variables_y_la_literatura.py` | How many variables survive at 5 % and at 10 %, and do the ones the literature names come out with the sign it predicts? | `regression-inventory.md` section 18, **D66** |
| `que_decide_el_panel.py` | Which pieces of the panel specification can the cross-sections settle, with what figure, and which one can they not settle at all? | `regression-inventory.md` section 19 |
| `variacion_para_el_panel.py` | How much variation is left to a within estimator once year effects are in, is a year of horizontal marking a change in the stock, and does painting or cycleway follow casualties? | **D46** (the panel amendment), `regression-inventory.md` section 19 |
| `rampa_de_rho.py` | How steep is the ρ climb year by year, on the scale of a settled year, and does that scale depend on which years and which estimator define it? | **D28** (the reference window), thesis section 4.4 |
| `reparto_entre_unidades.py` | Does the split of a casualty count across units change enough from year to year that one choropleth per year would show something the accumulated one does not, and how much deadlier is one unit than another? | the casualty annexes of the thesis, which show only accumulated choropleths, and the deaths per hundred injured on one of their own |
| `posiciones_de_la_senalizacion.py` | Can the vertical signage stock be rebuilt sign by sign, with positions, by pairing each removal with its sign through the identifier or by distance? It cannot, and this is the measurement that says so | **D47**, and the signage map of the urban-variables annex, which shows the records by class instead |
| `demarcacion_por_unidad.py` | How many kilometres of road marking were painted in each unit each year, for the two layers D46 rejects, measured with the pipeline's own line measurement? | **D46**, and the last section of the urban-variables annex |
| `duplicados_por_anio.py` | Are affected persons repeated in the casualty layers, and more so before 2021, as the approved anteproyecto states? | the question to my advisor about the pre-2021 duplication; no identical row in any year |
| `campos_de_la_fuente.py` | What does every field of the two casualty layers and the vehicle table hold, measured rather than read off its name, and which of them does the pipeline read, read off the code? | the field inventory in the annex on the source and its processing, and the field description of the final report |
| `parque_automotor.py` | What does the RUNT extract say about Bogotá's fleet, and do the four derived files beside it rebuild from it with the parameters their notebook declares? | `docs/vehicle-fleet-source.md`, and the fleet section of the annex on population and the vehicle fleet |

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

`ajuste_proporcional.py` and `margenes_para_el_ajuste.py` are the two halves of
what stands behind the fitting D54 declared and D60 settled, and they are
separate because they are checkable in different ways. The first reads no data at
all: every case is built in the script and every expected answer is written out by
hand or derived a second way, which is the only way to check an algorithm that has
no reference on real matrices. The case that decides is the one D60 names — a
matrix fitted against its own margins comes back as itself, exactly, in one
iteration — and three of the eight are about what the fitting refuses rather than
what it returns.

The second checks what the fitting will be given, which is where a reconstruction
actually goes wrong: iterative proportional fitting accepts almost anything, so
nothing about the result is informative if the margins are not. Three of its eleven
numbers are cited in the documentation. The two margins of a year disagree about
the grand total — worst 1.68 % after the correction, the Saturday motorcycle of
2013 — and the cause is that a sum of thirty log-linear curves is not the curve of
their sum, so it is a known cost of D40's per-unit interpolation and not a defect.
2005's pedestrian margin reads 0.163 trips per inhabitant against 0.737 in 2011,
a factor of 4.5, because it counts only the walking of fifteen minutes or more;
that is the measurement behind excluding it as an anchor. And UPL04 on the
Saturday of 2011 has 1,351 cycling trips of exposure with a margin of zero at both
ends, which is travel crossing a unit with none of it local — the difference
between a margin and an exposure, and the reason D60 fits at zone level instead of
between units.

`desagregacion_a_zonas.py` is the third of that set and checks the step D60 names
as an assumption: bringing a year's margins back down from the thirty units onto
the zones of the survey that seeds it. The check that decides is the identity —
a survey year disaggregated onto its own zones has to come back as that survey's
zone margins, and it does, to 1.5e-11 trips per day on margins of millions.

Two of its eleven checks exist because it found two silent defects. A block the
seed carried and the targets did not was left with its inside at zero and its
outside still held at the survey's level, which is a block of pure municipios
ring; since the ring is not symmetric between origins and destinations its two
margins disagree, and it cost the identity 4.65 %. And a day type the seed does
not measure — 2011 measured no Sunday — came back as 120 unplaceable unit-mode
combinations instead of as an error, which is the difference between a small real
finding and a stage wired to the wrong survey. Neither would have shown in the
result: the first swaps one plausible number for another and the second fills a
diagnostic table nobody would have read as a defect.

It also measures the two answers to the one question the disaggregation leaves
open. Between 8.5 % and 27.7 % of a survey's origin margin falls outside the
thirty units, in the ring of municipios the surveys cover and the study does not,
and a trip from Soacha has no unit margin to be scaled by. Holding it at the
seeding survey's level and scaling it by what the thirty units did as a whole
differ by a median of 0.40 % of the margin over 216 cells, by 9.47 % at worst, and
by exactly nothing in a year measured on its own kind of day.

`piso_de_la_semilla.py` and `panel_ajustado.py` close the set, and the first is
the measurement behind D61. Twenty-five of the fifty-two blocks the reconstruction
fits had margins no matrix with the survey's own support admitted, because the
seeds are between 0.5 % and 1.4 % dense and keeping every zero of a sample that
sparse is keeping sampling noise as geography. The floor fixes it, and what this
checks is that it fixes it without breaking what already worked: **D60's identity
is still exact and no survey year needed the floor**, which is why the floor is
applied only where the seed's own support falls short — a floored seed carries more
travel than the margins ask for, so fitting it would stop a survey year coming back
as itself. All 52 blocks converge, fourteen with the floor; it invents 11,965 trips
a day of 109,911,870, 0.0109 %; and the worst unit's margin error falls from
**55.74 % to 0.0097 %**, which is the whole point, because a cross-section reads
the variation between units and that is exactly the error that does not average
away.

`panel_ajustado.py` asks the two questions D62 rests on. Whether the fitted panel
can be read beside D40's — same columns in the same order, declared values in the
variant and provenance columns, a complete grid, and no key collision when the two
are concatenated — and whether it differs from it at all. It does, in the
informative way: **the two agree on the aggregate almost exactly and disagree about
individual units by a great deal.** The median ratio is 0.999 in all four modes and
cycling in a single unit and year runs from 0.49 to 2.35 of what D40 gives it. Had
they agreed everywhere, the honest conclusion would have been that the extra
assumption buys nothing, and this is the script that would have said so.

## What is not here

Tools that work on the thesis document rather than on the data stay in
`deliverables/diseno/`, because that is what they operate on: the design and
colour variants, the vertical-spacing detector, the acronym and foreign-word
checkers, and the script that maps each predictor to the sources in the
bibliography. They are of no use without the document, and the document is not
published.