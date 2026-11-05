import json
from pathlib import Path


def colors(inp):
    return sorted({v for r in inp for v in r if v != 0})


def scale(g, ky, kx):
    return [[v for v in r for _ in range(kx)] for r in g for _ in range(ky)]


def k_true(inp):
    return len(colors(inp))


def cells_count(inp, out):
    k = sum(1 for r in inp for v in r if v != 0)
    return scale(inp, k, k)


def k_with_background(inp, out):
    k = k_true(inp) + 1
    return scale(inp, k, k)


def k_minus_one(inp, out):
    k = k_true(inp) - 1
    return scale(inp, k, k)


def fixed_two(inp, out):
    g = scale(inp, 2, 2)
    return None if g == out else g


def tile_instead(inp, out):
    k = k_true(inp)
    return [list(r) * k for _ in range(k) for r in inp]


def transposed_input(inp, out):
    k = k_true(inp)
    t = [list(r) for r in zip(*inp)]
    return scale(t, k, k)


def horizontal_only(inp, out):
    k = k_true(inp)
    return scale(inp, 1, k)


def drop_last_block_row(inp, out):
    k = k_true(inp)
    return [list(r) for r in out[:-k]]


def background_filled(inp, out):
    c = colors(inp)[0]
    return [[c if v == 0 else v for v in r] for r in out]


def fractal(inp, out):
    k = k_true(inp)
    n = len(inp)
    m = len(inp[0])
    return [[inp[y % n][x % m] if inp[y // n][x // m] != 0 else 0
             for x in range(m * m)] for y in range(n * n)]


def mirrored_input(inp, out):
    k = k_true(inp)
    return scale([list(reversed(r)) for r in inp], k, k)


def row_max_colors(inp, out):
    k = max(len({v for v in r if v != 0}) for r in inp)
    g = scale(inp, k, k)
    return None if g == out else g


ALTERNATIVES = [
    ("k is the count of non-background cells", cells_count),
    ("k counts the background as a color (distinct colors plus one)", k_with_background),
    ("k is the color count minus one", k_minus_one),
    ("k is always 2", fixed_two),
    ("the input is tiled k times instead of each cell scaled to a block", tile_instead),
    ("the transposed input is scaled by k", transposed_input),
    ("scaling applies on the horizontal axis only", horizontal_only),
    ("the last row of blocks is cut off (off-by-one size)", drop_last_block_row),
    ("background cells take the first non-background color", background_filled),
    ("fractal: each non-background cell becomes a copy of the input, background cells stay empty", fractal),
    ("the horizontally mirrored input is scaled by k", mirrored_input),
    ("k is the largest number of distinct colors in one row", row_max_colors),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/b91ae062.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(n, desc)
