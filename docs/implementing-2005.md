# The 2005 survey: the inspection pass

**Nothing is implemented and nothing is declared.** This is the record of stage 0 of
[`adding-a-survey-year.md`](adding-a-survey-year.md) — inspect before declaring
anything — made on 2026-09-10, and of the go/no-go it was run to answer.

D40 deferred the 2005 survey on a measurement and
[§16 of the verification report](verification-report.md) made it: the held 2007–2010
block sits 15 to 19 points away from what 2005 published on the two modes that turn
over. That is the reason to open this delivery. What follows is what is in it.

---

## 1. The delivery, and the conversions

Four files, which is everything the Alcaldía publishes about this survey:

| File | What it is |
|---|---|
| `Encuesta.mdb` | the microdata, 57 MB, Access |
| `Descripcion Encuesta.DOC` | the data dictionary |
| `BM_58 STT VM Informe FinalVersion3.doc` | **not** the survey's results report — see §6 |
| `Presentacion Encuesta STT.ppt` | the results presentation, 28 February 2006, 54 slides |

The three Office files are legacy binary formats. They were converted by hand into
`convertidos/` beside them — `Descripcion Encuesta.docx`,
`Presentacion Encuesta STT.pptx` and `BM_58 STT VM Informe FinalVersion3.pdf` — and
**the originals are left untouched**, because that folder is the record of what was
delivered and the conversions are ours. `docs/data-layout.md` records the folder.

The DOCX was asked for rather than a PDF because the dictionary is a table of codes,
and in DOCX a cell is an element while in a PDF it is whitespace a parser has to
guess at; a mis-assigned mode label would corrupt the year without failing anything.
The PPTX was asked for because a native PowerPoint chart carries its own numbers.
**It has none** — 58 media files and zero native charts — so that hope did not pay
off, but the vector images turned out to carry their text labels, which is how §5
below was read.

---

## 2. The go/no-go: the trips can be put on a map this study already has

`MODULOD` is the trip module: **90,637 records, 29 columns.** The other three tables
are household (20,686), vehicles (21,517) and persons (71,509).

**The trips carry a zone code in three different zonings, at both ends:**

| Zoning | Zones | Records with a code |
|---|---:|---:|
| EMME — the STT's own model zoning | 621 | 88,234 |
| **UPZ** | 110 | 81,254 |
| JICA — the 1996–97 master plan zoning | 125 | 88,232 |

**The UPZ geometry is already in the repository**, at `data/geo/bog_upz`, 111
polygons — it was there for the predictor layers. Nothing has to be obtained.

- **109 of the 110** origin codes and **110 of the 111** destination codes are in
  that layer. The one that is not is code `89`.
- **77,777 of the 90,637 records (85.8 %) carry a usable UPZ at both ends.** The
  dictionary explains the rest: `ID_UPZ` says *"Para las encuestas de los municipios
  este campo se encuentra vacío"*, so what is missing is the municipalities — the
  same category as "outside the thirty units" in every other year.

**The EMME route is closed and it is the one that would have been better.** 621
zones would have been comparable to the ZAT of the other four years. There is no
shapefile in either the 2005 or the 2011 delivery, and the only EMME artefact is
`emmebank.zip`, a proprietary binary of the model itself.

### What UPZ costs, measured

| | Median zone area | Zones per unit |
|---|---:|---:|
| ZAT, 2015 / 2019 / 2023 | 0.41 km² | ~30 |
| **UPZ, 2005** | **3.48 km²** | **6** |

Eight times coarser, and five times less resolution inside a unit. **61 of the 111
UPZ straddle a unit boundary**, so the UPL are not clean aggregations of UPZ and the
area split does real work.

**And the coarseness does not bite where it was expected to.** A coarser zoning
should raise the intra-zonal share, because a bigger zone is easier to stay inside,
and an intra-zonal trip is spread by area rather than along a line — a different
spatial operator. It falls instead:

