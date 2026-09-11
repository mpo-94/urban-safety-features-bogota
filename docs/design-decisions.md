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
| D21 | The desire lines are out until it is settled what they measure | Methodological | Closed; superseded by D35 | No, superseded |
| D22 | A predictor is measured against every unit, and a zero is an observation | Methodological | Closed | Yes, for the ten static ones |
| D23 | The histogram bins and the correlation scale are declared, not inferred | Implementation | Closed; bin rule revised | Yes |
| D24 | The master table is one figure, shaded column by column | Implementation | Closed | Yes |
| D25 | The predictor declaration is what the code runs on, and it is exported | Implementation | Closed | Yes |
| D26 | The pipeline draws the map, as a reference map in four colours | Implementation | Closed; reverses D24's exclusion | Yes |
| D27 | A figure the document draws itself gets its data exported for it | Implementation | Closed | Yes, for the city series of ρ |
| D28 | The recording change is corrected against a 2023-2024 reference, pair by pair | Methodological | Closed | Yes |
| D29 | The deficit is drawn from the side carrying the surplus, by the reference composition | Methodological | Closed | Yes |
| D30 | 2007 is out of the corrected dataset altogether | Methodological | Closed | Yes |
| D31 | The corrected set never replaces the observed one, and both are labelled in the data | Implementation | Closed | Yes |
| D32 | The tree census enters whole, with two narrower variants measured beside it | Methodological | Closed on what is measured; which variant the models use is **open** | Yes |
| D33 | The tables the deliverables print are emitted as LaTeX, not transcribed | Implementation | Closed | Yes |
| D34 | The predictor figures come in two sets, and two variables are in neither | Implementation | Closed | Yes |
| D35 | The desire lines enter as exposure, apportioned by share of length | Methodological | Closed on the rule; the year and the selection are **open** | Yes |
| D36 | The population enters as a panel, one number per unit and per year | Methodological | Closed; the 2018 census is the only measured year and the rest are the city's projections | Yes |
| D37 | `data/` is filed by the role the data plays, and every root is declared | Implementation | Closed on the roots; where the exposure layers finally live is **open** | Yes |
| D38 | Exposure is built from the survey, per unit, year, mode and day type | Methodological | Closed for all five years; which day type the models take is **open** | Yes |
| D39 | The pedestrian mode is measured twice, and the series is read on the fifteen-minute one | Methodological | Closed | Yes |
| D40 | Exposure between survey years is interpolated as a rate, not as a level | Methodological | Closed on the method; 2005 joined the series on 2026-09-10 and the weekday held block is gone | Yes |
| D41 | The panel is compared against the casualty series, and that comparison is a diagnostic and never a constructor | Methodological | Closed on the diagnostic; the pandemic patch it left open is decided by D42 | Yes |
| D42 | The pandemic years are patched by the mirror assumption, at the city level, in a variant of their own | Methodological | Decided and built on 2026-09-10 | Yes |

Methodological decisions: D1-D7, D9, D10, D11, D15, D17, D18, D19, D21, D22, D32, D35,
D38, D39, D40.
Implementation decisions: D8, D12, D13, D14, D16, D20, D23, D24, D25, D26, D27, D33, D34.

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

**Status:** Closed. Superseded by **D35**, which answers the question this entry
left open and puts the layer in. The entry stays as written because the reasoning
for keeping it out was right at the time and the exclusion has to be explicable:
a reader comparing two runs will find the variable absent from one of them.

**Built:** No, and now superseded. The layer is read by the exposure module, not
by the predictor module, and it is still absent from the predictor list — for a
different reason, which D35 gives.

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

**Resolved by D35.** My advisor settled it: the variable is the trips, apportioned
by share of length, and it is exposure rather than a predictor. Two things this
entry got wrong are worth recording. The trips are **weekly** and not daily —
`ResultadoExp` is `f_exp` multiplied by the days per week the trip is made, which
the day-of-week flags confirm — so "the sum of `f_exp`" named the daily quantity
and the layer is built around the weekly one. And the fourth option this entry did
not list, counting the trip at its endpoints, turned out to be the one that does
not depend on a geometry the survey never measured.

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

---

## D28 — The recording change is corrected against a 2023-2024 reference, pair by pair

**Kind:** Methodological.

**Status:** Closed.

**Built:** Yes, in `src/correction.py`, route `corrected`.

**Context.** ρ(t) established that the source changed practice. Before 2018 a
crash entered the system with a single casualty recorded; from 2018 every
affected party gets its own record. What the diagnostic added, and what makes a
correction thinkable at all, is *what* was missing: not the crash, which was
always registered, but the casualty of the second party, and almost always the
protected one. The decomposition of each two-party crash into its three possible
outcomes — only the exposed side hurt, only the protected side hurt, both — is
what separated the two mechanisms. Had whole crashes been missing, the count of
crashes recorded with the protected side as the only casualty would have jumped
in step with ρ after 2018. It does not.

So the correction is bounded in a way that matters: it does not inflate a pair's
cell as a whole. It moves crashes from "one affected party" to "two" and credits
the party that the source failed to write down. That party is already in the data
— it took part in the crash and is carried through the pipeline precisely so the
counterpart of the other one can be resolved. Nothing is invented.

**Decision — one reference per pair, not a single factor.** A common factor was
tested and fails. ρ(2017) as a fraction of its reference is 0.49 and 0.58 in the
pairs where both sides are exposed, against 0.055 in pedestrian-car and
bicycle-car. The pairs where both sides are exposed were already near their
present level in 2018; the pairs facing a protected counterpart were at a quarter
of it. One coefficient cannot describe all nine, because what was being missed is
the casualty of the protected party, not "the second party" whichever it is.

**Decision — the reference window is 2023-2024.** This was the open question of
the session, and it was resolved against the obvious candidate. 2022-2024 was the
natural window and is wrong: 2022 is the last year of the climb, not the first
year of the plateau.

The evidence, in the order it settles the question:

- 2022 is the lowest of the three candidate years in seven of the nine pairs.
  Taken alone this proves little. Under independence the sign test gives
  p = 0.008, but the pairs are not independent — one city-wide shock moves all
  nine at once — and a permutation that treats the year effect as entirely shared
  cannot return anything below 1/6 = 0.167 whatever the data say. Failing to
  reach 0.05 there is a property of the design, not a finding, so the sign test
  cannot decide this either way.
- The statistic *can* be calibrated. Over the settled years 2010-2016, the
  deviation of the first year of a consecutive triplet from that triplet's mean
  ranges from −0.038 to +0.213 on the logit scale. 2022's is −0.101: lower than
  all five stable comparators, and the count of pairs where the first year is
  lowest is 7 against 1, 2, 3, 4, 4. On both statistics 2022 is as extreme as the
  design permits.
- What actually settles it is the shape of the climb. The common year-on-year
  increment of logit ρ, averaged over the nine pairs, is +0.376 from 2021 to 2022
  (2.20 standard deviations of a settled year, and every one of the nine pairs
  rises), +0.166 from 2022 to 2023 (0.97 sd, seven of nine rise), and −0.030 from
  2023 to 2024 (0.18 sd, three of nine rise). A decelerating ramp that flattens at
  2023. A year that is followed by a further climb has not reached the plateau,
  and 2022 is followed by one.

Including 2022 would have dragged the reference below the level the practice
actually reached, and would have done so in the pairs that had already arrived as
well as in the ones still climbing. Dropping it raises the reference by 1 to 14
per cent depending on the pair, most in bicycle-car.

The cost is declared: the plateau is now two years long, so the reference rests
on 2023 and 2024 alone. If a later extract shows ρ still moving after 2024, the
window is wrong and everything downstream of it moves. The window is a single
constant, `CORRECTION_REFERENCE_YEARS`, so revising it costs one edit and one run.

**Decision — the reference is calculated as pooled numerator over pooled
denominator.** Not the mean of the annual ρ. The years carry different numbers of
crashes and a mean of ratios would weigh a thin year like a thick one.

**Decision — a city reference, applied to every unit.** 40.9 % of the unit cells
carry fewer than ten crashes, so a factor cannot be estimated per unit; the
denominators are not there. The correction therefore assumes the change of
practice was homogeneous between units, which is reasonable if it came from a
change of procedure rather than from local habit, but it is an assumption and it
is stated as one. What follows from it in the arithmetic is that the deficit is
computed city-wide for each pair and year and then spread over the units in
proportion to the pool of convertible crashes each one holds.

**Decision — every year below the reference is corrected, pair by pair.** Not a
fixed cut at 2018. Each pair reached its ceiling at a different moment, and
leaving the intermediate years uncorrected would put a sawtooth in the series.
A pair-year already at or above its reference is left alone.

**Result.** 23,552 crashes reclassified, 133 of the 153 pair-years touched, all
30 units reached. The correction adds 15 to 21 per cent of affected parties in the
plateau years, decaying to 2.7 per cent in 2022 and nothing in 2023-2024, which is
the profile the mechanism predicts. Run `run_20260830_140246`.

---

## D29 — The deficit is drawn from the side carrying the surplus, by the reference composition

**Kind:** Methodological.

**Status:** Closed.

**Built:** Yes, in `correction.build_plan`.

**Context.** Knowing how many crashes have to move is not enough. A crash today
recorded with a single affected party is recorded as *which* party, and the
correction has to decide how many of the reclassified crashes come from each
side, because that determines which actor type gains the party and therefore
which cell of the matrix grows.

**Decision — the reference period's composition defines what a surplus is.** In
the reference window the practice is complete, so the composition of the three
outcomes there is the true one. In an under-recorded year, crashes that truly had
both parties affected appear as one side only. The surplus a side carries against
the reference composition is therefore the crashes on that side whose second
party went unrecorded, and that is where the reclassified ones come from.

The arithmetic is closed rather than approximate: the three shares sum to one in
both periods, so the two surpluses sum to the deficit exactly. Where one side's
surplus is negative — that side is under-represented against the reference — it
is clipped to zero and the whole deficit comes from the other, which keeps the
total whole. Both cases are checked against the pools before anything is moved.

**Consequence, and it is a check on the whole design.** The deficit comes almost
entirely from the pool where only the exposed side was recorded: 100 % in the
three pedestrian pairs, 92 to 99 % in the bicycle and motorcycle pairs against
cars, 66 % in car-public transport. So the party being added is overwhelmingly the
protected one — 13,828 cars, 8,403 motorcycles, 1,201 public transport vehicles,
against 120 bicycles and no pedestrians at all. That was not imposed. It falls out
of the reference composition, and it is the same conclusion the diagnostic reached
by a different route.

The pedestrian pairs are a special case worth stating plainly, because it limits
what they mean. A pedestrian is a party only by virtue of being a casualty: the
sources have no record of an unhurt pedestrian. So the "only the protected side
was hurt" outcome is structurally impossible there, the share is exactly zero in
all three pedestrian pairs, and ρ for them is not the same quantity as ρ for a
pair of vehicles. It is conditioned on the pedestrian having been hurt. The two
are not comparable and must not be read side by side as if they were.

**Decision — people come from the reference too, and the deaths are not rounded
away.** Adding a party means adding at least one person, since a party is affected
precisely because someone in it was hurt. How many comes from the mean people per
affected party of that actor type over the reference window, measured on the same
kind of crash, and injured and killed stay separate throughout.

The deaths needed care. The share of people killed is 0.11 % for a car occupant,
so a group of a few hundred promoted parties expects a fraction of a death and
rounds to none every single time. Rounded group by group the added deaths
disappeared: 139 instead of 153, a 9 % shortfall on the one count the whole design
goes out of its way not to bury. They are therefore allocated once per actor type
over all its promoted parties, weighted by the people each holds and capped by
them, so no party is credited with more deaths than occupants.

**Decision — which crashes inside a cell are chosen does not matter, and they are
chosen in a fixed order anyway.** Every crash in a cell shares its pair, its year,
its unit and the side that went unrecorded, so they are interchangeable for every
purpose the study puts them to. They are taken in order of crash identifier, so
the choice is reproducible and auditable rather than arbitrary at each run.

---

## D30 — 2007 is out of the corrected dataset altogether

**Kind:** Methodological.

**Status:** Closed.

**Built:** Yes: the year leaves before the plan is built and again before the
grid, each time with its own line in the funnel.

**Context.** D18 established that the 2007 vehicle table does not distinguish the
two parties of a vehicle-vehicle crash: 98.6 % of its crashes with two vehicles
carry a single class between them.

**Decision — 2007 is excluded from the corrected set, and the reason is not that
ρ cannot be computed for it.** ρ can be computed. The problem is upstream of ρ: a
year that cannot say which of two vehicles was which cannot support an inter-mode
matrix at all, corrected or observed. Correcting it would be putting a second
storey on a foundation that is not there.

It stays in the observed dataset, where it has always been, because the observed
dataset is the record of what the source says and 2007 is part of that record.
This is the one respect in which the two datasets do not span the same years, and
it is why the corrected matrix is built over its own year range rather than the
study period: materialising 2007 as a row of zeros would make a year with no
usable data look like a year in which nobody was hurt, which is exactly the defect
D10 exists to prevent.

**Consequence for the comparison.** Any check that compares the two totals has to
take 2007 off the observed side first, or the corrected set appears to have lost
11,414 affected parties. The verification does this explicitly rather than by
matching on the shared years and hoping.

---

## D31 — The corrected set never replaces the observed one, and both are labelled in the data

**Kind:** Implementation.

**Status:** Closed.

**Built:** Yes, in the `corrected` route.

**Context.** The correction rests on an assumption about homogeneity between
units and on a reference window resting on two years. It is a defensible estimate,
not a better measurement, and the models will have to be run against both to show
what it does and does not change. A pipeline that quietly replaced the data with
its corrected version would make that comparison impossible and would hide the
assumption inside a file name.

**Decision — one run produces both.** The two are built from a single reading of
the sources and a single party universe, so they differ by the correction and by
nothing else — not by a second run against a source that may have moved. That is
also what lets the verification compare them cell by cell, which is check four.

**Decision — the corrected set gets the same tables, the same matrices and the
same figures, in the same style.** It is going into a presentation, and an output
that has to be read differently from the original would not survive the trip.
What separates them is the name of every file and a column on every row, never
the shape.

**Decision — the dataset label travels in the data, not only in the file name.**
Every row of every exported table carries a `DATASET` column reading `OBSERVED` or
`RHO_CORRECTED`. A file name protects nothing once the file has been opened,
joined and passed on; a column survives all three. This is the guarantee that
nobody feeds a model the corrected set believing it is the observed one, or the
other way round.

**Decision — the observed files keep the names they already had.** Only the
corrected ones take the `__rho_corrected` suffix. Renaming both would have been
more symmetrical, but the observed tables already feed the dashboard, and breaking
every consumer to gain symmetry is a bad trade when the `DATASET` column already
makes confusion impossible.

**Decision — the correction itself is exported, not just its result.** Four
tables go out beside the matrices: the plan cell by cell, the city-level deficit
for every pair-year including the ones left alone, the reference ρ and
composition per pair, and the people-per-party rates per actor type. The
correction is an estimate, and an estimate that cannot be audited is a number
someone has to take on faith.

---

## D32 — The tree census enters whole, with two narrower variants measured beside it

**Kind:** Methodological.

**Status:** Closed on what the pipeline measures and on parks leaving the model
set. **Which of the three tree variables belongs in the final models is with my
advisor**, and the point of measuring all three is that he decides on figures
rather than on a description.

**Built:** Yes. `TREE_DENSITY`, `TREE_DENSITY_WITHOUT_P1` and
`TREE_DENSITY_U_CODES`, the eleventh, twelfth and thirteenth static predictors,
in run `run_20260831_011423`.

**Context.** The study needs a variable for the green surroundings of a street.
Until now that role was filled by `URBAN_PARK_AREA_SHARE`, the share of a unit
covered by park, which was in the model set from the beginning because it was the
only green layer delivered. The tree census arrived afterwards and covers the
same ground far more directly.

The two are not interchangeable, and the reason is mechanical rather than
statistical. What the literature attributes to street trees is visual narrowing:
a driver reads a carriageway lined with trees as tighter than it is and slows
down, and the trees also separate the footway from moving traffic. None of that
happens at the edge of a park. Park area measures how much green a unit contains;
tree density measures what its streets are like. The second is the construct this
study is arguing about, and the Bogotá study cited as an antecedent measured
street trees rather than the tree stock as a whole.

That argument decides which layer the variable comes from. It does not decide how
much of the layer belongs in it, and that is the part the delivered data cannot
settle.

**Decision — the variable that enters the models is the whole census.** No
criterion at all. This is the neutral state, and it is neutral in the precise
sense that every alternative presupposes a reading of the emplacement codes that
the delivered layer does not support and that the measurements below contradict.
A criterion has to be earned; measuring what the source contains does not.

**Decision — two narrower variants are measured beside it, and both stay out of
the models.** `TREE_DENSITY_WITHOUT_P1` drops the largest single code;
`TREE_DENSITY_U_CODES` keeps only the fifteen U codes. They follow the pattern
parks, carriageway and bridge deck already follow: measured on every run,
exported in every table, absent from the model set. Three columns in one table is
what turns "which subset should we use" from a discussion into a comparison.

**Decision — parks leave the model set and stay measured.** One green variable in
the models, and it is the one whose mechanism the study can state. Parks keep
being computed, exported and drawn, so the swap can be defended with the number
in hand rather than with an argument.

**Decision — a selection rule may name what it keeps or what it drops, never
both.** Naming what goes out suits a criterion that removes one thing from an
otherwise complete layer, which is the P1 variant. Naming what stays suits a
criterion that keeps a known set and would otherwise silently admit any new value
the source invented, which is the U variant: the fifteen codes are enumerated
rather than matched on their first letter, so a sixteenth appearing stops the run
instead of quietly joining the variable.

**Decision — all three enter as snapshots.** `Fecha_Actu` is not a time series.
It records when a tree was last surveyed, not when it was planted or when it grew
to the size at which it narrows anything. The 2005-2007 census stamps its own
dates on trees of every age, and those three years carry 1,043,993 of the
1,475,041 records, 70.8% of the layer. Treating that column as a series would
produce a variable whose year means "when somebody walked past with a clipboard".

### What the three variables are

Measured over the thirty units, in trees per square kilometre.

| Variable | Trees selected | Minimum | Median | Maximum | In the models |
|---|---:|---:|---:|---:|---|
| `TREE_DENSITY` | 1,475,041 | 901.55 | 3,405.41 | 7,937.46 | yes |
| `TREE_DENSITY_WITHOUT_P1` | 1,163,036 | 388.52 | 2,945.03 | 5,584.85 | no |
| `TREE_DENSITY_U_CODES` | 442,742 | 248.94 | 1,070.97 | 2,386.79 | no |

None of the three puts a unit at zero, so the implausible-zero flag all three
carry never fires.

### Why the codes could not decide it

The layer arrived with no dictionary for `Tipo_Empla`: its metadata file is 1 KB
and defines nothing. So every code was profiled against the other delivered
layers, over the full 1.47 million trees rather than a sample. Two things came
out of it, and both cut against a code-based criterion.

**`P1` is not the park emplacement.** It was taken for one, on the reasonable
ground that a tree inside a park produces none of the visual narrowing the
variable is about. Measured, 19.4% of `P1` trees fall inside a `parques_urb`
polygon, below the 34.9% of every other code weighted together, and the median
`P1` tree stands 40.6 m from the nearest carriageway. The codes that are actually
inside parks are `L2` at 88.9%, `L1` at 79.6% and `L3` at 74.6%. Dropping `P1`
removes 21% of the census on a premise the data does not support, which is why
that variant is a variant and not the variable.

**The fifteen U codes do not behave alike.** They are the closest thing in the
layer to a street category, and taken together 64.9% of them are within 5 m of a
carriageway against 27.1% for the census as a whole. But the set is not one
thing:

| Group | Codes | Trees | Median distance | Within 5 m | On a sidewalk |
|---|---|---:|---:|---:|---:|
| Plainly on the street | U13, U3, U11, U6, U5 | 208,664 | 0.9–1.3 m | 88–96% | 2–85% |
| In between | U9, U15, U4, U14, U1, U7 | 125,051 | 2.1–5.7 m | 45–69% | 1–48% |
| Not on the street | U2, U8, U10, U12 | 109,047 | 7.9–33.2 m | 11–36% | 3–30% |

A quarter of the U set is not by a carriageway, and most of that quarter is one
code: `U10` alone carries 86,607 trees at a median of 22.4 m. So "the U codes"
names a set that is mostly but not uniformly street, on a classification nobody
documented. That is defensible as a variant to compare against and not as the
definition the thesis rests on.

### Why not define it by distance to the carriageway

The obvious alternative is to drop the codes and use the mechanism directly:
keep the trees within some distance of a carriageway polygon. It is cheap, it is
one pass over the layer, it depends on no undocumented classification, and it is
exactly the thing the variable claims to be about. It was measured before being
ruled out, over the full census, at four thresholds.

| Threshold | Trees kept | Share of census | On a sidewalk | Largest correlation with the model set |
|---|---:|---:|---:|---|
| 3 m | 306,099 | 20.8% | 61.0% | **0.782** with arterial road |
| 5 m | 400,370 | 27.1% | 50.4% | **0.759** with arterial road |
| 7.5 m | 491,667 | 33.3% | 42.7% | **0.726** with arterial road |
| 10 m | 557,829 | 37.8% | 38.4% | **0.705** with arterial road |

**Every threshold lands above the 0.70 collinearity threshold against arterial
road area share.** The reason is structural rather than incidental: a unit with
more arterial surface has more carriageway edge, so more of its trees fall within
any fixed distance of one. A criterion defined by proximity to the road network
imports the geometry of the road network into the variable, and the variable
stops being independent evidence about the streetscape.

The same mechanism explains the U codes. A distance criterion at 5 m correlates
0.913 with `TREE_DENSITY_U_CODES`, which is as good as saying that the U codes
already are "trees near a road" under another name, and it is why that variant
reaches 0.690 against arterial road while the full census reaches 0.232.

So the distance criterion is technically the most viable and statistically the
worst available. It is worth putting to my advisor in exactly those terms, and it
is recorded here rather than implemented.

### What the swap does to the collinearity

Street trees and urban parks correlate at 0.383 across the thirty units: enough
to show they measure related things, nowhere near enough for one to stand in for
the other. The choice between them is a choice of construct and not of
collinearity.

Inside the model set nothing moves. Before and after the swap there are five
pairs at or above 0.70 in absolute value and the largest is 0.901, signalised
junctions against TransMilenio stations.

