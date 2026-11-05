import json
from pathlib import Path


def _rows(out):
    return [r[0] for r in out]


def _fill(colors, width=None):
    w = width if width is not None else len(colors)
    return [[c] * w for c in colors]


def _tile_has_hole(inp, i, n):
    # tiles are side by side with 1-wide gaps; bg is the most common colour
    h = len(inp)
    w = (len(inp[0]) - (n - 1)) // n
    cells = [inp[r][i * (w + 1) + c] for r in range(h) for c in range(w)]
    bg = max(set(cells), key=cells.count) if False else None
    return cells, w


def _full_tiles(inp, out):
    n = len(out)
    flat = [v for r in inp for v in r]
    bg = max(set(flat), key=flat.count)
    res = []
    for i in range(n):
        cells, _ = _tile_has_hole(inp, i, n)
        res.append(all(v == bg for v in cells))
    return res, bg


def reversed_order(inp, out):
    c = _rows(out)[::-1]
    return _fill(c)


def shifted_order(inp, out):
    c = _rows(out)
    return _fill(c[1:] + c[:1])


def transposed(inp, out):
    c = _rows(out)
    return [list(c) for _ in c]


def single_row(inp, out):
    return [_rows(out)]


def drop_last_tile(inp, out):
    c = _rows(out)
    return _fill(c[:-1])


def last_row_blank(inp, out):
    c = _rows(out)
    return _fill(c[:-1] + [0])


def extra_row(inp, out):
    c = _rows(out)
    return _fill(c + [c[-1]], len(c))


def all_first(inp, out):
    c = _rows(out)
    return _fill([c[0]] * len(c))


def diagonal_only(inp, out):
    n = len(out)
    return [[out[i][j] if i == j else 0 for j in range(n)] for i in range(n)]


def swap_first_two(inp, out):
    c = _rows(out)
    c[0], c[1] = c[1], c[0]
    return _fill(c)


def full_tile_as_bg(inp, out):
    full, bg = _full_tiles(inp, out)
    if not any(full):
        return None
    c = _rows(out)
    return _fill([bg if f else x for f, x in zip(full, c)])


def full_tile_wrong_color(inp, out):
    full, bg = _full_tiles(inp, out)
    if not any(full):
        return None
    c = _rows(out)
    return _fill([(8 if x != 8 else 2) if f else x for f, x in zip(full, c)])


ALTERNATIVES = [
    ("tiles counted from the right: rows in reverse tile order", reversed_order),
    ("each row takes the color of the next tile (off-by-one tile index)", shifted_order),
    ("tile colors fill columns instead of rows", transposed),
    ("output is one row of tile colors instead of a square", single_row),
    ("last tile is not read: output has one row too few", drop_last_tile),
    ("last tile has no entry: its row is left 0", last_row_blank),
    ("one extra row, repeating the last tile", extra_row),
    ("every row takes the first tile's color", all_first),
    ("only the diagonal cells are filled", diagonal_only),
    ("first two tiles' rows swapped", swap_first_two),
    ("the tile with no hole maps to the background color", full_tile_as_bg),
    ("the tile with no hole maps to the wrong catalog color", full_tile_wrong_color),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/995c5fa3.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
