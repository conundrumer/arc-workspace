"""Near-miss readings for 00dbd492.

Rule: each hollow square wall (color 2) holds one dot; the interior bg cells get
a color set by the interior size (3x3 -> 8, 5x5 -> 4, 7x7 -> 3).
"""
import json
from pathlib import Path


def squares(inp):
    """Return wall components (r0, c0, r1, c1) of non-zero cells with >= 8 cells."""
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0 and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            if len(cells) >= 8:
                ys = [p[0] for p in cells]
                xs = [p[1] for p in cells]
                res.append((min(ys), min(xs), max(ys), max(xs)))
    return res


def fill_color(out, sq):
    r0, c0, _, _ = sq
    return out[r0 + 1][c0 + 1]


def interior(sq):
    r0, c0, r1, c1 = sq
    return [(r, c) for r in range(r0 + 1, r1) for c in range(c0 + 1, c1)]


def copy(g):
    return [row[:] for row in g]


def unfilled_largest(inp, out):
    sqs = squares(inp)
    big = max(sqs, key=lambda s: (s[2] - s[0], -s[0], -s[1]))
    g = copy(out)
    for r, c in interior(big):
        g[r][c] = inp[r][c]
    return g


def only_largest(inp, out):
    sqs = squares(inp)
    if len(sqs) < 2:
        return None
    big = max(sqs, key=lambda s: (s[2] - s[0], -s[0], -s[1]))
    g = copy(inp)
    for r, c in interior(big):
        if inp[r][c] == 0:
            g[r][c] = out[r][c]
    return g


def fixed_8(inp, out):
    g = copy(out)
    for sq in squares(inp):
        for r, c in interior(sq):
            if inp[r][c] == 0:
                g[r][c] = 8
    return None if g == out else g


def cycled_colors(inp, out):
    m = {8: 4, 4: 3, 3: 8}
    g = copy(out)
    for sq in squares(inp):
        col = fill_color(out, sq)
        for r, c in interior(sq):
            if inp[r][c] == 0:
                g[r][c] = m.get(col, col)
    return g


def overwrite_dot(inp, out):
    g = copy(out)
    for sq in squares(inp):
        col = fill_color(out, sq)
        for r, c in interior(sq):
            g[r][c] = col
    return g


def fill_walls_too(inp, out):
    g = copy(out)
    for sq in squares(inp):
        col = fill_color(out, sq)
        r0, c0, r1, c1 = sq
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if inp[r][c] != 0 and (r, c) != (r0 + (r1 - r0) // 2, c0 + (c1 - c0) // 2):
                    g[r][c] = col
    return g


def shrunk_by_one(inp, out):
    g = copy(out)
    for sq in squares(inp):
        r0, c0, r1, c1 = sq
        for r, c in interior(sq):
            if r in (r0 + 1, r1 - 1) or c in (c0 + 1, c1 - 1):
                g[r][c] = inp[r][c]
    return g


def flood_all_bg(inp, out):
    h, w = len(inp), len(inp[0])
    cols = [fill_color(out, sq) for sq in squares(inp)]
    col = max(set(cols), key=cols.count)
    g = copy(out)
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0:
                g[r][c] = col
    return g


def cross_only(inp, out):
    g = copy(out)
    for sq in squares(inp):
        r0, c0, r1, c1 = sq
        mr, mc = (r0 + r1) // 2, (c0 + c1) // 2
        for r, c in interior(sq):
            if r != mr and c != mc:
                g[r][c] = inp[r][c]
    return g


def top_half_only(inp, out):
    g = copy(out)
    for sq in squares(inp):
        r0, c0, r1, c1 = sq
        mr = (r0 + r1) // 2
        for r, c in interior(sq):
            if r > mr:
                g[r][c] = inp[r][c]
    return g


def recolor_walls_not_interior(inp, out):
    g = copy(inp)
    for sq in squares(inp):
        col = fill_color(out, sq)
        r0, c0, r1, c1 = sq
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if inp[r][c] != 0 and (r in (r0, r1) or c in (c0, c1)):
                    g[r][c] = col
    return g


def crop_largest(inp, out):
    sqs = squares(inp)
    r0, c0, r1, c1 = max(sqs, key=lambda s: (s[2] - s[0], -s[0], -s[1]))
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("largest square is left unfilled", unfilled_largest),
    ("only the largest square is filled (needs several squares)", only_largest),
    ("every interior is filled with 8 regardless of size", fixed_8),
    ("fill colors rotated among 8, 4, 3 (size-to-color map shifted)", cycled_colors),
    ("center dot is overwritten by the fill color", overwrite_dot),
    ("wall cells are recolored with the fill color too", fill_walls_too),
    ("fill leaves a one-cell ring next to the wall empty", shrunk_by_one),
    ("all background cells of the grid are filled", flood_all_bg),
    ("only the row and column through the dot are filled", cross_only),
    ("only the upper half of each interior is filled", top_half_only),
    ("walls are recolored and the interior stays empty", recolor_walls_not_interior),
    ("output is cropped to the largest filled square", crop_largest),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/00dbd492.json'))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
            elif g is not None:
                print("  INVALID:", desc)
        print(n, desc)
