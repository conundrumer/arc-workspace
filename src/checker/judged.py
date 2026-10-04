"""The judgments every check reads from one place: Fit, the cases a
verdict line denotes, a run that gives no result, and the color-swap
witness."""

from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from typing import TypeGuard

from arc.task import COLORS, Task
from checker.domains import colors
from checker.finding import (
    AtFile,
    Finding,
    Kind,
    NoResultPayload,
    RunKind,
    Where,
    WholeFile,
)
from checker.payloads.branches import NoTaskPayload
from engine import (
    AdtValue,
    CpuLimit,
    Engine,
    Grid,
    ParseFailure,
    RecordValue,
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
    choice_bases,
    choice_values,
    is_concept_case,
    load,
)
from solver.model import is_concept as concept_base
from solver.names import Denoted, cover, denote, model_of
from solver.problems import Fault, Named, NameFault, ProblemKind
from solver.solve import (
    CaseOnPair,
    Grids,
    PairId,
    PairRuns,
    as_grid,
    by_base,
    is_result,
    parameter_reading,
    stored_facts,
)
from solver.vocabulary import COLOR
from solver.witness import Undefined

# A run that gives no result


def is_timeout(failure: object) -> TypeGuard[CpuLimit | WallLimit]:
    """The run reached a limit, CPU or wall; its outcome is no result."""
    return isinstance(failure, CpuLimit | WallLimit)


def no_result(failure: RunFailure, run: RunKind, case: Case | None,
              where: Where) -> Finding:
    """The finding for a run that gives no result: `TIMEOUT` where it
    reached either limit, `RUN_FAILED` for every other failure."""
    kind = Kind.TIMEOUT if is_timeout(failure) else Kind.RUN_FAILED
    return Finding(kind, where, NoResultPayload(run, case, failure))


def enumeration_failed(failure: RunFailure) -> Finding:
    """The finding for the run that enumerates the solver's cases where
    it gives no result."""
    return no_result(failure, RunKind.CASE, None, AtFile(WholeFile.SOLVER))


NO_TASK = Finding(Kind.NO_TASK, AtFile(WholeFile.SOLVER), NoTaskPayload())
"""The finding of a check that runs over the task's examples where the
solver's task has no task file."""


# Fit


@dataclass(frozen=True)
class Fits:
    """The model fits the task at its stored assignment: some case of it
    gives one of each pair's candidates on every train and test pair
    (principles.md, under "Models and tasks" and "Cases")."""

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


def differ(a: object, b: object) -> bool:
    """Two results of runs differ, one of them defined: other grids, in
    their resolutions' order, or one defined and the other not; two
    undefined outcomes agree (principles.md, under "Witnesses" and
    "Equivalence and subsumption")."""
    if isinstance(a, Grids) and isinstance(b, Grids):
        return a != b
    return {type(a), type(b)} == {Grids, Undefined}


def missed(run: CaseOnPair) -> bool:
    """The case misses the pair: its run gives a result, and that result
    is no candidate of the pair (principles.md, under "Models and tasks")."""
    return is_result(run.outcome) and not run.matches


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
        if missed(run):
            miss = miss or p.pair
        elif not is_result(run.outcome):
            limited.append((p.pair, run.outcome))
    if not seen:
        return None
    if miss is not None:
        return Misses(case, miss)
    if limited:
        return NoResult(case, tuple(limited))
    return Fits(case)


def fit(pairs: Sequence[PairRuns], cases: Sequence[Case]) -> Fit | None:
    """How the model whose cases are `cases` meets Fit
    (principles.md, under "Cases"): it fits where some case fits every pair. Where
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


def value_constructors(value: Value) -> list[str]:
    """Every constructor a value spells, outermost first; a field that is
    no constructor and no record holds data, and no branch."""
    match value:
        case AdtValue(constructor=name, args=args):
            return [name, *(n for a in args for n in value_constructors(a))]
        case RecordValue(fields=fields):
            return [n for f in fields for n in value_constructors(f)]
        case _:
            return []


def base_constructors(base: Base | None) -> list[str]:
    """The constructors a case's base takes, outermost first."""
    return [] if base is None else value_constructors(base)


def reading_names(solver: Solver, every: Sequence[Case],
                  reading: Collection[Base | None]) -> tuple[str, ...]:
    """The cases of `every` whose base is one of `reading`, by the fewest
    names that denote exactly them (`solver.names.cover`)."""
    return tuple(cover(solver, [c for c in every if c.base in reading],
                       every))


def parse_fault(solver: Solver) -> Fault | None:
    """The fault of a solver whose text does not parse, among its
    problems; None where it parses."""
    return solver.fault(ProblemKind.PARSE_FAILURE)


