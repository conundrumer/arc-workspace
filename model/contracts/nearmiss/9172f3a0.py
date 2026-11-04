from pathlib import Path
import json


def up(g, kr, kc=None):
    kc = kr if kc is None else kc
    return [[v for v in row for _ in range(kc)] for row in g for _ in range(kr)]


def transpose(g):
    return [list(r) for r in zip(*g)]


def nonzero_colors(inp):
    return sorted({v for r in inp for v in r if v})


def scale2(inp, out):
    return up(inp, 2)


def tile3(inp, out):
    n = len(inp)
    return [list(row) * n for _ in range(n) for row in inp]


def transposed(inp, out):
    return up(transpose(inp), len(inp))


def mirrored_cols(inp, out):
    return up([r[::-1] for r in inp], len(inp))


def fractal(inp, out):
    n = len(inp)
    return [[inp[i % n][j % n] if inp[i // n][j // n] else 0
             for j in range(n * n)] for i in range(n * n)]


def scale_distinct_colors(inp, out):
    k = len({v for r in inp for v in r})
    return up(inp, k)


def scale_nonzero_cells(inp, out):
    k = sum(1 for r in inp for v in r if v)
    return up(inp, k)


def crop_off_by_one(inp, out):
    return [r[1:] for r in out[1:]]


def stretch_wide(inp, out):
    return up(inp, 1, len(inp))


def stretch_tall(inp, out):
    return up(inp, len(inp), 1)


def flip_blocks_vertical(inp, out):
    return up(inp[::-1], len(inp))


def bg_filled(inp, out):
    cols = [v for r in inp for v in r if v]
    fill = max(set(cols), key=cols.count)
    return [[v if v else fill for v in r] for r in out]


def hollow_blocks(inp, out):
    n = len(inp)
    g = [r[:] for r in out]
    for bi in range(n):
        for bj in range(n):
            if inp[bi][bj]:
                for a in range(n):
                    for b in range(n):
                        if 0 < a < n - 1 and 0 < b < n - 1:
                            g[bi * n + a][bj * n + b] = 0
    return g


ALTERNATIVES = [
    ("scale factor 2 instead of the input size", scale2),
    ("tile the input 3x3 instead of upscaling each cell", tile3),
    ("upscale the transposed input", transposed),
    ("upscale the input with each row mirrored", mirrored_cols),
    ("self-similar fractal: input copy in each nonzero cell's block", fractal),
    ("scale factor is the number of distinct colors", scale_distinct_colors),
    ("scale factor is the number of nonzero cells", scale_nonzero_cells),
    ("output cropped by one row and column at the top left", crop_off_by_one),
    ("cells stretched horizontally only", stretch_wide),
    ("cells stretched vertically only", stretch_tall),
    ("upscale with the block rows in reverse order", flip_blocks_vertical),
    ("background blocks filled with the most common nonzero color", bg_filled),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/9172f3a0.json')))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
