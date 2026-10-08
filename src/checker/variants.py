"""What the surveys read of a variation of the solver: the profile its
program gives on the task's pairs, and whether the Determine comp still
reproduces the stored values under it."""

import os
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from arc.task import Example
from checker.finding import AtFile, AtPair, Finding, RunKind, Where, WholeFile
from checker.judged import is_timeout, no_result
from checker.runs import NoTask
from engine import (
    Engine,
    Grid,
    Limits,
    Program,
    RunFailure,
    Tuples,
    UngroundedVariable,
)
from solver.model import Case
from solver.aggregate import Solver
from solver.outcome import Assignment, Grids, Outcome
from engine.program import as_grid
from solver.determine import (
    Determined,
    DetermineResult,
    NoDetermine,
    determine,
)
from solver.pair_runs import (
    PairId,
    TaskSection,
    candidates,
    examples,
    matching,
)
from solver.group_runs import (
    GroupRuns,
    at_once,
    group_runs,
    read_case,
    read_run,
)
from solver.variant_limits import VariantBound, variant_bound, variant_limits
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
    none of them is a candidate. `pair` is None where the run that
    enumerates the cases failed and no pair was given."""

    pair: PairId | None
    failure: RunFailure | None


@dataclass(frozen=True)
class TimedOut:
    """A run that reached a limit, which is no result: its finding."""

    finding: Finding


type ProfileResult = Profile | Fails | TimedOut


EVERY_SECTION = (TaskSection.TRAIN, TaskSection.TEST)
"""The task's sections a survey's pairs come from where it names none."""


def pairs_of(solver: Solver, sections: Collection[TaskSection]
             = EVERY_SECTION) -> list[tuple[PairId, Example]]:
    """The task's pairs of `sections`, in the order of
    `solver.pair_runs.examples`."""
    task = solver.task
    if task is None:
        return []
    return [(p, ex) for p, ex in examples(task) if p.section in sections]


def with_program(solver: Solver, program: Program) -> Solver:
    """The solver with `program` in place of its own."""
    return replace(solver, program=program)


def timed_out(failure: RunFailure, run: RunKind, where: Where,
              bound: VariantBound | None = None) -> TimedOut:
    """A run of `run`'s kind that reached a limit, as a survey holds it;
    `bound` is the rule that set a variant's CPU limit (`no_result`)."""
    return TimedOut(no_result(failure, run, None, where, bound))


def _timed(failure: RunFailure, pair: PairId | None,
           bound: VariantBound | None = None) -> TimedOut:
    where = AtPair(pair) if pair is not None else AtFile(WholeFile.SOLVER)
    return timed_out(failure, RunKind.PAIR, where, bound)


def _unresulted(failed: Sequence[RunFailure], count: int, pair: PairId,
                bound: VariantBound | None = None
                ) -> Fails | TimedOut | None:
    """Of the runs of `count` cases on the pair, those of `failed` gave
    no result: the first of them that reached a limit, else, where every
    case's run failed, the pair failing with the first failure; None
    otherwise."""
    timed = next((o for o in failed if is_timeout(o)), None)
    if timed is not None:
        return _timed(timed, pair, bound)
    if failed and len(failed) == count:
        return Fails(pair, failed[0])
    return None


class _HeldEntry(frozenset[tuple[Case, tuple[Grid, ...]]]):
    """An entry that holds the runs it was read from, each case's outcome,
    and the CPU seconds of the costliest of its runs, so that an entry of
    another program can be compared with it run by run (`entry`), and a
    variant's runs on its pair limited by it (`variant_limits`)."""

    runs: GroupRuns
    outcomes: dict[Case, Outcome]
    cpu_seconds: float


def entry(engine: Engine, solver: Solver, cases: Sequence[Case],
          pair: PairId, ex: Example, limits: Limits,
          reference: Entry | None = None, held: bool = False,
          within: Entry | None = None) -> Entry | Fails | TimedOut:
    """The pair's profile entry under the solver's program, from the runs
    `solve.outcomes` groups the cases into. A run that reaches a limit is
    no result; a run that fails otherwise gives its cases no grid, and
    where every case's run fails, the pair fails with that failure. With
    `held`, the entry holds its runs and its cases' outcomes.

    Where `reference` holds its runs, the entry is compared with it run by
    run (`_compared`), and an entry that differs from it may hold only the
    cases read up to the difference. Where `within`, or else `reference`,
    holds its runs, the runs take `variant_limits` of its CPU seconds."""
    own = within if within is not None else reference
    bound = None
    if isinstance(own, _HeldEntry):
        limits = variant_limits(limits, own.cpu_seconds)
        bound = variant_bound(own.cpu_seconds)
    runs = group_runs(engine, solver, cases, as_grid(ex.input),
                      Assignment(()), limits)
    if isinstance(reference, _HeldEntry) \
            and reference.runs.columns == runs.columns:
        return _compared(runs, cases, pair, reference, bound)
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
                failures.append(o)
    stop = _unresulted(failures, len(got), pair, bound)
    if stop is not None:
        return stop
    cands = candidates(ex)
    if not any(matching(cands, got[c]) for c, _ in grids):
        return Fails(pair, None)
    if not held:
        return frozenset(grids)
    out = _HeldEntry(grids)
    out.runs = runs
    out.outcomes = got
    out.cpu_seconds = max(r.result.cpu_seconds for r in runs.runs
                          if isinstance(r.result, Tuples))
    return out


