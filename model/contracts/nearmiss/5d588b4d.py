import json
from collections import Counter
from pathlib import Path


def _facts(inp):
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    marks = [v for r in inp for v in r if v != bg]
    return bg, marks[0], len(marks), len(inp[0])


def _runs(n):
    return list(range(1, n + 1)) + list(range(n - 1, 0, -1))


def _seq(runs, fg, bg, gap=1):
    s = []
    for r in runs:
        s += [fg] * r + [bg] * gap
    return s


def _wrap(s, w, bg, rows=None):
    h = rows if rows is not None else -(-len(s) // w)
    s = (s + [bg] * (w * h))[: w * h]
    return [s[i * w:(i + 1) * w] for i in range(h)]


def _build(inp, n=None, runs=None, gap=1, w=None, fg=None, bg_out=None, rows=None):
    bg, col, cnt, width = _facts(inp)
    n = cnt if n is None else n
    runs = _runs(n) if runs is None else runs
    w = width if w is None else w
    fg = col if fg is None else fg
    b = bg if bg_out is None else bg_out
    return _wrap(_seq(runs, fg, b, gap), w, b, rows)


def n_plus_one(inp, out):
    return _build(inp, n=_facts(inp)[2] + 1)


def n_minus_one(inp, out):
    n = _facts(inp)[2] - 1
    return _build(inp, n=n) if n >= 1 else None


def ascending_only(inp, out):
    n = _facts(inp)[2]
    return _build(inp, runs=list(range(1, n + 1)))


def no_gaps(inp, out):
    return _build(inp, gap=0)


def double_gaps(inp, out):
    return _build(inp, gap=2)


def wrap_at_n(inp, out):
    return _build(inp, w=_facts(inp)[2])


def reversed_sequence(inp, out):
    bg, col, n, w = _facts(inp)
    s = _seq(_runs(n), col, bg)[::-1]
    return _wrap(s, w, bg, len(out))


def uniform_rows(inp, out):
    n = _facts(inp)[2]
    return _build(inp, runs=[n] * n)


def inverted_colors(inp, out):
    bg, col, n, w = _facts(inp)
    return [[col if v == bg else bg for v in r] for r in out]


def extra_blank_row(inp, out):
    return [r[:] for r in out] + [[_facts(inp)[0]] * len(out[0])]


def first_row_only(inp, out):
    return [out[0][:]] if len(out) > 1 else None


def column_major(inp, out):
    bg, col, n, w = _facts(inp)
    s = _seq(_runs(n), col, bg)
    h = -(-len(s) // w)
    s = s + [bg] * (w * h - len(s))
    return [[s[c * h + r] for c in range(w)] for r in range(h)]


ALTERNATIVES = [
    ("square side is the mark count plus one", n_plus_one),
    ("square side is the mark count minus one", n_minus_one),
    ("only the rising half of the diagonal runs, no descent", ascending_only),
    ("no background gap between runs", no_gaps),
    ("two-cell background gap between runs", double_gaps),
    ("line wraps at the square side instead of the input width", wrap_at_n),
    ("sequence laid out in reverse order", reversed_sequence),
    ("runs are the square's rows, all of full length", uniform_rows),
    ("foreground and background colors swapped", inverted_colors),
    ("one extra blank row below the true output", extra_blank_row),
    ("only the first line is produced, no wrap to later lines", first_row_only),
    ("sequence fills the canvas column by column", column_major),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/5d588b4d.json'))
    pairs = task["train"]
    ref = [_build(p["input"]) for p in pairs]
    print("reference matches true outputs:", [r == p["output"] for r, p in zip(ref, pairs)])
    for desc, f in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
