"""The checks on `@derive` and `@store` branches and on the determination,
and what the `derive` and `store` surveys share: the runs of cases on the
pairs, the witnesses a survey builds, and the named `@ignore` lines."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from checker.finding import (
    AtEntry,
    AtFile,
    AtLine,
    AtParameter,
    Finding,
    Kind,
    RunKind,
    WholeFile,
    WitnessFileRole,
)
from checker.judged import (
    Fit,
    Fits,
    Swap,
    fit,
    is_concept,
    no_result,
    swaps,
)
from checker.payloads.branches import (
    BranchEntryPayload,
    BranchName,
    DerivedDataPayload,
    DeterminationDiffPayload,
    IdleIgnorePayload,
    NoTaskPayload,
)
from checker.runs import NoTask, Runs
from engine import Grid, RunFailure
from solver.annotations import IgnoreForm
from solver.model import (
    Branch,
    Case,
    DeriveBranch,
    Solver,
    StoreBranch,
    branch_under,
    cases,
    takes,
)
from solver.names import Denoted, denote
from solver.problems import Fault
from solver.solve import (
    Assignment,
    CaseOnPair,
    Determined,
    Grids,
    NoDetermine,
    Outcome,
    PairId,
    PairRuns,
    as_grid,
    assignment,
    candidates,
    examples,
    group_grid,
    outcomes,
    outcomes_on,
)
from solver.vocabulary import COLOR
from solver.witness import (
    Entry,
    GroupGrid,
    Undefined,
    grouped,
)

# Runs of cases on the pairs


def pair_runs(runs: Runs, solver: Solver, cases: Sequence[Case]
              ) -> tuple[PairRuns, ...]:
    """Every case of `cases` on every train and test pair, as
    `solver.solve.pairs` runs a case of the solver; the cases share runs
    (`solver.solve.outcomes`)."""
    task = solver.task
    if task is None or not cases:
        return ()
    out: list[PairRuns] = []
    exs = list(examples(task))
    every = outcomes_on(runs.engine, solver, cases,
                        [(as_grid(ex.input), Assignment(())) for _, ex in exs],
                        runs.limits)
    for (pair, ex), got in zip(exs, every, strict=True):
        accepted = candidates(ex)
        runs_here: list[CaseOnPair] = []
        for c in cases:
            o = got[c]
            runs_here.append(CaseOnPair(c, o, () if not isinstance(o, Grids)
                                        else tuple(k for k, grids in accepted
                                                   if frozenset(o.grids)
                                                   == grids)))
        out.append(PairRuns(pair, tuple(runs_here)))
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
    """The cases that take `branch`: the one that takes it alone at the
    concept case first, then those that take it alone, then the rest."""
    alone = [c for c in cases if c.branches == (branch,)]
    first = [c for c in alone
             if is_concept(solver, counterpart(c, branch))]
    return list(dict.fromkeys([*first, *alone, *cases]))


def without_named_ignores(runs: Runs, solver: Solver
                          ) -> tuple[Case, ...] | RunFailure:
    """The cases the runner would hold with no named `@ignore: derive` or
    `@ignore: store` line standing."""
    a = solver.annotations
    kept = tuple(i for i in a.ignores
                 if i.form is IgnoreForm.LINT or i.name is None)
    if len(kept) == len(a.ignores):
        return cases(solver, runs.engine, runs.limits)
    return cases(replace(solver, annotations=replace(a, ignores=kept)),
                     runs.engine, runs.limits)


# Witnesses


class NoWitness(StrEnum):
    """Why a survey builds no witness of a branch."""

    NOT_ONE_COLOR = "not one color"
    """The parameter's stored value is other than one color."""
    NO_FREE_COLOR = "no free color"
    """No train input has a color neither it nor a parameter holds."""
    ONE_OUTPUT = "one output"
    """On every swap, each case that takes the branch gives its
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
    """A run on a grid a witness is sought on that failed, or reached a
    limit: which grid, as the survey names it, and the failure."""

    grid: str
    failure: RunFailure


def _differ(a: Outcome, b: Outcome) -> bool:
    """Two outcomes differ, one of them defined: the divergence
    (principles.md:123-125)."""
    if isinstance(a, Grids) and isinstance(b, Grids):
        return frozenset(a.grids) != frozenset(b.grids)
    return {type(a), type(b)} == {Grids, Undefined}


def diverges(runs: Runs, solver: Solver, cases: Sequence[Case],
             branch: DeriveBranch | StoreBranch, grid: Grid,
             assign: Assignment
             ) -> tuple[Case, Case] | RunFailure | None:
    """The first case of `cases` that gives on `grid` at `assign` an
    output other than its counterpart's, with that counterpart; the first
    failed run where none does and a run failed; None otherwise."""
    pairs = [(c, counterpart(c, branch)) for c in cases]
    got = outcomes(runs.engine, solver,
                   [x for pair in pairs for x in pair], grid, assign,
                   runs.limits)
    failed: RunFailure | None = None
    for case, other in pairs:
        a, b = got[case], got[other]
        for o in (a, b):
            if not isinstance(o, (Grids, Undefined)):
                failed = failed or o
        if _differ(a, b):
            return case, other
    return failed


def stored_colors(solver: Solver) -> frozenset[int]:
    """Every color a parameter's stored rows hold, in a `Color` column."""
    out: set[int] = set()
    for p in solver.params.parameters:
        if not isinstance(p.stored, tuple):
            continue
        cols = [i for i, c in enumerate(p.columns) if c.type == COLOR]
        out |= {v for r in p.stored for i in cols
                if isinstance(v := r[i], int)}
    return frozenset(out)


