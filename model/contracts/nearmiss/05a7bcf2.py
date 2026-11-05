"""Near-miss readings for ARC task 05a7bcf2.

Rule: an 8 wall spans the grid. Shapes of 4 on one side cast toward the wall:
their cells become 3 and the gap up to the wall becomes 4. The wall's 8 fill
runs from the wall to the far edge in those columns. The 2 structure on the far
side shifts rigidly to rest against the far edge (as 2, over the fill).
Each function below works in a normalized frame (wall is a row, far side is
below) and maps the result back.
"""
import json
from pathlib import Path

WALL, SHAPE, PUSH, MARK = 8, 4, 2, 3


def _t(g):
    return [list(r) for r in zip(*g)]


def _fl(g):
    return [list(r) for r in g[::-1]]


def _normalize(inp):
    ops = []
    g = [list(r) for r in inp]
    if not any(all(v == WALL for v in row) for row in g):
        g = _t(g)
        ops.append(_t)
    r = next(i for i, row in enumerate(g) if all(v == WALL for v in row))
    above = sum(v == PUSH for row in g[:r] for v in row)
    below = sum(v == PUSH for row in g[r + 1:] for v in row)
    if above > below:
        ops.append(_fl)
    return ops


def _apply(ops, g):
    g = [list(r) for r in g]
    for op in ops:
        g = op(g)
    return g


def _wrap(fn):
    def run(inp, out):
        ops = _normalize(inp)
        i, o = _apply(ops, inp), _apply(ops, out)
        r = next(k for k, row in enumerate(i) if all(v == WALL for v in row))
        h, w = len(i), len(i[0])
        fill = [c for c in range(w) if any(o[k][c] == WALL for k in range(r + 1, h))]
        res = fn(i, o, r, h, w, fill)
        if res is None:
            return None
        return _apply(list(reversed(ops)), res)
    return run


def _moved(o, r, h, fill):
    """Cells of the shifted 2 structure (in the fill columns, far side)."""
    return [(k, c) for c in fill for k in range(r + 1, h) if o[k][c] == PUSH]


def mark_as_shape(i, o, r, h, w, fill):
    return [[SHAPE if v == MARK else v for v in row] for row in o]


def gap_filled_with_mark(i, o, r, h, w, fill):
    return [[MARK if v == SHAPE else v for v in row] for row in o]


def gap_unfilled(i, o, r, h, w, fill):
    return [[0 if (v == SHAPE and i[k][c] == 0) else v for c, v in enumerate(row)]
            for k, row in enumerate(o)]


def fill_stops_at_wall(i, o, r, h, w, fill):
    res = [row[:] for row in o]
    for k in range(r + 1, h):
        res[k] = i[k][:]
    return res


def fill_all_columns(i, o, r, h, w, fill):
    res = [row[:] for row in o]
    for c in range(w):
        if c not in fill:
            for k in range(r + 1, h):
                if i[k][c] == 0:
                    res[k][c] = WALL
    return res


def push_stays(i, o, r, h, w, fill):
    res = [row[:] for row in o]
    for k, c in _moved(o, r, h, fill):
        res[k][c] = WALL
    for c in fill:
        for k in range(r + 1, h):
            if i[k][c] == PUSH:
                res[k][c] = PUSH
    return res


def push_removed(i, o, r, h, w, fill):
    res = [row[:] for row in o]
    for k, c in _moved(o, r, h, fill):
        res[k][c] = WALL
    return res


def push_one_short(i, o, r, h, w, fill):
    res = [row[:] for row in o]
    cells = _moved(o, r, h, fill)
    for k, c in cells:
        res[k][c] = WALL
    for k, c in cells:
        res[k - 1][c] = PUSH
    return res


def push_toward_wall(i, o, r, h, w, fill):
    res = [row[:] for row in o]
    cells = _moved(o, r, h, fill)
    if not cells:
        return None
    d = min(k for k, _ in cells) - (r + 1)
    for k, c in cells:
        res[k][c] = WALL
    for k, c in cells:
        res[k - d][c] = PUSH
    return res


def first_run_only(i, o, r, h, w, fill):
    if not fill:
        return None
    end = fill[0]
    while end + 1 in fill:
        end += 1
    res = [row[:] for row in o]
    for c in fill:
        if c > end:
            for k in range(h):
                res[k][c] = i[k][c]
    return res


def fill_with_shape_color(i, o, r, h, w, fill):
    return [[SHAPE if (k > r and v == WALL) else v for v in row]
            for k, row in enumerate(o)]


def unchanged(i, o, r, h, w, fill):
    return [row[:] for row in i]


ALTERNATIVES = [
    ("original shape cells recolored 4 instead of 3", _wrap(mark_as_shape)),
    ("gap between shape and wall filled with 3 instead of 4", _wrap(gap_filled_with_mark)),
    ("gap between shape and wall left empty", _wrap(gap_unfilled)),
    ("wall fill stops at the wall and does not reach the far side", _wrap(fill_stops_at_wall)),
    ("wall fill applied to every column, not only shape columns", _wrap(fill_all_columns)),
    ("2 structure stays in place instead of shifting to the far edge", _wrap(push_stays)),
    ("2 cells in the shape columns are overwritten by the fill instead of shifting", _wrap(push_removed)),
    ("2 structure stops one cell short of the far edge", _wrap(push_one_short)),
    ("2 structure shifts toward the wall instead of the far edge", _wrap(push_toward_wall)),
    ("only the first run of shape columns is processed", _wrap(first_run_only)),
    ("far-side fill uses the shape color 4 instead of the wall color", _wrap(fill_with_shape_color)),
    ("output equals the input", _wrap(unchanged)),
]


def _valid(g, ref):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r)
            and g != ref)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/05a7bcf2.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for name, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {name}")
