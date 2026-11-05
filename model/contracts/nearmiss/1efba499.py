"""Near-miss readings for ARC task 1efba499.

Rule: the most common non-background color forms a wall (a thick bar). The wall's
shorter bounding-box extent gives the axis that other pixels sit beyond it on.
Other-colored pixels on opposite sides of the wall in the same line swap: each
lands in the cell touching the wall on the far side, with the partner's color,
and the originals vanish. Pixels with no partner stay where they are.
"""
import json
from collections import Counter
from pathlib import Path


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _solve_vertical(inp, keep_orig=False, drop_unpaired=False, mirror=False,
                    gap=0, shift=0, only_low=False,
                    any_pixel=False):
    """Wall-crossing solver with the movement along rows (columns are lines)."""
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    others = [(n, c) for c, n in cnt.items() if c != bg]
    wall = max(others)[1]
    out = [[bg] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if inp[y][x] == wall:
                out[y][x] = wall
    for x in range(w):
        wy = [y for y in range(h) if inp[y][x] == wall]
        loose = [(y, inp[y][x]) for y in range(h)
                 if inp[y][x] not in (bg, wall)]
        if not wy:
            for y, c in loose:
                out[y][x] = c
            continue
        top, bot = min(wy), max(wy)
        above = [(y, c) for y, c in loose if y < top]
        below = [(y, c) for y, c in loose if y > bot]
        inside = [(y, c) for y, c in loose if top <= y <= bot]
        for y, c in inside:
            out[y][x] = c
        paired = bool(above and below)
        tx = x + shift
        if paired:
            if keep_orig:
                for y, c in above + below:
                    out[y][x] = c
            ca = above[-1][1]
            cb = below[0][1]
            up_c, dn_c = cb, ca
            if only_low:
                up_c = None
            ty, by = top - 1 - gap, bot + 1 + gap
            if mirror:
                for y, c in above:
                    out[top + bot - y][x] = c
                for y, c in below:
                    out[top + bot - y][x] = c
            elif 0 <= tx < w:
                if up_c is not None and 0 <= ty < h:
                    out[ty][tx] = up_c
                if 0 <= by < h:
                    out[by][tx] = dn_c
            if only_low:
                for y, c in above:
                    out[y][x] = c
        else:
            if drop_unpaired:
                continue
            for y, c in loose:
                out[y][x] = c
            if any_pixel and loose:
                for y, c in above:
                    out[y][x] = bg
                for y, c in below:
                    out[y][x] = bg
                if above:
                    out[bot + 1][x] = above[-1][1]
                if below:
                    out[top - 1][x] = below[0][1]
    return out


def _orient(inp):
    """Return True when the wall's shorter bounding-box extent is along rows."""
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    wall = max((n, c) for c, n in cnt.items() if c != bg)[1]
    ys = [y for y, r in enumerate(inp) for v in r if v == wall]
    xs = [x for r in inp for x, v in enumerate(r) if v == wall]
    return (max(ys) - min(ys)) <= (max(xs) - min(xs))


def _solve(inp, axis_flip=False, **kw):
    vert = _orient(inp) != axis_flip
    if vert:
        return _solve_vertical(inp, **kw)
    return _transpose(_solve_vertical(_transpose(inp), **kw))


def _cnt_bg_wall(inp):
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    wall = max((n, c) for c, n in cnt.items() if c != bg)[1]
    return bg, wall


def correct(inp, out):
    return _solve(inp)


def alt_wrong_axis(inp, out):
    return _solve(inp, axis_flip=True)


def alt_same_side(inp, out):
    # pixels move next to the wall on their own side, keeping their color
    h, w = len(inp), len(inp[0])
    bg, wall = _cnt_bg_wall(inp)
    res = _solve(inp)
    vert = _orient(inp)
    g = [row[:] for row in inp] if vert else _transpose(inp)
    r = res if vert else _transpose(res)
    hh, ww = len(g), len(g[0])
    o = [row[:] for row in g]
    for x in range(ww):
        wy = [y for y in range(hh) if g[y][x] == wall]
        if not wy:
            continue
        top, bot = min(wy), max(wy)
        above = [y for y in range(top) if g[y][x] not in (bg, wall)]
        below = [y for y in range(bot + 1, hh) if g[y][x] not in (bg, wall)]
        if above and below:
            for y in above + below:
                o[y][x] = bg
            o[top - 1][x] = g[above[-1]][x]
            o[bot + 1][x] = g[below[0]][x]
    return o if vert else _transpose(o)


def alt_keep_originals(inp, out):
    return _solve(inp, keep_orig=True)


def alt_drop_unpaired(inp, out):
    return _solve(inp, drop_unpaired=True)


def alt_mirror(inp, out):
    # paired pixels are reflected through the wall's center line
    return _solve(inp, mirror=True)


def alt_gap_one(inp, out):
    return _solve(inp, gap=1)


def alt_shift_one(inp, out):
    return _solve(inp, shift=1)


def alt_only_one_side(inp, out):
    return _solve(inp, only_low=True)


def alt_unpaired_cross(inp, out):
    return _solve(inp, any_pixel=True)


def alt_fill_wall_box(inp, out):
    # wall is filled to its whole bounding box
    bg, wall = _cnt_bg_wall(inp)
    ys = [y for y, r in enumerate(inp) for v in r if v == wall]
    xs = [x for r in inp for x, v in enumerate(r) if v == wall]
    o = [r[:] for r in out]
    for y in range(min(ys), max(ys) + 1):
        for x in range(min(xs), max(xs) + 1):
            o[y][x] = wall
    return o


def alt_wall_least_common(inp, out):
    # the rarest non-background color is taken as the wall
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    cols = sorted((n, c) for c, n in cnt.items() if c != bg)
    wall = cols[0][1]
    o = [[bg if v != wall else v for v in r] for r in inp]
    return o


def alt_unchanged(inp, out):
    return [r[:] for r in inp]


ALTERNATIVES = [
    ("movement axis taken along the wall's longer extent", alt_wrong_axis),
    ("pixels with a partner move next to the wall on their own side", alt_same_side),
    ("original pixels are left in place besides the moved ones", alt_keep_originals),
    ("pixels with no partner on the opposite side are deleted", alt_drop_unpaired),
    ("paired pixels are mirrored through the wall center instead of touching it", alt_mirror),
    ("moved pixels land one cell away from the wall", alt_gap_one),
    ("moved pixels land one line off along the wall", alt_shift_one),
    ("only one side's pixels are moved, the other side stays", alt_only_one_side),
    ("lone pixels without a partner also jump to the far side", alt_unpaired_cross),
    ("wall is filled out to its bounding box", alt_fill_wall_box),
    ("rarest non-background color taken as the wall, other pixels dropped", alt_wall_least_common),
    ("input returned unchanged", alt_unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/1efba499.json").read_text())
    train = task["train"]
    print("correct reproduces outputs:",
          all(correct(p["input"], p["output"]) == p["output"] for p in train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
