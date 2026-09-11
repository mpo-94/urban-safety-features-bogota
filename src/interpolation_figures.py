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

Six groups, numbered so that a directory listing is a reading order. The first
three describe the panel:

    00_summary  the four modes on one sheet, and where every cell comes from
    01_city     one mode and one kind of day at a time, level and rate
    02_units    the thirty units, as thirty small series and as a heatmap

and the last three are the evidence behind a decision that was taken or is still
open:

    03_pandemic    the twelve factors of D42, what they do, and why at the city
    04_diagnostic  D41's ratio, which says where the panel is least believable
    05_volatility  how far a unit's rate moves between two surveys, which is the
                   price of interpolating per unit and D40's open question

The last three read tables this module does not build — the patch factors, the
casualty diagnostic and the step table — and each is skipped, with a word in the
log, when the run did not produce the table it needs.

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


def base_year_of(provenance: pd.Series) -> int:
    """The year every index and every heatmap in this module is read against.

    **The first measured year the panel window contains**, which for the weekday
    is 2011 and for the Saturday is 2011 as well. The reason it is a measured year
    and not the first year of the window is that the first year of the window is
    itself a construction: indexing against 2007 would compare every cell to a
    number the interpolation invented, and a unit whose 2007 was badly built would
    look like a unit that changed.

    The reason it is the *first* of them rather than the last is that the panel is
    read forwards — what a reader asks of these figures is what happened to a unit
    over the eighteen years, and the answer reads better from the earliest
    observation.

    **2005 is not it**, even though it is measured and earlier: it lies outside the
    window, has no row in the panel, and three of the four day types have no 2005
    at all. It is drawn as the anchor it is, and `_outside_the_window` is what puts
    it on a figure.
    """
    measured = [year for year, value in provenance.items() if value == config.MEASURED_EXPOSURE]
    return int(measured[0] if measured else provenance.index[0])


def _outside_the_window(
    measured_table: pd.DataFrame | None,
    window: pd.Index,
    actor: str,
    day_type: str,
) -> pd.DataFrame:
    """The measured years of this series that the panel has no row for.

    2005 is the only one today. The casualty series starts in 2007 and the panel
    window follows it, so the fifth survey shapes the 2007-2010 curve from outside
    and never appears in the table these figures are drawn from. Leaving it off the
    figure would show four anchors where the series rests on five.

    The population comes back with the level because a figure of rates needs it and
    the panel has no row to take it from: the rate of a year outside the window is
    that year's trips over that year's residents, both from the measured table.
    """
    empty = pd.DataFrame(columns=[SERIES_COLUMN, config.POPULATION_COL], dtype=float)
    if measured_table is None:
        return empty
    rows = measured_table[
        (measured_table[config.ACTOR_TYPE_COL] == actor)
        & (measured_table[config.DAY_TYPE_COL] == day_type)
        & (~measured_table[config.YEAR_COL].isin(list(window)))
    ]
    if rows.empty:
        return empty
    return rows.groupby(config.YEAR_COL)[[SERIES_COLUMN, config.POPULATION_COL]].sum().sort_index()


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
    measured_table: pd.DataFrame | None = None,
) -> None:
    """One mode's city series, with both variants and every year marked.

    **Every year carries a dot and the dot is coloured by where its value came
    from**, which is the same palette the provenance strip uses: near-black for a
    survey year, blue for an interpolated one, grey for a held one and orange for a
    patched one. A figure that marked only the survey years would say what was
    measured and leave a reader to count the rest.

    The unpatched panel is drawn **over** the patched one, so that what the line
    shows by default is the panel as D40 builds it and the patch is visible only
    where it actually changes something. The patched line is the wider of the two
    for the same reason: where the two agree it shows as a hairline either side of
    the blue, and where they part company it is unmistakable.

    And a measured year that sits outside the window — 2005 — is drawn as the
    anchor it is, joined to the window by a dotted segment, because the series
    rests on five surveys and the panel has rows for four.
    """
    variants = _variants(table)
    provenance = _provenance_by_year(table, config.INTERPOLATED_VARIANT, actor, day_type)
    _shade_held(axis, provenance)

    base = _city_series(table, config.INTERPOLATED_VARIANT, actor, day_type, column) / scale
    patched = None
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
                linewidth=2.6, zorder=2,
                label=config.EXPOSURE_VARIANT_LABELS_ES[config.PANDEMIC_PATCHED_VARIANT],
            )

    axis.plot(
        base.index, base.to_numpy(),
        color=config.EXPOSURE_PROVENANCE_COLORS[config.INTERPOLATED_EXPOSURE],
        linewidth=1.6, zorder=3,
        label=config.EXPOSURE_VARIANT_LABELS_ES[config.INTERPOLATED_VARIANT],
    )

    # The anchor the panel has no row for, and the segment the interpolation
    # actually used to reach 2007. Dotted, because the panel holds no year
    # between the two and the line is the curve rather than a set of cells.
    outside = _outside_the_window(measured_table, base.index, actor, day_type)
    for year, row in outside.iterrows():
        # On the rate panel the anchor is its own trips over its own residents; on
        # a level panel it is the level, scaled like the rest of the axis.
        value = (
            row[SERIES_COLUMN] / row[config.POPULATION_COL]
            if column in (config.INTERPOLATED_RATE_COL, config.INTERPOLATED_RATE_OVER_15MIN_COL)
            else row[SERIES_COLUMN] / scale
        )
        axis.plot(
            [year, int(base.index.min())], [value, float(base.iloc[0])],
            linestyle=":", linewidth=1.3,
            color=config.EXPOSURE_PROVENANCE_COLORS[config.INTERPOLATED_EXPOSURE], zorder=3,
        )
        axis.plot(
            [year], [value], linestyle="none", marker="o", markersize=6,
            color=config.EXPOSURE_PROVENANCE_COLORS[config.MEASURED_EXPOSURE], zorder=5,
        )

    # One dot per year, on the colour of its own provenance.
    for value in config.EXPOSURE_PROVENANCES:
        years = [year for year, where in provenance.items() if where == value]
        if not years:
            continue
        axis.plot(
            years, base.loc[years].to_numpy(), linestyle="none", marker="o",
            markersize=6 if value == config.MEASURED_EXPOSURE else 4,
            color=config.EXPOSURE_PROVENANCE_COLORS[value], zorder=4,
            label=config.EXPOSURE_PROVENANCE_LABELS_ES[value],
        )
    if patched is not None and differs:
        axis.plot(
            differs, patched.loc[differs].to_numpy(), linestyle="none", marker="o",
            markersize=4,
            color=config.EXPOSURE_PROVENANCE_COLORS[config.IMPLIED_FROM_RISK_EXPOSURE],
            zorder=4,
            label=config.EXPOSURE_PROVENANCE_LABELS_ES[config.IMPLIED_FROM_RISK_EXPOSURE],
        )

    axis.set_ylim(bottom=0)
    axis.set_xlim(
        int(min([base.index.min(), *outside.index])), int(base.index.max())
    )
    # A year is an integer and a tick reading 2007,5 is a year that does not
    # exist. Every two years, so that both ends of the axis carry a label whether
    # or not the series reaches back to the anchor outside the window.
    axis.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
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


