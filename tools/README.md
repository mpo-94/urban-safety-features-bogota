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
```

Each prints a table and exits. `respuesta.py` takes the name of a run directory
and defaults to the one named in its own source, so a figure it produced can be
recomputed against the run it came from rather than against the newest one.

## What each one answers

| Script | Question | Evidence for |
|---|---|---|
| `flujos_vs_stock.py` | Is each annual file of a layer the state of the network that year, or what was built in it? | **D46** |
| `respuesta.py` | Does the response carry enough signal, pair by pair and year by year, to regress on thirty units? | `regression-inventory.md` §2 |
| `vigencia.py` | What date is each static layer actually from, read off its own columns rather than its file name? | `regression-inventory.md` §4 |

`flujos_vs_stock.py` measures the three line layers that carry an annual series
together, with the cycleway among them **as a control**. That is deliberate: the
totals of a flow only say how anomalous they are when something that really is a
stock is printed beside them, and the first run of that check found zero files in
two folders and would have been read as zero kilometres without it. Those two
folder names carry an ñ that this filesystem stores decomposed, so the paths are
resolved through `config.resolve_source_path` and never through a plain glob.

## What is not here

Tools that work on the thesis document rather than on the data stay in
`deliverables/diseno/`, because that is what they operate on: the design and
colour variants, the vertical-spacing detector, the acronym and foreign-word
checkers, and the script that maps each predictor to the sources in the
bibliography. They are of no use without the document, and the document is not
published.
