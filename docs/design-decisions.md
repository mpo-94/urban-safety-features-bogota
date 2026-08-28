# Design decisions

This is the record of choices that shaped the pipeline and that the code cannot
explain on its own: why I picked one option over another, what I rejected and on
what grounds, and what is still unresolved. The code says what it does; this says
why it does it that way.

I add entries as I go, not at the end. That means most entries are written before
the code that carries them out, so each one separates two different questions:

- **Kind** — **methodological** if it changes what the matrix measures, what it
  counts, what it excludes or how the pair is oriented; **implementation** if it
  only affects how the work is organised: formats, folders, file names, colour
  scales. The methodological ones belong in the thesis, because a reader has to
  know them to interpret a number. The implementation ones belong here and
  nowhere else.
- **Status** — is the decision itself settled, or still open? Open entries name
  who has to resolve them.
- **Built** — how much of it exists in the code today. A decision recorded here
  is not a description of what the pipeline currently does; this line says what
  is actually there.

Figures quoted in these entries name the base they were measured on. A count over
the vehicle table and a count over the frame already crossed with the casualties
are not interchangeable: the crossing repeats a vehicle once per casualty it
carried, so the second is larger for the same underlying records.

| # | Decision | Kind | Status | Built |
|---|---|---|---|---|
| D1 | One row per affected party, not per crash | Methodological | Closed | Yes |
| D2 | The counting unit is the party, with person counts alongside | Methodological | Closed | Yes |
| D3 | Casualty severity origin preserved from the first step | Methodological | Closed (aggregation open) | Yes, for loading |
| D4 | Vehicle classification by occupant protection | Methodological | Closed | Yes |
| D5 | Crashes with more than two parties are discarded | Methodological | Closed | Yes |
| D6 | Spatial join by containment only, no proximity fallback | Methodological | Closed (crash-level handling open) | Yes |
| D7 | The study universe is the 30 UPL of the layer | Methodological | Closed | Yes |
| D8 | Person identity falls back to row position | Implementation | Closed; fallback no longer in effect | Yes |
| D9 | The actor type of a casualty with no recorded vehicle comes from its role | Methodological | Closed | Yes |
| D10 | The grid is complete: an unobserved combination is a zero, not an absence | Methodological | Closed | Yes |
| D11 | Parties with no territorial unit leave the pipeline at aggregation | Methodological | Closed | Yes |
| D12 | Figures are drawn from the exported tables, on a shared logarithmic scale | Implementation | Closed | Yes |
| D13 | Output layout separates analysis tables from presentation tables | Implementation | Closed | Yes |
| D14 | Pictograms in pipeline figures — tried and reverted | Implementation | Closed, reverted | No, removed |
| D15 | The pipeline runs at UPL; the legacy figures become a historical contrast | Methodological | Closed | Yes |
| D16 | One entry point, one route per way of running the pipeline | Implementation | Closed | Yes |
| D17 | ρ(t) is computed from the party universe, on unordered pairs, with the denominator always beside it | Methodological | Closed | Yes |
| D18 | The 2007 vehicle table does not distinguish the two parties of a vehicle–vehicle crash | Methodological | **Open** | Detection only |
| D19 | The most recent extract prevails, whole year at a time | Methodological | Closed | Yes |
| D20 | The sources are checked for coverage, not only for arithmetic | Implementation | Closed | Yes |
| D21 | The desire lines are out until it is settled what they measure | Methodological | **Open** | No, excluded |
| D22 | A predictor is measured against every unit, and a zero is an observation | Methodological | Closed | Yes, for the ten static ones |
| D23 | The histogram bins and the correlation scale are declared, not inferred | Implementation | Closed; bin rule revised | Yes |
| D24 | The master table is one figure, shaded column by column | Implementation | Closed | Yes |
| D25 | The predictor declaration is what the code runs on, and it is exported | Implementation | Closed | Yes |
| D26 | The pipeline draws the map, as a reference map in four colours | Implementation | Closed; reverses D24's exclusion | Yes |
| D27 | A figure the document draws itself gets its data exported for it | Implementation | Closed | Yes, for the city series of ρ |

Methodological decisions: D1-D7, D9, D10, D11, D15, D17, D18, D19, D21, D22.
Implementation decisions: D8, D12, D13, D14, D16, D20, D23, D24, D25, D26, D27.

---

## D1 — One row per affected party, not per crash

**Kind:** Methodological.

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

**Kind:** Methodological.

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

**Kind:** Methodological.

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

**The assumption underneath, and its permanent check.** Counting injured and
killed separately only means anything if the two layers are mutually exclusive.
Every run reports how many people appear in both, with the cause named, whatever
the answer is.

On the original extract it was **4 people**, counted once as an injury and once as
a fatality, so 8 records described 4 people. **On the updated 2024 extract it is
zero**: all four were 2024 records, and the updated extract carries each of them
once (D19). The check is what makes that visible, and it is the reason it is
reported on every run rather than only when it fails.

**Open.** Which aggregation the models use. To settle with my advisor once the
matrix exists and the sparsity of the fatality cells can be inspected. The
duplication above belongs to the same conversation: if someone injured who later
died should count once as a fatality rather than once in each category, that is
the same question about what the two layers mean.

---

## D4 — Vehicle classification by occupant protection

**Kind:** Methodological.

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

**Kind:** Methodological.

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
technicality to leave unmentioned.

> **What this costs, in absolute terms.** The rule removes **15,375 crashes of
> 188,368 (8.16%)** and **34,475 people of 277,513 (12.42%)**. Among the
> discarded crashes there are **4,398 pedestrian-struck crashes, which is 7.81%
> of every pedestrian-struck crash in the base**. Measured on the updated 2024
> extract (D19); on the original extract it was 15,014 crashes of 184,112
> (8.15%), 33,527 people of 269,841 and 4,299 pedestrian-struck crashes (7.76%).
> The rule did not change — a fuller year has more crashes to apply it to.
>
> **The research proposal declares the inherited figure of 4,208 crashes (2.3%)
> and it has to be corrected to the figures above.** The two are not measuring
> the same thing: the inherited code deduplicated actor *types* before counting,
> so a crash between two cars counted as a single type and passed a threshold
> that my version applies to parties, where that crash is correctly two. Counting
> parties is what the rule was always meant to mean, and the larger number is the
> honest one.

**Rejected — keep them and split the attribution across the other parties.**
Fractional attribution invents a causal weighting the sources do not support, and
it makes the cells of the matrix non-integer, which then has to be explained
every time the matrix is shown.

**Rejected — keep them and pick the heaviest or fastest counterpart.** Same
problem with a more confident face on it. It would encode a hypothesis about
which mode causes harm into the very measurement meant to test that hypothesis.

**Measured — composition.** The absolute cost is stated above. The question that
remains is whether the loss falls evenly, because a rule that quietly thinned out
one mode would not be neutral however small it looked in total.

| Crash type | Discarded | % | Kept | % | Ratio | % of type |
|---|---:|---:|---:|---:|---:|---:|
| CHOQUE (collision) | 10,797 | 70.23% | 97,349 | 56.28% | 1.25x | 9.98% |
| ATROPELLO (pedestrian struck) | 4,398 | 28.61% | 51,881 | 29.99% | **0.95x** | 7.81% |
| VOLCAMIENTO (rollover) | 82 | 0.53% | 5,619 | 3.25% | 0.16x | 1.44% |
| OTRO | 74 | 0.48% | 4,818 | 2.79% | 0.17x | 1.51% |
| CAIDA DE OCUPANTE (occupant fall) | 22 | 0.14% | 11,100 | 6.42% | 0.02x | 0.20% |
| AUTOLESION | 0 | 0.00% | 2,193 | 1.27% | 0.00x | 0.00% |
| INCENDIO (fire) | 0 | 0.00% | 8 | 0.00% | 0.00x | 0.00% |

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

**The two readings both belong in the limitations, and they are not in
conflict.** In relative terms the exclusion does not discriminate against
pedestrians: they are removed at 0.95x their share of the survivors, marginally
less than their weight. In absolute terms it still removes 4,398 pedestrian-struck
crashes, 7.81% of all of them. A reader whose subject is vulnerable road users
will want the second number, and giving only the reassuring ratio would be a way
of not answering. The limitation to declare is: the matrix under-represents
crashes with three or more parties, 8.16% of the base, which skew towards
multi-vehicle collisions rather than towards any vulnerable mode, and this costs
7.81% of the pedestrian-struck crashes.

---

## D6 — Spatial join by containment only, no proximity fallback

**Kind:** Methodological.

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
casualty to a place where it did not happen. At UPL scale, the scale of the study,
this concerns **51 of 8,592 fatalities and 1,224 of 268,921 injuries**, 1,275
records in all, 0.46%. On the original extract, before 2024 was replaced, it was
50 and 1,186 on the same footprint. At locality scale, where the legacy pipeline
was measured, it was 61 and 1,344; the two footprints are not the same territory,
so the counts differ by construction and neither corrects the other. With a real 5 m threshold
the fallback recovered 3 of the 61 at locality scale. Fabricating locations for
half a percent of records to gain a handful is a bad trade.

