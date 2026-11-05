"""Near-miss rules for 6430c8c4.

The input is two 4x4 tiles stacked, split by a row of 4s. The output marks
with 3 the cells where both tiles are empty (0).
"""
import json
from pathlib import Path


def _tiles(inp):
    return [r[:] for r in inp[:4]], [r[:] for r in inp[5:9]]


def _combine(a, b, pred, on=3):
    return [[on if pred(x, y) else 0 for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def alt_or(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b, lambda x, y: x != 0 or y != 0)


def alt_and(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b, lambda x, y: x != 0 and y != 0)


def alt_xor(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b, lambda x, y: (x != 0) != (y != 0))


def alt_top_only(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b, lambda x, y: x == 0)


def alt_bottom_only(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b, lambda x, y: y == 0)


def alt_color_top(inp, out):
    a, _ = _tiles(inp)
    c = max(max(r) for r in a)
    return [[c if v else 0 for v in r] for r in out]


def alt_color_separator(inp, out):
    c = inp[4][0]
    return [[c if v else 0 for v in r] for r in out]


def alt_bottom_shifted(inp, out):
    # bottom tile taken one row early, so it includes the separator row
    a = inp[0:4]
    b = inp[4:8]
    return _combine(a, b, lambda x, y: x == 0 and y == 0)


def alt_flip_bottom_h(inp, out):
    a, b = _tiles(inp)
    b = [r[::-1] for r in b]
    return _combine(a, b, lambda x, y: x == 0 and y == 0)


def alt_flip_bottom_v(inp, out):
    a, b = _tiles(inp)
    b = b[::-1]
    return _combine(a, b, lambda x, y: x == 0 and y == 0)


def alt_transposed(inp, out):
    return [list(r) for r in zip(*out)]


def alt_output_with_separator(inp, out):
    # output keeps the whole input frame: result tile, separator, bottom tile
    _, b = _tiles(inp)
    return [r[:] for r in out] + [inp[4][:]] + b


ALTERNATIVES = [
    ("cells set where either tile is filled (OR instead of NOR)", alt_or),
    ("cells set where both tiles are filled (AND instead of NOR)", alt_and),
    ("cells set where exactly one tile is filled (XOR)", alt_xor),
    ("only the top tile is consulted; set where top is empty", alt_top_only),
    ("only the bottom tile is consulted; set where bottom is empty", alt_bottom_only),
    ("set cells take the top tile's color instead of 3", alt_color_top),
    ("set cells take the separator color instead of 3", alt_color_separator),
    ("bottom tile read one row early, including the separator row", alt_bottom_shifted),
    ("bottom tile mirrored left-right before combining", alt_flip_bottom_h),
    ("bottom tile flipped top-bottom before combining", alt_flip_bottom_v),
    ("result transposed", alt_transposed),
    ("output keeps separator row and bottom tile below the result", alt_output_with_separator),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/6430c8c4.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