def restricted(reference: Profile, cases: Collection[Case]) -> Profile:
    """`reference` read on `cases` alone, each entry with the runs that
    hold them, where `cases` are whole groups of the runs
    (`solver.group_runs.case_groups`), so that a profile of `cases` compares
    with it run by run (`entry`)."""
    out: list[Entry] = []
    for e in reference:
        kept = frozenset((c, g) for c, g in e if c in cases)
        if not isinstance(e, _HeldEntry):
            out.append(kept)
            continue
        held = _HeldEntry(kept)
        held.runs = GroupRuns(e.runs.columns, tuple(
            r for r in e.runs.runs if any(c in cases for c in r.cases)))
        held.outcomes = {c: o for c, o in e.outcomes.items() if c in cases}
        held.cpu_seconds = e.cpu_seconds
        out.append(held)
    return tuple(out)


def _compared(runs: GroupRuns, cases: Sequence[Case], pair: PairId,
              reference: _HeldEntry, bound: VariantBound | None
              ) -> Entry | Fails | TimedOut:
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
    stop = _unresulted([unread[c] for c in order if c in unread],
                       len(order), pair, bound)
    if stop is not None:
        return stop

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
            cases: tuple[Case, ...] | RunFailure,
            pairs: Sequence[tuple[PairId, Example]], limits: Limits,
            reference: Profile | None = None, held: bool = True,
            stop: Callable[[Sequence[Entry]], bool] | None = None,
            within: Profile | None = None) -> ProfileResult:
    """The profile of `cases` under the solver's program on `pairs`, read
    in pair order, `cases` the witnessed cases or the failure of the run
    that enumerates them (`checker.runs.Runs.cases`):
    the pair that fails where one does. With `reference`, the first pair
    whose entry differs from the reference's ends the reading, and the
    profile read so far, which differs, is the result. With `stop`, the
    reading ends at the first pair after which `stop` of the entries read
    holds, and the entries read are the result. A run that reaches a
    limit before any of these is no result.

    With `reference`, each pair's runs are compared with the reference's
    first (`entry`), and values are read only from the runs that differ.
    With none, the entries hold their runs, for a later profile to compare
    with, unless `held` is False. The runs on a pair take the limits of a
    variant of the solver whose profile `within`, or else `reference`,
    is (`entry`)."""
    if not isinstance(cases, tuple):
        if is_timeout(cases):
            return _timed(cases, pairs[0][0] if pairs else None)
        return Fails(pairs[0][0] if pairs else None, cases)
    out: list[Entry] = []
    for i, (pair, ex) in enumerate(pairs):
        ref = reference[i] if reference is not None \
            and i < len(reference) else None
        bound = within[i] if within is not None and i < len(within) \
            else None
        e = entry(engine, solver, cases, pair, ex, limits, ref,
                  held and reference is None, bound)
        if not isinstance(e, frozenset):
            return e
        out.append(e)
        if reference is not None and (i >= len(reference)
                                      or reference[i] != e):
            break
        if stop is not None and stop(out):
            break
    return tuple(out)


def ungrounded(result: ProfileResult) -> bool:
    """The program's run fails for an ungrounded variable, so the run
    measured nothing."""
    return isinstance(result, Fails) \
        and isinstance(result.failure, UngroundedVariable)


def determines(engine: Engine, solver: Solver, limits: Limits,
               measured: float | None = None
               ) -> bool | NoDetermine | NoTask | TimedOut:
    """`reproduces` of the solver's determination run; of a variant's,
    where the stored program's determination spent `measured` CPU seconds
    (`solver.determine.determine`)."""
    return reproduces(NoTask() if solver.task is None
                      else determine(engine, solver, limits, measured),
                      None if measured is None else variant_bound(measured))


def reproduces(got: DetermineResult | NoTask,
               bound: VariantBound | None = None
               ) -> bool | NoDetermine | NoTask | TimedOut:
    """Whether the determination run `got` reproduces every determined
    parameter's stored value; `NoDetermine` where the solver has no
    Determine comp, and `NoTask` where its task has no task file, so no
    determination is checked; where its run reached a limit, that run's
    finding, with `bound`, the rule that set a variant's CPU limit."""
    match got:
        case Determined():
            return not got.diffs
        case NoDetermine() | NoTask():
            return got
        case _:
            if is_timeout(got):
                return timed_out(got, RunKind.DETERMINATION,
                                 AtFile(WholeFile.SOLVER), bound)
            return False


def workers() -> int:
    return os.cpu_count() or 1


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
                 cases: tuple[Case, ...] | RunFailure,
                 pairs: Sequence[tuple[PairId, Example]], limits: Limits,
                 reference: Profile) -> bool | TimedOut:
    """The solver's program gives `reference` on `pairs`: every case's
    grids on every pair equal the reference profile's. A comparison of
    profiles, not a Fit judgment (`checker.judged.fit`)."""
    got = profile(engine, solver, cases, pairs, limits, reference)
    if isinstance(got, TimedOut):
        return got
    return got == reference


def test_verdicts[V](engine: Engine, solver: Solver,
                     cases: tuple[Case, ...] | RunFailure, limits: Limits,
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
    tests = pairs_of(solver, (TaskSection.TEST,))

    def verdict(value: V) -> TestVerdict:
        got = same_profile(engine, with_program(solver, program_of(value)),
                           cases, tests, limits, ref)
        if isinstance(got, TimedOut):
            return got
        return OnTest.PASSED if got else OnTest.REFUTED

    return dict(zip(values, at_once(verdict, values), strict=True))
