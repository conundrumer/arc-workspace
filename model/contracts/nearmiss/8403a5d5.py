import json
from pathlib import Path


def _info(inp):
    h, w = len(inp), len(inp[0])
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0:
                return h, w, r, c, inp[r][c]
    return None


def _dot_color(out, col):
    for row in out:
        for v in row:
            if v not in (0, col):
                return v
    return None


def _dot_pattern(inp, out, rows_for):
    h, w, r, c, col = _info(inp)
    d = _dot_color(out, col)
    g = [row[:] for row in out]
    for y in range(h):
        for x in range(w):
            if g[y][x] == d:
                g[y][x] = 0
    k = 0
    for x in range(c + 1, w, 2):
        yy = rows_for(k, h)
        if yy is not None and 0 <= yy < h:
            g[yy][x] = d
        k += 1
    return g


def no_alternate_top(inp, out):
    return _dot_pattern(inp, out, lambda k, h: 0)


def no_alternate_bottom(inp, out):
    return _dot_pattern(inp, out, lambda k, h: h - 1)


def start_bottom(inp, out):
    return _dot_pattern(inp, out, lambda k, h: h - 1 if k % 2 == 0 else 0)


def dots_inset(inp, out):
    return _dot_pattern(inp, out, lambda k, h: 1 if k % 2 == 0 else h - 2)


def no_dots(inp, out):
    h, w, r, c, col = _info(inp)
    d = _dot_color(out, col)
    return [[0 if v == d else v for v in row] for row in out]


def dots_bar_color(inp, out):
    h, w, r, c, col = _info(inp)
    d = _dot_color(out, col)
    return [[col if v == d else v for v in row] for row in out]


def only_first_dot(inp, out):
    h, w, r, c, col = _info(inp)
    d = _dot_color(out, col)
    g = [row[:] for row in out]
    seen = False
    for x in range(w):
        for y in range(h):
            if g[y][x] == d:
                if seen:
                    g[y][x] = 0
                seen = True
    return g


def single_bar(inp, out):
    h, w, r, c, col = _info(inp)
    g = [row[:] for row in out]
    for x in range(c + 1, w):
        for y in range(h):
            if g[y][x] == col:
                g[y][x] = 0
    return g


def every_column_bars(inp, out):
    h, w, r, c, col = _info(inp)
    d = _dot_color(out, col)
    g = [row[:] for row in out]
    for x in range(c, w):
        for y in range(h):
            g[y][x] = col
    return g


def mirrored_left(inp, out):
    h, w, r, c, col = _info(inp)
    return [row[::-1] for row in out]


def mirrored_walk(inp, out):
    # bars walk to the left of the marker instead of the right
    h, w, r, c, col = _info(inp)
    d = _dot_color(out, col)
    g = [[0] * w for _ in range(h)]
    for x in range(c, -1, -2):
        for y in range(h):
            g[y][x] = col
    k = 0
    for x in range(c - 1, -1, -2):
        g[0 if k % 2 == 0 else h - 1][x] = d
        k += 1
    return g


def bars_short(inp, out):
    h, w, r, c, col = _info(inp)
    g = [row[:] for row in out]
    for x in range(w):
        if g[0][x] == col:
            g[0][x] = 0
    return g


def last_bar_missing(inp, out):
    h, w, r, c, col = _info(inp)
    xs = [x for x in range(w) if out[h - 1][x] == col]
    g = [row[:] for row in out]
    for y in range(h):
        g[y][xs[-1]] = 0
    return g


def dot_on_bar_column(inp, out):
    h, w, r, c, col = _info(inp)
    d = _dot_color(out, col)
    g = [row[:] for row in out]
    for y in range(h):
        for x in range(w):
            if out[y][x] == d:
                g[y][x] = col if x > 0 else 0
                g[y][x - 1] = d
    return g


ALTERNATIVES = [
    ("every dot sits at the top end, no alternation", no_alternate_top),
    ("every dot sits at the bottom end, no alternation", no_alternate_bottom),
    ("dots alternate but start at the bottom end", start_bottom),
    ("dots one row inside the grid edge", dots_inset),
    ("no dots drawn, only the bars", no_dots),
    ("dots take the bar color", dots_bar_color),
    ("only the first dot is drawn", only_first_dot),
    ("only the marker bar, no repeated bars", single_bar),
    ("bars on every column right of the marker", every_column_bars),
    ("pattern walks left of the marker", mirrored_walk),
    ("bars stop one row short of the top", bars_short),
    ("last bar left out", last_bar_missing),
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
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/8403a5d5.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p['input'], p['output']), p['output']) for p in pairs)
        print(n, desc)
