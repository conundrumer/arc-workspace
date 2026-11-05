import json
from pathlib import Path


def _setup(inp):
    """Return (cells, near, far) where each is a list parallel to cells:
    (dir, color) toward the nearer / farther edge, plus the axis flag."""
    h, w = len(inp), len(inp[0])
    vertical = len(set(inp[0])) == 1 and inp[0][0] != 0 and len(set(inp[-1])) == 1 and inp[-1][0] != 0
    items = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 1:
                continue
            if vertical:
                a, b = r, h - 1 - r
                first = ((-1, 0), inp[0][0])
                second = ((1, 0), inp[-1][0])
            else:
                a, b = c, w - 1 - c
                first = ((0, -1), inp[r][0])
                second = ((0, 1), inp[r][-1])
            near, far = (first, second) if a < b else (second, first)
            items.append(((r, c), near, far, vertical))
    return items


def _paint(inp, placements):
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for (r, c), col in placements:
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = col
    return g


def _build(inp, fn):
    pl = []
    for (r, c), near, far, vert in _setup(inp):
        pl.extend(fn(r, c, near, far, vert))
    return _paint(inp, pl)


def far_side(inp, out):
    return _build(inp, lambda r, c, n, f, v: [((r + f[0][0], c + f[0][1]), f[1])])


def near_dir_far_color(inp, out):
    return _build(inp, lambda r, c, n, f, v: [((r + n[0][0], c + n[0][1]), f[1])])


def far_dir_near_color(inp, out):
    return _build(inp, lambda r, c, n, f, v: [((r + f[0][0], c + f[0][1]), n[1])])


def full_line(inp, out):
    def fn(r, c, n, f, v):
        d, col = n
        res = []
        rr, cc = r + d[0], c + d[1]
        h, w = len(inp), len(inp[0])
        while 0 < rr < h - 1 and 0 < cc < w - 1 or (not v and 0 < cc < w - 1 and 0 <= rr < h) or (v and 0 < rr < h - 1 and 0 <= cc < w):
            if inp[rr][cc] == 0:
                res.append(((rr, cc), col))
            rr, cc = rr + d[0], cc + d[1]
        return res
    return _build(inp, fn)


def length_two(inp, out):
    return _build(inp, lambda r, c, n, f, v: [((r + n[0][0] * k, c + n[0][1] * k), n[1]) for k in (1, 2)])


def only_first_edge(inp, out):
    """Tails only for cells nearer the top/left edge."""
    g = [row[:] for row in out]
    for (r, c), n, f, v in _setup(inp):
        if n[0] in ((1, 0), (0, 1)):
            g[r + n[0][0]][c + n[0][1]] = inp[r + n[0][0]][c + n[0][1]]
    return g


def perpendicular(inp, out):
    def fn(r, c, n, f, v):
        d = (n[0][1], n[0][0])
        return [((r + abs(d[0]), c + abs(d[1])), n[1])]
    return _build(inp, fn)


def replace_cell(inp, out):
    return _build(inp, lambda r, c, n, f, v: [((r, c), n[1])])


def gap_one(inp, out):
    return _build(inp, lambda r, c, n, f, v: [((r + 2 * n[0][0], c + 2 * n[0][1]), n[1])])


def first_color_only(inp, out):
    def fn(r, c, n, f, v):
        first = n if n[0] in ((-1, 0), (0, -1)) else f
        return [((r + n[0][0], c + n[0][1]), first[1])]
    return _build(inp, fn)


def both_sides(inp, out):
    return _build(inp, lambda r, c, n, f, v: [((r + n[0][0], c + n[0][1]), n[1]), ((r + f[0][0], c + f[0][1]), f[1])])


def no_tails_for_cells_near_far_margin(inp, out):
    """Tail only for cells whose nearer distance is at least 3 (misses short ones)."""
    g = [row[:] for row in out]
    h, w = len(inp), len(inp[0])
    for (r, c), n, f, v in _setup(inp):
        dist = r if v and n[0][0] < 0 else (h - 1 - r if v else (c if n[0][1] < 0 else w - 1 - c))
        if dist < 4:
            rr, cc = r + n[0][0], c + n[0][1]
            g[rr][cc] = inp[rr][cc]
    return g


ALTERNATIVES = [
    ("tail goes on the side of the farther edge, in the farther edge's color", far_side),
    ("tail goes on the nearer side but takes the farther edge's color", near_dir_far_color),
    ("tail goes on the farther side but takes the nearer edge's color", far_dir_near_color),
    ("tail grows as a full line from the 1 to the nearer edge", full_line),
    ("tail is two cells long", length_two),
    ("only cells nearer the top or left edge get a tail", only_first_edge),
    ("tail goes perpendicular to the edge axis, in the nearer edge's color", perpendicular),
    ("the 1 cell itself is recolored instead of adding a tail", replace_cell),
    ("tail is placed one cell too far, leaving a gap", gap_one),
    ("every tail takes the top or left edge's color", first_color_only),
    ("tails grow toward both edges, each in its own edge's color", both_sides),
    ("cells close to an edge (distance under 4) get no tail", no_tails_for_cells_near_far_margin),
]


def _valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/642248e4.json").read_text())
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
