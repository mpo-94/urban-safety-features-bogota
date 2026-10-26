"""Are affected persons repeated in the casualty layers, and more so before 2021?

    .venv/Scripts/python.exe tools/duplicados_por_anio.py

**Read only.** It reads the two integrated casualty layers under `data/integrated/` and writes
nothing.

The approved anteproyecto states that the records before 2021 are duplicated and commits to
correcting that duplication first, validated against the 2015-2019 collision total of the
pedestrian antecedent. Nothing in the pipeline or in `docs/` records such a duplication, so this
measures whether the data show one before the question goes to my advisor, who wrote the
sentence.

Three counts per layer and year: rows identical in every field but the object identifier, the
point position included; rows repeating a person key (form, vehicle, condition, sex and age); and
persons present in both the fatality and the injury layer under that key. The person key is
deliberately broad, so its count is a ceiling and not a count of proven duplicates: two
passengers of one bus with the same sex and age share it while being two people.
"""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTEGRATED = ROOT / "data" / "integrated"
PERSON_KEY = ["FORMULARIO", "CODIGO_VEH", "CONDICION", "GENERO", "EDAD"]
FIRST_YEAR_AFTER = 2021

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_layer(name: str) -> gpd.GeoDataFrame:
    layer = gpd.read_parquet(INTEGRATED / f"{name}__2024_updated_extract.parquet")
    # The position enters the identity test as coordinates, rounded to what the source carries.
    layer["X"] = layer.geometry.x.round(7)
    layer["Y"] = layer.geometry.y.round(7)
    return layer


def per_year(layers: dict[str, gpd.GeoDataFrame]) -> pd.DataFrame:
    rows = []
    for name, layer in layers.items():
        fields = layer.drop(columns=["OBJECTID", "geometry"])
        for year, of_year in fields.groupby("ANO_OCURRE"):
            rows.append(dict(layer=name, year=int(year), rows=len(of_year),
                             identical=int(of_year.duplicated().sum()),
                             same_person_key=int(of_year.duplicated(PERSON_KEY).sum())))
    table = pd.DataFrame(rows)
    table["period"] = table.year.map(lambda y: f"before {FIRST_YEAR_AFTER}" if y < FIRST_YEAR_AFTER
                                     else f"{FIRST_YEAR_AFTER} onwards")
    return table


def main() -> int:
    layers = {name: read_layer(name) for name in ("fatalities", "injuries")}
    table = per_year(layers)
    print(table.to_string(index=False))
    summary = table.groupby(["layer", "period"])[["rows", "identical", "same_person_key"]].sum()
    summary["same_person_key_pct"] = (100 * summary.same_person_key / summary.rows).round(3)
    print("\nBy period:")
    print(summary.to_string())
    both = layers["fatalities"].merge(layers["injuries"][PERSON_KEY].drop_duplicates(), on=PERSON_KEY)
    print(f"\nPersons in both layers under the person key: {len(both)} of {len(layers['fatalities'])} deaths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