The full census is not merely acceptable on this count, it is the best of the
candidates. Its largest correlation with anything in the model set is 0.308,
against TransMilenio, which makes it the most independent variable in the whole
set. The narrower the criterion gets, the more entangled the variable becomes:

| Candidate | Largest correlation with the model set |
|---|---|
| `TREE_DENSITY` | 0.308, TransMilenio |
| `TREE_DENSITY_WITHOUT_P1` | 0.465, TransMilenio |
| `TREE_DENSITY_U_CODES` | 0.690, arterial road |
| trees within 5 m of a carriageway | 0.759, arterial road |

That ordering is worth stating plainly, because it runs against the intuition
that a narrower and more mechanically faithful variable must be a better one
here. Narrowing the census by proximity to the road progressively replaces a
measurement of the streetscape with a measurement of the road network, which the
model already has twice over.

### One consequence for the exported tables

`TREE_DENSITY` and `TREE_DENSITY_WITHOUT_P1` correlate at 0.944, so they appear
in the table of pairs above the threshold. That is arithmetic, not a finding:
they are two counts of the same objects. The table carries a `SAME_SOURCE_LAYER`
column marking exactly this case, and only one variant is ever in the model set.

### Declared as a limitation

**The census is one snapshot of uneven recency, and the unevenness is not
random.** A unit last surveyed three years ago and one last surveyed fifteen
years ago sit in the same column with nothing between them to mark the
difference, and the survey date tracks when the area was urbanised: the 2005-2007
sweep covers the consolidated city and the later updates concentrate where the
city grew afterwards. A tree planted in 2010 in a unit whose record dates from
2006 is not in the layer at all, so the variable understates recently urbanised
units by an amount the data cannot recover.

This belongs in the Data chapter beside the other source limitations, not in a
correction. There is nothing to correct against: the column dates the survey, and
knowing when a unit was surveyed says nothing about how many trees were planted
after that date.

### Divergence from the anteproyecto

The anteproyecto declares urban parks among the built environment predictors and
does not mention arbolado, because the tree census had not been delivered when it
was written. The final report has to carry the change and its reason: the layer
that arrived allowed the green variable to be defined by the mechanism the
literature identifies, instead of by the only green layer available at the time.
Parks are still measured and still reported, so this is a change of model
specification and not a variable that disappeared.

---

## D33 — The tables the deliverables print are emitted as LaTeX, not transcribed

**Kind:** Implementation.

**Status:** Closed.

**Built:** Yes, as `src/latex.py`, called from the `matrix`, `corrected` and
`predictors` routes.

**Context.** Three tables travel from the pipeline into the documents as tables
rather than as pictures: the casualty matrix of each dataset, and the correlation
among the variables in the model set. That much was already settled. A table
projected on a screen stays legible at any size, keeps its text selectable and
takes the typeface of the document; a screenshot has to be redrawn whole every
time a number moves. What was not settled is how the numbers got from a CSV into
the `.tex`, and until now the answer was that they were typed in by hand.

Transcription is where the traceability breaks. A figure typed by hand can be
typed wrongly and nothing downstream would notice, and once it is in the document
there is no record of which run produced it. The rule that every quoted figure
carries its run cannot be kept by hand across sixty cells of a matrix.

**Decision — the pipeline emits the table body and the document supplies
everything around it.** Each file is a `tblr` and nothing else, `\input` inside
whatever `table` environment the document sets up. Captions, placement and column
widths depend on how much room the page has, which the pipeline does not know;
the numbers depend on the run, which the document does not know.

**Decision — every emitted file names its run in a comment at the top.** A LaTeX
comment, so it never reaches the compiled page, and first in the file, so it is
read before any of the numbers are.

**Decision — the shading ceiling is fixed in the configuration and the data
cannot push past it.** No cell goes above 70% of the accent colour, because above
that black text stops reading when projected, and switching to white text does
not rescue it: the accent colour never gets dark enough to carry white well.
Because the ceiling is a constant rather than a function of the data, it means the
same thing in a table of counts and in a divergent one, where a large negative
value is as dark as a large positive one.

Counts are shaded on the square root of the value over the largest in that table.
They span four orders of magnitude, and a proportional ramp would leave every cell
but a handful indistinguishable from white. Each matrix is shaded on its own
maximum, so the shading reads within a table and not across two, which is what the
caption in the document has to say.

**Decision — bold is the statistical claim and colour is only legibility.** In the
correlation table, bold marks the pairs at or above the declared threshold, which
is the claim the surrounding text makes; the colour carries sign and magnitude on
the capped ramp. They answer two different questions, and sharing one threshold
between them would make each answer the other's.

**Decision — both datasets name themselves in the file name.** The emitted
matrices are `__observed` and `__rho_corrected`. This is deliberately not what D31
decided for the CSV exports, where the observed set keeps its unsuffixed names so
the dashboard does not break. Nothing yet reads these files, and two tables about
to sit side by side on one slide must not be told apart by which one lacks a
suffix.

**Consequence.** The matrices in the current presentation were shaded up to 100%
of the accent colour, with white text in the darkest cell, which is what the
emitted tables no longer do. Dropping the emitted files in will make the darkest
cells lighter than they are today.

---

## D34 — The predictor figures come in two sets, and two variables are in neither

**Kind:** Implementation.

**Status:** Closed.

**Built:** Yes, as `FIGURE_SETS` in the configuration, drawn by the `predictors`
route in run `run_20260831_060432`.

**Context.** Measuring a variable, putting it in a model and drawing it are three
separate decisions, and until now the third one was not being made: the figures
were drawn for whatever happened to be declared. That worked while the declared
set and the model set were nearly the same. They are not any more. Thirteen
variables are measured, eight enter the models, and two of the thirteen are
alternative counts of one layer.

A single set of figures cannot serve both readers. A reader of the thesis needs
to see the eight the study estimates on; a reader checking the exclusions needs
to see the ones that were excluded, because the number that justifies an
exclusion only exists in a matrix that still contains the excluded variable.

**Decision — two sets, drawn on every run, from the same two tables.** The
complete set and the model set. Nothing but the list of columns differs between
them: both read the exported wide table and the exported correlation, so a figure
in one set and a figure in the other cannot disagree about a number. If they
could, one of the two would be wrong and there would be no way to tell which.

**Decision — the complete set exists to carry its own justification.**
`ROADWAY_AREA_SHARE` is out of the models because it correlates 0.969 with
`SIDEWALK_AREA_SHARE`. That figure is only visible in a matrix that still has
carriageway in it, so the set that excludes it cannot explain why. The complete
set is the evidence; the model set is the claim.

**Decision — the two tree variants are in neither set.** They are measured,
exported and reported like everything else, and they appear in no figure at all.
This is the first time a declared variable is deliberately not drawn, so the
reason matters: they are alternative counts of the same census as `TREE_DENSITY`,
kept because they are the evidence for choosing the whole census over a subset of
it (D32). In a table of data that evidence is a column somebody can quote. In a
heat map it is three tree columns side by side, three views of one layer, and
every reader would spend attention working out which one counts. The answer to
"why the whole census" is a paragraph and a table, not a column in a figure.

So the complete set holds eleven variables and not thirteen. "Complete" means
every measured *variable*, once each, over the eleven source layers.

**Decision — the set names every folder and every file.** The figures go to
`figures/predictors__complete/` and `figures/predictors__model/`, and each file
carries the same suffix: `histogram__TREE_DENSITY__model.png`,
`correlation__predictors__complete.png`, `table__predictors__model.png`. This is
the rule the two casualty datasets already follow, and for the same reason:
neither set is left unsuffixed, because two figures about to sit side by side
must not be told apart by which one lacks a suffix. A histogram of one variable
is otherwise identical in the two sets, and its file name is the only thing that
says which set it was drawn for.

**Decision — which sets draw a variable is a column of the exported
dictionary.** `FIGURE_SETS` lists them, and reads `none` for the two that are in
neither. A flag would not have done: there are two sets and a variable can be in
either, both, or neither, and neither is a deliberate state rather than an
oversight.

### The check that the figure and the printed table are the same numbers

The correlation of the model set now exists twice over: as the table computed
from the declared model set, which becomes the LaTeX the documents print, and as
the full matrix restricted to the model set, which is what the figure is drawn
from. A Pearson correlation between two columns does not depend on which other
columns are present, so the two must agree exactly.

The run checks it rather than assuming it, and reports the largest difference
between the two. It is 0.00e+00. This is worth checking every run because it is
the one discrepancy that would leave nothing else out of place: a figure in a
document and a table in the same document, disagreeing, with both routes
individually passing every other check.

The emitted table was also compared against the copy inside the informe de
avance, which is the file the presentation includes. The two are identical apart
from the provenance comment naming the run, so no number in the deck needed
touching.

---

## D35 — The desire lines enter as exposure, apportioned by share of length

**Kind:** Methodological. It decides what the variable measures, how a trip is
attributed to a unit, and which side of the model the variable sits on.

**Status:** Closed on the allocation rule and on where the variable lives. Both
questions this decision left open are now **answered, and superseded by D38**:
the layer is a 9.6% sample of the **2019** survey, not of 2023, and its 181 lines
were not selected by volume. It is no longer the study's exposure — D38 builds
that from the surveys.

**And the layer is now retired.** It left `config.EXPOSURE_LAYERS` when 2019 was
implemented, so it is no longer read on any run and no longer produces a table or
a figure. Its declaration stays in `config.BICYCLE_DESIRE_LINES`, naming the file,
and section 13 of the verification report stays in place, because the figures
below are quoted in finished work and have to remain recomputable by hand.

**It was validated against the survey before it went, and that check was the
reason to keep it this long.** All **160 of its origin-destination pairs** appear
among the pairs the pipeline builds from the 2019 survey, and no pair is
attributed more trips than the survey holds for it — two independent readings of
one source, one received as finished geometry and one built from the trip records,
agreeing exactly. The comparison also showed that **the plausibility test removes
15 of those 160 pairs**, 7.9% of the layer's trips, so the delivered layer carried
records this study judges impossible. See D38.

Read this for the allocation rule, which D38 inherits unchanged, and D38 for what
the variable now is.

**Built:** Yes, and now retired. `src/exposure.py`, route `exposure`. Run
`run_20260901_003409`; the same figures on `run_20260907_231531`, which is how the
replacement was checked; last measured there, and absent from
`run_20260908_005529` onward.

### What the layer turned out to be

D21 left the layer out because its length column was not what its name said. The
inspection that answered that question also turned up things that change the
shape of the variable, so they are recorded here rather than left in a
conversation:

- **181 line records**, one mode only: `modo_principal` reads `Bicicleta` on
  every row. There is no exposure by mode to be had from this file.
- **Two expansions, not one.** `f_exp` expands one surveyed trip to a day.
  `ResultadoExp` is `f_exp` multiplied by `totalViajes`, and `totalViajes` is not
  a count of trips at all: it equals the number of day-of-week flags set on the
  record, in all 181 rows. So `ResultadoExp` counts **trips per week** and
  `f_exp` counts trips per day. The layer sums to 556,997.58 weekly and
  113,269.31 daily.
- **No metric length column.** `Shape__Length` is in degrees — it matches the
  geometry's length in EPSG:4686 to 5e-13 — so the kilometres have to be computed
  by projecting, which is what the legacy code did.
- **No year anywhere.** The ESRI metadata dates its own export in ArcGIS
  (November 2023) and says nothing about the survey behind it.
- **The layer is a selection.** `ORIG_FID` runs from 156 to 7212 over 181 rows,
  so it was exported from a parent table of at least 7212 features.

### The allocation rule

**Decision — a line gives each unit it crosses the share of its trips that
matches the share of its length falling inside that unit.** A line worth 100
trips lying 50%, 30% and 20% across three units contributes 50, 30 and 20. It is
the rule the legacy code already applied through `overlay` with `intersection`;
what changes is that the result is named for what it is and overwrites nothing.

There has to be a rule because the lines are not local: a line crosses three
units in the median and as many as ten. Attributing the whole trip to one of them
would be a choice among ten, and any of the ten would be an assumption dressed up
as a rule — the same objection that removed the alphabetical pair ordering in D1.

**What was rejected, and why it is worth saying, because it is what the exported
alternatives are for.** Counting the trip whole at its origin, or whole at its
destination, uses only what the survey recorded and owes nothing to the geometry
between the two. That is a real advantage here, and it lost anyway: those rules
say where trips begin and end, which is close to where people live and work, and
the variable is meant to say how much cycling passes through a place. What the
casualty matrix is a rate over is traffic in the unit, not residence in it.

### The limitation the number carries

**The lines are straight.** Sinuosity — length over the straight distance between
the endpoints — is exactly 1.000 on all 181 of them, minimum, median and maximum
alike. They carry between 2 and 37 vertices, but only because ArcGIS densifies a
geodesic; the first vertex lands on the declared origin and the last on the
declared destination with a maximum gap of 0.00 m, which the run checks on every
execution.

So the kilometres inside a unit are a share of a chord nobody rode. The
apportionment is defensible as a way of spreading a trip along its corridor, and
it is not a measurement of distance pedalled in the unit. Any document quoting
this variable states that.

**That is why the three alternatives are exported beside it.** Trips counted at
the origin, trips counted at the destination, and kilometres of line inside the
unit, each in its own column and none of them a model variable. They exist so the
sensitivity of a result to the rule can be shown rather than asserted. On this
run they order the units similarly but not identically — Spearman against the
variable is 0.813 at the origin, 0.798 at the destination and 0.781 on kilometres
— while origin and destination agree with each other far more closely than either
agrees with the variable, at 0.973. The rules are different variables, not two
scales of one, so the choice had to be made on an argument.

### Where the variable lives

**Decision — exposure is not a predictor and stays out of the predictor module,
the correlation matrix and both figure sets.** Every predictor describes what a
unit is built like; this one describes how much travel is in it. In a rate model
they go on opposite sides — exposure is the offset the anteproyecto declared —
and a row for it in a matrix of built-environment variables would invite a reader
to compare it with variables it does not compete with.

It gets its own module, its own route, its own table and its own figure. The
figure is the pipeline's only thematic map, and it reuses the reference map's
cartography for everything except the one thing that has to differ: the fill
carries a value, so it takes a sequential ramp and a colour bar.

**Torca is an observed zero.** No desire line reaches UPL07 at all. It comes out
as `0.0` with the status `MEASURED`, never as a null, and on the map it keeps the
bottom of the ramp and gains a hatch of its own — at the bottom of a scale
running to sixty thousand it is the same pale colour as six units that are not
zero, so the fill alone could not say it. A unit that could not be measured would
leave the ramp entirely for a grey with a coarser, diagonal hatch. This is D22's
rule applied to a new table and carried into a figure.

### The mode is part of every column name

**Decision — a column name is built from the layer, not written down: the mode
leads, then what is counted, then over what period.** The variable is
`BICYCLE_TRIPS_PER_WEEK_BY_LENGTH_SHARE`.

`TRIPS_PER_WEEK_BY_LENGTH_SHARE` was correct for exactly as long as there was one
exposure layer. The table is wide over modes — one row per unit, a block of
columns per layer — because the panel it joins is keyed on unit and year, and an
exposure table with a row per unit and mode would need a filter before every
join. In that shape two layers with unprefixed names do not raise: one column
survives and the other leaves no trace.

So the quantity declares the part that describes it and the layer contributes the
mode, which means a layer cannot be added without saying which mode it is. A
check confirms every declared quantity is present under its prefixed name and
that the table carries exactly the declared columns in order. Two columns belong
to the unit and take no prefix: `POPULATION`, because a unit has one population
whichever mode is measured against it, and `VALUE_STATUS`.

The procedure for adding the next layer — what to verify in the file before
declaring anything, how it is named, which checks it inherits — is written down
in `docs/adding-an-exposure-layer.md`. It is a procedure and not a note because
the trap is always the same one: the expansion factor, whether the file has
already multiplied it out, and what period it expands.

### Normalisation, and the column that was empty

*Superseded in part by D36, which filled this socket and changed its key. What
follows is what was decided here; what the population is now is D36.*

The table carries trips per week per km², which is computed, and trips per week
per inhabitant, which at the time was not: **the study had no population by
unit.** The unit layer carries `AREA_HA` and nothing else, and the only
population in the delivered data was the `poblacion_` column of the UPZ layer —
111 polygons that do not nest inside the 30 units. Spreading it from one geometry
to the other would be an assumption about how population is distributed inside a
UPZ, which is a methodological choice and not a lookup, so it was not made.

**Decision — the column exists, is null, and the run says so loudly on every
execution**, naming the file it would read and the columns it expects. A
fabricated denominator would be worse than an absent one, because the absent one
is visible.

**What that socket assumed turned out to be wrong, and D36 says why.** It was
keyed on the unit alone, and a denominator that does not move within a unit is
collinear with that unit's fixed effect and drops out of the model. The census
file that fills it is keyed on the unit and the year, and it enters that way.
The per-inhabitant column here is now computed against a single declared year,
2023, which its name carries; it describes and it is not a model variable.

Which normalisation the models use is a separate question and stays open. If the
variable enters as an offset it goes in as a level and is not normalised at all,
and normalising it first and then using it as an offset would normalise it twice.

### The line measurement, written for four other layers

There was no way to measure a line layer before this. The method lives in the
predictor module rather than in the exposure module, and is registered like the
other two, so the four layers with an annual series — cycleways and the three
signage layers — are measured by it once their year is resolved. The splitting of
a line at the unit boundaries is a function of its own that both callers use, so
the kilometres of a cycleway inside a unit and the kilometres of a desire line
inside a unit cannot end up measured two slightly different ways.

The repair the polygon layers get is deliberately not applied to lines:
`make_valid` followed by `buffer(0)` reduces a geometry to its areal part, which
for a line is nothing, so the step that rescues a self-touching polygon would
delete every line it touched.

### The balance the run checks

What was allocated to the units plus what fell outside them equals what the file
holds, for all three quantities, on every run:

| Quantity | Inside the 30 UPL | Outside | Layer |
|---|---:|---:|---:|
| Trips per week | 530,018.53 | 26,979.05 | 556,997.58 |
| Trips per day | 107,844.36 | 5,424.95 | 113,269.31 |
| Kilometres | 1,087.56 | 131.70 | 1,219.26 |

This is the check the legacy pipeline could not have made, because the quantity
it exported was not a quantity the file held. Three of the 181 lines fall outside
every unit; 178 reach at least one.

### What was still open, and how it was answered

*Both of these were closed by the inspection that built D38. What follows is the
question as it stood; the answers are in D38 and they are the reason this layer
is no longer the study's exposure.*

**Which survey and which year.** Nothing in the file said, and it decided whether
the variable was contemporary with the casualty series or a fixed value attached
to eighteen years of it.

*Answered: it is **2019**.* All 181 records match an exact
`(zat_origen, zat_destino, f_exp)` triple among the 7,863 bicycle trips of the
2019 survey, and the endpoints sit on the 2019 zoning's centroids at a median
0.046 m against 2.148 m for the 2023 zoning. The November 2023 in the ESRI
metadata is an ArcGIS export date and nothing more — which also means the
`population_reference_year=2023` this layer declares divides by the wrong year.
It is left as it is, and D36 records why.

**What the 181 lines are a selection of.** They represent about 113 thousand
daily bicycle trips, far below Bogotá's citywide total, and `ORIG_FID` shows they
were drawn from a table of at least 7212 features. **If the criterion was volume,
this variable measures principal corridors and not exposure** — and principal
corridors correlate with the very infrastructure the predictors measure, which
would make it the wrong variable in a way no amount of care in the allocation
could fix.

*Answered: it was not volume, and the outcome is worse than if it had been.* The
layer's 160 distinct pairs rank from 1st to 792nd among 2019's 5,045 inter-zonal
bicycle pairs, only 61 are in the top 160, and the pairs ranked 3rd, 6th, 9th and
10th are missing. No threshold reproduces the set. What it is instead is an
unexplained sample that does not preserve the ranking: against the 2023 survey's
own bicycle exposure it correlates at **Spearman 0.362** over the thirty units.
The one thing the selection certainly did was drop every intra-zonal pair, which
is unavoidable — a trip that starts and ends in one zone has no line — and which
is 9.3% of 2019's bicycle travel.

So the caution this section ended on was right and did not go far enough. No
result rested on the variable, and none now will: D38 replaces it.

---

## D36 — The population enters as a panel, one number per unit and per year

**Kind:** Methodological. It decides what every rate in the study divides by, and
what that denominator is allowed to be used for.

**Status:** Closed on the shape of the denominator and on where it comes from.
**One thing about the file is open** and it is not mine to close: which of its
years are measured and which are projected or backcast.

**Built:** Yes. `src/population.py`, route `population`. Run
`run_20260901_091844`.

### The socket D35 left, and why it changed shape

D35 declared a place for a population and left it empty, because nothing in the
delivered data carried one at the scale of the unit. The file
`osb_demografia-poblacion-upl.csv` fills it, and filling it changed the key: the
socket was keyed on the unit, and the source is keyed on the unit and the year.

**Decision — the denominator is (unit, year) and never (unit).** Three reasons,
and the first is the one that matters.

**A constant denominator disappears into the model.** Every specification the
study will estimate carries a unit effect. A population that does not move within
a unit is collinear with that effect: the model absorbs it, the normalisation
goes with it, and nothing fails while it happens. A denominator that cannot
survive the model it was built for is not a denominator.

**The variation is not noise.** Between 2007 and 2024 a unit's population moves by
anything from **−28.5 %** in Barrios Unidos to **+557.9 %** in Torca, with a
median of +16.5 % and seven of the thirty units losing population. Torca is the
unit the exposure layer never reaches and the largest of the thirty; it also
sextupled. Averaging that into one number per unit would put the same denominator
under a 2008 casualty count and a 2024 one in a place where six times as many
people now live.

**The panel is a superset of the snapshot.** A series collapses to one number per
unit whenever a fixed denominator is wanted, and one number per unit can never be
expanded into a series. Choosing the shape that can become the other one costs
nothing and keeps the choice open.

### What the file is

One row per unit, year, sex and single year of age. **175,956 rows, no nulls, no
duplicates** on that key. It covers the **33 units of Decreto 555 de 2021** and
the years **2005 to 2035**, so both the study's 30 units and its 2007–2024 window
sit inside it with room to spare.

The pipeline adds sex and age away and keeps nothing coarser than (unit, year).
The file also carries the life-course and age-band labels each row belongs to;
those are groupings of the same single year of age and are read past, because
summing them alongside would count everybody twice.

**The unit numbers arrive as integers, 1 to 33, and the cartography spells them
`UPL01` to `UPL33`.** The rule that bridges the two is declared rather than
inlined, because a join on the wrong one of them matches nothing at all instead of
matching wrongly, and a join that matches nothing is the failure that hides
longest.