def parse_failure(solver: Solver) -> ParseFailure | None:
    """The parse's failure that `parse_fault` holds; None where the
    solver's text parses."""
    got = parse_fault(solver)
    return got.detail if got is not None \
        and isinstance(got.detail, ParseFailure) else None


def representative(solver: Solver, engine: Engine) -> Solver | None:
    """The family's representative solver the header names (`load`);
    None where the header names none or the reader reports it missing."""
    rep = solver.annotations.representative
    if rep is None \
            or solver.fault(ProblemKind.REPRESENTATIVE_MISSING) is not None:
        return None
    return load(rep.task_id, engine)


def concept_case(solver: Solver, cases: Iterable[Case]) -> Case | None:
    """The concept case among `cases`: the concept base, with no
    `@derive` or `@store` branch (`solver.model.is_concept_case`); None
    where none is it."""
    return next((c for c in cases if is_concept_case(solver, c)), None)


def base_names(solver: Solver, chosen: Sequence[Base | None],
               among: Sequence[Base | None]) -> tuple[str, ...]:
    """The fewest names whose bases among `among`, the solver's bases, are
    exactly `chosen` (`solver.names.cover`): the cases a value is stored
    at, the bases that depend on a relation."""
    picked = choice_values(chosen)
    if solver.choice is None or not picked:
        return ()
    return cover(solver, picked, choice_values(among))


def concept_among(solver: Solver, bases: Iterable[Base | None]
                  ) -> Base | None:
    """The concept case's base among `bases` (`solver.model.is_concept`),
    None where none is it."""
    return next((b for b in bases if concept_base(solver, b)), None)


@dataclass(frozen=True)
class AnyCase:
    """`any`: the output of any case defined on the witness
    (principles.md, under "Witnesses")."""


@dataclass(frozen=True)
class NoCase:
    """`other`: an output that no case produces (principles.md, under
    "Witnesses")."""


type VerdictCase = Case | None | AnyCase | NoCase | NameFault


def verdict_case(solver: Solver, verdict: Verdict, among: Sequence[Case],
                 branch: Branch | None) -> VerdictCase:
    """The case whose output the verdict denotes (principles.md, under "Witnesses";
    `derived` solver-file.md, under "Params", `stored` solver-file.md, under
    "Program"). A verdict asks for a model (principles.md, under "Witnesses",
    "the branch's name: the output of that branch's model"), so a name reads
    through `solver.names.model_of`, one case: the branches it names, with
    every other point at its concept branch (principles.md, under
    "Choice points and open parameters"), the case of `among` that is it where
    one is.
    `concept` is the concept case, and `derived` and `stored` the model of
    `branch`, the line's own. None where no model can be built.
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
                return NameFault(ProblemKind.NAME_DENOTES_NO_CASE,
                                 Named(verdict))
            return model_of(solver, Denoted((), (branch,)), among)
        case _:
            return model_named(solver, verdict.text, among)


def model_named(solver: Solver, text: str, among: Sequence[Case]
                ) -> Case | None | NameFault:
    """The model of the name `text` among `among`
    (`solver.names.model_of`); the fault `denote` gives where the name
    denotes nothing."""
    d = denote(solver, text)
    return d if isinstance(d, NameFault) else model_of(solver, d, among)


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


def stored_colors(engine: Engine, solver: Solver, cases: Iterable[Case]
                  ) -> frozenset[int]:
    """Every color the parameters' stored facts (`solver.solve.stored_facts`)
    hold in a `Color` column at the bases of `cases`
    (`solver.solve.by_base`). A case has no base only in a solver with no
    `Choice`, where no parameter has a case column."""
    bases = choice_bases(cases)
    out: set[int] = set()
    for p in solver.params.parameters:
        cols = [i for i, c in enumerate(p.columns) if c.type == COLOR]
        got = by_base(solver, parameter_reading(solver, p.name),
                      stored_facts(engine, solver, p), bases)
        out |= {v for _base, rows in got for r in rows for i in cols
                if isinstance(v := r[i], int)}
    return frozenset(out)


def swaps(engine: Engine, solver: Solver, task: Task, cases: Sequence[Case],
          stored: frozenset[int] | None = None) -> list[Swap]:
    """One color swap per train input of `task` that holds a color of
    `stored`, the colors the solver's parameters store at `cases` where
    None, and has a free color: the least stored color the input holds,
    swapped for the least color that neither the input nor a parameter
    holds at `cases` (`stored_colors`)."""
    held = stored_colors(engine, solver, cases)
    stored = held if stored is None else stored
    out: list[Swap] = []
    for i, ex in enumerate(task.train):
        grid = as_grid(ex.input)
        used = colors([grid])
        present = sorted(stored & used)
        free = [c for c in COLORS if c not in used | held]
        if not present or not free:
            continue
        out.append(Swap(i, present[0], free[0],
                        swapped(grid, present[0], free[0])))
    return out