**Rejected — enable the fallback by default to maximise coverage.** It recovers
almost nothing at an honest threshold, and at a generous one it relocates records
silently, which is worse than losing them visibly.

**Rejected — drop unlocated records at load time.** That destroys the ability to
report the loss, and it is premature: a crash whose victim point falls outside
every unit may still be reachable through another victim of the same crash.

**Open.** Whether a crash should be excluded when it cannot be located, or
assigned by some other means, and at which stage. To settle with my advisor.

---

## D7 — The study universe is the 30 UPL of the layer

**Kind:** Methodological.

**Status:** Closed.

**Built:** Yes. The universe is declared as 30 units alongside the UPL scale, and
the loader stops the run if the layer does not carry exactly that many. Every
grid, every coverage figure and every panel is built on those 30.

**Context.** Decreto 555 de 2021 defines 33 UPL. The layer I have carries 30:
UPL01, UPL02 and UPL06 are absent, and the total area is consistent with an urban
and urban-rural extract that leaves out the rural units. Those three are exactly
where the urban predictors — road infrastructure, modal share, built environment
— are largely undefined, so they would enter the panel as rows of missing values
rather than as observations.

**Decision.** **The study universe is the 30 UPL present in the layer.** Thirty is
the denominator of every coverage figure the study reports. A unit of that
universe that receives no casualty in a given year is a zero, by D10; there is no
partial coverage of a larger set to report, because the larger set is not the
universe.

This is a declaration of scope, not a shortfall, and it is written that way
everywhere: a figure phrased as "90.9% of the 33 units" describes a study that was
never specified, and invites a reader to look for the missing 9.1% as if it were
data lost in processing.

**Rejected — hold the panel at 33 and carry the three units as missing.** They
would be structurally empty rows in every variable, which is not the same as an
observed zero and would have to be excluded from every estimation anyway. The
result is the same 30 units with an extra explanation attached.

**Rejected — wait for the complete layer from the Secretaría Distrital de
Planeación.** It would only add rural units where the predictors do not exist,
and it blocked work that has no other reason to be blocked.

**What is built, and why it changed.** Until this was settled the loader warned
that the layer was short of the design. That warning is gone: nothing is short.
The check itself stays, now against 30, and it is stricter than it was — a
mismatch raises rather than warns. The reason is that the roster is the
denominator of every coverage figure, so a layer that does not carry the declared
universe is a different layer, not a smaller one, and continuing would silently
rebase every figure of the run on whatever happens to be on disk.

**Consequence for the panel.** The panel is 30 units by 18 years = 540 unit-years,
and every rate reported per unit is over those 30. See D15 for the run that made
UPL the scale of the pipeline, and D10 for what 30 units do to the sparsity of the
grid.

---

## D8 — Person identity falls back to row position

**Kind:** Implementation. The choice of key is a technical one; the duplication it exposes, in the open question below, is not.

**Status:** Closed. The fallback was forced by the data and **is no longer in
effect**: on the updated 2024 extract the source person code is unique within a
crash, and the pipeline uses it. The entry is kept because the fallback is still
in the code, still runs on every execution, and comes back the moment a source
stops being unique.

**Built:** Yes. The check runs before anything is built, reports its figures on
every run whatever they are, and picks the identifier accordingly, so the
fallback reverses itself automatically if the source is ever cleaned.

**It did reverse itself.** The four colliding pairs were all 2024 records, and the
updated extract carries each of those people once (D19). The check now measures
**0 colliding (crash, person) pairs and 0 null person codes over 277,513 records**,
and reports that it is using the source code. Nothing was edited to make that
happen, which is the property the check was built for: the decision follows the
data on every run instead of being frozen the day it was taken.

**What that means for the limitation below.** Party identifiers now derive from a
key the source owns rather than from row position, so they no longer depend on the
order the records arrive in and are comparable across runs. If a future extract
reintroduces a collision, the fallback returns and so does the limitation, which is
why the paragraph stays.

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

**The cost of the fallback: it is not stable across runs.** A key built from row
position depends on the order the records arrive in. Nothing in the current
pipeline reorders them, so two runs over the same files produce the same keys —
but the guarantee comes from the input order, not from the data, and it does not
survive a re-export, a re-sorted source, or a change in how the two layers are
concatenated. Party identifiers are therefore safe to use within a run and unsafe
to compare across runs. Anything that needs to match a party between two
executions must go through the crash and the vehicle, which are stable, and not
through the party identifier. The source person code would not have this problem,
which is one more reason to want the duplication settled.

**Open, and separate from the key.** Those 4 collisions look like the same person
recorded in both layers — same crash, same person code, same role, same date,
appearing once as an injury and once as a fatality. That is what someone who was
injured and later died would look like in two sources built at different times.
If so, 4 people are counted twice, once in each category.

I am not resolving it by identification, and deliberately so. In all 4 cases the
crash, the code, the role and the date coincide exactly, and that total agreement
is itself the evidence that they are one person: an identifier built to tell them
apart would be asserting the opposite of what the data suggests. The question is
what the two layers mean, not how to key them, and it is my advisor's to answer.
See D3, where the same question decides how injured and killed are aggregated.

What is built instead is a permanent check: every run reports how many people
appear in both layers, with the cause named, whether the answer is four or zero.
Four out of 269,841 changes nothing numerically today; a future extract in which
that number grows would inflate the person counts, and it has to be visible the
moment it happens rather than discovered afterwards.

---

## D9 — The actor type of a casualty with no recorded vehicle comes from its role

**Kind:** Methodological.

**Status:** Closed.

**Built:** Yes. The rule is applied when parties are resolved, and every run
reports how each group of standalone casualties was typed.

**Context.** 67,116 casualty records name no vehicle. The inherited pipeline
called every one of them a pedestrian. The role column disagrees, and its full
inventory over that group is short:

| Role recorded | Records |
|---|---:|
| PEATON | 65,022 |
| PASAJERO | 1,912 |
| CONDUCTOR | 119 |
| SIN INFORMACION | 63 |
| *no role recorded* | 0 |
| **Total** | **67,116** |

Measured on the updated 2024 extract (D19). On the original extract the group was
66,037 records, split 63,947 / 1,908 / 119 / 63 in the same order; the shape of
the inventory is what matters and it did not move.

A passenger with no vehicle recorded is not someone walking; it is someone whose
vehicle the form did not capture. Calling them pedestrians inflates one of the
very rows the study is about.

**Decision.** A casualty with no vehicle of its own becomes a party in itself,
which is right in every case, and its actor type comes from its role — but only
where the role settles the level of protection by itself. That is the principle
of D4 applied to a different symptom of the same gap:

| Role | Actor type | Why |
|---|---|---|
| PEATON | Pedestrian | No vehicle at all |
| MOTOCICLISTA | Motorcycle | Exposed whatever the particular machine was |
| CICLISTA | Bicycle | Same |
| CONDUCTOR | Residual | May be protected or not depending on what they drove |
| PASAJERO | Residual | Same |
| Anything else, or nothing | Residual | Reported separately, never classified on a guess |

**What the rule actually recovers, measured.** Nothing, on these sources. Of the
2,094 non-pedestrian records above, **0** carry a role of motorcyclist or
cyclist, so all 2,094 stay in the residual category. Every motorcyclist and every
cyclist in the data names a vehicle, which is what one would expect: the form
records the motorcycle or the bicycle as a vehicle in its own right.

The rule is still worth having, and the updated 2024 extract is where it started
to pay. Of the casualties that reference a vehicle absent from the vehicle table —
3 on the original extract, 101 now, because 69 crashes of the updated extract have
no rows in the vehicle table — **61 are motorcyclists or cyclists and are placed as
such instead of falling to the residual category**. The measurement above stands
for the records that name no vehicle at all; this is the other group, and it is no
longer negligible.

**Reported separately, not classified.** 63 records carry the role SIN
INFORMACION, which is not in the mapping. They go to the residual category and
are named in the run log on every execution. Whether that value should be treated
as equivalent to no role at all is a question about the source, not something to
settle in passing.

**The asymmetry is deliberate.** Where a vehicle is recorded, the vehicle decides
the actor type and the role is ignored — that is why the 464 casualties recorded
as pedestrians while referencing a vehicle are typed by their vehicle. Where no
vehicle is recorded, the role decides, because it is the only evidence there is.
These are different criteria because they answer to different evidence: a vehicle
reference resolves to a real party of the crash and can be checked against the
vehicle table, while a role is a field on a form with nothing behind it. Reading
the two rules side by side they can look contradictory; they are not, they are
ordered by how much each source of evidence can be trusted.

**Rejected — call them all pedestrians, as the inherited code did.** It inflates
the pedestrian row by around 2,000 records built from people who were riding in
something. Pedestrians are one of the vulnerable modes the study is about, so
contaminating that row is precisely the wrong place to be casual.

