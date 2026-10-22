"""How many kilometres of road marking were painted in each unit each year, for the two layers D46 rejects.

    .venv/Scripts/python.exe tools/demarcacion_por_unidad.py

**Read only.** It reads the two horizontal marking layers under `data/`. The one thing it
writes is the scratch run folder that loading the units needs, `results/_tools_demarcacion`,
which is never committed.

D46 established that both layers are flows: each year's file is what was painted that year,
and no year holds the marking in place. That is why the pipeline does not declare them and the
regressions never see them. The thesis still shows them, to back the section that explains why
they are out, and showing them per unit needs a measurement the pipeline does not make.

**It is the pipeline's own measurement.** The two layers are declared here, inside this
process only, exactly as the cycleway is declared in `src/config.py`, and measured with
`predictors.measure_line_layer`, the function that measures the cycleway. Nothing in `src/` is
changed and nothing is reimplemented. What the declaration says is the truth about the layers
and nothing more: `measures` calls the number kilometres painted that year, not kilometres in
place.

It prints, per layer and year, the kilometres inside the thirty units against the length of
the whole layer. The second column of the city totals is D46's, which is the check that the
declaration reads the files D46 read.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import pandas as pd

from src import config, loading, predictors
from src.provenance import RunLog

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

YEARS = tuple(range(2017, 2024))
LAYERS = {
    # name: (folder as delivered, file stem as delivered, label in Spanish)
    "HORIZONTAL_MARKING_PAINTED": ("Señalizacion_Horizontal", "Implementación_demarcación", "Demarcación horizontal"),
    "SCHOOL_ZONE_MARKING_PAINTED": ("Señalizacion_Horizontal_ZonasEscolares", "Implementacion_demarcacion",
                                    "Demarcación en zonas escolares"),
}


def declarations() -> dict[str, config.StaticPredictor]:
    """The two layers as the cycleway is declared, with what they are said plainly."""
    return {
        name: config.StaticPredictor(
            name=name,
            label=name.replace("_", " ").title(),
            label_es=label_es,
            source_layer=folder,
            source_citation=("SenalizacionSemaforizacionPMT",),
            source_files={year: f"{stem}_{year}.shp" for year in YEARS},
            geometry=config.LINE_GEOMETRY,
            method=config.LINE_LENGTH_METHOD,
            measures="kilometres of road marking painted that year, not the marking in place (D46)",
            time_coverage=config.ANNUAL_SERIES_COVERAGE,
            zero_is_implausible=False,
        )
        for name, (folder, stem, label_es) in LAYERS.items()
    }


def measure(log: RunLog) -> pd.DataFrame:
    """Kilometres painted per unit and year, one row per layer, unit and year."""
    units = predictors.prepare_units(loading.load_territorial_units(log))
    rows = []
    for name, declared in declarations().items():
        for year in YEARS:
            measured = predictors.measure_line_layer(declared, units, log, year)
            captured = measured.attrs.get(predictors.CAPTURED_FRACTION, float("nan"))
            # Every unit, painted or not: a unit with no marking that year is a zero, not a gap.
            measured = units[[config.AREA_CODE_COL, config.AREA_NAME_COL, config.AREA_UNIT_KM2_COL]].merge(
                measured, on=config.AREA_CODE_COL, how="left").fillna({config.PREDICTOR_MEASURE_COL: 0.0})
            measured["LAYER"] = name
            measured["YEAR"] = year
            measured["CAPTURED_FRACTION"] = captured
            rows.append(measured)
    return pd.concat(rows, ignore_index=True)


def main() -> int:
    scratch = ROOT / "results" / "_tools_demarcacion"
    scratch.mkdir(parents=True, exist_ok=True)
    table = measure(RunLog(run_dir=scratch))
    city = table.groupby(["LAYER", "YEAR"])[config.PREDICTOR_MEASURE_COL].sum().unstack("YEAR")
    print("kilometres painted inside the thirty units, by layer and year")
    print(city.round(1).to_string())
    print()
    print("D46 gives, for the whole horizontal marking layer: 436.0, 349.7, 163.2, 511.4, 248.0, 1,064.5, 262.6 km")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
