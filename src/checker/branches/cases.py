"""The runs of cases on the pairs, and the cases that take a `@derive`
or `@store` branch."""

from collections.abc import Sequence
from dataclasses import replace

from checker.judged import Fit, Fits, fit, missed
from checker.runs import Runs
from solver.aggregate import Solver, takes
from solver.model import (
    Branch,
    Case,
    DeriveBranch,
    StoreBranch,
    StoredAtDerive,
)
from solver.names import Denoted
from solver.pair_runs import (
    CaseOnPair,
    PairId,
    PairRuns,
    branch_model,
    examples,
    pair_on,
    task_inputs,
)


def pair_runs(runs: Runs, solver: Solver, cases: Sequence[Case]
              ) -> tuple[PairRuns, ...]:
    """The cases of `cases` on the train and test pairs, as
    `solver.pair_runs.pairs` runs a case of the solver, pair by pair: a case
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
    """The cases of `cases` that take `branch` (`solver.aggregate.takes`)."""
    return [c for c in cases if takes(solver, c, branch)]


def ordered(solver: Solver, cases: Sequence[Case],
            branch: DeriveBranch | StoreBranch) -> list[Case]:
    """The cases of `cases` that take `branch` (`taking`), with the
    branch's model (`branch_models`) first."""
    took = taking(solver, cases, branch)
    return list(dict.fromkeys([*branch_models(solver, took, branch),
                               *took]))


def branch_models(solver: Solver, cases: Sequence[Case],
                  branch: DeriveBranch | StoreBranch) -> list[Case]:
    """The cases of `cases` a branch's witness is judged on: the branch's
    model (`solver.pair_runs.branch_model`); none where no case of `cases`
    takes it."""
    got = branch_model(solver, cases, Denoted((), (branch,)))
    return [] if got is None else [got]


def untaken(runs: Runs, solver: Solver, branch: Branch) -> bool:
    """No case of the solver takes `branch`; False where the run that
    enumerates the solver's cases fails."""
    every = runs.solver_cases
    return isinstance(every, tuple) and not taking(solver, every, branch)


def untaken_lines(runs: Runs, solver: Solver) -> frozenset[int]:
    """The lines of the `@derive` and `@store` lines whose branch no case
    of the solver takes (`untaken`), whose verdicts are not judged."""
    return frozenset(b.line.line for b in solver.branches
                     if isinstance(b, (DeriveBranch, StoreBranch))
                     and b.line is not None and untaken(runs, solver, b))
