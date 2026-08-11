"""Party resolution and pairing.

Turns the casualty set and the vehicle table into one row per affected party,
each with the actor type of its counterpart.

A crash is a set of parties. A party is a vehicle with its occupants, or an
individual pedestrian, and carries an actor type and a casualty count that may be
zero. Parties with no casualties never emit a row, but they are what makes the
counterpart of the other parties knowable, and they count towards the two-party
threshold.

Run it directly to execute the stage:

    python -m src.parties
"""

from __future__ import annotations

import numpy as np
import pandas as pd

try:  # regular package import
    from src import config, loading
    from src.provenance import RunLog
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]
    import loading  # type: ignore[no-redef]
    from provenance import RunLog  # type: ignore[no-redef]


# Internal working columns, dropped before the result is returned.
_PARTY_KEY = "_party_key"
_PARTY_TYPE = "_party_type"


def verify_person_identifier(casualties: pd.DataFrame, log: RunLog) -> str:
    """Decide what identifies a person, and report the evidence either way.

    The source column is preferred because it allows going back to the original
    record. It is only usable if it identifies a person uniquely within a crash,
    which is measured here rather than assumed. If it does not, the row position
    in the casualty set is used instead: it identifies each person by
    construction, and inventing a composite key would only hide the problem.
    """
    total = len(casualties)
    null_ids = int(casualties[config.PERSON_ID_COL].isna().sum())
    duplicated = casualties.duplicated(subset=[config.CRASH_ID_COL, config.PERSON_ID_COL], keep=False)
    colliding_pairs = int(
        casualties.loc[duplicated].groupby([config.CRASH_ID_COL, config.PERSON_ID_COL]).ngroups
    )

    # A collision inside one layer means the source reuses the code for two
    # different people. A collision across layers is more likely the same person
    # recorded twice, which is a different problem with a different fix.
    within_layer = across_layers = 0
    if colliding_pairs:
        spans = casualties.loc[duplicated].groupby([config.CRASH_ID_COL, config.PERSON_ID_COL])[
            config.CASUALTY_SOURCE_COL
        ].nunique()
        across_layers = int((spans > 1).sum())
        within_layer = int((spans == 1).sum())

    log.info("person identifier check on the concatenated casualty set (%d rows):", total)
    log.info("    colliding (crash, person) pairs : %d", colliding_pairs)
    log.info("    rows with a null person code    : %d", null_ids)
    log.info("    collisions inside a single layer: %d", within_layer)
    log.info("    collisions spanning both layers : %d", across_layers)

    if colliding_pairs == 0 and null_ids == 0:
        log.info("    -> the source person code is unique within a crash; using it")
        return config.PERSON_ID_COL

    log.warn(
        "the source person code is not unique within a crash (%d colliding pair(s), %d null); "
        "falling back to row position, which identifies a person by construction",
        colliding_pairs,
        null_ids,
    )
    if across_layers and not within_layer:
        log.warn(
            "all %d collisions span both layers, which is what the same person recorded twice "
            "looks like; those people are counted twice until the duplication is settled",
            across_layers,
        )
    return "__row_position__"


def check_cross_layer_duplication(casualties: pd.DataFrame, log: RunLog) -> int:
    """Count people that appear in both source layers, every run, whatever the count.

    Separate counts of injured and killed only mean anything if the two layers
    are mutually exclusive. A person present in both is counted twice, once in
    each category, so this number must stay visible: if a future extract makes it
    grow, the person counts are inflated and it has to be obvious immediately.
    """
    duplicated = casualties.duplicated(subset=[config.CRASH_ID_COL, config.PERSON_ID_COL], keep=False)
    spanning = 0
    if duplicated.any():
        layers = casualties.loc[duplicated].groupby([config.CRASH_ID_COL, config.PERSON_ID_COL])[
            config.CASUALTY_SOURCE_COL
        ].nunique()
        spanning = int((layers > 1).sum())

    log.record(
        "cross-layer duplication check",
        rows_in=len(casualties),
        rows_out=len(casualties),
        notes=[
            f"{spanning} person(s) appear in both the fatality and the injury layer, "
            f"so {2 * spanning} records describe {spanning} people and the person counts "
            f"are inflated by {spanning}",
            "the two layers are assumed mutually exclusive; this is the check on that assumption",
        ],
    )
    if spanning:
        log.warn(
            "%d person(s) are recorded in both source layers; they are counted twice until "
            "the interpretation is settled",
            spanning,
        )
    return spanning


