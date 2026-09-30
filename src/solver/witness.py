"""The witness file (solver-file.md:172-199), and the one place where a
name in it resolves to the model it denotes."""

import fcntl
import json
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from arc.jsonio import format_file
from engine import Grid, Value, checkout
from solver.problems import (
    Expected,
    InWitnessFile,
    ProblemKind,
    Fault,
    ShapeFault,
)

if TYPE_CHECKING:
    from solver.model import Case, Solver


@dataclass(frozen=True)
class NoOutput:
    """`out` holds no cell at the case (principles.md:49: the output is
    empty)."""


type Cell = tuple[int, int]
"""A cell of a grid, by row and column."""


@dataclass(frozen=True)
class MissingCells:
    """`out`'s cells at the case leave cells of their frame without a
    color: the grid is not total (principles.md:49)."""

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
    proposer gives it no value on the input (principles.md "Two
    parameterizations")."""

    parameter: str
    proposer: str


type UndefinedReason = (NoOutput | MissingCells | ConflictingCells
                        | NegativeEdges | InconsistentBounds | NoDerivedValue)


@dataclass(frozen=True)
class Undefined:
    """`null`: the cases are undefined on the input (solver-file.md:186).
    Two values are equal whatever their reasons, as a witness file's
    `null` states none; two outputs are the same output only where their
    reasons are equal too (`same_output`)."""

    reason: UndefinedReason | None = field(default=None, compare=False)
    """Why a run gives no grid; None for a witness file's `null`, which
    states no reason."""


@dataclass(frozen=True)
class Resolutions:
    """A list of grids, one per tiebreak resolution (solver-file.md:186,
    history 1119), and the resolution value of each where a run gave them;
    a witness file holds the grids alone."""

    grids: tuple[Grid, ...]
    values: tuple[Value, ...] = field(default=(), compare=False)


type GroupGrid = Grid | Resolutions | Undefined


@dataclass(frozen=True)
class Group:
    """`{cases, grid}`, solver-file.md:185-186."""

    cases: tuple[str, ...]
    grid: GroupGrid


@dataclass(frozen=True)
class Groups:
    """An `output` of groups, for a verdict that is not `other`
    (solver-file.md:181)."""

    groups: tuple[Group, ...]


@dataclass(frozen=True)
class RejectedOutput:
    """An `output` that is a bare grid, the judged output of an `other`
    verdict (solver-file.md:182)."""

    grid: Grid


type Output = Groups | RejectedOutput

type AssignArg = int | str | tuple["AssignArg", ...]
"""solver-file.md:188-191: a string for a lib constant, a list for a
record."""


@dataclass(frozen=True)
class AssignRows:
    rows: tuple[tuple[AssignArg, ...], ...]


type AssignValue = AssignRows | Grid


@dataclass(frozen=True)
class Entry:
    """One witness of the file, solver-file.md:176-182. `assign` holds
    each parameter or stored relation it reassigns (history 1131) in file
    order. (A file entry; the `@witness` comment line is
    `solver.annotations.WitnessLine`.)"""

    id: str
    separates: str
    input: Grid
    assign: tuple[tuple[str, AssignValue], ...]
    output: Output


@dataclass(frozen=True)
class WitnessFile:
    """`programs/witnesses/<task_id>.wit.json`, solver-file.md:173."""

    task_id: str
    entries: tuple[Entry, ...]


def path(task_id: str) -> Path:
    """`programs/witnesses/<task_id>.wit.json` (solver-file.md:173)."""
    return checkout.witnesses() / f"{task_id}.wit.json"


def read(text: str) -> tuple[WitnessFile | None, tuple[Fault, ...]]:
    """The witness file `text` states, None where its shape gives none,
    and what could not be read.

    An entry off the shape is left out, with a problem for each part off
    it; an unknown field and a repeated id are problems beside the entry
    they stand in. Every `assign` value reads as rows here: whether a
    value is a grid depends on the parameter it names, which the model
    settles (`with_grids`)."""
    problems: list[Fault] = []

    def off(entry: str | None, field: Path_, expected: Expected) -> None:
        problems.append(Fault(
            ProblemKind.WITNESS_FILE_SHAPE, InWitnessFile(entry),
            ShapeFault(field, expected)))

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

type Path_ = tuple[str | int, ...]
type Off = Callable[[str | None, Path_, Expected], None]


def _typed(value: dict[str, object], key: str, kind: type, entry: str | None,
           prefix: Path_, off: Off) -> object:
    """`value[key]` where it is of `kind`; otherwise None, and the fault:
    the field missing, or of another kind."""
    if key not in value:
        off(entry, (*prefix, key), Expected.PRESENT)
        return None
    got = value[key]
    if not isinstance(got, kind):
        off(entry, (*prefix, key),
            Expected.STRING if kind is str else Expected.LIST)
        return None
    return got


def _grid(value: object) -> Grid | None:
    """A rectangular, nonempty grid of colors 0 to 9, or None."""
    if not isinstance(value, list) or not value:
        return None
    rows: list[tuple[int, ...]] = []
    for row in cast(list[object], value):
        if not isinstance(row, list) or not row:
            return None
        cells = cast(list[object], row)
        if not all(type(c) is int and 0 <= c <= 9 for c in cells):
            return None
        rows.append(tuple(cast(list[int], cells)))
    if len({len(r) for r in rows}) != 1:
        return None
    return tuple(rows)


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


def same_output(a: GroupGrid, b: GroupGrid) -> bool:
    """Whether two cases give the same output: equal grids, or both
    undefined for the same reason at the same cells."""
    if isinstance(a, Undefined) and isinstance(b, Undefined):
        return a.reason == b.reason
    return a == b


def grouped(solver: "Solver", outcomes: Sequence[tuple["Case", GroupGrid]]
            ) -> Groups:
    """An entry's groups from what each of the solver's cases gives on its
    input: one group per distinct output (`same_output`), the group that
    holds the concept case first and the rest in the order the cases come
    in, naming its cases by the fewest names that denote exactly them
    (`solver.names.cover`; solver-file.md:185)."""
    from solver.model import is_concept
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
        not c.branches and is_concept(solver, c.base) for c in group[0]))
    return Groups(tuple(Group(cover(solver, cases, among), g)
                        for cases, g in out))


