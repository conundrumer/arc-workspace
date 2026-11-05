"""Near-miss rules for ARC task 31d5ba1a.

The input stacks two 3x5 tiles (9 on top, 4 below). The true output marks
cells where exactly one tile is non-zero with 6.
"""
import json
from pathlib import Path


def _tiles(inp):
    h = len(inp) // 2
    return inp[:h], inp[h:]


def _combine(inp, f, color=6, bottom=None):
    top, bot = _tiles(inp)
    if bottom is not None:
        bot = bottom(bot)
    return [[color if f(a != 0, b != 0) else 0 for a, b in zip(r, s)]
            for r, s in zip(top, bot)]


def or_rule(inp, out):
    return _combine(inp, lambda a, b: a or b)


def and_rule(inp, out):
    return _combine(inp, lambda a, b: a and b)


def nor_rule(inp, out):
    return _combine(inp, lambda a, b: not a and not b)


def xor_color_9(inp, out):
    return _combine(inp, lambda a, b: a != b, color=9)


def top_only(inp, out):
    return _combine(inp, lambda a, b: a and not b)


def bottom_flipped_vertically(inp, out):
    return _combine(inp, lambda a, b: a != b, bottom=lambda t: t[::-1])


def bottom_mirrored_horizontally(inp, out):
    return _combine(inp, lambda a, b: a != b, bottom=lambda t: [r[::-1] for r in t])


def bottom_shifted_up_one_row(inp, out):
    # off-by-one split: bottom tile starts one row too early / late
    return _combine(inp, lambda a, b: a != b,
                    bottom=lambda t: t[1:] + [[0] * len(t[0])])


def output_shifted_right_one(inp, out):
    return [[r[-1]] + r[:-1] for r in out]


def output_stacked_twice(inp, out):
    return [list(r) for r in out] + [list(r) for r in out]


def output_transposed(inp, out):
    return [list(c) for c in zip(*out)]


def first_row_unfilled(inp, out):
    return [[0] * len(out[0])] + [list(r) for r in out[1:]]


ALTERNATIVES = [
    ("OR of the two tiles instead of XOR", or_rule),
    ("AND of the two tiles (both non-zero)", and_rule),
    ("NOR: mark cells empty in both tiles", nor_rule),
    ("XOR marked with color 9 instead of 6", xor_color_9),
    ("only cells set in the top tile and not in the bottom", top_only),
    ("bottom tile flipped vertically before XOR", bottom_flipped_vertically),
    ("bottom tile mirrored horizontally before XOR", bottom_mirrored_horizontally),
    ("bottom tile offset up one row before XOR", bottom_shifted_up_one_row),
    ("true output shifted right one column with wrap", output_shifted_right_one),
    ("true output stacked twice (6x5 size)", output_stacked_twice),
    ("true output transposed", output_transposed),
    ("top row of the true output left unfilled", first_row_unfilled),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/31d5ba1a.json'))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
