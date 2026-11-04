from pathlib import Path
import json, copy


def ink(g):
    return [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v != 0]


def groups(g, mode):
    """mode: 'line' (row or column), 'row', 'col', 'adj8', 'adj4'. Returns list of cell lists."""
    cells = ink(g)
    par = {p: p for p in cells}

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    def union(a, b):
        par[find(a)] = find(b)

    for i, a in enumerate(cells):
        for b in cells[i + 1:]:
            dr, dc = abs(a[0] - b[0]), abs(a[1] - b[1])
            if mode == 'line' and (dr == 0 or dc == 0):
                union(a, b)
            elif mode == 'row' and dr == 0:
                union(a, b)
            elif mode == 'col' and dc == 0:
                union(a, b)
            elif mode == 'adj8' and max(dr, dc) == 1:
                union(a, b)
            elif mode == 'adj4' and dr + dc == 1:
                union(a, b)
    d = {}
    for p in cells:
        d.setdefault(find(p), []).append(p)
    return list(d.values())


def bbox(cs):
    rs = [p[0] for p in cs]
    cc = [p[1] for p in cs]
    return min(rs), min(cc), max(rs), max(cc)


def fill_boxes(inp, boxes, color=2, margin=0, inner=False):
    h, w = len(inp), len(inp[0])
    o = copy.deepcopy(inp)
    for r0, c0, r1, c1 in boxes:
        if inner:
            r0, c0, r1, c1 = r0 + 1, c0 + 1, r1 - 1, c1 - 1
        r0, c0, r1, c1 = r0 - margin, c0 - margin, r1 + margin, c1 + margin
        for r in range(max(r0, 0), min(r1, h - 1) + 1):
            for c in range(max(c0, 0), min(c1, w - 1) + 1):
                if inp[r][c] == 0:
                    o[r][c] = color
    return o


def boxes_of(inp, mode):
    return [bbox(g) for g in groups(inp, mode)]


def adj8(inp, out):
    return fill_boxes(inp, boxes_of(inp, 'adj8'))


def adj4(inp, out):
    return fill_boxes(inp, boxes_of(inp, 'adj4'))


def wrong_color(inp, out):
    return [[4 if v == 2 else v for v in row] for row in out]


def global_box(inp, out):
    return fill_boxes(inp, [bbox(ink(inp))])


def row_only(inp, out):
    return fill_boxes(inp, boxes_of(inp, 'row'))


def col_only(inp, out):
    return fill_boxes(inp, boxes_of(inp, 'col'))


def margin1(inp, out):
    return fill_boxes(inp, boxes_of(inp, 'line'), margin=1)


def inner_only(inp, out):
    return fill_boxes(inp, boxes_of(inp, 'line'), inner=True)


def between_ink_in_row(inp, out):
    o = copy.deepcopy(inp)
    for r0, c0, r1, c1 in boxes_of(inp, 'line'):
        for r in range(r0, r1 + 1):
            cs = [c for c in range(c0, c1 + 1) if inp[r][c] != 0]
            if not cs:
                continue
            for c in range(min(cs), max(cs) + 1):
                if inp[r][c] == 0:
                    o[r][c] = 2
    return o


def rows_full_width(inp, out):
    w = len(inp[0])
    o = copy.deepcopy(inp)
    for r0, c0, r1, c1 in boxes_of(inp, 'line'):
        for r in range(r0, r1 + 1):
            for c in range(w):
                if inp[r][c] == 0:
                    o[r][c] = 2
    return o


def recolor_all_box(inp, out):
    o = copy.deepcopy(inp)
    for r0, c0, r1, c1 in boxes_of(inp, 'line'):
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                o[r][c] = 2
    return o


def largest_only(inp, out):
    gs = groups(inp, 'line')
    g = max(gs, key=len)
    return fill_boxes(inp, [bbox(g)])


def fill_adjacent_only(inp, out):
    o = copy.deepcopy(inp)
    h, w = len(inp), len(inp[0])
    for r in range(h):
        for c in range(w):
            if out[r][c] == 2:
                nb = [(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]
                if not any(0 <= a < h and 0 <= b < w and inp[a][b] != 0 for a, b in nb):
                    o[r][c] = 0
    return o


ALTERNATIVES = [
    ("group ink by 8-neighbour adjacency instead of line sharing", adj8),
    ("group ink by 4-neighbour adjacency instead of line sharing", adj4),
    ("fill color 4 instead of 2", wrong_color),
    ("one bounding box around all ink", global_box),
    ("group ink by shared row only", row_only),
    ("group ink by shared column only", col_only),
    ("fill bounding box grown by one cell on each side", margin1),
    ("fill only the box interior, one cell in from the box edge", inner_only),
    ("fill only background between the first and last ink cell of each box row", between_ink_in_row),
    ("fill background across the full grid width on each box's rows", rows_full_width),
    ("paint the whole box 2, including the ink cells", recolor_all_box),
    ("fill only background cells touching ink orthogonally", fill_adjacent_only),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/8fbca751.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("ERR", desc, e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
