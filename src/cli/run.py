"""The `run` and `lint` commands: the pairs, the lint and the
determination check of one solver, or the report over several."""

import argparse
import json
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
from checker import Finding, Kind, Runs, check_lint, check_faults
from checker.branches import check_stored_assignment
from checker.finding import LINT_SHAPES
from checker.render import Section, commands, pass_line, passes
from checker.render.branches import determination_lines
from cli import text
from cli.common import (
    LIMITS,
    all_stems,
    compile_failure,
    failed_lines,
    engine,
    load_solver,
    missing,
    no_task,
    stem_of,
)
from solver.category import Category
from solver.model import Case, Solver, has_determine
from solver.problems import Fault, ProblemKind
from solver.solve import (
    Assignment,
    CaseOnPair,
    Grids,
    Outcome,
    as_grid,
    candidates,
    examples,
    outcomes,
)
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
    the hints only with `hints`."""
    found = check_faults(solver, runs) + check_lint(solver, runs)
    return found if hints else [f for f in found if f.kind != Kind.HINT]


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
    def fails(self) -> bool:
        return not self.pairs_pass or not passes(self.determination)


def _pairs(solver: Solver, runs: Runs
           ) -> tuple[int, int, list[str], list[str]]:
    """How many pairs pass, of how many, the pair lines, and the lines of
    the failing pairs alone, as a report over several solvers gives
    them."""
    task = solver.task
    if task is None:
        return 0, 0, [], []
    exs = list(examples(task))
    got = runs.pairs
    if not isinstance(got, tuple):
        names = [pair_name(p.section, p.index) for p, _ex in exs]
        return 0, len(exs), commands.enumeration_failed_lines(names, got), \
            commands.shared_failure_lines(names, got)
    lines: list[str] = []
    failing: list[tuple[str, tuple[CaseOnPair, ...], Example]] = []
    ok = 0
    for pr, (_pid, ex) in zip(got, exs, strict=True):
        ok += commands.passed(pr.cases)
        if not commands.passed(pr.cases):
            failing.append((commands.name_of(pr), pr.cases, ex))
        lines += commands.pair_lines(solver, commands.name_of(pr), pr.cases, ex)
    return ok, len(exs), lines, commands.stem_failure_lines(solver, failing)


def check_one(eng: SouffleEngine, solver: Solver, hints: bool) -> Checked:
    """The pairs, the lint and the determination of one solver."""
    runs = Runs(eng, solver, LIMITS)
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
            solver, [f for f in lint if f.kind == Kind(ProblemKind.PARSE_FAILURE)])
    collisions = [f for f in lint if f.kind == Kind.LINT
                  and isinstance(f.payload, LINT_SHAPES)
                  and f.payload.category in COLLISIONS]
    return commands.compile_lines(solver, failure, collisions) \
        + commands.lint_section(solver, lint)


def cmd_one(arg: str, hints: bool = True, timed: bool = False) -> int:
    """One solver: its pairs, its lint and its determination check."""
    if missing(arg):
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    if no_task(solver):
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
            c.pair_secs, c.determine_secs if c.has_determine else None)))
    return 1 if c.fails or not passes(c.lint) else 0


# Several solvers


@dataclass(frozen=True)
class ReportSection:
    """One section of the report over several solvers: its kind, its
    header, and the lines of its entries."""

    kind: str
    header: str
    lines: tuple[str, ...]

    def printed(self) -> list[str]:
        return [*commands.section_header(self.header), *self.lines]


def _lint_sections(checked: Sequence[Checked]) -> list[ReportSection]:
    """The findings and hints sections over several solvers: each
    solver's lines, gathered under one header per kind."""
    out: list[ReportSection] = []
    for kind, header, keep in (
            ("findings", commands.LINT_FINDINGS, lambda f: f.kind != Kind.HINT),
            ("hints", commands.LINT_HINTS, lambda f: f.kind == Kind.HINT)):
        lines: list[str] = []
        solvers = 0
        count = 0
        for c in sorted(checked, key=lambda c: c.stem):
            shown = [f for f in c.lint if keep(f)]
            if not shown:
                continue
            solvers += 1
            count += len(shown)
            lines += commands.gathered_lint([(c.solver, shown)])
        if solvers:
            out.append(ReportSection(kind, header.format(
                count=count, solvers=solvers), tuple(lines)))
    return out


def _report(checked: Sequence[Checked], timed: bool) -> list[ReportSection]:
    out: list[ReportSection] = []
    failed = [c for c in checked if not c.pairs_pass]
    if failed:
        lines: list[str] = []
        for c in failed:
            lines += commands.failure_block(c.stem, c.failure_lines)
        out.append(ReportSection("failures", commands.FAILING_PAIRS.format(
            n=len(failed)), tuple(lines)))
    out += _lint_sections(checked)
    determined = [c for c in checked if c.has_determine]
    if determined:
        problems = [c for c in determined if not passes(c.determination)]
        out.append(ReportSection(
            "failures", commands.DETERMINATION_CHECKS.format(
                ok=len(determined) - len(problems), n=len(determined)),
            tuple(ln for c in sorted(problems, key=lambda c: c.stem)
                  for ln in commands.determination_block(
                      c.stem, c.determination_lines))))
    if timed:
        ranked = sorted(checked, key=lambda c: -(c.pair_secs + (
            c.determine_secs if c.has_determine else 0.0)))
        out.append(ReportSection("times", commands.TIMES, tuple(
            commands.time_row(c.pair_secs + (c.determine_secs if c.has_determine
                                         else 0.0),
                          c.stem, c.pair_secs,
                          c.determine_secs if c.has_determine else None)
            for c in ranked[:15])))
    return out


