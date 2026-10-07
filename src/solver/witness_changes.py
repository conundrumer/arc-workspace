"""The changes a run of a witness again makes in its entry of the witness
file (solver-file.md, under "Witness file"), and the entry that run
writes."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from engine import RunFailure
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.form_checks import output_form_problems, split_verdict_lines
from solver.model import Case
from solver.names import denoted_cases
from solver.problems import Fault, NameFault
from solver.witness import (
    Entry,
    GroupGrid,
    Outcomes,
    RejectedOutput,
    WitnessFile,
    grouped,
    members,
)


@dataclass(frozen=True)
class JudgedKept:
    """A judged output, which a run leaves as it is."""


@quotes("solver-file.md", "Witness file",
        "\"output\": Group[] // when the verdict is not other: one group per "
        "distinct output")
@dataclass(frozen=True)
class JudgedReplaced:
    """A judged output where no line records the verdict `other` for the
    entry, which the groups a run gives replace."""


@dataclass(frozen=True)
class GroupsKept:
    """The groups a run gives list the cases the file's groups list, each
    by the name the file gives it, with the same grids."""


@quotes("solver-file.md", "Witness file",
        "the fewest names whose cases together are exactly the cases that "
        "give this output")
@dataclass(frozen=True)
class NamesRewritten:
    """The file's groups list, by other names, the cases the run's groups
    list, with the same grids: the names of each file group denote together
    (`solver.names.denoted_cases`) the cases of the run's group, and the
    run's names replace them."""


@dataclass(frozen=True)
class PartitionChanged:
    """The groups a run gives split the solver's cases otherwise than the
    file's groups do: `newly` cases of the solver the file lists in no
    group, and `gone` names of the file that denote no case of the
    solver."""

    newly: int
    gone: int


@dataclass(frozen=True)
class GridChanged:
    """The groups a run gives split the solver's cases as the file's
    groups do, and a group's grid differs from the file's: `groups`
    holds the names of each such group, as the run names its cases."""

    groups: tuple[tuple[str, ...], ...]


type RecordChange = (JudgedKept | JudgedReplaced | GroupsKept
                     | NamesRewritten | PartitionChanged | GridChanged)
"""What running a witness of the file again changes in its entry."""


def _listing[T](groups: Sequence[tuple[frozenset[T], GroupGrid]]
                ) -> frozenset[tuple[frozenset[T], GroupGrid]]:
    """Groups as what each lists and its grid, in no order."""
    return frozenset(groups)


@quotes("solver-file.md", "Witness file",
        "\"output\": Group[] // when the verdict is not other: one group per "
        "distinct output")
@quotes("solver-file.md", "Witness file",
        "when the verdict is other: the annotator's judged output")
def rerecorded(solver: Solver, entry: Entry,
               run: Callable[[], Outcomes | RunFailure | Fault]
               ) -> tuple[Entry, RecordChange] | RunFailure | Fault:
    """The entry with its groups built again (`grouped`) from what `run`
    gives, the solver's cases on the entry's input at its `assign`, and
    what that changes in it; the failure where `run` gives no outcomes.
    A judged output stays where each line that records the entry's
    verdict (`solver.names.verdict_lines`) gives `other`, and `run` is not
    called for it; under any other verdict, or where no line records one,
    the groups replace it. Where the lines give `other` and another
    verdict both, the fault is the one `output_form_problems` gives for
    the entry, and `run` is not called."""
    other, another = split_verdict_lines(solver, entry.id)
    if other and another:
        alone = replace(solver, witness_file=WitnessFile(solver.task_id,
                                                         (entry,)))
        return next(output_form_problems(alone))
    if isinstance(entry.output, RejectedOutput) and other:
        return entry, JudgedKept()
    outcomes = run()
    if not isinstance(outcomes, tuple):
        return outcomes
    groups = grouped(solver, outcomes)
    got = replace(entry, output=groups)
    if isinstance(entry.output, RejectedOutput):
        return got, JudgedReplaced()
    if _listing([(frozenset(g.cases), g.grid) for g in groups.groups]) \
            == _listing([(frozenset(g.cases), g.grid)
                         for g in entry.output.groups]):
        return got, GroupsKept()
    among = [c for c, _g in outcomes]
    old: list[tuple[frozenset[Case], GroupGrid]] = []
    listing_none = 0
    for g in entry.output.groups:
        listed: set[Case] = set()
        for n in g.cases:
            denoted = denoted_cases(solver, n, among)
            if isinstance(denoted, NameFault) or not denoted:
                listing_none += 1
            else:
                listed |= denoted
        old.append((frozenset(listed), g.grid))
    new = [(frozenset(members(outcomes, g)), g) for g in groups.groups]
    if listing_none or {cs for cs, _g in old} != {cs for cs, _g in new}:
        was = {c for cs, _g in old for c in cs}
        return got, PartitionChanged(len(set(among) - was), listing_none)
    held = _listing(old)
    moved = tuple(g.cases for cs, g in new if (cs, g.grid) not in held)
    if not moved:
        return got, NamesRewritten()
    return got, GridChanged(moved)

