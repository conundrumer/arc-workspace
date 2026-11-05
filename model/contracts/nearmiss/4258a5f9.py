import json
from pathlib import Path


def _marks(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def _halo_color(inp, out):
    ink = {v for row in inp for v in row}
    for row in out:
        for v in row:
            if v not in ink:
                return v
    return 1


def _stamp(inp, out, offsets, marks=None, color=None, keep_marker=True, dr=0, dc=0):
    """Start from the input; paint `color` at each offset around each mark."""
    h, w = len(inp), len(inp[0])
    col = _halo_color(inp, out) if color is None else color
    g = [row[:] for row in inp]
    ms = _marks(inp) if marks is None else marks
    for r, c in ms:
        for a, b in offsets:
            y, x = r + a + dr, c + b + dc
            if 0 <= y < h and 0 <= x < w and (a, b) != (0, 0):
                g[y][x] = col
        if not keep_marker:
            g[r][c] = col
    return g


RING = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
PLUS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
BIG = [(a, b) for a in range(-2, 3) for b in range(-2, 3) if (a, b) != (0, 0)]
BOX5 = [(a, b) for a in range(-2, 3) for b in range(-2, 3) if max(abs(a), abs(b)) == 2]


def plus_only(inp, out):
    return _stamp(inp, out, PLUS)


def diag_only(inp, out):
    return _stamp(inp, out, DIAG)


def radius2_filled(inp, out):
    return _stamp(inp, out, BIG)


def radius2_ring_only(inp, out):
    return _stamp(inp, out, BOX5)


def wrong_color(inp, out):
    c = _halo_color(inp, out)
    return _stamp(inp, out, RING, color=(c + 1) % 10 or 2)


def marker_overwritten(inp, out):
    return _stamp(inp, out, RING, keep_marker=False)


def marker_erased(inp, out):
    g = _stamp(inp, out, RING)
    for r, c in _marks(inp):
        g[r][c] = 0
    return g


def shifted_down_right(inp, out):
    return _stamp(inp, out, RING, dr=1, dc=1)


def top_marker_only(inp, out):
    ms = sorted(_marks(inp))
    return _stamp(inp, out, RING, marks=ms[:1])


def skip_last_marker(inp, out):
    ms = sorted(_marks(inp))
    return _stamp(inp, out, RING, marks=ms[:-1])


def left_half_only(inp, out):
    w = len(inp[0])
    ms = [m for m in _marks(inp) if m[1] < w / 2]
    return _stamp(inp, out, RING, marks=ms)


def row_wide_band(inp, out):
    # halo spreads across the whole row above and below each marker
    h, w = len(inp), len(inp[0])
    col = _halo_color(inp, out)
    g = [row[:] for row in inp]
    for r, c in _marks(inp):
        for y in (r - 1, r + 1):
            if 0 <= y < h:
                for x in range(w):
                    g[y][x] = col
    return g


ALTERNATIVES = [
    ("halo on the four edge neighbours only (plus shape)", plus_only),
    ("halo on the four diagonal neighbours only", diag_only),
    ("halo is a filled 5x5 block around each marker", radius2_filled),
    ("halo is a ring at distance 2 instead of distance 1", radius2_ring_only),
    ("halo drawn in the wrong color", wrong_color),
    ("marker cell is also painted with the halo color", marker_overwritten),
    ("marker cell is cleared to 0 inside its halo", marker_erased),
    ("halo is placed one row down and one column right of the marker", shifted_down_right),
    ("only the topmost marker gets a halo", top_marker_only),
    ("the last marker in reading order gets no halo", skip_last_marker),
    ("only markers in the left half get a halo", left_half_only),
    ("halo spreads across the whole row above and below each marker", row_wide_band),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/4258a5f9.json").read_text())
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
