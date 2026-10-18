"""The one place where a name in a witness file resolves to the model it
denotes: an entry's groups from what the cases give, the cases a group
holds, and when two outputs are one."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from solver.witness import Group, GroupGrid, Groups

if TYPE_CHECKING:
    from solver.model import Case
    from solver.aggregate import Solver


def output_key(o: object) -> object:
    """A value two outputs share exactly where they are the same output
    (`same_output`): the output itself, as undefined outputs are one output
    whatever their reasons. `o` is what a witness file's group holds, or
    what a run gives."""
    return o


def same_output(a: object, b: object) -> bool:
    """Whether two cases give the same output: equal grids, or both
    undefined, whatever the reason or the cells. `a` and `b` are what
    a witness file's group holds, or what a run gives."""
    return output_key(a) == output_key(b)


def grouped(solver: "Solver", outcomes: Sequence[tuple["Case", GroupGrid]]
            ) -> Groups:
    """An entry's groups from what each of the solver's cases gives on its
    input: one group per distinct output (`same_output`), the group that
    holds the concept case first and the rest in the order the cases come
    in, naming its cases by the fewest names that denote exactly them
    (`solver.names.cover`; docs/handbook/solver-file.md#witness-file)."""
    from solver.aggregate import is_concept_case
    from solver.names import cover
    among = [c for c, _g in outcomes]
    out: list[tuple[list["Case"], GroupGrid]] = []
    for c, got in outcomes:
        for cases, g in out:
            if same_output(g, got):
                cases.append(c)
                break
        else:
            out.append(([c], got))
    out.sort(key=lambda group: not any(
        is_concept_case(solver, c) for c in group[0]))
    return Groups(tuple(Group(cover(solver, cases, among), g)
                        for cases, g in out))


type Outcomes = tuple[tuple["Case", GroupGrid], ...]
"""What each case of the solver gives on an entry's input at its
`assign`, in the order the cases come in."""


def members(outcomes: Outcomes, group: Group) -> tuple["Case", ...]:
    """The cases a group of `grouped(solver, outcomes)` holds: those that
    give its grid."""
    return tuple(c for c, g in outcomes if same_output(g, group.grid))
