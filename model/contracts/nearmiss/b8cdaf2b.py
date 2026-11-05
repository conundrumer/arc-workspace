import copy
import json
from pathlib import Path


def _geom(inp):
    h, w = len(inp), len(inp[0])
    cap_row = h - 2
    cols = [c for c in range(w) if inp[cap_row][c] != 0]
    cmin, cmax = min(cols), max(cols)
    outer = inp[cap_row][cmin]
    inner = inp[h - 1][cmin]
    return h, w, cap_row, cmin, cmax, outer, inner


def _paint(g, r, c, dr, dc, color, n=None):
    h, w = len(g), len(g[0])
    k = 0
    while 0 <= r < h and 0 <= c < w and (n is None or k < n):
        g[r][c] = color
        r += dr
        c += dc
        k += 1


def _true_len(inp, side):
    h, w, cap_row, cmin, cmax, outer, inner = _geom(inp)
    r = cap_row - 1
    c = cmin - 1 if side < 0 else cmax + 1
    n = 0
    while 0 <= r and 0 <= c < w:
        n += 1
        r -= 1
        c += side
    return n


def _rays(inp, row_off=0, col_off=0, dc_sign=1, color=None, length=None, vertical=False, both=False):
    """Draw both rays on a copy of inp. Each ray starts next to a cap end;
    dc_sign=1 goes outward, -1 inward. length may be a function (side)->int."""
    h, w, cap_row, cmin, cmax, outer, inner = _geom(inp)
    col = inner if color is None else color
    g = copy.deepcopy(inp)
    for side, base_c in ((-1, cmin), (1, cmax)):
        r0 = cap_row - 1 + row_off
        if vertical:
            c0 = base_c
            dc = 0
        else:
            c0 = base_c + side * (1 + col_off)
            dc = side * dc_sign
        n = length(side) if callable(length) else length
        _paint(g, r0, c0, -1, dc, col, n)
        if both:
            _paint(g, r0 + 1, c0 - dc, 1, -dc, col)
    return g


def _diff_cells(inp, out):
    return [(r, c) for r in range(len(out)) for c in range(len(out[0])) if out[r][c] != inp[r][c]]


def outer_color(inp, out):
    h, w, cap_row, cmin, cmax, outer, inner = _geom(inp)
    g = copy.deepcopy(out)
    for r, c in _diff_cells(inp, out):
        g[r][c] = outer
    return g


def left_only(inp, out):
    h, w, cap_row, cmin, cmax, outer, inner = _geom(inp)
    g = copy.deepcopy(out)
    for r, c in _diff_cells(inp, out):
        if c > cmax:
            g[r][c] = inp[r][c]
    return g


def vertical_rays(inp, out):
    return _rays(inp, vertical=True)


def start_too_low(inp, out):
    return _rays(inp, row_off=1)


def start_gap(inp, out):
    return _rays(inp, row_off=-1, col_off=1)


def start_above_cap_end(inp, out):
    return _rays(inp, col_off=-1)


def inward_rays(inp, out):
    return _rays(inp, dc_sign=-1, col_off=-0)


def full_diagonal_line(inp, out):
    return _rays(inp, both=True)


def unchanged(inp, out):
    return copy.deepcopy(inp)


def half_length(inp, out):
    return _rays(inp, length=lambda side: _true_len(inp, side) // 2)


def one_cell_short(inp, out):
    return _rays(inp, length=lambda side: _true_len(inp, side) - 1)


ALTERNATIVES = [
    ("rays take the cap's outer color instead of the base's inner color", outer_color),
    ("only the left ray is drawn", left_only),
    ("rays go straight up from the cap ends instead of diagonally", vertical_rays),
    ("rays start one row too low, in the cap row", start_too_low),
    ("rays start one row and one column too far, leaving a gap after the cap", start_gap),
    ("each ray starts straight above its cap end cell, not one column outward", start_above_cap_end),
    ("rays slant inward, toward the middle, instead of outward", inward_rays),
    ("each ray is a full diagonal line, also drawn back down over the cap and base", full_diagonal_line),
    ("nothing is drawn; the input is returned", unchanged),
    ("rays stop at half their true length", half_length),
    ("rays stop one cell before the frame edge", one_cell_short),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/b8cdaf2b.json"))
    pairs = task["train"]

    def valid(g):
        return (
            isinstance(g, list)
            and len(g) > 0
            and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        )

    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
