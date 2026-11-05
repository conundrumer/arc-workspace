"""Near-miss readings for ARC task c61be7dc.

Rule: two parallel walls bound a corridor of odd width. The walls close to
the cells next to the corridor's center line. The shape (symmetric about a
cross line) becomes a line of the shape color on the center line, with as
many cells as the shape, centered on the cross line.
"""
import json
from collections import Counter
from pathlib import Path


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _parse(inp):
    """Return (flip, info) with walls normalized to vertical columns."""
    flip = False
    g = inp
    H, W = len(g), len(g[0])
    cnt = Counter(v for r in g for v in r)
    bg = cnt.most_common(1)[0][0]
    others = [(c, k) for k, c in cnt.items() if k != bg]
    others.sort(reverse=True)
    L, S = others[0][1], others[1][1]

    def full_cols(g):
        return [j for j in range(len(g[0])) if all(r[j] == L for r in g)]

    if len(full_cols(g)) < 2:
        g = _transpose(g)
        flip = True
    cols = full_cols(g)
    a, b = cols[0], cols[-1]
    H, W = len(g), len(g[0])
    cross = next(i for i in range(H) if g[i][0] == L)
    shape = [(i, j) for i in range(H) for j in range(W) if g[i][j] == S]
    return flip, dict(g=g, H=H, W=W, bg=bg, L=L, S=S, a=a, b=b, m=(a + b) // 2,
                      cross=cross, shape=shape, n=len(shape))


def _build(p, walls, linecol, r0, n, color, old_cross_gap=False, keep_shape=False):
    H, W, bg, L, S, a, b, m, c = (p[k] for k in
                                  ("H", "W", "bg", "L", "S", "a", "b", "m", "cross"))
    g = [[bg] * W for _ in range(H)]
    for j in walls:
        if 0 <= j < W:
            for i in range(H):
                g[i][j] = L
    for j in range(W):
        g[c][j] = L
    if old_cross_gap:
        for j in range(a + 1, b):
            g[c][j] = bg
    if keep_shape:
        for i, j in p["shape"]:
            g[i][j] = S
    for i in range(r0, r0 + n):
        if 0 <= i < H:
            g[i][linecol] = color
    return g


def _wrap(f):
    def inner(inp, out):
        flip, p = _parse(inp)
        g = f(p)
        return _transpose(g) if flip else g
    return inner


def _std(p, **kw):
    args = dict(walls=[p["m"] - 1, p["m"] + 1], linecol=p["m"],
                r0=p["cross"] - p["n"] // 2, n=p["n"], color=p["S"])
    args.update(kw)
    return _build(p, **args)


def walls_stay(p):
    return _std(p, walls=[p["a"], p["b"]])


def shape_stays(p):
    return _std(p, keep_shape=True)


def len_along_extent(p):
    rows = [i for i, _ in p["shape"]]
    return _std(p, n=max(rows) - min(rows) + 1,
                r0=p["cross"] - (max(rows) - min(rows)) // 2)


def len_corridor_width(p):
    w = p["b"] - p["a"] - 1
    return _std(p, n=w, r0=p["cross"] - w // 2)


def line_at_corridor_edge(p):
    return _std(p, linecol=p["a"] + 1)


def line_wall_color(p):
    return _std(p, color=p["L"])


def line_from_cross(p):
    return _std(p, r0=p["cross"])


def cross_gap(p):
    g = _std(p)
    for j in range(p["a"] + 1, p["b"]):
        if j != p["m"]:
            g[p["cross"]][j] = p["bg"]
    return g


def old_walls_kept(p):
    return _std(p, walls=[p["a"], p["b"], p["m"] - 1, p["m"] + 1])


def walls_too_wide(p):
    return _std(p, walls=[p["m"] - 2, p["m"] + 2])


def line_shifted_one(p):
    return _std(p, r0=p["cross"] - p["n"] // 2 + 1)


def unchanged(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("walls stay at their old lines and the corridor is not closed", _wrap(walls_stay)),
    ("walls close but the shape stays as it was instead of becoming a line", _wrap(shape_stays)),
    ("line length is the shape's extent along the corridor, not its cell count", _wrap(len_along_extent)),
    ("line length is the corridor width, not the shape's cell count", _wrap(len_corridor_width)),
    ("line is drawn on the corridor's first column, not its center line", _wrap(line_at_corridor_edge)),
    ("line takes the wall color instead of the shape color", _wrap(line_wall_color)),
    ("line starts at the cross line and runs one way, not centered on it", _wrap(line_from_cross)),
    ("cross line is dropped inside the old corridor", _wrap(cross_gap)),
    ("old walls are not erased when the new walls are drawn", _wrap(old_walls_kept)),
    ("new walls sit two cells from the center line instead of one", _wrap(walls_too_wide)),
    ("line is centered one cell off the cross line", _wrap(line_shifted_one)),
    ("output equals the input", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/c61be7dc.json"))
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, f in ALTERNATIVES:
        ok = 0
        for pair in train:
            g = f(pair["input"], pair["output"])
            if g is not None and _valid(g) and g != pair["output"]:
                ok += 1
        print(f"{ok}/{len(train)}  {desc}")