**Rejected — drop them.** They are real casualties of real crashes, and the
residual category exists exactly so that records with an unknown attribute stay
in the count instead of disappearing.

**Rejected — infer the vehicle from the other parties of the crash.** In a
two-party crash one could guess that the unattached passenger was riding in the
other recorded vehicle. Sometimes true, unverifiable in general, and it would
manufacture exactly the kind of counterpart relationship the matrix is supposed
to measure.

**Noted, not decided.** Which side of the 464 contradictions is wrong. The
pipeline follows the vehicle for the reason above, but I have not investigated
whether the role or the reference is the error.

---

## D10 — The grid is complete: an unobserved combination is a zero, not an absence

**Kind:** Methodological.

**Status:** Closed.

**Built:** Yes. Every run reports how much of the grid is empty and whether any
unit or year is empty throughout.

**Context.** The inherited pipeline wrote only the combinations it had actually
seen. A locality with no cyclist casualties in 2009 simply had no row for that
combination, which makes a real zero and a missing observation look identical to
anything reading the file. In a panel that difference is not cosmetic: a zero is
an observation of no harm and belongs in the estimation, while a gap is an
absence of information and does not. Silently conflating them biases whatever is
fitted on top.

**Decision.** The matrix is a complete grid: every unit of the territorial layer,
every year of the study period, and every ordered pair of actor types, with zero
where nothing was observed. The unit roster comes from the shapefile rather than
from the data, so a unit that never appears in a single crash still gets its rows
of zeros instead of vanishing.

At UPL scale that is 30 units x 18 years x 6 actor types x 7 counterparts =
**22,680 cells, of which 7,673 (33.83%) are zero**. No unit and no year is empty
throughout. Emptiness concentrates where it should: Torca, on the northern edge,
is 55.16% empty, while Kennedy is 25.13% and Centro Histórico 23.54%. Measured at
locality scale the same grid was 14,364 cells and 29.80% zero, which is the
comparison that matters for the modelling note below. Completing 2024 (D19) moved
the share by a third of a point, from 34.17%: a fuller year fills cells that were
empty only because the records were missing.

**Rejected — keep only the observed combinations, as the inherited code did.**
Every consumer would have to reconstruct the grid to know whether a gap means
zero, and each would reconstruct it slightly differently.

**Rejected — write zeros only for combinations seen at least once anywhere.** A
half-complete grid is worse than either alternative, because it looks complete.

**Note for the modelling stage.** A third of the cells being zero is a property of
the data at this resolution, not a defect, but it does bear on the choice of
model. The share moves with the number of units, and predictably: cutting the
same casualties into 30 units instead of 19 took it from 29.80% to 33.83%, +4.03
points for 58% more units. At UPZ, with 111 units, it would be far higher again.
A third of the grid at zero is enough that which count distribution the panel is
fitted with is a decision to take deliberately rather than by default. It belongs
to the modelling stage and to my advisor, and it is now to be taken on this grid,
not on the locality one.

---

## D11 — Parties with no territorial unit leave the pipeline at aggregation

**Kind:** Methodological.

**Status:** Closed.

**Built:** Yes, with the loss named in the run record.

**Context.** D6 keeps casualties whose crash point falls outside every territorial
unit, rather than dropping them at load or snapping them somewhere they were not.
That postpones the question rather than answering it, and aggregation is where it
has to be answered: a cell is identified by its unit, so a record with no unit has
no cell to go to.

**Decision.** They leave here, and the loss is stated with its cause: at UPL scale,
**731 affected parties, carrying 1,083 injured and 43 killed**. That is 0.36% of
the 203,808 affected parties. Five of those 731 are there because their position
changed with the extract (D19), and the integration counts them separately for
that reason. At locality scale, on the original extract, it was 858 parties, 1,146
injured and 51 killed; the party model is identical in every one of those runs, and
the whole of the difference is that the layers cover different territory.

Dropping them at this point rather than at load is deliberate. Everything
upstream — the party model, the counterpart resolution, the two-party threshold —
is about crashes, not about places, and those records are perfectly valid there.
They only become unusable at the moment the analysis becomes spatial. Keeping
them until then means the funnel shows exactly what geography costs, separately
from what the crash model costs.

**Rejected — assign them to the nearest unit.** The same objection as in D6: it
attributes a casualty to a place where it did not happen, and at this stage it
would do so invisibly, after the record has already survived every other check.

**Rejected — a residual "unknown unit" row in the matrix.** It would keep the
totals whole, at the cost of a row that is not a place and cannot carry any of
the urban predictors the matrix exists to be regressed against.

---

## D12 — Figures are drawn from the exported tables, on a shared logarithmic scale

**Kind:** Implementation.

**Status:** Closed.

**Built:** Yes.

**Context.** Three separate decisions about the heatmaps, all with the same
motive: a figure that disagrees with the table it illustrates is worse than no
figure, because it is believed.

**Decision.**

*Figures read the exported files back from disk.* No figure recomputes anything
from the in-memory table. What is seen and what is analysed are the same numbers
by construction, not by care.

*One colour scale across all years within a count.* Per-year scaling would let
two heatmaps look comparable while being drawn to different rulers, which is the
most quietly misleading thing a series of figures can do. The aggregate figure is
excluded from that shared scale on purpose: it covers eighteen years at once and
is not comparable to a single year, so pretending otherwise would be the same
error in reverse.

*Logarithmic colour scale with the values printed on the cells.* The counts span
from single digits to thirty-five thousand. On a linear ramp everything except
the dominant cell collapses into one shade. The logarithm restores the structure
and the printed numbers restore the exact values the logarithm blurs. Zeros
cannot go on a logarithmic ramp at all, so they are drawn in a flat grey rather
than at the bottom of the ramp, where they would read as a small value instead of
none.

**Rejected — a linear scale with a clipped maximum.** It hides the dominant cell
instead of showing the rest, and the clipping point becomes an arbitrary editorial
choice buried in the code.

---

## D13 — Output layout separates analysis tables from presentation tables

**Kind:** Implementation.

**Status:** Closed.

**Built:** Yes.

**Context.** The stage emits one table meant to be fed to models and fifty-seven
meant to be read by people. They are the same numbers in different shapes, and
the cross-tabulated ones are the easy mistake: a matrix with actor types as
columns looks like a modelling table and is not one.

**Decision.** The file name says which is which before anyone opens it. The long
table for models is prefixed `analysis`, every cross-tabulation is prefixed
`presentation`, and each name carries its count and its year. Cross-tabulations
by year live in their own subdirectory so that the top level of the data folder
holds one analysis table and three aggregate views, not sixty files.

Row and column order is fixed in configuration rather than taken from whatever
the grouping returns, so two runs can be diffed line by line.

**Rejected — one file with everything and a column to filter on.** It is what the
long table already is. The presentation tables exist precisely because that shape
is unreadable.

**Extended by D25.** A third prefix, `reference`, for a table that describes the
variables instead of measuring anything. Two prefixes were enough while every
output was numbers.

---

## D14 — Pictograms in pipeline figures: tried and reverted

**Kind:** Implementation.

**Status:** Closed by reversal. The pipeline emits text-labelled figures only.

**Built:** No, and no longer present. It was built, reviewed on the rendered
output, and removed.

**Context.** The aggregate matrix was given a presentation figure whose axes were
labelled with pictograms — a pedestrian, a bicycle, a motorcycle, a car, a bus,
and markers for the residual and single-party categories — instead of category
names. They were drawn with plain geometric shapes in the figure code rather than
loaded from image files, so nothing had to be shipped, licensed or credited.

**Reverted, and why.** Looking at the rendered figure decided it. Pictograms
solve a problem the pipeline's figures do not have: they suit a page where the
reader meets the matrix once and needs to grasp it quickly, and the figures this
stage emits are working output, read next to their own numbers and alongside the
tables they come from. There the pictograms compete with five-digit values for
attention and remove the one thing a working figure must have, which is a label
you can read out loud and match to a column name in a file.

There is also a boundary worth keeping. The pipeline produces evidence; the
progress reports, the thesis and any article are where that evidence is
presented, and they have their own typography, their own icon set and their own
audience. Pictograms belong there, chosen for the page they sit on, not baked
into the pipeline where every figure would inherit them whatever it was for.

**Kept from the attempt.** Nothing. The pictogram code shared no logic with the
heatmaps beyond the colour scale, which already lived in the heatmap function, so
removing it left no gap to fill and no dead code behind.

**Recorded rather than deleted.** The choice was reasonable when it was made and
the reason it failed is not obvious from the outside — it comes from having seen
the output, not from an argument that could have been made in advance. Someone
proposing pictograms again in six months, quite possibly me, should be able to
find out that it was tried and what looking at it showed.

---

## D15 — The pipeline runs at UPL; the legacy figures become a historical contrast

**Kind:** Methodological.

**Status:** Closed.

**Built:** Yes. The active scale is UPL, and the loading stage is verified against
two different baselines depending on what each count actually measures.