**The join is checked on the names and not only on the codes.** All thirty names
agree with the cartography character for character, accents included. Two files
can agree on a code and disagree about which place it is; agreeing on the name as
well is what says they divide the city the same way. The run stops if any of the
thirty disagrees.

### The grid is required to be full

**Decision — 30 units × 18 years = 540 cells, and a missing cell stops the run.**
The panel is built as the full grid first and the file joined onto it, so a
unit-year the file does not cover arrives as a null the check can see rather than
as a row that is simply absent. It is D22's rule applied to the denominator, and
the reason it is a hard failure rather than a warning is specific: a predictor
missing for one unit-year leaves a hole a reader notices, while a denominator
missing for one unit-year silently removes that cell from every model built on
it, and nothing in the output says which cell went.

All 540 are present. The balance closes exactly: **132,448,396 person-years** in
the table against the same figure in the file, over the study's units and years.

### The three units the study does not have, measured

The file carries 33 units and the delivered cartography carries 30. The three it
adds are **UPL01 Sumapaz, UPL02 Cuenca del Tunjuelo and UPL06 Cerros
Orientales** — the rural units, where the urban predictors are largely undefined.

**This is the first time that decision can be measured in people rather than in
polygons.** In 2024 the three hold 3,305, 19,888 and 2,658 residents: **25,851
between them, 0.33 % of the city the file describes**, and between 0.22 % and
0.33 % across 2007–2024. The run reports it as a warning on every execution and
exports it year by year, because it is the answer to the question a jury asks
about 33 becoming 30. It confirms the universe rather than qualifying it: the
study covers 99.7 % of Bogotá's population.

Note that the file spells the first of them `Sumapáz`, with an accent the official
name does not carry. It is reported as the file spells it.

### The per-inhabitant column of the exposure table stays descriptive

*Superseded by D38 for the study's exposure, which now carries a year of its own
and therefore a plain `POPULATION` per unit and per year. What follows still
holds for the delivered layer's reference table, with one correction recorded at
the end of this section: the year it names is the wrong one.*

**Decision — `BICYCLE_TRIPS_PER_WEEK_PER_INHABITANT_2023` is a description and
enters no model with a time dimension**, and the column name says which year's
inhabitants it divides by.

The trips are a snapshot with no year at all. The population moves. Divide one by
the other inside a panel and the rate would vary from year to year entirely
because of its denominator — a change in cycling that is really a change in who
lives there. That is a worse failure than not normalising, because it produces a
number that looks like a trend.

So the year is nailed down and made visible. **2023**, because the ArcGIS export
in the layer's metadata is the only date the layer has, and it is declared on the
layer rather than as a setting of the module, since a second exposure layer would
arrive with a date of its own. The column carries that year in its name for the
same reason `TRIPS_PER_WEEK` carries its period: a rate that does not say what its
denominator was is the same class of mistake as a length column holding
kilometre-trips. The exposure table carries `POPULATION_2023` beside it so the
division can be recomputed from the table it appears in, the run checks that the
quotient is the quotient the name states, and the run warns on every execution
that the column describes and does not model.

**The models take their denominator from the population table, per unit and per
year.** That is the whole point of the panel, and it is why the two live in
separate tables.

### What D38 changed here, and the year that turned out wrong

**The socket this section filled has been emptied again, on the good side.** The
study's exposure is now built from the mobility surveys and every row of it
carries the year the survey was collected. So the denominator is read at the
numerator's own year, the exposure table carries a plain `POPULATION` keyed on
unit and year, and `TRIPS_PER_AVERAGE_DAY_PER_INHABITANT` is a rate that can
enter a model with a time dimension. The reasoning above was right for a
numerator with no year; it stops applying the moment the numerator has one.

**And the year this section chose is wrong.** 2023 came from the ArcGIS export
date in the delivered layer's metadata, which was the only date the layer had.
The layer is a sample of the **2019** survey, established in D38 — so
`BICYCLE_TRIPS_PER_WEEK_PER_INHABITANT_2023` divides 2019 trips by 2023
residents.

It is left as it is rather than corrected, and that is deliberate. The column is
descriptive, it enters nothing, and its numbers are quoted in finished work that
has to stay reproducible; renaming it would break that traceability to fix a
figure nobody uses. What is not acceptable is leaving it unrecorded, so it is
recorded here, and any document quoting that column says which year it divides by
and which year its numerator is.

### The route

`population` is a route of its own rather than a stage of another. The population
is nobody's variable: it is not a predictor, because it says nothing about what a
place is built like, and it is not exposure, because it counts residents and not
travel. It is what both of those and the casualty counts are divided by, so it
belongs to the study rather than to the module that happens to read it first. The
exposure module asks it for one year and does not read the file itself: two
readers of one file are two chances to sum it differently.

### Which years are measured and which are modelled, answered by the advisor

**The panel rests on the 2018 DANE census, and every other year of it is a
projection the city computed from that one.** Stated by my advisor on 2026-09-11.
The file spans 2005 to 2035; the census is 2018; so **2005–2017 are back-projections
and 2019–2035 are projections**, and the only year in the file that is a count is
2018.

That answers a question this decision had left open and that the run had been
warning about on every execution: the file does not say which years are which, and
**the shape of the series is not evidence for it** — a smooth curve is what a
projection and an interpolated census both look like, so reading provenance off one
would have been inference presented as fact. It took a person who knows where the
file came from.

**What it means for the study, and it belongs in the body of the thesis.** The study
window opens in 2007 and the census is 2018, so **the denominator of the first
eleven years is a model and not a count**. That is the same period in which ρ says
the recording of casualties was changing, and the two belong in one paragraph: the
data before 2018 are of a different kind from the data after it, on both sides of
the rate. Every exposure rate this study quotes for 2007–2017 divides a constructed
exposure by a back-projected population.

**What is still open** is narrower: whether the city's projection is the DANE one
disaggregated to the UPL or a model of the city's own, and how it treats the units
whose boundaries Decreto 555 de 2021 drew after the census was taken. Neither
changes the sentence above.

---

## D37 — `data/` is filed by the role the data plays, and every root is declared

**Kind:** Implementation. It changes where files sit and how a path is built, and
it changes no measurement: every route produces the same numbers before and after.

**Status:** Closed for the roots and for what has moved. The final location of the
exposure layers is **deliberately left open** until the replacement delivery has
been inspected.

**Built:** Yes. `src/config.py`, and `docs/data-layout.md` records the result.

### The defect this fixes

The pipeline separates predictors from exposure with some care — separate module,
separate route, separate table, and D35 spends several paragraphs on why they sit
on opposite sides of a rate model. And then `SurveyLineLayer.path` built the path
to the desire lines out of `PREDICTORS_DIR`.

That is not a cosmetic inconsistency. The configuration is the one place where a
column can be traced back to a file, and it was saying that exposure is a
predictor. It happened because the desire lines were delivered inside the bundle
of predictor layers, which is a fact about how the data arrived and not about what
it is.

**Decision — every source path is built from a root named for the role its data
plays, and never from another role's root.** Cartography, casualties, predictors,
exposure, population, and the two folders for deliveries in transit. The roots are
declared together at the top of `config.py` rather than scattered through it.

`PREDICTORS_DIR` and `EXPOSURE_DIR` point at the same folder today and are still
two constants. That is the whole point: the physical location is a delivery
artefact and the role is not, so the day the exposure files move it is one line.
`GEO_DATA_DIR` and `CRASH_DATA_DIR` were renamed to `CARTOGRAPHY_DIR` and
`CASUALTIES_DIR` in the same pass, because "geo" is a format and "crash data" is a
folder name, and neither is a role.

### What moved, and what did not

**The census moved to `data/population/`.** It was the only loose file under
`data/`, and unlike every other source it did not arrive inside a bundle, so there
was no delivered arrangement to preserve by leaving it where it landed.

**Two undeclared layers moved into `areas/`.** The bundle had filed
`luminarias_upz` beside the geometry folders, as a layer among them, and
`indiceseguridadnocturna` under a folder called `mean` — which is not a geometry
at all, but the measurement the delivery implied for it. Both are polygon layers.
Filing them by geometry makes `shp_properties_sorted/` hold exactly the three
folders `GEOMETRY_FOLDERS` declares, for the first time, and it means either could
be declared later without moving anything.

**Nothing else moved.** The delivered bundles keep their names and their internal
arrangement, including names that are not mine — `shp_properties_sorted`,
`data_siniestros_bogota`, `Líneas de deseo Matriz Origen Destino`. Being able to
say "this is the file I was given, where I was given it" is worth more than a
tidier tree, and the organisation the study needs lives in the declarations rather
than in the filesystem.

### Delivered and not read is now a recorded fact

`luminarias_upz` and `indiceseguridadnocturna` had sat in the bundle for months
with nothing pointing at them, and nothing anywhere said whether they had been
rejected or forgotten. **Decision — a delivered layer that no variable reads is
declared as such, with what it holds and what would have to be settled before it
could become a variable.** `config.UNDECLARED_PREDICTOR_LAYERS`, printed by the
`predictors` route on every run, which also says whether each is still on disk.

It is the same argument as D10. A zero and an absence are different facts and the
grid must not confuse them; delivered-and-rejected and never-delivered are
different facts and a folder cannot tell them apart.

Neither layer is rejected on its merits. Lighting is counted over the 111 UPZ,
which do not nest inside the 30 units, so using it would need the apportionment
decision D36 declined to make for the UPZ population. The safety index is
perceived safety, which is closer to an outcome than to a cause and would need an
argument of its own before sitting beside the thirteen.

### `data/integrated/` is the declared exception

It is the one place under `data/` that the pipeline writes. That is deliberate —
the `integrate` route rebuilds the casualty layers there and every other route
reads them as an input, which makes it an input by the time anything else runs —
but the arrangement was undeclared, and `data/` is described everywhere else as
raw. It is now written down rather than left to be inferred.

### `docs/data-layout.md`

`data/` is not in version control, so nothing in the repository said what it must
contain for the pipeline to run. **Decision — the layout is documented, and the
document is updated in the same commit as any move.** Nothing else can catch the
two drifting apart: a stale path in the code fails loudly on the next run, and a
stale sentence about a folder fails silently for as long as nobody checks.

The document also carries the rule for a new delivery: it lands in
`data/incoming/` in a folder of its own and nothing existing is overwritten in
place. A delivery written over a folder keeps every route running and quietly
changes what they produce, which is the failure that leaves nothing out of place
to notice.

### What is left open

**Where the exposure layers finally live.** The replacement delivery — four survey
years and four travel modes, against one year and one mode today — is in
`data/incoming/encuestas_movilidad/` and has not been read. Whether it wants
`exposure/<year>/`, `exposure/<year>/<mode>/` or something flatter follows from
how the delivery is actually shaped, and deciding it before inspecting the files
would be deciding it against an assumption. `EXPOSURE_DIR` still points into the
predictor bundle until then, which is exactly what having the constant is for.

---

## D38 — Exposure is built from the survey, per unit, year, mode and day type

**Kind:** Methodological. It decides what the exposure of the study measures, from
what source, at what shape, and it retires the variable every earlier exposure
figure was measured on.

**Status:** Closed for all four years. **Two things are open** and both are named
at the end: which day type the models take, and whether a day-type comparison is
supportable at all — a question 2019 made sharper, 2015 made answerable and 2011
has now given a third point.

**Built:** Yes. `src/surveys.py` and the second half of `src/exposure.py`, route
`exposure`. Run `run_20260910_154319`: **five years, 1,080 rows, 47 checks, none
failed.** Each year has been added without moving the ones before it, which is the
test this decision is held to: 2005 landed on that run and the other four came out
identical to the last decimal over all 960 of their rows and every column.

**Amended by 2005**, which asked for five changes where 2011 asked for one and is
the year this decision's contract was most nearly bent by. All five are
declarations that the other four leave empty: a zoning built at run time rather
than read from a delivery, a zone code composed from two columns in two code
systems, a published total that declares which part of the file it covers, a unit
marked as below resolution where before only a whole day type could be, and a
column declared measured but not comparable. `docs/implementing-2005.md` is the
record and its section 13 is what building it cost.

**Amended by 2019**, in four places, each marked below: the day type is not a
dimension every year carries; the duration is a declared rule and not a column
name; a zone code can name no place; and the delivered layer is retired, having
first been used for the strongest check the survey reader could get.

**Amended by 2015**, in three places, also marked below: the day type is a real
dimension of the study after all, carried by two of the three measured years; a
zone may be delivered in pieces; and the year that expands to one day of its own
kind *and* has more than one kind broke a check that no earlier year could have.
2015 also brought the best external control the exposure stage has had — its own
published origin-destination matrices, reproduced to the last decimal on both kinds
of day — and nothing downstream moved: 2019 and 2023 come out of the run identical
across all 480 of their rows.

**Amended by 2011**, in four places, each marked below: a year's trips may live in
more than one file and the day type may be a property of the file rather than of
the record; a delivery may arrive as a database rather than as text; a row may rest
on a sample that does not reach the scale of one unit, which is a different fact
from whether the row has a number in it; and the zone code has to be spelled by one
function on both sides of the join rather than by two that happened to agree. 2011
is the year the §6b contract was written for — the one that could not be made to
fit without a change — and the change was reported, decided by a person, and made
once: **2015, 2019 and 2023 come out of the run identical across all 720 of their
rows and every column.**

### What replaced what, and why it had to

D35 built the exposure from a delivered layer of 181 desire lines and left two
questions open: which survey and which year the layer came from, and by what
criterion its 181 lines were selected out of a larger table. Both are now
answered, and neither answer is the one that was hoped for.

**The layer is 2019, not 2023.** Every one of its 181 records matches an exact
`(zat_origen, zat_destino, f_exp)` triple among the 7,863 bicycle trip records of
the 2019 survey. Its endpoints sit on the centroids of the **2019** zoning at a
median distance of 0.046 m, against 2.148 m for the 2023 zoning, and 146 of the
181 origins land within a metre of a 2019 centroid where only 62 do for 2023. The
November 2023 date in its ESRI metadata is when somebody exported it from ArcGIS
and says nothing about the survey underneath. D36 pinned its per-inhabitant
denominator to 2023 on the strength of that date, and that was wrong.

**The selection was not by volume, and it is worse than if it had been.** The
fear D35 recorded was that the 181 lines were the largest origin-destination
pairs, which would have made the variable a measure of principal corridors. They
are not: the layer's 160 distinct pairs rank from 1st to 792nd among the 5,045
inter-zonal bicycle pairs of 2019, only 61 of them are in the top 160, and the
pairs ranked 3rd, 6th, 9th and 10th are absent. No threshold on the expansion
factor, on the days per week the trip is made, or on the pair's total volume
reproduces the set. The one thing the selection clearly did do is drop every
intra-zonal pair — 9.3% of 2019's bicycle travel, and unavoidable, because a trip
that begins and ends in one zone has no line to draw.

**So it is an unexplained 9.6% sample, and it does not preserve the ranking.**
Against the 2023 survey's own bicycle exposure the delivered layer's variable
correlates at **Spearman 0.362** over the thirty units. Kennedy is the most
cycled unit the survey knows and the delivered layer ranks it sixteenth; the
layer's own top unit, Edén, is sixth in the survey. Two variables that order the
same thirty places that differently are not two measurements of one quantity, and
no care in the allocation rule could have fixed it.

That is the case for building the lines instead of receiving them, and it is
stronger than the case that was made for it in advance.

### The source, and what one row of it means

**Decision — exposure is the four surveyed modes, per unit, per survey year, per
kind of day, apportioned from the household mobility survey.** The four modes are
on foot, bicycle, motorcycle and car, mapped to `PEDESTRIAN`, `BICYCLE`,
`MOTORCYCLE` and `CAR`, which is the vocabulary the casualty matrix already uses.
Counting the denominator in a different category from the numerator is the one
thing that would make every rate meaningless, so the mapping is to the matrix's
own types and to nothing else.

**Public transport is deliberately not a fifth mode.** The matrix's
`PUBLIC_TRANSPORT` counts the occupants of a bus involved in a crash; the survey's
counts the passengers of a system, over a network the study does not model. Those
are not the same denominator and pairing them would look like a rate.

**The mode is the principal mode of the trip, not its stages, and the limitation
is declared out loud: the walk to the bus stop is not counted as pedestrian
exposure.** A trip made mostly by TransMilenio contributes nothing to walking
here, and a real pedestrian really did cross real streets to reach the station.
The survey records those stages in a separate module. Using them would mean a
second unit of analysis — the stage rather than the trip — and a second
expansion, and it is a larger piece of work than this one. Every number drawn
from pedestrian exposure carries this sentence.

### Three decisions inside the mapping, each of which could have gone the other way

**The walking trips of under fifteen minutes are in.** 2023 is the only year that
splits walking, at 4,039,259 trips a day over fifteen minutes and 2,059,528 under
it. Excluding the short ones would put 2023 at 4.04 M against 2019's 6.94 M, a
42% collapse that never happened — 43.0% of 2019's walking, 2,984,881 trips a
day, lasts under fifteen minutes when its durations are derived from the reported
times, and the survey's own indicator IND_104 implies 43.1%. (This corrects
3,351,414 and 48.3%, quoted here and in the inventory before the duration rule
existed: that figure came from an unrounded derivation, which puts a
fifteen-minute walk at 14.999999999 and on the wrong side of the threshold.) The other three years count short walks and cannot separate them,
so including them is the only definition all four years measure.

**The motorised bicycle is in `BICYCLE`.** 2023 lists it separately, 364 records
and 71,277 trips a day, 6.39% of the mode; 2019 also lists it separately at 1.15%;
2011 and 2015 fold it into bicycle and cannot separate it. Two arguments point the
same way. The series has to measure one category across four years, and two of
those years cannot offer the narrower one. And the numerator cannot separate it
either: the crash source has no motorised-bicycle category at all, only
`BICICLETA` and `BICITAXI`, so a rider hurt on one is recorded as a cyclist or a
motorcyclist and there is no way to know which.

**The bicitaxi is inside an aggregate in two of the four years, and what that costs
is now measured in both.** 2019 gives it a label of its own, 2.4 % of that year's
cycling, and D38 puts it in `BICYCLE` because the crash source does. 2015 folds it
into `ILEGAL` and 2011 into `Informal`, together with the mototaxi, the informal car,
the collective taxi and the unlicensed charter, and neither can split the category
at the trip level. Reading the stages says the bicitaxi is 46,840 trips a day in
2015, 3.0 % of its cycling, and **11,354 in 2011, 1.9 %** — so the category is not
identical across the four years and the size of the difference runs between a
fiftieth and a thirtieth of one mode. 2011's mototaxi, in the same aggregate, is
1,032 trips a day, 0.25 % of its motorcycle travel. Recovering either would mean
taking the stage rather than the trip as the unit of analysis, which is a different
study.

**Every source label is accounted for, and one that is not stops the run.** Each
of the eleven mode labels of 2023 is either mapped to an actor type or declared
as deliberately not measured. There is no `OTHER` to fall through to, unlike the
vehicle types of D4: the study measures four modes and the rest of the survey is
out of scope, so an unrecognised label is a question for a person and not a
category. The check is what stops a mode from quietly becoming smaller than it is.

### The intra-zonal trips are apportioned, not discarded

**Decision — a trip whose origin and destination are the same zone is spread over
the units covering that zone in proportion to area.** It has no desire line: one
centroid, no length, nothing to apportion along.

The alternative was to drop them, and the cost of dropping them is not a small
loss of precision. They are **1,841,452 trips a day, 20.0%** of what the 2023
survey measures in the four modes, and they are concentrated in exactly the mode
the study cares most about: 39% of the walking under fifteen minutes and 22% of
the walking over it, against 2.2% of motorcycle travel. Dropping them would
remove a fifth to two fifths of pedestrian exposure, and it would remove more of
it from a unit built of large zones than from one built of small ones, which is a
bias by place and not just a shortfall.

Two rules rather than one, then, but for a mechanical reason and not a
methodological one: a zero-length line cannot be apportioned along its length.
The two endpoint allocations exported beside the variable use the same area rule,
so that "a zone is in a unit" means one thing in the module and the alternatives
differ from the variable only in which geometry they use.

### The records the geometry contradicts, found by looking at the map

**Decision — a record whose two zones are further apart than its mode could have
covered in the duration it reports is dropped, and the run says how many and
which mode they came from.**

It was found by drawing the desire lines and looking at them. The pedestrian map
was a tangle of lines crossing the whole city, for a mode whose trip-weighted
median line is 1.3 km. Chasing it: the extreme record is **82.3 km in 15
minutes**, and it is not an artefact of taking centroids for large peripheral
zones — those two polygons are 61.8 km apart at their nearest points and do not
touch.

The duration is the trustworthy half of the record, and it was checked before it
was used: 2023's `duracion_min` runs 3 to 14 minutes on the under-fifteen walking
category and 15 to 439 on the over-fifteen one, so it agrees with a column derived
independently of it. What is wrong is the pair of zones, or the mode, and the file
does not say which. What is certain either way is that the line drawn from such a
record is a line nobody travelled, and that it spreads pedestrian exposure across
units the walker never entered.

**The test is the most forgiving one available.** It compares the *shortest
distance between the two zone polygons* — the best case the traveller could
possibly have had, not the centroid distance the line will actually use — against
a generous ceiling speed times the record's own duration. The ceilings are 6 km/h
on foot, 25 by bicycle and 80 for the two motor modes, all well above what the
city allows sustained over a whole trip. A record that fails could not have been
made however the trip ran inside its own zones.

What it removes from 2023:

| Actor type | Records | Trips per day | Share of the mode |
|---|---:|---:|---:|
| `PEDESTRIAN` | | 889,649 | 14.6 % |
| `BICYCLE` | | 53,600 | 4.8 % |
| `MOTORCYCLE` | | 7,404 | 0.7 % |
| `CAR` | | 10,257 | 0.5 % |
| **All four** | **5,344** | **960,910** | |

**It is almost entirely a pedestrian problem**, which is the worst place for it:
a seventh of the walking, in the mode the study is most concerned with, was being
spread along corridors nobody walked. The three motorised modes lose under one per
cent between them, which is itself evidence the test is not catching ordinary
variation — a threshold that removed a similar slice of every mode would be a
threshold set too tight.

**The ranking of the units does not move.** Bicycle on a typical weekday runs
Kennedy, Patio Bonito, Bosa at the top and Usme-Entrenubes, San Cristóbal, Lucero
at the bottom before and after. What changes is the pedestrian line kilometres
inside the units, from 28,184 to 8,025, because the removed lines were long by
construction. The map is the clearest evidence: the pedestrian figure goes from
lines crossing the city to short local structure, which is what walking looks
like.

