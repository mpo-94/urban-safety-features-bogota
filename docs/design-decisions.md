# Design decisions

This is the record of choices that shaped the pipeline and that the code cannot
explain on its own: why I picked one option over another, what I rejected and on
what grounds, and what is still unresolved. The code says what it does; this says
why it does it that way.

I add entries as I go, not at the end. Each one carries a status, and the open
ones name who has to resolve them.

| # | Decision | Status |
|---|---|---|
| D1 | One row per affected party, not per crash | Closed |
| D2 | The counting unit is the party, with person counts alongside | Closed |
| D3 | Casualty severity origin preserved from the first step | Closed (aggregation open) |
| D4 | Vehicle classification by occupant protection | Closed |
| D5 | Crashes with more than two parties are discarded | Closed (measurement pending) |
| D6 | Spatial join by containment only, no proximity fallback | Closed (crash-level handling open) |
| D7 | The UPL layer is three units short of the design | **Open** |

---

## D1 — One row per affected party, not per crash

**Status:** Closed.

**Context.** The pipeline I inherited collapsed every crash into a single row and
then let the alphabetical order of the actor label decide which party was
recorded as the casualty and which as the counterpart. Alphabetical order has no
relation to who was actually hurt, so the orientation of every cell in the matrix
was decided by an accident of naming. That is a systematic bias, not noise: it
pushes the same actor types to the same side of the pair every time.

**Decision.** I model a crash as a set of parties. A party is either a vehicle
with its occupants or an individual pedestrian, and it carries an actor type and
a casualty count that may be zero. Rows of the matrix come only from parties with
casualties above zero; the counterpart is looked up among all parties of the
crash, whether or not they were hurt. A crash in which a cyclist and a
motorcyclist are both injured therefore produces two rows — the injured cyclist
with the motorcycle as counterpart, and the injured motorcyclist with the bicycle
as counterpart — instead of one row whose orientation depends on the letter B
preceding the letter M.

**Rejected — keep one row per crash and choose the principal victim by severity.**
This needs a severity ranking comparable across actor types, which the sources do
not provide, and it still throws away the second victim. The asymmetry between
modes is the object of study; discarding one side of it defeats the purpose.

**Rejected — one row per crash holding an unordered pair.** An unordered pair
cannot express that a pedestrian struck by a car and a car struck by a pedestrian
are different events with very different outcomes. The whole point of an
inter-mode matrix is that it is not symmetric.

---

## D2 — The counting unit is the party, with person counts alongside

**Status:** Closed.

**Context.** In the inherited pipeline the casualty column changed meaning
depending on the actor type: it summed people for pedestrians and cyclists, and
took a maximum for every other type. The same column therefore meant "number of
people" in some rows and "number of vehicles with at least one casualty" in
others, with nothing in its name to say so. Anyone reading the matrix as a person
count would overstate pedestrian and cyclist harm relative to everyone else.

**Decision.** The unit of the matrix is the affected party. A party with at least
one casualty counts as one, however many of its occupants were hurt. A bus with
eight injured occupants counts one. Three pedestrians hit by a car count three,
because each pedestrian is its own party. Every row also carries a parallel count
of people, split into injured and killed, so that a party matrix and a person
matrix can both be produced from a single run without touching the pipeline
again.

**Rejected — count people only.** A bus row would then rise and fall with how
full the bus happened to be, which measures occupancy rather than the risk
relationship between modes. It also makes mass transit look catastrophic next to
private cars for reasons that have nothing to do with the interaction being
studied.

**Rejected — keep the inherited hybrid.** It is not defensible to publish a
matrix whose cells mean different things in different rows, and the mixture
cannot be undone after the fact because the person counts were never kept.

**Rejected — count parties only and reconstruct people later.** Once the
aggregation collapses a vehicle's occupants there is no way back. Carrying both
counts through the pipeline costs two columns and keeps the option open.

---

