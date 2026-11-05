"""Near-miss readings for ff28f65a.

Rule: the input holds 2x2 blocks of color 2 on a 0 background. The output is
a 3x3 grid; the first N cells of the order (0,0) (0,2) (1,1) (2,0) (2,2) are
1, where N is the block count. All other cells are 0.
"""
import json
from pathlib import Path

TRUE_ORDER = [(0, 0), (0, 2), (1, 1), (2, 0), (2, 2)]


def count_blocks(inp):
    cells = sum(1 for r in inp for v in r if v != 0)
    return cells // 4


def render(n, order, size=3, mark=1, bg=0):
    g = [[bg] * size for _ in range(size)]
    for (r, c) in order[: max(n, 0)]:
        g[r][c] = mark
    return g


def count_cells_capped(inp, out):
    cells = sum(1 for r in inp for v in r if v != 0)
    return render(cells, TRUE_ORDER)


def one_too_few(inp, out):
    return render(count_blocks(inp) - 1, TRUE_ORDER)


def one_too_many(inp, out):
    return render(count_blocks(inp) + 1, TRUE_ORDER)


def column_major(inp, out):
    order = [(0, 0), (2, 0), (1, 1), (0, 2), (2, 2)]
    return render(count_blocks(inp), order)


def reversed_order(inp, out):
    return render(count_blocks(inp), TRUE_ORDER[::-1])


def center_first(inp, out):
    order = [(1, 1), (0, 0), (0, 2), (2, 0), (2, 2)]
    return render(count_blocks(inp), order)


def mark_color_two(inp, out):
    return [[2 if v == 1 else v for v in row] for row in out]


def row_major_all_cells(inp, out):
    order = [(r, c) for r in range(3) for c in range(3)]
    return render(count_blocks(inp), order)


def single_row(inp, out):
    n = count_blocks(inp)
    return [[1] * n]


def inverted(inp, out):
    return [[1 - v for v in row] for row in out]


def mirrored_corner(inp, out):
    order = [(0, 2), (0, 0), (1, 1), (2, 2), (2, 0)]
    return render(count_blocks(inp), order)


def count_block_rows(inp, out):
    # counts the distinct row bands that hold a block instead of the blocks
    rows = [i for i, r in enumerate(inp) if any(r)]
    bands = 0
    prev = -2
    for i in rows:
        if i > prev + 1:
            bands += 1
        prev = i
    return render(bands, TRUE_ORDER)


ALTERNATIVES = [
    ("count the colored cells instead of the 2x2 blocks (cap at 5)", count_cells_capped),
    ("mark one cell too few", one_too_few),
    ("mark one cell too many", one_too_many),
    ("fill the diagonal cells in column-major order", column_major),
    ("fill the diagonal cells from the last one backward", reversed_order),
    ("fill the center cell first", center_first),
    ("mark with color 2, the block color, instead of 1", mark_color_two),
    ("fill all 9 cells in row-major order", row_major_all_cells),
    ("output a single row of N ones instead of the 3x3 grid", single_row),
    ("swap the mark and background colors", inverted),
    ("fill the top-right corner before the top-left", mirrored_corner),
    ("count row bands that hold a block instead of the blocks", count_block_rows),
]


def valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/ff28f65a.json").read_text())
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