**What is given up, and it is real.** If the error was in the mode rather than in
the zones — a bus journey recorded as walking — then a genuine trip has been
removed rather than reclassified, and the survey's own published total for
walking is no longer reproduced by the study's pedestrian figure. That is why the
removal is a named cause in the balance and not a filter applied before counting:
`960,910.3 impossible for their mode` sits in the accounting beside the 284
records with no expansion factor, and the file's total still closes.

**Declared per year, like everything else.** The ceilings are one table in the
configuration and the duration is a field of the survey. A year that reports no
duration cannot be checked, and the run says so on every execution rather than
passing a check it did not make — that year is not known to be free of these
records, it is unexamined. *Amended by D39: a year that measures walking and
reports no duration now stops the run outright, because the pedestrian series is
read on the fifteen-minute definition and there is no way to state it without a
duration. What is written above still holds for a year that measures no walking,
and for the plausibility test itself.*

**Amended by 2019 — the duration is a declared rule, not a column name.** The
field was `duration_minutes_column`, on the assumption that every survey has a
duration column and only its name changes. Three of the four do not have one at
all in the same sense: 2023 gives minutes outright, 2019 gives a departure and an
arrival stored as fractions of a day, and 2015 gives them as `HH:MM:SS` text. So
it is now `duration_rule`, a small object dispatched through a registry in
`surveys.py` exactly as the day type is, with `DurationFromMinutesColumn` and
`DurationFromClockColumns` written and a third waiting for 2015.
`DurationFromTextClockColumns` is now written too, and it is the last one expected.

This is not a second reader and it is not the shape bending. It is the same
mechanism the day type already had, applied to the second field that turns out to
vary with whoever ran the survey — and it surfaced at the second year, which is
where `docs/mobility-surveys-inventory.md` §7 said such a thing should surface if
it was going to. Nothing downstream changed and 2023's numbers are identical.

**2019's derivation was verified twice before it was trusted**, which is the rule
that made the field worth generalising rather than guessing. Rounded to the
minute it reproduces the delivery's own `Aux_DuraciónEODH2019.csv` on 134,496 of
134,497 records — the exception is a trip from 9:00 to 12:00 that the auxiliary
file records as 81 minutes rather than 180, so the defect is in that file. And
walking of fifteen minutes or more comes out at 3,956,916.53 trips a day against
the 3,952,811.54 the survey publishes in indicator IND_104, 0.10 % apart. The
rounding is not cosmetic: without it, `(0.302083333333333 − 0.291666666666667) ×
1440` is 14.999999999 and a tenth of the walking falls on the wrong side of the
threshold.

What the test removes from 2019, against what it removed from 2023:

| Actor type | 2019 trips per day | Share of the mode | 2023 share |
|---|---:|---:|---:|
| `PEDESTRIAN` | 1,297,400 | 18.7 % | 14.6 % |
| `BICYCLE` | 73,007 | 6.0 % | 4.8 % |
| `CAR` | 16,365 | 0.7 % | 0.5 % |
| `MOTORCYCLE` | 10,975 | 1.2 % | 0.7 % |
| **All four** | **1,397,746** | | |

The same shape in both years — overwhelmingly a pedestrian problem, under 1.2 %
of each motorised mode — which is what a threshold catching a real defect rather
than ordinary variation looks like, now confirmed on a second survey run by a
different administration.

**Amended by 2015 — the derivation is exact, it is not rounded, and the test
removes an order of magnitude less.** Both halves need saying because both look
like defects and neither is.

*The duration.* `HORA_INICIO` and `HORA_FIN` are `HH:MM:SS` text, 503 records cross
midnight, and the derived gap reproduces the delivery's own `DIFERENCIA_HORAS` on
**all 147,251 records** — where 2019's reproduced its auxiliary file on all but one.
It also reproduces both of the survey's published fifteen-minute walking splits:
1,976,421 trips a day under fifteen minutes on the weekday against a published
1,976,421, and 1,037,074.9 on the Saturday against 1,037,075.

*And it is not rounded to the minute, where 2019's must be.* The rounding is not a
convention, it is a repair: 2019 stores a clock as a fraction of a day, so a
quarter of an hour comes back as 14.999999999 and a tenth of that year's walking
falls on the wrong side of the threshold. 2015's clock is exact and has nothing to
repair, so rounding would introduce the error instead — it pushes 619 Saturday
walking trips above fifteen minutes that the survey itself counts below, and the
published Saturday figure stops being reproduced. It changes nothing else: the
plausibility test rejects the same 1,096 records with rounding and without, and
**not one record changes side**. So the choice costs the study nothing and buys an
exact agreement with a published figure, which is the only reason to make it.

*The test removes far less, and it is the delivery and not the declaration.*

| Actor type | 2015 trips per day | Share of the mode | 2019 share | 2023 share |
|---|---:|---:|---:|---:|
| `PEDESTRIAN` | 312,674 | 3.3 % | 18.7 % | 14.6 % |
| `BICYCLE` | 9,297 | 0.6 % | 6.0 % | 4.8 % |
| `CAR` | 1,855 | 0.0 % | 0.7 % | 0.5 % |
| `MOTORCYCLE` | 609 | 0.0 % | 1.2 % | 0.7 % |
| **All four** | **324,435** | **1.9 %** | 13.1 % | 9.4 % |

Each mode's share is against that mode's total as the file holds it, which is what
the two tables above use; the last row is against what the year measures in the
four modes together, which is what `compare_years` prints.

A departure that large is the shape of a misread declaration, so it was chased
until it was explained. It is not the durations: the three years' walking durations
are distributed much alike and 2015 rejects an order of magnitude less in *every*
band, 1.8 % of its fifteen-to-thirty-minute walks against 16.5 % and 13.4 %. It is
not the coarseness of the zoning: the median zone is 0.410 km² in 2015, 0.412 in
2019 and 0.421 in 2023. What it is, is that 2015's zone pairs are genuinely closer
together — at the ninetieth percentile the two zones of a walking record are 1.45 km
apart against 7.07 km in 2019 and 3.63 km in 2023 — and the test only ever removes
the far tail.

**And 2015 is the one year that can be checked against itself here**, because it
reports the latitude and longitude of both endpoints and the pipeline does not use
them. Those coordinates say **2.8 %** of its walking records imply a straight-line
speed above 6 km/h. The zone test rejects **1.8 %**. Two independent readings agree
on the order of magnitude, and the zone test comes out the more forgiving of the
two, which is exactly what a test comparing the *nearest points of two polygons*
should do against one comparing the reported endpoints themselves. The low figure
is a better-geocoded delivery, and it is also the closest thing this study has to a
direct validation of the test.

### How a zone reaches a unit, in the detail that turned out to matter

The survey's zoning and the study's cartography draw the same boundaries from
different sources, and their overlay is full of slivers. Of 1,511 fragments, 593
are boundary noise. Left in, they hand a trip to as many as seven units a zone
does not touch.

**Decision — a fragment below a thousandth of its zone's area is discarded, and
what is discarded counts as falling outside the study area rather than being
redistributed.**

The threshold is not a round number chosen for tidiness. It sits inside an
empirical gap: no sliver exceeds **0.035%** of its zone and the smallest genuine
split is **1.73%** of one, a factor of 49 between them, so any threshold from a
ten-thousandth to a hundredth gives the identical answer. What comes out is **907
zones inside the study area, 896 of them wholly within one unit and 11 genuinely
divided between two**, with the discarded fragments totalling 4,762.90 m² over the
whole city.

**Amended by 2019 — a zone code can name no place, and that is declared per
year.** 2023's trips carry a zone on every record. 2019's do not: 3,994 records of
the measured modes have no zone at all, and 368 more name a code that is not a
zone. Two codes do that. `0` appears on records that carry no municipality and no
UTAM either, so it is that delivery's way of writing "not answered"; `1917`
appears once, above the top of its own zoning's range of 1 to 1908, on a record
whose municipality and UTAM are likewise empty, so it is a capture error.

Both are declared in `zone_codes_meaning_no_zone` and counted in the balance
beside the records with no zone at all, because that is where they belong: they
cannot be put on the map either. Together they are 695,819.3 trips a day, 6.1 % of
what 2019 measures in the four modes. The alternative for `1917` was to let the
run stop over 180.6 trips a day, and the alternative for `0` was to let 54,567.7
disappear into a failed zone lookup; naming both is what makes the decision
visible instead of either.

**The list is declared and never inferred, and a code in neither the zoning nor
the list still stops the run.** This is the one field that could quietly swallow a
real zone, so the reason for each code is written at the declaration rather than
inferred from the fact that it failed to match.

**Amended by 2011 — the zone code is spelled by one function on both sides of the
join.** It had been spelled twice, by two pieces of code that happened to agree: the
zoning cast its float code to an integer and then to text, and the trips were cast
straight to text. That works while the trips carry text, and 2011's arrive out of a
database as a double — `903.0` against the zoning's `903`, one zone to a reader and
two keys to a join that would then have matched nothing at all and taken every 2011
trip with it. `surveys.zone_code_text` now does both sides: a code that reads as a
whole number comes out as its digits, a code that reads as no number keeps its text
so that it still reaches the check that refuses codes the zoning does not have, and
a code with a fraction stops the run, because a zone numbered 810.5 is not a
rounding of anything. Nothing moved for the three years already measured, which is
the point — they were being spelled correctly by accident and are now spelled
correctly on purpose.

**2011 declares no `zone_codes_meaning_no_zone` and that is measured.** No record
of either database names a `0`, a `1000` or any code outside the zoning's range. Its
unplaceable records carry no zone at all, at both ends together, and **they are
exactly the records the consultant imputed** — `DONANTE` is set on 21,515 weekday
records and 440 Saturday ones and on no others, and those are exactly the records
with no zone. The imputation replaced the trips of 8,218 people who travelled and
did not answer the trip module, from a donor of similar occupation, stratum,
locality and day; it did not impute a geography, and the unimputed table carries no
origin or destination zone at all. So there is nothing to decide and nothing to
recover: 12,733 records of the four measured modes, 2,452,373 trips a day, counted
in the balance beside every other trip that cannot be placed. What follows for the
study is that **2011's exposure rests on its directly reported trips**, and that the
non-response correction the consultant performed is undone for this study's
geography — which is a limitation to state and not a defect to fix.

**Amended by 2015 — a zone may be delivered in several pieces, and that is
declared per year too.** `ZATs_2012_MAG.shp` has 948 features and 945 codes: 794
arrives as two detached polygons and 806 as three. The reader refused repeated
codes outright, because two different zones sharing a number would place a trip in
both. What decides between the two cases is the delivery's own arithmetic: its
`AREA` column is per feature and sums to the area of the union in both cases, 8.36 +
7.17 km² and 29.33 + 0.34 + 3.04 km², so the delivery itself treats them as one
zone each. Both are peripheral zones north of the city and no trip in the file
names either.

So `SurveyZoning` gains `zone_delivered_in_parts`, off by default. Declared on, the
pieces are dissolved by code; declared off — which is every other year — a repeated
code still stops the run. It is off by default because the reader cannot tell a
delivered multipart zone from a genuine collision, and the year that has looked is
the one that should say which it is.

**Amended by 2019 — the empirical gap that justifies the sliver threshold is a
property of the 2023 zoning and not a general one.** The threshold was set at a
thousandth of a zone's area because on the 2023 overlay no sliver exceeded 0.035 %
of its zone and the smallest genuine split was 1.73 % — a factor of 49, so any
threshold between a ten-thousandth and a hundredth gave the identical answer. That
argument does not survive the second year.

**On the 2019 overlay there is no gap at all.** The largest fragment below the
threshold is 0.0993 % of its zone and the smallest above it is 0.1002 %: the
distribution runs continuously across the cut, and 264 kept fragments are under
5 % of their zone against five in 2023. The 2019 ZAT boundaries simply do not nest
inside the UPL — 246 of its zones are divided between units against 11 of 2023's —
so the overlay produces a spectrum of genuine partial overlaps rather than a
population of slivers plus a population of splits.

**The threshold is therefore arbitrary for 2019, and the cost of that was
measured rather than argued.** Swept across the same two orders of magnitude, the
largest per-unit pedestrian figure moves **0.16 %** and the city total moves
1,017 trips a day in 4.16 million. The fragments in the continuum are numerous but
tiny in area, so they carry almost no travel. The threshold stays where it is,
and it stays there for a different reason in each year: an empirical gap in 2023,
a measured indifference in 2019.

**What a year must now do is show one or the other.** A year whose overlay has
neither a gap nor indifference would need a threshold argued on its own terms, and
that is a question for a person and not a constant to reuse.

**2015 has no gap either, and its indifference is tighter than 2019's.** Its 1,285
fragments run continuously across the cut — the largest below it is 0.0994 % of its
zone and the smallest above it 0.1007 % — so there is nothing for the threshold to
sit inside. Swept across the same two orders of magnitude, from a ten-thousandth to
a hundredth, **the largest per-unit pedestrian figure moves 0.096 %** and the city
total moves 799 trips a day in 4,459,688, which is 0.018 %.

**2011 borrows 2015's zoning, so it inherits the overlay and not the indifference.**
The fragment distribution is the same one — 1,285 fragments, the largest below the
cut at 0.0994 % and the smallest above it at 0.1007 % — because the overlay is a
property of the zoning and the cartography and not of the year. What is a property
of the year is how much travel sits on the fragments, and that had to be measured
again: swept across the same two orders of magnitude, **2011's largest per-unit
figure moves 0.41 %** and its pedestrian one 0.33 %, against 0.16 % for 2019 and
0.096 % for 2015. Larger than either, because 2011 puts more of its travel in the
peripheral zones the fragments touch, and still two orders below anything a figure
in this study rests on. Three of the four measured years therefore keep the
threshold on measured indifference and one on an empirical gap, which is the pattern
this amendment predicted rather than the exception it feared — and the lesson is the
one it was written for: **two years sharing a zoning share the gap and not the
indifference, so the sweep is re-run per year and never cited from the year before.**

Not renormalising is the other half of the decision. A zone's shares are left as
they come out, so they sum to one where the zone lies wholly inside the study area
and to less than one where part of it is in Soacha, in one of the three rural
units, or in a dropped sliver. Renormalising would fold cartographic noise back
into the units and leave the balance check unable to tell it from a zone that
genuinely lies half outside the city. The three cases stay distinguishable, which
is the whole point of measuring what falls outside instead of absorbing it.

### The table is long, and the mode leaves the column names

**Decision — one row per unit, year, actor type and day type, with the quantities
as columns.** The delivered layer's table was wide over the mode, which was right
while exposure was one undated snapshot of one mode. It stopped being right for
two reasons at once. The table has to join a casualty matrix keyed on unit, year
and actor type, which is a join on three columns the long shape has and the wide
one hides inside its column names. And it has to be interpolated over the fourteen
years no survey covers, which is a group-by in the long shape and a loop over
parsed column names in the wide one.

The mode therefore comes out of the column names. It was there to stop two
exposure layers from colliding in a table with one row per unit; in a table with a
row per mode there is nothing left to collide.

**A missing combination is absent and never zero.** The grid is built complete —
30 units × 4 actor types × 3 day types = 360 rows for 2023 — so a combination
nothing reached is a measured zero the code materialised on purpose, while a day
type a year cannot support is simply not in the table. That distinction is D10
applied to a dimension that is ragged by construction.

**Amended by 2011 — a row can be measured and still not reach the scale of a unit,
and that is a column of its own.** This decision expected 2011's Saturday to be the
ragged case and to be dropped or marked. It is marked, and the decision was the
advisor's: the rows are built, exported and flagged. What the implementation added
is that the flag could not go in `VALUE_STATUS`. That column answers "is there a
number here" — `MEASURED` against `NOT_MEASURED` — and every check in the run
filters on `MEASURED` meaning "rows that have a number in them", so a third value
would have silently taken 120 rows out of each of those checks. Whether a sample
reaches the scale of one unit is a different question and it gets
**`SAMPLE_SUPPORT`**, with `SUPPORTS_UNIT` and `CITY_LEVEL_ONLY`, declared per year
and per day type in `day_types_below_unit_resolution` with the year's own statement
beside it.

2011's Saturday is 4,035 records over 565 households expanding to 14,022,328 trips,
so one record stands for about 3,475 of them and a cell holds roughly 34 records
after four modes and thirty units; seven of the 240 rows come out at zero, three of
them whole units with no cycling at all. What makes the marking a statement rather
than a judgement of ours is that the consultant said it first: Tomo III expanded and
analysed the Saturday *"a nivel de ciudad y estrato socioeconómico"* where the
weekday was analysed *"a nivel de UPZ"*, its non-response imputation used the code
`TL` for every locality together because there was no sample by locality, and Tomo I
adds that *"el nivel de error de esta estimación es mayor que para el día hábil"*.
The figure is still real at the scale it was made for, which is why it is published
rather than dropped.

### The day type, and the thing the survey's own weighting turns out to say

This is the part that was not foreseen and it changed the shape of the table.

**What the expansion factor expands.** The 2023 technical sheet gives the
reference period as the mobility "del día inmediatamente anterior al que se
realiza la encuesta", so the day a trip was made is the day **before** the
interview and a household interviewed on a Sunday reports a Saturday. Taking the
interview date instead would file every one of those trips under the wrong kind of
day. Shifted correctly, the sample is 17,554 weekday households, 2,990 Saturday
and 2,211 Sunday.

**And the weights represent the universe once over all seven reference days, not
once per day.** The household factors sum to 3,623,413 against the 3,667,331
households the technical sheet declares, and the person factors to 9,216,326
against 9,273,186. So summing the trip factor over the weekday households gives
12,585,405, and that number is the weekday **contribution to an average day of the
collection period** — not the trips of one weekday. Divide a Saturday's casualties
by the Saturday figure of 2,249,520 and the rate comes out about seven times too
high, entirely because the denominator covers 13.2% of the universe rather than
all of it.

**Decision — both readings are exported, as two columns, with the conversion
between them in a third.** `TRIPS_PER_AVERAGE_DAY` is the survey's own expansion
apportioned; summed over the day types it is exactly what the file holds, which is
what the balance is checked against, and it is comparable between units but not
between day types. `TRIPS_PER_DAY_OF_TYPE` is that divided by
`DAY_TYPE_UNIVERSE_SHARE`, and it counts one day of that type, which is the only
one of the two a weekday and a Saturday can be compared on. Carrying the share in
the table rather than in the log is what lets a reader derive either column from
the other and check it.

**Amended by 2019 — the day type is not a dimension every year carries.** This
decision was written as though the ragged case would be a year with a Saturday too
thin to publish. It is not. **2019 surveyed one kind of day and no other**, so its
block of the table is 30 units × 4 modes × 1 day type = 120 rows, and `SATURDAY`
and `SUNDAY` are absent from it rather than zero. That is D10 applied to a
dimension ragged by construction, and 2019 exercised it before 2011 got the
chance.

**Amended by 2015 — and the amendment goes the other way: the day type is a
dimension of the study, not a property of 2023.** After 2019 it looked as though
one year in the series carried a Saturday and the rest did not, which would have
made a day-type comparison an artefact of a single delivery. 2015 has a Saturday,
observed and separately weighted, so two of the three measured years carry one and
the question of what the models take is a real question rather than a foregone one.

**What 2015's Saturday is, and how its own flag was made to say so.** The trip
record carries `DIA_HABIL` on 129,521 rows and `DIA_NOHABIL` on 17,730, one always
set and never both. The name does not say which day the second is, and the
interview date does: 2015 asks about the day *before* the interview — its module is
addressed to *"las personas del hogar con 5 años o más que viajaron el día
anterior"* and asks for *"los viajes que hizo entre las 4:00 a.m. del día de ayer y
las 4:00 a.m. del día de hoy"* — and `DIA_NOHABIL` is set on exactly the 3,591
households interviewed on a **Sunday** and on no other. So the day it names is a
Saturday. Tomo IV agrees in its own chapter heading, *"Indicadores día sábado"*.

**And the flag is the proof of the shift rather than a way around it.** Had it been
about the interview day, the 4,237 households interviewed on a Saturday would have
carried it; they do not, because they report a Friday. **No household was
interviewed on a Monday**, so no reference day of the survey is a Sunday, and 2015
has two day types rather than three.

The date and the flag were checked against each other and agree on **all 147,251
records**. The flag is nevertheless what the pipeline reads, for two reasons that
are about the delivery and not about the method: it is what the consultant grouped
by when publishing the matrices the reading is checked against, and one household's
row in the household file is displaced by a column — the date field holds the UTC
offset — so a rule reading the interview date would stop the entire run over one
corrupted record whose eight trips carry a perfectly good flag. That is
`DayTypeFromRecordFlags`, the third entry in a registry designed for four, and it
carries the same `stated_by` field `DayTypeIsAlwaysOne` does, for the same reason.

**Its expansion is 2019's answer and not 2023's, and it was established from the
file.** Each day type's subsample expands to the whole universe on its own: the
household weights sum to 2,967,290 over the 24,622 weekday households and to
3,045,530 over the 3,591 Saturday ones, and the person weights to 9,059,251 and
9,023,719. Three and a half thousand households carrying as much weight as
twenty-five thousand is what a factor that already expands to one day of its own
kind looks like from outside. Read as 2023's, 2015's Saturday would have come out
an eighth of what it is — and it would have looked entirely reasonable.

**Which is also why a check had to change.** `the universe shares of a year add to
one` was true of every year that existed when it was written, because the only year
with more than one day type spread its universe across them. 2015 is the first year
with more than one day type *and* a factor that expands to one day of each, so its
shares are 1.0 and 1.0 and they sum to two — correctly. The check now asks what the
year's own `weight_expands_to` implies: that the shares partition the universe, or
that each of them covers it once. This is the second time a check written inside
one year's assumptions has broken on the next, and it is recorded in section 7 of
`docs/adding-a-survey-year.md` beside the first.

The evidence is not one statement but five, all from the year's own delivery. The
questionnaire's trip module is addressed *"para las personas del hogar con 5 años
o más que se desplazaron el día anterior"* and reads *"los desplazamientos que
realizó el día de ayer, desde las 4 a.m. de ayer a las 4 a.m. de hoy"*. The
cartilla's glossary defines a *viajero* as a person reporting at least one trip on
that previous day. The report states the total as *"en un día típico, se realizan
18,996,286 viajes"*. The published origin-destination matrices — the artefact this
pipeline rebuilds — come only *"en un día típico"*, with peak and off-peak hours
as the sole further breakdown and **no Saturday or Sunday matrix anywhere**. And
the chapter comparing 2019 against 2011 and 2015 lists every difference between
the three surveys without mentioning the reference day.

