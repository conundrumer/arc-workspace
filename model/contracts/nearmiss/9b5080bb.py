"""Near-miss readings for ARC task 9b5080bb.

True rule: each figure is a rectangle with single-cell defects (bumps and
dents) on its sides; each defect is marked with the other panel's color on two
cells, the side cell at the defect and the cell just outside it.
"""
import json
from pathlib import Path


def _copy(g):
    return [row[:] for row in g]


def _dominoes(inp, out):
    """Mark cells (cells where out differs from inp), grouped into 4-connected
    groups. Returns a list of dicts: cells, color (mark color), kind."""
    h, w = len(inp), len(inp[0])
    marks = {(r, c) for r in range(h) for c in range(w) if inp[r][c] != out[r][c]}
    panels = {out[r][c] for r, c in marks}
    seen, groups = set(), []
    for start in sorted(marks):
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (r + dr, c + dc)
                if q in marks and q not in seen and out[q[0]][q[1]] == out[r][c]:
                    seen.add(q)
                    stack.append(q)
        groups.append(sorted(comp))
    bump_colors = {}
    for g in groups:
        for r, c in g:
            if inp[r][c] not in panels:
                bump_colors[inp[r][c]] = bump_colors.get(inp[r][c], 0) + 1
    fig = max(bump_colors, key=bump_colors.get) if bump_colors else None
    res = []
    for g in groups:
        res.append({
            "cells": g,
            "color": out[g[0][0]][g[0][1]],
            "kind": "bump" if inp[g[0][0]][g[0][1]] not in panels else "dent",
        })
    return res, panels, fig


def _components(inp, color):
    h, w = len(inp), len(inp[0])
    seen, comps = set(), []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == color and (r, c) not in seen:
                stack, comp = [(r, c)], []
                seen.add((r, c))
                while stack:
                    a, b = stack.pop()
                    comp.append((a, b))
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        q = (a + dr, b + dc)
                        if 0 <= q[0] < h and 0 <= q[1] < w and q not in seen and inp[q[0]][q[1]] == color:
                            seen.add(q)
                            stack.append(q)
                comps.append(comp)
    return comps


def _inside_outside(inp, dom, fig):
    """Return (inside_cell, outside_cell) of a two-cell defect: the inside cell
    is the one nearer to the centre of the nearest figure."""
    if fig is None or len(dom["cells"]) != 2:
        return None
    comps = _components(inp, fig)
    cells = dom["cells"]
    best, bd = None, None
    for comp in comps:
        d = min(abs(a - r) + abs(b - c) for a, b in comp for r, c in cells)
        if bd is None or d < bd:
            best, bd = comp, d
    cr = sum(a for a, _ in best) / len(best)
    cc = sum(b for _, b in best) / len(best)
    d0 = abs(cells[0][0] - cr) + abs(cells[0][1] - cc)
    d1 = abs(cells[1][0] - cr) + abs(cells[1][1] - cc)
    if d0 == d1:
        return None
    return (cells[0], cells[1]) if d0 < d1 else (cells[1], cells[0])


def _revert(inp, out, cells):
    g = _copy(out)
    for r, c in cells:
        g[r][c] = inp[r][c]
    return g


def _keep_only(inp, out, pred):
    doms, panels, fig = _dominoes(inp, out)
    drop = [cell for d in doms if not pred(d) for cell in d["cells"]]
    return _revert(inp, out, drop)


def unchanged(inp, out):
    return _copy(inp)


def dents_only(inp, out):
    return _keep_only(inp, out, lambda d: d["kind"] == "dent")


def bumps_only(inp, out):
    return _keep_only(inp, out, lambda d: d["kind"] == "bump")


def outside_only(inp, out):
    doms, panels, fig = _dominoes(inp, out)
    drop = []
    for d in doms:
        io = _inside_outside(inp, d, fig)
        if io is None:
            return None
        drop.append(io[0])
    return _revert(inp, out, drop)


