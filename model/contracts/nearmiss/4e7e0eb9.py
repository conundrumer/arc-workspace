"""Near-miss readings for ARC task 4e7e0eb9.

The grid holds one or more 9x9 sections (stacked at stride 10). Each section
has four 3x3 blocks. A mid row or mid column of the section that carries an
ink cell away from the crossing cell is a divider: the blocks swap across it.
A section without a divider takes the one non-majority color in every block.
"""
import json
from collections import Counter
from pathlib import Path

BG = 0
# block order: tl, tr, bl, br
ORIGINS = [(1, 1), (1, 5), (5, 1), (5, 5)]


def _sections(inp):
    secs = []
    for r0 in range(0, len(inp), 10):
        for c0 in range(0, len(inp[0]), 10):
            mr, mc = r0 + 4, c0 + 4
            row = [inp[mr][c0 + j] for j in range(9)]
            col = [inp[r0 + i][mc] for i in range(9)]
            secs.append({
                "r0": r0, "c0": c0,
                "h": any(v != BG for j, v in enumerate(row) if j != 4),
                "v": any(v != BG for i, v in enumerate(col) if i != 4),
                "h_incl": any(v != BG for v in row),
                "v_incl": any(v != BG for v in col),
                "blocks": [inp[r0 + a][c0 + b] for a, b in ORIGINS],
            })
    return secs


def _swap_tb(c):
    return [c[2], c[3], c[0], c[1]]


def _swap_lr(c):
    return [c[1], c[0], c[3], c[2]]


def _odd(c):
    top = Counter(c).most_common(1)[0][0]
    rest = [v for v in c if v != top]
    return rest[0] if rest else top


def _majority(c):
    return Counter(c).most_common(1)[0][0]


def _build(inp, fn):
    g = [list(r) for r in inp]
    secs = _sections(inp)
    for s in secs:
        new = fn(s, secs)
        for (a, b), col in zip(ORIGINS, new):
            for i in range(3):
                for j in range(3):
                    g[s["r0"] + a + i][s["c0"] + b + j] = col
    return g


def _true_blocks(s, h=None, v=None, fill=_odd):
    h = s["h"] if h is None else h
    v = s["v"] if v is None else v
    c = s["blocks"]
    if not h and not v:
        return [fill(c)] * 4
    if h:
        c = _swap_tb(c)
    if v:
        c = _swap_lr(c)
    return c


def _wrap(fn):
    def f(inp, out):
        g = fn(inp, out)
        return g if g != out else None
    return f


@_wrap
def swap_wrong_axis(inp, out):
    def fn(s, _):
        if not s["h"] and not s["v"]:
            return _true_blocks(s)
        return _true_blocks(s, h=s["v"], v=s["h"])
    return _build(inp, fn)


@_wrap
def undivided_unchanged(inp, out):
    def fn(s, _):
        if not s["h"] and not s["v"]:
            return s["blocks"]
        return _true_blocks(s)
    return _build(inp, fn)


@_wrap
def undivided_majority_color(inp, out):
    return _build(inp, lambda s, _: _true_blocks(s, fill=_majority))


@_wrap
def undivided_rotated(inp, out):
    def fn(s, _):
        if not s["h"] and not s["v"]:
            return _swap_lr(_swap_tb(s["blocks"]))
        return _true_blocks(s)
    return _build(inp, fn)


@_wrap
def crossing_cell_counts(inp, out):
    def fn(s, _):
        return _true_blocks(s, h=s["h_incl"], v=s["v_incl"])
    return _build(inp, fn)


@_wrap
def swap_first_row_or_col_only(inp, out):
    def fn(s, _):
        c = s["blocks"]
        if not s["h"] and not s["v"]:
            return _true_blocks(s)
        c = list(c)
        if s["h"]:
            c[0], c[2] = c[2], c[0]
        if s["v"]:
            c[0], c[1] = c[1], c[0]
        return c
    return _build(inp, fn)


@_wrap
def transpose_blocks(inp, out):
    def fn(s, _):
        if not s["h"] and not s["v"]:
            return _true_blocks(s)
        c = s["blocks"]
        return [c[0], c[2], c[1], c[3]]
    return _build(inp, fn)


@_wrap
def fill_top_row_only(inp, out):
    def fn(s, _):
        if not s["h"] and not s["v"]:
            c = s["blocks"]
            o = _odd(c)
            return [o, o, c[2], c[3]]
        return _true_blocks(s)
    return _build(inp, fn)


@_wrap
def divider_status_shared(inp, out):
    def fn(s, secs):
        h = any(t["h"] for t in secs)
        v = any(t["v"] for t in secs)
        return _true_blocks(s, h=h, v=v)
    return _build(inp, fn)


@_wrap
def crop_outer_ring(inp, out):
    return [r[1:-1] for r in out[1:-1]]


@_wrap
def fill_overreach_gaps(inp, out):
    g = [list(r) for r in out]
    for s in _sections(inp):
        if not s["h"] and not s["v"]:
            o = _odd(s["blocks"])
            for i in range(1, 8):
                for j in range(1, 8):
                    g[s["r0"] + i][s["c0"] + j] = o
    return g


ALTERNATIVES = [
    ("swap blocks across the wrong axis for dividered sections", swap_wrong_axis),
    ("leave sections without a divider as they are", undivided_unchanged),
    ("fill undivided sections with the majority color instead of the odd color", undivided_majority_color),
    ("rotate the blocks of undivided sections by 180 degrees instead of filling", undivided_rotated),
    ("count the crossing cell as ink, so every marked section swaps on both axes", crossing_cell_counts),
    ("swap only the first row or column of blocks across a divider", swap_first_row_or_col_only),
    ("transpose the blocks of dividered sections instead of swapping across the divider", transpose_blocks),
    ("fill only the top row of blocks in undivided sections", fill_top_row_only),
    ("apply the dividers found anywhere in the grid to every section", divider_status_shared),
    ("drop the outer ring of cells from the output", crop_outer_ring),
    ("fill undivided sections over the gaps between blocks too", fill_overreach_gaps),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / "data/tasks/4e7e0eb9.json"
    train = json.load(open(path))["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