## D3 — Casualty severity origin preserved from the first step

**Status:** Closed for loading. The aggregation choice is open, pending with my
advisor.

**Context.** Fatalities and injuries arrive as two separate point layers. The
inherited code flagged both with an identical value at load time and concatenated
them, which made the distinction unrecoverable everywhere downstream. Deaths are
about 3% of records (8,548 against 261,293), so merging them under one flag
buries the outcome that matters most.

**Decision.** Each record is tagged with the layer it came from at read time, and
that column is never dropped. I am deliberately not deciding here how the two
should be aggregated — whether the analysis uses a combined killed-or-injured
measure, separate models, or both. That decision belongs downstream and stays
reversible for as long as the column survives, which is the entire point of
recording it now.

**Rejected — derive severity later from the columns unique to the fatalities
layer.** It is the same information obtained in more steps, and it silently
breaks if either source layer changes its schema.

**Open.** Which aggregation the models use. To settle with my advisor once the
matrix exists and the sparsity of the fatality cells can be inspected.

---

## D4 — Vehicle classification by occupant protection

**Status:** Closed.

**Context.** The inherited mapping had no stated principle and was inconsistent
with itself: some entries followed how exposed the occupant is, others followed
what the vehicle is used for commercially. It was also incomplete. `MOTOTRICICLO`
was missing, so 300 source rows became null, and those nulls were later dropped
by a grouping operation without any error or warning — 25 crashes disappeared
from the study entirely. `AMBULACIA`, which is how the source actually spells it,
was missing too while the correct spelling was mapped, so that entry never
matched anything either.

**Decision.** One principle, written at the head of the mapping and applied
consistently: **the category reflects how protected the occupant is, not what the
vehicle is used for economically.** A rider with no bodywork around them belongs
with motorcycles whether the vehicle carries passengers, cargo or nothing;
someone inside a closed passenger cabin belongs with cars or with public
transport depending on whether the service is mass transit.

Applying it moves four categories away from where economic use had put them:
`MOTOTRICICLO`, `MOTOCARRO` and `CUATRIMOTO` join motorcycles, and `BICITAXI`
joins bicycles. Together they are about 1,200 of 1.47 million source rows, so the
reclassification is small in volume; I made it because a principle that bends for
inconvenient cases is not a principle.

Two exceptions are declared explicitly rather than left to look like oversights:

- `TRACCION ANIMAL` stays in the residual category because it belongs to neither
  the motorised nor the pedal family, so the protection criterion has nothing to
  say about it.
- `NO IDENTIFICADO` stays in the residual category because the vehicle is
  unknown, not because its level of protection was assessed and found to be
  anything in particular. This distinction matters if anyone later tries to
  interpret that category as a homogeneous class.

Matching is done on normalised text rather than character for character, and
anything unmatched is routed to the residual category and reported loudly at run
time. A typing variation in a future extract can then change a count, but it can
never delete rows in silence, which is exactly what happened before.

**Rejected — keep the inherited categories for comparability with the original
results.** Comparability with a result I know to be wrong is not worth having,
and it would carry the null-dropping defect forward.

**Rejected — a separate three-wheeler category.** The volume cannot support its
own row and column in the matrix, and splitting it off would separate exposure
levels that the stated principle says are the same.

---

## D5 — Crashes with more than two parties are discarded

**Status:** Closed as a rule. The measurement of what it removes is pending until
the aggregation stage exists.

**Context.** This follows the criterion of the European study being replicated,
but it also resolves a real problem in the data. With three or more parties the
counterpart of a given casualty is ambiguous: nothing in the sources says which
of the other two caused the harm, and any choice among them is an assumption
dressed as a rule. With at most two parties the counterpart is simply the other
party, with no ambiguity at all.

**Decision.** Discard crashes involving more than two parties, and treat the
resulting restriction as a declared limitation of the study rather than a
technicality to leave unmentioned. In the inherited run the equivalent filters
removed 4,208 of 184,112 crashes, about 2.3%.

