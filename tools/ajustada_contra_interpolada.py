"""How far the fitted exposure departs from D40's interpolated one, per mode, in the city and by unit.

    .venv/Scripts/python.exe tools/ajustada_contra_interpolada.py [fitted run] [interpolated run]

**Read only.** It reads `analysis__fitted_exposure_by_unit` of a `reconstruction` run and
`analysis__exposure_by_unit_interpolated` of an `exposure` run and writes nothing.

D62 printed this comparison when the fitted panel was first built, and found the two agreeing in
the aggregate and disagreeing about units by a great deal: cycling between 0.493 and 2.348 of D40's
figure. That was before D64 blended the two surveys that frame each year, and a blend of two seeds
moves each unit less than one seed does. The route no longer prints the comparison, so this is the
measurement a document cites.

Two answers per mode, on the weekday, which is the only day the reconstruction builds. The
**city** ratio of the summed exposures, year by year; and the **unit** ratio over the 1,200
constructed cells, as median, quartiles and range. The 360 measured cells, the three survey years
of the window, are checked to agree to rounding, because neither construction builds anything in a
year it measured; if they do not, the two runs do not describe the same surveys and the script
stops.
"""

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src import config  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DEFAULT_FITTED_RUN = "run_20261009_043126"
DEFAULT_INTERPOLATED_RUN = "run_20260924_233646"
KEY = ["AREA_CODE", "YEAR", "ACTOR_TYPE"]
COLUMN = "TRIPS_PER_DAY_OF_TYPE_OVER_15MIN"
WEEKDAY = config.MODEL_EXPOSURE_DAY_TYPE


def measure(fitted_run: str = DEFAULT_FITTED_RUN, interpolated_run: str = DEFAULT_INTERPOLATED_RUN):
    """The city ratio by year and mode, and the unit ratio's distribution by mode."""
    fitted = pd.read_parquet(REPO / "results" / fitted_run / "data" / "analysis__fitted_exposure_by_unit.parquet")
    fitted = fitted[(fitted.EXPOSURE_VARIANT == "FITTED") & (fitted.DAY_TYPE == WEEKDAY)].set_index(KEY)
    interpolated = pd.read_parquet(REPO / "results" / interpolated_run / "data"
                                   / "analysis__exposure_by_unit_interpolated.parquet")
    interpolated = interpolated[(interpolated.EXPOSURE_VARIANT == config.INTERPOLATED_VARIANT)
                                & (interpolated.DAY_TYPE == WEEKDAY)].set_index(KEY)
    common = fitted.index.intersection(interpolated.index)
    ratio = fitted.loc[common, COLUMN] / interpolated.loc[common, COLUMN]
    measured = fitted.loc[common, "EXPOSURE_PROVENANCE"] == "MEASURED"
    worst = float((ratio[measured] - 1).abs().max())
    if not worst < 1e-9:
        raise SystemExit(f"the measured cells differ by up to {worst}; the two runs are not the same surveys")
    built = ratio[~measured]
    units = built.groupby(level="ACTOR_TYPE").describe(percentiles=[0.25, 0.5, 0.75])[
        ["count", "min", "25%", "50%", "75%", "max"]]
    years = sorted(set(common.get_level_values("YEAR")))
    city = (fitted.loc[common, COLUMN].groupby(level=["YEAR", "ACTOR_TYPE"]).sum()
            / interpolated.loc[common, COLUMN].groupby(level=["YEAR", "ACTOR_TYPE"]).sum()).unstack("ACTOR_TYPE")
    return city.loc[years], units


def main() -> int:
    fitted_run = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FITTED_RUN
    interpolated_run = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_INTERPOLATED_RUN
    city, units = measure(fitted_run, interpolated_run)
    print(f"fitted {fitted_run} over interpolated {interpolated_run}, {WEEKDAY}")
    print("\ncity ratio, year by year")
    print(city.round(4).to_string())
    print("\nunit ratio over the constructed cells")
    print(units.round(4).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
