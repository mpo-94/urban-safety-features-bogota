# Design decisions

This is the record of choices that shaped the pipeline and that the code cannot
explain on its own: why I picked one option over another, what I rejected and on
what grounds, and what is still unresolved. The code says what it does; this says
why it does it that way.

I add entries as I go, not at the end. That means most entries are written before
the code that carries them out, so each one separates two different questions:

- **Status** — is the decision itself settled, or still open? Open entries name
  who has to resolve them.
- **Built** — how much of it exists in the code today. A decision recorded here
  is not a description of what the pipeline currently does; this line says what
  is actually there.

Figures quoted in these entries name the base they were measured on. A count over
the vehicle table and a count over the frame already crossed with the casualties
are not interchangeable: the crossing repeats a vehicle once per casualty it
carried, so the second is larger for the same underlying records.

| # | Decision | Status | Built |
|---|---|---|---|
| D1 | One row per affected party, not per crash | Closed | Yes |
| D2 | The counting unit is the party, with person counts alongside | Closed | Yes |
| D3 | Casualty severity origin preserved from the first step | Closed (aggregation open) | Yes, for loading |
| D4 | Vehicle classification by occupant protection | Closed | Yes |
| D5 | Crashes with more than two parties are discarded | Closed | Yes |
| D6 | Spatial join by containment only, no proximity fallback | Closed (crash-level handling open) | Yes |
| D7 | The UPL layer is three units short of the design | **Open** | Detection only |
| D8 | Person identity falls back to row position | Closed, forced by the data | Yes |
| D9 | A casualty with no recorded vehicle is not automatically a pedestrian | Closed | Yes |

---

## D1 — One row per affected party, not per crash

**Status:** Closed.

**Built:** Yes. Party resolution emits one row per affected party carrying its
counterpart's actor type. A crash in which two parties are both hurt emits two
rows, one from each side.

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

**Built:** Yes. Every emitted row carries the party count as one, and beside it
separate counts of people injured and people killed.

**Context.** In the inherited pipeline the casualty column changed meaning
depending on the actor type: it summed people for pedestrians and cyclists, and
took a maximum for every other type. The same column therefore meant "number of
people" in some rows and "number of vehicles with at least one casualty" in
others, with nothing in its name to say so. Anyone reading the matrix as a person
count would overstate pedestrian and cyclist harm relative to everyone else.

**Decision.** The unit of the matrix is the affected party. A party with at least
one casualty counts as one, however many of its occupants were hurt. A bus with
eight injured occupants counts one. Three pedestrians hit by a car count three,
because each pedestrian is its own party. Alongside that, every row carries a
parallel count of people, split into injured and killed, so that a party matrix
and a person matrix can both be produced from a single run without touching the
pipeline again.

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

**Built:** Yes, for loading. The origin is recorded as each layer is read and
survives into the concatenated set. Keeping it through the stages that follow is
a constraint on code not yet written.

**Context.** Fatalities and injuries arrive as two separate point layers. The
inherited code flagged both with an identical value at load time and concatenated
them, which made the distinction unrecoverable everywhere downstream. Fatalities
are 8,548 of the 269,841 casualty records, about 3%, so merging them under one
flag buries the outcome that matters most.

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

**Built:** Yes. The sources are checked against the mapping when they are read,
and the mapping is applied when parties are resolved. Unrecognised values reach
the residual category instead of becoming null, and are reported with their count
on every run.

**Context.** The inherited mapping had no stated principle and was inconsistent
with itself: some entries followed how exposed the occupant is, others followed
what the vehicle is used for commercially. It was also incomplete, and the
incompleteness cost real records.

`MOTOTRICICLO` was absent from it. That value appears on 300 rows of the vehicle
table, and on 388 rows of the frame already crossed with the casualties, which is
where the loss occurred; the two figures describe the same records, counted
before and after the crossing repeats a vehicle once per casualty it carried.
Those 388 rows became null, and the nulls were later dropped by a grouping
operation with no error and no warning. They touched 240 crashes, and 25 of those
lost every row they had and vanished from the study altogether.

`AMBULACIA`, which is how the source actually spells it, was absent as well,
while the correct spelling `AMBULANCIA` was mapped — so that entry matched
nothing. In this extract it cost no records, because the two rows carrying the
misspelling belong to crashes with no casualty and never reach the crossed frame.
It is the same defect as the one above, waiting for a different extract.

