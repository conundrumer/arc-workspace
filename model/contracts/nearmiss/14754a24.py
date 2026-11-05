import json
from pathlib import Path

DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _copy(g):
    return [row[:] for row in g]


def _cells(g, v):
    return [(r, c) for r, row in enumerate(g) for c, x in enumerate(row) if x == v]


def fill_wrong_color(inp, out):
    # Painted cells get the mark color 4 instead of 2.
    return [[4 if x == 2 else x for x in row] for row in out]


def overwrite_marks(inp, out):
    # The mark cells are painted too.
    return [[2 if x == 4 else x for x in row] for row in out]


def erase_marks(inp, out):
    # The mark cells are removed after the fill.
    return [[0 if x == 4 else x for x in row] for row in out]


def swap_colors(inp, out):
    # 4 and 2 exchanged.
    return [[2 if x == 4 else 4 if x == 2 else x for x in row] for row in out]


def miss_first_cell(inp, out):
    # The first painted cell in reading order stays unfilled.
    g = _copy(out)
    p = _cells(out, 2)
    if not p:
        return None
    r, c = p[0]
    g[r][c] = inp[r][c]
    return g


def shifted_fill(inp, out):
    # Fill placed one row down.
    g = _copy(inp)
    h, w = len(inp), len(inp[0])
    for r, c in _cells(out, 2):
        if r + 1 < h and inp[r + 1][c] != 4:
            g[r + 1][c] = 2
    return g


def fill_all_neighbors_of_marks(inp, out):
    # Every 5 next to a 4 is filled, with no check that a complete shape results.
    g = _copy(inp)
    h, w = len(inp), len(inp[0])
    for r, c in _cells(inp, 4):
        for dr, dc in DIRS:
            a, b = r + dr, c + dc
            if 0 <= a < h and 0 <= b < w and inp[a][b] == 5:
                g[a][b] = 2
    return g


def fill_background_neighbors(inp, out):
    # The 0 cells next to a 4 are filled instead of the 5 cells.
    g = _copy(inp)
    h, w = len(inp), len(inp[0])
    for r, c in _cells(inp, 4):
        for dr, dc in DIRS:
            a, b = r + dr, c + dc
            if 0 <= a < h and 0 <= b < w and inp[a][b] == 0:
                g[a][b] = 2
    return g


def crop_to_fill(inp, out):
    # Output is the bounding box of the filled cells.
    p = _cells(out, 2)
    if not p:
        return None
    r0 = min(r for r, c in p)
    r1 = max(r for r, c in p)
    c0 = min(c for r, c in p)
    c1 = max(c for r, c in p)
    g = [row[c0:c1 + 1] for row in out[r0:r1 + 1]]
    return g


def clear_unfilled_fives(inp, out):
    # Every 5 that is not filled is cleared.
    return [[0 if x == 5 else x for x in row] for row in out]


def fill_only_centers(inp, out):
    # Only the filled cells with two or more neighbors in the shape are kept.
    h, w = len(out), len(out[0])
    shape = {(r, c) for r in range(h) for c in range(w) if out[r][c] in (2, 4)}
    g = _copy(inp)
    for r, c in _cells(out, 2):
        n = sum((r + dr, c + dc) in shape for dr, dc in DIRS)
        if n >= 2:
            g[r][c] = 2
    return g


ALTERNATIVES = [
    ("fill uses the mark color 4 instead of 2", fill_wrong_color),
    ("mark cells are also painted 2", overwrite_marks),
    ("mark cells are erased to 0 after the fill", erase_marks),
    ("colors 4 and 2 are exchanged", swap_colors),
    ("first filled cell in reading order is left unfilled", miss_first_cell),
    ("fill is placed one row below the correct cells", shifted_fill),
    ("every 5 next to a mark is filled, with no complete-shape check", fill_all_neighbors_of_marks),
    ("0 cells next to a mark are filled instead of 5 cells", fill_background_neighbors),
    ("output is cropped to the bounding box of the fill", crop_to_fill),
    ("all unfilled 5 cells are cleared to 0", clear_unfilled_fives),
    ("only filled cells with two shape neighbors are filled", fill_only_centers),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and all(len(r) == len(g[0]) for r in g) and len(g[0]) > 0
        and all(type(x) is int and 0 <= x <= 9 for r in g for x in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/14754a24.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
