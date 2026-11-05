import json
from pathlib import Path


def _color(inp):
    return inp[0][0]


def _bg(inp, out):
    c = _color(inp)
    for row in out:
        for v in row:
            if v != c:
                return v
    return 0


def _draw(inp, out, size, rowline, colline, bg=None, line=None):
    n = size
    c = _color(inp) if line is None else line
    b = _bg(inp, out) if bg is None else bg
    return [[c if (rowline(i) or colline(j)) else b for j in range(n)]
            for i in range(n)]


def _period_from(n, w, g, start="tl"):
    p = w + g

    def tl(i):
        return i % p >= w

    def br(i):
        return (n - 1 - i) % p >= w

    return tl if start == "tl" else br


def anchor_bottom_right(inp, out):
    n = len(out)
    f = _period_from(n, len(inp), 1, "br")
    return _draw(inp, out, n, f, f)


def anchor_top_right(inp, out):
    n = len(out)
    r = _period_from(n, len(inp), 1, "tl")
    c = _period_from(n, len(inp), 1, "br")
    return _draw(inp, out, n, r, c)


def anchor_bottom_left(inp, out):
    n = len(out)
    r = _period_from(n, len(inp), 1, "br")
    c = _period_from(n, len(inp), 1, "tl")
    return _draw(inp, out, n, r, c)


def gap_two(inp, out):
    n = len(out)
    f = _period_from(n, len(inp), 2, "tl")
    return _draw(inp, out, n, f, f)


def no_gap_tile_minus_one(inp, out):
    n = len(out)
    w = len(inp) - 1
    if w < 1:
        return None
    f = _period_from(n, w, 1, "tl")
    return _draw(inp, out, n, f, f)


def line_before_tile(inp, out):
    n = len(out)
    w = len(inp)
    f = lambda i: i % (w + 1) == 0
    return _draw(inp, out, n, f, f)


def horizontal_only(inp, out):
    n = len(out)
    f = _period_from(n, len(inp), 1, "tl")
    return _draw(inp, out, n, f, lambda j: False)


def vertical_only(inp, out):
    n = len(out)
    f = _period_from(n, len(inp), 1, "tl")
    return _draw(inp, out, n, lambda i: False, f)


def swap_line_and_background(inp, out):
    c = _color(inp)
    b = _bg(inp, out)
    return [[b if v == c else c for v in row] for row in out]


def no_edge_lines(inp, out):
    n = len(out)
    f = _period_from(n, len(inp), 1, "tl")
    g = lambda i: f(i) and i != n - 1
    return _draw(inp, out, n, g, g)


def frame_one_smaller(inp, out):
    n = len(out) - 1
    f = _period_from(n, len(inp), 1, "tl")
    return _draw(inp, out, n, f, f)


def input_unchanged(inp, out):
    return [row[:] for row in inp]


def _skip_same(fn):
    def wrapped(inp, out):
        g = fn(inp, out)
        return None if g == out else g
    return wrapped


ALTERNATIVES = [
    ("lines counted from the bottom-right corner", anchor_bottom_right),
    ("rows counted from the top, columns from the right", anchor_top_right),
    ("rows counted from the bottom, columns from the left", anchor_bottom_left),
    ("separating lines two cells wide", gap_two),
    ("tile one cell narrower than the input", no_gap_tile_minus_one),
    ("a line comes before each tile instead of after", line_before_tile),
    ("only horizontal lines drawn", horizontal_only),
    ("only vertical lines drawn", vertical_only),
    ("line color and background color swapped", swap_line_and_background),
    ("no line drawn on the last row and column", no_edge_lines),
    ("frame one cell smaller than the true size", frame_one_smaller),
    ("input returned unchanged", input_unchanged),
]
ALTERNATIVES = [(d, _skip_same(f)) for d, f in ALTERNATIVES]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/695367ec.json').read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
