"""The figures of the reconstruction: what the fitting changed, where, and what it cost.

Four figures in three groups, and each exists because a question has no other answer. The
run already prints eleven checks and a comparison table; **what a table cannot do is say
*which* units and *which* years moved**, and that is precisely what a cross-section reads.

**The visual language is `interpolation_figures`'** and not a second one. Its `draw_heatmap`
is imported rather than reimplemented, because it already resolves the four things a ratio
needs: a diverging ramp in log2, so that doubling and halving sit the same distance from
the centre; a scale set by a percentile of the departures rather than by the largest of
them, so one outlier cannot leave the other twenty-nine in two shades of white; a grey for
a missing cell that belongs to no part of the ramp, since the centre of a diverging ramp is
white and a missing year would otherwise look like a year sitting exactly on 1; and marks
on the columns that are true by construction. Two figures of one study that use two ramps
are two figures a reader has to learn twice.

**The map does not go through `maps.render_choropleth`**, which is the one place this
departs from reuse. That function draws the reference cartography with a *sequential* ramp
and writes one map per file, and a ratio centred on one needs a diverging ramp and the four
modes side by side to be read at all. Adapting it would have changed a verified function
for a figure that is not the reference map.

See D60, D61, D62 and `docs/implementing-ipf.md`.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:  # regular package import
    from src import config, interpolation_figures, reconstruction
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import interpolation_figures  # type: ignore[no-redef]
    import reconstruction  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# The ramp is set by this percentile of the departures from one. **99 and not the 95 the
# interpolation uses**, decided by Mateo on 2026-10-07 after seeing both: at 95 the figure
# saturated 68 of its 1,560 cells and hid exactly the ones that say most, and at 99 it
# clips 16 and shows the range the comparison is about.
RATIO_PERCENTILE = 99.0

_RATIO_COL = "RAZON"


def _count(value: int) -> str:
    """A count, punctuated the way the reader punctuates it: Spanish uses a point."""
    return f"{value:,}".replace(",", ".")


def _ratio(built: pd.DataFrame, d40: pd.DataFrame) -> pd.DataFrame:
    """The fitted exposure over D40's, one row per unit, mode and year.

    **Unpatched against unpatched.** Comparing the patched fitted panel with D40's
    unpatched one would read D49's patch as a difference the fitting made, and they are two
    questions: what the reconstruction does to the exposure, and what the pandemic years do
    to it. This answers the first.
    """
    key = [config.AREA_CODE_COL, config.ACTOR_TYPE_COL, config.YEAR_COL]
    column = config.MODEL_EXPOSURE_COLUMN
    fitted = built[
        (built[config.EXPOSURE_VARIANT_COL] == config.FITTED_VARIANT)
        & (built[config.DAY_TYPE_COL] == config.MODEL_EXPOSURE_DAY_TYPE)
    ]
    interpolated = d40[
        (d40[config.EXPOSURE_VARIANT_COL] == config.INTERPOLATED_VARIANT)
        & (d40[config.DAY_TYPE_COL] == config.MODEL_EXPOSURE_DAY_TYPE)
    ]
    both = (
        fitted.set_index(key)[[column, config.EXPOSURE_PROVENANCE_COL]]
        .join(interpolated.set_index(key)[[column]], how="inner", rsuffix="_D40")
    )
    both[_RATIO_COL] = both[column] / both[f"{column}_D40"].where(
        both[f"{column}_D40"] > 0, np.nan
    )
    return both


def _measured_years(ratio: pd.DataFrame) -> list[int]:
    """The years that are their own seed, where the ratio is 1 by construction.

    Both variants carry the survey's own number there, so the column is exactly white and
    a reader should be able to see which columns those are without counting.
    """
    measured = ratio[config.EXPOSURE_PROVENANCE_COL] == config.MEASURED_EXPOSURE
    return sorted({int(year) for year in ratio[measured].index.get_level_values(2)})


def _modes(table: pd.DataFrame, level: int = 1) -> list[str]:
    present = set(table.index.get_level_values(level))
    return [mode for mode in config.ROAD_USER_LABELS_ES if mode in present]


# ---------------------------------------------------------------------------
# 00_comparacion
# ---------------------------------------------------------------------------


def _ratio_heatmap(
    ratio: pd.DataFrame, names: dict[str, str], path: Path, log: RunLog
) -> None:
    """Thirty units by thirteen years, one panel per mode, diverging around one.

    **The thirty rows share one order across the four panels**, by how far the unit moves
    in whichever mode moves it most. Ordering each panel by its own movement reads better
    and is wrong: the panels share a vertical axis, so one panel's rows would carry
    another's labels. Sharing the order also lets a unit be read across the four modes on
    one line, which is the second question anybody brings to this figure.

    Alphabetical would have been the third option and is the worst of them: the question is
    which units change, and in alphabetical order that can only be answered by reading all
    thirty.
    """
    measured = _measured_years(ratio)
    modes = _modes(ratio)
    departure = np.abs(np.log2(ratio[_RATIO_COL]))
    order = list(departure.groupby(level=0).max().sort_values(ascending=False).index)

    fig, axes = plt.subplots(
        1, len(modes), figsize=(4.6 * len(modes), 8.2), sharey=True, layout="constrained"
    )
    axes = np.atleast_1d(axes)
    images, clipped = [], 0
    for axis, mode in zip(axes, modes):
        block = ratio.xs(mode, level=1)[_RATIO_COL].unstack().reindex(order)
        block.index = [
            interpolation_figures.unit_label(code, names.get(code, "")) for code in block.index
        ]
        image, cut = interpolation_figures.draw_heatmap(
            axis, block, centre=1.0, mark_columns=tuple(measured),
            percentile=RATIO_PERCENTILE,
        )
        images.append(image)
        clipped += cut
        axis.set_title(config.ROAD_USER_LABELS_ES[mode], fontsize=10)

    bar = fig.colorbar(images[0], ax=axes.tolist(), fraction=0.016, pad=0.015, extend="both")
    bar.set_label("ajustada sobre interpolada", fontsize=8)
    bar.ax.tick_params(labelsize=7)

    constructed = ratio[~ratio.index.get_level_values(2).isin(measured)][_RATIO_COL]
    notes = [
        "líneas negras, años de encuesta: la razón es 1 por construcción",
        "filas ordenadas por cuánto se mueve la unidad, no alfabéticamente",
    ]
    if clipped:
        notes.append(
            f"{clipped} celda(s) de {_count(len(ratio))} fuera de la escala, que la fija el "
            f"percentil {RATIO_PERCENTILE:.0f} de las desviaciones"
        )
    years = sorted({int(year) for year in ratio.index.get_level_values(2)})
    fig.suptitle(
        "Exposición de la matriz ajustada (D60) sobre la interpolada (D40)\n"
        f"{config.DAY_TYPE_LABELS_ES[config.MODEL_EXPOSURE_DAY_TYPE]}, "
        f"{years[0]}-{years[-1]}, ambas sin parche de pandemia\n"
        + f"mediana de los años construidos {constructed.median():.3f}".replace(".", ",")
        + ": las dos coinciden en el agregado y discrepan por unidad\n"
        + "; ".join(notes),
        fontsize=11,
    )
    interpolation_figures.stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)
    log.info("%s: %d cell(s) outside the ramp", path.name, clipped)


def _ratio_distribution(ratio: pd.DataFrame, path: Path, log: RunLog) -> None:
    """How the ratio is distributed, which is what the heatmap cannot show at a glance.

    **The heatmap answers where and this answers how much**, and the two numbers that
    matter are far apart: the median is within a thousandth of one in every mode and the
    range runs from half to more than double. A reader who sees only the first concludes
    the reconstruction changed nothing.

    On a logarithmic axis, because the quantity is a ratio: half and double belong at equal
    distances from one, and on a linear axis half is squeezed into the left third while
    double has the whole right.
    """
    measured = _measured_years(ratio)
    modes = _modes(ratio)
    constructed = ratio[~ratio.index.get_level_values(2).isin(measured)]

    fig, axis = plt.subplots(figsize=(10.5, 5.0), layout="constrained")
    positions = range(len(modes))
    data = [constructed.xs(mode, level=1)[_RATIO_COL].dropna().to_numpy() for mode in modes]
    parts = axis.violinplot(
        [np.log2(values) for values in data], positions=list(positions),
        widths=0.8, showextrema=False, showmedians=False,
    )
    for body in parts["bodies"]:
        body.set_facecolor(config.EXPOSURE_PROVENANCE_COLORS[config.FITTED_EXPOSURE])
        body.set_alpha(0.45)
        body.set_edgecolor("none")
    for position, values in zip(positions, data):
        quartiles = np.percentile(np.log2(values), [25, 50, 75])
        axis.plot([position, position], quartiles[[0, 2]], color="#1a1a1a", linewidth=2.2)
        axis.plot([position], [quartiles[1]], marker="o", color="#ffffff",
                  markeredgecolor="#1a1a1a", markersize=5, zorder=3)

    axis.axhline(0.0, color="#1a1a1a", linewidth=0.8, alpha=0.55)
    # Labelled as ratios and not as logarithms: the axis is logarithmic so that the
    # distances are honest, and the reader is owed the number they came for.
    ticks = [-1.0, -0.5, 0.0, 0.5, 1.0]
    axis.set_yticks(ticks)
    axis.set_yticklabels([f"{2 ** tick:.2f}".replace(".", ",") for tick in ticks], fontsize=8)
    axis.set_xticks(list(positions))
    axis.set_xticklabels([config.ROAD_USER_LABELS_ES[mode] for mode in modes], fontsize=9)
    axis.set_ylabel("ajustada sobre interpolada", fontsize=9)
    axis.tick_params(length=0)
    for spine in ("top", "right"):
        axis.spines[spine].set_visible(False)

    summary = "; ".join(
        f"{config.ROAD_USER_LABELS_ES[mode]} {values.min():.2f}-{values.max():.2f}".replace(".", ",")
        for mode, values in zip(modes, data)
    )
    fig.suptitle(
        f"Distribución de la razón sobre los {len(constructed):,} años construidos\n"
        "la caja negra es el rango intercuartílico y el punto la mediana; "
        "eje logarítmico, de modo que la mitad y el doble distan lo mismo de 1\n"
        f"rangos: {summary}",
        fontsize=10,
    )
    interpolation_figures.stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 01_mapa
# ---------------------------------------------------------------------------


def _ratio_map(
    ratio: pd.DataFrame, units: gpd.GeoDataFrame, path: Path, log: RunLog
) -> None:
    """Where the disagreement lands, which decides whether it is structure or noise.

    **It is the question the heatmap raises and cannot answer.** If the fitting
    systematically raises the central units and lowers the peripheral ones, that is a
    finding about what the rate interpolation was missing and it belongs in the thesis. If
    it is scattered, that is also a finding, and a shorter one.

    The median over the constructed years rather than one year, because a single year is
    one draw of the fitting and the question is about the unit.
    """
    measured = _measured_years(ratio)
    modes = _modes(ratio)
    constructed = ratio[~ratio.index.get_level_values(2).isin(measured)]
    metric = units.to_crs(epsg=config.PROJECTED_CRS)

    # One ramp across the four panels, so that a stronger colour means a larger departure
    # wherever it appears. Four ramps would make the car look as unsettled as the bicycle.
    medians = constructed[_RATIO_COL].groupby(level=[0, 1]).median()
    span = max(float(np.nanpercentile(np.abs(np.log2(medians)), RATIO_PERCENTILE)), 0.05)
    norm = matplotlib.colors.TwoSlopeNorm(vmin=2 ** -span, vcenter=1.0, vmax=2 ** span)
    ramp = matplotlib.colormaps[config.DIVERGING_COLORMAP].with_extremes(bad="#e8e8e8")

    fig, axes = plt.subplots(1, len(modes), figsize=(3.6 * len(modes), 5.2),
                             layout="constrained")
    axes = np.atleast_1d(axes)
    for axis, mode in zip(axes, modes):
        values = medians.xs(mode, level=1).reindex(metric[config.AREA_CODE_COL])
        drawn = metric.assign(**{_RATIO_COL: values.to_numpy(dtype=float)})
        drawn.plot(
            column=_RATIO_COL, ax=axis, cmap=ramp, norm=norm,
            edgecolor="#ffffff", linewidth=0.35,
            missing_kwds={"color": "#e8e8e8", "edgecolor": "#ffffff", "linewidth": 0.35},
        )
        axis.set_title(config.ROAD_USER_LABELS_ES[mode], fontsize=10)
        axis.set_axis_off()

    image = matplotlib.cm.ScalarMappable(norm=norm, cmap=ramp)
    bar = fig.colorbar(image, ax=axes.tolist(), fraction=0.03, pad=0.02, extend="both")
    bar.set_label("mediana de la razón sobre los años construidos", fontsize=8)
    bar.ax.tick_params(labelsize=7)
    fig.suptitle(
        "Dónde cae la discrepancia entre la matriz ajustada y la interpolada\n"
        "una mediana por unidad y modo; rojo, el ajuste da más exposición que D40\n"
        "una sola rampa para los cuatro paneles, para que un color más fuerte signifique "
        "lo mismo en todos",
        fontsize=10,
    )
    interpolation_figures.stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 02_ajuste
# ---------------------------------------------------------------------------


def _fitting_blocks(fits: pd.DataFrame, path: Path, log: RunLog) -> None:
    """What the fitting did to reach each block, on the grid of years by modes.

    Two panels of the same grid, answering the two things a reader has to be able to check
    and that today live only in a log.

    **What the floor invented.** D61 is defensible because the number is 0.0109 % of the
    travel, and a decision defended by a number has to show the number. It is not spread
    evenly: it is cycling and motorcycling in the early segment, and seeing that is seeing
    that the years the study leans on are not the years that needed it.

    **Which survey seeds each year.** A panel of thirteen years resting on four matrices is
    unreadable without it, and it is what makes the seams legible — the first year after
    each change of seed is where the fitted panel's year-on-year change doubles.
    """
    modes = [mode for mode in config.ROAD_USER_LABELS_ES
             if mode in set(fits[config.ACTOR_TYPE_COL])]
    years = sorted({int(year) for year in fits[config.YEAR_COL]})
    fig, axes = plt.subplots(
        2, 1, figsize=(1.0 * len(years) + 3.0, 5.0),
        gridspec_kw={"height_ratios": [len(modes), 1.35]}, layout="constrained",
    )

    # **Sumadas y no la primera que aparezca.** Desde D64 un ano tiene dos bloques por
    # modo, uno por encuesta que lo siembra, y quedarse con el primero habria dibujado
    # la mitad del piso de ese ano sin decirlo.
    invented = fits.pivot_table(
        index=config.ACTOR_TYPE_COL, columns=config.YEAR_COL,
        values=reconstruction.OPENED_TRIPS_COL, aggfunc="sum",
    ).reindex(modes)[years]
    block_trips = fits.pivot_table(
        index=config.ACTOR_TYPE_COL, columns=config.YEAR_COL,
        values=reconstruction.BLOCK_TRIPS_COL, aggfunc="sum",
    ).reindex(modes)[years]
    share = (invented / block_trips * 100).fillna(0.0)
    image = axes[0].imshow(
        share.to_numpy(dtype=float), aspect="auto", interpolation="nearest",
        cmap=config.SEQUENTIAL_COLORMAP,
        norm=matplotlib.colors.Normalize(vmin=0.0, vmax=max(float(share.to_numpy().max()), 0.01)),
    )
    for row in range(share.shape[0]):
        for column in range(share.shape[1]):
            value = float(share.iloc[row, column])
            axes[0].text(
                column, row, "—" if value <= 0 else f"{value:.2f}".replace(".", ","),
                ha="center", va="center", fontsize=6.5,
                color=interpolation_figures.figures.text_color_on(image, value),
            )
    bar = fig.colorbar(image, ax=axes[0], fraction=0.02, pad=0.01)
    bar.set_label("% inventado", fontsize=7)
    bar.ax.tick_params(labelsize=6)
    axes[0].set_title(
        "Lo que el piso inventó, en % de los viajes del bloque (D61). "
        "Una raya, el bloque no necesitó piso",
        fontsize=9,
    )

    # **One strip and not one row per mode.** The seeding surveys are chosen per kind of
    # day and never per mode, so four rows would be four identical rows — and a figure
    # that repeats a constant invites a reader to look for the variation it implies.
    # Checked rather than assumed, because if it ever stopped being true this is where it
    # would show first.
    blends = {}
    for year, block in fits.groupby(config.YEAR_COL):
        per_mode = block.groupby(config.ACTOR_TYPE_COL).apply(
            lambda rows: tuple(sorted(
                (int(y), round(float(w), 6)) for y, w in zip(
                    rows[reconstruction.SEED_YEAR_COL],
                    rows[reconstruction.SEED_WEIGHT_COL])
            )), include_groups=False)
        if per_mode.nunique() > 1:
            raise ValueError(
                "the seeding surveys differ between modes in some year, and they are "
                "chosen per kind of day only. Either `seeding_blend` grew a mode argument "
                "or the blocks of one year were built from different surveys"
            )
        blends[int(year)] = per_mode.iloc[0]

    # **The colour is the effective seed year**, the weighted mean of the two, so the
    # strip runs continuously from one survey to the next instead of in steps. That
    # continuity is the whole of D64 and it is the thing worth seeing at a glance.
    effective = np.array([sum(y * w for y, w in blends[year]) for year in years])
    strip = axes[1].imshow(
        effective.reshape(1, -1), aspect="auto", interpolation="nearest",
        cmap=config.SEQUENTIAL_COLORMAP,
        vmin=float(effective.min()), vmax=float(effective.max()),
    )
    for column, year in enumerate(years):
        parts = blends[year]
        own = len(parts) == 1 and parts[0][0] == year
        label = (
            str(parts[0][0]) if len(parts) == 1
            else "\n".join(f"{y}·{w:.0%}" for y, w in parts)
        )
        # El color del texto lo decide el fondo y no una constante: la rampa llega a su
        # extremo oscuro en los años tardíos y ahí el texto fijo no se leía.
        axes[1].text(
            column, 0, label, ha="center", va="center",
            fontsize=6.5 if len(parts) == 1 else 5.4,
            color=interpolation_figures.figures.text_color_on(strip, effective[column]),
            fontweight="bold" if own else "normal",
        )
    axes[1].set_title(
        "En qué encuestas descansa cada año, que son las mismas para los cuatro modos "
        "porque se eligen por tipo de día.\n"
        "En negrita, el año es su propia semilla y no se ajusta nada (D64)",
        fontsize=9,
    )
    axes[1].set_yticks([0])
    axes[1].set_yticklabels(["Los cuatro modos"], fontsize=8)

    for index, axis in enumerate(axes):
        axis.set_xticks(range(len(years)))
        axis.set_xticklabels([str(year) for year in years], fontsize=7)
        if index == 0:
            axis.set_yticks(range(len(modes)))
            axis.set_yticklabels(
                [config.ROAD_USER_LABELS_ES[mode] for mode in modes], fontsize=8)
        axis.tick_params(length=0)
        for spine in axis.spines.values():
            spine.set_visible(False)
        # **Las líneas son los años de encuesta y ya no las costuras.** Antes marcaban
        # dónde cambiaba la semilla de golpe; con la mezcla no cambia de golpe en ninguna
        # parte, y lo que sí tiene un sitio es el año que descansa en una sola encuesta y
        # no se ajusta. D64.
        for column, year in enumerate(years):
            if len(blends[year]) == 1 and blends[year][0][0] == year:
                axis.axvline(column - 0.5, color="#1a1a1a", linewidth=0.9, alpha=0.5)
                axis.axvline(column + 0.5, color="#1a1a1a", linewidth=0.9, alpha=0.5)

    floored = int((fits[reconstruction.FLOORED_COL]).sum())
    anclas = sum(1 for year in years if len(blends[year]) == 1 and blends[year][0][0] == year)
    fig.suptitle(
        f"Lo que el ajuste hizo, bloque por bloque ({config.DAY_TYPE_LABELS_ES[config.MODEL_EXPOSURE_DAY_TYPE].lower()})\n"
        f"{floored} de {len(fits)} bloques necesitaron el piso; entre líneas, los "
        f"{anclas} años de encuesta, que descansan en sí mismos y no se ajustan",
        fontsize=10,
    )
    interpolation_figures.stamp(fig, log)
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Every figure
# ---------------------------------------------------------------------------


def draw(
    built: pd.DataFrame,
    fits: pd.DataFrame,
    d40: pd.DataFrame,
    units: gpd.GeoDataFrame,
    log: RunLog,
) -> dict[str, Path]:
    """The four figures, in their three numbered groups."""
    root = log.run_dir / config.FIGURES_SUBDIR / config.RECONSTRUCTION_FIGURES_SUBDIR
    groups = {
        name: root / folder for name, folder in config.RECONSTRUCTION_FIGURE_GROUPS.items()
    }
    for directory in groups.values():
        directory.mkdir(parents=True, exist_ok=True)

    ratio = _ratio(built, d40)
    names = (
        built.drop_duplicates(config.AREA_CODE_COL)
        .set_index(config.AREA_CODE_COL)[config.AREA_NAME_COL]
        .to_dict()
    )
    suffix = config.INTERPOLATION_FIGURE_FORMAT
    written: dict[str, Path] = {}

    path = groups["comparison"] / f"comparacion__razon_por_unidad.{suffix}"
    _ratio_heatmap(ratio, names, path, log)
    written[path.name] = path

    path = groups["comparison"] / f"comparacion__distribucion.{suffix}"
    _ratio_distribution(ratio, path, log)
    written[path.name] = path

    path = groups["map"] / f"mapa__razon_por_unidad.{suffix}"
    _ratio_map(ratio, units, path, log)
    written[path.name] = path

    path = groups["fitting"] / f"ajuste__bloques.{suffix}"
    _fitting_blocks(fits, path, log)
    written[path.name] = path

    log.record(
        "draw the reconstruction figures",
        rows_in=len(built),
        rows_out=len(built),
        notes=[
            f"{len(written)} figure(s) under "
            f"{config.FIGURES_SUBDIR}/{config.RECONSTRUCTION_FIGURES_SUBDIR}/",
            "the ramp is `interpolation_figures.draw_heatmap`'s, diverging in log2 around "
            f"one and set by the {RATIO_PERCENTILE:.0f}th percentile of the departures",
            "the comparison is unpatched against unpatched: the patch is a second question",
        ],
    )
    return written
