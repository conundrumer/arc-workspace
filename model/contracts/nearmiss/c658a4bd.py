import json
from pathlib import Path


def _rings(out):
    n = len(out)
    return [out[k][k] for k in range((n + 1) // 2)]


def _build(n, cols):
    m = len(cols) - 1
    return [[cols[min(m, min(r, n - 1 - r), c, n - 1 - c)] for c in range(n)]
            for r in range(n)]


def _cells(inp):
    d = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v:
                d.setdefault(v, []).append((r, c))
    return d


def _ext(cells):
    rs = [p[0] for p in cells]
    cs = [p[1] for p in cells]
    return max(rs) - min(rs) + 1, max(cs) - min(cs) + 1


def by_count(inp, out):
    d = _cells(inp)
    cols = sorted(d, key=lambda k: -len(d[k]))
    return _build(len(out), cols)


def by_bbox_area(inp, out):
    d = _cells(inp)
    cols = sorted(d, key=lambda k: -(_ext(d[k])[0] * _ext(d[k])[1]))
    return _build(len(out), cols)


def by_first_seen(inp, out):
    cols = []
    for row in inp:
        for v in row:
            if v and v not in cols:
                cols.append(v)
    return _build(len(out), cols)


def reversed_order(inp, out):
    return _build(len(out), _rings(out)[::-1])


def extra_bg_ring(inp, out):
    n = len(out) + 2
    return _build(n, [0] + _rings(out))


def drop_largest(inp, out):
    return [row[1:-1] for row in out[1:-1]]


def drop_smallest(inp, out):
    cols = _rings(out)[:-1]
    return _build(len(out), cols)


def swap_outer_two(inp, out):
    cols = _rings(out)
    cols[0], cols[1] = cols[1], cols[0]
    return _build(len(out), cols)


def side_twice_count(inp, out):
    n = 2 * len(_cells(inp))
    return _build(n, _rings(out))


def crop_nonbg(inp, out):
    d = _cells(inp)
    ps = [p for v in d.values() for p in v]
    r0 = min(p[0] for p in ps)
    r1 = max(p[0] for p in ps)
    c0 = min(p[1] for p in ps)
    c1 = max(p[1] for p in ps)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def hollow_core(inp, out):
    cols = _rings(out)
    g = _build(len(out), cols)
    n = len(out)
    k = len(cols) - 1
    for r in range(n):
        for c in range(n):
            if min(min(r, n - 1 - r), min(c, n - 1 - c)) == k:
                g[r][c] = 0
    return g


def side_from_min_extent(inp, out):
    # side of each square read from the smaller bbox extent; ring colors by that
    d = _cells(inp)
    cols = sorted(d, key=lambda k: -min(_ext(d[k])))
    return _build(len(out), cols)


def by_color_value(inp, out):
    return _build(len(out), sorted(_cells(inp)))


ALTERNATIVES = [
    ("order rings by visible cell count of each color", by_count),
    ("order rings by color value, smallest value outermost", by_color_value),
    ("order rings by first appearance of the color in row-major scan", by_first_seen),
    ("rings in reverse order: smallest square outermost", reversed_order),
    ("output has an extra outer ring of background", extra_bg_ring),
    ("largest square's ring is missing: outer ring stripped", drop_largest),
    ("smallest square ignored: its ring takes the next larger color", drop_smallest),
    ("two outermost ring colors swapped", swap_outer_two),
    ("output side is twice the square count", side_twice_count),
    ("output is the crop of all non-background cells in the input", crop_nonbg),
    ("innermost square drawn hollow with background", hollow_core),
    ("squares ordered by smaller bounding-box extent", side_from_min_extent),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/c658a4bd.json"))
    train = task["train"]
    print("pairs", len(train))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
