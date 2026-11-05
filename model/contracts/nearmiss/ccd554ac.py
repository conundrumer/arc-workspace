import json
from pathlib import Path


def tile(g, rows, cols):
    return [[g[r % len(g)][c % len(g[0])] for c in range(len(g[0]) * cols)]
            for r in range(len(g) * rows)]


def _same(a, b):
    return a == b


def _guard(g, out):
    return None if g == out else g


def tile_once(inp, out):
    return [r[:] for r in inp]


def tile_row_only(inp, out):
    n = len(inp)
    return _guard(tile(inp, 1, n), out)


def tile_one_more(inp, out):
    n = len(inp)
    return _guard(tile(inp, n + 1, n + 1), out)


def tile_one_fewer(inp, out):
    n = len(inp)
    return _guard(tile(inp, n - 1, n - 1), out)


def drop_last_tile_row(inp, out):
    n = len(inp)
    return _guard(tile(inp, n - 1, n), out)


def kron_nonzero(inp, out):
    n = len(inp)
    g = [[inp[r % n][c % n] if inp[r // n][c // n] != 0 else 0
          for c in range(n * n)] for r in range(n * n)]
    return _guard(g, out)


def kron_zero(inp, out):
    n = len(inp)
    g = [[inp[r % n][c % n] if inp[r // n][c // n] == 0 else 0
          for c in range(n * n)] for r in range(n * n)]
    return _guard(g, out)


def mirrored_alternate_tiles(inp, out):
    n = len(inp)
    g = [[0] * (n * n) for _ in range(n * n)]
    for r in range(n * n):
        for c in range(n * n):
            a, b = r % n, c % n
            if (c // n) % 2:
                b = n - 1 - b
            if (r // n) % 2:
                a = n - 1 - a
            g[r][c] = inp[a][b]
    return _guard(g, out)


def transposed_tile(inp, out):
    n = len(inp)
    t = [[inp[c][r] for c in range(n)] for r in range(n)]
    return _guard(tile(t, n, n), out)


def diagonal_tiles_only(inp, out):
    n = len(inp)
    g = [[out[r][c] if r // n == c // n else 0 for c in range(n * n)]
         for r in range(n * n)]
    return _guard(g, out)


def shifted_by_one_column(inp, out):
    g = [r[1:] + r[:1] for r in out]
    return _guard(g, out)


def tile_double_size(inp, out):
    return _guard(tile(inp, 2, 2), out)


ALTERNATIVES = [
    ("output is the input unchanged, no tiling", tile_once),
    ("input tiled only across one row of tiles", tile_row_only),
    ("tile count is one more than the input side", tile_one_more),
    ("tile count is one fewer than the input side", tile_one_fewer),
    ("last row of tiles is missing", drop_last_tile_row),
    ("tile placed only where the input cell is nonzero (fractal)", kron_nonzero),
    ("tile placed only where the input cell is zero (inverse fractal)", kron_zero),
    ("alternate tiles are mirrored", mirrored_alternate_tiles),
    ("tile is the transposed input", transposed_tile),
    ("only the diagonal tiles are filled", diagonal_tiles_only),
    ("tiled output rolled left by one column", shifted_by_one_column),
    ("fixed 2x2 tiling regardless of input size", tile_double_size),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == '__main__':
    path = Path(__file__).resolve().parents[3] / 'data/tasks/ccd554ac.json'
    train = json.load(open(path))['train']
    print(len(ALTERNATIVES), 'readings', len(train), 'pairs')
    for desc, f in ALTERNATIVES:
        n = sum(1 for p in train if valid(f(p['input'], p['output']), p['output']))
        print(n, desc)
