"""Near-miss rules for ARC task 184a9768.

Rule: frames are shapes with enclosed background (holes); pieces are the other
shapes. Each hole is filled with the color of the piece(s) whose shape tiles
it. Pieces and scattered noise cells vanish; frames stay.
"""
import json
from collections import Counter
from pathlib import Path

N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _copy(g):
    return [row[:] for row in g]


def _components(cells):
    """4-connected components of a set of (r, c)."""
    cells = set(cells)
    comps = []
    while cells:
        start = cells.pop()
        comp = {start}
        stack = [start]
        while stack:
            r, c = stack.pop()
            for dr, dc in N4:
                q = (r + dr, c + dc)
                if q in cells:
                    cells.discard(q)
                    comp.add(q)
                    stack.append(q)
        comps.append(comp)
    return comps


def _analyse(inp, out):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for row in inp for v in row).most_common(1)[0][0]
    in_colors = {v for row in inp for v in row}
    out_colors = {v for row in out for v in row}
    noise_colors = in_colors - out_colors - {bg}
    # holes: bg cells not reachable from the border through bg cells
    reach = set()
    stack = [(r, c) for r in range(h) for c in range(w)
             if (r in (0, h - 1) or c in (0, w - 1)) and inp[r][c] == bg]
    reach.update(stack)
    while stack:
        r, c = stack.pop()
        for dr, dc in N4:
            q = (r + dr, c + dc)
            if 0 <= q[0] < h and 0 <= q[1] < w and q not in reach and inp[q[0]][q[1]] == bg:
                reach.add(q)
                stack.append(q)
    hole = {(r, c) for r in range(h) for c in range(w)
            if inp[r][c] == bg and (r, c) not in reach}
    # objects: same-color 4-connected components, excluding bg and noise
    objs = []
    for col in in_colors - {bg} - noise_colors:
        cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == col]
        for comp in _components(cells):
            touches = any((r + dr, c + dc) in hole for r, c in comp for dr, dc in N4)
            objs.append({"color": col, "cells": comp, "frame": touches})
    hole_comps = _components(hole)
    for hc in hole_comps:
        fcols = Counter()
        for r, c in hc:
            for dr, dc in N4:
                q = (r + dr, c + dc)
                for i, o in enumerate(objs):
                    if o["frame"] and q in o["cells"]:
                        fcols[i] += 1
        hc_owner = fcols.most_common(1)[0][0] if fcols else None
        hc_info = hc_owner
        # store on a side list
        objs.append({"hole": hc, "owner": hc_info, "color": None, "cells": set(), "frame": False, "is_hole": True})
    frames = [o for o in objs if o["frame"]]
    pieces = [o for o in objs if not o["frame"] and not o.get("is_hole")]
    holes = [o for o in objs if o.get("is_hole")]
    noise = {(r, c) for r in range(h) for c in range(w) if inp[r][c] in noise_colors}
    return dict(h=h, w=w, bg=bg, hole=hole, frames=frames, pieces=pieces,
                holes=holes, noise=noise, objs=objs)


