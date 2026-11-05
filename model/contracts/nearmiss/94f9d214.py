"""Near-miss rules for 94f9d214.

Rule: the input is two 4x4 tiles stacked (top, bottom). The output is 2 where
both tiles are 0 (NOR), else 0.
"""
import json
from pathlib import Path


def _tiles(inp):
    h = len(inp) // 2
    return inp[:h], inp[h:]


def _combine(a, b, f, fill=2):
    return [[fill if f(x, y) else 0 for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def or_filled(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b, lambda x, y: x != 0 or y != 0)


def and_filled(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b, lambda x, y: x != 0 and y != 0)


def xor_filled(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b, lambda x, y: (x != 0) != (y != 0))


def only_top(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b, lambda x, y: x == 0)


def only_bottom(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b, lambda x, y: y == 0)


def fill_with_top_color(inp, out):
    a, b = _tiles(inp)
    c = max(max(r) for r in a)
    return [[c if v else 0 for v in r] for r in out]


def swap_fill_and_background(inp, out):
    return [[0 if v else 2 for v in r] for r in out]


def split_left_right(inp, out):
    w = len(inp[0]) // 2
    l = [r[:w] for r in inp]
    r_ = [r[w:] for r in inp]
    return _combine(l, r_, lambda x, y: x == 0 and y == 0)


def flip_bottom_vertically(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b[::-1], lambda x, y: x == 0 and y == 0)


def mirror_bottom_horizontally(inp, out):
    a, b = _tiles(inp)
    return _combine(a, [r[::-1] for r in b], lambda x, y: x == 0 and y == 0)


def split_off_by_one_row(inp, out):
    a, b = inp[:3], inp[3:6]
    return _combine(a, b, lambda x, y: x == 0 and y == 0)


def bottom_shifted_down_one_row(inp, out):
    a, b = _tiles(inp)
    b = b[-1:] + b[:-1]
    return _combine(a, b, lambda x, y: x == 0 and y == 0)


ALTERNATIVES = [
    ("fill where either tile is nonzero (OR instead of NOR)", or_filled),
    ("fill where both tiles are nonzero (AND)", and_filled),
    ("fill where exactly one tile is nonzero (XOR)", xor_filled),
    ("fill where only the top tile is 0, ignoring the bottom tile", only_top),
    ("fill where only the bottom tile is 0, ignoring the top tile", only_bottom),
    ("fill with the top tile's color instead of 2", fill_with_top_color),
    ("swap output fill and background (0 and 2)", swap_fill_and_background),
    ("split input into left and right halves instead of top and bottom", split_left_right),
    ("flip the bottom tile vertically before combining", flip_bottom_vertically),
    ("mirror the bottom tile horizontally before combining", mirror_bottom_horizontally),
    ("split the 8 rows at 3 instead of 4 (3-row tiles)", split_off_by_one_row),
    ("bottom tile shifted down one row (wrapping) before combining", bottom_shifted_down_one_row),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/94f9d214.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
