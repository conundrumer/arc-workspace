"""The checks on `@derive` and `@store` branches and on the determination,
and what the `derive` and `store` surveys share: the runs of cases on the
pairs, the witnesses a survey builds, and the named `@ignore` lines."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING

from checker.finding import (
    AtEntry,
    AtFile,
    AtLine,
    AtParameter,
    Finding,
    Kind,
    RunKind,
    Where,
    WholeFile,
)
from checker.judged import (
    NO_TASK,
    Fit,
    Fits,
    Swap,
    differ,
    fit,
    missed,
    no_result,
    swaps,
)
from checker.payloads.branches import (
    BranchEntryPayload,
    BranchName,
    DerivedDataPayload,
    DeterminationDiffPayload,
    ExcludedPayload,
    IdleIgnorePayload,
)
from checker.runs import NoTask, Runs
from engine import Grid, RelationName, RunFailure
from engine.quotes import quotes
from solver.annotations import IgnoreForm, IgnoreLine
from solver.model import (
    Branch,
    Case,
    DeriveBranch,
    Solver,
    StoreBranch,
    StoredAtDerive,
    branch_under,
    ignore_targets,
    takes,
)
from solver.cases import cases
from solver.names import Denoted, denote, denoted_cases
from solver.problems import Fault, NameFault, WitnessFileRole
from solver.outcome import Assignment, Grids, Outcome, group_grid, is_result
from solver.solve import (
    CaseOnPair,
    Determined,
    NoDetermine,
    PairId,
    PairRuns,
    assignment,
    branch_model,
    entry_assignments,
    examples,
    pair_on,
    task_inputs,
)
from solver.witness import (
    Entry,
    GroupGrid,
    Groups,
    Outcomes,
    grouped,
)

if TYPE_CHECKING:
    from checker.store import Change

# Runs of cases on the pairs


def pair_runs(runs: Runs, solver: Solver, cases: Sequence[Case]
              ) -> tuple[PairRuns, ...]:
    """The cases of `cases` on the train and test pairs, as
    `solver.solve.pairs` runs a case of the solver, pair by pair: a case
    runs on a pair only while it has missed no pair before, since Fit
    (`judged.fit`) reads a case's first miss alone, so a pair's runs hold
    the cases that ran there. The cases share runs
    (`solver.solve.outcomes`), and an outcome `runs` hold already is read
    (`Runs.outcomes_of`)."""
    task = solver.task
    if task is None or not cases:
        return ()
    out: list[PairRuns] = []
    alive = list(dict.fromkeys(cases))
    for (pair, ex), (grid, assign) in zip(examples(task), task_inputs(task),
                                          strict=True):
        if not alive:
            break
        here = pair_on(pair, ex, alive,
                       runs.outcomes_of(solver, alive, grid, assign))
        out.append(here)
        alive = [r.case for r in here.cases if not missed(r)]
    return tuple(out)


def _merged(*parts: Sequence[PairRuns]) -> tuple[PairRuns, ...]:
    by: dict[PairId, list[CaseOnPair]] = {}
    for part in parts:
        for p in part:
            by.setdefault(p.pair, []).extend(p.cases)
    return tuple(PairRuns(k, tuple(v)) for k, v in by.items())


def model_fit(runs: Runs, solver: Solver, cases: Sequence[Case]
              ) -> Fit | None:
    """How the model whose cases are `cases` meets Fit (`judged.fit`):
    the first case runs first, and the others only where it does not
    fit. None where `cases` holds none."""
    if not cases:
        return None
    first = pair_runs(runs, solver, cases[:1])
    got = fit(first, cases[:1])
    if isinstance(got, Fits) or len(cases) == 1:
        return got
    return fit(_merged(first, pair_runs(runs, solver, cases[1:])), cases)


def with_line(solver: Solver, branch: DeriveBranch | StoreBranch) -> Solver:
    """The solver with the branch's `@derive` or `@store` line standing:
    a `@derive` branch at its parameter's point, after the point's own
    branches, with the stored branch of the point first where the point
    is new; a `@store` branch after every other."""
    branches: list[Branch] = list(solver.branches)
    if isinstance(branch, StoreBranch):
        return replace(solver, branches=(*branches, branch))
    at = [i for i, b in enumerate(branches)
          if isinstance(b, (DeriveBranch, StoredAtDerive))
          and b.parameter == branch.parameter]
    if at:
        branches.insert(at[-1] + 1, branch)
    else:
        branches += [StoredAtDerive(branch.parameter), branch]
    return replace(solver, branches=tuple(branches))


def counterpart(case: Case, branch: DeriveBranch | StoreBranch) -> Case:
    """The case that takes the first branch of `branch`'s point and the
    same branches elsewhere."""
    return Case(case.base, tuple(b for b in case.branches if b != branch))


def taking(solver: Solver, cases: Sequence[Case], branch: Branch
           ) -> list[Case]:
    """The cases of `cases` that take `branch` (`solver.model.takes`)."""
    return [c for c in cases if takes(solver, c, branch)]


def ordered(solver: Solver, cases: Sequence[Case],
            branch: DeriveBranch | StoreBranch) -> list[Case]:
    """The cases of `cases` that take `branch` (`taking`), with the
    branch's model (`branch_models`) first."""
    took = taking(solver, cases, branch)
    return list(dict.fromkeys([*branch_models(solver, took, branch),
                               *took]))


