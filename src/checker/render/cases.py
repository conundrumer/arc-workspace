"""Cases as a report names them: a set of cases, the names that denote
it, a name's parts, and a parameter under a case."""

from collections.abc import Sequence

from controlled_markdown import mctx
from solver import names
from solver.aggregate import Solver
from solver.model import Case


def joined(parts: Sequence[str]) -> str:
    """The parts of one name joined as a witness file joins them,
    `<name> & <name>`
    ([Witness file](docs/handbook/solver-file.md#witness-file))."""
    return names.SEPARATOR.join(parts)


def cases_text(solver: Solver, cases: Sequence[Case],
               among: Sequence[Case]) -> str:
    """A set of cases as every report prints one: the fewest names whose
    cases among `among` are exactly them (`solver.names.cover`)."""
    return names_text(names.cover(solver, cases, among))


def names_text(names: Sequence[str]) -> str:
    """The names that denote a set of cases, as every report prints
    them."""
    return ", ".join(names)


def under_case(parameter: str, name: str) -> str:
    """A parameter's name with the name of the case whose value a line
    gives."""
    return mctx("{param} under {case}").format(param=parameter, case=name)
