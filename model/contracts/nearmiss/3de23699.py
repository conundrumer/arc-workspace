"""Near-miss readings for ARC task 3de23699.

Rule: four same-colored corner markers frame a rectangle. The output is the
interior of that rectangle (corners excluded), with the cells of the other
colored shape repainted in the marker color.
"""
import json
from collections import Counter
from pathlib import Path


def _parts(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    cols = [c for c in cnt if c != bg]
    cells = {c: [(i, j) for i in range(h) for j in range(w) if inp[i][j] == c] for c in cols}

    def bbox(ps):
        return (min(p[0] for p in ps), min(p[1] for p in ps),
                max(p[0] for p in ps), max(p[1] for p in ps))

    marker = shape = None
    for c in cols:
        r0, c0, r1, c1 = bbox(cells[c])
        others = [o for o in cols if o != c]
        if all(r0 < i < r1 and c0 < j < c1 for o in others for i, j in cells[o]):
            marker = c
    shape = [c for c in cols if c != marker][0]
    return bg, marker, shape, bbox(cells[marker]), cells


def _crop(g, r0, c0, r1, c1):
    """Rows r0..r1 and cols c0..c1 inclusive; None when out of range or empty."""
    if r0 < 0 or c0 < 0 or r1 >= len(g) or c1 >= len(g[0]) or r1 < r0 or c1 < c0:
        return None
    return [row[c0:c1 + 1] for row in g[r0:r1 + 1]]


def _interior(inp, recolor=True, grow=0):
    bg, m, s, (r0, c0, r1, c1), _ = _parts(inp)
    g = [[(m if (recolor and v == s) else v) for v in row] for row in inp]
    return _crop(g, r0 + 1 - grow, c0 + 1 - grow, r1 - 1 + grow, c1 - 1 + grow)


def full_box_with_corners(inp, out):
    return _interior(inp, grow=1)


def keep_shape_color(inp, out):
    return _interior(inp, recolor=False)


def shape_tight_bbox(inp, out):
    bg, m, s, _, cells = _parts(inp)
    ps = cells[s]
    r0, r1 = min(p[0] for p in ps), max(p[0] for p in ps)
    c0, c1 = min(p[1] for p in ps), max(p[1] for p in ps)
    g = [[(m if v == s else v) for v in row] for row in inp]
    return _crop(g, r0, c0, r1, c1)


def shape_tight_bbox_original_color(inp, out):
    bg, m, s, _, cells = _parts(inp)
    ps = cells[s]
    r0, r1 = min(p[0] for p in ps), max(p[0] for p in ps)
    c0, c1 = min(p[1] for p in ps), max(p[1] for p in ps)
    return _crop(inp, r0, c0, r1, c1)


def inverted_fill(inp, out):
    bg, m, s, _, _ = _parts(inp)
    g = _interior(inp)
    return [[0 if v == m else m for v in row] for row in g]


def window_shifted_down_right(inp, out):
    bg, m, s, (r0, c0, r1, c1), _ = _parts(inp)
    g = [[(m if v == s else v) for v in row] for row in inp]
    return _crop(g, r0 + 2, c0 + 2, r1, c1)


def interior_missing_last_row_col(inp, out):
    bg, m, s, (r0, c0, r1, c1), _ = _parts(inp)
    g = [[(m if v == s else v) for v in row] for row in inp]
    return _crop(g, r0 + 1, c0 + 1, r1 - 2, c1 - 2)


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def mirrored(inp, out):
    return [row[::-1] for row in out]


def whole_interior_filled(inp, out):
    bg, m, s, _, _ = _parts(inp)
    g = _interior(inp)
    return [[m for _ in row] for row in g]


def largest_component_only(inp, out):
    bg, m, s, (r0, c0, r1, c1), cells = _parts(inp)
    left = set(cells[s])
    comps = []
    while left:
        st = [left.pop()]
        comp = set(st)
        while st:
            i, j = st.pop()
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (i + d[0], j + d[1])
                if q in left:
                    left.remove(q)
                    comp.add(q)
                    st.append(q)
        comps.append(comp)
    best = max(comps, key=len)
    g = [[(m if (i, j) in best else (0 if v == s else v)) for j, v in enumerate(row)]
         for i, row in enumerate(inp)]
    return _crop(g, r0 + 1, c0 + 1, r1 - 1, c1 - 1)


def input_unchanged(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("crop includes the four corner markers (box one cell larger on each side)", full_box_with_corners),
    ("crop the interior but leave the shape in its original color", keep_shape_color),
    ("crop to the tight bounding box of the shape, recolored", shape_tight_bbox),
    ("crop to the tight bounding box of the shape, original color", shape_tight_bbox_original_color),
    ("interior with colors swapped: empty cells get marker color, shape cells become 0", inverted_fill),
    ("interior window shifted one cell down and right", window_shifted_down_right),
    ("interior crop one row and one column too small at the bottom and right", interior_missing_last_row_col),
    ("correct output transposed", transposed),
    ("correct output mirrored left to right", mirrored),
    ("whole interior filled with the marker color", whole_interior_filled),
    ("keep only the largest connected piece of the shape", largest_component_only),
    ("output is the input unchanged", input_unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/3de23699.json'))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
