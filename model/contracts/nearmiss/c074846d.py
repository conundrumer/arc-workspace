import json
from pathlib import Path

PIVOT = 5
ARM = 2
TRAIL = 3


def _parts(inp):
    pivot = None
    arm = []
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == PIVOT:
                pivot = (r, c)
            elif v == ARM:
                arm.append((r, c))
    return pivot, arm


def _swing(inp, turn, trail=TRAIL, new=ARM, remove_old=False, pivot_color=None,
           dist=lambda k: k, keep_old=False, draw_new=True):
    """turn maps an offset (dr, dc) to its new offset."""
    pivot, arm = _parts(inp)
    if pivot is None or not arm:
        return None
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    pr, pc = pivot
    for r, c in arm:
        g[r][c] = ARM if keep_old else (0 if remove_old else trail)
    if draw_new:
        for r, c in arm:
            dr, dc = r - pr, c - pc
            nr, nc = turn((dr, dc))
            k = max(abs(nr), abs(nc))
            if k:
                s = dist(k) / k
                nr, nc = round(nr * s), round(nc * s)
            r2, c2 = pr + nr, pc + nc
            if 0 <= r2 < h and 0 <= c2 < w:
                g[r2][c2] = new
    if pivot_color is not None:
        g[pr][pc] = pivot_color
    return g


def cw(o):
    return (o[1], -o[0])


def ccw(o):
    return (-o[1], o[0])


def half(o):
    return (-o[0], -o[1])


def transpose(o):
    return (o[1], o[0])


def ccw_alt(inp, out):
    return _swing(inp, ccw)


def half_turn(inp, out):
    return _swing(inp, half)


def keep_old_arm(inp, out):
    return _swing(inp, cw, keep_old=True)


def erase_old_arm(inp, out):
    return _swing(inp, cw, remove_old=True)


def wrong_new_color(inp, out):
    return _swing(inp, cw, new=TRAIL)


def wrong_trail_color(inp, out):
    return _swing(inp, cw, trail=PIVOT)


def no_swing(inp, out):
    return _swing(inp, cw, draw_new=False)


def pivot_recolored(inp, out):
    return _swing(inp, cw, pivot_color=TRAIL)


def one_cell_swing(inp, out):
    pivot, arm = _parts(inp)
    if pivot is None:
        return None
    g = _swing(inp, cw, draw_new=False)
    pr, pc = pivot
    near = min(arm, key=lambda p: abs(p[0] - pr) + abs(p[1] - pc))
    dr, dc = cw((near[0] - pr, near[1] - pc))
    r2, c2 = pr + dr, pc + dc
    if 0 <= r2 < len(g) and 0 <= c2 < len(g[0]):
        g[r2][c2] = ARM
    return g


def swing_one_farther(inp, out):
    return _swing(inp, cw, dist=lambda k: k + 1)


def diagonal_reflection(inp, out):
    return _swing(inp, transpose)


def swing_cw_trail_only_tip(inp, out):
    # old arm keeps its cell nearest the pivot only; the rest is erased
    pivot, arm = _parts(inp)
    if pivot is None:
        return None
    g = _swing(inp, cw)
    pr, pc = pivot
    for r, c in arm:
        g[r][c] = 0
    near = min(arm, key=lambda p: abs(p[0] - pr) + abs(p[1] - pc))
    g[near[0]][near[1]] = TRAIL
    return g


ALTERNATIVES = [
    ("arm turns a quarter turn counter-clockwise instead of clockwise", ccw_alt),
    ("arm turns a half turn to the opposite side of the pivot", half_turn),
    ("old arm keeps color 2 and the swung arm is also 2 (no recolor)", keep_old_arm),
    ("old arm cells are erased to 0 instead of recolored to 3", erase_old_arm),
    ("swung arm is painted 3 instead of 2", wrong_new_color),
    ("old arm is recolored to the pivot color 5 instead of 3", wrong_trail_color),
    ("old arm is recolored to 3 but no swung arm is drawn", no_swing),
    ("pivot is recolored to 3 along with the arm", pivot_recolored),
    ("only the cell next to the pivot is swung; the rest of the arm is dropped", one_cell_swing),
    ("swung arm sits one cell farther from the pivot than the old arm", swing_one_farther),
    ("arm is reflected across the diagonal through the pivot instead of turned", diagonal_reflection),
    ("old arm is reduced to one recolored cell next to the pivot, and the swung arm is full length", swing_cw_trail_only_tip),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) for r in g):
        return False
    w = len(g[0])
    if w == 0 or any(len(r) != w for r in g):
        return False
    if any(type(v) is not int or not 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/c074846d.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(n, desc)
