"""Near-miss readings for 83b6b474.

Rule: the background is the commonest input color. The other shapes are
pieces that tile the border of a square, each keeping its orientation. The
output is that square, with the background inside the ring.
"""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _copy(g):
    return [list(r) for r in g]


def _counts(out, bg):
    c = Counter(v for r in out for v in r)
    c.pop(bg, None)
    return c


def interior_filled_with_piece(inp, out):
    g = _copy(out)
    n = len(g)
    for y in range(1, n - 1):
        for x in range(1, len(g[0]) - 1):
            g[y][x] = out[0][0]
    return g


def side_one_short(inp, out):
    return [r[:-1] for r in out[:-1]]


def side_one_long(inp, out):
    bg = _bg(inp)
    return [list(r) + [bg] for r in out] + [[bg] * (len(out[0]) + 1)]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def mirrored_left_right(inp, out):
    return [r[::-1] for r in out]


def flipped_top_bottom(inp, out):
    return _copy(out[::-1])


def two_largest_pieces_swapped(inp, out):
    bg = _bg(inp)
    c = _counts(out, bg).most_common(2)
    if len(c) < 2:
        return None
    a, b = c[0][0], c[1][0]
    m = {a: b, b: a}
    return [[m.get(v, v) for v in r] for r in out]


def smallest_piece_left_out(inp, out):
    bg = _bg(inp)
    c = _counts(out, bg)
    if not c:
        return None
    s = min(c, key=lambda k: c[k])
    return [[bg if v == s else v for v in r] for r in out]


def wrong_background_color(inp, out):
    c = Counter(v for r in inp for v in r).most_common(2)
    if len(c) < 2:
        return None
    bg, other = c[0][0], c[1][0]
    return [[other if v == bg else v for v in r] for r in out]


def crop_of_all_non_background(inp, out):
    bg = _bg(inp)
    ys = [y for y, r in enumerate(inp) for v in r if v != bg]
    xs = [x for r in inp for x, v in enumerate(r) if v != bg]
    return [r[min(xs):max(xs) + 1] for r in inp[min(ys):max(ys) + 1]]


def ring_shifted_by_one_cell(inp, out):
    n, m = len(out), len(out[0])
    if n < 2 or m < 2:
        return None
    pos = [(0, x) for x in range(m)] + [(y, m - 1) for y in range(1, n)]
    pos += [(n - 1, x) for x in range(m - 2, -1, -1)]
    pos += [(y, 0) for y in range(n - 2, 0, -1)]
    vals = [out[y][x] for y, x in pos]
    vals = vals[-1:] + vals[:-1]
    g = _copy(out)
    for (y, x), v in zip(pos, vals):
        g[y][x] = v
    return g


def input_unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("interior of the ring filled with a piece color instead of background", interior_filled_with_piece),
    ("square side one cell too short (last row and column dropped)", side_one_short),
    ("square side one cell too long (extra background row and column)", side_one_long),
    ("output transposed (wrong orientation of the whole square)", transposed),
    ("output mirrored left to right", mirrored_left_right),
    ("output flipped top to bottom", flipped_top_bottom),
    ("colors of the two largest pieces swapped (wrong piece in each place)", two_largest_pieces_swapped),
    ("smallest piece left out of the ring", smallest_piece_left_out),
    ("second most common color taken as the background", wrong_background_color),
    ("crop of all non-background cells of the input as the answer", crop_of_all_non_background),
    ("pieces placed one cell further around the ring", ring_shifted_by_one_cell),
    ("input returned unchanged", input_unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/83b6b474.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
