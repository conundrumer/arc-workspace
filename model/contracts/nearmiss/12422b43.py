"""Near-miss readings for 12422b43.

Rule: column 0 holds a marker color on the first K rows (the unit length).
The pattern (ink) spans N rows from the top. The first K rows of the pattern
are repeated downward, starting at row N, until the grid ends.
"""
import json
from pathlib import Path


def _dims(inp):
    h, w = len(inp), len(inp[0])
    k = 0
    while k < h and inp[k][0] != 0:
        k += 1
    n = 0
    for r in range(h):
        if any(v != 0 for v in inp[r][1:]):
            n = r + 1
    return h, w, k, n


def _tile(inp, start, rows, period=None, shift=None):
    """Copy inp with `rows` (list of row lists) tiled from row `start`."""
    h = len(inp)
    g = [r[:] for r in inp]
    period = period or len(rows)
    for r in range(start, h):
        i = (r - start) % period
        g[r] = rows[i][:] if i < len(rows) else [0] * len(inp[0])
    return g


def _unit(inp, k, keep_marker=False):
    rows = []
    for r in range(k):
        row = inp[r][:]
        if not keep_marker:
            row[0] = 0
        rows.append(row)
    return rows


def start_at_marker_end(inp, out):
    h, w, k, n = _dims(inp)
    return _tile(inp, k, _unit(inp, k))


def unit_is_whole_ink(inp, out):
    h, w, k, n = _dims(inp)
    return _tile(inp, n, _unit(inp, n))


def single_copy_only(inp, out):
    h, w, k, n = _dims(inp)
    g = [r[:] for r in inp]
    u = _unit(inp, k)
    for i in range(k):
        if n + i < h:
            g[n + i] = u[i][:]
    return g


def reversed_unit(inp, out):
    h, w, k, n = _dims(inp)
    return _tile(inp, n, _unit(inp, k)[::-1])


def unit_from_bottom_of_ink(inp, out):
    h, w, k, n = _dims(inp)
    rows = [inp[r][:] for r in range(n - k, n)]
    for r in rows:
        r[0] = 0
    return _tile(inp, n, rows)


def start_one_row_late(inp, out):
    h, w, k, n = _dims(inp)
    return _tile(inp, n + 1, _unit(inp, k))


def copy_keeps_marker_column(inp, out):
    h, w, k, n = _dims(inp)
    return _tile(inp, n, _unit(inp, k, keep_marker=True))


def mirrored_unit(inp, out):
    h, w, k, n = _dims(inp)
    rows = [r[::-1] for r in _unit(inp, k)]
    return _tile(inp, n, rows)


def unit_one_row_short(inp, out):
    h, w, k, n = _dims(inp)
    if k < 2:
        return None
    return _tile(inp, n, _unit(inp, k - 1))


def blank_row_between_copies(inp, out):
    h, w, k, n = _dims(inp)
    return _tile(inp, n, _unit(inp, k), period=k + 1)


def unit_one_row_long(inp, out):
    h, w, k, n = _dims(inp)
    return _tile(inp, n, _unit(inp, k + 1))


def only_whole_copies_in_first_gap(inp, out):
    # Fills only as many full units as fit, but then clears the partial tail
    # and also drops the last full unit (one copy too few).
    h, w, k, n = _dims(inp)
    g = [r[:] for r in out]
    cnt = (h - n) // k
    if cnt < 1:
        return None
    for r in range(n + (cnt - 1) * k, h):
        g[r] = [0] * w
    return g


ALTERNATIVES = [
    ("tiling starts right after the marker rows, overwriting the rest of the ink", start_at_marker_end),
    ("the repeated unit is the whole ink block instead of the marker-length rows", unit_is_whole_ink),
    ("only one copy of the unit is placed instead of repeating to the grid end", single_copy_only),
    ("the unit rows are repeated in reverse order", reversed_unit),
    ("the unit is taken from the bottom rows of the ink, not the top", unit_from_bottom_of_ink),
    ("copies start one row below where they belong", start_one_row_late),
    ("the marker column is copied along with the unit", copy_keeps_marker_column),
    ("each copied unit row is mirrored left to right", mirrored_unit),
    ("the unit length is one row short of the marker length", unit_one_row_short),
    ("a blank row separates consecutive copies", blank_row_between_copies),
    ("the unit length is one row longer than the marker length", unit_one_row_long),
    ("the last full copy is left out and the tail cleared", only_whole_copies_in_first_gap),
]


def _valid(g):
    if not isinstance(g, list) or not g or not isinstance(g[0], list):
        return False
    w = len(g[0])
    return w > 0 and all(
        isinstance(r, list) and len(r) == w
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for v in r)
        for r in g)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/12422b43.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
