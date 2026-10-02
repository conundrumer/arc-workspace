"""The witness file (solver-file.md, under "Witness file"), and the one place
where a name in it resolves to the model it denotes."""

import fcntl
import json
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, cast

from arc.jsonio import format_file
from arc.task import as_grid as task_grid
from engine import Grid, RunFailure, Value, checkout
from engine.memo import write_whole
from engine.program import as_grid, grid_lists
from engine.quotes import quotes
from solver.problems import (
    Expected,
    InWitnessFile,
    ProblemKind,
    Fault,
    NameFault,
    ShapeFault,
    WitnessFileRole,
)

if TYPE_CHECKING:
    from solver.model import Case, Solver


@quotes("principles.md", "Models and tasks",
        "A model is defined at an assignment and input when its output is "
        "nonempty and contains only total grids.")
@dataclass(frozen=True)
class NoOutput:
    """`out` holds no cell at the case: the output is empty."""


type Cell = tuple[int, int]
"""A cell of a grid, by row and column."""


@quotes("principles.md", "Models and tasks",
        "A model is defined at an assignment and input when its output is "
        "nonempty and contains only total grids.")
@dataclass(frozen=True)
class MissingCells:
    """`out`'s cells at the case leave cells of their frame without a color:
    the grid is not total."""

    cells: tuple[Cell, ...]
    """The cells without a color, in row order."""


@dataclass(frozen=True)
class ConflictingCells:
    """`out`'s cells at the case give cells two colors, so they describe
    no grid."""

    cells: tuple[Cell, ...]
    """The cells with two colors, in row order."""


@dataclass(frozen=True)
class NegativeEdges:
    """`out`'s cells at the case give a cell a negative distance to an
    edge of its frame, so they describe no grid."""

    edges: tuple[tuple[int, int, int, int], ...]
    """Each such cell's distances to the top, bottom, left and right
    edges, in order."""


@dataclass(frozen=True)
class InconsistentBounds:
    """`out`'s cells at the case give more than one frame size, so they
    describe no grid."""

    bounds: tuple[Cell, ...]
    """The frame sizes, as height and width, in order."""


@dataclass(frozen=True)
class NoDerivedValue:
    """A `@derive` branch of the case derives its parameter, and the
    proposer gives it no value on the input (principles.md, under "Stored or
    derived")."""

    parameter: str
    proposer: str


type UndefinedReason = (NoOutput | MissingCells | ConflictingCells
                        | NegativeEdges | InconsistentBounds | NoDerivedValue)


@quotes("solver-file.md", "Witness file",
        "\"grid\": Grid | Grid[] | null } // null for undefined")
@dataclass(frozen=True)
class Undefined:
    """`null`: the cases are undefined on the input. Two values are equal
    whatever their reasons, as a witness file's `null` states none; two
    outputs are the same output only where their reasons are equal too
    (`same_output`)."""

    reason: UndefinedReason | None = field(default=None, compare=False)
    """Why a run gives no grid; None for a witness file's `null`, which
    states no reason."""


@quotes("solver-file.md", "Witness file",
        "a list of the grids the cases give, one per tiebreak resolution, "
        "when they give more than one")
@dataclass(frozen=True)
class Resolutions:
    """A list of grids, one per tiebreak resolution, and the resolution
    value of each where a run gave them; a witness file holds the grids
    alone."""

    grids: tuple[Grid, ...]
    values: tuple[Value, ...] = field(default=(), compare=False)


type GroupGrid = Grid | Resolutions | Undefined


@quotes("solver-file.md", "Witness file",
        "the fewest names whose cases together are exactly the cases that "
        "give this output")
@dataclass(frozen=True)
class Group:
    """`{cases, grid}`."""

    cases: tuple[str, ...]
    grid: GroupGrid


@quotes("solver-file.md", "Witness file",
        "\"output\": Group[] // when the verdict is not other: one group per "
        "distinct output")
@dataclass(frozen=True)
class Groups:
    """An `output` of groups, for a verdict that is not `other`."""

    groups: tuple[Group, ...]


@quotes("solver-file.md", "Witness file",
        "when the verdict is other: the annotator's judged output")