type Witness = SwapWitness | NoWitness | FailedOn


def swap_witness(runs: Runs, solver: Solver, cases: Sequence[Case],
                 branch: DeriveBranch | StoreBranch, color: int | None
                 ) -> Witness:
    """The color-swap witness of `branch` (`judged.swaps`): the first
    swapped train input on which a case that takes it diverges from its
    counterpart. `color` is the one color the branch's value holds; None
    where it holds other than one color."""
    task = solver.task
    if color is None or task is None:
        return NoWitness.NOT_ONE_COLOR
    found = swaps([as_grid(e.input) for e in task.train],
                  frozenset({color}), stored_colors(solver))
    if not found:
        return NoWitness.NO_FREE_COLOR
    failed: FailedOn | None = None
    for s in found:
        got = diverges(runs, solver, cases, branch, s.grid, Assignment(()))
        if isinstance(got, tuple):
            return SwapWitness(s, got[0], got[1])
        if got is not None and failed is None:
            failed = FailedOn(f"train {s.index}", got)
    return failed or NoWitness.ONE_OUTPUT


def witness_entry(runs: Runs, solver: Solver, name: str, separates: str,
                  grid: Grid, cases: Sequence[Case]) -> Entry | RunFailure:
    """The witness file's entry a survey builds for a branch: its id the
    branch's name, its input `grid`, and its groups the outputs `cases`
    give there, as `record` writes them (`solver.witness.grouped`). A
    case whose run fails fails the entry."""
    got = outcomes(runs.engine, solver, cases, grid, Assignment(()),
                   runs.limits)
    given: list[tuple[Case, GroupGrid]] = []
    for case in [*(c for c in cases if not c.branches),
                 *(c for c in cases if c.branches)]:
        o = got[case]
        if not isinstance(o, (Grids, Undefined)):
            return o
        given.append((case, group_grid(o)))
    return Entry(name, separates, grid, (), grouped(solver, given))


@dataclass(frozen=True)
class BuiltBy:
    """What a survey built a witness entry from: the solver with the
    branch's line standing, and the cases its groups were built from,
    which `record_lines` counts."""

    solver: Solver
    cases: tuple[Case, ...]


def file_entry(runs: Runs, name: str) -> Entry | None:
    """The witness file's entry of the id `name`, from the file the
    command reads."""
    return next((e for e in runs.entries if e.id == name), None)


