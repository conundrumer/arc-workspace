"""The check of one solver: its pairs, its lint and its determination
check, and the `run` command on one solver."""

import time
from dataclasses import dataclass

from arc.task import Example
from checker import Finding, Kind, Runs, fault_findings, check_lint
from checker.branches.checks import check_stored_assignment
from checker.finding import LINT_SHAPES, is_hint
from checker.render import commands, exit_code, passes, run_pairs
from checker.render.determination import determination_lines
from checker.sweep import GivingValues, values_giving
from cli import text
from cli.common import (
    LIMITS,
    command_solver,
    compile_failure,
    open_value_off,
    engine,
)
from solver.category import Category
from solver.model import Case
from solver.aggregate import Solver, has_determine
from solver.problems import Fault
from solver.pair_runs import CaseOnPair, examples
from souffle import SouffleEngine


COLLISIONS = frozenset({Category.RESERVED_NAME, Category.SHADOWED_TYPE,
                        Category.LIB_NAME})
"""The lint categories a compile failure prints beside Souffle's error."""


def lint_findings(solver: Solver, runs: Runs, hints: bool) -> list[Finding]:
    """The lint section's findings: the faults, then the lint's;
    the hints only with `hints`: the lint that
    docs/handbook/procedure.md#develop, asks the solver to pass."""
    found = fault_findings(solver, runs) + check_lint(solver, runs)
    return found if hints else [f for f in found if not is_hint(f)]


@dataclass(frozen=True)
class Checked:
    """One solver's run: its pairs with their pass verdicts, its findings,
    and the seconds the pairs and the determination took."""

    stem: str
    passes: int
    total: int
    pairs_pass: bool
    pair_lines: tuple[str, ...]
    failure_lines: tuple[str, ...]
    lint: tuple[Finding, ...]
    determination: tuple[Finding, ...]
    determination_lines: tuple[str, ...]
    has_determine: bool
    pair_secs: float
    determine_secs: float
    solver: Solver

    @property
    def determined_secs(self) -> float | None:
        """The seconds the determination took; None where the solver has
        no Determine comp."""
        return self.determine_secs if self.has_determine else None

    @property
    def total_secs(self) -> float:
        """The seconds the pairs and the determination took."""
        return self.pair_secs + (self.determined_secs or 0.0)

    @property
    def determination_fails(self) -> bool:
        """A finding of the determination fails
        (`checker.render.passes`)."""
        return not passes(self.determination)

    @property
    def fails(self) -> bool:
        """The pairs or the determination fail."""
        return not self.pairs_pass or self.determination_fails

    @property
    def exit_code(self) -> int:
        """The solver's exit code: 1 where its pairs or its determination
        fail, else the exit code its lint gives
        (`checker.render.exit_code`)."""
        return 1 if self.fails else exit_code(self.lint)


def _pairs(solver: Solver, runs: Runs
           ) -> tuple[int, int, list[str], list[str]]:
    """How many pairs pass, of how many, the pair lines, and the lines of
    the failing pairs alone, as a report over several solvers gives
    them."""
    task = solver.given_task
    exs = list(examples(task))
    got = runs.pairs
    if not isinstance(got, tuple):
        names = [p.text for p, _ex in exs]
        return 0, len(exs), run_pairs.enumeration_failed_lines(names, got), \
            run_pairs.shared_failure_lines(names, got)
    lines: list[str] = []
    failing: list[tuple[str, tuple[CaseOnPair, ...], Example,
                        tuple[GivingValues, ...]]] = []
    shown: set[Case] = set()
    giving = values_giving(solver, runs)
    ok = 0
    for pr, (_pid, ex) in zip(got, exs, strict=True):
        passed = run_pairs.passed(pr.cases)
        ok += passed
        here = tuple(g for g in giving if g.pair == pr.pair)
        if not passed:
            failing.append((pr.pair.text, pr.cases, ex, here))
        lines += run_pairs.pair_lines(solver, pr.pair.text, pr.cases, ex,
                                     shown, here)
    return ok, len(exs), lines, run_pairs.stem_failure_lines(solver, failing)


def check_one(eng: SouffleEngine, solver: Solver, hints: bool) -> Checked:
    """The pairs, the lint and the determination of one solver: the run
    docs/handbook/procedure.md#develop asks for, "Run the solver"."""
    runs = Runs(eng, solver, LIMITS)
    off = open_value_off(eng, solver)
    if off:
        return Checked(solver.stem, 0, len(list(examples(solver.given_task))),
                       False, (text.OPEN_VALUE_UNRUN,), (), tuple(off), (),
                       (), has_determine(solver), 0.0, 0.0, solver)
    t0 = time.perf_counter()
    ok, total, lines, failing = _pairs(solver, runs)
    pair_secs = time.perf_counter() - t0
    lint = lint_findings(solver, runs, hints)
    t0 = time.perf_counter()
    determination = check_stored_assignment(solver, runs)
    shown = determination_lines(solver, runs.determined, determination)
    determine_secs = time.perf_counter() - t0
    return Checked(solver.stem, ok, total, bool(total) and ok == total,
                   tuple(lines), tuple(failing), tuple(lint),
                   tuple(determination),
                   tuple(shown), has_determine(solver), pair_secs,
                   determine_secs, solver)


def _compile_lines(eng: SouffleEngine, solver: Solver, hints: bool
                   ) -> list[str] | None:
    """The lines of a solver whose program the engine rejects: the error,
    the lint findings that likely cause it, and the lint section; None
    where it compiles."""
    failure = compile_failure(eng, solver)
    if failure is None:
        return None
    runs = Runs(eng, solver, LIMITS)
    lint = lint_findings(solver, runs, hints)
    if isinstance(failure, Fault):
        return commands.lint_section(
            solver, [f for f in lint if f.kind == Kind(failure.kind)])
    collisions = [f for f in lint if f.kind == Kind.LINT
                  and isinstance(f.payload, LINT_SHAPES)
                  and f.payload.category in COLLISIONS]
    return commands.compile_lines(solver, failure, collisions) \
        + commands.lint_section(solver, lint)


def cmd_one(arg: str, hints: bool = True, timed: bool = False) -> int:
    """One solver: its pairs, its lint and its determination check."""
    eng = engine()
    solver = command_solver(arg, eng)
    if solver is None:
        return 2
    failed = _compile_lines(eng, solver, hints)
    if failed is not None:
        print("\n".join(failed))
        return 1
    c = check_one(eng, solver, hints)
    for line in [*c.pair_lines, *commands.lint_section(solver, c.lint),
                 *c.determination_lines]:
        print(line)
    if timed:
        print("\n".join(commands.time_line(
            c.pair_secs, c.determined_secs)))
    return c.exit_code
