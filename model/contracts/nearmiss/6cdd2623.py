import json
from collections import Counter
from pathlib import Path


def _color(out):
    return next(v for row in out for v in row if v)


def _lines(out):
    """Rows and columns that are drawn in the true output."""
    c = _color(out)
    h, w = len(out), len(out[0])
    rows = [r for r in range(h) if sum(out[r][x] == c for x in range(w)) >= w - 0 and all(out[r][x] == c for x in range(w))]
    cols = [x for x in range(w) if all(out[r][x] == c for r in range(h))]
    return c, rows, cols


def _blank(inp):
    return [[0] * len(inp[0]) for _ in inp]


def _draw(inp, c, rows, cols):
    g = _blank(inp)
    h, w = len(g), len(g[0])
    for r in rows:
        if 0 <= r < h:
            for x in range(w):
                g[r][x] = c
    for x in cols:
        if 0 <= x < w:
            for r in range(h):
                g[r][x] = c
    return g


def _marks(inp, c):
    """Edge marks of colour c: (row-line marks, column-line marks)."""
    h, w = len(inp), len(inp[0])
    rmarks = [(r, x) for r in range(h) for x in (0, w - 1) if inp[r][x] == c]
    cmarks = [(r, x) for x in range(w) for r in (0, h - 1) if inp[r][x] == c]
    return rmarks, cmarks


def only_rows(inp, out):
    c, rows, cols = _lines(out)
    return _draw(inp, c, rows, [])


def only_cols(inp, out):
    c, rows, cols = _lines(out)
    return _draw(inp, c, [], cols)


def swapped_axes(inp, out):
    c, rows, cols = _lines(out)
    return _draw(inp, c, cols, rows)


def half_lines(inp, out):
    c, rows, cols = _lines(out)
    g = _draw(inp, c, rows, cols)
    h, w = len(g), len(g[0])
    for r in range(h):
        for x in range(w):
            if g[r][x] and r not in rows and x >= w // 2 and x not in cols:
                g[r][x] = 0
            elif g[r][x] and r in rows and x not in cols and x >= w // 2:
                g[r][x] = 0
    return g


def wrong_color_most_common(inp, out):
    c, rows, cols = _lines(out)
    cnt = Counter(v for row in inp for v in row if v and v != c)
    if not cnt:
        return None
    return _draw(inp, cnt.most_common(1)[0][0], rows, cols)


def keep_input_noise(inp, out):
    c = _color(out)
    return [[out[r][x] if out[r][x] else inp[r][x] for x in range(len(out[0]))] for r in range(len(out))]


def lines_on_empty_cells_only(inp, out):
    return [[out[r][x] if inp[r][x] == 0 else inp[r][x] for x in range(len(out[0]))] for r in range(len(out))]


def every_cell_of_colour_casts(inp, out):
    c = _color(out)
    rows = sorted({r for r, row in enumerate(inp) for v in row if v == c})
    cols = sorted({x for row in inp for x, v in enumerate(row) if v == c})
    return _draw(inp, c, rows, cols)


def rays_stop_at_obstacles(inp, out):
    c = _color(out)
    h, w = len(inp), len(inp[0])
    rmarks, cmarks = _marks(inp, c)
    g = _blank(inp)
    for r, x in rmarks:
        d = 1 if x == 0 else -1
        g[r][x] = c
        k = x + d
        while 0 <= k < w and inp[r][k] == 0:
            g[r][k] = c
            k += d
    for r, x in cmarks:
        d = 1 if r == 0 else -1
        g[r][x] = c
        k = r + d
        while 0 <= k < h and inp[k][x] == 0:
            g[k][x] = c
            k += d
    return g


def shifted_by_one(inp, out):
    c, rows, cols = _lines(out)
    return _draw(inp, c, [r + 1 for r in rows], [x + 1 for x in cols])


def edge_lines_cropped(inp, out):
    c, rows, cols = _lines(out)
    g = _draw(inp, c, rows, cols)
    return [row[1:-1] for row in g[1:-1]]


ALTERNATIVES = [
    ("draw only the horizontal lines, ignore marks on top and bottom edges", only_rows),
    ("draw only the vertical lines, ignore marks on left and right edges", only_cols),
    ("swap orientation: left/right marks draw columns, top/bottom marks draw rows", swapped_axes),
    ("each line covers only the left half or top half of the grid", half_lines),
    ("draw the lines in the most common non-line colour", wrong_color_most_common),
    ("draw the lines but keep the input noise cells elsewhere", keep_input_noise),
    ("lines do not overwrite non-empty input cells", lines_on_empty_cells_only),
    ("every cell of the line colour, not only edge marks, casts a row and a column", every_cell_of_colour_casts),
    ("each line stops at the first non-empty input cell", rays_stop_at_obstacles),
    ("lines drawn one row and one column off", shifted_by_one),
    ("output cropped by one cell on every side", edge_lines_cropped),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/6cdd2623.json"))
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
