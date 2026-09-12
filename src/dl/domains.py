"""Candidate value domains for a parameter, by declared type."""

import re

from dl.paths import PROGRAMS_DIR

ENUM_TYPES = {
    "Dir": "DIR_", "Axis": "AXIS_", "DiagDir": "DIAG_",
    "DiagAxis": "DAXIS_", "D4": "D4_", "Sense": "SENSE_", "Sym": "SYM_",
}

POSITION_TYPES = {"Box", "Position", "Offset"}
MAG_POSITION_TYPES = {"Box", "Offset"}


def _lib_defines() -> dict[str, int]:
    """Constant-name -> value from lib.dl's #define table."""
    text = (PROGRAMS_DIR / "lib.dl").read_text()
    return {m.group(1): int(m.group(2))
            for m in re.finditer(r"^#define (\w+)\s+(\d+)", text, flags=re.MULTILINE)}


def _enum_domain(type_name: str, defines: dict[str, int]) -> list[int]:
    prefix = ENUM_TYPES[type_name]
    return sorted(v for k, v in defines.items() if k.startswith(prefix))


def _known_grids(task) -> list[list[list[int]]]:
    """The grids known at produce time: train pairs and test inputs."""
    return [g for ex in task.train for g in (ex.input, ex.output)] + [
        ex.input for ex in task.test
    ]


def _color_domain(task) -> list[int]:
    """Colors present in the known grids."""
    colors: set[int] = set()
    for grid in _known_grids(task):
        for row in grid:
            colors.update(row)
    return sorted(colors)


def _number_domain(task) -> list[int]:
    """0..max known grid dimension — the range of task-shape numbers."""
    dims = [
        d
        for grid in _known_grids(task)
        for d in (len(grid), len(grid[0]) if grid else 0)
    ]
    return list(range(max(dims) + 1))


def _move_domain(vals: list[tuple]) -> set[tuple]:
    """Positions with a stored value's edge-pair sums (t+b, l+r): the
    other cells of its frame."""
    out = set()
    sums = {(v[0] + v[1], v[2] + v[3]) for v in vals}
    for sv, sh in sums:
        group = [v for v in vals if (v[0] + v[1], v[2] + v[3]) == (sv, sh)]
        ts = [0, sv] + [v[0] for v in group] + [v[1] for v in group]
        ls = [0, sh] + [v[2] for v in group] + [v[3] for v in group]
        for t in range(min(ts), max(ts) + 1):
            for l in range(min(ls), max(ls) + 1):
                out.add((t, sv - t, l, sh - l))
    return out


def _position_domain(
    type_name: str, vals: list[tuple], nums: list[int]
) -> list[tuple]:
    """Candidate values for a Box-record parameter, by declared reading.

    Position (frame cell) — moves: the other cells of the stored frame.

    Offset (translation) — the antisymmetric
    grid: both free components ranged over `nums` and negations.

    Box (independent edge margins) — moves
    (redistributions of a depth across an edge pair) plus per-component
    lines over `nums` and negations with the other three fixed at stored.
    """
    line = sorted(set(nums) | {-n for n in nums})
    if type_name == "Offset":
        comps = {c for v in vals for c in v}
        span = sorted(set(line) | comps | {-c for c in comps})
        return sorted((t, -t, l, -l) for t in span for l in span)
    out = _move_domain(vals)
    if type_name == "Box":
        for v in vals:
            for i in range(4):
                for n in line:
                    out.add(v[:i] + (n,) + v[i + 1:])
    return sorted(out)