| | Intra-zonal |
|---|---:|
| **2005 on UPZ** | **12.5 %** |
| 2011 on ZAT | 32.7 % |
| 2015 / 2019 / 2023 on ZAT | 20.1 / 21.5 / 20.0 % |

Almost certainly because 2005 collected no walk under fifteen minutes, and short
walks are what stays inside one zone. Its trip mix is long by construction.

**The test that settles whether this is good enough was run on 2026-09-10 and it is
§9.** The short of it: the coarseness costs almost nothing, and the boundary costs
something real.

---

## 3. The dictionary settles the modes, and there are sixteen

`D35_MEDIO`, in the order the dictionary lists them, against the record counts:

| Code | Label | Records | | Code | Label | Records |
|---:|---|---:|---|---:|---|---:|
| 1 | A pie | 14,665 | | 9 | Bus | 15,787 |
| 2 | Bicicleta | 2,880 | | 10 | Buseta | 19,204 |
| 3 | Moto | 656 | | 11 | Microbús | 6,787 |
| 4 | Vehículo privado como conductor | 7,328 | | 12 | Transporte intermunicipal | 2,324 |
| 5 | Vehículo privado como pasajero | 2,390 | | 13 | Bus privado / De compañía | 1,755 |
| 6 | Taxi | 2,480 | | 14 | Bus escolar | 3,915 |
| 7 | TransMilenio | 7,751 | | 15 | Camión | 87 |
| 8 | Bus alimentador | 2,503 | | 16 | Otro | 125 |

**The mapping to this study's four actor types would be** `PEDESTRIAN` ← 1,
`BICYCLE` ← 2, `MOTORCYCLE` ← 3, `CAR` ← 4 **and** 5. Taxi stays out, as it does in
every other year.

Two things are cleaner here than in the years already implemented. **2005 splits the
private vehicle into driver and passenger**, which no other year does and which the
mapping simply adds back together. And **there is no `ILEGAL` or `Informal`
aggregate**: 2011 and 2015 bury the bicitaxi and the mototaxi inside one, and 2005
does not have one at all — only `Otro` at 125 records.

### And it settles the fields

`TIEMPO_VIA` is *"Tiempo de duración del viaje en minutos"*, whole minutes, **no
nulls**. So 2005's duration rule is `DurationFromMinutesColumn`, the simplest of the
three that already exist. **No new rule is needed and no new reader**: the container
is Access, which `AccessTable` has handled since 2011.

`D36_MINCAM` is *"Minutos que camina la persona encuestada antes de tomar su
transporte"* — access walking, not the trip's duration, and not to be confused with
it. `DISTANCIA` is the distance travelled, which **no other year carries**.

---

## 4. The transfer problem is identifiable, and it barely touches this study

This was the largest methodological unknown. The 2011 delivery's comparison chapter
says 2005 counted a transfer as a trip of its own, which inflates its total and is
recorded as a caveat on `config.PUBLISHED_2005`.

**`D34_MOTI` has a value for it.** The motives are Regreso a residencia, Trabajo,
Estudio, Negocios, Compras, Asuntos personales, **Trasbordo**, Otro — so a transfer
leg is not merely present, it is labelled.

**6,093 records, 6.7 % of the file, 615,041 weighted trips.** And they are
overwhelmingly on modes this study does not measure:

| Mode | Share of that mode's trips that are transfer legs |
|---|---:|
| Bus alimentador | 46.8 % |
| Transporte intermunicipal | 25.3 % |
| TransMilenio | 20.5 % |
| Microbús | 6.7 % |
| A pie | 3.9 % |
| Bus / Buseta | 3.3 / 3.2 % |
| Vehículo privado pasajero | 2.0 % |
| Moto | 0.5 % |
| Vehículo privado conductor / Bicicleta | 0.3 % |

