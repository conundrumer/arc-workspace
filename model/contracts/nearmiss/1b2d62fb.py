import json
from pathlib import Path


def _tiles(inp):
    w = len(inp[0])
    t = (w - 1) // 2
    left = [r[:t] for r in inp]
    right = [r[t + 1:] for r in inp]
    return left, right, t


def _combine(inp, f, color=8):
    left, right, t = _tiles(inp)
    return [[color if f(a, b) else 0 for a, b in zip(lr, rr)]
            for lr, rr in zip(left, right)]


def either_zero(inp, out):
    # 8 where at least one tile is empty (OR of emptiness, not both)
    return _combine(inp, lambda a, b: a == 0 or b == 0)


def exactly_one_zero(inp, out):
    # 8 where exactly one tile is empty (XOR)
    return _combine(inp, lambda a, b: (a == 0) != (b == 0))


def left_only(inp, out):
    # ignores the right tile
    return _combine(inp, lambda a, b: a == 0)


def right_only(inp, out):
    # ignores the left tile
    return _combine(inp, lambda a, b: b == 0)


def both_filled(inp, out):
    # 8 where both tiles are filled (AND of filled)
    return _combine(inp, lambda a, b: a != 0 and b != 0)


def wrong_color(inp, out):
    # right cells, wrong marker color 1
    return [[1 if v == 8 else v for v in r] for r in out]


def mirrored_right(inp, out):
    # right tile read mirrored left-right
    left, right, t = _tiles(inp)
    right = [r[::-1] for r in right]
    return [[8 if a == 0 and b == 0 else 0 for a, b in zip(lr, rr)]
            for lr, rr in zip(left, right)]


def separator_offset(inp, out):
    # right tile taken one column early, so it includes the separator column
    w = len(inp[0])
    t = (w - 1) // 2
    return [[8 if r[i] == 0 and r[i + t] == 0 else 0 for i in range(t)]
            for r in inp]


def full_width_overlay(inp, out):
    # output keeps the input width, with 8 drawn into the left tile only
    left, right, t = _tiles(inp)
    res = [list(r) for r in inp]
    for i in range(len(inp)):
        for j in range(t):
            if left[i][j] == 0 and right[i][j] == 0:
                res[i][j] = 8
    return res


def transposed(inp, out):
    # correct cells, rows and columns swapped
    return [list(c) for c in zip(*out)]


def flipped_vertical(inp, out):
    # correct cells, row order reversed
    return out[::-1]


def single_row_kept(inp, out):
    # only the last row of the answer is marked, other rows left empty
    res = [[0] * len(r) for r in out]
    res[-1] = list(out[-1])
    return res


ALTERNATIVES = [
    ("8 where either tile is empty instead of both", either_zero),
    ("8 where exactly one tile is empty (XOR)", exactly_one_zero),
    ("only the left tile is considered", left_only),
    ("only the right tile is considered", right_only),
    ("8 where both tiles are filled", both_filled),
    ("marker color 1 instead of 8", wrong_color),
    ("right tile mirrored before combining", mirrored_right),
    ("right tile starts at the separator column (offset by one)", separator_offset),
    ("output keeps full input width with 8 drawn into the left tile", full_width_overlay),
    ("output transposed", transposed),
    ("output rows in reverse order", flipped_vertical),
    ("only the last row of the answer is marked", single_row_kept),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/1b2d62fb.json'))
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
