import json
from pathlib import Path

MARK = 8
FIELD = 3


def _cells(g, c):
    return [(r, k) for r, row in enumerate(g) for k, v in enumerate(row) if v == c]


def _norm(cells):
    r0 = min(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    return frozenset((r - r0, c - c0) for r, c in cells)


def _rot(cells):
    return _norm([(c, -r) for r, c in cells])


def _flip(cells):
    return _norm([(r, -c) for r, c in cells])


def _orients(shape):
    """Return (rotations without flip, rotations with flip) as lists of normalized shapes."""
    rots = []
    s = _norm(shape)
    for _ in range(4):
        if s not in rots:
            rots.append(s)
        s = _rot(s)
    flips = []
    s = _flip(_norm(shape))
    for _ in range(4):
        if s not in flips and s not in rots:
            flips.append(s)
        s = _rot(s)
    return rots, flips


def _place(g, shapes, field, skip=()):
    """All distinct cell sets where a shape from `shapes` lies wholly on `field` cells."""
    h, w = len(g), len(g[0])
    found = []
    for s in shapes:
        sh = max(r for r, _ in s) + 1
        sw = max(c for _, c in s) + 1
        for r in range(h - sh + 1):
            for c in range(w - sw + 1):
                cs = frozenset((r + a, c + b) for a, b in s)
                if all(g[y][x] == field for y, x in cs) and cs not in found:
                    found.append(cs)
    return found


def _paint(g, cells, color=MARK):
    o = [row[:] for row in g]
    for r, c in cells:
        if 0 <= r < len(o) and 0 <= c < len(o[0]):
            o[r][c] = color
    return o


def _setup(inp):
    shape = _cells(inp, MARK)
    rots, flips = _orients(shape)
    return shape, rots, flips


def _true_stamps(inp):
    _, rots, flips = _setup(inp)
    return _place(inp, rots + flips, FIELD)


def half_turn_only(inp, out):
    shape, _, _ = _setup(inp)
    s0 = _norm(shape)
    st = _place(inp, [s0, _rot(_rot(s0))], FIELD)
    return _paint(inp, [x for s in st for x in s])


def no_rotations(inp, out):
    shape, rots, flips = _setup(inp)
    s0 = _norm(shape)
    mirror = _flip(s0)
    st = _place(inp, [s0, mirror], FIELD)
    return _paint(inp, [x for s in st for x in s])


def rotations_only_quarter(inp, out):
    shape, rots, flips = _setup(inp)
    s = _rot(_norm(shape))
    st = _place(inp, [s], FIELD)
    return _paint(inp, [x for s in st for x in s])


def field_is_zero(inp, out):
    _, rots, flips = _setup(inp)
    st = _place(inp, rots + flips, 0)
    return _paint(inp, [x for s in st for x in s])


def field_is_most_common(inp, out):
    _, rots, flips = _setup(inp)
    counts = {}
    for row in inp:
        for v in row:
            counts[v] = counts.get(v, 0) + 1
    top = max(counts, key=lambda k: counts[k])
    st = _place(inp, rots + flips, top)
    return _paint(inp, [x for s in st for x in s])


def stamp_wrong_color(inp, out):
    st = _true_stamps(inp)
    return _paint(inp, [x for s in st for x in s], 7)


def first_occurrence_only(inp, out):
    st = _true_stamps(inp)
    if len(st) < 2:
        return None
    first = min(st, key=lambda s: min(s))
    return _paint(inp, first)


def move_not_copy(inp, out):
    shape, _, _ = _setup(inp)
    o = [row[:] for row in out]
    for r, c in shape:
        o[r][c] = FIELD
    return o


def fill_bounding_box(inp, out):
    st = _true_stamps(inp)
    cells = []
    for s in st:
        r0 = min(r for r, _ in s)
        r1 = max(r for r, _ in s)
        c0 = min(c for _, c in s)
        c1 = max(c for _, c in s)
        cells += [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
    return _paint(inp, cells)


def shifted_one_column(inp, out):
    st = _true_stamps(inp)
    return _paint(inp, [(r, c + 1) for s in st for r, c in s])


def isolated_only(inp, out):
    """Stamp only where the field-colored component is exactly the shape."""
    st = _true_stamps(inp)
    h, w = len(inp), len(inp[0])
    keep = []
    for s in st:
        ok = True
        for r, c in s:
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                y, x = r + dr, c + dc
                if 0 <= y < h and 0 <= x < w and (y, x) not in s and inp[y][x] == FIELD:
                    ok = False
        if ok:
            keep.append(s)
    return _paint(inp, [x for s in keep for x in s])


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


ALTERNATIVES = [
    ("copies only the shape and its half-turn, no quarter-turns", half_turn_only),
    ("copies only the shape and its mirror image, no 90-degree rotations", no_rotations),
    ("copies only a single quarter-turn of the shape", rotations_only_quarter),
    ("looks for the shape among 0 cells instead of 3 cells", field_is_zero),
    ("looks for the shape among the most common color instead of 3 cells", field_is_most_common),
    ("draws the copies in color 7 instead of the mark color", stamp_wrong_color),
    ("draws only the top-left copy", first_occurrence_only),
    ("moves the shape instead of copying it (original cells reset to 3)", move_not_copy),
    ("fills the bounding box of each copy instead of the shape cells", fill_bounding_box),
    ("draws each copy one column to the right of its true place", shifted_one_column),
    ("draws only copies not touching other 3 cells", isolated_only),
    ("returns the transposed true output", transposed),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/50f325b5.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (
                isinstance(g, list)
                and len(g) > 0
                and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
                and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
                and g != p["output"]
            )
            n += ok
        print(n, desc)
    # sanity: true stamps reproduce the output
    for p in pairs:
        assert _paint(p["input"], [x for s in _true_stamps(p["input"]) for x in s]) == p["output"]