**Context.** The study is specified at UPL by year (D7). The pipeline ran at
locality scale until now for one reason: that is the scale the legacy notebook ran
on, and reproducing its counts exactly was the evidence that the reimplementation
had not changed the logic it inherited. That evidence has been obtained, and it
does not need to be obtained again on every run.

Six counts characterise the loading stage, and moving scale splits them in two:

- **Four are properties of the source files** — 8,548 fatalities, 261,293
  injuries, 269,841 concatenated, 1,465,735 vehicle rows. No territorial layer can
  move them.
- **Two count the records that fall outside every polygon** — 61 fatalities and
  1,344 injuries at locality scale. These are properties of the *footprint* of the
  layer. The UPL layer covers different territory, so they necessarily differ, and
  they do: **50 and 1,186**.

**Decision.** Keep both, and label them for what each one is.

The legacy figures stay in the code as a **historical contrast**, explicitly
recorded as measured at locality scale. The four source counts are still checked
against them on every run at any scale, because reproducing them is what says
loading changed none of the inherited logic. The two footprint counts are only
compared to them when the run is at locality scale.

Alongside them there is now a **live reference**: the footprint counts measured on
this implementation for each scale. UPL is declared at 50 and 1,186, and from now
on that is what a run is checked against. A scale with no entry yet reports its
figures as a first measurement instead of failing, and they are recorded
afterwards.

**Rejected — delete the legacy baseline now that the scale has moved.** It is the
evidence that the reimplementation reproduced the pipeline it replaces. That
result was obtained once and does not stop being true because the study moved
scale; deleting it would leave the claim in the documentation with nothing behind
it.

**Rejected — keep a single baseline and update its two footprint numbers to the
UPL ones.** It would silently turn a comparison against the legacy pipeline into a
comparison against myself, under the same name. The two say different things and
must not share a label.

**Rejected — drop the footprint counts from verification entirely, as
scale-dependent noise.** They are the only automatic check that the unit layer is
the one the run thinks it is. A layer swapped for another with a different
footprint would otherwise pass every check in the pipeline.

**What moved with the scale, measured.** Everything upstream of the spatial join
is unchanged, which is the expected result and worth stating as one: the party
model, the two-party threshold and the counterpart resolution do not know what a
polygon is. On the extract those figures were measured on, 198,311 affected
parties, 15,014 discarded crashes and 169,098 surviving crashes were identical at
both scales. What changes with the scale is only what geography touches: 701
parties left for lack of a unit instead of 858 (D11), the matrix carried 197,610
parties instead of 197,453, and the grid grew from 14,364 cells to 22,680 with a
third of them at zero instead of under 30% (D10). Those counts have since moved
again, for a different reason: 2024 was replaced (D19), and the current figures
are in the verification report.

---

## D16 — One entry point, one route per way of running the pipeline

**Kind:** Implementation.

**Status:** Closed.

**Built:** Yes. `src/run_pipeline.py` is the only way the pipeline is started.

**Context.** Each stage module carried its own `main()`, so `python -m src.matrix`
ran everything and `python -m src.loading` ran the first stage. Three entry points
that had to be kept in agreement, and no way to ask for anything other than what
each of them happened to do. The pipeline is about to grow two more things to run
— ρ(t) and the static predictors with their figures — and that pattern does not
survive them.

**Decision.** One module, one command, and a route for each way of running the
pipeline. A route is a name, a one-line summary and a function taking the run log;
adding one means writing that function and adding one entry to the registry, after
which the command line, the help text and the run directory follow with nothing
else to touch. The stage modules keep their stage functions and no longer have a
`main()`, so there is exactly one place where stages are chained.

Three properties are deliberate:

- **Every route gets its own run directory**, as before. A partial run is a run and
  leaves the same audit trail as a complete one.
- **The intermediate dump switch is a command-line flag**, `--dump-intermediates` /
  `--no-dump-intermediates`, overriding the configured default for that run only.
  Turning on a debugging aid should not be a source edit that can be committed by
  accident, which is exactly what had just happened to that switch.
- **Running with no arguments runs the full pipeline and says so**, listing the
  routes available. A pipeline that answers a bare invocation with a usage error
  is being pedantic about something it can perfectly well decide.

**Rejected — a route flag on each stage module.** Same duplication, spread thinner,
and it leaves no single place that shows what can be run.

**Rejected — one route per stage, composed on the command line.** It reads well
until a stage needs the output of two others, and then the composition has to know
the dependency graph. Routes are named paths through the pipeline precisely so the
dependencies stay in Python where they can be typed.

---

## D17 — ρ(t) is computed from the party universe, on unordered pairs, with the denominator always beside it

**Kind:** Methodological.

**Status:** Closed.

**Built:** Yes, as its own route. It produces one long table, two city views and
eleven figures, and it verifies itself before reporting anything.

**Context.** ρ is a diagnostic of the sources, not a result of the study. For a
pair of actor types it is the share of two-party crashes in which *both* parties
suffered casualties. Whether both sides of a collision come out of it hurt is
close to physical, so a sharp change between two consecutive years is evidence
about recording practice rather than about crashes. That is worth having because
the panel runs over eighteen years of a source that was not built to be a time
series.

Five choices had to be made, and they are all in the same direction: keep the
thing measurable and keep the reader able to see how much is behind each number.

**Decision — it reads the party universe, not the matrix.** The denominator counts
crashes in which only one party was affected, and the matrix cannot see those: once
a party without casualties has been dropped, a crash where one side was hurt is
indistinguishable from one where both were. ρ is therefore computed before that
filter, from the same party universe the matrix is built on, and it is not
derivable from any exported matrix. This is also why it is only measurable at all
here: the inherited pipeline collapsed each crash to a single row and destroyed the
information ρ needs.

Worth stating plainly, because it changes how the number reads: every crash in the
sources has at least one casualty, since that is what put it in the sources. One of
the two parties is therefore always affected, and ρ is really asking how often the
*other* one was too.

**Decision — the pair is unordered, and the nine pairs are derived from a rule.**
A motorcycle struck by a car and a car struck by a motorcycle are the same crash,
and "were both parties hurt" is a property of the event with no direction in it. So
each pair has exactly one representation, ordered canonically from the least
protected mode to the most, and there is no orientation to get wrong — the same
reason D6 gives for the matrix pair. The nine come from two rules rather than a
hand-written list: at least one side must be a motorcycle, a car or public
transport, and the other side is any of the five modes, with a mode against itself
excluded. Deriving them means the rules are the only thing to maintain, and a tenth
pair appearing in the output raises instead of being exported.

The residual category is excluded. It is a bag of unlike vehicles — heavy cabs,
rail, animal traction, unidentified — and a rate over it would average things that
have nothing in common. A mode against itself is excluded because the question is
about the interaction between two modes and there is only one mode there.

**Decision — both levels of aggregation in one table, distinguished by a column.**
Per unit and year, and for the whole city by year, in the same long table with an
explicit level column. The city value is the sum of numerators over the sum of
denominators — pooled, not the average of the unit values. The two are different
quantities: pooling weights every crash equally, while averaging the cells weights
every cell equally and so lets a cell of three crashes count as much as one of
three thousand. Measured over these sources the gap is **city 0.194 against 0.179
for the mean of the unit-year cells**, and up to **0.094 for a single pair**
(bicycle–motorcycle), which is why they cannot be used interchangeably.

City rows carry a code of their own rather than an empty unit column, so the key is
never null and a join against the matrix cannot match them by accident. Which level
a row belongs to is read from the level column, not inferred from what the unit
code looks like.

**Decision — an empty denominator makes ρ undefined, never zero.** With no crash of
that pair there is nothing to take a share of, and a zero would read as "both
parties were never hurt", which is a measurement rather than the absence of one.
The grid is complete in the sense of D10 — 31 × 18 × 9 = 5,022 rows, every unit,
year and pair present — but the cells with no crash carry a zero denominator and an
empty ρ. **275 of the 5,022 cells are in that state.**

This one is worth flagging because it is easy to reintroduce. Reshaping the city
table with an aggregating pivot sums an all-empty cell into a confident 0.000; the
export uses a plain pivot, which cannot, and which also raises if the one-row
assumption behind it ever breaks.

**Decision — nothing is filtered by how thin a cell is, and nothing is marked for
it either.** With 30 units, 18 years and nine pairs, **1,958 of the 4,860 unit-year
cells (40.29%) rest on fewer than ten crashes** and the median cell has thirteen. A
ρ of 1.000 built on two crashes is not a finding. The answer is not to hide those
cells, which would silently change what the table covers, but to make the
denominator impossible to miss: it travels beside ρ in every row of every export,
in the panel titles of the figures, and as its own figure for the city.

**Revised, at my advisor's instruction.** The figures used to draw points with
fewer than ten crashes behind them as hollow markers. That is gone. No cut by
number of events of any kind, not in the data and not by eye: a value resting on
two crashes is as much the measurement as one resting on two thousand, and marking
it differently is an editorial judgement applied inside the figure. **The only gap
in a line is a year where the denominator is zero**, because there ρ does not
exist. The ten-crash figure survives as a reporting statistic in the run log and
nowhere else.

