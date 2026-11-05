"""Near-miss readings for ARC task a3df8b1e (marker in bottom-left corner
shoots a diagonal ray that bounces between the side walls)."""
import json
from pathlib import Path

BG = 0


def _ink(out):
    return next(v for r in out for v in r if v != BG)


def _trace(h, w, period_fn, start_row=None, stop_row=None):
    """Cells (r, c) of a ray going up from the bottom-left, c given by period_fn(k)."""
    cells = []
    for k in range(h):
        r = h - 1 - k
        cells.append((r, period_fn(k, w)))
    return cells


def _paint(h, w, cells, color):
    g = [[BG] * w for _ in range(h)]
    for r, c in cells:
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = color
    return g


def _bounce(k, w):
    if w == 1:
        return 0
    p = 2 * (w - 1)
    m = k % p
    return m if m < w else p - m


def no_bounce_stops_at_wall(inp, out):
    h, w = len(out), len(out[0])
    cells = [(h - 1 - k, k) for k in range(min(h, w))]
    return _paint(h, w, cells, _ink(out))


def wraps_around(inp, out):
    h, w = len(out), len(out[0])
    return _paint(h, w, _trace(h, w, lambda k, w: k % w), _ink(out))


def dwell_at_wall(inp, out):
    # wall column is visited twice in a row (period 2w instead of 2w-2)
    h, w = len(out), len(out[0])
    def col(k, w):
        m = k % (2 * w)
        return m if m < w else 2 * w - 1 - m
    return _paint(h, w, _trace(h, w, col), _ink(out))


def marker_erased(inp, out):
    g = [list(r) for r in out]
    g[-1][0] = BG
    return g


def mirrored_start(inp, out):
    return [list(reversed(r)) for r in out]


def wrong_color(inp, out):
    ink = _ink(out)
    new = 5 if ink != 5 else 2
    return [[new if v != BG else BG for v in r] for r in out]


def stops_halfway(inp, out):
    g = [list(r) for r in out]
    h = len(g)
    for r in range(h // 2):
        g[r] = [BG] * len(g[r])
    return g


def starts_from_top(inp, out):
    return [list(r) for r in reversed(out)]


def transposed_axis(inp, out):
    return [list(r) for r in zip(*out)]


def every_other_row(inp, out):
    g = [list(r) for r in out]
    h = len(g)
    for r in range(h):
        if (h - 1 - r) % 2 == 1:
            g[r] = [BG] * len(g[r])
    return g


def complement_painted(inp, out):
    ink = _ink(out)
    return [[BG if v != BG else ink for v in r] for r in out]


def both_headings_union(inp, out):
    # also draws the trace that starts heading the opposite way (shifted by one column)
    h, w = len(out), len(out[0])
    ink = _ink(out)
    g = [list(r) for r in out]
    for k in range(h):
        c = _bounce(k + w - 1, w)
        g[h - 1 - k][c] = ink
    return g


ALTERNATIVES = [
    ("ray goes straight up-right and stops at the wall instead of bouncing", no_bounce_stops_at_wall),
    ("ray wraps around to the other side at the wall instead of reflecting", wraps_around),
    ("ray dwells one extra step at each wall (off-by-one reflection)", dwell_at_wall),
    ("marker cell itself is not kept in the trace", marker_erased),
    ("ray starts from the bottom-right corner (mirrored)", mirrored_start),
    ("trace drawn in the wrong color", wrong_color),
    ("ray stops after half the grid height", stops_halfway),
    ("ray starts from the top-left corner and goes down", starts_from_top),
    ("ray runs along the other axis (transposed trace)", transposed_axis),
    ("only every other ray step is drawn", every_other_row),
    ("the background is painted and the trace left empty", complement_painted),
    ("both a rising and a phase-shifted trace are drawn", both_headings_union),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/a3df8b1e.json').read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
