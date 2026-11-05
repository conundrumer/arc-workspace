import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    cells = [(y, x) for y in range(h) for x in range(w) if inp[y][x] != bg]
    y0 = min(y for y, _ in cells)
    y1 = max(y for y, _ in cells)
    x0 = min(x for _, x in cells)
    x1 = max(x for _, x in cells)
    outer = inp[y0][x0]
    inner = [(y, x) for y, x in cells if inp[y][x] != outer]
    inner_c = inp[inner[0][0]][inner[0][1]]
    by0 = min(y for y, _ in inner)
    by1 = max(y for y, _ in inner)
    bx0 = min(x for _, x in inner)
    bx1 = max(x for _, x in inner)
    return dict(h=h, w=w, bg=bg, box=(y0, x0, y1, x1), outer=outer,
                inner=inner_c, blk=(by0, bx0, by1, bx1),
                th=by1 - by0 + 1, tw=bx1 - bx0 + 1)


def _ring(inp, p, ty, tx, color, sides="tblr", fill_fig=False):
    """Copy of inp with the fig's bounding box grown by (ty, tx) on the given
    sides and the new cells painted; optionally paint over the fig too."""
    y0, x0, y1, x1 = p["box"]
    t = ty if "t" in sides else 0
    b = ty if "b" in sides else 0
    l = tx if "l" in sides else 0
    r = tx if "r" in sides else 0
    g = [row[:] for row in inp]
    for y in range(max(0, y0 - t), min(p["h"], y1 + b + 1)):
        for x in range(max(0, x0 - l), min(p["w"], x1 + r + 1)):
            inside = y0 <= y <= y1 and x0 <= x <= x1
            if fill_fig or not inside:
                g[y][x] = color
    return g


def thin_ring(inp, out):
    p = _parse(inp)
    return _ring(inp, p, 1, 1, p["inner"])


def thick_plus_one(inp, out):
    p = _parse(inp)
    return _ring(inp, p, p["th"] + 1, p["tw"] + 1, p["inner"])


def outer_color_ring(inp, out):
    p = _parse(inp)
    return _ring(inp, p, p["th"], p["tw"], p["outer"])


def sides_only(inp, out):
    p = _parse(inp)
    return _ring(inp, p, p["th"], p["tw"], p["inner"], sides="lr")


def forward_only(inp, out):
    p = _parse(inp)
    return _ring(inp, p, p["th"], p["tw"], p["inner"], sides="br")


def solid_fill(inp, out):
    p = _parse(inp)
    return _ring(inp, p, p["th"], p["tw"], p["inner"], fill_fig=True)


def inner_erased(inp, out):
    p = _parse(inp)
    g = [row[:] for row in out]
    by0, bx0, by1, bx1 = p["blk"]
    for y in range(by0, by1 + 1):
        for x in range(bx0, bx1 + 1):
            g[y][x] = p["outer"]
    return g


def swap_fig_colors(inp, out):
    p = _parse(inp)
    g = [row[:] for row in out]
    y0, x0, y1, x1 = p["box"]
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if inp[y][x] == p["outer"]:
                g[y][x] = p["inner"]
            elif inp[y][x] == p["inner"]:
                g[y][x] = p["outer"]
    return g


def crop_ring(inp, out):
    p = _parse(inp)
    full = _ring(inp, p, p["th"], p["tw"], p["inner"])
    y0, x0, y1, x1 = p["box"]
    t, l = p["th"], p["tw"]
    return [row[max(0, x0 - l):x1 + l + 1]
            for row in full[max(0, y0 - t):y1 + t + 1]]


def crop_fig(inp, out):
    p = _parse(inp)
    y0, x0, y1, x1 = p["box"]
    return [row[x0:x1 + 1] for row in inp[y0:y1 + 1]]


def ring_around_inner(inp, out):
    p = _parse(inp)
    by0, bx0, by1, bx1 = p["blk"]
    g = [row[:] for row in inp]
    for y in range(max(0, by0 - p["th"]), min(p["h"], by1 + p["th"] + 1)):
        for x in range(max(0, bx0 - p["tw"]), min(p["w"], bx1 + p["tw"] + 1)):
            if not (by0 <= y <= by1 and bx0 <= x <= bx1):
                g[y][x] = p["inner"]
    return g


ALTERNATIVES = [
    ("ring of the inner block's color but only 1 cell thick", thin_ring),
    ("ring one cell thicker than the inner block size", thick_plus_one),
    ("ring painted in the outer figure's color instead of the inner block's", outer_color_ring),
    ("ring added only on the left and right sides", sides_only),
    ("ring added only below and to the right of the figure", forward_only),
    ("ring painted as a solid rectangle covering the figure", solid_fill),
    ("ring correct but inner block erased to the outer color", inner_erased),
    ("ring correct but outer and inner colors of the figure swapped", swap_fig_colors),
    ("output cropped to the ring's bounding box", crop_ring),
    ("output is only the original figure cropped", crop_fig),
    ("ring drawn around the inner block instead of the whole figure", ring_around_inner),
]


def _valid(g, truth):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != truth)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/3a301edc.json').read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for name, fn in ALTERNATIVES:
        n = 0
        for pr in pairs:
            g = fn(pr["input"], pr["output"])
            if g is not None and _valid(g, pr["output"]):
                n += 1
        print(n, name)
