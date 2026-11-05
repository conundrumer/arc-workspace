"""Near-miss readings for ce4f8723.

Rule: the input is a top 4x4 tile (color 1), a row of 4s, and a bottom 4x4
tile (color 2). The output is a 4x4 grid: 3 where either tile has a cell, else 0.
"""
import json
from pathlib import Path

N = 4


def tiles(inp):
    top = [r[:] for r in inp[:N]]
    bot = [r[:] for r in inp[N + 1:2 * N + 1]]
    return top, bot


def combine(a, b, f, color=3):
    return [[color if f(x != 0, y != 0) else 0 for x, y in zip(ra, rb)]
            for ra, rb in zip(a, b)]


def and_(inp, out):
    t, b = tiles(inp)
    return combine(t, b, lambda x, y: x and y)


def xor(inp, out):
    t, b = tiles(inp)
    return combine(t, b, lambda x, y: x != y)


def or_color1(inp, out):
    t, b = tiles(inp)
    return combine(t, b, lambda x, y: x or y, 1)


def top_only(inp, out):
    t, b = tiles(inp)
    return combine(t, b, lambda x, y: x)


def bottom_only(inp, out):
    t, b = tiles(inp)
    return combine(t, b, lambda x, y: y)


def flip_bottom_v(inp, out):
    t, b = tiles(inp)
    return combine(t, b[::-1], lambda x, y: x or y)


def flip_bottom_h(inp, out):
    t, b = tiles(inp)
    return combine(t, [r[::-1] for r in b], lambda x, y: x or y)


def append_separator(inp, out):
    return [r[:] for r in out] + [inp[N][:]]


def nor(inp, out):
    t, b = tiles(inp)
    return combine(t, b, lambda x, y: not (x or y))


def top_minus_bottom(inp, out):
    t, b = tiles(inp)
    return combine(t, b, lambda x, y: x and not y)


def transpose_bottom(inp, out):
    t, b = tiles(inp)
    bt = [list(r) for r in zip(*b)]
    return combine(t, bt, lambda x, y: x or y)


def shifted_window(inp, out):
    # bottom tile read one row too high (starts on the separator row)
    t, _ = tiles(inp)
    b = [r[:] for r in inp[N:2 * N]]
    return combine(t, b, lambda x, y: x or y)


ALTERNATIVES = [
    ("3 only where both tiles have a cell (AND instead of OR)", and_),
    ("3 where exactly one tile has a cell (XOR)", xor),
    ("OR of the tiles drawn in color 1 instead of 3", or_color1),
    ("only the top tile is used, drawn in 3", top_only),
    ("only the bottom tile is used, drawn in 3", bottom_only),
    ("bottom tile flipped vertically before the OR", flip_bottom_v),
    ("bottom tile flipped horizontally before the OR", flip_bottom_h),
    ("output includes the separator row (5 rows)", append_separator),
    ("3 where neither tile has a cell (inverted OR)", nor),
    ("3 where top has a cell and bottom does not", top_minus_bottom),
    ("bottom tile transposed before the OR", transpose_bottom),
    ("bottom tile window off by one row, starting on the separator", shifted_window),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / "data/tasks/ce4f8723.json"
    train = json.load(open(path))["train"]
    print(f"{len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
