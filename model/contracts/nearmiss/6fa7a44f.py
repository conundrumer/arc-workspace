import json
from pathlib import Path


def _copy(g):
    return [list(r) for r in g]


def mirror_on_top(inp, out):
    # Reflection placed above the input instead of below.
    return _copy(inp[::-1]) + _copy(inp)


def plain_repeat(inp, out):
    # Input tiled twice vertically with no reflection.
    return _copy(inp) + _copy(inp)


def mirror_right(inp, out):
    # Reflection across a vertical axis: mirror copy to the right.
    return [list(r) + list(r[::-1]) for r in inp]


def shared_row_mirror(inp, out):
    # Mirror axis through the last row: that row is not repeated.
    return _copy(inp) + _copy(inp[::-1][1:])


def full_d4_tiling(inp, out):
    # Reflect in both directions, giving a 2x2 arrangement.
    top = [list(r) + list(r[::-1]) for r in inp]
    return top + _copy(top[::-1])


def transpose_below(inp, out):
    # Copy below is the transpose, not the vertical reflection.
    n = len(inp)
    m = len(inp[0])
    t = [[inp[i][j] for i in range(n)] for j in range(m)]
    return _copy(inp) + t


def three_copies(inp, out):
    # Reflection is followed by another copy of the input.
    return _copy(inp) + _copy(inp[::-1]) + _copy(inp)


def rolled_mirror(inp, out):
    # Mirror rows are in the right order but start one row late.
    rev = inp[::-1]
    return _copy(inp) + _copy(rev[1:] + rev[:1])


def mirror_only(inp, out):
    # Only the reflected copy is output.
    return _copy(inp[::-1])


def first_row_repeat(inp, out):
    # Bottom copy repeats the last input row for every row instead of reflecting.
    return _copy(inp) + [list(inp[-1]) for _ in inp]


def rows_flipped_in_place(inp, out):
    # Reflected block has each row reversed left to right but keeps row order.
    return _copy(inp) + [list(r[::-1]) for r in inp]


def mirror_shifted_colors(inp, out):
    # Right layout but the reflected block is cyclically shifted one column.
    return _copy(inp) + [list(r[1:] + r[:1]) for r in inp[::-1]]


ALTERNATIVES = [
    ("reflection placed above the input", mirror_on_top),
    ("input repeated without reflection", plain_repeat),
    ("reflection to the right (horizontal axis of symmetry swapped)", mirror_right),
    ("mirror axis on last row, which is not duplicated", shared_row_mirror),
    ("reflection in both directions (2x2 tiling)", full_d4_tiling),
    ("transpose stacked below input", transpose_below),
    ("input, reflection, then input again", three_copies),
    ("reflected rows cyclically shifted by one", rolled_mirror),
    ("only the reflected copy output", mirror_only),
    ("last input row repeated below", first_row_repeat),
    ("each row reversed left to right but row order kept", rows_flipped_in_place),
    ("reflected block shifted one column", mirror_shifted_colors),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/6fa7a44f.json").read_text())
    pairs = task["train"]
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
