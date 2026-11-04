from pathlib import Path
import json
from collections import Counter

D4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _counts(g):
    return Counter(c for r in g for c in r)


def _center(g):
    cnt = _counts(g)
    return min(cnt, key=lambda c: (cnt[c], c))


def _bg(g):
    cnt = _counts(g)
    return max(cnt, key=lambda c: (cnt[c], -c))


def _pluses(g, offs=D4, center=None):
    """List of (r, c, color) for cells of the center color whose offs cells share one color."""
    h, w = len(g), len(g[0])
    cc = _center(g) if center is None else center
    res = []
    for r in range(h):
        for c in range(w):
            if g[r][c] != cc:
                continue
            vals = []
            for dr, dc in offs:
                rr, cc2 = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc2 < w:
                    vals.append(g[rr][cc2])
                else:
                    vals = None
                    break
            if vals and len(set(vals)) == 1:
                res.append((r, c, vals[0]))
    return res


def _one(col):
    return [[col]]


def _wrap(f):
    def g(inp, out):
        res = f(inp, out)
        return res
    return g


def least_common_arm(inp, out):
    cnt = Counter(p[2] for p in _pluses(inp))
    m = min(cnt.values())
    return _one(min(c for c in cnt if cnt[c] == m))


def center_color(inp, out):
    return _one(_center(inp))


def background_color(inp, out):
    return _one(_bg(inp))


def most_common_nonbg_cell(inp, out):
    cnt = _counts(inp)
    bg, cen = _bg(inp), _center(inp)
    cand = {c: n for c, n in cnt.items() if c not in (bg, cen)}
    return _one(max(cand, key=lambda c: (cand[c], -c)))


def second_most_common_arm(inp, out):
    cnt = Counter(p[2] for p in _pluses(inp))
    order = sorted(cnt, key=lambda c: (-cnt[c], c))
    if len(order) < 2:
        return None
    return _one(order[1])


def first_plus(inp, out):
    p = sorted(_pluses(inp))
    return _one(p[0][2])


def last_plus(inp, out):
    p = sorted(_pluses(inp))
    return _one(p[-1][2])


def plus_crop_3x3(inp, out):
    cnt = Counter(p[2] for p in _pluses(inp))
    col = max(cnt, key=lambda c: (cnt[c], -c))
    cen = _center(inp)
    return [
        [0 if (i, j) in ((0, 0), (0, 2), (2, 0), (2, 2)) else (cen if (i, j) == (1, 1) else col)
         for j in range(3)] for i in range(3)]


def right_size_off_by_one(inp, out):
    v = out[0][0]
    return [[v, v], [v, v]]


def diagonal_arms(inp, out):
    ps = _pluses(inp, DG)
    if not ps:
        return None
    cnt = Counter(p[2] for p in ps)
    return _one(max(cnt, key=lambda c: (cnt[c], -c)))


def by_cell_count_not_plus_count(inp, out):
    # counts every cell of the arm colors, not only arm cells of pluses
    arm = {p[2] for p in _pluses(inp)}
    cnt = _counts(inp)
    return _one(max(arm, key=lambda c: (cnt[c], -c)))


def any_center_color_plus(inp, out):
    # centers: any non-bg cell, not only the rarest color; pick most common ring color
    bg = _bg(inp)
    cnt = Counter()
    h, w = len(inp), len(inp[0])
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            vals = {inp[r + dr][c + dc] for dr, dc in D4}
            if len(vals) == 1 and inp[r][c] != list(vals)[0]:
                cnt[list(vals)[0]] += 1
    if not cnt:
        return None
    # exclude nothing: includes ring of background/halo colors
    return _one(max(cnt, key=lambda c: (cnt[c], -c)))


ALTERNATIVES = [
    ("least common arm color among the pluses", least_common_arm),
    ("output the center color of the pluses", center_color),
    ("output the grid background (most common) color", background_color),
    ("most common non-background, non-center color over all cells", most_common_nonbg_cell),
    ("second most common arm color", second_most_common_arm),
    ("arm color of the first plus in reading order", first_plus),
    ("arm color of the last plus in reading order", last_plus),
    ("3x3 plus shape crop instead of one cell", plus_crop_3x3),
    ("correct color in a 2x2 output (off-by-one size)", right_size_off_by_one),
    ("pluses made from diagonal neighbors instead of orthogonal", diagonal_arms),
    ("rank arm colors by total cell count in the grid, not plus count", by_cell_count_not_plus_count),
    ("any cell whose four neighbors agree counts as a plus center (halo included)", any_center_color_plus),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/642d658d.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  ERR", desc, repr(e))
                g = None
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
