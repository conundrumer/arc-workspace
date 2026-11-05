"""Near-miss readings for b548a754: a framed box stretches toward a marker cell."""
import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    ink = {(r, c) for r in range(h) for c in range(w) if inp[r][c] != bg}
    def lone(p):
        r, c = p
        return not any((r + dr, c + dc) in ink for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    marker = next(p for p in sorted(ink) if lone(p))
    body = ink - {marker}
    r0 = min(r for r, _ in body); r1 = max(r for r, _ in body)
    c0 = min(c for _, c in body); c1 = max(c for _, c in body)
    rim = inp[r0][c0]
    core = inp[r0 + 1][c0 + 1]
    return h, w, bg, marker, (r0, r1, c0, c1), rim, core


def _blank(inp, bg, marker):
    g = [row[:] for row in inp]
    g[marker[0]][marker[1]] = bg
    return g


def _draw(g, r0, r1, c0, c1, rim, core):
    h, w = len(g), len(g[0])
    for r in range(max(r0, 0), min(r1, h - 1) + 1):
        for c in range(max(c0, 0), min(c1, w - 1) + 1):
            edge = r in (r0, r1) or c in (c0, c1)
            g[r][c] = rim if edge else core


def _stretched_bounds(inp, extra=0):
    h, w, bg, m, (r0, r1, c0, c1), rim, core = _parse(inp)
    mr, mc = m
    if mr > r1: r1 = mr + extra
    elif mr < r0: r0 = mr - extra
    elif mc > c1: c1 = mc + extra
    elif mc < c0: c0 = mc - extra
    return r0, r1, c0, c1


def marker_stays(inp, out):
    h, w, bg, m, b, rim, core = _parse(inp)
    g = [row[:] for row in out]
    g[m[0]][m[1]] = inp[m[0]][m[1]]
    return g


def stop_one_short(inp, out):
    h, w, bg, m, b, rim, core = _parse(inp)
    g = _blank(inp, bg, m)
    r0, r1, c0, c1 = _stretched_bounds(inp, extra=0)
    mr, mc = m
    if mr > b[1]: r1 -= 1
    elif mr < b[0]: r0 += 1
    elif mc > b[3]: c1 -= 1
    else: c0 += 1
    _draw(g, r0, r1, c0, c1, rim, core)
    return g


def overshoot_one(inp, out):
    h, w, bg, m, b, rim, core = _parse(inp)
    r0, r1, c0, c1 = _stretched_bounds(inp, extra=1)
    if r0 < 0 or c0 < 0 or r1 >= h or c1 >= w:
        return None
    g = _blank(inp, bg, m)
    _draw(g, r0, r1, c0, c1, rim, core)
    return g


def grow_both_sides(inp, out):
    h, w, bg, m, b, rim, core = _parse(inp)
    r0, r1, c0, c1 = _stretched_bounds(inp)
    br0, br1, bc0, bc1 = b
    mr, mc = m
    if mr > br1: r0 = br0 - (mr - br1)
    elif mr < br0: r1 = br1 + (br0 - mr)
    elif mc > bc1: c0 = bc0 - (mc - bc1)
    else: c1 = bc1 + (bc0 - mc)
    g = _blank(inp, bg, m)
    _draw(g, r0, r1, c0, c1, rim, core)
    return g


def extension_solid_rim(inp, out):
    h, w, bg, m, b, rim, core = _parse(inp)
    r0, r1, c0, c1 = _stretched_bounds(inp)
    g = _blank(inp, bg, m)
    _draw(g, r0, r1, c0, c1, rim, core)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if not (b[0] <= r <= b[1] and b[2] <= c <= b[3]):
                g[r][c] = rim
    return g


def extension_marker_color(inp, out):
    h, w, bg, m, b, rim, core = _parse(inp)
    mc_col = inp[m[0]][m[1]]
    r0, r1, c0, c1 = _stretched_bounds(inp)
    g = _blank(inp, bg, m)
    _draw(g, r0, r1, c0, c1, rim, core)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if not (b[0] <= r <= b[1] and b[2] <= c <= b[3]) and g[r][c] == core:
                g[r][c] = mc_col
    return g


def open_far_end(inp, out):
    h, w, bg, m, b, rim, core = _parse(inp)
    r0, r1, c0, c1 = _stretched_bounds(inp)
    g = _blank(inp, bg, m)
    _draw(g, r0, r1, c0, c1, rim, core)
    mr, mc = m
    if mr > b[1]:
        for c in range(c0 + 1, c1): g[r1][c] = core
    elif mr < b[0]:
        for c in range(c0 + 1, c1): g[r0][c] = core
    elif mc > b[3]:
        for r in range(r0 + 1, r1): g[r][c1] = core
    else:
        for r in range(r0 + 1, r1): g[r][c0] = core
    return g


def translate_box(inp, out):
    h, w, bg, m, b, rim, core = _parse(inp)
    br0, br1, bc0, bc1 = b
    mr, mc = m
    dr = dc = 0
    if mr > br1: dr = mr - br1
    elif mr < br0: dr = mr - br0
    elif mc > bc1: dc = mc - bc1
    else: dc = mc - bc0
    g = _blank(inp, bg, m)
    for r in range(br0, br1 + 1):
        for c in range(bc0, bc1 + 1):
            g[r][c] = bg
    for r in range(br0, br1 + 1):
        for c in range(bc0, bc1 + 1):
            g[r + dr][c + dc] = inp[r][c]
    return g


def line_to_marker_only(inp, out):
    h, w, bg, m, b, rim, core = _parse(inp)
    g = [row[:] for row in inp]
    mr, mc = m
    br0, br1, bc0, bc1 = b
    if mr > br1 or mr < br0:
        rs = range(br1 + 1, mr + 1) if mr > br1 else range(mr, br0)
        cc = (bc0 + bc1) // 2
        for r in rs: g[r][cc] = rim
    else:
        cs = range(bc1 + 1, mc + 1) if mc > bc1 else range(mc, bc0)
        rr = (br0 + br1) // 2
        for c in cs: g[rr][c] = rim
    return g


def swap_colors(inp, out):
    h, w, bg, m, b, rim, core = _parse(inp)
    r0, r1, c0, c1 = _stretched_bounds(inp)
    g = _blank(inp, bg, m)
    _draw(g, r0, r1, c0, c1, core, rim)
    return g


def remove_marker_only(inp, out):
    h, w, bg, m, b, rim, core = _parse(inp)
    return _blank(inp, bg, m)


def stretch_core_only(inp, out):
    """Core color grows to the marker, border stays on the original box."""
    h, w, bg, m, b, rim, core = _parse(inp)
    r0, r1, c0, c1 = _stretched_bounds(inp)
    g = _blank(inp, bg, m)
    _draw(g, b[0], b[1], b[2], b[3], rim, core)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if not (b[0] <= r <= b[1] and b[2] <= c <= b[3]):
                g[r][c] = core
    return g


ALTERNATIVES = [
    ("marker cell keeps its marker color instead of becoming border", marker_stays),
    ("box stretches to one cell before the marker", stop_one_short),
    ("box stretches one cell past the marker", overshoot_one),
    ("box grows on both sides by the marker distance", grow_both_sides),
    ("stretched part is filled with the border color", extension_solid_rim),
    ("stretched interior takes the marker color", extension_marker_color),
    ("far side of the stretched box has no border", open_far_end),
    ("box is moved so its far side reaches the marker, not stretched", translate_box),
    ("a one-cell line of border color joins the box to the marker", line_to_marker_only),
    ("border and interior colors are swapped in the stretched box", swap_colors),
    ("marker is removed and the box does not change", remove_marker_only),
    ("only interior color extends to the marker, no new border", stretch_core_only),
]


def _valid(g, truth):
    if not isinstance(g, list) or not g or not isinstance(g[0], list):
        return False
    if any(not isinstance(r, list) or len(r) != len(g[0]) for r in g):
        return False
    if any(type(v) is not int or not 0 <= v <= 9 for r in g for v in r):
        return False
    return g != truth


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b548a754.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error:", fn.__name__, repr(e))
                g = None
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {fn.__name__}: {desc}")