**Of the four modes this study measures, transfer legs are 671 records and 69,467
trips — 2.14 % of what those four modes weigh.**

So the caveat is true of the published *total* and nearly irrelevant to the *modes
this study compares*. It is also now a decision that can be taken explicitly —
dropped, or chained into journeys using the consecutive `D27_NVIA` of one person —
rather than an unquantified warning. The presentation's own slide 34 agrees the
category is real: it publishes Trasbordo at **11 %** of trips excluding returns
home, against 12.0 % on the record counts.

---

## 5. The walking floor is real, and it has a 4.7 % leak

The claim that makes 2005 includable at all is that it counted only long walks, so
that its pedestrian mode is D39's fifteen-minute column and nothing else.

**The presentation states it in the delivery's own words**, on slide 7: *"Se incluyen
viajes a pié superiores a 15 minutos"*.

**The microdata is nearly but not exactly that:**

| Walking duration | Records | Share | Weighted trips |
|---|---:|---:|---:|
| under 15 min | 663 | 4.5 % | 71,266 |
| under 16 min | 4,431 | 30.2 % | 467,413 |

The jump between those two rows is **3,768 records sitting at exactly 15 minutes**,
a quarter of all walking — the floor, with everything at or near it piling onto the
threshold. Below it there is a residue of 663 records, 4.7 % of the mode's weight,
which the instruction was supposed to exclude and did not.

**What follows for the study.** 2005's walking is comparable to
`TRIPS_PER_DAY_OF_TYPE_OVER_15MIN` and to nothing else, and applying this study's own
filter would make it exactly so by removing the leak. **The full pedestrian column
has no value for 2005 and never can**, so a fifth anchor would anchor one of the two
pedestrian columns and not the other — which is a real consequence for the shape of
the interpolated panel and is written into §8.

---

## 6. The report on disk is not the survey's results report

This is the finding that matters most for what is still missing.
`BM_58 STT VM Informe FinalVersion3` is titled **"Validación de las matrices
resultantes de la Encuesta de Movilidad mediante la modelación de transporte"**. It
is a later study that took the survey's matrices and **adjusted them against traffic
counts and a transport model**, in three passes — generation, modal split and hourly
fluctuation. Its Tabla 20 reports that the motorised total went from **6,487,888
before the adjustments to 7,340,622 after**, a rise of 13 %.

That explains the two weight columns the dictionary declares:

| Column | The dictionary's words |
|---|---|
| `FACTFINAL` | *"Factor de expansión de viajes"* |
| `FACTRED_FI` | *"Factor de expansión de viajes **ajustado por conteos**"* |

and the presentation's slide 11 confirms the process: *"Se tienen 3 factores de
expansión iniciales… En la segunda fase se modeló y se realizó un ajuste por
conteos"*.

### Which leaves `published_total` genuinely unsettled

Four numbers are in play and none of them agrees with another:

| Figure | Source | Territory |
|---|---:|---|
| `FACTFINAL` summed | the file itself | region, 10,192,098 |
| `FACTRED_FI` summed | the file itself | region, 10,425,456 |
| 8,919,392 | this report's Tabla 10, with population 7,312,766 and 1.22 trips per inhabitant | Bogotá |
| ~9,700,000 | the 2011 delivery's Tomo III, chapter 5 | region, a weekday |

**This is exactly the field §6b says must never be inherited or guessed**, and 2005
is the hardest case any year has presented: the survey's own results document is a
slide deck whose modal-split slide is a bar chart with no value labels.

### One consequence already: a live discrepancy with what is declared

`config.PUBLISHED_2005` currently carries `PEDESTRIAN 0.14` and `CAR 0.16`, read off
Figura 5.16 of the 2011 Tomo III by assigning its ten labels to its ten legend
entries in order. Against the microdata on `FACTFINAL`, eight of the ten categories
land within rounding — TPC 46.0 against 46, TransMilenio plus Alimentador 11.3
against 11, Bicicleta 2.8 against 3, Moto 0.7 against 1, Taxi 3.4 against 3, Escolar
4.2 against 4, Intermunicipal 1.6 against 2, Otro 0.15 against 0.3.

