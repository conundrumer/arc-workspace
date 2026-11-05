import json
from pathlib import Path

MARK = 2
HALO = 1


def _copy(g):
    return [r[:] for r in g]


def _markers(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == MARK]


def _stamp(inp, offsets, mark_pts=None, color=HALO, wrap=False, overwrite=False):
    g = _copy(inp)
    h, w = len(g), len(g[0])
    pts = _markers(inp) if mark_pts is None else mark_pts
    for r, c in pts:
        for dr, dc in offsets:
            rr, cc = r + dr, c + dc
            if wrap:
                rr, cc = rr % h, cc % w
            elif not (0 <= rr < h and 0 <= cc < w):
                continue
            if overwrite or g[rr][cc] == 0:
                g[rr][cc] = color
    return g


RING8 = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
PLUS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
RING24 = [(a, b) for a in range(-2, 3) for b in range(-2, 3) if (a, b) != (0, 0)]
HORIZ = [(0, -1), (0, 1)]


def plus_only(inp, out):
    return _stamp(inp, PLUS)


def diag_only(inp, out):
    return _stamp(inp, DIAG)


def radius2(inp, out):
    return _stamp(inp, RING24)


def wrong_color(inp, out):
    return _stamp(inp, RING8, color=5)


def wrapped(inp, out):
    return _stamp(inp, RING8, wrap=True)


def first_marker_only(inp, out):
    pts = _markers(inp)
    return _stamp(inp, RING8, mark_pts=pts[:1])


def last_marker_only(inp, out):
    pts = _markers(inp)
    return _stamp(inp, RING8, mark_pts=pts[-1:])


def other_colors_haloed(inp, out):
    pts = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v not in (0, MARK)]
    return _stamp(inp, RING8, mark_pts=pts)


def all_nonzero_haloed(inp, out):
    pts = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]
    return _stamp(inp, RING8, mark_pts=pts)


def marker_cell_filled(inp, out):
    return _stamp(inp, RING8 + [(0, 0)], overwrite=True)


def shifted_down_right(inp, out):
    return _stamp(inp, [(a + 1, b + 1) for a, b in RING8])


def horizontal_only(inp, out):
    return _stamp(inp, HORIZ)


ALTERNATIVES = [
    ("halo covers only the 4 orthogonal neighbours of each 2", plus_only),
    ("halo covers only the 4 diagonal neighbours of each 2", diag_only),
    ("halo is 5x5 (radius 2) around each 2", radius2),
    ("halo is color 5 instead of 1", wrong_color),
    ("halo wraps around the grid edges instead of clipping", wrapped),
    ("only the first 2 in reading order gets a halo", first_marker_only),
    ("only the last 2 in reading order gets a halo", last_marker_only),
    ("halos drawn around the non-2 colored cells instead of the 2s", other_colors_haloed),
    ("halos drawn around every nonzero cell, 2s and others", all_nonzero_haloed),
    ("the 2 itself is painted over with 1 as part of a 3x3 block", marker_cell_filled),
    ("halo is the 3x3 ring shifted one cell down and right", shifted_down_right),
    ("halo covers only left and right neighbours of each 2", horizontal_only),
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
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/dc1df850.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
