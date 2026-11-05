import json
from collections import Counter
from pathlib import Path

DIAGS = [(1, 1), (1, -1)]
DIRS8 = [(1, 1), (1, -1)]


def _hole_color(inp):
    c = Counter(v for r in inp for v in r)
    return min(c, key=lambda k: (c[k], k))


def _paint_color(inp, out):
    ins = {v for r in inp for v in r}
    for r in out:
        for v in r:
            if v not in ins:
                return v
    return 8


def _runs(inp, dirs=DIAGS):
    """Maximal diagonal runs of hole cells: list of (dir, [cells])."""
    h = _hole_color(inp)
    H, W = len(inp), len(inp[0])
    res = []
    for d in dirs:
        for i in range(H):
            for j in range(W):
                if inp[i][j] != h:
                    continue
                pi, pj = i - d[0], j - d[1]
                if 0 <= pi < H and 0 <= pj < W and inp[pi][pj] == h:
                    continue
                cells = []
                a, b = i, j
                while 0 <= a < H and 0 <= b < W and inp[a][b] == h:
                    cells.append((a, b))
                    a += d[0]
                    b += d[1]
                res.append((d, cells))
    return res


def _center_dist(cells, inp):
    H, W = len(inp), len(inp[0])
    ci, cj = (H - 1) / 2, (W - 1) / 2
    return min(abs(a - ci) + abs(b - cj) for a, b in cells), sum(
        abs(a - ci) + abs(b - cj) for a, b in cells) / len(cells)


def _line_dist(run, inp):
    """Distance from the run's diagonal line to the grid center."""
    H, W = len(inp), len(inp[0])
    d, cells = run
    a, b = cells[0]
    if d == (1, 1):
        return abs((a - b) - (H - W) / 2)
    return abs((a + b) - (H + W - 2) / 2)


def _paint(inp, cells, color, base=None):
    g = [list(r) for r in (base if base is not None else inp)]
    for a, b in cells:
        g[a][b] = color
    return g


def _longest(inp, dirs=DIAGS):
    runs = _runs(inp, dirs)
    if not runs:
        return []
    m = max(len(c) for _, c in runs)
    return [r for r in runs if len(r[1]) == m]


def _best(inp, dirs, key):
    c = _longest(inp, dirs)
    return min(c, key=key) if c else None


def main_diag_only(inp, out):
    r = _best(inp, [(1, 1)], lambda r: _line_dist(r, inp))
    return _paint(inp, r[1], _paint_color(inp, out)) if r else None


def anti_diag_only(inp, out):
    r = _best(inp, [(1, -1)], lambda r: _line_dist(r, inp))
    return _paint(inp, r[1], _paint_color(inp, out)) if r else None


def shortest_run(inp, out):
    runs = [r for r in _runs(inp) if len(r[1]) >= 2]
    if not runs:
        return None
    m = min(len(c) for _, c in runs)
    r = min((r for r in runs if len(r[1]) == m), key=lambda r: _line_dist(r, inp))
    return _paint(inp, r[1], _paint_color(inp, out))


def all_tied(inp, out):
    cs = _longest(inp)
    cells = [x for _, c in cs for x in c]
    return _paint(inp, cells, _paint_color(inp, out)) if cells else None


def tie_farthest(inp, out):
    r = max(_longest(inp), key=lambda r: (_line_dist(r, inp), r[0]))
    return _paint(inp, r[1], _paint_color(inp, out))


def tie_first_scan(inp, out):
    r = _longest(inp)
    r = min(r, key=lambda r: (r[1][0], r[0]))
    return _paint(inp, r[1], _paint_color(inp, out))


def line_count(inp, out):
    """Whole diagonal line with most hole cells, gaps included."""
    h = _hole_color(inp)
    H, W = len(inp), len(inp[0])
    lines = {}
    for i in range(H):
        for j in range(W):
            if inp[i][j] == h:
                lines.setdefault(("m", i - j), []).append((i, j))
                lines.setdefault(("a", i + j), []).append((i, j))
    m = max(len(v) for v in lines.values())
    best = [(k, v) for k, v in lines.items() if len(v) == m]

    def dist(kv):
        k, _ = kv
        return abs(k[1] - ((H - W) / 2 if k[0] == "m" else (H + W - 2) / 2))
    k, cells = min(best, key=lambda kv: (dist(kv), kv[0]))
    return _paint(inp, cells, _paint_color(inp, out))


def horizontal_run(inp, out):
    h = _hole_color(inp)
    best = []
    for i, row in enumerate(inp):
        j = 0
        while j < len(row):
            if row[j] == h:
                k = j
                while k < len(row) and row[k] == h:
                    k += 1
                if k - j > len(best):
                    best = [(i, x) for x in range(j, k)]
                j = k
            else:
                j += 1
    return _paint(inp, best, _paint_color(inp, out)) if best else None


