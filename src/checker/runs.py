"""The runs a check reads."""

from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cached_property
from typing import TYPE_CHECKING, NamedTuple

from engine import Engine, Grid, Index, Limits, RelationName, RunFailure
from engine.memo import ByIdentity
from engine.program import Rows
from solver.model import (
    Base,
    Branch,
    Case,
    base_case,
    DeriveBranch,
    choice_bases,
    every_base,
)
from solver.aggregate import Solver, enumerates, is_concept
from solver.cases import cases
from solver.names import Denoted, branch_text, name as case_name
from solver.problems import Fault, WitnessFileRole
from solver.outcome import Assignment, Outcome
from solver.solve import assignment, outcomes_on, relations_at
from solver.determine import DetermineResult, ParamDiff, determine
from solver.variations import Restrict, variation
from solver.pair_runs import PairRuns, TaskSection, pairs
from solver.witnessed_cases import branch_model, recorded_inputs, witnessed
from solver.group_runs import case_groups
from solver.per_case import per_case, at_bases
from solver.undefined import Undefined
from solver.witness import Entry, WitnessFile

if TYPE_CHECKING:
    from checker.derive import DeriveSurvey
    from checker.store.survey import StoreSurvey
    from checker.variants import Fails, Profile, TimedOut


class BaseOrder(NamedTuple):
    """Where a base stands among the bases (`Runs.bases`): the concept
    base first, the others by the name of their base case
    (`solver.model.base_case`)."""

    later: bool
    name: str


def base_order(solver: Solver, base: Base) -> BaseOrder:
    """Where `base` stands among the bases (`BaseOrder`)."""
    return BaseOrder(not is_concept(solver, base),
                     case_name(solver, base))


@dataclass(frozen=True)
class NoCases:
    """The run that enumerates the solver's cases failed, so a survey
    reads no value of a parameter that stores a value per case
    (`solver.per_case.per_case`), whose bases that run gives."""

    failure: RunFailure


@dataclass(frozen=True)
class NoTask:
    """The solver's task has no task file, so no run over its examples is
    made."""


def holding(groups: Iterable[Sequence[Case]], has: Callable[[Case], bool]
            ) -> list[Case]:
    """Every case of each of `groups` (`solver.group_runs.case_groups`) that
    holds a case for which `has` is true, in the groups' order."""
    return [c for g in groups if any(has(c) for c in g) for c in g]


@dataclass(frozen=True)
class Judged:
    """A program's judged cases: the witnessed cases of the program the
    runs judge, which every check and survey judges, and every case the
    runs of the groups that hold one of them show, which a judged case is
    compared against."""

    cases: tuple[Case, ...]
    shown: tuple[Case, ...]


def witness_file_role(given: object | None) -> WitnessFileRole:
    """`given` is the witness file the command names, None where it names
    none."""
    return WitnessFileRole.GIVEN if given is not None \
        else WitnessFileRole.TASK


