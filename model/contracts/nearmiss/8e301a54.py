import json
from pathlib import Path


def _bg(g):
    cnt = {}
    for r in g:
        for v in r:
            cnt[v] = cnt.get(v, 0) + 1
    return max(cnt, key=cnt.get)


def _cells(g):
    bg = _bg(g)
    by = {}
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v != bg:
                by.setdefault(v, []).append((r, c))
    return bg, by


def _shift(inp, dist, drow=1, dcol=0, keep=lambda col, cells: False, clamp=False):
    """Move every colour's cells by dist(col, cells) steps along (drow, dcol)."""
    bg, by = _cells(inp)
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    for col, cells in by.items():
        k = 0 if keep(col, cells) else dist(col, cells)
        for r, c in cells:
            nr, nc = r + drow * k, c + dcol * k
            if clamp:
                nr = min(max(nr, 0), h - 1)
                nc = min(max(nc, 0), w - 1)
            if 0 <= nr < h and 0 <= nc < w:
                g[nr][nc] = col
    return g


def up(inp, out):
    return _shift(inp, lambda c, s: len(s), drow=-1)


def right(inp, out):
    return _shift(inp, lambda c, s: len(s), drow=0, dcol=1)


def size_minus_one(inp, out):
    return _shift(inp, lambda c, s: len(s) - 1)


def size_plus_one(inp, out):
    return _shift(inp, lambda c, s: len(s) + 1)


def one_step(inp, out):
    return _shift(inp, lambda c, s: 1)


def height_distance(inp, out):
    return _shift(inp, lambda c, s: max(r for r, _ in s) - min(r for r, _ in s) + 1)


def anchor_five(inp, out):
    return _shift(inp, lambda c, s: len(s), keep=lambda c, s: c == 5)


def only_largest(inp, out):
    _, by = _cells(inp)
    m = max(len(s) for s in by.values())
    return _shift(inp, lambda c, s: len(s), keep=lambda c, s: len(s) < m)


def small_stay(inp, out):
    return _shift(inp, lambda c, s: len(s), keep=lambda c, s: len(s) < 3)


def ghost(inp, out):
    g = [row[:] for row in out]
    bg = _bg(inp)
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v != bg and g[r][c] == bg:
                g[r][c] = v
    return g


def fall_to_floor(inp, out):
    bg, by = _cells(inp)
    h = len(inp)
    g = [[bg] * len(inp[0]) for _ in range(h)]
    for col, cells in by.items():
        k = h - 1 - max(r for r, _ in cells)
        for r, c in cells:
            g[r + k][c] = col
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("shapes move up instead of down", up),
    ("shapes move right instead of down", right),
    ("shapes move by cell count minus one", size_minus_one),
    ("shapes move by cell count plus one", size_plus_one),
    ("every shape moves exactly one step down", one_step),
    ("shapes move by their row extent instead of cell count", height_distance),
    ("colour 5 is treated as fixed and does not move", anchor_five),
    ("only the largest shape moves", only_largest),
    ("shapes with fewer than 3 cells stay in place", small_stay),
    ("shapes move to the grid floor", fall_to_floor),
    ("true output with the original shape cells left behind", ghost),
    ("input returned unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/8e301a54.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