**Rejected — a minimum denominator, below which the cell is dropped or blanked.**
It buries the sparsity instead of showing it, and the threshold would become an
editorial choice hidden in the code that every downstream consumer inherits without
knowing.

**Decision — crashes with no territorial unit leave, as in D11.** The city total is
the sum over the units, so a crash the units cannot hold cannot be in the city total
either. It costs 320 crashes of 109,101.

**Figures — small multiples rather than nine lines.** Nine simultaneous series
cannot be told apart by colour, and the question the figure is asked is whether a
given pair moves between two years, which is about one series at a time. So the
city figure is nine panels on one grid with a common vertical scale, its
denominators are a second figure on the same layout rather than a second axis on
the first, and the unit figures are one per pair with thirty panels each, every
panel carrying the city curve behind it as a common reference. That is eleven
figures instead of two hundred and seventy series.

---

## D18 — The 2007 vehicle table does not distinguish the two parties of a vehicle–vehicle crash

**Kind:** Methodological. It decides what the first year of the panel can be used
for.

**Status:** **Open.** To settle with my advisor.

**Built:** Detection only. ρ makes it visible and the run names the year-pair
combinations that have no crash at all; nothing acts on it.

**Context.** ρ found it on its first run. **In 2007, six of the nine pairs have a
denominator of exactly zero for the whole city** — every pair between two vehicles.
Only the three pedestrian pairs have any crashes at all. That cannot be a property
of traffic.

Measured on the sources, in 2007 **4,040 of the 4,098 crashes with two vehicle rows
carry a single vehicle class between them (98.6%)**, against 19.9% in 2008 and
13.4% in 2015. Among two-party crashes with no pedestrian, **87.9% have both
parties of the same type in 2007**, against 13% to 22% in every other year of the
series.

The reading that fits is that the 2007 extract repeats the class of one vehicle on
the other party, so a motorcycle–car crash is recorded as car–car or
motorcycle–motorcycle. It is consistent with what the matrix already showed without
anyone noticing: the 2007 matrix has zeros in every cell between two different
motorised modes, and inflated diagonals — 1,516 car-by-car, 910
motorcycle-by-motorcycle, 377 bicycle-by-bicycle against 7 the following year.

**What this affects.** Only the counterpart of vehicle–vehicle crashes in 2007.
Pedestrian pairs are unaffected, since the pedestrian is a party in its own right
and does not come from the vehicle table. The casualty counts and the totals are
unaffected: nothing is lost, the counterpart is mislabelled. It is one year of
eighteen, and it is the first of the panel.

**Options on the table.**

- Drop 2007 from the panel, or from any analysis that uses the counterpart of a
  vehicle–vehicle crash, and say so.
- Keep 2007 for pedestrian pairs and for totals, and treat the vehicle–vehicle
  counterpart as missing for that year.
- Check the 2007 extract against another source before deciding whether it is the
  extract or the original that is wrong.

I am not choosing. What is built is that the run reports it: the year-pair
combinations with no crash in the whole city are named one by one, so this cannot
be scrolled past.

---

## D19 — The most recent extract prevails, whole year at a time

**Kind:** Methodological.

**Status:** Closed, and general. It is the rule for every future update, not a
decision about one file.

**Built:** Yes, as the `integrate` route. It rebuilds both casualty layers with
the replaced year taken from the updated extract, writes them to `data/integrated/`
and leaves the sources on disk untouched.

**Context.** A later extract of 2024 arrived, covering the whole year. The injury
layer of the original extract stops on 19 September 2024: September holds 178
records against a monthly median of 1,760 for that year, and October, November and
December hold none at all. The 2024 the pipeline had was two thirds of a year
presented as a whole one, and it looked like a 33% fall in casualties — a
plausible-looking number that nobody had reason to question.

The two extracts do not merely differ in length. Over the 15,566 people present in
both, they disagree on the crash type of one, the role of six, the vehicle
reference of three, the age of 59, and the position of 766, of which 142 move more
than 100 m and four more than 10 km. 28 people present in the original extract are
absent from the updated one, and six people it recorded as injured are recorded as
dead, with a date of death after the original extract was taken.

**Decision, with my advisor.** **Where two extracts describe the same record, the
more recent one prevails, and the replacement is done a whole year at a time.**
Concretely, for 2024:

- Every 2024 row of both layers is replaced. Not merged, not completed: replaced.
  The alternative — adding only what is missing — would have duplicated 15,566
  people, and picking field by field which extract to believe would mean inventing
  a record that neither source contains.
- **The 28 people who disappear are accepted.** They are not recovered, not carried
  forward, and not treated as an error to correct. If the updated extract does not
  have them, the study does not have them.
- **The geometry of the updated extract prevails**, including the 142 points that
  move more than 100 m. Five records that were inside a unit fall outside every
  unit under the new positions; they join the unlocated set that D6 and D11 already
  handle, and the integration counts them separately so that the increase is
  visibly a consequence of the change of extract and not a regression.
- **Severity comes from `MUERTE_POS`**: present means the person died. Verified
  against the previous extract — all 543 people already known to be fatalities
  carry it, and no person known to be injured does, apart from the six who died
  afterwards. It is a rule about this file rather than about the format, since the
  same column is null on 35% of the rows of the original fatality layer.
- **`CONDICION` remains the role column**, not `CONDICION_`. The latter reclassifies
  2,567 passengers as motorcyclists and 151 as cyclists, which is real information
  about the gap D9 describes, but it is a derived column whose provenance is not
  documented and it changes vocabulary between extracts (`ACOMPAÑANTE` became
  `PASAJERO`). Noted, not adopted.

**How it is built, and why that way.** The originals are never written to. The
route produces new layers beside them and one switch, `USE_UPDATED_2024`, decides
what every stage reads. Reverting is that one line, which matters because an
integration is exactly the kind of change that has to be undoable while the reason
for undoing it is still being argued about.

Three details of the incoming file are each a way to lose records in silence, so
each is converted explicitly and then checked:

- The geometry is WKT with no CRS declared anywhere. It is read as EPSG:4686,
  which is the frame under which 95% of the people present in both extracts land
  on exactly the same coordinates.
- The identifiers are typed differently from the shapefiles — the person code
  arrives as an integer where the layer holds text. A merge on mismatched types
  does not raise, it matches nothing, and it did exactly that once while the file
  was being inspected. Every column is now cast to the type of the layer it joins,
  the run stops if any of them still differs, and it stops again if the converted
  person codes stop finding their counterparts in the previous extract.
- The actor type of a casualty comes from the vehicle it rode. A vehicle reference
  that stopped resolving would lose no rows at all: it would quietly retype every
  2024 casualty as a party of its own. The rate is measured against the year before
  — 99.51% against 100.00% — and a collapse stops the run.

**The balance, with the causes kept apart.** The fatality layer goes from 8,548 to
8,592 rows and the injury layer from 261,293 to 268,921, and the record names the
2024 rows leaving and the 2024 rows entering separately rather than as a net. The
28 accepted losses, the six people who changed severity, and the newly unlocated
records are declared as their own notes, because a net of +7,628 rows would hide
every one of them.

**What it changed beyond 2024.** Nothing in any other year, by construction, and
two things that were not expected:

- **The four people who appeared in both layers are gone.** They were all 2024
  records, and the updated extract has each of them once. The cross-layer
  duplication check now reports zero.
- **Because of that, the person identifier reverted on its own.** The source person
  code is now unique within a crash across the whole set, so the fallback described
  in D8 no longer applies and the pipeline uses the source code. That was built to
  reverse itself if the source was ever cleaned, and it did, without anyone editing
  it.

---

## D20 — The sources are checked for coverage, not only for arithmetic

**Kind:** Implementation.

**Status:** Closed.

**Built:** Yes, as the `completeness` route.

**Context.** The pipeline verifies its own arithmetic in detail: every stage
balances, every record lost carries a named cause, and a run that does not add up
stops. None of that noticed that a third of 2024 was missing, because nothing was
lost — the records were never there. The checks covered what the pipeline does to
the data and nothing about whether the data covers the period it claims to.

**Decision.** Measure it. For every layer, year and month, count the records and
report the months that are empty or that hold less than half of the median month
of their own year. Judged against each year rather than against a fixed count,
because the layers grow by a factor of two over eighteen years and any absolute
threshold would either excuse the recent years or condemn the early ones.

It reports and never filters. What a thin month means — a real drop, a change of
system, an extract taken mid-month — is a question about the sources.

**What it finds on the integrated sources.** One month: **April 2020, at 38.5% of
that year's median**, which is the strict quarantine and is a real drop rather
than a gap. No year has an empty final month.

Run against the original extract, it names the defect it was built for:
**September 2024 at 10.1% of the median, and October, November and December
empty.**

**Its blind spot, stated rather than discovered later.** A year that is uniformly
under-reported passes, because every month is thin in the same way and the median
moves with them. 2008 and 2009 are exactly that shape — 10,241 and 9,116 records
against 14,148 in 2007 — and no month of either is flagged. The year-on-year
column is what makes those visible, and it is printed beside the monthly table for
that reason.

