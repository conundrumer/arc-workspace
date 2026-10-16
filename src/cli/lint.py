"""The `lint` command: the lint of one solver or of several, each
solver's result kept (`checker.lint_cache`)."""

from checker import Runs
from checker.lint_cache import LintResult, kept_lint, lint_result
from checker.render import Section, exit_code, pass_line
from cli.common import LIMITS, all_stems, engine, load_solver, solver_path, stem_of
from cli.check import lint_findings
from cli.report import any_missing, lint_sections
from solver.load import task_id_of


def cmd_lint(stems: list[str] | None, hints: bool = True) -> int:
    """Lint only, over `stems`, or over every solver: no pair runs and no
    determination check. Each solver's lines stand under one header per
    kind, then the pass line."""
    if stems is not None and any_missing(stems):
        return 2
    eng = engine()

    def linted(stem: str) -> LintResult:
        def make() -> LintResult:
            solver = load_solver(stem, eng)
            return lint_result(solver, lint_findings(
                solver, Runs(eng, solver, LIMITS), hints))
        return kept_lint(solver_path(stem), task_id_of(stem_of(stem)), eng,
                         LIMITS, hints, make)

    found = [linted(s) for s in (stems if stems is not None else all_stems())]
    sections = [ln for s in lint_sections(found) for ln in s.printed()]
    if sections:
        print("\n".join(sections))
    findings = [f for r in found for f in r.findings]
    ok = pass_line(Section.LINT, findings)
    if ok is not None:
        print(ok)
    return exit_code(findings)
