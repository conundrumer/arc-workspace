import json
from pathlib import Path


def _info(inp, out):
    h, w = len(inp), len(inp[0])
    fill = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != out[r][c]]
    fcol = out[fill[0][0]][fill[0][1]] if fill else None
    cols = {v for row in inp for v in row if v}
    scol = next(iter(cols - {fcol})) if fill else None
    return h, w, fill, fcol, scol


def _copy(g):
    return [row[:] for row in g]


def _fill_cols(fill):
    d = {}
    for r, c in fill:
        d.setdefault(c, []).append(r)
    return d


def wrong_fill_color(inp, out):
    h, w, fill, fcol, scol = _info(inp, out)
    g = _copy(out)
    for r, c in fill:
        g[r][c] = scol
    return g


def one_cell_only(inp, out):
    h, w, fill, fcol, scol = _info(inp, out)
    g = _copy(inp)
    for c, rs in _fill_cols(fill).items():
        g[min(rs)][c] = fcol
    return g


def stop_at_marker(inp, out):
    h, w, fill, fcol, scol = _info(inp, out)
    g = _copy(inp)
    for c, rs in _fill_cols(fill).items():
        for r in range(min(rs), h):
            if inp[r][c] == fcol:
                break
            g[r][c] = fcol
    return g


def fill_rightward(inp, out):
    h, w, fill, fcol, scol = _info(inp, out)
    g = _copy(inp)
    for c, rs in _fill_cols(fill).items():
        r = min(rs)
        for x in range(c, w):
            if inp[r][x] == scol:
                break
            g[r][x] = fcol
    return g


def all_columns_under_shape(inp, out):
    h, w, fill, fcol, scol = _info(inp, out)
    g = _copy(out)
    for c in range(w):
        rows = [r for r in range(h) if inp[r][c] == scol]
        if rows:
            for r in range(max(rows) + 1, h):
                g[r][c] = fcol
    return g


def leftmost_column_only(inp, out):
    h, w, fill, fcol, scol = _info(inp, out)
    cs = _fill_cols(fill)
    keep = min(cs)
    g = _copy(inp)
    for r in cs[keep]:
        g[r][keep] = fcol
    return g


def rightmost_column_only(inp, out):
    h, w, fill, fcol, scol = _info(inp, out)
    cs = _fill_cols(fill)
    keep = max(cs)
    g = _copy(inp)
    for r in cs[keep]:
        g[r][keep] = fcol
    return g


def start_one_row_late(inp, out):
    h, w, fill, fcol, scol = _info(inp, out)
    g = _copy(out)
    for c, rs in _fill_cols(fill).items():
        g[min(rs)][c] = inp[min(rs)][c]
    return g


def stop_one_row_early(inp, out):
    h, w, fill, fcol, scol = _info(inp, out)
    g = _copy(out)
    for c, rs in _fill_cols(fill).items():
        g[max(rs)][c] = inp[max(rs)][c]
    return g


def markers_erased(inp, out):
    h, w, fill, fcol, scol = _info(inp, out)
    g = _copy(out)
    fs = set(fill)
    for r in range(h):
        for c in range(w):
            if inp[r][c] == fcol and (r, c) not in fs and g[r][c] == fcol:
                g[r][c] = 0
    return g


def fill_two_wide(inp, out):
    h, w, fill, fcol, scol = _info(inp, out)
    g = _copy(out)
    for r, c in fill:
        if c + 1 < w and g[r][c + 1] == 0:
            g[r][c + 1] = fcol
    return g


def fill_upward(inp, out):
    h, w, fill, fcol, scol = _info(inp, out)
    g = _copy(inp)
    for c, rs in _fill_cols(fill).items():
        for r in range(min(rs) - 1, -1, -1):
            if inp[r][c] == scol:
                continue
            g[r][c] = fcol
    return g


ALTERNATIVES = [
    ("fill uses the shape color instead of the marker color", wrong_fill_color),
    ("fill paints only the first cell below the shape in each fill column", one_cell_only),
    ("fill stops at the first marker cell in its column", stop_at_marker),
    ("fill runs rightward from the start cell instead of downward", fill_rightward),
    ("every column under the shape is filled, not only the enclosed ones", all_columns_under_shape),
    ("only the leftmost fill column is filled", leftmost_column_only),
    ("only the rightmost fill column is filled", rightmost_column_only),
    ("fill starts one row too low", start_one_row_late),
    ("fill stops one row short of the bottom", stop_one_row_early),
    ("marker cells outside the fill are erased", markers_erased),
    ("fill is two columns wide", fill_two_wide),
    ("fill runs upward above the shape instead of downward", fill_upward),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/6d58a25d.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
