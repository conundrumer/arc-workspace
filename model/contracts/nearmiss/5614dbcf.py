"""Near-miss readings for ARC task 5614dbcf (noisy 3x3 tiles -> one cell per tile)."""
import json
from collections import Counter
from pathlib import Path

NOISE = 5


def _size(inp):
    return len(inp) // 3


def _tiles(inp, t=3, off=0):
    """Yield, per tile, the list of its cells; tiles are t x t, starting at offset off."""
    n = (len(inp) - off) // t
    m = (len(inp[0]) - off) // t
    return [[[inp[off + i * t + a][off + j * t + b] for a in range(t) for b in range(t)]
             for j in range(m)] for i in range(n)]


def _map_tiles(inp, fn, t=3, off=0):
    return [[fn(c) for c in row] for row in _tiles(inp, t, off)]


def _major(cells):
    return Counter(cells).most_common(1)[0][0]


def _minor(cells):
    cnt = Counter(cells)
    return min(cnt, key=lambda c: (cnt[c], c))


def _first_nonzero(cells):
    for c in cells:
        if c != 0:
            return c
    return 0


def _vflip(inp, out):
    return [row[:] for row in out[::-1]]


def _rot90(inp, out):
    return [list(r) for r in zip(*out[::-1])]


def _rot180(inp, out):
    return [row[::-1] for row in out[::-1]]


def _center(inp, out):
    return _map_tiles(inp, lambda c: c[4])


def _noise_wins(inp, out):
    return _map_tiles(inp, lambda c: NOISE if NOISE in c else _major(c))


def _first_nz(inp, out):
    return _map_tiles(inp, _first_nonzero)


def _tile2(inp, out):
    return _map_tiles(inp, _major, t=2)


def _offset1(inp, out):
    return _map_tiles(inp, _major, t=3, off=1)


def _denoise_full(inp, out):
    s = _size(inp)
    return [[out[i // 3][j // 3] for j in range(len(inp[0]))] for i in range(len(inp))]


def _minority(inp, out):
    return _map_tiles(inp, _minor)


def _empty_as_noise(inp, out):
    return [[NOISE if v == 0 else v for v in row] for row in out]


def _row_band(inp, out):
    res = []
    for i in range(len(out)):
        band = [inp[3 * i + a][x] for a in range(3) for x in range(len(inp[0]))]
        res.append([_major(band)] * len(out[0]))
    return res


ALTERNATIVES = [
    ("rows of the tile grid are read bottom to top", _vflip),
    ("tile grid is rotated a quarter turn clockwise", _rot90),
    ("tile grid is rotated a half turn", _rot180),
    ("each tile is read at its center cell, not by majority", _center),
    ("a tile holding any 5 takes color 5 (noise treated as a signal)", _noise_wins),
    ("each tile takes its first nonzero cell in raster order", _first_nz),
    ("tiles are 2x2 cells, so the output is a 4x4 grid", _tile2),
    ("tile grid starts one cell in from the top-left corner", _offset1),
    ("noise is removed but the tiles are not collapsed (9x9 output)", _denoise_full),
    ("each tile takes its least frequent color", _minority),
    ("empty (0) tiles are filled with the noise color", _empty_as_noise),
    ("every tile in a row band takes the band's majority color", _row_band),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/5614dbcf.json'))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
