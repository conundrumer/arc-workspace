from pathlib import Path
import json


def up(g, kr, kc):
    return [[v for v in row for _ in range(kc)] for row in g for _ in range(kr)]


def k_of(inp, out):
    return len(out) // len(inp)


def scale_plus_one(inp, out):
    k = k_of(inp, out)
    return up(inp, k + 1, k + 1)


def tile_not_scale(inp, out):
    k = k_of(inp, out)
    return [row * k for row in inp] * k


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def mirrored_input(inp, out):
    k = k_of(inp, out)
    return up([r[::-1] for r in inp], k, k)


def rows_only(inp, out):
    k = k_of(inp, out)
    return up(inp, k, 1)


def cols_only(inp, out):
    k = k_of(inp, out)
    return up(inp, 1, k)


def crop_off_by_one(inp, out):
    return [r[:-1] for r in out[:-1]]


def corner_only(inp, out):
    k = k_of(inp, out)
    g = [[0] * len(out[0]) for _ in out]
    for i, row in enumerate(inp):
        for j, v in enumerate(row):
            g[i * k][j * k] = v
    return g


def scale_by_color_count(inp, out):
    n = len({v for r in inp for v in r})
    return up(inp, n, n)


def scale_by_input_size(inp, out):
    n = len(inp)
    return up(inp, n, n)


def rotated_input(inp, out):
    k = k_of(inp, out)
    rot = [list(r) for r in zip(*inp[::-1])]
    return up(rot, k, k)


def one_block_unfilled(inp, out):
    k = k_of(inp, out)
    g = [r[:] for r in out]
    for i in range(k):
        for j in range(k):
            g[len(out) - 1 - i][len(out[0]) - 1 - j] = out[0][0] if out[0][0] != out[-1][-1] else (out[0][0] + 1) % 10
    return g


ALTERNATIVES = [
    ("scale factor is one more than the true factor", scale_plus_one),
    ("input tiled copy by copy instead of each cell enlarged", tile_not_scale),
    ("correct enlargement, then transposed", transposed),
    ("input mirrored left-right before enlarging", mirrored_input),
    ("cells enlarged vertically only", rows_only),
    ("cells enlarged horizontally only", cols_only),
    ("output one row and one column too small", crop_off_by_one),
    ("only the top-left cell of each block is painted, rest 0", corner_only),
    ("scale factor taken as the number of distinct colors", scale_by_color_count),
    ("scale factor taken as the input side length", scale_by_input_size),
    ("input rotated 90 degrees before enlarging", rotated_input),
    ("bottom-right block left in the top-left block's color", one_block_unfilled),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/c59eb873.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for name, f in ALTERNATIVES:
        c = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("ERR", name, e)
                g = None
            if g is not None and valid(g, p["output"]):
                c += 1
        print(c, name)
