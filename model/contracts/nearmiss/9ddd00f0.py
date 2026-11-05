import json
from pathlib import Path


def _geom(inp):
    h = len(inp)
    n = 1
    while n * n + n - 1 < h:
        n += 1
    ink = max(v for row in inp for v in row)
    return n, ink


def _build(inp, hole, base=None, only=None, gaps=False, color=None):
    """Fill every block with ink but for the cell hole(r, c, n); start from base (default input).
    only(r, c, inp_block_empty) decides which blocks are touched."""
    n, ink = _geom(inp)
    ink = ink if color is None else color
    g = [row[:] for row in (base if base is not None else inp)]
    for r in range(n):
        for c in range(n):
            r0, c0 = r * (n + 1), c * (n + 1)
            empty = all(inp[r0 + i][c0 + j] == 0 for i in range(n) for j in range(n))
            if only is not None and not only(r, c, empty):
                continue
            hr, hc = hole(r, c, n)
            for i in range(n):
                for j in range(n):
                    g[r0 + i][c0 + j] = 0 if (i, j) == (hr, hc) else ink
    if gaps:
        for i in range(len(g)):
            for j in range(len(g[0])):
                if i % (n + 1) == n or j % (n + 1) == n:
                    g[i][j] = ink
    return g


def transposed(inp, out):
    return _build(inp, lambda r, c, n: (c, r))


def flip_row(inp, out):
    return _build(inp, lambda r, c, n: (n - 1 - r, c))


def flip_col(inp, out):
    return _build(inp, lambda r, c, n: (r, n - 1 - c))


def fixed_corner(inp, out):
    return _build(inp, lambda r, c, n: (0, 0))


def centre(inp, out):
    return _build(inp, lambda r, c, n: (n // 2, n // 2))


def shifted_col(inp, out):
    return _build(inp, lambda r, c, n: (r, (c + 1) % n))


def no_hole(inp, out):
    return _build(inp, lambda r, c, n: (-1, -1))


def only_empty_blocks_diag(inp, out):
    return _build(inp, lambda r, c, n: (r, c), only=lambda r, c, e: r == c)


def gaps_inked(inp, out):
    return _build(inp, lambda r, c, n: (r, c), gaps=True)


def wrong_colour(inp, out):
    n, ink = _geom(inp)
    return [[((v + 1) % 10 or 1) if v else 0 for v in row] for row in out]


def unchanged(inp, out):
    return [row[:] for row in inp]


def hole_at_block_index(inp, out):
    # hole column from the block's row-major index, row fixed at 0
    return _build(inp, lambda r, c, n: (0, (r * n + c) % n))


ALTERNATIVES = [
    ("hole at (column, row) of the block in the arrangement: transposed place", transposed),
    ("hole row mirrored vertically: (N-1-row, column)", flip_row),
    ("hole column mirrored horizontally: (row, N-1-column)", flip_col),
    ("hole fixed at the top-left cell of every block", fixed_corner),
    ("hole fixed at the centre cell of every block", centre),
    ("hole column shifted by one to the right with wrap", shifted_col),
    ("every block filled completely, no hole", no_hole),
    ("only the diagonal blocks are filled, others keep the input", only_empty_blocks_diag),
    ("the background lines between blocks are inked as well", gaps_inked),
    ("output ink drawn in a different color than the input ink", wrong_colour),
    ("hole in row 0, column from row-major block index mod block size", hole_at_block_index),
    ("output equals the input", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/9ddd00f0.json').read_text())
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        cnt = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                cnt += 1
        print(f"{cnt}/{len(pairs)}  {desc}")
