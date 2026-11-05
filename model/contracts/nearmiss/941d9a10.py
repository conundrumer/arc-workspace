import json
from pathlib import Path


def _bands(inp, axis):
    """Index ranges (start, end) of the non-divider bands along an axis (0 rows, 1 cols)."""
    n = len(inp) if axis == 0 else len(inp[0])
    if axis == 0:
        div = [all(c == 5 for c in inp[i]) for i in range(n)]
    else:
        div = [all(r[j] == 5 for r in inp) for j in range(n)]
    bands, s = [], None
    for i in range(n):
        if not div[i] and s is None:
            s = i
        if div[i] and s is not None:
            bands.append((s, i))
            s = None
    if s is not None:
        bands.append((s, n))
    return bands


def _fill(grid, rb, cb, color):
    g = [r[:] for r in grid]
    for i in range(*rb):
        for j in range(*cb):
            g[i][j] = color
    return g


def _base(inp):
    return [r[:] for r in inp]


def _all_bands(inp):
    return _bands(inp, 0), _bands(inp, 1)


def _paint(inp, spec):
    rbs, cbs = _all_bands(inp)
    g = _base(inp)
    for (ri, ci, col) in spec(len(rbs), len(cbs)):
        if 0 <= ri < len(rbs) and 0 <= ci < len(cbs):
            g = _fill(g, rbs[ri], cbs[ci], col)
    return g


def correct(nr, nc):
    return [(0, 0, 1), (nr // 2, nc // 2, 2), (nr - 1, nc - 1, 3)]


def no_center(inp, out):
    return _paint(inp, lambda nr, nc: [(0, 0, 1), (nr - 1, nc - 1, 3)])


def no_corners(inp, out):
    return _paint(inp, lambda nr, nc: [(nr // 2, nc // 2, 2)])


def swap_corner_colors(inp, out):
    return _paint(inp, lambda nr, nc: [(0, 0, 3), (nr // 2, nc // 2, 2), (nr - 1, nc - 1, 1)])


def wrong_center_color(inp, out):
    return _paint(inp, lambda nr, nc: [(0, 0, 1), (nr // 2, nc // 2, 4), (nr - 1, nc - 1, 3)])


def corners_top_right_bottom_left(inp, out):
    return _paint(inp, lambda nr, nc: [(0, nc - 1, 1), (nr // 2, nc // 2, 2), (nr - 1, 0, 3)])


def center_upper_left(inp, out):
    # off-by-one: center band one earlier along rows
    return _paint(inp, lambda nr, nc: [(0, 0, 1), (nr // 2 - 1, nc // 2, 2), (nr - 1, nc - 1, 3)])


def center_shifted_col(inp, out):
    return _paint(inp, lambda nr, nc: [(0, 0, 1), (nr // 2, (nc // 2 + 1) % nc, 2), (nr - 1, nc - 1, 3)])


def center_transposed(inp, out):
    # center band index taken from the wrong axis counts (rows/cols mixed up)
    return _paint(inp, lambda nr, nc: [(0, 0, 1), (nc // 2, nr // 2, 2), (nr - 1, nc - 1, 3)])


def center_whole_middle_row(inp, out):
    rbs, cbs = _all_bands(inp)
    g = _base(inp)
    g = _fill(g, rbs[0], cbs[0], 1)
    for cb in cbs:
        g = _fill(g, rbs[len(rbs) // 2], cb, 2)
    return _fill(g, rbs[-1], cbs[-1], 3)


def all_four_corners(inp, out):
    return _paint(inp, lambda nr, nc: [(0, 0, 1), (nr // 2, nc // 2, 2), (nr - 1, nc - 1, 3),
                                       (0, nc - 1, 3), (nr - 1, 0, 1)])


def center_sized_to_corner_extent(inp, out):
    # first and last band only, painted along whole first row and last column of blocks
    rbs, cbs = _all_bands(inp)
    g = _base(inp)
    for cb in cbs[:1]:
        for rb in rbs[:1]:
            g = _fill(g, rb, cb, 1)
    for rb in rbs[:1]:
        for cb in cbs[:2]:
            g = _fill(g, rb, cb, 1)
    g = _fill(g, rbs[len(rbs) // 2], cbs[len(cbs) // 2], 2)
    return _fill(g, rbs[-1], cbs[-1], 3)


ALTERNATIVES = [
    ("center block left unpainted", no_center),
    ("only the middle block painted, corner blocks left unpainted", no_corners),
    ("top-left and bottom-right colors swapped", swap_corner_colors),
    ("center block painted with wrong color 4", wrong_center_color),
    ("corner blocks taken at top-right and bottom-left", corners_top_right_bottom_left),
    ("center block one band earlier along rows", center_upper_left),
    ("center block one band shifted along columns", center_shifted_col),
    ("center band index taken with row and column band counts swapped", center_transposed),
    ("whole middle band row painted 2 instead of one center block", center_whole_middle_row),
    ("all four corner blocks painted", all_four_corners),
    ("top-left color spans two blocks along the first block row", center_sized_to_corner_extent),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/941d9a10.json").read_text())
    pairs = task["train"]

    def valid(g, o):
        return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != o)

    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
