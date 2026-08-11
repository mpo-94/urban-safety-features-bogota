"""Run-scoped output directory, logging and record accounting.

Every stage of the pipeline reports how many records went in, how many came out,
and the named cause of each difference. A stage whose causes do not account for
its own difference stops the run: an unexplained gain or loss is exactly what
this pipeline exists to make impossible.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

try:  # regular package import
    from src import config
except ImportError:  # executed as a plain script from inside src/
    import config  # type: ignore[no-redef]


LOGGER_NAME = "casualty_matrix"


class ProvenanceError(RuntimeError):
    """Raised when a stage's record count does not balance against its causes."""


@dataclass(frozen=True)
class StageRecord:
    """What one pipeline stage did to the record count."""

    stage: str
    rows_in: int
    rows_out: int
    # (delta, cause) pairs. Every record gained or lost must carry a name.
    changes: tuple[tuple[int, str], ...] = ()
    # Observations that do not move the record count but must not go unnoticed,
    # such as records kept with a null territorial unit.
    notes: tuple[str, ...] = ()

    @property
    def delta(self) -> int:
        return self.rows_out - self.rows_in


@dataclass
class RunLog:
    """Per-run output directory, logger and stage accounting."""

    run_dir: Path = field(default_factory=config.new_run_directory)
    dump_intermediates: bool = config.DUMP_INTERMEDIATES
    records: list[StageRecord] = field(default_factory=list)
    logger: logging.Logger = field(init=False)

    def __post_init__(self) -> None:
        logger = logging.getLogger(LOGGER_NAME)
        logger.setLevel(logging.INFO)
        # Reconfigure from scratch so re-running in the same interpreter does not
        # accumulate handlers and duplicate every line.
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", "%Y-%m-%d %H:%M:%S")

        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(fmt)
        logger.addHandler(stream)

        file_handler = logging.FileHandler(self.run_dir / config.LOG_FILENAME, encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

        logger.propagate = False
        self.logger = logger

    # -- accounting ---------------------------------------------------------

    def record(
        self,
        stage: str,
        rows_in: int,
        rows_out: int,
        changes: Sequence[tuple[int, str]] = (),
        notes: Iterable[str] = (),
    ) -> StageRecord:
        """Register a stage and check that its causes account for the difference.

        `changes` holds signed deltas with a named cause each. Their sum must
        equal rows_out - rows_in, otherwise the run stops.
        """
        changes = tuple(changes)
        notes = tuple(notes)
        explained = sum(delta for delta, _ in changes)
        expected = rows_out - rows_in
        if explained != expected:
            raise ProvenanceError(
                f"stage {stage!r} does not balance: {rows_in} in, {rows_out} out "
                f"(difference {expected:+d}) but the named causes account for "
                f"{explained:+d}. Every record gained or lost needs a cause."
            )

        entry = StageRecord(stage=stage, rows_in=rows_in, rows_out=rows_out, changes=changes, notes=notes)
        self.records.append(entry)

        self.logger.info("%s: %d in -> %d out (%+d)", stage, rows_in, rows_out, entry.delta)
        for delta, cause in changes:
            self.logger.info("    %+d rows: %s", delta, cause)
        for note in notes:
            self.logger.info("    note: %s", note)
        return entry

    def warn(self, message: str, *args: object) -> None:
        self.logger.warning(message, *args)

    def info(self, message: str, *args: object) -> None:
        self.logger.info(message, *args)

    def table(self, title: str, text: str) -> None:
        """Log a pre-rendered block of text line by line, so it reaches the file."""
        self.logger.info("%s", title)
        for line in text.splitlines():
            self.logger.info("%s", line)

    # -- artefacts ----------------------------------------------------------

    def dump(self, frame: pd.DataFrame, name: str) -> Path | None:
        """Write a stage result to the run directory if dumping is enabled."""
        if not self.dump_intermediates:
            return None
        path = self.run_dir / f"{name}.parquet"
        frame.to_parquet(path)
        self.logger.info("intermediate written: %s (%d rows)", path.name, len(frame))
        return path

    def funnel(self) -> str:
        """The full record funnel of this run, as a table."""
        width = max([len(r.stage) for r in self.records] + [5])
        lines = [
            f"{'stage'.ljust(width)}  {'in':>10}  {'out':>10}  {'delta':>8}",
            f"{'-' * width}  {'-' * 10}  {'-' * 10}  {'-' * 8}",
        ]
        for r in self.records:
            lines.append(f"{r.stage.ljust(width)}  {r.rows_in:>10,}  {r.rows_out:>10,}  {r.delta:>+8,}")
            for delta, cause in r.changes:
                lines.append(f"{'':<{width}}  {delta:>+10,}  {'':>10}  {cause}")
            for note in r.notes:
                lines.append(f"{'':<{width}}  {'':>10}  {'':>10}  note: {note}")
        return "\n".join(lines)
