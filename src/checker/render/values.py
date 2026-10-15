"""Values and code as a report draws them: a resolution's grids,
a column's value, and a list of code or of names."""

from collections.abc import Sequence

from checker.finding import Code
from checker.render.grids import grid_lines, shifted
from controlled_markdown import mctx
from engine import Engine, Value
from solver.aggregate import Solver
from solver.out_grids import out_columns
from solver.witness import Resolutions


def resolution_lines(solver: Solver, out: Resolutions) -> list[str]:
    """A `Resolutions` output drawn: each grid under its resolution value
    as Souffle prints it, and under `grid <i>` where the run gave none, as
    a witness file's grids are, the values of a resolution of more than
    one resolution column joined by `, `."""
    from checker.render.relation import souffle_text
    columns = out_columns(solver.program).resolution
    lines: list[str] = []
    for i, grid in enumerate(out.grids):
        head = ", ".join(
            souffle_text(solver, v, c.type)
            for v, c in zip(out.values[i], columns, strict=True)) \
            if i < len(out.values) else mctx("grid {i}").format(i=i + 1)
        lines.append(f"{head}:")
        lines += [shifted(r, "  ") for r in grid_lines(grid)]
    return lines


def _codes(engine: Engine, codes: Sequence[Code]) -> str:
    return ", ".join(engine.text(c) for c in codes)


def _ticked(names: Sequence[str]) -> str:
    return ", ".join(f"`{n}`" for n in names)


def arg_text(value: Value, type_name: str, solver: Solver) -> str:
    """One column's value: where the column's type is a lib orientation
    type and exactly one of its members names the value, that member;
    any other value as the solver writes it. The type is the one the
    column declares, so a solver's own type, a subtype of an orientation
    type included, gives numbers. The members are those the type's
    `_elem` relation lists (`Lib.orientation_types`), so a `#define`
    outside them names no value of the type."""
    lib = solver.lib
    named = [m for m in lib.orientation_types.get(type_name, ())
             if lib.constants.get(m) == value]
    return named[0] if len(named) == 1 else solver.engine.text(value)
