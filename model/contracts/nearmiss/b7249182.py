import json
from pathlib import Path


def _dots(g):
    return [(r, c, v) for r, row in enumerate(g) for c, v in enumerate(row) if v != 0]


def _render(inp, depth=2, reach=2, stem=True, arms=True, swap=False, shift=0,
            fill=False, arms_out=False, only_first=False, bar=True, full_line=False):
    ds = _dots(inp)
    if len(ds) != 2:
        return None
    (r1, c1, v1), (r2, c2, v2) = ds
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    if r1 == r2:
        cells = [(r1, c) for c in range(c1, c2 + 1)]
        perp = (1, 0)
    elif c1 == c2:
        cells = [(r, c1) for r in range(r1, r2 + 1)]
        perp = (0, 1)
    else:
        return None
    n = len(cells)
    if n % 2:
        return None
    half = n // 2 + shift

    def put(r, c, v):
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = v

    if full_line:
        for i, (r, c) in enumerate(cells):
            put(r, c, v1 if i < n // 2 else v2)
        return g
    sides = [(cells[:half], v2 if swap else v1)]
    if not only_first:
        sides.append((cells[::-1][:n - half], v1 if swap else v2))
    for cs, col in sides:
        H = len(cs)
        ci = H - depth
        if ci < 0:
            continue
        if stem:
            for k in range(ci):
                put(*cs[k], col)
        if bar:
            cr, cc = cs[ci]
            for o in range(-reach, reach + 1):
                put(cr + perp[0] * o, cc + perp[1] * o, col)
        if arms:
            ks = range(0, ci + 1) if arms_out else range(ci, H)
            for k in ks:
                r, c = cs[k]
                for o in (-reach, reach):
                    put(r + perp[0] * o, c + perp[1] * o, col)
        if fill:
            for k in range(ci, H):
                r, c = cs[k]
                for o in range(-reach, reach + 1):
                    put(r + perp[0] * o, c + perp[1] * o, col)
    return g


def _drop_bar_side(inp, out):
    # keep the stems and bars, erase one arm per half: only the arm on the low side
    g = _render(inp)
    if g is None:
        return None
    ds = _dots(inp)
    (r1, c1, _), (r2, c2, _) = ds
    horiz = r1 == r2
    # remove cells strictly on the low-perpendicular side of the line
    for r in range(len(g)):
        for c in range(len(g[0])):
            if inp[r][c] == 0 and ((horiz and r > r1) or (not horiz and c > c1)):
                g[r][c] = 0
    return g


ALTERNATIVES = [
    ("box depth 1: the crossbar sits on the last cell of each half, with no arms",
     lambda i, o: _render(i, depth=1)),
    ("box depth 3: the stem stops one cell earlier than the true box",
     lambda i, o: _render(i, depth=3)),
    ("crossbar reaches only 1 cell to each side",
     lambda i, o: _render(i, reach=1)),
    ("crossbar reaches 3 cells to each side",
     lambda i, o: _render(i, reach=3)),
    ("crossbar without arms along the line",
     lambda i, o: _render(i, arms=False)),
    ("arms run from the crossbar back toward the dot instead of toward the middle",
     lambda i, o: _render(i, arms_out=True)),
    ("each half takes the color of the other dot",
     lambda i, o: _render(i, swap=True)),
    ("split point shifted by one cell: the first half is one cell longer",
     lambda i, o: _render(i, shift=1)),
    ("only the first dot's half is drawn",
     lambda i, o: _render(i, only_first=True)),
    ("the box is filled solid instead of left hollow",
     lambda i, o: _render(i, fill=True)),
    ("the dots are joined by a line in each half's color, with no box",
     lambda i, o: _render(i, full_line=True)),
    ("the box is drawn only on one side of the line (arms and bar on one side)",
     _drop_bar_side),
]


def _valid(g, truth):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
               for r in g for v in r):
        return False
    return g != truth


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/b7249182.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
