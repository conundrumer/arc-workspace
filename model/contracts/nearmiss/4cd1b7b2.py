import json
from collections import Counter
from pathlib import Path


def zeros(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 0]


def fill_with(inp, color):
    return [[color if v == 0 else v for v in row] for row in inp]


def row_only(order):
    # Each row's zeros take the colors missing from that row alone; the column is ignored.
    def f(inp, out):
        g = [row[:] for row in inp]
        n = len(inp)
        for r in range(n):
            missing = [k for k in range(1, n + 1) if k not in inp[r]]
            if order == "desc":
                missing.reverse()
            zs = [c for c in range(n) if inp[r][c] == 0]
            for c, k in zip(zs, missing):
                g[r][c] = k
        return g
    return f


def col_only(inp, out):
    # Each column's zeros take the colors missing from that column alone, in descending order; the row is ignored.
    n = len(inp)
    g = [row[:] for row in inp]
    for c in range(n):
        col = [inp[r][c] for r in range(n)]
        missing = [k for k in range(1, n + 1) if k not in col][::-1]
        zs = [r for r in range(n) if inp[r][c] == 0]
        for r, k in zip(zs, missing):
            g[r][c] = k
    return g


def only_single_zero_rows(inp, out):
    # Fills a zero only when its row has no other zero; other zeros stay 0.
    g = [row[:] for row in inp]
    for r, row in enumerate(inp):
        if row.count(0) == 1:
            c = row.index(0)
            g[r][c] = out[r][c]
    return g


def skip_first_zero_row(inp, out):
    # Leaves the zeros of the first row that has any zero unfilled.
    g = [row[:] for row in out]
    for r, row in enumerate(inp):
        if 0 in row:
            g[r] = row[:]
            break
    return g


def shifted_fill(inp, out):
    # Right color cells, but each fill is the next color up (wrapping 4 to 1).
    n = len(inp)
    return [[(out[r][c] % n) + 1 if inp[r][c] == 0 else out[r][c] for c in range(n)] for r in range(n)]


def copy_from_above(inp, out):
    # Each zero copies the cell above it (the cell below for the top row).
    n = len(inp)
    g = [row[:] for row in inp]
    for r in range(n):
        for c in range(n):
            if inp[r][c] == 0:
                g[r][c] = g[r - 1][c] if r > 0 else g[1][c]
    return g


def most_common_fill(inp, out):
    cnt = Counter(v for row in inp for v in row if v != 0)
    return fill_with(inp, cnt.most_common(1)[0][0])


def flip_h(inp, out):
    return [row[::-1] for row in out]


def transpose(inp, out):
    return [list(col) for col in zip(*out)]


def crop_last(inp, out):
    return [row[:-1] for row in out[:-1]]


def fill_five(inp, out):
    return fill_with(inp, 5)


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("zeros take a new color 5 instead of a color already in the grid", fill_five),
    ("each zero takes a color missing from its row only, in descending order, ignoring columns", row_only("desc")),
    ("each zero takes a color missing from its column only, in descending order, ignoring rows", col_only),
    ("only zeros that are alone in their row are filled; other zeros stay 0", only_single_zero_rows),
    ("zeros in the first row that has a zero are left unfilled", skip_first_zero_row),
    ("every filled cell gets the next color up, wrapping 4 to 1", shifted_fill),
    ("each zero copies the cell above it", copy_from_above),
    ("every zero takes the most common non-zero color", most_common_fill),
    ("correct fill, mirrored left to right", flip_h),
    ("correct fill, transposed", transpose),
    ("correct fill, with the last row and column cropped off", crop_last),
    ("input returned unchanged", unchanged),
]


def valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/4cd1b7b2.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
