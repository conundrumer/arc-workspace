"""Near-miss rules for 6855a6e4.

True rule: each mover cell (the color that moves) casts rays in the four
directions. A ray halts on the first mirror cell. Each mover cell is reflected
across that mirror cell. The original movers are erased.
"""
import json
from collections import Counter
from pathlib import Path

DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _colors(inp, out):
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    mover = None
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v != bg and out[r][c] != v:
                mover = v
    mirror = None
    for row in inp:
        for v in row:
            if v != bg and v != mover:
                mirror = v
    return bg, mover, mirror


def _cast(inp, r, c, d, mirror, last=False):
    h, w = len(inp), len(inp[0])
    hit = None
    rr, cc = r + d[0], c + d[1]
    while 0 <= rr < h and 0 <= cc < w:
        if inp[rr][cc] == mirror:
            hit = (rr, cc)
            if not last:
                return hit
        rr += d[0]
        cc += d[1]
    return hit


def _render(inp, out, erase=True, dirs=DIRS, last=False, shift=0,
            paint=None, nearest_only=False):
    bg, mover, mirror = _colors(inp, out)
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    if erase:
        for r in range(h):
            for c in range(w):
                if inp[r][c] == mover:
                    g[r][c] = bg
    hits = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != mover:
                continue
            for d in dirs:
                hit = _cast(inp, r, c, d, mirror, last)
                if hit is None:
                    continue
                dist = abs(hit[0] - r) + abs(hit[1] - c)
                hits.append((dist, d, r, c, hit))
    if nearest_only:
        best = {}
        for dist, d, r, c, hit in hits:
            best[d] = min(best.get(d, dist), dist)
        hits = [x for x in hits if x[0] == best[x[1]]]
    for dist, d, r, c, hit in hits:
        nr = 2 * hit[0] - r + shift * d[0]
        nc = 2 * hit[1] - c + shift * d[1]
        if 0 <= nr < h and 0 <= nc < w:
            g[nr][nc] = mover if paint is None else paint(mover, mirror)
    return g


def keep_originals(inp, out):
    return _render(inp, out, erase=False)


def no_reflection(inp, out):
    return _render(inp, out, dirs=[])


def image_one_closer(inp, out):
    return _render(inp, out, shift=-1)


def image_one_farther(inp, out):
    return _render(inp, out, shift=1)


def vertical_rays_only(inp, out):
    return _render(inp, out, dirs=[(-1, 0), (1, 0)])


def horizontal_rays_only(inp, out):
    return _render(inp, out, dirs=[(0, -1), (0, 1)])


def last_mirror_cell(inp, out):
    return _render(inp, out, last=True)


def paint_mirror_color(inp, out):
    return _render(inp, out, paint=lambda m, k: k)


def nearest_cells_only(inp, out):
    return _render(inp, out, nearest_only=True)


def point_reflect_in_frame(inp, out):
    bg, mover, mirror = _colors(inp, out)
    h, w = len(inp), len(inp[0])
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == mirror]
    r2 = min(r for r, _ in cells) + max(r for r, _ in cells)
    c2 = min(c for _, c in cells) + max(c for _, c in cells)
    g = [[bg if v == mover else v for v in row] for row in inp]
    for r in range(h):
        for c in range(w):
            if inp[r][c] == mover:
                nr, nc = r2 - r, c2 - c
                if 0 <= nr < h and 0 <= nc < w:
                    g[nr][nc] = mover
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("movers are reflected but the original movers are not erased", keep_originals),
    ("movers are erased and no reflection is drawn", no_reflection),
    ("image is placed one cell closer to the mirror than the true reflection", image_one_closer),
    ("image is placed one cell farther from the mirror than the true reflection", image_one_farther),
    ("only vertical rays are cast", vertical_rays_only),
    ("only horizontal rays are cast", horizontal_rays_only),
    ("rays pass the first mirror cell and halt on the last one", last_mirror_cell),
    ("image is painted in the mirror color instead of the mover color", paint_mirror_color),
    ("only the mover cells nearest the mirror are reflected", nearest_cells_only),
    ("movers are point-reflected through the center of the mirror frame", point_reflect_in_frame),
    ("output equals the input", unchanged),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(row, list) and len(row) == len(g[0]) for row in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for row in g for v in row):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/6855a6e4.json").read_text())
    pairs = task["train"]
    for p in pairs:
        assert _render(p["input"], p["output"]) == p["output"], "true rule check failed"
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
