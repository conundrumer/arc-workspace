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
    same_profile,
    pairs_of,
    parallel,
    profile,
    test_reference,
    test_verdicts,
    with_program,
)
from engine import Program, RelationName, RemoveFact, Row, Scope
from solver.model import Parameter, Solver, StoredGrid, row_value
from solver.solve import Remove, parameter, variation
from solver.vocabulary import PARAMS


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
    scope = Scope((PARAMS,))
    out: list[Row] = []
    for u in expanded.units:
        if u.scope == scope and u.body is None \
                and u.head.relation == RelationName((), p.name):
            row = row_value(u.head.args, solver.lib.constants)
            if row is not None:
                out.append(row)
    return out


def survey_drop_one(solver: Solver, runs: Runs) -> DropOneResult:
    """Each stored fact of each parameter that holds more than one, cut on
    its own: a fact whose removal keeps the stored program's profile on
    the train pairs is one they never need, and the test pairs then judge
    its removal. The mechanism of the unseen-key check (the determination
    step of procedure.md:142-146); a run that reached a limit is no
    result."""
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
    train = pairs_of(solver, ("train",))
    reference = profile(engine, solver, train, limits)
    if isinstance(reference, Fails):
        return TrainFails()
    if isinstance(reference, TimedOut):
        return reference
    ref = reference

    def program_of(f: Fact) -> Program:
        return variation(engine, solver, Remove(
            RemoveFact(parameter(solver, f.parameter), f.row)))

    train_fits = parallel(
        lambda f: same_profile(engine, with_program(solver, program_of(f)), train,
                       limits, ref), work)
    dead = [f for f, ok in zip(work, train_fits, strict=True) if ok is True]
    timed = [(f, ok.finding) for f, ok in zip(work, train_fits, strict=True)
             if isinstance(ok, TimedOut)]
    on_test = test_verdicts(engine, solver, limits, dead, program_of,
                            test_reference(engine, solver, limits)) \
        if dead else {}
    dropped: list[DroppedFact] = []
    for f in dead:
        v = on_test[f]
        if isinstance(v, TimedOut):
            timed.append((f, v.finding))
            continue
        dropped.append(DroppedFact(f, v, enumerable(f.types, solver.lib)))
    return DropOneReport(tuple(dropped), len(work), params, tuple(timed))
