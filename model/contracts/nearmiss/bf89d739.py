import json
from collections import Counter
from pathlib import Path


def parts(inp, out):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    dots = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != bg]
    color = next(out[r][c] for r in range(h) for c in range(w) if out[r][c] != inp[r][c])
    pair = None
    for i, a in enumerate(dots):
        for b in dots[i + 1:]:
            if a[0] == b[0]:
                pair = ("row", a, b)
            elif a[1] == b[1]:
                pair = ("col", a, b)
    kind, a, b = pair
    if kind == "row":
        r = a[0]
        c0, c1 = sorted((a[1], b[1]))
        trunk = [(r, c) for c in range(c0 + 1, c1)]
        lo, hi = c0, c1
        line = r
    else:
        c = a[1]
        r0, r1 = sorted((a[0], b[0]))
        trunk = [(r, c) for r in range(r0 + 1, r1)]
        lo, hi = r0, r1
        line = c
    branches = []
    for d in dots:
        if d in (a, b):
            continue
        pos = d[1] if kind == "row" else d[0]
        off = d[0] if kind == "row" else d[1]
        if lo < pos < hi:
            step = 1 if line > off else -1
            if kind == "row":
                cells = [(x, pos) for x in range(off + step, line, step)]
            else:
                cells = [(pos, x) for x in range(off + step, line, step)]
            branches.append((d, cells, off - line))
    return dict(h=h, w=w, bg=bg, dots=dots, color=color, kind=kind, a=a, b=b,
                trunk=trunk, lo=lo, hi=hi, line=line, branches=branches)


def render(inp, p, cells, color=None):
    g = [row[:] for row in inp]
    for r, c in cells:
        if g[r][c] == p["bg"]:
            g[r][c] = p["color"] if color is None else color
    return g


def all_branch(p):
    return [c for _, cs, _ in p["branches"] for c in cs]


def no_branches(inp, out):
    p = parts(inp, out)
    return render(inp, p, p["trunk"])


def no_trunk(inp, out):
    p = parts(inp, out)
    return render(inp, p, all_branch(p))


def dot_color_lines(inp, out):
    p = parts(inp, out)
    dc = inp[p["a"][0]][p["a"][1]]
    return render(inp, p, p["trunk"] + all_branch(p), color=dc)


def trunk_full_line(inp, out):
    p = parts(inp, out)
    if p["kind"] == "row":
        full = [(p["line"], c) for c in range(p["w"])]
    else:
        full = [(r, p["line"]) for r in range(p["h"])]
    return render(inp, p, full + all_branch(p))


def branch_short_by_one(inp, out):
    p = parts(inp, out)
    cells = []
    for _, cs, _ in p["branches"]:
        cells += cs[:-1]
    return render(inp, p, p["trunk"] + cells)


def branch_through_trunk(inp, out):
    p = parts(inp, out)
    cells = []
    for d, cs, sign in p["branches"]:
        pos = d[1] if p["kind"] == "row" else d[0]
        if p["kind"] == "row":
            cells += [(r, pos) for r in range(p["h"]) if r != d[0]]
        else:
            cells += [(pos, c) for c in range(p["w"]) if c != d[1]]
    return render(inp, p, p["trunk"] + cells)


def one_side_only(inp, out):
    p = parts(inp, out)
    cells = [c for _, cs, s in p["branches"] if s < 0 for c in cs]
    return render(inp, p, p["trunk"] + cells)


def nearest_dot_only(inp, out):
    p = parts(inp, out)
    if not p["branches"]:
        return None
    best = min(p["branches"], key=lambda t: abs(t[2]))
    return render(inp, p, p["trunk"] + best[1])


def pair_endpoints_overwritten(inp, out):
    p = parts(inp, out)
    g = render(inp, p, p["trunk"] + all_branch(p))
    for r, c in (p["a"], p["b"]):
        g[r][c] = p["color"]
    return g


def branch_parallel(inp, out):
    p = parts(inp, out)
    cells = []
    for d, _, _ in p["branches"]:
        if p["kind"] == "row":
            cells += [(d[0], c) for c in range(p["lo"] + 1, p["hi"])]
        else:
            cells += [(r, d[1]) for r in range(p["lo"] + 1, p["hi"])]
    return render(inp, p, p["trunk"] + cells)


def crop_to_dots_box(inp, out):
    p = parts(inp, out)
    rs = [r for r, _ in p["dots"]]
    cs = [c for _, c in p["dots"]]
    return [row[min(cs):max(cs) + 1] for row in out[min(rs):max(rs) + 1]]


ALTERNATIVES = [
    ("only the trunk between the aligned pair is drawn; off-line dots do not branch", no_branches),
    ("only the branches are drawn; the trunk between the aligned pair stays empty", no_trunk),
    ("lines are drawn in the dot color 2 instead of the new line color", dot_color_lines),
    ("the trunk runs across the whole grid, not only between the pair", trunk_full_line),
    ("each branch stops one cell short of the trunk", branch_short_by_one),
    ("each branch continues through the trunk to the grid edge", branch_through_trunk),
    ("only dots on the low-index side of the trunk branch", one_side_only),
    ("only the dot nearest the trunk branches", nearest_dot_only),
    ("the pair's own dots are overpainted with the line color", pair_endpoints_overwritten),
    ("each off-line dot draws its line parallel to the trunk across the pair's span", branch_parallel),
    ("output is cropped to the bounding box of the dots", crop_to_dots_box),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/bf89d739.json"))
    pairs = task["train"]
    for pr in pairs:
        p = parts(pr["input"], pr["output"])
        assert render(pr["input"], p, p["trunk"] + all_branch(p)) == pr["output"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in pairs:
            g = fn(pr["input"], pr["output"])
            if g is not None and valid(g, pr["output"]):
                n += 1
        print(n, desc)
