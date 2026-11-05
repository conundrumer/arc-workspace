"""Near-miss readings for ARC task 08ed6ac7.

True rule: each vertical bar of 5 is recolored by its height rank:
tallest 1, then 2, 3, 4.
"""
import json
from pathlib import Path


def _bars(inp):
    """Return a list of (col, [rows]) for each column that holds ink."""
    out = []
    for c in range(len(inp[0])):
        rows = [r for r in range(len(inp)) if inp[r][c] != 0]
        if rows:
            out.append((c, rows))
    return out


def _paint(inp, colors):
    """colors: dict col -> color. Paint each bar of inp with its color."""
    g = [row[:] for row in inp]
    for c, rows in _bars(inp):
        for r in rows:
            g[r][c] = colors.get(c, inp[r][c])
    return g


def _by_height(inp, palette, tallest_first=True):
    bars = sorted(_bars(inp), key=lambda b: len(b[1]), reverse=tallest_first)
    return {c: palette[i] if i < len(palette) else inp[rows[0]][c]
            for i, (c, rows) in enumerate(bars)}


def shortest_first(inp, out):
    return _paint(inp, _by_height(inp, [1, 2, 3, 4, 5, 6], tallest_first=False))


def left_to_right(inp, out):
    bars = sorted(_bars(inp))
    return _paint(inp, {c: i + 1 for i, (c, _) in enumerate(bars)})


def right_to_left(inp, out):
    bars = sorted(_bars(inp), reverse=True)
    return _paint(inp, {c: i + 1 for i, (c, _) in enumerate(bars)})


def all_one_color(inp, out):
    return _paint(inp, {c: 1 for c, _ in _bars(inp)})


def top_cell_dropped(inp, out):
    g = [row[:] for row in out]
    for c, rows in _bars(inp):
        g[rows[0]][c] = 0
    return g


def only_tallest_colored(inp, out):
    colors = _by_height(inp, [1])
    return _paint(inp, colors)


def only_two_tallest_colored(inp, out):
    return _paint(inp, _by_height(inp, [1, 2]))


def top_two_swapped(inp, out):
    sw = {1: 2, 2: 1}
    return [[sw.get(v, v) for v in row] for row in out]


def palette_shifted(inp, out):
    sh = {1: 2, 2: 3, 3: 4, 4: 1}
    return [[sh.get(v, v) for v in row] for row in out]


def color_is_height(inp, out):
    return _paint(inp, {c: min(len(rows), 9) for c, rows in _bars(inp)})


def top_aligned(inp, out):
    g = [[0] * len(out[0]) for _ in out]
    for c, rows in _bars(inp):
        for k, r in enumerate(rows):
            g[k][c] = out[rows[0]][c]
    return g


def rank_from_second(inp, out):
    """Tallest bar left uncolored; the rest ranked 1, 2, 3."""
    bars = sorted(_bars(inp), key=lambda b: len(b[1]), reverse=True)
    colors = {c: i for i, (c, _) in enumerate(bars) if i > 0}
    return _paint(inp, colors)


ALTERNATIVES = [
    ("shortest bar gets 1, taller bars get higher numbers", shortest_first),
    ("bars numbered 1..4 by column, left to right", left_to_right),
    ("bars numbered 1..4 by column, right to left", right_to_left),
    ("every bar gets color 1", all_one_color),
    ("correct colors but each bar is one cell short at the top", top_cell_dropped),
    ("only the tallest bar is recolored", only_tallest_colored),
    ("only the two tallest bars are recolored", only_two_tallest_colored),
    ("colors 1 and 2 swapped", top_two_swapped),
    ("colors cycle one step: tallest 2, then 3, 4, 1", palette_shifted),
    ("bar color is the bar's height", color_is_height),
    ("bars drawn hanging from the top row", top_aligned),
    ("tallest bar left 5, others ranked 1, 2, 3", rank_from_second),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
               for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/08ed6ac7.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