**Decision.** One principle, written at the head of the mapping and applied
consistently: **the category reflects how protected the occupant is, not what the
vehicle is used for economically.** A rider with no bodywork around them belongs
with motorcycles whether the vehicle carries passengers, cargo or nothing;
someone inside a closed passenger cabin belongs with cars or with public
transport depending on whether the service is mass transit.

Applying it moves four categories away from where economic use had put them:
`MOTOTRICICLO`, `MOTOCARRO` and `CUATRIMOTO` join motorcycles, and `BICITAXI`
joins bicycles. Together they are 1,192 of the 1,465,735 rows of the vehicle
table, and 646 of the 403,456 rows of the frame crossed with the casualties —
small on either base. I made the change because a principle that bends for
inconvenient cases is not a principle, not because the volume forced it.

Two exceptions are declared explicitly rather than left to look like oversights:

- `TRACCION ANIMAL` stays in the residual category because it belongs to neither
  the motorised nor the pedal family, so the protection criterion has nothing to
  say about it.
- `NO IDENTIFICADO` stays in the residual category because the vehicle is
  unknown, not because its level of protection was assessed and found to be
  anything in particular. This distinction matters if anyone later tries to
  interpret that category as a homogeneous class.

Two safeguards go with the mapping. Matching is on normalised text rather than
character for character, so a difference in spacing, casing or accents cannot
turn a known category into an unknown one. And anything still unmatched is routed
to the residual category and reported at run time, so that a typing variation in
a future extract can change a count but can never delete rows in silence, which
is precisely what happened before. On the current sources that second safeguard
already earns its keep: 5,658 vehicle parties carry no type at all and reach the
residual category instead of becoming null.

**Rejected — keep the inherited categories for comparability with the original
results.** Comparability with a result I know to be wrong is not worth having,
and it would carry the null-dropping defect forward.

**Rejected — a separate three-wheeler category.** The volume cannot support its
own row and column in the matrix, and splitting it off would separate exposure
levels that the stated principle says are the same.

---

## D5 — Crashes with more than two parties are discarded

**Status:** Closed, and measured.

**Built:** Yes. The threshold counts every recorded party of a crash, whether or
not it suffered casualties, and each run reports what it removes.

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

**Measured.** The rule removes **15,014 of 184,112 crashes, 8.15%**, and with them
33,527 of the 269,841 people who entered. That is far more than the 4,208 the
inherited pipeline lost to its equivalent filters, and the gap is not a
discrepancy: the inherited code deduplicated actor *types* before counting, so a
crash between two cars counted as one type and passed a threshold my version
applies to parties, where it is correctly two. Counting parties is what the rule
was always meant to mean.

The composition of what is removed, by crash type, against what survives:

| Crash type | Discarded | % | Kept | % | Ratio |
|---|---:|---:|---:|---:|---:|
| CHOQUE (collision) | 10,541 | 70.22% | 94,670 | 55.99% | 1.25x |
| ATROPELLO (pedestrian struck) | 4,299 | 28.64% | 51,081 | 30.21% | **0.95x** |
| VOLCAMIENTO (rollover) | 81 | 0.54% | 5,514 | 3.26% | 0.17x |
| OTRO | 69 | 0.46% | 4,778 | 2.83% | 0.16x |
| CAIDA DE OCUPANTE (occupant fall) | 22 | 0.15% | 10,829 | 6.40% | 0.02x |
| AUTOLESION | 0 | 0.00% | 2,193 | 1.30% | 0.00x |

The exclusion is **not neutral, but it does not fall on pedestrians.** Collisions
are over-represented among the discarded by a quarter, which is mechanical: a
crash needs several parties to be discarded, and multi-party crashes are
collisions almost by definition. Crashes that are single-party by nature —
rollovers, occupant falls, self-harm — are almost untouched, for the same reason
in reverse.

What I was most concerned about does not happen: pedestrian crashes are removed
at 0.95x their share of the survivors, marginally *less* than their weight. Given
that vulnerable road users are the object of the study, a rule that quietly
thinned out pedestrian records would have been a serious problem. It does not.

The limitation to declare is therefore narrower than feared, and specific: the
matrix under-represents collisions involving three or more parties, which are 8%
of crashes and skew towards multi-vehicle collisions rather than towards any
vulnerable mode.

---

## D6 — Spatial join by containment only, no proximity fallback

**Status:** Closed for the loading stage. What to do with unlocated records at
crash level is open, pending with my advisor.

**Built:** Yes. The join assigns by containment only, the proximity fallback is a
switch that is off, and unlocated points are counted and reported rather than
dropped or moved.

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

