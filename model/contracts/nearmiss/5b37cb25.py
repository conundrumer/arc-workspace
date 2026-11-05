"""Near-miss readings for ARC task 5b37cb25."""
import json
from collections import Counter
from pathlib import Path

DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


def _copy(g):
    return [row[:] for row in g]


def _edges(inp):
    h, w = len(inp), len(inp[0])
    return {"up": inp[0][w // 2], "down": inp[h - 1][w // 2],
            "left": inp[h // 2][0], "right": inp[h // 2][w - 1]}


def _ground(inp):
    h, w = len(inp), len(inp[0])
    c = Counter(inp[r][q] for r in range(1, h - 1) for q in range(1, w - 1))
    return c.most_common(1)[0][0]


def _bites(inp, out):
    """List of (center_row, center_col, open_direction, true_color)."""
    h, w = len(inp), len(inp[0])
    g = _ground(inp)
    diff = {(r, c) for r in range(h) for c in range(w) if inp[r][c] != out[r][c]}
    res = []
    for (r, c) in sorted(diff):
        if not all((r + dr, c + dc) in diff for dr, dc in DIRS.values()):
            continue
        opens = []
        for name, (dr, dc) in DIRS.items():
            br, bc = r + 2 * dr, c + 2 * dc
            inside = 1 <= br < h - 1 and 1 <= bc < w - 1
            if (not inside) or inp[br][bc] == g:
                opens.append(name)
        if len(opens) == 1:
            res.append((r, c, opens[0], out[r][c]))
    return res


def _cross(r, c, skip=None):
    cells = [(r, c)] + [(r + dr, c + dc) for n, (dr, dc) in DIRS.items() if n != skip]
    return cells


def _paint(base, cells, color):
    for (r, c) in cells:
        base[r][c] = color


def _recolor(inp, out, colorfn, cellsfn=None, select=None):
    bs = _bites(inp, out)
    if not bs:
        return None
    res = _copy(inp)
    e = _edges(inp)
    for i, (r, c, d, col) in enumerate(bs):
        if select is not None and not select(i, len(bs), d):
            continue
        cells = cellsfn(r, c, d) if cellsfn else _cross(r, c)
        _paint(res, cells, colorfn(e, d, r, c, inp))
    return res


OPP = {"up": "down", "down": "up", "left": "right", "right": "left"}


def opposite_edge(inp, out):
    return _recolor(inp, out, lambda e, d, r, c, g: e[OPP[d]])


def center_only(inp, out):
    return _recolor(inp, out, lambda e, d, r, c, g: e[d], lambda r, c, d: [(r, c)])


def skip_open_arm(inp, out):
    return _recolor(inp, out, lambda e, d, r, c, g: e[d], lambda r, c, d: _cross(r, c, skip=d))


def nearest_edge(inp, out):
    h, w = len(inp), len(inp[0])

    def col(e, d, r, c, g):
        dist = {"up": r, "down": h - 1 - r, "left": c, "right": w - 1 - c}
        return e[min(dist, key=lambda k: dist[k])]
    return _recolor(inp, out, col)


def vertical_only(inp, out):
    return _recolor(inp, out, lambda e, d, r, c, g: e[d],
                    select=lambda i, n, d: d in ("up", "down"))


def first_only(inp, out):
    return _recolor(inp, out, lambda e, d, r, c, g: e[d], select=lambda i, n, d: i == 0)


def ray_to_edge(inp, out):
    h, w = len(inp), len(inp[0])
    gr = _ground(inp)

    def cells(r, c, d):
        dr, dc = DIRS[d]
        res = _cross(r, c)
        rr, cc = r + 2 * dr, c + 2 * dc
        while 1 <= rr < h - 1 and 1 <= cc < w - 1 and inp[rr][cc] == gr:
            res.append((rr, cc))
            rr += dr
            cc += dc
        return res
    return _recolor(inp, out, lambda e, dd, r, c, g: e[dd], cells)


def fill_with_blob(inp, out):
    h, w = len(inp), len(inp[0])

    def col(e, d, r, c, g):
        for dd, (dr, dc) in DIRS.items():
            if dd != d:
                return g[r + 2 * dr][c + 2 * dc] if 0 <= r + 2 * dr < h and 0 <= c + 2 * dc < w else g[r][c]
    return _recolor(inp, out, col, lambda r, c, d: _cross(r, c, skip=d))


def swapped_axes(inp, out):
    m = {"up": "left", "down": "right", "left": "up", "right": "down"}
    return _recolor(inp, out, lambda e, d, r, c, g: e[m[d]])


def square_3x3(inp, out):
    cells = lambda r, c, d: [(r + a, c + b) for a in (-1, 0, 1) for b in (-1, 0, 1)]
    return _recolor(inp, out, lambda e, d, r, c, g: e[d], cells)


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("paint each bite with the edge colour on the opposite side", opposite_edge),
    ("paint only the centre cell of each bite", center_only),
    ("leave the arm outside the blob unpainted", skip_open_arm),
    ("colour each bite by the nearest border edge, not its open side", nearest_edge),
    ("paint only bites that open up or down", vertical_only),
    ("paint only the first bite in reading order", first_only),
    ("extend the paint in a ray from the open side to the interior limit", ray_to_edge),
    ("fill each bite with the surrounding blob colour", fill_with_blob),
    ("swap the axes when choosing the edge colour (up uses left, left uses up)", swapped_axes),
    ("paint a full 3x3 square around each bite centre", square_3x3),
    ("return the input unchanged", unchanged),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/5b37cb25.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs), "bites", [len(_bites(p["input"], p["output"])) for p in pairs])
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            if (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                    and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
                    and g != p["output"]):
                ok += 1
        print(ok, len(pairs), desc)