The data agree: travel participation runs 79.1 % to 80.6 % and trips per person
1.967 to 2.061 across all seven days the fieldwork ran, and about 10 % of trips
are for study on every one of them, which no real Sunday looks like.

**The day-of-week flags were the trap and they were declined.** `p32_lunes` to
`p32_domingo` are asked as *"¿Qué días de la semana realiza este viaje?"* — 13,436
records carry the Saturday flag, and using them would have produced a `SATURDAY`
row that looked exactly like 2023's and measured something else entirely.
Declared recurrence is not an observed day, and a Saturday built that way would
omit by construction every trip made only at weekends, since such a trip was never
reported at all. The column named `DAY_TYPE` has to mean one thing across four
years or it should not exist.

**So the year is declared as `DayTypeIsAlwaysOne`, and the declaration carries its
own evidence.** The rule has a `stated_by` field quoted in the log on every run,
because "this survey covers one day" is a claim about somebody else's fieldwork
and the cost of getting it wrong is a Saturday that silently never existed. A
declaration with no statement warns.

**Amended by 2011 — the day type can be a property of the file and not of the
record, and that is the one thing that changed the declaration.** Its `DiaTipico`
database holds 122,361 trips over 15,592 households and its `DiaSabado` 4,035 over
565: different samples of different households, in separate Access databases with
the same schema. Nothing on a record says which kind of day it is, and a rule
reading an already-loaded frame cannot see which file the frame came from.

`MobilitySurvey.trips` is therefore a **tuple of `TripSource`**, and a `TripSource`
pairs one table with the day type that file carries — or with `None`, meaning the
file holds more than one kind of day and the year's rule says which. The reader
tags every row with its source and `DayTypeFromSource` reads the tag. Three
properties were the point of taking it this way rather than any other:

- the ragged fact sits in the declaration, beside the path it is a fact about;
- **no day-type handler opens a file.** A rule that declared the Saturday database
  and loaded it would have been the smallest diff and the worst shape — the second
  reader this design has refused since 2023;
- the three years delivered as one file did not change meaning. They declare a
  one-entry tuple with no day type on it, and 720 rows came out unchanged.

*The shape first proposed for this did not close.* It was a mapping,
`trips={source: day_type}`, which cannot express a single file carrying three day
types the way 2023's does; the value would have had to be `None` and the field
would have meant two things. Putting the day type on the source is the same idea
with one meaning.

**And 2011 needed a reader, which went in as the third registry in the module.**
`AccessTable(path, table)` sits beside `DelimitedTable` and `read_table` dispatches
over `surveys._TABLE_READERS`. `pyodbc` is imported inside the reader so the other
three years still run where the 64-bit Access driver is absent, and the rows are
fetched through the cursor rather than through `pandas.read_sql`, which warns on a
raw connection. This is what the "one reader, four declarations" promise means in
practice: a container nobody had seen cost one entry in a registry, not a second
path through the module.

**What the second column then says is not credible, and it is a property of the
survey and not of the arithmetic.** Rescaled to the universe, the region makes
1.778 trips per person on a weekday, 1.802 on a Saturday and 1.749 on a Sunday.
Bogotá does not travel as much on a Sunday as on a Tuesday. Whether respondents
reported a generic day rather than the specific previous one, or the calibration
flattens the difference, the survey as delivered carries almost no day-of-week
signal — while still splitting the sample three ways and leaving the Saturday and
Sunday rows resting on 2,990 and 2,211 households instead of 22,755. The run says
so on every execution, because a column that looks like a rate will be used as one.

### The figures: two per combination, and the map shows a day

Every combination of year, actor type and day type gets two figures — a
choropleth of how much travel the unit ends up with, and the desire lines that
put it there. Twelve of each for 2023, twenty-four files with the scale-bar
variants, and the same for every year added.

**They are filed rather than listed, because four years come to 192 files.** Year,
then mode, then kind:

```
figures/exposure/
├── 2023/
│   ├── bicycle/
│   │   ├── choropleth/     exposure__2023_bicycle_weekday.pdf      (3 + 3 scalebar)
│   │   └── desire_lines/   desire_lines__2023_bicycle_weekday.pdf  (3 + 3 scalebar)
│   ├── car/  motorcycle/  pedestrian/
├── 2019/                   the same shape, one file per kind: it has one day type
└── 2015/  2011/            the same shape again, one folder per session
```

The year is outermost because it is the unit of work and of provenance: a session
implements one survey and creates one folder without touching the others. The
mode is next because a choropleth and the desire lines behind it explain each
other and are read together. The kind is innermost, and **every figure in the tree
sits under one of the two kinds**, so that a recursive match on
`*/choropleth/*.pdf` means "every choropleth of every year" with no exception to
remember.

**A year folder holds as many files as the year has day types, which is the tree
saying something true.** 2023 has three and 2019 has one, so 2023 contributes
twenty-four figures and 2019 eight. The `delivered_2019_bicycle/` folder that used
to sit at the end of this tree is gone with the layer.

**The names are repeated between the tree and the file names on purpose.** A
figure has to be copied into the document's own folder before LaTeX can see it,
so a file called `bicycle_weekday.pdf` would arrive there with its year stripped
off by the move. Redundant in the tree, self-identifying out of it.

**Only one file per figure is written, and it is the one with the scale bar.**
Both used to come out of every run, the bar-less one for slides and the other for
the page. In practice the study is producing figures for itself, so half of what
was written was read by nobody — twenty-five files instead of fifty.

The bar-less copy is not deleted, it is behind
`MAP_EMIT_NO_SCALEBAR_VARIANT`. The reason it stays in the pipeline at all is
that the alternative anyone reaches for is worse: opening the PDF and removing
the scale bar by hand. That does not work well, because the figure is vector and
the bar is an object to hunt down in Illustrator rather than a layer to hide —
and, decisively, the edit is gone the next time the route runs. Every generated
artefact here is reproducible from a run, and a retouched figure is not. A
presentation copy is one constant and one re-run.

Inverting which file carries the mark follows from that. **The standard figure
now takes the plain name and the optional copy is the one suffixed**, because a
`__scalebar` suffix on the only file distinguishes it from nothing. The rule
lives in `maps.figure_variants`, which every map in the pipeline goes through —
the choropleths, the desire lines and the reference map — so a run cannot end
with some of them having a presentation copy and others not.

**The scale-bar variant stays a suffix and never a folder.** It is the same figure
rendered twice; making it a directory would mean adding or removing a scale bar
changes the path in the `.tex` rather than one word in the file name.

**A map is 9 inches tall rather than 5.** These are vector figures, so the size is
not about resolution: it is the ratio between the map and the type, which is
fixed in points. At 5 inches a map came out the size of a postcard, 7 by 13 cm,
with the unit numbers and the colour bar crowding the territory. At 9 it is about
13 by 23 cm, the numbers shrink relative to the city, and the colour bar gains
room for seven ticks where it had four. The figures are read on screen while the
study is being built, and that is what the value is set for.

### The figures a deliverable will want are a different rendering, and not yet built

Everything above is sized and captioned for reading on a screen during the work.
A figure going into the written report or a slide differs in three settings, and
they are recorded here rather than built, because no deliverable needs them yet
and guessing a page size before there is a page is how a setting gets fixed
wrongly.

**Height**, which is one constant already.

**Whether the identifying text is drawn inside the figure.** Today it is, and it
would be duplicated by a LaTeX `\caption`. The two figures are not the same case.
On the desire-line map the whole title is caption material and would go. On the
choropleth the text is the colour bar's label, and part of it must stay whatever
the caption says — a bar with no unit on it means nothing — so what leaves is the
mode and the day, and what remains is `viajes por día`.

**Whether the bar-less copy is emitted**, which is the constant above.

The piece that makes the second one safe is that **the pipeline should export the
captions**, one row per figure, naming the file and the Spanish text that
identifies it. Then a `\caption` is copied from a generated file instead of being
typed, which is D33's argument for emitting tables as LaTeX applied to figures: a
number retyped by hand is a number that can be retyped wrongly, and there is no
way to tell afterwards which run it came from. Building that is the job of the
session that produces the first deliverable figure.

The delivered layer's folder is named for what it is rather than for what it
measures, because it is no longer the study's exposure and the tree should not
suggest otherwise. It carries **2019** — the year established in this decision,
not the 2023 its own per-inhabitant column still divides by — it sorts after the
year folders because letters follow digits, and when 2019 is implemented the
folder goes with the layer.

**The choropleth shows `TRIPS_PER_DAY_OF_TYPE` and not the variable.** This is
the decision inside the figures that matters. A map titled "viajes por día" has
to carry the trips of a day, and the variable counts a day type's share of an
average day: on the Saturday map that is six times too small, for no reason
except that a seventh of the households were surveyed about a Saturday. Drawing
the variable would have made two of every three maps say something false in their
title.

The cost is visible and it is the right cost to pay. Rescaled, the Sunday map is
the most intense of the three in all four modes — Bogotá does not cycle more on
Sunday than on Tuesday, and the figure says so plainly instead of hiding it in a
column nobody plots. The Sunday map is a diagnostic, the weekday map is the
result, and both are labelled.

**The colour ramp is shared across the day types of one mode and never across
modes.** Sharing it within a mode is what makes the three days comparable at a
glance, which is the whole point of the day being a dimension; without it all
three fill their own ramp and look equally intense however different their levels
are. The cost is small — in the worst case, bicycle on a typical weekday, the map
uses 53% of its ramp — while sharing across modes would draw bicycle and
motorcycle at a fifth of a ramp scaled by walking and leave neither pattern
readable.

**The desire-line map exists because this pipeline draws its own input.** No other
figure in the study does: a predictor is measured on a layer somebody else built,
and a reader can go and look at that layer. The lines here exist only because this
code made them, so without a figure of them there is no way to see what was made.
Three things about it differ from every other map in the pipeline, each for a
reason:

- **The units carry no numbers.** A label under three thousand crossing lines is
  unreadable, and an unreadable label is worse than none — it says the figure was
  never looked at.
- **The frame is the city and not the lines.** They run to Zipaquirá and
  Facatativá, 154 km apart against Bogotá's 23, so a map framed on them would put
  the study area in 15% of its width. They are drawn whole and simply leave the
  frame, which says what a clipped line could not: the travel continues past the
  edge of the study.
- **Width and opacity grow as the square root of the trips a line carries.** The
  spread forces it: on a typical weekday the median pedestrian line carries 233
  trips and the heaviest 7,474. Drawn uniformly the map would show which pairs
  were surveyed rather than where the travel is, and the heaviest tenth of the
  lines carries between a third and a half of all the trips. The heaviest are
  drawn last so a corridor is not buried under the light lines that follow it.

Only the inter-zonal trips have a line. The intra-zonal ones are on the
choropleth and cannot be here, which is the same fact that made them need a rule
of their own, and the caption says so rather than leaving the two figures
silently disagreeing.

### The denominator gets its year back

**Decision — the exposure table carries `POPULATION`, per unit and per year, and
`POPULATION_2023` is retired from it.** D36 pinned the delivered layer's
per-inhabitant column to a single declared year and made it descriptive, for a
good reason: the numerator had no year, and dividing an undated snapshot by a
moving denominator produces a rate that changes with its denominator alone.

That reason is gone. The survey numerator carries the year it was collected, so
the denominator is read at that same year and the column name has nothing left to
disambiguate. `TRIPS_PER_AVERAGE_DAY_PER_INHABITANT` is a rate and not a
description, and it can enter a model with a time dimension. The delivered
layer's table keeps its own `POPULATION_2023` column, because that table is now a
reference and its figures have to stay reproducible — and, since the layer is
2019 and not 2023, that column is also now known to divide by the wrong year,
which is recorded in D36 rather than silently corrected in a table nothing models.

### ~~The delivered layer stays, as a reference and not as the variable~~ Retired by 2019

*What this said, and it was right while it lasted: the 181 lines kept being
measured on every run and their table was filed under `reference__` rather than
`analysis__`, because D35, section 13 of the verification report and
`deliverables/plan.md` all quote figures measured on it. Its numbers were
unchanged by the survey work, which is how the reimplementation was checked:
556,997.5804 trips per week and 113,269.3056 per day in the layer, 530,018.5282
and 107,844.3591 apportioned to the units, 1,087.5609 km of 1,219.2583 inside
them, Spearman 0.813, 0.798 and 0.781 against the three alternatives, Torca still
an observed zero.*

**Amended by 2019 — the layer is out of `EXPOSURE_LAYERS` and is no longer
measured.** The reason it was kept was that the study had no other reading of the
2019 bicycle travel it sampled. It now has one, for four modes and thirty units,
and continuing to measure a 9.6 % sample of a survey the pipeline reads in full
would be computing a worse version of something it already has.

**It was not removed on trust, and the check it made possible was worth more than
the tidiness.** The layer is a subset of the same records the survey holds, so
every one of its origin-destination pairs had to appear among the pairs the
pipeline builds from that survey, with no pair attributed more trips than the
survey holds for it. Both hold: **160 of 160 pairs present, none over-attributed**,
compared on the records the two readings share. Two independent readings of one
source — one received as finished geometry, one built from the trip records —
agreeing on 160 pairs is the strongest confirmation the survey reader could get.

The comparison also says something about the layer. **The plausibility test
removes 15 of those 160 pairs outright**, 8,905.8 of the layer's 113,269.3 trips a
day and 7.9 % of it, and takes part of a sixteenth. The delivered layer therefore
carried records this study judges impossible for the mode that reported them, and
the fifteen come in symmetric pairs — a there-and-back between the same two zones
— which is what an outbound and return trip of one household looks like.

**What stays.** `config.BICYCLE_DESIRE_LINES` keeps its declaration, naming the
file, so a quoted figure can be recomputed by hand; section 13 of the verification
report stays in place as the record of what was measured on it; and the machinery
that measures a declared line layer stays in `exposure.py`, because it is generic
and a future delivery could use it. What goes is the entry in `EXPOSURE_LAYERS`,
the `reference__delivered_*` tables and the `delivered_2019_bicycle/` figure
folder. The route runs that half only when a layer is declared, so nothing is left
behind computing an empty table — which is one of the legacy defects this project
exists to avoid.

### Each year says for itself what its factor expands to

**Decision — `weight_expands_to` and `published_total` are declared per year and
never inherited.** 2023's factor expands one surveyed trip to an average day of
the collection period, which is why the day types need rescaling. A year whose
factor already expands to one day of the record's own kind declares that instead,
its universe shares come out as one, and no rescaling happens.

This is the field that must not be guessed, because guessing it is invisible:
every figure stays plausible and every one of them is out by the ratio between
the two readings. The point is sharper for the years still to come. 2015 has
**four candidate columns** and none of them is identified yet; 2011 and 2019 have
one each but neither has been checked. Inheriting 2023's answer would give all
three a number that looks right.

`published_total` is what turns the belief into a demonstration: the run
reconstructs the survey's own published total from the column it declared and
stops if the two disagree. For 2023 it reproduces 16,390,908 exactly. A year with
no published total found yet declares none, and the run says on every execution
that the reconstruction was checked against nothing — which is the state a
missing check should be in, rather than silently passing.

### One reader, four declarations

The machinery is written once. Adding 2019, 2015 or 2011 is one `MobilitySurvey`
in `config.py` and nothing else: the reading, the number parsing, the mode
mapping, the zone geometry, the line building, the apportionment, the checks, the
dictionary and the figures all follow from the declaration.

The one place the years genuinely differ beyond a column name is how each says
which kind of day a trip was made on — an interview date in 2023, a flag on the
record in 2015, day-of-week flags in 2019, a separate database in 2011. That is
declared as a rule object and dispatched through a registry, so a year adds a
small rule beside the others rather than a second way of reading a file. A year
whose rule is not written yet fails with a message naming itself, which is the
behaviour that keeps the gap visible.

**Each survey was commissioned by a different administration**, and that is the
reason the declaration is as wide as it is. The naming, the catalogue, the mode
vocabulary and the way the reference day is stated all change with whoever ran
the survey; none of it is knowable in advance and none of it can be inherited.
What is fixed is everything downstream — the measurement, the four actor types,
the shape of the table, the figures and where they are written — and a year that
cannot be made to fit that shape is a finding to report rather than a shape to
bend. `docs/mobility-surveys-inventory.md` §6b is the contract and
`docs/adding-a-survey-year.md` is the order to work in; a session implementing a
year reads both before it opens a survey folder.

**2019's session has one job the others do not: it retires the delivered layer,
and it should validate against it before doing so.** That layer is an incomplete
2019 — 181 lines, bicycle only, every record an exact triple from the 2019 survey
— so every one of its 160 origin-destination pairs must appear among the pairs
the pipeline builds from that survey, with no more trips attributed than the
survey's own total for each. Two independent readings of one source agreeing on
160 pairs is the strongest confirmation the survey reader can get, and a
disagreement is a defect found before anything rests on it.

### A year is checked against the years already measured

**Decision — the run compares each survey against the ones before it, and warns
where they disagree.** `exposure.compare_years` prints what each year measures
per mode and what each sets aside; with one year those are a baseline, and from
the second onwards they are the check.

It exists because of what the declaration is: six things per year, each
established from that year's own files, and every one of them able to be wrong in
a way that still produces plausible numbers. Nothing inside a year catches that
— the balance closes just as neatly on a misread column as on a correct one,
because it checks the reading against itself.

The year before is what catches it. Bogotá does not remake its travel between two
surveys, so three things are read as symptoms rather than findings: a mode share
moving more than ten points, a per-inhabitant trip rate moving more than 35 %, or
a Spearman below 0.70 between two years' orderings of the thirty units. That last
one is the same measurement that established the delivered layer was not what it
claimed, at 0.362.

**All three warn and none fails.** A real change of that size is possible and the
run cannot tell it from a misreading, so it refuses to let one pass unremarked
rather than pretending to judge it. The baseline is in §6b of the inventory.

### Amended by 2019 — the comparison is made on the column two years share

**Decision — `compare_years` reads `TRIPS_PER_DAY_OF_TYPE`, never
`TRIPS_PER_AVERAGE_DAY`.** This corrects a defect that existed from the moment
this comparison was written and could not be detected until a second year arrived.

`TRIPS_PER_AVERAGE_DAY` is what the file holds, so every within-year check uses it
and must: it is the quantity the balance closes on. But what it holds depends on
what that year's factor expands to. 2023's spreads the universe over seven
reference days, so its weekday rows carry **77.2 %** of a weekday; 2019's expands
to its one typical day, so its rows carry all of it. Compared on that column,
2023's weekday is measured against three quarters of itself.

What that produced, before and after:

| Actor type | 2019 per inhab. | 2023, wrong column | change | 2023, right column | change |
|---|---:|---:|---:|---:|---:|
| `PEDESTRIAN` | 0.554 | 0.420 | −24 % | 0.544 | −1.8 % |
| `CAR` | 0.243 | 0.158 | −35 % | 0.205 | −15.7 % |
| `BICYCLE` | 0.105 | 0.076 | −28 % | 0.098 | −6.2 % |
| `MOTORCYCLE` | 0.091 | 0.080 | −12 % | 0.104 | +15.1 % |

**The wrong version was nearly a false alarm and was certainly a false picture.**
Car came out at −35.0 % against a threshold of 35 %, so the check was one decimal
from warning about an artefact of its own arithmetic. And all four modes fell by
roughly the same amount, which is the tell: four modes measured independently do
not collapse in unison, and a uniform factor across all of them is arithmetic and
not a city. Corrected, the picture is one a reader can check against Bogotá —
walking and cycling flat, motorcycle up, car down.

**Mode shares and the Spearman are unaffected**, because a share is a ratio inside
one year and a rank cannot be moved by a constant factor. So the pedestrian
finding below stands exactly as it did; what was wrong was every level and every
rate.

**The general lesson is the one D38 already states about `weight_expands_to`, one
step further on.** That field must never be inherited because a wrong value is
invisible. The same is true of anything computed *across* years from a column
whose meaning that field controls — and a check written against a single year
cannot see it, because a comparison with nothing to compare against cannot be
wrong. The third year should assume the same class of defect is waiting wherever
two years are put side by side.

### The pedestrian ranking fired, and the investigation is the point
Pedestrian exposure orders the thirty units at **Spearman 0.662** between 2019 and
2023, below the 0.70 floor, while car, motorcycle and bicycle sit at 0.947, 0.893
and 0.886. Everything else agrees: no mode share moves ten points, no trip rate
moves 35 %, and the two years set aside almost the same fractions for the same
three reasons.

It was chased to the bottom and it is not a misread declaration.

- **The reading is verified against a published sub-city table.** Indicator IND_64
  of the 2019 delivery gives the trips of each of its 134 UTAM. Grouping our
  reading by the household's UTAM under the indicator's own rule reproduces **132
  of the 134 within 0.01 %, 130 of them to the last decimal**, and the total over
  them is 15,965,583 against 15,961,478. That single comparison exercises the
  expansion factor, the mode labels, the derived duration and the household key at
  once, which the city total cannot.
- **It is not the geometry.** The disagreement concentrates in the north-west —
  Tibabuyes falls from 8th to 28th, Rincón de Suba from 7th to 21st, Suba from
  23rd to 29th, Niza rises from 29th to 10th — and over that stretch the two
  zonings are nearly identical: 8 zones against 8 in Tibabuyes, 14 against 14 in
  Rincón, 28 against 28 in Niza, and the area each zoning assigns to each unit
  differs by under a tenth of a per cent.
- **It is not the intra-zonal rule.** Split into its two halves the correlation
  barely moves: 0.690 on the inter-zonal part alone against 0.662 on the whole.
- **It is not the allocation rule either.** The three allocations agree with each
  other unit by unit: Tibabuyes falls 71 % by length share, 70 % counted whole at
  the origin and 70 % at the destination; Niza rises 146 %, 155 % and 145 %. If
  the desire lines were putting trips in the wrong place the three would diverge.
- **It is not the sliver threshold.** Swept from a ten-thousandth to a hundredth,
  the largest per-unit pedestrian figure of 2019 moves 0.16 % and Niza 0.2 %.
- **And the raw trip files say it with no pipeline at all.** Summing each survey's
  own expansion factor over its walking trips by origin zone — one zoning for both
  years, since they number the same polygons the same way; no desire lines, no
  apportionment, no day-type rescaling, no duration filter — Tibabuyes' share of
  city walking falls **56 %**, Rincón de Suba's 44 %, Suba's 41 %, and Niza's
  rises **90 %**. Nothing this project does can be the cause of a difference that
  is already in the two files.

