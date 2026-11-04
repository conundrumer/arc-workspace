from pathlib import Path
import json
from collections import Counter


def bg_of(g):
    return Counter(c for r in g for c in r).most_common(1)[0][0]


def shift_row(row, d, bg, wrap=False, fill=None):
    w = len(row)
    f = bg if fill is None else fill
    res = []
    for j in range(w):
        s = j - d
        if wrap:
            res.append(row[s % w])
        else:
            res.append(row[s] if 0 <= s < w else f)
    return res


def shift_rows(inp, pred, d, wrap=False, fill=None):
    bg = bg_of(inp)
    return [shift_row(r, d(i) if callable(d) else d, bg, wrap, fill) if pred(i) else list(r)
            for i, r in enumerate(inp)]


def left(inp, out):
    return shift_rows(inp, lambda i: i % 2 == 1, -1)


def by_two(inp, out):
    return shift_rows(inp, lambda i: i % 2 == 1, 2)


def even_rows(inp, out):
    return shift_rows(inp, lambda i: i % 2 == 0, 1)


def wrapped(inp, out):
    return shift_rows(inp, lambda i: i % 2 == 1, 2, wrap=True)


def all_rows(inp, out):
    return shift_rows(inp, lambda i: True, 1)


def first_only(inp, out):
    return shift_rows(inp, lambda i: i == 1, 1)


def staircase(inp, out):
    return shift_rows(inp, lambda i: True, lambda i: i)


def vacated_zero(inp, out):
    return shift_rows(inp, lambda i: i % 2 == 1, 1, fill=0)


def copy_not_move(inp, out):
    bg = bg_of(inp)
    res = [list(r) for r in inp]
    for i in range(1, len(inp), 2):
        for j, c in enumerate(inp[i]):
            if c != bg and j + 1 < len(inp[i]):
                res[i][j + 1] = c
    return res


def columns_down(inp, out):
    t = [list(c) for c in zip(*inp)]
    bg = bg_of(inp)
    t2 = [shift_row(r, 1, bg) if i % 2 == 1 else list(r) for i, r in enumerate(t)]
    return [list(c) for c in zip(*t2)]


def swap_row_pairs(inp, out):
    res = [list(r) for r in inp]
    for i in range(0, len(res) - 1, 2):
        res[i], res[i + 1] = res[i + 1], res[i]
    return res


def anchor_shifted_too(inp, out):
    # anchor row shifts right, the other rows stay
    return shift_rows(inp, lambda i: i == 0, 1)


ALTERNATIVES = [
    ("odd rows shift left by 1 instead of right", left),
    ("odd rows shift right by 2 instead of 1", by_two),
    ("even rows shift instead of odd rows (wrong anchor row)", even_rows),
    ("odd rows rotate right by 2 with wrap-around", wrapped),
    ("every row shifts right by 1, anchor row included", all_rows),
    ("only the first row after the anchor shifts", first_only),
    ("row i shifts right by i (cumulative staircase)", staircase),
    ("shifted rows leave 0 in the vacated cell instead of background", vacated_zero),
    ("cells are copied one step right, originals left in place", copy_not_move),
    ("columns are the lines: odd columns shift down by 1", columns_down),
    ("adjacent row pairs are swapped instead of shifted", swap_row_pairs),
    ("only the anchor row shifts right, others stay", anchor_shifted_too),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/9968a131.json')))
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