def _norm(cells):
    r0 = min(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    return frozenset((r - r0, c - c0) for r, c in cells)


def noise_kept(inp, out):
    a = _analyse(inp, out)
    g = _copy(out)
    for r, c in a["noise"]:
        g[r][c] = inp[r][c]
    return g


def pieces_kept(inp, out):
    a = _analyse(inp, out)
    g = _copy(out)
    for p in a["pieces"]:
        for r, c in p["cells"]:
            g[r][c] = inp[r][c]
    return g


def holes_unfilled(inp, out):
    a = _analyse(inp, out)
    g = _copy(out)
    for r, c in a["hole"]:
        g[r][c] = a["bg"]
    return g


def holes_solid_frame_color(inp, out):
    a = _analyse(inp, out)
    g = _copy(out)
    for hc in a["holes"]:
        o = hc["owner"]
        if o is None:
            continue
        col = a["objs"][o]["color"]
        for r, c in hc["hole"]:
            g[r][c] = col
    return g


def only_largest_hole_per_frame(inp, out):
    a = _analyse(inp, out)
    g = _copy(out)
    best = {}
    for hc in a["holes"]:
        o = hc["owner"]
        if o not in best or len(hc["hole"]) > len(best[o]["hole"]):
            best[o] = hc
    for hc in a["holes"]:
        if best[hc["owner"]] is not hc:
            for r, c in hc["hole"]:
                g[r][c] = a["bg"]
    return g


def hole_colors_rotated(inp, out):
    a = _analyse(inp, out)
    comps = sorted(a["holes"], key=lambda x: min(x["hole"]))
    if len(comps) < 2:
        return None
    colors = [out[min(x["hole"])[0]][min(x["hole"])[1]] for x in comps]
    g = _copy(out)
    for i, hc in enumerate(comps):
        col = colors[(i + 1) % len(comps)]
        for r, c in hc["hole"]:
            g[r][c] = col
    return g


def exact_shape_only(inp, out):
    a = _analyse(inp, out)
    shapes = {}
    for p in a["pieces"]:
        shapes.setdefault(_norm(p["cells"]), p["color"])
    g = _copy(out)
    for hc in a["holes"]:
        shp = _norm(hc["hole"])
        col = shapes.get(shp, a["bg"])
        for r, c in hc["hole"]:
            g[r][c] = col
    return g


def fill_shifted_right(inp, out):
    a = _analyse(inp, out)
    g = _copy(out)
    for r, c in a["hole"]:
        g[r][c] = a["bg"]
    for r, c in a["hole"]:
        if (r, c + 1) in a["hole"]:
            g[r][c + 1] = out[r][c]
    return g


def crop_to_biggest_frame(inp, out):
    a = _analyse(inp, out)
    if not a["frames"]:
        return None
    f = max(a["frames"], key=lambda o: len(o["cells"]))
    rs = [r for r, _ in f["cells"]]
    cs = [c for _, c in f["cells"]]
    return [row[min(cs):max(cs) + 1] for row in out[min(rs):max(rs) + 1]]


def frames_erased(inp, out):
    a = _analyse(inp, out)
    g = _copy(out)
    for f in a["frames"]:
        for r, c in f["cells"]:
            g[r][c] = a["bg"]
    return g


def all_holes_largest_piece_color(inp, out):
    a = _analyse(inp, out)
    if not a["pieces"]:
        return None
    big = max(a["pieces"], key=lambda o: len(o["cells"]))
    g = _copy(out)
    for r, c in a["hole"]:
        g[r][c] = big["color"]
    return g


ALTERNATIVES = [
    ("Scattered noise cells are left in place instead of being erased", noise_kept),
    ("Pieces are copied into holes but their original cells are not erased", pieces_kept),
    ("Holes are left empty; pieces and noise vanish without filling anything", holes_unfilled),
    ("Holes are closed with the frame's own color instead of a piece color", holes_solid_frame_color),
    ("Only the largest hole of each frame is filled", only_largest_hole_per_frame),
    ("Holes take the fill color of the next hole in reading order (wrong piece to hole pairing)", hole_colors_rotated),
    ("A hole is filled only when one piece matches its shape exactly (no repeated tiling)", exact_shape_only),
    ("Fill is shifted one column right within each hole (off-by-one placement)", fill_shifted_right),
    ("Output is cropped to the largest frame's bounding box", crop_to_biggest_frame),
    ("Frames are erased and only the filled hole contents remain", frames_erased),
    ("Every hole is filled with the color of the largest piece", all_holes_largest_piece_color),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / "data/tasks/184a9768.json"
    train = json.load(open(path))["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for pair in train:
            g = fn(pair["input"], pair["output"])
            if g is not None and _valid(g) and g != pair["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
