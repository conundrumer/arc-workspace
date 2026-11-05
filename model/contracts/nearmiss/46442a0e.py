import json
from pathlib import Path


def cw(g):
    return [list(r) for r in zip(*g[::-1])]


def ccw(g):
    return [list(r) for r in zip(*g)][::-1]


def r180(g):
    return [r[::-1] for r in g[::-1]]


def fh(g):
    return [r[::-1] for r in g]


def fv(g):
    return [list(r) for r in g[::-1]]


def tr(g):
    return [list(r) for r in zip(*g)]


def quad(a, b, c, d):
    """2x2 arrangement of equal-size tiles a b / c d."""
    return [ra + rb for ra, rb in zip(a, b)] + [rc + rd for rc, rd in zip(c, d)]


def copy(g):
    return [list(r) for r in g]


def plain_tiling(inp, out):
    return quad(inp, inp, inp, inp)


def mirror_tiling(inp, out):
    return quad(inp, fh(inp), fv(inp), r180(inp))


def swapped_cw_ccw(inp, out):
    return quad(inp, ccw(inp), cw(inp), r180(inp))


def anchored_bottom_right(inp, out):
    return quad(r180(inp), fv(inp), fh(inp), inp)


def last_quadrant_transpose(inp, out):
    return quad(inp, cw(inp), ccw(inp), tr(inp))


def only_first_quadrant(inp, out):
    n = len(inp)
    g = [[0] * (2 * n) for _ in range(2 * n)]
    for i in range(n):
        for j in range(n):
            g[i][j] = inp[i][j]
    return g


def bottom_copies_top(inp, out):
    g = copy(out)
    n = len(inp)
    for i in range(n):
        g[n + i] = list(out[i])
    return g


def upscale_2x(inp, out):
    g = []
    for r in inp:
        row = [v for v in r for _ in range(2)]
        g.append(row)
        g.append(list(row))
    return g


def three_by_three(inp, out):
    n = len(inp)
    rows = []
    for bi in range(3):
        for i in range(n):
            row = []
            for bj in range(3):
                t = inp
                if bj % 2:
                    t = fh(t)
                if bi % 2:
                    t = fv(t)
                row += t[i]
            rows.append(row)
    return rows


def crop_last(inp, out):
    return [r[:-1] for r in out[:-1]]


def transposed_output(inp, out):
    return tr(out)


def rotated_tiles_same_direction(inp, out):
    return quad(inp, cw(inp), cw(cw(inp)), cw(cw(cw(inp))))


def unchanged(inp, out):
    return copy(inp)


ALTERNATIVES = [
    ("plain 2x2 translation tiling of the input", plain_tiling),
    ("mirror tiling: horizontal flip, vertical flip, 180 rotation", mirror_tiling),
    ("clockwise and counter-clockwise tiles swapped", swapped_cw_ccw),
    ("input anchored at the bottom-right instead of top-left", anchored_bottom_right),
    ("last tile is the transpose instead of the 180 rotation", last_quadrant_transpose),
    ("only the top-left tile filled, rest left 0", only_first_quadrant),
    ("bottom half repeats the top half", bottom_copies_top),
    ("input upscaled 2x instead of tiled", upscale_2x),
    ("3x3 mirror tiling instead of 2x2", three_by_three),
    ("output cropped by one row and column", crop_last),
    ("true output transposed (wrong orientation)", transposed_output),
    ("tiles are successive 90 degree clockwise rotations", rotated_tiles_same_direction),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / "data/tasks/46442a0e.json"
    train = json.load(open(path))["train"]
    print("pairs:", len(train), "readings:", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(ok, "-", desc)
