import json
from collections import Counter
from pathlib import Path

DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
CW = {"up": "right", "right": "down", "down": "left", "left": "up"}
OPP = {"up": "down", "down": "up", "left": "right", "right": "left"}


def box(inp):
    h, w = len(inp), len(inp[0])
    rows, cols = [], []
    for r in range(h):
        c, n = Counter(inp[r]).most_common(1)[0]
        if c != 0 and n >= w - 2:
            rows.append(r)
    for j in range(w):
        col = [inp[r][j] for r in range(h)]
        c, n = Counter(col).most_common(1)[0]
        if c != 0 and n >= h - 2:
            cols.append(j)
    return min(rows), max(rows), min(cols), max(cols)


def border_colors(inp, b):
    r0, r1, c0, c1 = b
    mid_r, mid_c = (r0 + r1) // 2, (c0 + c1) // 2
    return {"up": inp[r0][mid_c], "down": inp[r1][mid_c],
            "left": inp[mid_r][c0], "right": inp[mid_r][c1]}


def dots(inp, b):
    r0, r1, c0, c1 = b
    return [(r, c, inp[r][c]) for r in range(r0 + 1, r1) for c in range(c0 + 1, c1)
            if inp[r][c] != 0]


def crop(g, b):
    r0, r1, c0, c1 = b
    return [row[c0:c1 + 1] for row in g[r0:r1 + 1]]


def ray(g, b, r, c, d, col, stop_short=0):
    """Paint from (r,c) toward direction d until the border (exclusive), in g (full coords)."""
    r0, r1, c0, c1 = b
    dr, dc = DIRS[d]
    cells = []
    while r0 < r < r1 and c0 < c < c1:
        cells.append((r, c))
        r += dr
        c += dc
    if stop_short:
        cells = cells[:-stop_short]
    for (a, k) in cells:
        g[a][k] = col


def correct_dirs(inp, b):
    bc = border_colors(inp, b)
    return [(r, c, col, d) for (r, c, col) in dots(inp, b) for d in DIRS if bc[d] == col]


def solved_full(inp, b, dirmap=lambda d: d, stop_short=0):
    g = [row[:] for row in inp]
    for (r, c, col, d) in correct_dirs(inp, b):
        ray(g, b, r, c, dirmap(d), col, stop_short)
    return g


def alt_no_border_crop(inp, out):
    return [row[1:-1] for row in out[1:-1]]


def alt_oversize_box(inp, out):
    r0, r1, c0, c1 = box(inp)
    h, w = len(inp), len(inp[0])
    b2 = (max(r0 - 1, 0), min(r1 + 1, h - 1), max(c0 - 1, 0), min(c1 + 1, w - 1))
    g = solved_full(inp, box(inp))
    return crop(g, b2)


def alt_no_fill(inp, out):
    return crop(inp, box(inp))


def alt_opposite(inp, out):
    b = box(inp)
    return crop(solved_full(inp, b, lambda d: OPP[d]), b)


def alt_short_of_border(inp, out):
    b = box(inp)
    return crop(solved_full(inp, b, stop_short=1), b)


def alt_uncropped(inp, out):
    return solved_full(inp, box(inp))


def alt_all_directions(inp, out):
    b = box(inp)
    g = [row[:] for row in inp]
    for (r, c, col) in dots(inp, b):
        for d in DIRS:
            ray(g, b, r, c, d, col)
    return crop(g, b)


def alt_perpendicular(inp, out):
    b = box(inp)
    return crop(solved_full(inp, b, lambda d: CW[d]), b)


def alt_dot_extent(inp, out):
    b = box(inp)
    ds = dots(inp, b)
    r0, r1, c0, c1 = b
    rs = [r - r0 for r, _, _ in ds]
    cs = [c - c0 for _, c, _ in ds]
    if not ds:
        return None
    return [row[min(cs):max(cs) + 1] for row in out[min(rs):max(rs) + 1]]


def alt_transpose(inp, out):
    return [list(r) for r in zip(*out)]


def alt_ray_ignores_dot_blocking(inp, out):
    # Each ray is painted only from the dot nearest the border; farther dots in the same line are dropped.
    b = box(inp)
    r0, r1, c0, c1 = b
    g = [row[:] for row in inp]
    lines = {}
    for (r, c, col, d) in correct_dirs(inp, b):
        key = (d, c if d in ("up", "down") else r)
        dist = {"up": r - r0, "down": r1 - r, "left": c - c0, "right": c1 - c}[d]
        if key not in lines or dist < lines[key][0]:
            lines[key] = (dist, r, c, col, d)
    for (_, r, c, col, d) in lines.values():
        ray(g, b, r, c, d, col)
    for (r, c, col, d) in correct_dirs(inp, b):
        if (r, c) not in {(v[1], v[2]) for v in lines.values()}:
            g[r][c] = 0
    return crop(g, b)


def alt_half_ray(inp, out):
    # Each ray covers only the half of the distance nearest the dot.
    b = box(inp)
    g = [row[:] for row in inp]
    r0, r1, c0, c1 = b
    for (r, c, col, d) in correct_dirs(inp, b):
        dist = {"up": r - r0, "down": r1 - r, "left": c - c0, "right": c1 - c}[d]
        ray(g, b, r, c, d, col, stop_short=dist // 2)
    return crop(g, b)


ALTERNATIVES = [
    ("crop only the interior, dropping the divider border", alt_no_border_crop),
    ("crop one cell larger than the divider box on each side", alt_oversize_box),
    ("crop the divider box but cast no rays", alt_no_fill),
    ("rays go away from the matching border instead of toward it", alt_opposite),
    ("rays stop one cell short of the matching border", alt_short_of_border),
    ("rays drawn correctly but the grid is not cropped to the box", alt_uncropped),
    ("each dot casts a ray in all four directions", alt_all_directions),
    ("rays go toward the border clockwise of the matching one", alt_perpendicular),
    ("crop only to the extent of the dots, not the divider box", alt_dot_extent),
    ("correct output transposed", alt_transpose),
    ("only the dot nearest the border in each line casts a ray", alt_ray_ignores_dot_blocking),
    ("each ray covers only half the distance to the border", alt_half_ray),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/5daaa586.json").read_text())
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
