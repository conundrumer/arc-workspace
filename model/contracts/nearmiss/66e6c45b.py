"""Near-miss readings for ARC task 66e6c45b.

True rule: the 2x2 shape in the middle of the grid is erased, and each of its
cells moves diagonally outward to the grid corner on its own side.
"""
import json
from pathlib import Path


def _copy(g):
    return [list(r) for r in g]


def _corners(g):
    h, w = len(g), len(g[0])
    return (0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)


def _corner_perm(out, perm):
    """Copy of out whose corner i holds the color of out's corner perm[i]."""
    g = _copy(out)
    cs = _corners(out)
    for i, j in enumerate(perm):
        g[cs[i][0]][cs[i][1]] = out[cs[j][0]][cs[j][1]]
    return g


def center_kept(inp, out):
    # corners are filled but the original shape is not erased
    g = _copy(out)
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v and not g[r][c]:
                g[r][c] = v
    return g


def swap_left_right(inp, out):
    # cells go to the horizontally mirrored corner
    return _corner_perm(out, (1, 0, 3, 2))


def swap_top_bottom(inp, out):
    # cells go to the vertically mirrored corner
    return _corner_perm(out, (2, 3, 0, 1))


def opposite_corner(inp, out):
    # cells go to the diagonally opposite corner
    return _corner_perm(out, (3, 2, 1, 0))


def rotate_corners(inp, out):
    # cells go to the next corner clockwise
    return _corner_perm(out, (2, 0, 3, 1))


def horizontal_only(inp, out):
    # cells move sideways to the left/right edge, rows unchanged
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v:
                g[r][0 if c < w / 2 else w - 1] = v
    return g


def vertical_only(inp, out):
    # cells move up/down to the top/bottom edge, columns unchanged
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v:
                g[0 if r < h / 2 else h - 1][c] = v
    return g


def only_top_row_moves(inp, out):
    # top cells reach the corners; bottom cells stay where they are
    g = _copy(out)
    h, w = len(out), len(out[0])
    for r in (h - 1,):
        for c in range(w):
            g[r][c] = 0
    for r in range(h // 2, h):
        for c in range(w):
            if inp[r][c]:
                g[r][c] = inp[r][c]
    return g


def corner_blocks(inp, out):
    # each cell grows into a 2x2 block at its corner
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    cs = _corners(out)
    for (r, c) in cs:
        v = out[r][c]
        dr = 1 if r == 0 else -1
        dc = 1 if c == 0 else -1
        for a in (0, 1):
            for b in (0, 1):
                g[r + a * dr][c + b * dc] = v
    return g


def single_color(inp, out):
    # all four corners take the color of the top-left cell
    g = _copy(out)
    v = out[0][0]
    for r, c in _corners(out):
        g[r][c] = v
    return g


def crop_shape(inp, out):
    # output is just the cropped 2x2 shape
    rows = [r for r, row in enumerate(inp) if any(row)]
    cols = [c for c in range(len(inp[0])) if any(row[c] for row in inp)]
    return [row[cols[0]:cols[-1] + 1] for row in inp[rows[0]:rows[-1] + 1]]


def three_corners_only(inp, out):
    # the bottom-right cell is dropped
    g = _copy(out)
    g[len(g) - 1][len(g[0]) - 1] = 0
    return g


ALTERNATIVES = [
    ("corners filled but the original shape is not erased", center_kept),
    ("cells go to the horizontally mirrored corner", swap_left_right),
    ("cells go to the vertically mirrored corner", swap_top_bottom),
    ("cells go to the diagonally opposite corner", opposite_corner),
    ("cells go to the next corner clockwise", rotate_corners),
    ("cells move sideways to the left/right edge only", horizontal_only),
    ("cells move up/down to the top/bottom edge only", vertical_only),
    ("only the top cells move to corners; bottom cells stay", only_top_row_moves),
    ("each cell grows into a 2x2 block at its corner", corner_blocks),
    ("all four corners take the top-left cell's color", single_color),
    ("output is only the cropped 2x2 shape", crop_shape),
    ("bottom-right cell is dropped", three_corners_only),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/66e6c45b.json").read_text())
    train = task["train"]
    print(f"pairs: {len(train)}")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in train)
        print(f"{n}/{len(train)}  {desc}")
