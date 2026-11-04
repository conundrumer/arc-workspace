from pathlib import Path
import json
from collections import deque

N4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
N8 = N4 + [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def flood(inp, passable, nbrs=N4, edges=("t", "b", "l", "r")):
    """Cells reachable from the chosen border edges through passable cells."""
    h, w = len(inp), len(inp[0])
    seen = set()
    q = deque()
    for r in range(h):
        for c in range(w):
            on = ((r == 0 and "t" in edges) or (r == h - 1 and "b" in edges)
                  or (c == 0 and "l" in edges) or (c == w - 1 and "r" in edges))
            if on and passable(inp[r][c]):
                seen.add((r, c))
                q.append((r, c))
    while q:
        r, c = q.popleft()
        for dr, dc in nbrs:
            a, b = r + dr, c + dc
            if 0 <= a < h and 0 <= b < w and (a, b) not in seen and passable(inp[a][b]):
                seen.add((a, b))
                q.append((a, b))
    return seen


def paint(inp, reached, out_col=2, in_col=5, bg=0):
    return [[(out_col if (r, c) in reached else in_col) if v == bg else v
             for c, v in enumerate(row)] for r, row in enumerate(inp)]


def diag_leak(inp, out):
    return paint(inp, flood(inp, lambda v: v == 0, N8))


def swapped(inp, out):
    return paint(inp, flood(inp, lambda v: v == 0), out_col=5, in_col=2)


def top_left_only(inp, out):
    return paint(inp, flood(inp, lambda v: v == 0, edges=("t", "l")))


def top_bottom_only(inp, out):
    return paint(inp, flood(inp, lambda v: v == 0, edges=("t", "b")))


def all_two(inp, out):
    return [[2 if v == 0 else v for v in row] for row in inp]


def all_five(inp, out):
    return [[5 if v == 0 else v for v in row] for row in inp]


def ones_do_not_wall(inp, out):
    # flood passes through 0 and 1; only 3 walls
    reached = flood(inp, lambda v: v != 3)
    return paint(inp, reached)


def threes_do_not_wall(inp, out):
    reached = flood(inp, lambda v: v != 1)
    return paint(inp, reached)


def _components(inp, reached):
    h, w = len(inp), len(inp[0])
    seen, comps = set(), []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 and (r, c) not in reached and (r, c) not in seen:
                comp, q = [], deque([(r, c)])
                seen.add((r, c))
                while q:
                    a, b = q.popleft()
                    comp.append((a, b))
                    for dr, dc in N4:
                        x, y = a + dr, c * 0 + b + dc
                        if (0 <= x < h and 0 <= y < w and inp[x][y] == 0
                                and (x, y) not in reached and (x, y) not in seen):
                            seen.add((x, y))
                            q.append((x, y))
                comps.append(comp)
    return comps


def largest_enclosed_only(inp, out):
    reached = flood(inp, lambda v: v == 0)
    comps = _components(inp, reached)
    if not comps:
        return None
    big = max(comps, key=len)
    g = paint(inp, reached, in_col=2)
    for r, c in big:
        g[r][c] = 5
    return g


def min_size_two(inp, out):
    reached = flood(inp, lambda v: v == 0)
    g = paint(inp, reached, in_col=2)
    for comp in _components(inp, reached):
        if len(comp) >= 2:
            for r, c in comp:
                g[r][c] = 5
    return g


def drop_border(inp, out):
    return [row[1:-1] for row in out[1:-1]]


def row_col_bracketed(inp, out):
    # enclosed = 0 cell with a non-zero cell somewhere on both sides in its row
    # and on both sides in its column
    h, w = len(inp), len(inp[0])
    g = []
    for r in range(h):
        row = []
        for c in range(w):
            v = inp[r][c]
            if v != 0:
                row.append(v)
                continue
            rowv = inp[r]
            colv = [inp[i][c] for i in range(h)]
            ok = (any(x != 0 for x in rowv[:c]) and any(x != 0 for x in rowv[c + 1:])
                  and any(x != 0 for x in colv[:r]) and any(x != 0 for x in colv[r + 1:]))
            row.append(5 if ok else 2)
        g.append(row)
    return g


ALTERNATIVES = [
    ("flood from the border also leaks through diagonal contact (8-connectivity)", diag_leak),
    ("outside and enclosed fill colors swapped (outside 5, enclosed 2)", swapped),
    ("outside flood seeded only from the top and left edges", top_left_only),
    ("outside flood seeded only from the top and bottom edges", top_bottom_only),
    ("every 0 cell becomes 2, enclosed regions never marked", all_two),
    ("every 0 cell becomes 5", all_five),
    ("only color 3 walls the flood; color 1 cells let it pass", ones_do_not_wall),
    ("only color 1 walls the flood; color 3 cells let it pass", threes_do_not_wall),
    ("only the largest enclosed region gets 5, other enclosed regions get 2", largest_enclosed_only),
    ("enclosed regions of size 1 count as outside (only size >= 2 gets 5)", min_size_two),
    ("output cropped by one cell on every side", drop_border),
    ("enclosed means a non-zero cell exists on both sides in the row and in the column", row_col_bracketed),
]


def valid(g, true):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != true


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/84db8fc4.json')))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = sum(valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(n, desc)
    # sanity: the correct rule reproduces the true output
    ok = all(paint(p["input"], flood(p["input"], lambda v: v == 0)) == p["output"] for p in pairs)
    print("correct rule matches:", ok)
