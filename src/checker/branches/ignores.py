"""The named `@ignore: derive` and `@ignore: store` lines: what they
exclude, and the findings on the lines that exclude no case."""

from dataclasses import replace

from checker.branches.cases import taking
from checker.finding import AtLine, Finding, Kind, RunKind, Where
from checker.judged import no_result
from checker.payloads.branches import ExcludedPayload, IdleIgnorePayload
from checker.runs import Runs
from engine import RelationName, RunFailure
from solver.aggregate import Solver, branch_under, ignore_targets
from solver.annotations import IgnoreForm, IgnoreLine
from solver.cases import cases
from solver.model import Case, DeriveBranch, StoreBranch
from solver.names import Denoted, denote


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
    (`solver.aggregate.ignore_targets`)."""
    return [(t, i.proposer) for i in solver.annotations.ignores
            if i.form is form and i.name is None
            for t in ignore_targets(solver.program, i)]


def excluded_finding(runs: Runs, solver: Solver,
                     branch: DeriveBranch | StoreBranch, at: Where
                     ) -> Finding | None:
    """The finding on a `@derive` or `@store` line whose cases are
    excluded (`exclusion`); None where nothing excludes them."""
    excluded = exclusion(runs, solver, branch)
    return None if excluded is None \
        else Finding(Kind.BRANCH_EXCLUDED, at, excluded)


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