def entry_findings(runs: Runs, solver: Solver,
                   branch: DeriveBranch | StoreBranch, ref: BranchName,
                   name: str, cases: Sequence[Case], entry: Entry
                   ) -> list[Finding]:
    """Where the witness file's entry of a branch's name does not witness
    it (principles.md:126): at its assignment, no case that takes the
    branch diverges from its counterpart. A run that fails where none
    diverges is the finding in its place; an `assign` that names nothing
    is the fault `check_faults` reports."""
    assign = assignment(solver, entry)
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
    (solver-file.md:122, :138): no `@derive` or `@store` line stands above
    it, or no case takes that line's branch and every branch its name
    contains. A name that denotes no case is the fault
    `check_faults` reports."""
    solver = runs.solver
    a = solver.annotations
    bare = tuple(i for i in a.ignores
                 if i.form is IgnoreForm.LINT or i.name is None)
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
        without = cases(replace(solver, annotations=replace(a, ignores=bare)),
                       runs.engine, runs.limits)
        alone = cases(replace(solver, annotations=replace(
            a, ignores=(*bare, line))), runs.engine, runs.limits)
        if isinstance(without, tuple) and isinstance(alone, tuple) \
                and len(without) == len(alone):
            out.append(Finding(Kind.IDLE_BRANCH_IGNORE, AtLine(line.line),
                               payload))
    return out


# The checks


def check_two_parameterizations(solver: Solver, runs: Runs) -> list[Finding]:
    """principles.md:249-250 (Two parameterizations): storing a value and
    deriving it are two parameterizations, so each built-in derivation
    that fits a stored parameter is a branch of its own, whose cases are
    the solver's through a `@derive` line or recorded as failing a condition through a bare
    `@ignore: derive` line (solver-file.md:120-122; procedure.md:133-134).
    The findings on the `@derive` lines and their named `@ignore` lines:
    a second line of one branch, a line above a parameter no case of the solver
    reads, a branch that fails Fit, a named `@ignore` line that excludes
    no case, a derivation that fits with no line, and an entry of a
    branch's name that witnesses nothing."""
    return list(runs.derive_survey.findings)


def check_stored_or_derived(solver: Solver, runs: Runs) -> list[Finding]:
    """principles.md:249-250 (Two parameterizations), with the form of
    solver-file.md:137-138: a value the program derives that is the same
    on every input has a stored reading, a branch of its own, whose cases are
    the solver's through a `@store` line or recorded through a bare `@ignore: store` line, and
    a `@store` relation has one value on every input. The findings on the
    `@store` lines and on the relations with one value, and the markers
    under which cases they do not list read clauses (solver-file.md:104,
    whose markers place the stored value per case)."""
    return [f for f in runs.store_survey.findings
            if f.kind != Kind.STORE_PARAMS_ASK]


def check_color_structure_stored(solver: Solver, runs: Runs
                                 ) -> list[Finding]:
    """principles.md:244 (Color): where a stored value fits, the concept
    case stores structure over colors as a parameter. A relation between
    `in` and `out` that the concept case reads and that holds one color
    on every input, with no `@store` line, asks for a Params parameter."""
    return [f for f in runs.store_survey.findings
            if f.kind == Kind.STORE_PARAMS_ASK]


def check_stored_assignment(solver: Solver, runs: Runs) -> list[Finding]:
    """principles.md:54 and :58 (determination): the solver stores an
    assignment determined by the evidence, which the `Determine` comp
    derives from the examples (solver-file.md:157-162). A determined
    parameter whose determination differs from its stored value is a
    finding; one stored by a RIGID call differs where no D4 image of its
    block's stored assembly gives the determined one, since the stored
    pose is unobservable (patterns.md:98). A `Determine` relation
    that mirrors a relation `Params` derives is a finding too: a derived
    relation has no determination relation (solver-file.md:160)."""
    result = runs.determined
    out: list[Finding] = []
    for d in solver.params.derived:
        if d.mirrored:
            out.append(Finding(Kind.DETERMINATION_OF_DERIVED,
                               AtParameter(d.name),
                               DerivedDataPayload(d.name)))
    if isinstance(result, Determined):
        for d in result.diffs:
            out.append(Finding(Kind.DETERMINATION_DIFF,
                               AtParameter(d.parameter),
                               DeterminationDiffPayload(d)))
        return out
    if isinstance(result, NoTask):
        out.append(Finding(Kind.NO_TASK, AtFile(WholeFile.SOLVER),
                           NoTaskPayload()))
    elif not isinstance(result, NoDetermine):
        out.append(no_result(result, RunKind.DETERMINATION, None,
                             AtFile(WholeFile.SOLVER)))
    return out



def write_witnesses(runs: Runs, built: Sequence[Entry | None],
                    every_stem: bool) -> tuple[Fault, ...]:
    """Write the entries a `derive` or `store` run built to the task's
    witness file (`solver.witness.put`); nothing where the command runs
    over every stem."""
    from solver import witness

    entries = [e for e in built if e is not None]
    if every_stem or not entries:
        return ()
    return witness.put(witness.path(runs.solver.task_id),
                       runs.solver.task_id, entries)
