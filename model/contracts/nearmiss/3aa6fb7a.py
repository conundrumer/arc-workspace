import json
from pathlib import Path

BG = 0
INK = 8
FILL = 1


def _copy(g):
    return [list(r) for r in g]


def _holes(inp):
    """Empty cells that complete a 2x2 box holding exactly three ink cells."""
    h, w = len(inp), len(inp[0])
    res = []
    for r in range(h - 1):
        for c in range(w - 1):
            cells = [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)]
            ink = [p for p in cells if inp[p[0]][p[1]] == INK]
            if len(ink) == 3:
                hole = [p for p in cells if inp[p[0]][p[1]] != INK][0]
                if inp[hole[0]][hole[1]] == BG:
                    res.append((hole, ink))
    return res


def _components(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != BG and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                comp = []
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = y + dy, x + dx
                            if (0 <= ny < h and 0 <= nx < w and inp[ny][nx] != BG
                                    and (ny, nx) not in seen):
                                seen.add((ny, nx))
                                stack.append((ny, nx))
                comps.append(comp)
    return comps


def _count(inp, r, c, dirs):
    h, w = len(inp), len(inp[0])
    n = 0
    for dy, dx in dirs:
        y, x = r + dy, c + dx
        if 0 <= y < h and 0 <= x < w and inp[y][x] != BG:
            n += 1
    return n


ORTH = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def recolor_fill(color):
    def f(inp, out):
        g = _copy(out)
        for r, row in enumerate(g):
            for c, v in enumerate(row):
                if v == FILL:
                    g[r][c] = color
        return g
    return f


def ink_color_fill(inp, out):
    return recolor_fill(INK)(inp, out)


def wrong_color(inp, out):
    return recolor_fill(2)(inp, out)


def mark_elbow_ink(inp, out):
    # marks the ink cell at the elbow of each L instead of the empty cell
    g = _copy(inp)
    for hole, ink in _holes(inp):
        hr, hc = hole
        for (r, c) in ink:
            if abs(r - hr) == 1 and abs(c - hc) == 1:
                g[r][c] = FILL
    return g


def skip_last(inp, out):
    holes = _holes(inp)
    if len(holes) < 2:
        return None
    g = _copy(out)
    (r, c), _ = holes[-1]
    g[r][c] = BG
    return g


def skip_first(inp, out):
    holes = _holes(inp)
    if len(holes) < 2:
        return None
    g = _copy(out)
    (r, c), _ = holes[0]
    g[r][c] = BG
    return g


def diag_touch(inp, out):
    # any empty cell with an ink cell on a diagonal (misses the 3-cell condition)
    g = _copy(inp)
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == BG and _count(inp, r, c, DIAG) >= 1:
                g[r][c] = FILL
    return g


def any_touching_empty(inp, out):
    # any empty cell with an ink neighbour in 8 directions
    g = _copy(inp)
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == BG and _count(inp, r, c, ORTH + DIAG) >= 1:
                g[r][c] = FILL
    return g


def box_grown_by_one(inp, out):
    # bounding box of each component grown by one cell on every side
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for comp in _components(inp):
        r0 = max(0, min(p[0] for p in comp) - 1)
        r1 = min(h - 1, max(p[0] for p in comp) + 1)
        c0 = max(0, min(p[1] for p in comp) - 1)
        c1 = min(w - 1, max(p[1] for p in comp) + 1)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if inp[r][c] == BG:
                    g[r][c] = FILL
    return g


def shifted_down(inp, out):
    # right cells, one row too low
    h = len(inp)
    g = _copy(inp)
    for (r, c), _ in _holes(inp):
        if r + 1 < h and g[r + 1][c] == BG:
            g[r + 1][c] = FILL
    return g


def shifted_right(inp, out):
    w = len(inp[0])
    g = _copy(inp)
    for (r, c), _ in _holes(inp):
        if c + 1 < w and g[r][c + 1] == BG:
            g[r][c + 1] = FILL
    return g


def box_overwrites_ink(inp, out):
    # whole 2x2 box of each L painted with the fill color
    g = _copy(inp)
    for hole, ink in _holes(inp):
        for r, c in ink + [hole]:
            g[r][c] = FILL
    return g


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def mirrored_hole(inp, out):
    # fill placed at the elbow's mirror image across the L's long axis end:
    # the hole cell reflected through the elbow ink cell, when inside the grid
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for (hr, hc), ink in _holes(inp):
        for (r, c) in ink:
            if abs(r - hr) == 1 and abs(c - hc) == 1:
                y, x = 2 * r - hr, 2 * c - hc
                if 0 <= y < h and 0 <= x < w and g[y][x] == BG:
                    g[y][x] = FILL
    return g


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("fill color is 2 instead of 1", wrong_color),
    ("fill color is the ink color 8", ink_color_fill),
    ("marks the ink cell at the elbow of each L instead of the empty cell", mark_elbow_ink),
    ("leaves the last L unfilled", skip_last),
    ("leaves the first L unfilled", skip_first),
    ("fills any empty cell with an ink cell on a diagonal", diag_touch),
    ("fills every empty cell touching ink in 8 directions", any_touching_empty),
    ("fills the empty cells in each shape's bounding box grown by one", box_grown_by_one),
    ("fill lands one row below the correct cell", shifted_down),
    ("fill lands one column right of the correct cell", shifted_right),
    ("paints the whole 2x2 box of each L, covering the ink", box_overwrites_ink),
    ("fill lands past the elbow, mirroring the empty cell through the elbow", mirrored_hole),
]


def _valid(g):
    return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/3aa6fb7a.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
