"""Near-miss readings for 8886d717.

Rule: grid has a background-colored edge line (9) along one side, a big shape
of color 2, and scattered 8 marks. A mark inside the 2-shape is absorbed (becomes 2).
A mark in the 7 background stays and copies itself one cell toward the 9 line.
"""
import json
from collections import Counter
from pathlib import Path

MARK = 8
EDGE = 9
DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


def edge_dir(inp):
    h, w = len(inp), len(inp[0])
    if all(c == EDGE for c in inp[0]):
        return (-1, 0)
    if all(c == EDGE for c in inp[-1]):
        return (1, 0)
    if all(r[0] == EDGE for r in inp):
        return (0, -1)
    if all(r[-1] == EDGE for r in inp):
        return (0, 1)
    return None


def marks(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == MARK]


def region_color(inp, r, c):
    h, w = len(inp), len(inp[0])
    cnt = Counter()
    for dr, dc in DIRS.values():
        rr, cc = r + dr, c + dc
        if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] not in (MARK, EDGE):
            cnt[inp[rr][cc]] += 1
    return cnt.most_common(1)[0][0] if cnt else None


def build(inp, absorb=True, extend_in_bg=True, extend_in_shape=False, steps=1,
          direction="edge", fill_bg=None, shape_fill=None, plus=False):
    ed = edge_dir(inp)
    if ed is None:
        return None
    if direction == "away":
        d = (-ed[0], -ed[1])
    elif direction == "turn":
        d = (ed[1], -ed[0])
    else:
        d = ed
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    ms = marks(inp)
    info = [(r, c, region_color(inp, r, c)) for r, c in ms]
    for r, c, col in info:
        if col != 7 and absorb:
            g[r][c] = col if shape_fill is None else shape_fill
    for r, c, col in info:
        inshape = col != 7
        if (inshape and not extend_in_shape) or (not inshape and not extend_in_bg):
            continue
        dirs = list(DIRS.values()) if plus else [d]
        for dd in dirs:
            for s in range(1, steps + 1):
                rr, cc = r + dd[0] * s, c + dd[1] * s
                if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] != EDGE:
                    g[rr][cc] = MARK
    return g


def no_absorb(inp, out):
    return build(inp, absorb=False)


def extend_everywhere(inp, out):
    return build(inp, extend_in_shape=True)


def away_from_edge(inp, out):
    return build(inp, direction="away")


def two_steps(inp, out):
    return build(inp, steps=2)


def to_wall(inp, out):
    h, w = len(inp), len(inp[0])
    return build(inp, steps=max(h, w))


def no_copy(inp, out):
    return build(inp, extend_in_bg=False)


def perpendicular(inp, out):
    return build(inp, direction="turn")


def absorb_as_background(inp, out):
    return build(inp, shape_fill=7)


def plus_shape(inp, out):
    return build(inp, plus=True)


def edge_erased(inp, out):
    ed = edge_dir(inp)
    if ed is None:
        return None
    g = [row[:] for row in out]
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v == EDGE:
                g[r][c] = 7
    return g


def absorb_and_extend_in_shape_only(inp, out):
    return build(inp, extend_in_bg=False, extend_in_shape=True)


ALTERNATIVES = [
    ("marks inside the 2-shape are left as 8 instead of absorbed", no_absorb),
    ("marks in the 2-shape also copy toward the edge line", extend_everywhere),
    ("marks copy away from the edge line", away_from_edge),
    ("marks copy two cells toward the edge line", two_steps),
    ("marks extend as a ray all the way to the edge line", to_wall),
    ("marks in the background are kept but not copied; only absorption applies", no_copy),
    ("marks copy a quarter turn from the edge direction", perpendicular),
    ("absorbed marks become background 7 instead of the shape color", absorb_as_background),
    ("marks copy to all four neighbors", plus_shape),
    ("edge line is erased to background", edge_erased),
    ("only marks in the 2-shape copy toward the edge; background marks do not", absorb_and_extend_in_shape_only),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/8886d717.json"))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, f in ALTERNATIVES:
        n = sum(1 for p in train if valid(f(p["input"], p["output"]), p["output"]))
        print(f"{n}/{len(train)}  {desc}")
