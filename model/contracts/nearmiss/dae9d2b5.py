"""Near-miss readings for ARC task dae9d2b5.

Rule: the input is two 3x3 halves side by side (color 4 left, color 3 right).
The output marks with 6 every cell where either half is nonzero.
"""


def _halves(inp):
    w = len(inp[0]) // 2
    return [r[:w] for r in inp], [r[w:] for r in inp]


def _combine(inp, fn, color=6):
    a, b = _halves(inp)
    return [[color if fn(x, y) else 0 for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def _checked(g, out):
    return None if g == out else g


def and_instead_of_or(inp, out):
    return _checked(_combine(inp, lambda x, y: x and y), out)


def xor_instead_of_or(inp, out):
    return _checked(_combine(inp, lambda x, y: bool(x) != bool(y)), out)


def left_half_only(inp, out):
    return _checked(_combine(inp, lambda x, y: x), out)


def right_half_only(inp, out):
    return _checked(_combine(inp, lambda x, y: y), out)


def wrong_fill_color_keep_third(inp, out):
    return _checked(_combine(inp, lambda x, y: x or y, color=3), out)


def wrong_fill_color_keep_four(inp, out):
    return _checked(_combine(inp, lambda x, y: x or y, color=4), out)


def right_half_mirrored(inp, out):
    a, b = _halves(inp)
    b = [r[::-1] for r in b]
    return _checked(
        [[6 if x or y else 0 for x, y in zip(ra, rb)] for ra, rb in zip(a, b)], out
    )


def right_half_flipped_vertically(inp, out):
    a, b = _halves(inp)
    b = b[::-1]
    return _checked(
        [[6 if x or y else 0 for x, y in zip(ra, rb)] for ra, rb in zip(a, b)], out
    )


def inverted_mask(inp, out):
    return _checked(_combine(inp, lambda x, y: not (x or y)), out)


def recolor_in_place_no_merge(inp, out):
    # Keeps the 3x6 layout and recolors nonzero cells to 6 without overlaying.
    return _checked([[6 if v else 0 for v in r] for r in inp], out)


def split_off_by_one(inp, out):
    # Halves taken as columns 0-1 and 2-3 (width 2) instead of 0-2 and 3-5.
    w = len(inp[0]) // 2 - 1
    a = [r[:w] for r in inp]
    b = [r[w : 2 * w] for r in inp]
    return _checked(
        [[6 if x or y else 0 for x, y in zip(ra, rb)] for ra, rb in zip(a, b)], out
    )


def right_half_shifted_one_column(inp, out):
    a, b = _halves(inp)
    b = [r[1:] + r[:1] for r in b]
    return _checked(
        [[6 if x or y else 0 for x, y in zip(ra, rb)] for ra, rb in zip(a, b)], out
    )


ALTERNATIVES = [
    ("AND of the halves instead of OR", and_instead_of_or),
    ("XOR of the halves: overlap cells left unmarked", xor_instead_of_or),
    ("only the left (4) half is marked", left_half_only),
    ("only the right (3) half is marked", right_half_only),
    ("correct mask but filled with 3", wrong_fill_color_keep_third),
    ("correct mask but filled with 4", wrong_fill_color_keep_four),
    ("right half mirrored left-right before overlay", right_half_mirrored),
    ("right half flipped top-bottom before overlay", right_half_flipped_vertically),
    ("inverted mask: empty cells marked, occupied cells blank", inverted_mask),
    ("nonzero cells recolored to 6 in place, no overlay (3x6)", recolor_in_place_no_merge),
    ("halves split with width 2 instead of 3 (3x2 output)", split_off_by_one),
    ("right half shifted one column before overlay", right_half_shifted_one_column),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    import json
    from pathlib import Path

    task = json.loads(
        (Path(__file__).resolve().parents[3] / "data/tasks/dae9d2b5.json").read_text()
    )
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
