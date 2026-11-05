import json
from pathlib import Path


def _block(inp):
    cols = [c for c in range(len(inp[0])) if any(r[c] for r in inp)]
    return cols[0], cols[-1] + 1


def _make(inp, fill_col=0, copy=None, gap=0, fill_fn=None, keep_block=True):
    """Build an output: block at left, fill, then a copy `gap` columns short of the right edge."""
    H, W = len(inp), len(inp[0])
    c0, c1 = _block(inp)
    w = c1 - c0
    blk = [r[c0:c1] for r in inp]
    cp = blk if copy is None else copy
    g = []
    for i in range(H):
        f = fill_fn(i, blk) if fill_fn else blk[i][fill_col]
        row = [f] * W
        if keep_block:
            row[c0:c1] = blk[i]
        row[W - w - gap:W - gap] = cp[i]
        g.append(row)
    return g


def _ne(g, out):
    return None if g == out else g


def no_copy(inp, out):
    c0, c1 = _block(inp)
    return _ne(_make(inp, copy=[[r[0]] * (c1 - c0) for r in [rr[c0:c1] for rr in inp]]), out)


def fill_second_col(inp, out):
    return _ne(_make(inp, fill_col=1), out)


def mirrored_copy(inp, out):
    c0, c1 = _block(inp)
    cp = [r[c0:c1][::-1] for r in inp]
    return _ne(_make(inp, copy=cp), out)


def flipped_copy(inp, out):
    c0, c1 = _block(inp)
    cp = [r[c0:c1] for r in inp][::-1]
    return _ne(_make(inp, copy=cp), out)


def no_fill(inp, out):
    H, W = len(inp), len(inp[0])
    c0, c1 = _block(inp)
    g = [r[:] for r in out]
    for i in range(H):
        for c in range(c1, W - (c1 - c0)):
            g[i][c] = 0
    return _ne(g, out)


def copy_off_by_one(inp, out):
    return _ne(_make(inp, gap=1), out)


def copy_adjacent_rest_empty(inp, out):
    H, W = len(inp), len(inp[0])
    c0, c1 = _block(inp)
    w = c1 - c0
    g = [[0] * W for _ in range(H)]
    for i in range(H):
        g[i][c0:c1] = inp[i][c0:c1]
        g[i][c1:c1 + w] = inp[i][c0:c1]
    return _ne(g, out)


def fill_most_common_color(inp, out):
    c0, c1 = _block(inp)
    cnt = {}
    for r in inp:
        for v in r[c0:c1]:
            cnt[v] = cnt.get(v, 0) + 1
    m = max(cnt, key=lambda k: (cnt[k], -k))
    return _ne(_make(inp, fill_fn=lambda i, blk: m), out)


def fill_tile_block(inp, out):
    H, W = len(inp), len(inp[0])
    c0, c1 = _block(inp)
    w = c1 - c0
    g = [[inp[i][c0 + (c % w)] for c in range(W)] for i in range(H)]
    return _ne(g, out)


def fill_color_from_row_above(inp, out):
    return _ne(_make(inp, fill_fn=lambda i, blk: blk[max(i - 1, 0)][0]), out)


def partial_fill_gap_column(inp, out):
    H, W = len(inp), len(inp[0])
    c0, c1 = _block(inp)
    w = c1 - c0
    g = [r[:] for r in out]
    for i in range(H):
        g[i][W - w - 1] = 0
    return _ne(g, out)


def block_moved_not_copied(inp, out):
    H = len(inp)
    c0, c1 = _block(inp)
    g = [r[:] for r in out]
    for i in range(H):
        for c in range(c0, c1):
            g[i][c] = out[i][c0]
    return _ne(g, out)


ALTERNATIVES = [
    ("fill the gap and leave the far-edge copy as plain fill color", no_copy),
    ("fill the gap with each row's second block column instead of the first", fill_second_col),
    ("the far-edge copy is mirrored left to right", mirrored_copy),
    ("the far-edge copy is flipped top to bottom", flipped_copy),
    ("copy the block to the far edge but leave the gap empty", no_fill),
    ("copy sits one column short of the far edge, with an empty column between", copy_off_by_one),
    ("copy sits right next to the block and the rest stays empty", copy_adjacent_rest_empty),
    ("fill the whole gap with the block's most common color", fill_most_common_color),
    ("repeat the block as a tile across the whole width", fill_tile_block),
    ("each row's fill color is taken from the row above", fill_color_from_row_above),
    ("one gap column next to the copy is left empty", partial_fill_gap_column),
    ("block is moved to the far edge, its original cells become fill", block_moved_not_copied),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/62b74c02.json'))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
