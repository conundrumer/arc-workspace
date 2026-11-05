import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _order(out):
    seen = []
    for r in out:
        for v in r:
            if v != 0 and v not in seen:
                seen.append(v)
    return seen


def _seq(out):
    return [v for r in out for v in r]


def _runs(inp):
    """Number of horizontal runs of each non-background color."""
    bg = _bg(inp)
    res = Counter()
    for r in inp:
        prev = None
        for v in r:
            if v != bg and v != prev:
                res[v] += 1
            prev = v
    return res


def _grid(seq, h, w):
    return [list(seq[i * w:(i + 1) * w]) for i in range(h)]


def _pad(seq, n, fill=0):
    seq = list(seq)[:n]
    return seq + [fill] * (n - len(seq))


def _build(inp, out, counts, order, fill=0, h=None, w=None):
    h = h or len(out)
    w = w or len(out[0])
    seq = []
    for c in order:
        seq += [c] * counts.get(c, 0)
    return _grid(_pad(seq, h * w, fill), h, w)


def cells_not_runs(inp, out):
    bg = _bg(inp)
    cnt = Counter(v for r in inp for v in r if v != bg)
    return _build(inp, out, cnt, _order(out))


def swapped_order(inp, out):
    cnt = Counter(_seq(out))
    return _build(inp, out, cnt, list(reversed(_order(out))))


def column_major(inp, out):
    h, w = len(out), len(out[0])
    s = _seq(out)
    g = [[0] * w for _ in range(h)]
    for k, v in enumerate(s):
        g[k % h][k // h] = v
    return g


def fill_from_end(inp, out):
    h, w = len(out), len(out[0])
    return _grid(list(reversed(_seq(out))), h, w)


def transposed_shape(inp, out):
    h, w = len(out), len(out[0])
    return _grid(_seq(out), w, h)


def background_fill(inp, out):
    bg = _bg(inp)
    return [[bg if v == 0 else v for v in r] for r in out]


def one_per_color(inp, out):
    return _build(inp, out, {c: 1 for c in _order(out)}, _order(out))


def extra_first_color(inp, out):
    cnt = Counter(_seq(out))
    o = _order(out)
    cnt[o[0]] += 1
    return _build(inp, out, cnt, o)


def missing_last_color_one(inp, out):
    cnt = Counter(_seq(out))
    o = _order(out)
    cnt[o[-1]] -= 1
    return _build(inp, out, cnt, o)


def single_color(inp, out):
    cnt = Counter(_seq(out))
    o = _order(out)
    return _build(inp, out, {o[0]: cnt[o[0]] + cnt[o[-1]]}, [o[0]])


def snake_fill(inp, out):
    h, w = len(out), len(out[0])
    g = _grid(_seq(out), h, w)
    return [r if i % 2 == 0 else r[::-1] for i, r in enumerate(g)]


def crop_off_by_one(inp, out):
    return [r[:-1] for r in out]


def row_sorted_by_run_length(inp, out):
    """Orders colors by their run counts descending instead of by color rank."""
    cnt = Counter(_seq(out))
    o = sorted(_order(out), key=lambda c: -cnt[c])
    return _build(inp, out, cnt, o)


ALTERNATIVES = [
    ("count marked cells per color instead of runs", cells_not_runs),
    ("fill color blocks in the reverse color order", swapped_order),
    ("fill the output column by column", column_major),
    ("fill the output from the last cell backwards", fill_from_end),
    ("output has transposed shape (width and height swapped)", transposed_shape),
    ("unused cells get the input background color instead of 0", background_fill),
    ("one cell per color instead of one per run", one_per_color),
    ("first color gets one run too many", extra_first_color),
    ("last color gets one run too few", missing_last_color_one),
    ("all runs counted as the first color", single_color),
    ("rows alternate direction (snake fill)", snake_fill),
    ("output one column too narrow", crop_off_by_one),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/5289ad53.json'))
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
