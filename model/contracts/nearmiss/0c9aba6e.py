import json
from pathlib import Path


def _panels(inp):
    return inp[0:6], inp[7:13]


def _combine(inp, f, top=None, bot=None):
    t, b = _panels(inp)
    t = top if top is not None else t
    b = bot if bot is not None else b
    return [[8 if f(x != 0, y != 0) else 0 for x, y in zip(rt, rb)] for rt, rb in zip(t, b)]


def xor(inp, out):
    return _combine(inp, lambda a, b: a != b)


def both_filled(inp, out):
    return _combine(inp, lambda a, b: a and b)


def either_filled(inp, out):
    return _combine(inp, lambda a, b: a or b)


def top_only(inp, out):
    return _combine(inp, lambda a, b: not a)


def bottom_only(inp, out):
    return _combine(inp, lambda a, b: not b)


def bottom_flipped_vertically(inp, out):
    t, b = _panels(inp)
    return _combine(inp, lambda a, c: not a and not c, bot=b[::-1])


def bottom_mirrored_horizontally(inp, out):
    t, b = _panels(inp)
    return _combine(inp, lambda a, c: not a and not c, bot=[r[::-1] for r in b])


def wrong_fill_color(inp, out):
    return [[2 if v == 8 else v for v in r] for r in out]


def split_one_row_late(inp, out):
    # panels cut one row too low: bottom starts on the separator row
    t = inp[0:6]
    b = inp[6:12]
    return [[8 if x == 0 and y == 0 else 0 for x, y in zip(rt, rb)] for rt, rb in zip(t, b)]


def last_column_unfilled(inp, out):
    return [r[:-1] + [0] for r in out]


def top_half_only(inp, out):
    return [list(r) for r in out[:3]]


def inverted_with_fill_kept_as_panel_colors(inp, out):
    # keep the panel colors where a panel is filled, 8 where both empty is dropped
    t, b = _panels(inp)
    return [[x or y for x, y in zip(rt, rb)] for rt, rb in zip(t, b)]


ALTERNATIVES = [
    ("fill 8 where exactly one panel is filled (XOR)", xor),
    ("fill 8 where both panels are filled (AND)", both_filled),
    ("fill 8 where either panel is filled (OR)", either_filled),
    ("fill 8 where the top panel is empty, ignoring the bottom panel", top_only),
    ("fill 8 where the bottom panel is empty, ignoring the top panel", bottom_only),
    ("bottom panel rows read in reverse order before the NOR", bottom_flipped_vertically),
    ("bottom panel mirrored left-right before the NOR", bottom_mirrored_horizontally),
    ("correct cells but painted with the input color 2 instead of 8", wrong_fill_color),
    ("panels split one row too low, bottom panel starts on the separator", split_one_row_late),
    ("last column left unfilled", last_column_unfilled),
    ("only the top half of the output rows produced", top_half_only),
    ("output is the union of the two panels in their own colors, no 8", inverted_with_fill_kept_as_panel_colors),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/0c9aba6e.json'))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
