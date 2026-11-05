import json
from collections import Counter
from pathlib import Path


def _mask(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 0]


def _fill(inp, partner):
    """Fill each 0 cell from partner(r, c) in inp; leave 0 if the partner is out of range or 0."""
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for r, c in _mask(inp):
        pr, pc = partner(r, c)
        if 0 <= pr < h and 0 <= pc < w and inp[pr][pc] != 0:
            g[r][c] = inp[pr][pc]
    return g


def _regions(inp):
    seen, regs = set(), []
    for r, c in _mask(inp):
        if (r, c) in seen:
            continue
        stack, reg = [(r, c)], []
        seen.add((r, c))
        while stack:
            y, x = stack.pop()
            reg.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (y + dy, x + dx)
                if 0 <= n[0] < len(inp) and 0 <= n[1] < len(inp[0]) and inp[n[0]][n[1]] == 0 and n not in seen:
                    seen.add(n)
                    stack.append(n)
        regs.append(reg)
    return regs


def mirror_rows_only_wrong_axis(inp, out):
    return _fill(inp, lambda r, c: (30 - r, c))


def mirror_rows_shift_col(inp, out):
    return _fill(inp, lambda r, c: (31 - r, c + 1))


def mirror_cols_wrong_axis(inp, out):
    return _fill(inp, lambda r, c: (r, 30 - c))


def transpose_fill(inp, out):
    return _fill(inp, lambda r, c: (c, r))


def antidiagonal_fill(inp, out):
    n = len(inp)
    return _fill(inp, lambda r, c: (n - 1 - c, n - 1 - r))


def rot180_wrong_center(inp, out):
    n = len(inp)
    return _fill(inp, lambda r, c: (n - 1 - r, n - 1 - c))


def largest_region_unfilled(inp, out):
    regs = _regions(inp)
    if len(regs) < 2:
        return None
    big = max(regs, key=len)
    g = [row[:] for row in out]
    for r, c in big:
        g[r][c] = 0
    return g


def top_half_only(inp, out):
    g = [row[:] for row in out]
    for r, c in _mask(inp):
        if r >= len(inp) // 2:
            g[r][c] = 0
    return g


def solid_most_common(inp, out):
    cnt = Counter(v for row in inp for v in row if v != 0)
    col = cnt.most_common(1)[0][0]
    g = [row[:] for row in inp]
    for r, c in _mask(inp):
        g[r][c] = col
    return g


def left_neighbor_fill(inp, out):
    g = [row[:] for row in inp]
    for r, c in _mask(inp):
        x = c
        while x >= 0 and inp[r][x] == 0:
            x -= 1
        if x < 0:
            x = c
            while x < len(inp[0]) and inp[r][x] == 0:
                x += 1
        g[r][c] = inp[r][x]
    return g


def crop_largest_region(inp, out):
    regs = _regions(inp)
    big = max(regs, key=len)
    r0 = min(r for r, c in big)
    r1 = max(r for r, c in big)
    c0 = min(c for r, c in big)
    c1 = max(c for r, c in big)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def fill_with_background_swap(inp, out):
    # right shape of fill, but taken from the mirrored partner of the other axis pair only where the true value is the grid's most common color
    cnt = Counter(v for row in out for v in row)
    top = cnt.most_common(1)[0][0]
    g = [row[:] for row in out]
    for r, c in _mask(inp):
        if g[r][c] == top:
            g[r][c] = 0
    return g


ALTERNATIVES = [
    ("row mirror about the wrong axis (r -> 30-r), column kept", mirror_rows_only_wrong_axis),
    ("row mirror about the right axis but column off by one", mirror_rows_shift_col),
    ("column mirror about the wrong axis (c -> 30-c), row kept", mirror_cols_wrong_axis),
    ("fill from the transpose partner (c, r)", transpose_fill),
    ("fill from the anti-diagonal partner", antidiagonal_fill),
    ("fill from the 180-degree rotation about the grid centre (30-r, 30-c)", rot180_wrong_center),
    ("largest masked region left unfilled", largest_region_unfilled),
    ("only masked cells in the top half filled", top_half_only),
    ("masked cells filled with the most common color", solid_most_common),
    ("masked cells filled from the nearest non-masked cell in the row", left_neighbor_fill),
    ("output is the crop of the largest masked region", crop_largest_region),
    ("cells of the most common output color in the mask left as 0", fill_with_background_swap),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/af22c60d.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
