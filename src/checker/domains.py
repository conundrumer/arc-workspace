"""A parameter's candidate values, by the declared type of each column, and
a value as the sweep, drop-one and the determination plan print it."""

import itertools
from collections.abc import Iterable, Sequence
from enum import StrEnum

from arc.task import Task
from engine import RecordValue, Row, Value
from engine.program import grid_size, offset_place
from solver.model import Lib
from solver.run_parts import row_key, value_key
from solver.vocabulary import BOX, COLOR, NUMBER, OFFSET

MAGNITUDE_TYPES = frozenset({BOX, OFFSET})
"""The Box types whose fields are magnitudes, not a cell's place."""


class ColumnDomain(StrEnum):
    """What a column's candidate domain ranges over."""

    ORIENTATION = "orientation"
    COLOR = "color"
    NUMBER = "number"
    POSITION = "position"


def column_domain(type_name: str, lib: Lib) -> ColumnDomain | None:
    """What a column's candidate domain ranges over, by its type: the
    members of an orientation type (principles.md, "Orientation"), the
    colors of the known grids, the numbers up to the largest grid
    dimension, or the values a Box record's stored values imply; None for
    a type no domain enumerates."""
    if type_name in lib.orientation_types:
        return ColumnDomain.ORIENTATION
    if type_name == COLOR:
        return ColumnDomain.COLOR
    if type_name == NUMBER:
        return ColumnDomain.NUMBER
    if type_name in lib.box_types:
        return ColumnDomain.POSITION
    return None


def enumerable(types: Sequence[str], lib: Lib) -> bool:
    """Each column has a candidate domain."""
    return all(column_domain(t, lib) is not None for t in types)


def _known_grids(task: Task) -> list[list[list[int]]]:
    """The grids known at produce time: the train pairs and the test
    inputs."""
    return [g for ex in task.train for g in (ex.input, ex.output)] + [
        ex.input for ex in task.test]


def colors(grids: Iterable[Sequence[Sequence[int]]]) -> frozenset[int]:
    """The colors `grids` hold."""
    return frozenset(c for g in grids for row in g for c in row)


def color_domain(task: Task) -> list[Value]:
    """The colors the known grids hold."""
    return list(sorted(colors(_known_grids(task))))


def number_domain(task: Task) -> list[int]:
    """0 up to the largest dimension of a known grid."""
    dims = [d for g in _known_grids(task) for d in grid_size(g)]
    return list(range(max(dims, default=0) + 1))


def orientation_domain(type_name: str, lib: Lib) -> list[Value]:
    """The values of the orientation type's members, sorted."""
    members = lib.orientation_types[type_name]
    unvalued = [m for m in members if m not in lib.constants]
    if unvalued:
        raise ValueError(f"the lib gives no value to {', '.join(unvalued)}")
    return sorted((lib.constants[m] for m in members), key=value_key)


def _ints(v: Value) -> tuple[int, ...]:
    assert isinstance(v, RecordValue)
    return tuple(f for f in v.fields if isinstance(f, int))


def _move_domain(vals: list[tuple[int, ...]]) -> set[tuple[int, ...]]:
    """The places with a stored value's edge-pair sums: the other cells of
    its frame."""
    out: set[tuple[int, ...]] = set()
    sums = {(v[0] + v[1], v[2] + v[3]) for v in vals}
    for sv, sh in sums:
        group = [v for v in vals if (v[0] + v[1], v[2] + v[3]) == (sv, sh)]
        ts = [0, sv] + [v[0] for v in group] + [v[1] for v in group]
        ls = [0, sh] + [v[2] for v in group] + [v[3] for v in group]
        for t in range(min(ts), max(ts) + 1):
            for l in range(min(ls), max(ls) + 1):
                out.add((t, sv - t, l, sh - l))
    return out


def position_domain(type_name: str, stored: list[Value], nums: list[int]
                    ) -> list[Value]:
    """The candidates of a Box-record column: for a place, the other cells
    of the stored frame; for an Offset, both free components over the
    numbers and their negations; for a Box, the moves plus each field over
    the numbers and their negations with the others at stored."""
    vals = [_ints(v) for v in stored]
    line = sorted(set(nums) | {-n for n in nums})
    if type_name == OFFSET:
        comps = {c for v in vals for c in v}
        span = sorted(set(line) | comps | {-c for c in comps})
        return [RecordValue(offset_place(t, l)) for t in span for l in span]
    out = _move_domain(vals)
    if type_name == BOX:
        for v in vals:
            for i in range(4):
                for n in line:
                    out.add(v[:i] + (n,) + v[i + 1:])
    return [RecordValue(v) for v in sorted(out)]


def candidate_rows(domains: Sequence[Sequence[Value]], stored: Sequence[Row]
                   ) -> list[Row]:
    """A parameter's candidate rows: each row of its columns' domains
    (`param_domains`), and its stored rows, in row order."""
    return sorted(set(itertools.product(*domains)) | set(stored),
                  key=row_key)


def param_domains(types: Sequence[str], stored: Sequence[Row], task: Task,
                  lib: Lib) -> list[list[Value]]:
    """Each column's candidate domain, in column order. Raises
    `ValueError` for a column no domain enumerates."""
    out: list[list[Value]] = []
    for i, t in enumerate(types):
        match column_domain(t, lib):
            case ColumnDomain.ORIENTATION:
                out.append(orientation_domain(t, lib))
            case ColumnDomain.COLOR:
                out.append(color_domain(task))
            case ColumnDomain.NUMBER:
                out.append(list(number_domain(task)))
            case ColumnDomain.POSITION:
                out.append(position_domain(t, [s[i] for s in stored],
                                           number_domain(task)))
            case None:
                raise ValueError(f"no domain enumerates a `{t}` column")
    return out
