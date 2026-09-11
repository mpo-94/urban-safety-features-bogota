"""The interpolated panel in a shape a person can read: wide tables and figures.

The panel `src/interpolation.py` writes is 12,960 rows in a long table, which is
the right shape for joining it to the casualty matrix and to the predictors and
the wrong shape for looking at it. This module writes the second shape.

**Nothing downstream reads any of it.** It is a review artefact: the tables are
for opening in a spreadsheet and the figures are for the one question no check
can answer, which is whether the panel looks like the city it claims to describe.
A check says the arithmetic closed; a figure says walking collapsed in 2020 and
cycling did not, and that is what a reader can agree or disagree with.

The figures are in Spanish and the files that hold data are in English, which is
the split the rest of the pipeline already uses: the exposure choropleths are
labelled in Spanish and written to `figures/exposure/2023/pedestrian/`.

Three groups are drawn here and they describe the panel:

    00_summary  the four modes on one sheet, and where every cell comes from
    01_city     one mode and one kind of day at a time, level and rate
    02_units    the thirty units, as thirty small series and as a heatmap

Three more justify a decision — the pandemic patch, the casualty diagnostic and
the volatility of the per-unit steps — and they are not here yet.

See D40 and D42, and `docs/interpolating-the-exposure.md`.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # figures are written to disk, never displayed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Patch

try:  # regular package import
    from src import config
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# The column the series is read on, for every mode. D39 decided that, and a
# review artefact that quietly showed the other one would be reviewing something
# the study does not use. The pedestrian's full column is in the exported panel
# for anyone who wants it; it is not what these figures draw.
SERIES_COLUMN = config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL
RATE_COLUMN = config.INTERPOLATED_RATE_OVER_15MIN_COL


# ---------------------------------------------------------------------------
# Small shared things
# ---------------------------------------------------------------------------


def _thousands(value: float, _position: int = 0) -> str:
    """A number on an axis, punctuated the way the reader punctuates it.

    Spanish separates thousands with a point. `maps.py` carries the same three
    lines for the colour bars of the choropleths; sharing them would mean a
    figure module importing a map module for a string format.
    """
    return f"{value:,.0f}".replace(",", ".")


def _slug(value: str) -> str:
    """A file-name fragment, spelled the way the exposure figures spell it."""
    return value.lower().replace(" ", "_")


def _stamp(fig, log: RunLog) -> None:
    """The run this figure was drawn from, on the figure itself.

    Every figure quoted in this project carries the run it came from. A figure
    that is going to be pasted into a message loses whatever caption it had, so
    the traceability has to survive inside the image.
    """
    fig.text(0.995, 0.005, log.run_dir.name, ha="right", va="bottom",
             fontsize=6, color="#8a8a8a")


def _modes(table: pd.DataFrame) -> list[str]:
    """The study's road user types, in the order the study declares them."""
    present = set(table[config.ACTOR_TYPE_COL])
    return [actor for actor in config.ROAD_USER_TYPES if actor in present]


def _day_types(table: pd.DataFrame) -> list[str]:
    present = set(table[config.DAY_TYPE_COL])
    return [day for day in config.DAY_TYPES if day in present]


def _variants(table: pd.DataFrame) -> list[str]:
    present = set(table[config.EXPOSURE_VARIANT_COL])
    return [variant for variant in config.EXPOSURE_VARIANTS if variant in present]


def review_variant(table: pd.DataFrame) -> str:
    """The variant a single-variant figure should draw.

    The patched one where it exists, because it is the panel a model would be
    fitted on. A run with no casualty matrix to read has only the unpatched one,
    and then these figures describe that.
    """
    variants = _variants(table)
    return (
        config.PANDEMIC_PATCHED_VARIANT
        if config.PANDEMIC_PATCHED_VARIANT in variants
        else config.INTERPOLATED_VARIANT
    )


def _block(table: pd.DataFrame, variant: str, actor: str, day_type: str) -> pd.DataFrame:
    return table[
        (table[config.EXPOSURE_VARIANT_COL] == variant)
        & (table[config.ACTOR_TYPE_COL] == actor)
        & (table[config.DAY_TYPE_COL] == day_type)
    ]


