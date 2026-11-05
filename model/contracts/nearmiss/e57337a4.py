"""Near-miss rules for e57337a4.

True rule: split the 15x15 input into a 3x3 grid of 5x5 blocks. A block that
holds the rarest color becomes that color in the output; every other block
becomes the most common color.
"""
import json
from collections import Counter
from pathlib import Path


def _colors(inp):
    c = Counter(v for r in inp for v in r)
    ranked = c.most_common()
    return ranked[0][0], ranked[-1][0]  # background, mark


def _blocks(inp, n_out, size):
    """Return, per output cell, the list of input cells in its size x size block."""
    h, w = len(inp), len(inp[0])
    res = [[[] for _ in range(n_out)] for _ in range(n_out)]
    for r in range(h):
        for c in range(w):
            i, j = min(r // size, n_out - 1), min(c // size, n_out - 1)
            res[i][j].append(inp[r][c])
    return res


def _tile(inp, n_out, size, offset=(0, 0)):
    bg, mark = _colors(inp)
    out = [[bg] * n_out for _ in range(n_out)]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == mark:
                i = min(max((r + offset[0]) // size, 0), n_out - 1)
                j = min(max((c + offset[1]) // size, 0), n_out - 1)
                out[i][j] = mark
    return out


def swap_colors(inp, out):
    bg, mark = _colors(inp)
    return [[bg if v == mark else mark for v in r] for r in out]


def transpose(inp, out):
    g = [list(r) for r in zip(*out)]
    return None if g == out else g


def flip_h(inp, out):
    return [r[::-1] for r in out]


def rot180(inp, out):
    return [r[::-1] for r in out[::-1]]


def block_size_3(inp, out):
    # 3-cell blocks, giving a 5x5 output
    return _tile(inp, 5, 3)


def grid_4x4(inp, out):
    # 4x4 output grid with blocks of 4 (ceil(15/4)), last cells clipped
    return _tile(inp, 4, 4)


def top_left_sample(inp, out):
    # sample one cell per block instead of testing the whole block
    return [[inp[5 * i][5 * j] for j in range(3)] for i in range(3)]


def shifted_blocks(inp, out):
    # block boundaries shifted by 3 cells
    return _tile(inp, 3, 5, offset=(3, 3))


def first_mark_only(inp, out):
    bg, mark = _colors(inp)
    res = [[bg] * len(out[0]) for _ in out]
    for i, r in enumerate(out):
        for j, v in enumerate(r):
            if v == mark:
                res[i][j] = mark
                return None if res == out else res
    return None


def need_two_marks(inp, out):
    # a block counts as marked only with at least two marker cells
    bg, mark = _colors(inp)
    cnt = _blocks(inp, 3, 5)
    return [[mark if sum(v == mark for v in cnt[i][j]) >= 2 else bg
             for j in range(3)] for i in range(3)]


def dilated_marks(inp, out):
    # marked output cells also mark their 4-neighbours
    bg, mark = _colors(inp)
    res = [r[:] for r in out]
    h, w = len(out), len(out[0])
    for i in range(h):
        for j in range(w):
            if out[i][j] == mark:
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    a, b = i + di, j + dj
                    if 0 <= a < h and 0 <= b < w:
                        res[a][b] = mark
    return res


def all_background(inp, out):
    bg, _ = _colors(inp)
    return [[bg] * len(out[0]) for _ in out]


ALTERNATIVES = [
    ("swap the two colors: marked blocks get the background, others get the mark", swap_colors),
    ("transpose the output (row and column of a block swapped)", transpose),
    ("mirror the output left to right", flip_h),
    ("rotate the output by 180 degrees", rot180),
    ("use 3x3-cell blocks, giving a 5x5 output", block_size_3),
    ("use 4x4-cell blocks, giving a 4x4 output", grid_4x4),
    ("read only the top-left cell of each 5x5 block", top_left_sample),
    ("block boundaries shifted by 3 cells", shifted_blocks),
    ("only the first marked block (row-major) is marked", first_mark_only),
    ("a block is marked only if it holds two or more mark cells", need_two_marks),
    ("marked blocks also mark their 4-neighbour blocks", dilated_marks),
    ("ignore the marks: output all background", all_background),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/e57337a4.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
