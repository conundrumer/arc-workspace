"""Near-miss rules for 5d2a5c43.

Input: two 6x4 tiles (color 4 on 0) split by a column of 1s.
True output: 8 where either tile has 4, else 0.
"""
import json
from pathlib import Path


def _tiles(inp):
    w = len(inp[0])
    s = w // 2
    left = [r[:s] for r in inp]
    right = [r[s + 1:] for r in inp]
    return left, right


def _combine(inp, f, color=8):
    left, right = _tiles(inp)
    return [[color if f(a == 4, b == 4) else 0 for a, b in zip(lr, rr)]
            for lr, rr in zip(left, right)]


def and_rule(inp, out):
    return _combine(inp, lambda a, b: a and b)


def xor_rule(inp, out):
    return _combine(inp, lambda a, b: a != b)


def left_only(inp, out):
    return _combine(inp, lambda a, b: a)


def right_only(inp, out):
    return _combine(inp, lambda a, b: b)


def nor_rule(inp, out):
    return _combine(inp, lambda a, b: not (a or b))


def keep_color_4(inp, out):
    return _combine(inp, lambda a, b: a or b, color=4)


def right_mirrored(inp, out):
    left, right = _tiles(inp)
    right = [r[::-1] for r in right]
    return [[8 if (a == 4 or b == 4) else 0 for a, b in zip(lr, rr)]
            for lr, rr in zip(left, right)]


def right_flipped_vertical(inp, out):
    left, right = _tiles(inp)
    right = right[::-1]
    return [[8 if (a == 4 or b == 4) else 0 for a, b in zip(lr, rr)]
            for lr, rr in zip(left, right)]


def right_shifted_one(inp, out):
    left, right = _tiles(inp)
    right = [r[1:] + [0] for r in right]
    return [[8 if (a == 4 or b == 4) else 0 for a, b in zip(lr, rr)]
            for lr, rr in zip(left, right)]


def crop_last_column(inp, out):
    return [r[:-1] for r in out]


def first_row_unfilled(inp, out):
    return [[0] * len(out[0])] + [list(r) for r in out[1:]]


def keep_separator(inp, out):
    s = len(out[0]) // 2
    return [list(r[:s]) + [1] + list(r[s:]) for r in out]


ALTERNATIVES = [
    ("fill 8 only where both tiles have 4 (AND instead of OR)", and_rule),
    ("fill 8 where exactly one tile has 4 (XOR)", xor_rule),
    ("copy only the left tile as 8", left_only),
    ("copy only the right tile as 8", right_only),
    ("fill 8 where neither tile has 4 (inverted)", nor_rule),
    ("OR of the tiles but keep color 4 instead of recoloring to 8", keep_color_4),
    ("OR with the right tile mirrored left-right", right_mirrored),
    ("OR with the right tile flipped top-bottom", right_flipped_vertical),
    ("OR with the right tile shifted one column left (misaligned crop)", right_shifted_one),
    ("true output with the last column cropped (width off by one)", crop_last_column),
    ("true output with the first row left unfilled", first_row_unfilled),
    ("true output with the separator column of 1s kept in the middle", keep_separator),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/5d2a5c43.json').read_text())
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                  and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
                  and g != p["output"])
            n += ok
        print(n, "-", desc)
