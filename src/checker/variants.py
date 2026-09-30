"""What the surveys read of a variation of the solver: the profile its
program gives on the task's pairs, and whether the Determine comp still
reproduces the stored values under it."""

from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from enum import StrEnum
import os

from arc.task import Example
from checker.finding import AtFile, AtPair, Finding, RunKind, WholeFile
from checker.judged import is_timeout, no_result
from engine import (
    Engine,
    Tuples,
    Grid,
    Limits,
    Program,
    RunFailure,
    UngroundedVariable,
)
from solver.model import Case, Solver
from solver.model import cases as solver_cases
from solver.solve import (
    Assignment,
    Determined,
    GroupRuns,
    Grids,
    NoDetermine,
    Outcome,
    PairId,
    as_grid,
    candidates,
    determine,
    group_runs,
    read_case,
    read_run,
)
from solver.witness import Undefined

type Entry = frozenset[tuple[Case, tuple[Grid, ...]]]
"""A pair's profile entry: each case of the solver that gives grids on the pair,
with the grids it gives."""

type Profile = tuple[Entry, ...]
"""A program's profile: one entry per pair, in pair order."""


@dataclass(frozen=True)
class Fails:
    """A pair that no case of the solver passes under the program, or the run whose
    failure stopped it: `failure` is None where the runs gave outputs and
    none of them is a candidate."""

    pair: PairId
    failure: RunFailure | None


@dataclass(frozen=True)
class TimedOut:
    """A run that reached a limit, which is no result: its finding."""

    finding: Finding


type ProfileResult = Profile | Fails | TimedOut


def pairs_of(solver: Solver, sections: Sequence[str] = ("train", "test")
             ) -> list[tuple[PairId, Example]]:
    """The task's pairs of `sections`, section by section."""
    task = solver.task
    if task is None:
        return []
    out: list[tuple[PairId, Example]] = []
    for section in sections:
        exs = task.train if section == "train" else task.test
        out += [(PairId("train" if section == "train" else "test", i), ex)
                for i, ex in enumerate(exs)]
    return out


def with_program(solver: Solver, program: Program) -> Solver:
    """The solver with `program` in place of its own."""
    return replace(solver, program=program)


def _timed(failure: RunFailure, pair: PairId | None) -> TimedOut:
    where = AtPair(pair) if pair is not None else AtFile(WholeFile.SOLVER)
    return TimedOut(no_result(failure, RunKind.PAIR, None, where))


class _HeldEntry(frozenset[tuple[Case, tuple[Grid, ...]]]):
    """An entry that holds the runs it was read from and each case's
    outcome, so that an entry of another program can be compared with it
    run by run (`entry`)."""

    runs: GroupRuns
    outcomes: dict[Case, Outcome]


def entry(engine: Engine, solver: Solver, cases: Sequence[Case],
          pair: PairId, ex: Example, limits: Limits,
          reference: Entry | None = None, held: bool = False
          ) -> Entry | Fails | TimedOut:
    """The pair's profile entry under the solver's program, from the runs
    `solve.outcomes` groups the cases into. A run that reaches a limit is
    no result; a run that fails otherwise gives its cases no grid, and
    where every case's run fails, the pair fails with that failure. With
    `held`, the entry holds its runs and its cases' outcomes.

    Where `reference` holds its runs, the entry is compared with it run by
    run (`_compared`), and an entry that differs from it may hold only the
    cases read up to the difference."""
    runs = group_runs(engine, solver, cases, as_grid(ex.input),
                      Assignment(()), limits)
    if isinstance(reference, _HeldEntry) \
            and reference.runs.columns == runs.columns:
        return _compared(runs, cases, pair, reference)
    by_case: dict[Case, Outcome] = {}
    for run in runs.runs:
        by_case.update(read_run(runs.columns, run))
    got = {c: by_case[c] for c in dict.fromkeys(cases)}
    failures: list[RunFailure] = []
    grids: list[tuple[Case, tuple[Grid, ...]]] = []
    for c, o in got.items():
        match o:
            case Grids(grids=g):
                grids.append((c, g))
            case Undefined():
                pass
            case _:
                if is_timeout(o):
                    return _timed(o, pair)
                failures.append(o)
    if failures and len(failures) == len(got):
        return Fails(pair, failures[0])
    accepted = [a for _, a in candidates(ex)]
    if not any(frozenset(g) in accepted for _, g in grids):
        return Fails(pair, None)
    if not held:
        return frozenset(grids)
    out = _HeldEntry(grids)
    out.runs = runs
    out.outcomes = got
    return out


def _compared(runs: GroupRuns, cases: Sequence[Case], pair: PairId,
              reference: _HeldEntry) -> Entry | Fails | TimedOut:
    """`entry` from `runs`, where it equals `reference`, else an entry that
    differs from it: a run that reached a limit and a pair whose every run
    failed come first, as in `entry`, from the runs' results alone; then a
    run that gives the same cases the same result as the reference's run
    at its place, compared as sets of rows, gives them the reference's
    grids, and the other runs are read case by case until a case's grids
    differ from the reference's. The entry that differs holds the cases
    read up to there, and a pair that no case would pass counts as one
    that differs, since its entry differs from the reference's, which a
    case passes."""
    order = list(dict.fromkeys(cases))
    unread: dict[Case, RunFailure] = {}
    for run in runs.runs:
        if not isinstance(run.result, Tuples | Undefined):
            unread.update(dict.fromkeys(run.cases, run.result))
    failed = [unread[c] for c in order if c in unread]
    timed = next((o for o in failed if is_timeout(o)), None)
    if timed is not None:
        return _timed(timed, pair)
    if failed and len(failed) == len(order):
        return Fails(pair, failed[0])

    def grids_of(o: Outcome | None) -> tuple[Grid, ...] | None:
        return o.grids if isinstance(o, Grids) else None

    mine = set(order)
    known: list[tuple[Case, tuple[Grid, ...]]] = []

    def differs(c: Case, g: tuple[Grid, ...] | None) -> Entry:
        return frozenset([*known, *([(c, g)] if g is not None else [])])

    for c, o in reference.outcomes.items():
        if c not in mine and grids_of(o) is not None:
            return frozenset(known)
    refs = reference.runs.runs
    for i, run in enumerate(runs.runs):
        if i < len(refs) and refs[i].cases == run.cases \
                and refs[i].result == run.result:
            known += [(c, g) for c in run.cases
                      if (g := grids_of(reference.outcomes[c])) is not None]
            continue
        for c in run.cases:
            g = grids_of(read_case(runs.columns, run, c))
            if g != grids_of(reference.outcomes.get(c)):
                return differs(c, g)
            if g is not None:
                known.append((c, g))
    return frozenset(known)


