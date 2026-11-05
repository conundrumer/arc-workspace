"""Near-miss readings for ARC task 8597cfd7.

Rule: a full-width separator row cuts the grid into a top and a bottom
panel. Bars of two colors stand in each panel. The output is a 2x2 block of
the color whose bar grows the most from the top panel to the bottom panel.
"""
import json
from pathlib import Path


def _parts(inp):
    w = len(inp[0])
    sep_i = next(i for i, r in enumerate(inp) if len(set(r)) == 1 and r[0] != 0)
    sep = inp[sep_i][0]
    top = inp[:sep_i]
    bot = inp[sep_i + 1:]
    colors = sorted({c for r in inp for c in r} - {0, sep})
    return sep, top, bot, colors


def _count(panel, c):
    return sum(r.count(c) for r in panel)


def _fill(n_rows, n_cols, c):
    return [[c] * n_cols for _ in range(n_rows)]


def _growth(inp):
    sep, top, bot, colors = _parts(inp)
    return {c: _count(bot, c) - _count(top, c) for c in colors}


def _pick(scores, best=max):
    m = best(scores.values())
    return [c for c in sorted(scores) if scores[c] == m][0]


def least_growth(inp, out):
    g = _growth(inp)
    return _fill(2, 2, _pick(g, min))


def bottom_longest(inp, out):
    sep, top, bot, colors = _parts(inp)
    # tie goes to the larger color value
    s = {c: _count(bot, c) for c in colors}
    m = max(s.values())
    return _fill(2, 2, [c for c in sorted(s) if s[c] == m][-1])


def top_longest(inp, out):
    sep, top, bot, colors = _parts(inp)
    # tie goes to the larger color value
    s = {c: _count(top, c) for c in colors}
    m = max(s.values())
    return _fill(2, 2, [c for c in sorted(s) if s[c] == m][-1])


def whole_grid_most(inp, out):
    sep, top, bot, colors = _parts(inp)
    return _fill(2, 2, _pick({c: _count(inp, c) for c in colors}))


def separator_color(inp, out):
    sep, top, bot, colors = _parts(inp)
    return _fill(2, 2, sep)


def wrong_size_3(inp, out):
    return _fill(3, 3, out[0][0])


def single_cell(inp, out):
    return [[out[0][0]]]


def one_row(inp, out):
    return [[out[0][0]] * 2]


def corner_only(inp, out):
    g = [row[:] for row in out]
    for i in range(1, len(g)):
        for j in range(len(g[0])):
            g[i][j] = 0
    for i in range(len(g)):
        for j in range(1, len(g[0])):
            g[i][j] = 0
    return g


def bottom_panel_crop(inp, out):
    sep, top, bot, colors = _parts(inp)
    return [r[:] for r in bot]


def other_color(inp, out):
    sep, top, bot, colors = _parts(inp)
    return _fill(2, 2, [c for c in colors if c != out[0][0]][0])


def unchanged(inp, out):
    return [r[:] for r in inp]


ALTERNATIVES = [
    ("fill with the color that grows the least instead of the most", least_growth),
    ("pick the color with the most cells in the bottom panel, ignoring the top panel", bottom_longest),
    ("pick the color with the most cells in the top panel, ties to the larger color", top_longest),
    ("pick the color with the most cells in the whole grid", whole_grid_most),
    ("fill the 2x2 block with the separator color", separator_color),
    ("fill a 3x3 block with the winner", wrong_size_3),
    ("output a single cell of the winner", single_cell),
    ("output a 1x2 row of the winner", one_row),
    ("winner only in the top-left cell, rest 0", corner_only),
    ("output the bottom panel unchanged", bottom_panel_crop),
    ("fill with the non-winning bar color", other_color),
    ("return the input unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/8597cfd7.json'))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