@dataclass(frozen=True)
class RejectedOutput:
    """An `output` that is a bare grid, the judged output of an `other`
    verdict."""

    grid: Grid


type Output = Groups | RejectedOutput

type AssignArg = Annotated[int | str | tuple["AssignArg", ...],
    quotes("solver-file.md", "Witness file",
           "Use a string for a lib constant and a list for a record.")]
"""A string for a lib constant, a list for a record."""


@dataclass(frozen=True)
class AssignRows:
    rows: tuple[tuple[AssignArg, ...], ...]


@dataclass(frozen=True)
class AnchoredGrid:
    """A stamp picture an entry gives with its anchor: the grid, and the row
    and column of the anchor cell in it, counted from 0."""

    grid: Grid
    anchor: tuple[int, int]


type AssignValue = AssignRows | Grid | AnchoredGrid


@quotes("solver-file.md", "Witness file",
        "the parameters the witness reassigns, which may include a `@store` "
        "line's relation")
@dataclass(frozen=True)
class Entry:
    """One witness of the file. `assign` holds each parameter or stored
    relation it reassigns in file order. (A file entry; the `@witness`
    comment line is `solver.annotations.WitnessLine`.)"""

    id: str
    separates: str
    input: Grid
    assign: tuple[tuple[str, AssignValue], ...]
    output: Output


@quotes("solver-file.md", "Witness file",
        "`programs/witnesses/<task_id>.wit.json` holds the witnesses the "
        "solver's cases are pinned to.")
@dataclass(frozen=True)
class WitnessFile:
    """`programs/witnesses/<task_id>.wit.json`."""

    task_id: str
    entries: tuple[Entry, ...]

    def entry(self, id: str) -> Entry | None:
        """The file's first entry of the id `id`; None where it has none."""
        return next((e for e in self.entries if e.id == id), None)


def path(task_id: str) -> Path:
    """`programs/witnesses/<task_id>.wit.json` (solver-file.md, under "Witness
    file")."""
    return checkout.witnesses() / f"{task_id}.wit.json"


type Path_ = tuple[str | int, ...]
type Off = Callable[[str | None, Path_, Expected], None]


def shape_fault(entry: str | None, file: WitnessFileRole, field: Path_,
                expected: Expected) -> Fault:
    """A witness file off its shape: at `entry` of `file` (None for the file
    as a whole), the field `field` is not what `expected` says."""
    return Fault(ProblemKind.WITNESS_FILE_SHAPE, InWitnessFile(entry, file),
                 ShapeFault(field, expected))


def read(text: str, file: WitnessFileRole
         ) -> tuple[WitnessFile | None, tuple[Fault, ...]]:
    """The witness file `text` states, None where its shape gives none,
    and what could not be read, placed in `file`.

    An entry off the shape is left out, with a problem for each part off
    it; an unknown field and a repeated id are problems beside the entry
    they stand in. Every `assign` value reads as rows here: whether a
    value is a grid depends on the parameter it names, which the model
    settles (`with_grids`)."""
    problems: list[Fault] = []

    def off(entry: str | None, field: Path_, expected: Expected) -> None:
        problems.append(shape_fault(entry, file, field, expected))

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        off(None, (), Expected.JSON)
        return None, tuple(problems)
    if not isinstance(data, dict):
        off(None, (), Expected.OBJECT)
        return None, tuple(problems)
    top = cast(dict[str, object], data)
    for key in top:
        if key not in _FILE_KEYS:
            off(None, (key,), Expected.ABSENT)
    task_id = _typed(top, "id", str, None, (), off)
    entries = _typed(top, "witnesses", list, None, (), off)
    if not isinstance(task_id, str) or not isinstance(entries, list):
        return None, tuple(problems)
    out: list[Entry] = []
    seen: set[str] = set()
    for i, raw in enumerate(cast(list[object], entries)):
        entry = _entry(raw, i, off)
        if entry is None:
            continue
        if entry.id in seen:
            off(entry.id, ("id",), Expected.UNIQUE)
        seen.add(entry.id)
        out.append(entry)
    return WitnessFile(task_id, tuple(out)), tuple(problems)


_FILE_KEYS = ("id", "witnesses")
_ENTRY_KEYS = ("id", "separates", "input", "assign", "output")
_GROUP_KEYS = ("cases", "grid")



