"""Near-miss readings for ARC task 264363fd."""
import json
from collections import Counter
from pathlib import Path

DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _analyze(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            stack, comp = [(r, c)], []
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in DIRS:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != bg and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append(comp)
    rects, tmpl = [], None
    for comp in comps:
        ys = [p[0] for p in comp]
        xs = [p[1] for p in comp]
        box = (min(ys), min(xs), max(ys), max(xs))
        area = (box[2] - box[0] + 1) * (box[3] - box[1] + 1)
        if area == len(comp):
            cnt = Counter(inp[y][x] for y, x in comp)
            body = cnt.most_common(1)[0][0]
            marks = [p for p in comp if inp[p[0]][p[1]] != body]
            rects.append({"box": box, "body": body, "marks": marks})
        else:
            tmpl = {"cells": {p: inp[p[0]][p[1]] for p in comp}, "box": box}
    b = tmpl["box"]
    tmpl["anchor"] = ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
    tips = []
    cells = tmpl["cells"]
    for (y, x), col in cells.items():
        nb = [d for d in DIRS if (y + d[0], x + d[1]) in cells]
        if len(nb) == 1:
            tips.append(((y, x), col, (-nb[0][0], -nb[0][1])))
    tmpl["tips"] = tips
    return bg, rects, tmpl


def _solve(inp, anchor_shift=(0, 0), erase=True, rays="tip", ray_color="tip",
           ray_clip="rect", only_first_rect=False, tip_dirs=None, transpose=False,
           rect_mark_only_first=False, ray_start=1):
    bg, rects, tmpl = _analyze(inp)
    h, w = len(inp), len(inp[0])
    out = [row[:] for row in inp]
    cells = dict(tmpl["cells"])
    tips = list(tmpl["tips"])
    anchor = (tmpl["anchor"][0] + anchor_shift[0], tmpl["anchor"][1] + anchor_shift[1])
    if transpose:
        cells = {(x, y): v for (y, x), v in cells.items()}
        tips = [((x, y), c, (d[1], d[0])) for (y, x), c, d in tips]
        anchor = (anchor[1], anchor[0])
    if erase:
        for (y, x) in tmpl["cells"]:
            out[y][x] = bg
    sel = rects[:1] if only_first_rect else rects
    stamps = []
    for rc in sel:
        marks = sorted(rc["marks"])
        if rect_mark_only_first:
            marks = marks[:1]
        for (my, mx) in marks:
            dy, dx = my - anchor[0], mx - anchor[1]
            stamps.append((rc, dy, dx))
    # rays first, then stamps
    for rc, dy, dx in stamps:
        by0, bx0, by1, bx1 = rc["box"]
        for (ty, tx), col, d in tips:
            if tip_dirs is not None and d not in tip_dirs:
                continue
            dirs = {"tip": [d], "back": [(-d[0], -d[1])],
                    "all": DIRS, "none": []}[rays]
            color = col
            if ray_color == "marker":
                color = inp[rc["marks"][0][0]][rc["marks"][0][1]]
            elif ray_color == "body":
                color = rc["body"]
            for dd in dirs:
                y, x = ty + dy + dd[0] * ray_start, tx + dx + dd[1] * ray_start
                while 0 <= y < h and 0 <= x < w:
                    if ray_clip != "rect" or (by0 <= y <= by1 and bx0 <= x <= bx1):
                        out[y][x] = color
                    y += dd[0]
                    x += dd[1]
    for rc, dy, dx in stamps:
        for (ty, tx), col in cells.items():
            y, x = ty + dy, tx + dx
            by0, bx0, by1, bx1 = rc["box"]
            if by0 <= y <= by1 and bx0 <= x <= bx1:
                out[y][x] = col
    return out


def correct(inp):
    return _solve(inp)


def no_rays(inp, out):
    return _solve(inp, rays="none")


def keep_template(inp, out):
    bg, rects, tmpl = _analyze(inp)
    g = [row[:] for row in out]
    for (y, x), v in tmpl["cells"].items():
        g[y][x] = v
    return g


def down_right_tips_only(inp, out):
    return _solve(inp, tip_dirs=[(1, 0), (0, 1)])


def rays_all_dirs(inp, out):
    return _solve(inp, rays="all")


def rays_marker_color(inp, out):
    return _solve(inp, ray_color="marker")


def rays_unclipped(inp, out):
    return _solve(inp, ray_clip="none")


def anchor_corner(inp, out):
    bg, rects, tmpl = _analyze(inp)
    b = tmpl["box"]
    sh = (b[0] - tmpl["anchor"][0], b[1] - tmpl["anchor"][1])
    return _solve(inp, anchor_shift=sh)


def anchor_off_by_one(inp, out):
    return _solve(inp, anchor_shift=(0, 1))


def first_rect_only(inp, out):
    return _solve(inp, only_first_rect=True)


def first_marker_per_rect(inp, out):
    return _solve(inp, rect_mark_only_first=True)


def vertical_tips_only(inp, out):
    return _solve(inp, tip_dirs=[(-1, 0), (1, 0)])


def horizontal_tips_only(inp, out):
    return _solve(inp, tip_dirs=[(0, -1), (0, 1)])


def transposed_template(inp, out):
    return _solve(inp, transpose=True)


def rays_include_tip_offset(inp, out):
    # rays begin one cell further out, leaving a gap beside each tip
    return _solve(inp, ray_start=2)


ALTERNATIVES = [
    ("stamp the template at each marker but draw no rays", no_rays),
    ("template left in its original place instead of erased", keep_template),
    ("only tips pointing down or right cast rays", down_right_tips_only),
    ("rays run in all four directions from each tip", rays_all_dirs),
    ("rays use the marker color instead of the tip color", rays_marker_color),
    ("rays run to the grid edge instead of stopping at the rectangle", rays_unclipped),
    ("template aligned by its bbox corner instead of its center", anchor_corner),
    ("template aligned one column off center", anchor_off_by_one),
    ("only the first rectangle is stamped", first_rect_only),
    ("only the first marker of each rectangle is stamped", first_marker_per_rect),
    ("only vertical tips cast rays", vertical_tips_only),
    ("only horizontal tips cast rays", horizontal_tips_only),
]


def _valid(g, out):
    if g is None or not g or not isinstance(g, list):
        return False
    w = len(g[0])
    for r in g:
        if not isinstance(r, list) or len(r) != w:
            return False
        for v in r:
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9:
                return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/264363fd.json"))
    train = task["train"]
    for p in train:
        assert correct(p["input"]) == p["output"], "model of true rule is wrong"
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in train)
        print(f"{n}/{len(train)}  {desc}")
