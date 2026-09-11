"""Conventions shared by the figures the pipeline draws.

A rule that appears in two modules ends up being two rules the first time one of
them is edited. This module is where a rule several figures depend on lives, so
that changing it changes every figure it governs and no figure it does not.

It draws nothing. It holds the small decisions that have to be made identically
wherever they are made at all.
"""

from __future__ import annotations

from pathlib import Path

try:  # regular package import
    from src import config
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]


def count_figure_directory(
    run_dir: Path, count_name: str, year: int | None, suffix: str = ""
) -> Path:
    """Where every figure of one count, one year and one dataset goes.

    The matrix, the master table and the map of a given count and year are three
    views of one set of events, so they share a folder and a reader opening it
    gets all three rather than having to visit three trees. `year` of None is the
    aggregate over the whole span, which gets a folder of its own for the same
    reason a year does.

    The directory is created here, so a caller never writes the same mkdir twice.
    """
    tag = f"__{suffix}" if suffix else ""
    folder = str(year) if year is not None else config.ALL_YEARS_FOLDER
    directory = run_dir / config.FIGURES_SUBDIR / f"{count_name}{tag}" / folder
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def text_color_on(image, value: float) -> str:
    """The colour a number has to be printed in to read on the cell under it.

    Takes the colour the cell was actually painted — the image's own colormap
    applied through the image's own norm — and decides from its luminance. This
    is the only formulation that survives a change of colormap: a rule written
    against the position of the value along the ramp is a rule about one ramp's
    direction, and viridis runs dark to light while most sequential ramps run the
    other way.

    The value is expected to be inside the norm's range. A caller that clips its
    data to the ends of the ramp passes the clipped value, so the text is decided
    by the colour the reader sees rather than by a colour off the end of the bar.
    """
    red, green, blue, _ = image.cmap(image.norm(value))
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    if luminance < config.FIGURE_LIGHT_TEXT_BELOW_LUMINANCE:
        return config.FIGURE_LIGHT_TEXT_COLOR
    return config.FIGURE_DARK_TEXT_COLOR