---

## D21 — The desire lines are out until it is settled what they measure

**Kind:** Methodological. It decides whether a variable enters the study at all.

**Status:** **Open.** To settle with my advisor.

**Built:** No. The layer is not read, and it is absent from the predictor list
rather than present and filtered out later, so nothing downstream can pick it up
by accident.

**Context.** The origin-destination desire lines are one of the eleven single
snapshots, and on the face of it they are the most interesting of them: they are
the only variable in the set that describes how the city is *used* rather than how
it is built. Every other predictor is infrastructure.

The column they arrive in is not what its name says. The legacy code takes the
length of each line inside the unit, multiplies it by `f_exp` — the expansion
factor of the origin-destination survey, carried on each record — and writes the
product back over the kilometres under the same column name:

```python
inter["len_km_fexp"] = inter["len_km"] * inter["_fexp"]
grp["len_km"] = grp["len_km_metric"]      # the real kilometres are gone
```

Because `f_exp` varies from record to record — mean 625.8, range 323.8 to 1988.3 —
this is not a change of scale but a transformation. The result is neither
kilometres nor trips: it is a sum of kilometre-trips, and the raw kilometres and
the aggregate expansion factor are both computed and then dropped, so nothing
downstream can recover either. Verified numerically: the layer is 1,219.26 km long
and the exported column sums to 674,158.05.

**Why that makes it unusable here specifically.** A correlation matrix is a table
of relationships between quantities. A row for a quantity that has no unit is not
a weak result, it is an uninterpretable one: a reader cannot say what "desire lines
correlate at 0.6 with roadway share" would mean, because the left-hand side is not
a thing that has been measured. The same objection applies with more force once it
enters a model, where its coefficient would be reported in units that do not exist.

**Decision.** It stays out of this module and out of the correlation matrix. It is
excluded because of the ambiguity, not because it is unimportant, and the
distinction matters: the other four exclusions from this module — cycleways and
the three signage layers — are postponements, and this one is a question.

**Three defensible variables are hiding in that column, and the code produces a
fourth thing while labelling it the first.**

- **Kilometres of line inside the unit**, which is what the column name says and
  what the other three line layers actually hold. Comparable with them.
- **Number of trips crossing the unit**, the sum of `f_exp`, which is the survey's
  own estimate of volume and is probably what "intensity of bicycle travel" was
  meant to mean.
- **Kilometre-trips**, the sum of km times `f_exp`, which is exposure — distance
  travelled by bicycle inside the unit — and is a perfectly reasonable thing to
  want, but is not what the column is called and is not comparable to the other
  line layers.

All three are defensible; they answer different questions. What is not defensible
is producing the third and labelling it the first.

**Open.** Which of the three is the variable of interest. Once that is answered the
layer takes about as much code as any of the other line variables, and it joins the
module with the annual series.

---

## D22 — A predictor is measured against every unit, and a zero is an observation

**Kind:** Methodological.

**Status:** Closed.

**Built:** Yes, as the `predictors` route, for the ten static variables. The four
with an annual series are not written yet; the tables already carry the year column
they will fill.

**Context.** The predictor half of the study is a different kind of measurement
from the casualty half — no funnel of records, no counterparts, no severity — but
it has the same failure mode, and the inherited pipeline had it in three places at
once. All three make a unit disappear without saying so.

**Decision — one row per unit and variable, always.** Thirty units by ten variables
is 300 cells, and every one of them is written. In the legacy tables a unit the
layer never reaches has no row at all: `camaras_salvavidas` produces 24 rows and
`estacion_localidad` 23, so a histogram drawn from them has 24 and 23 bars' worth
of units and looks entirely normal. This is D10 applied to the other half of the
study, and it costs 14 cells here — 1 unit with no signalised intersection, 6 with
no speed camera, 7 with no TransMilenio station.

**Decision — "measured and found nothing" and "could not be measured" are
different, and they carry different values.** A zero means the measurement ran over
that unit and the feature is not there. A unit that could not be measured at all
carries a null and the status `NOT_MEASURED`, never a zero. The legacy output
expresses both as an absent row, which is exactly the confusion that makes an
absent row dangerous: Torca genuinely has no traffic lights, and that is a finding
about the northern edge of the city, not a gap.

On these layers every one of the 300 cells is measured, so the distinction costs
nothing today and exists for the day a layer arrives that does not cover the whole
city.

**Decision — a zero that could not be true is reported loudly.** Four variables are
declared as ones where a zero would mean the measurement failed rather than that
the feature is absent: sidewalk, arterial road, roadway and pedestrian crossings.
An urban planning unit with no carriageway is not a fact about Bogotá. The run
names any such zero and warns; it does not correct anything, because the answer is
to find out what went wrong and not to substitute a number. None fires on the
current layers, which is the intended state.

The other six are left out of that list deliberately. A unit with no park, no
bridge, no speed camera, no TransMilenio station, no bus stop or no traffic light
is unusual and perfectly possible, and flagging those would train me to dismiss the
warning.

**Decision — the normalisation is the area of the unit, for both families.**
Surfaces become a share of the unit, dimensionless and bounded by 1; point layers
become a density per square kilometre, bounded below and not above. Both come from
the geometry of the unit in EPSG:3116, not from the `AREA_HA` attribute the
shapefile carries, so numerator and denominator are measured in the same
projection. The two agree to within 0.08% where both exist; mixing them would make
a share of a unit slightly incoherent with itself for no gain.

Normalising is not optional here. UPL areas run from 6.52 km² to 53.82 km², a
factor of eight, so an unnormalised count would rank units by size before it ranked
them by anything else.

**Decision — what the measurement drops is counted, per layer.** The legacy point
join is an inner join, so points outside every unit vanish with no record; the audit
had to reconstruct the losses afterwards to find out they existed. Here every layer
reports what fell outside the units at the moment it is measured: 1,248 of 68,447
crossings (1.82%), 94 of 7,694 bus stops, 1 of 1,462 signalised intersections, and
for the surfaces the captured area against the layer total — 99.91% of sidewalk,
99.43% of roadway, 98.87% of parks, 99.93% of bridges.

**One of those numbers is not like the others.** Only **90.75% of the arterial road
surface** falls inside a UPL, against 98.9% or better for the other four. It is not
an error: the layer includes stretches of avenue beyond the perimeter of the units,
and the study universe is the 30 UPL of the layer (D7), so those stretches have
nowhere to go. It is worth stating because the arterial variable is therefore
measuring a slightly different territory from the other four, and because a reader
comparing city totals against an official figure will find 9% missing and deserve
to know why.

**Rejected — writing only the units a layer reaches, as the legacy does.** Every
consumer would have to know the unit roster to tell a zero from a gap, and each
would reconstruct it slightly differently. The histogram is where this bites: it
would silently be a histogram of a different number of units per variable.

**Rejected — filling the unreached units with zero and saying nothing.** That is
the right value with the wrong provenance. It is right here because these layers do
cover the city, and it would be wrong for a layer that does not, with nothing in
the output to tell the two situations apart.

---

## D23 — The histogram bins and the correlation scale are declared, not inferred

**Kind:** Implementation.

**Status:** Closed. The binning rule was revised once, after looking at the
rendered figures; the earlier rule and why it was replaced are recorded below.

**Built:** Yes. Both are settings in the configuration, and both figures are drawn
from the exported tables read back from disk, as D12 requires.

**Context.** With thirty observations the choice of bins decides a good part of
what a histogram looks like, and the plotting library's default is a choice made
by someone who never saw this data. Leaving it to the default means the figure has
a parameter nobody picked and nobody can defend.

**Decision — bin edges fall on round numbers, at a step chosen for the magnitude
of each variable.** The step is a rung of the 1-2-2.5-5 ladder scaled to the
variable — 0.001, 0.02, 0.25, 5, 50 — and the edges are the multiples of that step
that cover the observed range. Of the rungs that yield between four and ten bins,
the one whose bin count is nearest six wins; ties go to the finer step, which hides
less. The ten variables come out at six to eight bins.

**Decision — the ticks of the horizontal axis are the bin edges.** Not the ticks
the library would choose. This is the point of the whole rule: an axis is labelled
at round values whatever the bars do, so edges at 0.098 and 0.197 put every bar
between two labels and leave the reader interpolating to find out what the bar
covers. With round edges *and* the edges as the ticks, a bar begins and ends on a
printed number and the range it counts is read off directly.

**Decision — an empty bin is drawn, not left blank.** A bin with no unit in it gets
a hatched stub at the axis and its own zero, printed where the other counts are.
Blank, it reads as the figure having failed. It is a finding: in the urban park
histogram the units stop at 0.12 of the unit and start again at 0.14, and that gap
between the twenty-seven ordinary units and the three park-rich ones is the shape
of the variable. The count of empty bins is stated in the note under the figure so
that the hatching is not a private code.