So it is what the two samples say about walking in Suba, and **the study cannot
tell a real change from sampling variation there**. That is the honest answer and
it is the reason the check warns rather than fails. It is material for the report:
a jury reading a pedestrian rate for Tibabuyes in 2019 and another in 2023 will
see them differ by a factor of three, and the answer is that two surveys run four
years apart by different administrations disagree about that corner of the city
more than the study can resolve.

### The balance, and what the run checks

The run reads 100,174 trip records for 2023 and 134,497 for 2019, and accounts for
every one of them.

| | 2019 | 2023 |
|---|---:|---:|
| The four measured modes | 9,262,670.3 | 9,221,240.5 |
| Modes deliberately outside the study | 7,640,049.7 | 6,208,757.0 |
| Impossible for the mode that reported them | 1,397,746.3 | 960,910.3 |
| Records with no origin or destination zone | 695,819.3 | 0.0 |
| **Total in the file** | **18,996,285.6** | **16,390,907.8** |

The two sides of that check are different groupings of the same column, so it is a
check and not a restatement: a mode lost between the mapping and the totals would
show there and nowhere else. **284 of the 2023 records carry no expansion factor
and are dropped**; the survey's own published total is the sum that excludes them,
so they are outside the universe the file describes rather than a hole in it, and
imputing a weight for them would be inventing trips. The run says so on every
execution. Every 2019 record carries one.

Then the apportionment balances, per actor type and per day type rather than in
aggregate — an aggregate over four modes can close while two of them are wrong in
opposite directions. Over the twelve combinations of 2023 and the four of 2019 the
largest gap between what was apportioned to the units plus what fell outside and
what the file holds is **0.000000 trips**.

**1,697,260 trips a day fall outside the thirty units in 2023**, 18.4 % of the
four modes, and **1,806,461 in 2019**, 19.5 %. That is the twenty neighbouring
municipalities the survey also covers plus the three rural units the study does
not have, and it is measured rather than absorbed. The two years agreeing to a
point on that share is itself a check on the zoning of the newer one.

### What it produced

For 2023, 21,467 desire lines built between zone centroids, 145,460 km in all with
a median of 4.26 km, from 26,316 inter-zonal groupings; 1,197 intra-zonal
groupings spread by area. For 2019, 27,437 lines, 178,248 km, median 4.16 km, from
31,134 inter-zonal groupings and 1,078 intra-zonal ones. Apportioned to the units
on a typical weekday:

| Actor type | 2019 trips/day inside | Of which intra-zonal | Line km | 2023 trips/day inside | Of which intra-zonal | Line km |
|---|---:|---:|---:|---:|---:|---:|
| `PEDESTRIAN` | 4,160,690 | 1,270,486 | 13,040 | 4,274,636 | 1,366,277 | 8,025 |
| `CAR` | 1,827,723 | 39,298 | 81,864 | 1,611,352 | 40,190 | 39,028 |
| `BICYCLE` | 787,563 | 52,491 | 18,391 | 773,132 | 37,787 | 12,434 |
| `MOTORCYCLE` | 680,233 | 12,830 | 35,104 | 818,851 | 10,421 | 27,510 |

The trip counts are on the comparable column, `TRIPS_PER_DAY_OF_TYPE`, because
they put two years side by side; the kilometres are not a trip count and do not
scale with the expansion factor, so they are as measured.

The pedestrian kilometres are the smallest of the four in both years despite the
mode being by far the largest in trips, which is what a mode of short local
journeys should look like and what the figure showed it was not before the
impossible records came out. That it holds on a second survey, read through a
different set of column names and a duration derived rather than given, is the
strongest evidence available that the plausibility test measures the thing it was
built to measure.

The bicycle ranking is Kennedy, Patio Bonito, Bosa at the top and Usme-Entrenubes,
San Cristóbal, Lucero at the bottom, which is the south-western flat against the
southern hillsides and is what anyone who knows the city would predict. It is not
a check, but it is the kind of external agreement that would have been worth
worrying about if it had been absent.

**The lines are straight, and that limitation carries over from D35 unchanged.**
The kilometres inside a unit are a share of a chord nobody rode. The two endpoint
allocations are measured beside the variable on every run for exactly that reason,
and on the 2023 weekday they order the units almost identically to the variable
for pedestrians (0.995 and 0.993) and much less so for motorcycles (0.786 and
0.794) — the rules are different variables, not two scales of one, which is why
the choice had to be made on an argument rather than on agreement. The spread
across modes is itself informative: a pedestrian trip is short enough that
apportioning it along its corridor and counting it whole at its origin land in the
same unit, and a motorcycle trip is not.

### What is still open

**Which day type the models take.** A weekday, an average of the three weighted by
how the week is actually made of them, or the day type matched to the day each
crash happened on. The third is the most defensible and the most work, and it
needs the day type of the crash records, which nothing has yet resolved. It stays
open until the model specification is decided, and the table is shaped so that any
of the three is a filter or a group-by rather than a re-run.

**Whether a day-type comparison is supportable at all.** The flat trip rate across
the week is either a real property of Bogotá's travel that contradicts every
expectation, or an artefact of how the survey was asked or weighted. Resolving it
means reading the expansion document of the survey, not the technical sheet, and
it should be resolved before any document compares a Saturday with a weekday. If
it turns out to be an artefact, the honest answer is to publish the weekday only
and say why, and the table already supports that.

*2019 made this both sharper and easier.* Sharper, because a day type only 2023
has cannot enter a model with a time dimension: a Saturday series over four survey
years would have one point in it. Easier, because the weekday was then the only day
all the measured years shared, so publishing the weekday alone — the fallback if the
day-type signal turned out to be an artefact — was also the only choice the series
allowed. This decision was ready to be closed that way.

**2015 reopened it, and gave the evidence that was missing.** It carries a real
Saturday: 3,591 households surveyed about one, separately weighted, expanding to a
whole Saturday on their own. A Saturday series now has two points and would have
three if 2011's turns out usable, so it is no longer a property of one year.

**And 2015's Saturday behaves the way a Saturday should, which is what 2023's does
not.** Against its own weekday, inside the thirty units, its car travel rises 50 %
while walking falls 32 % and cycling 17 %; Tomo IV says the same of the whole
region in words, car up "aproximadamente el 45 %" and walking down 29 %. 2023's
Saturday, rescaled to the universe, says a Saturday carries as much travel as a
Tuesday. So the flat trip rate is a property of the 2023 delivery and not of
Bogotá's travel — which is the answer this section said had to come from an
expansion document, arrived at instead from a second survey that did not need
rescaling at all.

That does not settle which day type the models take, and it changes what the
question is. It is no longer "is a Saturday measurable"; it is whether a Saturday
measured well in 2015 and badly in 2023 can be put in one series. **That is a
decision for my advisor and it is not taken here.**

*2011 adds a third Saturday and it does not settle it either.* Its Saturday behaves
the way one should — against its own weekday, inside the thirty units, walking falls
29 % and cycling 18 % while car travel rises 89 %, which is 2015's pattern — but it
rests on 565 households and is marked `CITY_LEVEL_ONLY`, and the survey itself only
ever claimed it for the city. So the series has three Saturdays of three kinds: one
measured well at the unit (2015), one measured well at the city and marked at the
unit (2011), and one that needs rescaling to be read as a Saturday at all and then
says a Saturday carries as much travel as a Tuesday (2023). Whether those three are
one series is the question, and it is the same question as before with more evidence
under it.

**And 2011 raises one the other years could not.** Its two day types expand to
**different territories** — the weekday to Bogotá plus seventeen municipal cabeceras
and the Saturday to Bogotá alone, because *"la muestra para el día sábado se diseñó
solo para Bogotá"*. Inside the thirty units, which are all in Bogotá, that is
largely absorbed, since what falls outside is measured rather than redistributed.
It is nevertheless a difference of universe and not of sample, and a document
comparing 2011's Saturday with its weekday has to say so.

**What the delivered layer's 181 lines were selected by** remains unknown, and now
it does not matter for any result. It is recorded because the question was asked in
D35 and a reader deserves to know it was pursued to the point where the answer
stopped mattering rather than dropped.

---

## D39 — The pedestrian mode is measured twice, and the series is read on the fifteen-minute one

**Kind:** Methodological. It decides which walking trips the study's denominator
counts when four years are put in one series, and it amends D38 without reversing
it.

**Status:** Closed. Decided by my advisor on 2026-09-09, against the measurement
below.

**Built:** Yes. `src/surveys.py` and `src/exposure.py`, route `exposure`. Run
`run_20260909_214626`: 960 rows, 21 columns, 40 checks, none failed, and every
one of the 960 rows identical to `run_20260908_101110` on every column it already
had.

**Amended by 2005, which is the year this decision was written for without knowing
it.** 2005 collected walking of more than fifteen minutes and nothing shorter, so
D39's second column is the only one it can supply — and the consequence runs the
other way too: its `TRIPS_PER_DAY_OF_TYPE` holds long walking where every other
year's holds all walking. **The value is exported and not nulled**, because the
measured table is the record of what the surveys say and 2005 did measure walking;
what a null would have said is that there is no figure, which is false. What is not
true is that the figure is comparable, and that is declared instead, per column and
per actor type, in `not_comparable_on`. Measured, anchoring an interpolation on it
would spread the difference of definition as a 34 % annual rise through 2007–2010
where the comparable column reads 18 %.

This is also where the full column's own justification stops applying. D39 keeps
that column partly because the crash source cannot separate a short walk from a
long one, so it is the one whose denominator matches the numerator's category. For
2005 that is no longer true: its denominator excludes short walks while the
numerator counts their casualties. **Any pedestrian rate quoted for 2005 carries
that sentence.**

### The measurement that forced it

D38 decided that every walking trip is in, whatever its length, and gave two
reasons that are still true: 2011 and 2015 cannot offer the narrower category at
all, and the crash source cannot separate a short walk from a long one either, so a
denominator that excluded short walks would divide casualties by an exposure that
does not contain them.

That decision was taken when one year was implemented, and a comparison with
nothing to compare against cannot be wrong. With four years measured, the
pedestrian series on the column two years are comparable on is this — one weekday,
the whole surveyed region, from run `run_20260908_101110`:

| | Every walking trip | Index | Fifteen minutes or more | Index |
|---|---:|---:|---:|---:|
| 2011 | 8,136,778 | 100 | 3,733,664 | 100 |
| 2015 | 5,576,943 | 69 | 3,600,522 | 96 |
| 2019 | 6,941,798 | 85 | 3,956,917 | 106 |
| 2023 | 6,203,098 | 76 | 4,104,040 | 110 |

**The full column swings 46 % and does not move in one direction; the
fifteen-minute column rises monotonically after 2015 and its whole range is 14 %.**
The difference between the two is not the city. It is the instrument: 2011's
questionnaire asks for the short walk outright — *"para viajes realizados
completamente a pie incluya siempre los viajes al trabajo y estudio; para otros
propósitos solo aquellos cuya duración sea mayor a 3 minutos"* — and tells the
interviewer not to ask about stages for a trip made wholly on foot, while 2015's
states no floor, no such prompt, and records walking as a stage with its own minute
counter. The 2015 delivery's own Tabla 43 confirms it from the other side:
pedestrian **stages** fall 17 % between the two surveys where pedestrian **trips**
fall 31 %.

The other three modes have no such problem and need no second definition. Their
movements are large but they are the city: motorcycle travel roughly doubles between
2011 and 2015, which the 2015 delivery publishes as +102.82 % and calls the largest
change in its survey.

**And this is not a private worry.** The Sarmiento group names the same thing as a
limit on comparability in Delclòs-Alió et al. (2022), of which two of Bogotá's
neighbours in that study are examples: *"some of the surveys used in the study
explicitly omit short walking trips… not only this might partially limit
comparability, but it is also likely that actual levels of walking may be even
higher than what we have described here."*

### The decision

**Both definitions are measured, both are exported, and the series is read on the
fifteen-minute one.** The exposure table gains a second pedestrian quantity beside
the first; every other mode carries the same number in both, because no other mode
has two definitions.

**The second column is a second measurement and never a rescaling of the first.**
The city-level ratio between the two definitions is known per year, so multiplying
looks like a shortcut. It is not one: counted at the origin zone, each unit's share
of city walking under the two definitions correlates at Spearman 0.97–0.98 while the
ratio between the two shares runs **0.68 to 1.45 across the thirty units** — the
ranking survives and the levels do not. And that understates it, because it ignores
where the definitions diverge most: **short walks are about twice as intra-zonal as
long ones**, 49.1 % against 25.1 % in 2011, and an intra-zonal trip is apportioned
over a zone's units by area while an inter-zonal one is spread along a line. The two
definitions pass through different spatial operators in different proportions, so
the fifteen-minute column is produced by running the apportionment again with the
duration filter applied to the pedestrian records.

- **The full column stays** because it is what the surveys measure, because D38's
  two reasons for it have not stopped being true, and because the crash source
  still cannot separate a short walk from a long one — so the full column is the
  one whose denominator matches the numerator's category.
- **The series is read on the fifteen-minute column** because a fifteen-year
  interpolation cannot be laid over a quantity whose definition changes between two
  of its four anchors. That is the same rule as `TRIPS_PER_DAY_OF_TYPE`: **anything
  that puts two years side by side reads the column the two years mean the same
  thing on.**
- **The report shows what the choice costs.** Both columns exist, so the models can
  be run against each and the document can say whether the conclusions move. If
  they do, that is a finding about how much of the pedestrian result rests on a
  category the surveys disagree about.

**What is given up, and it is real.** Between a quarter and a half of walking leaves
the modelled denominator: 4,403,115 trips a day in 2011, 1,976,421 in 2015,
2,984,881 in 2019 and 2,099,058 in 2023. Those are real journeys with real
casualties attached, and the fifteen-minute rate therefore over-states risk per trip
by a factor that differs by year. The full column is exported precisely so that the
factor can be computed rather than argued about.

**The threshold is fifteen minutes and it is not ours.** It is the split the 2011
report publishes as its own second modal partition, the split the 2015 delivery
publishes for both of its day types, the split 2023 builds into its two walking
labels, and the definition the 2005 survey used for the whole mode. Choosing any
other number would mean losing every one of those published controls.

### What building it settled

**One column, `TRIPS_PER_DAY_OF_TYPE_OVER_15MIN`, and only on the comparable
basis.** Putting two years side by side is the only thing this definition exists
for, and `TRIPS_PER_AVERAGE_DAY` is the basis on which no two years can be put
side by side; the universe share stays in the table, so a reader who wants the
other basis can divide. The table goes from twenty columns to twenty-one and the
run from thirty-four checks to forty: one balance per year against the file's own
fifteen-minute total, and two more that a rescaled column could not pass.

**The second column travels through the apportionment beside the first rather
than after it.** The narrower definition is a second number on the same
origin-destination pair, written when the records are grouped, so both go through
the same line-length shares and the same zone-area shares in one pass. That is
what makes it a second apportionment and not a second reading of the survey: no
file is opened twice, no geometry is built twice, and the two columns cannot
diverge through anything but the trips behind them. The four city totals of the
table above are reproduced to the trip.

**And the per-unit measurement that justified it comes out stronger on the
variable itself than it did at the origin zone.** The argument for reapportioning
was measured on each unit's share of city walking counted at its origin zone: the
ranking barely moved, Spearman 0.972 to 0.982, while the ratio between the two
shares ran 0.68 to 1.45. On the apportioned variable — the column the models will
actually read — the ranking is as stable, **Spearman 0.953 to 0.992**, and the
ratio is wider still: **0.562 to 1.453 across the four years**. Suba holds 0.562
in 2023 and Torca 1.453 in 2015, so a single per-year factor would have given
Suba nearly twice the long walking it has. The check that catches that is per unit
and per year, and it is in the run.

**The duration stops being optional, which amends D38.** D38 allowed a year to
declare no `duration_rule`: what it lost was the plausibility test, and the run
said so on every execution rather than pretending to have made a check it had not.
That is still true of the plausibility test. It is not true of this column, because
there is no way to state the fifteen-minute definition without a duration and the
pedestrian series is read on it. **A year that measures walking and declares no
duration rule now stops the run**, naming the two ways out — declare the rule, or
take the year out of `MOBILITY_SURVEYS` — because both are decisions for a person
and the alternative is a null column that the interpolation would meet four stages
later. All five declared years have a duration rule, so nothing moved — and 2005,
which arrived after this was written, is the year it would have caught: its whole
pedestrian column is the fifteen-minute one.

**A walking record with no duration would be counted in the full column and left
out of the narrow one, and the run says so.** None of the five years has one; a
year that did would understate its own fifteen-minute column by exactly those
records, which is why it is a warning and not a silence.

### What the column says once it is inside the thirty units, and it is not what the city says

This is the finding the decision could not have had in advance, and it belongs
beside D39 rather than inside it.

The table that decided D39 is the **whole surveyed region**. Inside the thirty
units — which is the only place the study's exposure exists — the two definitions
look like this on one weekday, from the same run:

| | Region, every walk | Region, 15 min+ | Index | Inside the units, every walk | Index | Inside the units, 15 min+ | Index |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 8,136,778 | 3,733,664 | 100 | 5,477,038 | 100 | 2,563,176 | 100 |
| 2015 | 5,576,943 | 3,600,522 | 96 | 4,459,658 | 81 | 3,012,134 | 118 |
| 2019 | 6,941,798 | 3,956,917 | 106 | 4,160,690 | 76 | 2,494,690 | 97 |
| 2023 | 6,203,098 | 4,104,040 | 110 | 4,274,636 | 78 | 2,883,103 | 113 |

**The fifteen-minute series is monotone over the region and is not monotone inside
the units.** Its range over the region is 14 points; inside the units it is 21,
and it changes direction at 2019. The full column is still worse — 24 points
inside the units and a 46 % swing over the region — so the decision holds and the
narrower column is still the one two years can be compared on. But the improvement
the decision was taken on is smaller at the scale the models work at than it is at
the scale it was measured on, and any document quoting the 100/96/106/110 index
has to say which of the two it is quoting.

**What accounts for the difference is the funnel, and it is a property of each
delivery rather than of the definition.** The share of the region's own
fifteen-minute walking that reaches the thirty units is 68.7 % in 2011, 83.7 % in
2015, 63.0 % in 2019 and 70.3 % in 2023 — the same ordering, and very nearly the
same numbers, as the full column's 67.3 / 80.0 / 59.9 / 68.9. 2015 keeps most of
its walking because it is the best-geocoded delivery and the plausibility test
removes 3.3 % of it; 2019 keeps least because that test removes 18.7 %. So the
2015 and 2019 anchors of the pedestrian series carry a delivery effect that D39
does not remove and cannot, and **the 2015 → 2019 step of the interpolated
pedestrian series is where it lands**.

That is a limitation of the series and not a defect of this column. It is recorded
here so that D40's interpolation is read knowing it, and so that the report says it
before a reader finds it.

---

## D40 — Exposure between survey years is interpolated as a rate, not as a level

**Kind:** Methodological. It decides what the study's exposure is in the fourteen
years no survey covers, which is most of the panel.

**Status:** Closed on the method. Decided by my advisor on 2026-09-09. **Whether
the 2005 survey joins the series is open, and the measurement that decides it has
now been made** — see the last section.

**Built:** Yes. `src/interpolation.py`, route `interpolation`. Run
`run_20260910_154603`: 6,480 rows, 17 checks, none failed, on the exposure table of
`run_20260910_154319`.

**Amended by 2005, and the amendment is the one this decision asked for.** The
survey was implemented on 2026-09-10 and is now the fifth anchor, so **the weekday
held block no longer exists**: 2007 to 2010 are interpolated between 2005 and 2011
where they were held flat from 2011. The panel's provenance moves from 960
measured, 2,280 interpolated and 3,240 held to **960, 2,760 and 2,760**. The years
it replaced were overstated much as the comparison predicted — 2007's pedestrian
falls from 2,480,903 to 1,455,173 and its motorcycle from 264,143 to 100,527, while
the car barely moves, which is the one mode the held rate nearly fitted.

Three consequences are worth carrying:

- **Anchors are read per column and per actor type**, because a year may measure a
  column and not be comparable on it. See D39's amendment.
- **Two places assumed every anchor lies inside the window** and 2005 is the first
  that does not. That assumption was removed twice over: first by covering the survey
  years in the population panel and counting the anchors the window contains, and
  then, on 2026-09-10, by **building each series over its own span** — the window
  extended back to that series' earliest survey. The weekday runs 2005–2024 and
  carries 2006 as an ordinary interpolated year; the Saturday and the Sunday run
  2007–2024, because moving the window instead would have forced a Saturday for a
  year whose survey never measured one. The window still opens in 2007, where the
  casualty series opens, and a model gets it by filtering on the year.
- **The new segment is the widest of the four.** 59 of the 480 unit × mode × step
  combinations move by more than a factor of two on 2005 → 2011 against 47 on
  2011 → 2015, and the motorcycle passes it in all thirty units. The block that was
  an extrapolation is now an interpolation and it is the least steady of the four. `docs/interpolating-the-exposure.md` was the specification
and is now the record.

### What has to be filled, and what is already annual

The casualty series runs 2007–2024 observed and **2008–2024 corrected**, because
D30 takes 2007 out of the corrected set: a year that cannot say which of two
vehicles was which cannot support an inter-mode matrix. The surveys sit at 2011,
2015, 2019 and 2023 — evenly spaced, every four years, which is the friendliest
shape this problem could have had.

So of the eighteen observed years: **four are measured, nine fall between two
measured years, four fall before the first and one after the last.** On the
corrected set it is four, nine, three and one.

**One thing is already annual and it is the denominator's denominator.** D36 put the
population in as a panel, one number per unit and per year, covering 2005–2035. Every
year the interpolation has to fill already has a population for every one of the
thirty units, from a source that is not the survey.

### The decision

**Interpolate the rate; recover the level from the annual population.**

For each unit, actor type and day type:

1. take the rate at each measured year, `TRIPS_PER_DAY_OF_TYPE / POPULATION`;
2. interpolate that rate **log-linearly** between adjacent survey years — a
   constant proportional change per year rather than a constant absolute one, which
   keeps every value positive and treats a mode growing from a small base the way
   growth actually works;
3. recover the level as `rate(t) × POPULATION(unit, t)`.

**Why the rate and not the level.** The level is the product of two things that move
at different speeds and are known with very different confidence: how many people
live in a unit, which we know every year from the census panel, and how much each of
them travels by a given mode, which we know four times. Interpolating the level
throws the annual knowledge away and smears the demographic change across four-year
steps. Interpolating the rate uses each source for what it is good for. In a unit
whose population grew 40 % between two surveys — and several of the western
expansions did — the two give visibly different answers, and only one of them is
using information we actually have.

