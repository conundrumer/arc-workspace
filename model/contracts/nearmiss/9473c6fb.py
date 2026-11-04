from pathlib import Path
import json
from collections import Counter

CYC = [2, 8, 5]


def bg_of(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def marks(inp):
    b = bg_of(inp)
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != b]


def recolor(inp, key, cyc=CYC, reverse=False, absolute=False, skip=None, per_mark=False):
    """Colour each mark by the rank of key(mark) among occupied key values, cycling cyc."""
    ms = marks(inp)
    if per_mark:
        order = sorted(ms, key=lambda m: (key(m), m), reverse=reverse)
        idx = {m: i for i, m in enumerate(order)}
    else:
        vals = sorted({key(m) for m in ms}, reverse=reverse)
        rank = {v: (v if absolute else i) for i, v in enumerate(vals)}
        idx = {m: rank[key(m)] for m in ms}
    g = [row[:] for row in inp]
    for m in ms:
        if skip and skip(m, inp):
            continue
        g[m[0]][m[1]] = cyc[idx[m] % len(cyc)]
    return g


def row_key(m):
    return m[0]


def col_key(m):
    return m[1]


def true_axis_key(inp, out):
    for k in (row_key, col_key):
        if recolor(inp, k) == out:
            return k
    return row_key


def other_axis_key(inp, out):
    return col_key if true_axis_key(inp, out) is row_key else row_key


def wrong_order(inp, out):
    return recolor(inp, true_axis_key(inp, out), cyc=[2, 5, 8])


def wrong_axis(inp, out):
    return recolor(inp, other_axis_key(inp, out))


def reversed_dir(inp, out):
    return recolor(inp, true_axis_key(inp, out), reverse=True)


def slow_cycle(inp, out):
    return recolor(inp, true_axis_key(inp, out), cyc=[2, 2, 8, 8, 5, 5])


def start_offset(inp, out):
    return recolor(inp, true_axis_key(inp, out), cyc=[8, 5, 2])


def color_map(inp, out):
    b = bg_of(inp)
    order = []
    for row in inp:
        for v in row:
            if v != b and v not in order:
                order.append(v)
    m = {v: CYC[i % 3] for i, v in enumerate(order)}
    return [[m.get(v, v) for v in row] for row in inp]


def all_one(inp, out):
    b = bg_of(inp)
    return [[2 if v != b else v for v in row] for row in inp]


def two_cycle(inp, out):
    return recolor(inp, true_axis_key(inp, out), cyc=[2, 8])


def absolute_index(inp, out):
    return recolor(inp, true_axis_key(inp, out), absolute=True)


def last_line_untouched(inp, out):
    k = true_axis_key(inp, out)
    last = max(k(m) for m in marks(inp))
    return recolor(inp, k, skip=lambda m, i: k(m) == last)


def diagonal(inp, out):
    return recolor(inp, lambda m: m[0] + m[1])


def first_line_untouched(inp, out):
    k = true_axis_key(inp, out)
    first = min(k(m) for m in marks(inp))
    return recolor(inp, k, skip=lambda m, i: k(m) == first)


ALTERNATIVES = [
    ("cycle colours in order 2,5,8 instead of 2,8,5", wrong_order),
    ("rank marks by the wrong axis (columns instead of rows or the reverse)", wrong_axis),
    ("rank from the far edge, so the cycle starts at the opposite side", reversed_dir),
    ("cycle advances every second row/column instead of every one", slow_cycle),
    ("cycle starts at 8 instead of 2", start_offset),
    ("recolor by input mark color (by first appearance) rather than by position", color_map),
    ("every mark gets the single color 2, no cycle", all_one),
    ("cycle has only two colors 2,8", two_cycle),
    ("cycle index is the absolute row/column number, counting empty lines", absolute_index),
    ("last occupied row/column is left unrecolored", last_line_untouched),
    ("marks ranked along the diagonal r+c", diagonal),
    ("first occupied row/column is left unrecolored", first_line_untouched),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/9473c6fb.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
