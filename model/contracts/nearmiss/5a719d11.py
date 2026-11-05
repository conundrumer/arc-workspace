"""Near-miss readings for ARC task 5a719d11.

The grid holds panels separated by all-0 divider lines. Each panel has a
ground color (its commonest color) and marks (the other cells). Panels in
the same row band pair across the vertical divider. In the true output each
panel shows its partner's mark shape, at the same cell positions, drawn in
the partner's ground color on the panel's own ground.
"""
import json
from collections import Counter
from pathlib import Path


def bands(flags):
    runs, start = [], None
    for i, f in enumerate(flags):
        if not f and start is None:
            start = i
        if f and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(flags)))
    return runs


def layout(g):
    h, w = len(g), len(g[0])
    rows = bands([all(v == 0 for v in g[r]) for r in range(h)])
    cols = bands([all(g[r][c] == 0 for r in range(h)) for c in range(w)])
    return rows, cols


def ground(g, rb, cb):
    cnt = Counter(g[r][c] for r in range(*rb) for c in range(*cb))
    return cnt.most_common(1)[0][0]


def marks(g, rb, cb):
    """Set of (dr, dc) offsets of mark cells in the panel, plus the mark colors."""
    gr = ground(g, rb, cb)
    pos = {}
    for r in range(*rb):
        for c in range(*cb):
            if g[r][c] != gr:
                pos[(r - rb[0], c - cb[0])] = g[r][c]
    return pos


def paint(g, rb, cb, shape, color, gr, keep=None):
    """Redraw one panel: ground gr, then shape cells in color(pos)."""
    for r in range(*rb):
        for c in range(*cb):
            g[r][c] = gr
    for (dr, dc) in shape:
        r, c = rb[0] + dr, cb[0] + dc
        if r < rb[1] and c < cb[1] and 0 <= dr and 0 <= dc:
            g[r][c] = color


def horizontal_pairs(inp):
    rows, cols = layout(inp)
    if len(cols) != 2:
        return None
    return [(rb, cols[0], cols[1]) for rb in rows]


def transform(inp, shape_tf=lambda s, rb, cb: s, color_mode="partner_ground",
              keep_own=False, only_bands=None, only_side=None, swap_ground=False):
    pairs = horizontal_pairs(inp)
    if pairs is None:
        return None
    g = [row[:] for row in inp]
    for bi, (rb, lc, rc) in enumerate(pairs):
        if only_bands is not None and bi not in only_bands:
            continue
        panels = {"L": (rb, lc), "R": (rb, rc)}
        info = {}
        for k, (r_, c_) in panels.items():
            info[k] = (ground(inp, r_, c_), marks(inp, r_, c_))
        for k, o in (("L", "R"), ("R", "L")):
            if only_side is not None and k != only_side:
                continue
            r_, c_ = panels[k]
            og, om = info[o]
            sg, sm = info[k]
            shape = shape_tf(list(om.keys()), r_, c_)
            if color_mode == "partner_ground":
                color = og
            elif color_mode == "partner_mark":
                color = next(iter(om.values())) if om else og
            elif color_mode == "own_mark":
                color = next(iter(sm.values())) if sm else sg
            elif color_mode == "own_ground":
                color = sg
            else:
                color = og
            new_ground = og if swap_ground else sg
            paint(g, r_, c_, shape, color, new_ground)
            if keep_own:
                for (dr, dc), v in sm.items():
                    g[r_[0] + dr][c_[0] + dc] = v
    return g


def width_of(cb):
    return cb[1] - cb[0]


def height_of(rb):
    return rb[1] - rb[0]


# ---- readings -------------------------------------------------------------

def own_mark_color(inp, out):
    return transform(inp, color_mode="own_mark")


def partner_mark_color(inp, out):
    return transform(inp, color_mode="partner_mark")


def whole_panel_swap(inp, out):
    return transform(inp, swap_ground=True, color_mode="partner_mark")


def mirrored_horizontally(inp, out):
    def tf(s, rb, cb):
        w = width_of(cb)
        return [(dr, w - 1 - dc) for dr, dc in s]
    return transform(inp, shape_tf=tf)


def mirrored_vertically(inp, out):
    def tf(s, rb, cb):
        h = height_of(rb)
        return [(h - 1 - dr, dc) for dr, dc in s]
    return transform(inp, shape_tf=tf)


def shifted_one_column(inp, out):
    return transform(inp, shape_tf=lambda s, rb, cb: [(dr, dc + 1) for dr, dc in s])


def only_first_band(inp, out):
    return transform(inp, only_bands={0})


def only_left_panel_receives(inp, out):
    return transform(inp, only_side="L")


def union_with_own_marks(inp, out):
    return transform(inp, keep_own=True)


def marks_in_own_ground_color(inp, out):
    """Marks vanish: partner's shape painted in this panel's own ground."""
    return transform(inp, color_mode="own_ground")


def pair_vertically(inp, out):
    """Pair panels across the horizontal divider instead (band 0 with band 1)."""
    rows, cols = layout(inp)
    if len(rows) < 2:
        return None
    g = [row[:] for row in inp]
    for i in range(0, len(rows) - 1, 2):
        for cb in cols:
            a, b = rows[i], rows[i + 1]
            if height_of(a) != height_of(b):
                continue
            ga, gb = ground(inp, a, cb), ground(inp, b, cb)
            ma, mb = marks(inp, a, cb), marks(inp, b, cb)
            paint(g, a, cb, list(mb.keys()), gb, ga)
            paint(g, b, cb, list(ma.keys()), ga, gb)
    return g


def erase_all_marks(inp, out):
    rows, cols = layout(inp)
    g = [row[:] for row in inp]
    for rb in rows:
        for cb in cols:
            gr = ground(inp, rb, cb)
            for r in range(*rb):
                for c in range(*cb):
                    g[r][c] = gr
    return g


ALTERNATIVES = [
    ("partner's shape drawn in this panel's own original mark color", own_mark_color),
    ("partner's shape drawn in the partner's own mark color", partner_mark_color),
    ("whole panels exchanged: partner's ground too, not only the marks", whole_panel_swap),
    ("partner's shape mirrored left-right inside the panel", mirrored_horizontally),
    ("partner's shape mirrored top-bottom inside the panel", mirrored_vertically),
    ("partner's shape shifted one column right (off-by-one offset)", shifted_one_column),
    ("exchange applied only in the first row band of panels", only_first_band),
    ("only the left panel of each pair receives the partner's shape", only_left_panel_receives),
    ("partner's shape added to the panel while its own marks stay", union_with_own_marks),
    ("partner's shape drawn in the panel's own ground, so marks vanish", marks_in_own_ground_color),
    ("panels paired across the horizontal divider instead of the vertical one", pair_vertically),
    ("every panel emptied to its ground color", erase_all_marks),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/5a719d11.json"))
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(train)}  {desc}")
