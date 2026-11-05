import json
from pathlib import Path

FILL = 4


def _info(inp):
    h, w = len(inp), len(inp[0])
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0:
                return h, w, r, c, inp[r][c]


def _build(inp, cols, rows_end, move=1, fill=FILL, marker_color=None, overwrite=False):
    """Fill rows 0..rows_end-1 on cols, marker moved down by `move`."""
    h, w, r, c, m = _info(inp)
    g = [[0] * w for _ in range(h)]
    for x in cols:
        for y in range(min(rows_end, h)):
            g[y][x] = fill
    mr = r + move
    if 0 <= mr < h and (overwrite is False or g[mr][c] == 0):
        g[mr][c] = m if marker_color is None else marker_color
    return g


def _beams(inp, step=2, offset_from_marker=True):
    h, w, r, c, m = _info(inp)
    if offset_from_marker:
        return [x for x in range(w) if (x - c) % step == 0]
    return [x for x in range(w) if x % step == 0]


def no_move(inp, out):
    h, w, r, c, m = _info(inp)
    g = _build(inp, _beams(inp), r + 1, move=0)
    g[r][c] = m
    return g


def all_columns(inp, out):
    h, w, r, c, m = _info(inp)
    return _build(inp, range(w), r + 1)


def odd_columns(inp, out):
    h, w, r, c, m = _info(inp)
    cols = [x for x in range(w) if (x - c) % 2 == 1]
    return _build(inp, cols, r + 1)


def fill_below(inp, out):
    h, w, r, c, m = _info(inp)
    g = [[0] * w for _ in range(h)]
    for x in _beams(inp):
        for y in range(r + 1, h):
            g[y][x] = FILL
    g[r + 1][c] = m
    return g


def fill_marker_color(inp, out):
    h, w, r, c, m = _info(inp)
    return _build(inp, _beams(inp), r + 1, fill=m)


def fill_one_short(inp, out):
    h, w, r, c, m = _info(inp)
    return _build(inp, _beams(inp), r)


def fill_over_marker(inp, out):
    h, w, r, c, m = _info(inp)
    g = _build(inp, _beams(inp), r + 2)
    g[r + 1][c] = FILL
    return g


def move_two(inp, out):
    h, w, r, c, m = _info(inp)
    return _build(inp, _beams(inp), r + 1, move=2)


def full_height_columns(inp, out):
    h, w, r, c, m = _info(inp)
    g = _build(inp, _beams(inp), h)
    g[r + 1][c] = m
    return g


def marker_takes_fill_color(inp, out):
    h, w, r, c, m = _info(inp)
    return _build(inp, _beams(inp), r + 1, marker_color=FILL)


def parity_from_left_edge(inp, out):
    return _build(inp, _beams(inp, offset_from_marker=False), _info(inp)[2] + 1)


def own_column_only(inp, out):
    h, w, r, c, m = _info(inp)
    return _build(inp, [c], r + 1)


ALTERNATIVES = [
    ("marker stays in place instead of moving down one cell", no_move),
    ("every column is filled (period 1)", all_columns),
    ("odd-distance columns are filled instead of even-distance ones", odd_columns),
    ("fill goes from the marker toward the move side (down) instead of the opposite edge", fill_below),
    ("fill uses the marker color instead of 4", fill_marker_color),
    ("fill stops one row short of the marker's original row", fill_one_short),
    ("fill extends one row too far and covers the moved marker", fill_over_marker),
    ("marker moves down two cells", move_two),
    ("beam columns are filled over the full grid height", full_height_columns),
    ("moved marker takes the fill color 4", marker_takes_fill_color),
    ("beam columns picked by absolute even index from the left edge", parity_from_left_edge),
    ("only the marker's own column is filled", own_column_only),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/834ec97d.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                g = None
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, fn.__name__, "-", desc)
