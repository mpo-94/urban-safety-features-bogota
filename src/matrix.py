"""Aggregation into the inter-mode casualty matrix.

Takes the one-row-per-affected-party table and aggregates it to one row per
scale, territorial unit, year, affected actor type and counterpart actor type,
carrying three counts side by side: affected parties, people injured and people
killed.

The grid is complete. Every unit of the layer, every year of the study period and
every pair of actor types is present, with zero where nothing was observed. The
inherited pipeline simply omitted the combinations it never saw, which makes a
real zero and a missing observation look identical — a distinction that matters
a great deal in a panel.

Every figure is labelled with text. Pictograms belong in documents written
around this output, not in the working figures the pipeline emits.

Run the whole pipeline up to the matrix:

    python -m src.run_pipeline matrix
"""

from __future__ import annotations

import itertools
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # figures are written to disk, never displayed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm

try:  # regular package import
    from src import config
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


def _grid_keys() -> list[str]:
    return [
        config.SCALE_COL,
        config.AREA_CODE_COL,
        config.YEAR_COL,
        config.PARTY_TYPE_COL,
        config.COUNTERPART_TYPE_COL,
    ]


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def build_long_table(
    affected: pd.DataFrame,
    units: pd.DataFrame,
    log: RunLog,
    scale: config.TerritorialScale | None = None,
) -> pd.DataFrame:
    """Aggregate affected parties onto the complete grid."""
    scale = scale or config.active_scale()
    count_columns = list(config.MATRIX_COUNTS.values())

    located = affected[affected[config.AREA_CODE_COL].notna()]
    unlocated = affected[affected[config.AREA_CODE_COL].isna()]
    log.record(
        "restrict to located parties",
        rows_in=len(affected),
        rows_out=len(located),
        changes=[
            (
                -len(unlocated),
                "affected parties whose crash point falls outside every territorial unit, "
                "which have no cell to go to",
            )
        ],
        notes=[
            f"they carry {int(unlocated[config.PERSONS_INJURED_COL].sum()):,} injured and "
            f"{int(unlocated[config.PERSONS_KILLED_COL].sum()):,} killed",
        ],
    )

    observed = (
        located.groupby(
            [config.AREA_CODE_COL, config.YEAR_COL, config.PARTY_TYPE_COL, config.COUNTERPART_TYPE_COL],
            dropna=False,
            observed=True,
        )[count_columns]
        .sum()
        .reset_index()
    )

    # The unit roster comes from the layer, not from the data, so a unit that
    # never appears in a single crash still gets its rows of zeros.
    grid = pd.DataFrame(
        itertools.product(
            units[config.AREA_CODE_COL].tolist(),
            list(config.STUDY_YEARS),
            config.MATRIX_ROW_ORDER,
            config.MATRIX_COLUMN_ORDER,
        ),
        columns=[
            config.AREA_CODE_COL,
            config.YEAR_COL,
            config.PARTY_TYPE_COL,
            config.COUNTERPART_TYPE_COL,
        ],
    )
    grid[config.YEAR_COL] = grid[config.YEAR_COL].astype("Int64")
    observed[config.YEAR_COL] = observed[config.YEAR_COL].astype("Int64")

    long_table = grid.merge(
        observed,
        on=[config.AREA_CODE_COL, config.YEAR_COL, config.PARTY_TYPE_COL, config.COUNTERPART_TYPE_COL],
        how="left",
    )
    unmatched = len(observed) - int(
        observed.merge(
            grid,
            on=[config.AREA_CODE_COL, config.YEAR_COL, config.PARTY_TYPE_COL, config.COUNTERPART_TYPE_COL],
            how="inner",
        ).shape[0]
    )
    if unmatched:
        raise RuntimeError(
            f"{unmatched} observed combination(s) fall outside the declared grid; "
            "the actor type order or the unit roster is incomplete"
        )

    filled = int(long_table[count_columns].isna().all(axis=1).sum())
    long_table[count_columns] = long_table[count_columns].fillna(0).astype(int)

    long_table.insert(0, config.SCALE_COL, scale.label)
    long_table = long_table.merge(
        units[[config.AREA_CODE_COL, config.AREA_NAME_COL]], on=config.AREA_CODE_COL, how="left"
    )
    long_table = long_table[
        _grid_keys() + [config.AREA_NAME_COL] + count_columns
    ].sort_values(_grid_keys(), kind="stable").reset_index(drop=True)

    log.record(
        "aggregate onto the complete grid",
        rows_in=len(located),
        rows_out=len(long_table),
        changes=[
            (len(observed) - len(located), "affected parties collapsed into the cells they share"),
            (filled, "grid cells with no observation, materialised as zero rather than left absent"),
        ],
        notes=[
            f"grid = {len(units)} units x {len(config.STUDY_YEARS)} years x "
            f"{len(config.MATRIX_ROW_ORDER)} actor types x {len(config.MATRIX_COLUMN_ORDER)} counterparts",
            f"scale recorded as {scale.label} on every row",
        ],
    )
    return long_table