def without_named_ignores(runs: Runs, solver: Solver
                          ) -> tuple[Case, ...] | RunFailure:
    """The cases the runner would hold with no named `@ignore: derive` or
    `@ignore: store` line standing."""
    kept = _unnamed(solver)
    if len(kept) == len(solver.annotations.ignores):
        return cases(solver, runs.engine, runs.limits)
    return _cases_under(runs, solver, kept)


def _unnamed(solver: Solver) -> tuple[IgnoreLine, ...]:
    """The solver's `@ignore` lines less the named `@ignore: derive` and
    `@ignore: store` lines."""
    return tuple(i for i in solver.annotations.ignores
                 if i.form is IgnoreForm.LINT or i.name is None)


def _cases_under(runs: Runs, solver: Solver,
                 ignores: tuple[IgnoreLine, ...]) -> tuple[Case, ...] | RunFailure:
    """The solver's cases with `ignores` standing in place of its own
    `@ignore` lines."""
    return cases(replace(solver, annotations=replace(
        solver.annotations, ignores=ignores)), runs.engine, runs.limits)


def exclusion(runs: Runs, solver: Solver, branch: DeriveBranch | StoreBranch
              ) -> ExcludedPayload | None:
    """Where no case of the solver takes the branch of a `@derive` or
    `@store` line, what excludes its cases: the named `@ignore` lines
    under the line, where the cases the runner would hold without them
    take the branch, and `impl_choice`, where the cases with every value
    of `Choice` restored take it beyond those. None where neither excludes
    a case of it, as where no case reads the line's parameter or
    relation."""
    a = solver.annotations
    form = IgnoreForm.DERIVE if isinstance(branch, DeriveBranch) \
        else IgnoreForm.STORE
    named = [i.line for i in a.ignores
             if i.form is form and i.name is not None
             and branch_under(solver, i) == branch]
    unnamed = without_named_ignores(runs, solver)
    by_lines = isinstance(unnamed, tuple) and bool(taking(solver, unnamed,
                                                          branch))
    restored = runs.restored
    by_impl = False
    if isinstance(restored, Runs):
        every = without_named_ignores(restored, restored.solver)
        if isinstance(every, tuple):
            by_impl = len(taking(solver, every, branch)) > (
                len(taking(solver, unnamed, branch))
                if isinstance(unnamed, tuple) else 0)
    if not by_lines and not by_impl:
        return None
    return ExcludedPayload(branch, tuple(named) if by_lines else (),
                           by_impl)


def bare_ignored(solver: Solver, form: IgnoreForm
                 ) -> list[tuple[RelationName, str | None]]:
    """What the bare `@ignore: derive` or `@ignore: store` lines of `form`
    exclude: each target relation, with the line's proposer
    (`solver.model.ignore_targets`)."""
    return [(t, i.proposer) for i in solver.annotations.ignores
            if i.form is form and i.name is None
            for t in ignore_targets(solver.program, i)]


