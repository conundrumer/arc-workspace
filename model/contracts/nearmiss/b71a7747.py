import json
from collections import Counter
from pathlib import Path


def _info(inp, out):
    colors = {v for row in out for v in row}
    tile = Counter(v for row in out for v in row).most_common(1)[0][0]
    paths = colors - {tile}
    R = [r for r, row in enumerate(inp) if any(v in colors for v in row)]
    C = [c for c in range(len(inp[0])) if any(row[c] in colors for row in inp)]
    return colors, tile, paths, R, C


def _sub(inp, R, C):
    return [[inp[r][c] for c in C] for r in R]


def _runs(idx):
    runs = []
    for i in idx:
        if runs and runs[-1][-1] == i - 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    return runs


def path_only(inp, out):
    colors, tile, paths, R, C = _info(inp, out)
    R2 = [r for r, row in enumerate(inp) if any(v in paths for v in row)]
    C2 = [c for c in range(len(inp[0])) if any(row[c] in paths for row in inp)]
    return _sub(inp, R2, C2)


def columns_only(inp, out):
    colors, tile, paths, R, C = _info(inp, out)
    return _sub(inp, range(len(inp)), C)


def rows_only(inp, out):
    colors, tile, paths, R, C = _info(inp, out)
    return _sub(inp, R, range(len(inp[0])))


def path_erased(inp, out):
    colors, tile, paths, R, C = _info(inp, out)
    return [[tile if v in paths else v for v in row] for row in out]


def swapped_colors(inp, out):
    colors, tile, paths, R, C = _info(inp, out)
    other = next(iter(paths))
    m = {tile: other, other: tile}
    return [[m.get(v, v) for v in row] for row in out]


def gap_row_kept(inp, out):
    colors, tile, paths, R, C = _info(inp, out)

    def widen(idx):
        runs = _runs(idx)
        res = []
        for i, run in enumerate(runs):
            res += run
            if i + 1 < len(runs):
                res.append(run[-1] + 1)
        return res

    return _sub(inp, widen(R), widen(C))


def crop_last_dropped(inp, out):
    return [row[:-1] for row in out[:-1]]


def first_tile_only(inp, out):
    colors, tile, paths, R, C = _info(inp, out)
    s = len(_runs(R)[0])
    return [row[:s] for row in out[:s]]


def transposed(inp, out):
    return [list(col) for col in zip(*out)]


def tiles_in_place(inp, out):
    colors, tile, paths, R, C = _info(inp, out)
    Rs, Cs = set(R), set(C)
    return [[inp[r][c] if (r in Rs and c in Cs) else 0 for c in range(len(inp[0]))]
            for r in range(len(inp))]


def tile_rows_reversed(inp, out):
    return [row[:] for row in out[::-1]]


def last_row_tile_missing(inp, out):
    colors, tile, paths, R, C = _info(inp, out)
    s = len(_runs(R)[-1])
    return [row[:] for row in out[:-s]]


ALTERNATIVES = [
    ("only the path color marks the kept rows and columns", path_only),
    ("only the columns holding tile cells are kept; all rows stay", columns_only),
    ("only the rows holding tile cells are kept; all columns stay", rows_only),
    ("the path is read as noise and painted over with the tile color", path_erased),
    ("tile color and path color are swapped", swapped_colors),
    ("one line row and column is kept between neighboring tiles", gap_row_kept),
    ("the packed output loses its last row and column", crop_last_dropped),
    ("only the top-left tile is output", first_tile_only),
    ("the packed output is transposed", transposed),
    ("tiles stay at their input positions and the rest is blanked to 0", tiles_in_place),
    ("tile rows are packed in reverse order", tile_rows_reversed),
    ("the last row of tiles is dropped", last_row_tile_missing),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/b71a7747.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
