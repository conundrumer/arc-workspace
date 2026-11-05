"""Near-miss readings for ARC task 4938f0c2.

Rule: a 2x2 marker block sits among shapes; each shape is reflected across the
block's centre lines, so copies fill all four quadrants around the block.
"""
import json
from collections import Counter
from pathlib import Path


def _parts(inp):
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    marker = min(cnt, key=lambda k: (cnt[k], k))
    h, w = len(inp), len(inp[0])
    ink = [(r, c) for r in range(h) for c in range(w) if inp[r][c] not in (bg, marker)]
    block = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == marker]
    r0 = min(r for r, _ in block)
    r1 = max(r for r, _ in block)
    c0 = min(c for _, c in block)
    c1 = max(c for _, c in block)
    return bg, marker, ink, (r0, r1, c0, c1)


def _components(cells):
    cells = set(cells)
    comps = []
    for start in sorted(cells):
        if start not in cells:
            continue
        stack, comp = [start], []
        cells.discard(start)
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    n = (r + dr, c + dc)
                    if n in cells:
                        cells.discard(n)
                        stack.append(n)
        comps.append(comp)
    return comps


def _blank(inp, bg, marker, block):
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    r0, r1, c0, c1 = block
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            g[r][c] = marker
    return g


def _put(g, r, c, v):
    if 0 <= r < len(g) and 0 <= c < len(g[0]):
        g[r][c] = v


def _reflect_set(sr, sc, kinds):
    f = {
        "id": lambda r, c: (r, c),
        "h": lambda r, c: (r, sc - c),
        "v": lambda r, c: (sr - r, c),
        "hv": lambda r, c: (sr - r, sc - c),
    }
    return [f[k] for k in kinds]


def _first_component(ink):
    return _components(ink)[0] if ink else []


def _partial(kinds, drop_original=False):
    def fn(inp, out):
        bg, marker, ink, block = _parts(inp)
        r0, r1, c0, c1 = block
        g = _blank(inp, bg, marker, block)
        obj = _first_component(ink)
        for t in _reflect_set(r0 + r1, c0 + c1, kinds):
            for r, c in obj:
                _put(g, *t(r, c), inp[r][c])
        return g
    return fn


def _all_ink(sr_off, sc_off, absolute=None):
    def fn(inp, out):
        bg, marker, ink, block = _parts(inp)
        r0, r1, c0, c1 = block
        sr, sc = r0 + r1 + sr_off, c0 + c1 + sc_off
        if absolute == "grid":
            sr, sc = len(inp) - 1, len(inp[0]) - 1
        if absolute == "first":
            sr, sc = 2 * r0, 2 * c0
        g = [row[:] for row in inp]
        for t in _reflect_set(sr, sc, ["id", "h", "v", "hv"]):
            for r, c in ink:
                _put(g, *t(r, c), inp[r][c])
        return g
    return fn


def rotated(inp, out):
    bg, marker, ink, block = _parts(inp)
    r0, r1, c0, c1 = block
    # doubled centre coordinates keep everything integral
    cr2, cc2 = r0 + r1, c0 + c1
    g = [row[:] for row in inp]
    for r, c in ink:
        dr2, dc2 = 2 * r - cr2, 2 * c - cc2
        for (a, b) in ((dr2, dc2), (dc2, -dr2), (-dr2, -dc2), (-dc2, dr2)):
            nr, nc = (cr2 + a), (cc2 + b)
            if nr % 2 == 0 and nc % 2 == 0:
                _put(g, nr // 2, nc // 2, inp[r][c])
    return g


def copies_in_marker_color(inp, out):
    bg, marker, ink, block = _parts(inp)
    r0, r1, c0, c1 = block
    g = [row[:] for row in inp]
    for t in _reflect_set(r0 + r1, c0 + c1, ["h", "v", "hv"]):
        for r, c in ink:
            _put(g, *t(r, c), marker)
    return g


def solid_boxes(inp, out):
    bg, marker, ink, block = _parts(inp)
    ink_color = inp[ink[0][0]][ink[0][1]]
    cells = [(r, c) for r in range(len(out)) for c in range(len(out[0])) if out[r][c] == ink_color]
    g = [row[:] for row in out]
    for comp in _components(cells):
        rs = [r for r, _ in comp]
        cs = [c for _, c in comp]
        for r in range(min(rs), max(rs) + 1):
            for c in range(min(cs), max(cs) + 1):
                if g[r][c] == bg:
                    g[r][c] = ink_color
    return g


def copies_only(inp, out):
    bg, marker, ink, block = _parts(inp)
    r0, r1, c0, c1 = block
    g = _blank(inp, bg, marker, block)
    obj = _first_component(ink)
    for t in _reflect_set(r0 + r1, c0 + c1, ["h", "v", "hv"]):
        for r, c in obj:
            _put(g, *t(r, c), inp[r][c])
    return g


ALTERNATIVES = [
    ("reflect the first shape across the vertical centre line of the block only (left-right copy)", _partial(["id", "h"])),
    ("reflect the first shape across the horizontal centre line of the block only (up-down copy)", _partial(["id", "v"])),
    ("copy the first shape only into the diagonally opposite quadrant (180 degree turn)", _partial(["id", "hv"])),
    ("copy the first shape left-right and up-down but leave the diagonal quadrant empty", _partial(["id", "h", "v"])),
    ("reflection axes one cell past the block centre (off by one, toward bottom right)", _all_ink(1, 1)),
    ("reflection axes through the first block row and column instead of the block centre", _all_ink(0, 0, "first")),
    ("rotate shapes by 90 degree steps about the block instead of reflecting", rotated),
    ("copies drawn in the block colour instead of the shape colour", copies_in_marker_color),
    ("reflect across the grid centre lines instead of the block", _all_ink(0, 0, "grid")),
    ("copies filled as solid boxes of their bounding box", solid_boxes),
    ("draw the three reflected copies of the first shape and drop the original", copies_only),
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
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/4938f0c2.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            n += _valid(g, p["output"])
        print(f"{n}/{len(pairs)}  {desc}")
