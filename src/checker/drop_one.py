"""The drop-one survey: which stored facts of a parameter that holds more
than one at a case no train pair needs."""

from collections.abc import Sequence
from dataclasses import dataclass

from checker.domains import enumerable
from checker.finding import Finding
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
from engine import Program, RemoveFact, Row, RunFailure
from engine.quotes import quotes
from solver.model import Solver
from solver.model import parameter
from solver.solve import (
    stored_facts,
    PerCase,
    Remove,
    TaskSection,
    at_once,
    by_base,
    parameter_reading,
    variation,
)


@dataclass(frozen=True)
class Fact:
    """One stored fact of a parameter: the parameter, its column types
    (`solver.model.column_types`), and the fact's row."""

    parameter: str
    types: tuple[str, ...]
    row: Row


@dataclass(frozen=True)
class DroppedFact:
    """A fact whose removal keeps the train pairs' profile, with what the
    test pairs say of its removal, and whether `sweep` enumerates its
    parameter's values (`sweeps_values`)."""

    fact: Fact
    on_test: OnTest
    enumerable: bool


@dataclass(frozen=True)
class DropOneReport:
    """The facts no train pair needs; how many facts were tried, across
    how many parameters; each fact whose run reached a limit."""

    dropped: tuple[DroppedFact, ...]
    tested: int
    parameters: int
    timed_out: tuple[tuple[Fact, Finding], ...]


@dataclass(frozen=True)
class TrainFails:
    """The stored program fails a train pair."""


type DropOneResult = DropOneReport | TrainFails | TimedOut


def sweeps_values(solver: Solver, value_types: Sequence[str]) -> bool:
    """Whether the sweep enumerates a parameter's values: each column of
    its value (`solver.solve.PerCase.value_types`) has a candidate
    domain."""
    return enumerable(value_types, solver.lib)


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
    many: dict[str, bool] = {}
    for p in solver.params.parameters:
        reading = parameter_reading(solver, p.name)
        rows = _tried(solver, runs, reading, stored_facts(runs.engine, solver, p))
        if not isinstance(rows, list):
            failed = runs.train_profile
            return failed if isinstance(failed, TimedOut) else TrainFails()
        if rows:
            many[p.name] = sweeps_values(solver, reading.value_types)
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
        return variation(engine, solver, Remove(
            RemoveFact(parameter(solver, f.parameter), f.row)))

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
        dropped.append(DroppedFact(f, v, many[f.parameter]))
    return DropOneReport(tuple(dropped), len(work), len(many), tuple(timed))


def _tried(solver: Solver, runs: Runs, reading: PerCase, rows: list[Row]
           ) -> list[Row] | RunFailure:
    """The facts of `rows`, a parameter's stored facts, that drop-one
    cuts: the facts at each base of the cases the checks read
    (`solver.solve.by_base`) that holds more than one, a parameter with no
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
