"""The `run` and `lint` commands: the pairs, the lint and the
determination check of one solver, or the report over several."""

import argparse
import json
from enum import Enum
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arc.materialize import DESCRIPTION_KEYS
from arc.task import (
    LIST_SECTION,
    PAIR_SECTIONS,
    Example,
    PairFormError,
    PairSection,
    Probe,
    pair_name,
    read_pair,
    spelled,
)
from checker import Finding, Kind, Runs, fault_findings, check_lint
from checker.branches.checks import check_stored_assignment
from checker.finding import LINT_SHAPES, is_hint
from checker.render import Section, commands, exit_code, pass_line, passes, run_pairs
from checker.render.determination import determination_lines
from checker.sweep import GivingValues, values_giving
from cli import text
from cli.common import (
    LIMITS,
    all_stems,
    command_solver,
    compile_failure,
    compiles,
    open_value_off,
    engine,
    load_solver,
    missing,
    no_task,
)
from engine.program import as_grid
from solver.category import Category
from solver.model import Case
from solver.aggregate import Solver, has_determine
from solver.problems import Fault
from solver.outcome import Assignment, Outcome
from solver.solve import outcomes
from solver.pair_runs import CaseOnPair, TaskSection, candidates, examples, matching
from souffle import SouffleEngine

COLLISIONS = frozenset({Category.RESERVED_NAME, Category.SHADOWED_TYPE,
                        Category.LIB_NAME})
"""The lint categories a compile failure prints beside Souffle's error."""


def dispatch(args: argparse.Namespace) -> int:
    if args.pairs:
        if len(args.stems) != 1:
            print(text.PAIRS_ONE_STEM, file=sys.stderr)
            return 2
        if args.as_json:
            print(text.PAIRS_NO_JSON, file=sys.stderr)
            return 2
        return cmd_pairs(args.stems[0], args.pairs)
    if len(args.stems) == 1 and not args.as_json:
        return cmd_one(args.stems[0], args.hints, args.timed)
    return cmd_all(args.hints, args.timed, args.stems or None, args.as_json)


# The lint


def lint_findings(solver: Solver, runs: Runs, hints: bool) -> list[Finding]:
    """The lint section's findings: the faults, then the lint's;
    the hints only with `hints`: the lint that procedure.md, under
    "Develop", asks the solver to pass."""
    found = fault_findings(solver, runs) + check_lint(solver, runs)
    return found if hints else [f for f in found if not is_hint(f)]


