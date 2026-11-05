import json
from pathlib import Path

COLOR_OF_SIZE = {1: 4, 2: 3, 3: 2, 4: 1}


def comps(g, diag=False):
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diag:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    for r in range(h):
        for c in range(w):
            if g[r][c] == 0 or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in steps:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != 0 and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            res.append(cells)
    return res


def paint(inp, fn, diag=False):
    g = [row[:] for row in inp]
    cs = comps(inp, diag)
    for i, cells in enumerate(cs):
        col = fn(cells, cs, i)
        for y, x in cells:
            g[y][x] = col
    return g


def runs(g, horizontal):
    h, w = len(g), len(g[0])
    res = []
    outer, inner = (h, w) if horizontal else (w, h)
    for a in range(outer):
        cur = []
        for b in range(inner):
            y, x = (a, b) if horizontal else (b, a)
            if g[y][x] != 0:
                cur.append((y, x))
            else:
                if cur:
                    res.append(cur)
                cur = []
        if cur:
            res.append(cur)
    return res


def clamp(n):
    return COLOR_OF_SIZE.get(n, 5)


def merged_across_gap(inp, out):
    cs = comps(inp)
    parent = list(range(len(cs)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            if any(max(abs(a - c), abs(b - d)) <= 2 for a, b in cs[i] for c, d in cs[j]):
                parent[find(i)] = find(j)
    groups = {}
    for i, cells in enumerate(cs):
        groups.setdefault(find(i), []).extend(cells)
    g = [row[:] for row in inp]
    for cells in groups.values():
        for y, x in cells:
            g[y][x] = clamp(len(cells))
    return g


def color_equals_size(inp, out):
    return paint(inp, lambda c, cs, i: len(c))


def rank_ascending(inp, out):
    def f(c, cs, i):
        sizes = sorted(set(len(k) for k in cs))
        return sizes.index(len(c)) + 1
    return paint(inp, f)


def reading_order_index(inp, out):
    return paint(inp, lambda c, cs, i: i % 4 + 1)


def pairs_left_uncolored(inp, out):
    return paint(inp, lambda c, cs, i: 5 if len(c) == 2 else clamp(len(c)))


def largest_left_uncolored(inp, out):
    m = max(len(k) for k in comps(inp))
    return paint(inp, lambda c, cs, i: 5 if len(c) == m else clamp(len(c)))


def horizontal_runs(inp, out):
    g = [row[:] for row in inp]
    for cells in runs(inp, True):
        for y, x in cells:
            g[y][x] = clamp(len(cells))
    return g


def vertical_runs(inp, out):
    g = [row[:] for row in inp]
    for cells in runs(inp, False):
        for y, x in cells:
            g[y][x] = clamp(len(cells))
    return g


def bbox_area(inp, out):
    def f(c, cs, i):
        ys = [y for y, _ in c]
        xs = [x for _, x in c]
        a = (max(ys) - min(ys) + 1) * (max(xs) - min(xs) + 1)
        return clamp(a)
    return paint(inp, f)


def color_shifted(inp, out):
    return [[(v % 4) + 1 if v else 0 for v in row] for row in out]


def sizes_capped_at_three(inp, out):
    return paint(inp, lambda c, cs, i: clamp(min(len(c), 3)))


def big_vs_rest(inp, out):
    m = max(len(k) for k in comps(inp))
    return paint(inp, lambda c, cs, i: 1 if len(c) == m else 3)


def only_largest_recolored(inp, out):
    m = max(len(k) for k in comps(inp))
    return paint(inp, lambda c, cs, i: clamp(len(c)) if len(c) == m else 5)


ALTERNATIVES = [
    ("components within two cells of each other are merged into one object", merged_across_gap),
    ("color equals the component's cell count (1 to 4) instead of 5 minus it", color_equals_size),
    ("color is the rank of the size among distinct sizes in the grid, smallest first", rank_ascending),
    ("color is the object index in reading order, cycling 1 to 4", reading_order_index),
    ("two-cell components are left as 5", pairs_left_uncolored),
    ("the largest components are left as 5", largest_left_uncolored),
    ("only the largest components are recolored, the rest stay 5", only_largest_recolored),
    ("size is counted per horizontal run of cells, not per component", horizontal_runs),
    ("size is counted per vertical run of cells, not per component", vertical_runs),
    ("size is the bounding box area, not the cell count", bbox_area),
    ("every output color is off by one (cyclic shift in 1-4)", color_shifted),
    ("sizes above 3 are treated as 3", sizes_capped_at_three),
    ("largest components get 1 and all others get 3", big_vs_rest),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len(set(len(r) for r in g)) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/6e82a1ae.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