def untaken(runs: Runs, solver: Solver, branch: Branch) -> bool:
    """No case of the solver takes `branch`; False where the run that
    enumerates the solver's cases fails."""
    every = runs.solver_cases
    return isinstance(every, tuple) and not taking(solver, every, branch)


def excluded_finding(runs: Runs, solver: Solver,
                     branch: DeriveBranch | StoreBranch, at: Where
                     ) -> Finding | None:
    """The finding on a `@derive` or `@store` line whose cases are
    excluded (`exclusion`); None where nothing excludes them."""
    excluded = exclusion(runs, solver, branch)
    return None if excluded is None \
        else Finding(Kind.BRANCH_EXCLUDED, at, excluded)


def untaken_lines(runs: Runs, solver: Solver) -> frozenset[int]:
    """The lines of the `@derive` and `@store` lines whose branch no case
    of the solver takes (`untaken`), whose verdicts are not judged."""
    return frozenset(b.line.line for b in solver.branches
                     if isinstance(b, (DeriveBranch, StoreBranch))
                     and b.line is not None and untaken(runs, solver, b))


# Witnesses


class NoWitness(StrEnum):
    """Why a survey builds no witness of a branch."""

    NOT_ONE_COLOR = "not one color"
    """The parameter's stored value is other than one color."""
    NO_FREE_COLOR = "no free color"
    """No train input has a color neither it nor a parameter holds."""
    ONE_OUTPUT = "one output"
    """On no swap is the branch's model defined and other than its
    counterpart's output."""
    UNCHANGED = "unchanged"
    """No D4 image or color swap of a train input changes the value."""


@dataclass(frozen=True)
class SwapWitness:
    """A swapped train input on which `case`, which takes the branch,
    gives an output other than `other`, its counterpart."""

    swap: Swap
    case: Case
    other: Case


@dataclass(frozen=True)
class FailedOn:
    """A run on a swapped train input a witness is sought on that failed,
    or reached a limit: the train input's index, and the failure."""

    train: int
    failure: RunFailure


def diverges(runs: Runs, solver: Solver, cases: Sequence[Case],
             branch: DeriveBranch | StoreBranch, grid: Grid,
             assign: Assignment, defined: bool = False
             ) -> tuple[Case, Case] | RunFailure | None:
    """The first case of `cases` that gives on `grid` at `assign` an
    output other than its counterpart's, with that counterpart; with
    `defined`, only a case defined there counts. The first failed run
    where none does and a run failed; None otherwise."""
    pairs = [(c, counterpart(c, branch)) for c in cases]
    got = runs.outcomes_of(solver, [x for pair in pairs for x in pair],
                           grid, assign)
    failed: RunFailure | None = None
    for case, other in pairs:
        a, b = got[case], got[other]
        for o in (a, b):
            if not is_result(o):
                failed = failed or o
        if shows_apart(a, b) if defined else differ(a, b):
            return case, other
    return failed


def shows_apart(a: object, b: object) -> bool:
    """A run shows `a` defined and differing from `b` (`differ`): what a
    branch's witness needs of a case against its counterpart
    (`witness_divergence`), and what a run shows of no case that `b`
    subsumes (principles.md, under "Witnesses" and "Equivalence and
    subsumption")."""
    return isinstance(a, Grids) and differ(a, b)


def witness_divergence(runs: Runs, solver: Solver, cases: Sequence[Case],
                       branch: DeriveBranch | StoreBranch, grid: Grid,
                       assign: Assignment
                       ) -> tuple[Case, Case] | RunFailure | None:
    """The output a witness needs (principles.md, under "Witnesses"): the
    first case of `cases` defined on `grid` at `assign` that gives an
    output other than its counterpart's, with that counterpart
    (`diverges`)."""
    return diverges(runs, solver, cases, branch, grid, assign, defined=True)


