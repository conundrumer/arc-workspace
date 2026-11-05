import json
from collections import Counter
from pathlib import Path


def _bars(inp):
    """Bars left to right as (col, color, length). Bars are one-cell-wide columns
    that touch the bottom edge."""
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    h, w = len(inp), len(inp[0])
    bars = []
    for c in range(w):
        cells = [inp[r][c] for r in range(h) if inp[r][c] != bg]
        if cells:
            bars.append((c, cells[0], len(cells)))
    return bg, bars


def _render(inp, bg, cols, colors, lengths, top=False):
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    for c, col, n in zip(cols, colors, lengths):
        n = max(0, min(h, n))
        rows = range(0, n) if top else range(h - n, h)
        for r in rows:
            g[r][c] = col
    return g


def _shifted(inp, cshift, lshift, cyclic=True, top=False, order=None, lfun=None):
    bg, bars = _bars(inp)
    if order is not None:
        bars = order(bars)
    n = len(bars)
    cols = [b[0] for b in bars]
    colors, lengths = [], []
    for i, b in enumerate(bars):
        ci, li = i + cshift, i + lshift
        if cyclic:
            ci %= n
            li %= n
        else:
            ci = i if not 0 <= ci < n else ci
            li = i if not 0 <= li < n else li
        colors.append(bars[ci][1])
        lengths.append(bars[li][2])
    if lfun:
        lengths = lfun(lengths)
    return _render(inp, bg, cols, colors, lengths, top)


def _norm(g, out):
    return None if g == out else g


# Correct reading: colors come from the previous bar, lengths from the next bar.

def colors_next_lengths_next(inp, out):
    return _norm(_shifted(inp, +1, +1), out)


def colors_prev_lengths_prev(inp, out):
    return _norm(_shifted(inp, -1, -1), out)


def colors_next_lengths_prev(inp, out):
    return _norm(_shifted(inp, +1, -1), out)


def colors_only(inp, out):
    return _norm(_shifted(inp, -1, 0), out)


def lengths_only(inp, out):
    return _norm(_shifted(inp, 0, +1), out)


def no_wraparound(inp, out):
    return _norm(_shifted(inp, -1, +1, cyclic=False), out)


def anchored_top(inp, out):
    return _norm(_shifted(inp, -1, +1, top=True), out)


def shift_by_two(inp, out):
    return _norm(_shifted(inp, -2, +2), out)


def order_by_length(inp, out):
    return _norm(_shifted(inp, -1, +1, order=lambda bs: sorted(bs, key=lambda b: (b[2], b[0]))), out)


def length_too_long(inp, out):
    return _norm(_shifted(inp, -1, +1, lfun=lambda ls: [n + 1 for n in ls]), out)


def length_min_of_own_and_next(inp, out):
    bg, bars = _bars(inp)
    n = len(bars)
    cols = [b[0] for b in bars]
    colors = [bars[(i - 1) % n][1] for i in range(n)]
    lengths = [min(bars[i][2], bars[(i + 1) % n][2]) for i in range(n)]
    return _norm(_render(inp, bg, cols, colors, lengths), out)


def colors_mirrored(inp, out):
    bg, bars = _bars(inp)
    cols = [b[0] for b in bars]
    colors = [b[1] for b in reversed(bars)]
    lengths = [bars[(i + 1) % len(bars)][2] for i in range(len(bars))]
    return _norm(_render(inp, bg, cols, colors, lengths), out)


ALTERNATIVES = [
    ("colors and lengths both taken from the next bar", colors_next_lengths_next),
    ("colors and lengths both taken from the previous bar", colors_prev_lengths_prev),
    ("colors from the next bar, lengths from the previous bar (directions swapped)", colors_next_lengths_prev),
    ("only colors rotate; bars keep their own lengths", colors_only),
    ("only lengths rotate; bars keep their own colors", lengths_only),
    ("rotation does not wrap: the end bars keep their own color and length", no_wraparound),
    ("bars drawn hanging from the top edge instead of standing on the bottom", anchored_top),
    ("colors and lengths rotate by two positions instead of one", shift_by_two),
    ("bars ordered by length instead of by column", order_by_length),
    ("every output bar one cell too long", length_too_long),
    ("output length is the smaller of own and next bar length", length_min_of_own_and_next),
    ("colors reversed across the bars instead of rotated", colors_mirrored),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/2601afb7.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(ok, "/", len(pairs), desc)
