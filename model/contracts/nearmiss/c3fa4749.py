import json
from collections import Counter
from pathlib import Path

N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
N8 = N4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _comps(h, w, ok, nbrs):
    seen = {}
    comps = []
    for r in range(h):
        for c in range(w):
            if (r, c) in seen or not ok(r, c):
                continue
            idx = len(comps)
            stack = [(r, c)]
            seen[(r, c)] = idx
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in nbrs:
                    a, b = y + dy, x + dx
                    if 0 <= a < h and 0 <= b < w and (a, b) not in seen and ok(a, b):
                        seen[(a, b)] = idx
                        stack.append((a, b))
            comps.append(cells)
    return comps


def _pockets(g, k=6, adj8=False):
    """Return list of dicts for every walled pocket: cells, mouths, wall regions, block color."""
    h, w = len(g), len(g[0])
    nb = N8 if adj8 else N4
    regs = _comps(h, w, lambda r, c: True, nb) if False else None
    # same-color regions
    seen = {}
    regions = []
    for r in range(h):
        for c in range(w):
            if (r, c) in seen:
                continue
            col = g[r][c]
            idx = len(regions)
            stack = [(r, c)]
            seen[(r, c)] = idx
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in nb:
                    a, b = y + dy, x + dx
                    if 0 <= a < h and 0 <= b < w and (a, b) not in seen and g[a][b] == col:
                        seen[(a, b)] = idx
                        stack.append((a, b))
            regions.append(cells)
    block = {i for i, cs in enumerate(regions) if len(cs) >= k}
    comps = _comps(h, w, lambda r, c: seen[(r, c)] not in block, nb)
    out = []
    for cs in comps:
        cset = set(cs)
        wall = set()
        for (y, x) in cs:
            for dy, dx in nb:
                a, b = y + dy, x + dx
                if 0 <= a < h and 0 <= b < w and (a, b) not in cset:
                    wall.add(seen[(a, b)])
        mouths = [(y, x) for (y, x) in cs if y in (0, h - 1) or x in (0, w - 1)]
        bcol = g[regions[next(iter(wall))][0][0]][regions[next(iter(wall))][0][1]] if wall else None
        out.append({"cells": cs, "mouths": mouths, "wall": wall, "bcol": bcol})
    return out


def _paint(g, cells, col):
    o = [row[:] for row in g]
    for (y, x) in cells:
        o[y][x] = col
    return o


def _solve(g, k=6, adj8=False, pick=None, post=None):
    """Reference rule with switches. Fills every pocket walled by one block region."""
    o = [row[:] for row in g]
    ps = [p for p in _pockets(g, k, adj8) if len(p["wall"]) == 1 and p["mouths"]]
    for p in ps:
        col = pick(g, p) if pick else (g[p["mouths"][0][0]][p["mouths"][0][1]] if len(p["mouths"]) == 1 else None)
        if col is None:
            continue
        cells = post(g, p) if post else p["cells"]
        for (y, x) in cells:
            if 0 <= y < len(g) and 0 <= x < len(g[0]):
                o[y][x] = col
    return o


# --- wrong readings -------------------------------------------------------

def a_block_color(inp, out):
    return _solve(inp, pick=lambda g, p: p["bcol"] if len(p["mouths"]) == 1 else None)


def a_small_k(inp, out):
    return _solve(inp, k=3)


def a_keep_block_cells(inp, out):
    o = [row[:] for row in out]
    for p in _pockets(inp):
        if len(p["wall"]) == 1 and len(p["mouths"]) == 1:
            for (y, x) in p["cells"]:
                if inp[y][x] == p["bcol"]:
                    o[y][x] = inp[y][x]
    return o


def a_majority_color(inp, out):
    def pick(g, p):
        if len(p["mouths"]) != 1:
            return None
        return Counter(g[y][x] for (y, x) in p["cells"]).most_common(1)[0][0]
    return _solve(inp, pick=pick)


def a_bbox(inp, out):
    def post(g, p):
        ys = [y for y, _ in p["cells"]]
        xs = [x for _, x in p["cells"]]
        return [(y, x) for y in range(min(ys), max(ys) + 1) for x in range(min(xs), max(xs) + 1)]
    return _solve(inp, post=post)


def a_dilate(inp, out):
    def post(g, p):
        s = set(p["cells"])
        for (y, x) in p["cells"]:
            for dy, dx in N4:
                s.add((y + dy, x + dx))
        return s
    return _solve(inp, post=post)


def a_skip_largest(inp, out):
    ps = [p for p in _pockets(inp) if len(p["wall"]) == 1 and len(p["mouths"]) == 1]
    if len(ps) < 2:
        return None
    big = max(ps, key=lambda p: len(p["cells"]))
    o = [row[:] for row in out]
    for (y, x) in big["cells"]:
        o[y][x] = inp[y][x]
    return o


def a_only_largest(inp, out):
    ps = [p for p in _pockets(inp) if len(p["wall"]) == 1 and len(p["mouths"]) == 1]
    if len(ps) < 2:
        return None
    big = max(ps, key=lambda p: len(p["cells"]))
    p = ps[ps.index(big)]
    return _paint(inp, p["cells"], inp[p["mouths"][0][0]][p["mouths"][0][1]])


def a_far_end_color(inp, out):
    def pick(g, p):
        if len(p["mouths"]) != 1:
            return None
        my, mx = p["mouths"][0]
        y, x = max(p["cells"], key=lambda c: abs(c[0] - my) + abs(c[1] - mx))
        return g[y][x]
    return _solve(inp, pick=pick)


def a_ray_only(inp, out):
    def post(g, p):
        my, mx = p["mouths"][0]
        h, w = len(g), len(g[0])
        if mx in (0, w - 1):
            return [(y, x) for (y, x) in p["cells"] if y == my]
        return [(y, x) for (y, x) in p["cells"] if x == mx]
    return _solve(inp, post=post)


def a_grid_common_color(inp, out):
    c = Counter(v for r in inp for v in r).most_common(1)[0][0]
    return _solve(inp, pick=lambda g, p: c if len(p["mouths"]) == 1 else None)


def a_enclosed_too(inp, out):
    o = [row[:] for row in out]
    found = False
    for p in _pockets(inp):
        if len(p["wall"]) == 1 and not p["mouths"]:
            col = Counter(inp[y][x] for (y, x) in p["cells"]).most_common(1)[0][0]
            for (y, x) in p["cells"]:
                o[y][x] = col
                found = found or o[y][x] != out[y][x]
    return o if found else None


ALTERNATIVES = [
    ("pockets are filled with the color of the block that walls them", a_block_color),
    ("a pocket is filled with the color of its cell farthest from the mouth", a_far_end_color),
    ("only the pocket cells in the mouth's row or column are filled", a_ray_only),
    ("a block region needs only 3 cells, so small random patches count as blocks", a_small_k),
    ("every pocket is filled with the most common color of the whole input", a_grid_common_color),
    ("block-colored cells inside a pocket stay unchanged; only the other pocket cells are filled", a_keep_block_cells),
    ("a pocket is filled with the most common color of its own cells", a_majority_color),
    ("the whole bounding box of each pocket is filled", a_bbox),
    ("each pocket is filled one cell wider on every side", a_dilate),
    ("the largest pocket is left unfilled", a_skip_largest),
    ("only the largest pocket is filled", a_only_largest),
    ("a pocket that touches no border cell is also filled, with its own majority color", a_enclosed_too),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/c3fa4749.json"))
    pairs = task["train"]
    ref_ok = [_solve(p["input"]) == p["output"] for p in pairs]
    print("reference rule reproduces outputs:", ref_ok)
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                g = None
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
