import json
from collections import Counter
from pathlib import Path


def _frame(g):
    """Return (color, r0, r1, c0, c1) of the rectangular outline, or None."""
    h, w = len(g), len(g[0])
    best = None
    for c in {v for row in g for v in row}:
        cells = [(r, k) for r in range(h) for k in range(w) if g[r][k] == c]
        r0 = min(r for r, _ in cells); r1 = max(r for r, _ in cells)
        c0 = min(k for _, k in cells); c1 = max(k for _, k in cells)
        if r1 - r0 < 2 or c1 - c0 < 2 or (r1 - r0 + 1) * (c1 - c0 + 1) >= h * w:
            continue
        ok = all(g[r][k] == c
                 for r in range(r0, r1 + 1) for k in range(c0, c1 + 1)
                 if r in (r0, r1) or k in (c0, c1))
        if ok:
            area = (r1 - r0 + 1) * (c1 - c0 + 1)
            if best is None or area > best[0]:
                best = (area, c, r0, r1, c0, c1)
    return best[1:] if best else None


def _inks(g, f, region):
    fc, r0, r1, c0, c1 = f
    cnt = Counter(g[r][k] for r, k in region if g[r][k] not in (0, fc))
    return cnt


def _interior(f, shrink=0, grow=0):
    fc, r0, r1, c0, c1 = f
    d = 1 + shrink - grow
    return [(r, k) for r in range(r0 + d, r1 - d + 1) for k in range(c0 + d, c1 - d + 1)]


def _swap_region(g, f, region, keep=lambda r, k: True):
    fc = f[0]
    inks = sorted(_inks(g, f, region))
    if len(inks) != 2:
        return None
    a, b = inks
    o = [row[:] for row in g]
    for r, k in region:
        if keep(r, k):
            if g[r][k] == a:
                o[r][k] = b
            elif g[r][k] == b:
                o[r][k] = a
    return o


def _setup(inp):
    f = _frame(inp)
    if not f:
        return None
    return f


def swap_whole_grid(inp, out):
    f = _setup(inp)
    if not f:
        return None
    region = [(r, k) for r in range(len(inp)) for k in range(len(inp[0]))]
    return _swap_region(inp, f, region)


def swap_outside_only(inp, out):
    f = _setup(inp)
    if not f:
        return None
    fc, r0, r1, c0, c1 = f
    region = [(r, k) for r in range(len(inp)) for k in range(len(inp[0]))
              if not (r0 <= r <= r1 and c0 <= k <= c1)]
    o = [row[:] for row in inp]
    inks = sorted(_inks(inp, f, [(r, k) for r in range(len(inp)) for k in range(len(inp[0]))]))
    if len(inks) != 2:
        return None
    a, b = inks
    for r, k in region:
        if inp[r][k] == a:
            o[r][k] = b
        elif inp[r][k] == b:
            o[r][k] = a
    return o


def swap_inner_ring_shrunk(inp, out):
    f = _setup(inp)
    if not f:
        return None
    return _swap_region(inp, f, _interior(f, shrink=1))


def swap_only_ring(inp, out):
    f = _setup(inp)
    if not f:
        return None
    fc, r0, r1, c0, c1 = f
    inner = set(_interior(f, shrink=1))
    region = _interior(f)
    o = _swap_region(inp, f, region, keep=lambda r, k: (r, k) not in inner)
    return o


def swap_top_half(inp, out):
    f = _setup(inp)
    if not f:
        return None
    fc, r0, r1, c0, c1 = f
    mid = (r0 + r1) / 2
    return _swap_region(inp, f, _interior(f), keep=lambda r, k: r < mid)


def swap_left_half(inp, out):
    f = _setup(inp)
    if not f:
        return None
    fc, r0, r1, c0, c1 = f
    mid = (c0 + c1) / 2
    return _swap_region(inp, f, _interior(f), keep=lambda r, k: k < mid)


def swap_includes_frame_cells(inp, out):
    """Region is the full bounding box, so the frame takes part in the swap."""
    f = _setup(inp)
    if not f:
        return None
    fc, r0, r1, c0, c1 = f
    region = [(r, k) for r in range(r0, r1 + 1) for k in range(c0, c1 + 1)]
    o = [row[:] for row in inp]
    inks = sorted(_inks(inp, f, region))
    if len(inks) != 2:
        return None
    a, b = inks
    # frame trades with the first ink color
    for r, k in region:
        v = inp[r][k]
        if v == a:
            o[r][k] = fc
        elif v == fc:
            o[r][k] = a
    return o


def all_ink_to_majority(inp, out):
    f = _setup(inp)
    if not f:
        return None
    region = _interior(f)
    cnt = _inks(inp, f, region)
    if len(cnt) != 2:
        return None
    maj = cnt.most_common(1)[0][0]
    o = [row[:] for row in inp]
    for r, k in region:
        if inp[r][k] != 0:
            o[r][k] = maj
    return o


def ink_trades_with_background(inp, out):
    """Only the less frequent ink color trades with the background 0."""
    f = _setup(inp)
    if not f:
        return None
    region = _interior(f)
    cnt = _inks(inp, f, region)
    if len(cnt) != 2:
        return None
    mn = cnt.most_common()[-1][0]
    o = [row[:] for row in inp]
    for r, k in region:
        if inp[r][k] == mn:
            o[r][k] = 0
        elif inp[r][k] == 0:
            o[r][k] = mn
    return o


def mirror_interior_horizontally(inp, out):
    f = _setup(inp)
    if not f:
        return None
    fc, r0, r1, c0, c1 = f
    o = [row[:] for row in inp]
    for r in range(r0 + 1, r1):
        seg = inp[r][c0 + 1:c1]
        o[r][c0 + 1:c1] = seg[::-1]
    return o


def swap_and_clear_background_interior(inp, out):
    """Correct swap, but the interior zeros are filled with the frame color."""
    f = _setup(inp)
    if not f:
        return None
    o = [row[:] for row in out]
    for r, k in _interior(f):
        if inp[r][k] == 0:
            o[r][k] = f[0]
    return o


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("swap the two ink colors over the whole grid, not only inside the frame", swap_whole_grid),
    ("swap the ink colors only outside the frame, leaving the interior as is", swap_outside_only),
    ("interior taken one cell too small: the ring next to the frame is not swapped", swap_inner_ring_shrunk),
    ("only the ring of cells next to the frame is swapped, deeper cells unchanged", swap_only_ring),
    ("only the top half of the interior is swapped", swap_top_half),
    ("only the left half of the interior is swapped", swap_left_half),
    ("region is the whole bounding box, so one ink color trades with the frame color", swap_includes_frame_cells),
    ("all interior ink cells take the more frequent ink color", all_ink_to_majority),
    ("the rarer ink color trades with the background 0 instead of the other ink", ink_trades_with_background),
    ("interior is mirrored left to right instead of recolored", mirror_interior_horizontally),
    ("correct swap, but interior background cells are filled with the frame color", swap_and_clear_background_interior),
    ("output equals the input", unchanged),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/7ee1c6ea.json'))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
