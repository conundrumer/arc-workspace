import json
from pathlib import Path


def _geom(inp, out):
    h, w = len(inp), len(inp[0])
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == 5]
    r0 = min(r for r, c in cells) + 1
    r1 = max(r for r, c in cells) - 1
    c0 = min(c for r, c in cells) + 1
    c1 = max(c for r, c in cells) - 1
    main = out[r0][c0]  # color on the top-left / bottom-right quadrants
    anti = out[r0][c1]  # color on the top-right / bottom-left quadrants
    return h, w, r0, r1, c0, c1, main, anti


def _copy(g):
    return [row[:] for row in g]


def _paint(inp, out, fn, base="out"):
    """Rebuild the interior as fn(r, c, rr, cc, main, anti) over a copy of out or inp."""
    h, w, r0, r1, c0, c1, main, anti = _geom(inp, out)
    g = _copy(out if base == "out" else inp)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            g[r][c] = fn(r - r0, c - c0, r1 - r0 + 1, c1 - c0 + 1, main, anti)
    return g


def swap_colors(inp, out):
    return _paint(inp, out, lambda r, c, H, W, m, a: a if ((r >= H // 2) == (c >= W // 2)) else m)


def one_quadrant_per_mark(inp, out):
    # only the quadrant each mark sits in is filled (no opposite quadrant)
    h, w, r0, r1, c0, c1, main, anti = _geom(inp, out)
    g = _copy(inp)
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v in (0, 5):
                continue
            top = r < (r0 + r1) / 2
            left = c < (c0 + c1) / 2
            for rr in range(r0, r1 + 1):
                for cc in range(c0, c1 + 1):
                    if (rr < (r0 + r1) / 2) == top and (cc < (c0 + c1) / 2) == left:
                        g[rr][cc] = v
    return g


def checkerboard_cells(inp, out):
    return _paint(inp, out, lambda r, c, H, W, m, a: m if (r + c) % 2 == 0 else a)


def fill_with_first_mark(inp, out):
    h, w, r0, r1, c0, c1, main, anti = _geom(inp, out)
    for r in range(h):
        for c in range(w):
            if inp[r][c] not in (0, 5):
                col = inp[r][c]
                return _paint(inp, out, lambda *_a: col)


def left_right_split(inp, out):
    return _paint(inp, out, lambda r, c, H, W, m, a: m if c < W // 2 else a)


def top_bottom_split(inp, out):
    return _paint(inp, out, lambda r, c, H, W, m, a: m if r < H // 2 else a)


def only_main_diagonal_cells(inp, out):
    # single-cell diagonals instead of 2x2 quadrant blocks
    h, w, r0, r1, c0, c1, main, anti = _geom(inp, out)
    g = _copy(inp)
    n = r1 - r0 + 1
    for i in range(n):
        g[r0 + i][c0 + i] = main
        g[r0 + i][c1 - i] = anti
    return g


def paint_over_wall(inp, out):
    # quadrant blocks cover the wall box too (interior taken as the whole box)
    h, w, r0, r1, c0, c1, main, anti = _geom(inp, out)
    g = _copy(out)
    R0, R1, C0, C1 = r0 - 1, r1 + 1, c0 - 1, c1 + 1
    H, W = R1 - R0 + 1, C1 - C0 + 1
    for r in range(R0, R1 + 1):
        for c in range(C0, C1 + 1):
            g[r][c] = main if ((r - R0 >= H // 2) == (c - C0 >= W // 2)) else anti
    return g


def erase_marks(inp, out):
    g = _copy(out)
    for r in range(len(g)):
        for c in range(len(g[0])):
            if inp[r][c] not in (0, 5):
                g[r][c] = 0
    return g


def leave_one_quadrant_empty(inp, out):
    h, w, r0, r1, c0, c1, main, anti = _geom(inp, out)
    g = _copy(out)
    for r in range((r0 + r1 + 1) // 2, r1 + 1):
        for c in range((c0 + c1 + 1) // 2, c1 + 1):
            g[r][c] = 0
    return g


def crop_interior(inp, out):
    h, w, r0, r1, c0, c1, main, anti = _geom(inp, out)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def wall_recolored(inp, out):
    # walls take the first mark color as well
    h, w, r0, r1, c0, c1, main, anti = _geom(inp, out)
    g = _copy(out)
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 5:
                g[r][c] = main
    return g


ALTERNATIVES = [
    ("quadrant colors swapped: each mark paints the diagonal it is not on", swap_colors),
    ("each mark fills only its own quadrant, no opposite quadrant", one_quadrant_per_mark),
    ("single-cell checkerboard instead of 2x2 quadrant blocks", checkerboard_cells),
    ("whole interior filled with the first mark's color", fill_with_first_mark),
    ("interior split left/right between the two mark colors", left_right_split),
    ("interior split top/bottom between the two mark colors", top_bottom_split),
    ("only the two one-cell diagonals are drawn", only_main_diagonal_cells),
    ("quadrant pattern spans the whole wall box and overwrites the wall", paint_over_wall),
    ("marks outside the wall are erased after painting", erase_marks),
    ("one quadrant of the pattern left unfilled", leave_one_quadrant_empty),
    ("output is only the cropped interior", crop_interior),
    ("wall recolored with the quadrant color", wall_recolored),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/94414823.json"))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if (g is not None and g and isinstance(g, list)
                    and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
                    and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
                    and g != p["output"]):
                ok += 1
        print(ok, "/", len(pairs), desc)
