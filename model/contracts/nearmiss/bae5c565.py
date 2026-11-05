import json
from pathlib import Path


def _parse(inp):
    """Palette row is row 0; stalk is the column of 8 in the last row."""
    h, w = len(inp), len(inp[0])
    bg = inp[1][0]
    sc = next(c for c in range(w) if inp[h - 1][c] == 8)
    end = min(r for r in range(1, h) if inp[r][sc] == 8)
    return h, w, bg, sc, end


def _build(inp, start_of, color_of, keep_stalk=True, clear_palette=True, cols=None):
    """Background grid plus stalk; each non-stalk column fills from start_of(d)."""
    h, w, bg, sc, end = _parse(inp)
    g = [[bg] * w for _ in range(h)]
    if not clear_palette:
        g[0] = list(inp[0])
    if keep_stalk:
        for r in range(1, h):
            if inp[r][sc] == 8:
                g[r][sc] = 8
    for c in range(w):
        if c == sc or (cols is not None and not cols(c, sc)):
            continue
        d = abs(c - sc)
        for r in range(max(start_of(d, end), 0), h):
            g[r][c] = color_of(c, d)
    return g


def palette_left(inp, out):
    g = [list(r) for r in out]
    g[0] = list(inp[0])
    return g


def start_one_early(inp, out):
    return _build(inp, lambda d, e: e + d - 1, lambda c, d: inp[0][c])


def start_one_late(inp, out):
    return _build(inp, lambda d, e: e + d + 1, lambda c, d: inp[0][c])


def rectangle_from_stalk_end(inp, out):
    return _build(inp, lambda d, e: e, lambda c, d: inp[0][c])


def stop_short_of_edge(inp, out):
    h, w, bg, sc, end = _parse(inp)
    g = [list(r) for r in out]
    for c in range(w):
        if c != sc:
            g[h - 1][c] = bg
    return g


def colors_from_neighbor_column(inp, out):
    w = len(inp[0])
    return _build(inp, lambda d, e: e + d, lambda c, d: inp[0][min(c + 1, w - 1)])


def fill_with_stalk_color(inp, out):
    return _build(inp, lambda d, e: e + d, lambda c, d: 8)


def growing_staircase(inp, out):
    h, w, bg, sc, end = _parse(inp)
    m = max(abs(c - sc) for c in range(w))
    return _build(inp, lambda d, e: e + m - d, lambda c, d: inp[0][c])


def no_fill_only_clear_palette(inp, out):
    return _build(inp, lambda d, e: 10**6, lambda c, d: 0)


def staircase_on_palette_side(inp, out):
    h, w, bg, sc, end = _parse(inp)
    g = [[bg] * w for _ in range(h)]
    for r in range(1, h):
        if inp[r][sc] == 8:
            g[r][sc] = 8
    for c in range(w):
        if c == sc:
            continue
        height = h - (end + abs(c - sc))
        for r in range(0, max(height, 0)):
            g[r][c] = inp[0][c]
    return g


def stalk_dropped(inp, out):
    return _build(inp, lambda d, e: e + d, lambda c, d: inp[0][c], keep_stalk=False)


def fill_right_side_only(inp, out):
    return _build(inp, lambda d, e: e + d, lambda c, d: inp[0][c], cols=lambda c, s: c > s)


ALTERNATIVES = [
    ("palette row is left in place instead of cleared", palette_left),
    ("each column's fill starts one row too early", start_one_early),
    ("each column's fill starts one row too late", start_one_late),
    ("every column fills from the stalk's end row (rectangle, no staircase)", rectangle_from_stalk_end),
    ("fill stops one row short of the far edge", stop_short_of_edge),
    ("each column takes the palette color of its right-hand neighbor column", colors_from_neighbor_column),
    ("fill uses the stalk color instead of the palette colors", fill_with_stalk_color),
    ("staircase grows with distance from the stalk instead of shrinking", growing_staircase),
    ("palette is cleared and the stalk kept, but nothing is filled", no_fill_only_clear_palette),
    ("fill is the staircase on the palette side of the grid", staircase_on_palette_side),
    ("stalk is erased to background", stalk_dropped),
    ("only columns right of the stalk are filled", fill_right_side_only),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/bae5c565.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