_KINDS: dict[type, Expected] = {str: Expected.STRING, list: Expected.LIST}
"""The kinds `_typed` reads a field as, with what a field of another kind
was expected to be."""


def _typed(value: dict[str, object], key: str, kind: type, entry: str | None,
           prefix: Path_, off: Off) -> object:
    """`value[key]` where it is of `kind`, one of `_KINDS`; otherwise None,
    and the fault: the field missing, or of another kind."""
    if key not in value:
        off(entry, (*prefix, key), Expected.PRESENT)
        return None
    got = value[key]
    if not isinstance(got, kind):
        off(entry, (*prefix, key), _KINDS[kind])
        return None
    return got


def _grid(value: object) -> Grid | None:
    """A rectangular, nonempty grid of colors 0 to 9 (`arc.task.as_grid`),
    or None."""
    try:
        rows = task_grid(value)
    except ValueError:
        return None
    return as_grid(rows)


def _arg(value: object) -> AssignArg | None:
    if type(value) is int or isinstance(value, str):
        return value
    if isinstance(value, list):
        args = [_arg(v) for v in cast(list[object], value)]
        if any(a is None for a in args):
            return None
        return tuple(a for a in args if a is not None)
    return None


def _assign(value: object, entry: str | None, prefix: Path_, off: Off
            ) -> tuple[tuple[str, AssignValue], ...] | None:
    if not isinstance(value, dict):
        off(entry, (*prefix, "assign"), Expected.OBJECT)
        return None
    out: list[tuple[str, AssignValue]] = []
    for name, facts in cast(dict[str, object], value).items():
        if isinstance(facts, dict):
            anchored = _anchored(cast(dict[str, object], facts))
            if anchored is None:
                off(entry, (*prefix, "assign", name), Expected.ANCHORED_GRID)
                return None
            out.append((name, anchored))
            continue
        rows: list[tuple[AssignArg, ...]] = []
        if isinstance(facts, list):
            for fact in cast(list[object], facts):
                arg = _arg(fact) if isinstance(fact, list) else None
                if not isinstance(arg, tuple):
                    rows = []
                    break
                rows.append(arg)
        if not rows:
            off(entry, (*prefix, "assign", name), Expected.FACTS_OR_GRID)
            return None
        out.append((name, AssignRows(tuple(rows))))
    return tuple(out)


def _anchored(value: dict[str, object]) -> AnchoredGrid | None:
    """`{"grid": Grid, "anchor": [row, col]}` with the anchor a cell of the
    grid, or None."""
    if set(value) != {"grid", "anchor"}:
        return None
    grid = _grid(value["grid"])
    at = value["anchor"]
    if grid is None or not isinstance(at, list):
        return None
    cells = cast(list[object], at)
    if len(cells) != 2 or any(type(c) is not int for c in cells):
        return None
    r, c = cast(list[int], cells)
    if not (0 <= r < len(grid) and 0 <= c < len(grid[0])):
        return None
    return AnchoredGrid(grid, (r, c))


def read_assign(value: object
                ) -> tuple[tuple[tuple[str, AssignValue], ...] | None,
                           tuple[Fault, ...]]:
    """An `--assign` object, as `read` reads an entry's `assign` value, None
    where it is off its shape, and what could not be read."""
    problems: list[Fault] = []

    def off(entry: str | None, field: Path_, expected: Expected) -> None:
        problems.append(shape_fault(entry, WitnessFileRole.ASSIGN, field,
                                    expected))

    return _assign(value, None, (), off), tuple(problems)


def assign_with_grids(assign: tuple[tuple[str, AssignValue], ...],
                      grid_names: frozenset[str]
                      ) -> tuple[tuple[str, AssignValue], ...]:
    """`assign` with each value of a name in `grid_names`, a parameter
    stored as a grid, read as a grid where it has a grid's shape
    (solver-file.md, under "Witness file"), and as facts otherwise."""
    out: list[tuple[str, AssignValue]] = []
    for name, value in assign:
        if name in grid_names and isinstance(value, AssignRows):
            grid = _grid([list(r) for r in value.rows])
            if grid is not None:
                value = grid
        out.append((name, value))
    return tuple(out)


