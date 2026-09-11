"""Where the casualties happened, placed at the coordinate of their crash.

**This is not a choropleth and it is not a map of risk.** The counting by unit is
what the master table beside it does, and a map repeating it would say the same
thing twice; what this adds is the position of the event itself, which no table
can carry. And it carries counts, so the corridors that light up are the ones
that carry the travel — the Caracas, the Boyacá, the Primera de Mayo — not
necessarily the ones where a trip is most dangerous. Every figure says so in its
own caption, because that is the misreading a reader makes silently.

Two layers, always both:

* a **density surface**, computed in metres and clipped to the thirty units;
* the **points themselves** over it, at low opacity.

The pair degrades in the right direction. With thirteen thousand injured in a
year the surface carries the figure and the points are texture; with four hundred
killed the points carry it and the surface is nearly flat, which is the honest
picture, because a smooth surface over four hundred points invents structure that
is not in them.

**The density is weighted by the count the folder is about.** A crash that injured
four people contributes four to `injured/` and one to `parties/` at the same
coordinate, which is what makes the three maps of one year three different maps
rather than three drawings of the same dots. A row that contributes nothing to a
count — a crash with no death, on the `killed/` map — places no point at all.

The cartography is the one `src/maps.py` already established for the exposure
choropleths: same projection, same hairline borders, same north arrow, same scale
bar. The two appear in the same document and a reader should not have to work out
whether they show the same territory.
"""

from __future__ import annotations

import math
import textwrap
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")  # figures are written to disk, never displayed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
from matplotlib_map_utils.core.north_arrow import north_arrow
from matplotlib_scalebar.scalebar import ScaleBar
from mpl_toolkits.axes_grid1 import make_axes_locatable
from scipy.ndimage import gaussian_filter

try:  # regular package import
    from src import config, maps
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import maps  # type: ignore[no-redef]


HEXBIN = "hexbin"
KERNEL = "kernel"

QUANTILE = "quantile"
LOGARITHMIC = "log"

CONTOURS = "contour"
PIXELS = "image"

# What a caller that names no count gets. Every route names one; this is only so
# that a probe drawing one map by hand does not have to.
_DENSE_FLOOR = config.CASUALTY_MAP_RAMP_FLOOR_PERCENTILE["injured"]


def bandwidth_for(count_name: str) -> float:
    """The kernel width this count is drawn at, the same in every one of its years.

    Declared per count because the counts differ by two orders of magnitude, and
    never per year because two years drawn at two bandwidths look comparable and
    are not.
    """
    return config.CASUALTY_MAP_KERNEL_BANDWIDTH_M[count_name]


def floor_for(count_name: str) -> float:
    """The percentile below which this count's surface is left uncoloured.

    Per count and the same in every one of its years, like the bandwidth: it
    decides how much of the map is painted, and two years painted to different
    extents would look like two different amounts of harm.
    """
    return config.CASUALTY_MAP_RAMP_FLOOR_PERCENTILE[count_name]


def point_style(drawn: int) -> tuple[float, float]:
    """The size and opacity of the event marks, given how many there are.

    Interpolated between the two limit cases rather than chosen from bands, so
    that two neighbouring years of one count cannot land either side of an edge
    and come out visibly different for no reason in the data. Both follow a power
    of the count, which is the curve that keeps the ratio constant: ten times the
    marks multiplies each by the same factor wherever on the range that happens.

    Clamped at both ends, so no figure is handed a mark too small to see or an
    opacity that paints the city solid.
    """
    few, many = config.CASUALTY_MAP_POINTS_FEW, config.CASUALTY_MAP_POINTS_MANY
    span = math.log(many.points / few.points)
    position = math.log(max(drawn, 1) / few.points) / span
    position = min(max(position, 0.0), 1.0)
    size = few.size * (many.size / few.size) ** position
    alpha = few.alpha * (many.alpha / few.alpha) ** position
    return size, alpha


def _class_colours(colours, classes: int, span=None):
    """The colormap cut into as many steps as the ramp has classes.

    `span` is which stretch of the colormap the classes are taken from, as two
    fractions. It is not the whole of it: the palest end is too close to the
    ground the city is drawn on to read as a class, and the darkest end swallows
    the points drawn over it, which on a map of a few hundred deaths are the
    figure rather than the texture. See CASUALTY_MAP_RAMP_COLOR_SPAN.
    """
    low, high = span if span is not None else config.CASUALTY_MAP_RAMP_COLOR_SPAN
    return matplotlib.colors.ListedColormap(
        colours(np.linspace(low, high, classes)), name=f"{colours.name}_{classes}"
    )


