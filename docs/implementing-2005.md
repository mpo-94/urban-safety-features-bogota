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
precisely what this project does not do.** *(§11 closes this, and it closes in favour
of what is declared: the ordering of the slices is confirmed by eight of the ten
categories, and an assumption validated on eight is the one to trust for the two it
cannot be validated on.)* It mattered because: swapping
those two labels would move the pedestrian's published 2005→2011 growth from 2.72×
to 2.38× and the car's from 1.19× to 1.36×, which changes *which rows carry* D40's
argument even though it does not change its direction.

---

## 7. Where the six things §6b requires stand

| What | Field | Status after this pass |
|---|---|---|
| Which file holds the trips, and how it is encoded | `trips` | **Settled.** `MODULOD` of `Encuesta.mdb`, through the existing `AccessTable` |
| Which column is the expansion factor | `weight_column` | **Settled by an exact reproduction.** `FACTRED_FI`; see §11 |
| What one unit of it expands to | `weight_expands_to` | **Settled.** One typical weekday, which is 2019's answer; see §11 |
| A published total to check against | `published_total` | **Settled.** 9,689,027, stated to the trip in Tomo II of the 2011 delivery — but over a universe no other year's control total uses; see §11 |
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

*Three things were open when this was written and all three are now closed by §11:
which expansion factor, what it expands to, and what published total settles them.
What replaced them is one small change to `MobilitySurvey`, described there.*

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


---

## 10. The zoning: JICA was the wrong thing to look for

**There is no JICA geometry anywhere under `data/`.** The only zonings on disk are
the three ZAT of 2015, 2019 and 2023, the UPZ layer and the localities. Nothing in
either the 2005 or the 2011 delivery carries a shapefile of it.

**But Tomo II of the 2011 delivery says JICA is not what 2005 was zoned on.** Its
paragraph 4.21 is explicit: the 2005 origin-destination survey covers *"618 zonas
dentro del casco urbano de la ciudad de Bogotá o los 17 municipios aledaños… De esta
manera se suman 635 zonas en total que se definen como las zonas de transporte de la
encuesta de viajes O-D del 2005"*. That is the **EMME** zoning, the one
`D29_EMME`/`D32_EMME` carry, with 621 distinct codes in our records against the 635
the text describes. JICA is something else and older — the 134 zones of the 1996–97
master plan, kept in the file as a second coding.

So the zoning to want is the EMME one, and its source is named: *"Archivos SIG del
Plan Maestro de Movilidad de Bogotá para el año 2005, Secretaría de Tránsito y
Transporte"*. **It is not on disk either**, and unlike JICA it is worth asking for by
name.

### And Tomo II gives the seventeen municipalities their codes

Its Tabla 4.1 lists them: **609 Cota, 610 Chía, 611 Funza, 612 Mosquera, 613 Sopó,
614 Cajicá, 615 Tocancipá, 616 Tabio, 617 Zipaquirá, 618 Gachancipá, 619 Tenjo, 620
Madrid, 621 Bojacá, 622 Facatativá, 624 Soacha, 626 Sibaté, 635 La Calera.**

**The records confirm that structure exactly, with no exceptions on either end:**

| | Origin | Destination |
|---|---:|---:|
| Records whose EMME code is one of the seventeen | 6,980 | 6,850 |
| Records with no UPZ | 9,383 | 9,487 |
| **Both** | **6,980** | **6,850** |
| A municipality code *and* a UPZ | **0** | **0** |
| No zone in any zoning at all | 2,403 | 2,637 |

So every record that UPZ cannot place is either a named municipality or has no
geography whatsoever — the second being the same category as 2011's imputed sixth.

### Which makes most of the boundary loss recoverable without the 2005 GIS files

§9 measured what UPZ costs and found it is not the coarseness but the boundary: a
trip with one end outside Bogotá cannot be drawn at all. **Of the 12,860 records with
an end outside Bogotá, 9,157 — 71.2 % — have both ends as either a UPZ or a named
municipality**, and they are worth **750,536 trips a day**. What stays unplaceable is
3,703 records and 324,477 trips.

**What that needs is municipal boundaries and nothing else**: seventeen polygons of
standard national cartography, to be used exactly as an outer ZAT is used in every
other year — one zone, one centroid, a line drawn from it. It is not under `data/`
yet and it is a far smaller thing to obtain than a 2005 GIS archive.

---

## 11. The factor, settled by reproducing a published total to the trip

**Tomo II of the 2011 delivery states 2005's total, and it states it to the unit.**
Paragraph 4.26: *"el número total de viajes reportado en la encuesta de movilidad
para el área de estudio en el año 2005 fue de 9.689.027"*. The 2011 Tomo III's
"aproximadamente 9.700.000", which `config.PUBLISHED_2005` was declared on, is that
figure rounded.

Eight readings of the file were tested against it:

| Reading | Sum | Against the published figure |
|---|---:|---:|
| Every record, `FACTFINAL` | 10,192,098 | +5.19 % |
| Every record, `FACTRED_FI` | 10,425,456 | +7.60 % |
| Without transfer legs, `FACTFINAL` | 9,577,058 | −1.16 % |
| Without transfer legs, `FACTRED_FI` | 9,800,396 | +1.15 % |
| Without walks under fifteen minutes, `FACTFINAL` | 10,120,832 | +4.46 % |
| Without transfers and short walks, `FACTFINAL` | 9,507,719 | −1.87 % |
| Bogotá households only, `FACTFINAL` | 9,455,723 | −2.41 % |
| **Bogotá households only, `FACTRED_FI`** | **9,689,027.11** | **+0.0000001 %** |

**One reading matches, and it matches to a tenth of a trip in nine and a half
million** — one part in 10⁸. That is the same order of agreement as the 2015 matrices,
and it settles three fields at once.

- **`weight_column` is `FACTRED_FI`**, the count-adjusted factor, not the survey's
  own `FACTFINAL`. The dictionary distinguishes them — *"Factor de expansión de
  viajes"* against *"Factor de expansión de viajes ajustado por conteos"* — and the
  published figure is computed on the adjusted one.
- **`weight_expands_to` is one typical weekday**, which is 2019's answer rather than
  2023's. Two things say so. The household factor over Bogotá sums to 1,946,608
  households implying **7,175,566 residents against the 7,312,766 the validation
  report states, 98.1 %**; and 9,689,027 trips over the 6,512,461 expanded persons
  aged five and over is **1.488 trips per person**, inside the range of the mobility
  index the 2011 comparison chapter publishes by stratum for 2005, 0.95 to 2.01.
- **`published_total` is 9,689,027**, with Tomo II ¶4.26 as its source.

### And one thing has to be reported rather than absorbed

**The control total covers a universe no other year's does: Bogotá households, not
the whole surveyed region.** 15,652 of the file's 18,091 households. Every other year
publishes a total over everything its factor weights, and `surveys.read` checks the
sum of the whole file against `published_total` accordingly. **2005 cannot pass that
check as written**, and it is not because the reading is wrong.

That is §6b's case exactly — a year that cannot be made to fit without a change —
and the change is small and of the shape the contract asks for: a declared statement
of *which subset* the published total covers, beside the total itself, so the run
checks the sum the publication actually made. It is the second time a year has needed
something (2011 needed `TripSource`), and like that one it leaves the other four
untouched, since a year that declares no subset checks the whole file as before.

### Where the two factors differ, and it is one of our four modes

The adjustment was applied to the motorised modes and to those only, exactly as the
validation study describes:

| Mode | `FACTFINAL` → `FACTRED_FI` |
|---|---:|
| Bicicleta | −0.0 % |
| Bus escolar, Bus privado | −0.0 % |
| Moto | **−0.1 %** |
| A pie | **+0.1 %** |
| Buseta, Bus alimentador | +1.7 % |
| TransMilenio | +2.2 % |
| Bus | +2.6 % |
| Taxi | +3.1 % |
| Vehículo privado como pasajero | **+5.4 %** |
| Vehículo privado como conductor | **+8.3 %** |

**So the choice of factor is immaterial for three of this study's four modes and
material for one.** Walking, cycling and the motorcycle move by a tenth of a per
cent; the car moves by 8 %. Which is worth knowing before any 2005 car figure is
compared against another year's.

### The modal split, and why the declaration stands

§6 recorded a live discrepancy: `config.PUBLISHED_2005` carries `PEDESTRIAN 0.14`
and `CAR 0.16`, read off the pie chart of Figura 5.16 by assigning its ten labels to
its ten legend entries in slice order, and the microdata seemed to fit the other way
round. It was left open rather than fitted. It can now be closed, and it closes in
favour of what is declared.

Recomputed over the region on `FACTFINAL` — which is the universe the published pie
turns out to be on, since the Bogotá-only universe puts *Intermunicipal* at 0.7 %
against a published 2 % — and folding *Bus privado / De compañía* into "Privado",
nine of the ten categories land within the chart's own half-point rounding: TPC 46.0
against 46, TransMilenio with its feeder 11.3 against 11, Bicicleta 2.8 against 3,
Moto 0.7 against 1, Taxi 3.4 against 3, Escolar 4.2 against 4, Intermunicipal 1.6
against 2, Otro 0.2 against 0.3, and walking 14.9 against 14.

**The tenth is the private vehicle at 14.9 against 16**, about a point out. And the
two readings cannot be told apart by magnitude, because walking and the private
vehicle both measure 14.9: swapping the labels moves the error from one to the other
and leaves it the same size.

**What decides it is the ordering, not the magnitudes.** The legend is alphabetical
and the slices run clockwise in that order, and **eight of the ten categories confirm
that ordering unambiguously**. An assumption validated on eight cases is the one to
trust for the two it cannot be validated on. So `PEDESTRIAN 0.14` and `CAR 0.16`
stand, and what is recorded instead is that our reading puts the private vehicle
about a point below what the chart shows.
