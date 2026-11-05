import json
from collections import Counter
from pathlib import Path


def _colors(inp):
    cnt = Counter(v for r in inp for v in r if v)
    ordered = [c for c, _ in cnt.most_common()]
    return ordered[0], ordered[-1]  # frame, ink


def _comps(inp):
    """Enclosed regions (not reachable from the border without crossing the frame)."""
    frame, ink = _colors(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    stack = [(r, c) for r in range(h) for c in range(w)
             if (r in (0, h - 1) or c in (0, w - 1)) and inp[r][c] != frame]
    seen.update(stack)
    while stack:
        r, c = stack.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (r + dr, c + dc)
            if 0 <= q[0] < h and 0 <= q[1] < w and q not in seen and inp[q[0]][q[1]] != frame:
                seen.add(q)
                stack.append(q)
    enc = {(r, c) for r in range(h) for c in range(w) if inp[r][c] != frame} - seen
    res, done = [], set()
    for s in sorted(enc):
        if s in done:
            continue
        comp, st = set(), [s]
        done.add(s)
        while st:
            r, c = st.pop()
            comp.add((r, c))
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (r + dr, c + dc)
                if q in enc and q not in done:
                    done.add(q)
                    st.append(q)
        rs = [p[0] for p in comp]
        cs = [p[1] for p in comp]
        res.append({
            "cells": comp,
            "box": (min(rs), max(rs), min(cs), max(cs)),
            "ink": {p for p in comp if inp[p[0]][p[1]] == ink},
        })
    return res, frame, ink


def _flip(p, box, axis, off=0):
    r0, r1, c0, c1 = box
    r, c = p
    if axis == "H":  # left-right mirror
        return (r, c0 + c1 - c + off)
    return (r0 + r1 - r + off, c)  # "V": top-bottom mirror


def _true_axis(inp, out, comp, ink):
    for ax in ("H", "V"):
        got = {p for p in comp["cells"] if out[p[0]][p[1]] == ink}
        if got == comp["ink"] | {_flip(p, comp["box"], ax) for p in comp["ink"]}:
            return ax
    return None


def _paint(inp, cells, color):
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for r, c in cells:
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = color
    return g


def _each(inp, out, fn):
    """fn(comp, axis, other_axis, frame, ink) -> (cells_to_paint, color, cells_to_erase)."""
    comps, frame, ink = _comps(inp)
    g = [row[:] for row in inp]
    for comp in comps:
        ax = _true_axis(inp, out, comp, ink)
        if ax is None:
            continue
        oth = "V" if ax == "H" else "H"
        paint, color, erase = fn(comp, ax, oth, frame, ink)
        for r, c in erase:
            g[r][c] = 0
        g = _paint(g, paint, color)
    return g


def mirror_outer_line_only(inp, out):
    def fn(k, ax, oth, f, i):
        idx = 1 if ax == "H" else 0
        lo = min(p[idx] for p in k["ink"])
        part = {p for p in k["ink"] if p[idx] == lo}
        return k["ink"] | {_flip(p, k["box"], ax) for p in part}, i, set()
    return _each(inp, out, fn)


def transposed_copy(inp, out):
    def fn(k, ax, oth, f, i):
        rmin = min(p[0] for p in k["ink"])
        cmin = min(p[1] for p in k["ink"])
        return k["ink"] | {(rmin + (c - cmin), cmin + (r - rmin)) for r, c in k["ink"]}, i, set()
    return _each(inp, out, fn)


def move_not_copy(inp, out):
    return _each(inp, out, lambda k, ax, oth, f, i: (
        {_flip(p, k["box"], ax) for p in k["ink"]}, i, k["ink"]))


def off_by_one_mirror(inp, out):
    return _each(inp, out, lambda k, ax, oth, f, i: (
        k["ink"] | {_flip(p, k["box"], ax, -1) for p in k["ink"]}, i, set()))


def wrong_color(inp, out):
    return _each(inp, out, lambda k, ax, oth, f, i: (
        {_flip(p, k["box"], ax) for p in k["ink"]}, f, set()))


def mirror_about_near_edge(inp, out):
    def fn(k, ax, oth, f, i):
        r0, r1, c0, c1 = k["box"]
        if ax == "H":
            return k["ink"] | {(r, 2 * c0 - c) for r, c in k["ink"]}, i, set()
        return k["ink"] | {(2 * r0 - r, c) for r, c in k["ink"]}, i, set()
    return _each(inp, out, fn)


def translate_not_mirror(inp, out):
    def fn(k, ax, oth, f, i):
        r0, r1, c0, c1 = k["box"]
        if ax == "H":
            lo = min(p[1] for p in k["ink"])
            hi = max(p[1] for p in k["ink"])
            d = (c0 + c1) - hi - lo
            moved = {(r, c + d) for r, c in k["ink"]}
        else:
            lo = min(p[0] for p in k["ink"])
            hi = max(p[0] for p in k["ink"])
            d = (r0 + r1) - hi - lo
            moved = {(r + d, c) for r, c in k["ink"]}
        return k["ink"] | moved, i, set()
    return _each(inp, out, fn)


def first_enclosure_only(inp, out):
    comps, frame, ink = _comps(inp)
    if len(comps) < 2:
        return None
    k = comps[0]
    ax = _true_axis(inp, out, k, ink)
    if ax is None:
        return None
    return _paint(inp, k["ink"] | {_flip(p, k["box"], ax) for p in k["ink"]}, ink)


def mirror_about_grid_center(inp, out):
    h, w = len(inp), len(inp[0])

    def fn(k, ax, oth, f, i):
        if ax == "H":
            return k["ink"] | {(r, w - 1 - c) for r, c in k["ink"]}, i, set()
        return k["ink"] | {(h - 1 - r, c) for r, c in k["ink"]}, i, set()
    return _each(inp, out, fn)


def crop_enclosure(inp, out):
    comps, frame, ink = _comps(inp)
    k = max(comps, key=lambda k: len(k["cells"]))
    r0, r1, c0, c1 = k["box"]
    res = [row[:] for row in out[r0:r1 + 1]]
    return [row[c0:c1 + 1] for row in res]


def fill_bbox_of_union(inp, out):
    def fn(k, ax, oth, f, i):
        allc = k["ink"] | {_flip(p, k["box"], ax) for p in k["ink"]}
        rs = [p[0] for p in allc]
        cs = [p[1] for p in allc]
        return {(r, c) for r in range(min(rs), max(rs) + 1)
                for c in range(min(cs), max(cs) + 1)
                if (r, c) in k["cells"]}, i, set()
    return _each(inp, out, fn)


def mirror_whole_interior_content(inp, out):
    """Reflect the ink into the far half of the frame's outer box, including the wall columns."""
    def fn(k, ax, oth, f, i):
        r0, r1, c0, c1 = k["box"]
        box = (r0 - 1, r1 + 1, c0 - 1, c1 + 1)
        return k["ink"] | {_flip(p, box, ax) for p in k["ink"]}, i, set()
    return _each(inp, out, fn)


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("mirror only the outermost line of ink, not the whole shape", mirror_outer_line_only),
    ("add a transposed (diagonal) copy of the ink instead of a mirror", transposed_copy),
    ("move the ink to the mirrored spot instead of keeping the original", move_not_copy),
    ("mirror about a center off by one cell", off_by_one_mirror),
    ("mirrored copy painted in the frame color", wrong_color),
    ("reflect about the enclosure's near edge instead of its center", mirror_about_near_edge),
    ("translated copy placed at the mirrored position, not flipped", translate_not_mirror),
    ("complete only the first enclosure and leave the others", first_enclosure_only),
    ("mirror about the grid center line instead of the enclosure center", mirror_about_grid_center),
    ("output only the enclosure interior, cropped", crop_enclosure),
    ("fill the whole box spanning original and mirrored ink", fill_bbox_of_union),
    ("output the input unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/18419cfa.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        per = []
        for p in pairs:
            g = fn(p["input"], p["output"])
            ok = g is not None and _valid(g) and g != p["output"]
            per.append(int(ok))
            n += ok
        print(f"{n}/{len(pairs)} {per} {desc}")
