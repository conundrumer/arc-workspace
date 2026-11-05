import json
from pathlib import Path


def comps(g, color):
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if g[r][c] != color or (r, c) in seen:
                continue
            stack, cells = [(r, c)], []
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and g[ny][nx] == color and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            res.append(cells)
    return res


def is_block(cells):
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return len(cells) == 4 and max(ys) - min(ys) == 1 and max(xs) - min(xs) == 1


def blocks(g, color):
    return sum(1 for c in comps(g, color) if is_block(c))


def bar(out, n, color=1, right=False, start=0):
    w = len(out[0])
    n = max(0, min(n, w))
    row = [0] * w
    for i in range(n):
        j = (w - 1 - i) if right else start + i
        if 0 <= j < w:
            row[j] = color
    return [row]


def true_n(out):
    return sum(1 for v in out[0] if v)


def all_components(inp, out):
    return bar(out, len(comps(inp, 1)))


def red_blocks(inp, out):
    return bar(out, blocks(inp, 2))


def red_bar(inp, out):
    return [[2 if v else 0 for v in out[0]]]


def right_aligned(inp, out):
    return bar(out, true_n(out), right=True)


def both_colors(inp, out):
    return bar(out, blocks(inp, 1) + blocks(inp, 2))


def minus_one(inp, out):
    return bar(out, true_n(out) - 1)


def plus_one(inp, out):
    return bar(out, true_n(out) + 1)


def cell_count(inp, out):
    return bar(out, sum(v == 1 for r in inp for v in r))


def transposed(inp, out):
    return [[v] for v in out[0]]


def full_bar(inp, out):
    return [[1] * len(out[0])]


def offset_start(inp, out):
    return bar(out, true_n(out), start=1)


def single_cells_only(inp, out):
    return bar(out, sum(1 for c in comps(inp, 1) if len(c) == 1))


ALTERNATIVES = [
    ("count every 4-connected color-1 component, including single cells", all_components),
    ("count the 2x2 blocks of color 2 instead of color 1", red_blocks),
    ("draw the bar in color 2 instead of color 1", red_bar),
    ("draw the bar from the right end instead of the left", right_aligned),
    ("count 2x2 blocks of both colors 1 and 2", both_colors),
    ("bar one cell too short", minus_one),
    ("bar one cell too long", plus_one),
    ("bar length is the number of color-1 cells in the input", cell_count),
    ("output is a column (5x1) instead of a row", transposed),
    ("fill the whole bar, ignoring the block count", full_bar),
    ("bar starts at the second cell instead of the first", offset_start),
    ("count only isolated single color-1 cells", single_cells_only),
]


def valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/1fad071e.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
