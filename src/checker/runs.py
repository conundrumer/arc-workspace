"""The runs a check reads."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cached_property
from typing import TYPE_CHECKING

from engine import (
    Engine,
    Grid,
    GridInput,
    Index,
    Limits,
    Program,
    RelationName,
    RunFailure,
    Tuples,
)
from engine.program import Rows
from solver.model import Case, Solver, cases, enumerates, every_base
from solver.problems import Fault
from solver.solve import (
    Assignment,
    Restrict,
    Outcome,
    DetermineResult,
    PairRuns,
    assignment,
    case_program,
    determine,
    output_rows,
    outcomes,
    pairs,
    relations_at,
    variation,
)
from solver.vocabulary import INPUT
from solver.witness import Entry, Undefined, WitnessFile

if TYPE_CHECKING:
    from checker.derive import DeriveSurvey
    from checker.store import StoreSurvey


@dataclass(frozen=True)
class NoTask:
    """The solver's task has no task file, so no run over its examples is
    made."""


class Runs:
    """The runs the checks of one command read, built once per command.
    Each part is computed on first use, so a check that reads no run costs
    none (plan §D5 `Runs`). Each run stops at `limits`, which the command
    passes from its option.

    `kept` is set on the runs of the `witness --every-case` form
    (`restored`): the cases the solver's own `impl_choice` holds, whose
    findings the form shows. `given` is a witness file the command reads in
    place of the task's (`witness --file`)."""

    def __init__(self, engine: Engine, solver: Solver, limits: Limits,
                 kept: tuple[Case, ...] | None = None,
                 given: WitnessFile | None = None) -> None:
        self.engine = engine
        self.solver = solver
        self.limits = limits
        self.kept = kept
        self.given = given
        self._outcomes: dict[tuple[Grid, Assignment, Case],
                             Outcome | Fault] = {}
        self._alone: dict[object, Runs] = {}
        self._assignments: dict[Entry, Assignment | Fault] = {}

    @cached_property
    def index(self) -> Index:
        """The engine's index of the solver's program: which units feed and
        read each relation, and where a qualified name resolves."""
        return self.engine.index(self.solver.program)

    @cached_property
    def cases(self) -> tuple[Case, ...] | RunFailure:
        """The solver's cases (`solver.model.cases`)."""
        return cases(self.solver, self.engine, self.limits)

    @cached_property
    def derive_survey(self) -> "DeriveSurvey":
        """The `derive` report of the solver (`checker.derive`)."""
        from checker.derive import derive_survey
        return derive_survey(self)

    @cached_property
    def store_survey(self) -> "StoreSurvey":
        """The `store` report of the solver (`checker.store`)."""
        from checker.store import store_survey
        return store_survey(self)

    @cached_property
    def determined(self) -> DetermineResult | NoTask:
        """`solver.solve.determine` of the solver; `NoTask` where the
        solver's task has no task file, whose examples it runs over."""
        if self.solver.task is None:
            return NoTask()
        return determine(self.engine, self.solver, self.limits)

    @cached_property
    def pairs(self) -> tuple[PairRuns, ...] | RunFailure:
        """`solver.solve.pairs` of the solver."""
        return pairs(self.engine, self.solver, self.limits)

    @property
    def entries(self) -> tuple[Entry, ...]:
        """The witness entries the checks read: the given file's, else the
        task's witness file's."""
        file = self.given or self.solver.witness_file
        return () if file is None else file.entries

    def assignment(self, entry: Entry) -> Assignment | Fault:
        """The assignment `entry` stands at (`solver.solve.assignment`),
        computed once per entry."""
        if entry not in self._assignments:
            self._assignments[entry] = assignment(self.solver, entry)
        return self._assignments[entry]

    def outcome(self, entry: Entry, case: Case) -> Outcome | Fault:
        """What `case` gives on the entry's input at the entry's assignment
        (`grid_outcome`), or the problem that stops the entry's
        assignment."""
        at = self.assignment(entry)
        return at if isinstance(at, Fault) \
            else self.grid_outcome(entry.input, at, case)

    def grid_outcome(self, grid: Grid, at: Assignment, case: Case
                     ) -> Outcome:
        """What `case` gives on `grid` at `at` (`solver.solve.outcomes`),
        computed once per grid and assignment for every case of the solver, and for
        a case the runner does not hold, on its own."""
        key = (grid, at, case)
        if key not in self._outcomes:
            solver_cases = self.cases
            cases = [c for c in solver_cases if (grid, at, c) not in self._outcomes] \
                if isinstance(solver_cases, tuple) and case in solver_cases else [case]
            for c, got in outcomes(self.engine, self.solver, cases, grid, at,
                                   self.limits).items():
                self._outcomes[(grid, at, c)] = got
        got = self._outcomes[key]
        assert not isinstance(got, Fault)
        return got

    def relations_on(self, grid: Grid, relations: Sequence[RelationName],
                     cap: int | None = None
                     ) -> Mapping[RelationName, Rows] | RunFailure:
        """The rows each of `relations` holds when the solver's program
        runs on `grid` as it stands, with no `@derive` or `@store` branch
        (`solver.solve.relations_at`). With `cap`, a relation holds at most
        `cap` plus one of its rows, all of them where it has at most `cap`,
        and the run prints none past those. A relation the run does not
        output raises `ValueError`."""
        if cap is None:
            got = relations_at(self.engine, self.solver, Case(None, ()), grid,
                               relations, Assignment(()), self.limits)
        else:
            program = case_program(self.engine, self.solver, Case(None, ()),
                                   grid, Assignment(()), self.limits)
            if not isinstance(program, Program):
                got = program
            else:
                ran = self.engine.run(program, {INPUT: GridInput(grid)},
                                      list(relations), self.limits,
                                      dict.fromkeys(relations, cap))
                got = output_rows(ran, relations) \
                    if isinstance(ran, Tuples) else ran
        if isinstance(got, Undefined):
            raise ValueError("a run with no `@derive` branch gave undefined")
        return got

    def alone(self, case: Case) -> "Runs":
        """The runs of the solver with `impl_choice` holding the case's
        base alone, so that no other case `impl_choice` holds changes what
        it gives (procedure.md:210, "with that case restored")."""
        if case.base not in self._alone:
            program = variation(self.engine, self.solver,
                                Restrict((Case(case.base, ()),)))
            self._alone[case.base] = Runs(
                self.engine, replace(self.solver, program=program),
                self.limits, given=self.given)
        return self._alone[case.base]

    @cached_property
    def restored(self) -> "Runs | RunFailure | None":
        """The runs of the `witness --every-case` form: the solver with
        `impl_choice` holding every case of `Choice` (procedure.md:210),
        with `kept` the cases the solver holds. None for a solver with no
        `impl_choice`, which holds every case already, and for a `Choice`
        whose cases no enumeration gives; the failure of the run that
        enumerates the solver's cases where it fails."""
        choice = self.solver.choice
        if choice is None or not enumerates(self.solver.program):
            return None
        bases = every_base(choice)
        if bases is None:
            return None
        kept = self.cases
        if not isinstance(kept, tuple):
            return kept
        program = variation(self.engine, self.solver,
                            Restrict(tuple(Case(b, ()) for b in bases)))
        return Runs(self.engine, replace(self.solver, program=program),
                    self.limits, kept=kept, given=self.given)
