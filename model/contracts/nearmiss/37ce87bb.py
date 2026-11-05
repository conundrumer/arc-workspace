import json
from collections import Counter
from pathlib import Path

ADD, SUB, NEW = 8, 2, 5


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _bar_cols(inp):
    bg = _bg(inp)
    return sorted({j for r in inp for j, c in enumerate(r) if c != bg})


def _excess(inp):
    cnt = Counter(c for r in inp for c in r)
    return cnt[ADD] - cnt[SUB]


def _result_col(inp, out):
    cols = {j for i, r in enumerate(out) for j, c in enumerate(r) if c != inp[i][j]}
    return min(cols)


def _paint(inp, col, n, color=NEW, from_top=False):
    h = len(inp)
    g = [r[:] for r in inp]
    n = max(0, min(n, h))
    rows = range(0, n) if from_top else range(h - n, h)
    for i in rows:
        g[i][col] = color
    return g


def _base(inp, out):
    return [r[:] for r in inp]


def fill_from_top(inp, out):
    return _paint(inp, _result_col(inp, out), _excess(inp), from_top=True)


def count_plus_one(inp, out):
    return _paint(inp, _result_col(inp, out), _excess(inp) + 1)


def count_minus_one(inp, out):
    return _paint(inp, _result_col(inp, out), _excess(inp) - 1)


def add_only(inp, out):
    cnt = Counter(c for r in inp for c in r)
    return _paint(inp, _result_col(inp, out), cnt[ADD])


def bar_count(inp, out):
    return _paint(inp, _result_col(inp, out), len(_bar_cols(inp)))


def tallest_bar(inp, out):
    bg = _bg(inp)
    best = max(sum(1 for r in inp if r[j] != bg) for j in _bar_cols(inp))
    return _paint(inp, _result_col(inp, out), best)


def sub_only(inp, out):
    cnt = Counter(c for r in inp for c in r)
    return _paint(inp, _result_col(inp, out), cnt[SUB])


def wrong_color_add(inp, out):
    g = [r[:] for r in out]
    for i, r in enumerate(out):
        for j, c in enumerate(r):
            if c != inp[i][j]:
                g[i][j] = ADD
    return g


def adjacent_column(inp, out):
    c = _result_col(inp, out)
    nc = c - 1
    return _paint(inp, nc, _excess(inp))


def leftmost_free_column(inp, out):
    bars = set(_bar_cols(inp))
    nc = next(j for j in range(len(inp[0])) if j not in bars)
    return _paint(inp, nc, _excess(inp))


def whole_column(inp, out):
    return _paint(inp, _result_col(inp, out), len(inp))


def mirrored_column(inp, out):
    c = _result_col(inp, out)
    return _paint(inp, len(inp[0]) - 1 - c, _excess(inp))


ALTERNATIVES = [
    ("result cells fill down from the top edge instead of up from the bottom", fill_from_top),
    ("result height is excess plus one", count_plus_one),
    ("result height is excess minus one", count_minus_one),
    ("result height counts only the add-color cells, ignoring the subtract color", add_only),
    ("result height is the number of bar lines", bar_count),
    ("result height is the height of the tallest bar", tallest_bar),
    ("result height counts only the subtract-color cells", sub_only),
    ("result cells painted in the add color instead of the new color", wrong_color_add),
    ("result line one column from the last bar instead of two", adjacent_column),
    ("result line at the leftmost barless column", leftmost_free_column),
    ("result line fills the whole column", whole_column),
    ("result line at the horizontally mirrored column", mirrored_column),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    w = len(g[0])
    if any(not isinstance(r, list) or len(r) != w for r in g):
        return False
    if any(not isinstance(c, int) or not 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/37ce87bb.json"))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, f in ALTERNATIVES:
        n = sum(_valid(f(p["input"], p["output"]), p["output"]) for p in train)
        print(n, desc)
