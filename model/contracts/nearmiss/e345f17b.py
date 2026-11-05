import json
from pathlib import Path


def _halves(inp):
    h = len(inp[0]) // 2
    return [r[:h] for r in inp], [r[h:] for r in inp]


def _combine(inp, f, color=4):
    left, right = _halves(inp)
    return [[color if f(a, b) else 0 for a, b in zip(l, r)] for l, r in zip(left, right)]


def either_empty(inp, out):
    return _combine(inp, lambda a, b: a == 0 or b == 0)


def both_filled(inp, out):
    return _combine(inp, lambda a, b: a != 0 and b != 0)


def exactly_one_empty(inp, out):
    return _combine(inp, lambda a, b: (a == 0) != (b == 0))


def left_only(inp, out):
    return _combine(inp, lambda a, b: a == 0)


def right_only(inp, out):
    return _combine(inp, lambda a, b: b == 0)


def fill_with_left_color(inp, out):
    return [[6 if v == 4 else v for v in r] for r in out]


def fill_with_right_color(inp, out):
    return [[5 if v == 4 else v for v in r] for r in out]


def inverted(inp, out):
    return [[0 if v == 4 else 4 for v in r] for r in out]


def right_mirrored(inp, out):
    left, right = _halves(inp)
    return [[4 if a == 0 and b == 0 else 0 for a, b in zip(l, r[::-1])]
            for l, r in zip(left, right)]


def top_row_fill_missing(inp, out):
    res = [r[:] for r in out]
    for r in res:
        if 4 in r:
            for i in range(len(r)):
                r[i] = 0
            break
    return res


def split_top_bottom(inp, out):
    h = len(inp) // 2
    top, bot = inp[:h], inp[h:]
    return [[4 if a == 0 and b == 0 else 0 for a, b in zip(t, b_)]
            for t, b_ in zip(top, bot)]


ALTERNATIVES = [
    ("fill where either half is empty (OR instead of NOR)", either_empty),
    ("fill where both halves are non-empty", both_filled),
    ("fill where exactly one half is empty (XOR)", exactly_one_empty),
    ("only the left half is consulted", left_only),
    ("only the right half is consulted", right_only),
    ("fill cells use the left half color 6", fill_with_left_color),
    ("fill cells use the right half color 5", fill_with_right_color),
    ("output is inverted: filled and empty cells swapped", inverted),
    ("right half is mirrored horizontally before combining", right_mirrored),
    ("topmost filled row of the output is left unfilled", top_row_fill_missing),
    ("input is split into top and bottom halves instead of left and right", split_top_bottom),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/e345f17b.json'))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
