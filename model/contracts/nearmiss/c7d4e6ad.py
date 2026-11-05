import json
from collections import Counter
from pathlib import Path

T = 5


def _copy(g):
    return [list(r) for r in g]


def _recolor(inp, color_of):
    g = _copy(inp)
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == T:
                g[r][c] = color_of(r, c)
    return g


def _margin_colors(inp):
    return [r[0] for r in inp if r[0] not in (0, T)]


def right_edge_color(inp, out):
    # Reads the replacement color from the right edge column instead of the left.
    return _recolor(inp, lambda r, c: inp[r][-1])


def row_above(inp, out):
    # Off by one row: takes the color from the row above.
    return _recolor(inp, lambda r, c: inp[max(r - 1, 0)][0])


def row_below(inp, out):
    # Off by one row: takes the color from the row below.
    return _recolor(inp, lambda r, c: inp[min(r + 1, len(inp) - 1)][0])


def first_color_only(inp, out):
    # One replacement color for the whole shape: the top-most margin color.
    m = _margin_colors(inp)
    return _recolor(inp, lambda r, c: m[0])


def last_color_only(inp, out):
    # One replacement color for the whole shape: the bottom-most margin color.
    m = _margin_colors(inp)
    return _recolor(inp, lambda r, c: m[-1])


def most_common_color(inp, out):
    # One replacement color for the whole shape: the most frequent margin color.
    m = _margin_colors(inp)
    k = Counter(m).most_common(1)[0][0]
    return _recolor(inp, lambda r, c: k)


def mirrored_rows(inp, out):
    # Row order flipped: reads the margin color from the vertically mirrored row.
    h = len(inp)
    return _recolor(inp, lambda r, c: inp[h - 1 - r][0])


def erase_targets(inp, out):
    # Treats the shape as noise and erases it to background.
    return _recolor(inp, lambda r, c: 0)


def leftmost_kept(inp, out):
    # Leaves the left-most shape cell of each row uncolored.
    g = _copy(out)
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == T:
                g[r][c] = T
                break
    return g


def margin_cleared(inp, out):
    # Recolors correctly but also clears the margin column.
    g = _copy(out)
    for r in range(len(g)):
        g[r][0] = 0
    return g


def fill_row_span(inp, out):
    # Fills the whole row between margin and the right-most shape cell, not only the shape cells.
    g = _copy(out)
    for r, row in enumerate(inp):
        cs = [c for c, v in enumerate(row) if v == T]
        if cs:
            for c in range(1, max(cs) + 1):
                g[r][c] = inp[r][0]
    return g


def column_scan_color(inp, out):
    # Transposed reading: indexes the margin colors by shape column instead of by row.
    m = _margin_colors(inp)
    return _recolor(inp, lambda r, c: m[min(c, len(m) - 1)])


ALTERNATIVES = [
    ("replacement color read from the right edge column instead of the left", right_edge_color),
    ("replacement color taken from the row above (off by one row)", row_above),
    ("replacement color taken from the row below (off by one row)", row_below),
    ("whole shape takes the top-most margin color", first_color_only),
    ("whole shape takes the bottom-most margin color", last_color_only),
    ("whole shape takes the most frequent margin color", most_common_color),
    ("margin color read from the vertically mirrored row", mirrored_rows),
    ("shape erased to background instead of recolored", erase_targets),
    ("left-most shape cell of each row left uncolored", leftmost_kept),
    ("recolor correct but margin column cleared", margin_cleared),
    ("recolor spills over whole row span up to the right-most shape cell", fill_row_span),
    ("replacement color chosen by shape column index among margin colors", column_scan_color),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/c7d4e6ad.json"))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
