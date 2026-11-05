import json
from collections import Counter
from pathlib import Path

MARK = 7


def _ranked(inp):
    c = Counter(v for r in inp for v in r)
    return sorted(c, key=lambda k: (-c[k], k)), c


def _recolor(inp, keep, mark=MARK):
    return [[v if v in keep else mark for v in r] for r in inp]


def keep_top1(inp, out):
    order, _ = _ranked(inp)
    return _recolor(inp, set(order[:1]))


def keep_top3(inp, out):
    order, _ = _ranked(inp)
    return _recolor(inp, set(order[:3]))


def keep_least_frequent2(inp, out):
    order, _ = _ranked(inp)
    return _recolor(inp, set(order[-2:]))


def wrong_mark_color(inp, out):
    return [[8 if v == MARK else v for v in r] for r in out]


def swap_kept_and_marked(inp, out):
    return [[MARK if o != MARK else i for i, o in zip(ri, ro)] for ri, ro in zip(inp, out)]


def mark_only_rarest(inp, out):
    order, _ = _ranked(inp)
    return _recolor(inp, set(order[:-1]))


def zero_is_background(inp, out):
    return [[0 if i == 0 else o for i, o in zip(ri, ro)] for ri, ro in zip(inp, out)]


def keep_first_seen_two(inp, out):
    seen = []
    for r in inp:
        for v in r:
            if v not in seen:
                seen.append(v)
    return _recolor(inp, set(seen[:2]))


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def first_row_unmarked(inp, out):
    return [list(inp[0])] + [list(r) for r in out[1:]]


def crop_border(inp, out):
    return [r[1:-1] for r in out[1:-1]]


def keep_two_largest_values(inp, out):
    cols = sorted({v for r in inp for v in r}, reverse=True)
    return _recolor(inp, set(cols[:2]))


ALTERNATIVES = [
    ("keep only the single most frequent color", keep_top1),
    ("keep the three most frequent colors", keep_top3),
    ("keep the two least frequent colors instead of the most frequent", keep_least_frequent2),
    ("mark the dropped colors with 8 instead of 7", wrong_mark_color),
    ("mark the two kept colors and leave the rest", swap_kept_and_marked),
    ("mark only the single least frequent color", mark_only_rarest),
    ("treat 0 as background that is never marked", zero_is_background),
    ("keep the first two colors seen in row-major order", keep_first_seen_two),
    ("output transposed", transposed),
    ("first row is left unmarked", first_row_unmarked),
    ("output cropped by one cell at each border", crop_border),
    ("keep the two numerically largest colors", keep_two_largest_values),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/9caf5b84.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for name, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, name)
