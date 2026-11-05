import json
from pathlib import Path

BAR = 2
MARK = 8


def _cols(inp):
    """Map column -> sorted list of rows holding a bar cell."""
    res = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == BAR:
                res.setdefault(c, []).append(r)
    return res


def _paint(inp, chooser, color=MARK, cols_filter=None):
    """Copy inp, then recolor chooser(rows) cells of each bar."""
    g = [row[:] for row in inp]
    cols = _cols(inp)
    for c, rows in cols.items():
        if cols_filter is not None and not cols_filter(c, cols):
            continue
        for r in chooser(rows):
            g[r][c] = color
    return g


def top_half(inp, out):
    return _paint(inp, lambda rows: rows[: len(rows) // 2])


def ceil_half(inp, out):
    return _paint(inp, lambda rows: rows[len(rows) - (len(rows) + 1) // 2:])


def floor_half_plus_one(inp, out):
    return _paint(inp, lambda rows: rows[len(rows) - min(len(rows), len(rows) // 2 + 1):])


def floor_half_minus_one(inp, out):
    return _paint(inp, lambda rows: rows[len(rows) - max(0, len(rows) // 2 - 1):] if len(rows) // 2 - 1 > 0 else [])


def whole_bar(inp, out):
    return _paint(inp, lambda rows: rows)


def wrong_color(inp, out):
    return [[1 if v == MARK else v for v in row] for row in out]


def only_tallest(inp, out):
    return _paint(
        inp,
        lambda rows: rows[len(rows) - len(rows) // 2:],
        cols_filter=lambda c, cols: len(cols[c]) == max(len(v) for v in cols.values()),
    )


def only_leftmost(inp, out):
    return _paint(
        inp,
        lambda rows: rows[len(rows) - len(rows) // 2:],
        cols_filter=lambda c, cols: c == min(cols),
    )


def alternate_bars(inp, out):
    def keep(c, cols):
        order = sorted(cols)
        return order.index(c) % 2 == 0
    return _paint(inp, lambda rows: rows[len(rows) - len(rows) // 2:], cols_filter=keep)


def global_half(inp, out):
    h = len(inp)
    g = [row[:] for row in inp]
    for r in range(h // 2, h):
        for c, v in enumerate(inp[r]):
            if v == BAR:
                g[r][c] = MARK
    return g


def bottom_cell_only(inp, out):
    return _paint(inp, lambda rows: rows[-1:])


def bars_shorter_than_tallest(inp, out):
    """Halves counted from the tallest bar's height, so every bar gets the same row band."""
    cols = _cols(inp)
    tall = max(len(v) for v in cols.values())
    g = [row[:] for row in inp]
    top = len(inp) - tall // 2
    for c, rows in cols.items():
        for r in rows:
            if r >= top:
                g[r][c] = MARK
    return g


ALTERNATIVES = [
    ("recolor the top half of each bar instead of the bottom half", top_half),
    ("recolor the rounded-up half of each bar", ceil_half),
    ("recolor one cell more than half of each bar", floor_half_plus_one),
    ("recolor one cell fewer than half of each bar", floor_half_minus_one),
    ("recolor the whole of every bar", whole_bar),
    ("recolor the bottom half with color 1 instead of 8", wrong_color),
    ("recolor the bottom half of only the tallest bar", only_tallest),
    ("recolor the bottom half of only the leftmost bar", only_leftmost),
    ("recolor the bottom half of every other bar", alternate_bars),
    ("recolor all bar cells in the bottom half of the grid rows", global_half),
    ("recolor only the bottom cell of each bar", bottom_cell_only),
    ("recolor the same bottom band, half the tallest bar, on every bar", bars_shorter_than_tallest),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/ce9e57f2.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
