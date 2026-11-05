import json
from pathlib import Path


def _blocks(inp, color):
    h, w = len(inp), len(inp[0])
    n = 0
    for r in range(h - 1):
        for c in range(w - 1):
            if all(inp[r + i][c + j] == color for i in (0, 1) for j in (0, 1)):
                n += 1
    return n


def _components(inp, color):
    h, w = len(inp), len(inp[0])
    seen = set()
    n = 0
    for r in range(h):
        for c in range(w):
            if inp[r][c] == color and (r, c) not in seen:
                n += 1
                stack = [(r, c)]
                seen.add((r, c))
                while stack:
                    y, x = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == color and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
    return n


def _diag(n, size=3):
    n = max(0, min(size, n))
    return [[1 if (i == j and i < n) else 0 for j in range(size)] for i in range(size)]


def count_color2(inp, out):
    return _diag(_blocks(inp, 2))


def count_both_colors(inp, out):
    return _diag(_blocks(inp, 2) + _blocks(inp, 3))


def count_plus_one(inp, out):
    return _diag(_blocks(inp, 3) + 1)


def count_minus_one(inp, out):
    return _diag(_blocks(inp, 3) - 1)


def anti_diagonal(inp, out):
    return [row[::-1] for row in out]


def row_major_fill(inp, out):
    n = _blocks(inp, 3)
    return [[1 if 3 * i + j < n else 0 for j in range(3)] for i in range(3)]


def count_single_cell_components(inp, out):
    return _diag(_components(inp, 3))


def square_size_n(inp, out):
    n = _blocks(inp, 3)
    return [[1 if i == j else 0 for j in range(n)] for i in range(n)]


def mark_color_3(inp, out):
    return [[3 if v == 1 else v for v in row] for row in out]


def always_full_diagonal(inp, out):
    return _diag(3)


def last_cells_of_diagonal(inp, out):
    n = _blocks(inp, 3)
    return [[1 if i == j and i >= 3 - n else 0 for j in range(3)] for i in range(3)]


ALTERNATIVES = [
    ("count 2x2 blocks of color 2 instead of color 3", count_color2),
    ("count 2x2 blocks of both colors 2 and 3", count_both_colors),
    ("diagonal length is block count plus one", count_plus_one),
    ("diagonal length is block count minus one", count_minus_one),
    ("mark the anti-diagonal instead of the main diagonal", anti_diagonal),
    ("fill the first N cells in row-major order instead of the diagonal", row_major_fill),
    ("count connected components of color 3 instead of 2x2 blocks", count_single_cell_components),
    ("output is an N by N identity grid sized by the block count", square_size_n),
    ("mark with color 3 instead of 1", mark_color_3),
    ("ignore the count and mark the whole diagonal", always_full_diagonal),
    ("mark the last N diagonal cells instead of the first N", last_cells_of_diagonal),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/3b4c2228.json').read_text())
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        k = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                k += 1
        print(f"{k}/{len(pairs)}  {desc}")