**Replaced — Sturges' rule, `ceil(log2(30)) + 1 = 6` equal parts of the observed
range.** It was the rule until the figures were looked at side by side with their
own axes. Six bins over thirty observations is a good target and remains the
target; what failed was cutting the *observed range* into six, which puts the edges
wherever the extreme values happen to fall. The bars and the axis labels then
disagree — the bars start at 0.0250 and 0.0463 while the axis is labelled 0.02,
0.04, 0.06 — and the figure looks misaligned even though every count in it is
right. Round edges keep the target and remove the disagreement.

The property that made Sturges' attractive was that n is fixed at thirty by D7, so
one rule gives one bin count for all ten figures. That is weakened, not lost: the
count now lands between six and eight depending on how a variable's range sits
against the ladder. It is worth the trade, because the alignment defect is visible
in every figure and the difference between six and eight bins is not something a
reader has to reconcile across figures that are, in any case, in different units.

**Rejected — Freedman-Diaconis, or any data-dependent rule.** Unchanged from the
first version of this entry, and the new rule is not a step towards it. F-D sets
the bin *width* from the spread of the data, so each variable is drawn to its own
resolution; here the data only picks a rung of a ladder that is the same for all
ten, and it picks it from the magnitude of the variable, which is exactly what has
to differ between a share bounded by 1 and a density reaching 355.

**Rejected — the library default.** It is a data-dependent rule with no name on it,
which is the same objection plus the inability to state in the thesis what was
done.

**Rejected — unequal-width bins, quantile or logarithmic.** Several of these
variables are strongly right-skewed — bridge deck has fourteen of thirty units in
its first bin — and variable-width bins would flatten exactly that. The skew is a
property of the city worth seeing, not a rendering problem to fix.

**Decision — the correlation heatmap is diverging and centred on zero.** Fixed at
−1 to +1 rather than scaled to the observed range, so that the colour of a cell
means the same thing in this figure as in any other drawn the same way, and so that
two variables moving together and two moving against each other cannot land on
similar colours. The value is printed on every cell, for the same reason D12 prints
them on the casualty heatmaps: a colour ramp shows the pattern well and the number
badly.

**Decision — both axes carry the readable label and the canonical name.** The short
label on one line, the name as it appears in the code and in the exported tables
underneath it, smaller and monospaced. The figure is read next to the CSV it came
from, and `Signalised junctions` does not say which of ten columns to open;
`SIGNALISED_INTERSECTION_DENSITY` does. The same pair of lines labels the master
table of D24, so the two figures are labelled alike.

**Decision — high pairs are reported, never dropped.** Pairs above 0.7 in absolute
value are named in the run log and exported as their own small table, because two
variables that correlate that strongly measure close to the same thing and putting
both into one model buys nothing and destabilises the coefficients of each. It is a
reporting threshold in the sense of D17's sparse denominator: nothing is removed
from any table because of it, and which pair to drop is a modelling decision, not a
plotting one.

---

## D24 — The master table is one figure, shaded column by column

**Kind:** Implementation.

**Status:** Closed.

**Built:** Yes, as `table__static_predictors.png` in the predictors route.

**Context.** Ten histograms show ten distributions and no unit; the correlation
matrix shows ten variables against each other and no unit either. Neither answers
the question the predictor half is for, which is what a given UPL is like across
all ten variables at once, and how it sits against the rest of the city. That
question is answered by the wide table, and until now the wide table existed only
as a CSV and as a block of monospaced text in the run log.

**Decision — the whole grid in one figure: thirty units by ten variables, every
value printed.** The same three hundred cells the wide table holds, in the order of
the unit code, with the variables in the configured order. Nothing is summarised
and nothing is dropped, because the figure exists to be read cell by cell as much
as at a glance.

**Decision — the colour of a cell comes from its own column.** Each column is
shaded from its own minimum to its own maximum. The variables span four orders of
magnitude — bridge deck at 0.0001 of a unit against 355 crossings per km² — so a
single ramp across the figure would paint every share at one end and every density
at the other, and the picture would show which family a column belongs to and
nothing else.

**This is the opposite of D12's rule, deliberately, and the figure says so.** D12
puts the casualty heatmaps on one shared scale precisely so cells can be compared
across the figure. A reader who carries that habit here would compare a dark cell
in one column against a dark cell in another and conclude something false. Two
devices guard against it: a note under the title stating that colours are
comparable down a column and never across, and the minimum and maximum of each
column printed at its foot, which says what the palest and the darkest cell of that
column actually mean. The second one matters more — it makes the scale checkable
instead of asserted.

**Decision — the number of decimals comes from the top of each column.** About
three significant digits at the column maximum: four decimals for bridge deck, one
for bus stop density, none for pedestrian crossings. One decimal count for all ten
either prints `355.3447` or rounds bridge deck to `0.00`, and with three hundred
numbers on one page, readability is the whole point of printing them.

**Rejected — a figure per variable, or a small multiple of thirty maps.** Both
exist in some form already: the histograms are the per-variable view, and a map is
a different project with its own decisions about classification and colour. What
was missing was the join of the two axes in one place, which is a table.

*Superseded in part by D26.* The half of this that says a map brings its own
decisions still holds; what no longer holds is that those decisions had nowhere to
be made. They are made in D26, and the pipeline draws a reference map of the
units. The small multiple of thirty thematic maps rejected here is still rejected.

**Rejected — normalising the values themselves and printing z-scores.** That would
make one colour scale legitimate across the whole figure, at the cost of printing
numbers that appear in no exported table. The point of this figure is to show the
measured values; a reader who wants comparable magnitudes has the correlation
matrix and, later, the model.

---

## D25 — The predictor declaration is what the code runs on, and it is exported

**Kind:** Implementation.

**Status:** Closed.

**Built:** Yes. Every static predictor is declared in `config.StaticPredictor`, the
measurement reads that declaration, and it is exported as
`reference__static_predictors_dictionary.csv`.

**Context.** The code is in English and the delivered data is in Spanish. Going
from `ARTERIAL_ROAD_AREA_SHARE` to the `avenidas_corregidas` layer, and from there
to the file it came out of, meant reading the measurement and deducing it. That
chain has to be written down somewhere, and the only question was where.

**Rejected first, because it is the obvious answer — comments.** A comment drifts
from the code without anyone noticing, which is precisely the defect the audit
found in the inherited notebook: a text cell described a rule for ordering the
pair that the code never implemented, and the cell was right about the intention
and wrong about the program for as long as anyone had read it. Documentation the
code does not depend on cannot be trusted, however carefully it is written.

**Decision — one structured declaration per variable, and the code runs on it.**
Each variable declares its canonical name, its readable label, its source layer as
the data names it, the file inside that layer, the geometry, the measurement
method, what it measures, its time coverage and whether a zero would be
implausible. Four of those fields are load-bearing:

- **the source layer and the file build the path.** There is no path written
  anywhere else, so a wrong layer name raises a missing file instead of quietly
  measuring something else.
- **the geometry picks the folder and is checked against the file.** The layer is
  read, its geometry types are compared with the ones the declared kind admits,
  and a disagreement stops the run. Declaring a point layer as a surface fails on
  contact with the data rather than producing a plausible number.
- **the method selects the function that computes the variable.** The dictionary
  entry and the code that produces the number are chosen by the same key.
- **the time coverage is checked against the table.** All ten declare themselves
  snapshots, and a check confirms that no row of a snapshot variable carries a
  year.

Everything a variable can say about itself is therefore either used by the
measurement or checked against its output. That is the whole point: this is not a
description of the pipeline, it is what the pipeline reads.

**Decision — the sentence describing a computation belongs to the method, not to
the variable.** Ten variables are measured by two methods, so a sentence per
variable would be the same text written five times, and five copies drift
separately. The sentence sits on the method, beside the units it produces, and the
key that selects the sentence is the key that selects the function. The exported
dictionary still carries the sentence on every row, because a table a reader has
to join to itself is worse than a repeated string.

**Decision — the family is derived from the geometry, not declared beside it.**
`PREDICTOR_FAMILY` still reads AREA and POINT in the exported tables, exactly as
before, but it is now computed from the declared geometry. Two fields that must
always agree are one field.

**Decision — the dictionary is exported, under a prefix of its own.** D13 splits
the outputs into tables for models (`analysis`) and tables for reading
(`presentation`). The dictionary is neither: it measures nothing and describes the
variables the other tables measure. It goes out as `reference`, a third prefix,
because filing it under either of the other two would make that name mean two
things. It carries `PREDICTOR`, `PREDICTOR_FAMILY`, `MEASURE_UNIT` and `VALUE_UNIT`
under the same names and with the same values as the measurement tables, so the
dashboard joins it to them on the variable name.

**Decision — the declaration is checked against the tables at the end of the run.**
Four checks, alongside the twelve already there: every declared source file exists
on disk; the set of declared variables and the set of measured variables are the
same, so there is no orphan entry and no undeclared variable; the dictionary covers
every predictor column of the wide table; and the units in the dictionary agree
with the units in the long table, which the first three would not catch. The
dictionary and the wide table are read back from disk for this, as D12 requires of
anything that checks an exported artefact.

