"""Near-miss readings for ARC task 845d6e51.

Rule: a frame (color 5) boxes a legend of colored shapes in a corner. Every
color 3 shape outside the frame takes the color of the legend shape that has
the same form under some rotation or reflection.
"""
import json
from pathlib import Path

QUERY = 3
BG = 0
FRAME = 5


def _frame_box(g):
    cells = [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v == FRAME]
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def _components(g, cells_ok):
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if (r, c) in seen or not cells_ok(r, c):
                continue
            col = g[r][c]
            stack = [(r, c)]
            seen.add((r, c))
            cur = []
            while stack:
                a, b = stack.pop()
                cur.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and (x, y) not in seen and g[x][y] == col and cells_ok(x, y):
                        seen.add((x, y))
                        stack.append((x, y))
            comps.append((col, sorted(cur)))
    return comps


def _parse(inp):
    r0, r1, c0, c1 = _frame_box(inp)

    def inside(r, c):
        return r0 <= r <= r1 and c0 <= c <= c1

    legend = _components(inp, lambda r, c: inside(r, c) and inp[r][c] not in (BG, FRAME))
    queries = _components(inp, lambda r, c: not inside(r, c) and inp[r][c] == QUERY)
    return (r0, r1, c0, c1), legend, [q for _, q in queries]


def _norm(cells):
    mr = min(r for r, _ in cells)
    mc = min(c for _, c in cells)
    return frozenset((r - mr, c - mc) for r, c in cells)


def _rot(cells):
    return _norm([(c, -r) for r, c in cells])


def _flip_h(cells):
    return _norm([(r, -c) for r, c in cells])


def _flip_v(cells):
    return _norm([(-r, c) for r, c in cells])


def _variants(cells, kind):
    s = _norm(cells)
    if kind == "id":
        return {s}
    if kind == "rot":
        out = [s]
        for _ in range(3):
            out.append(_rot(out[-1]))
        return set(out)
    if kind == "half":
        return {s, _rot(_rot(s))}
    if kind == "klein":
        return {s, _flip_h(s), _flip_v(s), _flip_h(_flip_v(s))}
    if kind == "d4":
        rots = _variants(cells, "rot")
        return rots | {_flip_h(x) for x in rots}
    raise ValueError(kind)


def _match_color(q, legend, kind):
    qs = _norm(q)
    hits = [col for col, cells in legend if qs in _variants(cells, kind)]
    return hits[0] if hits else None


def _paint(inp, assign):
    """Copy of inp where each query component gets assign(q) (None keeps 3)."""
    _, legend, queries = _parse(inp)
    g = [row[:] for row in inp]
    for q in queries:
        col = assign(q, legend)
        if col is None:
            continue
        for r, c in q:
            g[r][c] = col
    return g


def _kind_reading(kind):
    def f(inp, out):
        return _paint(inp, lambda q, legend: _match_color(q, legend, kind))
    return f


def first_legend_color(inp, out):
    return _paint(inp, lambda q, legend: legend[0][0])


def shifted_legend_color(inp, out):
    _, legend, queries = _parse(inp)
    cols = sorted({col for col, _ in legend})
    g = [row[:] for row in inp]
    for q in queries:
        true_col = out[q[0][0]][q[0][1]]
        if true_col not in cols:
            return None
        nxt = cols[(cols.index(true_col) + 1) % len(cols)]
        for r, c in q:
            g[r][c] = nxt
    return g


def only_largest_recolored(inp, out):
    _, legend, queries = _parse(inp)
    big = max(queries, key=len)
    g = [row[:] for row in inp]
    for r, c in big:
        g[r][c] = out[r][c]
    return g


def nearest_legend_color(inp, out):
    def assign(q, legend):
        qr = sum(r for r, _ in q) / len(q)
        qc = sum(c for _, c in q) / len(q)
        best = None
        for col, cells in legend:
            lr = sum(r for r, _ in cells) / len(cells)
            lc = sum(c for _, c in cells) / len(cells)
            d = (lr - qr) ** 2 + (lc - qc) ** 2
            if best is None or d < best[0]:
                best = (d, col)
        return best[1]
    return _paint(inp, assign)


def match_by_cell_count(inp, out):
    def assign(q, legend):
        for col, cells in legend:
            if len(cells) == len(q):
                return col
        return None
    return _paint(inp, assign)


def legend_erased(inp, out):
    (r0, r1, c0, c1), _, _ = _parse(inp)
    g = [row[:] for row in out]
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if g[r][c] != FRAME:
                g[r][c] = BG
    return g


def crop_below_frame(inp, out):
    (r0, r1, c0, c1), _, _ = _parse(inp)
    return [row[:] for row in out[r1 + 1:]]


def frame_erased(inp, out):
    return [[BG if v == FRAME else v for v in row] for row in out]


ALTERNATIVES = [
    ("every query shape takes the color of the first legend shape in reading order", first_legend_color),
    ("each query shape takes the next legend color after its correct one", shifted_legend_color),
    ("shapes match the legend only with the same orientation (no rotation or reflection)", _kind_reading("id")),
    ("shapes match the legend under identity and 180 degree turn only", _kind_reading("half")),
    ("shapes match the legend under the flip group only (identity, mirrors, 180 turn), not 90 degree turns", _kind_reading("klein")),
    ("only the largest query shape is recolored", only_largest_recolored),
    ("each query shape takes the color of the nearest legend shape", nearest_legend_color),
    ("shapes match the legend by cell count alone", match_by_cell_count),
    ("correct recoloring but the legend is erased from the output", legend_erased),
    ("correct recoloring but the output is cropped to the rows below the frame", crop_below_frame),
    ("correct recoloring but the frame lines are erased from the output", frame_erased),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/845d6e51.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
