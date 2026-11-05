import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _parse(inp, out):
    """Return background, centers {color: (r, c)}, satellites [(r, c, color, center_color)]."""
    bg = _bg(inp)
    cnt = Counter(v for r in inp for v in r)
    h, w = len(inp), len(inp[0])
    centers = {}
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v != bg and cnt[v] == 1:
                centers[v] = (r, c)
    pair = {}
    for cc, (r, c) in centers.items():
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            rr, cc2 = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc2 < w and out[rr][cc2] != bg:
                pair[out[rr][cc2]] = cc
    sats = []
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v != bg and v not in centers and v in pair:
                sats.append((r, c, v, pair[v]))
    return bg, centers, sats


def _dir(sat, ctr):
    dr, dc = sat[0] - ctr[0], sat[1] - ctr[1]
    if dr == 0 and dc != 0:
        return (0, 1 if dc > 0 else -1)
    if dc == 0 and dr != 0:
        return (1 if dr > 0 else -1, 0)
    return None


def _build(inp, out, place, keep_centers=True, extra=None, keep=None):
    bg, centers, sats = _parse(inp, out)
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    if keep_centers:
        for cc, (r, c) in centers.items():
            g[r][c] = cc
    for s in sats:
        d = _dir(s, centers[s[3]])
        if d is None:
            continue
        res = place(s, centers[s[3]], d, centers)
        if res is None:
            continue
        r, c, v = res
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = v
    return g


def _std(s, ctr, d, centers, gap=0):
    return (ctr[0] + d[0] * (1 + gap), ctr[1] + d[1] * (1 + gap), s[2])


def base(inp, out):
    return _build(inp, out, _std)


def gap_one(inp, out):
    return _build(inp, out, lambda s, c, d, cs: _std(s, c, d, cs, 1))


def opposite_side(inp, out):
    return _build(inp, out, lambda s, c, d, cs: (c[0] - d[0], c[1] - d[1], s[2]))


def diagonal(inp, out):
    return _build(inp, out, lambda s, c, d, cs: (c[0] + d[0] + d[1], c[1] + d[1] - d[0], s[2]))


def recolor_to_center(inp, out):
    bg, centers, sats = _parse(inp, out)
    return _build(inp, out, lambda s, c, d, cs: (c[0] + d[0], c[1] + d[1], s[3]))


def horizontal_only(inp, out):
    def place(s, c, d, cs):
        if d[0] == 0:
            return _std(s, c, d, cs)
        return (s[0], s[1], s[2])
    return _build(inp, out, place)


def vertical_only(inp, out):
    def place(s, c, d, cs):
        if d[1] == 0:
            return _std(s, c, d, cs)
        return (s[0], s[1], s[2])
    return _build(inp, out, place)


def copy_not_move(inp, out):
    bg = _bg(inp)
    _, centers, sats = _parse(inp, out)
    g = [row[:] for row in out]
    for r, c, v, _cc in sats:
        if g[r][c] == bg:
            g[r][c] = v
    return g


def centers_removed(inp, out):
    bg, centers, _ = _parse(inp, out)
    g = [row[:] for row in out]
    for r, c in centers.values():
        g[r][c] = bg
    return g


def nearest_only(inp, out):
    bg, centers, sats = _parse(inp, out)
    best = {}
    for s in sats:
        ctr = centers[s[3]]
        d = abs(s[0] - ctr[0]) + abs(s[1] - ctr[1])
        if s[3] not in best or d < best[s[3]][0]:
            best[s[3]] = (d, s)
    keep = {v[1][:2] for v in best.values()}
    g = [[bg] * len(inp[0]) for _ in inp]
    for cc, (r, c) in centers.items():
        g[r][c] = cc
    for s in sats:
        if s[:2] not in keep:
            continue
        ctr = centers[s[3]]
        d = _dir(s, ctr)
        if d is None:
            continue
        g[ctr[0] + d[0]][ctr[1] + d[1]] = s[2]
    return g


def cropped_to_content(inp, out):
    bg = _bg(out)
    rows = [i for i, r in enumerate(out) if any(v != bg for v in r)]
    cols = [j for j in range(len(out[0])) if any(r[j] != bg for r in out)]
    if not rows:
        return None
    return [r[cols[0]:cols[-1] + 1] for r in out[rows[0]:rows[-1] + 1]]


def unchanged_input(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("Each satellite stops one empty cell away from its center instead of next to it", gap_one),
    ("Each satellite lands on the side of its center opposite to the side it started on", opposite_side),
    ("Each satellite lands on a diagonal neighbor of its center instead of an orthogonal one", diagonal),
    ("Each satellite takes the center's color when it moves next to the center", recolor_to_center),
    ("Only satellites in the same row as their center move; those in the center's column stay", horizontal_only),
    ("Only satellites in the same column as their center move; those in the center's row stay", vertical_only),
    ("Satellites are copied next to the center and also stay at their original cells", copy_not_move),
    ("The center cell is cleared once its satellites have gathered", centers_removed),
    ("Only the nearest satellite of each center moves; the others are dropped", nearest_only),
    ("The output is cropped to the bounding box of the gathered shapes", cropped_to_content),
    ("The grid is left as in the input", unchanged_input),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/ae3edfdc.json'))
    train = task["train"]
    for p in train:
        assert base(p["input"], p["output"]) == p["output"], "base solver mismatch"
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                  and all(type(v) is int and 0 <= v <= 9 for r in g for v in r) and g != p["output"])
            n += ok
        print(f"{n}/{len(train)}  {desc}")