@dataclass(frozen=True)
class RecordedWitness:
    """An input of the witness file, at its entry's assignment, on which
    `case`, which takes the branch, is defined and gives an output other
    than `other`, its counterpart: the entry's id, and the entry, whose
    input and `assign` a built witness takes."""

    entry: Entry
    case: Case
    other: Case


@dataclass(frozen=True)
class Unwitnessed:
    """No input the survey looks on witnesses the branch: why no color
    swap serves, or the swap run that failed, where no input of the
    witness file serves either; and the first case the survey looks with
    (`witness_targets`), with its counterpart, which no input shows apart
    (`shows_apart`), None where it looks with no case."""

    swap: NoWitness | FailedOn
    pair: tuple[Case, Case] | None


type Witness = SwapWitness | RecordedWitness | Unwitnessed


def branch_models(solver: Solver, cases: Sequence[Case],
                  branch: DeriveBranch | StoreBranch) -> list[Case]:
    """The cases of `cases` a branch's witness is judged on: the branch's
    model (`solver.solve.branch_model`); none where no case of `cases`
    takes it."""
    got = branch_model(solver, cases, Denoted((), (branch,)))
    return [] if got is None else [got]


def fitting(runs: Runs, solver: Solver, cases: Sequence[Case]
            ) -> list[Case]:
    """The cases of `cases` that fit the pairs (`judged.fit`), in their
    order, from the runs on the pairs `runs` hold or make
    (`pair_runs`)."""
    if solver.task is None or not cases:
        return []
    got = pair_runs(runs, solver, cases)
    return [c for c in cases if isinstance(fit(got, [c]), Fits)]


def witness_targets(runs: Runs, solver: Solver, cases: Sequence[Case],
                    branch: DeriveBranch | StoreBranch) -> list[Case]:
    """The cases a survey looks for a branch's witness with, each against
    its counterpart: the branch's models
    (`branch_models`), else the cases that take it, in `ordered` order,
    each where it and its counterpart fit the pairs, since a case that
    fails Fit is no separation target."""
    models = branch_models(solver, cases, branch)
    fit = fitting_both(runs, solver, list(dict.fromkeys(
        [*models, *ordered(solver, cases, branch)])), branch)
    return [c for c in models if c in fit] or fit


def fitting_both(runs: Runs, solver: Solver, cases: Sequence[Case],
                 branch: DeriveBranch | StoreBranch) -> list[Case]:
    """The cases of `cases` that fit the pairs with their counterparts
    (`fitting`, `counterpart`)."""
    fit_set = set(fitting(runs, solver, [x for c in cases
                                         for x in (c, counterpart(c, branch))]))
    return [c for c in cases
            if c in fit_set and counterpart(c, branch) in fit_set]


def swap_witness(runs: Runs, solver: Solver, cases: Sequence[Case],
                 branch: DeriveBranch | StoreBranch, color: int | None
                 ) -> SwapWitness | NoWitness | FailedOn:
    """The color-swap witness of `branch` (`judged.swaps`): the first
    swapped train input on which a case the survey looks with
    (`witness_targets`) gives the output a witness needs
    (`witness_divergence`, principles.md, under "Witnesses"). `color` is
    the one color the branch's value holds; None where it holds other
    than one color."""
    task = solver.given_task
    if color is None:
        return NoWitness.NOT_ONE_COLOR
    found = swaps(runs.engine, solver, task, cases, frozenset({color}))
    if not found:
        return NoWitness.NO_FREE_COLOR
    models = witness_targets(runs, solver, cases, branch)
    if not models:
        return NoWitness.ONE_OUTPUT
    failed: FailedOn | None = None
    for s in found:
        got = witness_divergence(runs, solver, models, branch, s.grid,
                                 Assignment(()))
        if isinstance(got, tuple):
            return SwapWitness(s, got[0], got[1])
        if got is not None and failed is None:
            failed = FailedOn(s.index, got)
    return failed or NoWitness.ONE_OUTPUT