**Two do not.** Walking comes out at **14.9 %** against a published 14, and the
private vehicle at **13.5 %** against a published 16.

Several reconstructions close that gap — reading the chart's two labels the other
way round, or folding *Bus privado / De compañía* into "Privado", or using
`FACTRED_FI` instead of `FACTFINAL` — and **choosing among them by which one fits is
precisely what this project does not do.** It is left open, and it matters: swapping
those two labels would move the pedestrian's published 2005→2011 growth from 2.72×
to 2.38× and the car's from 1.19× to 1.36×, which changes *which rows carry* D40's
argument even though it does not change its direction.

---

## 7. Where the six things §6b requires stand

| What | Field | Status after this pass |
|---|---|---|
| Which file holds the trips, and how it is encoded | `trips` | **Settled.** `MODULOD` of `Encuesta.mdb`, through the existing `AccessTable` |
| Which column is the expansion factor | `weight_column` | **Open.** Two candidates, and the choice is the survey's own against the count-adjusted one |
| What one unit of it expands to | `weight_expands_to` | **Open**, and tangled with the one above |
| A published total to check against | `published_total` | **Open, and the hardest.** Four candidate figures on three territories; see §6 |
| How the year says which kind of day | `day_type_rule` | **Settled by the primary source.** `DayTypeIsAlwaysOne`, like 2019 — slide 32 says the reference day is the day before, *"y en caso de ser sábado, domingo o lunes sobre el día jueves"*, so every reference day is a weekday by construction |
| How it states the trip duration | `duration_rule` | **Settled.** `DurationFromMinutesColumn("TIEMPO_VIA")`, whole minutes, no nulls |

Plus the mode map and the modes deliberately not measured, both **settled** by §3.

**2005 needs no new machinery.** No new reader, no new duration rule, no new day-type
rule. The only genuinely new thing it would ask for is a decision about the transfer
legs, and §4 shows that decision is worth 2.14 % of the four modes.

---

## 8. What has not been done, and what is left open

**Not done:** the whole of stage 1 onwards. Nothing is declared, nothing is
implemented, no figure from 2005 has entered any table.

**Three things are open** and two of them are the same thing: which expansion factor,
what it expands to, and what published total settles them. §6 is where that work
starts, and it may end in a decision rather than a measurement — if no published
figure can be reconciled, the honest options are to declare the year with no control
total and say so loudly, as `MobilitySurvey.published_total = None` already allows,
or to leave 2005 as a city-level reference rather than a panel year.

**Two changes to the interpolation are already known to be needed** if 2005 does
become an anchor, both because it would be the first anchor outside the study window:

- the population panel is built over 2007–2024 only, and the anchor loop would ask
  it for 2005;
- the check that each series has as many measured years as surveys measured that day
  type counts rows in the panel, and a 2005 anchor would not have one.

Neither is a redesign. Both are places that quietly assume every anchor is inside the
window, and 2005 would be the first that is not.

**The test that had to come before any of this is §9**, and it has been run.


---

## 9. What the coarse zoning costs, measured on a year that has both

2005 can only reach the units through UPZ, and whether that is good enough is not
answerable from 2005: it has no ZAT version to be compared against. **2015 has
both.** So it was read twice — once on its own ZAT, once with every ZAT collapsed
into the UPZ its centroid falls in — and the two results compared per unit. Same
records in both runs, and the plausibility test applied once on the ZAT geometry and
its verdict carried across unchanged, so that what is measured is the apportionment
and not two effects at once.

**The coarseness itself costs almost nothing.** On a 2015 weekday, per unit:

| Mode | City on ZAT | City on UPZ | Gap | Spearman | Pearson | Per-unit ratio, median |
|---|---:|---:|---:|---:|---:|---:|
| `PEDESTRIAN` | 4,459,658 | 4,394,305 | −1.5 % | 0.994 | 0.997 | 0.99 |
| `BICYCLE` | 633,406 | 616,027 | −2.7 % | 0.988 | 0.992 | 0.98 |
| `MOTORCYCLE` | 714,894 | 656,032 | −8.2 % | 0.981 | 0.992 | 0.93 |
| `CAR` | 1,631,914 | 1,545,259 | −5.3 % | 0.971 | 0.997 | 0.96 |

Spearman 0.97 to 0.99 and Pearson 0.99 or better on all four modes. **Collapsing
945 zones into 110 barely moves either the ordering of the thirty units or their
levels.** The intra-zonal share rises only from 20.1 % to 24.7 %, far less than the
factor-of-eight change in zone size would suggest, because what a bigger zone
captures is short trips and 2015's short trips were already mostly intra-zonal.

**What costs is the boundary, and it is a different thing entirely.** UPZ stops at
Bogotá's edge: 827 of the 945 ZAT fall inside a UPZ and 118 do not, and **18.1 % of
2015's trips have an end that cannot be placed**. A ZAT year keeps such a trip and
gives the units the share of its line that falls inside them; a UPZ year cannot draw
the line at all and loses it whole. That is what the negative city gaps above are,
and it is why they are largest on the two motorised modes, which travel furthest and
cross the city boundary most.

**It falls on the perimeter, and on one unit above all.** The units below 0.90 of
their ZAT figure:

| Mode | Units below 0.90 |
|---|---|
| `PEDESTRIAN` | Torca 0.16, Tibabuyes 0.83 |
| `BICYCLE` | Torca 0.51, Arborizadora 0.79, Toberín 0.84, Bosa 0.87 |
| `MOTORCYCLE` | Torca 0.15, Bosa 0.59, Porvenir 0.70, Arborizadora 0.81, Tibabuyes 0.82, Patio Bonito 0.84, Britalia 0.85, Engativá 0.88, Tunjuelito 0.90, Fontibón 0.90 |
| `CAR` | Torca 0.22, Bosa 0.69, Tibabuyes 0.70, Edén 0.72, Fontibón 0.76, Britalia 0.77, Arborizadora 0.87, Suba 0.89 |

Every one of them is on the city's edge, facing Soacha, Mosquera, Funza, Chía or
Cota. **Torca is the extreme in all four modes** — the largest and most peripheral
unit, the one the delivered desire-lines layer never reached and the one D36 records
as having sextupled its population, mostly expansion land the urban UPZ layer barely
covers.

**And this is not an artefact of the test.** In 2005 the municipality households
genuinely carry no UPZ — the dictionary says the field is empty for them — so the
loss the test simulates is exactly the loss a 2005 read would suffer.

### What follows

**2005 can enter the panel as a fifth anchor**, and two things have to be declared
with it rather than discovered later:

- **Torca is not usable from 2005.** Its figure would be a sixth to a half of what
  the same trips give on a fine zoning. Marking that row rather than publishing it
  is the same decision D38 already took for 2011's Saturday, and
  `SAMPLE_SUPPORT` is the column for it.
- **The perimeter units are understated relative to the ZAT years**, by 10 % to 40 %
  and by a mode-dependent amount. That belongs in the same table as the share of
  each survey's own total that reaches the units, which already ranges from 53 % to
  89 % across years and modes — so 2005 would sit inside a spread the study already
  reports rather than outside it.

**The mitigation, if it is ever wanted, is the JICA zoning.** 2005 carries it on
88,232 records against UPZ's 81,254, and the difference is precisely the municipality
ends, because JICA was a regional master plan and its zones do not stop at the city
line. Its geometry is not on disk and not in either delivery. Looking for it is worth
one search before accepting the boundary loss as fixed.
