"""What the panel shows by itself: people, infrastructure, trips and casualties across the units.

    .venv/Scripts/python.exe tools/patrones_del_panel.py

**Read only.** It reads the tables the pipeline exported and prints the descriptive patterns the
discussion of the final report reads, numbered as the thesis numbers them (P9 to P17). It fits no
model of the study: the one regression it runs, in P17, repeats the phase 4 specification with a
different denominator. Nothing in `src/` imports it, and it writes nothing.

Every comparison across units is a Spearman rank correlation over the thirty units, Torca included,
unless it says otherwise, and the two years compared are 2012 and 2023. 2023 is a survey year, so
its trips are measured rather than reconstructed, and it opens the reference window of the
recording correction. Trips are weekday trips of the fitted exposure with the pandemic patch; the
pedestrian is counted on the fifteen-minute definition (D39). Casualties are affected parties.

Two cautions travel with every figure:

- **The population of a unit is a DANE-SDP projection, not a count.** How its growth splits between
  units inherits the projection's assumptions.
- **The trips of a unit are a construction in the years no survey covers, and change between
  surveys.** A few units move in ways that look like the reconstruction rather than the street
  (Tibabuyes, Usme, Suba, Engativá), so what holds for the city is firmer than what holds per unit.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

REPO = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# The runs every figure is read from, pinned so a document can quote them and a rerun can repeat them.
RUNS = {
    "population": "run_20260911_022324",
    "predictors": "run_20260922_010308",
    "matrix": "run_20261006_203551",
    "exposure": "run_20261009_043126",
    "regressions": "run_20261116_172435",
    "panel": "run_20261116_172543",
    "contrast": "run_20261116_172533",
}
FIRST, LAST = 2012, 2023
MODES = ["PEDESTRIAN", "BICYCLE", "MOTORCYCLE", "CAR"]
LEVEL = 0.10  # the study's reading level (D71)


def table(run: str, name: str) -> pd.DataFrame:
    return pd.read_parquet(REPO / "results" / RUNS[run] / "data" / f"{name}.parquet")


def weekday_trips() -> pd.DataFrame:
    """Trips per weekday by unit, year and mode, the pedestrian on its fifteen-minute definition."""
    e = table("exposure", "analysis__fitted_exposure_by_unit")
    e = e[(e.DAY_TYPE == "WEEKDAY") & (e.EXPOSURE_VARIANT == "FITTED_PANDEMIC_PATCHED")]
    trips = np.where(e.ACTOR_TYPE == "PEDESTRIAN", e.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN, e.TRIPS_PER_DAY_OF_TYPE)
    return e.assign(TRIPS=trips).pivot_table(index=["AREA_CODE", "YEAR"], columns="ACTOR_TYPE", values="TRIPS")


def unit_table() -> pd.DataFrame:
    """One row per unit: people, area, infrastructure, trips and casualties in the two years compared."""
    pop = table("population", "analysis__population_by_unit_year")
    pop = pop[pop.SCALE == "UPL"]
    names = pop.drop_duplicates("AREA_CODE").set_index("AREA_CODE").AREA_NAME
    people = pop.pivot_table(index="AREA_CODE", columns="YEAR", values="POPULATION")
    s = table("predictors", "analysis__static_predictors_long")
    area = s.drop_duplicates("AREA_CODE").set_index("AREA_CODE").AREA_UNIT_KM2
    static = s[s.YEAR.isna()].pivot_table(index="AREA_CODE", columns="PREDICTOR", values="VALUE")
    series = s[s.YEAR.notna()].pivot_table(index=["AREA_CODE", "YEAR"], columns="PREDICTOR", values="MEASURE")
    cycleway_km = series["CYCLEWAY_LENGTH_DENSITY"].unstack()
    signs = series["VERTICAL_SIGNAGE_DENSITY"].unstack()
    trips = weekday_trips()
    m = table("matrix", "analysis__matrix_long__rho_corrected")
    m = m[m.SCALE == "UPL"]
    parties = m.pivot_table(index=["AREA_CODE", "YEAR"], columns="PARTY_TYPE", values="AFFECTED_PARTIES", aggfunc="sum")
    parties["ALL"] = parties.sum(axis=1)

    u = pd.DataFrame({"name": names, "area": area, "pop_first": people[FIRST], "pop_last": people[LAST]})
    u["pop_growth"] = u.pop_last / u.pop_first - 1
    for year, tag in ((FIRST, "first"), (LAST, "last")):
        for mode in MODES:
            u[f"trips_{mode}_{tag}"] = trips[mode].xs(year, level="YEAR")
        u[f"trips_{tag}"] = sum(u[f"trips_{mode}_{tag}"] for mode in MODES)
        for kind in ["ALL", "MOTORCYCLE", "BICYCLE", "PEDESTRIAN"]:
            u[f"parties_{kind}_{tag}"] = parties[kind].xs(year, level="YEAR")
    u["cycleway_first"], u["cycleway_last"] = cycleway_km[FIRST], cycleway_km[LAST]
    u["signs_2015"], u["signs_last"] = signs[2015], signs[LAST]
    for name in ["ARTERIAL_ROAD_AREA_SHARE", "TRANSMILENIO_STATION_DENSITY", "SIDEWALK_AREA_SHARE",
                 "SIGNALISED_INTERSECTION_DENSITY", "SPEED_CAMERA_DENSITY"]:
        u[name] = static[name]
    u["attraction"] = u.trips_last / u.pop_last
    return u


def spearman(u: pd.DataFrame, a: str, b: str) -> float:
    return round(u[a].corr(u[b], method="spearman"), 2)


def people_and_places(u: pd.DataFrame) -> None:
    print("P9. Casualties follow where people go, not where they live (2023)")
    u["parties_per_resident"] = u.parties_ALL_last / u.pop_last
    u["parties_per_trip"] = u.parties_ALL_last / u.trips_last
    print(f"  attraction (trips touching the unit per resident): {u.attraction.min():.2f} to {u.attraction.max():.2f}; highest "
          + ", ".join(u.sort_values("attraction").tail(5).name))
    print(f"  attraction against parties per resident {spearman(u, 'attraction', 'parties_per_resident')}, "
          f"per trip {spearman(u, 'attraction', 'parties_per_trip')}; against arterial share "
          f"{spearman(u, 'attraction', 'ARTERIAL_ROAD_AREA_SHARE')}, TransMilenio {spearman(u, 'attraction', 'TRANSMILENIO_STATION_DENSITY')}, "
          f"population growth {spearman(u, 'attraction', 'pop_growth')}")

    print("\nP10. The city grows where the infrastructure is not")
    growth = u.pop_last.sum() - u.pop_first.sum()
    fastest = u.sort_values("pop_growth").tail(5)
    print(f"  city {u.pop_first.sum():,.0f} -> {u.pop_last.sum():,.0f} ({100 * growth / u.pop_first.sum():.1f} %); "
          f"the five fastest ({', '.join(fastest.name)}) take {100 * (fastest.pop_last - fastest.pop_first).sum() / growth:.0f} %, "
          f"Torca alone {100 * (u.loc['UPL07', 'pop_last'] - u.loc['UPL07', 'pop_first']) / growth:.1f} %")
    print("  losing: " + ", ".join(f"{r.name} {100 * r.pop_growth:+.1f} %" for r in u.sort_values("pop_growth").head(5).itertuples()))
    print(f"  population growth against traffic lights {spearman(u, 'pop_growth', 'SIGNALISED_INTERSECTION_DENSITY')}, arterial "
          f"{spearman(u, 'pop_growth', 'ARTERIAL_ROAD_AREA_SHARE')}, TransMilenio {spearman(u, 'pop_growth', 'TRANSMILENIO_STATION_DENSITY')}, "
          f"cameras {spearman(u, 'pop_growth', 'SPEED_CAMERA_DENSITY')}")
    u["cycleway_growth"] = u.cycleway_last - u.cycleway_first
    u["cycleway_per_100k"] = 1e5 * u.cycleway_last / u.pop_last
    print(f"  cycleway {u.cycleway_first.sum():.0f} -> {u.cycleway_last.sum():.0f} km; its growth against population growth "
          f"{spearman(u, 'cycleway_growth', 'pop_growth')}, arterial {spearman(u, 'cycleway_growth', 'ARTERIAL_ROAD_AREA_SHARE')}, "
          f"the network of {FIRST} {spearman(u, 'cycleway_growth', 'cycleway_first')}")
    print(f"  cycleway per 100 000 residents in {LAST}: {u.cycleway_per_100k.min():.1f} ({u.loc[u.cycleway_per_100k.idxmin(), 'name']}) "
          f"to {u.cycleway_per_100k.max():.1f} ({u.loc[u.cycleway_per_100k.idxmax(), 'name']}), median {u.cycleway_per_100k.median():.1f}")
    u["signs_growth"] = u.signs_last / u.signs_2015 - 1
    print(f"  vertical signs {u.signs_2015.sum():,.0f} (2015) -> {u.signs_last.sum():,.0f}; growth against population growth "
          f"{spearman(u, 'signs_growth', 'pop_growth')}")
    t = u.loc["UPL07"]
    print(f"  Torca: {t.pop_first:,.0f} -> {t.pop_last:,.0f} residents on {t.area:.1f} km2, {t.cycleway_last:.1f} km of cycleway, "
          f"parties {t.parties_ALL_first:.0f} -> {t.parties_ALL_last:.0f}")


def mobility(u: pd.DataFrame) -> None:
    print("\nP11 and P12. How the city moved: trips by mode")
    for mode in MODES:
        a, b = u[f"trips_{mode}_first"].sum(), u[f"trips_{mode}_last"].sum()
        print(f"  {mode:10} {a:,.0f} -> {b:,.0f} per weekday ({100 * (b / a - 1):+.0f} %); per resident "
              f"{a / u.pop_first.sum():.3f} -> {b / u.pop_last.sum():.3f}")
    share = lambda tag: u[f"trips_MOTORCYCLE_{tag}"] / (u[f"trips_MOTORCYCLE_{tag}"] + u[f"trips_CAR_{tag}"])
    city = lambda tag: u[f"trips_MOTORCYCLE_{tag}"].sum() / (u[f"trips_MOTORCYCLE_{tag}"].sum() + u[f"trips_CAR_{tag}"].sum())
    u["moto_share_change"] = share("last") - share("first")
    print(f"  motorcycle share of motorised trips {city('first'):.3f} -> {city('last'):.3f}; rose most in "
          + ", ".join(f"{r.name} {100 * r.moto_share_change:+.1f} pts" for r in u.sort_values("moto_share_change").tail(5).itertuples())
          + f"; against population growth {spearman(u, 'moto_share_change', 'pop_growth')}")
    for mode in ("MOTORCYCLE", "BICYCLE"):
        u[f"{mode}_trip_growth"] = u[f"trips_{mode}_last"] / u[f"trips_{mode}_first"] - 1
        u[f"{mode}_party_growth"] = u[f"parties_{mode}_last"] / u[f"parties_{mode}_first"] - 1
        print(f"  {mode.lower()} trip growth against its party growth {spearman(u, f'{mode}_trip_growth', f'{mode}_party_growth')}")
    print(f"  bicycle trip growth against cycleway growth {spearman(u, 'BICYCLE_trip_growth', 'cycleway_growth')}")

    print(f"\nP13. The rate per trip, {FIRST} against {LAST} (corrected set)")
    u["party_growth"] = u.parties_ALL_last / u.parties_ALL_first - 1
    u["trip_growth"] = u.trips_last / u.trips_first - 1
    u["rate_change"] = (u.parties_ALL_last / u.trips_last) / (u.parties_ALL_first / u.trips_first) - 1
    print(f"  city parties {u.parties_ALL_first.sum():,.0f} -> {u.parties_ALL_last.sum():,.0f}, trips "
          f"{100 * (u.trips_last.sum() / u.trips_first.sum() - 1):+.0f} %; rate per trip, median unit {100 * u.rate_change.median():+.0f} %")
    print(f"  rate change against cycleway growth {spearman(u, 'rate_change', 'cycleway_growth')}, arterial "
          f"{spearman(u, 'rate_change', 'ARTERIAL_ROAD_AREA_SHARE')}, population growth {spearman(u, 'rate_change', 'pop_growth')}; "
          f"party growth against trip growth {spearman(u, 'party_growth', 'trip_growth')}, population growth {spearman(u, 'party_growth', 'pop_growth')}")


def pandemic_and_recording() -> None:
    monthly = table("matrix", "analysis__casualties_by_unit_month")
    monthly = monthly[monthly.SCALE == "UPL"].groupby(["YEAR", "MONTH"])[["AFFECTED_PARTIES", "PERSONS_KILLED"]].sum()
    parties = monthly.AFFECTED_PARTIES.unstack()
    print("\nP14. The pandemic (observed set)")
    print("  2020 against 2019 by month, %: " + " ".join(f"{100 * x:.0f}" for x in parties.loc[2020] / parties.loc[2019]))
    print("  2021 against 2019 by month, %: " + " ".join(f"{100 * x:.0f}" for x in parties.loc[2021] / parties.loc[2019]))
    killed = monthly.PERSONS_KILLED.unstack().sum(axis=1)
    print(f"  parties 2019 {parties.loc[2019].sum():,.0f}, 2020 {parties.loc[2020].sum():,.0f}; killed 2019 {killed.loc[2019]:.0f}, 2020 {killed.loc[2020]:.0f}")
    m = table("matrix", "analysis__matrix_long")
    m = m[m.SCALE == "UPL"].groupby(["YEAR", "PARTY_TYPE"])[["AFFECTED_PARTIES", "PERSONS_KILLED"]].sum()
    trips = weekday_trips().groupby(level="YEAR").sum()
    # The corrected set is the one the study reports. The recording ramp runs through these years
    # and inflates the observed car occupant, so both are printed; deaths are not reclassified by
    # the correction and come out the same in the two.
    corrected = table("matrix", "analysis__matrix_long__rho_corrected")
    corrected = corrected[corrected.SCALE == "UPL"].groupby(["YEAR", "PARTY_TYPE"])[["AFFECTED_PARTIES", "PERSONS_KILLED"]].sum()
    for counts, dataset in ((m, "observed"), (corrected, "corrected")):
        for column, label in (("AFFECTED_PARTIES", "parties"), ("PERSONS_KILLED", "killed")):
            per_trip = counts[column].unstack()[MODES].loc[2019:2022] / trips[MODES].loc[2019:2022]
            rel = per_trip / per_trip.loc[2019]
            print(f"  {label} per trip against 2019, {dataset}: " + "; ".join(
                f"{mode.lower()} " + " ".join(f"{y}:{rel.loc[y, mode]:.2f}" for y in (2020, 2021, 2022)) for mode in MODES))

    print("\nP15. The recording change without rho (observed set)")
    print("  2018 against 2017 by month, %: " + " ".join(f"{100 * x:.0f}" for x in parties.loc[2018] / parties.loc[2017]))
    persons = table("matrix", "analysis__matrix_long")
    persons = persons[persons.SCALE == "UPL"].groupby("YEAR")[["PERSONS_INJURED", "PERSONS_KILLED"]].sum()
    ratio = 1000 * persons.PERSONS_KILLED / persons.PERSONS_INJURED
    print("  killed per 1000 injured: " + " ".join(f"{y}:{ratio.loc[y]:.1f}" for y in range(2014, 2021)))
    shares = m.AFFECTED_PARTIES.unstack()
    shares = 100 * shares.div(shares.sum(axis=1), axis=0)
    print("  car occupant share of parties, %: " + " ".join(f"{y}:{shares.loc[y, 'CAR']:.1f}" for y in (2012, 2017, 2018, 2021, 2023)))
    print("  pedestrian share of parties, %: " + " ".join(f"{y}:{shares.loc[y, 'PEDESTRIAN']:.1f}" for y in (2012, 2017, 2018, 2023)))


def cross_sections_against_panel() -> None:
    print("\nP16. The cross-sections against the panel (inherited specification, main panel)")
    spec = dict(DATASET="RHO_CORRECTED", OFFSET="MODE_EXPOSURE", FAMILY="NEGATIVE_BINOMIAL", CANDIDATE_SET="URBAN_ONLY")
    c = table("regressions", "analysis__regression_coefficients")
    m = table("regressions", "analysis__regression_models")
    for key, value in spec.items():
        c, m = c[c[key] == value], m[m[key] == value]
    c = c[c.TERM != "INTERCEPT"]
    cells = m.groupby(["SELECTION_METHOD", "PAIR"]).size()
    chosen = c.groupby(["SELECTION_METHOD", "PAIR", "TERM"]).agg(n=("COEFFICIENT", "size"),
                                                                 positive=("COEFFICIENT", lambda s: int((s > 0).sum()))).reset_index()
    chosen["share"] = [n / cells[(meth, pair)] for meth, pair, n in zip(chosen.SELECTION_METHOD, chosen.PAIR, chosen.n)]
    chosen["sign"] = np.sign(2 * chosen.positive - chosen.n)
    p = table("panel", "analysis__panel_coefficients")
    p = p[(p.DATASET == "RHO_CORRECTED") & (p.MODEL == "CRE") & (p.PANEL == "PRINCIPAL")]
    # The panel's between-unit reading of each variable: the constant, or for the cycleway its between effect.
    between = p[(p.ROLE == "CONSTANT") | ((p.ROLE == "BETWEEN") & (p.TERM == "CYCLEWAY_LENGTH_DENSITY"))][["PAIR", "TERM", "COEFFICIENT", "P_VALUE"]]
    for method in ("BEST_SUBSET_AIC", "BACKWARD_ELIMINATION"):
        x = chosen[chosen.SELECTION_METHOD == method].merge(between, on=["PAIR", "TERM"])
        often = x[x.n >= 3]
        agree = np.sign(often.COEFFICIENT) == often.sign
        associated = often.P_VALUE < LEVEL
        x_assoc = x.P_VALUE < LEVEL
        print(f"  {method}: of {len(often)} variable-pair combinations chosen in three years or more, the panel's sign agrees in "
              f"{int(agree.sum())} ({100 * agree.mean():.0f} %), and in {int(agree[associated].sum())} of the {int(associated.sum())} "
              f"the panel calls associations; median selection share {x[x_assoc].share.median():.2f} where the panel finds an "
              f"association and {x[~x_assoc].share.median():.2f} where it does not; Spearman of share against -log10 p "
              f"{x.share.corr(-np.log10(x.P_VALUE), method='spearman'):.2f}")


def denominator_of_phase_four() -> None:
    print("\nP17. The phase 4 cycleway divergence under two denominators (pedestrian against car)")
    d = table("contrast", "analysis__contrast_design")
    e = table("exposure", "analysis__fitted_exposure_by_unit")
    e = e[(e.DAY_TYPE == "WEEKDAY") & (e.EXPOSURE_VARIANT == "FITTED_PANDEMIC_PATCHED") & e.YEAR.between(2012, 2024)
          & (e.ACTOR_TYPE == "PEDESTRIAN")]
    walking = e.groupby("AREA_CODE").TRIPS_PER_DAY_OF_TYPE_OVER_15MIN.sum()
    candidates = ["WALKING_SHARE", "CYCLING_SHARE", "CYCLEWAY_LENGTH_DENSITY"]
    z = lambda s: (s - s.mean()) / s.std(ddof=1)
    for stratum in ("PERSONS_KILLED", "PERSONS_INJURED"):
        f = d[(d.SERIES == "PEDESTRIAN__CAR") & (d.STRATUM == stratum) & (d.DATASET == "RHO_CORRECTED")].set_index("AREA_CODE")
        f = f.assign(RATE_PER_TRIP=f.CASUALTIES / walking.loc[f.index])
        for response, label in (("RATE_PER_MILLION", "per resident, as phase 4"), ("RATE_PER_TRIP", "per pedestrian trip")):
            fits = []
            for k in (2, 3):
                for chosen in itertools.combinations(candidates, k):
                    X = pd.concat([z(f[v].astype(float)) for v in chosen], axis=1).to_numpy(float)
                    fits.append((chosen, sm.OLS(z(f[response].astype(float)).to_numpy(float), X).fit()))
            best_vars, best = min(fits, key=lambda vf: vf[1].aic)
            full = dict(zip(candidates, fits[-1][1].params)), dict(zip(candidates, fits[-1][1].pvalues))
            cyc = ("not selected" if "CYCLEWAY_LENGTH_DENSITY" not in best_vars else
                   f"{best.params[best_vars.index('CYCLEWAY_LENGTH_DENSITY')]:+.2f} (p {best.pvalues[best_vars.index('CYCLEWAY_LENGTH_DENSITY')]:.3f})")
            print(f"  {stratum:15} {label:26} AIC-selected model: cycleway {cyc}; three-covariate model "
                  f"{full[0]['CYCLEWAY_LENGTH_DENSITY']:+.2f} (p {full[1]['CYCLEWAY_LENGTH_DENSITY']:.3f})")


def main() -> int:
    u = unit_table()
    people_and_places(u)
    mobility(u)
    pandemic_and_recording()
    cross_sections_against_panel()
    denominator_of_phase_four()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
