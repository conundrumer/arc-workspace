import json
from pathlib import Path


def _halves(inp):
    h = len(inp) // 2
    return inp[:h], inp[h:]


def _combine(inp, f, color=4, flip_bottom=None):
    top, bot = _halves(inp)
    if flip_bottom == "v":
        bot = bot[::-1]
    elif flip_bottom == "h":
        bot = [r[::-1] for r in bot]
    return [[color if f(a != 0, b != 0) else 0 for a, b in zip(rt, rb)]
            for rt, rb in zip(top, bot)]


def and_rule(inp, out):
    return _combine(inp, lambda a, b: a and b)


def xor_rule(inp, out):
    return _combine(inp, lambda a, b: a != b)


def top_only(inp, out):
    return _combine(inp, lambda a, b: a)


def bottom_only(inp, out):
    return _combine(inp, lambda a, b: b)


def nor_rule(inp, out):
    return _combine(inp, lambda a, b: not (a or b))


def color_three(inp, out):
    return _combine(inp, lambda a, b: a or b, color=3)


def color_five(inp, out):
    return _combine(inp, lambda a, b: a or b, color=5)


def flipped_bottom_v(inp, out):
    return _combine(inp, lambda a, b: a or b, flip_bottom="v")


def mirrored_bottom_h(inp, out):
    return _combine(inp, lambda a, b: a or b, flip_bottom="h")


def keep_source_colors(inp, out):
    top, bot = _halves(inp)
    return [[a if a else b for a, b in zip(rt, rb)] for rt, rb in zip(top, bot)]


def drop_last_row(inp, out):
    return [list(r) for r in out[:-1]]


def side_by_side_split(inp, out):
    # splits the columns into left/right halves instead of top/bottom
    w = len(inp[0]) // 2
    return [[4 if (r[c] != 0 or r[c + w] != 0) else 0 for c in range(w)]
            for r in inp]


ALTERNATIVES = [
    ("cell is filled only where both tiles are non-zero (AND)", and_rule),
    ("cell is filled where exactly one tile is non-zero (XOR)", xor_rule),
    ("output is the top tile alone, painted 4", top_only),
    ("output is the bottom tile alone, painted 4", bottom_only),
    ("fill the cells where both tiles are zero (complement of OR)", nor_rule),
    ("OR is right but the fill color is the top tile color 3", color_three),
    ("OR is right but the fill color is the bottom tile color 5", color_five),
    ("bottom tile is flipped vertically before the OR", flipped_bottom_v),
    ("bottom tile is mirrored horizontally before the OR", mirrored_bottom_h),
    ("output keeps source colors (3 from top, else 5 from bottom)", keep_source_colors),
    ("output is the true OR with its last row dropped", drop_last_row),
    ("grid is split into left and right halves instead of top and bottom", side_by_side_split),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/d19f7514.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                  and g != p["output"])
            n += ok
        print(f"{n}/{len(pairs)}  {desc}")
