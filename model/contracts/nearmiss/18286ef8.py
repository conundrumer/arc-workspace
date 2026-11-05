"""Near-miss readings for ARC task 18286ef8.

Rule: a 5-frame with a 9 inside sits in one tile of a grid cut by 0 lines.
One tile holds a marker cell (a color that vanishes). The 9 slides, in the
direction from its tile to the marker's tile, to the end of its frame; the
marker cell becomes 9 and the origin of the 9 becomes 5 again.
"""
import json
from pathlib import Path


def _segments(n, is_div):
    segs, start = [], None
    for i in range(n):
        if is_div(i):
            if start is not None:
                segs.append((start, i - 1))
                start = None
        elif start is None:
            start = i
    if start is not None:
        segs.append((start, n - 1))
    return segs


def _info(inp, out):
    h, w = len(inp), len(inp[0])
    rows = _segments(h, lambda r: all(v == 0 for v in inp[r]))
    cols = _segments(w, lambda c: all(inp[r][c] == 0 for r in range(h)))
    cells = [(r, c) for r in range(h) for c in range(w)]
    g = next(p for p in cells if inp[p[0]][p[1]] == 9)
    fr = [p for p in cells if inp[p[0]][p[1]] == 5] + [g]
    r0 = min(p[0] for p in fr)
    r1 = max(p[0] for p in fr)
    c0 = min(p[1] for p in fr)
    c1 = max(p[1] for p in fr)
    box = (r0, c0, r1, c1)
    inbox = lambda p: r0 <= p[0] <= r1 and c0 <= p[1] <= c1
    d = next(p for p in cells if out[p[0]][p[1]] == 9 and inbox(p))
    t = next(p for p in cells if out[p[0]][p[1]] == 9 and not inbox(p))

    def tile(p):
        ri = next(i for i, s in enumerate(rows) if s[0] <= p[0] <= s[1])
        ci = next(i for i, s in enumerate(cols) if s[0] <= p[1] <= s[1])
        return ri, ci

    return dict(h=h, w=w, rows=rows, cols=cols, g=g, box=box, inbox=inbox,
                d=d, t=t, tile=tile)


def _sign(x):
    return (x > 0) - (x < 0)


def _dir(I, a, b):
    ta, tb = I["tile"](a), I["tile"](b)
    return _sign(tb[0] - ta[0]), _sign(tb[1] - ta[1])


def _slide(I, start, dr, dc):
    r, c = start
    while True:
        nr, nc = r + dr, c + dc
        if not I["inbox"]((nr, nc)):
            return r, c
        r, c = nr, nc


def _copy(g):
    return [row[:] for row in g]


def _moved(inp, out, I, dest, target_color=9, target_cell=None):
    """Output where the 9 ends at dest, origin restored, marker handled."""
    res = _copy(out)
    g, d, t = I["g"], I["d"], I["t"]
    res[d[0]][d[1]] = inp[d[0]][d[1]]
    res[g[0]][g[1]] = 5
    res[dest[0]][dest[1]] = 9
    return res


def no_move(inp, out):
    I = _info(inp, out)
    res = _copy(out)
    d, g = I["d"], I["g"]
    res[d[0]][d[1]] = 5
    res[g[0]][g[1]] = 9
    return res


def marker_kept(inp, out):
    I = _info(inp, out)
    res = _copy(out)
    t = I["t"]
    res[t[0]][t[1]] = inp[t[0]][t[1]]
    return res


def copy_not_move(inp, out):
    I = _info(inp, out)
    res = _copy(out)
    g = I["g"]
    res[g[0]][g[1]] = 9
    return res


def opposite_direction(inp, out):
    I = _info(inp, out)
    dr, dc = _dir(I, I["g"], I["t"])
    return _moved(inp, out, I, _slide(I, I["g"], -dr, -dc))


def mirrored_column_direction(inp, out):
    I = _info(inp, out)
    dr, dc = _dir(I, I["g"], I["t"])
    return _moved(inp, out, I, _slide(I, I["g"], dr, -dc))


def overshoot_frame(inp, out):
    I = _info(inp, out)
    dr, dc = _dir(I, I["g"], I["t"])
    d = I["d"]
    p = (d[0] + dr, d[1] + dc)
    if not (0 <= p[0] < I["h"] and 0 <= p[1] < I["w"]):
        return None
    return _moved(inp, out, I, p)


def takes_marker_color(inp, out):
    I = _info(inp, out)
    res = _copy(out)
    d, t = I["d"], I["t"]
    res[d[0]][d[1]] = inp[t[0]][t[1]]
    return res


def origin_becomes_background(inp, out):
    I = _info(inp, out)
    res = _copy(out)
    g = I["g"]
    res[g[0]][g[1]] = 7
    return res


def marker_erased(inp, out):
    I = _info(inp, out)
    res = _copy(out)
    t = I["t"]
    res[t[0]][t[1]] = 7
    return res


def relative_position_in_marker_tile(inp, out):
    I = _info(inp, out)
    t = I["t"]
    ri, ci = I["tile"](t)
    rs, cs = I["rows"][ri], I["cols"][ci]
    rel = (t[0] - rs[0], t[1] - cs[0])
    r0, c0, r1, c1 = I["box"]
    dest = (r0 + rel[0], c0 + rel[1])
    if not I["inbox"](dest):
        return None
    return _moved(inp, out, I, dest)


def toward_other_marker(inp, out):
    I = _info(inp, out)
    g, t = I["g"], I["t"]
    gt = I["tile"](g)
    skip = {0, 5, 7, 9}
    for r in range(I["h"]):
        for c in range(I["w"]):
            v = inp[r][c]
            if v in skip or (r, c) == t:
                continue
            tt = I["tile"]((r, c))
            if tt == gt or max(abs(tt[0] - gt[0]), abs(tt[1] - gt[1])) != 1:
                continue
            dr, dc = _dir(I, g, (r, c))
            res = _moved(inp, out, I, _slide(I, g, dr, dc))
            res[t[0]][t[1]] = inp[t[0]][t[1]]
            res[r][c] = 9
            return res
    return None


ALTERNATIVES = [
    ("the 9 stays put and only the marker cell becomes 9", no_move),
    ("the 9 moves but the marker cell keeps its color", marker_kept),
    ("the 9 is copied to its destination and also stays at its origin", copy_not_move),
    ("the 9 slides away from the marker's tile instead of toward it", opposite_direction),
    ("the horizontal part of the direction is mirrored", mirrored_column_direction),
    ("the 9 slides one cell past the frame edge", overshoot_frame),
    ("the destination takes the marker's color instead of 9", takes_marker_color),
    ("the origin of the 9 becomes background 7 instead of frame 5", origin_becomes_background),
    ("the marker cell is erased to 7 instead of becoming 9", marker_erased),
    ("the 9 goes to the marker's relative position in its own tile", relative_position_in_marker_tile),
    ("the 9 looks toward a different colored cell in a neighboring tile", toward_other_marker),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/18286ef8.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for name, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            good = (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                    and len({len(r) for r in g}) == 1
                    and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))
            if good and g != p["output"]:
                ok += 1
        print(ok, name)
