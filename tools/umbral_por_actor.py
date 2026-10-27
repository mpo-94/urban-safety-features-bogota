"""What the two-party threshold removes from each actor type, and whether it reorders them.

    .venv/Scripts/python.exe tools/umbral_por_actor.py

**Read only.** It loads the sources through `src.run_pipeline.load_sources` and builds the party
universe with `src.parties.build_parties`, the same two calls the pipeline makes, and writes
nothing but the run log the loaders insist on, to a scratch folder under `results/`.

D5 discards every crash with more than two parties, because with three or more the counterpart of a
casualty is ambiguous. The verification report counts what that removes in total: 49,698 of 368,394
parties. What it does not say is whether the loss falls evenly. If crashes of three or more parties
concentrate in one actor type, the threshold does not only shrink the matrix, it reorders it, and
that has to be declared. This measures, for each actor type of the affected party, how many affected
parties, persons and deaths sit in crashes over the threshold, and the type's share of all affected
parties before and after it.

The counts are checked against the funnel of `docs/verification-report.md` section 2: 368,394 parties
in the universe and 203,808 affected parties that survive the threshold. If either moves, the script
stops instead of measuring a different universe.
"""

import logging
import os
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.chdir(REPO)  # the paths in config are relative to the repository root

from src import config, parties  # noqa: E402
from src.provenance import RunLog  # noqa: E402
from src.run_pipeline import load_sources  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# The funnel figures this measurement has to reproduce before it can say anything new.
EXPECTED = {"parties": 368394, "affected_kept": 203808}


def measure() -> pd.DataFrame:
    """One row per actor type of the affected party: what the threshold removes and the shares.

    Kept apart from `main` so a document that prints the table calls this and does not measure
    the same thing a second way.
    """
    scratch = REPO / "results" / "_tools_umbral"
    scratch.mkdir(parents=True, exist_ok=True)
    log = RunLog(run_dir=scratch)
    logging.getLogger().setLevel(logging.ERROR)
    _, casualties, vehicles = load_sources(log)

    universe = parties.build_parties(casualties, vehicles, log)
    # The internal column names of src/parties.py, read off the module rather than retyped.
    key, kind = parties._PARTY_KEY, parties._PARTY_TYPE
    size = universe.groupby(config.CRASH_ID_COL)[key].transform("size")
    universe = universe.assign(
        over=size > config.MAX_PARTIES_PER_CRASH,
        persons=universe["_injured"] + universe["_killed"],
        affected=(universe["_injured"] + universe["_killed"]) > 0,
    )
    measured = {"parties": len(universe),
                "affected_kept": int((universe.affected & ~universe.over).sum())}
    if measured != EXPECTED:
        raise SystemExit(f"the universe is not the one of the verification report: {measured} vs {EXPECTED}")

    affected = universe[universe.affected]
    table = affected.groupby([kind, "over"]).agg(parties=(key, "size"), persons=("persons", "sum"),
                                                 killed=("_killed", "sum")).unstack("over", fill_value=0)
    out = pd.DataFrame({
        "affected": table[("parties", False)] + table[("parties", True)],
        "lost": table[("parties", True)],
        "persons_lost": table[("persons", True)],
        "killed_lost": table[("killed", True)],
    })
    out["lost_pct"] = 100 * out.lost / out.affected
    out["share_before_pct"] = 100 * out.affected / out.affected.sum()
    kept = out.affected - out.lost
    out["share_after_pct"] = 100 * kept / kept.sum()
    return out.sort_values("affected", ascending=False)


def main() -> int:
    out = measure()
    print("Affected parties by actor type, before and after the two-party threshold")
    print(out.round(2).to_string())
    print()
    total_lost, total = int(out.lost.sum()), int(out.affected.sum())
    print(f"affected parties in crashes over the threshold: {total_lost:,} of {total:,} "
          f"({100 * total_lost / total:.2f}%); persons {int(out.persons_lost.sum()):,}; "
          f"deaths {int(out.killed_lost.sum()):,}")
    order_before = list(out.sort_values("share_before_pct", ascending=False).index)
    order_after = list(out.sort_values("share_after_pct", ascending=False).index)
    print(f"order by share before: {order_before}")
    print(f"order by share after:  {order_after}")
    print(f"the threshold {'keeps' if order_before == order_after else 'changes'} the order of the actor types")
    return 0


if __name__ == "__main__":
    sys.exit(main())
