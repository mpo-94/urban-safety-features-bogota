"""The shape of the ρ ramp, which is what fixes the reference window of the correction.

    .venv/Scripts/python.exe tools/rampa_de_rho.py [rho_run]

**Read only.** It reads the city ρ the `rho` route exports and prints; nothing in `src/`
imports it. The default run is the one section 4.4 of the thesis quotes.

D28 settles the reference window by the shape of the climb rather than by a sign test, and
the thesis prints that shape as a table. The table had no instrument behind it: the common
increment was recomputable by hand, but the standard deviation it is expressed in was not
written down anywhere, neither which years nor which estimator. This is that instrument, and
the definition it fixes is the one D28 states in words.

**The common increment** of a year is the mean over the nine pairs of the year-on-year change
in logit ρ,

    Δ_t = (1/9) Σ_p [logit ρ_{p,t} − logit ρ_{p,t−1}],

on the city value of each pair, which is pooled and not averaged over units. It is undefined
for 2008, because 2007 does not distinguish the two parties of a vehicle-vehicle crash and
six of the nine pairs have no ρ that year (D18).

**The scale** is the standard deviation of Δ over the steps that lie inside the settled
years 2010-2016, the same span D28 calibrates its triplet test on: the six steps ending in
2011 to 2016, as a population standard deviation, since those six steps are the whole of
what is being described and not a sample from something larger. Expressed on it, a step of
2 means a year moved twice as much as a settled year typically does. The sample standard
deviation and two other spans are printed beside it, so the choice can be seen to matter or
not.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import config  # noqa: E402

DEFAULT_RUN = "run_20261016_031817"

# D28's settled years. The steps inside them are the ones that end in 2011 to 2016.
SETTLED_YEARS = (2010, 2016)
# The steps the thesis tabulates: the last year of the climb and the two of the window.
TABULATED_STEPS = (2022, 2023, 2024)


def city_rho(run: str) -> pd.DataFrame:
    """The city ρ by year and pair, as the route exports it for reading."""
    path = REPO / "results" / run / "data" / f"{config.PRESENTATION_PREFIX}__rho_city_rho__by_year.csv"
    if not path.exists():
        raise FileNotFoundError(f"{run} holds no city rho table: {path}")
    return pd.read_csv(path).set_index(config.YEAR_COL).astype(float)


def common_increment(rho: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """Δ_t, and the per-pair steps it averages.

    A year with any pair undefined gets no Δ, rather than a mean over fewer pairs, because a
    mean over a different set of pairs is a different statistic.
    """
    logit = np.log(rho / (1.0 - rho))
    steps = logit.diff()
    delta = steps.mean(axis=1, skipna=False)
    return delta, steps


def settled_scale(delta: pd.Series, first: int, last: int, ddof: int) -> float:
    inside = delta.loc[first + 1:last].dropna()
    return float(inside.std(ddof=ddof))


def main() -> int:
    run = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RUN
    try:
        rho = city_rho(run)
    except FileNotFoundError as error:
        print(error)
        return 1
    delta, steps = common_increment(rho)
    scale = settled_scale(delta, *SETTLED_YEARS, ddof=0)
    print(f"run: {run}, {rho.shape[1]} pairs")
    print(f"scale: population sd of the common increment over the steps inside "
          f"{SETTLED_YEARS[0]}-{SETTLED_YEARS[1]}, {scale:.4f}\n")

    print(f"{'step':<14} {'increment':>10} {'in sd':>7} {'pairs rising':>13}")
    for year in delta.index:
        if pd.isna(delta.loc[year]):
            continue
        rising = int((steps.loc[year] > 0).sum())
        mark = "  <- tabulated" if year in TABULATED_STEPS else ""
        print(f"{year - 1} to {year:<6} {delta.loc[year]:>+10.3f} {delta.loc[year] / scale:>+7.2f} "
              f"{rising:>9} of {steps.loc[year].notna().sum()}{mark}")

    print("\nhow much the choice of scale moves the tabulated steps:")
    for first, last in ((2009 - 1, 2016), SETTLED_YEARS, (2011, 2016)):
        for ddof in (0, 1):
            s = settled_scale(delta, first, last, ddof)
            cells = ", ".join(f"{year} {delta.loc[year] / s:+.2f}" for year in TABULATED_STEPS)
            print(f"  steps inside {first}-{last}, ddof={ddof}: sd {s:.4f}; {cells}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
