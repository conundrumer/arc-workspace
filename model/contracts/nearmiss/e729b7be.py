from pathlib import Path
import json
from collections import Counter


def _info(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    marker = min(cnt, key=lambda k: (cnt[k], k))
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == marker]
    cross = None
    for r, c in cells:
        for dr, dc in ((1, 0), (0, 1)):
            r1, c1, r2, c2 = r - dr, c - dc, r + dr, c + dc
            if 0 <= r1 and 0 <= c1 and r2 < h and c2 < w:
                a, b = inp[r1][c1], inp[r2][c2]
                if a == b and a not in (bg, marker):
                    cross = (r, c)
                    line = a
    return h, w, bg, marker, line, cross, cells


def _paint(inp, f, overwrite=False, keep=None):
    h, w, bg = len(inp), len(inp[0]), _info(inp)[2]
    g = [row[:] for row in inp]
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v == bg or (keep and not keep(r, c, v)):
                continue
            r2, c2 = f(r, c)
            if 0 <= r2 < h and 0 <= c2 < w and (overwrite or inp[r2][c2] == bg):
                g[r2][c2] = v
    return g


def transpose(inp, out):
    cr, cc = _info(inp)[5]
    return _paint(inp, lambda r, c: (cr + (c - cc), cc + (r - cr)))


def flip_lr(inp, out):
    cr, cc = _info(inp)[5]
    return _paint(inp, lambda r, c: (r, 2 * cc - c))


def flip_ud(inp, out):
    cr, cc = _info(inp)[5]
    return _paint(inp, lambda r, c: (2 * cr - r, c))


def bbox_center(inp, out):
    _, _, bg, marker, line, _, _ = _info(inp)
    pts = [(r, c) for r in range(len(inp)) for c in range(len(inp[0]))
           if inp[r][c] not in (bg, marker, line)]
    r0, r1 = min(p[0] for p in pts), max(p[0] for p in pts)
    c0, c1 = min(p[1] for p in pts), max(p[1] for p in pts)
    return _paint(inp, lambda r, c: (r0 + r1 - r, c0 + c1 - c))


def off_by_one(inp, out):
    cr, cc = _info(inp)[5]
    return _paint(inp, lambda r, c: (2 * cr - r, 2 * (cc + 1) - c))


def quarter_turn(inp, out):
    cr, cc = _info(inp)[5]
    return _paint(inp, lambda r, c: (cr + (c - cc), cc - (r - cr)))


def anti_transpose(inp, out):
    cr, cc = _info(inp)[5]
    return _paint(inp, lambda r, c: (cr - (c - cc), cc - (r - cr)))


def one_side_only(inp, out):
    cr, cc = _info(inp)[5]
    return _paint(inp, lambda r, c: (2 * cr - r, 2 * cc - c),
                  keep=lambda r, c, v: r <= cr)


def _recolor(inp, out, color):
    bg = _info(inp)[2]
    return [[color if inp[r][c] == bg and out[r][c] != bg else out[r][c]
             for c in range(len(out[0]))] for r in range(len(out))]


def marker_colored(inp, out):
    return _recolor(inp, out, _info(inp)[3])


def line_colored(inp, out):
    return _recolor(inp, out, _info(inp)[4])


def first_marker(inp, out):
    cells = _info(inp)[6]
    cr, cc = cells[0]
    return _paint(inp, lambda r, c: (2 * cr - r, 2 * cc - c))


def lower_half_missing(inp, out):
    cr = _info(inp)[5][0]
    bg = _info(inp)[2]
    return [[bg if r > cr and inp[r][c] == bg else out[r][c]
             for c in range(len(out[0]))] for r in range(len(out))]


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("transpose about the crossing instead of a half turn", transpose),
    ("mirror left-right across the crossing column", flip_lr),
    ("mirror top-bottom across the crossing row", flip_ud),
    ("half turn about the center of the shape bounding box", bbox_center),
    ("half turn about a center one column off the crossing", off_by_one),
    ("quarter turn about the crossing", quarter_turn),
    ("anti-diagonal transpose about the crossing", anti_transpose),
    ("half turn of only the shape cells on the upper side of the crossing", one_side_only),
    ("copy drawn in the marker color", marker_colored),
    ("copy drawn in the line color", line_colored),
    ("half turn about the first marker cell in reading order", first_marker),
    ("copy missing below the crossing row", lower_half_missing),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    path = str(Path(__file__).resolve().parents[3] / 'data/tasks/e729b7be.json')
    train = json.load(open(path))["train"]
    # sanity: the true rule reproduces the output
    for p in train:
        cr, cc = _info(p["input"])[5]
        assert _paint(p["input"], lambda r, c: (2 * cr - r, 2 * cc - c)) == p["output"]
    for name, f in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error:", name, repr(e))
                g = None
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(train), name)
