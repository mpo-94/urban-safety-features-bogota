"""Does the source leave any trace of an unhurt pedestrian? The evidence for the two layers of D69.

    .venv/Scripts/python.exe tools/rastro_del_peaton.py

**Read only.** It reads `actor_vial.csv`, `accidente.csv` and the vehicle table from `data/`, and
the matrix of the run `config.HODGE_MATRIX_SOURCE_RUN` names, and writes nothing.

On a pedestrian edge of the casualty matrix, H_{vehicle, pedestrian} counts only the crashes where
the pedestrian was hurt too, if the source does not record an unhurt pedestrian. Three things are
measured, because D69 rests on each:

1. How many road users of each role `actor_vial` records as unhurt. Unhurt drivers recorded and
   unhurt pedestrians not would place the blindness in the source, not in the pipeline.
2. How many crashes classed as hitting a pedestrian have no pedestrian recorded at all, with one
   vehicle and that vehicle hurt. They are the only possible trace of an unhurt pedestrian, and
   their yearly count says whether they behave like a phenomenon or like a lost record.
3. How far the pedestrian potential would move if every one of them were an unhurt pedestrian:
   the most favourable rebuilding of the pedestrian edges there could be.
"""

from __future__ import annotations

import sys

from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config, hodge  # noqa: E402

SOURCE = config.PROJECT_ROOT / "data" / "data_siniestros_bogota"
HURT_STATES = ("HERIDO", "MUERTO")
PEDESTRIAN_ROLE = config.PEDESTRIAN_ROLE
HITTING_A_PEDESTRIAN = "ATROPELLO"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    actors = pd.read_csv(SOURCE / "actor_vial.csv", usecols=["FORMULARIO", "CONDICION", "ESTADO"],
                         low_memory=False)
    by_role = pd.crosstab(actors.CONDICION.fillna("NO DATA"), actors.ESTADO.fillna("NO DATA"))
    print("1. Road users by role and state, actor_vial:")
    print(by_role.to_string())

    crashes = pd.read_csv(SOURCE / "accidente.csv", usecols=["FORMULARIO", "CLASE_ACC", "ANO_OCURRENCIA_ACC"],
                          low_memory=False)
    hits = crashes[crashes.CLASE_ACC == HITTING_A_PEDESTRIAN]
    with_pedestrian = hits.FORMULARIO.isin(actors.loc[actors.CONDICION == PEDESTRIAN_ROLE, "FORMULARIO"])
    without = hits[~with_pedestrian]

    vehicles = pd.read_csv(config.VEHICLES_PATH, usecols=[config.CRASH_ID_COL, config.VEHICLE_ID_COL, "CLASE"],
                           low_memory=False)
    vehicles = (vehicles[vehicles[config.CRASH_ID_COL].isin(without.FORMULARIO)]
                .dropna(subset=[config.VEHICLE_ID_COL])
                .drop_duplicates([config.CRASH_ID_COL, config.VEHICLE_ID_COL]))
    # The pipeline's own classification, with the pipeline's own fallback.
    vehicles["type"] = (vehicles.CLASE.map(config.normalize_vehicle_type).map(config.VEHICLE_TYPE_MAP)
                        .fillna(config.VEHICLE_TYPE_FALLBACK))
    per_crash = vehicles.groupby(config.CRASH_ID_COL).size()
    one_vehicle = per_crash[per_crash == 1].index
    vehicle_type = vehicles[vehicles[config.CRASH_ID_COL].isin(one_vehicle)].set_index(config.CRASH_ID_COL)["type"]
    hurt = actors[actors.FORMULARIO.isin(one_vehicle) & actors.ESTADO.isin(HURT_STATES)].FORMULARIO
    trace = vehicle_type[vehicle_type.index.isin(hurt)]
    years = without.set_index("FORMULARIO").ANO_OCURRENCIA_ACC.reindex(trace.index)

    print(f"\n2. Crashes hitting a pedestrian: {len(hits)}; with no pedestrian recorded: {len(without)}; "
          f"of those, one vehicle and that vehicle hurt: {len(trace)}")
    print("   by vehicle type:", trace.value_counts().to_dict())
    print("   by year:", years.value_counts().sort_index().to_dict())

    # 3. The pedestrian potential against the car, on the corrected set, with and without the trace.
    run_dir = config.run_directory_holding(hodge.MATRIX_FILES[config.CORRECTED_DATASET],
                                           config.HODGE_MATRIX_SOURCE_RUN)
    long_table = pd.read_parquet(run_dir / config.DATA_SUBDIR / hodge.MATRIX_FILES[config.CORRECTED_DATASET])
    city = sum(hodge.matrices(long_table, config.AFFECTED_PARTIES_COL).values())
    rebuilt = city.copy()
    pedestrian = hodge.INDEX[config.PEDESTRIAN]
    for actor, count in trace.value_counts().items():
        rebuilt[hodge.INDEX[actor], pedestrian] += count
    every = tuple(range(len(hodge.ACTORS)))
    car = hodge.INDEX[config.CAR]
    print(f"\n3. Pedestrian potential against the car, corrected set, parties ({run_dir.name}):")
    for name, matrix in (("as recorded", city), ("with the trace added", rebuilt)):
        result = hodge.fit(hodge.edge_flow(matrix, every, config.HODGE_CONTINUITY))
        value, _ = hodge.contrast(result, pedestrian, car)
        print(f"   {name:<22} {value:.3f}   gradient share {result.gradient_share:.4f}")


if __name__ == "__main__":
    main()