# One solver


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
    procedure.md asks for under "Develop", "Run the solver"."""
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


# Several solvers


class ReportKind(Enum):
    """What a section of the report over several solvers holds, as the
    JSON report names it."""

    FAILURES = "failures"
    FINDINGS = "findings"
    HINTS = "hints"
    TIMES = "times"


@dataclass(frozen=True)
class ReportSection:
    """One section of the report over several solvers: its kind, its
    header, and the lines of its entries."""

    kind: ReportKind
    header: str
    lines: tuple[str, ...]

    def printed(self) -> list[str]:
        return [*commands.section_header(self.header), *self.lines]


def lint_sections(found: Sequence[tuple[Solver, Sequence[Finding]]]
                  ) -> list[ReportSection]:
    """The findings and hints sections over several solvers: each
    solver's lines, in the order `found` gives the solvers, gathered under
    one header per kind; a kind no solver has gets no section."""
    out: list[ReportSection] = []
    for kind, header, keep in (
            (ReportKind.FINDINGS, commands.LINT_FINDINGS,
             lambda f: not is_hint(f)),
            (ReportKind.HINTS, commands.LINT_HINTS, is_hint)):
        shown = [(s, [f for f in fs if keep(f)]) for s, fs in found]
        shown = [(s, fs) for s, fs in shown if fs]
        if shown:
            out.append(ReportSection(kind, header.format(
                count=sum(len(fs) for _s, fs in shown), solvers=len(shown)),
                tuple(commands.gathered_lint(shown))))
    return out


def _report(checked: Sequence[Checked], timed: bool) -> list[ReportSection]:
    out: list[ReportSection] = []
    failed = [c for c in checked if not c.pairs_pass]
    if failed:
        lines: list[str] = []
        for c in failed:
            lines += commands.failure_block(c.stem, c.failure_lines)
        out.append(ReportSection(ReportKind.FAILURES, commands.FAILING_PAIRS.format(
            n=len(failed)), tuple(lines)))
    out += lint_sections([(c.solver, c.lint)
                          for c in sorted(checked, key=lambda c: c.stem)])
    determined = [c for c in checked if c.has_determine]
    if determined:
        problems = [c for c in determined if c.determination_fails]
        out.append(ReportSection(
            ReportKind.FAILURES, commands.DETERMINATION_CHECKS.format(
                ok=len(determined) - len(problems), n=len(determined)),
            tuple(ln for c in sorted(problems, key=lambda c: c.stem)
                  for ln in commands.determination_block(
                      c.stem, c.determination_lines))))
    if timed:
        ranked = sorted(checked, key=lambda c: -c.total_secs)
        out.append(ReportSection(ReportKind.TIMES, commands.TIMES, tuple(
            commands.time_row(c.total_secs, c.stem, c.pair_secs,
                              c.determined_secs)
            for c in ranked[:commands.SLOWEST])))
    return out


def any_missing(stems: list[str]) -> bool:
    """Whether no solver file stands at one of `stems`, the first such in
    sorted order given its line on stderr (`missing`)."""
    return any(missing(s) for s in sorted(set(stems)))


def cmd_all(hints: bool = True, timed: bool = False,
            stems: list[str] | None = None, as_json: bool = False) -> int:
    """The report over `stems`, or over every solver: the verdict lines,
    then each section, then the summary; with `as_json`, one JSON
    object."""
    if stems is not None and any_missing(stems):
        return 2
    eng = engine()
    solvers = [load_solver(s, eng)
               for s in (stems if stems is not None else all_stems())]
    if [s for s in solvers if no_task(s)]:
        return 2
    checked = [check_one(eng, s, hints) for s in solvers]
    sections = _report(checked, timed)
    if as_json:
        print(json.dumps(_json(checked, sections), ensure_ascii=False))
    else:
        for c in checked:
            print(commands.verdict_line(c.stem, c.passes, c.total, c.fails))
        for s in sections:
            print("\n".join(s.printed()))
        print()
        print(commands.SUMMARY.format(passing=sum(not c.fails for c in checked),
                                  total=len(checked)))
    return max((c.exit_code for c in checked), default=0)


def _json(checked: Sequence[Checked], sections: Sequence[ReportSection]
          ) -> dict[str, Any]:
    return {
        "verdicts": [{"stem": c.stem, "passes": c.passes, "total": c.total,
                      "pairs_pass": c.pairs_pass} for c in checked],
        "determination_checks": [{"stem": c.stem,
                                  "problem": c.determination_fails}
                                 for c in checked if c.has_determine],
        "sections": [{"kind": s.kind.value, "header": s.header,
                      "lines": list(s.lines)} for s in sections],
    }


# `lint`


def cmd_lint(stems: list[str] | None, hints: bool = True) -> int:
    """Lint only, over `stems`, or over every solver: no pair runs and no
    determination check. Each solver's lines stand under one header per
    kind, then the pass line."""
    if stems is not None and any_missing(stems):
        return 2
    eng = engine()
    found: list[tuple[Solver, list[Finding]]] = []
    for stem in stems if stems is not None else all_stems():
        solver = load_solver(stem, eng)
        found.append((solver, lint_findings(
            solver, Runs(eng, solver, LIMITS), hints)))
    sections = [ln for s in lint_sections(found) for ln in s.printed()]
    if sections:
        print("\n".join(sections))
    findings = [f for _s, fs in found for f in fs]
    ok = pass_line(Section.LINT, findings)
    if ok is not None:
        print(ok)
    return exit_code(findings)


# `run --pairs`


class PairsFault(Enum):
    """How a pairs file is off its form, or that it holds no pair."""

    NOT_JSON = "not json"
    BAD_KEY = "bad key"
    NO_FORM = "no form"
    NO_LIST = "no list"
    NONE = "none"
    LIST_OUTPUT = "list output"


class PairsFileError(Exception):
    """A pairs file off its form: the fault and its parts, which
    `_pairs_text` writes."""

    def __init__(self, fault: PairsFault, **parts: object) -> None:
        super().__init__(fault.value)
        self.fault = fault
        self.parts = parts


PAIRS_TEXT = {
    PairsFault.NOT_JSON: text.PAIRS_NOT_JSON,
    PairsFault.BAD_KEY: text.PAIRS_BAD_KEY,
    PairsFault.NO_FORM: text.PAIRS_NO_FORM,
    PairsFault.NO_LIST: text.PAIRS_NO_LIST,
    PairsFault.NONE: text.PAIRS_NONE,
    PairsFault.LIST_OUTPUT: text.PAIRS_LIST_OUTPUT,
}
"""The sentence of each pairs-file fault, from its parts."""


def _pairs_text(e: PairsFileError) -> str:
    return PAIRS_TEXT[e.fault].format(**e.parts)


def _pairs_file(path: Path) -> list[tuple[PairSection, list[Example | Probe]]]:
    """The pairs of a pairs file, per section, each read as a task file's
    pair is (`arc.task.read_pair`): a bare list of pairs is the one
    section `arc.task.LIST_SECTION`, and an object holds the sections a
    task file holds, beside which it may hold the keys that describe a
    task, unread. A pair of the bare list that holds an output is the fault
    `PairsFault.LIST_OUTPUT`: an output is judged against a train or a test
    pair's candidates (`solver.pair_runs.matching`)."""
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise PairsFileError(PairsFault.NOT_JSON, error=e) from None
    if isinstance(data, list):
        found: list[tuple[PairSection, object]] = [(LIST_SECTION, data)]
    elif isinstance(data, dict):
        for key in data:
            if key not in PAIR_SECTIONS and key not in DESCRIPTION_KEYS:
                raise PairsFileError(PairsFault.BAD_KEY, key=key,
                                     sections=spelled(PAIR_SECTIONS))
        found = [(k, data[k]) for k in PAIR_SECTIONS if k in data]
    else:
        raise PairsFileError(PairsFault.NO_FORM,
                             sections=spelled(PAIR_SECTIONS))
    out: list[tuple[PairSection, list[Example | Probe]]] = []
    for section, pairs in found:
        if not isinstance(pairs, list):
            raise PairsFileError(PairsFault.NO_LIST, section=section)
        read = [read_pair(section, i, e) for i, e in enumerate(pairs)]
        if section == LIST_SECTION and any(isinstance(e, Example)
                                           for e in read):
            raise PairsFileError(PairsFault.LIST_OUTPUT,
                                 sections=spelled(PAIR_SECTIONS))
        out.append((section, read))
    if not any(pairs for _, pairs in out):
        raise PairsFileError(PairsFault.NONE)
    return out


