"""Near-miss rules for 92e50de0.

Rule: dividers cut the grid into 3x3 tiles (period 4). The ink in one tile is
copied to every second tile in each direction (same tile-index parity as the
source), at the same place inside the tile.
"""
import json
from collections import Counter
from pathlib import Path


def _info(inp):
    h, w = len(inp), len(inp[0])
    flat = [v for row in inp for v in row]
    bg = Counter(flat).most_common(1)[0][0]
    drows = [r for r in range(h) if len(set(inp[r])) == 1 and inp[r][0] != bg]
    dcols = [c for c in range(w)
             if len({inp[r][c] for r in range(h)}) == 1 and inp[0][c] != bg]
    d = inp[drows[0]][0]
    P = drows[1] - drows[0]
    r0 = drows[0] + 1
    c0 = dcols[0] + 1
    ink = []
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v != bg and v != d and (r - r0) % P != P - 1 and (c - c0) % P != P - 1:
                ink.append((r, c, v))
    return h, w, bg, d, P, r0, c0, ink


def _paint(inp, keep, shift=(0, 0), tf=None):
    """Start from inp; copy the ink to each tile (tr, tc) with keep(tr, tc, sr, sc)."""
    h, w, bg, d, P, r0, c0, ink = _info(inp)
    g = [row[:] for row in inp]
    sr, sc = (ink[0][0] - r0) // P, (ink[0][1] - c0) // P
    for tr in range(-2, h // P + 3):
        for tc in range(-2, w // P + 3):
            if not keep(tr, tc, sr, sc):
                continue
            for r, c, v in ink:
                pr, pc = (r - r0) % P, (c - c0) % P
                if tf is not None:
                    if (tr, tc) == (sr, sc):
                        pass
                    else:
                        pr, pc = tf(pr, pc)
                rr = r0 + tr * P + pr + shift[0]
                cc = c0 + tc * P + pc + shift[1]
                if (tr, tc) == (sr, sc):
                    rr, cc = r, c
                if 0 <= rr < h and 0 <= cc < w:
                    if (rr - r0) % P != P - 1 and (cc - c0) % P != P - 1:
                        g[rr][cc] = v
    return g


def _true(tr, tc, sr, sc):
    return (tr - sr) % 2 == 0 and (tc - sc) % 2 == 0


def _every_tile(inp, out):
    return _paint(inp, lambda tr, tc, sr, sc: True)


def _same_row(inp, out):
    return _paint(inp, lambda tr, tc, sr, sc: _true(tr, tc, sr, sc) and tr == sr)


def _same_col(inp, out):
    return _paint(inp, lambda tr, tc, sr, sc: _true(tr, tc, sr, sc) and tc == sc)


def _checker(inp, out):
    return _paint(inp, lambda tr, tc, sr, sc: (tr + tc - sr - sc) % 2 == 0)


def _offset_copies(inp, out):
    return _paint(inp, lambda tr, tc, sr, sc: _true(tr, tc, sr, sc), shift=(0, 1))


def _forward_only(inp, out):
    return _paint(inp, lambda tr, tc, sr, sc: _true(tr, tc, sr, sc) and tr >= sr and tc >= sc)


def _flip_copies(inp, out):
    g = _paint(inp, lambda tr, tc, sr, sc: _true(tr, tc, sr, sc), tf=lambda pr, pc: (pr, 2 - pc))
    return g if g != out else None


def _cross(inp, out):
    return _paint(inp, lambda tr, tc, sr, sc: _true(tr, tc, sr, sc) and (tr == sr or tc == sc))


def _period_three(inp, out):
    h, w, bg, d, P, r0, c0, ink = _info(inp)
    g = [row[:] for row in inp]
    for k in range(-h // 3 - 1, h // 3 + 2):
        for l in range(-w // 3 - 1, w // 3 + 2):
            for r, c, v in ink:
                rr, cc = r + 3 * k, c + 3 * l
                if 0 <= rr < h and 0 <= cc < w:
                    if (rr - r0) % P != P - 1 and (cc - c0) % P != P - 1:
                        g[rr][cc] = v
    return g


def _recolor_copies(inp, out):
    d = _info(inp)[3]
    return [[d if out[r][c] != inp[r][c] else out[r][c] for c in range(len(out[0]))]
            for r in range(len(out))]


def _neighbours(inp, out):
    return _paint(inp, lambda tr, tc, sr, sc: _true(tr, tc, sr, sc) and abs(tr - sr) <= 2 and abs(tc - sc) <= 2)


def _unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("copy into every tile, not every second tile", _every_tile),
    ("copy only along the source tile's row of tiles", _same_row),
    ("copy only along the source tile's column of tiles", _same_col),
    ("copy into every other tile, in checkerboard order", _checker),
    ("each copy lands one column to the right of its tile place", _offset_copies),
    ("copy only to tiles right of and below the source, not left or above", _forward_only),
    ("copies are mirrored left-right inside their tile", _flip_copies),
    ("copy along the source tile's row and column only", _cross),
    ("copy with period 3 (tile size) ignoring the divider width", _period_three),
    ("copies are drawn in the divider color", _recolor_copies),
    ("copy only into the nearest copy places around the source tile", _neighbours),
    ("no copying: output equals input", _unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/92e50de0.json').read_text())
    pairs = task["train"]
    # sanity: the full copy rule reproduces the true output
    for p in pairs:
        assert _paint(p["input"], _true) == p["output"]
    print("task 92e50de0:", len(pairs), "pairs,", len(ALTERNATIVES), "readings")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
