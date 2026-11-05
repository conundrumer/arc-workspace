import json
from collections import Counter
from pathlib import Path


def mark_cells(inp):
    cnt = Counter(v for row in inp for v in row if v)
    if not cnt:
        return []
    col = min(cnt, key=lambda c: (cnt[c], c))
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == col]


def build(inp, rad=2, dy=0, dx=0, line="bottom", stem=True, top=5, bot=8,
          side=2, line_color=2, keep_mark=True, line_span="full"):
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    marks = mark_cells(inp)
    if not marks:
        return None
    mc = inp[marks[0][0]][marks[0][1]]

    def put(r, c, v):
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = v

    for (r, c) in marks:
        r += dy
        c += dx
        # line first, bracket over it
        if line in ("bottom", "top"):
            lr = r + rad if line == "bottom" else r - rad
            for cc in range(w):
                if line_span == "left" and cc > c:
                    continue
                if line_span == "right" and cc < c:
                    continue
                put(lr, cc, line_color)
        elif line in ("left", "right"):
            lc = c - rad if line == "left" else c + rad
            for rr in range(h):
                put(rr, lc, line_color)
        for k in range(-rad, rad + 1):
            put(r - rad, c + k, top)
            put(r + rad, c + k, bot)
        for rr in range(r - rad + 1, r + rad):
            put(rr, c - rad, side)
            put(rr, c + rad, side)
        if stem:
            for rr in range(r - rad + 1, r):
                put(rr, c, top)
        if keep_mark:
            put(r, c, mc)
    return g


def make(**kw):
    def f(inp, out):
        return build(inp, **kw)
    return f


def line_only(inp, out):
    g = [row[:] for row in inp]
    for (r, c) in mark_cells(inp):
        if r + 2 < len(g):
            g[r + 2] = [2] * len(g[0])
    return g


def bracket_only(inp, out):
    g = [row[:] for row in out]
    for (r, c) in mark_cells(inp):
        lr = r + 2
        if lr < len(g):
            for cc in range(len(g[0])):
                if not (c - 2 <= cc <= c + 2):
                    g[lr][cc] = inp[lr][cc]
    return g


def line_stops_at_bracket(inp, out):
    g = [row[:] for row in out]
    for (r, c) in mark_cells(inp):
        lr = r + 2
        for cc in range(len(g[0])):
            if cc > c + 2:
                g[lr][cc] = inp[lr][cc]
    return g


def bottom_row_all_line_color(inp, out):
    g = [row[:] for row in out]
    for (r, c) in mark_cells(inp):
        for cc in range(c - 2, c + 3):
            g[r + 2][cc] = 2
    return g


def hollow_no_sides(inp, out):
    g = [row[:] for row in out]
    for (r, c) in mark_cells(inp):
        for rr in range(r - 1, r + 2):
            for cc in (c - 2, c + 2):
                g[rr][cc] = inp[rr][cc]
    return g


def swap_top_bottom_colors(inp, out):
    g = [row[:] for row in out]
    for (r, c) in mark_cells(inp):
        for k in range(-2, 3):
            g[r - 2][c + k] = 8
            g[r + 2][c + k] = 5
    return g


ALTERNATIVES = [
    ("line only: the 2-line is drawn through the row two below the mark, no bracket", line_only),
    ("bracket only: no 2-line across the grid beyond the bracket", bracket_only),
    ("line stops at the bracket: only the left side of the line is drawn", line_stops_at_bracket),
    ("line runs along the top edge of the bracket instead of the bottom", make(line="top")),
    ("line runs vertically along the right edge of the bracket", make(line="right")),
    ("bracket is 3x3 (radius 1) instead of 5x5", make(rad=1)),
    ("bracket is centered one row lower than the mark", make(dy=1)),
    ("bracket is centered one column to the right of the mark", make(dx=1)),
    ("bracket has no 5 stem above the mark", make(stem=False)),
    ("bracket edge on the line row stays 2 instead of 8", bottom_row_all_line_color),
    ("bracket sides are missing; only top and bottom edges", hollow_no_sides),
    ("top and bottom edge colors are swapped (top 8, bottom 5)", swap_top_bottom_colors),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/3f23242b.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", repr(e))
                g = None
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))
            if ok and g != p["output"]:
                n += 1
        print(n, desc)