**Built:** Detection only. The expected number of units is declared alongside
each scale and a run on the UPL scale reports the shortfall. Nothing acts on it.

**Context.** The panel is specified as UPL by year, over the 33 units defined by
Decreto 555 de 2021. The shapefile I have carries 30 of them: UPL01, UPL02 and
UPL06 are absent, and its total area is consistent with an urban and urban-rural
extract that leaves out the rural units. Whatever else is true, no variable built
on this layer can exceed 90.9% coverage of the intended panel, and the three
missing units will never receive a value from any source.

**Decision.** Not taken. All I have done meanwhile is make the shortfall
impossible to miss, so that no coverage figure gets reported without it being
obvious that the denominator is in question.

**Options on the table.**

- Obtain the complete layer from the Secretaría Distrital de Planeación and keep
  the panel at 33 units. Preferable if the layer exists, but the missing units
  appear to be rural, where the urban predictors are largely undefined anyway.
- Declare the study universe to be the 30 urban UPL and state the restriction
  explicitly. Honest and immediately actionable, at the cost of a narrower claim.

Deciding this early matters more than deciding it well: every coverage figure I
report downstream is computed against one denominator or the other.

---

## D8 — Person identity falls back to row position

**Status:** Closed, but forced by the data rather than chosen. Worth revisiting
if the duplication described below is settled.

**Built:** Yes. The check runs before anything is built, reports its three
figures on every run whatever they are, and picks the identifier accordingly, so
the fallback reverses itself automatically if the source is ever cleaned.

**Context.** Pedestrians share a single value in the vehicle field, so that field
cannot tell two pedestrians of the same crash apart. Each of them has to be its
own party, which means I need something that identifies a person within a crash.
The obvious candidate is the person code the source carries, which has the real
advantage of leading back to the original record.

I measured it instead of assuming it. Over the 269,841 concatenated casualty
records: **no record has a null person code**, and **4 pairs of records share a
(crash, person) code**. All 4 collisions span the two source layers — none occurs
inside a single layer.

**Decision.** Use the row position in the casualty set, which identifies a person
by construction. The source code is not unique, so it cannot be the key, and
building a composite key out of other columns would only paper over the problem
with something that looks authoritative and is not.

**Rejected — a composite key of crash, person code and source layer.** It would
be unique, but only by encoding the duplication into the key, which makes the
duplicated people invisible rather than absent.

**Rejected — silently dropping the second record of each colliding pair.** That
is a decision about double counting disguised as a technical clean-up, and it
belongs in the open question below, not in a key choice.

**Open, and separate from the key.** Those 4 collisions look like the same person
recorded in both layers — same crash, same person code, same role, same date,
appearing once as an injury and once as a fatality. That is what someone who was
injured and later died would look like in two sources built at different times.
If so, 4 people are counted twice, once in each category. It is four people out
of 269,841, so it changes nothing numerically, but it is a question about what
the sources mean rather than about arithmetic. To settle with my advisor.

---

## D9 — A casualty with no recorded vehicle is not automatically a pedestrian

**Status:** Closed.

**Built:** Yes, and the counts below are reported on every run.

**Context.** 66,037 casualty records name no vehicle. The inherited pipeline
treated every one of them as a pedestrian. But the role column disagrees: 63,947
of them are indeed recorded as pedestrians, while 2,090 are recorded as
passengers, drivers, or with no information at all. A passenger with no vehicle
recorded is not someone walking; it is someone whose vehicle the form did not
capture.

**Decision.** A casualty with no vehicle of its own becomes a party in itself,
which is right in every case. Its actor type is pedestrian only when the source
says the person was a pedestrian; otherwise it is the residual category, because
the vehicle is unknown rather than absent. This is the same principle already
settled in D4 for unknown vehicle types, applied to a different symptom of the
same gap.

**Rejected — call them all pedestrians, as the inherited code did.** It inflates
the pedestrian row of the matrix by around 2,000 records built from people who
were riding in something. Pedestrians are one of the vulnerable modes the study
is about, so contaminating that row is precisely the wrong place to be casual.

**Rejected — drop them.** They are real casualties of real crashes, and the
residual category exists exactly so that records with an unknown attribute stay
in the count instead of disappearing.

**Noted, not decided.** The reverse inconsistency also exists: 464 casualties are
recorded as pedestrians and yet reference a vehicle, which cannot both be true.
The pipeline follows the vehicle reference, because it resolves to a real vehicle
in the crash while the role is free text on a form. The number is small and I
have not investigated which side is wrong.
