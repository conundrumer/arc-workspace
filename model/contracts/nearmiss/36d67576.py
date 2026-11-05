"""Near-miss readings for 36d67576.

Rule: the grid holds several parts (8-connected non-zero groups) made of
shape color 4 and one anchor cell of color 2. One part also carries marks
(colors 1 and 3). Every other part is a rotated/reflected copy of the
model part's shape; the marks are carried to it with the same transform,
relative to the anchor, and drawn on background cells.
"""
import json
from pathlib import Path

ANCHOR = 2
SHAPE = 4
MARKS = (1, 3)

D4 = [
    lambda r, c: (r, c),
    lambda r, c: (c, -r),
    lambda r, c: (-r, -c),
    lambda r, c: (-c, r),
    lambda r, c: (r, -c),
    lambda r, c: (-r, c),
    lambda r, c: (c, r),
    lambda r, c: (-c, -r),
]
INVERSE = [0, 3, 2, 1, 4, 5, 6, 7]


def components(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0
                                and (ny, nx) not in seen):
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            comps.append(sorted(cells))
    return comps


def parse(inp):
    """Return (model, others); each part is a dict with anchor/shape/marks."""
    parts = []
    for cells in components(inp):
        anchor = [p for p in cells if inp[p[0]][p[1]] == ANCHOR]
        if len(anchor) != 1:
            return None
        a = anchor[0]
        parts.append({
            "anchor": a,
            "cells": cells,
            "shape": {(y - a[0], x - a[1]) for y, x in cells
                      if inp[y][x] in (SHAPE, ANCHOR)},
            "marks": [((y - a[0], x - a[1]), inp[y][x]) for y, x in cells
                      if inp[y][x] in MARKS],
        })
    models = [p for p in parts if p["marks"]]
    if len(models) != 1:
        return None
    others = [p for p in parts if not p["marks"]]
    return models[0], others


def find_d(model, part, with_anchor=True):
    """Indices of D4 elements carrying the model shape onto the part."""
    found = []
    for i, f in enumerate(D4):
        if with_anchor:
            if {f(*p) for p in model["shape"]} == part["shape"]:
                found.append(i)
        else:
            a = {f(*p) for p in model["shape"] if p != (0, 0)}
            b = {p for p in part["shape"] if p != (0, 0)}
            if a == b:
                found.append(i)
    return found


def stamp(inp, base, placements, overwrite=False):
    """placements: list of (row, col, color). Draw onto a copy of base."""
    g = [row[:] for row in base]
    for r, c, col in placements:
        if 0 <= r < len(g) and 0 <= c < len(g[0]):
            if overwrite or inp[r][c] == 0:
                g[r][c] = col
    return g


def carry(inp, choose, offset_of=None, overwrite=False, only_color=None,
          swap=False, base=None):
    """Carry the model marks to every other part.

    choose(model, part) returns the index of the D4 element to use (or None).
    offset_of(part) gives the origin the marks are placed from.
    """
    pr = parse(inp)
    if pr is None:
        return None
    model, others = pr
    pl = []
    for part in others:
        d = choose(model, part)
        if d is None:
            return None
        o = offset_of(part) if offset_of else part["anchor"]
        for (dy, dx), col in model["marks"]:
            if only_color is not None and col != only_color:
                continue
            if swap:
                col = 4 - col
            y, x = D4[d](dy, dx)
            pl.append((o[0] + y, o[1] + x, col))
    return stamp(inp, base if base is not None else inp, pl, overwrite)


def true_d(model, part):
    f = find_d(model, part)
    return f[0] if f else None


def guard(g, out):
    if g is None or g == out:
        return None
    return g


# ---- readings ----

def r_no_ones(inp, out):
    g = [row[:] for row in out]
    for r in range(len(g)):
        for c in range(len(g[0])):
            if out[r][c] == 1 and inp[r][c] == 0:
                g[r][c] = 0
    return guard(g, out)


def r_no_threes(inp, out):
    g = [row[:] for row in out]
    for r in range(len(g)):
        for c in range(len(g[0])):
            if out[r][c] == 3 and inp[r][c] == 0:
                g[r][c] = 0
    return guard(g, out)


def r_swap_colors(inp, out):
    g = [row[:] for row in out]
    for r in range(len(g)):
        for c in range(len(g[0])):
            if inp[r][c] == 0 and out[r][c] in MARKS:
                g[r][c] = 4 - out[r][c]
    return guard(g, out)


