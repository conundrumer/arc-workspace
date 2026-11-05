import json
from collections import Counter
from pathlib import Path

N = 30
MASK = 9


def _mask_cells(inp, out):
    return [(r, c) for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] == MASK]


def _fill(inp, mapper, default=None):
    """Replace each mask cell by the value at mapper(r, c) when that cell is
    in range and not a mask cell; else use default (None keeps the mask color)."""
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for r in range(h):
        for c in range(w):
            if inp[r][c] != MASK:
                continue
            r2, c2 = mapper(r, c)
            if 0 <= r2 < h and 0 <= c2 < w and inp[r2][c2] != MASK:
                g[r][c] = inp[r2][c2]
            elif default is not None:
                g[r][c] = default
    return g


def zero_fill(inp, out):
    return [[0 if v == MASK else v for v in row] for row in inp]


def ud_offset_minus1(inp, out):
    return _fill(inp, lambda r, c: (30 - r, c))


def ud_offset_plus1(inp, out):
    return _fill(inp, lambda r, c: (32 - r, c))


def lr_offset_minus1(inp, out):
    return _fill(inp, lambda r, c: (r, 30 - c))


def lr_offset_plus1(inp, out):
    return _fill(inp, lambda r, c: (r, 32 - c))


def grid_center_ud(inp, out):
    # mirror about the grid's own center line rather than the pattern's axis
    return _fill(inp, lambda r, c: (len(inp) - 1 - r, c))


def grid_center_lr(inp, out):
    return _fill(inp, lambda r, c: (r, len(inp[0]) - 1 - c))


def transpose_fill(inp, out):
    return _fill(inp, lambda r, c: (c, r))


def rot180_pattern_axis(inp, out):
    return _fill(inp, lambda r, c: (31 - r, 31 - c))


def left_neighbor_inpaint(inp, out):
    g = [row[:] for row in inp]
    for r in range(len(g)):
        for c in range(len(g[0])):
            if g[r][c] == MASK:
                g[r][c] = g[r][c - 1] if c > 0 else 0
    return g


def row_majority_fill(inp, out):
    g = [row[:] for row in inp]
    for r, row in enumerate(inp):
        vals = [v for v in row if v != MASK]
        if MASK in row:
            m = Counter(vals).most_common(1)[0][0] if vals else 0
            g[r] = [m if v == MASK else v for v in row]
    return g


def half_filled(inp, out):
    # only mask cells in the upper half are restored
    g = [row[:] for row in out]
    for r, c in _mask_cells(inp, out):
        if r >= len(inp) // 2:
            g[r][c] = MASK
    return g


def crop_mask_box(inp, out):
    cells = _mask_cells(inp, out)
    r0 = min(r for r, c in cells)
    r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells)
    c1 = max(c for r, c in cells)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def ud_only_lr_skipped(inp, out):
    # restore only cells whose vertical mirror is visible; the rest stay masked
    return _fill(inp, lambda r, c: (31 - r, c))


ALTERNATIVES = [
    ("mask cells replaced by background 0", zero_fill),
    ("vertical mirror with axis off by one (row sum 30)", ud_offset_minus1),
    ("vertical mirror with axis off by one (row sum 32)", ud_offset_plus1),
    ("horizontal mirror with axis off by one (column sum 30)", lr_offset_minus1),
    ("mirror about the grid center line vertically, not the pattern axis", grid_center_ud),
    ("mirror about the grid center line horizontally, not the pattern axis", grid_center_lr),
    ("fill from the transposed cell (diagonal symmetry)", transpose_fill),
    ("fill from the point-reflected cell about the pattern center", rot180_pattern_axis),
    ("inpaint mask from left neighbor", left_neighbor_inpaint),
    ("fill each mask cell with the most common color of its row", row_majority_fill),
    ("only upper-half mask cells restored", half_filled),
    ("output is the crop of the true output over the mask bounding box", crop_mask_box),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/3631a71a.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
