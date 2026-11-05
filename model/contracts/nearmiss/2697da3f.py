"""Near-miss readings for ARC task 2697da3f.

True rule: crop the figure, put it unrotated against the left edge of a
square canvas of side 2*w + h (centered by w rows from the top), and add its
three quarter-turn rotations about the canvas center.
"""
import json
from collections import Counter
from pathlib import Path


def rot(g):
    """Quarter turn clockwise."""
    return [list(r) for r in zip(*g[::-1])]


def bg_of(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def crop(g, margin=0):
    bg = bg_of(g)
    cells = [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v != bg]
    r0 = max(min(r for r, _ in cells) - margin, 0)
    r1 = min(max(r for r, _ in cells) + margin, len(g) - 1)
    c0 = max(min(c for _, c in cells) - margin, 0)
    c1 = min(max(c for _, c in cells) + margin, len(g[0]) - 1)
    return [row[c0:c1 + 1] for row in g[r0:r1 + 1]]


def blank(h, w, v=0):
    return [[v] * w for _ in range(h)]


def paint(canvas, f, top, left):
    for r, row in enumerate(f):
        for c, v in enumerate(row):
            if v and 0 <= top + r < len(canvas) and 0 <= left + c < len(canvas[0]):
                canvas[top + r][left + c] = v


def union(grids):
    n, m = len(grids[0]), len(grids[0][0])
    res = blank(n, m)
    for g in grids:
        for r in range(n):
            for c in range(m):
                if g[r][c]:
                    res[r][c] = g[r][c]
    return res


def turns(g, ks):
    res = []
    for k in range(4):
        if k in ks:
            res.append(g)
        g = rot(g)
    return union(res)


def render(f, arm="left", ks=(0, 1, 2, 3), depth=None, span=None, off=None):
    h, w = len(f), len(f[0])
    horiz = arm in ("left", "right")
    d = depth if depth is not None else (w if horiz else h)
    s = span if span is not None else (h if horiz else w)
    n = 2 * d + s
    o = d if off is None else off
    cv = blank(n, n)
    fh, fw = h, w
    if arm == "left":
        paint(cv, f, o, 0)
    elif arm == "right":
        paint(cv, f, o, n - fw)
    elif arm == "up":
        paint(cv, f, 0, o)
    else:
        paint(cv, f, n - fh, o)
    return turns(cv, ks)


def _figure(inp):
    return crop(inp)


def true_reading(inp, out):
    return render(_figure(inp))


def swapped_turn_direction(inp, out):
    """Each copy keeps its slot but turns the opposite way."""
    f = _figure(inp)
    h, w = len(f), len(f[0])
    n = 2 * w + h
    cw = rot(f)
    ccw = rot(rot(rot(f)))
    half = rot(rot(f))
    cv = blank(n, n)
    paint(cv, f, w, 0)
    paint(cv, ccw, 0, w)
    paint(cv, half, w, n - w)
    paint(cv, cw, n - w, w)
    return cv


def arm_right(inp, out):
    return render(_figure(inp), "right")


def arm_up(inp, out):
    return render(_figure(inp), "up")


def swapped_axes(inp, out):
    f = _figure(inp)
    h, w = len(f), len(f[0])
    return render(f, "left", depth=h, span=w)


def two_copies(inp, out):
    return render(_figure(inp), "left", ks=(0, 2))


def three_copies(inp, out):
    return render(_figure(inp), "left", ks=(0, 1, 2))


def no_rotation(inp, out):
    f = _figure(inp)
    h, w = len(f), len(f[0])
    n = 2 * w + h
    cv = blank(n, n)
    paint(cv, f, w, 0)
    paint(cv, f, w, n - w)
    paint(cv, f, 0, (n - w) // 2)
    paint(cv, f, n - h, (n - w) // 2)
    return cv


def inverted(inp, out):
    cols = {v for r in out for v in r if v}
    ink = max(cols)
    return [[0 if v else ink for v in r] for r in out]


def whole_input_as_figure(inp, out):
    return render(inp)


def crop_with_margin(inp, out):
    return render(crop(inp, 1))


def edge_aligned_top(inp, out):
    return render(_figure(inp), "left", off=0)


def padded_canvas(inp, out):
    return [list(r) + [0] for r in out] + [[0] * (len(out[0]) + 1)]


ALTERNATIVES = [
    ("top and bottom copies turn the opposite way from the true quarter turns", swapped_turn_direction),
    ("the input-oriented copy sits against the right edge", arm_right),
    ("the input-oriented copy sits against the top edge", arm_up),
    ("canvas depth and span use the swapped figure axes", swapped_axes),
    ("only the arm copy and its half-turn copy are painted", two_copies),
    ("three of the four rotated copies are painted", three_copies),
    ("copies are placed at the four edges without rotation", no_rotation),
    ("figure and background colors are swapped", inverted),
    ("the whole input grid is the figure instead of its bounding box", whole_input_as_figure),
    ("the bounding box is taken one cell too wide on every side", crop_with_margin),
    ("the arm copy is aligned to the canvas corner instead of centered", edge_aligned_top),
    ("canvas is one row and column larger than needed", padded_canvas),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if any(len(r) != len(g[0]) or len(r) == 0 for r in g):
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/2697da3f.json").read_text())
    pairs = task["train"]
    ok_true = all(true_reading(p["input"], p["output"]) == p["output"] for p in pairs)
    print("reference rule reproduces outputs:", ok_true)
    print("readings:", len(ALTERNATIVES), "pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
