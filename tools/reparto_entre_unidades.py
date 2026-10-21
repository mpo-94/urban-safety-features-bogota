"""Whether the way a casualty count splits across units changes from one year to the next.

    .venv/Scripts/python.exe tools/reparto_entre_unidades.py [count] [run]

`count` is `parties` (the default), `persons` (injured plus killed) or `killed`.

**Read only.** It reads the monthly table a `corrected` run exports and writes nothing.
The default run is the one the casualty annexes of the thesis are drawn from.

The annexes show one choropleth per count, the accumulated one, instead of one per year, and
that is a claim about the data: that a year's choropleth would look like the accumulated one.
A choropleth carries the ranking of the units and how much the top of it weighs, so this
measures exactly those two things on the observed dataset, the only one with maps.

**1. The ranking.** Spearman's correlation between each year's count per unit and the
accumulated count, and the largest number of places any unit moves between the two.

**2. The weight of the top.** The share of each year's count that falls in the five units
with most of it over the whole period, and how many of those five are also among the five
largest of that year.

The second is the one a reader sees: the dark units of the choropleth. The first says how
far the claim reaches, because the units in the middle do reorder and the claim is about the
head of the distribution, not about every unit. For `killed` the ranking moves much more,
and most of that is the noise of small numbers: a unit records about fifteen deaths a year.

**3. For `killed`, how deadly a unit is**, as deaths per hundred injured over the whole
period. It is why the persons annex shows the deaths on a map of their own: if every unit
killed the same share of the people it injured, the deaths would only repeat the injured.
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = "run_20261006_203551"
TOP = 5
COUNTS = {
    "parties": ["AFFECTED_PARTIES"],
    "persons": ["PERSONS_INJURED", "PERSONS_KILLED"],
    "killed": ["PERSONS_KILLED"],
}

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    count = sys.argv[1] if len(sys.argv) > 1 else "parties"
    if count not in COUNTS:
        raise SystemExit(f"count must be one of {', '.join(COUNTS)}, not {count}")
    run = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_RUN
    monthly = pd.read_csv(ROOT / "results" / run / "data" / "analysis__casualties_by_unit_month.csv")
    observed = monthly[monthly["DATASET"] == "OBSERVED"].copy()
    observed["COUNT"] = observed[COUNTS[count]].sum(axis=1)
    by_unit = observed.pivot_table(index="AREA_CODE", columns="YEAR", values="COUNT",
                                   aggfunc="sum", fill_value=0)
    accumulated = by_unit.sum(axis=1)
    accumulated_rank = accumulated.rank(ascending=False)
    head = list(accumulated.nlargest(TOP).index)

    rows = []
    for year in by_unit.columns:
        that_year = by_unit[year]
        moved = (that_year.rank(ascending=False) - accumulated_rank).abs()
        rows.append({
            "year": year,
            "city": int(that_year.sum()),
            "spearman": that_year.corr(accumulated, method="spearman"),
            "largest_move": int(moved.max()),
            "unit_that_moves": moved.idxmax(),
            "top_share": that_year[head].sum() / that_year.sum(),
            "top_kept": len(set(head) & set(that_year.nlargest(TOP).index)),
            "largest_unit": that_year.idxmax(),
        })
    table = pd.DataFrame(rows)

    print(f"run {run}, observed dataset, count {count}, {len(by_unit)} units, "
          f"{len(by_unit.columns)} years")
    print(f"the {TOP} units with most of it over the period: {', '.join(head)}")
    print(f"their share of the accumulated count: {accumulated[head].sum() / accumulated.sum():.1%}")
    print()
    print(table.to_string(index=False, formatters={"spearman": "{:.3f}".format,
                                                   "top_share": "{:.1%}".format}))
    print()
    print(f"Spearman from {table['spearman'].min():.3f} to {table['spearman'].max():.3f} "
          f"(median {table['spearman'].median():.3f}); top-{TOP} share from "
          f"{table['top_share'].min():.1%} to {table['top_share'].max():.1%}; at least "
          f"{table['top_kept'].min()} of the {TOP} kept every year; largest unit every year among "
          f"{sorted(table['largest_unit'].unique())}; city from {table['city'].min()} to "
          f"{table['city'].max()} a year")

    if count == "killed":
        totals = observed.groupby("AREA_CODE")[["PERSONS_INJURED", "PERSONS_KILLED"]].sum()
        deadly = (100 * totals["PERSONS_KILLED"] / totals["PERSONS_INJURED"]).sort_values()
        print()
        print("deaths per hundred injured, whole period, by unit:")
        print(f"  from {deadly.min():.2f} ({deadly.idxmin()}) to {deadly.max():.2f} "
              f"({deadly.idxmax()}), median {deadly.median():.2f}")
        print("  the three deadliest:", ", ".join(f"{u} {v:.2f}" for u, v in deadly.tail(3)[::-1].items()))
        print(f"  Spearman of killed against injured by unit: "
              f"{totals['PERSONS_KILLED'].corr(totals['PERSONS_INJURED'], method='spearman'):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
