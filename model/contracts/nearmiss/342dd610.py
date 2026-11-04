from pathlib import Path
import json
from collections import Counter


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _ink(g, bg):
    return sorted((r, c, v) for r, row in enumerate(g) for c, v in enumerate(row) if v != bg)


def _info(inp, out):
    bg = _bg(inp)
    a = _ink(inp, bg)
    b = _ink(out, bg)
    dr, dc = b[0][0] - a[0][0], b[0][1] - a[0][1]
    return bg, a, b, dr, dc


def _place(inp, bg, cells, keep=()):
    """Blank the input ink, then draw (r, c, v) cells; None if any is off the grid."""
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    for r, c, v in list(keep) + list(cells):
        if not (0 <= r < h and 0 <= c < w):
            return None
        g[r][c] = v
    return g


def stay(inp, out):
    return [row[:] for row in inp]


def opposite(inp, out):
    bg, a, b, dr, dc = _info(inp, out)
    return _place(inp, bg, [(r - dr, c - dc, v) for r, c, v in a])


def one_further(inp, out):
    bg, a, b, dr, dc = _info(inp, out)
    sr = (dr > 0) - (dr < 0)
    sc = (dc > 0) - (dc < 0)
    return _place(inp, bg, [(r + dr + sr, c + dc + sc, v) for r, c, v in a])


def one_short(inp, out):
    bg, a, b, dr, dc = _info(inp, out)
    sr = (dr > 0) - (dr < 0)
    sc = (dc > 0) - (dc < 0)
    if abs(dr) + abs(dc) < 2:
        return None
    return _place(inp, bg, [(r + dr - sr, c + dc - sc, v) for r, c, v in a])


def perpendicular(inp, out):
    bg, a, b, dr, dc = _info(inp, out)
    return _place(inp, bg, [(r + dc, c - dr, v) for r, c, v in a])


def only_top_moves(inp, out):
    bg, a, b, dr, dc = _info(inp, out)
    if len(a) < 2:
        return None
    r, c, v = a[0]
    return _place(inp, bg, [(r + dr, c + dc, v)], keep=a[1:])


def copy_not_move(inp, out):
    bg, a, b, dr, dc = _info(inp, out)
    return _place(inp, bg, b, keep=a)


def to_edge(inp, out):
    bg, a, b, dr, dc = _info(inp, out)
    h, w = len(inp), len(inp[0])
    sr = (dr > 0) - (dr < 0)
    sc = (dc > 0) - (dc < 0)
    cells = []
    for r, c, v in a:
        nr = (h - 1) if sr > 0 else 0 if sr < 0 else r
        nc = (w - 1) if sc > 0 else 0 if sc < 0 else c
        cells.append((nr, nc, v))
    return _place(inp, bg, cells)


def wrong_color(inp, out):
    bg, a, b, dr, dc = _info(inp, out)
    return _place(inp, bg, [(r, c, 3 if v != 3 else 4) for r, c, v in b])


def mirrored_output(inp, out):
    return [row[::-1] for row in out[::-1]]


def one_step_only(inp, out):
    bg, a, b, dr, dc = _info(inp, out)
    sr = (dr > 0) - (dr < 0)
    sc = (dc > 0) - (dc < 0)
    return _place(inp, bg, [(r + sr, c + sc, v) for r, c, v in a])


def swapped_axis(inp, out):
    bg, a, b, dr, dc = _info(inp, out)
    return _place(inp, bg, [(r + dc, c + dr, v) for r, c, v in a])


ALTERNATIVES = [
    ("cells stay where they are (input unchanged)", stay),
    ("cells move the true distance in the opposite direction", opposite),
    ("cells move one step further than the true distance", one_further),
    ("cells move one step less than the true distance", one_short),
    ("cells move the true distance in the perpendicular direction", perpendicular),
    ("only the top-most colored cell moves, the others stay", only_top_moves),
    ("cells are copied to the new place and also stay at the old place", copy_not_move),
    ("cells slide all the way to the grid edge in the true direction", to_edge),
    ("moved cells take a wrong color", wrong_color),
    ("output is the true output rotated by 180 degrees", mirrored_output),
    ("cells move one step in the true direction", one_step_only),
    ("horizontal and vertical displacement are swapped", swapped_axis),
]


def _valid(g, out):
    if g is None or not g or not isinstance(g, list):
        return False
    w = len(g[0])
    if w == 0:
        return False
    for r in g:
        if not isinstance(r, list) or len(r) != w:
            return False
        if any(type(v) is not int or not 0 <= v <= 9 for v in r):
            return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/342dd610.json')))
    pairs = task["train"]
    counts = []
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("ERROR", desc, e)
                g = None
            n += _valid(g, p["output"])
        counts.append(n)
        print(f"{n}/{len(pairs)}  {desc}")
