"""The parsed view of the solver corpus: each file with its AST and index,
and the size measure over one program."""

from collections.abc import Iterator
from pathlib import Path

from dl.dlparse import Bool, Comp, Index, Program, Rigid, Rule, body_literals, parse
from dl.paths import all_stems
from dl.solve import solver_file


def each_solver() -> Iterator[tuple[Path, Program, Index]]:
    """Every solver, parsed and indexed, in stem order."""
    for stem in all_stems():
        path = solver_file(stem)[0]
        program = parse(path.read_text())
        yield path, program, Index(program)


def _rules(items: list) -> Iterator[Rule]:
    for it in items:
        if isinstance(it, Rule):
            yield it
        elif isinstance(it, (Comp, Rigid)):
            yield from _rules(it.items)


def literal_count(program: Program) -> int:
    """Program complexity: one per rule head and one per body atom,
    negation, or comparison, disjunction branches expanded and aggregate
    bodies included. Facts count their head. Declarations, types, inits,
    and the terms inside a literal add nothing: the measure follows the
    program, not the code around it."""
    return sum(1 + sum(1 for lit in body_literals(r) if not isinstance(lit, Bool))
               for r in _rules(program.items))
