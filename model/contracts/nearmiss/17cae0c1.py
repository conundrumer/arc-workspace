import json
from pathlib import Path


def _panels(inp):
    return len(inp[0]) // 3


def _colors(out):
    return [out[0][3 * k] for k in range(len(out[0]) // 3)]


def _paint(inp, cols, only_glyph=None, fill_bg=False):
    h, w = len(inp), len(inp[0])
    res = []
    for r in range(h):
        row = []
        for c in range(w):
            k = c // 3
            on = inp[r][c] != 0
            if only_glyph is True:
                row.append(cols[k] if on else 0)
            elif only_glyph is False:
                row.append(5 if on else cols[k])
            else:
                row.append(cols[k])
        res.append(row)
    return res


def unchanged(inp, out):
    return [r[:] for r in inp]


def fill_with_five(inp, out):
    return [[5] * len(r) for r in out]


def paint_glyph_only(inp, out):
    return _paint(inp, _colors(out), only_glyph=True)


def paint_background_only(inp, out):
    return _paint(inp, _colors(out), only_glyph=False)


def reverse_panel_colors(inp, out):
    return _paint(inp, _colors(out)[::-1])


def swap_first_two(inp, out):
    cols = _colors(out)
    cols[0], cols[1] = cols[1], cols[0]
    return _paint(inp, cols)


def first_color_everywhere(inp, out):
    cols = _colors(out)
    return _paint(inp, [cols[0]] * len(cols))


def one_cell_per_panel(inp, out):
    return [_colors(out)]


def first_panel_left_unfilled(inp, out):
    res = [r[:] for r in out]
    for r in range(len(res)):
        for c in range(3):
            res[r][c] = inp[r][c]
    return res


def last_panel_left_unfilled(inp, out):
    res = [r[:] for r in out]
    n = len(res[0])
    for r in range(len(res)):
        for c in range(n - 3, n):
            res[r][c] = inp[r][c]
    return res


def shifted_one_column(inp, out):
    return [r[-1:] + r[:-1] for r in out]


def fill_only_middle_row(inp, out):
    res = [r[:] for r in out]
    for r in range(len(res)):
        if r != len(res) // 2:
            res[r] = [0] * len(res[r])
    return res


ALTERNATIVES = [
    ("output is the input unchanged", unchanged),
    ("panels are filled with the glyph color 5 instead of a catalog color", fill_with_five),
    ("only the glyph cells are recolored, background stays 0", paint_glyph_only),
    ("only the background cells are recolored, glyph cells stay 5", paint_background_only),
    ("panel colors come in reversed panel order", reverse_panel_colors),
    ("colors of the first two panels are swapped", swap_first_two),
    ("every panel gets the color of the first panel", first_color_everywhere),
    ("output is one row with one cell per panel", one_cell_per_panel),
    ("first panel is not filled and keeps its input glyph", first_panel_left_unfilled),
    ("last panel is not filled and keeps its input glyph", last_panel_left_unfilled),
    ("filled panels are shifted one column right with wraparound", shifted_one_column),
    ("only the middle row of each panel is filled", fill_only_middle_row),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/17cae0c1.json"))
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