def _city_series(
    table: pd.DataFrame, variant: str, actor: str, day_type: str, column: str = SERIES_COLUMN
) -> pd.Series:
    """One mode's trips a day over the thirty units, year by year.

    **A rate is not summed.** The city's trips per inhabitant is the city's trips
    over the city's residents; adding up thirty per-unit rates adds thirty ratios
    with thirty different denominators and gives a number that is not a rate of
    anything. The two aggregations differ by a factor of about thirty, so the
    mistake shows, but it shows as a plausible-looking axis and not as an error.
    """
    block = _block(table, variant, actor, day_type)
    if column in (config.INTERPOLATED_RATE_COL, config.INTERPOLATED_RATE_OVER_15MIN_COL):
        level = (
            config.TRIPS_PER_DAY_OF_TYPE_COL
            if column == config.INTERPOLATED_RATE_COL
            else config.TRIPS_PER_DAY_OF_TYPE_OVER_15MIN_COL
        )
        totals = block.groupby(config.YEAR_COL)[[level, config.POPULATION_COL]].sum()
        return (totals[level] / totals[config.POPULATION_COL]).sort_index()
    return block.groupby(config.YEAR_COL)[column].sum().sort_index()


def _provenance_by_year(table: pd.DataFrame, variant: str, actor: str, day_type: str) -> pd.Series:
    """Where each year of a series came from.

    Read off one unit and not averaged: the provenance of a cell is a property of
    the year and the series, identical across the thirty units by construction,
    and a mode that ever stopped being so would be a defect this returns rather
    than hides.
    """
    block = _block(table, variant, actor, day_type)
    per_year = block.groupby(config.YEAR_COL)[config.EXPOSURE_PROVENANCE_COL].agg(
        lambda values: values.iloc[0] if values.nunique() == 1 else "MIXED"
    )
    return per_year.sort_index()


def _shade_held(axis, provenance: pd.Series) -> None:
    """A light band behind the years that carry no behavioural information."""
    held = [year for year, value in provenance.items() if value == config.HELD_EXPOSURE]
    for year in held:
        axis.axvspan(
            year - 0.5, year + 0.5,
            color=config.EXPOSURE_PROVENANCE_COLORS[config.HELD_EXPOSURE],
            alpha=0.13, linewidth=0, zorder=0,
        )


def _draw_series(
    axis,
    table: pd.DataFrame,
    actor: str,
    day_type: str,
    column: str = SERIES_COLUMN,
    scale: float = 1.0,
) -> None:
    """One mode's city series, with both variants and the anchors marked.

    The unpatched panel is the line; the patched one is drawn over it only where
    the two differ, plus the anchor on each side so that the segment joins the
    curve rather than floating. Reading it: where there is one line the two
    constructions agree, and where there are two the difference is the patch.
    """
    variants = _variants(table)
    provenance = _provenance_by_year(table, config.INTERPOLATED_VARIANT, actor, day_type)
    _shade_held(axis, provenance)

    base = _city_series(table, config.INTERPOLATED_VARIANT, actor, day_type, column) / scale
    axis.plot(
        base.index, base.to_numpy(),
        color=config.EXPOSURE_PROVENANCE_COLORS[config.INTERPOLATED_EXPOSURE],
        linewidth=1.6, zorder=2,
        label=config.EXPOSURE_VARIANT_LABELS_ES[config.INTERPOLATED_VARIANT],
    )

    if config.PANDEMIC_PATCHED_VARIANT in variants:
        patched = _city_series(
            table, config.PANDEMIC_PATCHED_VARIANT, actor, day_type, column
        ) / scale
        differs = [year for year in patched.index if not np.isclose(patched[year], base[year])]
        if differs:
            span = [year for year in patched.index if min(differs) - 1 <= year <= max(differs) + 1]
            axis.plot(
                span, patched.loc[span].to_numpy(),
                color=config.EXPOSURE_PROVENANCE_COLORS[config.IMPLIED_FROM_RISK_EXPOSURE],
                linewidth=1.8, zorder=3,
                label=config.EXPOSURE_VARIANT_LABELS_ES[config.PANDEMIC_PATCHED_VARIANT],
            )

    measured = [
        year for year, value in provenance.items() if value == config.MEASURED_EXPOSURE
    ]
    axis.plot(
        measured, base.loc[measured].to_numpy(), linestyle="none", marker="o", markersize=5,
        color=config.EXPOSURE_PROVENANCE_COLORS[config.MEASURED_EXPOSURE], zorder=4,
        label=config.EXPOSURE_PROVENANCE_LABELS_ES[config.MEASURED_EXPOSURE],
    )

    axis.set_ylim(bottom=0)
    axis.set_xlim(int(base.index.min()), int(base.index.max()))
    # A year is an integer and a tick reading 2007,5 is a year that does not
    # exist. Every three years lands on the survey years of the series.
    axis.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(3))
    axis.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{int(value)}"))
    axis.yaxis.set_major_formatter(plt.FuncFormatter(_thousands))
    axis.grid(True, axis="y", color="#e4e4e4", linewidth=0.6, zorder=0)
    axis.set_axisbelow(True)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)