def class_positions(classes: int, concentration: float | None = None) -> np.ndarray:
    """Where along the ordered values the class breaks are taken, as fractions.

    **Even quantiles give every class the same area, and that is the defect.**
    Cutting at 1/7, 2/7 and so on puts a seventh of the coloured surface in each
    band by construction, so the darkest band is as large as the palest one in
    every map ever drawn this way. What a density map is read for is the opposite:
    a small intense core inside a wide faint surround.

    The positions are therefore bunched towards the top, by `1 - (1 - p) ** k`. At
    k = 1 they are the even quantiles. Above it each successive class covers less
    of the surface than the one below: at k = 2 the seven classes hold roughly
    26, 22, 18, 14, 10, 6 and 2 per cent of it, so the darkest marks the densest
    fiftieth rather than the densest seventh.

    This changes which values the colours mean and not the values themselves, and
    the bar still prints every break, so what each class covers stays checkable.
    """
    k = config.CASUALTY_MAP_RAMP_CONCENTRATION if concentration is None else concentration
    even = np.linspace(0.0, 1.0, classes + 1)
    return 1.0 - (1.0 - even) ** k


def quantile_breaks(
    positive: np.ndarray, classes: int, floor_percentile: float | None = None,
    concentration: float | None = None,
) -> np.ndarray:
    """Class breaks at quantiles of the values drawn, floor to maximum.

    Computed once over every year of a count and then handed to each year, so the
    set of maps shares one ruler. Deriving them per year would give every year the
    same seven colours over its own range, which is precisely the "two maps drawn
    to different rulers" that a shared scale exists to prevent.
    """
    if not positive.size:
        return np.array([1.0, 2.0])
    percentile = _DENSE_FLOOR if floor_percentile is None else floor_percentile
    low = max(float(np.percentile(positive, percentile)), float(np.nextafter(0.0, 1.0)))
    inside = positive[positive >= low]
    breaks = np.unique(np.quantile(inside, class_positions(classes, concentration)))
    if breaks.size < 2:
        breaks = np.array([low, max(float(positive.max()), low * 1.01)])
    breaks[0] = low
    breaks[-1] = max(float(positive.max()), low * 1.01)
    return breaks


def build_ramp(
    positive: np.ndarray,
    breaks: np.ndarray | None,
    *,
    ramp: str,
    classes: int,
    colours,
    floor_percentile: float | None = None,
    concentration: float | None = None,
):
    """The norm the surface is painted through, and the values at its breaks.

    **Quantile classes, not a continuous logarithmic ramp**, and the reason is
    that the surface is smoothed before it is coloured. A logarithmic ramp is the
    right answer for raw counts, which run over four orders of magnitude; a kernel
    has already pulled its values together, so inside the built city the density
    spans about one power of ten while the ramp has to reach down to the empty
    edges. Stretched over both, two thirds of the colours go to the edges and the
    city comes out one flat shade.

    Quantile breaks put the steps where the values are. The bar carries the value
    at every break, so what the classes mean stays checkable.

    `breaks` are the class edges to use instead of this surface's own, which is how
    the years of one count are made to share a scale: they are the quantiles of
    every year pooled, computed once by `quantile_breaks` and handed to each map.
    """
    if breaks is None:
        breaks = quantile_breaks(positive, classes, floor_percentile, concentration)
    low, high = float(breaks[0]), float(breaks[-1])

    if ramp == LOGARITHMIC:
        return matplotlib.colors.LogNorm(vmin=low, vmax=high), np.array([low, high])

    norm = matplotlib.colors.BoundaryNorm(
        breaks, ncolors=len(breaks) - 1, clip=False, extend="neither"
    )
    return norm, breaks


# ---------------------------------------------------------------------------
# What gets drawn
# ---------------------------------------------------------------------------


