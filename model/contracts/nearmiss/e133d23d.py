import json
from pathlib import Path


def _tiles(inp):
    left = [r[0:3] for r in inp]
    right = [r[4:7] for r in inp]
    return left, right


def _combine(a, b, f, color=2):
    return [[color if f(x != 0, y != 0) else 0 for x, y in zip(ra, rb)]
            for ra, rb in zip(a, b)]


def and_rule(inp, out):
    l, r = _tiles(inp)
    return _combine(l, r, lambda x, y: x and y)


def xor_rule(inp, out):
    l, r = _tiles(inp)
    return _combine(l, r, lambda x, y: x != y)


def nor_rule(inp, out):
    l, r = _tiles(inp)
    return _combine(l, r, lambda x, y: not (x or y))


def left_only(inp, out):
    l, r = _tiles(inp)
    return _combine(l, r, lambda x, y: x)


def right_only(inp, out):
    l, r = _tiles(inp)
    return _combine(l, r, lambda x, y: y)


def wrong_color(inp, out):
    return [[6 if v == 2 else v for v in row] for row in out]


def mirror_right(inp, out):
    l, r = _tiles(inp)
    r = [row[::-1] for row in r]
    return _combine(l, r, lambda x, y: x or y)


def flip_right_vertical(inp, out):
    l, r = _tiles(inp)
    r = r[::-1]
    return _combine(l, r, lambda x, y: x or y)


def transpose_right(inp, out):
    l, r = _tiles(inp)
    r = [list(c) for c in zip(*r)]
    return _combine(l, r, lambda x, y: x or y)


def right_offset_by_one(inp, out):
    l = [r[0:3] for r in inp]
    r = [row[3:6] for row in inp]
    return _combine(l, r, lambda x, y: x or y)


def no_combine_recolor(inp, out):
    return [[2 if v != 0 else 0 for v in row] for row in inp]


def unfilled_first_row(inp, out):
    return [[0] * len(out[0])] + [list(r) for r in out[1:]]


def _differs(fn):
    def wrapped(inp, out):
        g = fn(inp, out)
        return None if g == out else g
    return wrapped


_RAW = [
    ("AND of the two tiles instead of OR", and_rule),
    ("XOR of the two tiles instead of OR", xor_rule),
    ("2 where neither tile has a cell (inverted OR)", nor_rule),
    ("only the left (6) tile is read", left_only),
    ("only the right (8) tile is read", right_only),
    ("correct fill pattern in color 6 instead of 2", wrong_color),
    ("right tile mirrored left-right before OR", mirror_right),
    ("right tile flipped top-bottom before OR", flip_right_vertical),
    ("right tile transposed before OR", transpose_right),
    ("right tile cropped one column too far left (includes separator)", right_offset_by_one),
    ("whole 3x7 input recolored to 2 with no combining", no_combine_recolor),
    ("true output with the top row left unfilled", unfilled_first_row),
]

ALTERNATIVES = [(d, _differs(f)) for d, f in _RAW]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/e133d23d.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