def recorded_witness(runs: Runs, solver: Solver, cases: Sequence[Case],
                     branch: DeriveBranch | StoreBranch,
                     swap: NoWitness | FailedOn
                     ) -> RecordedWitness | Unwitnessed:
    """The first input of the witness file, each at its entry's
    assignment, on which a case the survey looks with
    (`witness_targets`) gives the output a witness needs
    (`witness_divergence`, principles.md, under "Witnesses"): the
    recorded inputs a survey looks on beside the color swaps, `swap`
    saying why no color swap serves. `Unwitnessed` where none does; an
    entry whose `assign` names nothing is the fault `fault_findings`
    reports, and is passed over."""
    models = witness_targets(runs, solver, cases, branch)
    if not models:
        return Unwitnessed(swap, None)
    for e, assign in entry_assignments(runs.engine, runs.solver, runs.entries,
                                       runs.file_role):
        got = witness_divergence(runs, solver, models, branch, e.input,
                                 assign)
        if isinstance(got, tuple):
            return RecordedWitness(e, *got)
    return Unwitnessed(swap, (models[0], counterpart(models[0], branch)))


def witness_entry(runs: Runs, solver: Solver, name: str, separates: str,
                  grid: Grid, cases: Sequence[Case],
                  given: Entry | None = None) -> Entry | RunFailure:
    """The witness file's entry a survey builds for a branch: its id the
    branch's name, its input `grid`, and its groups the outputs `cases`
    give there, as `record` writes them (`solver.witness.grouped`); built
    from an entry of the file, `given`, the entry's `assign` and the
    outputs at its assignment. A case whose run fails fails the entry."""
    assign = Assignment(()) if given is None \
        else assignment(runs.engine, solver, given, runs.file_role)
    assert not isinstance(assign, Fault)
    got = runs.outcomes_of(solver, cases, grid, assign)
    groups = groups_of(solver, [(c, got[c]) for c in [
        *(c for c in cases if c.is_base_case),
        *(c for c in cases if not c.is_base_case)]])
    if not isinstance(groups, Groups):
        assert not isinstance(groups, Fault)
        return groups
    return Entry(name, separates, grid, () if given is None else given.assign,
                 groups)


def results(got: Sequence[tuple[Case, Outcome | Fault]]
            ) -> Outcomes | RunFailure | Fault:
    """Each case's outcome on an input as a witness file's group holds it
    (`solver.outcome.group_grid`), in the order of `got`; the first outcome
    that is no result (`solver.outcome.is_result`) in their place."""
    found: list[tuple[Case, GroupGrid]] = []
    for case, o in got:
        if not is_result(o):
            return o
        found.append((case, group_grid(o)))
    return tuple(found)


def entry_outcomes(runs: Runs, entry: Entry) -> Outcomes | RunFailure | Fault:
    """What each case the checks read (`Runs.cases`) gives on the entry's
    input at its `assign`, in the order the cases come in (`results`): a
    grid, a list of grids per resolution (history 1119), or undefined. The
    failure of the run that enumerates the cases, the problem that stops
    the entry's assignment, or the first run with no result, in its
    place."""
    cases = runs.cases
    if not isinstance(cases, tuple):
        return cases
    at = runs.assignment(entry)
    if isinstance(at, Fault):
        return at
    return results([(c, runs.outcome(entry, c)) for c in cases])


def groups_of(solver: Solver, got: Sequence[tuple[Case, Outcome | Fault]]
              ) -> Groups | RunFailure | Fault:
    """An entry's groups from each case's outcome on its input, as
    `record` writes them (`solver.witness.grouped`); the first outcome of
    `got` that is no result in their place (`results`)."""
    found = results(got)
    return grouped(solver, found) if isinstance(found, tuple) else found


def swap_entry(runs: Runs, solver: Solver, name: str, branch: BranchName,
               train: int, change: "Change", grid: Grid,
               cases: Sequence[Case]) -> Entry | RunFailure:
    """The witness entry a survey builds for a branch on a train input
    changed by `change` (`witness_entry`), its `separates` the renderer's
    prose for it."""
    from checker.render.branches import separates
    return witness_entry(runs, solver, name,
                         separates(branch, train, change), grid, cases)


