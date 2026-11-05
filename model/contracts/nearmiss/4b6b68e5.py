import json
from collections import Counter
from pathlib import Path

N4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
N8 = N4 + [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def bgcolor(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def components(g, bg, nb=N4):
    h, w = len(g), len(g[0])
    seen = {}
    comps = []
    for i in range(h):
        for j in range(w):
            if g[i][j] == bg or (i, j) in seen:
                continue
            c = g[i][j]
            stack = [(i, j)]
            seen[(i, j)] = len(comps)
            cells = []
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for da, db in nb:
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and (x, y) not in seen and g[x][y] == c:
                        seen[(x, y)] = len(comps)
                        stack.append((x, y))
            comps.append(cells)
    return comps


def analyse(g, nb_obj=N4, nb_flood=N4, min_size=2):
    """Return bg, outlines (list of cell sets), specks (list of cells),
    enclosed (per outline: set of enclosed cells)."""
    h, w = len(g), len(g[0])
    bg = bgcolor(g)
    comps = components(g, bg, nb_obj)
    outlines = [set(c) for c in comps if len(c) >= min_size]
    specks = [c[0] for c in comps if len(c) < min_size]
    enclosed = []
    for wall in outlines:
        reach = set()
        stack = [(i, j) for i in range(h) for j in range(w)
                 if (i in (0, h - 1) or j in (0, w - 1)) and (i, j) not in wall]
        reach.update(stack)
        while stack:
            a, b = stack.pop()
            for da, db in nb_flood:
                x, y = a + da, b + db
                if 0 <= x < h and 0 <= y < w and (x, y) not in wall and (x, y) not in reach:
                    reach.add((x, y))
                    stack.append((x, y))
        enc = {(i, j) for i in range(h) for j in range(w)
               if (i, j) not in wall and (i, j) not in reach}
        enclosed.append(enc)
    return bg, outlines, specks, enclosed


def regions(enc, nb=N4):
    left = set(enc)
    out = []
    while left:
        s = left.pop()
        stack = [s]
        reg = {s}
        while stack:
            a, b = stack.pop()
            for da, db in nb:
                p = (a + da, b + db)
                if p in left:
                    left.discard(p)
                    reg.add(p)
                    stack.append(p)
        out.append(reg)
    return out


def commonest(cols, pick="most"):
    cnt = Counter(cols)
    if not cnt:
        return None
    ordered = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))
    return ordered[0][0] if pick == "most" else ordered[-1][0]


def solve(g, fill_pick="most", per_cavity=False, clear_outside=True,
          fill_specks=True, only_largest=False, nb_flood=N4, nb_obj=N4,
          scope="enclosed", color_scope="shape", fill_with_outline=False):
    h, w = len(g), len(g[0])
    bg, outlines, specks, enclosed = analyse(g, nb_obj, nb_flood)
    res = [[bg] * w for _ in range(h)]
    if not clear_outside:
        for (i, j) in specks:
            res[i][j] = g[i][j]
    allspeck_cols = [g[i][j] for (i, j) in specks]
    order = sorted(range(len(outlines)), key=lambda k: -len(outlines[k]))
    for k, wall in enumerate(outlines):
        for (i, j) in wall:
            res[i][j] = g[i][j]
    for k, wall in enumerate(outlines):
        if only_largest and k != order[0]:
            if not clear_outside:
                pass
            for (i, j) in enclosed[k]:
                if (i, j) in specks or not clear_outside:
                    res[i][j] = g[i][j]
            continue
        enc = enclosed[k]
        if scope == "bbox" and wall:
            r0 = min(i for i, _ in wall); r1 = max(i for i, _ in wall)
            c0 = min(j for _, j in wall); c1 = max(j for _, j in wall)
            enc = {(i, j) for i in range(r0, r1 + 1) for j in range(c0, c1 + 1)
                   if (i, j) not in wall}
        groups = regions(enc) if per_cavity else [enc]
        for grp in groups:
            if color_scope == "grid":
                cols = allspeck_cols
            else:
                cols = [g[i][j] for (i, j) in grp if g[i][j] != bg]
            c = commonest(cols, fill_pick)
            if fill_with_outline:
                c = g[next(iter(wall))[0]][next(iter(wall))[1]]
            if c is None:
                continue
            for (i, j) in grp:
                if not fill_specks and g[i][j] == bg:
                    res[i][j] = c
                elif fill_specks:
                    res[i][j] = c
                else:
                    res[i][j] = g[i][j]
    return res


