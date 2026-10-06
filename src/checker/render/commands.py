"""The frame lines of the commands: what a command prints around the
renderer's sections (a summary table, a section header, a solver's
time, a witness report's head, a solver's block over every solver)."""

from collections.abc import Sequence
from pathlib import Path

from checker.finding import Finding
from checker.render import (
    Section,
    finding_lines,
    header_line,
    in_line_order,
    noun,
    pass_line,
    render,
)
from checker.render.faults import detail_text
from checker.render.lint import lint_line
from checker.render.locations import LineForm, file_name, solver_name
from checker.render.no_result import failure_text
from checker.render.grids import GridRow, shifted
from controlled_markdown import mctx
from engine import RunFailure
from solver.annotations import verdict_text
from solver.aggregate import Solver
from solver.problems import Fault

# Files and the stamp

NO_WITNESS_FILE = mctx("no witness file at {path}: the first witness that "
                       "`record`, `derive` or `store` writes creates it")
CORPUS_READ_ONLY = mctx("read-only over every solver: a run on this stem "
                        "alone records the witnesses below")
STAMP = mctx("runner and lib: {stamp}")
UNCAUGHT = mctx("{kind}: {error}")


COMPILE_CAUSE = mctx("likely cause:")
TIME_LINE = mctx("time: {parts}")
TIME_PAIRS = mctx("pairs {secs:.1f}s")
TIME_DETERMINATION = mctx("determination {secs:.1f}s")


# A run over several solvers

def verdict_line(stem: str, passes: int, total: int, fails: bool) -> str:
    """One solver's line in a run over several: its pair count, and
    whether it passes."""
    return f"{stem}: {passes}/{total} {'FAIL' if fails else 'PASS'}"


def section_header(header: str) -> list[str]:
    return ["", header_line(header)]


FAILING_PAIRS = mctx("{n} solver(s) with a failing pair")
LINT_FINDINGS = mctx("findings: {count} across {solvers} solver(s)")
LINT_HINTS = mctx("hints: {count} across {solvers} solver(s)")
DETERMINATION_CHECKS = mctx("determination checks: {ok}/{n} ok")
SLOWEST = 15
"""How many solvers the `times` section of a run over several lists."""
TIMES = mctx("times: slowest {n} (wall seconds)").format(n=SLOWEST)
SUMMARY = mctx("summary: {passing}/{total} solvers")


def time_row(total: float, stem: str, pairs: float,
             determination: float | None) -> str:
    part = "" if determination is None \
        else f", determination {determination:.1f}"
    return f"  {total:5.1f}  {stem}  (pairs {pairs:.1f}{part})"


def judgment_first(lines: Sequence[str]) -> list[str]:
    """A section's lines with the blocks that draw no grid first, in
    their order, then those that draw one, in theirs, so that the first
    screen holds the section's findings, count and pass lines. A block is
    a line and the lines below it that are indented further, the blank
    lines between them included; it draws a grid where it holds a
    `GridRow`."""
    blocks: list[list[str]] = []
    head = -1
    pending: list[str] = []
    for line in lines:
        if not line.strip():
            pending.append(line)
            continue
        indent = len(line) - len(line.lstrip(" "))
        if blocks and indent > head:
            blocks[-1] += [*pending, line]
        else:
            blocks.append([*pending, line])
            head = indent
        pending = []
    if pending:
        if blocks:
            blocks[-1] += pending
        else:
            blocks.append(pending)

    def draws(block: list[str]) -> bool:
        return any(isinstance(line, GridRow) for line in block)

    return [line for b in (*(b for b in blocks if not draws(b)),
                           *(b for b in blocks if draws(b)))
            for line in b]


# `witness`, `derive`, `store` and `audit`

WITNESS_LINES = mctx("`@witness` lines:")
NO_WITNESS_LINES = mctx("no witness lines")
GRIDS_RUN = mctx("{n} witness {grids} run")
WITNESS_FILE_OK = mctx("witness file: ok")
AUDIT_SECTION = mctx("{name} ({seconds:.0f}s)")


def audit_section(name: Section, seconds: float) -> str:
    """An audit section's header line, with the seconds the section
    took."""
    return header_line(AUDIT_SECTION.format(name=name.value,
                                            seconds=seconds))

