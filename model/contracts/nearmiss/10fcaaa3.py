import json
from pathlib import Path

DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
ORTH = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def tile(g, a=2, b=2):
    return [list(r) * b for _ in range(a) for r in g]


def halo(g, offs, color=8, wrap=False, overwrite=False):
    h, w = len(g), len(g[0])
    res = [r[:] for r in g]
    for i in range(h):
        for j in range(w):
            if g[i][j] == 0:
                continue
            for di, dj in offs:
                y, x = i + di, j + dj
                if wrap:
                    y %= h
                    x %= w
                elif not (0 <= y < h and 0 <= x < w):
                    continue
                if overwrite or g[y][x] == 0:
                    res[y][x] = color
    return res


def no_tiling(inp, out):
    return halo(inp, DIAG)


def orthogonal(inp, out):
    return halo(tile(inp), ORTH)


def eight_neighbours(inp, out):
    return halo(tile(inp), DIAG + ORTH)


def halo_mark_color(inp, out):
    t = tile(inp)
    h, w = len(t), len(t[0])
    res = [r[:] for r in t]
    for i in range(h):
        for j in range(w):
            if t[i][j]:
                for di, dj in DIAG:
                    y, x = i + di, j + dj
                    if 0 <= y < h and 0 <= x < w and t[y][x] == 0:
                        res[y][x] = t[i][j]
    return res


def tile_horizontal_only(inp, out):
    return halo(tile(inp, 1, 2), DIAG)


def tile_three(inp, out):
    return halo(tile(inp, 3, 3), DIAG)


def wrap_around(inp, out):
    return halo(tile(inp), DIAG, wrap=True)


def halo_overwrites_marks(inp, out):
    return halo(tile(inp), DIAG, overwrite=True)


def halo_per_tile(inp, out):
    h = halo(inp, DIAG)
    return tile(h)


def down_diagonals_only(inp, out):
    return halo(tile(inp), [(1, -1), (1, 1)])


def main_diagonal_only(inp, out):
    return halo(tile(inp), [(-1, -1), (1, 1)])


def diagonal_reach_two(inp, out):
    return halo(tile(inp), DIAG + [(-2, -2), (-2, 2), (2, -2), (2, 2)])


ALTERNATIVES = [
    ("no tiling: halo drawn on the input at its own size", no_tiling),
    ("halo on orthogonal neighbours instead of diagonals", orthogonal),
    ("halo on all eight neighbours", eight_neighbours),
    ("halo painted in the mark's color instead of 8", halo_mark_color),
    ("tiled only twice horizontally, not 2x2", tile_horizontal_only),
    ("tiled 3x3 instead of 2x2", tile_three),
    ("halo wraps around the edges of the tiled grid", wrap_around),
    ("halo overwrites marks as well as background", halo_overwrites_marks),
    ("halo computed inside one tile and then tiled, so it never crosses tile borders", halo_per_tile),
    ("halo only on the two lower diagonals", down_diagonals_only),
    ("halo only on the main-diagonal neighbours", main_diagonal_only),
    ("halo also reaches two cells along each diagonal", diagonal_reach_two),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/10fcaaa3.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(n, desc)
