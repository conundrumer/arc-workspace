import json
from pathlib import Path


def _segments(flags):
    segs, start = [], None
    for i, f in enumerate(flags + [True]):
        if not f and start is None:
            start = i
        if f and start is not None:
            segs.append((start, i))
            start = None
    return segs


def _layout(inp):
    h, w = len(inp), len(inp[0])
    row_div = [len(set(r)) == 1 and r[0] != 0 for r in inp]
    col_div = [len(set(inp[r][c] for r in range(h))) == 1 and inp[0][c] != 0 for c in range(w)]
    rsegs, csegs = _segments(row_div), _segments(col_div)
    panels = [(r0, r1, c0, c1) for (r0, r1) in rsegs for (c0, c1) in csegs]
    src = None
    for p in panels:
        r0, r1, c0, c1 = p
        if any(inp[r][c] for r in range(r0, r1) for c in range(c0, c1)):
            src = p
    return rsegs, csegs, panels, src, row_div, col_div


def _grid(inp):
    return [list(r) for r in inp]


def _block(inp, p):
    r0, r1, c0, c1 = p
    return [list(inp[r][c0:c1]) for r in range(r0, r1)]


def _paste(g, p, block):
    r0, r1, c0, c1 = p
    for i, r in enumerate(range(r0, r1)):
        for j, c in enumerate(range(c0, c1)):
            g[r][c] = block[i][j]


def _fill(inp, targets_fn, xform=lambda b: b, clear_src=False):
    rsegs, csegs, panels, src, _, _ = _layout(inp)
    g = _grid(inp)
    blk = xform(_block(inp, src))
    for p in targets_fn(panels, src, rsegs, csegs):
        _paste(g, p, blk)
    if clear_src:
        _paste(g, src, [[0] * (src[3] - src[2]) for _ in range(src[1] - src[0])])
    return g


def same_row_only(inp, out):
    return _fill(inp, lambda ps, s, rs, cs: [p for p in ps if p[0] == s[0]])


def same_col_only(inp, out):
    return _fill(inp, lambda ps, s, rs, cs: [p for p in ps if p[2] == s[2]])


def all_but_last(inp, out):
    return _fill(inp, lambda ps, s, rs, cs: ps[:-1])


def mirror_lr(inp, out):
    return _fill(inp, lambda ps, s, rs, cs: ps, lambda b: [r[::-1] for r in b])


def mirror_ud(inp, out):
    return _fill(inp, lambda ps, s, rs, cs: ps, lambda b: b[::-1])


def rotate_180(inp, out):
    return _fill(inp, lambda ps, s, rs, cs: ps, lambda b: [r[::-1] for r in b[::-1]])


def move_not_copy(inp, out):
    return _fill(inp, lambda ps, s, rs, cs: [p for p in ps if p != s], clear_src=True)


def erase_dividers(inp, out):
    g = [list(r) for r in out]
    _, _, _, _, rd, cd = _layout(inp)
    for r in range(len(g)):
        for c in range(len(g[0])):
            if rd[r] or cd[c]:
                g[r][c] = 0
    return g


def shift_right_one(inp, out):
    def sh(b):
        return [[0] + r[:-1] for r in b]
    return _fill(inp, lambda ps, s, rs, cs: ps, sh)


def panel_one_short(inp, out):
    # panel size read as one less on each axis: last row and column of each copy stay blank
    def cut(b):
        b = [r[:-1] + [0] for r in b[:-1]] + [[0] * len(b[0])]
        return b
    return _fill(inp, lambda ps, s, rs, cs: ps, cut)


def one_color_copies(inp, out):
    rsegs, csegs, panels, src, _, _ = _layout(inp)
    blk = _block(inp, src)
    cols = sorted({v for r in blk for v in r if v})
    k = cols[0]
    g = _fill(inp, lambda ps, s, rs, cs: ps, lambda b: [[k if v else 0 for v in r] for r in b])
    _paste(g, src, blk)
    return g


def copy_to_other_row_only(inp, out):
    # copies into the panel row away from the source but not along the source's own row
    rsegs, csegs, panels, src, _, _ = _layout(inp)
    g = _grid(inp)
    blk = _block(inp, src)
    for p in panels:
        if p[0] != src[0]:
            _paste(g, p, blk)
    return g


ALTERNATIVES = [
    ("copy the drawn panel only into panels in its own panel row", same_row_only),
    ("copy the drawn panel only into panels in its own panel column", same_col_only),
    ("copy the drawn panel into every panel except the last in reading order", all_but_last),
    ("copies are the drawn panel mirrored left to right", mirror_lr),
    ("copies are the drawn panel flipped top to bottom", mirror_ud),
    ("copies are the drawn panel rotated 180 degrees", rotate_180),
    ("move the drawn panel to the others: the original panel is cleared", move_not_copy),
    ("divider lines are erased in the output", erase_dividers),
    ("copies are offset one column to the right inside each panel", shift_right_one),
    ("panel size is read as one too small: last row and column of each copy stay blank", panel_one_short),
    ("copies are drawn in a single color, the lowest color of the drawn panel", one_color_copies),
    ("copy the drawn panel only into panels in other panel rows", copy_to_other_row_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/c444b776.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
