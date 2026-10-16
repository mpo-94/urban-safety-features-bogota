"""What the panel can identify, and whether horizontal road marking can join it.

    .venv/Scripts/python.exe tools/variacion_para_el_panel.py [run]

**Read only.** The one thing it writes is the scratch run folder that loading the units
needs, `results/_tools_panel`, which is never committed. Nothing in `src/` imports it. The
default run is the regression run the panel proposal of 2026-10-09 was measured on.

Three measurements, each one a figure that a decision about the panel cites.

**1. How much of each candidate's variance a within estimator gets to use.** A unit fixed
effect removes the unit mean, so what is left to identify a coefficient is the variation of
a unit around its own mean; a year effect removes the year mean on top of that.

The one-way share corrects the figures of the 2026-10-09 proposal, which were 38.5 % for the
cycleway and 0.7 % for the vertical signage. Those put the mean of the per-unit standard
deviations into a variance share, and a mean of standard deviations is not the pooled
within standard deviation: 0.350 against 0.412 for the cycleway, 10.65 against 11.98 for the
signage. The pooled one is the one whose square adds to the between variance to give the
total exactly, which is the check that tells the two apart. The shares are 46.4 % and 0.9 %.

**The two-way share is the one that matters**, because the proposal carries year effects,
and a variable that grows everywhere at once has its growth absorbed by them: 14.8 % for the
cycleway and 0.23 % for the signage, which is close to nothing left to identify it.

**2. Whether a year of horizontal marking is a change in the stock.** D46 rejected the two
marking layers for the cross-sections because they hold no inventory, and a panel weakens
that objection: under a unit effect, an unknown starting stock is a constant per unit and
the model absorbs it, so only the changes are needed. That holds **only if each year's file
is the change in the stock**. If a large share of what is painted in a year lies on top of
what was painted in an earlier year, the files are repainting, and summing them does not
add up to a stock however the base is handled. Measured as the share of each year's length
lying within a tolerance of a line painted in any earlier year of the delivery, with the
cycleway as the control: a stock overlaps its previous years almost entirely, and a flow of
genuinely new marking would barely overlap at all.

The tolerance matters and is reported at three values. Parallel lane lines on one
carriageway are about three metres apart, so a tolerance of a metre or more starts to count
a new line beside an old one as the same line; half a metre does not, but it also misses a
repaint digitised slightly off. The cycleway at the same tolerances says how much of the
loss is digitisation.

**3. Whether painting follows casualties.** D46's second objection was that kilometres
painted respond to observed danger rather than cause it. Papke's test of strict exogeneity
adds next year's value of the regressor to the fixed effects model: if it comes out
associated with this year's outcome, the regressor responds to the outcome. This measures
the descriptive version of that, correlations of two-way demeaned log casualties with
two-way demeaned painting density the same year, the year before and the year after, and
the same for the change in cycleway. It is indicative, not a test: the observations are
unit-years of 29 units, which are not independent, and the band printed assumes they are.

**4. Whether the vertical signage can be carried back to 2012-2014**, run alone with
`--signage`. The layer starts at the 2015 inventory, so a panel that includes it loses four
of its thirteen years. Every inventory record is dated, and counting the ones dated up to a
year gives that year's stock if nothing was ever removed or replaced before 2015. The
measurement prints how far each carried-back year sits from 2015, checks that 2015 comes out
exactly as the pipeline measures it, and gives the removal rate the later files record as the
order of magnitude of the error a carried-back year cannot see.

**5. How much of the recording correction the panel's own effects absorb**, run alone with
`--correction`. The correction differs between the two casualty sets only where ρ adds
parties, and the measurement says pair by pair how large it is, how much of it a year effect
and a unit effect take, and whether what they leave moves with the cycleway, which is what
would make the two sets give different within coefficients.

**6. Whether there are enough deaths for the stratum Phase 4 compares in level**, run alone
with `--deaths`. Zero cells per pair, per unit-year and summed over the window, against the
contract's threshold.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import config  # noqa: E402
import loading  # noqa: E402
import predictors  # noqa: E402
from provenance import RunLog  # noqa: E402

DEFAULT_RUN = "run_20261009_084114"
# The latest run of the `corrected` route, which is the one that writes the persons killed
# per cell of both sets; the regression tables carry affected parties only.
DEFAULT_MATRIX_RUN = "run_20261006_203551"

# The three tolerances of measurement 2, in metres. Declared rather than tuned to what comes
# out: half a metre is below any lane spacing, one metre is the usual digitising error of a
# municipal layer, and two metres is where neighbouring lane lines start to merge.
OVERLAP_TOLERANCES_M: tuple[float, ...] = (0.5, 1.0, 2.0)

MARKING_LAYERS: tuple[tuple[str, str], ...] = (
    ("Horizontal marking", "lines/Señalizacion_Horizontal"),
    ("School-zone marking", "lines/Señalizacion_Horizontal_ZonasEscolares"),
)
CYCLEWAY_LAYER = ("Cycleway (control: a stock)", "lines/ciclo_lines")

# A within deviation this small relative to the variable's own scale is floating-point
# residue, not variation: the ten constant candidates come out at 1e-13 to 1e-19.
CONSTANT_TOLERANCE = 1e-9


def two_way_demean(frame: pd.DataFrame, column: str, max_iterations: int = 200) -> pd.Series:
    """Remove unit and year means from one column, by alternating projections.

    On a balanced panel one pass is exact. The vertical signage covers fewer years than the
    cycleway and a lagged pair loses a year at one end, so the general method is used and
    run until a further pass moves nothing.
    """
    values = frame[column].astype(float).copy()
    for _ in range(max_iterations):
        before = values.copy()
        values = values - values.groupby(frame[config.AREA_CODE_COL]).transform("mean")
        values = values - values.groupby(frame["YEAR"]).transform("mean")
        if float((values - before).abs().max()) < 1e-12:
            break
    return values


def variance_shares(units_by_year: pd.DataFrame, candidates: tuple[str, ...]) -> pd.DataFrame:
    """The within and between standard deviations of every candidate, and what is left."""
    rows = []
    for name in candidates:
        present = units_by_year[[config.AREA_CODE_COL, "YEAR", name]].dropna()
        x = present[name].astype(float)
        unit_mean = x.groupby(present[config.AREA_CODE_COL]).transform("mean")
        within = x - unit_mean
        between_sd = float(x.groupby(present[config.AREA_CODE_COL]).mean().std(ddof=0))
        within_sd = float(within.std(ddof=0))
        total_variance = float(((x - x.mean()) ** 2).mean())
        scale = max(float(x.abs().max()), 1.0)
        varies = within_sd > CONSTANT_TOLERANCE * scale
        two_way = two_way_demean(present, name) if varies else within * 0.0
        units_that_change = int(
            (present.groupby(config.AREA_CODE_COL)[name].agg(lambda s: s.max() - s.min())
             > CONSTANT_TOLERANCE * scale).sum()
        )
        rows.append({
            "variable": name,
            "years": f"{int(present['YEAR'].min())}-{int(present['YEAR'].max())}",
            "within_sd": within_sd,
            "between_sd": between_sd,
            "one_way_share": within_sd ** 2 / (within_sd ** 2 + between_sd ** 2) if varies else 0.0,
            "two_way_share": float((two_way ** 2).mean()) / total_variance if varies else 0.0,
            "units_that_change": units_that_change,
        })
    return pd.DataFrame(rows)


def year_of(path: Path) -> int:
    return int(re.search(r"(20\d{2})", path.name).group(1))


def read_series(relative: str) -> dict[int, gpd.GeoDataFrame]:
    """One layer per year, projected, with its unusable geometries dropped.

    The folder is resolved the way the pipeline resolves it: two of these names carry an ñ
    that this filesystem stores decomposed, and a plain glob finds nothing.
    """
    folder = config.resolve_source_path(config.PREDICTORS_DIR / relative)
    layers = {}
    for path in sorted(folder.glob("*.shp"), key=year_of):
        layer = gpd.read_file(path)
        layer = layer[layer.geometry.notna() & ~layer.geometry.is_empty]
        layers[year_of(path)] = layer[["geometry"]].to_crs(epsg=config.PROJECTED_CRS).reset_index(drop=True)
    return layers


def sample_along(lines: np.ndarray, step: float) -> tuple[np.ndarray, np.ndarray]:
    """Points spaced about `step` metres along every line, and the length each stands for.

    Each line of length L gets n = max(1, round(L / step)) points at the centres of n equal
    pieces, so every point stands for L / n metres and the weights add up to the length of
    the layer exactly. Measuring the overlap on these points is what makes the test cheap:
    a union of thousands of buffered lines per year took longer than this whole tool.
    """
    lengths = shapely.length(lines)
    counts = np.maximum(1, np.round(lengths / step)).astype(int)
    owner = np.repeat(np.arange(len(lines)), counts)
    position = np.concatenate([(np.arange(n) + 0.5) / n for n in counts]) if len(counts) else np.array([])
    points = shapely.line_interpolate_point(lines[owner], position * lengths[owner])
    return points, (lengths / counts)[owner]


def overlap_with_earlier_years(layers: dict[int, gpd.GeoDataFrame], tolerances: tuple[float, ...],
                               step: float = 2.0) -> dict[float, pd.DataFrame]:
    """Share of each year's length lying within each tolerance of a line of any earlier year.

    A point of year t counts as covered when some line of an earlier year passes within the
    tolerance of it; the covered share is the weight of the covered points over the weight of
    all of them. Lines are taken apart into their simple parts first, because interpolation
    along a multi-part line is not defined the same way in every version of the library.
    """
    simple = {year: shapely.get_parts(layer.geometry.to_numpy()) for year, layer in layers.items()}
    tables: dict[float, list[dict]] = {tol: [] for tol in tolerances}
    earlier: list[np.ndarray] = []
    for year in sorted(simple):
        lines = simple[year]
        points, weights = sample_along(lines, step)
        km = float(weights.sum()) / 1000.0
        tree = shapely.STRtree(np.concatenate(earlier)) if earlier else None
        for tol in tolerances:
            if tree is None or len(points) == 0:
                tables[tol].append({"year": year, "km": km, "overlap": np.nan, "new_km": km})
                continue
            found = tree.query_nearest(points, max_distance=tol, return_distance=False, all_matches=False)
            covered = np.zeros(len(points), dtype=bool)
            covered[np.unique(found[0])] = True
            share = float(weights[covered].sum() / weights.sum())
            tables[tol].append({"year": year, "km": km, "overlap": share, "new_km": km * (1.0 - share)})
        earlier.append(lines)
    return {tol: pd.DataFrame(rows) for tol, rows in tables.items()}


def density_by_unit_year(layers: dict[int, gpd.GeoDataFrame], units: gpd.GeoDataFrame) -> pd.DataFrame:
    """Kilometres per square kilometre inside each unit, per year, with zeros kept.

    The cut at unit boundaries is the pipeline's own `split_lines_by_unit`, so a line that
    crosses three units is measured exactly as the cycleway is.
    """
    frames = []
    for year, layer in layers.items():
        lines = layer.copy()
        lines["_LINE"] = np.arange(len(lines))
        fragments = predictors.split_lines_by_unit(lines, units, "_LINE")
        km = fragments.groupby(config.AREA_CODE_COL)[predictors.FRAGMENT_LENGTH_COL].sum()
        table = units[[config.AREA_CODE_COL, config.AREA_UNIT_KM2_COL]].copy()
        table["YEAR"] = year
        table["KM"] = table[config.AREA_CODE_COL].map(km).fillna(0.0)
        frames.append(table)
    flows = pd.concat(frames, ignore_index=True)
    flows["DENSITY"] = flows["KM"] / flows[config.AREA_UNIT_KM2_COL]
    return flows[[config.AREA_CODE_COL, "YEAR", "KM", "DENSITY"]]


def demeaned_correlation(frame: pd.DataFrame, left: str, right: str) -> tuple[float, int]:
    """Correlation of two columns after removing unit and year means from each."""
    sample = frame[[config.AREA_CODE_COL, "YEAR", left, right]].dropna()
    a = two_way_demean(sample, left)
    b = two_way_demean(sample, right)
    if float(a.std()) == 0.0 or float(b.std()) == 0.0:
        return float("nan"), len(sample)
    return float(np.corrcoef(a, b)[0, 1]), len(sample)


def with_shifted(frame: pd.DataFrame, column: str, shift: int, name: str) -> pd.DataFrame:
    """Attach `column` taken `shift` years later (positive) or earlier (negative)."""
    moved = frame[[config.AREA_CODE_COL, "YEAR", column]].copy()
    moved["YEAR"] = moved["YEAR"] - shift
    moved = moved.rename(columns={column: name})
    return frame.merge(moved, on=[config.AREA_CODE_COL, "YEAR"], how="left")


SHIFTS: tuple[tuple[int, str], ...] = (
    (1, "the year after the casualties"),
    (0, "the same year"),
    (-1, "the year before the casualties"),
)


def lead_lag_correlations(frame: pd.DataFrame, regressor: str) -> pd.DataFrame:
    """Two-way demeaned correlations of log casualties with the regressor a year apart.

    One row per shift: the regressor the year after the casualties, which is Papke's lead,
    the same year, and the year before. The band is the naive one, as if the unit-years were
    independent, and is printed beside the figure so nobody reads it as a test.
    """
    rows = []
    for shift, wording in SHIFTS:
        column = f"_{regressor}_{shift}"
        shifted = with_shifted(frame, regressor, shift, column)
        r, n = demeaned_correlation(shifted, "LOG_CASUALTIES", column)
        rows.append({"shift": shift, "wording": wording, "r": r, "n": n,
                     "band": 1.96 / np.sqrt(max(n - 3, 1))})
    return pd.DataFrame(rows)


def print_correlations(label: str, frame: pd.DataFrame, regressor: str) -> None:
    print(f"\n  {label}")
    for row in lead_lag_correlations(frame, regressor).itertuples():
        print(f"    {row.wording:<32} r = {row.r:+.3f}   n = {row.n:>3}   naive 95 % band ±{row.band:.3f}")


def casualties_by_unit_year(table: pd.DataFrame) -> pd.DataFrame:
    """Affected parties summed over the pairs, per unit and year, and their log(1 + count)."""
    casualties = (table.groupby([config.AREA_CODE_COL, "YEAR"])["AFFECTED_PARTIES"].sum()
                  .rename("CASUALTIES").reset_index())
    casualties["LOG_CASUALTIES"] = np.log1p(casualties["CASUALTIES"])
    return casualties


def cycleway_changes(units_by_year: pd.DataFrame) -> pd.DataFrame:
    """The change in cycleway density over the previous year, per unit."""
    cycle = units_by_year[[config.AREA_CODE_COL, "YEAR", "CYCLEWAY_LENGTH_DENSITY"]].copy()
    cycle = cycle.sort_values([config.AREA_CODE_COL, "YEAR"])
    cycle["CYCLEWAY_CHANGE"] = cycle.groupby(config.AREA_CODE_COL)["CYCLEWAY_LENGTH_DENSITY"].diff()
    return cycle


def observations_needed(r: float, z_alpha: float = 1.96, z_power: float = 0.84) -> float:
    """Independent observations needed to tell a correlation `r` from zero.

    Fisher's transformation, at a two-sided 5 % and 80 % power by default. It is what a
    model on the marking flow would need, against the 203 unit-years it would have, which are
    not independent either.
    """
    return ((z_alpha + z_power) / np.arctanh(r)) ** 2 + 3


def signage_missing_years(design: pd.DataFrame, corrected: pd.DataFrame) -> dict:
    """What a panel that includes the vertical signage loses: years, unit-years and parties.

    Read off the design table itself rather than off the declaration, because what matters
    is where the regressions found a value, and the two have to agree.
    """
    units_by_year = design.drop_duplicates([config.AREA_CODE_COL, "YEAR"])
    missing = units_by_year[units_by_year["VERTICAL_SIGNAGE_DENSITY"].isna()]
    years = sorted(int(y) for y in missing["YEAR"].unique())
    shares = {}
    for label, table in (("observed", design), ("rho-corrected", corrected)):
        shares[label] = float(table.loc[table["YEAR"].isin(years), "AFFECTED_PARTIES"].sum()
                              / table["AFFECTED_PARTIES"].sum())
    present = units_by_year.dropna(subset=["VERTICAL_SIGNAGE_DENSITY"])
    return {"years": years, "unit_years": len(missing), "rows_per_pair": len(units_by_year),
            "rows_with": len(units_by_year) - len(missing), "parties_share": shares,
            "first": int(present["YEAR"].min()), "last": int(present["YEAR"].max()),
            "city_mean": present.groupby("YEAR")["VERTICAL_SIGNAGE_DENSITY"].mean()}


def signage_carry_back(units: gpd.GeoDataFrame, log: RunLog, design_units: pd.DataFrame) -> dict:
    """Measurement 4: can the signage be carried back to 2012-2014 from its installation dates?

    The inventory is the stock at the end of 2015 and every record carries the date it was
    installed (D47), so the signs in place at the end of an earlier year are, at first sight,
    the ones dated up to that year. That is a lower bound and the size of its error is what
    decides whether it is usable: a sign removed before 2015 is not in the inventory at all,
    and a sign replaced before 2015 carries the date of its replacement. Neither can be seen
    from 2015. The removals the later files do record give the order of magnitude of the
    first error.
    """
    stock = config.VERTICAL_SIGNAGE_STOCK
    folder = config.resolve_source_path(config.PREDICTORS_DIR / "points/Señalizacion_Vertical")
    inventory = gpd.read_file(next(p for p in folder.glob("*.shp") if p.name.endswith("2016.shp")))
    installed = pd.to_datetime(inventory["FECHA_FASE"]).dt.year

    counts_by_action: dict[str, int] = {}
    removals: list[int] = []
    for year, name in stock.intervention_files.items():
        path = folder / name if (folder / name).exists() else next(folder.glob(f"*{year}.shp"))
        actions = gpd.read_file(path, columns=[stock.action_column])[stock.action_column]
        removals.append(int(actions.isin(stock.removes).sum()))
        for action, count in actions.value_counts().items():
            counts_by_action[action] = counts_by_action.get(action, 0) + int(count)

    area = units.set_index(config.AREA_CODE_COL)[config.AREA_UNIT_KM2_COL]
    rows = []
    for year in (2012, 2013, 2014, stock.inventory_as_of_year):
        counts, _ = _locate(inventory[installed <= year], units, log)
        density = (counts.reindex(area.index).fillna(0) / area).rename("VERTICAL_SIGNAGE_DENSITY")
        rows.append(density.reset_index().assign(YEAR=year))
    carried = pd.concat(rows, ignore_index=True)

    # The year the inventory is as of has to come out as the pipeline's own figure, or the
    # carried-back years are being measured differently from the ones they would join.
    pipeline_2015 = design_units[design_units["YEAR"] == stock.inventory_as_of_year].set_index(
        config.AREA_CODE_COL)["VERTICAL_SIGNAGE_DENSITY"]
    mine_2015 = carried[carried["YEAR"] == stock.inventory_as_of_year].set_index(
        config.AREA_CODE_COL)["VERTICAL_SIGNAGE_DENSITY"]
    gap = float((mine_2015 - pipeline_2015.reindex(mine_2015.index)).abs().max())

    early = carried[carried["YEAR"] < stock.inventory_as_of_year]
    share_after = 1 - (early.groupby("YEAR")["VERTICAL_SIGNAGE_DENSITY"].sum() / mine_2015.sum())
    unit_range = {}
    for year in share_after.index:
        here = early[early["YEAR"] == year].set_index(config.AREA_CODE_COL)["VERTICAL_SIGNAGE_DENSITY"]
        per_unit = 1 - here / mine_2015.reindex(here.index)
        unit_range[int(year)] = (float(per_unit.min()), float(per_unit.max()))

    joined = pd.concat([
        early[[config.AREA_CODE_COL, "YEAR", "VERTICAL_SIGNAGE_DENSITY"]],
        design_units[[config.AREA_CODE_COL, "YEAR", "VERTICAL_SIGNAGE_DENSITY"]].dropna(),
    ], ignore_index=True)
    carried_shares = variance_shares(joined, ("VERTICAL_SIGNAGE_DENSITY",)).iloc[0]

    return {
        "inventory_size": len(inventory),
        "installed_range": (int(installed.min()), int(installed.max())),
        "installed_by_year": installed.value_counts().sort_index(),
        "actions": counts_by_action,
        "removals_per_year": float(np.mean(removals)),
        "removal_share_per_year": float(np.mean(removals)) / len(inventory),
        "check_gap": gap,
        "share_installed_after": share_after,
        "unit_range": unit_range,
        "carried_years": carried_shares["years"],
        "carried_one_way": float(carried_shares["one_way_share"]),
        "carried_two_way": float(carried_shares["two_way_share"]),
    }


def print_signage_carry_back(result: dict) -> None:
    low, high = result["installed_range"]
    print(f"  inventory: {result['inventory_size']:,} signs, installed {low}-{high}")
    installed = result["installed_by_year"]
    for year in range(2010, high + 1):
        print(f"    installed in {year}: {int(installed.get(year, 0)):>6,}"
              f"   in place by the end of {year} if nothing was ever removed: "
              f"{int(installed[installed.index <= year].sum()):>6,}")
    actions = result["actions"]
    print(f"  what the later files record, 2017-2023: "
          + ", ".join(f"{count:,} {action}" for action, count in sorted(actions.items()))
          + f"; {result['removals_per_year']:,.0f} removals a year, "
            f"{result['removal_share_per_year']:.2%} of the 2015 stock")
    print(f"  check: 2015 measured here against the pipeline's 2015, worst unit differs by "
          f"{result['check_gap']:.2e}")
    for year, share in result["share_installed_after"].items():
        low_u, high_u = result["unit_range"][int(year)]
        print(f"    {int(year)}: {share:.1%} of the 2015 stock was installed after it "
              f"(by unit {low_u:.1%} to {high_u:.1%})")
    print(f"  carried back to {result['carried_years']}: within share {result['carried_one_way']:.1%}, "
          f"left with year effects {result['carried_two_way']:.2%}")


def both_sets(observed: pd.DataFrame, corrected: pd.DataFrame) -> pd.DataFrame:
    """The two casualty sets side by side, cell by cell, with the correction as a log ratio.

    Raises if the two do not cover the same cells, because every comparison below assumes
    they do and a silent inner join would compare a subset.
    """
    keys = [config.AREA_CODE_COL, "PAIR", "YEAR"]
    both = observed[keys + ["AFFECTED_PARTIES", "CYCLEWAY_LENGTH_DENSITY"]].merge(
        corrected[keys + ["AFFECTED_PARTIES"]], on=keys, suffixes=("_OBSERVED", "_CORRECTED"))
    if len(both) != len(observed) or len(both) != len(corrected):
        raise ValueError(f"the two sets do not cover the same cells: {len(both)} joined, "
                         f"{len(observed)} observed, {len(corrected)} corrected")
    both["CORRECTION"] = np.log1p(both["AFFECTED_PARTIES_CORRECTED"]) - np.log1p(both["AFFECTED_PARTIES_OBSERVED"])
    return both


def correction_by_pair(both: pd.DataFrame) -> pd.DataFrame:
    """Per pair: parties added, their share of all added, the 2012 ratio, and what effects leave."""
    added = (both.groupby("PAIR")["AFFECTED_PARTIES_CORRECTED"].sum()
             - both.groupby("PAIR")["AFFECTED_PARTIES_OBSERVED"].sum())
    by_year = both.groupby(["PAIR", "YEAR"])[["AFFECTED_PARTIES_OBSERVED", "AFFECTED_PARTIES_CORRECTED"]].sum()
    ratio = (by_year["AFFECTED_PARTIES_CORRECTED"] / by_year["AFFECTED_PARTIES_OBSERVED"]).unstack("YEAR")
    rows = []
    for pair, cells in both.groupby("PAIR"):
        cells = cells.reset_index(drop=True)
        x = cells["CORRECTION"]
        total = float(((x - x.mean()) ** 2).mean())
        row = {"pair": pair, "added": int(added[pair]), "added_share": float(added[pair] / added.sum()),
               "ratio_first": float(ratio.loc[pair].iloc[0]), "ratio_max": float(ratio.loc[pair].max()),
               "variance": total, "after_year": np.nan, "after_both": np.nan, "r_cycleway": np.nan}
        if total > 0.0:
            after_year = x - x.groupby(cells["YEAR"]).transform("mean")
            row["after_year"] = float((after_year ** 2).mean()) / total
            row["after_both"] = float((two_way_demean(cells, "CORRECTION") ** 2).mean()) / total
            row["r_cycleway"] = demeaned_correlation(cells, "CORRECTION", "CYCLEWAY_LENGTH_DENSITY")[0]
        rows.append(row)
    return pd.DataFrame(rows).sort_values("added", ascending=False).reset_index(drop=True)


def pair_unit_means(both: pd.DataFrame, pair: str) -> pd.DataFrame:
    """Mean affected parties per unit, by year, in the two sets, for one pair."""
    block = both[both["PAIR"] == pair]
    return (block.groupby("YEAR")[["AFFECTED_PARTIES_OBSERVED", "AFFECTED_PARTIES_CORRECTED"]].mean()
            .rename(columns={"AFFECTED_PARTIES_OBSERVED": "observed", "AFFECTED_PARTIES_CORRECTED": "corrected"}))


def what_the_correction_leaves(observed: pd.DataFrame, corrected: pd.DataFrame) -> None:
    """Measurement 5: how much of the recording correction a panel's own effects absorb.

    The correction is measured as the log of the corrected count over the observed one, per
    unit, pair and year, with one added to both so a zero does not become infinite. A year
    effect absorbs the part common to the city in a year, and a unit effect the part constant
    in a unit; what neither absorbs is what can make the two sets give different within
    coefficients. Whether it does depends on whether that remainder moves with the variables
    that change, so it is correlated, two-way demeaned, with the cycleway.
    """
    both = both_sets(observed, corrected)
    city = both.groupby("YEAR")[["AFFECTED_PARTIES_OBSERVED", "AFFECTED_PARTIES_CORRECTED"]].sum()
    ratio = city["AFFECTED_PARTIES_CORRECTED"] / city["AFFECTED_PARTIES_OBSERVED"]
    print("  corrected over observed, whole city, all pairs:")
    print("    " + ", ".join(f"{int(y)}: {r:.3f}" for y, r in ratio.items()))

    print(f"\n  {'pair':<26} {'added':>6} {'share':>7} {'first yr':>9} {'total var':>10} "
          f"{'after year':>11} {'after both':>11} {'r cycleway':>11}")
    for row in correction_by_pair(both).itertuples():
        if row.variance == 0.0:
            print(f"  {row.pair:<26} {row.added:>6} {row.added_share:>6.1%} {row.ratio_first:>9.3f}   no correction")
            continue
        print(f"  {row.pair:<26} {row.added:>6} {row.added_share:>6.1%} {row.ratio_first:>9.3f} "
              f"{row.variance:>10.4f} {row.after_year:>10.1%} {row.after_both:>10.1%} {row.r_cycleway:>+11.3f}")


def deaths_table(matrix_run: str) -> pd.DataFrame:
    """Measurement 6: are there enough deaths for the stratum Phase 4 compares in level?

    The contract limits Phase 4's level comparison to deaths, because the source cannot
    rebuild KSI. Whether a deaths stratum exists depends on how many cells are zero, judged by
    the contract's own threshold of fewer than half the cells at zero, per unit and year and
    summed over the window on the estimating units. One row per set and pair.
    """
    data = REPO / "results" / matrix_run / "data"
    excluded = {e.unit for e in config.REGRESSION_EXCLUDED_UNITS}
    years = set(config.REGRESSION_YEARS)
    rows = []
    for label, name in (("observed", "analysis__matrix_long"), ("rho-corrected", "analysis__matrix_long__rho_corrected")):
        matrix = pd.read_parquet(data / f"{name}.parquet")
        matrix = matrix[matrix["YEAR"].isin(years) & ~matrix[config.AREA_CODE_COL].isin(excluded)]
        for pair in config.REGRESSION_PAIRS:
            block = matrix[(matrix["PARTY_TYPE"] == pair.affected) & (matrix["COUNTERPART_TYPE"] == pair.counterpart)]
            unit_years = block.groupby([config.AREA_CODE_COL, "YEAR"])["PERSONS_KILLED"].sum()
            summed = block.groupby(config.AREA_CODE_COL)["PERSONS_KILLED"].sum()
            rows.append({"set": label, "pair": pair.name, "units": int(matrix[config.AREA_CODE_COL].nunique()),
                         "killed": int(block["PERSONS_KILLED"].sum()),
                         "zero_unit_years": float((unit_years == 0).mean()),
                         "zero_units_summed": float((summed == 0).mean())})
    return pd.DataFrame(rows)


def deaths_by_pair(matrix_run: str) -> None:
    table = deaths_table(matrix_run)
    for label, block in table.groupby("set", sort=False):
        print(f"\n  {label}, {block['units'].iloc[0]} units, {min(config.REGRESSION_YEARS)}-"
              f"{max(config.REGRESSION_YEARS)}, from {matrix_run}")
        print(f"  {'pair':<26} {'killed':>7} {'zero unit-years':>16} {'zero units, summed':>19}")
        for row in block.itertuples():
            print(f"  {row.pair:<26} {row.killed:>7} {row.zero_unit_years:>15.0%} {row.zero_units_summed:>18.0%}")
    print(f"\n  the contract's threshold: fewer than {config.REGRESSION_MAX_ZERO_SHARE:.0%} of the cells at zero")


def _locate(points: gpd.GeoDataFrame, units: gpd.GeoDataFrame, log: RunLog) -> tuple[pd.Series, object]:
    """The pipeline's own point location, so a carried-back year counts the way 2015 does."""
    return predictors._locate_points(points, units, "VERTICAL_SIGNAGE_DENSITY", log)


