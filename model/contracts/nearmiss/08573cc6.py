"""Near-miss rules for ARC task 08573cc6.

Rule: the dot (rarest color) starts a spiral. The first arm goes left and has
as many cells as there are marker tiles (2). Each next arm turns
counterclockwise (left, down, right, up) and is one cell longer. An arm the
grid edge cuts short ends the spiral. Horizontal arms take the color of the
marker in the grid corner, vertical arms the other marker's color. The marker
tiles are erased.
"""
import json
from pathlib import Path

LEFT, DOWN, RIGHT, UP = (0, -1), (1, 0), (0, 1), (-1, 0)
CCW = [LEFT, DOWN, RIGHT, UP]
CW = [LEFT, UP, RIGHT, DOWN]


def _info(inp):
    h, w = len(inp), len(inp[0])
    nz = [(r, c) for r in range(h) for c in range(w) if inp[r][c]]

    def isolated(p):
        return not any(q != p and abs(q[0] - p[0]) <= 1 and abs(q[1] - p[1]) <= 1 for q in nz)

    dot = next(p for p in nz if isolated(p))
    dot_color = inp[dot[0]][dot[1]]
    markers = [(p, inp[p[0]][p[1]]) for p in nz if p != dot]
    corner = inp[0][0] if inp[0][0] and inp[0][0] != dot_color else markers[0][1]
    others = [v for _, v in markers if v != corner]
    other = others[0] if others else corner
    return dot, dot_color, markers, corner, other


def _spiral(inp, order=CCW, start_idx=0, n0=None, step=lambda i: 1,
            max_arms=None, drop_clipped=False, color_fn=None, swap=False):
    h, w = len(inp), len(inp[0])
    dot, dot_color, markers, corner, other = _info(inp)
    if n0 is None:
        n0 = len(markers)
    g = [[0] * w for _ in range(h)]
    r, c = dot
    n = n0
    i = 0
    while max_arms is None or i < max_arms:
        d = order[(start_idx + i) % 4]
        horizontal = d[0] == 0
        col = corner if horizontal else other
        if swap:
            col = other if horizontal else corner
        if color_fn:
            col = color_fn(horizontal, corner, other)
        er, ec = r + d[0] * n, c + d[1] * n
        on_grid = 0 <= er < h and 0 <= ec < w
        if drop_clipped and not on_grid:
            break
        for k in range(1, n + 1):
            rr, cc = r + d[0] * k, c + d[1] * k
            if 0 <= rr < h and 0 <= cc < w:
                g[rr][cc] = col
        if not on_grid:
            break
        r, c = er, ec
        n += step(i)
        i += 1
    g[dot[0]][dot[1]] = dot_color
    return g


def swap_axis_colors(inp, out):
    return _spiral(inp, swap=True)


def clockwise(inp, out):
    return _spiral(inp, order=CW)


def first_arm_one(inp, out):
    return _spiral(inp, n0=1)


def first_arm_three(inp, out):
    return _spiral(inp, n0=3)


def start_up(inp, out):
    return _spiral(inp, start_idx=3)


def growth_every_two(inp, out):
    return _spiral(inp, step=lambda i: 1 if i % 2 == 1 else 0)


def drop_clipped_arm(inp, out):
    return _spiral(inp, drop_clipped=True)


def single_color(inp, out):
    return _spiral(inp, color_fn=lambda horizontal, corner, other: corner)


def one_ring_only(inp, out):
    return _spiral(inp, max_arms=4)


def markers_kept(inp, out):
    g = [row[:] for row in out]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v and g[r][c] == 0:
                g[r][c] = v
    return g


def dot_erased(inp, out):
    dot = _info(inp)[0]
    g = [row[:] for row in out]
    g[dot[0]][dot[1]] = 0
    return g


ALTERNATIVES = [
    ("horizontal arms take the other marker's color and vertical arms the corner marker's color", swap_axis_colors),
    ("the spiral turns clockwise instead of counterclockwise", clockwise),
    ("the first arm has 1 cell instead of the marker count", first_arm_one),
    ("the first arm has 3 cells instead of the marker count", first_arm_three),
    ("the first arm goes up instead of left", start_up),
    ("arm length grows by one only after every second arm", growth_every_two),
    ("the last arm, which the grid edge cuts short, is left out", drop_clipped_arm),
    ("all arms take the corner marker's color", single_color),
    ("only the first four arms are drawn", one_ring_only),
    ("the marker tiles stay in the output", markers_kept),
    ("the dot cell is erased", dot_erased),
]


def _valid(g, out):
    if g is None or not g or not isinstance(g, list):
        return False
    if any(not isinstance(r, list) or len(r) != len(g[0]) for r in g):
        return False
    if any(type(v) is not int or not 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/08573cc6.json"))
    pairs = task["train"]
    # sanity check: the correct simulation reproduces the output
    for p in pairs:
        assert _spiral(p["input"]) == p["output"], "simulator mismatch"
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