def count_points(
    affected: pd.DataFrame, count_name: str, units: gpd.GeoDataFrame
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The projected coordinate and weight of every party that carries this count.

    Rows contributing nothing to the count place no point: a crash in which nobody
    died is not on the `killed/` map, and drawing it there at weight zero would put
    a dot where the map claims a death.

    The coordinate is projected here and nowhere else. It travels through the
    tables in degrees, and every metre this module measures — a cell, a bandwidth,
    a scale bar — is measured after this call.
    """
    column = config.MATRIX_COUNTS[count_name]
    carrying = affected[
        (affected[column] > 0)
        & affected[config.POINT_X_COL].notna()
        & affected[config.POINT_Y_COL].notna()
    ]

    projected = gpd.GeoSeries(
        gpd.points_from_xy(carrying[config.POINT_X_COL], carrying[config.POINT_Y_COL]),
        crs=config.SOURCE_CRS,
    ).to_crs(epsg=config.PROJECTED_CRS)

    return (
        projected.x.to_numpy(),
        projected.y.to_numpy(),
        carrying[column].to_numpy(dtype=float),
    )


def accounted_for(affected: pd.DataFrame, count_name: str) -> dict[str, int]:
    """What the year holds, split into what a map can draw and what it cannot.

    The map has to account for the same parties the matrix does, the same way: a
    party whose crash falls outside every unit leaves at aggregation (D11) and it
    leaves the map for the same reason, not silently.
    """
    column = config.MATRIX_COUNTS[count_name]
    carries = affected[column] > 0
    has_point = affected[config.POINT_X_COL].notna() & affected[config.POINT_Y_COL].notna()
    located = affected[config.AREA_CODE_COL].notna()
    return {
        "total": int(affected.loc[carries, column].sum()),
        "drawn": int(affected.loc[carries & has_point & located, column].sum()),
        "outside_every_unit": int(affected.loc[carries & has_point & ~located, column].sum()),
        "no_coordinate": int(affected.loc[carries & ~has_point, column].sum()),
    }


# ---------------------------------------------------------------------------
# The two surfaces
# ---------------------------------------------------------------------------


def _city(units: gpd.GeoDataFrame):
    """The thirty units as one shape, in metres, for clipping and masking."""
    return units.to_crs(epsg=config.PROJECTED_CRS).geometry.union_all()


def _hexbin_surface(axis, x, y, weights, bounds, cell_m: float, cmap, norm):
    """Counts in hexagonal cells of a declared width, and nothing else.

    Hexbin invents nothing: a cell holds the casualties that fell in it and the
    grid is visible, so a reader can see the resolution the figure is drawn at
    rather than having to trust a smooth surface. `gridsize` counts cells across
    the frame, so the declared width in metres is turned into one here and the
    width actually achieved is returned, since it can only be an integer number of
    cells across.
    """
    minx, miny, maxx, maxy = bounds
    across = max(int(round((maxx - minx) / cell_m)), 1)
    achieved = (maxx - minx) / across

    image = axis.hexbin(
        x, y, C=weights, reduce_C_function=np.sum,
        gridsize=across, extent=(minx, maxx, miny, maxy),
        cmap=cmap, norm=norm, mincnt=1, linewidths=0.0, zorder=2,
    )
    return image, achieved


def _kernel_surface(
    axis, x, y, weights, bounds, city, bandwidth_m: float, cell_m: float, cmap, norm,
    breaks=None, render: str | None = None,
):
    """A Gaussian density in casualties per square kilometre, clipped to the units.

    Built by binning onto a fine raster and convolving, rather than by evaluating a
    kernel at every point against every other. The two give the same surface and
    this one is linear in the number of casualties instead of quadratic, which
    matters at two hundred thousand of them; it also makes the bandwidth exactly
    what it says it is — a standard deviation in metres, isotropic, because the
    raster is metric and square.

    **Everything outside the thirty units is masked and not merely covered.** A
    kernel does not know where the city stops, so without the mask the surface
    would spill over the Cerros and past the edge of the study area and invite a
    reader to look for casualties in places the study does not cover.
    """
    minx, miny, maxx, maxy = bounds
    columns = max(int(round((maxx - minx) / cell_m)), 1)
    rows = max(int(round((maxy - miny) / cell_m)), 1)

    binned, x_edges, y_edges = np.histogram2d(
        x, y, bins=[columns, rows], range=[[minx, maxx], [miny, maxy]], weights=weights
    )
    smoothed = gaussian_filter(binned, sigma=bandwidth_m / cell_m, mode="constant")

    # From casualties in a cell to casualties per square kilometre, so the number
    # on the colour bar is a density a reader can carry to another figure rather
    # than an artefact of how fine the raster happens to be.
    cell_km2 = (cell_m / 1000.0) ** 2
    density = smoothed / cell_km2

    centres_x = 0.5 * (x_edges[:-1] + x_edges[1:])
    centres_y = 0.5 * (y_edges[:-1] + y_edges[1:])
    mesh_x, mesh_y = np.meshgrid(centres_x, centres_y, indexing="ij")
    inside = shapely.contains_xy(city, mesh_x, mesh_y)

    surface = np.ma.masked_where(~inside | (density <= 0), density)

    render = render or config.CASUALTY_MAP_SURFACE_RENDER
    if render == CONTOURS and breaks is not None and len(breaks) > 2:
        # **The bands as polygons rather than as pixels.** The surface is already
        # drawn as a handful of classes, so what separates two colours is a
        # contour and not a gradient; marching squares finds that contour on the
        # same grid the density was computed on and fills it as a shape. The
        # result is the same classes at the same breaks, resolution-independent,
        # and the edge between two bands is a smooth polyline instead of a
        # staircase of cells.
        #
        # The mask is what clips it: contouring a masked array stops at the mask,
        # and the mask is the thirty units, so the city's own outline bounds the
        # surface with no separate clip path.
        image = axis.contourf(
            mesh_x, mesh_y, surface,
            levels=breaks, cmap=cmap, norm=norm,
            extend="max",  # a year drawn on pooled breaks may run past the top
            zorder=2,
        )
        # Adjacent fills share an edge, and a renderer that antialiases each of
        # them separately leaves a pale hairline along every boundary. Giving each
        # band an edge of its own face colour closes the seam.
        image.set_edgecolor("face")
        image.set_linewidth(0.0)
    else:
        image = axis.imshow(
            surface.T,
            origin="lower",
            extent=(minx, maxx, miny, maxy),
            cmap=cmap,
            norm=norm,
            interpolation="bilinear",
            zorder=2,
        )
    return image, surface


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


def render(
    units: gpd.GeoDataFrame,
    x: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    out_path: Path,
    *,
    technique: str,
    title: str,
    legend_label: str,
    notes: list[str],
    colormap: str = config.CASUALTY_MAP_COLORMAP,
    ramp: str = config.CASUALTY_MAP_RAMP,
    classes: int = config.CASUALTY_MAP_RAMP_CLASSES,
    colour_span: tuple[float, float] | None = None,
    cell_m: float = config.CASUALTY_MAP_HEX_CELL_M,
    bandwidth_m: float = 200.0,
    raster_cell_m: float = config.CASUALTY_MAP_KERNEL_CELL_M,
    height_in: float = config.CASUALTY_MAP_HEIGHT_IN,
    dpi: int = config.CASUALTY_MAP_DPI,
    breaks: np.ndarray | None = None,
    rasterize_points: bool | None = None,
    style: tuple[float, float] | None = None,
    surface_render: str | None = None,
    floor_percentile: float | None = None,
    concentration: float | None = None,
) -> dict[str, float]:
    """Draw one map and return what the figure had to decide, for the note.

    `breaks` imposes the class edges instead of taking them from this year's own
    surface. It is what lets the years of one count share a scale, the way the
    matrices and the master tables already do; without it a quiet year and a heavy
    one both fill their ramp and look equally intense.
    """
    metric = units.to_crs(epsg=config.PROJECTED_CRS)
    city = metric.geometry.union_all()
    minx, miny, maxx, maxy = metric.total_bounds
    bounds = (minx, miny, maxx, maxy)

    width_in = height_in * (maxx - minx) / (maxy - miny)
    figure, axis = plt.subplots(figsize=(width_in, height_in))

    # The city drawn flat underneath, so a unit with no casualty at all reads as a
    # place the study covers and found nothing, not as a hole in the map.
    metric.plot(ax=axis, color=config.CASUALTY_MAP_GROUND_COLOR, edgecolor="none", zorder=1)

    colours = matplotlib.colormaps[colormap]
    measured: dict[str, float] = {"classes": float(classes)}

    # A first pass over the values the surface will hold, to set the ramp before
    # anything is drawn with it. Counts per cell are extremely skewed — a few
    # intersections carry an enormous share — so the ramp is logarithmic and a
    # linear one would show one bright cell and nothing else.
    if technique == HEXBIN:
        probe_figure, probe_axis = plt.subplots()
        probe, achieved = _hexbin_surface(
            probe_axis, x, y, weights, bounds, cell_m,
            colours, matplotlib.colors.Normalize(),
        )
        values = probe.get_array().compressed() if np.ma.isMaskedArray(probe.get_array()) else probe.get_array()
        values = np.asarray(values, dtype=float)
        plt.close(probe_figure)
        measured["cell_m"] = achieved
    elif technique == KERNEL:
        columns = max(int(round((maxx - minx) / raster_cell_m)), 1)
        rows = max(int(round((maxy - miny) / raster_cell_m)), 1)
        binned, _, _ = np.histogram2d(
            x, y, bins=[columns, rows], range=[[minx, maxx], [miny, maxy]], weights=weights
        )
        smoothed = gaussian_filter(binned, sigma=bandwidth_m / raster_cell_m, mode="constant")
        density = smoothed / ((raster_cell_m / 1000.0) ** 2)
        centres_x = np.linspace(minx, maxx, columns, endpoint=False) + raster_cell_m / 2
        centres_y = np.linspace(miny, maxy, rows, endpoint=False) + raster_cell_m / 2
        mesh_x, mesh_y = np.meshgrid(centres_x, centres_y, indexing="ij")
        values = density[shapely.contains_xy(city, mesh_x, mesh_y) & (density > 0)]
        measured["bandwidth_m"] = bandwidth_m
        measured["raster_cell_m"] = raster_cell_m
    else:
        raise ValueError(f"unknown technique {technique!r}; expected {HEXBIN!r} or {KERNEL!r}")

    positive = values[values > 0]
    norm, breaks = build_ramp(
        positive, breaks, ramp=ramp, classes=classes, colours=colours,
        floor_percentile=floor_percentile, concentration=concentration,
    )
    if ramp == QUANTILE:
        colours = _class_colours(colours, len(breaks) - 1, colour_span)
    # Anything under the floor takes no colour at all and lets the flat city
    # through. Painting it the palest class would say there is something there.
    colours = colours.with_extremes(under=(0, 0, 0, 0))
    measured["ramp_low"], measured["ramp_high"] = float(breaks[0]), float(breaks[-1])

    if technique == HEXBIN:
        image, achieved = _hexbin_surface(axis, x, y, weights, bounds, cell_m, colours, norm)
        measured["cell_m"] = achieved
        # Hexagons straddling the boundary stick out of the city they describe.
        # Clipped rather than redrawn, so no cell's value is altered to fit.
        clip = matplotlib.patches.PathPatch(
            _city_path(metric), transform=axis.transData, facecolor="none", edgecolor="none"
        )
        axis.add_patch(clip)
        image.set_clip_path(clip)
    else:
        image, _ = _kernel_surface(
            axis, x, y, weights, bounds, city, bandwidth_m, raster_cell_m, colours, norm,
            breaks=breaks, render=surface_render,
        )

    # The points over the surface. They are what carries a map of four hundred
    # deaths, where a smoothed surface would be a picture of sampling noise.
    size, alpha = style if style is not None else point_style(len(x))
    axis.scatter(
        x, y,
        s=size,
        c=config.CASUALTY_MAP_POINT_COLOR,
        alpha=alpha,
        linewidths=0.0,
        zorder=3,
        rasterized=(config.CASUALTY_MAP_RASTERIZE_POINTS
                    if rasterize_points is None else rasterize_points),
    )
    measured["point_size"], measured["point_alpha"] = size, alpha
    measured["points"] = float(len(x))

    metric.plot(
        ax=axis, facecolor="none",
        edgecolor=config.MAP_BOUNDARY_COLOR, linewidth=config.MAP_BOUNDARY_WIDTH, zorder=4,
    )

    axis.set_xlim(minx, maxx)
    axis.set_ylim(miny, maxy)
    axis.set_aspect("equal")
    axis.set_axis_off()

    north_arrow(
        axis,
        location=config.MAP_NORTH_ARROW_LOCATION,
        scale=config.MAP_NORTH_ARROW_SCALE,
        base={"facecolor": config.MAP_LABEL_COLOR, "edgecolor": config.MAP_LABEL_COLOR, "linewidth": 0.4},
        fancy=False,
        label={
            "text": "N", "position": "bottom", "ha": "center",
            "fontsize": config.MAP_LABEL_FONT_PT + 1, "color": config.MAP_LABEL_COLOR,
            "fontweight": "normal", "stroke_width": 0,
        },
        shadow=False,
    )
    axis.add_artist(
        ScaleBar(
            1, units="m",
            fixed_value=config.CASUALTY_MAP_SCALEBAR_KM, fixed_units="km",
            location=config.MAP_SCALEBAR_LOCATION,
            frameon=False, color=config.MAP_LABEL_COLOR,
            font_properties={"size": config.MAP_LABEL_FONT_PT + 1},
        )
    )

    divider = make_axes_locatable(axis)
    bar_axis = divider.append_axes(
        config.MAP_COLORBAR_LOCATION, size=config.MAP_COLORBAR_SIZE,
        pad=config.MAP_COLORBAR_PAD, axes_class=matplotlib.axes.Axes,
    )
    bar = figure.colorbar(
        image, cax=bar_axis, orientation="horizontal",
        # The breaks are the whole statement of a quantile ramp, so every one of
        # them is on the bar with its value. A class a reader cannot put a number
        # on is decoration.
        **({"ticks": breaks, "spacing": "uniform"} if ramp == QUANTILE else {"extend": "both"}),
    )
    bar.set_label(legend_label, fontsize=config.MAP_LABEL_FONT_PT + 1, color=config.MAP_LABEL_COLOR)
    bar.ax.tick_params(labelsize=config.MAP_LABEL_FONT_PT, colors=config.MAP_LABEL_COLOR)
    if ramp == QUANTILE:
        bar.ax.xaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda value, _: _break_label(value))
        )
    bar.outline.set_linewidth(0.4)
    bar.outline.set_edgecolor(config.MAP_BOUNDARY_COLOR)

    axis.set_title(title, fontsize=config.MAP_LABEL_FONT_PT + 4, color=config.MAP_LABEL_COLOR, pad=10)
    _caption(figure, bar_axis, notes)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out_path, dpi=dpi, bbox_inches="tight", pad_inches=0.08)
    plt.close(figure)
    return measured


def _caption(figure, bar_axis, notes: list[str]) -> None:
    """The note under the colour bar, wrapped to the width of the map itself.

    Set as one long line it decides how wide the figure is: `bbox_inches="tight"`
    grows the saved image to fit whatever sticks out, so a sentence wider than the
    city adds white space down both sides of every map. Wrapping it to the bar —
    which is exactly as wide as the map — keeps the figure the size of its subject.

    The wrap is measured after a first layout pass rather than guessed, because the
    frame's width follows the footprint of the city and the type does not scale
    with it.
    """
    figure.canvas.draw()
    box = bar_axis.get_position()
    # Below everything the bar occupies, which is not the bar itself: its ticks and
    # its own label hang under the box, and anchoring to the box puts the caption
    # on top of them.
    occupied = bar_axis.get_tightbbox(figure.canvas.get_renderer()).transformed(
        figure.transFigure.inverted()
    )
    width_in = box.width * figure.get_figwidth()

    # Average character width of this face is about half its point size, which is
    # close enough for a wrap: being a character out moves a word, not the margin.
    per_line = max(int(width_in * 72 / (0.5 * config.MAP_LABEL_FONT_PT)), 20)
    wrapped = "\n".join(textwrap.fill(note, per_line) for note in notes)

    figure.text(
        box.x0 + box.width / 2,
        occupied.y0 - config.CASUALTY_MAP_CAPTION_GAP,
        wrapped,
        ha="center", va="top",
        fontsize=config.MAP_LABEL_FONT_PT, color=config.FIGURE_TECHNICAL_LABEL_COLOR,
        linespacing=1.35,
    )


def _break_label(value: float) -> str:
    """A class break, punctuated the way the document punctuates a number.

    Spanish separates thousands with a point and decimals with a comma, and these
    figures are read by a Colombian jury beside a text that does the same.
    """
    if value >= 10:
        return f"{value:,.0f}".replace(",", ".")
    # Enough decimals to tell two breaks apart. A sparse count's lowest classes sit
    # in the hundredths, and printing them all as "0,0" makes the bar say nothing
    # exactly where a reader needs it to say something.
    decimals = 1 if value >= 1 else (2 if value >= 0.1 else 3)
    return f"{value:.{decimals}f}".replace(".", ",")


def _city_path(metric: gpd.GeoDataFrame):
    """The thirty units as one matplotlib path, for clipping the hexagons."""
    vertices: list[tuple[float, float]] = []
    codes: list[int] = []
    for geometry in metric.geometry:
        parts = geometry.geoms if geometry.geom_type == "MultiPolygon" else [geometry]
        for part in parts:
            for ring in [part.exterior, *part.interiors]:
                coordinates = list(ring.coords)
                vertices.extend(coordinates)
                codes.extend(
                    [matplotlib.path.Path.MOVETO]
                    + [matplotlib.path.Path.LINETO] * (len(coordinates) - 2)
                    + [matplotlib.path.Path.CLOSEPOLY]
                )
    return matplotlib.path.Path(vertices, codes)