def side_only(inp, out):
    doms, panels, fig = _dominoes(inp, out)
    drop = []
    for d in doms:
        io = _inside_outside(inp, d, fig)
        if io is None:
            return None
        drop.append(io[1])
    return _revert(inp, out, drop)


def own_panel_color(inp, out):
    doms, panels, fig = _dominoes(inp, out)
    if len(panels) != 2:
        return None
    g = _copy(out)
    for d in doms:
        own = next(p for p in panels if p != d["color"])
        for r, c in d["cells"]:
            g[r][c] = own
    return g


def fill_dents_with_figure(inp, out):
    doms, panels, fig = _dominoes(inp, out)
    if fig is None:
        return None
    g = _keep_only(inp, out, lambda d: d["kind"] == "dent")
    for d in doms:
        if d["kind"] == "dent":
            for r, c in d["cells"]:
                g[r][c] = fig
    return g


def horizontal_only(inp, out):
    return _keep_only(inp, out, lambda d: d["cells"][0][0] == d["cells"][-1][0])


def vertical_only(inp, out):
    return _keep_only(inp, out, lambda d: d["cells"][0][1] == d["cells"][-1][1])


def one_panel_color_only(inp, out):
    doms, panels, fig = _dominoes(inp, out)
    lo = min(panels)
    return _keep_only(inp, out, lambda d: d["color"] == lo)


def shifted_outward(inp, out):
    doms, panels, fig = _dominoes(inp, out)
    h, w = len(inp), len(inp[0])
    g = _copy(out)
    for d in doms:
        io = _inside_outside(inp, d, fig)
        if io is None:
            return None
        (ir, ic), (orr, oc) = io
        g[ir][ic] = inp[ir][ic]
        br, bc = orr + (orr - ir), oc + (oc - ic)
        if 0 <= br < h and 0 <= bc < w:
            g[br][bc] = d["color"]
    return g


def wide_stripe(inp, out):
    doms, panels, fig = _dominoes(inp, out)
    h, w = len(inp), len(inp[0])
    g = _copy(out)
    for d in doms:
        if len(d["cells"]) != 2:
            return None
        (r0, c0), (r1, c1) = d["cells"]
        pr, pc = (1, 0) if r0 == r1 else (0, 1)
        for r, c in d["cells"]:
            for s in (-1, 1):
                a, b = r + s * pr, c + s * pc
                if 0 <= a < h and 0 <= b < w:
                    g[a][b] = d["color"]
    return g


ALTERNATIVES = [
    ("input returned unchanged (no defect marked)", unchanged),
    ("only dents are marked, bumps are ignored", dents_only),
    ("only bumps are marked, dents are ignored", bumps_only),
    ("only the cell just outside each defect is marked, not the side cell", outside_only),
    ("only the side cell of each defect is marked, not the cell outside", side_only),
    ("defects are marked with the figure's own panel color instead of the other panel's", own_panel_color),
    ("dents are filled with the figure color and nothing is marked", fill_dents_with_figure),
    ("only defects on left and right sides are marked", horizontal_only),
    ("only defects on top and bottom sides are marked", vertical_only),
    ("only defects that take the lower panel color are marked (one panel's figures)", one_panel_color_only),
    ("mark is shifted one cell outward: the outside cell and the cell beyond it", shifted_outward),
    ("mark is three cells wide along the side instead of one", wide_stripe),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    w = len(g[0])
    for row in g:
        if not isinstance(row, list) or len(row) != w:
            return False
        for v in row:
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9:
                return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/9b5080bb.json").read_text())
    pairs = task["train"]
    print(f"train pairs: {len(pairs)}")
    for desc, fn in ALTERNATIVES:
        n = sum(1 for p in pairs if _valid(fn(p["input"], p["output"]), p["output"]))
        print(f"{n}/{len(pairs)}  {desc}")
