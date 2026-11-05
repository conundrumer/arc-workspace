"""Near-miss readings for ARC task 46f33fce.

True rule: split the input into 2x2 tiles; a tile takes the color of its ink
cell (background 0 where none); each tile becomes a 4x4 block in the output.
"""
import json
from pathlib import Path


def _coarse(inp, tile=2, dr=0, dc=0, pick="last"):
    """Grid of tile colors. Cell (r, c) falls into tile ((r+dr)//tile, (c+dc)//tile)."""
    h, w = len(inp), len(inp[0])
    nh = (h - 1 + dr) // tile + 1
    nw = (w - 1 + dc) // tile + 1
    g = [[0] * nw for _ in range(nh)]
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v:
                tr, tc = (r + dr) // tile, (c + dc) // tile
                if pick == "first" and g[tr][tc]:
                    continue
                g[tr][tc] = v
    return g


def _scale(g, kr, kc=None):
    kc = kr if kc is None else kc
    return [[v for v in row for _ in range(kc)] for row in g for _ in range(kr)]


def scale_two(inp, out):
    # block size 2 instead of 4: output as large as the input
    return _scale(_coarse(inp), 2)


def no_downsample(inp, out):
    # each input cell read as its own tile, scaled by 2
    return _scale(inp, 2)


def tile_offset_plus(inp, out):
    # tile grid shifted by one cell, so ink sits at the tile's top-left
    return _scale(_coarse(inp, dr=1, dc=1), 4)


def transposed(inp, out):
    g = _coarse(inp)
    t = [list(r) for r in zip(*g)]
    return _scale(t, 4)


def mirrored(inp, out):
    g = [row[::-1] for row in _coarse(inp)]
    return _scale(g, 4)


def scale_three(inp, out):
    return _scale(_coarse(inp), 3)


def aspect_wrong(inp, out):
    # rows scaled by 4, columns by 2
    return _scale(_coarse(inp), 4, 2)


def big_tiles(inp, out):
    # tiles of 5x5 cells (2x2 coarse grid), later ink wins, scaled to 20x20
    h = len(inp)
    return _scale(_coarse(inp, tile=h // 2), 10)


def first_color_only(inp, out):
    # a color is painted only at its first tile in reading order
    g = _coarse(inp)
    seen = set()
    for row in g:
        for i, v in enumerate(row):
            if v and v in seen:
                row[i] = 0
            elif v:
                seen.add(v)
    return _scale(g, 4)


def bg_filled_with_common_ink(inp, out):
    # the background is taken to be the most frequent non-zero color
    counts = {}
    for row in inp:
        for v in row:
            if v:
                counts[v] = counts.get(v, 0) + 1
    if not counts:
        return None
    top = max(sorted(counts), key=lambda k: counts[k])
    g = [[v or top for v in row] for row in _coarse(inp)]
    return _scale(g, 4)


def ink_only_first_row_of_tile(inp, out):
    # ink read only from the tile's top row of cells (even rows): misses the ink
    g = _coarse([[v if r % 2 == 0 else 0 for v in row] for r, row in enumerate(inp)])
    return _scale(g, 4)


def ink_block_one_tile_left(inp, out):
    # output blocks are drawn one coarse cell to the left (wrapped around)
    g = [row[1:] + row[:1] for row in _coarse(inp)]
    return _scale(g, 4)


ALTERNATIVES = [
    ("blocks of 2x2 instead of 4x4, giving an input-sized output", scale_two),
    ("no tile division: input cells scaled by 2", no_downsample),
    ("tile grid shifted by one cell, giving a larger coarse grid", tile_offset_plus),
    ("coarse tile grid transposed before scaling", transposed),
    ("coarse tile grid mirrored left to right before scaling", mirrored),
    ("blocks of 3x3 instead of 4x4", scale_three),
    ("rows scaled by 4 but columns by 2", aspect_wrong),
    ("tiles of 5x5 cells, later ink wins, blocks of 10x10", big_tiles),
    ("a color is painted only at its first tile", first_color_only),
    ("background taken as the most frequent ink color", bg_filled_with_common_ink),
    ("ink read only from even rows of each tile", ink_only_first_row_of_tile),
    ("coarse grid shifted one tile left with wraparound", ink_block_one_tile_left),
]


def _valid(g):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) and r for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/46f33fce.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
