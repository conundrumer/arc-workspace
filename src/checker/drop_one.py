"""The drop-one survey: which stored facts of a parameter that holds more
than one no train pair needs."""

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
from engine import Program, RelationName, RemoveFact, Row
from engine.quotes import quotes
from solver.model import Parameter, Solver, StoredGrid, row_value
from solver.solve import Remove, TaskSection, at_once, parameter, variation
from solver.vocabulary import PARAMS_SCOPE


@dataclass(frozen=True)
class Fact:
    """One stored fact of a parameter: the parameter, its column types,
    and the fact's row."""

    parameter: str
    types: tuple[str, ...]
    row: Row


@dataclass(frozen=True)
class DroppedFact:
    """A fact whose removal keeps the train pairs' profile, with what the
    test pairs say of its removal, and whether `sweep` enumerates its
    parameter."""

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


def stored_facts(solver: Solver, runs: Runs, p: Parameter) -> list[Row]:
    """The parameter's stored facts, a GRID call's cells among them."""
    if not isinstance(p.stored, StoredGrid):
        return list(p.stored)
    expanded = runs.engine.expand(solver.program)
    out: list[Row] = []
    for u in expanded.units:
        if u.scope == PARAMS_SCOPE and u.body is None \
                and u.head.relation == RelationName((), p.name):
            row = row_value(u.head.args, solver.lib.constants)
            if row is None:
                raise ValueError(f"a fact of `{p.name}` the GRID expansion "
                                 "wrote states no constant")
            out.append(row)
    return out


@quotes("principles.md", "Cases",
        "**Unseen key.** When a test uses a key that no train pair contains, "
        "a lookup table fails Fit.")
def survey_drop_one(solver: Solver, runs: Runs) -> DropOneResult:
    """Each stored fact of each parameter that holds more than one, cut on
    its own: a fact whose removal keeps the stored program's profile on
    the train pairs is one they never need, and the test pairs then judge
    its removal. The mechanism of the unseen-key check; a run that reached
    a limit is no result."""
    engine, limits = runs.engine, runs.limits
    work: list[Fact] = []
    params = 0
    for p in solver.params.parameters:
        rows = stored_facts(solver, runs, p)
        if len(rows) > 1:
            params += 1
            types = tuple(c.type for c in p.columns)
            work += [Fact(p.name, types, r) for r in rows]
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
        dropped.append(DroppedFact(f, v, enumerable(f.types, solver.lib)))
    return DropOneReport(tuple(dropped), len(work), params, tuple(timed))
