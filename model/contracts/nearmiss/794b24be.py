import json
from pathlib import Path

ORDER = [(0, 0), (0, 1), (0, 2), (1, 1)]


def count(inp):
    return sum(1 for r in inp for v in r if v != 0)


def blank(inp):
    return [[0] * len(inp[0]) for _ in inp]


def fill(inp, n, order=ORDER, color=2):
    g = blank(inp)
    for r, c in order[:max(n, 0)]:
        g[r][c] = color
    return g


def off_by_one_less(inp, out):
    return fill(inp, count(inp) - 1)


def off_by_one_more(inp, out):
    return fill(inp, count(inp) + 1)


def ink_color(inp, out):
    return [[1 if v == 2 else v for v in r] for r in out]


def column_major(inp, out):
    return fill(inp, count(inp), [(0, 0), (1, 0), (2, 0), (1, 1)])


def row_major(inp, out):
    return fill(inp, count(inp), [(0, 0), (0, 1), (0, 2), (1, 0)])


def keep_ink(inp, out):
    g = [r[:] for r in out]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v != 0 and g[r][c] == 0:
                g[r][c] = v
    return g


def count_rows_with_ink(inp, out):
    return fill(inp, sum(1 for r in inp if any(r)))


def count_components(inp, out):
    h, w = len(inp), len(inp[0])
    seen = set()
    n = 0
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0 and (r, c) not in seen:
                n += 1
                stack = [(r, c)]
                seen.add((r, c))
                while stack:
                    y, x = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0 and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
    return fill(inp, n)


def fill_from_bottom(inp, out):
    return out[::-1]


def center_first(inp, out):
    return fill(inp, count(inp), [(1, 1), (0, 0), (0, 1), (0, 2)])


def recolor_in_place(inp, out):
    return [[2 if v != 0 else 0 for v in r] for r in inp]


def cap_at_three(inp, out):
    return fill(inp, min(count(inp), 3))


ALTERNATIVES = [
    ("Fill one cell fewer than the ink count", off_by_one_less),
    ("Fill one cell more than the ink count", off_by_one_more),
    ("Paint the filled cells with the ink color 1 instead of 2", ink_color),
    ("Fill in column-major order down the left column", column_major),
    ("Fill in plain row-major order, wrapping to the second row's first cell", row_major),
    ("Keep the input ink cells and overlay the marks", keep_ink),
    ("Count rows that hold ink instead of ink cells", count_rows_with_ink),
    ("Count 4-connected ink components instead of ink cells", count_components),
    ("Fill the correct cells from the bottom row up", fill_from_bottom),
    ("Fill the center cell first", center_first),
    ("Recolor the ink cells to 2 in place", recolor_in_place),
    ("Cap the count at 3, so the fourth cell is never filled", cap_at_three),
]


def valid(g, out):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/794b24be.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = sum(1 for p in pairs if (g := fn(p["input"], p["output"])) is not None and valid(g, p["output"]))
        print(f"{n}/{len(pairs)}  {desc}")
