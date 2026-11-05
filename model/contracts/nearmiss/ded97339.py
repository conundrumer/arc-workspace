import json
from pathlib import Path


def marks(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v]


def segments(inp):
    """Segments between consecutive same-color marks in a row or column.
    Each is (axis, fixed, start, end, color); axis 'h' = row, 'v' = column."""
    segs = []
    ms = marks(inp)
    for v in {m[2] for m in ms}:
        pts = [(r, c) for r, c, x in ms if x == v]
        for r in sorted({p[0] for p in pts}):
            cs = sorted(c for rr, c in pts if rr == r)
            for a, b in zip(cs, cs[1:]):
                segs.append(("h", r, a, b, v))
        for c in sorted({p[1] for p in pts}):
            rs = sorted(r for r, cc in pts if cc == c)
            for a, b in zip(rs, rs[1:]):
                segs.append(("v", c, a, b, v))
    return segs


def paint(grid, seg, lo_pad=0, hi_pad=0, color=None, include_ends=True):
    axis, fixed, a, b, v = seg
    h, w = len(grid), len(grid[0])
    col = v if color is None else color
    for t in range(a + lo_pad, b + hi_pad + 1):
        r, c = (fixed, t) if axis == "h" else (t, fixed)
        if 0 <= r < h and 0 <= c < w:
            grid[r][c] = col


def blank(inp):
    return [row[:] for row in inp]


def only_rows(inp, out):
    g = blank(inp)
    for s in segments(inp):
        if s[0] == "h":
            paint(g, s)
    return g


def only_cols(inp, out):
    g = blank(inp)
    for s in segments(inp):
        if s[0] == "v":
            paint(g, s)
    return g


def to_border(inp, out):
    g = blank(inp)
    h, w = len(inp), len(inp[0])
    for axis, fixed, a, b, v in segments(inp):
        for t in range(h if axis == "v" else w):
            if axis == "h":
                g[fixed][t] = v
            else:
                g[t][fixed] = v
    return g


def wrong_color(inp, out):
    g = blank(out)
    for r, row in enumerate(out):
        for c, v in enumerate(row):
            if v and not inp[r][c]:
                g[r][c] = 5 if v != 5 else 1
    return g


def one_short(inp, out):
    g = blank(inp)
    for s in segments(inp):
        paint(g, s, lo_pad=2, hi_pad=-2)
    return g


def all_through_marks(inp, out):
    g = blank(inp)
    h, w = len(inp), len(inp[0])
    for r, c, v in marks(inp):
        for t in range(w):
            g[r][t] = v
        for t in range(h):
            g[t][c] = v
    return g


def first_line_only(inp, out):
    segs = segments(inp)
    if not segs:
        return None
    segs.sort(key=lambda s: (s[2] if s[0] == "v" else s[1], s[1] if s[0] == "v" else s[2]))
    s = min(segs, key=lambda s: (s[1], s[2]) if s[0] == "h" else (s[2], s[1]))
    g = blank(inp)
    paint(g, s)
    return g


def drop_unpaired(inp, out):
    g = blank(out)
    paired = set()
    for axis, fixed, a, b, v in segments(inp):
        for t in (a, b):
            paired.add((fixed, t) if axis == "h" else (t, fixed))
    for r, c, v in marks(inp):
        if (r, c) not in paired:
            g[r][c] = 0
    return g


def overshoot(inp, out):
    g = blank(inp)
    for s in segments(inp):
        paint(g, s, lo_pad=-1, hi_pad=1)
    return g


def short_only(inp, out):
    g = blank(inp)
    for s in segments(inp):
        if s[3] - s[2] <= 4:
            paint(g, s)
    return g


def transposed(inp, out):
    return [list(row) for row in zip(*out)]


ALTERNATIVES = [
    ("connect same-colored marks only along rows", only_rows),
    ("connect same-colored marks only along columns", only_cols),
    ("extend each connecting line to the grid border", to_border),
    ("fill the connecting lines with color 5 instead of the mark color", wrong_color),
    ("lines stop one cell short of the marks at both ends", one_short),
    ("draw the full row and column through every mark, paired or not", all_through_marks),
    ("draw only the first connecting line", first_line_only),
    ("erase marks that have no partner", drop_unpaired),
    ("lines overshoot each end by one cell", overshoot),
    ("connect only marks that are close together (4 cells or fewer apart)", short_only),
    ("output transposed (wrong orientation)", transposed),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(type(x) is int and 0 <= x <= 9 for r in g for x in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/ded97339.json"))
    train = task["train"]
    print("pairs", len(train))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
