"""rho(t): the share of two-party crashes in which both parties suffered casualties.

For a pair of actor types, rho is

    crashes of that pair where both parties had casualties
    -------------------------------------------------------
    all crashes of that pair

between 0 and 1. It is a diagnostic, not a result of the study. Whether both
parties of a collision come out of it with casualties is close to physical, so an
abrupt change between two consecutive years is evidence about how casualties were
recorded that year, not about the crashes.

Two things about the denominator decide where this has to be computed.

First, every crash in the sources has at least one casualty — that is what puts it
in the sources at all. So one of the two parties is always affected, and rho is
really asking how often the *other* one was too.

Second, the denominator counts crashes where only one party was affected, and the
matrix cannot see those: by the time a party with no casualties has been dropped,
a crash where one party was hurt looks exactly like a crash where both were. rho
is therefore computed from the party universe, before that filter, and it cannot
be derived from the aggregated matrix.

This sits beside the pipeline rather than inside it: nothing downstream consumes
rho, and the matrix does not change because of it.

Run it:

    python -m src.run_pipeline rho
"""

from __future__ import annotations

import itertools
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # figures are written to disk, never displayed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:  # regular package import
    from src import config
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# Internal working columns, dropped before the result is returned.
_RANK = "_rank"
_AFFECTED = "_affected"

# Short labels for logs and figure titles only. The exported table always carries
# the full category names, because that is what joins to the matrix.
_SHORT_LABEL = {
    config.PEDESTRIAN: "PED",
    config.BICYCLE: "BIC",
    config.MOTORCYCLE: "MOT",
    config.CAR: "CAR",
    config.PUBLIC_TRANSPORT: "PUB",
}


def _short_pair(pair_label: str) -> str:
    return config.RHO_PAIR_SEPARATOR.join(
        _SHORT_LABEL.get(side, side) for side in pair_label.split(config.RHO_PAIR_SEPARATOR)
    )


# ---------------------------------------------------------------------------
# From parties to crashes
# ---------------------------------------------------------------------------


