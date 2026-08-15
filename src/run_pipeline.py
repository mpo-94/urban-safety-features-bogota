"""Single entry point for the pipeline.

Every way of running the pipeline is a *route*: a named sequence of stages that
gets its own timestamped run directory and its own log. Routes exist because the
stages are expensive and rarely all needed at once — checking a change to party
resolution should not have to rebuild fifty-seven figures first.

    python -m src.run_pipeline                 # full pipeline, and says so
    python -m src.run_pipeline matrix          # the same, named explicitly
    python -m src.run_pipeline parties         # stop after party resolution
    python -m src.run_pipeline loading         # sources only
    python -m src.run_pipeline loading --dump-intermediates

Adding a route means writing one function that takes a RunLog and adding one
entry to ROUTES. Nothing else in the module needs to change; the command line,
the help text and the run directory follow from the registry.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from src import config, loading, matrix, parties
from src.provenance import RunLog


class RouteFailed(RuntimeError):
    """A route stopped because one of its own checks did not pass.

    Distinct from an exception raised inside a stage: this one means the
    pipeline ran to completion and disagreed with its baseline, which is a
    result, not a crash.
    """


# ---------------------------------------------------------------------------
# Shared prologue
# ---------------------------------------------------------------------------


def load_sources(log: RunLog) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read and locate everything the later stages need, verified before use.

    The unit layer is loaded once and passed down, so a run reads the shapefile a
    single time however many stages want it.
    """
    units = loading.load_territorial_units(log)
    casualties = loading.load_casualties(log, units=units)
    vehicles = loading.load_vehicles(log)

    passed, _ = loading.verify_loading(casualties, vehicles, log)
    if not passed:
        # Stop here rather than let a later stage build on numbers that already
        # disagree with the baseline.
        raise RouteFailed("loading diverges from its baseline; fix that before running any further stage")
    return units, casualties, vehicles


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def run_loading(log: RunLog) -> None:
    """Read the sources, locate them, verify the counts."""
    load_sources(log)
    log.table("record funnel:", log.funnel())


def run_parties(log: RunLog) -> None:
    """Everything up to one row per affected party, with its counterpart."""
    _, casualties, vehicles = load_sources(log)
    affected = parties.resolve(casualties, vehicles, log)

    log.table("record funnel:", log.funnel())
    log.table(
        "divergence from the legacy pipeline (reported, not corrected):",
        parties.divergence_report(affected),
    )
    counterparts = pd.crosstab(affected[config.PARTY_TYPE_COL], affected[config.COUNTERPART_TYPE_COL])
    log.table("affected parties by actor type and counterpart:", counterparts.to_string())


def run_matrix(log: RunLog) -> None:
    """The full pipeline: sources, parties, matrix, tables and figures."""
    units, casualties, vehicles = load_sources(log)
    affected = parties.resolve(casualties, vehicles, log)
    long_table = matrix.build(affected, units, log)

    paths = matrix.export(long_table, log)
    matrix.render_heatmaps(paths, log)

    log.table("record funnel:", log.funnel())
    if not matrix.verify(long_table, affected, units, log):
        raise RouteFailed("the matrix does not agree with what entered it")
    matrix.report(long_table, log)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Route:
    """One way of running the pipeline, as offered on the command line."""

    name: str
    summary: str  # one line, shown in the help and when no route is given
    run: Callable[[RunLog], None]


# Longest route first, so the help reads from the whole pipeline down to its
# parts. ρ(t) and the static predictors join this list as they are written.
ROUTES: tuple[Route, ...] = (
    Route("matrix", "full pipeline up to the casualty matrix, with tables and figures", run_matrix),
    Route("parties", "up to party resolution: one row per affected party", run_parties),
    Route("loading", "sources only: read them, locate them, verify the counts", run_loading),
)

# Running with no arguments does the whole thing rather than complaining, since
# that is what a pipeline is for; which route ran is announced either way.
DEFAULT_ROUTE = "matrix"

ROUTES_BY_NAME: dict[str, Route] = {route.name: route for route in ROUTES}


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def _route_help() -> str:
    width = max(len(route.name) for route in ROUTES)
    return "\n".join(f"  {route.name.ljust(width)}  {route.summary}" for route in ROUTES)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.run_pipeline",
        description="Run the casualty matrix pipeline, or one part of it.",
        epilog=f"routes:\n{_route_help()}\n\nwith no route, {DEFAULT_ROUTE} runs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "route",
        nargs="?",
        default=None,
        choices=sorted(ROUTES_BY_NAME),
        help=f"which part to run (default: {DEFAULT_ROUTE})",
    )
    parser.add_argument(
        "--dump-intermediates",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "write each stage's output to the run directory, overriding the configured "
            f"default ({'on' if config.DUMP_INTERMEDIATES else 'off'}) for this run only"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    chosen = args.route or DEFAULT_ROUTE
    route = ROUTES_BY_NAME[chosen]

    dump = config.DUMP_INTERMEDIATES if args.dump_intermediates is None else args.dump_intermediates
    log = RunLog(dump_intermediates=dump)

    if args.route is None:
        log.info("no route given, running the default one: %s (%s)", route.name, route.summary)
        for line in _route_help().splitlines():
            log.info("%s", line)

    scale = config.active_scale()
    log.info("route: %s (%s)", route.name, route.summary)
    log.info("run directory: %s", log.run_dir)
    log.info(
        "scale: %s (%d units) | period: %d-%d | source CRS: EPSG:%d | projected CRS: EPSG:%d",
        scale.label,
        scale.expected_units,
        config.FIRST_YEAR,
        config.LAST_YEAR,
        config.SOURCE_CRS,
        config.PROJECTED_CRS,
    )
    log.info(
        "intermediate dumps: %s%s",
        "on" if log.dump_intermediates else "off",
        "" if args.dump_intermediates is None else " (from the command line)",
    )

    try:
        route.run(log)
    except RouteFailed as failure:
        log.warn("stopping: %s", failure)
        return 1

    log.info("route %s finished; output in %s", route.name, log.run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