def recorded_entry(runs: Runs, solver: Solver, name: str, branch: BranchName,
                   entry: Entry, cases: Sequence[Case]) -> Entry | RunFailure:
    """The witness entry a survey builds for a branch on the input of an
    entry of the witness file, at its assignment (`witness_entry`)."""
    from checker.render.branches import separates_recorded
    return witness_entry(runs, solver, name,
                         separates_recorded(branch, entry), entry.input,
                         cases, entry)


@dataclass(frozen=True)
class BuiltBy:
    """What a survey built a witness entry from: the solver with the
    branch's line standing, and the cases its groups were built from,
    which `record_lines` counts."""

    solver: Solver
    cases: tuple[Case, ...]


def unnamed(solver: Solver, cases: Sequence[Case], entry: Entry
            ) -> tuple[str, ...]:
    """The names of the entry's groups that denote no case of `cases`,
    the solver's cases, in the order the groups hold them: a survey writes
    an entry only where each name it holds denotes a case of the solver
    (solver-file.md, under "Witness file")."""
    if not isinstance(entry.output, Groups):
        return ()
    out: list[str] = []
    for g in entry.output.groups:
        for n in g.cases:
            got = denoted_cases(solver, n, cases)
            if (isinstance(got, NameFault) or not got) and n not in out:
                out.append(n)
    return tuple(out)


def entry_findings(runs: Runs, solver: Solver,
                   branch: DeriveBranch | StoreBranch, ref: BranchName,
                   name: str, cases: Sequence[Case], entry: Entry
                   ) -> list[Finding]:
    """Where the witness file's entry of a branch's name does not witness
    it (principles.md, under "Witnesses"): at its assignment, no case that takes the
    branch diverges from its counterpart. A run that fails where none
    diverges is the finding in its place; an `assign` that names nothing
    is the fault `fault_findings` reports."""
    assign = assignment(runs.engine, solver, entry, runs.file_role)
    if isinstance(assign, Fault):
        return []
    got = diverges(runs, solver, cases, branch, entry.input, assign)
    where = AtEntry(name, WitnessFileRole.TASK, assigned=False)
    if isinstance(got, tuple):
        return []
    if got is not None:
        return [no_result(got, RunKind.WITNESS, None, where)]
    return [Finding(Kind.BRANCH_ENTRY, where, BranchEntryPayload(ref, name))]


# Idle `@ignore` lines


def idle_ignores(runs: Runs, form: IgnoreForm) -> list[Finding]:
    """A finding per named `@ignore: derive` or `@ignore: store` line
    that excludes no case the runner would hold without it
    (solver-file.md, under "Params" and "Program"): no `@derive` or `@store`
    line stands above it, or no case takes that line's branch and every branch
    its name contains. A name that denotes no case is the fault
    `fault_findings` reports."""
    solver = runs.solver
    a = solver.annotations
    bare = _unnamed(solver)
    out: list[Finding] = []
    for line in a.ignores:
        if line.form is not form or line.name is None:
            continue
        denoted = denote(solver, line.name)
        if not isinstance(denoted, Denoted):
            continue
        under = branch_under(solver, line)
        payload = IdleIgnorePayload(
            line, under if isinstance(under, (DeriveBranch, StoreBranch))
            else None, denoted.branches)
        if payload.under is None:
            out.append(Finding(Kind.IDLE_BRANCH_IGNORE, AtLine(line.line),
                               payload))
            continue
        without = without_named_ignores(runs, solver)
        alone = _cases_under(runs, solver, (*bare, line))
        if not isinstance(without, tuple):
            out.append(no_result(without, RunKind.CASE, None,
                                 AtLine(line.line)))
        elif not isinstance(alone, tuple):
            out.append(no_result(alone, RunKind.CASE, None, AtLine(line.line)))
        elif len(without) == len(alone):
            out.append(Finding(Kind.IDLE_BRANCH_IGNORE, AtLine(line.line),
                               payload))
    return out


# The checks


