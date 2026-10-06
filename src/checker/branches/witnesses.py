"""The witnesses of a `@derive` or `@store` branch a survey builds,
the entries of the witness file it builds from them, and the findings on
an entry of a branch's name."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from checker.branches.cases import branch_models, counterpart, ordered, pair_runs
from checker.finding import AtEntry, Finding, Kind, RunKind
from checker.judged import Fits, Swap, differ, fit, no_result, swaps
from checker.payloads.branches import BranchEntryPayload, BranchName
from checker.runs import Runs
from engine import Grid, RunFailure
from solver.aggregate import Solver
from solver.model import Case, DeriveBranch, StoreBranch
from solver.names import denoted_cases
from solver.outcome import Assignment, Grids, Outcome, group_grid, is_result
from solver.problems import Fault, NameFault, WitnessFileRole
from solver.solve import assignment, entry_assignments
from solver.witness import (
    Entry,
    GroupGrid,
    Groups,
    Outcomes,
    grouped,
)

if TYPE_CHECKING:
    from checker.store.witness import Change


class NoWitness(StrEnum):
    """Why a survey builds no witness of a branch."""

    NO_FIT = "no fit"
    """No case that takes the branch fits the pairs with its counterpart
    (`witness_targets`), so the survey runs on no input."""
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
    (`shows_apart`). Where it looks with no case, `swap` is
    `NoWitness.NO_FIT` and `pair` None."""

    swap: NoWitness | FailedOn
    pair: tuple[Case, Case] | None


type Witness = SwapWitness | RecordedWitness | Unwitnessed


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
    than one color. `NoWitness.NO_FIT` where the survey looks with no
    case."""
    task = solver.given_task
    if color is None:
        return NoWitness.NOT_ONE_COLOR
    found = swaps(runs.engine, solver, task, cases, frozenset({color}))
    if not found:
        return NoWitness.NO_FREE_COLOR
    models = witness_targets(runs, solver, cases, branch)
    if not models:
        return NoWitness.NO_FIT
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
    saying why no color swap serves. `Unwitnessed` where none does, and
    with `NoWitness.NO_FIT` where it looks with no case; an entry whose
    `assign` names nothing is the fault `fault_findings` reports, and is
    passed over."""
    models = witness_targets(runs, solver, cases, branch)
    if not models:
        return Unwitnessed(NoWitness.NO_FIT, None)
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
