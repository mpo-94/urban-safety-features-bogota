"""Month-by-month completeness of the casualty layers.

The 2024 injury layer stopped in mid-September and nothing said so. The year
looked like a 33% drop in casualties, which is a plausible-looking number, and it
took an updated extract arriving to reveal that a third of the year was simply
absent.

That is a hole in the checks, not a piece of bad luck: the pipeline verifies its
own arithmetic thoroughly and verified nothing about whether the sources cover
the period they claim to. This measures it. For every layer and every year it
counts the records of each month and flags the months that are empty or far below
what the rest of that year looks like.

It reports; it does not filter, correct or exclude anything. What a thin month
means — a real drop, a strike, a change of system, an extract taken mid-month —
is a question about the sources.

Run it:

    python -m src.run_pipeline completeness
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

try:  # regular package import
    from src import config, loading
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import loading  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


def monthly_counts(log: RunLog) -> pd.DataFrame:
    """One row per layer, year and month, with the records seen in it.

    The month comes from the date rather than from MES_OCURRE, so a row with a
    damaged month name still lands in the right month, and the two can be
    compared if they ever disagree.
    """
    frames: list[pd.DataFrame] = []
    for path, label in (
        (config.FATALITIES_PATH, config.FATALITY_SOURCE),
        (config.INJURIES_PATH, config.INJURY_SOURCE),
    ):
        layer = loading.read_point_layer(path)
        dates = pd.to_datetime(layer[config.DATE_SOURCE_COL], errors="coerce")
        undated = int(dates.isna().sum())
        if undated:
            log.warn("%s: %d row(s) have no usable date and cannot be placed in a month", label, undated)

        frame = pd.DataFrame(
            {
                config.CASUALTY_SOURCE_COL: label,
                config.YEAR_COL: layer[config.YEAR_SOURCE_COL].astype("Int64"),
                "MONTH": dates.dt.month.astype("Int64"),
            }
        )
        disagreeing = int((frame[config.YEAR_COL] != dates.dt.year.astype("Int64")).sum())
        if disagreeing:
            log.warn(
                "%s: %d row(s) whose year column disagrees with the year of their date",
                label,
                disagreeing,
            )
        log.record(
            f"read layer for the completeness audit [{label}]",
            rows_in=len(layer),
            rows_out=len(frame),
            notes=[
                f"source={path.name}",
                f"{undated} row(s) without a usable date, {disagreeing} whose year and date disagree",
            ],
        )
        frames.append(frame)

    observed = (
        pd.concat(frames, ignore_index=True)
        .groupby([config.CASUALTY_SOURCE_COL, config.YEAR_COL, "MONTH"], dropna=True)
        .size()
        .reset_index(name="RECORDS")
    )

    # Complete grid, so a month with no record at all is a zero that can be seen
    # rather than a row that is not there — the same reason as D10.
    grid = pd.MultiIndex.from_product(
        [
            [config.FATALITY_SOURCE, config.INJURY_SOURCE],
            list(config.STUDY_YEARS),
            range(1, 13),
        ],
        names=[config.CASUALTY_SOURCE_COL, config.YEAR_COL, "MONTH"],
    ).to_frame(index=False)
    grid[config.YEAR_COL] = grid[config.YEAR_COL].astype("Int64")
    grid["MONTH"] = grid["MONTH"].astype("Int64")

    table = grid.merge(observed, on=list(grid.columns), how="left")
    table["RECORDS"] = table["RECORDS"].fillna(0).astype(int)
    return table


def flag_thin_months(table: pd.DataFrame) -> pd.DataFrame:
    """Mark the months that are empty or far below the rest of their own year.

    Each year is judged against itself. A layer that grows over eighteen years
    would make any fixed threshold either miss the early years or condemn them,
    while the question here is whether a month is out of line with the months
    beside it.
    """
    table = table.copy()
    reference = table.groupby([config.CASUALTY_SOURCE_COL, config.YEAR_COL])["RECORDS"].transform("median")
    table["YEAR_MEDIAN"] = reference
    table["SHARE_OF_MEDIAN"] = (table["RECORDS"] / reference.where(reference > 0)).astype("Float64")
    table["EMPTY"] = table["RECORDS"] == 0
    table["THIN"] = table["SHARE_OF_MEDIAN"] < config.COMPLETENESS_THIN_SHARE
    return table


def export(table: pd.DataFrame, log: RunLog) -> Path:
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{config.ANALYSIS_PREFIX}__monthly_completeness.csv"
    table.to_csv(path, index=False, encoding="utf-8")
    log.info("exported the monthly completeness table to %s/%s", config.DATA_SUBDIR, path.name)
    return path


def report(table: pd.DataFrame, log: RunLog) -> None:
    for label in (config.FATALITY_SOURCE, config.INJURY_SOURCE):
        layer = table[table[config.CASUALTY_SOURCE_COL] == label]
        wide = layer.pivot(index=config.YEAR_COL, columns="MONTH", values="RECORDS")
        lines = [
            f"{'year':>6}  " + "  ".join(f"{month:>5}" for month in range(1, 13)) + f"  {'total':>7}",
            f"{'-' * 6}  " + "  ".join("-" * 5 for _ in range(12)) + f"  {'-' * 7}",
        ]
        for year, row in wide.iterrows():
            cells = "  ".join(f"{int(row[month]):>5,}" for month in range(1, 13))
            lines.append(f"{int(year):>6}  {cells}  {int(row.sum()):>7,}")
        log.table(f"records per month [{label}]:", "\n".join(lines))

    flagged = table[table["THIN"] | table["EMPTY"]].sort_values(
        [config.CASUALTY_SOURCE_COL, config.YEAR_COL, "MONTH"]
    )
    lines = [
        f"{'layer':<10}  {'year':>6}  {'month':>6}  {'records':>8}  {'year median':>12}  {'share':>7}",
        f"{'-' * 10}  {'-' * 6}  {'-' * 6}  {'-' * 8}  {'-' * 12}  {'-' * 7}",
    ]
    for _, row in flagged.iterrows():
        share = "-" if pd.isna(row["SHARE_OF_MEDIAN"]) else f"{100 * float(row['SHARE_OF_MEDIAN']):.1f}%"
        lines.append(
            f"{row[config.CASUALTY_SOURCE_COL]:<10}  {int(row[config.YEAR_COL]):>6}  "
            f"{int(row['MONTH']):>6}  {int(row['RECORDS']):>8,}  {int(row['YEAR_MEDIAN']):>12,}  {share:>7}"
        )
    if flagged.empty:
        lines.append(
            f"(no month is empty or below {100 * config.COMPLETENESS_THIN_SHARE:.0f}% "
            "of the median month of its own year)"
        )
    log.table(
        f"months that are empty or below {100 * config.COMPLETENESS_THIN_SHARE:.0f}% "
        "of their year's median:",
        "\n".join(lines),
    )

    # A year missing its tail is what a truncated extract looks like, and it is
    # worth naming separately from a single thin month in the middle.
    lines = []
    for label in (config.FATALITY_SOURCE, config.INJURY_SOURCE):
        layer = table[table[config.CASUALTY_SOURCE_COL] == label]
        for year in config.STUDY_YEARS:
            months = layer[layer[config.YEAR_COL] == year].sort_values("MONTH")
            empty = months["EMPTY"].to_numpy()
            trailing = 0
            for value in empty[::-1]:
                if not value:
                    break
                trailing += 1
            if trailing:
                lines.append(
                    f"    {label:<10} {year}: last {trailing} month(s) of the year empty, "
                    f"{int(months['RECORDS'].sum()):,} records in the year"
                )
    log.table(
        "years whose final months are empty, which is what a truncated extract looks like:",
        "\n".join(lines) if lines else "    (none)",
    )

    totals = table.groupby([config.CASUALTY_SOURCE_COL, config.YEAR_COL])["RECORDS"].sum().unstack(0)
    lines = [
        f"{'year':>6}  {'fatalities':>11}  {'injuries':>10}  {'total':>10}  {'change':>8}",
        f"{'-' * 6}  {'-' * 11}  {'-' * 10}  {'-' * 10}  {'-' * 8}",
    ]
    previous = None
    for year in config.STUDY_YEARS:
        fatal = int(totals.loc[year, config.FATALITY_SOURCE])
        injured = int(totals.loc[year, config.INJURY_SOURCE])
        total = fatal + injured
        change = "-" if previous is None else f"{100 * (total - previous) / previous:+.1f}%"
        lines.append(f"{year:>6}  {fatal:>11,}  {injured:>10,}  {total:>10,}  {change:>8}")
        previous = total
    log.table("records per year, for reading the table above against:", "\n".join(lines))