**Extending it — the four variables with an annual series.** Adding one is a new
entry with `time_coverage=ANNUAL_SERIES_COVERAGE`, and for the cycleway and
horizontal signage layers a `line` geometry, whose folder and geometry types are
already declared because the delivered data already has that folder. What is not
there is a method for measuring a line layer: adding it means one entry in
`MEASUREMENT_METHODS` with its sentence and units, and one function bound to that
key. No placeholder was left behind for it — a method described in the
configuration and bound to nothing fails at the variable that declares it, which is
the correct behaviour and not a gap to pre-fill.

**Out of scope, deliberately.** Only the predictor variables. The vehicle type
mapping (D4) already carries the Spanish-to-English equivalence for the road user
types and is declared the same way — exhaustively, in the configuration, used by
the code — so there is nothing to fix there.

---

## D26 — The pipeline draws the map, as a reference map in four colours

**Kind:** Implementation.

**Status:** Closed. Reverses the exclusion D24 made.

**Built:** Yes, as the `map` route, writing `map__territorial_units.pdf`.

**Context.** D24 turned a map down among the alternatives it rejected, on the
grounds that a map is a different project with its own decisions about
classification and colour. That was true, and it is no longer a reason to leave it
out, because those decisions can be made and are made below. What changed is the
demand: both documents need the reader to see the geography before any result
means anything. The informe final says so in its own section 3.2, and the
presentation opens on the study universe. A reader who does not know Bogotá cannot
weigh a rate per unit without knowing what the units look like, and with units
running from 6.52 to 53.82 square kilometres the shapes carry as much as the count.

**Decision — the pipeline draws it, from the layer every other stage reads.** Not
from the copy of the official cartography that also sits in the repository. Drawn
from `UnidadPlaneamientoLocal.shp` through the same loader, the figure shows the
thirty units of the study *by construction*: same file, same universe check, same
CRS handling. Drawn from a second copy it would show thirty units only for as long
as whoever produced it filtered correctly, and nothing would catch it if they did
not.

**Decision — it is a reference map, not a thematic one.** This is the decision the
rest follow from. A reference map shows the shape of the territory and how it is
divided; a thematic map shows a variable over it. Nothing here is measured and
nothing is classified, so the fill carries no information: it says only that this
unit is not that one.

**Decision — four colours, not thirty.** The first version gave every unit a
colour of its own, from a palette of thirty spread around the hue circle, assigned
by a search that maximised the contrast between neighbours. It was the wrong
instrument. A qualitative palette of one colour per category is built for
categorical data, where a colour means something; here there is no category and no
meaning, so thirty hues are thirty hues of noise, and the map competes for
attention with the argument it exists to support. The convention on a reference
map is the *fewest* colours that separate neighbours, and the four colour theorem
says four is enough. The adjacency of the thirty UPL is computed from the
geometries and coloured by DSATUR, which finds four on this layer over
seventy-four borders. Five would have been acceptable; the run reports how many it
used, and a check fails if any two units sharing a border share a colour.

**Decision — ColorBrewer Pastel2, and hairline borders in one colour.** Pastel2 is
the pastel form of Set2, the qualitative family built to survive colour blindness,
and it is unsaturated, which is what a background should be. With the fill
separating the units the stroke has nothing left to do, so it is a hairline in a
single grey. The first version needed a heavy white border *and* a dark silhouette
precisely because its fills were fighting each other; fixing the fill removed the
need for both.

**Decision — identity is the unit code, printed inside the unit.** Colour cannot
carry identity when four colours cover thirty units, and it should not: a legend
of thirty entries beside a map of thirty units is a lookup table pretending to be
a figure. The number is the UPL code without its prefix and without a leading
zero, because the narrowest unit is 6.52 km² and a character that carries no
information is a character that does not go in.

**Decision — the label sits at the pole of inaccessibility.** The centroid is out:
on a polygon shaped like a crescent or an L it falls outside the polygon
altogether, and several of these units are shaped exactly like that.
`representative_point` fixes that much, and it was the first choice for that
reason, but it answers the wrong question. It returns *some* interior point, and a
label needs the interior point with the most room around it, which is the pole of
inaccessibility: `shapely.ops.polylabel`. On this layer the difference decides the
figure. `representative_point` leaves as little as 438 m of clearance, on a unit
where it lands in a neck, against never less than 932 m for the pole. At 7 pt that
is five labels crossing their own borders against none.

**Decision — the font size is the largest the geometry allows, and it is
checked.** The check compares each label's rendered box against its own polygon in
data coordinates, and names the units that spill. Measured, not estimated:
estimating from the area would credit a 6.52 km² unit with 2.5 km of room in every
direction, which is true of a square and false of everything on this map. Because
the test is a ratio of font to figure, the largest font that passes is also the
largest the number will be once a document scales the figure down. On this layer
that ceiling sits between 7 and 8 points against a five inch figure.

**Decision — the north arrow and the scale bar come from libraries.**
`matplotlib-map-utils` for the arrow, which is what the GeoPandas documentation
points at, and `matplotlib-scalebar` for the bar. Neither is drawn by hand. The
scale bar states a real distance and can only do that where the coordinates are
metres, which fixes the map's CRS at EPSG:3116, the one the pipeline already uses
for every area it measures. Both are drawn in the colour of the labels, with the
arrow's two-tone form and drop shadow off: their defaults make the furniture the
loudest thing on the page.

**Decision — the arrow goes in the upper left.** Bogotá's footprint leans to the
north east, so the upper right corner of the figure is over the city and the
arrow sat on top of Torca. At that latitude the left side is empty.

**Decision — the scale bar goes in a second copy of the figure, not in the only
one.** Every run writes both, and a document includes whichever it needs. A map
reproduced at the width of a page can carry a scale bar and one shrunk into a
slide cannot: at that size the bar's own label falls below what a projector
resolves, and it earns its place by supporting a claim about distance, which the
presentation does not make and the informe final does. Two files rather than a
setting, so producing the other variant is never a matter of editing the
configuration and running again — which is the failure mode that leaves two
documents disagreeing about which run they came from.

**Decision — vector, and transparent.** Every other figure the pipeline writes is
a PNG at 150 dpi, which suits figures dense with text and marks. This one is
almost all edges, and edges are what rasterising ruins. Transparent, so it carries
no white rectangle of its own onto a slide whose background is an image.

**Rejected — a legend, unit names, or a title inside the figure.** The caption of
the document that carries it says what it is, in that document's language, and a
title inside the figure would repeat it in the wrong one. Names would not fit, and
the code plus a table is how a reader gets from a number on the map to a name.

**Rejected — one colour per unit, assigned to maximise contrast between
neighbours.** Built first, and described above. It is recorded here rather than
quietly deleted because it is the kind of thing that looks like the obvious answer
until the question "what does this colour mean" is asked out loud.

---

## D27 — A figure the document draws itself gets its data exported for it

**Kind:** Implementation.

**Status:** Closed.

**Built:** Yes, as `presentation__rho_city_rho__by_year.dat` in the rho route.

**Context.** Two kinds of figure now exist. Most are drawn by the pipeline and
copied into a document as images. A few are drawn by the document itself, in
LaTeX: the casualty matrices as native tables, and now the city series of ρ with
`pgfplots`. The reason is the same in both cases and is recorded in the style
rules of `deliverables/plan.md`. A native figure is legible at any size, inherits
the document's typeface, and is corrected by changing a number in the source
rather than by rebuilding an image.

That reason has a cost, and this decision is about the cost. A native figure whose
numbers are typed into the `.tex` is a copy of a run, and it drifts from that run
the moment anything upstream changes. These numbers have already moved three
times.

**Decision — the pipeline exports the series the document plots.** The rho route
writes the same city view it already exports as a CSV a second time, in the shape
`pgfplots` reads. The document points `\pgfplotstableread` at that file and every
`\addplot` names a column. No value is written by hand.

**Decision — it is a separate file and not a change to the CSV.** The CSV beside
it is what the dashboard joins, and its column names have to keep matching the
matrix, which is the point of D13's naming discipline. The `.dat` differs from it
in exactly two ways, both forced by its only reader being LaTeX:

- The pair separator becomes an underscore. `pgfplots` addresses a column by name
  inside a key-value list, and a hyphen there is fragile.
- An undefined ρ is written out as `nan` rather than left as an empty field. An
  empty field between two separators reads as a zero, and a year in which a pair
  had no crash at all is not a year in which nobody was hurt. The axis is set to
  break the line at those points instead of drawing through them.

**Decision — all nine pairs go out, whatever a given figure plots.** The
presentation draws five and the informe final will draw nine. Exporting only what
one figure needs would mean re-running the pipeline to redraw it.

**Decision — a check reads the file back.** Both things that can go wrong here are
silent: a value rounded away by the printed precision, and an undefined ρ arriving
as a zero. The check compares the file on disk against the series it came from,
cell by cell, and confirms the gaps are still gaps. That is what D12 asks of
anything that checks an exported artefact.