**Outside the measured range the rate is held flat, not extrapolated.** For
2007–2010 the rate is 2011's; for 2024 it is 2023's. The population still moves, so
the level still moves. Prolonging a trend instead would mean extrapolating four
years backwards from a slope fitted to two points — and for the pedestrian mode that
slope is the 2011→2015 segment, which D39 has just established measures a change of
instrument. **A trend extrapolated from an artefact is worse than no trend.**

**The unit is the point, and the interpolation is per unit for that reason.** The
whole study is thirty units over eighteen years; a city curve handed identically to
every unit would not be an exposure panel. So every one of the 30 × 4 × day-type
series is interpolated on its own trajectory, and the cost of that is that each
inherits its own unit's sampling noise. Measured on the column the series is read
on, which is D39's fifteen-minute one: **67 of the 360 unit × mode × step
combinations move by more than a factor of two between adjacent surveys, and 47 of
those 67 are on the 2011 → 2015 step** — the segment that already carries an
instrument change, an imputation without geography and a smaller share of city
totals reaching the units than 2015 delivers on any mode. The widest is Chapinero's
cycling rate at 8.85×. The run reports this on every execution and does not fail on
it; whether the trajectories need shrinking toward the city's is an open question,
asked with that table in hand.

*(On the full pedestrian column the same measurement gives 64 and 45. Walking is
the whole difference — the other three modes carry the same number in both columns
— and the figure quoted here is the one measured on the column the interpolation
actually runs on. The 41 this decision carried until 2026-09-10 was an arithmetic
slip against its own table, which summed to 45.)*

**Every cell says where it came from.** The interpolated table carries
`EXPOSURE_PROVENANCE`, one of `MEASURED`, `INTERPOLATED` or `HELD`, and
`YEARS_TO_NEAREST_SURVEY`, which runs 0 to 4. This is the same discipline as
`VALUE_STATUS` and `SAMPLE_SUPPORT`: a number that was measured and a number that
was constructed are different facts, and a table that cannot tell them apart invites
a reader to treat fourteen constructed years as fourteen observations. It also lets
a model weight by distance to a measured year, or drop the held block, without
re-running anything.

### What was rejected, and why it is worth writing down

**The nearest-survey step function.** Each year takes the closest survey, no
interpolation at all. This is not a straw man: it is what **Zewdie et al. (2024)**
does, in one of the three papers this thesis is built on and with Sarmiento as
second author — a single 2019 survey as the Poisson offset for the five crash years
2015–2019. It has a real virtue, which is that it never invents a number. It was
rejected because it puts three discontinuities inside the panel and wastes the one
gift this data set gives us: four measured years, exactly four years apart, over the
middle of the series. A step function is the right answer when you have one survey;
we have four.

**Prolonging the trend outside the measured range.** Rejected above.

**Anchoring the annual city total on an external indicator per mode** — motorcycle
and car registrations, TransMilenio ridership, bicycle counts — and interpolating
only each unit's spatial share. **This is the better method and it is not rejected;
it is deferred.** It is more defensible than anything above, because it replaces an
assumption about the shape of a curve with an annual measurement of the curve
itself. What it costs is one external series per mode, each of which has to be
obtained, checked against the survey years it overlaps, and shown to measure the
same thing the survey measures — which is the whole of this project's method applied
four more times. It is the natural second version of this decision and the report
should say that it is.

### Whether 2005 joins the series, and how that gets decided

Adding the 2005 survey would turn the only backward extrapolation into an
interpolation between measured points — three or four years of the panel, depending
on which casualty set the models take.

**It is not implemented and it is not on disk.** Nothing of 2005 is under `data/`.
Including it is a full implementation pass: the download, the six things
§6b requires, and a fifth zoning, over six years that contain the opening of
TransMilenio's phases II and III.

**Its pedestrian mode only exists under D39's definition.** The 2005 survey counted
walking of more than fifteen minutes and nothing shorter — the 2011 report says so
outright, *"a diferencia de la encuesta del año 2005 en la cual sólo se tomaron en
cuenta viajes mayores a 15 minutos para el modo a pie"* — and publishes its own
fifteen-minute partition to be comparable with it. So D39 is what makes 2005
includable at all; without it there would be nothing to discuss.

**Decision — not now, and the question is settled by measurement rather than by
argument.** The interpolation is built on the four years, the held rate produces a
2007–2010 block, and that block is compared against the 2005 figures the 2011 report
already publishes. If it lands far from them, 2005 is implemented and the reason for
implementing it is a number. If it lands close, the held rate was adequate and no
session was spent on it. Doing the cheap thing that tests the expensive thing is the
same move this project made with the delivered desire-lines layer, and it paid then.

### The measurement, made on 2026-09-10, and it does not land close

**Where 2005's figures actually are: chapter 5 of Tomo III of the 2011 delivery**,
titled *"Comparación de indicadores de las encuestas de movilidad 2005-2011"* and
written for exactly this purpose. It is the only place either delivery states 2005's
numbers at all, and it is comparable to this study by construction: it says that
everything in it counts trips *"incluyendo los viajes a pie mayores o iguales a
quince (15) minutos"*, which is D39's second pedestrian column and nothing else. The
figures are declared in `config.PUBLISHED_2005` with that citation beside them, so
the comparison is made by the run rather than typed into a report.

**The prose of that chapter pins three modes and the figures beside it pin all
four.** Paragraphs 5.15 and 5.16 give walking, motorcycle and public transport and
say only that *"el vehículo privado se mantiene entre el rango del 14% y el 16%"*
across the two years. Figura 5.16 and Figura 5.17, on page 265, are the two modal
splits drawn in full, and they say which end of that range belongs to which year —
**car is 16 % in 2005 and 14 % in 2011, not a flat 15 % in both** — and they state
the bicycle, which the prose never does. Both were read before this comparison was
made, and the difference matters: on the prose alone the car row appeared to grow
1.36× and it actually grows 1.19×.

**The comparison is made over the whole surveyed region and not over the thirty
units.** Every figure any of the four deliveries publishes is stated on that
territory, and the share of a mode that reaches the units differs by mode and by
year — 53 % of 2011's cycling against 75 % of its car travel — so a per-unit
composition compared against a published one would measure the funnel and call it a
change in the city. The `exposure` route therefore exports
`reference__survey_city_totals`, which is what each survey measures per mode and day
type before any of this study's removals, and the `interpolation` route reads it.
What makes the region comparison transfer to the panel is that holding a rate flat
holds the composition with it: **inside the thirty units the held block's
composition at 2007 is within 0.10 points of the anchor's at 2011**, and that
remainder is only the different pace at which the units grow.

**The control, and it is as good as this project has had:**

| Mode | Published 2011 | This study, 2011 | Gap |
|---|---:|---:|---:|
| `PEDESTRIAN` | 56.0 % | 56.8 % | +0.8 |
| `BICYCLE` | 10.0 % | 9.3 % | −0.7 |
| `MOTORCYCLE` | 6.0 % | 6.3 % | +0.3 |
| `CAR` | 28.0 % | 27.7 % | −0.3 |

**Eight tenths of a point at worst, on four modes**, which is what says the 2005
column is being compared against something.

**The test.** The held block cannot differ from 2011 at all, so this is 2005 against
2011 with two years of population growth in between:

| | `PEDESTRIAN` | `BICYCLE` | `MOTORCYCLE` | `CAR` |
|---|---:|---:|---:|---:|
| Published 2005 | 41.2 % | 8.8 % | 2.9 % | 47.1 % |
| The held block | 56.8 % | 9.3 % | 6.3 % | 27.7 % |
| Gap | **+15.6** | +0.5 | **+3.3** | **−19.4** |

**The bicycle is the one mode that barely moves**, which is a finding rather than a
null result: cycling grew at almost exactly the rate the rest of the city's travel
grew, so its *share* is flat while its level more than doubles. Walking and the car
are where the composition turns over.

And the same thing as growth, which is what the held rate asserts. A held rate moves
only with its denominator, so over the six years it grows 1.06×. The band is what
the rounding of the two pie charts allows — the shares are labelled in whole per
cent, which is nothing on a mode at 46 % and half the value on a mode at 1 %:

| | Published 2005 | Published 2011 | Growth | Band | Held |
|---|---:|---:|---:|---|---:|
| `PEDESTRIAN` | 1,358,000 | 3,696,000 | 2.72× | 2.58–2.87× | 1.06× |
| `BICYCLE` | 291,000 | 660,000 | 2.27× | 1.75–2.99× | 1.06× |
| `MOTORCYCLE` | 97,000 | 396,000 | 4.08× | 2.27–9.53× | 1.06× |
| `CAR` | 1,552,000 | 1,848,000 | 1.19× | 1.11–1.27× | 1.06× |

**All four contradict the held rate even at the most forgiving end of their
rounding** — but they do not contradict it equally, and the report has to say so.
Motorcycle and bicycle are the strong rows: large factors, and neither is subject to
the walking caveat or to the transfer rule. Walking is larger still and is the row
the chapter itself warns about. **Car is contradicted by five per cent**, 1.11×
against 1.06× at the bottom of its band, which is inside any reasonable allowance
for two surveys run six years apart by different consultants. On the car alone this
test would be inconclusive.

**And the source publishes the held quantity itself.** The same chapter gives trips
per person on a weekday by socioeconomic stratum for both years — 0.95 → 1.48, 1.08 →
1.58, 1.27 → 1.68, 1.51 → 2.12, 2.01 → 2.31, 1.92 → 2.31. **All six rise, by 15 % to
56 %, 36 % on the median.** Holding a rate flat is holding trips per person flat.
Nothing in the comparison is closer to the assumption being tested and nothing
contradicts it more directly.

**Five caveats, all of them printed by the run.** 2005 counted a transfer as a trip
of its own, so its total is inflated and the real growth is *larger* than the
published one — the gaps above are conservative. The chapter says the walking of the
two surveys was collected differently even at the same threshold, so the pedestrian
row is the weakest of the four and motorcycle and car are subject to neither that
nor the transfer rule. The 2015 delivery's Tomo IV states that a direct comparison
with 2005 **is not possible** and publishes 2005 only as reference values — a
statement about levels, and the reason this test decides whether to implement 2005
rather than anchoring anything to it. The shares are read off pie charts in whole
per cent, hence the bands. And **these are the figures the 2011 delivery published
about 2005, not the 2005 survey itself**: what a reading of its own records would
support is a different question and a larger one.

**What this settles and what it leaves.** It settles that **the held block is the
weakest part of the panel and is weak in a direction the data can name**: it sits
15 to 19 points away from the only external evidence about those years on the two
modes that turn over, on a comparison whose control agrees to eight tenths of a
point, and it asserts a flat trips-per-person where the source measures a 36 % rise.
It does not settle that implementing 2005 is worth a session — that is my advisor's
decision, and it is a full implementation pass, a fifth zoning and six years
containing TransMilenio's phases II and III. What D40 promised was a number rather
than an impression, and the number is above.

**And the decision was taken: 2005 was implemented on 2026-09-10**, so this section
is the measurement that decided it rather than a pending question. What it bought is
what it promised — 2007 to 2010 are interpolated between two measured years and the
weekday held block no longer exists — and the years it replaced were overstated much
as the gaps above predicted. D40's amendment at the head of this decision is the
outcome, [`implementing-2005.md`](implementing-2005.md) is the year's record, and the
test above became a control on the reading: this study lands 2.9 points from the
published 2005 composition against 0.8 for 2011.

**One thing the same exercise found that this decision did not ask for.** The
interpolated curve was compared against the one annual series the study already has,
its own casualty count, and the disagreement is 2020: pedestrian casualties halve
while the interpolated pedestrian exposure rises 4 %, because 2020 sits on a straight
line between 2019 and 2023 and a log-linear interpolation cannot see a pandemic. The
constructed years 2020–2022 are the second-weakest block in the panel after the held
one, and unlike the held one their weakness has a date.

### What this leaves open

**Whether the per-unit trajectories need shrinking toward the city's.** Named above
and measured; the answer must not be to interpolate the city and give every unit the
same curve, because the unit is what the study is about.

**Which casualty set the panel is built against**, and therefore whether the window
starts at 2007 or 2008. The observed set has eighteen years and 2007 among them; the
corrected set has seventeen and does not. It is not this decision's to take — D31
says both sets exist and the models are to be run against both — but the
interpolation has to produce whichever window is asked for, so it is built over the
full 2007–2024 and the choice stays a filter.

**Whether the held block belongs in the models at all.** ~~Four of eighteen years~~
**on the weekday, none, since 2005 was implemented**: 2007 to 2010 are interpolated
and the held block is now the Saturday's two ends, the whole Sunday and 2024. The
question stays open for those, and for the same reason — a block with no within-unit
behavioural variation, only demographic, is a block a panel estimator will treat as
information. `YEARS_TO_NEAREST_SURVEY` is in the table so that this can be tested
rather than assumed.

**Whether the 2011→2015 segment should be interpolated at all for the pedestrian
mode.** D39 removes the definitional part of that segment's problem. It does not
remove the rest: 2011 also delivers a smaller share of its city totals to the units
than 2015 does on every one of the four modes — 67.3 % of its walking against
80.0 % — because the sixth of its records that were imputed carry no geography and
because its shorter reported durations fail the plausibility test more often. That is a level difference between two adjacent anchors that is a property of
the delivery, and the interpolation runs straight through it.

### What building it settled

**A route of its own that reads a file rather than a survey.** `interpolation` reads
the exposure table another run exported and the population panel, and writes one more
table beside them. It could have rebuilt the measured table in memory instead, and
that was refused for two reasons: it would mean reading five surveys again to produce
a table this stage is forbidden to change, and it would make the interpolation look
like a second measurement of the same thing. What it costs is that the run has to say
which run it read, and it does — in the log, in the record funnel and in the exported
dictionary.

**Two rates, not one.** This decision sketched a single `TRIPS_PER_INHABITANT`. There
are two, because the procedure runs twice — once per pedestrian definition — and each
level has to be recoverable from its own rate rather than from the other's. They are
named `TRIPS_PER_DAY_OF_TYPE_PER_INHABITANT` and
`TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_PER_INHABITANT` rather than `TRIPS_PER_INHABITANT`,
because the measured table already carries a per-inhabitant column computed on
`TRIPS_PER_AVERAGE_DAY` and the two tables are joined to each other. Two columns with
one name and two meanings is the failure this pipeline has already had once.

**A measured year's level is carried through and not recomputed.** Dividing by the
population and multiplying back is right to a part in 1e16, and this table has to
reproduce the measured one exactly, so the arithmetic is simply not done where there
is nothing to compute. The check compares all 960 measured rows against the measured
table bit for bit, on every column the two share.

**Twenty-one cells of each column are filled linearly**, because a rate of exactly
zero at one end of a segment makes the logarithm undefined. They are the three
constructed years of the 2011 → 2015 segment sitting on top of the seven zero cells
of 2011's Saturday. **No epsilon was introduced**: nudging a zero to 1e-9 to keep the
logarithm alive would turn "nobody cycled in San Cristóbal on a Saturday in 2011"
into a rate that rises by orders of magnitude across the segment, which is arithmetic
inventing a trend out of an observed zero. It also means the guarantee that the
fifteen-minute column stays inside the full one — which log-linear interpolation
provides and linear interpolation does not — had to become a check rather than an
argument.

**`SAMPLE_SUPPORT` is inherited and the weaker anchor wins.** A value built between
2011's Saturday and 2015's rests on a sample the consultant themself only claimed at
the scale of the city, and a constructed value cannot be better supported than what
it was constructed from. 960 rows carry `CITY_LEVEL_ONLY`, all Saturdays, over
2007–2014 — eight years marked by an anchor that measured one of them.

**The Sunday rests on a single anchor and is held flat across the window**, which
this decision left to a person and the implementation had to choose a default for.
It is held rather than dropped for the reason D36 gave for the population panel over
the snapshot: a table that holds it filters down to one that does not and the reverse
is impossible. What makes that safe rather than misleading is that its 2,040
constructed rows all say `HELD`, all sit at up to sixteen years from their only
survey, and the run warns about them by name on every execution. **Whether a Sunday
series belongs in any model is still a decision for a person**, and it is now a
decision that can be taken by filtering rather than by re-running.

**The volatility table moved, and it moved because of D39.** Measured on the column
the series is actually read on, **67 of 360** weekday unit × mode × step combinations
move by more than a factor of two and **47** of them are on the 2011 → 2015 step,
against 64 and 45 on the full pedestrian column. Walking is the whole difference; the
other three modes carry the same number in both. The run prints both figures. *(The
41 this decision carried until 2026-09-10 was an arithmetic slip against its own
table, which summed to 45 from the first measurement.)*


---

## D41 — The panel is compared against the casualty series, and that comparison is a diagnostic and never a constructor

**Kind:** Methodological. It decides what the study's own casualty counts are allowed
to do to the exposure panel, which is the one place where the numerator of every
model could contaminate its denominator.

**Status:** Closed on the diagnostic. The one thing it left open — whether the
pandemic years are patched by the mirror assumption instead of by the interpolation,
which is the last section — **was decided on 2026-09-10 and is D42**. This decision
stays as the reasoning that made that one possible: it is where the two assumptions
are shown to be the same system with the assumption moved, and D42 is where one of
them is applied to three named years.

**Built:** Yes. `src/interpolation.py`, route `interpolation`. Run
`run_20260910_031907`: 4,200 rows in `reference__exposure_against_casualties`.

### The system, stated properly

A casualty count is roughly **exposure times risk**. The casualties are known for
all eighteen years and the exposure for four, so in every constructed year there is
**one equation and two unknowns** and something has to be assumed about one of the
two factors. There is no way out of that by being careful.

- **D40 assumes the exposure is smooth** — log-linear in the rate between surveys —
  and lets the risk take whatever fluctuation is left.
- **The mirror is to assume the risk is smooth** and let the exposure take it.

**These are the same underidentified system with the assumption placed on different
factors, and calling the second one circular and the first one not would be wrong.**
D40's construction uses the casualty series exactly as much: it just spends its one
degree of freedom on the other quantity. Saying so is the point of this decision,
because the alternative is a report that presents a coin flip as the natural choice.

### Which of the two is actually smoother, measured

It is an empirical question, and the four survey years are where both quantities are
known. Between adjacent surveys, at the city and per mode, the number of steps in
which each quantity moves by the larger factor:

| | Exposure moves more | Risk moves more |
|---|---:|---:|
| Against the **observed** casualties | 4 of 12 | **8 of 12** |
| Against the **corrected** casualties | **7 of 12** | 5 of 12 |

**On the observed set the risk looks far more volatile, and almost all of that is
the recording change.** The extreme is the car between 2019 and 2023: implied risk
×2.66 observed against ×1.40 corrected. Once ρ is taken out it is close to a tie.

**So D40's assumption is not better supported than its mirror.** It is one of two
defensible choices and the report has to say so rather than presenting it as the
obvious one. What this decision adds is that the *cost* of the choice can be
measured cell by cell, and it is.

### Why it is still not the constructor

Three reasons, and the first is the one that decides it.

**It would assume the shape of the estimand.** The study exists to estimate risk as
a function of urban features. D40 assumes the shape of the **denominator**, which is
a nuisance parameter: what it contaminates is an auxiliary quantity. Building the
exposure from an assumed risk trajectory assumes the shape of **the answer**, and a
model fitted on it would recover part of what was put in. That asymmetry, and not
circularity, is the difference between the two.

**The matrix is two-sided.** The study's artefact is not "pedestrian casualties", it
is "pedestrian casualties in collisions with a car". Those depend on the pedestrian
exposure **and** on the counterpart's. Inverting for one of them needs a functional
form linking the pair — a safety-in-numbers exponent — and that exponent is one of
the things the thesis wants to estimate. The one-sided inversion below is adequate
for a diagnostic and would not be adequate for a panel.

**And ρ leaves no usable choice.** Inverting the observed set injects the recording
change straight into the exposure — the car's implied risk reaching 266 against a
corrected 140 is what that looks like. Inverting the corrected set means the
exposure depends on which casualty dataset was chosen, and **D31 exists to have both
run side by side**: two runs that do not share a denominator are not comparable, so
the one comparison D31 was written to make would be destroyed by the thing meant to
improve it.

### What it produces

One row per unit, year, actor type and casualty dataset, on the weekday exposure —
a casualty count is annual and carries no kind of day, so the pairing is declared
rather than smuggled in as a dimension.

| Column | What it holds |
|---|---|
| `AFFECTED_PARTIES` | the casualty count of that type, in that unit and year |
| `TRIPS_PER_DAY_OF_TYPE_OVER_15MIN` | the exposure the panel carries |
| `IMPLIED_RISK` | the first over the second: what the panel implies about risk |
| `SMOOTH_RISK` | that same quantity carried across the constructed years by D40's own rule |
| `IMPLIED_TRIPS_PER_DAY_OF_TYPE_OVER_15MIN` | casualties over the smooth risk: the exposure the mirror assumption gives |
| `IMPLIED_OVER_INTERPOLATED` | the diagnostic |

**The last column reads two ways and they are the same number**, which is what makes
it worth exporting:

    implied exposure / interpolated exposure = implied risk / smooth risk

because both sides are the casualty count cancelling. So one column answers "how far
would the exposure move under the opposite assumption" and "how far does the risk
this panel implies depart from a smooth path". It is exactly one at every survey
year, and its distance from one in a constructed year is how much of the movement
the panel is putting into the risk rather than into the exposure. The run checks the
identity rather than asserting it.

### What it says, and it is cleaner than expected

At the city, against the corrected casualties, the ratio by year:

| Year | | `PEDESTRIAN` | `BICYCLE` | `MOTORCYCLE` | `CAR` |
|---|---|---:|---:|---:|---:|
| 2008 | `HELD` | 0.77× | 0.75× | 0.77× | 0.89× |
| 2009 | `HELD` | 0.73× | 0.71× | 0.67× | 0.80× |
| 2010 | `HELD` | 0.97× | 1.08× | 1.05× | 1.07× |
| 2012–2018 | `INTERPOLATED` | 0.95–1.08× | 0.93–1.12× | 0.90–1.13× | 0.89–1.15× |
| **2020** | `INTERPOLATED` | **0.60×** | 0.99× | **0.72×** | **0.67×** |
| 2021 | `INTERPOLATED` | 0.75× | 1.12× | 0.92× | 0.95× |
| 2022 | `INTERPOLATED` | 0.97× | 1.05× | 1.00× | 1.00× |
| 2024 | `HELD` | 1.04× | 0.95× | 1.05× | 0.92× |

