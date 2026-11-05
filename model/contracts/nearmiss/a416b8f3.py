import json
from pathlib import Path


def _tile_h(g, n):
    return [row * n for row in g]


def _tile_v(g, n):
    return [list(row) for _ in range(n) for row in g]


def horizontal_three(inp, out):
    return _tile_h(inp, 3)


def vertical_two(inp, out):
    return _tile_v(inp, 2)


def mirrored_second_copy(inp, out):
    return [row + row[::-1] for row in inp]


def vertically_flipped_second_copy(inp, out):
    return [row + row for row in inp[::-1]]


def two_by_two(inp, out):
    return _tile_v(_tile_h(inp, 2), 2)


def drop_last_column_copy(inp, out):
    return [row + row[:-1] for row in inp]


def extra_leading_column(inp, out):
    return [row + row[1:] for row in inp]


def copies_equal_colors(inp, out):
    n = len({c for row in inp for c in row if c})
    return _tile_h(inp, n)


def second_copy_nonzero_only_first_row(inp, out):
    return [row + (row if i == 0 else [0] * len(row)) for i, row in enumerate(inp)]


def second_copy_shifted_down(inp, out):
    h = len(inp)
    return [inp[i] + inp[(i - 1) % h] for i in range(h)]


def tile_transposed(inp, out):
    t = [list(r) for r in zip(*inp)]
    return _tile_h(t, 2)


def swap_halves_colors(inp, out):
    # second copy recolored with the most common nonzero color
    from collections import Counter
    cnt = Counter(c for row in inp for c in row if c)
    m = cnt.most_common(1)[0][0]
    return [row + [m if c else 0 for c in row] for row in inp]


ALTERNATIVES = [
    ("tile the input 3 times horizontally", horizontal_three),
    ("tile the input 2 times vertically", vertical_two),
    ("second horizontal copy is a mirror image", mirrored_second_copy),
    ("both copies are the input flipped upside down", vertically_flipped_second_copy),
    ("tile 2x2 in both directions", two_by_two),
    ("second copy loses its last column", drop_last_column_copy),
    ("second copy loses its first column", extra_leading_column),
    ("number of horizontal copies equals number of distinct nonzero colors", copies_equal_colors),
    ("only the first row is copied; other rows of the second copy are blank", second_copy_nonzero_only_first_row),
    ("second copy is shifted down one row with wraparound", second_copy_shifted_down),
    ("transposed input tiled twice horizontally", tile_transposed),
    ("second copy keeps only shape, recolored to the commonest color", swap_halves_colors),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/a416b8f3.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        valid = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (
                isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
                and g != p["output"]
            )
            valid += ok
        print(f"{valid}/{len(pairs)}  {desc}")