def _summary_sheet(
    table: pd.DataFrame, path: Path, log: RunLog, measured_table: pd.DataFrame | None = None
) -> None:
    """The four modes on one sheet, on the kind of day the models take."""
    day_type = config.PANDEMIC_PATCH_DAY_TYPE
    modes = _modes(table)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for axis, actor in zip(axes.ravel(), modes):
        _draw_series(axis, table, actor, day_type, scale=1000.0, measured_table=measured_table)
        axis.set_title(config.ROAD_USER_LABELS_ES[actor], fontsize=10)
        axis.set_ylabel("miles de viajes al día", fontsize=8)
        axis.tick_params(labelsize=8)
    for axis in axes.ravel()[len(modes):]:
        axis.set_visible(False)

    # One entry per label rather than one per artist: four modes drawn the same way
    # produce the same handle four times.
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    # The band, which the dots already name, so the entry says what the band means
    # rather than repeating the word.
    unique["Bloque sostenido: la tasa no se mueve"] = Patch(
        facecolor=config.EXPOSURE_PROVENANCE_COLORS[config.HELD_EXPOSURE], alpha=0.13
    )
    fig.legend(
        list(unique.values()), list(unique), loc="lower center",
        ncol=min(4, len(unique)), fontsize=8, frameon=False,
    )

    fig.suptitle(
        "La exposición del estudio en las 30 UPL, "
        f"{config.DAY_TYPE_LABELS_ES[day_type]}\n"
        "cada año lleva un punto del color de su procedencia; la caminata es la de 15 "
        "minutos o más (D39)",
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


def _city_figure(
    table: pd.DataFrame,
    actor: str,
    day_type: str,
    path: Path,
    log: RunLog,
    measured_table: pd.DataFrame | None = None,
) -> None:
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
    _draw_series(top, table, actor, day_type, scale=1000.0, measured_table=measured_table)
    top.set_ylabel("miles de viajes al día", fontsize=9)
    # The same anchor on both panels. They share an x axis, so a panel drawn
    # without it would pull the other one's limits in and cut the anchor off the
    # figure entirely.
    _draw_series(
        bottom, table, actor, day_type, column=RATE_COLUMN, measured_table=measured_table
    )
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
    table: pd.DataFrame,
    actor: str,
    day_type: str,
    path: Path,
    log: RunLog,
    measured_table: pd.DataFrame | None = None,
) -> None:
    """Thirty small series on one sheet, each against its own first measured year.

    Indexed rather than levelled, because Kennedy makes forty times the walking
    trips Torca does and a shared axis of levels would show one line and
    twenty-nine flat ones. What the sheet is for is the shape: a unit whose
    trajectory does something no city does is visible here and nowhere else — so
    the panels are drawn large enough to read one at a time rather than packed to
    fit the page.

    The unpatched panel is drawn over the patched one, and the anchors of each
    series carry a dot, including the one outside the window.
    """
    units = (
        table[[config.AREA_CODE_COL, config.AREA_NAME_COL]]
        .drop_duplicates()
        .sort_values(config.AREA_CODE_COL)
    )
    provenance = _provenance_by_year(table, config.INTERPOLATED_VARIANT, actor, day_type)
    base_year = base_year_of(provenance)
    anchors = [year for year, value in provenance.items() if value == config.MEASURED_EXPOSURE]
    outside = _outside_the_window(measured_table, provenance.index, actor, day_type)
    outside_years = list(outside.index)

    columns = 5
    rows = int(np.ceil(len(units) / columns))
    fig, axes = plt.subplots(
        rows, columns, figsize=(3.2 * columns, 2.4 * rows), sharex=True, sharey=True
    )
    variants = _variants(table)
    first, last = int(min([provenance.index.min(), *outside_years])), int(provenance.index.max())
    for axis, (_, unit) in zip(axes.ravel(), units.iterrows()):
        code = unit[config.AREA_CODE_COL]
        _shade_held(axis, provenance)
        indexed = {}
        for variant in variants:
            block = _block(table, variant, actor, day_type)
            series = block[block[config.AREA_CODE_COL] == code].set_index(config.YEAR_COL)[
                SERIES_COLUMN
            ].sort_index()
            indexed[variant] = 100 * series / series[base_year]
        base = indexed[config.INTERPOLATED_VARIANT]

        # The patched line is drawn ONLY over the years it changes, plus one either
        # side so the segment joins the curve. Drawn over the whole window it would
        # sit under the blue for fifteen of the eighteen years and show as a halo,
        # and what this sheet is read for is the trajectory D40 builds.
        after = indexed.get(config.PANDEMIC_PATCHED_VARIANT)
        if after is not None:
            differs = [
                year for year in after.index if not np.isclose(after[year], base[year])
            ]
            if differs:
                span = [
                    year for year in after.index
                    if min(differs) - 1 <= year <= max(differs) + 1
                ]
                axis.plot(
                    span, after.loc[span].to_numpy(),
                    color=config.EXPOSURE_PROVENANCE_COLORS[config.IMPLIED_FROM_RISK_EXPOSURE],
                    linewidth=1.6, zorder=2,
                )
        axis.plot(
            base.index, base.to_numpy(),
            color=config.EXPOSURE_PROVENANCE_COLORS[config.INTERPOLATED_EXPOSURE],
            linewidth=1.5, zorder=3,
        )
        if base is not None:
            axis.plot(
                anchors, base.loc[anchors].to_numpy(), linestyle="none", marker="o",
                markersize=3.5,
                color=config.EXPOSURE_PROVENANCE_COLORS[config.MEASURED_EXPOSURE], zorder=4,
            )
            for year in outside_years:
                block = _block(table, config.INTERPOLATED_VARIANT, actor, day_type)
                anchor_value = measured_table[
                    (measured_table[config.AREA_CODE_COL] == code)
                    & (measured_table[config.ACTOR_TYPE_COL] == actor)
                    & (measured_table[config.DAY_TYPE_COL] == day_type)
                    & (measured_table[config.YEAR_COL] == year)
                ][SERIES_COLUMN]
                if anchor_value.empty:
                    continue
                value = 100 * float(anchor_value.iloc[0]) / float(
                    block[block[config.AREA_CODE_COL] == code].set_index(config.YEAR_COL)[
                        SERIES_COLUMN
                    ][base_year]
                )
                axis.plot(
                    [year, int(provenance.index.min())], [value, float(base.iloc[0])],
                    linestyle=":", linewidth=1.1,
                    color=config.EXPOSURE_PROVENANCE_COLORS[config.INTERPOLATED_EXPOSURE],
                    zorder=3,
                )
                axis.plot(
                    [year], [value], linestyle="none", marker="o", markersize=3.5,
                    color=config.EXPOSURE_PROVENANCE_COLORS[config.MEASURED_EXPOSURE], zorder=4,
                )
        axis.axhline(100, color="#cccccc", linewidth=0.7, zorder=1)
        axis.set_xlim(first, last)
        axis.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(5))
        axis.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{int(value)}"))
        axis.set_title(f"{code} {unit[config.AREA_NAME_COL]}"[:30], fontsize=9)
        axis.tick_params(labelsize=8)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
    for axis in axes.ravel()[len(units):]:
        axis.set_visible(False)

    fig.suptitle(
        f"{config.ROAD_USER_LABELS_ES[actor]} — {config.DAY_TYPE_LABELS_ES[day_type]}, "
        f"cada unidad contra su propio {base_year} = 100,\n"
        "que es el primer año medido dentro de la ventana\n"
        "azul sin parche y naranja con el parche de pandemia; puntos negros, años de encuesta; "
        "bandas grises, años sostenidos"
        + (
            "\n"
            + ", ".join(str(year) for year in outside.index)
            + " es ancla de la interpolación y no tiene fila en el panel, por eso su tramo va "
            "punteado"
            if len(outside) else ""
        ),
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def _draw_heatmap(
    axis,
    matrix: pd.DataFrame,
    *,
    centre: float | None = 1.0,
    mark_columns: tuple = (),
    annotate_above: float | None = None,
    percentile: float = 95.0,
) -> tuple:
    """A block of unit-by-something, on a ramp one outlier cannot flatten.

    **The ramp is set by the 95th percentile of the departures and not by the
    largest of them**, and the rest is clipped with the colour bar saying so. One
    unit reaching five times its anchor — Torca's walking does — would otherwise
    leave the other twenty-nine in two shades of white.

    `centre` of 1.0 gives a diverging ramp around it, which is what an index or a
    ratio wants; None gives a sequential one from the bottom of the data, which is
    what a quantity with a floor wants, such as a step factor that is at least one
    by construction. Returns the image and how many cells were clipped.
    """
    values = matrix.to_numpy(dtype=float)
    if centre is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            departures = np.abs(np.log2(values / centre))
        span = max(float(np.nanpercentile(departures, percentile)), 0.2)
        low, high = centre * 2 ** -span, centre * 2 ** span
        norm = TwoSlopeNorm(vmin=low, vcenter=centre, vmax=high)
        cmap = config.DIVERGING_COLORMAP
    else:
        low = float(np.nanmin(values))
        high = max(float(np.nanpercentile(values, percentile)), low * 1.01)
        norm = matplotlib.colors.Normalize(vmin=low, vmax=high)
        cmap = config.SEQUENTIAL_COLORMAP
    clipped = int(np.nansum((values < low) | (values > high)))

    # A year the matrix has no value for is drawn in a grey that belongs to no part
    # of the ramp. White would not do: the centre of a diverging ramp is white, so a
    # missing year and a year sitting exactly on the base year would look the same,
    # and one of the two is a value.
    ramp = matplotlib.colormaps[cmap].with_extremes(bad="#e8e8e8")
    image = axis.imshow(
        np.clip(values, low, high),
        aspect="auto", cmap=ramp, norm=norm, interpolation="nearest",
    )
    axis.set_xticks(range(len(matrix.columns)))
    axis.set_xticklabels([str(column) for column in matrix.columns], fontsize=7, rotation=90)
    axis.set_yticks(range(len(matrix)))
    axis.set_yticklabels([str(label)[:28] for label in matrix.index], fontsize=7)
    axis.tick_params(length=0)
    for spine in axis.spines.values():
        spine.set_visible(False)

    # The columns that are true by construction, marked on the axis rather than in
    # the cells: an anchor year is exactly 1.00 everywhere and a reader should be
    # able to see which columns those are without counting.
    for position, column in enumerate(matrix.columns):
        if column in mark_columns:
            axis.axvline(position, color="#1a1a1a", linewidth=0.8, alpha=0.55)

    if annotate_above is not None:
        for row in range(values.shape[0]):
            for column in range(values.shape[1]):
                value = values[row, column]
                if not (np.isfinite(value) and value > annotate_above):
                    continue
                # Black on the pale end of the ramp and white on the dark end.
                # The cells worth annotating are exactly the dark ones, so a
                # fixed colour would hide the figures that matter most.
                red, green, blue, _ = image.cmap(image.norm(min(value, high)))
                luminance = 0.299 * red + 0.587 * green + 0.114 * blue
                axis.text(
                    column, row, f"{value:.1f}".replace(".", ","),
                    ha="center", va="center", fontsize=6,
                    color="#ffffff" if luminance < 0.55 else "#1a1a1a",
                )
    return image, clipped


def _unit_label(code: str, name: str) -> str:
    return f"{code} {name}"


def _unit_heatmap(
    table: pd.DataFrame,
    actor: str,
    day_type: str,
    path: Path,
    log: RunLog,
    measured_table: pd.DataFrame | None = None,
) -> None:
    """The thirty trajectories as a block, ordered by size.

    Diverging around the base year `base_year_of` picks — the first measured year
    inside the window, which for the weekday is 2011 — so blue is below what that
    unit measured and red is above. **Why that year and not another is a choice a
    reader has to be told about**, and it is in the title of the figure as well as
    in that function's docstring, because an index is only as meaningful as its
    base.

    Ordered by the last year's level so that the big units are together, which is
    what makes a band of colour crossing the whole block legible as something the
    city did rather than something one unit did.

    A measured year outside the window gets a column of its own, and the years
    between it and the window are left blank, because the panel holds no value
    for them.
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
    base_year = base_year_of(provenance)

    outside = _outside_the_window(measured_table, wide.columns, actor, day_type)
    if not outside.empty:
        earlier = measured_table[
            (measured_table[config.ACTOR_TYPE_COL] == actor)
            & (measured_table[config.DAY_TYPE_COL] == day_type)
            & (measured_table[config.YEAR_COL].isin(list(outside.index)))
        ].pivot_table(
            index=[config.AREA_CODE_COL, config.AREA_NAME_COL],
            columns=config.YEAR_COL,
            values=SERIES_COLUMN,
        )
        wide = earlier.join(wide, how="right")
        anchors = sorted(set(anchors) | set(outside.index))
        # Every year between the anchor and the window, so that the gap the panel
        # has is a gap on the figure too.
        wide = wide.reindex(
            columns=range(int(min(anchors)), int(max(wide.columns)) + 1)
        )

    indexed = wide.div(wide[base_year], axis=0)
    indexed = indexed.loc[wide[wide.columns[-1]].sort_values(ascending=False).index]
    indexed.index = [_unit_label(code, name) for code, name in indexed.index]

    fig, axis = plt.subplots(figsize=(10, 8))
    image, clipped = _draw_heatmap(axis, indexed, centre=1.0, mark_columns=tuple(anchors))
    bar = fig.colorbar(image, ax=axis, fraction=0.03, pad=0.02, extend="both")
    bar.set_label(f"contra el {base_year} de la misma unidad", fontsize=8)
    bar.ax.tick_params(labelsize=7)

    fig.suptitle(
        f"{config.ROAD_USER_LABELS_ES[actor]} — {config.DAY_TYPE_LABELS_ES[day_type]}, "
        f"variante {variant}\n"
        f"cada fila es una UPL contra su propio {base_year},\n"
        "que es el primer año medido dentro de la ventana\n"
        "líneas negras, años de encuesta; gris, año sin fila en el panel"
        + (f"; {clipped} celda(s) fuera de la escala" if clipped else ""),
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 03_pandemic
# ---------------------------------------------------------------------------


def _pandemic_factors(patch, path: Path, log: RunLog) -> None:
    """The twelve numbers D42 rests on, and the twelve the other dataset gives.

    The bars are the declared series and the dashes are the sensitivity. What the
    figure is for is the comparison between them: where a dash sits on its bar the
    patch does not depend on the rho question at all, and where it does not the
    difference is the recording change, which is the car and the motorcycle and
    nothing else.
    """
    table = patch.table
    modes = [actor for actor in config.ROAD_USER_TYPES if actor in set(table[config.ACTOR_TYPE_COL])]
    years = list(config.PANDEMIC_PATCH_YEARS)
    declared = table[table[config.DATASET_COL] == patch.dataset].set_index(
        [config.ACTOR_TYPE_COL, config.YEAR_COL]
    )[config.PANDEMIC_PATCH_FACTOR_COL]
    others = [name for name in sorted(table[config.DATASET_COL].unique()) if name != patch.dataset]

    fig, axis = plt.subplots(figsize=(10, 5.2))
    positions, labels, heights = [], [], []
    position = 0.0
    for actor in modes:
        for year in years:
            positions.append(position)
            labels.append(str(year))
            heights.append(float(declared.loc[(actor, year)]))
            position += 1.0
        position += 0.8

    bars = axis.bar(
        positions, heights,
        color=config.EXPOSURE_PROVENANCE_COLORS[config.IMPLIED_FROM_RISK_EXPOSURE],
        width=0.8, zorder=3,
    )

    sensitivities = []
    for name in others:
        sensitivity = table[table[config.DATASET_COL] == name].set_index(
            [config.ACTOR_TYPE_COL, config.YEAR_COL]
        )[config.PANDEMIC_PATCH_FACTOR_COL]
        values = [float(sensitivity.loc[(actor, year)]) for actor in modes for year in years]
        sensitivities.append(values)
        axis.plot(
            positions, values, linestyle="none", marker="_", markersize=16, markeredgewidth=2,
            color="#1a1a1a", zorder=4, label=f"mismo factor sobre {name}",
        )

    # Above whichever of the two marks is higher, or the label of a bar whose
    # sensitivity sits above it lands on top of the dash.
    tops = [
        max([height] + [values[index] for values in sensitivities])
        for index, height in enumerate(heights)
    ]
    for bar, height, top in zip(bars, heights, tops):
        axis.text(
            bar.get_x() + bar.get_width() / 2, top + 0.025, f"{height:.3f}".replace(".", ","),
            ha="center", va="bottom", fontsize=7,
        )

    axis.axhline(1.0, color="#1a1a1a", linewidth=1.0, zorder=2)
    axis.set_xticks(positions)
    axis.set_xticklabels(labels, fontsize=8)
    axis.set_ylabel("factor aplicado a la exposición", fontsize=9)
    axis.set_ylim(0, max(tops) * 1.18)
    axis.grid(True, axis="y", color="#e4e4e4", linewidth=0.6, zorder=0)
    axis.set_axisbelow(True)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)

    # The mode under its three years, once, instead of on every bar.
    for index, actor in enumerate(modes):
        centre = float(np.mean(positions[index * len(years):(index + 1) * len(years)]))
        axis.text(
            centre, -0.09, config.ROAD_USER_LABELS_ES[actor], ha="center", va="top",
            fontsize=10, transform=axis.get_xaxis_transform(),
        )
    if others:
        axis.legend(fontsize=8, frameon=False, loc="upper left")

    fig.suptitle(
        f"El parche de pandemia: qué multiplica cada modo y año (D42)\n"
        f"derivado de {patch.dataset}; por encima de 1 el parche dice que hubo más viaje "
        "que la línea recta",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.90))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def _pandemic_before_after(table: pd.DataFrame, path: Path, log: RunLog) -> None:
    """The four modes through the pandemic, each against its own 2019.

    Indexed and on one pair of axes rather than four, because the argument for the
    patch is that the four modes agree: everything collapses in 2020 except
    cycling, which holds and then peaks in 2021. Four panels would show four
    plausible series; one shows the agreement.
    """
    day_type = config.PANDEMIC_PATCH_DAY_TYPE
    years = list(config.PANDEMIC_PATCH_YEARS)
    span = [years[0] - 1, *years, years[-1] + 1]
    modes = _modes(table)
    styles = dict(zip(modes, ("-", "--", "-.", ":")))

    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    for axis, variant in zip(
        (left, right), (config.INTERPOLATED_VARIANT, config.PANDEMIC_PATCHED_VARIANT)
    ):
        for actor in modes:
            series = _city_series(table, variant, actor, day_type)
            if not set(span) <= set(series.index):
                continue
            indexed = 100 * series.loc[span] / series[span[0]]
            axis.plot(
                span, indexed.to_numpy(), linestyle=styles[actor], linewidth=1.8,
                color=(
                    config.EXPOSURE_PROVENANCE_COLORS[config.IMPLIED_FROM_RISK_EXPOSURE]
                    if variant == config.PANDEMIC_PATCHED_VARIANT
                    else config.EXPOSURE_PROVENANCE_COLORS[config.INTERPOLATED_EXPOSURE]
                ),
                label=config.ROAD_USER_LABELS_ES[actor],
            )
        axis.axhline(100, color="#cccccc", linewidth=0.8)
        axis.set_title(config.EXPOSURE_VARIANT_LABELS_ES[variant], fontsize=10)
        axis.set_xticks(span)
        axis.set_xticklabels([str(year) for year in span], fontsize=8)
        axis.tick_params(labelsize=8)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
    left.set_ylabel(f"índice, {span[0]} = 100", fontsize=9)
    left.legend(fontsize=8, frameon=False, ncol=2)

    fig.suptitle(
        "Lo que el parche le hace a la pandemia, por modo\n"
        "la línea recta de la izquierda dice que caminar creció 4 % en 2020",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def _pandemic_dispersion(diagnostic: pd.DataFrame, patch, path: Path, log: RunLog) -> None:
    """Why the factor is one number for the city and not thirty.

    Every dot is a unit's own factor, which is what a per-unit patch would have
    applied; the bar is the factor D42 applies instead. The median casualty count
    printed under each mode is the reason the dots scatter: at fifty casualties a
    cell, Poisson noise alone is worth about fourteen per cent, so most of the
    spread is counting error and would have been written into the exposure of
    thirty places for three years.
    """
    rows = diagnostic[
        (diagnostic[config.DATASET_COL] == patch.dataset)
        & diagnostic[config.YEAR_COL].isin(list(config.PANDEMIC_PATCH_YEARS))
    ]
    modes = [actor for actor in config.ROAD_USER_TYPES if actor in set(rows[config.ACTOR_TYPE_COL])]
    years = list(config.PANDEMIC_PATCH_YEARS)

    fig, axes = plt.subplots(1, len(years), figsize=(3.6 * len(years), 4.8), sharey=True)
    generator = np.random.default_rng(0)  # the jitter is cosmetic and has to repeat
    for axis, year in zip(np.atleast_1d(axes), years):
        for position, actor in enumerate(modes):
            cell = rows[(rows[config.ACTOR_TYPE_COL] == actor) & (rows[config.YEAR_COL] == year)]
            values = cell[config.EXPOSURE_RATIO_COL].to_numpy(dtype=float)
            axis.plot(
                position + generator.uniform(-0.16, 0.16, len(values)), values,
                linestyle="none", marker="o", markersize=3.5, alpha=0.55,
                color=config.EXPOSURE_PROVENANCE_COLORS[config.INTERPOLATED_EXPOSURE], zorder=2,
            )
            city = patch.factors[(actor, year)]
            axis.plot(
                [position - 0.3, position + 0.3], [city, city], linewidth=2.4,
                color=config.EXPOSURE_PROVENANCE_COLORS[config.IMPLIED_FROM_RISK_EXPOSURE],
                zorder=3,
            )
        axis.axhline(1.0, color="#cccccc", linewidth=0.8, zorder=1)
        axis.set_yscale("log", base=2)
        axis.set_yticks([0.25, 0.5, 1, 2, 4])
        axis.set_yticklabels(["0,25", "0,5", "1", "2", "4"], fontsize=8)
        axis.set_xticks(range(len(modes)))
        axis.set_xticklabels(
            [
                f"{config.ROAD_USER_LABELS_ES[actor]}\n({int(rows[(rows[config.ACTOR_TYPE_COL] == actor) & (rows[config.YEAR_COL] == year)][config.AFFECTED_PARTIES_COL].median())})"
                for actor in modes
            ],
            fontsize=8,
        )
        axis.set_title(str(year), fontsize=10)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
    np.atleast_1d(axes)[0].set_ylabel("factor que implicaría cada unidad", fontsize=9)

    fig.suptitle(
        "Por qué el factor se calcula en la ciudad y no en la unidad (D42)\n"
        "cada punto es una UPL y la barra naranja es el factor que se aplicó; entre "
        "paréntesis, la mediana de siniestros por unidad",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 04_diagnostic
# ---------------------------------------------------------------------------


def _diagnostic_city(diagnostic: pd.DataFrame, path: Path, log: RunLog) -> None:
    """D41's ratio at the scale of the city, both casualty datasets.

    One at every survey year by construction, and its distance from one is how
    much of the movement the panel is putting into the risk rather than into the
    exposure. Read at the city first and at a unit afterwards: the per-unit
    version of this number carries Poisson noise that the city's does not.
    """
    modes = [actor for actor in config.ROAD_USER_TYPES if actor in set(diagnostic[config.ACTOR_TYPE_COL])]
    datasets = sorted(diagnostic[config.DATASET_COL].unique())
    styles = dict(zip(datasets, ("-", "--")))
    colours = dict(zip(datasets, (
        config.EXPOSURE_PROVENANCE_COLORS[config.INTERPOLATED_EXPOSURE],
        config.EXPOSURE_PROVENANCE_COLORS[config.MEASURED_EXPOSURE],
    )))

    fig, axes = plt.subplots(2, 2, figsize=(11, 6.8), sharex=True, sharey=True)
    for axis, actor in zip(axes.ravel(), modes):
        for dataset in datasets:
            rows = diagnostic[
                (diagnostic[config.ACTOR_TYPE_COL] == actor)
                & (diagnostic[config.DATASET_COL] == dataset)
            ]
            totals = rows.groupby(config.YEAR_COL)[
                [config.IMPLIED_EXPOSURE_COL, SERIES_COLUMN]
            ].sum(min_count=1)
            ratio = totals[config.IMPLIED_EXPOSURE_COL] / totals[SERIES_COLUMN]
            axis.plot(
                ratio.index, ratio.to_numpy(), linestyle=styles[dataset], linewidth=1.5,
                color=colours[dataset], label=dataset,
            )
        anchors = sorted(
            diagnostic.loc[
                (diagnostic[config.ACTOR_TYPE_COL] == actor)
                & (diagnostic[config.EXPOSURE_PROVENANCE_COL] == config.MEASURED_EXPOSURE),
                config.YEAR_COL,
            ].unique()
        )
        for year in anchors:
            axis.axvline(year, color="#dddddd", linewidth=0.9, zorder=0)
        axis.axhline(1.0, color="#1a1a1a", linewidth=0.9, zorder=1)
        axis.set_title(config.ROAD_USER_LABELS_ES[actor], fontsize=10)
        axis.set_yscale("log", base=2)
        axis.set_yticks([0.5, 0.75, 1, 1.5, 2])
        axis.set_yticklabels(["0,5", "0,75", "1", "1,5", "2"], fontsize=8)
        axis.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(3))
        axis.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{int(value)}"))
        axis.tick_params(labelsize=8)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
    axes.ravel()[0].legend(fontsize=8, frameon=False)

    fig.suptitle(
        "D41: la exposición que implicaría un riesgo suave, sobre la que lleva el panel\n"
        "vale 1 en cada año de encuesta por construcción; las líneas grises son esos años",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.89))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def _diagnostic_heatmap(
    diagnostic: pd.DataFrame, actor: str, dataset: str, path: Path, log: RunLog
) -> None:
    """The same ratio, unit by unit, which is where it gets noisy and where it gets read."""
    rows = diagnostic[
        (diagnostic[config.ACTOR_TYPE_COL] == actor) & (diagnostic[config.DATASET_COL] == dataset)
    ]
    matrix = rows.pivot_table(
        index=[config.AREA_CODE_COL, config.AREA_NAME_COL],
        columns=config.YEAR_COL,
        values=config.EXPOSURE_RATIO_COL,
    )
    order = rows.groupby([config.AREA_CODE_COL, config.AREA_NAME_COL])[
        config.AFFECTED_PARTIES_COL
    ].sum().sort_values(ascending=False).index
    matrix = matrix.loc[order]
    matrix.index = [_unit_label(code, name) for code, name in matrix.index]
    anchors = tuple(sorted(
        rows.loc[
            rows[config.EXPOSURE_PROVENANCE_COL] == config.MEASURED_EXPOSURE, config.YEAR_COL
        ].unique()
    ))

    fig, axis = plt.subplots(figsize=(10, 8))
    image, clipped = _draw_heatmap(axis, matrix, centre=1.0, mark_columns=anchors)
    bar = fig.colorbar(image, ax=axis, fraction=0.03, pad=0.02, extend="both")
    bar.set_label("implicada por el riesgo ÷ la del panel", fontsize=8)
    bar.ax.tick_params(labelsize=7)

    fig.suptitle(
        f"{config.ROAD_USER_LABELS_ES[actor]} — D41 por unidad, conjunto {dataset}\n"
        "las unidades van de más a menos siniestros, que es de menos a más ruido"
        + (f"; {clipped} celda(s) fuera de la escala" if clipped else ""),
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 05_volatility
# ---------------------------------------------------------------------------


def _volatility_heatmap(steps: pd.DataFrame, path: Path, log: RunLog) -> None:
    """How far every unit's rate moves between two adjacent surveys, all of it at once.

    The price of interpolating per unit, and the table D40's open question is
    asked with: whether the per-unit trajectories need shrinking toward the city's
    is a decision for a person, and this is what it is taken in front of. The
    figures printed in the cells are the ones past the declared factor, which is
    the set the question is about.
    """
    modes = [actor for actor in config.ROAD_USER_TYPES if actor in set(steps[config.ACTOR_TYPE_COL])]
    order = sorted({
        _unit_label(code, name)
        for code, name in zip(steps[config.AREA_CODE_COL], steps[config.AREA_NAME_COL])
    })

    # Not `sharey`: the four panels carry the same thirty units in the same order
    # by construction, and sharing the axis makes blanking the second panel's
    # labels blank the first panel's as well.
    fig, axes = plt.subplots(1, len(modes), figsize=(3.0 * len(modes), 8.4))
    image = None
    for position, (axis, actor) in enumerate(zip(np.atleast_1d(axes), modes)):
        rows = steps[steps[config.ACTOR_TYPE_COL] == actor].copy()
        rows["_LABEL"] = [
            _unit_label(code, name)
            for code, name in zip(rows[config.AREA_CODE_COL], rows[config.AREA_NAME_COL])
        ]
        matrix = rows.pivot_table(index="_LABEL", columns="STEP", values="FACTOR").reindex(order)
        image, _ = _draw_heatmap(
            axis, matrix, centre=None, annotate_above=config.EXPOSURE_STEP_FACTOR
        )
        axis.set_title(config.ROAD_USER_LABELS_ES[actor], fontsize=10)
        if position:
            axis.set_yticklabels([])

    if image is not None:
        bar = fig.colorbar(
            image, ax=np.atleast_1d(axes).tolist(), fraction=0.02, pad=0.02, extend="max"
        )
        bar.set_label("factor entre encuestas contiguas", fontsize=8)
        bar.ax.tick_params(labelsize=7)

    fig.suptitle(
        "Cuánto se mueve la tasa de cada unidad entre dos encuestas contiguas\n"
        f"el número escrito es el factor cuando pasa de {config.EXPOSURE_STEP_FACTOR:.0f}; "
        "es el precio de interpolar por unidad (D40)",
        fontsize=11,
    )
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)


def _volatility_distribution(steps: pd.DataFrame, path: Path, log: RunLog) -> None:
    """The same thing as thirty dots a step, which is where the outliers show.

    A heatmap says which cells are extreme and this says how extreme, on a scale
    where a factor of two and a factor of nine are not the same colour. The line
    is the threshold the run reports on.
    """
    modes = [actor for actor in config.ROAD_USER_TYPES if actor in set(steps[config.ACTOR_TYPE_COL])]
    order = sorted(steps["STEP"].unique())

    fig, axes = plt.subplots(1, len(modes), figsize=(3.0 * len(modes), 5.0), sharey=True)
    generator = np.random.default_rng(0)
    for position, (axis, actor) in enumerate(zip(np.atleast_1d(axes), modes)):
        for index, step in enumerate(order):
            values = steps.loc[
                (steps[config.ACTOR_TYPE_COL] == actor) & (steps["STEP"] == step), "FACTOR"
            ].to_numpy(dtype=float)
            values = values[np.isfinite(values)]
            axis.plot(
                index + generator.uniform(-0.16, 0.16, len(values)), values,
                linestyle="none", marker="o", markersize=3.5, alpha=0.5,
                color=config.EXPOSURE_PROVENANCE_COLORS[config.INTERPOLATED_EXPOSURE], zorder=2,
            )
            if len(values):
                median = float(np.median(values))
                axis.plot(
                    [index - 0.3, index + 0.3], [median, median], linewidth=2.0,
                    color=config.EXPOSURE_PROVENANCE_COLORS[config.MEASURED_EXPOSURE], zorder=3,
                )
        axis.axhline(
            config.EXPOSURE_STEP_FACTOR,
            color=config.EXPOSURE_PROVENANCE_COLORS[config.IMPLIED_FROM_RISK_EXPOSURE],
            linewidth=1.2, zorder=1,
        )
        axis.set_yscale("log", base=2)
        axis.set_xticks(range(len(order)))
        axis.set_xticklabels([step.replace("-", "\n") for step in order], fontsize=7)
        axis.set_title(config.ROAD_USER_LABELS_ES[actor], fontsize=10)
        axis.tick_params(labelsize=8)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
        if position == 0:
            axis.set_ylabel("factor entre encuestas contiguas", fontsize=9)

    fig.suptitle(
        "La misma tabla como distribución: treinta unidades por tramo\n"
        f"la raya negra es la mediana y la naranja el factor de {config.EXPOSURE_STEP_FACTOR:.0f} "
        "que la corrida reporta",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    _stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Drawing all of it
# ---------------------------------------------------------------------------


def draw(
    table: pd.DataFrame,
    log: RunLog,
    patch=None,
    diagnostic: pd.DataFrame | None = None,
    steps: pd.DataFrame | None = None,
    measured_table: pd.DataFrame | None = None,
) -> dict[str, Path]:
    """Every figure, in the six numbered groups.

    The first three are drawn from the panel alone. The last three read a table
    this module does not build — the patch factors, the casualty diagnostic and
    the step table — and each is skipped with a word in the log when the run did
    not produce what it needs, because a run with no casualty matrix to read is a
    legitimate run and not a failure.
    """
    root = log.run_dir / config.FIGURES_SUBDIR / config.INTERPOLATION_FIGURES_SUBDIR
    suffix = config.INTERPOLATION_FIGURE_FORMAT
    day_type = config.PANDEMIC_PATCH_DAY_TYPE
    written: dict[str, Path] = {}

    summary = root / config.INTERPOLATION_FIGURE_GROUPS["summary"]
    summary.mkdir(parents=True, exist_ok=True)
    path = summary / f"summary__city_series.{suffix}"
    _summary_sheet(table, path, log, measured_table=measured_table)
    written[path.stem] = path
    path = summary / f"summary__provenance.{suffix}"
    _provenance_sheet(table, path, log)
    written[path.stem] = path

    for actor in _modes(table):
        city = root / config.INTERPOLATION_FIGURE_GROUPS["city"] / _slug(actor)
        city.mkdir(parents=True, exist_ok=True)
        for day in _day_types(table):
            path = city / f"city__{_slug(actor)}_{_slug(day)}.{suffix}"
            _city_figure(table, actor, day, path, log, measured_table=measured_table)
            written[path.stem] = path

        units = root / config.INTERPOLATION_FIGURE_GROUPS["units"] / _slug(actor)
        units.mkdir(parents=True, exist_ok=True)
        # The weekday alone, and it is a scope rather than an oversight: it is the
        # day the models take, the Sunday rests on a single anchor, and ninety
        # sheets of thirty panels would be read by nobody.
        path = units / f"units__{_slug(actor)}_{_slug(day_type)}_series.{suffix}"
        _unit_series_sheet(table, actor, day_type, path, log, measured_table=measured_table)
        written[path.stem] = path
        path = units / f"units__{_slug(actor)}_{_slug(day_type)}_heatmap.{suffix}"
        _unit_heatmap(table, actor, day_type, path, log, measured_table=measured_table)
        written[path.stem] = path

    groups = 3

    if patch is not None:
        pandemic = root / config.INTERPOLATION_FIGURE_GROUPS["pandemic"]
        pandemic.mkdir(parents=True, exist_ok=True)
        path = pandemic / f"pandemic__factors.{suffix}"
        _pandemic_factors(patch, path, log)
        written[path.stem] = path
        path = pandemic / f"pandemic__before_after.{suffix}"
        _pandemic_before_after(table, path, log)
        written[path.stem] = path
        if diagnostic is not None:
            path = pandemic / f"pandemic__unit_dispersion.{suffix}"
            _pandemic_dispersion(diagnostic, patch, path, log)
            written[path.stem] = path
        groups += 1
    else:
        log.info(
            "the pandemic figures are not drawn: this run built no patch, so there are no "
            "factors to show. See D42"
        )

    if diagnostic is not None and not diagnostic.empty:
        folder = root / config.INTERPOLATION_FIGURE_GROUPS["diagnostic"]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"diagnostic__city.{suffix}"
        _diagnostic_city(diagnostic, path, log)
        written[path.stem] = path
        dataset = (
            config.PANDEMIC_PATCH_DATASET
            if config.PANDEMIC_PATCH_DATASET in set(diagnostic[config.DATASET_COL])
            else sorted(diagnostic[config.DATASET_COL].unique())[0]
        )
        for actor in _modes(diagnostic):
            by_mode = folder / _slug(actor)
            by_mode.mkdir(parents=True, exist_ok=True)
            path = by_mode / f"diagnostic__{_slug(actor)}_heatmap.{suffix}"
            _diagnostic_heatmap(diagnostic, actor, dataset, path, log)
            written[path.stem] = path
        groups += 1
    else:
        log.info(
            "the diagnostic figures are not drawn: this run read no casualty matrix, so there "
            "is nothing to compare the panel against. See D41"
        )

    if steps is not None and not steps.empty:
        folder = root / config.INTERPOLATION_FIGURE_GROUPS["volatility"]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"volatility__steps.{suffix}"
        _volatility_heatmap(steps, path, log)
        written[path.stem] = path
        path = folder / f"volatility__distribution.{suffix}"
        _volatility_distribution(steps, path, log)
        written[path.stem] = path
        groups += 1

    log.info(
        "wrote %d figure(s) under %s/%s/, in %d group(s)",
        len(written),
        config.FIGURES_SUBDIR,
        config.INTERPOLATION_FIGURES_SUBDIR,
        groups,
    )
    return written
