import json
from pathlib import Path


def _tiles(inp):
    left = [row[1:4] for row in inp[1:4]]
    right = [row[5:8] for row in inp[1:4]]
    return left, right


def _color(out):
    return max(v for row in out for v in row)


def _paint(tile, col):
    return [[col if v else 0 for v in row] for row in tile]


def key_tile_shape(inp, out):
    left, _ = _tiles(inp)
    return _paint(left, _color(out))


def keep_gray(inp, out):
    _, right = _tiles(inp)
    return [row[:] for row in right]


def fixed_color(inp, out):
    _, right = _tiles(inp)
    return _paint(right, 8)


def color_by_count(inp, out):
    left, right = _tiles(inp)
    n = sum(1 for row in left for v in row if v)
    return _paint(right, n)


def paint_background(inp, out):
    _, right = _tiles(inp)
    col = _color(out)
    return [[0 if v else col for v in row] for row in right]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def mirrored(inp, out):
    return [row[::-1] for row in out]


def crop_with_gap(inp, out):
    col = _color(out)
    return [[col if v else 0 for v in row[4:9]] for row in inp[1:4]]


def union_of_tiles(inp, out):
    left, right = _tiles(inp)
    col = _color(out)
    return [[col if (a or b) else 0 for a, b in zip(r1, r2)]
            for r1, r2 in zip(left, right)]


def key_color_on_key_tile_xor(inp, out):
    left, right = _tiles(inp)
    col = _color(out)
    return [[col if (a != 0) != (b != 0) else 0 for a, b in zip(r1, r2)]
            for r1, r2 in zip(left, right)]


def whole_input_recolored(inp, out):
    col = _color(out)
    return [[col if v else 0 for v in row] for row in inp[1:4]]


ALTERNATIVES = [
    ("output the key (left) tile's shape instead of the target tile, in the right color", key_tile_shape),
    ("copy the target tile unchanged without recoloring (stays gray)", keep_gray),
    ("recolor the target tile with a fixed color 8 instead of the key-determined color", fixed_color),
    ("color the target tile by the count of cells in the key tile", color_by_count),
    ("paint the background cells of the target tile instead of the shape cells", paint_background),
    ("transpose the correct output", transposed),
    ("mirror the correct output left to right", mirrored),
    ("crop 3x5 including the gap column and border column of the right side", crop_with_gap),
    ("union of key and target tiles recolored", union_of_tiles),
    ("symmetric difference of key and target tiles recolored", key_color_on_key_tile_xor),
    ("recolor the whole 3x7 interior of the input including both tiles", whole_input_recolored),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/ed74f2f2.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = sum(1 for p in pairs
                if (g := f(p["input"], p["output"])) is not None and _valid(g, p["output"]))
        print(n, desc)