def build_parties(casualties: pd.DataFrame, vehicles: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """Build the party universe: every party of every crash in scope, with its
    actor type and its casualty counts."""
    person_key = verify_person_identifier(casualties, log)

    casualties = casualties.copy()
    if person_key == "__row_position__":
        casualties["_person_key"] = np.arange(len(casualties)).astype(str)
    else:
        casualties["_person_key"] = casualties[person_key].astype(str)

    crash_ids = casualties[config.CRASH_ID_COL].dropna().unique()

    # -- vehicle parties ----------------------------------------------------
    in_scope = vehicles[vehicles[config.CRASH_ID_COL].isin(crash_ids)].copy()
    rows_before = len(in_scope)
    in_scope = in_scope.dropna(subset=[config.VEHICLE_ID_COL])
    dropped_no_id = rows_before - len(in_scope)

    duplicated_keys = int(in_scope.duplicated([config.CRASH_ID_COL, config.VEHICLE_ID_COL]).sum())
    if duplicated_keys:
        log.warn("%d vehicle rows share a (crash, vehicle) key and would merge into one party", duplicated_keys)
    in_scope = in_scope.drop_duplicates([config.CRASH_ID_COL, config.VEHICLE_ID_COL])

    normalized = in_scope["CLASE"].map(config.normalize_vehicle_type)
    mapped = normalized.map(config.VEHICLE_TYPE_MAP)
    unrecognised = int(mapped.isna().sum())
    if unrecognised:
        # Never a null: a vehicle whose type is unknown is still a vehicle, and a
        # null here is what made whole crashes disappear from the legacy run.
        offenders = in_scope.loc[mapped.isna(), "CLASE"].fillna("<null>").value_counts().head(5).to_dict()
        log.warn(
            "%d vehicle parties have an unrecognised type and fall back to %s; most common: %s",
            unrecognised,
            config.VEHICLE_TYPE_FALLBACK,
            offenders,
        )
    in_scope[_PARTY_TYPE] = mapped.fillna(config.VEHICLE_TYPE_FALLBACK)
    in_scope[_PARTY_KEY] = "V" + in_scope[config.VEHICLE_ID_COL].astype(int).astype(str)

    causes = [
        (-(len(vehicles) - rows_before), "vehicle rows of crashes with no casualty (out of study scope)"),
        (-dropped_no_id, "vehicle rows with no vehicle code, which cannot form a party"),
        (-duplicated_keys, "vehicle rows sharing a (crash, vehicle) key"),
    ]
    log.record(
        "build vehicle parties",
        rows_in=len(vehicles),
        rows_out=len(in_scope),
        changes=[(delta, cause) for delta, cause in causes if delta],
        notes=[f"{unrecognised} parties with an unrecognised type routed to {config.VEHICLE_TYPE_FALLBACK}"],
    )

    # -- attach casualties to vehicle parties -------------------------------
    linked = casualties.merge(
        in_scope[[config.CRASH_ID_COL, config.VEHICLE_ID_COL, _PARTY_KEY, _PARTY_TYPE]],
        left_on=[config.CRASH_ID_COL, config.VEHICLE_ID_COL_IN_CASUALTIES],
        right_on=[config.CRASH_ID_COL, config.VEHICLE_ID_COL],
        how="left",
    )
    if len(linked) != len(casualties):
        raise RuntimeError(
            f"attaching casualties to vehicle parties changed the row count "
            f"({len(casualties)} -> {len(linked)}); the vehicle key is not unique"
        )

    standalone = linked[_PARTY_KEY].isna()
    no_reference = standalone & linked[config.VEHICLE_ID_COL_IN_CASUALTIES].isna()
    dangling = standalone & linked[config.VEHICLE_ID_COL_IN_CASUALTIES].notna()

    # A casualty with no vehicle of its own is a party in itself, and its actor
    # type comes from the role on the form. The two situations use different
    # evidence on purpose: where a vehicle is recorded it decides, because it
    # resolves to a real party of the crash; where none is, the role is all there
    # is. The legacy pipeline called every one of these cases a pedestrian and
    # inflated that row of the matrix.
    role = linked.loc[standalone, config.ROLE_COL]
    from_role = role.map(config.ROLE_TO_ACTOR_TYPE)
    linked.loc[standalone, _PARTY_KEY] = "P" + linked.loc[standalone, "_person_key"]
    linked.loc[standalone, _PARTY_TYPE] = from_role.fillna(config.VEHICLE_TYPE_FALLBACK)

    recovered = int(role.isin(config.ROLES_RESOLVING_TO_A_MODE).sum())
    as_pedestrian = int(from_role.eq(config.PEDESTRIAN).sum())
    residual_by_rule = int(from_role.eq(config.VEHICLE_TYPE_FALLBACK).sum())
    unlisted = role[~role.isin(config.ROLE_TO_ACTOR_TYPE)]
    unlisted_values = unlisted.dropna().value_counts().to_dict()
    no_role = int(unlisted.isna().sum())
    if unlisted_values or no_role:
        # Not classified on a guess: an unforeseen role is a question for the
        # person who owns the methodology, not something to resolve in passing.
        log.warn(
            "%d standalone casualties carry a role absent from the role mapping and go to %s: %s%s",
            len(unlisted),
            config.VEHICLE_TYPE_FALLBACK,
            unlisted_values or "{}",
            f" plus {no_role} with no role recorded" if no_role else "",
        )

    pedestrian_in_vehicle = int((~standalone & linked[config.ROLE_COL].eq(config.PEDESTRIAN_ROLE)).sum())
    log.record(
        "attach casualties to parties",
        rows_in=len(casualties),
        rows_out=len(linked),
        notes=[
            f"{int((~standalone).sum())} casualties ride a recorded vehicle party",
            f"{int(no_reference.sum())} casualties name no vehicle and become a party of their own",
            f"{int(dangling.sum())} casualties name a vehicle absent from the vehicle table, "
            f"also treated as a party of their own",
            f"standalone typing by role: {as_pedestrian} pedestrian, {recovered} placed by a role that "
            f"implies the mode on its own, {residual_by_rule} sent to {config.VEHICLE_TYPE_FALLBACK} "
            f"because the role does not imply protection, {len(unlisted)} with an unlisted or absent role",
            f"{pedestrian_in_vehicle} casualties are recorded as pedestrians yet ride a vehicle party; "
            f"the vehicle reference is followed",
        ],
    )

    # -- party universe -----------------------------------------------------
    casualty_parties = linked.loc[standalone, [config.CRASH_ID_COL, _PARTY_KEY, _PARTY_TYPE]]
    parties = pd.concat(
        [in_scope[[config.CRASH_ID_COL, _PARTY_KEY, _PARTY_TYPE]], casualty_parties],
        ignore_index=True,
    )
    collisions = int(parties.duplicated([config.CRASH_ID_COL, _PARTY_KEY]).sum())
    if collisions:
        raise RuntimeError(f"{collisions} party keys collide within a crash; the party model is unsound")

    counts = (
        linked.assign(
            _injured=linked[config.CASUALTY_SOURCE_COL].eq(config.INJURY_SOURCE).astype(int),
            _killed=linked[config.CASUALTY_SOURCE_COL].eq(config.FATALITY_SOURCE).astype(int),
        )
        .groupby([config.CRASH_ID_COL, _PARTY_KEY], as_index=False)[["_injured", "_killed"]]
        .sum()
    )
    parties = parties.merge(counts, on=[config.CRASH_ID_COL, _PARTY_KEY], how="left")
    parties[["_injured", "_killed"]] = parties[["_injured", "_killed"]].fillna(0).astype(int)

    log.record(
        "assemble party universe",
        rows_in=len(in_scope),
        rows_out=len(parties),
        changes=[(len(casualty_parties), "casualties with no vehicle of their own, each its own party")],
        notes=[
            f"{int((parties[['_injured', '_killed']].sum(axis=1) == 0).sum())} parties took part without casualties; "
            f"they emit no row but determine the counterpart of the others",
        ],
    )
    return parties


def resolve_pairs(parties: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """Apply the two-party threshold and give every party its counterpart."""
    party_count = parties.groupby(config.CRASH_ID_COL)[_PARTY_KEY].transform("size")

    crashes_before = parties[config.CRASH_ID_COL].nunique()
    over_threshold = party_count > config.MAX_PARTIES_PER_CRASH
    discarded_crashes = parties.loc[over_threshold, config.CRASH_ID_COL].nunique()

    kept = parties.loc[~over_threshold].copy()
    log.record(
        "apply the two-party threshold",
        rows_in=len(parties),
        rows_out=len(kept),
        changes=[
            (
                -int(over_threshold.sum()),
                f"parties of the {discarded_crashes:,} crashes with more than "
                f"{config.MAX_PARTIES_PER_CRASH} recorded parties",
            )
        ],
        notes=[f"{crashes_before - discarded_crashes:,} of {crashes_before:,} crashes survive the threshold"],
    )

    # With at most two parties the counterpart is simply the other one, so no
    # ordering rule is needed and none is applied. Position, not value, decides
    # which of the two is the other, so a crash between two parties of the same
    # type still resolves correctly.
    kept = kept.sort_values([config.CRASH_ID_COL, _PARTY_KEY], kind="stable")
    grouped = kept.groupby(config.CRASH_ID_COL)[_PARTY_TYPE]
    position = grouped.cumcount()
    kept[config.COUNTERPART_TYPE_COL] = np.where(
        grouped.transform("size") == 1,
        config.SELF_COUNTERPART,
        np.where(position == 0, grouped.transform("last"), grouped.transform("first")),
    )
    return kept


def emit_rows(kept: pd.DataFrame, casualties: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """Keep the parties that suffered casualties and attach the crash attributes."""
    affected = kept[kept[["_injured", "_killed"]].sum(axis=1) > 0].copy()

    # The study universe is crashes with at least one casualty, so a crash that
    # keeps parties but emits nothing should be impossible. Reported either way:
    # a check that only speaks up when it fails leaves no evidence that it ran.
    crashes_with_parties = kept[config.CRASH_ID_COL].nunique()
    crashes_emitting = affected[config.CRASH_ID_COL].nunique()
    silent_crashes = crashes_with_parties - crashes_emitting
    if silent_crashes:
        log.warn(
            "%d crash(es) kept parties but no party of theirs suffered a casualty; "
            "this contradicts the study universe and needs investigating",
            silent_crashes,
        )
    else:
        log.info(
            "check passed: all %d surviving crashes have at least one party with casualties",
            crashes_with_parties,
        )

    log.record(
        "keep the parties that suffered casualties",
        rows_in=len(kept),
        rows_out=len(affected),
        changes=[(-(len(kept) - len(affected)), "parties that took part without casualties")],
    )

    # Crash attributes are taken once per crash. They were verified to agree
    # across a crash's victims, except where one victim could not be located, so
    # the first non-null wins.
    attrs = (
        casualties.sort_values(config.AREA_CODE_COL, na_position="last")
        .groupby(config.CRASH_ID_COL, as_index=False)
        .agg(
            **{
                config.YEAR_COL: (config.YEAR_SOURCE_COL, "first"),
                config.CRASH_CLASS_COL: (config.CRASH_CLASS_SOURCE_COL, "first"),
                config.AREA_CODE_COL: (config.AREA_CODE_COL, "first"),
                config.AREA_NAME_COL: (config.AREA_NAME_COL, "first"),
            }
        )
    )
    rows_before = len(affected)
    affected = affected.merge(attrs, on=config.CRASH_ID_COL, how="left")
    if len(affected) != rows_before:
        raise RuntimeError("attaching crash attributes changed the row count")

    result = affected.rename(
        columns={
            _PARTY_KEY: config.PARTY_ID_COL,
            _PARTY_TYPE: config.PARTY_TYPE_COL,
            "_injured": config.PERSONS_INJURED_COL,
            "_killed": config.PERSONS_KILLED_COL,
        }
    )
    # The party is the counting unit: one party with casualties counts once,
    # however many of its occupants were hurt. The person counts sit beside it so
    # a party matrix and a person matrix come out of the same run.
    result[config.AFFECTED_PARTIES_COL] = 1
    result[config.YEAR_COL] = result[config.YEAR_COL].astype("Int64")

    columns = [
        config.CRASH_ID_COL,
        config.PARTY_ID_COL,
        config.PARTY_TYPE_COL,
        config.COUNTERPART_TYPE_COL,
        config.AFFECTED_PARTIES_COL,
        config.PERSONS_INJURED_COL,
        config.PERSONS_KILLED_COL,
        config.AREA_CODE_COL,
        config.AREA_NAME_COL,
        config.YEAR_COL,
        config.CRASH_CLASS_COL,
    ]
    return result[columns].sort_values([config.CRASH_ID_COL, config.PARTY_ID_COL]).reset_index(drop=True)


def check_person_balance(result: pd.DataFrame, casualties: pd.DataFrame, parties: pd.DataFrame, log: RunLog) -> None:
    """The people on the emitted rows must account for everyone who came in."""
    party_count = parties.groupby(config.CRASH_ID_COL)[_PARTY_KEY].transform("size")
    discarded_crashes = set(parties.loc[party_count > config.MAX_PARTIES_PER_CRASH, config.CRASH_ID_COL])
    lost_to_threshold = int(casualties[config.CRASH_ID_COL].isin(discarded_crashes).sum())

    emitted = int(result[config.PERSONS_INJURED_COL].sum() + result[config.PERSONS_KILLED_COL].sum())
    log.record(
        "person balance across the stage",
        rows_in=len(casualties),
        rows_out=emitted,
        changes=[(-lost_to_threshold, f"people in crashes discarded by the {config.MAX_PARTIES_PER_CRASH}-party threshold")],
        notes=[
            f"{int(result[config.PERSONS_INJURED_COL].sum()):,} injured and "
            f"{int(result[config.PERSONS_KILLED_COL].sum()):,} killed on "
            f"{len(result):,} affected parties",
        ],
    )


def threshold_composition(parties: pd.DataFrame, casualties: pd.DataFrame) -> str:
    """Compare the crash types of what the threshold discards against what it keeps.

    If multi-party crashes concentrate in one crash type, the exclusion is not
    neutral and has to be declared as a limitation rather than a technicality.
    """
    party_count = parties.groupby(config.CRASH_ID_COL)[_PARTY_KEY].transform("size")
    discarded = set(parties.loc[party_count > config.MAX_PARTIES_PER_CRASH, config.CRASH_ID_COL])

    per_crash = casualties.drop_duplicates(config.CRASH_ID_COL)[
        [config.CRASH_ID_COL, config.CRASH_CLASS_SOURCE_COL]
    ].copy()
    per_crash["_discarded"] = per_crash[config.CRASH_ID_COL].isin(discarded)

    kept_share = per_crash.loc[~per_crash["_discarded"], config.CRASH_CLASS_SOURCE_COL].value_counts(normalize=True)
    drop_share = per_crash.loc[per_crash["_discarded"], config.CRASH_CLASS_SOURCE_COL].value_counts(normalize=True)
    drop_count = per_crash.loc[per_crash["_discarded"], config.CRASH_CLASS_SOURCE_COL].value_counts()
    keep_count = per_crash.loc[~per_crash["_discarded"], config.CRASH_CLASS_SOURCE_COL].value_counts()

    # Name breaks ties so two runs order the table identically and can be diffed.
    classes = sorted(
        set(kept_share.index) | set(drop_share.index),
        key=lambda c: (-drop_share.get(c, 0.0), -kept_share.get(c, 0.0), str(c)),
    )
    lines = [
        f"{'crash type':<20}  {'discarded':>10}  {'%':>7}  {'kept':>10}  {'%':>7}  {'ratio':>7}  {'% of type':>10}",
        f"{'-' * 20}  {'-' * 10}  {'-' * 7}  {'-' * 10}  {'-' * 7}  {'-' * 7}  {'-' * 10}",
    ]
    for crash_class in classes:
        d_pct = 100 * drop_share.get(crash_class, 0.0)
        k_pct = 100 * kept_share.get(crash_class, 0.0)
        ratio = f"{d_pct / k_pct:.2f}x" if k_pct else "n/a"
        dropped = int(drop_count.get(crash_class, 0))
        kept = int(keep_count.get(crash_class, 0))
        # The share of this crash type that the rule removes. The relative
        # columns say whether the loss is skewed; this one says how much of the
        # type is actually gone, which is the figure a limitations section needs.
        of_type = f"{100 * dropped / (dropped + kept):.2f}%" if dropped + kept else "n/a"
        lines.append(
            f"{str(crash_class):<20}  {dropped:>10,}  {d_pct:>6.2f}%  "
            f"{kept:>10,}  {k_pct:>6.2f}%  {ratio:>7}  {of_type:>10}"
        )
    lines.append("")
    lines.append(
        f"crashes discarded: {len(discarded):,} of {per_crash[config.CRASH_ID_COL].nunique():,} "
        f"({100 * len(discarded) / per_crash[config.CRASH_ID_COL].nunique():.2f}%)"
    )
    return "\n".join(lines)


def divergence_report(result: pd.DataFrame) -> str:
    """Quantify how far this stage departs from the legacy pipeline, by design.

    The legacy figures are a reference point, never a target: they carry the
    orientation bias the party model exists to remove.
    """
    ref = config.LEGACY_REFERENCE
    moto_bike = int(
        result.loc[
            result[config.PARTY_TYPE_COL].eq(config.MOTORCYCLE)
            & result[config.COUNTERPART_TYPE_COL].eq(config.BICYCLE),
            config.AFFECTED_PARTIES_COL,
        ].sum()
    )
    bike_moto = int(
        result.loc[
            result[config.PARTY_TYPE_COL].eq(config.BICYCLE)
            & result[config.COUNTERPART_TYPE_COL].eq(config.MOTORCYCLE),
            config.AFFECTED_PARTIES_COL,
        ].sum()
    )

    crashes = int(result[config.CRASH_ID_COL].nunique())

    def ratio(a: int, b: int) -> str:
        return f"{a / b:.2f}x" if b else "n/a"

    lines = [
        f"{'measure':<44}  {'legacy':>10}  {'this stage':>12}",
        f"{'-' * 44}  {'-' * 10}  {'-' * 12}",
        f"{'rows emitted':<44}  {ref['exported_rows']:>10,}  {len(result):>12,}",
        f"{'  (legacy row = one crash; here = one party)':<44}  {'':>10}  {'':>12}",
        f"{'crashes represented':<44}  {ref['exported_rows']:>10,}  {crashes:>12,}",
        f"{'motorcycle harmed, bicycle counterpart':<44}  "
        f"{ref['motorcycle_row_bicycle_counterpart']:>10,}  {moto_bike:>12,}",
        f"{'bicycle harmed, motorcycle counterpart':<44}  "
        f"{ref['bicycle_row_motorcycle_counterpart']:>10,}  {bike_moto:>12,}",
        "",
        f"orientation of that pair (motorcycle-harmed : bicycle-harmed)",
        f"    legacy      {ratio(ref['motorcycle_row_bicycle_counterpart'], ref['bicycle_row_motorcycle_counterpart'])}"
        f"  -> a motorcyclist recorded as the harmed party far more often than a cyclist",
        f"    this stage  {ratio(moto_bike, bike_moto)}",
    ]
    return "\n".join(lines)


def resolve(casualties: pd.DataFrame, vehicles: pd.DataFrame, log: RunLog) -> pd.DataFrame:
    """Full stage: one row per affected party, with its counterpart."""
    check_cross_layer_duplication(casualties, log)
    parties = build_parties(casualties, vehicles, log)
    kept = resolve_pairs(parties, log)
    result = emit_rows(kept, casualties, log)
    check_person_balance(result, casualties, parties, log)

    log.table("crash type composition of what the two-party threshold removes:",
              threshold_composition(parties, casualties))
    log.dump(result, "05_affected_parties")
    return result


def main() -> int:
    log = RunLog()
    log.info("run directory: %s", log.run_dir)

    casualties = loading.load_casualties(log)
    vehicles = loading.load_vehicles(log)
    passed, _ = loading.verify_against_legacy(casualties, vehicles, log)
    if not passed:
        log.warn("stopping: loading diverges from the legacy baseline")
        return 1

    result = resolve(casualties, vehicles, log)

    log.table("record funnel:", log.funnel())
    log.table("divergence from the legacy pipeline (reported, not corrected):", divergence_report(result))

    counterparts = pd.crosstab(result[config.PARTY_TYPE_COL], result[config.COUNTERPART_TYPE_COL])
    log.table("affected parties by actor type and counterpart:", counterparts.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
