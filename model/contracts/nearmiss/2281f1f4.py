import json
from pathlib import Path


def _marks(inp):
    h, w = len(inp), len(inp[0])
    cols = [c for c in range(w - 1) if inp[0][c] == 5]
    rows = [r for r in range(1, h) if inp[r][w - 1] == 5]
    return h, w, cols, rows


def _copy(g):
    return [list(r) for r in g]


def _recolor(inp, out):
    return [[1 if v == 2 else v for v in r] for r in out]


def _marker_color(inp, out):
    return [[5 if v == 2 else v for v in r] for r in out]


def _full_lines(inp, out):
    h, w, cols, rows = _marks(inp)
    g = _copy(inp)
    for r in rows:
        for c in range(w - 1):
            if g[r][c] == 0:
                g[r][c] = 2
    for c in cols:
        for r in range(1, h):
            if g[r][c] == 0:
                g[r][c] = 2
    return g


def _skip_first_row(inp, out):
    h, w, cols, rows = _marks(inp)
    g = _copy(out)
    if rows:
        for c in cols:
            g[rows[0]][c] = 0
    return g


def _skip_last_col(inp, out):
    h, w, cols, rows = _marks(inp)
    g = _copy(out)
    if cols:
        for r in rows:
            g[r][cols[-1]] = 0
    return g


def _shift_down(inp, out):
    h, w, cols, rows = _marks(inp)
    g = _copy(inp)
    for r in rows:
        if r + 1 < h:
            for c in cols:
                g[r + 1][c] = 2
    return g


def _shift_right(inp, out):
    h, w, cols, rows = _marks(inp)
    g = _copy(inp)
    for r in rows:
        for c in cols:
            if c + 1 < w - 1:
                g[r][c + 1] = 2
    return g


def _mirror_rows(inp, out):
    h, w, cols, rows = _marks(inp)
    g = _copy(inp)
    for r in rows:
        for c in cols:
            g[h - 1 - r][c] = 2
    return g


def _mirror_cols(inp, out):
    h, w, cols, rows = _marks(inp)
    g = _copy(inp)
    for r in rows:
        for c in cols:
            g[r][w - 1 - c] = 2
    return g


def _right_edge_overwritten(inp, out):
    h, w, cols, rows = _marks(inp)
    g = _copy(out)
    for r in rows:
        g[r][w - 1] = 2
    return g


def _column_only(inp, out):
    h, w, cols, rows = _marks(inp)
    g = _copy(inp)
    for c in cols:
        for r in range(1, h):
            if g[r][c] == 0:
                g[r][c] = 2
    return g


def _row_only(inp, out):
    h, w, cols, rows = _marks(inp)
    g = _copy(inp)
    for r in rows:
        for c in range(w - 1):
            if g[r][c] == 0:
                g[r][c] = 2
    return g


def _unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("crossings drawn in color 1 instead of 2", _recolor),
    ("crossings drawn in the marker color 5", _marker_color),
    ("whole marked rows and columns filled, not only the crossings", _full_lines),
    ("the topmost marked row left unfilled", _skip_first_row),
    ("the rightmost marked column left unfilled", _skip_last_col),
    ("crossings placed one row below the marked rows", _shift_down),
    ("crossings placed one column right of the marked columns", _shift_right),
    ("row marks read from the bottom (rows mirrored vertically)", _mirror_rows),
    ("column marks read from the right (columns mirrored horizontally)", _mirror_cols),
    ("the right-edge marker cells also recolored to 2", _right_edge_overwritten),
    ("only the marked columns filled below the top row", _column_only),
    ("input returned unchanged", _unchanged),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/2281f1f4.json"))
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