And per cell, over the 1,560 constructed unit-year-mode cells of the corrected set,
how many would move by more than a factor of 1.5:

| Block | Cells beyond 1.5× | Of | Share |
|---|---:|---:|---:|
| `HELD` — 2008–2010 and 2024 | 98 | 480 | 20 % |
| `INTERPOLATED` 2020–2022 | 64 | 360 | 18 % |
| `INTERPOLATED` everywhere else | **30** | 720 | **4 %** |

**The two assumptions agree almost everywhere and disagree exactly where the panel
was already known to be weak.** Outside the held block and the pandemic the
disagreement is four per cent of cells and the city ratios sit within about a tenth
of one; inside them it is a fifth of cells and the city ratio reaches 0.60. That is
the strongest thing this diagnostic could have said: it means the interpolation is
not being rescued by luck in the ordinary years, and it means the two weak blocks
are weak for reasons that show up independently of how they were found.

**Two of the numbers are worth reading on their own.** In 2020 the pedestrian ratio
is 0.60 and the **bicycle ratio is 0.99** — the panel's cycling exposure for the
pandemic year needs no correction at all while its walking exposure would have to
fall by two fifths. Cycling holding up through 2020 while other travel collapsed is
what happened in most cities that measured it, so the diagnostic is picking up
something real rather than noise. And the 2020 pedestrian figure says the panel
implies **walking risk per trip fell by 40 % in the pandemic year**, which
contradicts what is known about emptier and faster streets: the implied risk is
implausible in a specific direction, which is evidence about the exposure and not
merely about the fit.

**The noise floor is not the objection it looked like.** The median constructed cell
rests on 88 pedestrian casualties, 124 motorcycle, 37 car and 34 bicycle, so Poisson
noise alone is worth 9 % to 17 % of the ratio. Only 45 of the 1,560 cells rest on
fewer than ten casualties and exactly one saw none at all — and that one implies an
exposure of zero, which is the method failing rather than a finding, so it is
counted apart.

### The 2020 departure is not a level, it is spatially structured, and that is worse

Measured on 2026-09-10, after five candidate external sources were read and none of
them turned out to carry a usable series. Two of them said something about the
*shape* of the pandemic instead, and that was testable against the diagnostic
already built.

The INTALInC LAC observatory's Bogota report finds that **58 % of low-income
residents could not work from home against 10 % of high-income ones**. And Guerrero
Ayala et al. (Uniandes, COPA), tracking GPS movement in **San Cristobal and Ciudad
Bolivar**, conclude that at the population level there was **no significant change
in movement dynamics** between 2019 and 2021 — a negative result in two peripheral,
low-income localities. Together they predict that the collapse in travel was
concentrated where people could afford to stay home.

**The diagnostic says exactly that.** The 2020 ratio, unit by unit, on the corrected
casualties:

| Mode | Most overstated by the panel | Least overstated | Spread |
|---|---|---|---|
| `CAR` | Chapinero 0.45, Teusaquillo 0.50, Usaquen 0.52, Barrios Unidos 0.57 | Lucero 1.18, Torca 1.08, Tibabuyes 0.97, Rincon de Suba 0.97 | 0.45–1.18 |
| `PEDESTRIAN` | Barrios Unidos 0.40, Tabora 0.42, Engativa 0.43, Teusaquillo 0.46 | Rafael Uribe 0.83, Patio Bonito 0.81, Britalia 0.77, Tibabuyes 0.71 | 0.40–0.83 |

And the mechanism is measurable rather than merely legible in the names. Against
each unit's car trips per inhabitant in 2019 — a proxy for motorisation and for
income — the 2020 ratio correlates at **Spearman −0.49 for the car and −0.53 for the
pedestrian**, and at **−0.09 for the bicycle**, which is the mode whose city ratio
was 0.99 to begin with.

**Whichever of the two smoothness assumptions is taken, 2020 departs from it in a
spatially structured way, and the structure runs along a proxy for income.** Under
the exposure-is-smooth assumption the departure sits in the exposure; under the
risk-is-smooth assumption it sits in the risk. The study cannot say which without an
external series, and it does not need to in order to see the danger: **a denominator
whose error is correlated with the socioeconomic geography of the city, inside a
model whose whole purpose is to relate risk to urban form, would present itself as a
finding about urban form.**

That is a different and larger problem than three years sitting at the wrong level,
and it makes the least defensible option the one that requires no decision: leaving
those years in the models untouched and unmarked.

### What was open here, and it is a decision rather than a measurement

**Decided on 2026-09-10, and it is D42**: the three years are patched, by a factor
per mode computed at the city level, in a variant of the panel rather than in place
of it. What follows is the case as it stood when the question was still open, and it
is left as written because it is the argument D42 rests on.

**Whether the pandemic years are patched by the mirror assumption.** The diagnostic
was built to say where the panel is least believable and it isolates two blocks. For
2020–2022 there is a case for using the mirror — assume the risk is smooth there and
take the exposure the casualties imply — that does not exist for the panel as a
whole:

- the disagreement is concentrated and dated, so the patch would be a **declared
  exception on named years** rather than a method;
- the reason the interpolation fails there is known and external to the data, which
  is not the case anywhere else;
- and the direction of the failure is checkable: the implied pedestrian risk falling
  40 % in 2020 is not merely different from smooth, it is implausible.

What it would still cost is the first objection above, undiluted: those three years'
exposure would carry an assumption about the risk, and a model estimating risk would
be reading them. **If it is done, the years have to be marked in the panel** — a
fourth value beside `MEASURED`, `INTERPOLATED` and `HELD` — so that a model can drop
them, and the report has to say that the pandemic exposure of this study rests on
its own casualty counts.

**The better patch is external and it is the same one D40 defers.** One measured
annual series per mode gives a second equation instead of a second assumption, and
2020 is precisely the year for which such series are most likely to exist and to be
published. Looking for one is cheaper than it was when D40 deferred it, because now
only three years have to be covered well.

**And there is a candidate, recorded here so the lead is not lost.** Gómez Triana,
I. (2021), directed by Á. Rodríguez Valencia, Universidad de los Andes,
`hdl.handle.net/1992/53693`, compares three modes across 2019–2021 using the
**aforos and fare validations of the Secretaría Distrital de Movilidad**. The
period covers 2020 and 2021 exactly, and counts and validations are genuinely
exogenous to the crash record, which is the property that turns a second assumption
into a second equation. Four things have to be established before it can be used,
and none of them can be read off an abstract:

- **which three modes**, because the pairing with aforos and validations suggests
  bicycle, public transport and private vehicle — and public transport is not one
  of this study's four (D38), while the pedestrian is both absent from that likely
  trio and the mode with the worst diagnostic;
- **whether the counting programme itself ran through the lockdowns.** Stations
  suspended in April and May 2020 would bias an annual mean upward, and it is the
  same class of defect as the recording change in the crash data: a measurement
  whose completeness moved with the thing being measured;
- **what a count is measuring**, because an aforo is a flow across a screenline and
  this study's exposure is trips per day apportioned to a unit. What transfers is
  the **city-level temporal shape**, not the level and not the spatial
  distribution — which is exactly the anchored design D40 sketches: rescale the
  annual city total per mode, keep each unit's share from the interpolation;
- **and whether the numbers exist as data or only as charts.** The work is a
  pointer to the SDM's own series as much as a source; what is worth asking its
  author or its director for is which datasets were used and whether they are
  obtainable, rather than the document itself. A figure read by eye needs its
  precision declared, as `PublishedYear.share_rounding` does for 2005.

**If it does say what the diagnostic says, that is worth more than either alone.**
The table above puts the bicycle at 0.99 in 2020 and the pedestrian at 0.60. An
independent count agreeing that cycling held and walking collapsed would let those
years be patched with a corroboration instead of a preference, and that is a
different kind of argument from anything available today.

**Four other candidates were read on 2026-09-10 and none carries a usable series**,
which is recorded here so that they are not read a second time:

| Source | What it is | Why it does not serve |
|---|---|---|
| Posada Parada et al. (2021), *Revista Pensamiento Udecino* | perception survey of Bogota residents | perceptions rather than travel, and no time series at all |
| Guerrero Ayala et al. (Uniandes, COPA) | GPS traces from the Muevelo app, 2019 and 2021 | 213 participants in two localities; a sample that size cannot carry a city series — but its negative finding is used above |
| Gacharna Pinto and Aponte Sanchez (U. Libre Cucuta) | national bibliographic review | a review rather than a source; **it points at Google's Community Mobility Reports**, which is the one lead in it |
| INTALInC LAC, Bogota report 3 | web survey, 776 responses, March to May 2020, self-declared as not representative | a two-point comparison and not a series — but its income split is used above |
| Sanin Riano (Uniandes, 2022) | university students, EM2019 plus 400 own surveys, 2019 against 2022 | one subpopulation and two points |

**Google's Community Mobility Reports are the second lead, and their shape is right
where the theses' is wrong**: daily, published for Bogota, running from early 2020
to late 2022, and exogenous to everything this study measures. Three things have to
be established before they could be used, and none of them off an abstract either:
that they are indexed to a pre-pandemic baseline rather than given as levels; that
they are categorised by **destination** — workplaces, transit stations, residential
— and not by mode, so what they can anchor is an activity index and not a mode's
exposure; and that the population behind them is whoever carries a phone with
location history enabled, whose composition is unknown and may itself have moved
during the period being measured.

---

## D42 — The pandemic years are patched by the mirror assumption, at the city level, in a variant of their own

**Kind:** Methodological. It decides what the exposure of 2020, 2021 and 2022 is,
which is the one block of the panel where D40's construction is known to be wrong
rather than merely uncertain.

**Status:** Decided on 2026-09-10. It answers the question D41 left open, and it is
the only place in this study where the casualty series constructs an exposure
instead of checking one.

**Built:** Yes, on 2026-09-10, in the run that follows the one this decision was
written against. `src/interpolation.py`, route `interpolation`, run
`run_20260910_192902`: 12,960 rows over two variants, **23 checks, none failed**,
and the six the section at the end asks for are among them. The decision was
written before any of it existed, which is what let the argument be settled apart
from the implementation of the argument.

### What the panel asserts about the pandemic today, and why it cannot stand

Inside the thirty units, on the weekday, indexed to 2019 = 100:

| Mode | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---:|---:|---:|---:|---:|
| `PEDESTRIAN` | 100 | 104 | 107 | 111 | 116 |
| `BICYCLE` | 100 | 100 | 99 | 99 | 98 |
| `MOTORCYCLE` | 100 | 106 | 110 | 115 | 120 |
| `CAR` | 100 | 98 | 95 | 91 | 88 |

**The panel says walking grew four per cent in 2020 and kept growing.** That is not
a defensible sentence in front of a committee, and it is not a defect of the
interpolation: D40 does exactly what it says it does, which is to draw a smooth line
between two measured years. The line is right about the years around the pandemic
and wrong about the pandemic, because the information that 2020 happened is not in
the two anchors and no care inside D40's own terms can put it there.

D41 states the system: a casualty count is roughly exposure times risk, the
casualties are known for all eighteen years of the window and the exposure for four
of them, so every constructed year has one equation and two unknowns. D40 spends its degree of freedom
on the exposure. **For these three years it is spent on the risk instead.**

### The decision, in four parts

**One. The years are 2020, 2021 and 2022, and all four modes in each.** Not a
mode-by-mode selection: choosing which cells get the treatment after seeing which
ones look better under it is fitting, and this decision does not do that.

**Two. The factor is computed at the city level, one per mode and year, and applied
to all thirty units.** The city's risk at 2019 and at 2023 is measured; the risk
between them is interpolated log-linearly by D40's own rule; the exposure that risk
implies is the year's casualties divided by it; the factor is that implied exposure
over the exposure the panel carries. Each unit keeps the share of the city it already
had, so **the geography of the panel stays where it comes from, which is the
survey**.

**Three. The factor is derived from the ρ-corrected casualty series**, with the
observed variant computed and printed beside it on every run as a sensitivity rather
than kept as a second product.

**Four. The patched years are a variant of the panel and not a replacement of it**,
carried as rows under an `EXPOSURE_VARIANT` column, with a fourth provenance value,
`IMPLIED_FROM_RISK`, beside `MEASURED`, `INTERPOLATED` and `HELD` — and the patch
applies to the **weekday only**.

### The factors, measured on `run_20260910_154603`

Corrected on the left, observed on the right:

| Mode | 2020 | 2021 | 2022 | | 2020 obs. | 2021 obs. | 2022 obs. |
|---|---:|---:|---:|---|---:|---:|---:|
| `PEDESTRIAN` | **0.584** | **0.746** | 0.963 | | 0.584 | 0.746 | 0.963 |
| `BICYCLE` | 1.001 | **1.126** | 1.054 | | 1.001 | 1.126 | 1.054 |
| `MOTORCYCLE` | **0.721** | 0.925 | 1.001 | | 0.734 | 0.948 | 1.012 |
| `CAR` | **0.706** | 0.993 | 1.040 | | 0.695 | 1.101 | 1.084 |

And what they do to the series, on the same index as above:

| Mode | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---:|---:|---:|---:|---:|
| `PEDESTRIAN` | 100 | **60** | **80** | 107 | 116 |
| `BICYCLE` | 100 | 100 | **112** | 104 | 98 |
| `MOTORCYCLE` | 100 | **76** | 102 | 115 | 120 |
| `CAR` | 100 | **69** | 94 | 95 | 88 |

**The four modes tell one story and it is the story that happened**: everything
collapses in 2020 except cycling, which holds and then peaks in 2021, the year Bogotá
opened its temporary bike lanes. Nothing in the method knows that. The four series
are produced independently of one another, from four casualty counts and four
interpolated risks, and **that they agree is the evidence for the patch** — which is
the argument to make, rather than the plausibility of any one of them.

### Why all three years and not 2020 alone

2020 is the year with the unambiguous case, and the first version of this decision
was going to stop there. The measurement above is what changed it: 2021's pedestrian
at 0.75 and 2022's at 0.96 describe a recovery that is neither instant nor complete,
which is what a recovery looks like, and cutting the patch after 2020 would assert
that travel returned to the interpolated line on 1 January 2021.

The two factors above one — cycling at 1.13 in 2021 and the car at 1.04 in 2022 — are
the ones to look at hardest, since they claim *more* travel than a straight line drawn
through a period of restrictions. For cycling that is what Bogotá's own reporting says
happened. For the car in 2022 it is four per cent, which is inside anything this
method can resolve.

### Why the city and not the unit

The mirror assumption can be inverted cell by cell — D41's diagnostic already does,
which is what makes the temptation concrete. It should not be, and the reason is
measured. Per-unit factors for the same mode and year spread like this:

| Mode, 2020 | 5th pct | median | 95th pct | range | median casualties per unit |
|---|---:|---:|---:|---|---:|
| `PEDESTRIAN` | 0.42 | 0.58 | 0.79 | 0.40–0.83 | 51 |
| `BICYCLE` | 0.73 | 0.99 | 1.43 | 0.68–1.74 | 60 |
| `MOTORCYCLE` | 0.59 | 0.71 | 0.93 | 0.52–0.96 | 146 |
| `CAR` | 0.51 | 0.72 | 1.03 | 0.45–1.18 | 58.5 |

**At fifty casualties a cell, Poisson noise alone is worth about fourteen per cent**,
so the bicycle's 0.68 to 1.74 is very nearly all of it noise — a factor of two and a
half between two units, manufactured out of counting error and then written into the
exposure of thirty places for three years. The pedestrian's spread is wider than noise
and may carry something real, since the business districts plausibly emptied more than
the residential ones. **Separating that from noise needs shrinkage toward the city
factor, and that is the same open question D40 already has** about the per-unit
trajectories. It is not answered here. What this decision does instead is publish the
dispersion as a figure, so that it can be answered on evidence.

The two orders of aggregation were compared. Taking the city total and implying once
differs from implying per unit and adding up by 0.1 to 1.7 points on three modes, and
by 3.6 to 4.4 on the car.

### Why the ρ-corrected series, and how much that choice matters

D41 objects that inverting the observed set injects the recording change straight into
the exposure, and that inverting the corrected set makes the exposure depend on which
casualty dataset was chosen — destroying the comparison D31 exists to make. **Both
objections survive this decision and neither is fatal to it, because the choice was
measured.**

**ρ does not touch the pedestrian at all.** In every one of the seventeen years the
two sets share, the corrected pedestrian count equals the observed one to the record, so **the factor that
matters most — 0.584 in 2020, the one that motivated this whole decision — does not
depend on the ρ question in any way.** The bicycle moves by at most 1.3 %. Where the
two sets diverge is the car, by up to 129 %, and the motorcycle by up to 24 %, which
is exactly the population ρ exists to repair: a car occupant recorded as unhurt
where a pedestrian never is.

So the choice is consequential only for the car and the motorcycle, and there the
corrected set is the one whose numerator is not moving for a reason that has nothing
to do with travel. The 2020 factors agree within 1.5 points on all four modes under
either set; where they disagree is the car in 2021, 0.993 corrected against 1.101
observed.

**What survives as a real cost:** a model fitted on the observed casualties over the
patched exposure has, in those three years, a denominator built from the corrected
ones. It is three years of eighteen, on one variant of the panel, and the variant is a
filter — but it is stated in the report, and it is why the observed factors are
printed on every run rather than discarded.

### Why a variant and not a replacement

The precedent is D31 and D39: the observed and the corrected casualty sets live side
by side, the two pedestrian definitions live side by side, and in both cases what
chooses between them downstream is a filter rather than a re-run. **A study that
cannot show the unpatched panel cannot be argued with**, and my advisor has to be able
to see both.

The cost is that fifteen of the eighteen years are identical between the two variants
and are carried twice — 12,960 rows where there were 6,480. The alternative considered
was a parallel column, `..._PATCHED`, which is compact and duplicates nothing; it was
rejected because in fifteen years out of eighteen it is one number written under two
names, which is a failure this pipeline has already had once. **What the row design
needs in exchange is that `EXPOSURE_VARIANT` is part of the key wherever the table is
joined or summed**, the dictionary saying so and a check enforcing it, because a table
that can be summed across variants will eventually be summed across variants.

### What it costs, and all of it goes in the report

**In the patched years the risk is not measurable.** By construction it is the
log-linear interpolation between 2019 and 2023. No model fitted on this variant can be
read as having measured how risk moved in 2020, 2021 or 2022 — not for the city and
not for a unit. This is the central limitation and it belongs in the body, not in a
footnote.

**The direction of the error is known.** The pandemic literature reports that risk per
trip *rose* on emptied streets — fewer vehicles, higher speeds. If it rose and this
decision assumes it was smooth, the rise is attributed to a fall in travel and **the
patch overstates how far travel fell**. That is a bound with a sign, which is worth
more than an unsigned uncertainty, and it means the patched series is the lower end of
what those years could have been.

**The patch carries no geography of its own, and this is the objection to it that
bites.** Every unit is multiplied by the same number, so how differently the pandemic
hit Chapinero and Kennedy is not measured: only the level moves, never the spatial
pattern. D41 measured that the 2020 departure **is** spatially structured — against
each unit's car trips per inhabitant in 2019, a proxy for motorisation and for income,
the ratio correlates at Spearman −0.49 for the car and −0.53 for the pedestrian — and
warned where that leads: a denominator whose error runs along the socioeconomic
geography of the city, inside a model built to relate risk to urban form, presents
itself as a finding about urban form.

**A uniform factor removes the level of that error and not its structure.** It is an
improvement and not a solution, and saying otherwise would be worse than not patching
at all. What it is not is a step in the wrong direction: the alternative that would
absorb the structure is the per-unit patch, and that one writes the *risk's* spatial
pattern into the exposure, which is the failure D41's first objection describes and on
a quantity the thesis exists to estimate. Between leaving the level wrong and leaving
the structure unabsorbed, this decision takes the second, marks the years, and leaves
the shrinkage question where D40 already has it.

**And the matrix is two-sided.** D41's second objection stands unaltered — a
pedestrian casualty in a collision with a car depends on both exposures, and this
inversion is one-sided. It is adequate for a level correction of three years applied
per mode; it would not be adequate as a method.

**The Saturday and the Sunday of those years are not patched.** The casualty series
carries no kind of day, the factor is derived on the weekday pairing D41 declares, and
the Sunday rests on a single anchor. Their cells keep `INTERPOLATED` and `HELD` and a
factor of exactly one, and the report says that the pandemic correction is a weekday
correction.

### What was rejected

**Patching the whole panel by the mirror assumption.** It is D41's first objection and
it stands: assuming the shape of the risk assumes the shape of what the thesis
estimates. What makes three named years different is that the cause is known, external
to the data, dated, and its direction checkable — a declared exception on named years
and not a method.

**Choosing the years or the modes by how plausible the result looks.** Named above.
The rule is stated first and applied to all twelve cells.

**Nulling the pandemic years instead.** It is the same mistake 2005's pedestrian column
would have been: a null says there is no figure, when what is true is that the figure
rests on a different assumption. Marked and exported beats absent, and a model that
wants to drop those years can, precisely because they are marked.

**A patch derived per unit.** Measured above and rejected on the dispersion.

### What retires it

**One measured annual series per mode**, which turns the second assumption into a
second equation. D41's last section names the two candidates — the SDM's aforos and
fare validations through Gómez Triana (2021), and Google's Community Mobility
Reports — and says what has to be established about each before it can be used. That
approach is being made through Universidad de los Andes.

**This decision is built to be retired.** The patch is a factor per mode and year
applied to a variant of the panel; replacing it with an externally anchored factor
changes twelve numbers and nothing else, and the unpatched variant is untouched
throughout. If the external series arrives and agrees — cycling holding, walking
collapsing — then those years rest on a corroboration instead of on a preference,
which is a different kind of argument from anything available today.

### What building it has to prove

The checks the implementation is not finished without:

- **the anchors do not move.** 2019 and 2023, and every other measured year, are
  identical between the two variants to the last decimal.
- **only twelve mode-year combinations differ**, and only on the weekday.
- **D39's two invariants survive**: the fifteen-minute column stays inside the full
  one, and the two remain equal on the three modes with a single definition. Applying
  one factor per mode and year to both columns is what guarantees this, and the check
  is what proves the guarantee was not lost on the way.
- **the patched city total equals the casualties over the smoothed risk**, per mode
  and year, to a part in 1e-9 — the identity the whole decision rests on, verified
  rather than assumed.
- **the factor table is printed on every run**, both datasets, and the run does not
  fail on it.
- **`EXPOSURE_VARIANT` is part of the key**, and no exported table can be summed
  across variants without the check noticing.
