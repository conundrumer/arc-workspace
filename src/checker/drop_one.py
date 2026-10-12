"""The drop-one survey: which stored facts of a parameter that holds more
than one at a case no train pair needs."""

from dataclasses import dataclass

from checker.finding import Finding
from checker.payloads.open_values import Fact, TrainFails
from checker.runs import Runs
from checker.variants import (
    Fails,
    OnTest,
    TimedOut,
    pairs_of,
    same_profile,
    test_verdicts,
    with_program,
)
from engine import Engine, Program, RemoveFact, Row, RunFailure
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.readers import parameter
from solver.determine import stored_facts
from solver.variations import Remove, variation
from solver.pair_runs import TaskSection
from solver.group_runs import at_once
from solver.per_case import PerCase, by_base, parameter_reading


@dataclass(frozen=True)
class DroppedFact:
    """A fact whose removal keeps the train pairs' profile, with what the
    test pairs say of its removal."""

    fact: Fact
    on_test: OnTest


@dataclass(frozen=True)
class DropOneReport:
    """The facts no train pair needs; how many facts were tried, across
    how many parameters; each fact whose run reached a limit."""

    dropped: tuple[DroppedFact, ...]
    tested: int
    parameters: int
    timed_out: tuple[tuple[Fact, Finding], ...]


type DropOneResult = DropOneReport | TrainFails | TimedOut


@quotes("principles.md", "Cases",
        "**Unseen key.** When a test uses a key that no train pair contains, "
        "a lookup table fails Fit.")
def survey_drop_one(solver: Solver, runs: Runs) -> DropOneResult:
    """Each stored fact of each parameter that holds more than one at a
    case (`_tried`), cut on its own: a fact whose removal keeps the stored
    program's profile on the train pairs is one they never need, and the
    test pairs then judge its removal. The mechanism of the unseen-key
    check; a run that reached a limit is no result."""
    engine, limits = runs.engine, runs.limits
    work: list[Fact] = []
    tried: list[str] = []
    for p in solver.params.parameters:
        reading = parameter_reading(solver, p.name)
        rows = _tried(solver, runs, reading, stored_facts(runs.engine, solver, p))
        if not isinstance(rows, list):
            failed = runs.train_profile
            return failed if isinstance(failed, TimedOut) else TrainFails()
        if rows:
            tried.append(p.name)
            work += [Fact(p.name, reading.types, r) for r in rows]
    if not work:
        return DropOneReport((), 0, 0, ())
    train = pairs_of(solver, (TaskSection.TRAIN,))
    reference = runs.train_profile
    if isinstance(reference, Fails):
        return TrainFails()
    if isinstance(reference, TimedOut):
        return reference
    ref = reference

    def program_of(f: Fact) -> Program:
        return removal(engine, solver, f)

    train_fits = at_once(
        lambda f: same_profile(engine, with_program(solver, program_of(f)),
                               runs.cases, train, limits, ref), work)
    dead = [f for f, ok in zip(work, train_fits, strict=True) if ok is True]
    timed = [(f, ok.finding) for f, ok in zip(work, train_fits, strict=True)
             if isinstance(ok, TimedOut)]
    on_test = test_verdicts(engine, solver, runs.cases, limits, dead,
                            program_of, runs.test_profile) \
        if dead else {}
    dropped: list[DroppedFact] = []
    for f in dead:
        v = on_test[f]
        if isinstance(v, TimedOut):
            timed.append((f, v.finding))
            continue
        dropped.append(DroppedFact(f, v))
    return DropOneReport(tuple(dropped), len(work), len(tried), tuple(timed))


def removal(engine: Engine, solver: Solver, fact: Fact) -> Program:
    """The solver's program with `fact` removed."""
    return variation(engine, solver, Remove(
        RemoveFact(parameter(solver, fact.parameter), fact.row)))


def _tried(solver: Solver, runs: Runs, reading: PerCase, rows: list[Row]
           ) -> list[Row] | RunFailure:
    """The facts of `rows`, a parameter's stored facts, that drop-one
    cuts: the facts at each base of the cases the checks read
    (`solver.per_case.by_base`) that holds more than one, a parameter with no
    case column holding every fact; the failure of the run that
    enumerates the cases where it fails."""
    got = by_base(solver, reading, rows, runs.bases)
    if not isinstance(got, list):
        return got
    out: dict[Row, None] = {}
    for _base, at in got:
        if len(at) > 1:
            out |= dict.fromkeys(at)
    return list(out)
