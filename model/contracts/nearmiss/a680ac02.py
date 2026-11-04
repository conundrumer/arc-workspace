from pathlib import Path
import json


def squares(inp):
    """Return list of dicts: color, r, c (top-left), hollow, grid (4x4)."""
    cells = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v:
                cells.setdefault(v, []).append((r, c))
    res = []
    for col, cs in cells.items():
        r0 = min(r for r, _ in cs)
        c0 = min(c for _, c in cs)
        g = [[inp[r0 + i][c0 + j] for j in range(4)] for i in range(4)]
        res.append(dict(color=col, r=r0, c=c0, hollow=len(cs) == 12, grid=g))
    return res


def hollow(inp):
    return [s for s in squares(inp) if s["hollow"]]


def true_axis(inp):
    """0 = stack vertically (row extents disjoint), 1 = side by side."""
    h = hollow(inp)
    rows_disjoint = all(a["r"] + 4 <= b["r"] or b["r"] + 4 <= a["r"]
                        for i, a in enumerate(h) for b in h[i + 1:])
    return 0 if rows_disjoint else 1


def lay(sqs, axis, gap=0, step=4):
    n = len(sqs)
    size = step * (n - 1) + 4 + gap * (n - 1) if step == 4 else step * (n - 1) + 4
    if step == 4:
        size = 4 * n + gap * (n - 1)
    h, w = (size, 4) if axis == 0 else (4, size)
    g = [[0] * w for _ in range(h)]
    for k, s in enumerate(sqs):
        off = k * (step + gap)
        for i in range(4):
            for j in range(4):
                v = s["grid"][i][j]
                r, c = (off + i, j) if axis == 0 else (i, off + j)
                if v or g[r][c] == 0:
                    g[r][c] = v if v else g[r][c]
    return g


def order(sqs, axis):
    key = (lambda s: s["r"]) if axis == 0 else (lambda s: s["c"])
    return sorted(sqs, key=key)


def ordered_true(inp):
    ax = true_axis(inp)
    return order(hollow(inp), ax), ax


def all_squares_true_axis(inp, out):
    ax = true_axis(inp)
    return lay(order(squares(inp), ax), ax)


def wrong_axis(inp, out):
    ax = 1 - true_axis(inp)
    return lay(order(hollow(inp), ax), ax)


def reverse_order(inp, out):
    s, ax = ordered_true(inp)
    return lay(s[::-1], ax)


def gap_one(inp, out):
    s, ax = ordered_true(inp)
    return lay(s, ax, gap=1)


def solid_only(inp, out):
    ax = true_axis(inp)
    s = [q for q in squares(inp) if not q["hollow"]]
    return lay(order(s, ax), ax)


def holes_filled(inp, out):
    s, ax = ordered_true(inp)
    s = [dict(q, grid=[[q["color"]] * 4 for _ in range(4)]) for q in s]
    return lay(s, ax)


def drop_last(inp, out):
    s, ax = ordered_true(inp)
    return lay(s[:-1], ax)


def by_color(inp, out):
    s, ax = ordered_true(inp)
    return lay(sorted(s, key=lambda q: q["color"]), ax)


def crop_bbox(inp, out):
    s = hollow(inp)
    r0 = min(q["r"] for q in s)
    r1 = max(q["r"] for q in s) + 4
    c0 = min(q["c"] for q in s)
    c1 = max(q["c"] for q in s) + 4
    return [row[c0:c1] for row in inp[r0:r1]]


def overlap_one(inp, out):
    s, ax = ordered_true(inp)
    return lay(s, ax, step=3)


def axis_by_all_bbox(inp, out):
    sq = squares(inp)
    h = max(q["r"] for q in sq) + 4 - min(q["r"] for q in sq)
    w = max(q["c"] for q in sq) + 4 - min(q["c"] for q in sq)
    ax = 0 if h > w else 1
    return lay(order(hollow(inp), ax), ax)


def order_by_other_coord(inp, out):
    ax = true_axis(inp)
    s = order(hollow(inp), 1 - ax)
    return lay(s, ax)


def one_color(inp, out):
    s, ax = ordered_true(inp)
    c = s[0]["color"]
    s = [dict(q, grid=[[c if v else 0 for v in row] for row in q["grid"]]) for q in s]
    return lay(s, ax)


ALTERNATIVES = [
    ("keep solid squares too, lined up along the correct axis", all_squares_true_axis),
    ("line the hollow squares up along the wrong axis", wrong_axis),
    ("hollow squares in reverse input order", reverse_order),
    ("one blank cell between neighboring squares", gap_one),
    ("keep only the solid squares", solid_only),
    ("hollow squares with the 2x2 hole filled in their color", holes_filled),
    ("drop the last hollow square", drop_last),
    ("order the squares by color value", by_color),
    ("crop the bounding box of the hollow squares from the input", crop_bbox),
    ("squares overlap by one cell when placed", overlap_one),
    ("axis from the longer side of the bounding box of all squares", axis_by_all_bbox),
    ("order by the coordinate across the layout axis", order_by_other_coord),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    import os
    p = str(Path(__file__).resolve().parents[3] / 'data/tasks/a680ac02.json')
    train = json.load(open(p))["train"]
    print("pairs:", len(train))
    for d, f in ALTERNATIVES:
        n = 0
        for pr in train:
            try:
                g = f(pr["input"], pr["output"])
            except Exception as e:
                print("  error", d, e)
                g = None
            if g is not None and valid(g, pr["output"]):
                n += 1
        print(n, d)