def build_crash_pairs(universe: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """One row per two-party crash: its pair of actor types, and whether both were hurt.

    Single-party crashes leave here. They have no counterpart, so there is no pair
    to ask the question about, and counting them anywhere in rho would mean
    deciding what "both parties" means when there is only one.
    """
    rows_in = len(universe)
    party_count = universe.groupby(config.CRASH_ID_COL)[config.PARTY_ID_COL].transform("size")
    two_party = universe[party_count == 2].copy()

    single_party_rows = rows_in - len(two_party)
    crashes = len(two_party) // 2

    # The two sides are ordered canonically, so a pair has one representation and
    # no orientation. Ranking by actor type and breaking ties on the party
    # identifier keeps that order stable when both parties are of the same type.
    rank = {actor: position for position, actor in enumerate(config.RHO_PAIR_ORDER)}
    two_party[_RANK] = two_party[config.PARTY_TYPE_COL].map(lambda actor: rank.get(actor, len(rank)))
    two_party[_AFFECTED] = (
        two_party[config.PERSONS_INJURED_COL] + two_party[config.PERSONS_KILLED_COL]
    ) > 0
    two_party = two_party.sort_values(
        [config.CRASH_ID_COL, _RANK, config.PARTY_ID_COL], kind="stable"
    )
    position = two_party.groupby(config.CRASH_ID_COL).cumcount()

    first = two_party[position == 0].set_index(config.CRASH_ID_COL)
    second = two_party[position == 1].set_index(config.CRASH_ID_COL)
    pairs = pd.DataFrame(
        {
            config.PAIR_FIRST_COL: first[config.PARTY_TYPE_COL],
            config.PAIR_SECOND_COL: second[config.PARTY_TYPE_COL].reindex(first.index),
            _AFFECTED: (first[_AFFECTED] & second[_AFFECTED].reindex(first.index)),
        }
    ).reset_index()

    if len(pairs) != crashes:
        raise RuntimeError(
            f"{crashes} two-party crashes produced {len(pairs)} pair rows; "
            "the two parties of a crash did not pair up one to one"
        )

    log.record(
        "collapse parties into two-party crashes",
        rows_in=rows_in,
        rows_out=len(pairs),
        changes=[
            (-single_party_rows, "parties of single-party crashes, which have no counterpart to pair with"),
            (-crashes, "the second party of each crash, folded into the row of its crash"),
        ],
        notes=[
            f"{int(pairs[_AFFECTED].sum()):,} of {len(pairs):,} crashes have casualties on both parties",
        ],
    )
    return pairs


def restrict_to_pairs(pairs: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """Keep the crashes belonging to one of the nine pairs.

    The three exclusions are counted in sequence, so a crash removed for more than
    one reason is attributed to the first that applies and the balance closes.
    """
    rows_in = len(pairs)
    sides = [config.PAIR_FIRST_COL, config.PAIR_SECOND_COL]

    residual = pairs[sides].eq(config.OTHER).any(axis=1)
    kept = pairs[~residual]
    dropped_residual = rows_in - len(kept)

    same_type = kept[config.PAIR_FIRST_COL] == kept[config.PAIR_SECOND_COL]
    before = len(kept)
    kept = kept[~same_type]
    dropped_same = before - len(kept)

    has_primary = kept[sides].isin(config.RHO_PRIMARY_TYPES).any(axis=1)
    before = len(kept)
    kept = kept[has_primary].copy()
    dropped_no_primary = before - len(kept)

    kept[config.PAIR_COL] = [
        config.rho_pair_label(first, second)
        for first, second in zip(kept[config.PAIR_FIRST_COL], kept[config.PAIR_SECOND_COL])
    ]

    # The three rules above should leave exactly the nine declared pairs. If they
    # do not, one of them is wrong, and it is better to find out here than to see
    # a tenth column appear in the output.
    unexpected = sorted(set(kept[config.PAIR_COL]) - set(config.RHO_PAIR_LABELS))
    if unexpected:
        raise RuntimeError(f"pairs outside the nine declared ones reached the table: {unexpected}")

    log.record(
        "restrict to the nine pairs",
        rows_in=rows_in,
        rows_out=len(kept),
        changes=[
            (-dropped_residual, f"crashes with a party in the residual category {config.OTHER}"),
            (-dropped_same, "crashes between two parties of the same type, which are not one of the pairs"),
            (
                -dropped_no_primary,
                f"crashes with no {', '.join(config.RHO_PRIMARY_TYPES).lower()} party, "
                "so neither side is one of the modes that impose the risk",
            ),
        ],
        notes=[f"{len(config.RHO_PAIRS)} pairs: {', '.join(config.RHO_PAIR_LABELS)}"],
    )
    return kept


def place_in_time_and_space(pairs: pd.DataFrame, crash_attrs: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """Attach the year and the territorial unit of each crash, and drop the unlocated.

    Same source of truth as the matrix (parties.crash_attributes), so a crash lands
    in the same cell in both tables. Crashes outside every unit leave here for the
    reason given in D11: a cell is identified by its unit, and the city total is
    the sum over the units, so a crash with no unit has no place in either.
    """
    rows_in = len(pairs)
    placed = pairs.merge(
        crash_attrs[[config.CRASH_ID_COL, config.YEAR_COL, config.AREA_CODE_COL, config.AREA_NAME_COL]],
        on=config.CRASH_ID_COL,
        how="left",
    )
    if len(placed) != rows_in:
        raise RuntimeError("attaching crash attributes changed the row count")

    located = placed[placed[config.AREA_CODE_COL].notna()].copy()
    located[config.YEAR_COL] = located[config.YEAR_COL].astype("Int64")

    log.record(
        "restrict to located crashes",
        rows_in=rows_in,
        rows_out=len(located),
        changes=[
            (
                -(rows_in - len(located)),
                "crashes whose point falls outside every territorial unit, which have no cell to go to",
            )
        ],
        notes=[
            "the city total is the sum over the units, so a crash the units cannot hold "
            "cannot be in the city total either",
        ],
    )
    return located


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _complete_grid(area_codes: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        itertools.product(area_codes, list(config.STUDY_YEARS), config.RHO_PAIR_LABELS),
        columns=[config.AREA_CODE_COL, config.YEAR_COL, config.PAIR_COL],
    )


def _aggregate(crashes: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return (
        crashes.groupby(keys, dropna=False, observed=True)[_AFFECTED]
        .agg(**{config.RHO_NUMERATOR_COL: "sum", config.RHO_DENOMINATOR_COL: "size"})
        .reset_index()
    )


def build_long_table(
    crashes: pd.DataFrame,
    units: pd.DataFrame,
    log: RunLog,
    scale: config.TerritorialScale | None = None,
) -> pd.DataFrame:
    """Both levels of aggregation on one complete grid, with rho undefined where empty.

    The two levels are different quantities and are never mixed: the city value is
    the sum of numerators over the sum of denominators, not the average of the unit
    values. Which one a row is comes from its own column, not from what its unit
    code happens to look like.
    """
    scale = scale or config.active_scale()
    area_codes = units[config.AREA_CODE_COL].tolist()

    # -- per unit and year --------------------------------------------------
    observed = _aggregate(crashes, [config.AREA_CODE_COL, config.YEAR_COL, config.PAIR_COL])
    grid = _complete_grid(area_codes)
    grid[config.YEAR_COL] = grid[config.YEAR_COL].astype("Int64")
    observed[config.YEAR_COL] = observed[config.YEAR_COL].astype("Int64")

    by_unit = grid.merge(observed, on=[config.AREA_CODE_COL, config.YEAR_COL, config.PAIR_COL], how="left")
    unmatched = len(observed) - len(
        observed.merge(grid, on=[config.AREA_CODE_COL, config.YEAR_COL, config.PAIR_COL], how="inner")
    )
    if unmatched:
        raise RuntimeError(
            f"{unmatched} observed combination(s) fall outside the declared grid; "
            "the unit roster or the pair list is incomplete"
        )
    by_unit[config.AGGREGATION_LEVEL_COL] = config.UNIT_LEVEL

    log.record(
        "aggregate rho onto the unit grid",
        rows_in=len(crashes),
        rows_out=len(by_unit),
        changes=[
            (len(observed) - len(crashes), "crashes collapsed into the unit-year-pair cells they share"),
            (
                len(by_unit) - len(observed),
                "grid cells with no crash of that pair, kept with a zero denominator and rho undefined",
            ),
        ],
        notes=[
            f"grid = {len(area_codes)} units x {len(config.STUDY_YEARS)} years x "
            f"{len(config.RHO_PAIRS)} pairs",
        ],
    )

    # -- whole city, by year ------------------------------------------------
    city_observed = _aggregate(crashes, [config.YEAR_COL, config.PAIR_COL])
    city_grid = _complete_grid([config.CITY_AREA_CODE])
    city_grid[config.YEAR_COL] = city_grid[config.YEAR_COL].astype("Int64")
    city_observed[config.YEAR_COL] = city_observed[config.YEAR_COL].astype("Int64")

    by_city = city_grid.merge(city_observed, on=[config.YEAR_COL, config.PAIR_COL], how="left")
    by_city[config.AGGREGATION_LEVEL_COL] = config.CITY_LEVEL

    log.record(
        "aggregate rho for the whole city",
        rows_in=len(crashes),
        rows_out=len(by_city),
        changes=[
            (
                len(city_observed) - len(crashes),
                "the same crashes collapsed by year and pair, with no unit dimension",
            ),
            (
                len(by_city) - len(city_observed),
                "year-pair combinations with no crash at all, kept with rho undefined",
            ),
        ],
        notes=[
            "sum of numerators over sum of denominators; this is not the average of the unit values",
        ],
    )

    # -- one table ----------------------------------------------------------
    long_table = pd.concat([by_unit, by_city], ignore_index=True)
    counts = [config.RHO_NUMERATOR_COL, config.RHO_DENOMINATOR_COL]
    long_table[counts] = long_table[counts].fillna(0).astype(int)

    long_table[config.SCALE_COL] = scale.label
    names = dict(zip(units[config.AREA_CODE_COL], units[config.AREA_NAME_COL]))
    names[config.CITY_AREA_CODE] = config.CITY_AREA_NAME
    long_table[config.AREA_NAME_COL] = long_table[config.AREA_CODE_COL].map(names)

    sides = long_table[config.PAIR_COL].str.split(config.RHO_PAIR_SEPARATOR, expand=True)
    long_table[config.PAIR_FIRST_COL] = sides[0]
    long_table[config.PAIR_SECOND_COL] = sides[1]

    # Undefined, not zero: with no crash of the pair there is nothing to take a
    # share of, and a zero there would read as "both parties were never hurt".
    denominator = long_table[config.RHO_DENOMINATOR_COL]
    long_table[config.RHO_COL] = (
        (long_table[config.RHO_NUMERATOR_COL] / denominator.where(denominator > 0)).astype("Float64")
    )

    ordered = [
        config.SCALE_COL,
        config.AGGREGATION_LEVEL_COL,
        config.AREA_CODE_COL,
        config.AREA_NAME_COL,
        config.YEAR_COL,
        config.PAIR_COL,
        config.PAIR_FIRST_COL,
        config.PAIR_SECOND_COL,
        config.RHO_NUMERATOR_COL,
        config.RHO_DENOMINATOR_COL,
        config.RHO_COL,
    ]
    long_table = long_table[ordered].sort_values(
        [config.AGGREGATION_LEVEL_COL, config.AREA_CODE_COL, config.YEAR_COL, config.PAIR_COL],
        kind="stable",
    ).reset_index(drop=True)

    log.record(
        "assemble the rho table",
        rows_in=len(by_unit),
        rows_out=len(long_table),
        changes=[(len(by_city), f"city rows, marked {config.CITY_LEVEL} in {config.AGGREGATION_LEVEL_COL}")],
        notes=[
            f"{int(long_table[config.RHO_COL].isna().sum()):,} cells have an empty denominator "
            "and carry no rho",
        ],
    )
    return long_table


def city_table(long_table: pd.DataFrame, column: str) -> pd.DataFrame:
    """One city-level column as a year-by-pair table, in the declared pair order.

    Reshaped with pivot rather than pivot_table on purpose. There is exactly one
    city row per year and pair, so no aggregation is needed, and an aggregating
    reshape would sum a cell whose rho is undefined into a confident 0.000 — which
    is the one thing this table must never say. pivot also raises if the one-row
    assumption is ever false, instead of quietly averaging.
    """
    city = long_table[long_table[config.AGGREGATION_LEVEL_COL] == config.CITY_LEVEL]
    table = city.pivot(index=config.YEAR_COL, columns=config.PAIR_COL, values=column)
    return table.reindex(index=list(config.STUDY_YEARS), columns=list(config.RHO_PAIR_LABELS))


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export(long_table: pd.DataFrame, log: RunLog) -> dict[str, Path]:
    """Write the analysis table and the city views, and return the paths."""
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    long_path = data_dir / f"{config.ANALYSIS_PREFIX}__rho_long.csv"
    long_table.to_csv(long_path, index=False, encoding="utf-8")
    long_table.to_parquet(long_path.with_suffix(".parquet"))
    paths["long"] = long_path

    # The denominator is exported beside rho at every level, and on its own for
    # the city, because a rho without its denominator invites reading noise as
    # signal and that is the one mistake this table can cause.
    for name, column in (("rho", config.RHO_COL), ("denominators", config.RHO_DENOMINATOR_COL)):
        path = data_dir / f"{config.PRESENTATION_PREFIX}__rho_city_{name}__by_year.csv"
        city_table(long_table, column).to_csv(path, encoding="utf-8")
        paths[f"city_{name}"] = path

    log.info("exported 1 analysis table and %d presentation tables to %s/", len(paths) - 1, config.DATA_SUBDIR)
    return paths


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def _style_panel(axis, title: str) -> None:
    axis.set_ylim(-0.03, 1.03)
    axis.set_xlim(config.FIRST_YEAR - 0.5, config.LAST_YEAR + 0.5)
    axis.set_title(title, fontsize=9)
    axis.grid(True, color=config.RHO_GRID_COLOR, linewidth=0.6)
    axis.set_axisbelow(True)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    axis.tick_params(labelsize=7)


def _draw_series(axis, years, values, color: str, label: str | None = None) -> None:
    """One rho series, every point drawn the same way.

    No mark distinguishes a value by how many crashes are behind it. A rho of one
    over two crashes is as much the measurement as a rho of one over two thousand,
    and singling it out in the figure is a cut applied by eye. The only gap in the
    line is where the denominator is zero: there rho does not exist, the value is
    missing rather than small, and matplotlib leaves the break by itself.

    The denominator is still reported everywhere it belongs — beside rho in every
    row of the exported table, in the panel titles, and as a figure of its own.
    """
    axis.plot(years, values, color=color, linewidth=1.6, zorder=3, label=label)
    axis.plot(
        years,
        np.asarray(values, dtype=float),
        linestyle="none",
        marker="o",
        markersize=3.4,
        markerfacecolor=color,
        markeredgecolor=color,
        zorder=4,
    )


def _city_series(long_table: pd.DataFrame, pair: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    city = long_table[
        (long_table[config.AGGREGATION_LEVEL_COL] == config.CITY_LEVEL)
        & (long_table[config.PAIR_COL] == pair)
    ].sort_values(config.YEAR_COL)
    return (
        city[config.YEAR_COL].to_numpy(dtype=int),
        city[config.RHO_COL].astype(float).to_numpy(),
        city[config.RHO_DENOMINATOR_COL].to_numpy(dtype=int),
    )


def _render_city(long_table: pd.DataFrame, out_path: Path) -> None:
    """The nine pairs for the whole city, one panel each.

    Faceted rather than nine lines on one pair of axes: nine simultaneous series
    cannot be told apart by colour, and the question asked of this figure is
    whether a given pair jumps between two years, which is a question about one
    series at a time.
    """
    fig, axes = plt.subplots(3, 3, figsize=(12, 9), sharex=True, sharey=True)
    for axis, pair in zip(axes.ravel(), config.RHO_PAIR_LABELS):
        years, values, _ = _city_series(long_table, pair)
        _draw_series(axis, years, values, config.RHO_SERIES_COLOR)
        _style_panel(axis, _short_pair(pair))

    for axis in axes[-1]:
        axis.set_xlabel("year", fontsize=8)
    for axis in axes[:, 0]:
        axis.set_ylabel("rho", fontsize=8)

    fig.suptitle(
        f"rho(t) — both parties with casualties, whole city ({config.active_scale().label} scale)\n"
        "a gap in a line is a year with no crash of that pair, where rho does not exist",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def _render_city_denominators(long_table: pd.DataFrame, out_path: Path) -> None:
    """The denominators behind the figure above, on the same layout.

    Its own figure rather than a second axis on the first: two scales on one plot
    make the reader compare two rulers drawn as one.
    """
    fig, axes = plt.subplots(3, 3, figsize=(12, 9), sharex=True, sharey=True)
    for axis, pair in zip(axes.ravel(), config.RHO_PAIR_LABELS):
        years, _, denominators = _city_series(long_table, pair)
        axis.plot(years, denominators, color=config.RHO_SERIES_COLOR, linewidth=1.6)
        axis.set_yscale("log")
        axis.set_title(_short_pair(pair), fontsize=9)
        axis.grid(True, color=config.RHO_GRID_COLOR, linewidth=0.6)
        axis.set_axisbelow(True)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
        axis.tick_params(labelsize=7)

    for axis in axes[-1]:
        axis.set_xlabel("year", fontsize=8)
    for axis in axes[:, 0]:
        axis.set_ylabel("crashes", fontsize=8)

    fig.suptitle(
        "crashes behind each rho, whole city (logarithmic)\n"
        "the denominator of the figure beside it, on the same layout",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def _render_units_for_pair(long_table: pd.DataFrame, pair: str, units: pd.DataFrame, out_path: Path) -> None:
    """One pair across every unit, one panel per unit, with the city curve behind it.

    Thirty units by nine pairs is 270 series. Drawn as thirty figures of nine
    lines each they would be unreadable, and as one figure they would be a mess of
    hues, so the split is one figure per pair: every panel then answers the same
    question for a different place, and the grey city curve gives each panel the
    same reference to be judged against.
    """
    city_years, city_values, _ = _city_series(long_table, pair)

    columns = 5
    rows = int(np.ceil(len(units) / columns))
    fig, axes = plt.subplots(rows, columns, figsize=(15, 2.1 * rows), sharex=True, sharey=True)
    flat = axes.ravel()

    subset = long_table[
        (long_table[config.AGGREGATION_LEVEL_COL] == config.UNIT_LEVEL)
        & (long_table[config.PAIR_COL] == pair)
    ]
    for axis, (code, name) in zip(flat, zip(units[config.AREA_CODE_COL], units[config.AREA_NAME_COL])):
        unit = subset[subset[config.AREA_CODE_COL] == code].sort_values(config.YEAR_COL)
        axis.plot(city_years, city_values, color=config.RHO_REFERENCE_COLOR, linewidth=1.2,
                  zorder=2, label="whole city")
        _draw_series(
            axis,
            unit[config.YEAR_COL].to_numpy(dtype=int),
            unit[config.RHO_COL].astype(float).to_numpy(),
            config.RHO_SERIES_COLOR,
            label=str(code),
        )
        total = int(unit[config.RHO_DENOMINATOR_COL].sum())
        _style_panel(axis, f"{code} {name} ({total:,})")

    for axis in flat[len(units):]:  # trailing panels of an incomplete last row
        axis.set_visible(False)

    handles = [
        plt.Line2D([], [], color=config.RHO_SERIES_COLOR, linewidth=1.6, label="this unit"),
        plt.Line2D([], [], color=config.RHO_REFERENCE_COLOR, linewidth=1.2, label="whole city"),
    ]
    # Anchored in the margin the title reserves. Left to its own devices the
    # legend lands on top of the last panel's data.
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.995, 0.995), ncol=2,
               fontsize=9, frameon=False)
    fig.suptitle(
        f"rho(t) for {_short_pair(pair)} by unit — {pair}\n"
        "panel title carries the crashes behind the whole series; a gap is a year with no crash",
        fontsize=11,
        x=0.4,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def render_figures(long_table: pd.DataFrame, units: pd.DataFrame, log: RunLog) -> int:
    figures_dir = log.run_dir / config.FIGURES_SUBDIR / "rho"
    figures_dir.mkdir(parents=True, exist_ok=True)

    # Panels go in unit-code order rather than in whatever order the shapefile
    # happens to store, so a panel can be found and two runs look the same.
    units = units.sort_values(config.AREA_CODE_COL, kind="stable").reset_index(drop=True)

    _render_city(long_table, figures_dir / "rho_city__by_pair.png")
    _render_city_denominators(long_table, figures_dir / "rho_city__denominators.png")
    written = 2

    units_dir = figures_dir / "by_unit"
    units_dir.mkdir(parents=True, exist_ok=True)
    for pair in config.RHO_PAIR_LABELS:
        _render_units_for_pair(long_table, pair, units, units_dir / f"rho_units__{pair}.png")
        written += 1

    log.info("wrote %d rho figures under %s/rho/", written, config.FIGURES_SUBDIR)
    return written


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(long_table: pd.DataFrame, crashes: pd.DataFrame, units: pd.DataFrame, log: RunLog) -> bool:
    """Check the table against its own definition and against what entered it."""
    checks: list[tuple[str, bool, str]] = []

    numerator = long_table[config.RHO_NUMERATOR_COL]
    denominator = long_table[config.RHO_DENOMINATOR_COL]

    over = int((numerator > denominator).sum())
    checks.append(("numerator never exceeds denominator", over == 0, f"{over} row(s) above"))

    defined = long_table[config.RHO_COL].notna()
    outside = int(((long_table.loc[defined, config.RHO_COL] < 0) | (long_table.loc[defined, config.RHO_COL] > 1)).sum())
    checks.append(("rho within [0, 1] where defined", outside == 0, f"{int(defined.sum()):,} defined, {outside} outside"))

    mismatch = int((defined != (denominator > 0)).sum())
    checks.append((
        "rho defined exactly where the denominator is not zero",
        mismatch == 0,
        f"{int((denominator == 0).sum()):,} empty cells, {mismatch} disagreements",
    ))

    by_unit = long_table[long_table[config.AGGREGATION_LEVEL_COL] == config.UNIT_LEVEL]
    by_city = long_table[long_table[config.AGGREGATION_LEVEL_COL] == config.CITY_LEVEL]
    unit_totals = by_unit.groupby(config.YEAR_COL)[[config.RHO_NUMERATOR_COL, config.RHO_DENOMINATOR_COL]].sum()
    city_totals = by_city.groupby(config.YEAR_COL)[[config.RHO_NUMERATOR_COL, config.RHO_DENOMINATOR_COL]].sum()
    same_denominators = unit_totals[config.RHO_DENOMINATOR_COL].equals(city_totals[config.RHO_DENOMINATOR_COL])
    same_numerators = unit_totals[config.RHO_NUMERATOR_COL].equals(city_totals[config.RHO_NUMERATOR_COL])
    disagreeing = int((unit_totals[config.RHO_DENOMINATOR_COL] != city_totals[config.RHO_DENOMINATOR_COL]).sum())
    checks.append((
        "units sum to the city total, year by year",
        same_denominators and same_numerators,
        f"{len(city_totals)} years, {disagreeing} disagreeing",
    ))

    # A crash belongs to one pair and is counted once. If any were counted twice,
    # the denominators would total more than the crashes that entered.
    entered = len(crashes)
    counted = int(by_city[config.RHO_DENOMINATOR_COL].sum())
    checks.append((
        "every crash counted once, in one pair only",
        entered == counted,
        f"{entered:,} in, {counted:,} counted",
    ))

    expected_rows = (len(units) + 1) * len(config.STUDY_YEARS) * len(config.RHO_PAIRS)
    checks.append((
        "grid has exactly the declared number of cells",
        len(long_table) == expected_rows,
        f"{len(long_table):,} of {expected_rows:,}",
    ))

    width = max(len(name) for name, _, _ in checks)
    lines = [f"{'check'.ljust(width)}  {'result':>8}  detail", f"{'-' * width}  {'-' * 8}  ------"]
    for name, ok, detail in checks:
        lines.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("rho verification:", "\n".join(lines))

    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("rho verification FAILED")
    return passed


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _pair_columns_header(label: str) -> str:
    return f"{label:>6}  " + "  ".join(f"{_short_pair(pair):>9}" for pair in config.RHO_PAIR_LABELS)


def report(long_table: pd.DataFrame, log: RunLog) -> None:
    rho_by_year = city_table(long_table, config.RHO_COL)
    denominators_by_year = city_table(long_table, config.RHO_DENOMINATOR_COL)

    lines = [_pair_columns_header("year")]
    lines.append(f"{'-' * 6}  " + "  ".join("-" * 9 for _ in config.RHO_PAIR_LABELS))
    for year in config.STUDY_YEARS:
        cells = []
        for pair in config.RHO_PAIR_LABELS:
            value = rho_by_year.loc[year, pair]
            cells.append(f"{'-':>9}" if pd.isna(value) else f"{float(value):>9.3f}")
        lines.append(f"{year:>6}  " + "  ".join(cells))
    log.table("rho by year, whole city:", "\n".join(lines))

    lines = [_pair_columns_header("year")]
    lines.append(f"{'-' * 6}  " + "  ".join("-" * 9 for _ in config.RHO_PAIR_LABELS))
    for year in config.STUDY_YEARS:
        cells = [f"{int(denominators_by_year.loc[year, pair]):>9,}" for pair in config.RHO_PAIR_LABELS]
        lines.append(f"{year:>6}  " + "  ".join(cells))
    totals = [f"{int(denominators_by_year[pair].sum()):>9,}" for pair in config.RHO_PAIR_LABELS]
    lines.append(f"{'-' * 6}  " + "  ".join("-" * 9 for _ in config.RHO_PAIR_LABELS))
    lines.append(f"{'total':>6}  " + "  ".join(totals))
    log.table("crashes behind each rho above (the denominator):", "\n".join(lines))

    # -- year-pair combinations the city has no crash for --------------------
    # Named one by one rather than counted. A pair with no crash at all in a given
    # year is not a small rho, it is the absence of the observation, and at city
    # scale that says something about the sources rather than about the city.
    empty_city = [
        (int(year), pair)
        for pair in config.RHO_PAIR_LABELS
        for year in config.STUDY_YEARS
        if int(denominators_by_year.loc[year, pair]) == 0
    ]
    if empty_city:
        by_year: dict[int, list[str]] = {}
        for year, pair in empty_city:
            by_year.setdefault(year, []).append(_short_pair(pair))
        lines = [f"{len(empty_city)} year-pair combination(s) have no crash at all in the whole city:"]
        for year, pairs_of_year in sorted(by_year.items()):
            lines.append(f"    {year}: {', '.join(pairs_of_year)}")
        lines.append("")
        lines.append("rho is undefined there and is exported empty, never as zero")
        log.table("where the city has no crash of a pair:", "\n".join(lines))

    # -- year-on-year jumps -------------------------------------------------
    jumps: list[tuple[float, str, int, float, float, int, int]] = []
    for pair in config.RHO_PAIR_LABELS:
        series = rho_by_year[pair]
        for year in list(config.STUDY_YEARS)[1:]:
            before, after = series.loc[year - 1], series.loc[year]
            if pd.isna(before) or pd.isna(after):
                continue
            change = float(after) - float(before)
            jumps.append((
                abs(change), pair, year, float(before), float(after),
                int(denominators_by_year.loc[year - 1, pair]), int(denominators_by_year.loc[year, pair]),
            ))
    jumps.sort(reverse=True)

    lines = [
        f"{'pair':<10}  {'change':>18}  {'rho before':>10}  {'rho after':>10}  {'delta':>7}  {'crashes':>15}",
        f"{'-' * 10}  {'-' * 18}  {'-' * 10}  {'-' * 10}  {'-' * 7}  {'-' * 15}",
    ]
    flagged = [jump for jump in jumps if jump[0] >= config.RHO_JUMP_THRESHOLD]
    for _, pair, year, before, after, den_before, den_after in flagged:
        lines.append(
            f"{_short_pair(pair):<10}  {f'{year - 1} to {year}':>18}  {before:>10.3f}  {after:>10.3f}  "
            f"{after - before:>+7.3f}  {f'{den_before:,} to {den_after:,}':>15}"
        )
    if not flagged:
        lines.append(f"(no year-on-year change reaches {config.RHO_JUMP_THRESHOLD:.2f})")
    lines.append("")
    largest = jumps[0] if jumps else None
    if largest:
        lines.append(
            f"largest single jump: {_short_pair(largest[1])} between {largest[2] - 1} and {largest[2]}, "
            f"{largest[3]:.3f} to {largest[4]:.3f} ({largest[4] - largest[3]:+.3f})"
        )
    log.table(
        f"year-on-year changes of at least {config.RHO_JUMP_THRESHOLD:.2f}, whole city:",
        "\n".join(lines),
    )

    # -- how thin the unit grid is -----------------------------------------
    by_unit = long_table[long_table[config.AGGREGATION_LEVEL_COL] == config.UNIT_LEVEL]
    denominator = by_unit[config.RHO_DENOMINATOR_COL]
    empty = int((denominator == 0).sum())
    thin = int((denominator < config.RHO_SPARSE_DENOMINATOR).sum())
    lines = [
        f"cells by unit and year          : {len(by_unit):,}",
        f"denominator below {config.RHO_SPARSE_DENOMINATOR:<2}            : {thin:,} ({100 * thin / len(by_unit):.2f}%)",
        f"of which empty (rho undefined)  : {empty:,} ({100 * empty / len(by_unit):.2f}%)",
        f"median crashes behind a cell    : {denominator.median():.0f}",
        "",
        "share of thin cells by pair:",
    ]
    for pair in config.RHO_PAIR_LABELS:
        subset = by_unit.loc[by_unit[config.PAIR_COL] == pair, config.RHO_DENOMINATOR_COL]
        lines.append(
            f"    {_short_pair(pair):<10} {100 * (subset < config.RHO_SPARSE_DENOMINATOR).mean():>6.2f}% thin, "
            f"{100 * (subset == 0).mean():>6.2f}% empty, median {subset.median():.0f}"
        )
    lines.append("")
    lines.append("nothing is filtered on this: every cell is exported with its denominator beside it")
    log.table("how thin the unit-level grid is:", "\n".join(lines))

    # -- pooled city value against the average of the units -----------------
    lines = [
        f"{'pair':<10}  {'city (pooled)':>13}  {'mean of units':>13}  {'difference':>11}  {'units counted':>13}",
        f"{'-' * 10}  {'-' * 13}  {'-' * 13}  {'-' * 11}  {'-' * 13}",
    ]
    for pair in config.RHO_PAIR_LABELS:
        city_rows = long_table[
            (long_table[config.AGGREGATION_LEVEL_COL] == config.CITY_LEVEL)
            & (long_table[config.PAIR_COL] == pair)
        ]
        pooled = city_rows[config.RHO_NUMERATOR_COL].sum() / max(int(city_rows[config.RHO_DENOMINATOR_COL].sum()), 1)
        unit_rows = by_unit[(by_unit[config.PAIR_COL] == pair) & by_unit[config.RHO_COL].notna()]
        mean_of_units = float(unit_rows[config.RHO_COL].astype(float).mean())
        lines.append(
            f"{_short_pair(pair):<10}  {pooled:>13.3f}  {mean_of_units:>13.3f}  "
            f"{mean_of_units - pooled:>+11.3f}  {len(unit_rows):>13,}"
        )
    all_city = long_table[long_table[config.AGGREGATION_LEVEL_COL] == config.CITY_LEVEL]
    pooled_all = all_city[config.RHO_NUMERATOR_COL].sum() / int(all_city[config.RHO_DENOMINATOR_COL].sum())
    mean_all = float(by_unit.loc[by_unit[config.RHO_COL].notna(), config.RHO_COL].astype(float).mean())
    lines.append("")
    lines.append(f"over every pair: city {pooled_all:.3f}, mean of unit-year cells {mean_all:.3f} "
                 f"({mean_all - pooled_all:+.3f})")
    lines.append(
        "the two are different quantities: the city value weights every crash equally, while the average "
        "of the cells weights every cell equally and so lets a cell of three crashes count as much as one "
        "of three thousand"
    )
    log.table("city value against the average of the units:", "\n".join(lines))


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


def compute(
    universe: pd.DataFrame,
    crash_attrs: pd.DataFrame,
    units: pd.DataFrame,
    log: RunLog,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The whole calculation: from the party universe to the rho table.

    Returns the table and the crashes that entered it, which verification needs to
    check that each crash was counted exactly once.
    """
    pairs = build_crash_pairs(universe, log)
    pairs = restrict_to_pairs(pairs, log)
    crashes = place_in_time_and_space(pairs, crash_attrs, log)
    log.dump(crashes, "07_rho_crashes")

    long_table = build_long_table(crashes, units, log)
    log.dump(long_table, "08_rho_long")
    return long_table, crashes
