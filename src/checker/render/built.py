"""The witness a `derive` or `store` block builds, as `record` prints one,
and why a case is undefined on an input."""

from collections.abc import Sequence

from checker.render.grids import grid_lines, shifted
from checker.render.values import resolution_lines
from controlled_markdown import mctx
from solver.aggregate import Solver
from solver.model import Case
from solver.names import Denoted, denote
from solver.undefined import (
    ConflictingCells,
    InconsistentBounds,
    MissingCells,
    NegativeEdges,
    NoDerivedValue,
    NoOutput,
    Undefined,
    UndefinedReason,
)
from solver.witness import Entry, Groups, Resolutions

GROUP_WIDTH = 100
"""The widest a witness group's line of case names stands; a wider
group puts each name on a line of its own."""


def takes_branch(solver: Solver, name: str) -> bool:
    """Whether the case a witness file's name denotes takes a `@derive` or
    `@store` branch (`solver.names.denote`)."""
    d = denote(solver, name)
    return isinstance(d, Denoted) and bool(d.branches)


def undefined_text(reason: UndefinedReason | None,
                   counted: bool = False) -> str:
    """Why a case is undefined on an input, with the cells or the values
    at fault listed, or counted where `counted`; `undefined` for a reason
    not known."""
    match reason:
        case NoOutput():
            return mctx("emits nothing")
        case ConflictingCells(cells=cells):
            return mctx("conflicts at: {cells}").format(
                cells=_items(cells, counted, "cell", "cells"))
        case MissingCells(cells=cells):
            return mctx("missing cells at: {cells}").format(
                cells=_items(cells, counted, "cell", "cells"))
        case NegativeEdges(edges=edges):
            return mctx("negative edge distances (top, bottom, left, "
                        "right) at: {edges}").format(
                edges=_items(edges, counted, "cell", "cells"))
        case InconsistentBounds(bounds=bounds):
            return mctx("inconsistent grid bounds (height, width): "
                        "{bounds}").format(
                bounds=_items(bounds, counted, "frame size", "frame sizes"))
        case NoDerivedValue(parameter=parameter, proposer=proposer):
            return mctx("{proposer} derives no {parameter}").format(
                proposer=proposer, parameter=parameter)
        case None:
            return mctx("undefined")


def _items(items: Sequence[object], counted: bool, one: str, many: str
           ) -> str:
    if not counted:
        return str(list(items))
    return f"{len(items)} {one if len(items) == 1 else many}"


def undefined_lines(reason: UndefinedReason | None) -> list[str]:
    """Why a case's cells describe no grid (`undefined_text`), as lines
    under the case's name; nothing for a case with no cell or with no
    derived value, whose name says it."""
    if reason is None or isinstance(reason, NoOutput | NoDerivedValue):
        return []
    return [undefined_text(reason)]


def record_lines(entry: Entry, solver: Solver, cases: Sequence[Case],
                 of: int) -> list[str]:
    """A built witness as `record` prints it: the input, each group of
    cases above the grid they give, or above why their cells describe no
    grid (`undefined_lines`), the cases that give none, and the
    count line (`checker.render.recording.COUNT_LINE`): how many `cases`,
    the witnessed cases the groups were built from, of the `of` cases of
    the solver, and the distinct grids."""
    lines = [mctx("input:"), *(shifted(r, "  ") for r in grid_lines(
        entry.input))]
    groups = entry.output.groups if isinstance(entry.output, Groups) else ()
    silent: list[tuple[str, UndefinedReason | None]] = []
    grids: set[object] = set()
    for g in groups:
        out = g.grid
        if isinstance(out, Undefined):
            grids.add(out)
        why = undefined_lines(out.reason) if isinstance(out, Undefined) \
            else []
        if isinstance(out, Undefined) and not why:
            silent += [(n, out.reason) for n in g.cases]
            continue
        joined = ", ".join(g.cases)
        lines.append("")
        if len(joined) > GROUP_WIDTH:
            lines += [f"  {n}" for n in g.cases] + [":"]
        else:
            lines.append(f"{joined}:")
        if isinstance(out, Undefined):
            lines += [f"  {ln}" for ln in why]
        elif isinstance(out, Resolutions):
            grids.update(out.grids)
            lines += [shifted(r, "  ") for r in resolution_lines(solver, out)]
        else:
            grids.add(out)
            lines += [shifted(r, "  ") for r in grid_lines(out)]
    if silent:
        lines.append("")
        lines += [mctx("{name}: {why}").format(name=n, why=undefined_text(
            NoOutput() if isinstance(r, NoOutput)
            or (r is None and not takes_branch(solver, n)) else None))
            for n, r in silent]
    if of > 1:
        from checker.render.recording import COUNT_LINE
        lines += ["", COUNT_LINE.format(n=len(cases), m=of, g=len(grids))]
    return lines
