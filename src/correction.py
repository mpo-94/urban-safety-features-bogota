"""The correction for the change in how casualties were recorded.

ρ(t) showed that the source changed practice: before 2018 a crash entered the
system with one casualty recorded, and from 2018 every affected party gets its
own record. The crash itself was always there — what was missing was the casualty
of the second party, and the diagnostic showed it was almost always the protected
one.

That is what makes the correction possible at all, and it is also what bounds it.
It does not inflate a pair's cell as a whole: it reclassifies crashes that today
carry a single affected party into crashes carrying two, and the party it adds is
the one that was already sitting in the party universe with no casualties against
its name. Nothing is invented; a party that took part is credited with the
casualty the source failed to write down.

Four decisions shape it, and all four are declared rather than inferred:

  the reference window is 2023-2024, the years ρ has settled in (D28);
  the reference is a city figure applied to every unit, because the per-unit
      denominators are far too thin to estimate a factor from (D28);
  the deficit is split between the two sides by the composition of the reference
      period, so the side that carries a surplus is the side it comes from (D29);
  2007 is out of the corrected set altogether, because that year does not
      distinguish the two parties of a vehicle-vehicle crash at all (D30).

The correction never replaces the observed data. A run produces both sets, and
the dataset each row belongs to travels in a column of every exported table (D31).

Run it with:

    python -m src.run_pipeline corrected
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

try:  # regular package import
    from src import config, parties, rho
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import parties  # type: ignore[no-redef]
    import rho  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# Working columns. They never leave this module, so they carry the leading
# underscore that says so.
_PARTY_ID_A = "_party_id_a"
_PARTY_ID_B = "_party_id_b"
_AFFECTED_A = "_affected_a"
_AFFECTED_B = "_affected_b"
_PROMOTED_TYPE = "_promoted_type"
_PROMOTED_PARTY = "_promoted_party"

SIDE_A = "A"
SIDE_B = "B"


class QuietLog:
    """A log that takes the accounting calls and drops them, passing warnings on.

    The verification rebuilds the outcome table from the corrected universe, which
    is a check and not a stage of the run. Its record counts must not land in the
    funnel beside the real ones, or the funnel would appear to process the same
    parties twice. Warnings and tables still go through: a check that falls silent
    exactly when something is wrong is worse than no check at all.
    """

    def __init__(self, inner: RunLog) -> None:
        self._inner = inner

    def record(self, *args: object, **kwargs: object) -> None:
        return None

    def info(self, *args: object, **kwargs: object) -> None:
        return None

    def dump(self, *args: object, **kwargs: object) -> None:
        return None

    def warn(self, message: str, *args: object) -> None:
        self._inner.warn(message, *args)

    def table(self, title: str, text: str) -> None:
        self._inner.table(title, text)


def corrected_years() -> tuple[int, ...]:
    """The years the corrected dataset spans: the study period minus the exclusions."""
    return tuple(
        year for year in config.STUDY_YEARS if year not in config.CORRECTION_EXCLUDED_YEARS
    )


def _short_pair(label: str) -> str:
    for long_name, abbreviation in (
        ("PEDESTRIAN", "PED"),
        ("BICYCLE", "BIC"),
        ("MOTORCYCLE", "MOT"),
        ("PUBLIC_TRANSPORT", "PT"),
    ):
        label = label.replace(long_name, abbreviation)
    return label


# ---------------------------------------------------------------------------
# The three outcomes of a two-party crash
# ---------------------------------------------------------------------------


def crash_outcomes(universe: pd.DataFrame, crash_attrs: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """One row per located two-party crash of the nine pairs, with its outcome.

    The same stages ρ runs, with one difference that is the whole point: the two
    sides keep their own affected flag instead of being reduced to their
    conjunction. ρ only needs to know whether both were hurt; the correction needs
    to know *which* one was not, because that is the party it will promote.

    Both party identifiers are carried through, so a crash chosen for
    reclassification can be traced back to the exact row of the universe that has
    to change.
    """
    rows_in = len(universe)
    party_count = universe.groupby(config.CRASH_ID_COL)[config.PARTY_ID_COL].transform("size")
    two_party = universe[party_count == 2].copy()

    # Canonical order inside the pair, least protected side first, exactly as ρ
    # orders it. Ties broken on the party identifier so a crash between two
    # parties of the same type still has a stable first and second.
    rank = {actor: position for position, actor in enumerate(config.RHO_PAIR_ORDER)}
    two_party["_rank"] = two_party[config.PARTY_TYPE_COL].map(lambda actor: rank.get(actor, len(rank)))
    two_party["_affected"] = (
        two_party[config.PERSONS_INJURED_COL] + two_party[config.PERSONS_KILLED_COL]
    ) > 0
    two_party = two_party.sort_values(
        [config.CRASH_ID_COL, "_rank", config.PARTY_ID_COL], kind="stable"
    )
    position = two_party.groupby(config.CRASH_ID_COL).cumcount()

    first = two_party[position == 0].set_index(config.CRASH_ID_COL)
    second = two_party[position == 1].set_index(config.CRASH_ID_COL)
    pairs = pd.DataFrame(
        {
            config.PAIR_FIRST_COL: first[config.PARTY_TYPE_COL],
            config.PAIR_SECOND_COL: second[config.PARTY_TYPE_COL].reindex(first.index),
            _PARTY_ID_A: first[config.PARTY_ID_COL],
            _PARTY_ID_B: second[config.PARTY_ID_COL].reindex(first.index),
            _AFFECTED_A: first["_affected"],
            _AFFECTED_B: second["_affected"].reindex(first.index),
        }
    ).reset_index()

    log.record(
        "collapse parties into two-party crashes, keeping both sides' outcome",
        rows_in=rows_in,
        rows_out=len(pairs),
        changes=[
            (
                -(rows_in - 2 * len(pairs)),
                "parties of single-party crashes, which have no counterpart to pair with",
            ),
            (-len(pairs), "the second party of each crash, folded into the row of its crash"),
        ],
    )

    kept = rho.restrict_to_pairs(pairs, log)
    placed = rho.place_in_time_and_space(kept, crash_attrs, log)

    placed[config.OUTCOME_COL] = np.select(
        [
            placed[_AFFECTED_A] & placed[_AFFECTED_B],
            placed[_AFFECTED_A] & ~placed[_AFFECTED_B],
            ~placed[_AFFECTED_A] & placed[_AFFECTED_B],
        ],
        [config.OUTCOME_BOTH, config.OUTCOME_ONLY_A, config.OUTCOME_ONLY_B],
        default=config.OUTCOME_NEITHER,
    )

    # The study universe is crashes with at least one casualty, so a two-party
    # crash with neither side affected cannot exist. Checked rather than assumed,
    # because everything below divides by counts that would be wrong if it did.
    stray = int((placed[config.OUTCOME_COL] == config.OUTCOME_NEITHER).sum())
    if stray:
        raise RuntimeError(
            f"{stray} two-party crash(es) have no affected party at all; "
            "the party universe disagrees with the study universe"
        )
    log.info(
        "check passed: all %d located two-party crashes of the nine pairs have an affected party",
        len(placed),
    )
    return placed


# ---------------------------------------------------------------------------
# The reference period
# ---------------------------------------------------------------------------


def pair_reference(outcomes: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """ρ and the composition of the three outcomes over the reference window, by pair.

    Pooled numerator over pooled denominator, not the mean of the annual ρ. The
    years of the window carry different numbers of crashes, and a mean of ratios
    would weigh a thin year the same as a thick one.
    """
    window = outcomes[outcomes[config.YEAR_COL].isin(config.CORRECTION_REFERENCE_YEARS)]
    counts = (
        window.pivot_table(
            index=config.PAIR_COL,
            columns=config.OUTCOME_COL,
            values=config.CRASH_ID_COL,
            aggfunc="count",
            fill_value=0,
        )
        .reindex(columns=[config.OUTCOME_ONLY_A, config.OUTCOME_ONLY_B, config.OUTCOME_BOTH], fill_value=0)
        .reindex(index=list(config.RHO_PAIR_LABELS), fill_value=0)
    )
    counts["TOTAL"] = counts.sum(axis=1)

    empty = counts.index[counts["TOTAL"] == 0].tolist()
    if empty:
        raise RuntimeError(
            f"no crashes in the reference window for {empty}; the correction has nothing to anchor on"
        )

    reference = pd.DataFrame(index=counts.index)
    reference[config.CORRECTION_RHO_REFERENCE_COL] = counts[config.OUTCOME_BOTH] / counts["TOTAL"]
    reference["SHARE_ONLY_A"] = counts[config.OUTCOME_ONLY_A] / counts["TOTAL"]
    reference["SHARE_ONLY_B"] = counts[config.OUTCOME_ONLY_B] / counts["TOTAL"]
    reference["CRASHES"] = counts["TOTAL"]

    lines = [f"{'pair':<12}  {'rho ref':>9}  {'only A':>9}  {'only B':>9}  {'crashes':>9}"]
    lines.append(f"{'-' * 12}  {'-' * 9}  {'-' * 9}  {'-' * 9}  {'-' * 9}")
    for label, row in reference.iterrows():
        lines.append(
            f"{_short_pair(label):<12}  {row[config.CORRECTION_RHO_REFERENCE_COL]:>9.4f}  "
            f"{row['SHARE_ONLY_A']:>9.4f}  {row['SHARE_ONLY_B']:>9.4f}  {int(row['CRASHES']):>9,}"
        )
    log.table(
        f"reference window {'-'.join(str(y) for y in config.CORRECTION_REFERENCE_YEARS)}, "
        "pooled numerator over pooled denominator:",
        "\n".join(lines),
    )
    return reference


def person_reference(universe: pd.DataFrame, outcomes: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """People per affected party, and the share of them killed, by actor type.

    A promoted party has to be given people, because a party is affected only by
    virtue of someone in it being hurt. How many comes from the reference window,
    measured over the affected parties of the same actor type in the same kind of
    crash — the two-party crashes of the nine pairs — since that is the population
    the promoted party belongs to.
    """
    window_crashes = set(
        outcomes.loc[
            outcomes[config.YEAR_COL].isin(config.CORRECTION_REFERENCE_YEARS), config.CRASH_ID_COL
        ]
    )
    in_window = universe[universe[config.CRASH_ID_COL].isin(window_crashes)]
    people = in_window[config.PERSONS_INJURED_COL] + in_window[config.PERSONS_KILLED_COL]
    affected = in_window[people > 0]

    grouped = affected.groupby(config.PARTY_TYPE_COL)[
        [config.PERSONS_INJURED_COL, config.PERSONS_KILLED_COL]
    ].sum()
    grouped["PARTIES"] = affected.groupby(config.PARTY_TYPE_COL).size()
    grouped["PERSONS"] = grouped[config.PERSONS_INJURED_COL] + grouped[config.PERSONS_KILLED_COL]
    grouped["PERSONS_PER_PARTY"] = grouped["PERSONS"] / grouped["PARTIES"]
    grouped["SHARE_KILLED"] = grouped[config.PERSONS_KILLED_COL] / grouped["PERSONS"]

    # A party is affected because someone in it was hurt, so the mean can never
    # fall below one. If it does, the affected flag and the person counts have
    # come apart somewhere upstream.
    below = grouped.index[grouped["PERSONS_PER_PARTY"] < 1.0].tolist()
    if below:
        raise RuntimeError(f"affected parties of type {below} average fewer than one person")

    lines = [f"{'actor type':<20}  {'parties':>9}  {'people':>9}  {'per party':>10}  {'killed':>9}"]
    lines.append(f"{'-' * 20}  {'-' * 9}  {'-' * 9}  {'-' * 10}  {'-' * 9}")
    for actor, row in grouped.iterrows():
        lines.append(
            f"{actor:<20}  {int(row['PARTIES']):>9,}  {int(row['PERSONS']):>9,}  "
            f"{row['PERSONS_PER_PARTY']:>10.4f}  {row['SHARE_KILLED']:>9.4f}"
        )
    log.table("people per affected party over the reference window, by actor type:", "\n".join(lines))
    return grouped


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


def _largest_remainder(weights: np.ndarray, total: int, caps: np.ndarray) -> np.ndarray:
    """Split an integer total across cells in proportion to weights, respecting caps.

    Rounding each cell's share on its own would leave the parts summing to
    something other than the whole, and the whole is a count of crashes that has
    to be exact. The floors go out first and the remainder to the largest
    fractional parts, skipping any cell already holding every crash it has.
    """
    if total <= 0:
        return np.zeros(len(weights), dtype=int)
    if caps.sum() < total:
        raise RuntimeError(
            f"asked to place {total} crashes into cells holding only {int(caps.sum())}"
        )

    weight_sum = weights.sum()
    if weight_sum <= 0:
        # Nothing to allocate in proportion to: spread over whatever can take it.
        weights = (caps > 0).astype(float)
        weight_sum = weights.sum()

    quota = total * weights / weight_sum
    allocation = np.minimum(np.floor(quota), caps).astype(int)
    remaining = int(total - allocation.sum())

    order = np.argsort(-(quota - np.floor(quota)), kind="stable")
    index = 0
    guard = 0
    while remaining > 0:
        cell = order[index % len(order)]
        if allocation[cell] < caps[cell]:
            allocation[cell] += 1
            remaining -= 1
        index += 1
        guard += 1
        if guard > len(order) * (total + 2):
            raise RuntimeError("the allocation failed to place every crash; the caps are inconsistent")
    return allocation


def build_plan(
    outcomes: pd.DataFrame, reference: pd.DataFrame, log: RunLog
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """How many crashes to reclassify, by pair, year, unit and side.

    Returns the plan itself, one row per unit cell that gains crashes, and the
    city table it was derived from, which carries every pair-year including the
    ones left alone and is what the verification reads.

    The deficit is computed at city level, because the reference is a city figure
    and the per-unit denominators are far too thin to carry one of their own. It
    is then spread over the units in proportion to the pool of convertible crashes
    each one actually holds, which is what "the change of practice was homogeneous
    between units" means when it is written as arithmetic.

    A pair-year whose ρ already sits at or above the reference is left alone, and
    so is every year of the reference window itself.
    """
    plan_rows: list[dict] = []
    city_rows: list[dict] = []

    # The excluded years leave before anything is planned, not after. Correcting a
    # year that the corrected set does not contain would spend part of the deficit
    # on crashes that are then dropped, and the record balance would not close.
    in_scope = outcomes[~outcomes[config.YEAR_COL].isin(config.CORRECTION_EXCLUDED_YEARS)]

    for (pair, year), group in in_scope.groupby([config.PAIR_COL, config.YEAR_COL], sort=True):
        reference_row = reference.loc[pair]
        rho_reference = reference_row[config.CORRECTION_RHO_REFERENCE_COL]

        total = len(group)
        outcome = group[config.OUTCOME_COL]
        both = int((outcome == config.OUTCOME_BOTH).sum())
        only_a = int((outcome == config.OUTCOME_ONLY_A).sum())
        only_b = int((outcome == config.OUTCOME_ONLY_B).sum())
        rho_observed = both / total

        in_window = year in config.CORRECTION_REFERENCE_YEARS
        # The target is a whole number of crashes: rho is a count over a count, and
        # a fractional crash cannot be reclassified.
        target = int(round(rho_reference * total))
        deficit = 0 if in_window or rho_observed >= rho_reference else max(0, target - both)

        # Where the reclassified crashes come from. In the reference period the
        # practice is complete, so its composition is the true one; the surplus a
        # side carries against that composition is the crashes on that side whose
        # second party went unrecorded. The two surpluses sum to the deficit
        # exactly, because the three shares sum to one on both sides of the
        # comparison, so clipping a negative one and giving the rest to the other
        # keeps the total whole.
        surplus_a = max(only_a - reference_row["SHARE_ONLY_A"] * total, 0.0)
        surplus_b = max(only_b - reference_row["SHARE_ONLY_B"] * total, 0.0)
        weight = surplus_a + surplus_b
        if deficit and weight > 0:
            from_a = min(int(round(deficit * surplus_a / weight)), only_a)
            from_b = min(deficit - from_a, only_b)
            from_a = deficit - from_b
        else:
            from_a = from_b = 0
        if from_a > only_a or from_b > only_b or from_a + from_b != deficit:
            raise RuntimeError(
                f"{pair} {year}: the split of a deficit of {deficit} into {from_a}+{from_b} "
                f"does not fit the pools ({only_a}, {only_b})"
            )

        city_rows.append(
            {
                config.PAIR_COL: pair,
                config.YEAR_COL: int(year),
                config.RHO_DENOMINATOR_COL: total,
                config.OUTCOME_ONLY_A: only_a,
                config.OUTCOME_ONLY_B: only_b,
                config.OUTCOME_BOTH: both,
                config.CORRECTION_RHO_OBSERVED_COL: rho_observed,
                config.CORRECTION_RHO_REFERENCE_COL: rho_reference,
                config.CORRECTION_DEFICIT_COL: deficit,
                "FROM_ONLY_A": from_a,
                "FROM_ONLY_B": from_b,
                config.CORRECTION_RHO_CORRECTED_COL: (both + deficit) / total,
                "IN_REFERENCE_WINDOW": in_window,
            }
        )

        if not deficit:
            continue

        # Spread each side's share over the units, in proportion to the crashes
        # each unit holds in the pool the reclassification draws from.
        for pool, side, count in (
            (config.OUTCOME_ONLY_A, SIDE_B, from_a),
            (config.OUTCOME_ONLY_B, SIDE_A, from_b),
        ):
            if not count:
                continue
            pool_crashes = group[group[config.OUTCOME_COL] == pool]
            by_unit = pool_crashes.groupby(
                [config.AREA_CODE_COL, config.AREA_NAME_COL], sort=True
            ).size()
            allocation = _largest_remainder(
                by_unit.to_numpy(dtype=float), count, by_unit.to_numpy(dtype=float)
            )
            promoted_type = (
                pair.split(config.RHO_PAIR_SEPARATOR)[1]
                if side == SIDE_B
                else pair.split(config.RHO_PAIR_SEPARATOR)[0]
            )
            for ((area_code, area_name), pool_size), allocated in zip(by_unit.items(), allocation):
                if not allocated:
                    continue
                plan_rows.append(
                    {
                        config.PAIR_COL: pair,
                        config.YEAR_COL: int(year),
                        config.AREA_CODE_COL: area_code,
                        config.AREA_NAME_COL: area_name,
                        config.CORRECTION_POOL_COL: pool,
                        config.CORRECTION_SIDE_COL: side,
                        config.PARTY_TYPE_COL: promoted_type,
                        "POOL_SIZE": int(pool_size),
                        config.CORRECTION_DEFICIT_COL: int(allocated),
                    }
                )

    city = pd.DataFrame(city_rows)
    plan = pd.DataFrame(plan_rows)

    placed = int(plan[config.CORRECTION_DEFICIT_COL].sum()) if len(plan) else 0
    wanted = int(city[config.CORRECTION_DEFICIT_COL].sum())
    if placed != wanted:
        raise RuntimeError(
            f"the city deficit is {wanted} crashes but {placed} were placed in units"
        )

    corrected = city[city[config.CORRECTION_DEFICIT_COL] > 0]
    log.info(
        "correction plan: %d crashes reclassified across %d pair-years of %d, in %d unit cells",
        wanted,
        len(corrected),
        len(city),
        len(plan),
    )
    return plan, city


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------


def select_promotions(
    outcomes: pd.DataFrame, plan: pd.DataFrame, persons: pd.DataFrame, log: RunLog
) -> pd.DataFrame:
    """Name the crashes to reclassify and the party each one gains.

    Which crashes inside a cell are chosen does not matter and cannot be known:
    every crash in a cell shares its pair, its year, its unit and the side that
    went unrecorded, so they are interchangeable for every purpose the study puts
    them to. They are taken in order of crash identifier, so the choice is at
    least the same on every run and can be audited.
    """
    chosen: list[pd.DataFrame] = []
    for _, cell in plan.iterrows():
        pool = outcomes[
            (outcomes[config.PAIR_COL] == cell[config.PAIR_COL])
            & (outcomes[config.YEAR_COL] == cell[config.YEAR_COL])
            & (outcomes[config.AREA_CODE_COL] == cell[config.AREA_CODE_COL])
            & (outcomes[config.OUTCOME_COL] == cell[config.CORRECTION_POOL_COL])
        ].sort_values(config.CRASH_ID_COL, kind="stable")
        take = pool.head(int(cell[config.CORRECTION_DEFICIT_COL])).copy()
        if len(take) != int(cell[config.CORRECTION_DEFICIT_COL]):
            raise RuntimeError(
                f"cell {cell[config.PAIR_COL]} {cell[config.YEAR_COL]} "
                f"{cell[config.AREA_CODE_COL]} holds {len(pool)} crashes but "
                f"{int(cell[config.CORRECTION_DEFICIT_COL])} were asked for"
            )
        take[_PROMOTED_PARTY] = (
            take[_PARTY_ID_B] if cell[config.CORRECTION_SIDE_COL] == SIDE_B else take[_PARTY_ID_A]
        )
        take[_PROMOTED_TYPE] = cell[config.PARTY_TYPE_COL]
        take[config.CORRECTION_SIDE_COL] = cell[config.CORRECTION_SIDE_COL]
        take[config.CORRECTION_POOL_COL] = cell[config.CORRECTION_POOL_COL]
        chosen.append(take)

    promotions = pd.concat(chosen, ignore_index=True) if chosen else pd.DataFrame()
    if promotions.empty:
        return promotions

    duplicated = int(promotions.duplicated(config.CRASH_ID_COL).sum())
    if duplicated:
        raise RuntimeError(f"{duplicated} crash(es) were chosen twice; a crash gains at most one party")

    promotions = _assign_people(promotions, persons)
    log.info(
        "selected %d crashes to reclassify; they gain %d parties, %d injured and %d killed",
        len(promotions),
        len(promotions),
        int(promotions[config.PERSONS_INJURED_COL].sum()),
        int(promotions[config.PERSONS_KILLED_COL].sum()),
    )
    return promotions


def _assign_people(promotions: pd.DataFrame, persons: pd.DataFrame) -> pd.DataFrame:
    """Give every promoted party its people, keeping injured and killed apart.

    The rates are means over the reference window and the parties are whole, so
    the totals are rounded once per group and then handed out inside it. Every
    promoted party gets at least one person, which is not a safeguard but the
    definition: a party is affected precisely because someone in it was hurt.
    """
    promotions = promotions.sort_values(
        [config.PAIR_COL, config.YEAR_COL, _PROMOTED_TYPE, config.CRASH_ID_COL], kind="stable"
    ).reset_index(drop=True)

    people = np.zeros(len(promotions), dtype=int)

    # People first, group by group. The mean is close to one and the groups are
    # large, so rounding here is small and falls either way.
    for (_, _, actor), group in promotions.groupby(
        [config.PAIR_COL, config.YEAR_COL, _PROMOTED_TYPE], sort=False
    ):
        rates = persons.loc[actor]
        size = len(group)
        total_people = max(int(round(size * rates["PERSONS_PER_PARTY"])), size)

        # One person each, then the surplus spread evenly so no party collects a
        # second occupant before every party has a first.
        allocated = np.ones(size, dtype=int)
        surplus = total_people - size
        allocated += surplus // size
        allocated[: surplus % size] += 1
        people[group.index] = allocated

    # The killed are allocated per actor type over all its promoted parties at
    # once, not group by group. The share of people killed is well under one per
    # cent for a car occupant, so a group of a few hundred expects a fraction of a
    # death and would round to none every single time. Rounded per group the
    # deaths would vanish; rounded once for the actor type they do not. Deaths are
    # three per cent of the record and the whole design goes out of its way not to
    # bury them, so this is not a place to let rounding decide.
    killed = np.zeros(len(promotions), dtype=int)
    for actor, group in promotions.groupby(_PROMOTED_TYPE, sort=False):
        rates = persons.loc[actor]
        in_group = people[group.index]
        target = int(round(in_group.sum() * rates["SHARE_KILLED"]))
        # Weighted by the people each party holds, and capped by them, so no party
        # is credited with more deaths than it has occupants.
        killed[group.index] = _largest_remainder(
            in_group.astype(float), target, in_group.astype(float)
        )

    promotions[config.PERSONS_INJURED_COL] = people - killed
    promotions[config.PERSONS_KILLED_COL] = killed
    return promotions


def promote(universe: pd.DataFrame, promotions: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """Credit each promoted party with the casualty the source did not record.

    The party is already in the universe — it took part in the crash and was
    carried through precisely so its counterpart could be resolved. All that
    changes is that its person counts stop being zero.
    """
    corrected = universe.copy()
    key = [config.CRASH_ID_COL, config.PARTY_ID_COL]

    additions = promotions[
        [config.CRASH_ID_COL, _PROMOTED_PARTY, config.PERSONS_INJURED_COL, config.PERSONS_KILLED_COL]
    ].rename(
        columns={
            _PROMOTED_PARTY: config.PARTY_ID_COL,
            config.PERSONS_INJURED_COL: "_add_injured",
            config.PERSONS_KILLED_COL: "_add_killed",
        }
    )

    rows_before = len(corrected)
    corrected = corrected.merge(additions, on=key, how="left")
    if len(corrected) != rows_before:
        raise RuntimeError("promoting parties changed the row count of the universe")

    matched = int(corrected["_add_injured"].notna().sum())
    if matched != len(promotions):
        raise RuntimeError(
            f"{len(promotions)} parties were to be promoted but {matched} matched the universe"
        )

    # The parties being promoted must be the ones the source left with nothing
    # against their name. Anything else would mean the outcome table and the
    # universe disagree about who was hurt.
    promoted = corrected["_add_injured"].notna()
    already = int(
        (
            corrected.loc[promoted, config.PERSONS_INJURED_COL]
            + corrected.loc[promoted, config.PERSONS_KILLED_COL]
        ).gt(0).sum()
    )
    if already:
        raise RuntimeError(f"{already} of the parties to promote already carried casualties")

    corrected[config.PERSONS_INJURED_COL] += corrected["_add_injured"].fillna(0).astype(int)
    corrected[config.PERSONS_KILLED_COL] += corrected["_add_killed"].fillna(0).astype(int)
    corrected = corrected.drop(columns=["_add_injured", "_add_killed"])

    log.record(
        "promote the parties whose casualty was not recorded",
        rows_in=rows_before,
        rows_out=len(corrected),
        changes=[],
        notes=[
            f"{len(promotions):,} parties went from no casualty to at least one; no row was "
            f"added or removed, because the party was already in the universe",
            f"{int(promotions[config.PERSONS_INJURED_COL].sum()):,} injured and "
            f"{int(promotions[config.PERSONS_KILLED_COL].sum()):,} killed were credited to them",
        ],
    )
    return corrected


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export(plan: pd.DataFrame, city: pd.DataFrame, reference: pd.DataFrame,
           persons: pd.DataFrame, log: RunLog) -> dict[str, Path]:
    """Write the correction itself, so it can be audited rather than believed."""
    data_dir = log.run_dir / config.DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    for name, frame, index in (
        ("plan", plan, False),
        ("city", city, False),
        ("reference", reference.reset_index(), False),
        ("person_rates", persons.reset_index(), False),
    ):
        path = data_dir / f"{config.ANALYSIS_PREFIX}__correction_{name}.csv"
        frame.to_csv(path, index=index, encoding="utf-8")
        paths[name] = path

    log.info("exported %d correction tables to %s/", len(paths), config.DATA_SUBDIR)
    return paths


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(
    city: pd.DataFrame,
    corrected_outcomes: pd.DataFrame,
    observed_matrix: pd.DataFrame,
    corrected_matrix: pd.DataFrame,
    promotions: pd.DataFrame,
    log: RunLog,
) -> bool:
    """Check the corrected set against the five things the design promises."""
    checks: list[tuple[str, bool, str]] = []

    # 1. rho of the corrected set lands on the reference in every corrected year.
    recomputed = (
        corrected_outcomes.assign(
            _both=corrected_outcomes[config.OUTCOME_COL] == config.OUTCOME_BOTH
        )
        .groupby([config.PAIR_COL, config.YEAR_COL])["_both"]
        .agg(["sum", "size"])
    )
    recomputed["rho"] = recomputed["sum"] / recomputed["size"]
    touched = city[city[config.CORRECTION_DEFICIT_COL] > 0].set_index(
        [config.PAIR_COL, config.YEAR_COL]
    )
    joined = touched.join(recomputed[["rho", "size"]], how="left")
    # The target is a whole number of crashes, so rho can miss the reference by up
    # to the value of one crash. Anything beyond that is an error, not rounding.
    allowed = config.CORRECTION_RHO_TOLERANCE_CRASHES / joined["size"]
    deviation = (joined["rho"] - joined[config.CORRECTION_RHO_REFERENCE_COL]).abs()
    worst = float((deviation - allowed).max()) if len(joined) else 0.0
    checks.append(
        (
            "corrected rho equals the reference in every corrected pair-year",
            bool((deviation <= allowed).all()),
            f"{len(joined)} pair-years, worst excess over the one-crash tolerance {worst:+.2e}",
        )
    )

    # 2. the reference window is untouched.
    in_window = city[city["IN_REFERENCE_WINDOW"]]
    checks.append(
        (
            "no crash reclassified inside the reference window",
            bool((in_window[config.CORRECTION_DEFICIT_COL] == 0).all()),
            f"{int(in_window[config.CORRECTION_DEFICIT_COL].sum())} reclassified in "
            f"{'-'.join(str(y) for y in config.CORRECTION_REFERENCE_YEARS)}",
        )
    )

    # 3. the excluded years are absent from the corrected set.
    present = set(corrected_matrix[config.YEAR_COL].dropna().astype(int))
    excluded = set(config.CORRECTION_EXCLUDED_YEARS)
    checks.append(
        (
            "the excluded years are absent from the corrected matrix",
            not (present & excluded),
            f"{sorted(present & excluded) or 'none'} present; span "
            f"{min(present)}-{max(present)}",
        )
    )

    # 4. no cell of the corrected matrix is below its observed counterpart. The
    # correction only ever adds, so a cell that fell means it added in the wrong
    # place and took from somewhere else.
    keys = [
        config.AREA_CODE_COL,
        config.YEAR_COL,
        config.PARTY_TYPE_COL,
        config.COUNTERPART_TYPE_COL,
    ]
    counts = list(config.MATRIX_COUNTS.values())
    comparison = observed_matrix.merge(
        corrected_matrix, on=keys, how="inner", suffixes=("_observed", "_corrected")
    )
    fell = 0
    for column in counts:
        fell += int((comparison[f"{column}_corrected"] < comparison[f"{column}_observed"]).sum())
    checks.append(
        (
            "no cell of the corrected matrix is below the observed one",
            fell == 0,
            f"{fell} cells fell, over {len(comparison):,} shared cells and {len(counts)} counts",
        )
    )

    # 5. the record balance closes: what the corrected matrix holds beyond the
    # observed one is exactly what the plan said it would add.
    for name, column, planned in (
        ("parties", config.AFFECTED_PARTIES_COL, len(promotions)),
        ("injured", config.PERSONS_INJURED_COL, int(promotions[config.PERSONS_INJURED_COL].sum())),
        ("killed", config.PERSONS_KILLED_COL, int(promotions[config.PERSONS_KILLED_COL].sum())),
    ):
        # 2007 is in the observed matrix and out of the corrected one, so it has
        # to come off the observed side before the two can be compared.
        comparable = observed_matrix[
            ~observed_matrix[config.YEAR_COL].isin(config.CORRECTION_EXCLUDED_YEARS)
        ]
        difference = int(corrected_matrix[column].sum()) - int(comparable[column].sum())
        checks.append(
            (
                f"{name}: the corrected total exceeds the observed one by exactly the plan",
                difference == planned,
                f"{difference:+,} observed, {planned:+,} planned",
            )
        )

    width = max(len(name) for name, _, _ in checks)
    lines = [f"{'check'.ljust(width)}  {'result':>8}  detail", f"{'-' * width}  {'-' * 8}  ------"]
    for name, ok, detail in checks:
        lines.append(f"{name.ljust(width)}  {'OK' if ok else 'FAILED':>8}  {detail}")
    log.table("correction verification:", "\n".join(lines))

    passed = all(ok for _, ok, _ in checks)
    if not passed:
        log.warn("correction verification FAILED")
    return passed


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def report(city: pd.DataFrame, plan: pd.DataFrame, promotions: pd.DataFrame, log: RunLog) -> None:
    by_year = city.groupby(config.YEAR_COL)[
        [config.CORRECTION_DEFICIT_COL, "FROM_ONLY_A", "FROM_ONLY_B", config.RHO_DENOMINATOR_COL]
    ].sum()
    lines = [
        f"{'year':>6}  {'crashes':>9}  {'reclassified':>13}  {'B added':>9}  {'A added':>9}  {'share':>7}"
    ]
    lines.append(f"{'-' * 6}  {'-' * 9}  {'-' * 13}  {'-' * 9}  {'-' * 9}  {'-' * 7}")
    for year, row in by_year.iterrows():
        total = row[config.RHO_DENOMINATOR_COL]
        lines.append(
            f"{int(year):>6}  {int(total):>9,}  {int(row[config.CORRECTION_DEFICIT_COL]):>13,}  "
            f"{int(row['FROM_ONLY_A']):>9,}  {int(row['FROM_ONLY_B']):>9,}  "
            f"{100 * row[config.CORRECTION_DEFICIT_COL] / total:>6.1f}%"
        )
    log.table(
        "crashes reclassified by year (B added = the protected side was the one missing):",
        "\n".join(lines),
    )

    by_pair = city.groupby(config.PAIR_COL)[
        [config.CORRECTION_DEFICIT_COL, "FROM_ONLY_A", "FROM_ONLY_B", config.RHO_DENOMINATOR_COL]
    ].sum()
    lines = [f"{'pair':<12}  {'crashes':>9}  {'reclassified':>13}  {'share':>7}  {'from only A':>12}"]
    lines.append(f"{'-' * 12}  {'-' * 9}  {'-' * 13}  {'-' * 7}  {'-' * 12}")
    for label in config.RHO_PAIR_LABELS:
        row = by_pair.loc[label]
        deficit = row[config.CORRECTION_DEFICIT_COL]
        share = row["FROM_ONLY_A"] / deficit if deficit else float("nan")
        lines.append(
            f"{_short_pair(label):<12}  {int(row[config.RHO_DENOMINATOR_COL]):>9,}  "
            f"{int(deficit):>13,}  "
            f"{100 * deficit / row[config.RHO_DENOMINATOR_COL]:>6.1f}%  {share:>12.3f}"
        )
    log.table("crashes reclassified by pair, and the share drawn from the only-A pool:", "\n".join(lines))

    added = promotions.groupby(_PROMOTED_TYPE).agg(
        parties=(config.CRASH_ID_COL, "size"),
        injured=(config.PERSONS_INJURED_COL, "sum"),
        killed=(config.PERSONS_KILLED_COL, "sum"),
    )
    lines = [f"{'actor type':<20}  {'parties':>9}  {'injured':>9}  {'killed':>8}"]
    lines.append(f"{'-' * 20}  {'-' * 9}  {'-' * 9}  {'-' * 8}")
    for actor, row in added.iterrows():
        lines.append(
            f"{actor:<20}  {int(row['parties']):>9,}  {int(row['injured']):>9,}  {int(row['killed']):>8,}"
        )
    lines.append(f"{'-' * 20}  {'-' * 9}  {'-' * 9}  {'-' * 8}")
    lines.append(
        f"{'total':<20}  {int(added['parties'].sum()):>9,}  "
        f"{int(added['injured'].sum()):>9,}  {int(added['killed'].sum()):>8,}"
    )
    log.table("parties added by actor type:", "\n".join(lines))

    units_touched = plan[config.AREA_CODE_COL].nunique()
    log.info(
        "the correction reaches %d units and %d pair-year-unit cells",
        units_touched,
        len(plan),
    )


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


def apply(
    universe: pd.DataFrame, crash_attrs: pd.DataFrame, log: RunLog
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Build the corrected party universe, and everything needed to check it.

    Returns the corrected universe and the intermediate tables, so the route can
    export them, verify against them and report from them without recomputing any
    of it.
    """
    outcomes = crash_outcomes(universe, crash_attrs, log)
    reference = pair_reference(outcomes, log)
    persons = person_reference(universe, outcomes, log)
    plan, city = build_plan(outcomes, reference, log)
    promotions = select_promotions(outcomes, plan, persons, log)
    corrected = promote(universe, promotions, log)

    log.dump(plan, "07_correction_plan")
    log.dump(city, "07_correction_city")
    log.dump(promotions.drop(columns=[_PARTY_ID_A, _PARTY_ID_B]), "07_correction_promotions")

    return corrected, {
        "outcomes": outcomes,
        "reference": reference,
        "persons": persons,
        "plan": plan,
        "city": city,
        "promotions": promotions,
    }
