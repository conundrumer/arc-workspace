"""Near-miss readings for 8719f442.

Rule: each active input cell (i, j) puts a solid block, in the fill color, on
tile (i+1, j+1) of a (n+2) x (n+2) tile layout. Each active cell on the input
edge also puts a copy of the whole input on the tile just outside that edge
(orthogonal directions only).
"""
import json
from pathlib import Path

ORTH = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _fill(inp):
    return max(max(r) for r in inp)


def _build(inp, blocks=True, copies=True, dirs=ORTH, edge_only=True, off=1,
           block_pattern=None, copy_tf=None, all_cells=False, size_tiles=None):
    n = len(inp)
    fill = _fill(inp)
    m = size_tiles if size_tiles is not None else n + 2
    g = [[0] * (m * n) for _ in range(m * n)]

    def put(ti, tj, pat):
        if not (0 <= ti < m and 0 <= tj < m):
            return
        for a in range(n):
            for b in range(n):
                g[ti * n + a][tj * n + b] = pat[a][b]

    solid = [[fill] * n for _ in range(n)]
    cells = [(i, j) for i in range(n) for j in range(n)
             if all_cells or inp[i][j] != 0]
    seats = {(i + off, j + off) for i, j in cells}
    if blocks:
        for ti, tj in seats:
            put(ti, tj, block_pattern(inp) if block_pattern else solid)
    if copies:
        cp = copy_tf(inp) if copy_tf else inp
        for i, j in cells:
            for di, dj in dirs:
                if edge_only and 0 <= i + di < n and 0 <= j + dj < n:
                    continue
                t = (i + off + di, j + off + dj)
                if t in seats:
                    continue
                put(t[0], t[1], cp)
    return g


def reading_no_copies(inp, out):
    return _build(inp, copies=False)


def reading_no_blocks(inp, out):
    return _build(inp, blocks=False)


def reading_diag_copies(inp, out):
    return _build(inp, dirs=ORTH + DIAG)


def reading_interior_copies(inp, out):
    return _build(inp, edge_only=False)


def reading_no_inset(inp, out):
    # blocks seated with no one-tile inset; copies keep their outer position
    n = len(inp)
    g = _build(inp, copies=True, blocks=False)
    fill = _fill(inp)
    for i in range(n):
        for j in range(n):
            if inp[i][j] != 0:
                for a in range(n):
                    for b in range(n):
                        g[i * n + a][j * n + b] = fill
    return g


def reading_pattern_blocks(inp, out):
    return _build(inp, block_pattern=lambda x: [r[:] for r in x])


def reading_inverted_copies(inp, out):
    fill = _fill(inp)
    return _build(inp, copy_tf=lambda x: [[0 if v else fill for v in r] for r in x])


def reading_vertical_only(inp, out):
    return _build(inp, dirs=[(-1, 0), (1, 0)])


def reading_all_cells_blocked(inp, out):
    return _all_blocks(inp)


def _all_blocks(inp):
    n = len(inp)
    fill = _fill(inp)
    g = _build(inp, blocks=False)
    for ti in range(1, n + 1):
        for tj in range(1, n + 1):
            for a in range(n):
                for b in range(n):
                    g[ti * n + a][tj * n + b] = fill
    return g


def reading_tile_layout(inp, out):
    # output is the tile layout itself: one cell per tile
    n = len(inp)
    fill = _fill(inp)
    m = n + 2
    g = [[0] * m for _ in range(m)]
    for i in range(n):
        for j in range(n):
            if inp[i][j]:
                g[i + 1][j + 1] = fill
                for di, dj in ORTH:
                    if not (0 <= i + di < n and 0 <= j + dj < n):
                        g[i + 1 + di][j + 1 + dj] = fill
    return g


def reading_swapped_edge(inp, out):
    # copy goes to the opposite side of the layout (clamped to the layout)
    n = len(inp)
    m = n + 2
    g = _build(inp, copies=False)
    seats = {(i + 1, j + 1) for i in range(n) for j in range(n) if inp[i][j]}
    for i in range(n):
        for j in range(n):
            if not inp[i][j]:
                continue
            for di, dj in ORTH:
                if 0 <= i + di < n and 0 <= j + dj < n:
                    continue
                t = (i + 1 - di * n, j + 1 - dj * n)
                t = (min(max(t[0], 0), m - 1), min(max(t[1], 0), m - 1))
                if t in seats:
                    continue
                for a in range(n):
                    for b in range(n):
                        g[t[0] * n + a][t[1] * n + b] = inp[a][b]
    return g


def reading_copy_two_tiles_out(inp, out):
    # the copy lands one tile too far from the seat
    n = len(inp)
    m = n + 2
    g = _build(inp, copies=False)
    seats = {(i + 1, j + 1) for i in range(n) for j in range(n) if inp[i][j]}
    for i in range(n):
        for j in range(n):
            if not inp[i][j]:
                continue
            for di, dj in ORTH:
                if 0 <= i + di < n and 0 <= j + dj < n:
                    continue
                t = (i + 1 + 2 * di, j + 1 + 2 * dj)
                if not (0 <= t[0] < m and 0 <= t[1] < m) or t in seats:
                    continue
                for a in range(n):
                    for b in range(n):
                        g[t[0] * n + a][t[1] * n + b] = inp[a][b]
    return g


ALTERNATIVES = [
    ("blocks are placed but the edge copies of the input are left out", reading_no_copies),
    ("edge copies are placed but the solid blocks are left out", reading_no_blocks),
    ("copies also go diagonally outside corner cells", reading_diag_copies),
    ("every active cell gets copies in all four directions, not only at the input edge", reading_interior_copies),
    ("blocks sit at the cell's own tile, with no one-tile inset", reading_no_inset),
    ("blocks hold the input pattern instead of a solid fill", reading_pattern_blocks),
    ("copies are color-inverted (fill and background swapped)", reading_inverted_copies),
    ("copies are placed only above and below, not left and right", reading_vertical_only),
    ("the whole inner 3x3 tile region is filled with blocks, whatever the cell activity", reading_all_cells_blocked),
    ("output is the one-cell-per-tile layout, not the expanded grid", reading_tile_layout),
    ("copies go to the far side of the layout instead of the near side", reading_swapped_edge),
    ("copies land two tiles from the seat instead of one", reading_copy_two_tiles_out),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/8719f442.json"))
    pairs = task["train"]
    # sanity: the correct build reproduces the true output
    assert all(_build(p["input"]) == p["output"] for p in pairs), "base build is wrong"
    print("task 8719f442:", len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, f in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = f([r[:] for r in p["input"]], [r[:] for r in p["output"]])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(ok, "/", len(pairs), f.__name__, "-", desc)
