import json
from pathlib import Path

D4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def cast(inp, dirs=D4, color=4, block=(1,), overwrite=(0, 2), skip=(), gap=0,
         limit=None, band_block=False):
    """Draw rays from every 8 cell in dirs. Rays turn overwrite cells into color,
    stop at block cells, and pass over skip cells without painting."""
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == 8]
    stops = {}
    paint = []
    for dr, dc in dirs:
        for r0, c0 in cells:
            r, c = r0 + dr, c0 + dc
            while 0 <= r < h and 0 <= c < w and inp[r][c] == 8:
                r += dr
                c += dc
            n = 0
            cur = []
            while 0 <= r < h and 0 <= c < w:
                v = inp[r][c]
                n += 1
                if v in block:
                    stops[(dr, dc, r0 if dc else c0)] = n
                    break
                if limit is not None and n > limit:
                    break
                if n > gap and v in overwrite and v not in skip:
                    cur.append((r, c))
                r += dr
                c += dc
            paint.append(((dr, dc, r0 if dc else c0), cur))
    for key, cur in paint:
        for r, c in cur:
            g[r][c] = color
    return g


def true_cast(inp):
    return cast(inp)


def alt_through_ones(inp, out):
    return cast(inp, block=(), overwrite=(0, 1, 2))


def alt_stop_at_two(inp, out):
    return cast(inp, block=(1, 2))


def alt_keep_twos(inp, out):
    return cast(inp, overwrite=(0,))


def alt_horizontal_only(inp, out):
    return cast(inp, dirs=[(0, -1), (0, 1)])


def alt_vertical_only(inp, out):
    return cast(inp, dirs=[(-1, 0), (1, 0)])


def alt_down_right_only(inp, out):
    return cast(inp, dirs=[(1, 0), (0, 1)])


def alt_color_three(inp, out):
    return [[3 if v == 4 else v for v in row] for row in out]


def alt_color_eight(inp, out):
    return [[8 if v == 4 else v for v in row] for row in out]


def alt_one_blocks_whole_band(inp, out):
    # a 1 stops every ray of its band at that line
    h, w = len(inp), len(inp[0])
    g = cast(inp, block=(), overwrite=(0, 2))
    for dr, dc in D4:
        cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == 8]
        lim = {}
        for r0, c0 in cells:
            r, c = r0 + dr, c0 + dc
            while 0 <= r < h and 0 <= c < w and inp[r][c] == 8:
                r += dr
                c += dc
            while 0 <= r < h and 0 <= c < w:
                if inp[r][c] == 1:
                    lim[(r0, c0)] = (r, c)
                    break
                r += dr
                c += dc
        for (r0, c0), (rs, cs) in lim.items():
            for r1, c1 in cells:
                r, c = r1 + dr, c1 + dc
                while 0 <= r < h and 0 <= c < w:
                    beyond = (dr and (r - rs) * dr >= 0) or (dc and (c - cs) * dc >= 0)
                    if beyond and inp[r][c] != 8 and g[r][c] == 4:
                        g[r][c] = inp[r][c]
                    r += dr
                    c += dc
    return g


def alt_diagonals_added(inp, out):
    return cast(inp, dirs=D4 + DIAG)


def alt_short_rays(inp, out):
    return cast(inp, limit=3)


def alt_gap_one(inp, out):
    return cast(inp, gap=1)


ALTERNATIVES = [
    ("rays pass through 1 cells and overwrite them with 4", alt_through_ones),
    ("rays stop at the first 2 as well as at 1", alt_stop_at_two),
    ("rays leave 2 cells unchanged (only 0 cells become 4)", alt_keep_twos),
    ("rays go left and right only", alt_horizontal_only),
    ("rays go up and down only", alt_vertical_only),
    ("rays go down and right only", alt_down_right_only),
    ("ray color is 3 instead of 4", alt_color_three),
    ("ray color is 8 instead of 4", alt_color_eight),
    ("a 1 stops the whole band of rays beyond it, not just its own ray", alt_one_blocks_whole_band),
    ("rays also go along the four diagonals", alt_diagonals_added),
    ("rays are limited to 3 cells long", alt_short_rays),
    ("rays start one cell away from the 8 block (gap of one)", alt_gap_one),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/6ffe8f07.json").read_text())
    pairs = task["train"]
    assert all(true_cast(p["input"]) == p["output"] for p in pairs), "true rule check failed"
    print(len(ALTERNATIVES), "readings", len(pairs), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
