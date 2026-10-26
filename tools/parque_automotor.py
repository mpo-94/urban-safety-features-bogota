"""What the RUNT vehicle registry says about Bogotá, and whether the derived series rebuild from it.

    .venv/Scripts/python.exe tools/parque_automotor.py

**Read only.** It reads `data/incoming/parque automotor/` and writes nothing.

The registry is outside the pipeline (docs/vehicle-fleet-source.md): nothing in `src/` reads it
and no model divides by it. The thesis shows it anyway, in the annex on population and the
vehicle fleet, and every figure of that annex comes from here or from the derived files this
script checks.

Two kinds of output. The **measurements** are counts read off the extract: Bogotá's active fleet
by class and by service, the vehicles registered each year, and the municipalities with the most
registrations. The **check** concerns the four derived files that sit beside the extract. They
are my advisor's, built in `parque_automotor_bogota.ipynb` with a Weibull survival curve, a
motorisation ceiling and four scenarios that add Soacha; none of that has a published source
yet. Rather than take the files as given, this script rebuilds each derived column from the raw
extract with the parameters the notebook declares and reports the largest difference. A
difference of zero says the file is what the notebook says it is; it says nothing about whether
the assumptions are right, which is for the annex to state.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data" / "incoming" / "parque automotor"
EXTRACT = FOLDER / "CRECIMIENTO_DEL_PARQUE_AUTOMOTOR_RUNT2.0_20260810.csv"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BOGOTA = ("BOGOTA D.C.", "BOGOTA")
# The notebook's own parameters, copied from its first cell so the rebuild uses what built the files.
CUT_YEAR = 2026
LIGHT = ("AUTOMOVIL", "CAMIONETA", "CAMPERO")
MOTORCYCLE = ("MOTOCICLETA",)
SURVIVAL = {"light": (22.0, 4.0), "motorcycle": (14.0, 3.0)}  # (median life in years, shape)
SENSITIVITY = {"light": (16, 19, 22, 25, 28), "motorcycle": (10, 12, 14, 16, 18)}  # median lives tried
CEILING_PER_1000 = {"motorcycle": 300.0, "light": 200.0}
SABANA = ("SOACHA", "CHIA", "COTA", "FUNZA", "MOSQUERA", "MADRID", "CAJICA", "ZIPAQUIRA",
          "FACATATIVA", "SIBATE", "LA CALERA", "TOCANCIPA", "TENJO", "GACHANCIPA", "SOPO",
          "EL ROSAL", "BOJACA", "SUBACHOQUE")
SABANA_SHARES = (0.30, 0.50)  # ψ, the share of the rest of the Sabana's pool assigned to Bogotá
SERIES_YEARS = range(2000, CUT_YEAR + 1)
# 1900 is the extract's code for "no registration year"; the notebook drops it.
NO_YEAR = 1900


def read_extract() -> pd.DataFrame:
    """The extract with short column names. A row is a count, not a vehicle."""
    raw = pd.read_csv(EXTRACT, dtype={"FECHA DE REGISTRO": int, "CANTIDAD": int})
    return raw.rename(columns={
        "NOMBRE_DEPARTAMENTO": "department", "NOMBRE_MUNICIPIO": "municipality",
        "NOMBRE_SERVICIO": "service", "ESTADO_DEL_VEHICULO": "state",
        "NOMBRE_DE_LA_CLASE": "vehicle_class", "FECHA DE REGISTRO": "registration_year",
        "CANTIDAD": "vehicles",
    })


def in_bogota(registry: pd.DataFrame) -> pd.Series:
    return (registry.department == BOGOTA[0]) & (registry.municipality == BOGOTA[1])


def bogota_by_class(registry: pd.DataFrame) -> pd.Series:
    """Active vehicles registered in Bogotá, by class, largest first."""
    active = registry[in_bogota(registry) & (registry.state == "ACTIVO")]
    return active.groupby("vehicle_class").vehicles.sum().sort_values(ascending=False)


def bogota_by_service(registry: pd.DataFrame) -> pd.Series:
    """Active vehicles registered in Bogotá, by service, largest first."""
    active = registry[in_bogota(registry) & (registry.state == "ACTIVO")]
    return active.groupby("service").vehicles.sum().sort_values(ascending=False)


def bogota_by_state(registry: pd.DataFrame) -> pd.Series:
    return registry[in_bogota(registry)].groupby("state").vehicles.sum()


def top_municipalities(registry: pd.DataFrame, how_many: int = 10) -> pd.DataFrame:
    """The municipalities with the most vehicles registered, every state and service counted."""
    totals = registry.groupby(["department", "municipality"]).vehicles.sum()
    return totals.sort_values(ascending=False).head(how_many).reset_index()


def cohorts(registry: pd.DataFrame, classes, places=(BOGOTA,)) -> pd.Series:
    """Private, active vehicles of these classes still registered today, by year of registration.

    The notebook's filters: private service only, active state only, the no-year code dropped.
    """
    where = pd.Series(False, index=registry.index)
    for department, municipality in places:
        where |= (registry.department == department) & (registry.municipality == municipality)
    where &= ((registry.service == "PARTICULAR") & (registry.state == "ACTIVO")
              & registry.vehicle_class.isin(classes))
    counts = registry[where].groupby("registration_year").vehicles.sum().sort_index()
    return counts.drop(index=NO_YEAR, errors="ignore")


def weibull_survival(age, median_life: float, shape: float) -> np.ndarray:
    """S(a) = exp[-(a/α)^β] with α chosen so that S(median_life) = 1/2."""
    age = np.clip(np.asarray(age, float), 0, None)
    scale = median_life / np.log(2) ** (1.0 / shape)
    return np.exp(-(age / scale) ** shape)


def stock_series(cohort: pd.Series, years, median_life: float, shape: float):
    """Registered stock, surviving stock and mean surviving age at each year."""
    registered, surviving, mean_age = [], [], []
    born = cohort.index.to_numpy(float)
    count = cohort.to_numpy(float)
    for year in years:
        alive = born <= year
        weight = count[alive] * weibull_survival(year - born[alive], median_life, shape)
        registered.append(count[alive].sum())
        surviving.append(weight.sum())
        mean_age.append((weight * (year - born[alive])).sum() / weight.sum())
    return np.array(registered), np.array(surviving), np.array(mean_age)


def sensitivity(registry: pd.DataFrame) -> pd.DataFrame:
    """Surviving stock at the cut and its mean age, for each median life the notebook tries."""
    rows = []
    for kind, classes in (("light", LIGHT), ("motorcycle", MOTORCYCLE)):
        cohort = cohorts(registry, classes)
        shape = SURVIVAL[kind][1]
        for median_life in SENSITIVITY[kind]:
            _, surviving, mean_age = stock_series(cohort, [CUT_YEAR], median_life, shape)
            rows.append(dict(kind=kind, median_life=median_life, surviving=surviving[0],
                             mean_age=mean_age[0], chosen=median_life == SURVIVAL[kind][0]))
    return pd.DataFrame(rows)


def scenarios(registry: pd.DataFrame, rates: pd.DataFrame) -> pd.DataFrame:
    """The notebook's four ways of adding Soacha, rebuilt: A alone, B plus Soacha, C plus Soacha
    scaled by its retention factor φ, D as C plus ψ of the rest of the Sabana, for each ψ."""
    years = np.array(SERIES_YEARS)
    soacha = (("CUNDINAMARCA", "SOACHA"),)
    rest = tuple(("CUNDINAMARCA", m) for m in SABANA if m != "SOACHA")
    soacha_rates = rates.set_index("municipio").loc["SOACHA"]
    phi = {"motorcycle": soacha_rates.motos_local / soacha_rates.motos,
           "light": soacha_rates.liv_local / soacha_rates.livianos}
    out = pd.DataFrame({"year": years})
    for kind, classes in (("motorcycle", MOTORCYCLE), ("light", LIGHT)):
        survival = SURVIVAL[kind]
        alone = stock_series(cohorts(registry, classes), years, *survival)[1]
        with_soacha = stock_series(cohorts(registry, classes, soacha), years, *survival)[1]
        with_rest = stock_series(cohorts(registry, classes, rest), years, *survival)[1]
        out[f"{kind}_A"] = alone
        out[f"{kind}_B"] = alone + with_soacha
        out[f"{kind}_C"] = alone + phi[kind] * with_soacha
        for psi in SABANA_SHARES:
            out[f"{kind}_D{round(100 * psi)}"] = out[f"{kind}_C"] + psi * with_rest
    out.attrs["phi"] = phi
    return out


def check_derived(registry: pd.DataFrame) -> dict[str, float]:
    """Largest absolute difference between each derived column and its rebuild from the extract."""
    differences = {}
    light, motorcycle = cohorts(registry, LIGHT), cohorts(registry, MOTORCYCLE)

    profile = pd.read_csv(FOLDER / "bogota_perfil_edad.csv").set_index("anio_matricula")
    differences["perfil_edad: liv_runt"] = float((profile.liv_runt - light.reindex(profile.index, fill_value=0)).abs().max())
    differences["perfil_edad: moto_runt"] = float((profile.moto_runt - motorcycle.reindex(profile.index, fill_value=0)).abs().max())
    age = CUT_YEAR - profile.index.to_numpy(float)
    differences["perfil_edad: S_liv"] = float(np.abs(profile.S_liv - weibull_survival(age, *SURVIVAL["light"])).max())
    differences["perfil_edad: S_moto"] = float(np.abs(profile.S_moto - weibull_survival(age, *SURVIVAL["motorcycle"])).max())

    series = pd.read_csv(FOLDER / "bogota_serie_2000_2026.csv")
    years = series.anio.to_numpy()
    for prefix, cohort, survival in (("moto", motorcycle, SURVIVAL["motorcycle"]), ("liv", light, SURVIVAL["light"])):
        registered, surviving, mean_age = stock_series(cohort, years, *survival)
        differences[f"serie: {prefix}_runt_acum"] = float(np.abs(series[f"{prefix}_runt_acum"] - registered).max())
        differences[f"serie: {prefix}_circulante"] = float(np.abs(series[f"{prefix}_circulante"] - surviving).max())
        if prefix == "moto":
            differences["serie: moto_edad_media"] = float(np.abs(series.moto_edad_media - mean_age).max())
            differences["serie: moto_nuevas"] = float(np.abs(series.moto_nuevas - cohort.reindex(years, fill_value=0).to_numpy()).max())

    rates = pd.read_csv(FOLDER / "bogota_tasas_motorizacion.csv")
    rebuilt = []
    for row in rates.itertuples():
        department = BOGOTA[0] if row.municipio == "BOGOTA" else "CUNDINAMARCA"
        place = ((department, row.municipio),)
        rebuilt.append((cohorts(registry, MOTORCYCLE, place).sum(), cohorts(registry, LIGHT, place).sum()))
    rebuilt = np.array(rebuilt, float)
    differences["tasas: motos"] = float(np.abs(rates.motos - rebuilt[:, 0]).max())
    differences["tasas: livianos"] = float(np.abs(rates.livianos - rebuilt[:, 1]).max())
    local = np.minimum(rates.motos, rates.poblacion * CEILING_PER_1000["motorcycle"] / 1000)
    differences["tasas: motos_local"] = float(np.abs(rates.motos_local - local).max())

    delivered = pd.read_csv(FOLDER / "bogota_soacha_escenarios_2000_2026.csv")
    rebuilt = scenarios(registry, rates)
    for prefix, kind in (("moto", "motorcycle"), ("liv", "light")):
        for letter in ("A", "B", "C"):
            differences[f"escenarios: {prefix}_{letter}"] = float(np.abs(delivered[f"{prefix}_{letter}"] - rebuilt[f"{kind}_{letter}"]).max())
        # The notebook names both D scenarios "D", so the file keeps only one of them: which one
        # is read off the difference against each rebuild.
        for psi in SABANA_SHARES:
            tag = f"D{round(100 * psi)}"
            differences[f"escenarios: {prefix}_D vs ψ={psi}"] = float(np.abs(delivered[f"{prefix}_D"] - rebuilt[f"{kind}_{tag}"]).max())
    return differences


def main() -> int:
    registry = read_extract()
    print(f"extract: {len(registry):,} rows, {registry.vehicles.sum():,} vehicles")
    print("\nBogotá by state:", bogota_by_state(registry).to_dict())
    print("\nBogotá, active, by class (twelve largest):")
    print(bogota_by_class(registry).head(12).to_string())
    print("\nBogotá, active, by service:")
    print(bogota_by_service(registry).to_string())
    print("\nMunicipalities with the most vehicles registered:")
    print(top_municipalities(registry).to_string(index=False))
    print("\nDerived files rebuilt from the extract, largest absolute difference:")
    for what, difference in check_derived(registry).items():
        print(f"  {what:32} {difference:.3g}")
    print("\nSurviving stock at the cut, by median life:")
    print(sensitivity(registry).to_string(index=False))
    rates = pd.read_csv(FOLDER / "bogota_tasas_motorizacion.csv")
    rebuilt = scenarios(registry, rates)
    print("\nRetention factor φ of Soacha:", {k: round(float(v), 4) for k, v in rebuilt.attrs["phi"].items()})
    print(rebuilt[rebuilt.year.isin([2000, 2012, 2016, 2024, 2026])].round(0).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
