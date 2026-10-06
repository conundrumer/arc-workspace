"""The rows of `relation`: a relation's rows under its columns, and a
column's value as `relation` prints it."""

from collections.abc import Sequence

from checker.judged import value_constructors
from checker.render import arg_text, joined
from controlled_markdown import mctx
from engine import AdtValue, RecordValue, Value
from solver.model import Solver
from solver.names import name as case_name
from solver.vocabulary import CHOICE

NO_ROWS = mctx("{head}: no rows")


def relation_lines(name: str, columns: Sequence[str],
                   rows: Sequence[Sequence[str]]) -> list[str]:
    """One relation's rows as Souffle prints them, under its columns."""
    head = f"{name}({', '.join(columns)})"
    if not rows:
        return [NO_ROWS.format(head=head)]
    return [f"{head}:", *("  " + "\t".join(r) for r in rows)]


def souffle_text(solver: Solver, value: Value, type_name: str) -> str:
    """A column's value of `relation` as Souffle prints it; a `Choice`
    value by its case's name, a value of an ADT at a choice point by
    the branches of its constructors, each by its name, joined by
    ` & `, and a value of a lib orientation type by its constant
    (`arg_text`)."""
    if type_name == CHOICE and isinstance(value, AdtValue | RecordValue):
        return case_name(solver, value)
    points = set() if solver.choice is None \
        else {p.type for p in solver.choice.points}
    if type_name in points and isinstance(value, AdtValue):
        return joined(value_constructors(value))
    return arg_text(value, type_name, solver.lib)
