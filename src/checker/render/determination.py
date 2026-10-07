"""The determination section of `run`."""

from collections.abc import Sequence

from checker.finding import Finding
from checker.judged import NO_TASK
from checker.payloads.branches import DeterminationDiffPayload
from checker.render import finding_lines, in_line_order
from checker.render.locations import line_text
from checker.render.branches import diff_line, differing, finding_text
from checker.runs import NoTask
from controlled_markdown import mctx
from engine.program import dotted
from solver.aggregate import Solver
from solver.determine import Determined, DetermineResult, NoDetermine


def determination_lines(solver: Solver, result: DetermineResult | NoTask,
                        findings: Sequence[Finding]) -> list[str]:
    """The determination section of `run`
    ([Determination](docs/handbook/solver-file.md#determination)): the
    cycles among the determined parameters, then each finding, and the
    `ok` line with the determined parameters where no finding stands."""
    if isinstance(result, NoDetermine):
        return [mctx("determination: no Determine comp")]
    if isinstance(result, NoTask):
        return [mctx("determination: ") + finding_text(solver, NO_TASK)]
    lines: list[str] = []
    if isinstance(result, Determined):
        scopes = {u.id: u.scope for u in solver.program.units}
        lines += [mctx("circular determination: ") + ", ".join(
            mctx("{param} reads params.{reads} ({comp} {line})").format(
                param=r.parameter, reads=r.reads,
                comp=dotted(scopes[r.unit].components),
                line=line_text(r.line))
            for r in cycle) for cycle in result.cycles]
    diffs = [n for f in findings
             if isinstance(f.payload, DeterminationDiffPayload)
             for n in differing(solver, f.payload)]
    others = [f for f in findings
              if not isinstance(f.payload, DeterminationDiffPayload)]
    for f in in_line_order(others):
        lines += finding_lines(solver, f)
    if diffs:
        lines.append(diff_line(diffs))
    if isinstance(result, Determined) and not findings and not result.cycles:
        names = sorted(p.name for p in solver.params.parameters
                       if p.determined)
        lines.append(mctx("determination: ok ({params})").format(
            params=", ".join(names)))
    return lines