# ---------------------------------------------------------------------------
# The wide tables
# ---------------------------------------------------------------------------


def wide_tables(table: pd.DataFrame, log: RunLog) -> dict[str, Path]:
    """One file per mode and kind of day: thirty units down, eighteen years across.

    Both variants in the same file, under a column that names them, because the
    question these are opened with is usually "what does the patch do to this
    unit" and two files would have to be put side by side to answer it.

    Two files each. The level is trips a day, which is what a model reads; the
    index is the same series against the first year that measured it, which is
    the only way thirty units of very different sizes can be compared by eye.
    """
    directory = log.run_dir / config.REVIEW_SUBDIR
    directory.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    for actor in _modes(table):
        for day_type in _day_types(table):
            rows_level: list[pd.DataFrame] = []
            rows_index: list[pd.DataFrame] = []
            for variant in _variants(table):
                block = _block(table, variant, actor, day_type)
                wide = block.pivot_table(
                    index=[config.AREA_CODE_COL, config.AREA_NAME_COL],
                    columns=config.YEAR_COL,
                    values=SERIES_COLUMN,
                )
                # The base is the unit's own first measured year, so the index
                # says what happened to that unit rather than what happened to
                # the city it sits in.
                provenance = _provenance_by_year(table, variant, actor, day_type)
                anchors = [
                    year for year, value in provenance.items()
                    if value == config.MEASURED_EXPOSURE
                ]
                base = wide[anchors[0]] if anchors else wide[wide.columns[0]]
                indexed = wide.div(base, axis=0) * 100

                for frame, target in ((wide, rows_level), (indexed, rows_index)):
                    out = frame.reset_index()
                    out.insert(2, config.EXPOSURE_VARIANT_COL, variant)
                    target.append(out)

            for kind, frames in (("level", rows_level), ("index", rows_index)):
                path = directory / f"wide__{_slug(actor)}_{_slug(day_type)}_{kind}.csv"
                pd.concat(frames, ignore_index=True).to_csv(
                    path, index=False, encoding="utf-8", float_format="%.3f"
                )
                paths[path.stem] = path

    # And the provenance of every series, which is four columns and says what the
    # eighteen columns of every table above are made of.
    provenance_rows = [
        {
            config.ACTOR_TYPE_COL: actor,
            config.DAY_TYPE_COL: day_type,
            config.EXPOSURE_VARIANT_COL: variant,
            config.YEAR_COL: year,
            config.EXPOSURE_PROVENANCE_COL: value,
        }
        for variant in _variants(table)
        for actor in _modes(table)
        for day_type in _day_types(table)
        for year, value in _provenance_by_year(table, variant, actor, day_type).items()
    ]
    path = directory / "wide__provenance.csv"
    pd.DataFrame(provenance_rows).to_csv(path, index=False, encoding="utf-8")
    paths[path.stem] = path

    log.info(
        "wrote %d wide table(s) for reading under %s/, one per mode and kind of day",
        len(paths),
        config.REVIEW_SUBDIR,
    )
    return paths


# ---------------------------------------------------------------------------
# 00_summary
# ---------------------------------------------------------------------------


