import json
from pathlib import Path

D4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
D8 = D4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def comps(inp, dirs=D4, wrap=False):
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 3 or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cur = []
            while stack:
                y, x = stack.pop()
                cur.append((y, x))
                for dy, dx in dirs:
                    ny, nx = y + dy, x + dx
                    if wrap:
                        ny, nx = ny % h, nx % w
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == 3 and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            res.append(cur)
    return res


def paint(inp, cells, color=8):
    g = [row[:] for row in inp]
    for y, x in cells:
        g[y][x] = color
    return g


def grouped_cells(inp, dirs=D4, wrap=False, minsize=2):
    return [p for comp in comps(inp, dirs, wrap) if len(comp) >= minsize for p in comp]


def eight_conn(inp, out):
    return paint(inp, grouped_cells(inp, D8))


def largest_only(inp, out):
    cs = comps(inp)
    m = max(len(c) for c in cs)
    big = [c for c in cs if len(c) == m]
    if len(big) != 1:
        return None
    return paint(inp, big[0])


def size_ge4(inp, out):
    return paint(inp, grouped_cells(inp, minsize=4))


def isolated_instead(inp, out):
    return paint(inp, [p for c in comps(inp) if len(c) == 1 for p in c])


def horizontal_only(inp, out):
    return paint(inp, grouped_cells(inp, [(0, -1), (0, 1)]))


def vertical_only(inp, out):
    return paint(inp, grouped_cells(inp, [(-1, 0), (1, 0)]))


def wrong_color(inp, out):
    return [[2 if v == 8 else v for v in row] for row in out]


def all_threes(inp, out):
    return [[8 if v == 3 else v for v in row] for row in inp]


def wraparound(inp, out):
    return paint(inp, grouped_cells(inp, wrap=True))


def erase_isolated(inp, out):
    g = [row[:] for row in out]
    for y, row in enumerate(g):
        for x, v in enumerate(row):
            if v == 3:
                g[y][x] = 0
    return g


def first_component_only(inp, out):
    cs = [c for c in comps(inp) if len(c) >= 2]
    if len(cs) < 2:
        return None
    return paint(inp, cs[0])


def degree_ge2(inp, out):
    h, w = len(inp), len(inp[0])
    cells = []
    for y in range(h):
        for x in range(w):
            if inp[y][x] == 3:
                n = sum(1 for dy, dx in D4 if 0 <= y + dy < h and 0 <= x + dx < w and inp[y + dy][x + dx] == 3)
                if n >= 2:
                    cells.append((y, x))
    return paint(inp, cells)


ALTERNATIVES = [
    ("adjacency includes diagonals (8-connectivity)", eight_conn),
    ("only the single largest 3-group becomes 8", largest_only),
    ("only groups of 4 or more cells become 8", size_ge4),
    ("isolated 3 cells become 8 instead of grouped ones", isolated_instead),
    ("only horizontal neighbors count as adjacent", horizontal_only),
    ("only vertical neighbors count as adjacent", vertical_only),
    ("grouped cells recolored to 2 instead of 8", wrong_color),
    ("every 3 becomes 8, no adjacency condition", all_threes),
    ("grid edges wrap around when checking adjacency", wraparound),
    ("isolated 3 cells are erased to 0", erase_isolated),
    ("only the first (top-left) group becomes 8", first_component_only),
    ("only cells with two or more 3-neighbors become 8", degree_ge2),
]


def valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/67385a82.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
