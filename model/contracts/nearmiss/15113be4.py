"""Near-miss rules for ARC task 15113be4.

Rule: a grid of 3x3 cells split by separator lines (color 4). A key shape of
one odd color sits in a bordered corner block. The key shape (one cell-sized
footprint, drawn at scale 2) is stamped in the key color onto every other cell
whose ink (color 1) covers all footprint positions.
"""
import json
from pathlib import Path

PERIOD = 4
SIZE = 3


def _ok(inp):
    return len(inp) == len(inp[0]) and len(inp) % PERIOD == PERIOD - 1


def _cells(inp):
    n = (len(inp) + 1) // PERIOD
    return [(a, b) for a in range(n) for b in range(n)]


def _pos(a, b):
    return [(a * PERIOD + i, b * PERIOD + j) for i in range(SIZE) for j in range(SIZE)]


def _key_color(inp):
    for row in inp:
        for v in row:
            if v not in (0, 1, 4):
                return v
    return None


def _is_key_cell(inp, a, b):
    return any(inp[r][c] not in (0, 1) for r, c in _pos(a, b))


def _footprint(inp, out):
    """Footprint in cell frame, read from the true output."""
    for a, b in _cells(inp):
        ch = {(r - a * PERIOD, c - b * PERIOD) for r, c in _pos(a, b) if inp[r][c] != out[r][c]}
        if ch:
            return ch
    return set()


def _stamped(inp, out):
    return [(a, b) for a, b in _cells(inp)
            if any(inp[r][c] != out[r][c] for r, c in _pos(a, b))]


def _copy(g):
    return [row[:] for row in g]


def _stamp(inp, fp, col, cond):
    """Paint fp in color col on non-key cells where cond(ink_set, fp) holds."""
    g = _copy(inp)
    for a, b in _cells(inp):
        if _is_key_cell(inp, a, b):
            continue
        ink = {(i, j) for i in range(SIZE) for j in range(SIZE)
               if inp[a * PERIOD + i][b * PERIOD + j] == 1}
        if cond(ink, fp):
            for i, j in fp:
                g[a * PERIOD + i][b * PERIOD + j] = col
    return g


def _covers(ink, fp):
    return fp <= ink


def _prep(inp, out):
    if not _ok(inp):
        return None
    fp = _footprint(inp, out)
    col = _key_color(inp)
    if not fp or col is None:
        return None
    return fp, col


def wrong_color(inp, out):
    p = _prep(inp, out)
    if not p:
        return None
    fp, col = p
    new = 5 if col != 5 else 2
    return [[new if v == col and inp[r][c] == 1 else v for c, v in enumerate(row)]
            for r, row in enumerate(out)]


def first_only(inp, out):
    if not _prep(inp, out):
        return None
    st = _stamped(inp, out)
    keep = st[0]
    g = _copy(out)
    for a, b in st[1:]:
        for r, c in _pos(a, b):
            g[r][c] = inp[r][c]
    return g


def top_row_only(inp, out):
    if not _prep(inp, out):
        return None
    st = _stamped(inp, out)
    top = min(a for a, _ in st)
    g = _copy(out)
    for a, b in st:
        if a != top:
            for r, c in _pos(a, b):
                g[r][c] = inp[r][c]
    return g


def exact_match_only(inp, out):
    """Stamp only cells whose ink equals the footprint exactly."""
    p = _prep(inp, out)
    if not p:
        return None
    fp, col = p
    return _stamp(inp, fp, col, lambda ink, f: ink == f)


def mirrored_footprint(inp, out):
    p = _prep(inp, out)
    if not p:
        return None
    fp, col = p
    f2 = {(i, SIZE - 1 - j) for i, j in fp}
    return _stamp(inp, f2, col, _covers)


def transposed_footprint(inp, out):
    p = _prep(inp, out)
    if not p:
        return None
    fp, col = p
    f2 = {(j, i) for i, j in fp}
    return _stamp(inp, f2, col, _covers)


def stamp_everywhere(inp, out):
    """Ignore the ink condition: stamp every non-key cell."""
    p = _prep(inp, out)
    if not p:
        return None
    fp, col = p
    return _stamp(inp, fp, col, lambda ink, f: True)


def any_overlap(inp, out):
    """Stamp where ink touches at least one footprint position."""
    p = _prep(inp, out)
    if not p:
        return None
    fp, col = p
    return _stamp(inp, fp, col, lambda ink, f: bool(ink & f))


def recolor_all_ink(inp, out):
    """In each stamped cell, recolor all ink, not only the footprint."""
    p = _prep(inp, out)
    if not p:
        return None
    fp, col = p
    g = _copy(out)
    for a, b in _stamped(inp, out):
        for r, c in _pos(a, b):
            if inp[r][c] == 1:
                g[r][c] = col
    return g


def shifted_footprint(inp, out):
    """Footprint offset one column to the right (clipped cells skipped)."""
    p = _prep(inp, out)
    if not p:
        return None
    fp, col = p
    f2 = {(i, j + 1) for i, j in fp}
    if any(j >= SIZE for _, j in f2):
        f2 = {(i, j) for i, j in f2 if j < SIZE}
    return _stamp(inp, f2, col, _covers)


def complement_footprint(inp, out):
    """Stamp the complement of the footprint where ink covers the complement."""
    p = _prep(inp, out)
    if not p:
        return None
    fp, col = p
    f2 = {(i, j) for i in range(SIZE) for j in range(SIZE)} - fp
    return _stamp(inp, f2, col, lambda ink, f: bool(ink & f))


ALTERNATIVES = [
    ("stamp in a wrong color instead of the key color", wrong_color),
    ("stamp only the first matching cell", first_only),
    ("stamp only matching cells in the top cell row", top_row_only),
    ("stamp only cells whose ink equals the footprint exactly", exact_match_only),
    ("footprint mirrored left to right", mirrored_footprint),
    ("footprint transposed", transposed_footprint),
    ("stamp the footprint in every non-key cell, ignoring ink", stamp_everywhere),
    ("stamp where ink overlaps at least one footprint position", any_overlap),
    ("recolor all ink of each matching cell, not just the footprint", recolor_all_ink),
    ("footprint offset one column right", shifted_footprint),
    ("footprint complement stamped where ink touches it", complement_footprint),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/15113be4.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
