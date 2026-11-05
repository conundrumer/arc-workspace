"""Near-miss rules for task 230f2e48.

Rule: each arm is a straight line of body color from an anchor cell (5) through a
joint cell (0). The stretch beyond the joint is cut off and re-drawn at a right
angle from the joint, on the side with more free background, same length.
"""
import json
from collections import Counter
from pathlib import Path

ANCHOR, JOINT = 5, 0
DIRS = [(-1, 0), (0, 1), (1, 0), (0, -1)]


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _arms(g):
    """Return a list of dicts: anchor, joint, d (arm direction), tail cells, in scan order."""
    bg = _bg(g)
    h, w = len(g), len(g[0])
    seen = set()
    arms = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            comp, stack = [], [(r, c)]
            seen.add((r, c))
            while stack:
                p = stack.pop()
                comp.append(p)
                for dr, dc in DIRS:
                    q = (p[0] + dr, p[1] + dc)
                    if 0 <= q[0] < h and 0 <= q[1] < w and q not in seen and g[q[0]][q[1]] != bg:
                        seen.add(q)
                        stack.append(q)
            a = [p for p in comp if g[p[0]][p[1]] == ANCHOR]
            j = [p for p in comp if g[p[0]][p[1]] == JOINT]
            if len(a) != 1 or len(j) != 1:
                continue
            a, j = a[0], j[0]
            sgn = lambda x: (x > 0) - (x < 0)
            d = (sgn(j[0] - a[0]), sgn(j[1] - a[1]))
            tail = []
            p = (j[0] + d[0], j[1] + d[1])
            while 0 <= p[0] < h and 0 <= p[1] < w and g[p[0]][p[1]] != bg:
                tail.append(p)
                p = (p[0] + d[0], p[1] + d[1])
            arms.append(dict(anchor=a, joint=j, d=d, tail=tail, comp=comp))
    return arms


def _room(g, start, step):
    bg = _bg(g)
    h, w = len(g), len(g[0])
    n = 0
    p = (start[0] + step[0], start[1] + step[1])
    while 0 <= p[0] < h and 0 <= p[1] < w and g[p[0]][p[1]] == bg:
        n += 1
        p = (p[0] + step[0], p[1] + step[1])
    return n


def _edge_dist(g, start, step):
    h, w = len(g), len(g[0])
    if step[0]:
        return start[0] if step[0] < 0 else h - 1 - start[0]
    return start[1] if step[1] < 0 else w - 1 - start[1]


def _body(g):
    bg = _bg(g)
    return Counter(v for r in g for v in r if v not in (bg, ANCHOR, JOINT)).most_common(1)[0][0]


def _perps(d):
    return [(d[1], d[0]), (-d[1], -d[0])] if d[0] == 0 else [(d[1], d[0]), (-d[1], -d[0])]


def _perp_pair(d):
    # the two directions at right angles to d
    return [(d[1], d[0]), (-d[1], -d[0])]


def _pick(g, arm, mode):
    j, d = arm["joint"], arm["d"]
    p1, p2 = _perp_pair(d)
    r1, r2 = _room(g, j, p1), _room(g, j, p2)
    if mode == "more":
        return p1 if r1 >= r2 else p2
    if mode == "less":
        return p1 if r1 < r2 else p2
    if mode == "edge":  # nearer grid edge, ignoring obstacles
        e1, e2 = _edge_dist(g, j, p1), _edge_dist(g, j, p2)
        return p1 if e1 <= e2 else p2
    if mode == "edge_far":  # farther grid edge, ignoring obstacles
        e1, e2 = _edge_dist(g, j, p1), _edge_dist(g, j, p2)
        return p1 if e1 > e2 else p2
    # fixed turn relative to arm direction: clockwise (rows down, cols right)
    cw = (d[1], -d[0])
    ccw = (-d[1], d[0])
    return cw if mode == "cw" else ccw


def _render(inp, mode="more", erase=True, dlen=0, color=None, gap=0, back=0,
            both=False, only_first=False, start_shift=0, only_longest=False):
    g = [r[:] for r in inp]
    bg = _bg(g)
    h, w = len(g), len(g[0])
    body = _body(g) if color is None else color
    arms = _arms(inp)
    if only_first:
        arms = arms[:1]
    if only_longest and arms:
        arms = [max(arms, key=lambda a: len(a["tail"]))]
    for arm in arms:
        k = len(arm["tail"])
        if erase:
            for (r, c) in arm["tail"]:
                g[r][c] = bg
        n = max(k + dlen, 0)
        if both:
            dirs = _perp_pair(arm["d"])
        else:
            dirs = [_pick(inp, arm, mode)]
        jr, jc = arm["joint"]
        base = (jr - back * arm["d"][0], jc - back * arm["d"][1])
        for s in dirs:
            for i in range(1, n + 1):
                t = i + gap
                r, c = base[0] + s[0] * t, base[1] + s[1] * t
                if 0 <= r < h and 0 <= c < w:
                    g[r][c] = body
    return g


def _wrap(f):
    def inner(inp, out):
        g = f(inp, out)
        if g is None or g == out:
            return None
        return g
    return inner


def less_room(inp, out):
    return _render(inp, mode="less")


def keep_tail(inp, out):
    return _render(inp, erase=False)


def short_by_one(inp, out):
    return _render(inp, dlen=-1)


def long_by_one(inp, out):
    return _render(inp, dlen=1)


def gap_before_fold(inp, out):
    return _render(inp, gap=1)


def both_sides(inp, out):
    return _render(inp, both=True)


def always_clockwise(inp, out):
    return _render(inp, mode="cw")


def always_counter_clockwise(inp, out):
    return _render(inp, mode="ccw")


def no_fold(inp, out):
    return _render(inp, dlen=-10**6)


def anchor_color_fold(inp, out):
    return _render(inp, color=ANCHOR)


def joint_color_fold(inp, out):
    return _render(inp, color=JOINT)


def nearer_edge(inp, out):
    return _render(inp, mode="edge")


def first_arm_only(inp, out):
    return _render(inp, only_first=True)


def fold_from_before_joint(inp, out):
    return _render(inp, back=1)


ALTERNATIVES = [
    ("fold turns toward the side with less free background", _wrap(less_room)),
    ("tail is copied to the fold but not erased from the arm", _wrap(keep_tail)),
    ("fold is one cell shorter than the tail", _wrap(short_by_one)),
    ("fold is one cell longer than the tail", _wrap(long_by_one)),
    ("fold starts one cell away from the joint, leaving a gap", _wrap(gap_before_fold)),
    ("tail is folded to both sides of the joint", _wrap(both_sides)),
    ("fold always turns clockwise relative to the arm direction", _wrap(always_clockwise)),
    ("tail is cut off but no fold is drawn", _wrap(no_fold)),
    ("fold is drawn in the anchor color", _wrap(anchor_color_fold)),
    ("fold turns toward the nearer grid edge, ignoring obstacles", _wrap(nearer_edge)),
    ("only the first arm in scan order is folded", _wrap(first_arm_only)),
    ("fold is attached one cell before the joint", _wrap(fold_from_before_joint)),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/230f2e48.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
