"""Near-miss rules for ARC task 6d1d5c90.

True rule: column 0 is a band of 6 with one 2 (the marker) at row m.
Drop column 0 and rotate the remaining rows downward, cyclically, by m.
"""
import json
from pathlib import Path


def _marker_row(inp):
    for r, row in enumerate(inp):
        if row[0] == 2:
            return r
    return 0


def _body(inp):
    return [row[1:] for row in inp]


def _rot_down(rows, k):
    n = len(rows)
    k %= n
    return [list(rows[(i - k) % n]) for i in range(n)]


def shift_up(inp, out):
    return _rot_down(_body(inp), -_marker_row(inp))


def shift_plus_one(inp, out):
    return _rot_down(_body(inp), _marker_row(inp) + 1)


def shift_minus_one(inp, out):
    return _rot_down(_body(inp), _marker_row(inp) - 1)


def keep_band_column(inp, out):
    return _rot_down(inp, _marker_row(inp))


def shift_from_bottom(inp, out):
    n = len(inp)
    return _rot_down(_body(inp), n - 1 - _marker_row(inp))


def shift_not_cyclic(inp, out):
    m = _marker_row(inp)
    body = _body(inp)
    n = len(body)
    w = len(body[0])
    return [list(body[i - m]) if i - m >= 0 else [0] * w for i in range(n)]


def shift_columns(inp, out):
    m = _marker_row(inp)
    res = []
    for row in _body(inp):
        w = len(row)
        res.append([row[(j - m) % w] for j in range(w)])
    return res


def shift_one_only(inp, out):
    return _rot_down(_body(inp), 1)


def shift_by_first_band_row(inp, out):
    k = next((r for r, row in enumerate(inp) if row[0] == 6), 0)
    return _rot_down(_body(inp), k)


def drop_last_column(inp, out):
    return _rot_down([row[:-1] for row in inp], _marker_row(inp))


def flip_rows(inp, out):
    return [list(r) for r in reversed(out)]


def no_shift(inp, out):
    return _body(inp)


ALTERNATIVES = [
    ("rows rotate upward by the marker row instead of downward", shift_up),
    ("rotation is one row too far (marker index plus one)", shift_plus_one),
    ("rotation is one row too short (marker index minus one)", shift_minus_one),
    ("band column kept in the output and rotated with the rows", keep_band_column),
    ("rotation counted from the bottom edge instead of the top", shift_from_bottom),
    ("rows pushed down without wrapping, vacated top rows filled with 0", shift_not_cyclic),
    ("cells rotate along each row (columns) instead of rows", shift_columns),
    ("rotation is always one row regardless of marker position", shift_one_only),
    ("rotation taken from the first 6 cell of the band instead of the 2", shift_by_first_band_row),
    ("crop drops the last column instead of the band column", drop_last_column),
    ("output row order reversed (vertical flip) instead of rotated", flip_rows),
    ("band column cropped but rows not rotated at all", no_shift),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1
        and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/6d1d5c90.json").read_text())
    pairs = task["train"]
    print(f"task 6d1d5c90, {len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
