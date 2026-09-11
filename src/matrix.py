"""Aggregation into the inter-mode casualty matrix, and into the master table beside it.

Takes the one-row-per-affected-party table and aggregates it to one row per
scale, territorial unit, year, affected actor type and counterpart actor type,
carrying three counts side by side: affected parties, people injured and people
killed.

The same parties are aggregated a second way, by unit, year and month with no
pair attached. That is the master table, and it answers the question the matrix
cannot: how many events of each kind happened in a place and when. Both come out
of one resolution of parties, which is what keeps them from drifting apart, and
a check compares them per unit and year in all three counts.

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
import matplotlib.patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm

try:  # regular package import
    from src import config, figures
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import figures  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


def _grid_keys() -> list[str]:
    return [
        config.DATASET_COL,
        config.SCALE_COL,
        config.AREA_CODE_COL,
        config.YEAR_COL,
        config.PARTY_TYPE_COL,
        config.COUNTERPART_TYPE_COL,
    ]


def grid_years(years: tuple[int, ...] | None = None) -> list[int]:
    """The years the grid is materialised over.

    The observed dataset spans the whole study period. The corrected one cannot
    include 2007, because that year does not distinguish the two parties of a
    vehicle-vehicle crash, so it is built over a shorter span and the grid has to
    follow — otherwise 2007 would come back as a row of zeros and read as a year
    in which nobody was hurt.
    """
    return list(years) if years is not None else list(config.STUDY_YEARS)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def build_long_table(
    affected: pd.DataFrame,
    units: pd.DataFrame,
    log: RunLog,
    scale: config.TerritorialScale | None = None,
    years: tuple[int, ...] | None = None,
    dataset: str = config.OBSERVED_DATASET,
) -> pd.DataFrame:
    """Aggregate affected parties onto the complete grid."""
    scale = scale or config.active_scale()
    count_columns = list(config.MATRIX_COUNTS.values())
    year_range = grid_years(years)

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
            year_range,
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

    # The dataset label travels in the table itself, not only in the file name, so
    # a model handed the corrected set instead of the observed one is not relying
    # on whoever moved the file to have read its name. See D31.
    long_table.insert(0, config.SCALE_COL, scale.label)
    long_table.insert(0, config.DATASET_COL, dataset)
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
            f"grid = {len(units)} units x {len(year_range)} years x "
            f"{len(config.MATRIX_ROW_ORDER)} actor types x {len(config.MATRIX_COLUMN_ORDER)} counterparts",
            f"scale recorded as {scale.label} on every row",
            f"dataset recorded as {dataset} on every row; "
            f"years {min(year_range)}-{max(year_range)}",
        ],
    )
    return long_table


def build_master_table(
    affected: pd.DataFrame,
    units: pd.DataFrame,
    log: RunLog,
    years: tuple[int, ...] | None = None,
    dataset: str = config.OBSERVED_DATASET,
) -> pd.DataFrame:
    """Aggregate affected parties onto the complete unit-year-month grid.

    The same events as the matrix, cut a different way. The matrix answers who was
    harmed by whom; this answers how many events of each kind happened in a place
    and when, which is a different question and a much smaller table — no pair, so
    30 units x 18 years x 12 months rather than 22,680 cells.

    The grid is complete for the same reason the matrix's is (D10): a unit-month
    with no casualty is an observation of no harm, and it has to be a zero rather
    than a row that is not there.
    """
    label = f" [{dataset}]"
    count_columns = list(config.MATRIX_COUNTS.values())
    year_range = grid_years(years)

    usable = affected[
        affected[config.AREA_CODE_COL].notna() & affected[config.MONTH_COL].notna()
    ]
    unlocated = int(affected[config.AREA_CODE_COL].isna().sum())
    # Undated parties are counted among the located ones only, so the two causes
    # below do not both claim the same row and the balance closes.
    undated = int((affected[config.AREA_CODE_COL].notna() & affected[config.MONTH_COL].isna()).sum())

    observed = (
        usable.groupby([config.AREA_CODE_COL, config.YEAR_COL, config.MONTH_COL], observed=True)[
            count_columns
        ]
        .sum()
        .reset_index()
    )

    grid = pd.DataFrame(
        itertools.product(units[config.AREA_CODE_COL].tolist(), year_range, range(1, 13)),
        columns=[config.AREA_CODE_COL, config.YEAR_COL, config.MONTH_COL],
    )
    for frame in (grid, observed):
        frame[config.YEAR_COL] = frame[config.YEAR_COL].astype("Int64")
        frame[config.MONTH_COL] = frame[config.MONTH_COL].astype("Int64")

    keys = [config.AREA_CODE_COL, config.YEAR_COL, config.MONTH_COL]
    master = grid.merge(observed, on=keys, how="left")
    unmatched = len(observed) - int(observed.merge(grid, on=keys, how="inner").shape[0])
    if unmatched:
        raise RuntimeError(
            f"{unmatched} observed unit-month(s) fall outside the declared grid; "
            "the unit roster or the year range is incomplete"
        )

    filled = int(master[count_columns].isna().all(axis=1).sum())
    master[count_columns] = master[count_columns].fillna(0).astype(int)

    master.insert(0, config.SCALE_COL, config.active_scale().label)
    master.insert(0, config.DATASET_COL, dataset)
    master = master.merge(
        units[[config.AREA_CODE_COL, config.AREA_NAME_COL]], on=config.AREA_CODE_COL, how="left"
    )
    master = master[
        [
            config.DATASET_COL,
            config.SCALE_COL,
            config.AREA_CODE_COL,
            config.AREA_NAME_COL,
            config.YEAR_COL,
            config.MONTH_COL,
        ]
        + count_columns
    ].sort_values(
        [config.DATASET_COL, config.AREA_CODE_COL, config.YEAR_COL, config.MONTH_COL], kind="stable"
    ).reset_index(drop=True)

    causes = [
        (-unlocated, "affected parties whose crash point falls outside every territorial unit (D11)"),
        (-undated, "affected parties whose crash carries no usable date, so no month to sit in"),
        (len(observed) - len(usable), "affected parties collapsed into the unit-months they share"),
        (filled, "unit-months with no casualty, materialised as zero rather than left absent (D10)"),
    ]
    log.record(
        f"aggregate onto the unit-month grid{label}",
        rows_in=len(affected),
        rows_out=len(master),
        changes=[(delta, cause) for delta, cause in causes if delta],
        notes=[
            f"grid = {len(units)} units x {len(year_range)} years x 12 months",
            f"month read from {config.DATE_SOURCE_COL}, which is the only column of the sources "
            f"that carries one: MES_OCURRE is null in every row of both",
            f"dataset recorded as {dataset} on every row; years {min(year_range)}-{max(year_range)}",
        ],
    )
    return master


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


def export(
    long_table: pd.DataFrame,
    log: RunLog,
    years: tuple[int, ...] | None = None,
    suffix: str = "",
) -> dict[str, Path]:
    """Write the analysis table and every presentation table, and return the paths.

    The suffix names the dataset in the file name. It is empty for the observed
    set, which keeps the names it has always had so nothing reading them breaks,
    and set for the corrected one, whose files are new.
    """
    data_dir = log.run_dir / config.DATA_SUBDIR
    year_dir = data_dir / config.BY_YEAR_SUBDIR
    year_dir.mkdir(parents=True, exist_ok=True)
    tag = f"__{suffix}" if suffix else ""
    year_range = grid_years(years)

    paths: dict[str, Path] = {}

    long_path = data_dir / f"{config.ANALYSIS_PREFIX}__matrix_long{tag}.csv"
    long_table.to_csv(long_path, index=False, encoding="utf-8")
    long_table.to_parquet(long_path.with_suffix(".parquet"))
    paths["long"] = long_path

    for count_name in config.MATRIX_COUNTS:
        path = data_dir / f"{config.PRESENTATION_PREFIX}__crosstab_{count_name}__all_years{tag}.csv"
        crosstab(long_table, count_name).to_csv(path, encoding="utf-8")
        paths[f"crosstab_{count_name}"] = path

        for year in year_range:
            year_path = year_dir / f"{config.PRESENTATION_PREFIX}__crosstab_{count_name}__{year}{tag}.csv"
            crosstab(long_table, count_name, year).to_csv(year_path, encoding="utf-8")
            paths[f"crosstab_{count_name}_{year}"] = year_path

    log.info(
        "exported 1 analysis table and %d presentation tables to %s/ (%s)",
        len(paths) - 1,
        config.DATA_SUBDIR,
        suffix or config.OBSERVED_DATASET.lower(),
    )
    return paths


def export_master_table(tables: list[pd.DataFrame], log: RunLog) -> Path:
    """Write the unit-year-month table, every dataset the run built in one file.

    One file rather than one per dataset, unlike the matrices. The matrices keep
    separate files because the observed ones already feed the dashboard under the
    names they have (D31); this table is new, nothing reads it yet, and the
    `DATASET` column is what tells the two apart wherever it is opened. Stacking
    them means a consumer that wants both does not have to know there are two
    files to look for.
    """
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)

    stacked = pd.concat(tables, ignore_index=True).sort_values(
        [config.DATASET_COL, config.AREA_CODE_COL, config.YEAR_COL, config.MONTH_COL],
        kind="stable",
    ).reset_index(drop=True)

    path = data_dir / f"{config.ANALYSIS_PREFIX}__casualties_by_unit_month.csv"
    stacked.to_csv(path, index=False, encoding="utf-8")
    stacked.to_parquet(path.with_suffix(".parquet"))

    log.info(
        "exported the unit-month master table to %s/%s: %d rows over %s",
        config.DATA_SUBDIR,
        path.name,
        len(stacked),
        ", ".join(
            f"{dataset} ({rows:,})"
            for dataset, rows in stacked[config.DATASET_COL].value_counts().sort_index().items()
        ),
    )
    return path


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
            colour = config.HEATMAP_EMPTY_TEXT_COLOR
        else:
            colour = figures.text_color_on(image, value)
        ax.text(col, row, f"{int(value):,}", ha="center", va="center", fontsize=8, color=colour)

    bar = fig.colorbar(image, ax=ax, shrink=0.85)
    bar.set_label("count (logarithmic scale)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def render_heatmaps(
    paths: dict[str, Path],
    log: RunLog,
    years: tuple[int, ...] | None = None,
    suffix: str = "",
) -> int:
    """Draw one heatmap per count and year, plus an aggregate one per count.

    Every figure is drawn from the exported table read back from disk, so what is
    seen and what is analysed are the same numbers by construction.

    The corrected set gets the same figures in the same style, in a directory of
    its own and with the dataset named in every title: a heatmap that has been
    saved out of its folder must still say which of the two it shows.
    """
    written = 0
    year_range = grid_years(years)
    tag = f"__{suffix}" if suffix else ""
    titled = f" [{suffix}]" if suffix else ""
    for count_name in config.MATRIX_COUNTS:
        yearly = {year: _read_crosstab(paths[f"crosstab_{count_name}_{year}"]) for year in year_range}

        # One colour scale for all years of this count. Per-year scaling would
        # make two heatmaps look comparable while being drawn to different rulers.
        positives = np.concatenate([t.to_numpy(dtype=float).ravel() for t in yearly.values()])
        positives = positives[positives > 0]
        vmin, vmax = (float(positives.min()), float(positives.max())) if positives.size else (1.0, 2.0)
        log.info(
            "%s: shared colour scale across years spans %.0f to %.0f", count_name, vmin, vmax
        )

        for year, table in yearly.items():
            directory = figures.count_figure_directory(log.run_dir, count_name, year, suffix)
            _draw_heatmap(
                table,
                f"Casualty matrix — {count_name} — {year} ({config.active_scale().label}){titled}",
                vmin,
                vmax,
                directory / f"heatmap_{count_name}__{year}{tag}.png",
            )
            written += 1

        # The aggregate covers eighteen years at once, so it is not on the same
        # ruler as a single year and gets its own scale.
        aggregate = _read_crosstab(paths[f"crosstab_{count_name}"])
        agg_values = aggregate.to_numpy(dtype=float).ravel()
        agg_positive = agg_values[agg_values > 0]
        _draw_heatmap(
            aggregate,
            f"Casualty matrix — {count_name} — {min(year_range)}-{max(year_range)} "
            f"({config.active_scale().label}){titled}",
            float(agg_positive.min()) if agg_positive.size else 1.0,
            float(agg_positive.max()) if agg_positive.size else 2.0,
            figures.count_figure_directory(log.run_dir, count_name, None, suffix)
            / f"heatmap_{count_name}__all_years{tag}.png",
        )
        written += 1

    log.info("wrote %d heatmaps under %s/", written, config.FIGURES_SUBDIR)
    return written


# ---------------------------------------------------------------------------
# The master table as a figure
# ---------------------------------------------------------------------------

MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def master_pivot(
    master: pd.DataFrame, count_name: str, dataset: str, year: int | None = None
) -> pd.DataFrame:
    """One count as a unit-by-month table, or unit-by-year for the aggregate.

    Rows are the units in code order and columns are the months of the year, which
    is the shape that reads on a page: thirty by twelve, the same proportions as
    the predictors' master table, so the two look like they belong to one study.
    Left as counts with no total attached — the totals are the figure's, computed
    from exactly the cells it draws.
    """
    column = config.MATRIX_COUNTS[count_name]
    subset = master[master[config.DATASET_COL] == dataset]
    across = config.MONTH_COL if year is not None else config.YEAR_COL
    if year is not None:
        subset = subset[subset[config.YEAR_COL] == year]

    table = subset.pivot_table(
        index=[config.AREA_CODE_COL, config.AREA_NAME_COL],
        columns=across,
        values=column,
        aggfunc="sum",
        fill_value=0,
    )
    table.index = [f"{code}  {name}" for code, name in table.index]
    if year is not None:
        table.columns = [MONTH_LABELS[int(month) - 1] for month in table.columns]
    else:
        table.columns = [str(int(value)) for value in table.columns]
    return table


def _draw_master_table(
    table: pd.DataFrame, title: str, notes: list[str], vmin: float, vmax: float, out_path: Path
) -> None:
    """Every unit against every month, printed and shaded, with totals on both sides.

    **The shading covers the body and never the totals.** A row total is an order
    of magnitude above the cells it sums, so putting the two on one ramp would
    spend the whole scale on the totals and leave the body flat. The totals are
    drawn on a neutral ground that belongs to no part of the ramp, and the note
    under the title says so, because a reader cannot see a scale something was
    left out of.

    Inside the body one ramp covers the whole table. Unlike the predictors' master
    table, whose columns are a share and a density and cannot share a scale, every
    cell here is the same count of the same thing.
    """
    body = table.to_numpy(dtype=float)
    rows, columns = body.shape
    row_totals = body.sum(axis=1)
    column_totals = body.sum(axis=0)
    grand_total = body.sum()

    # Zeros cannot sit on a logarithmic ramp, and drawing them at its bottom would
    # suggest a small count where there is none. Flat colour, as in the matrix.
    masked = np.ma.masked_where(body <= 0, body)
    cmap = plt.get_cmap(config.CASUALTY_TABLE_COLORMAP).copy()
    cmap.set_bad(config.HEATMAP_EMPTY_COLOR)
    norm = LogNorm(vmin=max(vmin, 1.0), vmax=max(vmax, 2.0))

    width = config.CASUALTY_TABLE_WIDTH_BASE_IN + config.CASUALTY_TABLE_WIDTH_PER_COLUMN_IN * (columns + 1)
    fig, ax = plt.subplots(figsize=(width, config.CASUALTY_TABLE_HEIGHT_IN))

    # The body is drawn into its own extent so the totals strip can be painted
    # beside it without ever entering the array the ramp is computed from.
    image = ax.imshow(
        masked,
        cmap=cmap,
        norm=norm,
        aspect="auto",
        extent=(-0.5, columns - 0.5, rows - 0.5, -0.5),
    )
    ax.set_xlim(-0.5, columns + 0.5)
    ax.set_ylim(rows + 0.5, -0.5)

    for anchor, span_width, span_height in (
        ((columns - 0.5, -0.5), 1.0, rows + 1.0),  # the total column
        ((-0.5, rows - 0.5), columns + 1.0, 1.0),  # the total row
    ):
        ax.add_patch(
            matplotlib.patches.Rectangle(
                anchor,
                span_width,
                span_height,
                facecolor=config.CASUALTY_TABLE_TOTAL_COLOR,
                edgecolor="none",
                zorder=1,
            )
        )

    font = config.CASUALTY_TABLE_CELL_FONT_PT
    for row, column in itertools.product(range(rows), range(columns)):
        value = body[row, column]
        colour = (
            config.HEATMAP_EMPTY_TEXT_COLOR if value <= 0 else figures.text_color_on(image, value)
        )
        ax.text(column, row, f"{int(value):,}", ha="center", va="center", fontsize=font, color=colour)

    for row in range(rows):
        ax.text(columns, row, f"{int(row_totals[row]):,}", ha="center", va="center",
                fontsize=font, color=config.CASUALTY_TABLE_TOTAL_TEXT_COLOR, fontweight="bold", zorder=2)
    for column in range(columns):
        ax.text(column, rows, f"{int(column_totals[column]):,}", ha="center", va="center",
                fontsize=font, color=config.CASUALTY_TABLE_TOTAL_TEXT_COLOR, fontweight="bold", zorder=2)
    ax.text(columns, rows, f"{int(grand_total):,}", ha="center", va="center",
            fontsize=font + 0.5, color=config.CASUALTY_TABLE_TOTAL_TEXT_COLOR, fontweight="bold", zorder=2)

    ax.set_xticks(
        range(columns + 1),
        list(table.columns) + [config.CASUALTY_TABLE_TOTAL_LABEL],
        fontsize=font + 1,
    )
    ax.xaxis.set_ticks_position("top")
    ax.set_yticks(
        range(rows + 1),
        list(table.index) + [config.CASUALTY_TABLE_TOTAL_LABEL],
        fontsize=font + 1,
    )

    # Separators on the cell boundaries rather than on the centres, so four
    # hundred numbers read as a table instead of as a field of colour.
    ax.set_xticks(np.arange(-0.5, columns + 1, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, rows + 1, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.0)
    ax.tick_params(which="minor", length=0)
    ax.tick_params(which="major", length=0)
    # And a heavier rule where the body stops and the totals begin, which is the
    # one boundary in the figure that means something.
    ax.axvline(columns - 0.5, color=config.FIGURE_TECHNICAL_LABEL_COLOR, linewidth=1.2, zorder=3)
    ax.axhline(rows - 0.5, color=config.FIGURE_TECHNICAL_LABEL_COLOR, linewidth=1.2, zorder=3)

    ax.set_title(title + "\n" + "\n".join(notes), fontsize=9.5, pad=14)

    bar = fig.colorbar(image, ax=ax, shrink=0.4, pad=0.02)
    bar.set_label("count (logarithmic scale, body only)", fontsize=font + 1)
    bar.ax.tick_params(labelsize=font)

    fig.tight_layout()
    fig.savefig(out_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)


def render_master_tables(
    master_path: Path,
    log: RunLog,
    years: tuple[int, ...] | None = None,
    dataset: str = config.OBSERVED_DATASET,
    suffix: str = "",
) -> int:
    """One master table figure per count and year, plus one over the whole span.

    Drawn from the exported table read back from disk, as every figure of this
    pipeline is (D12), so what is seen and what is analysed are the same numbers
    by construction rather than by two computations agreeing.
    """
    master = pd.read_csv(master_path)
    year_range = grid_years(years)
    tag = f"__{suffix}" if suffix else ""
    titled = f" [{suffix}]" if suffix else ""
    scale = config.active_scale()
    written = 0

    for count_name in config.MATRIX_COUNTS:
        yearly = {
            year: master_pivot(master, count_name, dataset, year) for year in year_range
        }

        # One ramp for every year of this count, as the matrix figures already do,
        # so that two years can be compared by looking at them rather than by
        # reading two colour bars against each other.
        positives = np.concatenate([t.to_numpy(dtype=float).ravel() for t in yearly.values()])
        positives = positives[positives > 0]
        vmin, vmax = (float(positives.min()), float(positives.max())) if positives.size else (1.0, 2.0)
        log.info(
            "%s%s: master table ramp shared across years spans %.0f to %.0f",
            count_name,
            titled,
            vmin,
            vmax,
        )

        shared_note = (
            f"Body shaded on a logarithmic ramp from {vmin:,.0f} to {vmax:,.0f}, shared by every "
            f"year of this count so two years can be compared by looking at them."
        )
        totals_note = (
            "Totals are outside the ramp, on a neutral ground: they are an order of magnitude "
            "above the cells they sum and would flatten the body."
        )
        for year, table in yearly.items():
            _draw_master_table(
                table,
                f"Casualties by unit and month — {count_name} — {year} ({scale.label}){titled}",
                [shared_note, totals_note],
                vmin,
                vmax,
                figures.count_figure_directory(log.run_dir, count_name, year, suffix)
                / f"table_{count_name}__{year}{tag}.png",
            )
            written += 1

        # The aggregate carries the years across the top instead of the months,
        # and has eighteen times the counts in a cell, so it gets its own ramp
        # exactly as the aggregate matrix does.
        aggregate = master_pivot(master, count_name, dataset, None)
        values = aggregate.to_numpy(dtype=float).ravel()
        positive = values[values > 0]
        low = float(positive.min()) if positive.size else 1.0
        high = float(positive.max()) if positive.size else 2.0
        _draw_master_table(
            aggregate,
            f"Casualties by unit and year — {count_name} — "
            f"{min(year_range)}-{max(year_range)} ({scale.label}){titled}",
            [
                f"Body shaded on a logarithmic ramp from {low:,.0f} to {high:,.0f}, this figure's "
                f"own: a cell here holds a whole year and is not on the ruler of the yearly tables.",
                totals_note,
            ],
            low,
            high,
            figures.count_figure_directory(log.run_dir, count_name, None, suffix)
            / f"table_{count_name}__all_years{tag}.png",
        )
        written += 1

    log.info("wrote %d master table figures under %s/", written, config.FIGURES_SUBDIR)
    return written


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(
    long_table: pd.DataFrame,
    affected: pd.DataFrame,
    units: pd.DataFrame,
    log: RunLog,
    years: tuple[int, ...] | None = None,
) -> bool:
    """Check the matrix against what entered it, and against its own definition."""
    located = affected[affected[config.AREA_CODE_COL].notna()]
    year_range = grid_years(years)
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

    expected_years = set(year_range)
    present_years = set(long_table[config.YEAR_COL].dropna().astype(int))
    checks.append(("every year of the dataset's span is in the grid", expected_years == present_years,
                   f"{len(present_years)} of {len(expected_years)}"))

    expected_rows = len(units) * len(year_range) * len(config.MATRIX_ROW_ORDER) * len(config.MATRIX_COLUMN_ORDER)
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


def verify_master_table(
    master: pd.DataFrame,
    long_table: pd.DataFrame,
    units: pd.DataFrame,
    log: RunLog,
    years: tuple[int, ...] | None = None,
    dataset: str = config.OBSERVED_DATASET,
    path: Path | None = None,
) -> bool:
    """Check the master table against the matrix of the same events.

    This is the check that matters. Two tables describing one set of events that
    disagree are worse than one table, because whichever a reader opens first
    looks right; and the two are cut differently enough — one by pair, one by
    month — that a defect in either would not show up inside it.

    Summed over the months and over the pairs, the two must agree per unit and
    year, exactly, in all three counts.
    """
    count_columns = list(config.MATRIX_COUNTS.values())
    year_range = grid_years(years)
    keys = [config.AREA_CODE_COL, config.YEAR_COL]
    checks: list[tuple[str, bool, str]] = []

    subset = master[master[config.DATASET_COL] == dataset]

    from_master = subset.groupby(keys, observed=True)[count_columns].sum().sort_index()
    from_matrix = long_table.groupby(keys, observed=True)[count_columns].sum().sort_index()
    same_index = from_master.index.equals(from_matrix.index)
    checks.append((
        "both tables cover the same unit-years",
        same_index,
        f"{len(from_master)} unit-years in the master table, {len(from_matrix)} in the matrix",
    ))
    if same_index:
        for name, column in config.MATRIX_COUNTS.items():
            differing = int((from_master[column] != from_matrix[column]).sum())
            checks.append((
                f"{name}: master table equals the matrix, per unit and year",
                differing == 0,
                f"{differing} unit-year(s) differ; totals {int(from_master[column].sum()):,} "
                f"and {int(from_matrix[column].sum()):,}",
            ))

    expected_rows = len(units) * len(year_range) * 12
    checks.append((
        "grid has exactly the declared number of unit-months",
        len(subset) == expected_rows,
        f"{len(subset):,} of {expected_rows:,} "
        f"({len(units)} units x {len(year_range)} years x 12 months)",
    ))

    months = set(subset[config.MONTH_COL].dropna().astype(int))
    checks.append((
        "every month of the year is in the grid",
        months == set(range(1, 13)),
        f"{len(months)} of 12",
    ))

    negatives = int((subset[count_columns] < 0).to_numpy().sum())
    checks.append(("no negative cell", negatives == 0, f"{negatives} negative values"))

    duplicated = int(subset.duplicated([config.AREA_CODE_COL, config.YEAR_COL, config.MONTH_COL]).sum())
    checks.append((
        "one row per unit, year and month",
        duplicated == 0,
        f"{duplicated} duplicated key(s)",
    ))

    if path is not None:
        # Read back rather than trusted, because the figures are drawn from the
        # file and not from the frame in memory.
        on_disk = pd.read_csv(path)
        on_disk = on_disk[on_disk[config.DATASET_COL] == dataset]
        written = int(on_disk[count_columns].to_numpy().sum())
        held = int(subset[count_columns].to_numpy().sum())
        checks.append((
            "the exported file holds what was built",
            written == held and len(on_disk) == len(subset),
            f"{len(on_disk):,} rows and {written:,} counted on disk, {len(subset):,} and {held:,} in memory",
        ))

    width = max(len(name) for name, _, _ in checks)
    lines = [f"{'check'.ljust(width)}  {'result':>8}  detail", f"{'-' * width}  {'-' * 8}  ------"]
    for name, ok, detail in checks:
        lines.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table(f"master table verification [{dataset}]:", "\n".join(lines))

    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("master table verification FAILED [%s]", dataset)
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


def report_master_table(master: pd.DataFrame, log: RunLog) -> None:
    """What the unit-month cut shows that the matrix cannot.

    The matrix is summed over the year, so a year whose casualties all fall in one
    half of it looks exactly like a year spread evenly. That is the shape this
    table exists to make visible, and January being the thinnest month every year
    is the kind of thing that should be seen once rather than assumed.
    """
    dataset = master[config.DATASET_COL].iloc[0]
    counts = list(config.MATRIX_COUNTS.values())

    by_month = master.groupby(config.MONTH_COL)[counts].sum()
    total = by_month[config.AFFECTED_PARTIES_COL].sum()
    lines = [
        f"{'month':>6}  {'parties':>10}  {'share':>7}  {'injured':>10}  {'killed':>8}",
        f"{'-' * 6}  {'-' * 10}  {'-' * 7}  {'-' * 10}  {'-' * 8}",
    ]
    for month, row in by_month.iterrows():
        parties_here = int(row[config.AFFECTED_PARTIES_COL])
        lines.append(
            f"{MONTH_LABELS[int(month) - 1]:>6}  {parties_here:>10,}  "
            f"{100 * parties_here / total if total else 0:>6.2f}%  "
            f"{int(row[config.PERSONS_INJURED_COL]):>10,}  {int(row[config.PERSONS_KILLED_COL]):>8,}"
        )
    log.table(f"affected parties by month, over the whole span [{dataset}]:", "\n".join(lines))

    empty = master[counts].sum(axis=1) == 0
    lines = [
        f"unit-months in the grid     : {len(master):,}",
        f"unit-months with no casualty: {int(empty.sum()):,} ({100 * empty.mean():.2f}%)",
    ]
    by_unit = master.assign(_empty=empty).groupby(
        [config.AREA_CODE_COL, config.AREA_NAME_COL]
    )["_empty"].mean().sort_values(ascending=False)
    lines.append("")
    lines.append("units with the most empty months:")
    for (code, name), value in by_unit.head(3).items():
        lines.append(f"    {code} {str(name):<22} {100 * value:>6.2f}% of its months empty")
    lines.append("units with the fewest:")
    for (code, name), value in by_unit.tail(3).items():
        lines.append(f"    {code} {str(name):<22} {100 * value:>6.2f}% of its months empty")

    # The range the figure's ramp has to cover, which is what says whether a
    # logarithmic one is doing any work.
    positive = master.loc[master[config.AFFECTED_PARTIES_COL] > 0, config.AFFECTED_PARTIES_COL]
    if len(positive):
        lines.append("")
        lines.append(
            f"affected parties in a unit-month: {int(positive.min())} to {int(positive.max())}, "
            f"median {positive.median():.0f} — a span of "
            f"{positive.max() / max(positive.min(), 1):.0f}x, which is why the body of the "
            f"master table figure is shaded logarithmically"
        )
    log.table(f"unit-month grid [{dataset}]:", "\n".join(lines))


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


def build(
    affected: pd.DataFrame,
    units: pd.DataFrame,
    log: RunLog,
    years: tuple[int, ...] | None = None,
    dataset: str = config.OBSERVED_DATASET,
    dump_name: str = "06_matrix_long",
) -> pd.DataFrame:
    long_table = build_long_table(affected, units, log, years=years, dataset=dataset)
    log.dump(long_table, dump_name)
    return long_table


def build_master(
    affected: pd.DataFrame,
    units: pd.DataFrame,
    log: RunLog,
    years: tuple[int, ...] | None = None,
    dataset: str = config.OBSERVED_DATASET,
    dump_name: str = "06_casualties_by_unit_month",
) -> pd.DataFrame:
    """The same stage as `build`, cut by month instead of by pair.

    Numbered alongside the matrix rather than after it, because the two are one
    stage: both are the aggregation of one resolution of parties.
    """
    master = build_master_table(affected, units, log, years=years, dataset=dataset)
    log.dump(master, dump_name)
    return master
