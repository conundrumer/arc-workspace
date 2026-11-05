import json
from pathlib import Path

DIRS4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _copy(g):
    return [row[:] for row in g]


def _bends(inp, out):
    """Cells the true output paints: (r, c, color, open diagonal (dr, dc))."""
    h, w = len(inp), len(inp[0])
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != out[r][c]:
                dr = dc = 0
                for a, b in DIRS4:
                    rr, cc = r + a, c + b
                    if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] != 0:
                        if a:
                            dr -= a
                        else:
                            dc -= b
                res.append((r, c, out[r][c], (dr, dc)))
    return res


def all_open(inp, out):
    g = _copy(out)
    for r, c, col, _ in _bends(inp, out):
        g[r][c] = 4
    return g


def all_enclosed(inp, out):
    g = _copy(out)
    for r, c, col, _ in _bends(inp, out):
        g[r][c] = 2
    return g


def swapped(inp, out):
    g = _copy(out)
    for r, c, col, _ in _bends(inp, out):
        g[r][c] = 2 if col == 4 else 4
    return g


def only_open(inp, out):
    g = _copy(out)
    for r, c, col, _ in _bends(inp, out):
        if col == 2:
            g[r][c] = inp[r][c]
    return g


def only_enclosed(inp, out):
    g = _copy(out)
    for r, c, col, _ in _bends(inp, out):
        if col == 4:
            g[r][c] = inp[r][c]
    return g


def paint_inside_cell(inp, out):
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r, c, col, (dr, dc) in _bends(inp, out):
        rr, cc = r + dr, c + dc
        if 0 <= rr < h and 0 <= cc < w and g[rr][cc] == 0:
            g[rr][cc] = col
    return g


def paint_straight(inp, out):
    h, w = len(inp), len(inp[0])
    g = _copy(out)
    n = 0
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0:
                continue
            nb = [(a, b) for a, b in DIRS4
                  if 0 <= r + a < h and 0 <= c + b < w and inp[r + a][c + b] != 0]
            if len(nb) == 2 and nb[0][0] == -nb[1][0] and nb[0][1] == -nb[1][1]:
                g[r][c] = 4
                n += 1
    return g if n else None


def row_ray_enclosed(inp, out):
    """A corner counts as enclosed when its inside cell has line cells left and right in its row."""
    h, w = len(inp), len(inp[0])
    g = _copy(out)
    for r, c, col, (dr, dc) in _bends(inp, out):
        rr, cc = r + dr, c + dc
        if 0 <= rr < h and 0 <= cc < w:
            inside = any(inp[rr][x] != 0 for x in range(cc)) and any(inp[rr][x] != 0 for x in range(cc + 1, w))
        else:
            inside = False
        g[r][c] = 2 if inside else 4
    return g


def toward_center(inp, out):
    h, w = len(inp), len(inp[0])
    g = _copy(out)
    for r, c, col, (dr, dc) in _bends(inp, out):
        d0 = abs(r - (h - 1) / 2) + abs(c - (w - 1) / 2)
        d1 = abs(r + dr - (h - 1) / 2) + abs(c + dc - (w - 1) / 2)
        g[r][c] = 2 if d1 < d0 else 4
    return g


def crop_ink(inp, out):
    cells = [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if inp[r][c] != 0]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def first_bend_only(inp, out):
    bends = _bends(inp, out)
    g = _copy(inp)
    for r, c, col, _ in bends[:1]:
        g[r][c] = col
    return g


def unpainted_ink_removed(inp, out):
    """Painted corners only, with the straight line cells erased."""
    g = [[0] * len(row) for row in inp]
    for r, c, col, _ in _bends(inp, out):
        g[r][c] = col
    return g


ALTERNATIVES = [
    ("every corner painted 4, no enclosed/open distinction", all_open),
    ("every corner painted 2, no enclosed/open distinction", all_enclosed),
    ("colors 4 and 2 swapped between open and enclosed corners", swapped),
    ("only corners facing the outside are painted", only_open),
    ("only corners facing an enclosed region are painted", only_enclosed),
    ("the cell inside each corner is painted instead of the corner", paint_inside_cell),
    ("straight line cells also painted 4", paint_straight),
    ("only the painted corners are kept and the line cells are erased", unpainted_ink_removed),
    ("enclosed decided by line cells left and right in the inside cell's row", row_ray_enclosed),
    ("corner color chosen by whether it opens toward the grid center", toward_center),
    ("output cropped to the bounding box of the lines", crop_ink),
    ("only the first corner in reading order is painted", first_bend_only),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/15663ba9.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            good = (isinstance(g, list) and g and all(isinstance(row, list) for row in g)
                    and len({len(row) for row in g}) == 1 and len(g[0]) > 0
                    and all(type(v) is int and 0 <= v <= 9 for row in g for v in row))
            if good and g != p["output"]:
                ok += 1
        print(ok, desc)