class Runs:
    """The runs the checks of one command read, built once per command,
    for one program: the solver, the solver with every case restored
    (`restored`), the solver with a line a survey proposes (`lined_runs`),
    or the solver with one base alone (`alone`). Each part is computed on
    first use, so a check that reads no run costs none.
    Each run stops at `limits`, which the command passes from its option.
    Every check and survey reads its cases from `judged`.

    `kept` is set on the runs of the `witness --every-case` form: the
    cases the solver's own `impl_choice` holds (`restored`), or those the
    solver file `--dropped-from` names holds (`restored_against`), whose
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
        self._view: tuple[Case, ...] | None = None
        self._outcomes: dict[tuple[Grid, Assignment, Case], Outcome] = {}
        self._alone: dict[object, Runs] = {}
        self._lined: ByIdentity[Solver, Runs] = ByIdentity()
        self._profiles: dict[tuple[TaskSection, ...],
                             "Profile | Fails | TimedOut"] = {}
        self._assignments: dict[Entry, Assignment | Fault] = {}
        self._unlined: Runs | None = None

    @cached_property
    def index(self) -> Index:
        """The engine's index of the solver's program: which units feed and
        read each relation, and where a qualified name resolves."""
        return self.engine.index(self.solver.program)

    @cached_property
    def solver_cases(self) -> tuple[Case, ...] | RunFailure:
        """The solver's cases (`solver.cases.cases`)."""
        return cases(self.solver, self.engine, self.limits)

    @property
    def case_count(self) -> int:
        """How many cases the solver has (`solver_cases`); none where the
        run that enumerates them fails."""
        every = self.solver_cases
        return len(every) if isinstance(every, tuple) else 0

    @property
    def cases(self) -> tuple[Case, ...] | RunFailure:
        """The cases the checks read (`judged`): the judged cases, or
        on the view `showing` gives, the cases they are compared against;
        the failure of the run that enumerates the solver's cases where it
        fails."""
        if self._view is not None:
            return self._view
        got = self.judged
        return got.cases if isinstance(got, Judged) else got

    @property
    def cases_or_none(self) -> tuple[Case, ...]:
        """The cases the checks read (`cases`); none where the run that
        enumerates the solver's cases fails, which a check reports."""
        got = self.cases
        return got if isinstance(got, tuple) else ()

    @property
    def bases(self) -> list[Base] | RunFailure:
        """The bases of the cases the checks read (`cases`), the concept
        base first and the others by the name of their base case
        (`solver.model.base_case`); the failure of the run that enumerates
        the solver's cases where it fails."""
        got = self.cases
        if not isinstance(got, tuple):
            return got
        return sorted(choice_bases(got),
                      key=lambda b: base_order(self.solver, b))

    def differing_bases(self, d: ParamDiff
                        ) -> tuple[Base, ...] | RunFailure | None:
        """For a parameter that stores a value per case (`per_case`), each
        base (`bases`) at which its stored and its determined value differ:
        a row of the diff holds there (`solver.per_case.at_bases`), whether the
        row is stored or determined; the failure of the run that enumerates
        the solver's cases where it fails; None for a parameter with no
        case column, whose one value differs."""
        pc = per_case(self.solver, d.parameter)
        if pc is None:
            return None
        got = at_bases(self.solver, pc, (*d.stored_only, *d.determined_only),
                       self.bases)
        if not isinstance(got, list):
            return got
        return tuple(b for b, at in got if at)

    @cached_property
    def judged(self) -> Judged | RunFailure:
        """The program's judged cases with their runs: its witnessed cases
        (`witnessed`), and every case of the groups that hold one of them
        (`solver.group_runs.case_groups`, as `batches` makes the runs); the
        failure of the run that enumerates the solver's cases where it
        fails."""
        found = self.witnessed
        every = self.solver_cases
        if not isinstance(found, tuple) or not isinstance(every, tuple):
            return found if not isinstance(found, tuple) else every  # type: ignore[return-value]
        held = set(found)
        shown = {c for batch in self.batches(every)
                 for c in holding(case_groups(self.solver, batch),
                                  held.__contains__)}
        return Judged(found, tuple(c for c in every if c in shown))

    @cached_property
    def showing(self) -> "Runs":
        """These runs with the cases the judged cases are compared against
        (`Judged.shown`) read in place of the judged ones, sharing their
        outcomes: the cases the dropped-case check compares with."""
        got = self.judged
        if not isinstance(got, Judged):
            return self
        view = self.sharing(self.solver, kept=self.kept)
        view._view = got.shown
        view._alone = self._alone
        view._lined = self._lined
        view.solver_cases = self.solver_cases
        view.judged = got
        return view

    @cached_property
    def witnessed(self) -> tuple[Case, ...] | RunFailure:
        """The witnessed cases of the solver's cases
        (`solver.witnessed_cases.witnessed`), from the runs of every case of the
        solver on every recorded input, the given file's entries in place
        of the task's, held in these runs; the failure of the run that
        enumerates the solver's cases where it fails. On the runs of the
        solver with a line a survey proposes (`lined_runs`), a case of the
        solver keeps its standing in the solver's runs, and the runs made
        are those of the groups that hold a case taking the new branch,
        the others held already."""
        base = self._unlined
        unlined = None
        if base is not None:
            every, found = base.solver_cases, base.witnessed
            if isinstance(every, tuple) and isinstance(found, tuple):
                unlined = (every, found)
        return witnessed(self.engine, self.solver, self.limits,
                         self.file_role, self.entries, self._run_every,
                         unlined)

    def _run_every(self, every: Sequence[Case],
                   inputs: Sequence[tuple[Grid, Assignment]]
                   ) -> list[dict[Case, Outcome]]:
        """What each of `every`, the solver's cases, gives on each input,
        run in the batches of `batches`, each group of a batch
        (`case_groups`) that holds a case these runs lack on some input run
        on the inputs where a case is lacking, and held
        (`solver.pair_runs.RunOn`)."""
        missing = [(g, a) for g, a in inputs
                   if any((g, a, c) not in self._outcomes for c in every)]
        for batch in self.batches(every):
            run = set(holding(case_groups(self.solver, batch), lambda c: any(
                (g, a, c) not in self._outcomes for g, a in missing)))
            lacking = [c for c in batch if c in run]
            if lacking:
                self._hold(self.solver, lacking, missing)
        return self.outcomes_at(every, inputs)

    @cached_property
    def derive_survey(self) -> "DeriveSurvey":
        """The `derive` report of the solver (`checker.derive`)."""
        from checker.derive import survey_derive
        return survey_derive(self)

    @cached_property
    def store_survey(self) -> "StoreSurvey":
        """The `store` report of the solver (`checker.store`)."""
        from checker.store import survey_store
        return survey_store(self)

    @cached_property
    def determined(self) -> DetermineResult | NoTask:
        """`solver.determine.determine` of the solver; `NoTask` where the
        solver's task has no task file, whose examples it runs over."""
        if self.solver.task is None:
            return NoTask()
        return determine(self.engine, self.solver, self.limits)

    def profile(self, sections: tuple[TaskSection, ...]
                ) -> "Profile | Fails | TimedOut":
        """The solver's profile of the judged cases on the pairs of
        `sections` (`checker.variants.profile`): what a variant's runs on
        those pairs are compared with; computed once per `sections`."""
        if sections not in self._profiles:
            from checker.variants import pairs_of, profile
            self._profiles[sections] = profile(
                self.engine, self.solver, self.cases,
                pairs_of(self.solver, sections), self.limits)
        return self._profiles[sections]

    @property
    def train_profile(self) -> "Profile | Fails | TimedOut":
        """`profile` on the train pairs."""
        return self.profile((TaskSection.TRAIN,))

    @property
    def test_profile(self) -> "Profile | Fails | TimedOut":
        """`profile` on the test pairs."""
        return self.profile((TaskSection.TEST,))

    @cached_property
    def pairs(self) -> tuple[PairRuns, ...] | RunFailure:
        """`solver.pair_runs.pairs` of the solver's witnessed cases."""
        cases = self.cases
        if not isinstance(cases, tuple):
            return cases
        return pairs(self.engine, self.solver, self.limits, cases,
                     self.outcomes_at)

    @property
    def witness_file(self) -> WitnessFile | None:
        """The witness file the checks read: the given one, else the
        task's; None where neither is."""
        return self.given or self.solver.witness_file

    def entry(self, id: str) -> Entry | None:
        """The entry of the id `id` the checks read (`witness_file`), the
        first where two have it; None where none has it."""
        file = self.witness_file
        return None if file is None else file.entry(id)

    def branch_entry(self, branch: Branch) -> Entry | None:
        """The entry of a branch's witness (`entry`), filed under the
        branch's name (`solver.names.branch_text`)."""
        return self.entry(branch_text(branch))

    @property
    def file_role(self) -> WitnessFileRole:
        """The role of the witness file the checks read (`witness_file`)."""
        return witness_file_role(self.given)

    @property
    def entries(self) -> tuple[Entry, ...]:
        """The witness entries the checks read (`witness_file`)."""
        file = self.witness_file
        return () if file is None else file.entries

    def assignment(self, entry: Entry) -> Assignment | Fault:
        """The assignment `entry` stands at (`solver.solve.assignment`),
        computed once per entry."""
        if entry not in self._assignments:
            self._assignments[entry] = assignment(self.engine, self.solver, entry,
                                                  self.file_role)
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
        computed once per grid and assignment (`_fill`)."""
        key = (grid, at, case)
        if key not in self._outcomes:
            self._fill(self.solver, [case], [(grid, at)])
        return self._outcomes[key]

    def outcomes_at(self, cases: Sequence[Case],
                    inputs: Sequence[tuple[Grid, Assignment]]
                    ) -> list[dict[Case, Outcome]]:
        """What each of `cases` gives on each input (`grid_outcome`), in
        the order of `inputs`."""
        return [{c: self.grid_outcome(g, a, c) for c in cases}
                for g, a in inputs]

    def _hold(self, solver: Solver, batch: Sequence[Case],
              inputs: Sequence[tuple[Grid, Assignment]]) -> None:
        """Run `batch` together on each input under `solver`
        (`solver.solve.outcomes_on`) and hold each outcome these runs
        lack."""
        for (g, a), got in zip(inputs, outcomes_on(
                self.engine, solver, batch, inputs, self.limits), strict=True):
            for c, o in got.items():
                self._outcomes.setdefault((g, a, c), o)

    def batches(self, cases: Sequence[Case]) -> list[list[Case]]:
        """The cases the runs of the solver's cases on a recorded input are
        made for together, in their order. On the runs with every case
        restored (`restored`), the cases whose base the solver's own
        `impl_choice` holds run apart from the others, so that their
        groups are the solver's own groups and their runs the solver's
        own runs, in the solver's own order; otherwise all at once."""
        if self.kept is None:
            return [list(cases)]
        kept = {k.base for k in self.kept}
        order = {c: i for i, c in enumerate(self.kept)}
        return [b for b in (
            sorted((c for c in cases if c.base in kept),
                   key=lambda c: order.get(c, len(order))),
            [c for c in cases if c.base not in kept]) if b]

    @cached_property
    def recorded(self) -> tuple[tuple[Grid, Assignment], ...]:
        """The recorded inputs, each at its assignment
        (`solver.witnessed_cases.recorded_inputs`)."""
        return tuple(recorded_inputs(self.engine, self.solver, self.entries,
                                     self.file_role))

    @cached_property
    def _recorded(self) -> frozenset[tuple[Grid, Assignment]]:
        return frozenset(self.recorded)

    def _fill(self, solver: Solver, wanted: Sequence[Case],
              inputs: Sequence[tuple[Grid, Assignment]]) -> None:
        """Run what these runs lack of `wanted` on each input under
        `solver`, which shares their program, and hold it. A case of the
        solver's cases runs with every one of them that these runs lack,
        on a recorded input, as the witnessed-case computation runs them,
        so that its stored runs serve where another command made them;
        with every witnessed case on another input; any other case on its
        own."""
        every = self.solver_cases
        on_recorded = every if isinstance(every, tuple) else ()
        recorded_set = frozenset(on_recorded)
        batches: dict[tuple[Case, ...], list[tuple[Grid, Assignment]]] = {}
        for g, a in dict.fromkeys(inputs):
            missing = [c for c in dict.fromkeys(wanted)
                       if (g, a, c) not in self._outcomes]
            if not missing:
                continue
            recorded = (g, a) in self._recorded
            if recorded:
                pool, members = on_recorded, recorded_set
            else:
                judged = self.cases
                pool = judged if isinstance(judged, tuple) else ()
                members = frozenset(pool)
            parts = [missing]
            if any(c in members for c in missing):
                lacking = [c for c in pool if (g, a, c) not in self._outcomes]
                parts = [*(self.batches(lacking) if recorded
                           else [lacking]),
                         [c for c in missing if c not in members]]
            for part in parts:
                if part:
                    batches.setdefault(tuple(part), []).append((g, a))
        for batch, at in batches.items():
            self._hold(solver, batch, at)

    def _shares(self, solver: Solver) -> bool:
        """Whether a case gives under `solver` what it gives under the
        solver of these runs: the same program, `Choice` and parameters,
        as where a survey stands a line it proposes."""
        mine = self.solver
        return solver is mine or (solver.program is mine.program
                                  and solver.choice is mine.choice
                                  and solver.params is mine.params)

    def outcomes_on(self, solver: Solver, cases: Sequence[Case],
                    inputs: Sequence[tuple[Grid, Assignment]]
                    ) -> list[dict[Case, Outcome]]:
        """What each of `cases` gives on each input at its assignment
        under `solver` (`solver.solve.outcomes_on`), in the order of
        `inputs`. Where `solver` shares these runs' program, an outcome
        these runs hold already is read, as those of the witnessed-case
        computation, and the others run as `_fill` runs them and are
        held. `solver.witnessed_cases.recorded_inputs` gives in this
        form a task's inputs and the inputs of a witness file's
        entries, `placed_inputs` the same from entries already at
        their assignments (`entry_assignments`), and `task_inputs` a
        task's inputs alone."""
        wanted = list(dict.fromkeys(cases))
        if not self._shares(solver):
            return outcomes_on(self.engine, solver, wanted, inputs,
                               self.limits)
        self._fill(solver, wanted, inputs)
        return self.outcomes_at(wanted, inputs)

    def outcomes_of(self, solver: Solver, cases: Sequence[Case], grid: Grid,
                    at: Assignment) -> dict[Case, Outcome]:
        """`outcomes_on` on one input."""
        return self.outcomes_on(solver, cases, [(grid, at)])[0]

    def relations_on(self, grid: Grid | None,
                     relations: Sequence[RelationName], at: Assignment,
                     cap: int | None = None
                     ) -> Mapping[RelationName, Rows] | Undefined | RunFailure:
        """The rows each of `relations` holds when the solver's program
        runs on `grid`, the empty input where it is None, at `at`, with no
        `@derive` or `@store` branch (`solver.solve.relations_at`):
        undefined, or the run's failure, in their place. With `cap`, a
        relation holds at most `cap` plus one of its rows, all of them
        where it has at most `cap`, and the run prints none past those. A
        relation the run does not output raises `ValueError`."""
        return relations_at(self.engine, self.solver, base_case(None), grid,
                            relations, at, self.limits, cap)

    def defined_relations(self, grid: Grid,
                          relations: Sequence[RelationName],
                          cap: int | None = None
                          ) -> Mapping[RelationName, Rows] | RunFailure:
        """The rows each of `relations` holds on `grid` at the stored
        assignment (`relations_on`). A run with no `@derive` branch gives
        no undefined output, so undefined raises `ValueError`."""
        got = self.relations_on(grid, relations, Assignment(()), cap)
        if isinstance(got, Undefined):
            raise ValueError("a run with no `@derive` branch gave undefined")
        return got

    def lined_runs(self, solver: Solver) -> "Runs":
        """The runs of `solver`, the solver with a line a survey proposes
        added, on the recorded inputs these runs read, sharing their
        outcomes where the two share a program (`_shares`); made once per
        such solver."""
        def make() -> Runs:
            if not self._shares(solver):
                return Runs(self.engine, solver, self.limits,
                            given=self.given)
            got = self.sharing(solver)
            got._unlined = self
            return got
        return self._lined.compute(solver, make)

    def sharing(self, solver: Solver, kept: tuple[Case, ...] | None = None
                ) -> "Runs":
        """Runs of `solver`, which gives each case what the solver of
        these runs gives, with these runs' given file, holding the outcomes
        and assignments these runs hold and those either computes
        after."""
        got = Runs(self.engine, solver, self.limits, kept=kept,
                   given=self.given)
        got._outcomes = self._outcomes
        got._assignments = self._assignments
        return got

    def lined(self, solver: Solver, derived: DeriveBranch | None = None
              ) -> tuple[Case, ...] | RunFailure:
        """The cases a survey judges a line it proposes with, and its built
        entry groups, on `solver`, the solver with that line added
        (`lined_runs`): its judged cases. With `derived`, the `@derive`
        branch of a derivation no line holds: the judged cases of these
        runs' solver and the branch's model among the cases of `solver`
        (`solver.witnessed_cases.branch_model`), in the order of those cases, and no
        witnessed case of `solver` is computed, since a derivation with no
        line is judged on its model alone. The failure of the run that
        enumerates either solver's cases where it fails."""
        if derived is None:
            return self.lined_runs(solver).cases
        every = self.lined_runs(solver).solver_cases
        if not isinstance(every, tuple):
            return every
        own = self.cases
        if not isinstance(own, tuple):
            return own
        model = branch_model(solver, every, Denoted((), (derived,)))
        kept = {*own, *(() if model is None else (model,))}
        return tuple(c for c in every if c in kept)

    def alone(self, case: Case) -> "Runs":
        """The runs of the solver with `impl_choice` holding the case's
        base alone, so that no other case `impl_choice` holds changes what
        it gives (procedure.md, under "Reconcile", "with that case restored")."""
        if case.base not in self._alone:
            self._alone[case.base] = self._restricted((case.base,))
        return self._alone[case.base]

    def _restricted(self, bases: Sequence[Base | None],
                    kept: tuple[Case, ...] | None = None) -> "Runs":
        """The runs of the solver with `impl_choice` holding `bases`
        alone (`solver.variations.Restrict`). Where the solver declares no
        `impl_choice`, no clause reads it (solver-file.md, under "Cases"),
        so these are the runs of the solver as it stands."""
        solver = self.solver
        if enumerates(solver.program):
            program = variation(self.engine, solver,
                                Restrict(tuple(base_case(b) for b in bases)))
            solver = replace(solver, program=program)
        return Runs(self.engine, solver, self.limits, kept=kept,
                    given=self.given)

    def _every_base(self) -> tuple[Base, ...] | None:
        """Every case of `Choice` (`solver.model.every_base`); None for a
        solver with no `Choice`, or a `Choice` whose cases no enumeration
        gives."""
        choice = self.solver.choice
        return None if choice is None else every_base(choice)

    @cached_property
    def restored(self) -> "Runs | RunFailure | None":
        """The runs of the `witness --every-case` form: the solver with
        `impl_choice` holding every case of `Choice` (procedure.md, under
        "Reconcile"), with `kept` the solver's cases. None for a solver with no
        `impl_choice`, which holds every case already, and for a `Choice`
        whose cases no enumeration gives; the failure of the run that
        enumerates the solver's cases where it fails."""
        if not enumerates(self.solver.program):
            return None
        bases = self._every_base()
        if bases is None:
            return None
        kept = self.solver_cases
        if not isinstance(kept, tuple):
            return kept
        return self._restricted(bases, kept)

    def restored_against(self, held: Collection[str]
                         ) -> "Runs | RunFailure | None":
        """The runs of the `witness --every-case --dropped-from` form: the
        solver with `impl_choice` holding every case of `Choice`, with
        `kept` each of its cases whose name (`solver.names.name`) is among
        `held`, the names of the cases of the solver file the option
        names, so that each other case is judged as a case that file drops.
        Also for a solver with no `impl_choice`, where `held` lacks a case
        of `Choice`; None where it lacks none, and for a `Choice` whose
        cases no enumeration gives; the failure of the run that enumerates
        the cases where it fails."""
        bases = self._every_base()
        if bases is None:
            return None
        every = self._restricted(bases)
        cases = every.solver_cases
        if not isinstance(cases, tuple):
            return cases
        kept = tuple(c for c in cases if case_name(self.solver, c) in held)
        if len(kept) == len(cases) and not enumerates(self.solver.program):
            return None
        return every.sharing(every.solver, kept=kept)
