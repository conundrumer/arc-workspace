"""The judgments every check reads from one place: Fit, the cases a
verdict line denotes, a run that gives no result, and the color-swap
witness (plan §D5, "Judged once")."""

from collections.abc import Sequence
from dataclasses import dataclass

from checker.finding import Finding, Kind, NoResultPayload, RunKind, Where
from engine import (
    AdtValue,
    CpuLimit,
    Engine,
    Grid,
    Limits,
    RecordValue,
    RelationName,
    RunFailure,
    Value,
    WallLimit,
)
from solver.annotations import Verdict, VerdictWord
from solver.model import (
    Base,
    Branch,
    Case,
    DeriveBranch,
    Solver,
    StoreBranch,
)
from solver.model import is_concept as concept_base
from solver.names import Denoted, denote, model_of
from solver.problems import InSolver, Named, ProblemKind, Fault
from solver.solve import Grids, PairId, PairRuns
from solver.witness import Undefined

# A run that gives no result


def is_timeout(failure: RunFailure) -> bool:
    """The run reached a limit, CPU or wall; its outcome is no result."""
    return isinstance(failure, CpuLimit | WallLimit)


def no_result(failure: RunFailure, run: RunKind, case: Case | None,
              where: Where) -> Finding:
    """The finding for a run that gives no result: `TIMEOUT` where it
    reached either limit, `RUN_FAILED` for every other failure."""
    kind = Kind.TIMEOUT if is_timeout(failure) else Kind.RUN_FAILED
    return Finding(kind, where, NoResultPayload(run, case, failure))


# Fit


@dataclass(frozen=True)
class Fits:
    """The model fits the task at its stored assignment: some case of it
    gives one of each pair's candidates on every train and test pair
    (principles.md:74-78, :272)."""

    case: Case


@dataclass(frozen=True)
class Misses:
    """Every case of the model fails at some pair: the first case at the
    first pair where it gives no candidate. A run that fails is no miss:
    Fit is not judged on its pair (`NoResult`)."""

    case: Case
    pair: PairId


@dataclass(frozen=True)
class NoResult:
    """No case of the model fits, and some case misses at no pair but has
    a run that reached a limit or failed on some: the judgment rests on
    runs with no result, which neither fit nor miss there."""

    case: Case
    pairs: tuple[tuple[PairId, RunFailure], ...]


type Fit = Fits | Misses | NoResult


def _case_fit(pairs: Sequence[PairRuns], case: Case) -> Fit | None:
    """How one case meets Fit; None where `pairs` holds no run of it."""
    limited: list[tuple[PairId, RunFailure]] = []
    miss: PairId | None = None
    seen = False
    for p in pairs:
        run = next((c for c in p.cases if c.case == case), None)
        if run is None:
            continue
        seen = True
        if isinstance(run.outcome, Grids) and run.matches:
            continue
        if not isinstance(run.outcome, Grids | Undefined):
            limited.append((p.pair, run.outcome))
            continue
        miss = miss or p.pair
    if not seen:
        return None
    if miss is not None:
        return Misses(case, miss)
    if limited:
        return NoResult(case, tuple(limited))
    return Fits(case)


def fit(pairs: Sequence[PairRuns], cases: Sequence[Case]) -> Fit | None:
    """How the model whose cases are `cases` meets Fit
    (principles.md:272): it fits where some case fits every pair. Where
    none fits and some case misses at no pair but has a run that reached
    a limit or failed, the
    judgment rests on no result; otherwise it misses where its first case
    misses first. None where `pairs` runs none of `cases`."""
    judged = [f for c in cases if (f := _case_fit(pairs, c)) is not None]
    if not judged:
        return None
    for f in judged:
        if isinstance(f, Fits):
            return f
    for f in judged:
        if isinstance(f, NoResult):
            return f
    return judged[0]


# The cases a verdict line denotes


def _constructors(value: Value) -> list[str]:
    """Every constructor a `Choice` value spells, outermost first."""
    match value:
        case AdtValue(constructor=name, args=args):
            return [name, *(n for a in args for n in _constructors(a))]
        case RecordValue(fields=fields):
            return [n for f in fields for n in _constructors(f)]
        case _:
            return []


def base_constructors(base: Base | None) -> list[str]:
    """The constructors a case's base takes, outermost first."""
    return [] if base is None else _constructors(base)


def is_concept(solver: Solver, case: Case) -> bool:
    """The concept case: the concept case's base (`solver.model.is_concept`)
    with the first branch at every `@derive` and `@store` point
    (principles.md:102)."""
    return not case.branches and concept_base(solver, case.base)


@dataclass(frozen=True)
class AnyCase:
    """`any`: the output of any case defined on the witness
    (principles.md:152)."""


@dataclass(frozen=True)
class NoCase:
    """`other`: an output that no case produces (principles.md:153)."""


type VerdictCase = Case | None | AnyCase | NoCase | Fault


def verdict_case(solver: Solver, verdict: Verdict, among: Sequence[Case],
                 branch: Branch | None) -> VerdictCase:
    """The case whose output the verdict denotes (principles.md:150-153;
    `derived` solver-file.md:121, `stored` solver-file.md:138). A verdict
    asks for a model (principles.md:152, "the branch's name: the output
    of that branch's model"), so a name reads through `solver.names.model_of`,
    one case: the branches it names, with every other point at its concept
    branch (principles.md:116), the case of `among` that is it where one
    is. `concept` is the concept case, and `derived` and `stored` the
    model of `branch`, the line's own. None where no model can be built.
    A name that denotes nothing is the fault `denote` gives. `derived` or
    `stored` on a line with no branch of its kind denotes nothing, and is
    that problem too, with the word as the name: a verdict word is never
    read as a name. The problem's place is left for the caller."""
    match verdict:
        case VerdictWord.ANY:
            return AnyCase()
        case VerdictWord.OTHER:
            return NoCase()
        case VerdictWord.CONCEPT:
            return model_of(solver, Denoted((), ()), among)
        case VerdictWord.DERIVED | VerdictWord.STORED:
            kind = DeriveBranch if verdict == VerdictWord.DERIVED \
                else StoreBranch
            if not isinstance(branch, kind):
                return Fault(ProblemKind.NAME_DENOTES_NO_CASE,
                             InSolver(0), Named(verdict.value))
            return model_of(solver, Denoted((), (branch,)), among)
        case _:
            d = denote(solver, verdict.text)
            return d if isinstance(d, Fault) else model_of(solver, d, among)


# The color-swap witness


@dataclass(frozen=True)
class Swap:
    """A train input with one color swapped for another: the input's
    index, the stored color, the free color, and the swapped grid."""

    index: int
    stored: int
    free: int
    grid: Grid


def swapped(grid: Grid, a: int, b: int) -> Grid:
    """`grid` with the colors `a` and `b` swapped."""
    return tuple(tuple(b if c == a else a if c == b else c for c in row)
                 for row in grid)


def swaps(inputs: Sequence[Grid], stored: frozenset[int],
          stored_colors: frozenset[int]) -> list[Swap]:
    """One color swap per train input that holds a color of `stored` and
    has a free color: the least stored color the input holds, swapped
    for the least color that neither the input nor `stored_colors`, the
    colors the solver's parameters store, holds."""
    out: list[Swap] = []
    for i, grid in enumerate(inputs):
        used = {c for row in grid for c in row}
        present = sorted(stored & used)
        free = [c for c in range(10) if c not in used | stored_colors]
        if not present or not free:
            continue
        out.append(Swap(i, present[0], free[0],
                        swapped(grid, present[0], free[0])))
    return out