def truth(inp, out):
    return solve(inp)


def a_least_common(inp, out):
    return solve(inp, fill_pick="least")


def a_grid_color(inp, out):
    return solve(inp, color_scope="grid")


def a_grid_commonest(inp, out):
    # fill color is the commonest non-background color of the whole grid
    bg = bgcolor(inp)
    c = commonest([v for r in inp for v in r if v != bg])
    return solve(inp, fill_with_outline=False) and _repaint(inp, out, c)


def _repaint(inp, out, c):
    bg, outlines, specks, enclosed = analyse(inp)
    res = [row[:] for row in out]
    for enc in enclosed:
        for (i, j) in enc:
            res[i][j] = c
    return res


def a_keep_outside(inp, out):
    return solve(inp, clear_outside=False)


def a_inside_specks_stay(inp, out):
    return solve(inp, fill_specks=False)


def a_margin(inp, out):
    # fill leaves the enclosed cells that touch the outline unfilled
    bg, outlines, specks, enclosed = analyse(inp)
    h, w = len(inp), len(inp[0])
    res = [row[:] for row in out]
    for k, wall in enumerate(outlines):
        for (i, j) in enclosed[k]:
            if any((i + da, j + db) in wall for da, db in N8):
                res[i][j] = bg
    return res


def a_outline_color(inp, out):
    return solve(inp, fill_with_outline=True)


def a_bbox_fill(inp, out):
    return solve(inp, scope="bbox")


def a_only_largest(inp, out):
    return solve(inp, only_largest=True)


def a_crop_largest(inp, out):
    bg, outlines, specks, enclosed = analyse(inp)
    if not outlines:
        return None
    big = max(outlines, key=len)
    r0 = min(i for i, _ in big); r1 = max(i for i, _ in big)
    c0 = min(j for _, j in big); c1 = max(j for _, j in big)
    full = out
    return [row[c0:c1 + 1] for row in full[r0:r1 + 1]]


def a_recolor_specks_only(inp, out):
    # recolor only the inside specks to the majority color; no fill of empty cells
    h, w = len(inp), len(inp[0])
    bg, outlines, specks, enclosed = analyse(inp)
    res = [row[:] for row in out]
    for k, enc in enumerate(enclosed):
        cols = [inp[i][j] for (i, j) in enc if inp[i][j] != bg]
        c = commonest(cols)
        if c is None:
            continue
        for (i, j) in enc:
            res[i][j] = c if inp[i][j] != bg else bg
    return res


def a_fill_incl_outline_gaps_only(inp, out):
    # fill ignores the specks' color: use the top-left-most inside speck color
    bg, outlines, specks, enclosed = analyse(inp)
    res = [row[:] for row in out]
    for enc in enclosed:
        sp = sorted((p for p in enc if inp[p[0]][p[1]] != bg))
        if not sp:
            continue
        c = inp[sp[0][0]][sp[0][1]]
        for (i, j) in enc:
            res[i][j] = c
    return res


def a_leave_inside_specks_and_outside(inp, out):
    # input returned with only the fill applied on top of the untouched input
    res = [row[:] for row in inp]
    bg, outlines, specks, enclosed = analyse(inp)
    for enc in enclosed:
        for (i, j) in enc:
            res[i][j] = out[i][j]
    return res


ALTERNATIVES = [
    ("fill with the least common speck color inside the outline", a_least_common),
    ("fill with the commonest speck color of the whole grid, not the outline", a_grid_color),
    ("fill color is the commonest non-background color of the whole grid", a_grid_commonest),
    ("specks outside every outline are kept", a_keep_outside),
    ("only empty cells inside are filled; inside specks stay", a_inside_specks_stay),
    ("fill stops one cell short of the outline", a_margin),
    ("fill with the outline's own color", a_outline_color),
    ("fill the whole bounding box of each outline", a_bbox_fill),
    ("only the largest outline is processed", a_only_largest),
    ("crop output to the largest outline's bounding box", a_crop_largest),
    ("recolor only inside specks to the majority color, leave empty cells", a_recolor_specks_only),
    ("fill color is the first speck inside in reading order", a_fill_incl_outline_gaps_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/4b6b68e5.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    ok_truth = sum(truth(p["input"], p["output"]) == p["output"] for p in pairs)
    print("sanity: reference solver matches", ok_truth, "of", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            r = fn(p["input"], p["output"])
            if r is not None and _valid(r) and r != p["output"]:
                n += 1
        print(n, desc)
