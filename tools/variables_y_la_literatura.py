"""How many variables survive at 5 % and at 10 %, and do the ones the literature names?

    .venv/Scripts/python.exe tools/variables_y_la_literatura.py [run]

**Read only.** It reads the exported tables of a finished regression run and the
declared literature expectations in `config.LITERATURE_EXPECTATIONS`, and writes one CSV
beside its log. Nothing in `src/` imports it.

The advisor asked two things on 2026-10-12 and they need different arithmetic, because
the two selection methods use the p-value in opposite ways. In backward elimination the
alpha **is** the stopping rule, so everything that survives is significant by
construction and what a looser alpha changes is how many variables survive. In the AIC
search the p-value never enters, so significance can be counted afterwards on what AIC
chose.

**At 5 % the median cell keeps three variables and 84 of 1 766 keep none; at 10 % the
median is four and only 8 keep none.** The counterfactual is exact rather than refitted:
the elimination rule is the same for any alpha and all that changes is where the walk
stops, so a looser alpha is a prefix of the stricter walk and is read off the recorded
path. It is validated by reconstructing alpha = 0.05, which reproduces 1 766 of 1 766
walks the run saved. **It only works in the loosening direction** — a stricter alpha
would need steps that never happened.

| Family | cells | median at 5 % | none at 5 % | median at 10 % | none at 10 % |
|---|---:|---:|---:|---:|---:|
| Least squares | 624 | 2 | 72 | 2 | 8 |
| Poisson | 624 | 6 | 0 | 6 | 0 |
| Negative binomial | 518 | 3 | 12 | 4 | 0 |

**All eight cells that stay empty at 10 % are least squares**, and the 72 that the
loosening rescues are too. Poisson never has an empty cell at either alpha, which is
overdispersion and not explanatory power: its standard errors come out too small, so
almost nothing is eliminated.

The second half is the crossing, and the answer changed shape twice as the literature was
actually read instead of assumed. **Of the twelve candidates only three have a quantified
expectation with a definite sign, one has a mechanism and no estimate, five are disputed,
one is a reported null and two have nothing in the corpus at all.** The three with a sign
split two to one: the arterial road agrees in 80 % of its significant coefficients and the
street tree in 71 %, while the signalised intersection carries the opposite sign in 93 % of
its own. The sidewalk, the one that rests on a mechanism, agrees in 60 %.

**That is one reversal, and it was four before the three BRT sources and the three of
2026-10-13 were read.** The TransMilenio station, the bus stop and the pedestrian crossing
each stopped being a contradiction for the same reason: the literature on them does not
hold a single sign. The BRT sources estimate the corridor as protective and describe the
station as the place where pedestrians are run over crossing to reach it. The marked
crossing made no difference on two-lane roads and was associated with a *higher* crash rate
on multilane roads above about 12,000 vehicles a day. The bus stop comes out protective for
deaths in the Bogota study and hazardous at the site level where stop usage is measured
rather than stop density. **Three of the four reversals were an artefact of an incomplete
reading, not a finding.**

The one that survives has a reading the sources themselves supply: a signal is **placed
where the traffic already is**, so a cross-section cannot tell the effect of the feature
from the reason it was built there. Chapter 2 of the thesis already says exactly this about
the pedestrian bridge.

**The third report puts that reading to the test rather than accepting it, and now it
holds.** Ranked against the arterial share — the one thing this study measures that stands
for where the fast, heavy traffic is — the signalised intersection correlates at 0.89, the
highest of any variable other than the arterial itself. The test still cuts both ways and
that limit is worth keeping: the vertical signage and the bridge are the two most
arterial-bound variables of all, at 0.92 and 0.90, and both come out negative, so sitting on
the arterial does not by itself force a positive coefficient.

What that leaves is a single reversal with a demonstrated reading, which is further than a
cross-section usually gets and still not a causal claim. It is the substantive argument for
the panel stage, where the same unit is observed before and after the infrastructure arrives
and placement stops being confounded with effect.

The expectations themselves are declared in `config.LITERATURE_EXPECTATIONS`, one entry
per candidate, with the estimate as its source states it and a line on how far that
source's setting is from ours. They live there rather than in a document so that the
table the thesis prints and the measurement that fills it read the same declaration.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# The variable labels are Spanish and the console this runs on is not UTF-8, so
# without this the accented ones come out as replacement characters.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config  # noqa: E402

# The run the docstring's figures come from. Named here rather than resolved to the
# newest one, so a number a document quotes can be recomputed against the run it
# came from instead of against whatever ran last.
DEFAULT_RUN = "run_20261009_084114"

# The year the placement test is taken in. Ten of the twelve candidates are a snapshot, so
# the year only moves the cycleway and the vertical signage; the last one is taken so that
# both are read at their fullest extent rather than part-built.
PLACEMENT_YEAR = 2023

# What identifies one fitted cell. The model id would do, but it is a concatenation
# and grouping on the parts is what lets the breakdowns below be taken by family
# and by dataset without parsing it back apart.
CELL = ["DATASET", "OFFSET", "PAIR", "YEAR", "FAMILY"]

FAMILY_LABELS = {
    "OLS": "Least squares",
    "POISSON": "Poisson",
    "NEGATIVE_BINOMIAL": "Negative binomial",
}

DIRECTION_LABELS = {
    config.EXPECTS_FEWER: "fewer casualties",
    config.EXPECTS_MORE: "more casualties",
    config.EXPECTS_NOTHING: "no association",
    config.EXPECTS_DISPUTED: "disputed",
    config.NO_EXPECTATION: "no expectation",
}

# The sign a declared expectation predicts for our coefficient. The response is a
# casualty count with exposure in the offset, so a feature the literature reports as
# protective predicts a negative coefficient. The four entries that predict nothing
# map to None, and a None is reported as such rather than scored as agreement.
EXPECTED_SIGN = {
    config.EXPECTS_FEWER: -1,
    config.EXPECTS_MORE: +1,
    config.EXPECTS_NOTHING: None,
    config.EXPECTS_DISPUTED: None,
    config.NO_EXPECTATION: None,
}


def surviving_at(walk: pd.DataFrame, alpha: float) -> int:
    """How many variables the walk would keep if it stopped at this alpha.

    The recorded path holds, for every variable removed, the step it left on and the
    p-value it carried then. Loosening the alpha changes nothing up to the first step
    whose p-value does not exceed the new alpha: at that point there is no longer a
    reason to remove anything, and everything still standing is the model.
    """
    removed = walk[walk["STEP_REMOVED"].notna()].sort_values("STEP_REMOVED")
    steps_that_still_happen = 0
    for p_value in removed["P_VALUE"]:
        if p_value <= alpha:
            break
        steps_that_still_happen += 1
    return len(walk) - steps_that_still_happen


def count_by_alpha(walks: pd.DataFrame) -> pd.DataFrame:
    """One row per completed walk: how many variables at each alpha, and what was saved."""
    rows = []
    for key, walk in walks.groupby(CELL, observed=True):
        rows.append(
            dict(
                zip(CELL, key),
                candidates=len(walk),
                at_05=surviving_at(walk, 0.05),
                at_10=surviving_at(walk, 0.10),
                saved_by_the_run=int(walk["SURVIVED"].sum()),
            )
        )
    return pd.DataFrame(rows)


def report_alpha(data: Path) -> pd.DataFrame:
    paths = pd.read_parquet(data / "analysis__regression_elimination_path.parquet")
    coefficients = pd.read_parquet(data / "analysis__regression_coefficients.parquet")
    predictors = coefficients[coefficients["TERM"] != "INTERCEPT"]

    print("=" * 78)
    print("HOW MANY VARIABLES ARE SIGNIFICANT, AT 5 % AND AT 10 %")
    print("=" * 78)

    aic = predictors[predictors["SELECTION_METHOD"] == config.BEST_SUBSET_SELECTION]
    per_model = (
        aic.assign(at_05=aic["P_VALUE"] <= 0.05, at_10=aic["P_VALUE"] <= 0.10)
        .groupby(CELL, observed=True)
        .agg(chosen=("TERM", "size"), at_05=("at_05", "sum"), at_10=("at_10", "sum"))
    )
    print(
        f"\nAIC search — the p-value does not select, so significance is read afterwards."
        f"\n  {len(per_model)} models, {len(aic)} chosen coefficients"
        f"\n  significant at 5 %: {int((aic['P_VALUE'] <= 0.05).sum())}"
        f" ({(aic['P_VALUE'] <= 0.05).mean():.1%} of what AIC chose)"
        f"\n  significant at 10 %: {int((aic['P_VALUE'] <= 0.10).sum())}"
        f" ({(aic['P_VALUE'] <= 0.10).mean():.1%})"
    )
    for column, alpha in (("at_05", 0.05), ("at_10", 0.10)):
        empty = int((per_model[column] == 0).sum())
        print(
            f"  at {alpha:.2f}: median {per_model[column].median():.0f} per model,"
            f" mean {per_model[column].mean():.2f},"
            f" models with none {empty} ({empty / len(per_model):.1%})"
        )

    walks = paths[paths["WALK_COMPLETED"]]
    incomplete = paths[~paths["WALK_COMPLETED"]].groupby(CELL, observed=True).ngroups
    counts = count_by_alpha(walks)

    disagreeing = int((counts["at_05"] != counts["saved_by_the_run"]).sum())
    print(
        f"\nBackward elimination — the alpha is the stopping rule."
        f"\n  {len(counts)} completed walks, {incomplete} cells with none"
        f"\n  VALIDATION: reconstructing 0.05 matches"
        f" {len(counts) - disagreeing} of {len(counts)} walks"
        f"  {'OK' if disagreeing == 0 else 'FAILS'}"
    )
    if disagreeing:
        raise SystemExit(
            "the reconstruction does not reproduce the run, so the 10 % figure cannot be trusted"
        )

    for column, alpha in (("at_05", 0.05), ("at_10", 0.10)):
        empty = int((counts[column] == 0).sum())
        print(
            f"  at {alpha:.2f}: median {counts[column].median():.0f} per cell,"
            f" mean {counts[column].mean():.2f},"
            f" cells with none {empty} ({empty / len(counts):.1%})"
        )
    rescued = int(((counts["at_05"] == 0) & (counts["at_10"] > 0)).sum())
    still_empty = counts[(counts["at_05"] == 0) & (counts["at_10"] == 0)]
    print(
        f"  of the {int((counts['at_05'] == 0).sum())} cells empty at 0.05,"
        f" {rescued} stop being empty at 0.10;"
        f" the {len(still_empty)} that remain are"
        f" {', '.join(sorted(FAMILY_LABELS.get(f, f) for f in still_empty['FAMILY'].unique()))}"
    )

    by_family = counts.groupby("FAMILY").agg(
        cells=("at_05", "size"),
        median_05=("at_05", "median"),
        none_05=("at_05", lambda column: int((column == 0).sum())),
        median_10=("at_10", "median"),
        none_10=("at_10", lambda column: int((column == 0).sum())),
    )
    by_family.index = [FAMILY_LABELS.get(name, name) for name in by_family.index]
    print("\n  by family:")
    print(by_family.to_string(float_format=lambda value: f"{value:.0f}"))
    return counts


def literature_crossing(data: Path) -> pd.DataFrame:
    """Each candidate's declared expectation against the sign its coefficients carry.

    Restricted to the pairs whose affected party is the pedestrian. That restriction is
    not a convenience: every quantified expectation in the corpus is a pedestrian rate
    with pedestrian trips in the denominator, and reading it against a cyclist or
    motorcyclist coefficient would be comparing two different quantities.

    Pure: it prints nothing, so the slide generator in `deliverables/` can call it
    instead of reimplementing the crossing and measuring its own copy of it.
    """
    coefficients = pd.read_parquet(data / "analysis__regression_coefficients.parquet")
    predictors = coefficients[coefficients["TERM"] != "INTERCEPT"].copy()
    predictors["AFFECTED"] = predictors["PAIR"].str.split("__").str[0]
    pedestrian = predictors[predictors["AFFECTED"] == "PEDESTRIAN"]

    rows = []
    for name in config.REGRESSION_URBAN_CANDIDATES:
        expectation = config.LITERATURE_EXPECTATIONS_BY_PREDICTOR[name]
        appearances = pedestrian[pedestrian["TERM"] == name]
        significant = appearances[appearances["P_VALUE"] <= 0.05]
        positive = int((significant["COEFFICIENT_STANDARDISED"] > 0).sum())
        share_positive = positive / len(significant) if len(significant) else float("nan")
        wanted = EXPECTED_SIGN[expectation.direction]
        if wanted is None:
            verdict = "no sign predicted"
        else:
            share_as_expected = share_positive if wanted > 0 else 1 - share_positive
            verdict = (
                f"{'agrees' if share_as_expected > 0.5 else 'contradicts'}"
                f" ({share_as_expected:.0%} as expected)"
            )
        rows.append(
            {
                "predictor": name,
                "variable": config.predictor_label_es(name),
                "direction": expectation.direction,
                "expectation": DIRECTION_LABELS[expectation.direction],
                "basis": expectation.basis,
                "sources": " ".join(expectation.source_citation) or "-",
                "appears": len(appearances),
                "significant_05": len(significant),
                "share_positive": share_positive,
                "verdict": verdict,
            }
        )
    return pd.DataFrame(rows)


def report_literature(data: Path) -> pd.DataFrame:
    crossing = literature_crossing(data)
    print("\n" + "=" * 78)
    print("WHAT THE LITERATURE EXPECTS, AGAINST WHAT THE MODELS SELECT")
    print("=" * 78)
    print(
        "  pedestrian pairs only, both methods pooled for the sign and reported"
        "\n  separately for how often the variable is kept"
    )
    print()
    print(
        crossing.drop(columns=["predictor", "direction", "sources"]).to_string(
            index=False, float_format=lambda value: f"{value:.0%}"
        )
    )

    print("\n  what each expectation rests on:")
    for name in config.REGRESSION_URBAN_CANDIDATES:
        expectation = config.LITERATURE_EXPECTATIONS_BY_PREDICTOR[name]
        label = config.predictor_label_es(name)
        print(f"    {label}")
        if expectation.reported:
            print(f"      reported:      {expectation.reported}")
        print(f"      comparability: {expectation.comparability}")
        if expectation.source_citation:
            print(f"      sources:       {', '.join(expectation.source_citation)}")

    quantified = sum(
        1
        for e in config.LITERATURE_EXPECTATIONS
        if e.basis == config.QUANTIFIED_BASIS and EXPECTED_SIGN[e.direction] is not None
    )
    # Counted only where a sign is expected, like the quantified ones, so the five
    # categories stay a partition: the speed camera rests on a mechanism but is also
    # disputed, and counting it twice would make the categories add up to thirteen.
    mechanism = sum(
        1
        for e in config.LITERATURE_EXPECTATIONS
        if e.basis == config.MECHANISM_BASIS and EXPECTED_SIGN[e.direction] is not None
    )
    disputed = sum(
        1 for e in config.LITERATURE_EXPECTATIONS if e.direction == config.EXPECTS_DISPUTED
    )
    null_result = sum(
        1 for e in config.LITERATURE_EXPECTATIONS if e.direction == config.EXPECTS_NOTHING
    )
    nothing = sum(
        1 for e in config.LITERATURE_EXPECTATIONS if e.direction == config.NO_EXPECTATION
    )
    print(
        f"\n  of the {len(config.LITERATURE_EXPECTATIONS)} candidates:"
        f" {quantified} carry a quantified expectation with a definite sign,"
        f" {mechanism} a mechanism and no estimate,"
        f" {disputed} are disputed,"
        f" {null_result} is a reported null and"
        f" {nothing} have nothing in the corpus"
    )
    return crossing


def placement_against_arterial(data: Path) -> pd.DataFrame:
    """Puts the placement reading to the test instead of accepting it.

    If what contaminates the coefficient is where the work gets built, the variables that
    come out backwards should be the ones most tied to the arterial network. The arterial
    share is the only thing this study measures that stands for where the fast, heavy
    traffic is, so it is the available proxy and the test is only as good as it.

    **It survives for two of the four and fails for the other two**, which is the result
    that keeps the reading from being a blanket excuse.

    Pure, like `literature_crossing`, so the slide generator can call it.
    """
    frame = pd.read_parquet(data / "analysis__regression_data.parquet")
    # One row per unit: the table carries a row per unit and pair, and every unit appears
    # under the same eight pairs, so dropping duplicates is exact rather than a sample.
    units = frame[frame["YEAR"] == PLACEMENT_YEAR].drop_duplicates(subset=["AREA_CODE"])

    # El veredicto del cruce, derivado de la declaración en lugar de escrito aquí: lo que
    # una variable sin signo esperado haga con el suyo no es ni acuerdo ni desacuerdo, y
    # mantener la lista a mano ya se desincronizó una vez cuando TransMilenio pasó a estar
    # en disputa.
    verdicts = {}
    for row in literature_crossing(data).to_dict("records"):
        wanted = EXPECTED_SIGN[row["direction"]]
        if wanted is None:
            verdicts[row["predictor"]] = "no expectation"
            continue
        share = row["share_positive"] if wanted > 0 else 1 - row["share_positive"]
        verdicts[row["predictor"]] = "agrees" if share > 0.5 else "contradicts"

    rows = [
        {
            "variable": config.predictor_label_es(name),
            "spearman_with_arterial": units[name].corr(
                units["ARTERIAL_ROAD_AREA_SHARE"], method="spearman"
            ),
            "verdict": verdicts.get(name, "no expectation"),
        }
        for name in config.REGRESSION_URBAN_CANDIDATES
    ]
    return pd.DataFrame(rows).sort_values("spearman_with_arterial", ascending=False)


def report_placement(data: Path) -> pd.DataFrame:
    placement = placement_against_arterial(data)
    units = pd.read_parquet(data / "analysis__regression_data.parquet")
    units = units[units["YEAR"] == PLACEMENT_YEAR].drop_duplicates(subset=["AREA_CODE"])

    print("\n" + "=" * 78)
    print("IS THE REVERSAL EXPLAINED BY WHERE THE WORKS ARE BUILT?")
    print("=" * 78)
    print(f"  {len(units)} units, {PLACEMENT_YEAR}, rank correlation with the arterial share\n")
    print(placement.to_string(index=False, float_format=lambda value: f"{value:.3f}"))

    without_itself = placement[placement["variable"] != config.predictor_label_es(
        "ARTERIAL_ROAD_AREA_SHARE")]
    print("\n  by verdict:")
    print(
        without_itself.groupby("verdict")["spearman_with_arterial"]
        .agg(["size", "mean", "min", "max"])
        .to_string(float_format=lambda value: f"{value:.3f}")
    )
    print(
        "\n  The reading holds for the signalised intersection, the only reversal left: it"
        "\n  correlates higher with the arterial than any variable but the arterial itself."
        "\n  The limit still stands, though. Arterial co-location does not by itself force a"
        "\n  positive sign: the vertical signage and the bridge are the two most"
        "\n  arterial-bound variables of all and both come out negative."
    )
    return placement


def main() -> int:
    run = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RUN
    data = REPO / "results" / run / "data"
    if not data.is_dir():
        print(f"no such run: {data}")
        return 1
    print(f"run: {run}\n")

    counts = report_alpha(data)
    crossing = report_literature(data)
    placement = report_placement(data)

    # Beside the other tools' output rather than inside the run, so a run folder
    # holds only what the pipeline put there and stays diffable against another.
    output = REPO / "results" / "_tools_literatura"
    output.mkdir(parents=True, exist_ok=True)
    counts.to_csv(output / "variables_por_alfa.csv", index=False, encoding="utf-8")
    crossing.to_csv(output / "variables_y_la_literatura.csv", index=False, encoding="utf-8")
    placement.to_csv(output / "colocacion_en_la_arterial.csv", index=False, encoding="utf-8")
    print(f"\nwritten to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
