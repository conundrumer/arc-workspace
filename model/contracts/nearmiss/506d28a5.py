import json
from pathlib import Path


def tiles(inp):
    """Split the input at the all-4 separator row into (top, bottom, sep_row)."""
    for i, row in enumerate(inp):
        if all(v == 4 for v in row):
            return inp[:i], inp[i + 1:], row
    h = len(inp) // 2
    return inp[:h], inp[h:], None


def combine(inp, f, fill=3):
    top, bot, _ = tiles(inp)
    return [[fill if f(a != 0, b != 0) else 0 for a, b in zip(r1, r2)]
            for r1, r2 in zip(top, bot)]


def and_rule(inp, out):
    return combine(inp, lambda a, b: a and b)


def xor_rule(inp, out):
    return combine(inp, lambda a, b: a != b)


def top_only(inp, out):
    return combine(inp, lambda a, b: a)


def bottom_only(inp, out):
    return combine(inp, lambda a, b: b)


def nor_rule(inp, out):
    return combine(inp, lambda a, b: not (a or b))


def top_color_fill(inp, out):
    return combine(inp, lambda a, b: a or b, fill=2)


def separator_color_fill(inp, out):
    return combine(inp, lambda a, b: a or b, fill=4)


def own_colors(inp, out):
    top, bot, _ = tiles(inp)
    return [[a if a else b for a, b in zip(r1, r2)] for r1, r2 in zip(top, bot)]


def bottom_mirrored(inp, out):
    top, bot, _ = tiles(inp)
    flipped = [r[::-1] for r in bot]
    return [[3 if (a or b) else 0 for a, b in zip(r1, r2)]
            for r1, r2 in zip(top, flipped)]


def bottom_flipped_vertically(inp, out):
    top, bot, _ = tiles(inp)
    flipped = bot[::-1]
    return [[3 if (a or b) else 0 for a, b in zip(r1, r2)]
            for r1, r2 in zip(top, flipped)]


def bottom_shifted_down(inp, out):
    top, bot, _ = tiles(inp)
    shifted = bot[-1:] + bot[:-1]
    return [[3 if (a or b) else 0 for a, b in zip(r1, r2)]
            for r1, r2 in zip(top, shifted)]


def stacked_with_separator(inp, out):
    _, _, sep = tiles(inp)
    if sep is None:
        return None
    return [list(r) for r in out] + [list(sep)] + [list(r) for r in out]


def drop_last_column(inp, out):
    return [list(r[:-1]) for r in out]


ALTERNATIVES = [
    ("cell is filled only where both tiles are filled (AND, not OR)", and_rule),
    ("cell is filled where exactly one tile is filled (XOR)", xor_rule),
    ("output is the top tile's shape alone, bottom tile ignored", top_only),
    ("output is the bottom tile's shape alone, top tile ignored", bottom_only),
    ("filled and empty swapped: filled only where both tiles are empty (NOR)", nor_rule),
    ("correct union but filled with the top tile's color 2 instead of 3", top_color_fill),
    ("correct union but filled with the separator color 4 instead of 3", separator_color_fill),
    ("union keeps each tile's own color (top color wins) instead of the single output color", own_colors),
    ("bottom tile mirrored left-right before the union", bottom_mirrored),
    ("bottom tile flipped top-bottom before the union", bottom_flipped_vertically),
    ("bottom tile offset down by one row (wrapping) before the union", bottom_shifted_down),
    ("output cropped one column short (last column dropped)", drop_last_column),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/506d28a5.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
