import json
from pathlib import Path

MARK, SRC, DST = 8, 1, 3


def bbox(g, c=MARK):
    cells = [(r, k) for r, row in enumerate(g) for k, v in enumerate(row) if v == c]
    rs = [r for r, _ in cells]
    ks = [k for _, k in cells]
    return min(rs), max(rs), min(ks), max(ks)


def paint(inp, region, src=SRC, dst=DST):
    """Recolor src cells of inp inside region(r, k) to dst."""
    g = [row[:] for row in inp]
    for r, row in enumerate(g):
        for k, v in enumerate(row):
            if v == src and region(r, k):
                g[r][k] = dst
    return g


def in_box(inp, dr0=0, dr1=0, dk0=0, dk1=0):
    r0, r1, k0, k1 = bbox(inp)
    return lambda r, k: r0 + dr0 <= r <= r1 + dr1 and k0 + dk0 <= k <= k1 + dk1


def whole_grid(inp, out):
    return paint(inp, lambda r, k: True)


def marker_also_recolored(inp, out):
    g = paint(inp, in_box(inp))
    for r, row in enumerate(g):
        for k, v in enumerate(row):
            if v == MARK:
                g[r][k] = DST
    return g


def input_unchanged(inp, out):
    return [row[:] for row in inp]


def wrong_color(inp, out):
    return paint(inp, in_box(inp), dst=2)


def inner_box(inp, out):
    r0, r1, k0, k1 = bbox(inp)
    if r1 - r0 < 2 or k1 - k0 < 2:
        return None
    return paint(inp, in_box(inp, 1, -1, 1, -1))


def outer_box(inp, out):
    return paint(inp, in_box(inp, -1, 1, -1, 1))


def clipped_box(inp, out):
    return paint(inp, in_box(inp, 0, -1, 0, -1))


def marker_recolored(inp, out):
    g = [row[:] for row in inp]
    for r, row in enumerate(g):
        for k, v in enumerate(row):
            if v == MARK:
                g[r][k] = DST
    return g


def upper_half_of_box(inp, out):
    r0, r1, _, _ = bbox(inp)
    mid = (r0 + r1) // 2
    box = in_box(inp)
    return paint(inp, lambda r, k: box(r, k) and r <= mid)


def bbox_rows_full_width(inp, out):
    r0, r1, _, _ = bbox(inp)
    return paint(inp, lambda r, k: r0 <= r <= r1)


def bbox_cols_full_height(inp, out):
    _, _, k0, k1 = bbox(inp)
    return paint(inp, lambda r, k: k0 <= k <= k1)


def crop_box(inp, out):
    r0, r1, k0, k1 = bbox(inp)
    return [row[k0:k1 + 1] for row in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("recolor every 1 in the whole grid, not only inside the 8 box", whole_grid),
    ("recolor the 1 cells in the box and also the 8 marker cells", marker_also_recolored),
    ("no recoloring, input returned unchanged", input_unchanged),
    ("recolor the 1 cells in the box with 2 instead of 3", wrong_color),
    ("box shrunk by one cell on every side", inner_box),
    ("box grown by one cell on every side", outer_box),
    ("box misses its last row and last column", clipped_box),
    ("recolor the 8 marker cells to 3 and leave the 1 cells", marker_recolored),
    ("recolor 1 cells only in the upper half of the box rows", upper_half_of_box),
    ("recolor 1 cells in all rows spanned by the box, across the full width", bbox_rows_full_width),
    ("recolor 1 cells in all columns spanned by the box, across the full height", bbox_cols_full_height),
    ("output only the cropped box region", crop_box),
]


def valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / 'data/tasks/32597951.json'
    train = json.load(open(path))["train"]
    print("pairs", len(train))
    for desc, fn in ALTERNATIVES:
        n = sum(valid(fn([r[:] for r in p["input"]], [r[:] for r in p["output"]]), p["output"]) for p in train)
        print(n, desc)