def crosstab(long_table: pd.DataFrame, count_name: str, year: int | None = None) -> pd.DataFrame:
    """One count as an actor-by-counterpart table, in the declared order."""
    column = config.MATRIX_COUNTS[count_name]
    subset = long_table if year is None else long_table[long_table[config.YEAR_COL] == year]
    table = subset.pivot_table(
        index=config.PARTY_TYPE_COL,
        columns=config.COUNTERPART_TYPE_COL,
        values=column,
        aggfunc="sum",
        fill_value=0,
    )
    return table.reindex(index=list(config.MATRIX_ROW_ORDER), columns=list(config.MATRIX_COLUMN_ORDER), fill_value=0)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export(long_table: pd.DataFrame, log: RunLog) -> dict[str, Path]:
    """Write the analysis table and every presentation table, and return the paths."""
    data_dir = log.run_dir / config.DATA_SUBDIR
    year_dir = data_dir / config.BY_YEAR_SUBDIR
    year_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    long_path = data_dir / f"{config.ANALYSIS_PREFIX}__matrix_long.csv"
    long_table.to_csv(long_path, index=False, encoding="utf-8")
    long_table.to_parquet(long_path.with_suffix(".parquet"))
    paths["long"] = long_path

    for count_name in config.MATRIX_COUNTS:
        path = data_dir / f"{config.PRESENTATION_PREFIX}__crosstab_{count_name}__all_years.csv"
        crosstab(long_table, count_name).to_csv(path, encoding="utf-8")
        paths[f"crosstab_{count_name}"] = path

        for year in config.STUDY_YEARS:
            year_path = year_dir / f"{config.PRESENTATION_PREFIX}__crosstab_{count_name}__{year}.csv"
            crosstab(long_table, count_name, year).to_csv(year_path, encoding="utf-8")
            paths[f"crosstab_{count_name}_{year}"] = year_path

    log.info(
        "exported 1 analysis table and %d presentation tables to %s/",
        len(paths) - 1,
        config.DATA_SUBDIR,
    )
    return paths


# ---------------------------------------------------------------------------
# Heatmaps
# ---------------------------------------------------------------------------


def _read_crosstab(path: Path) -> pd.DataFrame:
    """Read back an exported table exactly as written, without recomputing it."""
    table = pd.read_csv(path, index_col=0)
    return table.reindex(index=list(config.MATRIX_ROW_ORDER), columns=list(config.MATRIX_COLUMN_ORDER))


