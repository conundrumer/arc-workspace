import json
from pathlib import Path


def _cells(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def _blank(g):
    return [[0] * len(g[0]) for _ in g]


def _rows(inp):
    rs = [r for r, _, _ in _cells(inp)]
    return min(rs), max(rs)


def _cols(inp):
    cs = [c for _, c, _ in _cells(inp)]
    return min(cs), max(cs)


def _place(inp, fn, base=None):
    """fn(r, c) -> (r2, c2); cells moved off the grid are dropped."""
    g = [row[:] for row in base] if base else _blank(inp)
    for r, c, v in _cells(inp):
        r2, c2 = fn(r, c)
        if 0 <= r2 < len(g) and 0 <= c2 < len(g[0]):
            g[r2][c2] = v
    return g


def shear_right(inp, out):
    _, bot = _rows(inp)
    return _place(inp, lambda r, c: (r, c + bot - r))


def anchor_top(inp, out):
    top, _ = _rows(inp)
    return _place(inp, lambda r, c: (r, c - (r - top)))


def anchor_top_right(inp, out):
    top, _ = _rows(inp)
    return _place(inp, lambda r, c: (r, c + (r - top)))


def shift_one_only(inp, out):
    _, bot = _rows(inp)
    return _place(inp, lambda r, c: (r, c - 1 if r < bot else c))


def off_by_one_less(inp, out):
    _, bot = _rows(inp)
    return _place(inp, lambda r, c: (r, c - max(bot - r - 1, 0)))


def off_by_one_more(inp, out):
    _, bot = _rows(inp)
    return _place(inp, lambda r, c: (r, c - (bot - r + 1)))


def double_shift(inp, out):
    _, bot = _rows(inp)
    return _place(inp, lambda r, c: (r, c - 2 * (bot - r)))


def rigid_shift(inp, out):
    top, bot = _rows(inp)
    return _place(inp, lambda r, c: (r, c - (bot - top)))


def vertical_shear_up(inp, out):
    _, right = _cols(inp)
    return _place(inp, lambda r, c: (r - (right - c), c))


def vertical_shear_down_left_anchor(inp, out):
    left, _ = _cols(inp)
    return _place(inp, lambda r, c: (r + (c - left), c))


def keep_original_too(inp, out):
    _, bot = _rows(inp)
    return _place(inp, lambda r, c: (r, c - (bot - r)), base=inp)


def top_row_unshifted(inp, out):
    top, _ = _rows(inp)
    g = [row[:] for row in out]
    g[top] = inp[top][:]
    return g


ALTERNATIVES = [
    ("shear to the right instead of the left (rows shift right by distance from bottom)", shear_right),
    ("anchor the top row and shift lower rows left by their distance from the top", anchor_top),
    ("anchor the top row and shift lower rows right by their distance from the top", anchor_top_right),
    ("shift every non-bottom row left by exactly one cell", shift_one_only),
    ("off by one: shift by distance from bottom minus one", off_by_one_less),
    ("off by one: shift by distance from bottom plus one", off_by_one_more),
    ("shift by twice the distance from the bottom", double_shift),
    ("move the whole shape rigidly left by its height minus one", rigid_shift),
    ("shear columns vertically: shift up by distance from the rightmost column", vertical_shear_up),
    ("shear columns vertically: shift down by distance from the leftmost column", vertical_shear_down_left_anchor),
    ("draw the sheared shape on top of the unmoved original cells", keep_original_too),
    ("correct shear except the top row is left unshifted", top_row_unshifted),
]


def _valid(g, out):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/423a55dc.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