def grids_run(n: int) -> str:
    return GRIDS_RUN.format(n=n, grids=noun(n, "grid"))


# Composed frames


def failed_line(solver: Solver, failure: RunFailure) -> str:
    """The line a compile failure prints once, before anything runs."""
    return f"{solver_name(solver)}: {failure_text(failure)}"


def compile_lines(solver: Solver, failure: RunFailure,
                  collisions: Sequence[Finding]) -> list[str]:
    """A solver whose program the engine rejects: the error, then the
    lint findings that likely cause it."""
    lines = [failed_line(solver, failure)]
    if collisions:
        lines.append(COMPILE_CAUSE)
        lines += [f"  {lint_line(solver, f)}" for f in collisions]
    return lines


def lint_section(solver: Solver, findings: Sequence[Finding]) -> list[str]:
    """The lint section of `run`, closed by a blank line and its pass line
    where the findings pass, and by a blank line otherwise."""
    lines = render(solver, Section.LINT, findings)
    return lines if pass_line(Section.LINT, findings) is not None \
        else [*lines, ""]


def time_line(pairs: float, determination: float | None) -> list[str]:
    """The time `run --time` gives one solver, after a blank line."""
    parts = [TIME_PAIRS.format(secs=pairs)]
    if determination is not None:
        parts.append(TIME_DETERMINATION.format(secs=determination))
    return ["", TIME_LINE.format(parts=", ".join(parts))]


def gathered_lint(shown: Sequence[tuple[Solver, Sequence[Finding]]]
                  ) -> list[str]:
    """The lint findings of several solvers under one header, each
    solver's lines indented, each solver's in line order."""
    return [f"  {ln}" for s, fs in shown for f in in_line_order(fs)
            for ln in finding_lines(s, f, LineForm.FILE)]


def failure_block(stem: str, lines: Sequence[str]) -> list[str]:
    """A solver's failing pairs in the report over several solvers."""
    return ["", f"{stem}:", *(f"  {ln}" for ln in lines)]


def determination_block(stem: str, lines: Sequence[str]) -> list[str]:
    """A solver's determination lines in the report over several
    solvers."""
    return [f"  {file_name(stem)}: {ln}" for ln in lines]


def annotation_lines(solver: Solver) -> list[str]:
    """What each `@witness` line states, one block per line."""
    lines: list[str] = []
    for w in solver.annotations.witnesses:
        lines.append(f"{w.id}: {w.plausibility.value} "
                     f"{verdict_text(w.verdict)}")
        lines += [f"  relaxed: {s}" for s in w.relaxed]
        lines += [f"  reassigned: {p}" for p in w.reassigned]
        if w.approximates:
            lines.append(f"  under @approximated: of {w.approximates}")
    return lines or [NO_WITNESS_LINES]


def witness_head(solver: Solver, grids: int | None, path: Path) -> list[str]:
    """The head of the witness report: the `@witness` lines, then the
    count of witness grids, or the missing file's line."""
    return [WITNESS_LINES, *(f"  {ln}" for ln in annotation_lines(solver)),
            "", NO_WITNESS_FILE.format(path=path) if grids is None
            else grids_run(grids)]


def indented(solver: Solver, section: Section,
             findings: Sequence[Finding]) -> list[str]:
    """A section as the `witness`, `derive` and `store` reports print it:
    each finding's lines indented, and the pass line as it stands."""
    lines = render(solver, section, findings)
    ok = pass_line(section, findings)
    body = lines[:-1] if ok is not None else lines
    return [shifted(ln, "  ") for ln in body] + ([ok] if ok is not None
                                                 else [])


def shape_problem_line(path: Path, problem: Fault) -> str:
    """A witness file's shape problem, checked with no solver."""
    return f"{path}: {problem.kind.value}: {detail_text(problem.detail)}"


def stem_head(stem: str) -> str:
    """The head of one solver's block in `derive` or `store` over every
    solver."""
    return f"{stem}:"


def entry_line(entry_id: str, what: object) -> str:
    """A witness entry's id and what running it again gave."""
    return f"{entry_id}: {what}"
