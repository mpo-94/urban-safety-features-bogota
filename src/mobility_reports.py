"""Google's COVID-19 Community Mobility Reports, read for Bogotá.

What the pandemic patch needs is one number per year saying how much less the
city moved than it would have. This module produces that number, and nothing
else, from a source that has no connection to crash records — which is the whole
point of replacing the earlier patch (D49 supersedes D42).

Three things about the source decide how it is read, and each was measured
rather than assumed.

**Bogotá exists only as a whole city.** Every one of the 974 rows has an empty
`sub_region_2`, so there is no locality breakdown and certainly no UPL. The
factor is therefore a city-wide number, applied to every unit alike.

**There is no mode.** The six series are categories of destination, not ways of
travelling: shops, groceries, parks, transit stations, workplaces and homes.
None of them is walking or cycling, and the one that names transport counts
visits to stations rather than trips by bus. So this module returns a single
shock common to all modes, and what distinguishes the modes comes from
elsewhere — the survey trend, and for the bicycle a measured figure.

**The baseline is a Bogotá January, which is not a normal month.** Google
compares every day against the median of the same weekday between 3 January and
6 February 2020, and in Bogotá that window is school holidays. Measured in 2022,
the year closest to normal in the series, January reads lowest of the ten months
in all four categories — workplaces at 0.845 against 1.20 in September. So
`1 + change/100` is not "fraction of normal": it is "fraction of a January", and
using it directly would write that seasonality into the patch.

The fix is to compare each month against the same month of a normal year rather
than against Google's own baseline. The seasonality then sits on both sides of
the ratio and cancels.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass

import pandas as pd

try:  # regular package import
    from src import config
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


@dataclass(frozen=True)
class MobilityShock:
    """How much less the city moved in each patched year than in a normal one.

    `by_year` is what the patch consumes. `table` is the same thing with its
    working shown — one row per year and month — so that the handful of numbers
    the patch rests on can be read without running anything.
    """

    by_year: dict[int, float]
    table: pd.DataFrame
    reference_year: int
    categories: tuple[str, ...]
    months_used: dict[int, tuple[int, ...]]


def _city_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """The rows for Bogotá as a whole, which is the only scale the source has."""
    named = frame[config.GOOGLE_REGION_COL].fillna("")
    is_bogota = named.str.contains(config.GOOGLE_REGION_NAME, case=False, regex=False)
    # A filled sub_region_2 would be a place inside the region. Bogotá has none,
    # and the check is kept so that a future delivery that does would be caught
    # here rather than silently doubling every day.
    return frame[is_bogota & frame[config.GOOGLE_SUBREGION_COL].isna()]


def read(log: RunLog) -> pd.DataFrame:
    """Every daily row Google published for Bogotá, one column per category."""
    frames = []
    for year, path in sorted(config.GOOGLE_MOBILITY_FILES.items()):
        if not path.exists():
            raise FileNotFoundError(
                f"the {year} community mobility report is declared at {path} and is not "
                "there; see docs/data-layout.md"
            )
        frames.append(_city_rows(pd.read_csv(path, low_memory=False)))

    daily = pd.concat(frames, ignore_index=True)
    if daily.empty:
        raise ValueError(
            f"no rows for {config.GOOGLE_REGION_NAME!r} in the community mobility reports"
        )

    daily[config.GOOGLE_DATE_COL] = pd.to_datetime(daily[config.GOOGLE_DATE_COL])
    missing = [
        column for column in config.GOOGLE_CATEGORY_COLUMNS
        if daily[column].isna().any()
    ]
    if missing:
        raise ValueError(
            "the community mobility reports have gaps in "
            f"{', '.join(missing)}; the composite cannot be built over a hole"
        )

    log.info(
        "community mobility reports: %d daily rows for %s, %s to %s",
        len(daily), config.GOOGLE_REGION_NAME,
        daily[config.GOOGLE_DATE_COL].min().date(),
        daily[config.GOOGLE_DATE_COL].max().date(),
    )
    return daily


def _monthly_level(daily: pd.DataFrame) -> pd.DataFrame:
    """The composite, averaged by year and month over weekdays only.

    Weekdays only because the patch multiplies weekday exposure and these
    categories have a strong weekly cycle: workplaces in 2020 reads 0.645 over
    every day and 0.571 over weekdays alone.

    The composite is the plain mean of the four out-of-home categories. The two
    that are left out are left out for reasons, not for tidiness: `residential`
    measures time at home rather than visits, so it is a different quantity in
    different units, and `grocery_and_pharmacy` is essential travel that rose
    above baseline while everything else fell, so it moves against the thing
    being measured.
    """
    weekdays = daily[daily[config.GOOGLE_DATE_COL].dt.dayofweek < 5].copy()
    for column in config.GOOGLE_CATEGORY_COLUMNS:
        weekdays[column] = 1 + weekdays[column] / 100
    weekdays["YEAR"] = weekdays[config.GOOGLE_DATE_COL].dt.year
    weekdays["MONTH"] = weekdays[config.GOOGLE_DATE_COL].dt.month
    level = weekdays.groupby(["YEAR", "MONTH"])[
        list(config.GOOGLE_CATEGORY_COLUMNS)
    ].mean()
    level["COMPOSITE"] = level.mean(axis=1)
    return level


def build(daily: pd.DataFrame, log: RunLog) -> MobilityShock:
    """One shock per patched year: that year against the same months of a normal one."""
    level = _monthly_level(daily)
    reference = config.GOOGLE_REFERENCE_YEAR
    if reference not in level.index.get_level_values("YEAR"):
        raise ValueError(f"the reference year {reference} is not in the reports")
    reference_months = set(level.loc[reference].index)

    rows: list[dict] = []
    by_year: dict[int, float] = {}
    months_used: dict[int, tuple[int, ...]] = {}
    for year in config.PANDEMIC_PATCH_YEARS:
        if year not in level.index.get_level_values("YEAR"):
            raise ValueError(
                f"{year} is declared a patched year and the reports do not cover it"
            )
        shared = sorted(set(level.loc[year].index) & reference_months)
        if not shared:
            raise ValueError(f"{year} and {reference} share no month to compare")
        ratios = []
        for month in shared:
            ratio = (float(level.loc[(year, month), "COMPOSITE"])
                     / float(level.loc[(reference, month), "COMPOSITE"]))
            ratios.append(ratio)
            rows.append({
                "YEAR": year,
                "MONTH": month,
                "MONTH_NAME": calendar.month_name[month],
                "COMPOSITE": float(level.loc[(year, month), "COMPOSITE"]),
                "COMPOSITE_REFERENCE": float(level.loc[(reference, month), "COMPOSITE"]),
                "RATIO": ratio,
            })
        by_year[year] = sum(ratios) / len(ratios)
        months_used[year] = tuple(shared)

        skipped = sorted(set(level.loc[year].index) - reference_months)
        log.info(
            "%d against %d: %.3f over %d shared month(s)%s",
            year, reference, by_year[year], len(shared),
            f", leaving out {', '.join(calendar.month_abbr[m] for m in skipped)} "
            f"because {reference} does not reach them" if skipped else "",
        )

    return MobilityShock(
        by_year=by_year,
        table=pd.DataFrame(rows),
        reference_year=reference,
        categories=config.GOOGLE_CATEGORY_COLUMNS,
        months_used=months_used,
    )


def verify(shock: MobilityShock, daily: pd.DataFrame, log: RunLog) -> bool:
    """Checks that would each have caught a real way of getting this wrong."""
    reference = daily[daily[config.GOOGLE_DATE_COL].dt.year == config.GOOGLE_REFERENCE_YEAR]
    lowest = min(float(reference[column].mean()) for column in config.GOOGLE_CATEGORY_COLUMNS)
    ordered = sorted(shock.by_year.items())

    checks: list[tuple[str, bool, str]] = [
        # If the reference year were itself depressed, every factor would be
        # divided by a small number and the collapse would read shallower than
        # it was. Measured: its weakest category sits at or above the baseline.
        (
            f"the reference year {config.GOOGLE_REFERENCE_YEAR} is not itself collapsed",
            lowest > -5.0,
            f"weakest category at {1 + lowest / 100:.3f} of Google's baseline",
        ),
        (
            "every shock is a fraction below one",
            all(0 < value < 1 for value in shock.by_year.values()),
            ", ".join(f"{year} {value:.3f}" for year, value in ordered),
        ),
        # A shock built on one or two months would be an annual number in name only.
        (
            "each shock rests on at least nine months",
            all(len(months) >= 9 for months in shock.months_used.values()),
            ", ".join(f"{year} {len(months)}" for year, months in sorted(shock.months_used.items())),
        ),
        (
            "the collapse is deeper in the first patched year than in the second",
            [value for _, value in ordered] == sorted(value for _, value in ordered),
            " then ".join(f"{value:.3f}" for _, value in ordered),
        ),
    ]

    width = max(len(name) for name, _, _ in checks)
    log.table(
        "community mobility reports verification:",
        "\n".join(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}"
                  for name, ok, detail in checks),
    )
    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("community mobility reports verification FAILED")
    return passed
