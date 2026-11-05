import json
from pathlib import Path

FULL = [[8, 8], [8, 8]]
BROKEN = [[0, 8], [8, 8]]


def _tile(out):
    return [row[:2] for row in out[:2]]


def _arrange(tile, gap=1, nr=2, nc=2, bg=0):
    h = len(tile)
    w = len(tile[0])
    H = nr * h + (nr - 1) * gap
    W = nc * w + (nc - 1) * gap
    g = [[bg] * W for _ in range(H)]
    for a in range(nr):
        for b in range(nc):
            for i in range(h):
                for j in range(w):
                    g[a * (h + gap) + i][b * (w + gap) + j] = tile[i][j]
    return g


def no_gap(inp, out):
    return _arrange(_tile(out), gap=0)


def gap_two(inp, out):
    return _arrange(_tile(out), gap=2)


def always_full(inp, out):
    return _arrange(FULL)


def always_broken(inp, out):
    return _arrange(BROKEN)


def swapped_class(inp, out):
    return _arrange(BROKEN if _tile(out) == FULL else FULL)


def mirrored_broken(inp, out):
    t = _tile(out)
    return _arrange([row[::-1] for row in t])


def flipped_vertical(inp, out):
    t = _tile(out)
    return _arrange(t[::-1])


def one_tile_row(inp, out):
    g = _arrange(_tile(out))
    for r in range(3, 5):
        g[r] = [0] * 5
    return g


def three_tiles(inp, out):
    g = [row[:] for row in out]
    for r in range(3, 5):
        for c in range(3, 5):
            g[r][c] = 0
    return g


def single_tile(inp, out):
    g = [[0] * 5 for _ in range(5)]
    t = _tile(out)
    for i in range(2):
        for j in range(2):
            g[i][j] = t[i][j]
    return g


def inverted_colors(inp, out):
    return [[8 if v == 0 else 0 for v in row] for row in out]


def input_crop(inp, out):
    return [row[:5] for row in inp[:5]]


ALTERNATIVES = [
    ("tiles placed with no gap between them (4x4 output)", no_gap),
    ("tiles placed with a gap of two cells (6x6 output)", gap_two),
    ("always the full 2x2 tile, whatever the ink", always_full),
    ("always the tile with the top-left cell missing, whatever the ink", always_broken),
    ("the two tile kinds swapped: the wrong class is chosen", swapped_class),
    ("tile mirrored left to right", mirrored_broken),
    ("tile flipped top to bottom", flipped_vertical),
    ("only the top row of tiles drawn", one_tile_row),
    ("bottom-right tile left out", three_tiles),
    ("a single tile in the top-left corner of a blank 5x5", single_tile),
    ("tile cells and background swapped (0 and 8 exchanged)", inverted_colors),
    ("top-left 5x5 crop of the input", input_crop),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/b1fc8b8e.json'))
    train = task['train']
    print('pairs', len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(n, desc)