def _group_grid(value: object) -> GroupGrid | None:
    if value is None:
        return Undefined()
    if (grid := _grid(value)) is not None:
        return grid
    if isinstance(value, list) and value:
        grids = [_grid(g) for g in cast(list[object], value)]
        if all(g is not None for g in grids):
            return Resolutions(tuple(g for g in grids if g is not None))
    return None


def _output(value: object, entry: str | None, prefix: Path_, off: Off
            ) -> Output | None:
    at = (*prefix, "output")
    if (grid := _grid(value)) is not None:
        return RejectedOutput(grid)
    if not isinstance(value, list) or not all(
            isinstance(g, dict) for g in cast(list[object], value)):
        off(entry, at, Expected.GROUPS_OR_GRID)
        return None
    groups: list[Group] = []
    seen: set[str] = set()
    ok = True
    for i, raw in enumerate(cast(list[dict[str, object]], value)):
        for key in raw:
            if key not in _GROUP_KEYS:
                off(entry, (*at, i, key), Expected.ABSENT)
        cases = _typed(raw, "cases", list, entry, (*at, i), off)
        if "grid" not in raw:
            off(entry, (*at, i, "grid"), Expected.PRESENT)
        if not isinstance(cases, list) or "grid" not in raw:
            ok = False
            continue
        names = cast(list[object], cases)
        if not names:
            off(entry, (*at, i, "cases"), Expected.NONEMPTY)
        bad = [j for j, n in enumerate(names) if not isinstance(n, str)]
        for j in bad:
            off(entry, (*at, i, "cases", j), Expected.STRING)
        if bad:
            ok = False
            continue
        for j, n in enumerate(cast(list[str], names)):
            if n in seen:
                off(entry, (*at, i, "cases", j), Expected.UNIQUE)
            seen.add(n)
        grid = _group_grid(raw["grid"])
        if grid is None:
            off(entry, (*at, i, "grid"), Expected.GROUP_GRID)
            ok = False
            continue
        groups.append(Group(tuple(cast(list[str], names)), grid))
    return Groups(tuple(groups)) if ok else None


def _entry(raw: object, index: int, off: Off) -> Entry | None:
    """One witness. Its problems name it by its id, or, where it has none,
    by its place in `witnesses` as the start of the field's path."""
    if not isinstance(raw, dict):
        off(None, ("witnesses", index), Expected.OBJECT)
        return None
    e = cast(dict[str, object], raw)
    ident = e.get("id")
    entry = ident if isinstance(ident, str) else None
    prefix: Path_ = () if entry is not None else ("witnesses", index)
    for key in e:
        if key not in _ENTRY_KEYS:
            off(entry, (*prefix, key), Expected.ABSENT)
    _typed(e, "id", str, entry, prefix, off)
    separates = _typed(e, "separates", str, entry, prefix, off)
    grid = None
    if "input" not in e:
        off(entry, (*prefix, "input"), Expected.PRESENT)
    elif (grid := _grid(e["input"])) is None:
        off(entry, (*prefix, "input"), Expected.GRID)
    output = None
    if "output" not in e:
        off(entry, (*prefix, "output"), Expected.PRESENT)
    else:
        output = _output(e["output"], entry, prefix, off)
    assign = () if "assign" not in e \
        else _assign(e["assign"], entry, prefix, off)
    if entry is None or not isinstance(separates, str) \
            or grid is None or output is None or assign is None:
        return None
    return Entry(entry, separates, grid, assign, output)


def output_key(o: object) -> object:
    """A value two outputs share exactly where they are the same output
    (`same_output`): an undefined output's reason beside `Undefined`, any
    other output itself. `o` is what a witness file's group holds, or what
    a run gives."""
    return (Undefined, o.reason) if isinstance(o, Undefined) else o


def same_output(a: object, b: object) -> bool:
    """Whether two cases give the same output: equal grids, or both
    undefined for the same reason at the same cells. `a` and `b` are what
    a witness file's group holds, or what a run gives."""
    return output_key(a) == output_key(b)