def _summary_sheet(table: pd.DataFrame, path: Path, log: RunLog) -> None:
    """The four modes on one sheet, on the kind of day the models take."""
    day_type = config.PANDEMIC_PATCH_DAY_TYPE
    modes = _modes(table)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for axis, actor in zip(axes.ravel(), modes):
        _draw_series(axis, table, actor, day_type, scale=1000.0)
        axis.set_title(config.ROAD_USER_LABELS_ES[actor], fontsize=10)
        axis.set_ylabel("miles de viajes al día", fontsize=8)
        axis.tick_params(labelsize=8)
    for axis in axes.ravel()[len(modes):]:
        axis.set_visible(False)

    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    handles.append(Patch(
        facecolor=config.EXPOSURE_PROVENANCE_COLORS[config.HELD_EXPOSURE], alpha=0.13,
        label=f"{config.EXPOSURE_PROVENANCE_LABELS_ES[config.HELD_EXPOSURE]} "
              "(la tasa no se mueve)",
    ))
    labels.append(handles[-1].get_label())
    fig.legend(handles, labels, loc="lower center", ncol=len(handles), fontsize=8, frameon=False)

    fig.suptitle(
        "La exposición del estudio en las 30 UPL, "
        f"{config.DAY_TYPE_LABELS_ES[day_type]}\n"
        "los puntos son los años de encuesta; la caminata es la de 15 minutos o más (D39)",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.92))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def _provenance_sheet(table: pd.DataFrame, path: Path, log: RunLog) -> None:
    """Where every cell of the panel comes from, in one picture.

    One strip per kind of day, modes down and years across. It is the figure that
    stops eighteen constructed years being read as eighteen observations, and it
    is the first one to look at: everything else in this folder is a series drawn
    on top of these cells.
    """
    variant = review_variant(table)
    modes = _modes(table)
    day_types = _day_types(table)
    years = sorted(table[config.YEAR_COL].unique())
    order = list(config.EXPOSURE_PROVENANCES)
    colours = [config.EXPOSURE_PROVENANCE_COLORS[value] for value in order]

    fig, axes = plt.subplots(
        len(day_types), 1, figsize=(11, 1.6 + 2.1 * len(day_types)), squeeze=False
    )
    for axis, day_type in zip(axes.ravel(), day_types):
        grid = np.full((len(modes), len(years)), np.nan)
        for row, actor in enumerate(modes):
            provenance = _provenance_by_year(table, variant, actor, day_type)
            for column, year in enumerate(years):
                if year in provenance.index:
                    grid[row, column] = order.index(provenance[year])
        axis.imshow(
            grid, aspect="auto", cmap=matplotlib.colors.ListedColormap(colours),
            vmin=-0.5, vmax=len(order) - 0.5, interpolation="nearest",
        )
        axis.set_yticks(range(len(modes)))
        axis.set_yticklabels([config.ROAD_USER_LABELS_ES[actor] for actor in modes], fontsize=8)
        axis.set_xticks(range(len(years)))
        axis.set_xticklabels([str(year) for year in years], fontsize=7, rotation=90)
        axis.set_title(config.DAY_TYPE_LABELS_ES[day_type].capitalize(), fontsize=9, loc="left")
        axis.tick_params(length=0)
        for spine in axis.spines.values():
            spine.set_visible(False)

    fig.legend(
        handles=[
            Patch(facecolor=config.EXPOSURE_PROVENANCE_COLORS[value],
                  label=config.EXPOSURE_PROVENANCE_LABELS_ES[value])
            for value in order
        ],
        loc="lower center", ncol=len(order), fontsize=8, frameon=False,
    )
    fig.suptitle(
        f"De dónde viene cada celda del panel — variante {variant}\n"
        "cada columna es un año y cada fila un modo; la procedencia es igual en las 30 unidades",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 0.90))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 01_city
# ---------------------------------------------------------------------------


