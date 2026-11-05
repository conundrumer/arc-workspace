import json
from collections import Counter
from pathlib import Path


def _parts(inp):
    """Return (bg, shape_color, marker_color, marker_cell) or None."""
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    others = sorted((n, c) for c, n in cnt.items() if c != bg)
    if len(others) < 2:
        return None
    m = others[0][1]
    s = others[-1][1]
    cell = next((i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == m)
    return bg, s, m, cell


def _copy(g):
    return [list(r) for r in g]


def keep_marker(inp, out):
    p = _parts(inp)
    if not p:
        return None
    g = _copy(out)
    g[p[3][0]][p[3][1]] = p[2]
    return g


def keep_shape_color(inp, out):
    p = _parts(inp)
    if not p:
        return None
    g = _copy(inp)
    g[p[3][0]][p[3][1]] = p[0]
    return g


def swap_colors(inp, out):
    p = _parts(inp)
    if not p:
        return None
    bg, s, m, _ = p
    return [[m if v == s else s if v == m else v for v in r] for r in inp]


def fill_background(inp, out):
    p = _parts(inp)
    if not p:
        return None
    m = p[2]
    return [[m for _ in r] for r in out]


def skip_last_shape_row(inp, out):
    p = _parts(inp)
    if not p:
        return None
    bg, s, m, _ = p
    rows = [i for i, r in enumerate(inp) if s in r]
    g = _copy(out)
    for j, v in enumerate(inp[rows[-1]]):
        if v == s:
            g[rows[-1]][j] = s
    return g


def skip_leftmost_shape_column(inp, out):
    p = _parts(inp)
    if not p:
        return None
    bg, s, m, _ = p
    c = min(j for r in inp for j, v in enumerate(r) if v == s)
    g = _copy(out)
    for i, r in enumerate(inp):
        if r[c] == s:
            g[i][c] = s
    return g


def fill_bounding_box(inp, out):
    p = _parts(inp)
    if not p:
        return None
    bg, s, m, _ = p
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == s]
    r0 = min(i for i, _ in cells); r1 = max(i for i, _ in cells)
    c0 = min(j for _, j in cells); c1 = max(j for _, j in cells)
    g = _copy(out)
    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            g[i][j] = m
    return g


def crop_to_shape(inp, out):
    p = _parts(inp)
    if not p:
        return None
    bg, s, m, _ = p
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == s]
    r0 = min(i for i, _ in cells); r1 = max(i for i, _ in cells)
    c0 = min(j for _, j in cells); c1 = max(j for _, j in cells)
    return [[m if inp[i][j] == s else bg for j in range(c0, c1 + 1)] for i in range(r0, r1 + 1)]


def flip_vertical(inp, out):
    return [list(r) for r in reversed(out)]


def shift_right(inp, out):
    p = _parts(inp)
    if not p:
        return None
    bg, s, m, _ = p
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    for i in range(h):
        for j in range(w):
            if inp[i][j] == s and j + 1 < w:
                g[i][j + 1] = m
    return g


def recolor_border_only(inp, out):
    p = _parts(inp)
    if not p:
        return None
    bg, s, m, _ = p
    h, w = len(inp), len(inp[0])
    g = _copy(out)
    for i in range(h):
        for j in range(w):
            if inp[i][j] != s:
                continue
            nb = [(i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)]
            edge = any(not (0 <= a < h and 0 <= b < w) or inp[a][b] != s for a, b in nb)
            if not edge:
                g[i][j] = s
    return g


ALTERNATIVES = [
    ("Shape is recolored but the marker cell stays in place", keep_marker),
    ("Marker is erased but the shape keeps its own color", keep_shape_color),
    ("Shape color and marker color are swapped", swap_colors),
    ("Whole grid is filled with the marker color", fill_background),
    ("Bottom row of the shape is left in its original color", skip_last_shape_row),
    ("Leftmost column of the shape is left in its original color", skip_leftmost_shape_column),
    ("Bounding box of the shape is filled with the marker color", fill_bounding_box),
    ("Output is cropped to the shape's bounding box", crop_to_shape),
    ("Output is flipped vertically", flip_vertical),
    ("Recolored shape is shifted one column right", shift_right),
    ("Only the shape's border cells are recolored, interior kept", recolor_border_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/aabf363d.json'))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in train:
            g = fn(pr["input"], pr["output"])
            if g is not None and _valid(g) and g != pr["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