def grouped(solver: "Solver", outcomes: Sequence[tuple["Case", GroupGrid]]
            ) -> Groups:
    """An entry's groups from what each of the solver's cases gives on its
    input: one group per distinct output (`same_output`), the group that
    holds the concept case first and the rest in the order the cases come
    in, naming its cases by the fewest names that denote exactly them
    (`solver.names.cover`; solver-file.md, under "Witness file")."""
    from solver.model import is_concept_case
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


@dataclass(frozen=True)
class JudgedKept:
    """A judged output, which a run leaves as it is."""


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


type RecordChange = (JudgedKept | GroupsKept | NamesRewritten
                     | PartitionChanged | GridChanged)
"""What running a witness of the file again changes in its entry."""


def _listing[T](groups: Sequence[tuple[frozenset[T], GroupGrid]]
                ) -> frozenset[tuple[frozenset[T], GroupGrid]]:
    """Groups as what each lists and its grid, in no order."""
    return frozenset(groups)


def rerecorded(solver: "Solver", entry: Entry,
               run: Callable[[], Outcomes | RunFailure | Fault]
               ) -> tuple[Entry, RecordChange] | RunFailure | Fault:
    """The entry with its groups built again (`grouped`) from what `run`
    gives, the solver's cases on the entry's input at its `assign`, and
    what that changes in it; a judged output stays, and `run` is not
    called for it. The failure where `run` gives no outcomes."""
    from solver.names import denoted_cases
    if isinstance(entry.output, RejectedOutput):
        return entry, JudgedKept()
    outcomes = run()
    if not isinstance(outcomes, tuple):
        return outcomes
    groups = grouped(solver, outcomes)
    got = replace(entry, output=groups)
    if _listing([(frozenset(g.cases), g.grid) for g in groups.groups]) \
            == _listing([(frozenset(g.cases), g.grid)
                         for g in entry.output.groups]):
        return got, GroupsKept()
    among = [c for c, _g in outcomes]
    old: list[tuple[frozenset["Case"], GroupGrid]] = []
    unheld = 0
    for g in entry.output.groups:
        listed: set["Case"] = set()
        for n in g.cases:
            denoted = denoted_cases(solver, n, among)
            if isinstance(denoted, NameFault) or not denoted:
                unheld += 1
            else:
                listed |= denoted
        old.append((frozenset(listed), g.grid))
    new = [(frozenset(members(outcomes, g)), g) for g in groups.groups]
    if unheld or {cs for cs, _g in old} != {cs for cs, _g in new}:
        was = {c for cs, _g in old for c in cs}
        return got, PartitionChanged(len(set(among) - was), unheld)
    held = _listing(old)
    moved = tuple(g.cases for cs, g in new if (cs, g.grid) not in held)
    if not moved:
        return got, NamesRewritten()
    return got, GridChanged(moved)


def with_grids(file: WitnessFile, grid_names: frozenset[str]) -> WitnessFile:
    """`file` with each `assign` value of a name in `grid_names`, a
    parameter stored as a grid, read as a grid where it has a grid's shape
    (solver-file.md, under "Witness file"), and as facts otherwise
    (`assign_with_grids`)."""
    entries = tuple(replace(e, assign=assign_with_grids(e.assign, grid_names))
                    for e in file.entries)
    return replace(file, entries=entries)


def _json_arg(arg: AssignArg) -> object:
    return [_json_arg(a) for a in arg] if isinstance(arg, tuple) else arg


def assign_json(assign: Sequence[tuple[str, AssignValue]]
                ) -> dict[str, Any]:
    """An `assign` value in the witness file's JSON form."""
    return {name: _assign_value_json(v) for name, v in assign}


def _assign_value_json(value: AssignValue) -> object:
    match value:
        case AssignRows(rows=rows):
            return [[_json_arg(a) for a in row] for row in rows]
        case AnchoredGrid(grid=grid, anchor=(r, c)):
            return {"grid": grid_lists(grid), "anchor": [r, c]}
        case _:
            return grid_lists(value)


def _json_entry(e: Entry) -> dict[str, Any]:
    out: dict[str, Any] = {"id": e.id, "separates": e.separates,
                           "input": grid_lists(e.input)}
    if e.assign:
        out["assign"] = assign_json(e.assign)
    match e.output:
        case RejectedOutput(grid=grid):
            out["output"] = grid_lists(grid)
        case Groups(groups=groups):
            out["output"] = [{"cases": list(g.cases),
                              "grid": _json_group_grid(g.grid)}
                             for g in groups]
    return out


