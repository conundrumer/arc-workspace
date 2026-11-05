import json
from pathlib import Path


def parse(out):
    """Return (T, occ, tile) of the true fractal output; gap is 1."""
    n = len(out)
    T = next(t for t in range(2, 20) if t * t + t - 1 == n)
    step = T + 1
    occ = [[False] * T for _ in range(T)]
    tile = None
    for r in range(T):
        for c in range(T):
            blk = [row[c * step:c * step + T] for row in out[r * step:r * step + T]]
            if any(v != 0 for row in blk for v in row):
                occ[r][c] = True
                if tile is None:
                    tile = [[2 if v else 0 for v in row] for row in blk]
    return T, occ, tile


def build(T, occ, tile_of, mark_of=None, color=8, mark_empty=False):
    step = T + 1
    n = T * T + T - 1
    g = [[0] * n for _ in range(n)]
    for r in range(T):
        for c in range(T):
            if not occ[r][c]:
                if not (mark_empty and mark_of):
                    continue
            else:
                tile = tile_of(r, c)
                for i in range(T):
                    for j in range(T):
                        g[r * step + i][c * step + j] = tile[i][j]
            if mark_of:
                p = mark_of(r, c)
                if p is not None:
                    i, j = p
                    if 0 <= i < T and 0 <= j < T:
                        if occ[r][c] and g[r * step + i][c * step + j] == 0:
                            continue
                        g[r * step + i][c * step + j] = color
    return g


def alt_mark_color_3(inp, out):
    return [[3 if v == 8 else v for v in row] for row in out]


def alt_no_marks(inp, out):
    return [[2 if v == 8 else v for v in row] for row in out]


def alt_mark_transposed(inp, out):
    T, occ, tile = parse(out)
    return build(T, occ, lambda r, c: tile, lambda r, c: (c, r))


def alt_mark_mirrored(inp, out):
    T, occ, tile = parse(out)
    return build(T, occ, lambda r, c: tile, lambda r, c: (r, T - 1 - c))


def alt_mark_off_by_one(inp, out):
    T, occ, tile = parse(out)
    return build(T, occ, lambda r, c: tile, lambda r, c: (r, (c + 1) % T))


def alt_inverted_occupancy(inp, out):
    T, occ, tile = parse(out)
    inv = [[not x for x in row] for row in occ]
    return build(T, inv, lambda r, c: tile, lambda r, c: (r, c))


def alt_flipped_tile(inp, out):
    T, occ, tile = parse(out)
    flipped = [row[::-1] for row in tile]
    return build(T, occ, lambda r, c: flipped, lambda r, c: (r, c))


def alt_marks_first_block_row_only(inp, out):
    T, occ, tile = parse(out)
    step = T + 1
    g = [row[:] for row in out]
    for y in range(step, len(g)):
        for x in range(len(g)):
            if g[y][x] == 8:
                g[y][x] = 2
    return g


def alt_marks_in_empty_blocks_too(inp, out):
    T, occ, tile = parse(out)
    return build(T, occ, lambda r, c: tile, lambda r, c: (r, c), mark_empty=True)


def alt_return_tile(inp, out):
    T, occ, tile = parse(out)
    return [row[:] for row in tile]


def alt_input_unchanged(inp, out):
    return [row[:] for row in inp]


def alt_no_gap(inp, out):
    T, occ, tile = parse(out)
    n = T * T
    g = [[0] * n for _ in range(n)]
    for r in range(T):
        for c in range(T):
            if occ[r][c]:
                for i in range(T):
                    for j in range(T):
                        g[r * T + i][c * T + j] = tile[i][j]
                if tile[r][c]:
                    g[r * T + r][c * T + c] = 8
    return g


ALTERNATIVES = [
    ("mark color is the input's 3 instead of 8", alt_mark_color_3),
    ("marks omitted: fractal drawn only in ink", alt_no_marks),
    ("mark sits at the transposed tile position (c, r) of block (r, c)", alt_mark_transposed),
    ("mark sits at the mirrored column T-1-c of the tile", alt_mark_mirrored),
    ("mark sits one column right of the correct tile position", alt_mark_off_by_one),
    ("blocks are filled where the shape is empty (occupancy inverted)", alt_inverted_occupancy),
    ("each block holds a horizontally flipped copy of the tile", alt_flipped_tile),
    ("marks only in the first row of blocks", alt_marks_first_block_row_only),
    ("a mark is also placed in empty blocks", alt_marks_in_empty_blocks_too),
    ("output is just the single shape tile", alt_return_tile),
    ("blocks are laid out with no gap between them", alt_no_gap),
    ("output equals the input", alt_input_unchanged),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/456873bc.json').read_text())
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        cnt = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                cnt += 1
        print(cnt, desc)
