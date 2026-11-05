import json
from collections import Counter
from pathlib import Path


def _t(g):
    return [list(r) for r in zip(*g)]


def _parse(inp):
    """Find the two same-pattern monochrome lines; return the grid in a
    row frame (transposed when the lines are columns) and the task parts."""
    for tr in (False, True):
        G = _t(inp) if tr else [list(r) for r in inp]
        bg = Counter(v for r in G for v in r).most_common(1)[0][0]
        mono = {}
        for r, row in enumerate(G):
            pos = frozenset(c for c, v in enumerate(row) if v != bg)
            cols = {v for v in row if v != bg}
            if pos and len(cols) == 1:
                mono[r] = (pos, next(iter(cols)))
        rows = sorted(mono)
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if mono[a][0] == mono[b][0] and mono[a][1] != mono[b][1]:
                    cnt = Counter(v for row in G for v in row if v != bg)
                    sc = cnt.most_common(1)[0][0]
                    d, s = (a, b) if mono[a][1] == sc else (b, a)
                    return tr, G, bg, s, d, sc, mono[s][1]
    return None


def _shape(G, bg, d, sc):
    return [(r, c) for r, row in enumerate(G) for c, v in enumerate(row)
            if v == sc and r != d]


def _build(inp, place, color=None, base=None, keep=True):
    """Stamp shape cells on the row frame. place(r, c, s, d) -> (r2, c2)."""
    tr, G, bg, s, d, sc, pc = _parse(inp)
    H, W = len(G), len(G[0])
    R = [list(r) for r in (base if base is not None else G)]
    for r, c in _shape(G, bg, d, sc):
        r2, c2 = place(r, c, s, d)
        if 0 <= r2 < H and 0 <= c2 < W:
            R[r2][c2] = pc if color is None else color
    return _t(R) if tr else R


def _true(inp):
    return _build(inp, lambda r, c, s, d: (d - (r - s), c))


def _diff_cells(inp, out):
    return [(i, j) for i, row in enumerate(out) for j, v in enumerate(row)
            if inp[i][j] != v]


def a_shape_color(inp, out):
    tr, G, bg, s, d, sc, pc = _parse(inp)
    R = [list(r) for r in out]
    for i, j in _diff_cells(inp, out):
        R[i][j] = sc
    return R


def a_translate(inp, out):
    return _build(inp, lambda r, c, s, d: (d + (r - s), c))


def a_reflect_d(inp, out):
    return _build(inp, lambda r, c, s, d: (2 * d - r, c))


def a_off_by_one(inp, out):
    return _build(inp, lambda r, c, s, d: (d - (r - s) + 1, c))


def a_reflect_s(inp, out):
    return _build(inp, lambda r, c, s, d: (2 * s - r, c))


def a_drop_farthest(inp, out):
    tr, G, bg, s, d, sc, pc = _parse(inp)
    far = max(abs(r - s) for r, c in _shape(G, bg, d, sc))
    O = _t(out) if tr else [list(r) for r in out]
    for r, c in _shape(G, bg, d, sc):
        if abs(r - s) == far:
            O[d - (r - s)][c] = bg
    return _t(O) if tr else O


def a_bbox_fill(inp, out):
    tr, G, bg, s, d, sc, pc = _parse(inp)
    pts = [(d - (r - s), c) for r, c in _shape(G, bg, d, sc)]
    r0, r1 = min(p[0] for p in pts), max(p[0] for p in pts)
    c0, c1 = min(p[1] for p in pts), max(p[1] for p in pts)
    O = _t(out) if tr else [list(r) for r in out]
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            O[r][c] = pc
    return _t(O) if tr else O


def a_extra_copy(inp, out):
    tr, G, bg, s, d, sc, pc = _parse(inp)
    H, W = len(G), len(G[0])
    O = _t(out) if tr else [list(r) for r in out]
    for r, c in _shape(G, bg, d, sc):
        r2 = 2 * s - r
        if 0 <= r2 < H and G[r2][c] == bg:
            O[r2][c] = pc
    return _t(O) if tr else O


def a_recolor_source(inp, out):
    tr, G, bg, s, d, sc, pc = _parse(inp)
    O = _t(out) if tr else [list(r) for r in out]
    for r, c in _shape(G, bg, d, sc):
        O[r][c] = pc
    return _t(O) if tr else O


def a_unchanged(inp, out):
    return [list(r) for r in inp]


def a_shift_along(inp, out):
    return _build(inp, lambda r, c, s, d: (d - (r - s), c + 1))


ALTERNATIVES = [
    ("copy keeps the shape's own color instead of the marker line color", a_shape_color),
    ("copy is translated onto the other line without flipping", a_translate),
    ("shape is mirrored about the other line, not the marker line", a_reflect_d),
    ("copy is placed one cell too far from the other line", a_off_by_one),
    ("copy is drawn on the far side of the marker line, mirroring the shape in place", a_reflect_s),
    ("copy misses the cells farthest from the marker line", a_drop_farthest),
    ("copy region is filled solid over its bounding box", a_bbox_fill),
    ("copy is drawn on both lines (extra mirror about the marker line kept)", a_extra_copy),
    ("original shape is also recolored to the marker color", a_recolor_source),
    ("copy is shifted one cell along the line direction", a_shift_along),
    ("output equals the input", a_unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/66ac4c3b.json").read_text())
    train = task["train"]
    for p in train:
        assert _true(p["input"]) == p["output"], "reference reconstruction failed"
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