def _json_group_grid(grid: GroupGrid) -> object:
    match grid:
        case Undefined():
            return None
        case Resolutions(grids=grids):
            return [grid_lists(g) for g in grids]
        case _:
            return grid_lists(grid)


def text(file: WitnessFile) -> str:
    """The file's text, in the layout every witness file takes
    (`arc.jsonio.format_file`: one grid row per line)."""
    return format_file({"id": file.task_id,
                        "witnesses": [_json_entry(e) for e in file.entries]})


def _merged_text(at: Path, task_id: str, entries: Sequence[Entry],
                 removed: Sequence[str] = ()
                 ) -> tuple[str | None, str] | list[Fault]:
    """The file's text at `at` (None where no file is there) and the text
    with `entries` put into it (`put`) and the entries of the ids
    `removed` taken out (`remove`); the file's problems where it is off
    its shape, an entry with no id among them (`read`), so every entry
    the merge meets has one."""
    held_text: str | None = None
    data: dict[str, Any] = {"id": task_id, "witnesses": []}
    if at.exists():
        held_text = at.read_text()
        on_disk, problems = read(held_text, WitnessFileRole.TASK)
        if on_disk is None or problems:
            return list(problems)
        data = json.loads(held_text)
    kept: list[dict[str, Any]] = [e for e in data["witnesses"]
                                  if e["id"] not in removed]
    data["witnesses"] = kept
    for entry in entries:
        ids = [e["id"] for e in kept]
        if entry.id in ids:
            kept[ids.index(entry.id)] = _json_entry(entry)
        else:
            kept.append(_json_entry(entry))
    return held_text, format_file(data)


def put_changed(at: Path, task_id: str, entries: Sequence[Entry]
                ) -> bool | tuple[Fault, ...]:
    """`put`, where the text it writes differs from the file's: whether
    the file was written, or the file's problems where it is off its
    shape. The text differs where an entry's content, or the order of
    its groups or of their cases, is not the writer's."""
    at.parent.mkdir(parents=True, exist_ok=True)
    return _write_merged(at, task_id, entries, (), True)


def remove(at: Path, task_id: str, ids: Sequence[str]) -> tuple[Fault, ...]:
    """Take the entries of `ids` out of the witness file at `at` and
    write it, as `put` writes, the other entries keeping their text. A
    file that is off the shape is not written, and its problems are
    returned."""
    got = _write_merged(at, task_id, (), ids, False)
    return () if isinstance(got, bool) else got


def put(at: Path, task_id: str, entries: Sequence[Entry]
        ) -> tuple[Fault, ...]:
    """Put `entries` into the witness file at `at` and write it: each
    replaces the entry of its id where one stands, and follows the last
    entry otherwise; a file that is not there is created. The file is read
    and written under a lock on its directory, so writers of one file at
    the same time each keep their entries, and the text goes to a file
    beside it that then replaces it, so a write that stops part way leaves
    the file as it was. The entries it does not put keep their text as the
    layout gives it. A file there that is off the shape is not written,
    and its problems are returned."""
    at.parent.mkdir(parents=True, exist_ok=True)
    got = _write_merged(at, task_id, entries, (), False)
    return () if isinstance(got, bool) else got


def _write_merged(at: Path, task_id: str, entries: Sequence[Entry],
                  removed: Sequence[str], only_changed: bool
                  ) -> bool | tuple[Fault, ...]:
    """The file at `at` merged with `entries` and without the entries of
    the ids `removed` (`_merged_text`), read and written under a lock on
    its directory, and written whole (`write_whole`): whether it was
    written, which it is not where `only_changed` holds and the text is
    the file's; the file's problems where it is off its shape."""
    lock = os.open(at.parent, os.O_RDONLY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        got = _merged_text(at, task_id, entries, removed)
        if isinstance(got, list):
            return tuple(got)
        held_text, text = got
        if only_changed and text == held_text:
            return False
        write_whole(at, text.encode())
        return True
    finally:
        os.close(lock)
