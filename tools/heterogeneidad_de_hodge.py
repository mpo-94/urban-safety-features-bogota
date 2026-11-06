"""What the correction does to the test of whether units differ, and how precise the city potential is.

    .venv/Scripts/python.exe tools/heterogeneidad_de_hodge.py

**Read only.** It reads the matrix of the run `config.HODGE_MATRIX_SOURCE_RUN` names, calls
`src/hodge.py` rather than repeating it, and writes nothing. It is the evidence for two statements
of D69 and section 33 of the verification report:

1. **The corrected set cannot carry the heterogeneity test alone.** Pooled within each five-year
   window, the between-unit statistic falls well below its degrees of freedom on the corrected set,
   which sampling alone does not do, while on the observed set it stays near one. The correction
   brings each unit toward the city's reference completeness and pulls the potentials together.
2. **The Poisson standard errors overstate the precision.** The city residual is many times its
   Poisson variance; scaled by it, as a quasi-Poisson fit would, the gaps between pedestrian,
   bicycle and motorcycle on the corrected set stop being separations.
"""

from __future__ import annotations

import sys

from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config, hodge  # noqa: E402

WINDOWS = {"2008-2012": range(2008, 2013), "2013-2017": range(2013, 2018), "2018-2022": range(2018, 2023),
           "2023-2024": range(2023, 2025)}
GAPS = (("PEDESTRIAN", "BICYCLE"), ("BICYCLE", "MOTORCYCLE"), ("MOTORCYCLE", "CAR"))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    tables = {}
    for dataset, filename in hodge.MATRIX_FILES.items():
        run_dir = config.run_directory_holding(filename, config.HODGE_MATRIX_SOURCE_RUN)
        tables[dataset] = pd.read_parquet(run_dir / config.DATA_SUBDIR / filename)
    print(f"matrix read from {run_dir.name}\n")

    vehicles = tuple(hodge.INDEX[a] for a in config.HODGE_LAYERS[config.HODGE_HETEROGENEITY_LAYER])
    print("1. Between-unit statistic over its degrees of freedom, vehicle layer, parties:")
    rows = []
    for dataset, long_table in tables.items():
        for window, years in WINDOWS.items():
            cells = hodge.matrices(long_table[long_table[config.YEAR_COL].isin(list(years))],
                                   config.AFFECTED_PARTIES_COL)
            pooled: dict[str, np.ndarray] = {}
            for (unit, _), matrix in cells.items():
                pooled[unit] = pooled.get(unit, 0) + matrix
            flows = {unit: hodge.edge_flow(m, vehicles, config.HODGE_CONTINUITY) for unit, m in pooled.items()}
            test = hodge.heterogeneity_test(flows, dataset, config.AFFECTED_PARTIES_COL,
                                            config.HODGE_HETEROGENEITY_LAYER, window)
            overall = test[test[config.ROAD_USER_TYPE_COL] == "ALL"].iloc[0]
            rows.append({"dataset": dataset, "window": window, "chi2": round(overall.STATISTIC, 1),
                         "df": int(overall.DF), "chi2_over_df": round(overall.STATISTIC / overall.DF, 2),
                         "p_chi2": round(overall.P_VALUE_CHI2, 3), "F": round(overall.F, 2),
                         "p_F": round(overall.P_VALUE_F, 3)})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n2. City gaps between neighbouring types, parties, with errors scaled by the dispersion:")
    for dataset, long_table in tables.items():
        city = sum(hodge.matrices(long_table, config.AFFECTED_PARTIES_COL).values())
        for layer, actors in config.HODGE_LAYERS.items():
            vertices = tuple(hodge.INDEX[a] for a in actors)
            result = hodge.fit(hodge.edge_flow(city, vertices, config.HODGE_CONTINUITY))
            dispersion = result.residual_sum / result.residual_df
            parts = []
            for first, second in GAPS:
                if first not in actors:
                    continue
                value, error = hodge.contrast(result, hodge.INDEX[first], hodge.INDEX[second])
                parts.append(f"{first.lower()}-{second.lower()} {value:.3f} (z {value / (error * np.sqrt(dispersion)):.1f})")
            print(f"   {dataset:<14} {layer:<19} dispersion {dispersion:6.1f}  " + "; ".join(parts))


if __name__ == "__main__":
    main()