def with_grids(file: WitnessFile, grid_names: frozenset[str]
               ) -> tuple[WitnessFile, tuple[Fault, ...]]:
    """`file` with each `assign` value of a name in `grid_names`, a
    parameter stored as a grid, read as a grid where it has a grid's shape
    (solver-file.md:180, :192), and as facts otherwise; a value that is
    neither is the problem `read` gives."""
    problems: list[Fault] = []
    entries: list[Entry] = []
    for e in file.entries:
        assign: list[tuple[str, AssignValue]] = []
        for name, value in e.assign:
            if name in grid_names and isinstance(value, AssignRows):
                grid = _grid([list(r) for r in value.rows])
                if grid is not None:
                    value = grid
            assign.append((name, value))
        entries.append(replace(e, assign=tuple(assign)))
    return replace(file, entries=tuple(entries)), tuple(problems)


def _json_grid(grid: Grid) -> list[list[int]]:
    return [list(r) for r in grid]


def _json_arg(arg: AssignArg) -> object:
    return [_json_arg(a) for a in arg] if isinstance(arg, tuple) else arg


def _json_entry(e: Entry) -> dict[str, Any]:
    out: dict[str, Any] = {"id": e.id, "separates": e.separates,
                           "input": _json_grid(e.input)}
    if e.assign:
        out["assign"] = {
            name: (_json_grid(v) if not isinstance(v, AssignRows)
                   else [[_json_arg(a) for a in row] for row in v.rows])
            for name, v in e.assign}
    match e.output:
        case RejectedOutput(grid=grid):
            out["output"] = _json_grid(grid)
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
            return [_json_grid(g) for g in grids]
        case _:
            return _json_grid(grid)


def text(file: WitnessFile) -> str:
    """The file's text, in the layout every witness file takes
    (`arc.jsonio.format_file`: one grid row per line)."""
    return format_file({"id": file.task_id,
                        "witnesses": [_json_entry(e) for e in file.entries]})


def _merged_text(at: Path, task_id: str, entries: Sequence[Entry]
                 ) -> tuple[str | None, str] | list[Fault]:
    """The file's text at `at` (None where no file is there) and the text
    with `entries` put into it (`put`); the file's problems where it is
    off its shape, an entry with no id among them (`read`), so every
    entry the merge meets has one."""
    held_text: str | None = None
    data: dict[str, Any] = {"id": task_id, "witnesses": []}
    if at.exists():
        held_text = at.read_text()
        on_disk, problems = read(held_text)
        if on_disk is None or problems:
            return list(problems)
        data = json.loads(held_text)
    kept: list[dict[str, Any]] = data["witnesses"]
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
    lock = os.open(at.parent, os.O_RDONLY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        got = _merged_text(at, task_id, entries)
        if isinstance(got, list):
            return tuple(got)
        held_text, text = got
        if text == held_text:
            return False
        _replace(at, text)
        return True
    finally:
        os.close(lock)


def _replace(at: Path, text: str) -> None:
    """Write `text` to a file beside `at` that then replaces it."""
    tmp = at.with_name(f".{at.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text)
        os.replace(tmp, at)
    finally:
        tmp.unlink(missing_ok=True)


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
    lock = os.open(at.parent, os.O_RDONLY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        got = _merged_text(at, task_id, entries)
        if isinstance(got, list):
            return tuple(got)
        _replace(at, got[1])
        return ()
    finally:
        os.close(lock)
