import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    """Cutting lines, line color and the mark on each line crossing."""
    h, w = len(inp), len(inp[0])
    lr = [r for r in range(h) if all(v != 0 for v in inp[r])]
    lc = [c for c in range(w) if all(inp[r][c] != 0 for r in range(h))]
    cnt = Counter(inp[r][c] for r in lr for c in range(w))
    line = cnt.most_common(1)[0][0]
    marks = {}
    for i, r in enumerate(lr):
        for j, c in enumerate(lc):
            if inp[r][c] != line:
                marks[(i, j)] = inp[r][c]
    return lr, lc, line, marks


def _corners(i, j):
    return [(i, j), (i, j + 1), (i + 1, j), (i + 1, j + 1)]


def _box(marks):
    if not marks:
        return None
    ii = [p[0] for p in marks]
    jj = [p[1] for p in marks]
    return min(ii), max(ii), min(jj), max(jj)


def _tile_grid(tiles, box):
    """tiles: dict (i, j) -> color; box: (i0, i1, j0, j1) tile range, inclusive."""
    i0, i1, j0, j1 = box
    return [[tiles.get((i, j), 0) for j in range(j0, j1 + 1)] for i in range(i0, i1 + 1)]


def _marks_tile_box(marks):
    b = _box(marks)
    if b is None:
        return None
    return b[0], b[1] - 1, b[2], b[3] - 1


def _true_tiles(marks):
    t = {}
    if not marks:
        return t
    i0, i1, j0, j1 = _box(marks)
    for i in range(i0, i1):
        for j in range(j0, j1):
            cs = [marks.get(p) for p in _corners(i, j)]
            if None not in cs and len(set(cs)) == 1:
                t[(i, j)] = cs[0]
    return t


def any_corner(inp, out):
    lr, lc, line, marks = _parse(inp)
    box = _marks_tile_box(marks)
    t = {}
    for i in range(box[0], box[1] + 1):
        for j in range(box[2], box[3] + 1):
            cs = [marks[p] for p in _corners(i, j) if p in marks]
            if cs:
                t[(i, j)] = cs[0]
    return _tile_grid(t, box)


def mixed_ok(inp, out):
    lr, lc, line, marks = _parse(inp)
    box = _marks_tile_box(marks)
    t = {}
    for i in range(box[0], box[1] + 1):
        for j in range(box[2], box[3] + 1):
            cs = [marks.get(p) for p in _corners(i, j)]
            if None not in cs:
                t[(i, j)] = cs[0]
    return _tile_grid(t, box)


def top_edge_only(inp, out):
    lr, lc, line, marks = _parse(inp)
    box = _marks_tile_box(marks)
    t = {}
    for i in range(box[0], box[1] + 1):
        for j in range(box[2], box[3] + 1):
            a, b = marks.get((i, j)), marks.get((i, j + 1))
            if a is not None and a == b:
                t[(i, j)] = a
    return _tile_grid(t, box)


def full_tiling(inp, out):
    lr, lc, line, marks = _parse(inp)
    t = _true_tiles(marks)
    return _tile_grid(t, (0, len(lr) - 2, 0, len(lc) - 2))


def three_of_four(inp, out):
    lr, lc, line, marks = _parse(inp)
    box = _marks_tile_box(marks)
    t = {}
    for i in range(box[0], box[1] + 1):
        for j in range(box[2], box[3] + 1):
            cs = [marks.get(p) for p in _corners(i, j)]
            c, n = Counter(x for x in cs if x is not None).most_common(1)[0] if any(x is not None for x in cs) else (0, 0)
            if n >= 3:
                t[(i, j)] = c
    return _tile_grid(t, box)


def flip_horizontal(inp, out):
    return [row[::-1] for row in out]


def padded_one_tile(inp, out):
    w = len(out[0])
    return [[0] * (w + 2)] + [[0] + row + [0] for row in out] + [[0] * (w + 2)]


def drop_last(inp, out):
    return [row[:-1] for row in out[:-1]]


def node_grid(inp, out):
    lr, lc, line, marks = _parse(inp)
    i0, i1, j0, j1 = _box(marks)
    return [[marks.get((i, j), 0) for j in range(j0, j1 + 1)] for i in range(i0, i1 + 1)]


def flip_vertical(inp, out):
    return [row[:] for row in out[::-1]]


def transpose(inp, out):
    return [list(r) for r in zip(*out)]


def single_color(inp, out):
    cnt = Counter(v for row in out for v in row if v != 0)
    if not cnt:
        return None
    c = cnt.most_common(1)[0][0]
    return [[c if v else 0 for v in row] for row in out]


def line_color_fill(inp, out):
    lr, lc, line, marks = _parse(inp)
    return [[line if v else 0 for v in row] for row in out]


ALTERNATIVES = [
    ("a tile is filled when any one corner is marked (first mark in reading order), not all four", any_corner),
    ("a tile is filled when all four corners are marked even with different colors, using the top-left color", mixed_ok),
    ("a tile is filled when its top two corners carry the same mark color", top_edge_only),
    ("the output covers every tile between cutting lines, not just the marks' box", full_tiling),
    ("a tile is filled when at least three corners carry the same mark color", three_of_four),
    ("the output has an extra empty tile ring around the marks' box", padded_one_tile),
    ("the output is one tile short in each direction", drop_last),
    ("the output lists the marks at line crossings, one cell per crossing, not per tile", node_grid),
    ("the output is flipped top to bottom", flip_vertical),
    ("the output is transposed", transpose),
    ("every filled tile takes the most common mark color", single_color),
    ("filled tiles take the cutting-line color", line_color_fill),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/7837ac64.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