def _true_cells(inp, out):
    pc = _paint_color(inp, out)
    return pc, [(i, j) for i, r in enumerate(out) for j, v in enumerate(r) if v == pc]


def drop_end_cell(inp, out):
    pc, cells = _true_cells(inp, out)
    cells.sort()
    a, b = cells[0]
    g = [list(r) for r in out]
    g[a][b] = inp[a][b]
    return g


def extend_one_past(inp, out):
    pc, cells = _true_cells(inp, out)
    cells.sort()
    if len(cells) < 2:
        return None
    d = (cells[1][0] - cells[0][0], cells[1][1] - cells[0][1])
    a, b = cells[-1][0] + d[0], cells[-1][1] + d[1]
    H, W = len(out), len(out[0])
    if not (0 <= a < H and 0 <= b < W):
        a, b = cells[0][0] - d[0], cells[0][1] - d[1]
    if not (0 <= a < H and 0 <= b < W):
        return None
    g = [list(r) for r in out]
    g[a][b] = pc
    return g


def per_region(inp, out):
    """Longest run painted in each 4-connected hole region."""
    h = _hole_color(inp)
    H, W = len(inp), len(inp[0])
    comp = {}
    n = 0
    for i in range(H):
        for j in range(W):
            if inp[i][j] == h and (i, j) not in comp:
                st = [(i, j)]
                comp[(i, j)] = n
                while st:
                    a, b = st.pop()
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        p = (a + da, b + db)
                        if 0 <= p[0] < H and 0 <= p[1] < W and inp[p[0]][p[1]] == h and p not in comp:
                            comp[p] = n
                            st.append(p)
                n += 1
    runs = _runs(inp)
    pc = _paint_color(inp, out)
    cells = []
    for k in range(n):
        rs = [r for r in runs if comp[r[1][0]] == k]
        m = max(len(c) for _, c in rs)
        top = [r for r in rs if len(r[1]) == m]
        r = min(top, key=lambda r: _line_dist(r, inp))
        cells += r[1]
    return _paint(inp, cells, pc)


def paint_every_hole_diag(inp, out):
    """Every diagonal run of length >= 3 painted."""
    pc = _paint_color(inp, out)
    cells = [x for _, c in _runs(inp) if len(c) >= 3 for x in c]
    return _paint(inp, cells, pc) if cells else None


def paint_whole_hole(inp, out):
    """All hole cells painted."""
    h = _hole_color(inp)
    pc = _paint_color(inp, out)
    return [[pc if v == h else v for v in r] for r in inp]


def _true_dir(inp, out):
    pc, cells = _true_cells(inp, out)
    cells.sort()
    if len(cells) < 2:
        return None
    return (cells[1][0] - cells[0][0], cells[1][1] - cells[0][1])


def second_longest(inp, out):
    runs = sorted(_runs(inp), key=lambda r: (-len(r[1]), _line_dist(r, inp)))
    m = len(runs[0][1])
    rest = [r for r in runs if len(r[1]) < m]
    if not rest:
        return None
    return _paint(inp, rest[0][1], _paint_color(inp, out))


def other_axis_longest(inp, out):
    d = _true_dir(inp, out)
    if d is None:
        return None
    r = _best(inp, [x for x in DIAGS if x != d], lambda r: _line_dist(r, inp))
    return _paint(inp, r[1], _paint_color(inp, out)) if r else None


def both_axes_longest(inp, out):
    cells = []
    for d in DIAGS:
        r = _best(inp, [d], lambda r: _line_dist(r, inp))
        if r:
            cells += r[1]
    return _paint(inp, cells, _paint_color(inp, out)) if cells else None


def central_cell_run(inp, out):
    """Longest run through the hole cell nearest the grid center."""
    H, W = len(inp), len(inp[0])
    runs = _runs(inp)
    cells = {x for _, c in runs for x in c}
    cc = min(cells, key=lambda x: (abs(x[0] - (H - 1) / 2) + abs(x[1] - (W - 1) / 2), x))
    thr = [r for r in runs if cc in r[1]]
    r = max(thr, key=lambda r: len(r[1]))
    return _paint(inp, r[1], _paint_color(inp, out))


ALTERNATIVES = [
    ("only runs along the down-left diagonal compete", anti_diag_only),
    ("the shortest run of length 2 or more is painted", shortest_run),
    ("every run tied for longest is painted", all_tied),
    ("among tied longest runs the one farthest from the center is painted", tie_farthest),
    ("the longest horizontal run is painted instead of a diagonal one", horizontal_run),
    ("the true run is painted without its first cell", drop_end_cell),
    ("the true run is painted and extended one cell past its end", extend_one_past),
    ("every diagonal run of 3 or more cells is painted", paint_every_hole_diag),
    ("the second-longest run is painted", second_longest),
    ("the longest run of the other diagonal axis is painted", other_axis_longest),
    ("the longest run of each diagonal axis is painted", both_axes_longest),
    ("the longest run through the hole cell nearest the center is painted", central_cell_run),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/aa300dc3.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