def load_inputs(run: str = DEFAULT_RUN) -> dict:
    """Everything the measurements read, loaded once: the two design tables and the units.

    The units are the estimating ones, so a measurement here never counts Torca where the
    regressions do not. Loading them needs a run log, which writes only to the scratch folder.
    """
    data = REPO / "results" / run / "data"
    if not data.is_dir():
        raise FileNotFoundError(f"no such run: {data}")
    scratch = REPO / "results" / "_tools_panel"
    scratch.mkdir(parents=True, exist_ok=True)
    log = RunLog(scratch)
    logging.getLogger().setLevel(logging.ERROR)

    design = pd.read_parquet(data / "analysis__regression_data.parquet")
    corrected = pd.read_parquet(data / "analysis__regression_data__RHO_CORRECTED.parquet")
    units_by_year = design.drop_duplicates([config.AREA_CODE_COL, "YEAR"])
    estimating = sorted(units_by_year[config.AREA_CODE_COL].unique())
    units = predictors.prepare_units(loading.load_territorial_units(log))
    units = units[units[config.AREA_CODE_COL].isin(estimating)].reset_index(drop=True)
    return {"run": run, "log": log, "design": design, "corrected": corrected,
            "units_by_year": units_by_year, "units": units, "estimating": estimating}


def main() -> int:
    # `--signage`, `--correction` and `--deaths` run one measurement alone: the line overlaps
    # of measurement 2 take minutes and nothing in the others depends on them.
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    try:
        inputs = load_inputs(positional[0] if positional else DEFAULT_RUN)
    except FileNotFoundError as error:
        print(error)
        return 1
    run, log, design, corrected = inputs["run"], inputs["log"], inputs["design"], inputs["corrected"]
    units_by_year, units, estimating = inputs["units_by_year"], inputs["units"], inputs["estimating"]
    candidates = config.REGRESSION_URBAN_CANDIDATES
    print(f"run: {run}   {len(design)} rows, {len(estimating)} units, "
          f"{units_by_year['YEAR'].nunique()} years, {design['PAIR'].nunique()} pairs\n")

    print("=" * 92)
    print("1. WHAT A WITHIN ESTIMATOR GETS TO USE")
    print("=" * 92)
    shares = variance_shares(units_by_year, candidates)
    print(f"  {'variable':<34} {'years':<10} {'within sd':>11} {'between sd':>11} "
          f"{'one-way':>9} {'two-way':>9} {'units':>6}")
    for row in shares.itertuples():
        print(f"  {row.variable:<34} {row.years:<10} {row.within_sd:>11.4g} {row.between_sd:>11.4g} "
              f"{row.one_way_share:>8.1%} {row.two_way_share:>8.2%} {row.units_that_change:>6}")
    print("  one-way: pooled within variance over the total, which corrects the 2026-10-09 proposal.")
    print("  two-way: what is left after unit and year means, over the total variance.")
    print("  units: how many of the units change at all over the years the variable covers.")
    repeated = ", ".join(f"{r.later} repeats {r.earlier}" for r in config.CYCLEWAY_REPEATED_YEARS)
    print(f"  cycleway: {repeated}, so one of its year-on-year changes is zero by construction.")

    if "--deaths" in flags:
        print("\n" + "=" * 92)
        print("6. ARE THERE ENOUGH DEATHS FOR THE STRATUM PHASE 4 COMPARES IN LEVEL?")
        print("=" * 92)
        deaths_by_pair(DEFAULT_MATRIX_RUN)
        return 0

    if "--correction" in flags:
        print("\n" + "=" * 92)
        print("5. HOW MUCH OF THE RECORDING CORRECTION THE PANEL'S OWN EFFECTS ABSORB")
        print("=" * 92)
        what_the_correction_leaves(design, corrected)
        return 0

    if "--signage" in flags:
        print("\n" + "=" * 92)
        print("4. CAN THE SIGNAGE BE CARRIED BACK TO 2012-2014 FROM ITS INSTALLATION DATES?")
        print("=" * 92)
        print_signage_carry_back(signage_carry_back(units, log, units_by_year))
        return 0

    print("\n" + "=" * 92)
    print("2. IS A YEAR OF MARKING A CHANGE IN THE STOCK?  share of each year lying on an earlier year")
    print("=" * 92)
    series = {title: read_series(relative) for title, relative in (*MARKING_LAYERS, CYCLEWAY_LAYER)}
    for title, layers in series.items():
        print(f"\n  {title}   ({min(layers)}-{max(layers)}, {len(layers)} files)")
        tables = overlap_with_earlier_years(layers, OVERLAP_TOLERANCES_M)
        first = tables[OVERLAP_TOLERANCES_M[0]]
        header = "".join(f"  overlap {tol:>3} m" for tol in OVERLAP_TOLERANCES_M)
        print(f"    {'year':>6} {'km':>9}{header}")
        for i, year in enumerate(first["year"]):
            cells = "".join(
                f"  {'':>8}{'—':>3}" if np.isnan(tables[tol]['overlap'].iloc[i])
                else f"  {tables[tol]['overlap'].iloc[i]:>12.1%}"
                for tol in OVERLAP_TOLERANCES_M
            )
            print(f"    {int(year):>6} {first['km'].iloc[i]:>9.1f}{cells}")
        for tol in OVERLAP_TOLERANCES_M:
            t = tables[tol]
            print(f"    at {tol} m: {t['km'].sum():,.1f} km painted over the delivery, of which "
                  f"{t['new_km'].sum():,.1f} km on ground no earlier year had touched "
                  f"({t['new_km'].sum() / t['km'].sum():.1%})")

    print("\n" + "=" * 92)
    print("3. DOES PAINTING FOLLOW CASUALTIES?  two-way demeaned, 29 units")
    print("=" * 92)
    for label, table in (("rho-corrected", corrected), ("observed", design)):
        casualties = casualties_by_unit_year(table)
        print(f"\n  casualties: affected parties summed over the {table['PAIR'].nunique()} pairs, "
              f"{label} dataset, log(1 + count)")
        for title, relative in MARKING_LAYERS:
            flows = density_by_unit_year(series[title], units)
            zero = float((flows["KM"] == 0).mean())
            if label == "rho-corrected":
                left = variance_shares(flows, ("DENSITY",)).iloc[0]
                print(f"\n  {title} as a flow: within share {left.one_way_share:.1%}, "
                      f"left with year effects {left.two_way_share:.1%}, over {len(flows)} unit-years")
            merged = casualties.merge(flows, on=[config.AREA_CODE_COL, "YEAR"], how="inner")
            print_correlations(f"{title} density ({zero:.0%} of unit-years paint nothing)", merged, "DENSITY")
        merged = casualties.merge(cycleway_changes(units_by_year), on=[config.AREA_CODE_COL, "YEAR"], how="inner")
        print_correlations("change in cycleway density over the previous year", merged, "CYCLEWAY_CHANGE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
