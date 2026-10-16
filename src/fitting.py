"""Iterative proportional fitting: the matrix that satisfies new margins without
inventing structure the seed did not already contain.

D54 declared the method in the anteproyecto and D60 settled what it is fitted on: the
matrix stays on the survey's own zones and the margins come down from the unit. This
module is only the fitting. It knows nothing about surveys, units, years or modes, and
that is deliberate — the arithmetic is small enough to be read in one sitting and
general enough to be tested against cases whose answer is known in advance.

**What the method is.** Given a seed matrix and the row and column totals the result must
have, scale the rows to match their totals, then the columns to match theirs, then the
rows again, and keep going. Each half-step satisfies one set of margins exactly and
disturbs the other, and under the condition below the disturbance shrinks geometrically
until both hold at once.

**Why it is this and not a regression.** Among all the matrices with the required margins,
the one it converges to is the one that minimises the Kullback-Leibler divergence from the
seed. In words: of everything consistent with what we now know about the totals, it picks
what is closest to what the survey actually saw, and adds nothing else. That is the
argument the anteproyecto makes from statistical mechanics, and with a uniform seed it
reduces to the maximum-entropy trip distribution model.

**When it does not converge, and this is not rare in practice.** Fitting is possible only
if the seed's zero pattern allows it. A row whose every positive cell sits in columns whose
totals are zero cannot be scaled to a positive total, and no number of iterations fixes it.
The code detects that case and says which row or column caused it rather than returning a
matrix that silently misses its margins.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Both margins must agree on the grand total before any fitting makes sense, and
# floating point means "agree" needs a tolerance. This one is relative, so it does
# not have to be retuned when the trips go from thousands to millions.
TOTALS_TOLERANCE = 1e-9

# The iteration stops when no margin is further from its target than this, in relative
# terms.
#
# **It is set at the noise floor of the step that follows it, not as tight as it can be
# got.** What happens to a fitted matrix next is that the cells carrying almost nothing
# are dropped, and measured over the thirteen years that pruning costs the margins
# between 1e-4 and 4e-4 by itself. A tolerance tighter than that is measuring below the
# error of the very next operation: it buys nothing and costs tens of thousands of
# passes, because the blocks that need the floor converge slowly by nature — they are the
# ones whose margins the survey's own support could not reach at all.
#
# What the number has to be small enough for is the exposure, and there it has room to
# spare. A relative error of 1e-4 on a zone margin aggregates to at most 1e-4 on a unit's
# margin; measured, the worst unit in the study comes out at 1.1e-5. The exposure enters
# the models as a logarithm, so an error of 1e-4 moves a prediction by a hundredth of a
# per cent.
#
# The row margin is the one this bounds. The column scaling is the last thing each pass
# does, so the column margins are exact when the loop stops and the asymmetry is the
# tolerance itself.
DEFAULT_TOLERANCE = 1e-4
DEFAULT_MAX_ITERATIONS = 20_000

# How often the margins are measured against their targets. Not every pass, because the
# measurement walks the whole matrix and on a dense seed costs as much as the two scalings
# it is checking. Ten overshoots the stopping point by at most nine passes, which on a
# fitting that needs ten thousand is nothing, and halves the time it takes.
#
# It is also why the loop measures only the row margin: the column scaling is the last
# thing each pass does, so the column margin is exact when the check happens and the row
# margin is the only one that can still be off.
CONVERGENCE_CHECK_EVERY = 10


@dataclass(frozen=True)
class Fit:
    """A fitted matrix and everything needed to judge whether to trust it."""

    matrix: np.ndarray
    iterations: int
    converged: bool
    # The largest relative distance any margin still has from its target. Reported
    # whether or not it converged, because a run that stopped at 1e-7 is a
    # different thing from one that stopped at 0.3 and both are "not converged".
    #
    # **A large value here usually means no such matrix exists, not that the iteration
    # needed longer.** `infeasible_by` separates the two, and the separation matters
    # because the remedies are opposite: more passes, or a different support. Measured on
    # the 2017 cycling block, 2,000 and 50,000 iterations leave exactly the same 0.6706.
    worst_margin_error: float

    def __post_init__(self) -> None:
        if np.any(self.matrix < 0):
            raise ValueError("a fitted matrix with a negative cell is not a trip matrix")


def _relative_error(got: np.ndarray, want: np.ndarray) -> float:
    """How far the achieved margins are from the targets, relative to the targets.

    Relative and not absolute so that one large zone does not hide a small zone
    missing its margin entirely. Where the target is zero the achieved value must
    be zero too, and the absolute difference is the right measure there.
    """
    scale = np.where(want > 0, want, 1.0)
    return float(np.max(np.abs(got - want) / scale)) if got.size else 0.0


def unfittable_margins(
    seed: np.ndarray, rows: np.ndarray, columns: np.ndarray
) -> list[str]:
    """The margins the seed's zero pattern makes impossible, named one by one.

    Fitting cannot create a trip where the seed has none: a zero cell stays zero
    through every scaling, because both operations are multiplications. So a row
    with a positive target whose seed is zero everywhere has nowhere to put its
    trips, and the same for a column. Returned as text rather than raised, so the
    caller can report every offending margin at once instead of the first.

    The converse is also checked: a row whose target is zero but whose seed is
    positive is fine — it scales to zero in one step — and is not reported.
    """
    problems: list[str] = []
    for index in np.where((rows > 0) & (seed.sum(axis=1) == 0))[0]:
        problems.append(
            f"row {int(index)} needs {rows[index]:,.1f} trips and the seed gives it no cell"
        )
    for index in np.where((columns > 0) & (seed.sum(axis=0) == 0))[0]:
        problems.append(
            f"column {int(index)} needs {columns[index]:,.1f} trips and the seed gives it no cell"
        )
    return problems


def components_of_edges(
    origins: np.ndarray,
    destinations: np.ndarray,
    origin_count: int,
    destination_count: int,
) -> np.ndarray:
    """Which block of mutually reachable places each origin and each destination is in.

    The edges are the cells that hold travel: edge `(i, j)` joins origin `i` to
    destination `j`, and a trip can only ever be moved inside one connected piece of that
    graph. Returned as one label per node, origins first and destinations after them, so
    `origin_count` of `r` puts destination `j` at `r + j`.

    **Origin `i` and destination `i` are different nodes even when they are the same
    place**, and that is not a technicality. If one zone only ever sends to a second and
    the second only ever sends back to the first, the two cells form two separate pieces
    and the margins owe two conditions rather than one; treating the zone as a single node
    asks only that the pair balance overall, which is weaker and lets through margins no
    matrix has.

    It takes the edges rather than a matrix so that a caller holding the sparse list —
    which is how an origin-destination matrix is actually stored — does not have to
    materialise a square grid to ask the question, and so that there is one
    implementation of it rather than one per shape.

    Union-find rather than a graph library, for the reason the module docstring gives:
    the arithmetic here should be readable in one sitting, and this is fifteen lines.
    """
    parent = list(range(origin_count + destination_count))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]  # halve the path as we walk it
            index = parent[index]
        return index

    for origin, destination in zip(origins, destinations):
        left, right = root(int(origin)), root(origin_count + int(destination))
        if left != right:
            parent[left] = right
    return np.array([root(index) for index in range(origin_count + destination_count)])


def support_components(seed: np.ndarray) -> np.ndarray:
    """`components_of_edges` for a seed held as a matrix."""
    rows, columns = np.nonzero(seed)
    return components_of_edges(rows, columns, seed.shape[0], seed.shape[1])


def inconsistent_components(
    seed: np.ndarray,
    rows: np.ndarray,
    columns: np.ndarray,
    tolerance: float = TOTALS_TOLERANCE,
) -> list[str]:
    """The blocks of the seed whose two margins disagree, which is what blocks fitting.

    **This is the condition that actually decides whether a fitting is possible**, and it
    is stronger than the grand total agreeing. A trip can only move inside a connected
    piece of the seed's support, so each piece has to be self-consistent: the row margins
    of its origins and the column margins of its destinations must sum to the same thing.
    If they do not, no matrix has both, the iteration oscillates instead of converging,
    and after the maximum number of passes it returns something that misses its margins by
    whatever the disagreement was.

    It is not a corner case. The 2015 cycling matrix splits into pieces — one holding
    almost every zone and a handful holding two or three — and every one of them had
    margins that disagreed, because those margins are built from growth factors
    interpolated per unit and nothing in that construction knows about the support. The
    small pieces are 0.02 % of the matrix in trips, and they were enough to stop the whole
    block converging.

    Reported as text rather than raised, like `unfittable_margins`, so a caller can fix
    every piece at once instead of the first.
    """
    labels = support_components(seed)
    origins = seed.shape[0]
    problems: list[str] = []
    for label in np.unique(labels):
        inside = labels == label
        row_total = float(rows[inside[:origins]].sum())
        column_total = float(columns[inside[origins:]].sum())
        scale = max(abs(row_total), abs(column_total), 1.0)
        if abs(row_total - column_total) > tolerance * scale:
            places = int(inside.sum())
            problems.append(
                f"a block of {places} node(s) is asked for {row_total:,.4f} trips out and "
                f"{column_total:,.4f} in, and nothing can leave it"
            )
    return problems


def infeasible_by(
    seed: np.ndarray,
    rows: np.ndarray,
    columns: np.ndarray,
    scale: float = 1000.0,
) -> float:
    """How many trips of the row margins no matrix with this support can place.

    **The exact condition, and the reason `inconsistent_components` is not enough.**
    Fitting is possible if and only if the row margins can be routed to the column
    margins through the cells the seed holds, which is a transportation feasibility
    question: for every set of origins, what is asked of them cannot exceed what is asked
    of the destinations they can reach. Component consistency is the special case where
    the set is a whole connected piece, so it catches some infeasible problems and not
    all. The 2017 cycling block passes it and is still infeasible by 1,966 trips a day of
    899,651, which is 0.219 % — and 0.219 % of infeasibility leaves one unit's margin
    missed by 56 % after the iteration gives up.

    Answered by maximum flow on origins to cells to destinations: the margins can be
    satisfied exactly when the flow saturates the origins. Returned as the shortfall in
    trips, zero when the problem is feasible.

    **It is a diagnosis and not a guard, which is why `fit` does not call it.** Maximum
    flow costs far more than an iteration, and on a seed with no zeros — which is what a
    floored seed is — the answer is always zero. Call it when a fitting fails to converge,
    to tell "no such matrix exists" apart from "the iteration needed more passes". The
    two have different remedies and the error messages cannot tell them apart.

    `scale` turns the margins into the integers the flow solver needs. A thousand means
    the answer is accurate to a thousandth of a trip, which is four orders of magnitude
    below anything the exposure is read at.
    """
    from scipy.sparse import csr_matrix  # noqa: PLC0415 - only this function needs it
    from scipy.sparse.csgraph import maximum_flow  # noqa: PLC0415

    seed = np.asarray(seed, dtype=float)
    out = np.rint(np.asarray(rows, dtype=float) * scale).astype(np.int64)
    into = np.rint(np.asarray(columns, dtype=float) * scale).astype(np.int64)
    if out.sum() <= 0:
        return 0.0
    # Rounding can leave the two integer totals a few units apart, and a flow problem
    # whose two sides disagree is a different question from the one being asked. The
    # difference goes on the largest column, where it is relatively smallest.
    into[int(np.argmax(into))] += out.sum() - into.sum()

    places = seed.shape[0]
    source, sink = 0, seed.shape[0] + seed.shape[1] + 1
    starts: list[int] = []
    ends: list[int] = []
    capacities: list[int] = []
    for index, demand in enumerate(out):
        if demand > 0:
            starts.append(source)
            ends.append(1 + index)
            capacities.append(int(demand))
    for index, demand in enumerate(into):
        if demand > 0:
            starts.append(1 + places + index)
            ends.append(sink)
            capacities.append(int(demand))
    # A cell is an edge of unlimited capacity: what constrains it is the margins at both
    # of its ends, not anything about the cell itself.
    unlimited = int(out.sum())
    for row, column in zip(*np.nonzero(seed)):
        starts.append(1 + int(row))
        ends.append(1 + places + int(column))
        capacities.append(unlimited)

    network = csr_matrix(
        (capacities, (starts, ends)), shape=(sink + 1, sink + 1)
    )
    placed = maximum_flow(network, source, sink).flow_value
    return max(0.0, float(out.sum() - placed) / scale)


def fit(
    seed: np.ndarray,
    rows: np.ndarray,
    columns: np.ndarray,
    tolerance: float = DEFAULT_TOLERANCE,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> Fit:
    """Scale `seed` until its row and column sums are `rows` and `columns`.

    **The seed decides the shape and the margins decide the level.** Every zero of
    the seed is a zero of the result, which is what makes the method conservative:
    it cannot invent travel between two places the survey never saw travel between.

    Raises rather than returns on the three ways the problem is malformed: margins
    that disagree about the grand total, a negative anywhere, and a zero pattern
    that makes the margins unreachable. All three are errors in what was handed in,
    not failures of the iteration, and a caller that gets a matrix back from one of
    them would be getting a quiet wrong answer.
    """
    seed = np.asarray(seed, dtype=float)
    rows = np.asarray(rows, dtype=float)
    columns = np.asarray(columns, dtype=float)

    if seed.ndim != 2:
        raise ValueError(f"the seed must be a matrix, got {seed.ndim} dimension(s)")
    if seed.shape != (rows.size, columns.size):
        raise ValueError(
            f"seed is {seed.shape} but the margins are {rows.size} by {columns.size}"
        )
    if np.any(seed < 0) or np.any(rows < 0) or np.any(columns < 0):
        raise ValueError("a negative trip count is not a thing that can be fitted")

    total_rows, total_columns = rows.sum(), columns.sum()
    if total_rows <= 0:
        raise ValueError("the margins are all zero; there is nothing to fit")
    if abs(total_rows - total_columns) > TOTALS_TOLERANCE * max(total_rows, total_columns):
        raise ValueError(
            f"the two margins disagree about the grand total: {total_rows:,.4f} against "
            f"{total_columns:,.4f}. They have to be made consistent before fitting, "
            "because no matrix has both."
        )

    problems = unfittable_margins(seed, rows, columns)
    if problems:
        raise ValueError(
            "the seed's zero pattern makes these margins unreachable, and no number of "
            "iterations changes that: " + "; ".join(problems[:6])
            + (f" (and {len(problems) - 6} more)" if len(problems) > 6 else "")
        )

    # The condition that actually decides. Checked here and not left to the caller
    # because without it the iteration does not fail — it runs to the maximum number of
    # passes and returns a matrix that misses its margins, which is the one outcome this
    # module exists to prevent. The first version of this file checked only the
    # degenerate case above and gave a clean bill of health to margins no matrix had.
    disagreeing = inconsistent_components(seed, rows, columns)
    if disagreeing:
        raise ValueError(
            f"the seed's support splits into blocks nothing can travel between, and "
            f"{len(disagreeing)} of them are asked for more trips out than in or the "
            "reverse. The margins have to be made consistent inside every block, not "
            "only in the grand total: " + "; ".join(disagreeing[:4])
            + (f" (and {len(disagreeing) - 4} more)" if len(disagreeing) > 4 else "")
        )

    matrix = seed.copy()
    iterations = 0
    worst = float("inf")
    for iterations in range(1, max_iterations + 1):
        # Rows first, then columns. The order does not change what it converges to,
        # only which margin is exact if the loop is cut short, and the loop is not
        # cut short: it runs until both are within tolerance.
        row_sums = matrix.sum(axis=1)
        scale = np.divide(rows, row_sums, out=np.zeros_like(rows), where=row_sums > 0)
        matrix *= scale[:, None]

        column_sums = matrix.sum(axis=0)
        scale = np.divide(columns, column_sums, out=np.zeros_like(columns),
                          where=column_sums > 0)
        matrix *= scale[None, :]

        # **The column margin is exact at this point, so only the row margin is worth
        # measuring**, and measuring it is not free: it walks the whole matrix again, and
        # on a dense seed of 887 zones that is as much work as the two scalings together.
        # Checking every `CONVERGENCE_CHECK_EVERY` passes halves the cost of a fitting
        # that needs ten thousand of them and overshoots by at most nine.
        if iterations % CONVERGENCE_CHECK_EVERY == 0 or iterations == max_iterations:
            worst = _relative_error(matrix.sum(axis=1), rows)
            if worst <= tolerance:
                return Fit(matrix, iterations, True, worst)

    return Fit(matrix, iterations, False, worst)