def _city_figure(table: pd.DataFrame, actor: str, day_type: str, path: Path, log: RunLog) -> None:
    """One mode and one kind of day: the level above, the rate below.

    The two panels are the decision D40 took, drawn. What is interpolated is the
    rate — the bottom panel, which is flat wherever the exposure is held and
    straight in logarithm between anchors — and the level above it is that rate
    times a population that moves every year. A reader who wonders why a held
    block is not flat finds the answer by looking down.
    """
    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(9, 6.4), sharex=True, gridspec_kw={"height_ratios": (2, 1)}
    )
    _draw_series(top, table, actor, day_type, scale=1000.0)
    top.set_ylabel("miles de viajes al día", fontsize=9)
    _draw_series(bottom, table, actor, day_type, column=RATE_COLUMN)
    bottom.set_ylabel("viajes por habitante", fontsize=9)
    bottom.yaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{value:.2f}".replace(".", ",")))
    bottom.set_xlabel("año", fontsize=9)
    for axis in (top, bottom):
        axis.tick_params(labelsize=8)

    handles, labels = top.get_legend_handles_labels()
    top.legend(handles, labels, fontsize=8, frameon=False, loc="best")
    fig.suptitle(
        f"{config.ROAD_USER_LABELS_ES[actor]} — {config.DAY_TYPE_LABELS_ES[day_type]}, "
        "30 UPL\narriba el nivel, abajo la tasa que es lo que en realidad se interpola",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 02_units
# ---------------------------------------------------------------------------


def _unit_series_sheet(
    table: pd.DataFrame, actor: str, day_type: str, path: Path, log: RunLog
) -> None:
    """Thirty small series on one sheet, each against its own first measured year.

    Indexed rather than levelled, because Kennedy makes forty times the walking
    trips Torca does and a shared axis of levels would show one line and
    twenty-nine flat ones. What the sheet is for is the shape: a unit whose
    trajectory does something no city does is visible here and nowhere else.
    """
    units = (
        table[[config.AREA_CODE_COL, config.AREA_NAME_COL]]
        .drop_duplicates()
        .sort_values(config.AREA_CODE_COL)
    )
    provenance = _provenance_by_year(table, config.INTERPOLATED_VARIANT, actor, day_type)
    anchors = [year for year, value in provenance.items() if value == config.MEASURED_EXPOSURE]
    base_year = anchors[0] if anchors else provenance.index[0]

    columns = 6
    rows = int(np.ceil(len(units) / columns))
    fig, axes = plt.subplots(rows, columns, figsize=(2.2 * columns, 1.7 * rows), sharex=True, sharey=True)
    variants = _variants(table)
    for axis, (_, unit) in zip(axes.ravel(), units.iterrows()):
        code = unit[config.AREA_CODE_COL]
        _shade_held(axis, provenance)
        for variant in variants:
            block = _block(table, variant, actor, day_type)
            series = block[block[config.AREA_CODE_COL] == code].set_index(config.YEAR_COL)[
                SERIES_COLUMN
            ].sort_index()
            indexed = 100 * series / series[base_year]
            colour = (
                config.EXPOSURE_PROVENANCE_COLORS[config.IMPLIED_FROM_RISK_EXPOSURE]
                if variant == config.PANDEMIC_PATCHED_VARIANT
                else config.EXPOSURE_PROVENANCE_COLORS[config.INTERPOLATED_EXPOSURE]
            )
            axis.plot(indexed.index, indexed.to_numpy(), color=colour, linewidth=1.2,
                      zorder=3 if variant == config.PANDEMIC_PATCHED_VARIANT else 2)
        axis.axhline(100, color="#cccccc", linewidth=0.7, zorder=1)
        axis.set_xlim(int(provenance.index.min()), int(provenance.index.max()))
        axis.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(5))
        axis.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{int(value)}"))
        axis.set_title(
            f"{code} {unit[config.AREA_NAME_COL]}"[:26], fontsize=7,
        )
        axis.tick_params(labelsize=6)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
    for axis in axes.ravel()[len(units):]:
        axis.set_visible(False)

    fig.suptitle(
        f"{config.ROAD_USER_LABELS_ES[actor]} — {config.DAY_TYPE_LABELS_ES[day_type]}, "
        f"cada unidad contra su propio {base_year} = 100\n"
        f"azul sin parche, naranja con el parche de pandemia; gris, años sostenidos",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def _unit_heatmap(
    table: pd.DataFrame, actor: str, day_type: str, path: Path, log: RunLog
) -> None:
    """The same thirty trajectories as a block, ordered by size.

    Diverging around the anchor: blue is below what that unit measured, red is
    above. Ordered by the last year's level so that the big units are together,
    which is what makes a band of colour crossing the whole block legible as
    something the city did rather than something one unit did.
    """
    variant = review_variant(table)
    block = _block(table, variant, actor, day_type)
    wide = block.pivot_table(
        index=[config.AREA_CODE_COL, config.AREA_NAME_COL],
        columns=config.YEAR_COL,
        values=SERIES_COLUMN,
    )
    provenance = _provenance_by_year(table, variant, actor, day_type)
    anchors = [year for year, value in provenance.items() if value == config.MEASURED_EXPOSURE]
    base_year = anchors[0] if anchors else wide.columns[0]
    indexed = wide.div(wide[base_year], axis=0)
    indexed = indexed.loc[wide[wide.columns[-1]].sort_values(ascending=False).index]

    # The ramp is set by the 95th percentile of the departures and not by the
    # largest of them, and the rest is clipped. One unit reaching five times its
    # anchor — Torca's walking does — would otherwise leave the other twenty-nine
    # in two shades of white. The colour bar says the ends are open.
    values = indexed.to_numpy()
    span = max(float(np.nanpercentile(np.abs(np.log2(values)), 95)), 0.2)
    norm = TwoSlopeNorm(vmin=2 ** -span, vcenter=1.0, vmax=2 ** span)
    clipped = int((np.abs(np.log2(values)) > span).sum())

    fig, axis = plt.subplots(figsize=(10, 8))
    image = axis.imshow(
        np.clip(values, 2 ** -span, 2 ** span),
        aspect="auto", cmap=config.DIVERGING_COLORMAP, norm=norm, interpolation="nearest",
    )
    axis.set_xticks(range(len(indexed.columns)))
    axis.set_xticklabels([str(year) for year in indexed.columns], fontsize=7, rotation=90)
    axis.set_yticks(range(len(indexed)))
    axis.set_yticklabels(
        [f"{code} {name}"[:28] for code, name in indexed.index], fontsize=7
    )
    axis.tick_params(length=0)
    for spine in axis.spines.values():
        spine.set_visible(False)

    # The anchors, marked on the axis rather than in the cells: every one of them
    # is exactly 1.00 by construction and a reader should be able to see which
    # columns those are without counting.
    for column, year in enumerate(indexed.columns):
        if year in anchors:
            axis.axvline(column, color="#1a1a1a", linewidth=0.8, alpha=0.55)

    bar = fig.colorbar(image, ax=axis, fraction=0.03, pad=0.02, extend="both")
    bar.set_label(f"contra el {base_year} de la misma unidad", fontsize=8)
    bar.ax.tick_params(labelsize=7)

    fig.suptitle(
        f"{config.ROAD_USER_LABELS_ES[actor]} — {config.DAY_TYPE_LABELS_ES[day_type]}, "
        f"variante {variant}\n"
        f"cada fila es una UPL contra su propio {base_year}; las líneas negras son años de "
        f"encuesta" + (f"; {clipped} celda(s) fuera de la escala" if clipped else ""),
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Drawing all of it
# ---------------------------------------------------------------------------


def draw(table: pd.DataFrame, log: RunLog) -> dict[str, Path]:
    """Every figure of the three groups that describe the panel.

    The groups that justify a decision — the patch, the diagnostic and the
    volatility — are not drawn here yet, and the numbered folders leave room for
    them in reading order.
    """
    root = log.run_dir / config.FIGURES_SUBDIR / config.INTERPOLATION_FIGURES_SUBDIR
    suffix = config.INTERPOLATION_FIGURE_FORMAT
    day_type = config.PANDEMIC_PATCH_DAY_TYPE
    written: dict[str, Path] = {}

    summary = root / config.INTERPOLATION_FIGURE_GROUPS["summary"]
    summary.mkdir(parents=True, exist_ok=True)
    path = summary / f"summary__city_series.{suffix}"
    _summary_sheet(table, path, log)
    written[path.stem] = path
    path = summary / f"summary__provenance.{suffix}"
    _provenance_sheet(table, path, log)
    written[path.stem] = path

    for actor in _modes(table):
        city = root / config.INTERPOLATION_FIGURE_GROUPS["city"] / _slug(actor)
        city.mkdir(parents=True, exist_ok=True)
        for day in _day_types(table):
            path = city / f"city__{_slug(actor)}_{_slug(day)}.{suffix}"
            _city_figure(table, actor, day, path, log)
            written[path.stem] = path

        units = root / config.INTERPOLATION_FIGURE_GROUPS["units"] / _slug(actor)
        units.mkdir(parents=True, exist_ok=True)
        # The weekday alone, and it is a scope rather than an oversight: it is the
        # day the models take, the Sunday rests on a single anchor, and ninety
        # sheets of thirty panels would be read by nobody.
        path = units / f"units__{_slug(actor)}_{_slug(day_type)}_series.{suffix}"
        _unit_series_sheet(table, actor, day_type, path, log)
        written[path.stem] = path
        path = units / f"units__{_slug(actor)}_{_slug(day_type)}_heatmap.{suffix}"
        _unit_heatmap(table, actor, day_type, path, log)
        written[path.stem] = path

    log.info(
        "wrote %d figure(s) under %s/%s/, in %d group(s)",
        len(written),
        config.FIGURES_SUBDIR,
        config.INTERPOLATION_FIGURES_SUBDIR,
        3,
    )
    return written
