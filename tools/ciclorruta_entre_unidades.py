"""Where Bogota's cycleway is, across the 29 estimating units: the reading of Phase 4's divergence.

    .venv/Scripts/python.exe tools/ciclorruta_entre_unidades.py

**Read only.** It reads the regression design of `config.CONTRAST_DESIGN_RUN` and the modal shares
of the most recent run of the contrast route, and writes nothing.

Phase 4 (D70) finds the cycleway associated with more pedestrian deaths between units, where the
European study found it associated with fewer between cities, while the panel finds its within-unit
effect negative. A between-unit association reads where a thing is as well as what it does, so this
prints the correlation, across the 29 units, of the cycleway averaged over 2012-2024 with the other
features of the place: the arterial road and sidewalk shares, the TransMilenio stations, the
population and the walking share.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config  # noqa: E402

DESIGN = f"{config.ANALYSIS_PREFIX}__regression_data.parquet"
FEATURES = ["ARTERIAL_ROAD_AREA_SHARE", "SIDEWALK_AREA_SHARE", "TRANSMILENIO_STATION_DENSITY",
            config.OFFSET_POPULATION]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    run_dir = config.run_directory_holding(DESIGN, config.CONTRAST_DESIGN_RUN)
    design = pd.read_parquet(run_dir / config.DATA_SUBDIR / DESIGN)
    design = design[design[config.YEAR_COL].isin(config.REGRESSION_YEARS)].drop_duplicates(
        [config.AREA_CODE_COL, config.YEAR_COL])
    means = design.groupby(config.AREA_CODE_COL)[["CYCLEWAY_LENGTH_DENSITY", *FEATURES]].mean()
    shares_file = f"{config.CONTRAST_SHARES_FILENAME}.parquet"
    shares_dir = config.run_directory_holding(shares_file)
    shares = pd.read_parquet(shares_dir / config.DATA_SUBDIR / shares_file)
    walking = shares[shares["SHARE_LEVEL"] == "WINDOW_MEAN"].set_index(config.AREA_CODE_COL)[config.WALKING_SHARE]
    table = means.join(walking, how="inner")
    print(f"{len(table)} units; design from {run_dir.name}, shares from {shares_dir.name}")
    print("correlation of the window-mean cycleway with:")
    for column in [*FEATURES, config.WALKING_SHARE]:
        print(f"   {column:<30} {table['CYCLEWAY_LENGTH_DENSITY'].corr(table[column]):+.2f}")


if __name__ == "__main__":
    main()
