import json
from pathlib import Path


def _colors(inp):
    return inp[0][0], inp[1][0]


def swapped_phase(inp, out):
    return [list(r) for r in reversed(out)]


def vertical_stripes(inp, out):
    return [list(out[0]) for _ in out]


def horizontal_stripes_period2(inp, out):
    a, b = _colors(inp)
    w = len(inp[0])
    return [[a if (c // 2) % 2 == 0 else b for c in range(w)],
            [b if (c // 2) % 2 == 0 else a for c in range(w)]]


def only_second_row_alternates(inp, out):
    a, b = _colors(inp)
    w = len(inp[0])
    return [[a] * w, [b if c % 2 == 0 else a for c in range(w)]]


def left_half_only(inp, out):
    w = len(inp[0])
    return [[out[r][c] if c < w // 2 else inp[r][c] for c in range(w)]
            for r in range(len(inp))]


def background_zero(inp, out):
    a, _ = _colors(inp)
    w = len(inp[0])
    return [[a if c % 2 == 0 else 0 for c in range(w)],
            [0 if c % 2 == 0 else a for c in range(w)]]


def width_minus_one(inp, out):
    return [r[:-1] for r in out]


def transposed_shape(inp, out):
    return [list(col) for col in zip(*out)]


def doubled_height(inp, out):
    return [list(r) for r in out] + [list(r) for r in out]


def one_color_checker_wrong_second(inp, out):
    # second color taken from the first row's color instead of the other row's
    a, b = _colors(inp)
    w = len(inp[0])
    return [[a] * w, [a] * w]


def last_column_unfilled(inp, out):
    g = [list(r) for r in out]
    for r in range(len(g)):
        g[r][-1] = inp[r][-1]
    return g


def rows_swapped_input(inp, out):
    return [list(inp[1]), list(inp[0])]


ALTERNATIVES = [
    ("checkerboard phase swapped: top row starts with the lower row's color", swapped_phase),
    ("vertical stripes: every row alternates the same way, no row-to-row flip", vertical_stripes),
    ("alternation in blocks of two columns instead of one", horizontal_stripes_period2),
    ("only the lower row alternates; the top row stays uniform", only_second_row_alternates),
    ("only the left half is checkered; the right half stays as input", left_half_only),
    ("second checker color is 0 instead of the other row's color", background_zero),
    ("output one column narrower than input", width_minus_one),
    ("output transposed: tall and narrow instead of wide and short", transposed_shape),
    ("checkerboard pattern repeated down to double the height", doubled_height),
    ("both rows filled with the top row's color", one_color_checker_wrong_second),
    ("last column left unchanged from input", last_column_unfilled),
    ("input rows swapped, no alternation", rows_swapped_input),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/e9afcf9a.json').read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
