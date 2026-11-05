"""Near-miss rules for ARC task 1478ab18.

Rule: the rarest color marks cells. Two marks on a common diagonal that are
farthest apart form the hypotenuse of a right triangle. The right angle sits at
the box corner that holds no mark. The triangle outline is drawn in color 8,
except at marks.
"""
import json
from collections import Counter
from pathlib import Path


def _copy(g):
    return [row[:] for row in g]


def _marks(inp):
    cnt = Counter(v for row in inp for v in row)
    col = min(cnt, key=lambda k: (cnt[k], k))
    return col, [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == col]


def _bg(inp):
    return Counter(v for row in inp for v in row).most_common(1)[0][0]


def _pairs(marks):
    res = []
    for i, p in enumerate(marks):
        for q in marks[i + 1:]:
            dr, dc = q[0] - p[0], q[1] - p[1]
            if dr != 0 and abs(dr) == abs(dc):
                res.append((abs(dr), p, q))
    return res


def _ink(inp, out):
    vals = Counter()
    for ri, ro in zip(inp, out):
        for a, b in zip(ri, ro):
            if a != b:
                vals[b] += 1
    return vals.most_common(1)[0][0]


def _cross(p, q, x):
    return (q[0] - p[0]) * (x[1] - p[1]) - (q[1] - p[1]) * (x[0] - p[0])


def _region(p, q, c):
    sc = _cross(p, q, c)
    r0, r1 = sorted((p[0], q[0]))
    c0, c1 = sorted((p[1], q[1]))
    cells = set()
    for r in range(r0, r1 + 1):
        for k in range(c0, c1 + 1):
            s = _cross(p, q, (r, k))
            if s == 0 or (s > 0) == (sc > 0):
                cells.add((r, k))
    return cells


def _split(p, q, c, region):
    hyp = {x for x in region if _cross(p, q, x) == 0}
    legs = {x for x in region if x[0] == c[0] or x[1] == c[1]}
    return hyp, legs


def _corners(p, q):
    return [(p[0], q[1]), (q[0], p[1])]


def _setup(inp, out, shortest=False):
    mcol, marks = _marks(inp)
    prs = _pairs(marks)
    if not prs:
        return None
    pick = min(prs) if shortest else max(prs)
    _, p, q = pick
    cs = _corners(p, q)
    mset = set(marks)
    free = [c for c in cs if c not in mset]
    if shortest:
        if not free:
            return None
        # choose the corner whose triangle holds the most other marks
        c = max(free, key=lambda x: len(_region(p, q, x) & (mset - {p, q})))
        return mcol, marks, p, q, c, [x for x in cs if x != c][0]
    free = [c for c in cs if out[c[0]][c[1]] != inp[c[0]][c[1]]]
    if len(free) != 1:
        return None
    c = free[0]
    return mcol, marks, p, q, c, [x for x in cs if x != c][0]


def _paint(inp, cells, val):
    g = _copy(inp)
    for r, c in cells:
        g[r][c] = val
    return g


def alt_mark_color(inp, out):
    mcol, _ = _marks(inp)
    ink = _ink(inp, out)
    return [[mcol if v == ink else v for v in row] for row in out]


def alt_mirror(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    mcol, marks, p, q, c, other = s
    return _paint(inp, _region(p, q, other) - set(marks), _ink(inp, out))


def alt_solid(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    mcol, marks, p, q, c, other = s
    return _paint(inp, _region(p, q, c) - set(marks), _ink(inp, out))


def alt_interior(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    mcol, marks, p, q, c, other = s
    reg = _region(p, q, c)
    hyp, legs = _split(p, q, c, reg)
    return _paint(inp, reg - hyp - legs - set(marks), _ink(inp, out))


def alt_box(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    mcol, marks, p, q, c, other = s
    reg = _region(p, q, c) | _region(p, q, other)
    return _paint(inp, reg - set(marks), _ink(inp, out))


def alt_no_hypotenuse(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    mcol, marks, p, q, c, other = s
    hyp, _ = _split(p, q, c, _region(p, q, c))
    g = _copy(out)
    bg = _bg(inp)
    for r, k in hyp:
        if (r, k) not in set(marks):
            g[r][k] = bg
    return g


def alt_overpaint_marks(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    mcol, marks, p, q, c, other = s
    reg = _region(p, q, c)
    g = _copy(out)
    for r, k in reg:
        g[r][k] = _ink(inp, out)
    return g


def alt_shortest_pair(inp, out):
    s = _setup(inp, out, shortest=True)
    if not s:
        return None
    mcol, marks, p, q, c, other = s
    return _paint(inp, _region(p, q, c) - set(marks), _ink(inp, out))


def alt_hypotenuse_line(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    mcol, marks, p, q, c, other = s
    hyp, _ = _split(p, q, c, _region(p, q, c))
    return _paint(inp, hyp - set(marks), _ink(inp, out))


def alt_legs_only(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    mcol, marks, p, q, c, other = s
    _, legs = _split(p, q, c, _region(p, q, c))
    return _paint(inp, legs - set(marks), _ink(inp, out))


def alt_ink_marks_corner_extra(inp, out):
    """Fill is right, but the free right-angle corner cell itself is left unpainted."""
    s = _setup(inp, out)
    if not s:
        return None
    mcol, marks, p, q, c, other = s
    g = _copy(out)
    g[c[0]][c[1]] = inp[c[0]][c[1]]
    return g


ALTERNATIVES = [
    ("fill the triangle with the mark color instead of the new color", alt_mark_color),
    ("put the right angle at the marked corner (triangle on the wrong side of the hypotenuse)", alt_mirror),
    ("fill the triangle solid instead of drawing only its outline", alt_solid),
    ("fill only the strict interior, leaving the three sides unpainted", alt_interior),
    ("fill the whole bounding box of the hypotenuse pair", alt_box),
    ("leave the hypotenuse diagonal unpainted", alt_no_hypotenuse),
    ("paint over marks inside the triangle and at its vertices with the new color", alt_overpaint_marks),
    ("take the closest diagonal mark pair as the hypotenuse", alt_shortest_pair),
    ("draw only the hypotenuse diagonal line", alt_hypotenuse_line),
    ("draw only the two legs from the right angle", alt_legs_only),
    ("leave the right-angle corner cell unpainted", alt_ink_marks_corner_extra),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/1478ab18.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
