"""The lines of `grid` and `record`: the judged output, the constructors
no case takes, the count line of a built witness, and what `record`
wrote to the witness file or left unwritten."""

from collections.abc import Sequence

from checker.render import Section, counted, noun
from checker.render.grids import grid_lines, shifted
from checker.render.hints import derive_line_to_add
from checker.render.values import _ticked
from controlled_markdown import mctx
from engine import Grid
from engine.program import RelationDecl
from engine.text import text as code_text
from solver.aggregate import Solver
from solver.model import Case, takes_constructor
from solver.names import ctor_text
from solver.witness import (
    GridChanged,
    GroupsKept,
    JudgedKept,
    NamesRewritten,
    PartitionChanged,
    RecordChange,
)

JUDGED_OUTPUT = mctx("judged output:")
WOULD_RECORD = mctx("would record witness `{id}`")


WROTE = mctx("wrote witness `{id}` to {path}")
REMOVED = mctx("removed witness `{id}` from {path}")
RESEPARATED = mctx("rewrote the `separates` text of witness `{id}` in {path}")


def not_written(id: str, names: Sequence[str], kind: Section, lineless: bool
                ) -> str:
    """The line of a witness a survey built and did not write, since its
    groups hold `names`, which denote no case of the solver; `lineless`
    where the survey built it with a `@derive` or `@store` line (`kind`)
    the solver does not hold."""
    if lineless:
        return mctx("wrote no witness `{id}`: the solver has no `@{kind}` "
                    "line for `{id}`; once the line is written, `{kind}` "
                    "writes the witness").format(id=id, kind=kind.value)
    return mctx("wrote no witness `{id}`: its groups name {names}, which "
                "denote no case of the solver").format(
        id=id, names=_ticked(names))


def wrote_lineless(id: str, path: object, proposer: str,
                   decl: RelationDecl) -> str:
    """The line of a witness the `derive` survey wrote for a derivation
    with no `@derive` line: its groups name the branch, which the solver
    denotes once the line stands above the parameter's declaration."""
    return mctx("wrote witness `{id}` to {path}; its groups name `{id}`, so "
                "add `{line}` above `{decl}`, its verdict read from this "
                "witness").format(
        id=id, path=path, decl=code_text(decl),
        line=derive_line_to_add(proposer))


FORMATTED = mctx("formatted {path}")
RERECORDED_ONE = mctx("re-recorded witness `{id}` in {path}: {change}")


def _witnesses(n: int) -> str:
    return counted(n, mctx("witness"), mctx("witnesses"))


def rerecorded_all(n: int, path: object, changed: int) -> str:
    """The line of `record --all` that wrote the file: how many witnesses
    ran, and how many of them changed groups."""
    return mctx("re-recorded {witnesses} in {path}: {changed} with changed "
                "groups").format(witnesses=_witnesses(n), path=path,
                                 changed=changed)


def unchanged_file(n: int, path: object) -> str:
    """The line of `record --all` that wrote nothing, since the file
    already holds the text the writer writes."""
    return mctx("re-ran {witnesses}: {path} holds them as the writer "
                "writes them, so nothing was written").format(
                    witnesses=_witnesses(n), path=path)


WROTE_NOTHING = mctx("wrote nothing to {path}: {failed} of {n} witnesses "
                     "could not be run")
COUNT_LINE = mctx("{n} witnessed cases of {m}, {g} distinct grid(s)")
"""The count line of a built witness: the witnessed cases its groups were
built from, the solver's cases, and the distinct grids they give
(solver-file.md, under "Cases"). `grid` prints the same line
(`record_lines`)."""


def untaken_constructor_lines(solver: Solver, cases: Sequence[Case]
                              ) -> list[str]:
    """A line for each constructor of the solver's `Choice`, at any
    depth, that no case of `cases` takes, in point order."""
    choice = solver.choice
    if choice is None:
        return []
    return [mctx("no case takes {ctor}").format(ctor=ctor_text(c.name))
            for p in choice.points for c in p.constructors
            if not any(takes_constructor(choice, k.base, c) for k in cases)]


GROUPS_KEPT = mctx("groups unchanged")
JUDGED_KEPT = mctx("judged output kept")
GROUPS_CHANGED = mctx("groups changed: {newly} {cases} newly listed, {gone} "
                      "no longer listed")
GRID_CHANGED = mctx("grid changed in {groups}: {names}")
NAMES_REWRITTEN = mctx("names rewritten to the listed form")


def rerecord_text(change: RecordChange) -> str:
    """What running a witness again changed in its entry, as `record`
    prints it."""
    match change:
        case JudgedKept():
            return JUDGED_KEPT
        case GroupsKept():
            return GROUPS_KEPT
        case NamesRewritten():
            return NAMES_REWRITTEN
        case PartitionChanged(newly=newly, gone=gone):
            return GROUPS_CHANGED.format(
                newly=newly, gone=gone,
                cases=noun(newly, "case"))
        case GridChanged(groups=groups):
            return GRID_CHANGED.format(
                groups=counted(len(groups), mctx("group")),
                names="; ".join(_ticked(g) for g in groups))


def judged_lines(grid: Grid) -> list[str]:
    return ["", JUDGED_OUTPUT, *(shifted(r, "  ") for r in grid_lines(grid))]