@quotes("principles.md", "Stored or derived",
        "**Two parameterizations.** Storing a value and deriving that value "
        "produce two different parameterizations.")
@quotes("solver-file.md", "Params",
        "**`@derive` directive.** The line is a branch of a choice point on "
        "the parameter")
@quotes("procedure.md", "Develop",
        "Hold as a branch each built-in derivation that fits a parameter")
def check_two_parameterizations(solver: Solver, runs: Runs) -> list[Finding]:
    """The findings on the `@derive` lines and their named `@ignore` lines:
    a second line of one branch, a line above a parameter no case of the
    solver reads, a branch that fails Fit, a named `@ignore` line that
    excludes no case, a derivation that fits with no line, and an entry of a
    branch's name that witnesses nothing."""
    return list(runs.derive_survey.findings)


@quotes("principles.md", "Stored or derived",
        "**Two parameterizations.** Storing a value and deriving that value "
        "produce two different parameterizations.")
@quotes("solver-file.md", "Program",
        "**`@store` directive.** The relation, or the instance's relation the "
        "line names, has one value on every input, and the line is a branch "
        "of a choice point on it")
@quotes("solver-file.md", "Cases",
        "**Case markers.** Cases do not interleave: each case's Params and "
        "clauses are under its marker.")
def check_stored_or_derived(solver: Solver, runs: Runs) -> list[Finding]:
    """The findings on the `@store` lines and on the relations with one
    value on every input, and the markers under which cases they do not list
    read clauses."""
    return [f for f in runs.store_survey.findings
            if f.kind != Kind.STORE_PARAMS_ASK]


@quotes("principles.md", "Stored or derived",
        "Where a stored value fits, the concept case stores structure over "
        "colors as a parameter.")
def check_color_structure_stored(solver: Solver, runs: Runs
                                 ) -> list[Finding]:
    """A relation between `in` and `out` that the concept case reads and
    that holds one color on every input, with no `@store` line, asks for a
    Params parameter."""
    return [f for f in runs.store_survey.findings
            if f.kind == Kind.STORE_PARAMS_ASK]


@quotes("principles.md", "Models and tasks",
        "For each model, the solver stores an assignment determined by the "
        "evidence.")
@quotes("solver-file.md", "Determination",
        "`Determine` contains the determination as one relation per "
        "determined parameter, with the parameter's name and schema, derived "
        "from `ex_in` and `ex_out`.")
@quotes("solver-file.md", "Determination",
        "The determination relation of a parameter with a case column gives "
        "the rows of every case.")
@quotes("solver-file.md", "Determination",
        "A derived relation has no determination relation.")
@quotes("patterns.md", "`RIGID` — parameter relations coupled as a rigid assembly",
        "exposes them only as D4 placements that transform them together, so "
        "the stored pose is unobservable.")
def check_stored_assignment(solver: Solver, runs: Runs) -> list[Finding]:
    """A determined parameter whose `Determine` relation differs from its
    stored value is a finding; one stored by a RIGID call differs where no
    D4 image of its block's stored assembly gives the determined one. A
    parameter with a case column differs where its rows differ at a case
    the checks read (`checker.runs.Runs.differing_bases`), since each case
    reads its own rows. A
    `Determine` relation that mirrors a relation `Params` derives is a
    finding too."""
    result = runs.determined
    out: list[Finding] = []
    for d in solver.params.derived:
        if d.mirrored:
            out.append(Finding(Kind.DETERMINATION_OF_DERIVED,
                               AtParameter(d.name),
                               DerivedDataPayload(d.name)))
    if isinstance(result, Determined):
        for d in result.diffs:
            bases = runs.differing_bases(d)
            if bases == ():
                continue
            out.append(Finding(Kind.DETERMINATION_DIFF,
                               AtParameter(d.parameter),
                               DeterminationDiffPayload(d, bases)))
        return out
    if isinstance(result, NoTask):
        out.append(NO_TASK)
    elif not isinstance(result, NoDetermine):
        out.append(no_result(result, RunKind.DETERMINATION, None,
                             AtFile(WholeFile.SOLVER)))
    return out

