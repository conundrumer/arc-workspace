"""Near-miss readings for ARC task 00576224 (2x2 input -> 6x6, 3x3 tiling with a flipped middle band)."""
import json
from pathlib import Path


def fliplr(g):
    return [r[::-1] for r in g]


def flipud(g):
    return g[::-1]


def rot180(g):
    return [r[::-1] for r in g[::-1]]


def transpose(g):
    return [list(r) for r in zip(*g)]


def rot90(g):
    return [list(r) for r in zip(*g[::-1])]


def tile(blocks):
    """blocks: list of rows, each a list of grids of equal size."""
    out = []
    for brow in blocks:
        h = len(brow[0])
        for a in range(h):
            out.append([v for blk in brow for v in blk[a]])
    return out


def bands(inp, fns, ncols=3):
    return tile([[fn(inp) for _ in range(ncols)] for fn in fns])


def ident(g):
    return [list(r) for r in g]


def plain_tiling(inp, out):
    return bands(inp, [ident, ident, ident])


def middle_flipud(inp, out):
    return bands(inp, [ident, flipud, ident])


def middle_rot180(inp, out):
    return bands(inp, [ident, rot180, ident])


def middle_transpose(inp, out):
    return bands(inp, [ident, transpose, ident])


def bottom_flipped(inp, out):
    return bands(inp, [ident, ident, fliplr])


def top_and_bottom_flipped(inp, out):
    return bands(inp, [fliplr, ident, fliplr])


def flip_middle_column(inp, out):
    cols = [ident, fliplr, ident]
    return tile([[c(inp) for c in cols] for _ in range(3)])


def checkerboard_flip(inp, out):
    fns = [ident, fliplr]
    return tile([[fns[(i + j) % 2](inp) for j in range(3)] for i in range(3)])


def cumulative_rot90(inp, out):
    return bands(inp, [ident, rot90, rot180])


def two_bands_only(inp, out):
    return bands(inp, [ident, fliplr])


def two_columns_only(inp, out):
    return bands(inp, [ident, fliplr, ident], ncols=2)


def mirror_whole_output(inp, out):
    return fliplr(out)


ALTERNATIVES = [
    ("tile the input 3x3 with no flip anywhere", plain_tiling),
    ("middle band flipped top-to-bottom instead of left-to-right", middle_flipud),
    ("middle band rotated 180 degrees instead of mirrored left-to-right", middle_rot180),
    ("middle band transposed instead of mirrored left-to-right", middle_transpose),
    ("the bottom band is the flipped one instead of the middle", bottom_flipped),
    ("top and bottom bands flipped, middle plain", top_and_bottom_flipped),
    ("the middle column of blocks is flipped instead of the middle row", flip_middle_column),
    ("blocks flipped in a checkerboard pattern", checkerboard_flip),
    ("each band rotates a further quarter turn (0, 90, 180)", cumulative_rot90),
    ("only two bands of blocks (plain, flipped): 4x6 output", two_bands_only),
    ("only two columns of blocks: 6x4 output", two_columns_only),
    ("the correct output mirrored left-to-right as a whole", mirror_whole_output),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/00576224.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
