"""Near-miss readings for ARC task 09629e4f.

The grid is a 3x3 array of 3x3 tiles split by lines of 5. The template is the
tile without any 8 (the one with most 0 cells). Each template cell becomes a
solid 3x3 block of that color at the same position in the tile array.
"""
import json
from pathlib import Path

STEP = 4


def tiles(inp):
    return [[[row[STEP * j:STEP * j + 3] for row in inp[STEP * i:STEP * i + 3]]
             for j in range(3)] for i in range(3)]


def zeros(tile):
    return sum(v == 0 for r in tile for v in r)


def flat_tiles(inp):
    t = tiles(inp)
    return [(i, j, t[i][j]) for i in range(3) for j in range(3)]


def true_template(inp):
    return max(flat_tiles(inp), key=lambda x: zeros(x[2]))[2]


def blank(inp):
    return [[5 if (r % STEP == 3 or c % STEP == 3) else 0 for c in range(len(inp[0]))]
            for r in range(len(inp))]


def paint(inp, cell_fn):
    """cell_fn(i, j, a, b) gives the color of cell (a, b) of tile (i, j)."""
    g = blank(inp)
    for i in range(3):
        for j in range(3):
            for a in range(3):
                for b in range(3):
                    g[STEP * i + a][STEP * j + b] = cell_fn(i, j, a, b)
    return g


def solid(inp, tpl):
    return paint(inp, lambda i, j, a, b: tpl[i][j])


def marked_template(inp, out):
    # wrong tile: the first tile that holds an 8
    for i, j, t in flat_tiles(inp):
        if any(8 in r for r in t):
            return solid(inp, t)
    return None


def densest_template(inp, out):
    t = min(flat_tiles(inp), key=lambda x: zeros(x[2]))[2]
    return solid(inp, t)


def transposed(inp, out):
    t = true_template(inp)
    return solid(inp, [[t[j][i] for j in range(3)] for i in range(3)])


def mirrored(inp, out):
    t = true_template(inp)
    return solid(inp, [r[::-1] for r in t])


def center_only(inp, out):
    t = true_template(inp)
    return paint(inp, lambda i, j, a, b: t[i][j] if (a, b) == (1, 1) else 0)


def no_separators(inp, out):
    return [[out[r][c] for c in range(len(out[0])) if c % STEP != 3]
            for r in range(len(out)) if r % STEP != 3]


def erased_separators(inp, out):
    return [[0 if (r % STEP == 3 or c % STEP == 3) else v for c, v in enumerate(row)]
            for r, row in enumerate(out)]


def template_tile_left_as_input(inp, out):
    ts = flat_tiles(inp)
    i, j, _ = max(ts, key=lambda x: zeros(x[2]))
    g = [row[:] for row in out]
    for a in range(3):
        for b in range(3):
            g[STEP * i + a][STEP * j + b] = inp[STEP * i + a][STEP * j + b]
    return g


def pattern_only(inp, out):
    # output is the 3x3 template itself, one cell per tile
    return [row[:] for row in true_template(inp)]


def rotated(inp, out):
    t = true_template(inp)
    return solid(inp, [[t[2 - j][i] for j in range(3)] for i in range(3)])


def last_block_dropped(inp, out):
    t = true_template(inp)
    cells = [(i, j) for i in range(3) for j in range(3) if t[i][j]]
    di, dj = cells[-1]
    return paint(inp, lambda i, j, a, b: 0 if (i, j) == (di, dj) else t[i][j])


def tile_pattern_copy(inp, out):
    # each template color paints the template's own shape, not a solid block
    t = true_template(inp)
    return paint(inp, lambda i, j, a, b: t[i][j] if t[a][b] else 0)


ALTERNATIVES = [
    ("template is the first tile that holds an 8 (the marker color)", marked_template),
    ("template is the densest tile (fewest 0 cells)", densest_template),
    ("template cells placed transposed in the tile array", transposed),
    ("template cells placed mirrored left to right", mirrored),
    ("template cells placed rotated a quarter turn", rotated),
    ("only the center cell of each tile is colored, not the whole tile", center_only),
    ("separator lines of 5 are cut out of the output", no_separators),
    ("separator lines are cleared to 0", erased_separators),
    ("the tile that held the template keeps its input content", template_tile_left_as_input),
    ("output is the bare 3x3 template, one cell per tile", pattern_only),
    ("the last colored tile is left empty", last_block_dropped),
    ("each colored tile copies the template shape instead of a solid block", tile_pattern_copy),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/09629e4f.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
