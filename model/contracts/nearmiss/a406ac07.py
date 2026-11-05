import json
from pathlib import Path


def _parts(inp):
    h, w = len(inp), len(inp[0])
    right = [inp[r][w - 1] for r in range(h - 1)]
    bottom = [inp[h - 1][c] for c in range(w - 1)]
    return h, w, right, bottom


def _copy(g):
    return [row[:] for row in g]


def _build(inp, cell):
    h, w, right, bottom = _parts(inp)
    g = _copy(inp)
    for r in range(h - 1):
        for c in range(w - 1):
            g[r][c] = cell(r, c, right, bottom)
    return g


def row_fill(inp, out):
    # any row whose right-edge color occurs on the bottom edge is filled across
    return _build(inp, lambda r, c, R, B: R[r] if R[r] in B else 0)


def always_row(inp, out):
    return _build(inp, lambda r, c, R, B: R[r])


def always_col(inp, out):
    return _build(inp, lambda r, c, R, B: B[c])


def row_off_by_one(inp, out):
    return _build(inp, lambda r, c, R, B: R[(r + 1) % len(R)] if R[(r + 1) % len(R)] == B[c] else 0)


def reversed_bottom(inp, out):
    return _build(inp, lambda r, c, R, B: R[r] if R[r] == B[len(B) - 1 - c] else 0)


def constant_color(inp, out):
    return [[1 if (v != 0 and (i < len(out) - 1 and j < len(out[0]) - 1)) else v
             for j, v in enumerate(row)] for i, row in enumerate(out)]


def headers_cleared(inp, out):
    h, w = len(out), len(out[0])
    return [[0 if (i == h - 1 or j == w - 1) else v for j, v in enumerate(row)]
            for i, row in enumerate(out)]


def cropped_inner(inp, out):
    return [row[:-1] for row in out[:-1]]


def first_cell_only(inp, out):
    g = _copy(out)
    h, w, right, bottom = _parts(inp)
    seen = set()
    for r in range(h - 1):
        for c in range(w - 1):
            if g[r][c] != 0:
                if g[r][c] in seen:
                    g[r][c] = 0
                else:
                    seen.add(g[r][c])
    return g


def square_blocks_only(inp, out):
    h, w, right, bottom = _parts(inp)
    g = _copy(out)
    for col in set(right):
        rows = [r for r in range(h - 1) if right[r] == col]
        cols = [c for c in range(w - 1) if bottom[c] == col]
        if len(rows) != len(cols):
            for r in rows:
                for c in cols:
                    g[r][c] = 0
    return None if g == out else g


def swap_axes(inp, out):
    # match each column's bottom color against right-edge colors, painting transposed layout
    h, w, right, bottom = _parts(inp)
    if h != w:
        return None
    return _build(inp, lambda r, c, R, B: R[c] if R[c] == B[r] else 0)


def edges_erased_on_match(inp, out):
    g = _copy(out)
    h, w = len(g), len(g[0])
    for r in range(h - 1):
        if any(g[r][c] != 0 for c in range(w - 1)):
            g[r][w - 1] = 0
    return g


ALTERNATIVES = [
    ("fill a whole row with the right-edge color when that color appears anywhere on the bottom edge", row_fill),
    ("fill every interior cell with its row's right-edge color", always_row),
    ("fill every interior cell with its column's bottom-edge color", always_col),
    ("compare right-edge colors with the bottom edge one row too low", row_off_by_one),
    ("read the bottom edge in reverse order", reversed_bottom),
    ("paint matched blocks with a constant color 1", constant_color),
    ("clear the right column and bottom row after filling", headers_cleared),
    ("return only the interior without the edge column and row", cropped_inner),
    ("paint only the first cell of each color", first_cell_only),
    ("keep only blocks whose row run and column run have equal length", square_blocks_only),
    ("swap the roles of the row and column axes", swap_axes),
    ("erase the right-edge cell of rows that got a filled block", edges_erased_on_match),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/a406ac07.json'))
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in train)
        print(n, "/", len(train), desc)