def cmd_pairs(arg: str, path: str) -> int:
    """One solver against the pairs of a JSON file in place of the task's.
    A pair without an output prints what each case gives on its input."""
    if missing(arg):
        return 2
    p = Path(path)
    if not p.exists():
        print(text.NO_PAIRS_FILE.format(path=p), file=sys.stderr)
        return 2
    try:
        sections = _pairs_file(p)
    except PairsFileError as e:
        print(f"{p}: {_pairs_text(e)}", file=sys.stderr)
        return 2
    except PairFormError as e:
        print(f"{p}: {e}", file=sys.stderr)
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    if not compiles(eng, solver):
        return 1
    runs = Runs(eng, solver, LIMITS)
    solver_cases = runs.cases
    if not isinstance(solver_cases, tuple):
        print("\n".join(run_pairs.enumeration_failed_lines(
            [pair_name(kind, idx) for kind, pairs in sections
             for idx in range(len(pairs))], solver_cases)))
        return 1 if any(isinstance(e, Example)
                        for _kind, pairs in sections for e in pairs) else 0
    failed = False
    for kind, pairs in sections:
        for idx, e in enumerate(pairs):
            name = pair_name(kind, idx)
            got = outcomes(eng, solver, solver_cases, as_grid(e.input),
                           Assignment(()), LIMITS)
            if isinstance(e, Probe):
                print("\n".join(run_pairs.probe_lines(
                    solver, name, [(c, got[c]) for c in solver_cases])))
                continue
            cases = tuple(_on_pair(c, got[c], TaskSection(kind), e)
                          for c in solver_cases)
            if not run_pairs.passed(cases):
                failed = True
            print("\n".join(run_pairs.pair_lines(solver, name, cases, e)))
    return 1 if failed else 0


def _on_pair(case: Case, o: Outcome, section: TaskSection, ex: Example
             ) -> CaseOnPair:
    """What `case` gives on a pair of `section`, and the candidates its
    grids match, as `solver.pair_runs.pairs` judges a case of the
    solver."""
    return CaseOnPair(case, o, matching(candidates(section, ex), o))
