import json
from pathlib import Path


def _bbox(g):
    cells = [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return r0, r1, c0, c1


def _segments(n, boundary):
    """Split range(n) into runs; boundary(i) says a break lies between i and i+1."""
    segs, start = [], 0
    for i in range(n - 1):
        if boundary(i):
            segs.append((start, i))
            start = i + 1
    segs.append((start, n - 1))
    return segs


def _blocks(inp):
    r0, r1, c0, c1 = _bbox(inp)
    sub = [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]
    h, w = len(sub), len(sub[0])

    def rbreak(i):
        return any(sub[i][c] and sub[i + 1][c] and sub[i][c] != sub[i + 1][c] for c in range(w))

    def cbreak(j):
        return any(sub[r][j] and sub[r][j + 1] and sub[r][j] != sub[r][j + 1] for r in range(h))

    return sub, _segments(h, rbreak), _segments(w, cbreak)


def _tile_grid(inp, pick):
    sub, rs, cs = _blocks(inp)
    return [[pick(sub, a, b, c, d) for (c, d) in cs] for (a, b) in rs]


def _majority(sub, a, b, c, d):
    cnt = {}
    for r in range(a, b + 1):
        for k in range(c, d + 1):
            if sub[r][k]:
                cnt[sub[r][k]] = cnt.get(sub[r][k], 0) + 1
    return max(cnt, key=cnt.get)


def _topleft(sub, a, b, c, d):
    return sub[a][c]


def _flip_h(g):
    return [row[::-1] for row in g]


def _flip_v(g):
    return g[::-1]


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _tiles(inp):
    return _tile_grid(inp, _majority)


def no_flip(inp, out):
    return _tiles(inp)


def flip_vertical(inp, out):
    return _flip_v(_tiles(inp))


def rot180(inp, out):
    return _flip_v(_flip_h(_tiles(inp)))


def transpose(inp, out):
    return _transpose(_tiles(inp))


def rotate_cw(inp, out):
    return _flip_h(_transpose(_tiles(inp)))


def crop_no_collapse(inp, out):
    # every line kept at full size, mirrored, with no merging of lines into tiles
    r0, r1, c0, c1 = _bbox(inp)
    return _flip_h([row[c0:c1 + 1] for row in inp[r0:r1 + 1]])


def mirror_first_row_only(inp, out):
    # the mirror is applied to the top row of tiles only
    t = _tiles(inp)
    return [t[0][::-1]] + t[1:]


def drop_last_tile_row(inp, out):
    return out[:-1]


def drop_first_tile_col(inp, out):
    return [row[1:] for row in out]


def zero_border(inp, out):
    w = len(out[0])
    return [[0] * (w + 2)] + [[0] + row + [0] for row in out] + [[0] * (w + 2)]


def shift_columns(inp, out):
    return [row[1:] + row[:1] for row in out]


def corner_cell_color(inp, out):
    # tile color read from the top-left cell of each block, mirrored; a hole there gives 0
    return _flip_h(_tile_grid(inp, _topleft))


ALTERNATIVES = [
    ("tile grid is not mirrored", no_flip),
    ("tile grid is flipped top to bottom instead of left to right", flip_vertical),
    ("tile grid is rotated 180 degrees", rot180),
    ("tile grid is transposed", transpose),
    ("tile grid is rotated 90 degrees clockwise", rotate_cw),
    ("each line is kept at full size, no collapse into tiles", crop_no_collapse),
    ("only the top row of tiles is mirrored", mirror_first_row_only),
    ("last row of tiles is dropped", drop_last_tile_row),
    ("first column of tiles is dropped", drop_first_tile_col),
    ("output is padded with a border of background", zero_border),
    ("tile columns are cyclically shifted by one", shift_columns),
    ("tile color is read from the block's top-left cell, so a hole gives 0", corner_cell_color),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/80214e03.json").read_text())
    pairs = task["train"]
    for p in pairs:
        assert _flip_h(_tiles(p["input"])) == p["output"], "tile parse mismatch"
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
