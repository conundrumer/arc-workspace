"""Near-miss rules for task 34b99a2b: two 5x4 subgrids (colors 8 and 5) split by a
column of 4; output cell is 2 where exactly one subgrid is non-zero, else 0."""
import json
from pathlib import Path


def _halves(inp):
    left = [r[0:4] for r in inp]
    right = [r[5:9] for r in inp]
    return left, right


def _combine(a, b, f, fill=2):
    return [[fill if f(x != 0, y != 0) else 0 for x, y in zip(ra, rb)]
            for ra, rb in zip(a, b)]


def and_rule(inp, out):
    l, r = _halves(inp)
    return _combine(l, r, lambda x, y: x and y)


def or_rule(inp, out):
    l, r = _halves(inp)
    return _combine(l, r, lambda x, y: x or y)


def xnor_rule(inp, out):
    l, r = _halves(inp)
    return _combine(l, r, lambda x, y: x == y)


def fill_left_color(inp, out):
    return [[8 if v else 0 for v in row] for row in out]


def source_colors(inp, out):
    l, r = _halves(inp)
    return [[(x or y) if bool(x) != bool(y) else 0 for x, y in zip(ra, rb)]
            for ra, rb in zip(l, r)]


def left_only(inp, out):
    l, r = _halves(inp)
    return _combine(l, r, lambda x, y: x and not y)


def right_only(inp, out):
    l, r = _halves(inp)
    return _combine(l, r, lambda x, y: y and not x)


def mirror_right(inp, out):
    l, r = _halves(inp)
    r = [row[::-1] for row in r]
    return _combine(l, r, lambda x, y: x != y)


def flip_right_vertical(inp, out):
    l, r = _halves(inp)
    return _combine(l, r[::-1], lambda x, y: x != y)


def offset_right(inp, out):
    # right subgrid taken one column early (includes the separator column)
    l = [r[0:4] for r in inp]
    r = [row[4:8] for row in inp]
    return _combine(l, r, lambda x, y: x != y)


def drop_last_row(inp, out):
    return [row[:] for row in out[:-1]]


def transposed(inp, out):
    return [list(c) for c in zip(*out)]


ALTERNATIVES = [
    ("AND: fill only where both subgrids are non-zero", and_rule),
    ("OR: fill where either subgrid is non-zero", or_rule),
    ("XNOR: fill where both subgrids agree on zero/non-zero", xnor_rule),
    ("fill color is 8 (the left subgrid color) instead of 2", fill_left_color),
    ("XOR cells keep their source color (8 or 5) instead of 2", source_colors),
    ("fill only cells set in the left subgrid and not the right", left_only),
    ("fill only cells set in the right subgrid and not the left", right_only),
    ("right subgrid mirrored left-right before XOR", mirror_right),
    ("right subgrid flipped top-bottom before XOR", flip_right_vertical),
    ("right subgrid read one column early (off-by-one offset)", offset_right),
    ("output one row short (last row cropped)", drop_last_row),
    ("output transposed to 4x5", transposed),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/34b99a2b.json'))
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