def _draw_heatmap(table: pd.DataFrame, title: str, vmin: float, vmax: float, out_path: Path) -> None:
    values = table.to_numpy(dtype=float)
    # Zeros cannot be placed on a logarithmic ramp, and drawing them at the
    # bottom of it would suggest a small value where there is none. They get
    # their own flat colour instead.
    masked = np.ma.masked_where(values <= 0, values)

    cmap = plt.get_cmap(config.HEATMAP_COLORMAP).copy()
    cmap.set_bad(config.HEATMAP_EMPTY_COLOR)
    norm = LogNorm(vmin=max(vmin, 1.0), vmax=max(vmax, 2.0))

    fig, ax = plt.subplots(figsize=(9.5, 6.2))
    image = ax.imshow(masked, cmap=cmap, norm=norm, aspect="auto")

    ax.set_xticks(range(len(table.columns)), table.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(table.index)), table.index)
    ax.set_xlabel("Counterpart")
    ax.set_ylabel("Affected party")
    ax.set_title(title)

    # The numbers are on the cells because a logarithmic ramp shows the order of
    # magnitude well and the exact value badly.
    for row, col in itertools.product(range(values.shape[0]), range(values.shape[1])):
        value = values[row, col]
        if value <= 0:
            colour = "#999999"
        else:
            colour = "white" if norm(value) > 0.55 else "black"
        ax.text(col, row, f"{int(value):,}", ha="center", va="center", fontsize=8, color=colour)

    bar = fig.colorbar(image, ax=ax, shrink=0.85)
    bar.set_label("count (logarithmic scale)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def render_heatmaps(paths: dict[str, Path], log: RunLog) -> int:
    """Draw one heatmap per count and year, plus an aggregate one per count.

    Every figure is drawn from the exported table read back from disk, so what is
    seen and what is analysed are the same numbers by construction.
    """
    written = 0
    for count_name in config.MATRIX_COUNTS:
        figures_dir = log.run_dir / config.FIGURES_SUBDIR / count_name
        figures_dir.mkdir(parents=True, exist_ok=True)

        yearly = {year: _read_crosstab(paths[f"crosstab_{count_name}_{year}"]) for year in config.STUDY_YEARS}

        # One colour scale for all years of this count. Per-year scaling would
        # make two heatmaps look comparable while being drawn to different rulers.
        positives = np.concatenate([t.to_numpy(dtype=float).ravel() for t in yearly.values()])
        positives = positives[positives > 0]
        vmin, vmax = (float(positives.min()), float(positives.max())) if positives.size else (1.0, 2.0)
        log.info(
            "%s: shared colour scale across years spans %.0f to %.0f", count_name, vmin, vmax
        )

        for year, table in yearly.items():
            _draw_heatmap(
                table,
                f"Casualty matrix — {count_name} — {year} ({config.active_scale().label})",
                vmin,
                vmax,
                figures_dir / f"heatmap_{count_name}__{year}.png",
            )
            written += 1

        # The aggregate covers eighteen years at once, so it is not on the same
        # ruler as a single year and gets its own scale.
        aggregate = _read_crosstab(paths[f"crosstab_{count_name}"])
        agg_values = aggregate.to_numpy(dtype=float).ravel()
        agg_positive = agg_values[agg_values > 0]
        _draw_heatmap(
            aggregate,
            f"Casualty matrix — {count_name} — {config.FIRST_YEAR}-{config.LAST_YEAR} "
            f"({config.active_scale().label})",
            float(agg_positive.min()) if agg_positive.size else 1.0,
            float(agg_positive.max()) if agg_positive.size else 2.0,
            figures_dir / f"heatmap_{count_name}__all_years.png",
        )
        written += 1

    log.info("wrote %d heatmaps under %s/", written, config.FIGURES_SUBDIR)
    return written


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(long_table: pd.DataFrame, affected: pd.DataFrame, units: pd.DataFrame, log: RunLog) -> bool:
    """Check the matrix against what entered it, and against its own definition."""
    located = affected[affected[config.AREA_CODE_COL].notna()]
    checks: list[tuple[str, bool, str]] = []

    for name, column in config.MATRIX_COUNTS.items():
        entered = int(located[column].sum())
        in_matrix = int(long_table[column].sum())
        checks.append((f"{name}: matrix total equals what entered", entered == in_matrix,
                       f"{entered:,} in, {in_matrix:,} in matrix"))

    negatives = int((long_table[list(config.MATRIX_COUNTS.values())] < 0).to_numpy().sum())
    checks.append(("no negative cell", negatives == 0, f"{negatives} negative values"))

    persons = long_table[config.PERSONS_INJURED_COL] + long_table[config.PERSONS_KILLED_COL]
    fewer = int((persons < long_table[config.AFFECTED_PARTIES_COL]).sum())
    checks.append(("no cell with fewer people than parties", fewer == 0, f"{fewer} such cells"))

    expected_units = set(units[config.AREA_CODE_COL])
    present_units = set(long_table[config.AREA_CODE_COL])
    checks.append(("every unit of the layer is in the grid", expected_units == present_units,
                   f"{len(present_units)} of {len(expected_units)}"))

    expected_years = set(config.STUDY_YEARS)
    present_years = set(long_table[config.YEAR_COL].dropna().astype(int))
    checks.append(("every year of the study period is in the grid", expected_years == present_years,
                   f"{len(present_years)} of {len(expected_years)}"))

    expected_rows = len(units) * len(config.STUDY_YEARS) * len(config.MATRIX_ROW_ORDER) * len(config.MATRIX_COLUMN_ORDER)
    checks.append(("grid has exactly the declared number of cells", len(long_table) == expected_rows,
                   f"{len(long_table):,} of {expected_rows:,}"))

    width = max(len(name) for name, _, _ in checks)
    lines = [f"{'check'.ljust(width)}  {'result':>8}  detail", f"{'-' * width}  {'-' * 8}  ------"]
    for name, ok, detail in checks:
        lines.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("matrix verification:", "\n".join(lines))

    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("matrix verification FAILED")
    return passed


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def report(long_table: pd.DataFrame, log: RunLog) -> None:
    counts = list(config.MATRIX_COUNTS.values())

    for count_name in config.MATRIX_COUNTS:
        table = crosstab(long_table, count_name)
        rendered = table.to_string()
        total = int(table.to_numpy().sum())
        log.table(f"aggregate matrix — {count_name} (total {total:,}):", rendered)

    # Largest and smallest cells, to judge whether the matrix is plausible.
    aggregate = crosstab(long_table, "parties").stack()
    ordered = aggregate.sort_values(ascending=False)
    lines = ["largest cells:"]
    for (row, col), value in ordered.head(3).items():
        lines.append(f"    {row:<17} harmed by {col:<17} {int(value):>8,}")
    lines.append("smallest cells:")
    for (row, col), value in ordered.tail(3).items():
        lines.append(f"    {row:<17} harmed by {col:<17} {int(value):>8,}")
    log.table("matrix extremes (affected parties):", "\n".join(lines))

    # Pedestrians and bicycles should barely appear as the counterpart: neither
    # imposes lethal risk on others. If they do, the pair is oriented wrongly.
    table = crosstab(long_table, "parties")
    grand_total = int(table.to_numpy().sum())
    lines = [f"{'counterpart':<20}  {'affected parties':>17}  {'share':>7}"]
    lines.append(f"{'-' * 20}  {'-' * 17}  {'-' * 7}")
    for column in config.MATRIX_COLUMN_ORDER:
        value = int(table[column].sum())
        lines.append(f"{column:<20}  {value:>17,}  {100 * value / grand_total:>6.2f}%")
    vulnerable = int(table[config.PEDESTRIAN].sum() + table[config.BICYCLE].sum())
    share = 100 * vulnerable / grand_total
    lines.append("")
    lines.append(f"pedestrian and bicycle as counterpart together: {vulnerable:,} ({share:.2f}%)")
    lines.append(
        "expected to be small: neither mode imposes lethal risk on others, so a large share here "
        "would mean the pair is oriented backwards"
        if share < 15
        else "WARNING: this share is high enough to suspect an orientation problem"
    )
    log.table("counterpart shares (orientation check):", "\n".join(lines))

    per_year = long_table.groupby(config.YEAR_COL)[counts].sum()
    lines = [f"{'year':>6}  {'parties':>10}  {'injured':>10}  {'killed':>8}"]
    lines.append(f"{'-' * 6}  {'-' * 10}  {'-' * 10}  {'-' * 8}")
    for year, row in per_year.iterrows():
        lines.append(
            f"{int(year):>6}  {int(row[config.AFFECTED_PARTIES_COL]):>10,}  "
            f"{int(row[config.PERSONS_INJURED_COL]):>10,}  {int(row[config.PERSONS_KILLED_COL]):>8,}"
        )
    lines.append(f"{'-' * 6}  {'-' * 10}  {'-' * 10}  {'-' * 8}")
    lines.append(
        f"{'total':>6}  {int(per_year[config.AFFECTED_PARTIES_COL].sum()):>10,}  "
        f"{int(per_year[config.PERSONS_INJURED_COL].sum()):>10,}  "
        f"{int(per_year[config.PERSONS_KILLED_COL].sum()):>8,}"
    )
    log.table("people by year, for checking against official figures:", "\n".join(lines))

    # Emptiness of the grid.
    empty = (long_table[counts].sum(axis=1) == 0)
    lines = [
        f"cells in the grid            : {len(long_table):,}",
        f"cells with no observation    : {int(empty.sum()):,} ({100 * empty.mean():.2f}%)",
    ]
    by_unit = long_table.assign(_empty=empty).groupby(
        [config.AREA_CODE_COL, config.AREA_NAME_COL])["_empty"].mean().sort_values(ascending=False)
    lines.append("")
    lines.append("emptiest units:")
    for (code, name), value in by_unit.head(3).items():
        lines.append(f"    {code} {str(name):<22} {100 * value:>6.2f}% empty")
    lines.append("fullest units:")
    for (code, name), value in by_unit.tail(3).items():
        lines.append(f"    {code} {str(name):<22} {100 * value:>6.2f}% empty")
    fully_empty_units = int((by_unit == 1.0).sum())
    lines.append(f"units with no observation at all: {fully_empty_units}")

    by_year = long_table.assign(_empty=empty).groupby(config.YEAR_COL)["_empty"].mean()
    lines.append("")
    lines.append("share of empty cells by year:")
    lines.append("    " + "  ".join(f"{int(y)}:{100 * v:.0f}%" for y, v in by_year.items()))
    fully_empty_years = int((by_year == 1.0).sum())
    lines.append(f"years with no observation at all: {fully_empty_years}")
    log.table("grid emptiness:", "\n".join(lines))


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


def build(affected: pd.DataFrame, units: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    long_table = build_long_table(affected, units, log)
    log.dump(long_table, "06_matrix_long")
    return long_table
