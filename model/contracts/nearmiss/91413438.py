import json
from pathlib import Path


def _counts(inp):
    cells = [c for r in inp for c in r]
    return cells.count(0), len(cells) - cells.count(0)


def _render(inp, n, positions, tile=None):
    """n x n tiles of the tile size; tile content at each (tr, tc) in positions."""
    tile = tile or inp
    h, w = len(tile), len(tile[0])
    g = [[0] * (n * w) for _ in range(n * h)]
    for tr, tc in positions:
        if 0 <= tr < n and 0 <= tc < n:
            for i in range(h):
                for j in range(w):
                    g[tr * h + i][tc * w + j] = tile[i][j]
    return g


def _row_major(n, k):
    return [(i // n, i % n) for i in range(min(k, n * n))]


def swapped_counts(inp, out):
    z, nz = _counts(inp)
    return _render(inp, nz, _row_major(nz, z))


def column_major(inp, out):
    z, nz = _counts(inp)
    return _render(inp, z, [(i % z, i // z) for i in range(min(nz, z * z))])


def one_extra_copy(inp, out):
    z, nz = _counts(inp)
    return _render(inp, z, _row_major(z, nz + 1))


def one_fewer_copy(inp, out):
    z, nz = _counts(inp)
    return _render(inp, z, _row_major(z, nz - 1))


def from_bottom_right(inp, out):
    z, nz = _counts(inp)
    pos = [(z - 1 - i // z, z - 1 - i % z) for i in range(min(nz, z * z))]
    return _render(inp, z, pos)


def from_bottom_left(inp, out):
    z, nz = _counts(inp)
    pos = [(z - 1 - i // z, i % z) for i in range(min(nz, z * z))]
    return _render(inp, z, pos)


def side_off_by_one(inp, out):
    z, nz = _counts(inp)
    return _render(inp, z + 1, _row_major(z + 1, nz))


def fill_all_tiles(inp, out):
    z, nz = _counts(inp)
    return _render(inp, z, _row_major(z, z * z))


def inverted_tile(inp, out):
    z, nz = _counts(inp)
    col = max(c for r in inp for c in r)
    tile = [[0 if c else col for c in r] for r in inp]
    return _render(inp, z, _row_major(z, nz), tile)


def transposed_tile(inp, out):
    z, nz = _counts(inp)
    tile = [list(r) for r in zip(*inp)]
    return _render(inp, z, _row_major(z, nz), tile)


def last_tiles(inp, out):
    z, nz = _counts(inp)
    k = min(nz, z * z)
    return _render(inp, z, [((z * z - k + i) // z, (z * z - k + i) % z) for i in range(k)])


def every_other_tile(inp, out):
    z, nz = _counts(inp)
    return _render(inp, z, [((2 * i) // z, (2 * i) % z) for i in range(nz)])


ALTERNATIVES = [
    ("tile count from nonzero cells and copy count from zero cells (swapped)", swapped_counts),
    ("copies fill tiles column by column", column_major),
    ("one copy too many", one_extra_copy),
    ("one copy too few", one_fewer_copy),
    ("copies fill from bottom-right going leftwards then upwards", from_bottom_right),
    ("copies fill from bottom-left row by row going upwards", from_bottom_left),
    ("tile grid one tile too large per side", side_off_by_one),
    ("every tile gets a copy", fill_all_tiles),
    ("copied tile is color-inverted", inverted_tile),
    ("copied tile is transposed", transposed_tile),
    ("copies occupy the last tiles in row-major order instead of the first", last_tiles),
    ("copies placed on every other tile in row-major order", every_other_tile),
]


def _valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/91413438.json"))
    pairs = task["train"]
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
