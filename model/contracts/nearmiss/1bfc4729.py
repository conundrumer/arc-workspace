import json
from pathlib import Path


def _marks(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def _halves(inp):
    """Return [(top, bottom, color, line_row)] for the two stacked halves."""
    h = len(inp)
    half = h // 2
    ms = sorted(_marks(inp))
    top = [m for m in ms if m[0] < half][0]
    bot = [m for m in ms if m[0] >= half][0]
    return [(0, half - 1, top[2], top[0]), (half, h - 1, bot[2], bot[0])]


def _draw(inp, spec, border=True, line=True, inner=False):
    """spec: list of (top, bottom, color, line_row). Draws on a blank grid."""
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    for t, b, col, lr in spec:
        if border:
            for c in range(w):
                g[t][c] = col
                g[b][c] = col
            for r in range(t, b + 1):
                g[r][0] = col
                g[r][w - 1] = col
        if inner:
            for c in range(w):
                g[t][c] = col
                g[b][c] = col
        if line and t <= lr <= b:
            for c in range(w):
                g[lr][c] = col
    return g


def swap_colors(inp, out):
    (_, _, a, _), (_, _, b, _) = _halves(inp)
    return [[b if v == a else a if v == b else v for v in row] for row in out]


def no_border(inp, out):
    return _draw(inp, _halves(inp), border=False)


def no_line(inp, out):
    return _draw(inp, _halves(inp), line=False)


def line_off_by_one(inp, out):
    spec = [(t, b, col, min(b, lr + 1)) for t, b, col, lr in _halves(inp)]
    return _draw(inp, spec)


def columns_instead(inp, out):
    h, w = len(inp), len(inp[0])
    half = w // 2
    ms = sorted(_marks(inp), key=lambda m: m[1])
    left, right = ms[0], ms[1]
    g = [[0] * w for _ in range(h)]
    for l, r, col, lc in [(0, half - 1, left[2], left[1]), (half, w - 1, right[2], right[1])]:
        for rr in range(h):
            g[rr][l] = col
            g[rr][r] = col
            g[rr][lc] = col
        for c in range(l, r + 1):
            g[0][c] = col
            g[h - 1][c] = col
    return g


def one_outer_frame(inp, out):
    h, w = len(inp), len(inp[0])
    spec = _halves(inp)
    g = _draw(inp, spec, border=False)
    col = spec[0][2]
    for c in range(w):
        g[0][c] = col
        g[h - 1][c] = col
    for r in range(h):
        g[r][0] = col
        g[r][w - 1] = col
    return g


def split_off_by_one(inp, out):
    h = len(inp)
    half = h // 2 + 1
    (_, _, ca, la), (_, _, cb, lb) = _halves(inp)
    return _draw(inp, [(0, half - 1, ca, la), (half, h - 1, cb, lb)])


def fill_halves(inp, out):
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    for t, b, col, _ in _halves(inp):
        for r in range(t, b + 1):
            for c in range(w):
                g[r][c] = col
    return g


def closed_boxes(inp, out):
    return _draw(inp, _halves(inp), inner=True)


def top_half_only(inp, out):
    spec = _halves(inp)[:1]
    return _draw(inp, spec)


def line_at_half_edge(inp, out):
    # line drawn on the half's inner edge instead of at the mark's distance
    h = len(inp)
    half = h // 2
    (_, _, ca, _), (_, _, cb, _) = _halves(inp)
    return _draw(inp, [(0, half - 1, ca, half - 1), (half, h - 1, cb, half)])


ALTERNATIVES = [
    ("each half takes the other half's color", swap_colors),
    ("only the mark lines are drawn, no border", no_border),
    ("only the border is drawn, no line through the mark", no_line),
    ("each line sits one cell further from the half's outer edge", line_off_by_one),
    ("halves split left/right, with vertical lines at the mark columns", columns_instead),
    ("one frame around the whole grid in the top color, lines in own colors", one_outer_frame),
    ("halves split one row too low", split_off_by_one),
    ("each half is filled solid with its color", fill_halves),
    ("each half is a closed box, with a border on its inner edge too", closed_boxes),
    ("only the top half is drawn", top_half_only),
    ("line drawn on the inner edge of each half instead of at the mark", line_at_half_edge),
]


def _valid(g, out):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/1bfc4729.json").read_text())
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", e)
                g = None
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
