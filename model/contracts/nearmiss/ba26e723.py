import json
from pathlib import Path


def _recolor(inp, pred, color=6, src=4, only_rows=None):
    g = [row[:] for row in inp]
    for r, row in enumerate(g):
        if only_rows is not None and r not in only_rows:
            continue
        for c, v in enumerate(row):
            if v == src and pred(r, c, len(row)):
                g[r][c] = color
    return g


def period2(inp, out):
    return _recolor(inp, lambda r, c, w: c % 2 == 0)


def period4(inp, out):
    return _recolor(inp, lambda r, c, w: c % 4 == 0)


def from_right(inp, out):
    g = _recolor(inp, lambda r, c, w: (w - 1 - c) % 3 == 0)
    return None if g == out else g


def phase1(inp, out):
    return _recolor(inp, lambda r, c, w: c % 3 == 1)


def phase2(inp, out):
    return _recolor(inp, lambda r, c, w: c % 3 == 2)


def middle_row_only(inp, out):
    return _recolor(inp, lambda r, c, w: c % 3 == 0, only_rows={1})


def outer_rows_only(inp, out):
    return _recolor(inp, lambda r, c, w: c % 3 == 0, only_rows={0, 2})


def skip_first_column(inp, out):
    return _recolor(inp, lambda r, c, w: c % 3 == 0 and c > 0)


def paint_zero_cells(inp, out):
    g = [row[:] for row in inp]
    for row in g:
        for c in range(len(row)):
            if c % 3 == 0:
                row[c] = 6
    return g


def wrong_color(inp, out):
    return _recolor(inp, lambda r, c, w: c % 3 == 0, color=2)


def every_third_four(inp, out):
    g = [row[:] for row in inp]
    for row in g:
        n = 0
        for c, v in enumerate(row):
            if v == 4:
                if n % 3 == 0:
                    row[c] = 6
                n += 1
    return g


def rows_by_stride(inp, out):
    # Stride applied down the rows instead of along the columns.
    return _recolor(inp, lambda r, c, w: (r + c) % 3 == 0)


ALTERNATIVES = [
    ("stride 2 instead of 3 from the left edge", period2),
    ("stride 4 instead of 3 from the left edge", period4),
    ("stride 3 counted from the right edge", from_right),
    ("stride 3 with phase 1 (columns 1, 4, 7, ...)", phase1),
    ("stride 3 with phase 2 (columns 2, 5, 8, ...)", phase2),
    ("only the middle row is recolored", middle_row_only),
    ("only the top and bottom rows are recolored", outer_rows_only),
    ("column 0 is skipped (off by one at the start)", skip_first_column),
    ("every cell in stride columns becomes 6, including 0 cells", paint_zero_cells),
    ("recolored cells get 2 instead of 6", wrong_color),
    ("every third 4-cell in each row is recolored", every_third_four),
    ("stride follows a diagonal, (row + col) % 3 == 0", rows_by_stride),
]


def _valid(g):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) and r for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/ba26e723.json"))
    pairs = task["train"]
    print(len(pairs), "train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {fn.__name__}: {desc}")
