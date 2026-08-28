"""The map of the territorial units: a reference map of the thirty UPL.

The figure answers one question, which is what the study universe looks like on
the ground. A reader who does not know Bogotá cannot judge any result without
it, and with units running from 6.52 to 53.82 square kilometres the shapes
matter as much as the count.

It is drawn from the layer every other stage reads, not from a second copy of
the official cartography. That is the point of putting it here: the map shows
the thirty units of the study because it was built from the same file, and not
because someone filtered a download correctly.

**It is a reference map and not a thematic one.** Nothing is classified and
nothing is measured. The fill says only that this unit is not that one, so it
takes the fewest colours that can say it: four suffice for no two units sharing
a border to share a colour, which is what the four colour theorem asserts and
what a greedy heuristic finds without trouble on thirty polygons. A qualitative
palette of thirty would be a scheme for categorical data used where there is no
category, and thirty hues that mean nothing are thirty hues of noise.

Everything else follows from that. With the fill doing the separating, the
borders can be hairlines of a single colour. Identity is carried by the number
inside each unit, not by its colour.

Run it:

    python -m src.run_pipeline map
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")  # figures are written to disk, never displayed
import matplotlib.pyplot as plt
from matplotlib_map_utils.core.north_arrow import north_arrow
from matplotlib_scalebar.scalebar import ScaleBar
from shapely.geometry import box
from shapely.ops import polylabel

try:  # regular package import
    from src import config
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Who touches whom
# ---------------------------------------------------------------------------


def adjacency(units: gpd.GeoDataFrame) -> list[set[int]]:
    """For each unit, the positions of the units that share a border with it.

    Positions rather than codes, because everything downstream indexes the rows
    of the layer in the order they were read, and translating back and forth
    between two keys is an invitation to get one of them wrong.

    Computed in the metric CRS: the tolerance is a distance, and a distance in
    degrees means nothing.
    """
    metric = units.to_crs(epsg=config.PROJECTED_CRS)
    grown = metric.geometry.buffer(config.MAP_ADJACENCY_TOLERANCE_M)

    neighbours: list[set[int]] = [set() for _ in range(len(metric))]
    index = metric.sindex
    for position, region in enumerate(grown):
        for candidate in index.query(region, predicate="intersects"):
            if int(candidate) != position:
                neighbours[position].add(int(candidate))

    # A border is shared by both sides. Enforcing it costs nothing and lets the
    # rest of the module look at one side only.
    for position, side in enumerate(list(neighbours)):
        for other in side:
            neighbours[other].add(position)
    return neighbours


def colour_classes(neighbours: list[set[int]]) -> list[int]:
    """A proper colouring: no unit shares a class with a unit it touches.

    DSATUR, which repeatedly takes the uncoloured unit facing the most distinct
    colours among its neighbours and gives it the lowest colour none of them
    holds. It is a heuristic and not a proof, so it is not guaranteed to find
    four; on a planar graph of thirty polygons it reliably does, and if it ever
    came back with five the map would still be correct and the run says how many
    it used.

    Deterministic: ties in saturation go to the unit with more neighbours, and
    ties in that to the earlier row, so the same layer always gives the same map.
    """
    count = len(neighbours)
    classes = [-1] * count
    facing: list[set[int]] = [set() for _ in range(count)]

    for _ in range(count):
        position = max(
            (candidate for candidate in range(count) if classes[candidate] < 0),
            key=lambda candidate: (len(facing[candidate]), len(neighbours[candidate]), -candidate),
        )
        classes[position] = next(
            colour for colour in itertools.count() if colour not in facing[position]
        )
        for other in neighbours[position]:
            facing[other].add(classes[position])
    return classes


# ---------------------------------------------------------------------------
# What gets drawn
# ---------------------------------------------------------------------------


def unit_labels(units: gpd.GeoDataFrame) -> list[str]:
    """The identifying number of each unit, without its prefix or leading zero.

    UPL03 becomes 3. The prefix is the same on all thirty and says nothing, and
    the zero is a character competing for room inside the narrowest polygons.
    """
    labels = []
    for code in units[config.AREA_CODE_COL]:
        digits = re.sub(r"\D", "", str(code))
        if not digits:
            raise ValueError(f"unit code {code!r} carries no number to label the map with")
        labels.append(str(int(digits)))
    return labels


def label_anchor(geometry):
    """Where the number goes: the interior point furthest from the boundary.

    The centroid is out, because on a polygon shaped like a crescent or an L it
    falls outside the polygon altogether and several of these units are shaped
    exactly like that. Both representative_point and the pole of inaccessibility
    fix that, but they answer different questions: the first returns some point
    inside, the second the point with the most room around it, and a label needs
    room. On this layer the first leaves as little as 438 m of clearance and the
    second never less than 932 m, which is the difference between five labels
    crossing their own borders and none.

    A multi-part unit is labelled once, on its largest part, because two numbers
    for one unit would read as two units.
    """
    if geometry.geom_type == "MultiPolygon":
        geometry = max(geometry.geoms, key=lambda part: part.area)
    return polylabel(geometry, tolerance=config.MAP_LABEL_ANCHOR_TOLERANCE_M)


@dataclass(frozen=True)
class Composition:
    """Everything the map needs, decided once.

    Carried to the drawing, the checks and the report, so the three cannot end
    up describing three different maps.
    """

    neighbours: list[set[int]]
    classes: list[int]  # position in the layer -> position in the palette
    labels: list[str]

    @property
    def colours_used(self) -> int:
        return len(set(self.classes))

    @property
    def borders(self) -> int:
        return sum(len(side) for side in self.neighbours) // 2

    def colour_of(self, position: int) -> str:
        return config.MAP_PALETTE[self.classes[position]]

    def adjacent_pairs_sharing_a_colour(self) -> list[tuple[int, int]]:
        """The pairs the colouring failed on. Empty is the only acceptable answer."""
        return [
            (one, other)
            for one, side in enumerate(self.neighbours)
            for other in side
            if other > one and self.classes[one] == self.classes[other]
        ]


def compose(units: gpd.GeoDataFrame) -> Composition:
    """Decide the colouring and the labels."""
    neighbours = adjacency(units)
    classes = colour_classes(neighbours)
    if max(classes) >= len(config.MAP_PALETTE):
        raise ValueError(
            f"the colouring needs {max(classes) + 1} colours and the declared palette has "
            f"{len(config.MAP_PALETTE)}; add entries to MAP_PALETTE rather than reusing one"
        )
    return Composition(neighbours=neighbours, classes=classes, labels=unit_labels(units))


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


def render(
    units: gpd.GeoDataFrame,
    composition: Composition,
    out_path: Path,
    scalebar: bool,
) -> list[int]:
    """Draw the map and return the units whose label does not fit inside them.

    Drawn in the metric CRS for two reasons. The scale bar states a distance and
    can only do that where the coordinates are metres; and plotted in degrees a
    figure of Bogotá comes out stretched north to south by about the secant of
    its latitude, which is small enough to pass unnoticed and wrong all the same.
    The CRS does not change with `scalebar`: the second reason stands on its own.
    """
    metric = units.to_crs(epsg=config.PROJECTED_CRS)

    minx, miny, maxx, maxy = metric.total_bounds
    height = config.MAP_FIGURE_HEIGHT_IN
    width = height * (maxx - minx) / (maxy - miny)

    figure, axis = plt.subplots(figsize=(width, height))
    metric.plot(
        ax=axis,
        color=[composition.colour_of(position) for position in range(len(metric))],
        edgecolor=config.MAP_BOUNDARY_COLOR,
        linewidth=config.MAP_BOUNDARY_WIDTH,
    )

    texts = []
    for position, geometry in enumerate(metric.geometry):
        anchor = label_anchor(geometry)
        texts.append(
            axis.text(
                anchor.x,
                anchor.y,
                composition.labels[position],
                ha="center",
                va="center",
                fontsize=config.MAP_LABEL_FONT_PT,
                color=config.MAP_LABEL_COLOR,
            )
        )

    axis.set_aspect("equal")
    axis.set_axis_off()

    # Monochrome and in the colour of the labels. The defaults give a two-tone
    # arrow with an outlined N and a drop shadow, which on a pastel reference
    # map is the loudest thing on the page.
    north_arrow(
        axis,
        location=config.MAP_NORTH_ARROW_LOCATION,
        scale=config.MAP_NORTH_ARROW_SCALE,
        base={"facecolor": config.MAP_LABEL_COLOR, "edgecolor": config.MAP_LABEL_COLOR, "linewidth": 0.4},
        fancy=False,
        label={
            "text": "N",
            "position": "bottom",
            "ha": "center",
            "fontsize": config.MAP_LABEL_FONT_PT + 1,
            "color": config.MAP_LABEL_COLOR,
            "fontweight": "normal",
            "stroke_width": 0,
        },
        shadow=False,
    )
    if scalebar:
        axis.add_artist(
            ScaleBar(
                1,  # the CRS is in metres, so one data unit is one metre
                units="m",
                location=config.MAP_SCALEBAR_LOCATION,
                length_fraction=config.MAP_SCALEBAR_LENGTH_FRACTION,
                frameon=False,
                color=config.MAP_LABEL_COLOR,
                font_properties={"size": config.MAP_LABEL_FONT_PT},
            )
        )

    overflowing = _labels_that_do_not_fit(figure, axis, metric, texts)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Transparent, so the figure carries no white rectangle of its own onto a
    # slide or a page that has a background of its own.
    figure.savefig(out_path, bbox_inches="tight", pad_inches=0.02, transparent=True)
    plt.close(figure)
    return overflowing


def _labels_that_do_not_fit(figure, axis, metric: gpd.GeoDataFrame, texts: list) -> list[int]:
    """Which numbers spill out of the unit they belong to.

    Measured rather than estimated: the figure is laid out once, each label's
    box is read back in display coordinates and converted to metres, and the box
    is tested against its own polygon. Estimating from the area would say a
    6.52 km2 unit has 2.5 km to spare in every direction, which is true of a
    square and false of everything on this map.
    """
    figure.canvas.draw()
    inverse = axis.transData.inverted()

    overflowing = []
    for position, text in enumerate(texts):
        window = text.get_window_extent(renderer=figure.canvas.get_renderer())
        (left, bottom), (right, top) = inverse.transform([(window.x0, window.y0), (window.x1, window.y1)])
        if not metric.geometry.iloc[position].contains(box(left, bottom, right, top)):
            overflowing.append(position)
    return overflowing


def render_figures(
    units: gpd.GeoDataFrame,
    composition: Composition,
    log: RunLog,
) -> tuple[list[Path], list[int]]:
    """Write both maps and say how they came out.

    Two files, identical but for the scale bar: see MAP_SCALEBAR_SUFFIX for why
    that is a second figure rather than a setting. Everything else about them is
    the same, so the labels are measured once, on the plain one.
    """
    directory = log.run_dir / config.FIGURES_SUBDIR / config.MAP_FIGURES_SUBDIR
    stem = "map__territorial_units"
    out_paths = [
        directory / f"{stem}.{config.MAP_FIGURE_FORMAT}",
        directory / f"{stem}{config.MAP_SCALEBAR_SUFFIX}.{config.MAP_FIGURE_FORMAT}",
    ]
    overflowing = render(units, composition, out_paths[0], scalebar=False)
    render(units, composition, out_paths[1], scalebar=True)

    log.info(
        "map: %d units over %d borders, coloured with %d of the %d declared colours",
        len(units),
        composition.borders,
        composition.colours_used,
        len(config.MAP_PALETTE),
    )
    if overflowing:
        names = ", ".join(
            f"{units.iloc[position][config.AREA_CODE_COL]} ({units.iloc[position][config.AREA_NAME_COL]})"
            for position in overflowing
        )
        log.warn(
            "%d label(s) do not fit inside their unit at %.1fpt: %s. Either the font comes down or "
            "the figure goes up; both are one value in the configuration",
            len(overflowing),
            config.MAP_LABEL_FONT_PT,
            names,
        )
    for path in out_paths:
        log.info("wrote %s", path)
    return out_paths, overflowing


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(
    units: gpd.GeoDataFrame,
    composition: Composition,
    out_paths: list[Path],
    overflowing: list[int],
    log: RunLog,
) -> bool:
    """Check the map against the layer it was drawn from."""
    checks: list[tuple[str, bool, str]] = []
    expected = config.active_scale().expected_units

    checks.append((
        "every unit of the layer is drawn",
        len(composition.classes) == len(units) == expected,
        f"{len(units)} drawn, {expected} declared",
    ))

    clashing = composition.adjacent_pairs_sharing_a_colour()
    checks.append((
        "no two units that share a border share a colour",
        not clashing,
        f"{composition.borders} borders, {len(clashing)} sharing a colour",
    ))

    checks.append((
        "four colours were enough",
        composition.colours_used <= 4,
        f"{composition.colours_used} used",
    ))

    isolated = [position for position, side in enumerate(composition.neighbours) if not side]
    checks.append((
        "the layer is one footprint, with no unit off on its own",
        not isolated,
        f"{len(isolated)} unit(s) touching nothing",
    ))

    checks.append((
        "every label fits inside the unit it names",
        not overflowing,
        f"{len(overflowing)} of {len(units)} spilling over",
    ))

    written = [path for path in out_paths if path.exists() and path.stat().st_size > 0]
    checks.append((
        "both figures are on disk and neither is empty",
        len(written) == len(out_paths),
        ", ".join(f"{path.name} {path.stat().st_size:,} bytes" for path in written) or "none written",
    ))

    width = max(len(name) for name, _, _ in checks)
    lines = [f"{'check'.ljust(width)}  {'result':>8}  detail", f"{'-' * width}  {'-' * 8}  ------"]
    for name, ok, detail in checks:
        lines.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("map verification:", "\n".join(lines))

    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("map verification FAILED")
    return passed


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def report(units: gpd.GeoDataFrame, composition: Composition, log: RunLog) -> None:
    """What the map shows, in numbers, for whoever reads the log instead."""
    metric = units.to_crs(epsg=config.PROJECTED_CRS)
    areas = (metric.geometry.area / 1e6).to_numpy()
    names = units[config.AREA_NAME_COL].to_numpy()
    codes = units[config.AREA_CODE_COL].to_numpy()
    degrees = [len(side) for side in composition.neighbours]

    smallest, largest = int(areas.argmin()), int(areas.argmax())
    log.info(
        "unit areas: smallest %.2f km2 (%s %s), largest %.2f km2 (%s %s)",
        areas[smallest],
        codes[smallest],
        names[smallest],
        areas[largest],
        codes[largest],
        names[largest],
    )
    log.info(
        "borders: %d in total, %.1f neighbours per unit on average, most is %d",
        composition.borders,
        sum(degrees) / len(degrees),
        max(degrees),
    )

    per_colour = [composition.classes.count(colour) for colour in range(composition.colours_used)]
    log.info(
        "colours: %s",
        ", ".join(
            f"{config.MAP_PALETTE[colour]} on {count} unit(s)"
            for colour, count in enumerate(per_colour)
        ),
    )