def cmd_all(hints: bool = True, timed: bool = False,
            stems: list[str] | None = None, as_json: bool = False) -> int:
    """The report over `stems`, or over every solver: the verdict lines,
    then each section, then the summary; with `as_json`, one JSON
    object."""
    if stems is not None and any(missing(s) for s in sorted(set(stems))):
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
    return 1 if any(c.fails for c in checked) else 0


def _json(checked: Sequence[Checked], sections: Sequence[ReportSection]
          ) -> dict[str, Any]:
    return {
        "verdicts": [{"stem": c.stem, "passes": c.passes, "total": c.total,
                      "pairs_pass": c.pairs_pass} for c in checked],
        "determination_checks": [{"stem": c.stem,
                                  "problem": not passes(c.determination)}
                                 for c in checked if c.has_determine],
        "sections": [{"kind": s.kind, "header": s.header,
                      "lines": list(s.lines)} for s in sections],
    }


# `lint`


def cmd_lint(arg: str | None, hints: bool = True) -> int:
    """Lint only: no pair runs and no determination check. Each solver's
    lines stand under one header per kind, then the pass line."""
    if arg is not None and missing(arg):
        return 2
    eng = engine()
    found: list[tuple[Solver, list[Finding]]] = []
    for stem in [stem_of(arg)] if arg is not None else all_stems():
        solver = load_solver(stem, eng)
        found.append((solver, lint_findings(
            solver, Runs(eng, solver, LIMITS), hints)))
    sections: list[str] = []
    for header, keep in ((commands.LINT_FINDINGS, lambda f: f.kind != Kind.HINT),
                         (commands.LINT_HINTS, lambda f: f.kind == Kind.HINT)):
        shown = [(s, [f for f in fs if keep(f)]) for s, fs in found]
        shown = [(s, fs) for s, fs in shown if fs]
        if not shown:
            continue
        sections += commands.section_header(header.format(
            count=sum(len(fs) for _s, fs in shown), solvers=len(shown)))
        sections += commands.gathered_lint(shown)
    if sections:
        print("\n".join(sections))
    ok = pass_line(Section.LINT, [f for _s, fs in found for f in fs])
    if ok is None:
        return 1
    print(ok)
    return 0


# `run --pairs`


class PairsFileError(Exception):
    """A pairs file off its form, or one that holds no pair."""


def _pairs_file(path: Path) -> list[tuple[PairSection, list[Example | Probe]]]:
    """The pairs of a pairs file, per section, each read as a task file's
    pair is (`arc.task.read_pair`): a bare list of pairs is the one
    section `arc.task.LIST_SECTION`, and an object holds the sections a
    task file holds, beside which it may hold the keys that describe a
    task, unread."""
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise PairsFileError(text.PAIRS_NOT_JSON.format(
            error=e)) from None
    if isinstance(data, list):
        found: list[tuple[PairSection, object]] = [(LIST_SECTION, data)]
    elif isinstance(data, dict):
        for key in data:
            if key not in PAIR_SECTIONS and key not in DESCRIPTION_KEYS:
                raise PairsFileError(text.PAIRS_BAD_KEY.format(
                        key=key, sections=spelled(PAIR_SECTIONS)))
        found = [(k, data[k]) for k in PAIR_SECTIONS if k in data]
    else:
        raise PairsFileError(text.PAIRS_NO_FORM.format(sections=spelled(PAIR_SECTIONS)))
    out: list[tuple[PairSection, list[Example | Probe]]] = []
    for section, pairs in found:
        if not isinstance(pairs, list):
            raise PairsFileError(text.PAIRS_NO_LIST
                                 .format(section=section))
        out.append((section, [read_pair(section, i, e)
                              for i, e in enumerate(pairs)]))
    if not any(pairs for _, pairs in out):
        raise PairsFileError(text.PAIRS_NONE)
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
    except (PairsFileError, PairFormError) as e:
        print(f"{p}: {e}", file=sys.stderr)
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    failure = compile_failure(eng, solver)
    if failure is not None:
        print("\n".join(failed_lines(solver, failure)))
        return 1
    runs = Runs(eng, solver, LIMITS)
    solver_cases = runs.cases
    failed = False
    for kind, pairs in sections:
        for idx, e in enumerate(pairs):
            name = pair_name(kind, idx)
            if not isinstance(solver_cases, tuple):
                failed = failed or isinstance(e, Example)
                print("\n".join(commands.enumeration_failed_lines([name], solver_cases)))
                continue
            got = outcomes(eng, solver, solver_cases, as_grid(e.input),
                           Assignment(()), LIMITS)
            if isinstance(e, Probe):
                print("\n".join(commands.probe_lines(
                    solver, name, [(c, got[c]) for c in solver_cases])))
                continue
            cases = tuple(_on_pair(c, got[c], e) for c in solver_cases)
            if not commands.passed(cases):
                failed = True
            print("\n".join(commands.pair_lines(solver, name, cases, e)))
    return 1 if failed else 0


def _on_pair(case: Case, o: Outcome, ex: Example) -> CaseOnPair:
    """What `case` gives on a pair, and the candidates its grids match,
    as `solver.solve.pairs` judges a case of the solver."""
    if not isinstance(o, Grids):
        return CaseOnPair(case, o, ())
    return CaseOnPair(case, o, tuple(k for k, grids in candidates(ex)
                                     if frozenset(o.grids) == grids))
