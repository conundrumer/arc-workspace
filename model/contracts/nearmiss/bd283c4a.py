import json
from collections import Counter
from pathlib import Path


def _counts(inp):
    c = Counter(v for r in inp for v in r)
    # ascending by count (the true fill order: rightmost column first)
    return sorted(c.items(), key=lambda kv: (kv[1], kv[0]))


def _cells(h, w, start, axis, snake=False):
    """Raster order of cells. start: (top|bottom, left|right); axis: 'col' runs down/up a column
    then steps to the next column; 'row' runs along a row then steps to the next row."""
    v, hz = start
    rows = list(range(h)) if v == "top" else list(range(h - 1, -1, -1))
    cols = list(range(w)) if hz == "left" else list(range(w - 1, -1, -1))
    order = []
    if axis == "col":
        for k, c in enumerate(cols):
            rr = rows if not (snake and k % 2) else rows[::-1]
            order += [(r, c) for r in rr]
    else:
        for k, r in enumerate(rows):
            cc = cols if not (snake and k % 2) else cols[::-1]
            order += [(r, c) for c in cc]
    return order


def _fill(h, w, seq, order):
    g = [[0] * w for _ in range(h)]
    i = 0
    for color, n in seq:
        for _ in range(n):
            r, c = order[i]
            g[r][c] = color
            i += 1
    return g


def _make(start, axis, snake=False, rank=None, shift=0):
    def f(inp, out):
        h, w = len(inp), len(inp[0])
        seq = _counts(inp)
        if rank == "desc":
            seq = seq[::-1]
        elif rank == "value":
            seq = sorted(seq, key=lambda kv: kv[0])
        elif rank == "first":
            seen = []
            for r in inp:
                for v in r:
                    if v not in seen:
                        seen.append(v)
            d = dict(seq)
            seq = [(c, d[c]) for c in seen]
        if shift:
            # each color but the last takes shift fewer cells; the last takes the rest
            seq = [(c, max(n - shift, 0)) for c, n in seq[:-1]] + [seq[-1]]
            tot = h * w - sum(n for _, n in seq[:-1])
            seq[-1] = (seq[-1][0], tot)
        return _fill(h, w, seq, _cells(h, w, start, axis, snake))
    return f


def _swap_two_lowest(inp, out):
    seq = _counts(inp)
    a, b = seq[0][0], seq[1][0]
    return [[b if v == a else a if v == b else v for v in r] for r in out]


def _drop_lowest(inp, out):
    # the rarest color is ignored; the next color fills its cells
    seq = _counts(inp)
    a, b = seq[0][0], seq[1][0]
    return [[b if v == a else v for v in r] for r in out]


def _transpose_out(inp, out):
    h, w = len(out), len(out[0])
    return [[out[r][c] for r in range(h)] for c in range(w)] if h != w else [list(r) for r in zip(*out)]


ALTERNATIVES = [
    ("fill starts at the top-left corner, down columns, moving right", _make(("top", "left"), "col")),
    ("fill starts at the bottom-right corner, up columns, moving left", _make(("bottom", "right"), "col")),
    ("fill runs along rows from the top-right corner, moving down", _make(("top", "right"), "row")),
    ("fill runs along rows from the bottom-left corner, moving up", _make(("bottom", "left"), "row")),
    ("colors ranked with the highest count first at the top-right corner", _make(("top", "right"), "col", rank="desc")),
    ("colors ordered by first appearance in the input instead of by count", _make(("top", "right"), "col", rank="first")),
    ("colors ordered by color value instead of by count", _make(("top", "right"), "col", rank="value")),
    ("fill snakes along rows: rows alternate right-to-left and left-to-right", _make(("top", "right"), "row", snake=True)),
    ("each non-last color takes one cell fewer than its count", _make(("top", "right"), "col", shift=1)),
    ("the two rarest colors swap places in the true output", _swap_two_lowest),
    ("the rarest color is dropped and the next rarest fills its cells", _drop_lowest),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/bd283c4a.json").read_text())
    pairs = task["train"]

    def valid(g, out):
        return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                and all(type(v) is int and 0 <= v <= 9 for r in g for v in r) and g != out)

    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
