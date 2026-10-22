"""Whether the vertical signage stock can be rebuilt sign by sign, with positions, and not only as counts.

    .venv/Scripts/python.exe tools/posiciones_de_la_senalizacion.py [run]

**Read only.** It reads the signage files under `data/` and the long predictor table of a
`predictors` run. The one thing it writes is the scratch run folder that loading the units
needs, `results/_tools_senalizacion`, which is never committed. The default run is the one the
thesis cites.

D47 builds the stock of each unit as the inventory plus the signs installed minus the signs
removed, each movement counted in the unit where its own record falls. That gives counts, and
counts are all a choropleth needs. A map of where the signs stand at the end of the series
needs more: each removal has to take away one particular sign, and each relocation has to move
one. The files carry an `ID` column in the inventory and in every year of movements, so it is
possible in principle. This measures whether it holds in practice, on four questions:

**1. Does each removal find its sign?** Its `ID` among the signs standing at that moment,
which are the inventory and everything installed before, less what was already removed.

**2. Is it the same sign?** The distance between the removal record and the sign it found. A
removal a few metres away is the same post recorded twice; one kilometres away is a reused or
mistyped identifier.

**3. What do relocations and installations do to identifiers?** A relocation should find its
sign and move it; an installation should bring an identifier not already standing.

**4. Does the rebuilt stock give the pipeline's counts back?** Located in the units and
counted, year by year, against the `MEASURE` column of the run. Only if it does is a map of
the rebuilt stock the same thing the variable measures.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import geopandas as gpd
import numpy as np
import pandas as pd

from src import config, loading
from src.provenance import RunLog

DEFAULT_RUN = "run_20260922_010308"
NAME = "VERTICAL_SIGNAGE_DENSITY"
# Below this, a removal and the sign it found are taken as the same post recorded twice.
SAME_POST_M = 30.0

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read(predictor, year: int | None) -> gpd.GeoDataFrame:
    path = config.resolve_source_path(predictor.path_for(year))
    layer = gpd.read_file(path, columns=["ID", predictor.stock_series.action_column])
    layer = layer[layer.geometry.notna() & ~layer.geometry.is_empty]
    layer = layer.explode(index_parts=False).reset_index(drop=True).to_crs(epsg=config.PROJECTED_CRS)
    layer["ID"] = layer["ID"].astype("Int64")
    return layer


def unit_of(points: gpd.GeoDataFrame, units: gpd.GeoDataFrame) -> pd.Series:
    joined = gpd.sjoin(points[["geometry"]], units[[config.AREA_CODE_COL, "geometry"]],
                       how="left", predicate=config.SPATIAL_JOIN_PREDICATE)
    joined = joined[~joined.index.duplicated(keep="first")]
    return joined[config.AREA_CODE_COL].reindex(points.index)


def main() -> int:
    run = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RUN
    predictor = next(p for p in config.STATIC_PREDICTORS if p.name == NAME)
    series = predictor.stock_series
    scratch = ROOT / "results" / "_tools_senalizacion"
    scratch.mkdir(parents=True, exist_ok=True)
    log = RunLog(run_dir=scratch)
    units = loading.load_territorial_units(log).to_crs(epsg=config.PROJECTED_CRS)

    inventory = read(predictor, series.inventory_as_of_year)
    stock = inventory[["ID", "geometry"]].copy()
    duplicated = int(stock["ID"].duplicated(keep=False).sum())
    print(f"inventory as of {series.inventory_as_of_year}: {len(stock)} signs, "
          f"{stock['ID'].isna().sum()} without ID, {duplicated} sharing an ID with another")

    pipeline = pd.read_csv(ROOT / "results" / run / "data" / "analysis__static_predictors_long.csv")
    pipeline = pipeline[pipeline["PREDICTOR"] == NAME].pivot_table(index="AREA_CODE", columns="YEAR",
                                                                    values="MEASURE")

    rows = []
    for year in series.years:
        # A year with no file of movements carries the stock of the year before, as in D47.
        if year in series.intervention_files:
            moves = read(predictor, year)
            action = moves[series.action_column]
            removals = moves[action.isin(series.removes)]
            relocations = moves[action == "REUBICAR"]
            installs = moves[action.isin(series.adds)]
            standing = stock.drop_duplicates("ID", keep="last").set_index("ID")

            # The other way to pair a removal with its sign: the standing sign nearest to it.
            nearest = gpd.sjoin_nearest(removals[["geometry"]], stock[["geometry"]], how="left",
                                        distance_col="nearest_m")
            nearest = nearest[~nearest.index.duplicated(keep="first")]["nearest_m"].to_numpy()
            found = removals["ID"].isin(standing.index)
            distances = np.array([removals.geometry.iloc[i].distance(standing.geometry.loc[k])
                                  for i, k in enumerate(removals["ID"]) if found.iloc[i]])
            moved_found = relocations["ID"].isin(standing.index)
            install_collides = installs["ID"].isin(standing.index)

            # The rebuild: take away the sign each removal found, move each relocation, add the
            # installations. A removal that finds nothing takes nothing away from the map.
            stock = stock[~stock["ID"].isin(removals.loc[found.to_numpy(), "ID"])]
            relocated = relocations[moved_found.to_numpy()]
            stock = stock[~stock["ID"].isin(relocated["ID"])]
            stock = pd.concat([stock, relocated[["ID", "geometry"]], installs[["ID", "geometry"]]],
                              ignore_index=True)
            rows.append({
                "year": year, "removals": len(removals), "found": int(found.sum()),
                "same_post": int((distances <= SAME_POST_M).sum()),
                "median_m": float(np.median(distances)) if len(distances) else np.nan,
                "p95_m": float(np.percentile(distances, 95)) if len(distances) else np.nan,
                "nearest_within_5m": int((nearest <= 5).sum()),
                "nearest_within_30m": int((nearest <= SAME_POST_M).sum()),
                "nearest_median_m": float(np.median(nearest)) if len(nearest) else np.nan,
                "relocations": len(relocations), "relocations_found": int(moved_found.sum()),
                "installs": len(installs), "installs_with_standing_id": int(install_collides.sum()),
            })
        stock = gpd.GeoDataFrame(stock, geometry="geometry", crs=f"EPSG:{config.PROJECTED_CRS}")
        counts = unit_of(stock, units).value_counts()
        expected = pipeline[year] if year in pipeline.columns else None
        if expected is not None:
            difference = counts.reindex(expected.index, fill_value=0) - expected
            rows_for_year = next((r for r in rows if r["year"] == year), None)
            summary = {"stock": len(stock), "in_units": int(counts.sum()),
                       "pipeline": int(expected.sum()),
                       "units_off": int((difference.abs() > 0).sum()),
                       "largest_unit_gap": int(difference.abs().max())}
            if rows_for_year is None:
                rows.append({"year": year, **summary})
            else:
                rows_for_year.update(summary)

    table = pd.DataFrame(rows)
    print()
    print(table.to_string(index=False, float_format=lambda v: f"{v:,.1f}"))
    print()
    removals = table["removals"].sum()
    print(f"removals that find their sign: {table['found'].sum():.0f} of {removals:.0f} "
          f"({table['found'].sum() / removals:.1%}); of those, within {SAME_POST_M:.0f} m: "
          f"{table['same_post'].sum():.0f}")
    print(f"removals with a standing sign within 5 m: {table['nearest_within_5m'].sum():.0f}; "
          f"within {SAME_POST_M:.0f} m: {table['nearest_within_30m'].sum():.0f} of {removals:.0f}")
    last = table.iloc[-1]
    print(f"end of the series, {int(last['year'])}: rebuilt stock {int(last['in_units'])} in the units, "
          f"pipeline {int(last['pipeline'])}; {int(last['units_off'])} units differ, the largest by "
          f"{int(last['largest_unit_gap'])} signs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
