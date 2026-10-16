"""The report over several solvers: the `run` command on more than one
solver, or on every solver, and its lint sections, which the `lint`
command prints too."""

import json
from enum import Enum
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from checker.lint_cache import LintResult, lint_result
from checker.render import commands
from cli.common import (
    all_stems,
    engine,
    load_solver,
    missing,
    no_task,
)
from cli.check import Checked, check_one


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


def lint_sections(found: Sequence[LintResult]) -> list[ReportSection]:
    """The findings and hints sections over several solvers: each
    solver's lines, in the order `found` gives the solvers, gathered under
    one header per kind; a kind no solver has gets no section."""
    out: list[ReportSection] = []
    for kind, header, hints in (
            (ReportKind.FINDINGS, commands.LINT_FINDINGS, False),
            (ReportKind.HINTS, commands.LINT_HINTS, True)):
        shown = [r for r in found if r.lines(hints)]
        if shown:
            out.append(ReportSection(kind, header.format(
                count=sum(r.count(hints) for r in shown), solvers=len(shown)),
                tuple(ln for r in shown for ln in r.lines(hints))))
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
    out += lint_sections([lint_result(c.solver, c.lint)
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
