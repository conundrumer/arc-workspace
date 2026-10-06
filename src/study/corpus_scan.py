"""A scan of the solver corpus for parameters that state the same number."""

from cli.common import all_stems
from cli.common import engine as _engine
from solver.load import load
from solver.aggregate import Solver
from solver.vocabulary import NUMBER


def equal_literal_params(solver: Solver) -> list[tuple[int, list[str]]]:
    """Groups of the solver's Params parameters that hold one single-number
    row each and state the same number, as (number, parameter names).
    A parameter read by no group is left out; so is a group of one."""
    values: dict[str, int] = {}
    for param in solver.params.parameters:
        if [c.type for c in param.columns] != [NUMBER]:
            continue
        rows = param.stored
        if not isinstance(rows, tuple) or len(rows) != 1 \
                or len(rows[0]) != 1 or not isinstance(rows[0][0], int):
            continue
        values[param.name] = rows[0][0]
    groups: dict[int, list[str]] = {}
    for name, value in values.items():
        groups.setdefault(value, []).append(name)
    return [(v, names) for v, names in sorted(groups.items()) if len(names) > 1]


def equal_literal_corpus() -> list[tuple[str, int, list[str]]]:
    """(stem, literal, relation names) for every solver under
    programs/solvers/ carrying such a group, sorted by stem."""
    found = []
    engine = _engine()
    for stem in all_stems():
        for value, names in equal_literal_params(load(stem, engine)):
            found.append((stem, value, names))
    return found
