import json
from collections import Counter
from pathlib import Path

MARK = 2
FILL = 4


def _cells(inp, color):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == color]


def _clusters(cells, reach, metric="cheb"):
    """Group cells; two cells link when their distance is within reach."""
    left = set(cells)
    groups = []
    while left:
        seed = left.pop()
        grp, stack = [seed], [seed]
        while stack:
            r, c = stack.pop()
            for q in list(left):
                dr, dc = abs(q[0] - r), abs(q[1] - c)
                d = max(dr, dc) if metric == "cheb" else dr + dc
                if d <= reach:
                    left.discard(q)
                    grp.append(q)
                    stack.append(q)
        groups.append(grp)
    return groups


def _box(grp):
    rs = [p[0] for p in grp]
    cs = [p[1] for p in grp]
    return min(rs), min(cs), max(rs), max(cs)


def _paint(inp, boxes, color=FILL, mark=MARK, keep=None, grow=0):
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for r0, c0, r1, c1 in boxes:
        r0, c0, r1, c1 = r0 - grow, c0 - grow, r1 + grow, c1 + grow
        if r1 < r0 or c1 < c0:
            continue
        for r in range(max(r0, 0), min(r1, h - 1) + 1):
            for c in range(max(c0, 0), min(c1, w - 1) + 1):
                if inp[r][c] == mark:
                    continue
                if keep is not None and keep(inp[r][c]):
                    continue
                g[r][c] = color
    return g


def _boxes(inp, reach=2, metric="cheb"):
    return [_box(g) for g in _clusters(_cells(inp, MARK), reach, metric)]


def _changed(inp, out):
    return [(r, c) for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] != out[r][c]]


def wrong_fill_color(inp, out):
    return [[6 if v == FILL else v for v in row] for row in out]


def mark_also_filled(inp, out):
    return _paint(inp, _boxes(inp), mark=-1)


def adjacent_only(inp, out):
    return _paint(inp, _boxes(inp, 1))


def gap_two(inp, out):
    return _paint(inp, _boxes(inp, 3))


def orthogonal_only(inp, out):
    return _paint(inp, _boxes(inp, 1, "man"))


def one_global_box(inp, out):
    return _paint(inp, [_box(_cells(inp, MARK))])


def interior_only(inp, out):
    return _paint(inp, _boxes(inp), grow=-1)


def margin_one(inp, out):
    return _paint(inp, _boxes(inp), grow=1)


def largest_cluster_only(inp, out):
    groups = _clusters(_cells(inp, MARK), 2)
    if len(groups) < 2:
        return None
    return _paint(inp, [_box(max(groups, key=len))])


def smallest_cluster_skipped(inp, out):
    groups = _clusters(_cells(inp, MARK), 2)
    if len(groups) < 2:
        return None
    groups.sort(key=len)
    return _paint(inp, [_box(g) for g in groups[1:]])


def spare_most_common_color(inp, out):
    ch = _changed(inp, out)
    common = Counter(inp[r][c] for r, c in ch).most_common(1)[0][0]
    return _paint(inp, _boxes(inp), keep=lambda v: v == common)


def full_width_rows(inp, out):
    w = len(inp[0])
    return _paint(inp, [(r0, 0, r1, w - 1) for r0, _, r1, _ in _boxes(inp)])


def fill_with_background(inp, out):
    bg = Counter(v for row in inp for v in row).most_common(1)[0][0]
    return _paint(inp, _boxes(inp), color=bg) if bg != MARK else None


ALTERNATIVES = [
    ("fill color 6 instead of 4", wrong_fill_color),
    ("mark cells inside the box are repainted too", mark_also_filled),
    ("clusters link only through touching cells (no gap of one)", adjacent_only),
    ("clusters link across gaps of up to two cells", gap_two),
    ("clusters link only through edge-adjacent cells", orthogonal_only),
    ("one box around all mark cells", one_global_box),
    ("box shrunk by one cell on each side", interior_only),
    ("box grown by one cell on each side", margin_one),
    ("only the largest cluster's box is filled", largest_cluster_only),
    ("the smallest cluster's box is left unfilled", smallest_cluster_skipped),
    ("fill spares cells of the most common color in the box", spare_most_common_color),
    ("fill spans the full grid width over the rows of each box", full_width_rows),
]


def _valid(g, out):
    if g is None:
        return False
    if not g or not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/36fdfd69.json").read_text())
    pairs = task["train"]
    for p in pairs:
        assert _paint(p["input"], _boxes(p["input"])) == p["output"], "base rule mismatch"
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