def profile(engine: Engine, solver: Solver,
            pairs: Sequence[tuple[PairId, Example]], limits: Limits,
            reference: Profile | None = None, held: bool = True
            ) -> ProfileResult:
    """The profile of the solver's program on `pairs`, read in pair order:
    the pair that fails where one does. With `reference`, the first pair
    whose entry differs from the reference's ends the reading, and the
    profile read so far, which differs, is the result. A run that reaches a
    limit before any of these is no result.

    With `reference`, each pair's runs are compared with the reference's
    first (`entry`), and values are read only from the runs that differ.
    With none, the entries hold their runs, for a later profile to compare
    with, unless `held` is False."""
    cases = solver_cases(solver, engine, limits)
    if not isinstance(cases, tuple):
        if is_timeout(cases):
            return _timed(cases, pairs[0][0] if pairs else None)
        return Fails(pairs[0][0] if pairs else PairId("train", 0), cases)
    out: list[Entry] = []
    for i, (pair, ex) in enumerate(pairs):
        ref = reference[i] if reference is not None \
            and i < len(reference) else None
        e = entry(engine, solver, cases, pair, ex, limits, ref,
                  held and reference is None)
        if not isinstance(e, frozenset):
            return e
        out.append(e)
        if reference is not None and (i >= len(reference)
                                      or reference[i] != e):
            break
    return tuple(out)


def ungrounded(result: ProfileResult) -> bool:
    """The program's run fails for an ungrounded variable, so the run
    measured nothing."""
    return isinstance(result, Fails) \
        and isinstance(result.failure, UngroundedVariable)


def determines(engine: Engine, solver: Solver, limits: Limits
               ) -> bool | NoDetermine | TimedOut:
    """The Determine comp reproduces every determined parameter's stored
    value; `NoDetermine` where the solver has no Determine comp, so no
    determination is checked; where its run reached a limit, that run's
    finding."""
    got = determine(engine, solver, limits)
    match got:
        case Determined():
            return not got.diffs
        case NoDetermine():
            return got
        case _:
            if is_timeout(got):
                return TimedOut(no_result(got, RunKind.DETERMINATION, None,
                                          AtFile(WholeFile.SOLVER)))
            return False


def workers() -> int:
    return os.cpu_count() or 1


def parallel[T, R](fn: Callable[[T], R], items: Iterable[T]) -> list[R]:
    """`fn` over `items`, in threads; the engine bounds the runs at
    once."""
    with ThreadPoolExecutor(max_workers=workers()) as pool:
        return list(pool.map(fn, items))


class OnTest(StrEnum):
    """What the test pairs say of a variation the train pairs admit:
    PASSED, the test pairs give the stored program's profile under it;
    REFUTED, they give another; UNJUDGED, the stored program fails a test
    pair, so it has no test profile to judge by; NOT_RUN, no test ran for
    it (principles.md, "Models and tasks")."""

    PASSED = "passed"
    REFUTED = "refuted"
    UNJUDGED = "unjudged"
    NOT_RUN = "not run"


type TestVerdict = OnTest | TimedOut


def same_profile(engine: Engine, solver: Solver,
                 pairs: Sequence[tuple[PairId, Example]], limits: Limits,
                 reference: Profile) -> bool | TimedOut:
    """The solver's program gives `reference` on `pairs`: every case's
    grids on every pair equal the reference profile's. A comparison of
    profiles, not a Fit judgment (`checker.judged.fit`)."""
    got = profile(engine, solver, pairs, limits, reference)
    if isinstance(got, TimedOut):
        return got
    return got == reference


def test_reference(engine: Engine, solver: Solver, limits: Limits
                   ) -> Profile | Fails | TimedOut:
    """The stored program's profile on the test pairs."""
    return profile(engine, solver, pairs_of(solver, ("test",)), limits)


def test_verdicts[V](engine: Engine, solver: Solver, limits: Limits,
                     values: Sequence[V], program_of: Callable[[V], Program],
                     reference: Profile | Fails | TimedOut
                     ) -> dict[V, TestVerdict]:
    """Each value's verdict on the test pairs: whether the program under
    it (`program_of`) gives the stored program's test profile."""
    if isinstance(reference, Fails):
        return dict.fromkeys(values, OnTest.UNJUDGED)
    if isinstance(reference, TimedOut):
        return dict.fromkeys(values, reference)
    ref: Profile = reference
    tests = pairs_of(solver, ("test",))

    def verdict(value: V) -> TestVerdict:
        got = same_profile(engine, with_program(solver, program_of(value)), tests,
                   limits, ref)
        if isinstance(got, TimedOut):
            return got
        return OnTest.PASSED if got else OnTest.REFUTED

    return dict(zip(values, parallel(verdict, values), strict=True))