def r_skip_last_part(inp, out):
    # the marks drawn around the last part in reading order are left out
    if parse(inp) is None:
        return None
    h, w = len(inp), len(inp[0])
    best = None
    for cells in components(inp):
        zone = {(y + dy, x + dx) for y, x in cells
                for dy in range(-3, 4) for dx in range(-3, 4)}
        gained = [(y, x) for y, x in zone
                  if 0 <= y < h and 0 <= x < w and inp[y][x] == 0
                  and out[y][x] != 0]
        if gained:
            best = gained
    if best is None:
        return None
    g = [row[:] for row in out]
    for y, x in best:
        g[y][x] = 0
    return guard(g, out)


def r_translate_only(inp, out):
    return guard(carry(inp, lambda m, p: 0), out)


def r_inverse_transform(inp, out):
    def ch(m, p):
        d = true_d(m, p)
        return None if d is None else INVERSE[d]
    return guard(carry(inp, ch), out)


def r_flip_only(inp, out):
    # treat every copy as a horizontal mirror of the model
    return guard(carry(inp, lambda m, p: 4), out)


def r_transpose_only(inp, out):
    return guard(carry(inp, lambda m, p: 6), out)


def r_extra_transpose(inp, out):
    # the right transform, followed by an extra transpose
    def ch(m, p):
        d = true_d(m, p)
        if d is None:
            return None
        pts = [(1, 2), (3, -5)]
        want = [D4[6](*D4[d](*q)) for q in pts]
        for i, f in enumerate(D4):
            if [f(*q) for q in pts] == want:
                return i
        return None
    return guard(carry(inp, ch), out)


def r_rotate_180(inp, out):
    return guard(carry(inp, lambda m, p: 2), out)


def r_bbox_origin(inp, out):
    # marks measured from the part's bounding-box top-left, not the anchor,
    # with the model measured the same way; no transform
    pr = parse(inp)
    if pr is None:
        return None
    model, others = pr

    def tl(cells):
        return (min(y for y, x in cells), min(x for y, x in cells))
    ma = model["anchor"]
    mt = tl(model["cells"])
    pl = []
    for part in others:
        t = tl(part["cells"])
        for (dy, dx), col in model["marks"]:
            y = ma[0] + dy - mt[0]
            x = ma[1] + dx - mt[1]
            pl.append((t[0] + y, t[1] + x, col))
    return guard(stamp(inp, inp, pl), out)


def r_erase_model_marks(inp, out):
    # marks are moved to the copies instead of copied
    pr = parse(inp)
    if pr is None:
        return None
    model = pr[0]
    g = [row[:] for row in out]
    a = model["anchor"]
    for (dy, dx), col in model["marks"]:
        g[a[0] + dy][a[1] + dx] = 0
    return guard(g, out)


def r_only_ones_on_copies(inp, out):
    # carry only color 1 through the transform, keep the true result for 3
    def ch(m, p):
        return true_d(m, p)
    g = carry(inp, ch, only_color=1)
    return guard(g, out)


def r_overwrite(inp, out):
    # marks overwrite shape cells too (not only background)
    return guard(carry(inp, true_d, overwrite=True), out)


ALTERNATIVES = [
    ("fill only the 3 marks, leave the 1 marks out", r_no_ones),
    ("fill only the 1 marks, leave the 3 marks out", r_no_threes),
    ("swap colors 1 and 3 on the carried marks", r_swap_colors),
    ("leave the last receiving part without marks", r_skip_last_part),
    ("copy marks by translation only, no rotation or reflection", r_translate_only),
    ("apply the inverse of the right transform to the marks", r_inverse_transform),
    ("treat every part as a left-right mirror of the model", r_flip_only),
    ("treat every part as a transpose of the model", r_transpose_only),
    ("apply the right transform, then an extra transpose", r_extra_transpose),
    ("treat every part as the model turned 180 degrees", r_rotate_180),
    ("measure marks from the bounding-box corner instead of the 2", r_bbox_origin),
    ("move the marks off the model instead of copying them", r_erase_model_marks),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3]
                       / "data/tasks/36d67576.json").read_text())
    train = task["train"]
    # sanity: the true reading reproduces every train output
    for i, p in enumerate(train):
        t = carry(p["input"], true_d)
        assert t == p["output"], f"true reading mismatch on pair {i}"
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            ok = (isinstance(g, list) and g and all(
                isinstance(row, list) and len(row) == len(g[0])
                and all(isinstance(v, int) and 0 <= v <= 9 for v in row)
                for row in g) and g != p["output"])
            n += bool(ok)
        print(f"{n}/{len(train)}  {desc}")
