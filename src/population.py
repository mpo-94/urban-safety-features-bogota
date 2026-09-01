"""Resident population per territorial unit and year.

This is the denominator. Casualties are counted per unit and per year, and a count
becomes a rate only when it is divided by something that says how many people were
there to be hurt. Everything in this module exists to make that division defensible.

**One number per unit and per year, never one per unit.** The alternative was a
single figure for each unit, and it fails twice over. A denominator that does not
move inside a unit is collinear with that unit's fixed effect: the model absorbs it
and the normalisation disappears without anything failing. And the movement it
would throw away is large — between 2007 and 2024 a unit's population changes by
anything from −28.5% in Barrios Unidos to +557.9% in Torca, which is not the kind
of variation a study of rates can average over. The series is also a superset: it
collapses to one number per unit whenever a fixed denominator is wanted, and no
amount of work turns one number per unit back into a series. See D36.

**What the file is.** One row per unit, year, sex and single year of age, over the
33 units of Decreto 555 de 2021 and the years 2005 to 2035. The pipeline adds the
sex and age breakdown away and keeps nothing coarser than (unit, year), because
nothing downstream asks for less and a total that has already been rounded into
age bands cannot be taken apart again.

**Three of the file's units are not in the study.** The delivered cartography holds
30 UPL and the file holds 33; the three it adds are the rural units, where the urban
predictors are undefined. That is the reason the study universe is 30, and this
module is the only place where the size of that decision can be measured in people
rather than in polygons. The run reports it every time: the three together are
about 0.3% of the city. It is a confirmation, not a shortfall.

**What is open.** The file covers 2005 to 2035, which no census does, so some of
those years are projections and some are probably backcasts. Which years are which
is not in the file, and deciding it from the shape of the series would be inference
presented as provenance. It stays an open question for my advisor, and nothing here
assumes an answer. See D36.

Run it:

    python -m src.run_pipeline population
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

try:  # regular package import
    from src import config
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# Working column, private to this module. The file numbers its units and the study
# spells them; this holds the spelling while the raw number is still around to be
# checked against.
_UNIT_CODE_COL = "_UNIT_CODE"


# ---------------------------------------------------------------------------
# Reading the file
# ---------------------------------------------------------------------------


def read(log: RunLog) -> pd.DataFrame:
    """Read the population file and hold the declaration to account.

    Every column the aggregation uses is named in the configuration and read
    through it, so a delivery that renames one fails here rather than quietly
    summing a different column. The file arrives with a byte order mark and
    semicolons, both declared, because a reader that guesses either would give a
    first column nobody can address by name.
    """
    source = config.POPULATION_SOURCE
    if not source.path.exists():
        raise FileNotFoundError(
            f"the population source {source.path} does not exist; it needs {source.describes}"
        )

    wanted = [
        source.year_column,
        source.code_column,
        source.name_column,
        *source.breakdown_columns,
        source.count_column,
    ]
    table = pd.read_csv(source.path, sep=source.separator, encoding=source.encoding)
    missing = [column for column in wanted if column not in table.columns]
    if missing:
        raise ValueError(
            f"{source.path.name} does not carry {', '.join(missing)}; it needs {source.describes}. "
            f"The columns it does carry are: {', '.join(table.columns)}"
        )

    # Only the declared columns. The file also carries the life-course and age-band
    # labels each row belongs to, which are groupings of the single year of age the
    # aggregation already reads and would be summed twice if they came along.
    table = table[wanted].copy()
    table[_UNIT_CODE_COL] = table[source.code_column].map(source.unit_code)

    log.record(
        "read the population file",
        rows_in=len(table),
        rows_out=len(table),
        notes=[
            f"source={source.path.name}, one row per unit, year and {' and '.join(source.breakdown_columns).lower()}",
            f"{table[_UNIT_CODE_COL].nunique()} unit(s), years {table[source.year_column].min()}"
            f"-{table[source.year_column].max()}",
            f"unit numbers rendered as {source.code_prefix}NN to match how the unit layer spells them",
        ],
    )
    return table


def aggregate(raw: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """Add the sex and age breakdown away, leaving one row per unit and year.

    Every unit and every year the file carries, not only the ones the study uses:
    the three units outside the study have to survive this step in order to be
    reported, and the years outside the study period are what shows that the file
    reaches further than any census does.
    """
    source = config.POPULATION_SOURCE
    # The file's own name for the unit is a grouping key rather than an aggregate,
    # which is safe because it is constant within a unit and is checked to be: a
    # unit spelled two ways would come out as two rows and fail the cell count.
    totals = (
        raw.groupby(
            [_UNIT_CODE_COL, source.name_column, source.year_column], as_index=False
        )[source.count_column]
        .sum()
        .rename(columns={source.year_column: config.YEAR_COL, source.count_column: config.POPULATION_COL})
    )

    log.record(
        "add the population over sex and age",
        rows_in=len(raw),
        rows_out=len(totals),
        changes=[(
            len(totals) - len(raw),
            f"rows lost to the sum: one row per unit and year in place of one per "
            f"{' and '.join(source.breakdown_columns).lower()} within it",
        )],
        notes=[
            f"{totals[_UNIT_CODE_COL].nunique()} unit(s) over {totals[config.YEAR_COL].nunique()} year(s)",
            f"{totals[config.POPULATION_COL].sum():,} person-years in the file as delivered",
        ],
    )
    return totals


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------


def build(
    units: gpd.GeoDataFrame,
    log: RunLog,
    scale: config.TerritorialScale | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """One row per study unit and study year, with the raw file and the full totals.

    The returned table is the study's: 30 units by 18 years, in the column order the
    configuration declares. The other two come back so the checks can be made against
    what was read rather than against a second pass over the same file — the totals
    still hold the three units outside the study, which is what makes them reportable.

    The unit name comes from the cartography and not from the file, because the
    cartography is what every other table in the study is named from. That the two
    agree is checked rather than assumed, and it is checked on the names and not only
    on the codes: two files can agree on a code and disagree on which place it is.
    """
    scale = scale or config.active_scale()
    source = config.POPULATION_SOURCE

    raw = read(log)
    totals = aggregate(raw, log)

    study_units = units[[config.AREA_CODE_COL, config.AREA_NAME_COL]].copy()
    years = pd.DataFrame({config.YEAR_COL: list(config.STUDY_YEARS)})
    # The full grid first, then the file joined onto it. Built this way round so a
    # unit-year the file does not cover arrives as a null that the checks catch,
    # rather than as a row that is simply not there and that a later join would
    # drop without a word. It is D22's rule applied to the denominator.
    grid = study_units.merge(years, how="cross")
    table = grid.merge(
        totals.rename(columns={_UNIT_CODE_COL: config.AREA_CODE_COL}),
        on=[config.AREA_CODE_COL, config.YEAR_COL],
        how="left",
    )

    table[config.SCALE_COL] = scale.label
    table = (
        table[list(config.POPULATION_TABLE_COLUMNS)]
        .sort_values([config.AREA_CODE_COL, config.YEAR_COL], kind="stable")
        .reset_index(drop=True)
    )

    outside = sorted(set(totals[_UNIT_CODE_COL]) - set(study_units[config.AREA_CODE_COL]))
    covered = totals[
        totals[_UNIT_CODE_COL].isin(set(study_units[config.AREA_CODE_COL]))
        & totals[config.YEAR_COL].isin(list(config.STUDY_YEARS))
    ]
    log.record(
        "restrict the population to the study",
        rows_in=len(totals),
        rows_out=len(table),
        changes=[
            (
                -(len(totals) - len(covered)),
                f"unit-years outside the study: {len(outside)} unit(s) the cartography does not "
                f"carry, and the years outside {config.FIRST_YEAR}-{config.LAST_YEAR}",
            ),
            (
                len(table) - len(covered),
                "unit-years the file does not cover, kept as null rows so the check can see them",
            ),
        ],
        notes=[
            f"scale={scale.label}, {len(study_units)} unit(s) over {len(years)} year(s) "
            f"= {len(table)} cells",
            f"source={source.path.name}",
        ],
    )

    warn_about_the_file(totals, units, log)
    return table, totals, raw


def warn_about_the_file(totals: pd.DataFrame, units: gpd.GeoDataFrame, log: RunLog) -> None:
    """The two things a reader has to be told every time this file is read.

    In `build` and not in `report`, because they are properties of the source and
    not of the route: any run that reads the population reads them along with it,
    and a caveat that only appears when somebody asks for the summary is a caveat
    that stops being seen.
    """
    first, last = config.FIRST_YEAR, config.LAST_YEAR
    outside = units_outside_the_study(totals, units)
    in_study_years = outside[outside[config.YEAR_COL].between(first, last)]

    # The measured reason the universe is 30 units. It is the figure the Datos
    # chapter needs and the only one that answers the question a jury asks about
    # the three missing units.
    if not in_study_years.empty:
        per_year = in_study_years.groupby(config.YEAR_COL)["SHARE_OF_CITY"].sum() * 100
        latest = in_study_years[in_study_years[config.YEAR_COL] == last]
        log.warn(
            "the population file carries %d unit(s) the study does not: %s. They are the rural "
            "units the delivered cartography omits, and together they are %.2f%% of the city in "
            "%d (%.2f%% to %.2f%% over %d-%d). That is what working on %d units leaves out, and "
            "it is the measured reason the universe is %d; see D36",
            latest[_UNIT_CODE_COL].nunique(),
            ", ".join(
                f"{row[_UNIT_CODE_COL]} {row[config.POPULATION_SOURCE.name_column]} "
                f"({int(row[config.POPULATION_COL]):,} in {last})"
                for _, row in latest.iterrows()
            ),
            per_year[last],
            last,
            per_year.min(),
            per_year.max(),
            first,
            last,
            len(units),
            len(units),
        )

    # Said on every run rather than written down once, because it is the kind of
    # caveat that stops being repeated the moment the number starts looking solid.
    log.warn(
        "which years of %s are measured and which are projected or backcast is not in the file: "
        "it spans %d-%d, wider than any census, and the distinction cannot be read off the shape "
        "of the series. Open question for my advisor; see D36",
        config.POPULATION_SOURCE.path.name,
        int(totals[config.YEAR_COL].min()),
        int(totals[config.YEAR_COL].max()),
    )


def for_year(table: pd.DataFrame, year: int) -> pd.Series:
    """The population of every unit in one year, indexed by unit code.

    What a table with no year of its own has to ask for. It raises rather than
    returning a short series if the year is not in the table, because a rate
    silently computed against a missing denominator is the failure this module was
    written to prevent.
    """
    wanted = table[table[config.YEAR_COL] == year]
    if wanted.empty:
        available = f"{table[config.YEAR_COL].min()}-{table[config.YEAR_COL].max()}"
        raise ValueError(f"the population table has no year {year}; it covers {available}")
    return wanted.set_index(config.AREA_CODE_COL)[config.POPULATION_COL].astype(float)


def units_outside_the_study(totals: pd.DataFrame, units: gpd.GeoDataFrame) -> pd.DataFrame:
    """The file's units that the cartography does not carry, year by year.

    One row per such unit and year, with its population and its share of the city
    the file describes. This is the measurement behind the study universe: the
    three units are absent from the layer, and what the study leaves out by working
    on 30 of the 33 is these people and no others.
    """
    absent = sorted(set(totals[_UNIT_CODE_COL]) - set(units[config.AREA_CODE_COL]))
    city = totals.groupby(config.YEAR_COL)[config.POPULATION_COL].sum()
    # Their names come from the file because they come from nowhere else: these are
    # the units the cartography does not carry, so there is no layer row to read a
    # name from.
    outside = totals[totals[_UNIT_CODE_COL].isin(absent)].copy()
    outside["CITY_POPULATION"] = outside[config.YEAR_COL].map(city)
    outside["SHARE_OF_CITY"] = outside[config.POPULATION_COL] / outside["CITY_POPULATION"]
    return outside.sort_values([config.YEAR_COL, _UNIT_CODE_COL], kind="stable").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export(table: pd.DataFrame, totals: pd.DataFrame, units: gpd.GeoDataFrame, log: RunLog) -> dict[str, Path]:
    """Write the panel of denominators and the measurement of what the study omits."""
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    table_path = data_dir / f"{config.ANALYSIS_PREFIX}__population_by_unit_year.csv"
    table.to_csv(table_path, index=False, encoding="utf-8")
    table.to_parquet(table_path.with_suffix(".parquet"))
    paths["table"] = table_path

    # Exported rather than left in the log, because it is the evidence a chapter
    # cites for why the universe is 30 units and a reader may want the year they
    # are writing about rather than the one the log happened to print.
    outside_path = data_dir / f"{config.PRESENTATION_PREFIX}__population_outside_the_study.csv"
    outside = units_outside_the_study(totals, units)
    # The identifying columns are named as every other exported table names them,
    # so this one joins to the rest. The name comes from the population file rather
    # than from the cartography, which is unavoidable: these are exactly the units
    # the cartography does not carry.
    outside.rename(
        columns={
            _UNIT_CODE_COL: config.AREA_CODE_COL,
            config.POPULATION_SOURCE.name_column: config.AREA_NAME_COL,
        }
    ).to_csv(outside_path, index=False, encoding="utf-8")
    paths["outside"] = outside_path

    log.info("exported 1 analysis table and 1 presentation table to %s/", config.DATA_SUBDIR)
    return paths


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(
    table: pd.DataFrame,
    totals: pd.DataFrame,
    raw: pd.DataFrame,
    units: gpd.GeoDataFrame,
    log: RunLog,
    paths: dict[str, Path] | None = None,
) -> bool:
    """Check the panel against the file it came from, and against the cartography.

    The check that matters is completeness. A predictor that is missing for one
    unit-year leaves a hole a reader can see; a denominator that is missing for one
    unit-year removes that cell from every model built on it, and nothing in the
    output says which cell went. So the grid is required to be full, and the run
    stops if it is not.
    """
    source = config.POPULATION_SOURCE
    checks: list[tuple[str, bool, str]] = []

    expected_units = set(units[config.AREA_CODE_COL])
    expected_years = set(config.STUDY_YEARS)
    expected_cells = len(expected_units) * len(expected_years)

    checks.append((
        "the table carries exactly the declared columns, in the declared order",
        list(table.columns) == list(config.POPULATION_TABLE_COLUMNS),
        f"{len(table.columns)} columns against {len(config.POPULATION_TABLE_COLUMNS)} declared",
    ))
    checks.append((
        "one row per unit and year, with no unit and no year missing",
        len(table) == expected_cells
        and set(table[config.AREA_CODE_COL]) == expected_units
        and set(table[config.YEAR_COL]) == expected_years,
        f"{len(table)} rows against {len(expected_units)} units x {len(expected_years)} years "
        f"= {expected_cells}",
    ))
    empty = table[table[config.POPULATION_COL].isna()]
    checks.append((
        "every unit-year of the study has a population",
        empty.empty,
        f"{len(empty)} cell(s) with none"
        + (
            ": " + ", ".join(
                f"{row[config.AREA_CODE_COL]} {row[config.YEAR_COL]}"
                for _, row in empty.head(5).iterrows()
            )
            if not empty.empty
            else ""
        ),
    ))
    nonpositive = table[table[config.POPULATION_COL].fillna(0) <= 0]
    checks.append((
        "no population is zero or negative",
        nonpositive.empty,
        f"{len(nonpositive)} cell(s) at or below zero",
    ))

    # The balance. Every person in a study cell of the file is in the table exactly
    # once, which is what says the sum over sex and age neither dropped a row nor
    # counted one twice.
    in_study = raw[
        raw[_UNIT_CODE_COL].isin(expected_units) & raw[source.year_column].isin(expected_years)
    ]
    from_file = int(in_study[source.count_column].sum())
    in_table = int(table[config.POPULATION_COL].fillna(0).sum())
    checks.append((
        "the table holds exactly the people the file holds for those units and years",
        from_file == in_table,
        f"{in_table:,} in the table against {from_file:,} in the file",
    ))
    checks.append((
        "the file has one row per unit, year, sex and age",
        not raw.duplicated([_UNIT_CODE_COL, source.year_column, *source.breakdown_columns]).any(),
        f"{int(raw.duplicated([_UNIT_CODE_COL, source.year_column, *source.breakdown_columns]).sum())} "
        "duplicate row(s)",
    ))

    # The join is on the code, so the code is not what proves the join is right. The
    # names are: they were delivered independently of the cartography and agreeing
    # on all thirty of them is what says the two files divide the city the same way.
    file_names = (
        raw[[_UNIT_CODE_COL, source.name_column]]
        .drop_duplicates()
        .set_index(_UNIT_CODE_COL)[source.name_column]
    )
    layer_names = units.set_index(config.AREA_CODE_COL)[config.AREA_NAME_COL]
    shared = sorted(set(file_names.index) & set(layer_names.index))
    disagreeing = [
        f"{code}: {layer_names[code]!r} against {file_names[code]!r}"
        for code in shared
        if layer_names[code] != file_names[code]
    ]
    checks.append((
        "every unit name in the file matches the cartography character for character",
        not disagreeing and len(shared) == len(expected_units),
        f"{len(shared)} of {len(expected_units)} unit(s) matched"
        + (f"; disagreeing: {'; '.join(disagreeing)}" if disagreeing else ""),
    ))

    outside = sorted(set(totals[_UNIT_CODE_COL]) - expected_units)
    checks.append((
        "the units the file adds to the study are the declared ones",
        tuple(outside) == config.POPULATION_UNITS_OUTSIDE_STUDY,
        f"{', '.join(outside) or 'none'} against "
        f"{', '.join(config.POPULATION_UNITS_OUTSIDE_STUDY)} declared",
    ))

    if paths:
        written = [path for path in paths.values() if path.exists() and path.stat().st_size > 0]
        checks.append((
            "every exported file is on disk and none is empty",
            len(written) == len(paths),
            f"{len(written)} of {len(paths)}",
        ))

    width = max(len(name) for name, _, _ in checks)
    rendered = [
        f"{'check'.ljust(width)}  {'result':>8}  detail",
        f"{'-' * width}  {'-' * 8}  ------",
    ]
    for name, ok, detail in checks:
        rendered.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("population verification:", "\n".join(rendered))

    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("population verification FAILED")
    return passed


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def report(table: pd.DataFrame, totals: pd.DataFrame, units: gpd.GeoDataFrame, log: RunLog) -> None:
    """What the denominator looks like, and what the study leaves outside it."""
    first, last = config.FIRST_YEAR, config.LAST_YEAR
    wide = table.pivot(
        index=config.AREA_CODE_COL, columns=config.YEAR_COL, values=config.POPULATION_COL
    )
    names = units.set_index(config.AREA_CODE_COL)[config.AREA_NAME_COL]

    log.info(
        "population of the %d units: %s in %d, %s in %d, %+.1f%% over the period",
        len(wide),
        f"{int(wide[first].sum()):,}",
        first,
        f"{int(wide[last].sum()):,}",
        last,
        100 * (wide[last].sum() / wide[first].sum() - 1),
    )

    # The spread is the argument for keeping the year. A denominator that moved the
    # same way everywhere could be dropped into the unit effect without losing much;
    # this one cannot.
    change = (wide[last] / wide[first] - 1) * 100
    log.info(
        "change between %d and %d: %+.1f%% in %s (%s) to %+.1f%% in %s (%s), median %+.1f%%; "
        "%d unit(s) lost population",
        first,
        last,
        change.min(),
        change.idxmin(),
        names[change.idxmin()],
        change.max(),
        change.idxmax(),
        names[change.idxmax()],
        change.median(),
        int((change < 0).sum()),
    )

    ranked = change.sort_values()
    log.table(
        f"population change {first}-{last}, by unit:",
        "\n".join(
            f"{code}  {names[code][:24].ljust(24)}  {int(wide.loc[code, first]):>9,}  "
            f"{int(wide.loc[code, last]):>9,}  {value:+8.1f}%"
            for code, value in ranked.items()
        ),
    )

    # What the study leaves out, in people. The warning itself is raised where the
    # file is read, so that a route which only borrows a year of the population
    # still carries it; here it is the table behind that warning.
    outside = units_outside_the_study(totals, units)
    in_study_years = outside[outside[config.YEAR_COL].between(first, last)]
    if in_study_years.empty:
        return

    log.table(
        f"the units the file carries and the study does not, {first} and {last}:",
        "\n".join(
            f"{row[_UNIT_CODE_COL]}  {row[config.POPULATION_SOURCE.name_column][:24].ljust(24)}  "
            f"{int(row[config.POPULATION_COL]):>9,}  {100 * row['SHARE_OF_CITY']:>6.3f}% of the city"
            for _, row in in_study_years[
                in_study_years[config.YEAR_COL].isin((first, last))
            ].iterrows()
        ),
    )
