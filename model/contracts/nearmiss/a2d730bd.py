"""Near-miss readings for ARC task a2d730bd.

Rule: each lone dot lies in line with a solid rectangle of its own color.
The dot is erased. A line of the dot's color joins the block to the dot, a
T-shaped foot (the face cell and its two side neighbors) sits against the
block, and an arrowhead (the dot's two side neighbors and the cell beyond)
marks the dot's place.
"""
import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _components(g, bg):
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            col = g[r][c]
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and g[ny][nx] == col:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append((col, cells))
    return comps


def _parse(g):
    """Return (bg, dots) where each dot is (r, c, color, d, block box, step)."""
    h, w = len(g), len(g[0])
    bg = _bg(g)
    comps = _components(g, bg)
    blocks = []
    for col, cells in comps:
        rs = [y for y, _ in cells]
        cs = [x for _, x in cells]
        r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
        if r1 - r0 >= 1 and c1 - c0 >= 1 and len(cells) == (r1 - r0 + 1) * (c1 - c0 + 1):
            blocks.append((col, r0, r1, c0, c1))
    dots = []
    for col, cells in comps:
        if len(cells) != 1:
            continue
        r, c = cells[0]
        if any(
            0 <= r + dy < h and 0 <= c + dx < w and (dy or dx) and g[r + dy][c + dx] != bg
            for dy in (-1, 0, 1) for dx in (-1, 0, 1)
        ):
            continue
        best = None
        for bcol, r0, r1, c0, c1 in blocks:
            if bcol != col:
                continue
            if r0 <= r <= r1:
                d = (0, 1) if c > c1 else (0, -1)
                gap = c - c1 if c > c1 else c0 - c
            elif c0 <= c <= c1:
                d = (1, 0) if r > r1 else (-1, 0)
                gap = r - r1 if r > r1 else r0 - r
            else:
                continue
            if best is None or gap < best[0]:
                best = (gap, d, (r0, r1, c0, c1))
        if best:
            dots.append((r, c, col, best[1], best[2], best[0]))
    return bg, dots


def _draw(inp, head="full", foot="full", clear=True, line="full",
          foot_shift=0, foot_half=1, only_axis=None, through=False,
          to_edge=False, ring=False):
    g = [list(r) for r in inp]
    h, w = len(g), len(g[0])
    bg, dots = _parse(inp)

    def put(y, x, v):
        if 0 <= y < h and 0 <= x < w:
            g[y][x] = v

    for r, c, col, d, box, gap in dots:
        horiz = d[0] == 0
        if only_axis == "h" and not horiz:
            continue
        if only_axis == "v" and horiz:
            continue
        p = (d[1], d[0])  # perpendicular
        if clear:
            put(r, c, bg)
        # face cell is gap-1 steps back from the dot along -d
        fy, fx = r - d[0] * (gap - 1), c - d[1] * (gap - 1)
        if line != "none":
            stop = 1 if line == "full" else 2
            for k in range(stop, gap):
                put(r - d[0] * k, c - d[1] * k, col)
        if foot != "none":
            cy, cx = fy + d[0] * foot_shift, fx + d[1] * foot_shift
            put(cy, cx, col)
            for s in range(1, foot_half + 1):
                put(cy + p[0] * s, cx + p[1] * s, col)
                put(cy - p[0] * s, cx - p[1] * s, col)
        if through:
            r0, r1, c0, c1 = box
            span = (r1 - r0 + 1) if not horiz else (c1 - c0 + 1)
            by, bx = fy - d[0] * (span + 1), fx - d[1] * (span + 1)
            put(by, bx, col)
            put(by + p[0], bx + p[1], col)
            put(by - p[0], bx - p[1], col)
        if head != "none":
            put(r + p[0], c + p[1], col)
            put(r - p[0], c - p[1], col)
            if head == "full":
                put(r + d[0], c + d[1], col)
        if ring:
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy or dx:
                        put(r + dy, c + dx, col)
        if to_edge:
            y, x = r + d[0], c + d[1]
            while 0 <= y < h and 0 <= x < w:
                put(y, x, col)
                y, x = y + d[0], x + d[1]
    return g


def _wrap(**kw):
    def f(inp, out):
        res = _draw(inp, **kw)
        return None if res == out else res
    return f


def keeps_dot(inp, out):
    return _wrap(clear=False)(inp, out)


def no_arrowhead(inp, out):
    return _wrap(head="none")(inp, out)


def head_without_tip(inp, out):
    return _wrap(head="arms")(inp, out)


def no_foot(inp, out):
    return _wrap(foot="none")(inp, out)


def line_only(inp, out):
    return _wrap(foot="none", head="none")(inp, out)


def foot_detached(inp, out):
    return _wrap(foot_shift=1)(inp, out)


def foot_too_wide(inp, out):
    return _wrap(foot_half=2)(inp, out)


def line_short_by_one(inp, out):
    return _wrap(line="short")(inp, out)


def line_runs_to_edge(inp, out):
    return _wrap(to_edge=True)(inp, out)


def foot_on_far_side(inp, out):
    return _wrap(foot="none", through=True)(inp, out)


def head_is_ring(inp, out):
    return _wrap(ring=True)(inp, out)


def horizontal_dots_only(inp, out):
    return _wrap(only_axis="h")(inp, out)


ALTERNATIVES = [
    ("the dot stays in place after the connection is drawn", keeps_dot),
    ("the line and foot are drawn but the dot gets no arrowhead", no_arrowhead),
    ("the arrowhead has its two side cells but not the tip beyond the dot", head_without_tip),
    ("the line and arrowhead are drawn but no foot stands against the block", no_foot),
    ("only a bare line joins block and dot, with no foot and no arrowhead", line_only),
    ("the foot stands one cell further out, leaving a gap against the block", foot_detached),
    ("the foot is five cells wide instead of three", foot_too_wide),
    ("the line stops one cell short of the dot", line_short_by_one),
    ("the line continues past the dot to the grid edge", line_runs_to_edge),
    ("the foot is put on the block's far side instead of the near side", foot_on_far_side),
    ("the arrowhead is a full ring of eight cells around the dot", head_is_ring),
    ("only dots left or right of their block are connected", horizontal_dots_only),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/a2d730bd.json").read_text())
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (
                isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                and len({len(r) for r in g}) == 1
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                and g != p["output"]
            )
            n += ok
        print(n, desc)
