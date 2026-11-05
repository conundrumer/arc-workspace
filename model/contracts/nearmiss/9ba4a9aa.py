import json
from collections import Counter
from pathlib import Path


def ground(g):
    return Counter(c for r in g for c in r).most_common(1)[0][0]


def squares(g):
    """All 3x3 windows with no ground cell: (r, c, framed)."""
    bg = ground(g)
    h, w = len(g), len(g[0])
    res = []
    for r in range(h - 2):
        for c in range(w - 2):
            win = [g[r + i][c + j] for i in range(3) for j in range(3)]
            if bg in win:
                continue
            ring = win[:4] + win[5:]
            res.append((r, c, len(set(ring)) == 1 and win[4] != ring[0]))
    return res


def crop(g, r, c, pad=0):
    bg = ground(g)
    h, w = len(g), len(g[0])
    return [[g[i][j] if 0 <= i < h and 0 <= j < w else bg
             for j in range(c - pad, c + 3 + pad)] for i in range(r - pad, r + 3 + pad)]


def target_pos(inp, out):
    return [(r, c) for r, c, f in squares(inp) if f and crop(inp, r, c) == out]


def others(inp, out):
    tp = target_pos(inp, out)
    return [(r, c) for r, c, f in squares(inp) if f and (r, c) not in tp]


def sources(inp):
    return [(r, c) for r, c, f in squares(inp) if not f]


def dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def first_other(inp, out):
    o = others(inp, out)
    return crop(inp, *min(o)) if o else None


def last_other(inp, out):
    o = others(inp, out)
    return crop(inp, *max(o)) if o else None


def source_square(inp, out):
    s = sources(inp)
    return crop(inp, *s[0]) if s else None


def nearest_to_source(inp, out):
    s, f = sources(inp), [(r, c) for r, c, fr in squares(inp) if fr]
    if not s or not f:
        return None
    return crop(inp, *min(f, key=lambda p: dist(p, s[0])))


def farthest_from_source(inp, out):
    s, f = sources(inp), [(r, c) for r, c, fr in squares(inp) if fr]
    if not s or not f:
        return None
    return crop(inp, *max(f, key=lambda p: dist(p, s[0])))


def swap_colors(inp, out):
    a, b = out[0][0], out[1][1]
    return [[b if x == a else a if x == b else x for x in row] for row in out]


def center_ground(inp, out):
    g = [row[:] for row in out]
    g[1][1] = ground(inp)
    return g


def padded(inp, out):
    tp = target_pos(inp, out)
    return crop(inp, *tp[0], pad=1) if tp else None


def drop_row(inp, out):
    return [row[:] for row in out[:2]]


def source_center(inp, out):
    s = sources(inp)
    if not s:
        return None
    r, c = s[0]
    g = [row[:] for row in out]
    g[1][1] = inp[r + 1][c + 1]
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("outputs the first other framed square in reading order", first_other),
    ("outputs the last other framed square in reading order", last_other),
    ("outputs the unframed source square itself", source_square),
    ("outputs the framed square nearest to the source", nearest_to_source),
    ("outputs the framed square farthest from the source", farthest_from_source),
    ("frame and center colors swapped in the picked square", swap_colors),
    ("center of the picked square left as ground", center_ground),
    ("crops the picked square with a one-cell margin (5x5)", padded),
    ("crops only two rows of the picked square", drop_row),
    ("picked square gets the source's center color", source_center),
    ("returns the input unchanged", unchanged),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/9ba4a9aa.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                  and all(isinstance(x, int) and 0 <= x <= 9 for r in g for x in r)
                  and g != p["output"])
            n += ok
        print(f"{n}/{len(pairs)}  {desc}")
