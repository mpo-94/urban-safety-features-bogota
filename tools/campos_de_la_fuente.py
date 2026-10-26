"""What every field of the three casualty files holds, and which of them the pipeline reads.

    .venv/Scripts/python.exe tools/campos_de_la_fuente.py

**Read only.** It reads the two casualty layers and the vehicle table under
`data/data_siniestros_bogota/` and writes nothing.

The final report describes these files field by field and says the study uses only some of
them; the annex on the source lists all of them. A field's name is not evidence of what it holds,
so every field is described by what is measured in it: its type, its share of empty rows, how many
distinct values it takes and the three commonest.

**Which fields the pipeline reads is read off the code, not declared here.** A field counts as
read when `src/config.py` names it in a constant that some other module of `src/` uses, or when a
module of `src/` other than the configuration names it directly. A field that appears only in the
configuration, as `EDAD` does for the population file, is not read from these files. The
geometry is read by every route that places a casualty in a unit.

The pipeline reads the integrated layers, in which the 2024 extract replaces the year 2024 of the
delivered ones; they carry the same fields, which this tool checks.

**`MES_OCURRE` is not empty.** The design record said on 2026-09-11 that it was null in every row
of both layers. Measured on 2026-10-26 it has no empty row in either, delivered or integrated, and
its month name agrees with the month of `FECHA_OCUR` in every row. The month is still read from
the date, and the two say the same; what was wrong was the reason given for it.
"""

import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import config  # noqa: E402

SOURCE = ROOT / "data" / "data_siniestros_bogota"
FILES = {
    "MUERTO": SOURCE / "MUERTO" / "MUERTO.shp",
    "LESIONADO": SOURCE / "LESIONADO" / "LESIONADO.shp",
    "vehiculo": SOURCE / "vehiculo.csv",
}
INTEGRATED = {"MUERTO": config.INTEGRATED_FATALITIES_PATH, "LESIONADO": config.INTEGRATED_INJURIES_PATH}
GEOMETRY = "geometry"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read(name: str) -> pd.DataFrame:
    path = FILES[name]
    if path.suffix == ".csv":
        return pd.read_csv(path, low_memory=False)
    return gpd.read_file(path)


def readers() -> dict[str, list[str]]:
    """For each field name, the modules of src/ that read it, from the code."""
    modules = {p.stem: p.read_text(encoding="utf-8") for p in (ROOT / "src").glob("*.py")}
    others = {name: text for name, text in modules.items() if name != "config"}
    found: dict[str, set[str]] = {}
    # Through a constant: a string-valued name of config used as config.NAME elsewhere.
    for constant, value in vars(config).items():
        if not (constant.isupper() and isinstance(value, str)):
            continue
        for module, text in others.items():
            if re.search(rf"\bconfig\.{constant}\b", text):
                found.setdefault(value, set()).add(module)
    # Directly: the name written as a string literal in a module other than config.
    for module, text in others.items():
        for literal in re.findall(r"[\"']([A-Z_]{3,})[\"']", text):
            found.setdefault(literal, set()).add(module)
    return {field: sorted(mods) for field, mods in found.items()}


def inventory() -> pd.DataFrame:
    """One row per field of the three files, with what is measured in it and who reads it."""
    read_by = readers()
    rows = []
    for name in FILES:
        table = read(name)
        if name in INTEGRATED:
            integrated = gpd.read_parquet(INTEGRATED[name]).columns
            if list(integrated) != list(table.columns):
                raise SystemExit(f"{name}: the integrated layer has other fields than the delivered one")
        for position, field in enumerate(table.columns, start=1):
            if field == GEOMETRY:
                rows.append({"file": name, "rows": len(table), "position": position, "field": field,
                             "dtype": "point", "empty_share": float(table.geometry.is_empty.mean()),
                             "distinct": None, "commonest": [], "read_by": ["loading"]})
                continue
            column = table[field]
            commonest = column.dropna().astype(str).value_counts().index[:3].tolist()
            rows.append({"file": name, "rows": len(table), "position": position, "field": field,
                         "dtype": str(column.dtype), "empty_share": float(column.isna().mean()),
                         "distinct": int(column.nunique()), "commonest": commonest,
                         "read_by": read_by.get(field, [])})
    return pd.DataFrame(rows)


MONTH_NAMES = ("ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
               "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE")


def month_names() -> pd.DataFrame:
    """Whether MES_OCURRE is empty, and whether it agrees with the month of FECHA_OCUR.

    Measured on the delivered layers and on the integrated ones the pipeline reads, the second
    through `loading.read_point_layer`, the pipeline's own reader. MES_OCURRE holds the month as
    a Spanish name, so it is compared as text: converted to a number, every row would come out
    null, which is not the same as the column being empty.
    """
    sys.path.insert(0, str(ROOT))
    from src import loading

    rows = []
    for name, integrated in INTEGRATED.items():
        for kind, layer in (("delivered", read(name)), ("integrated", loading.read_point_layer(integrated))):
            month = pd.to_datetime(layer[config.DATE_SOURCE_COL], errors="coerce").dt.month
            from_date = month.map(lambda m: MONTH_NAMES[int(m) - 1] if pd.notna(m) else None)
            named = layer["MES_OCURRE"].astype("string").str.strip().str.upper()
            rows.append({"layer": name, "kind": kind, "rows": len(layer),
                         "empty": int(layer["MES_OCURRE"].isna().sum()),
                         "agree": int((named == from_date).sum())})
    return pd.DataFrame(rows)


def vehicle_classes() -> pd.Series:
    """Rows of the vehicle table per raw CLASE, the empty ones under NaN, commonest first.

    The raw spelling is kept, because the annex shows what the source writes; the pipeline
    normalises it before looking it up in config.VEHICLE_TYPE_MAP.
    """
    classes = pd.read_csv(FILES["vehiculo"], usecols=["CLASE"], low_memory=False)["CLASE"]
    return classes.value_counts(dropna=False)


def main() -> int:
    table = inventory()
    for name, fields in table.groupby("file", sort=False):
        print(f"\n{name}: {int(fields['rows'].iloc[0]):,} rows, {len(fields)} fields, "
              f"{int(fields['read_by'].map(bool).sum())} read by the pipeline")
        for row in fields.itertuples():
            readers_text = ", ".join(row.read_by) if row.read_by else "-"
            distinct = "" if row.distinct is None else f"{row.distinct:>9,}"
            print(f"  {row.field:16} {row.dtype:15} empty {row.empty_share:6.1%} {distinct:>9}  "
                  f"read by {readers_text:40} {row.commonest}")
    print("\nMES_OCURRE against the month of FECHA_OCUR:")
    for row in month_names().itertuples():
        print(f"  {row.layer:10} {row.kind:10} {row.rows:>9,} rows, {row.empty:>7,} empty, "
              f"{row.agree:>9,} agree ({row.agree / row.rows:.2%})")
    print("\nvehiculo.csv, rows per raw CLASE and the type the pipeline gives it:")
    for value, rows in vehicle_classes().items():
        kind = f"{config.VEHICLE_TYPE_FALLBACK} (empty)" if pd.isna(value) else config.VEHICLE_TYPE_MAP.get(
            config.normalize_vehicle_type(value), f"{config.VEHICLE_TYPE_FALLBACK} (fallback)")
        print(f"  {str(value):20} {rows:>9,}  {kind}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