**Rejected — keep them and split the attribution across the other parties.**
Fractional attribution invents a causal weighting the sources do not support, and
it makes the cells of the matrix non-integer, which then has to be explained
every time the matrix is shown.

**Rejected — keep them and pick the heaviest or fastest counterpart.** Same
problem with a more confident face on it. It would encode a hypothesis about
which mode causes harm into the very measurement meant to test that hypothesis.

**Pending.** Measuring how many crashes this removes in my own pipeline and
whether their composition differs from the rest — if multi-party crashes are
concentrated in particular modes or particular localities, the exclusion is not
neutral and has to be reported as such.

---

## D6 — Spatial join by containment only, no proximity fallback

**Status:** Closed for the loading stage. What to do with unlocated records at
crash level is open, pending with my advisor.

**Context.** The inherited code looked as though it snapped unmatched points to
the nearest polygon within a tolerance. It never did. It searched for unmatched
points in the result of a left join, which by construction keeps every input row,
so its set of unmatched points was always empty and the fallback never executed.
Had it executed, the tolerance was expressed in degrees while the join ran in
geographic coordinates, so the effective threshold was roughly 550 km rather than
the 5 m it appears to be. Every number the inherited pipeline produced therefore
comes from plain containment, and the tolerance in its source is decoration.

I record this because I initially believed the tolerance was real, and the
correction changes what "reproducing the legacy figures" means: my
containment-only join matches those figures because it does what that code
actually did, not by coincidence.

**Decision.** Assign a casualty to the unit that contains its point, and to
nothing else. Points falling outside every unit keep a null unit, are reported,
and are not dropped at load. The proximity fallback exists as a switch, off by
default, with its threshold expressed in metres and applied in the projected
coordinate system so the unit is genuinely metres.

The reasoning is that snapping a point to a polygon it is not inside assigns a
casualty to a place where it did not happen. At locality scale this concerns 61
of 8,548 fatalities and 1,344 of 261,293 injuries, about half a percent; with a
real 5 m threshold the fallback would recover 3 of those 61. Fabricating
locations for half a percent of records to gain a handful is a bad trade.

**Rejected — enable the fallback by default to maximise coverage.** It recovers
almost nothing at an honest threshold, and at a generous one it relocates records
silently, which is worse than losing them visibly.

**Rejected — drop unlocated records at load time.** That destroys the ability to
report the loss, and it is premature: a crash whose victim point falls outside
every unit may still be reachable through another victim of the same crash.

**Open.** Whether a crash should be excluded when it cannot be located, or
assigned by some other means, and at which stage. To settle with my advisor.

---

## D7 — The UPL layer is three units short of the design

**Status:** **Open.** Blocking for the panel specification. To settle with my
advisor.

**Context.** The panel is specified as UPL by year, over the 33 units defined by
Decreto 555 de 2021. The shapefile I have carries 30 of them: UPL01, UPL02 and
UPL06 are absent, and its total area is consistent with an urban and urban-rural
extract that leaves out the rural units. Whatever else is true, no variable built
on this layer can exceed 90.9% coverage of the intended panel, and the three
missing units will never receive a value from any source.

**Decision.** Not taken. What I have done meanwhile is make the shortfall
impossible to miss: the expected number of units is declared alongside each
scale, and the loader warns whenever the layer disagrees with it, naming how many
units will never receive data.

**Options on the table.**

- Obtain the complete layer from the Secretaría Distrital de Planeación and keep
  the panel at 33 units. Preferable if the layer exists, but the missing units
  appear to be rural, where the urban predictors are largely undefined anyway.
- Declare the study universe to be the 30 urban UPL and state the restriction
  explicitly. Honest and immediately actionable, at the cost of a narrower claim.

Deciding this early matters more than deciding it well: every coverage figure I
report downstream is computed against one denominator or the other.
