"""Near-miss rules for ARC task 1a244afd.

Rule: pivots (the color that stays) each pair with one pointer (the color that
disappears) in the same row or column. The pointer is erased. A mark (new
color) is placed at the pivot, offset by the pointer's distance, in the
pointer's direction turned 90 degrees counter-clockwise (dropped if off grid).
"""
import json
from collections import Counter
from pathlib import Path


def ccw(d):
    return (-d[1], d[0])


def cw(d):
    return (d[1], -d[0])


def info(inp, out):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    cols = {v for r in inp for v in r} - {bg}
    pivc = [c for c in cols
            if all(out[i][j] == c for i in range(h) for j in range(w) if inp[i][j] == c)]
    ptrc = [c for c in cols if c not in pivc]
    outnew = {v for r in out for v in r} - {v for r in inp for v in r}
    piv_col, ptr_col = pivc[0], ptrc[0]
    mark = next(iter(outnew))
    pivs = [(i, j) for i in range(h) for j in range(w) if inp[i][j] == piv_col]
    ptrs = [(i, j) for i in range(h) for j in range(w) if inp[i][j] == ptr_col]
    return h, w, bg, piv_col, ptr_col, mark, pivs, ptrs


def matchings(pivs, ptrs):
    res = []

    def go(k, used, acc):
        if k == len(pivs):
            res.append(list(acc))
            return
        p = pivs[k]
        for q in ptrs:
            if q not in used and (q[0] == p[0] or q[1] == p[1]):
                used.add(q)
                acc.append((p, q))
                go(k + 1, used, acc)
                acc.pop()
                used.discard(q)

    go(0, set(), [])
    return res


def sgn(x):
    return (x > 0) - (x < 0)


def build(inp, pairs, bg, mark, place, keep_ptr=False, keep_piv=True, ptr_col=None,
          mark_col=None, wrap=False):
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for p, q in pairs:
        if not keep_ptr:
            g[q[0]][q[1]] = bg
        if not keep_piv:
            g[p[0]][p[1]] = bg
    for p, q in pairs:
        pos = place(p, q)
        if pos is None:
            continue
        i, j = pos
        if wrap:
            i, j = i % h, j % w
        if 0 <= i < h and 0 <= j < w:
            g[i][j] = mark if mark_col is None else mark_col
    return g


def true_place(p, q, turn=ccw, extra=0):
    d = (sgn(q[0] - p[0]), sgn(q[1] - p[1]))
    k = abs(q[0] - p[0]) + abs(q[1] - p[1]) + extra
    t = turn(d)
    return (p[0] + t[0] * k, p[1] + t[1] * k)


def correct_pairs(inp, out):
    h, w, bg, pc, qc, mark, pivs, ptrs = info(inp, out)
    for m in matchings(pivs, ptrs):
        if build(inp, m, bg, mark, true_place) == out:
            return m
    # fall back: any matching
    ms = matchings(pivs, ptrs)
    return ms[0] if ms else []


def make(place_fn, **kw):
    def f(inp, out):
        h, w, bg, pc, qc, mark, pivs, ptrs = info(inp, out)
        pairs = correct_pairs(inp, out)
        return build(inp, pairs, bg, mark, place_fn, **kw)
    return f


def turn_cw(inp, out):
    return make(lambda p, q: true_place(p, q, cw))(inp, out)


def no_turn(inp, out):
    return make(lambda p, q: true_place(p, q, lambda d: d))(inp, out)


def reflect(inp, out):
    return make(lambda p, q: true_place(p, q, lambda d: (-d[0], -d[1])))(inp, out)


def dist_plus_one(inp, out):
    return make(lambda p, q: true_place(p, q, ccw, 1))(inp, out)


def dist_one(inp, out):
    def pl(p, q):
        d = (sgn(q[0] - p[0]), sgn(q[1] - p[1]))
        t = ccw(d)
        return (p[0] + t[0], p[1] + t[1])
    return make(pl)(inp, out)


def keep_pointers(inp, out):
    return make(true_place, keep_ptr=True)(inp, out)


def no_marks(inp, out):
    return make(lambda p, q: None)(inp, out)


def mark_is_pointer_color(inp, out):
    h, w, bg, pc, qc, mark, pivs, ptrs = info(inp, out)
    pairs = correct_pairs(inp, out)
    return build(inp, pairs, bg, mark, true_place, mark_col=qc)


def erase_pivots(inp, out):
    return make(true_place, keep_piv=False)(inp, out)


def rotate_about_pointer(inp, out):
    def pl(p, q):
        # turn the pivot-from-pointer direction around the pointer
        d = (sgn(p[0] - q[0]), sgn(p[1] - q[1]))
        k = abs(q[0] - p[0]) + abs(q[1] - p[1])
        t = ccw(d)
        return (q[0] + t[0] * k, q[1] + t[1] * k)
    return make(pl)(inp, out)


def wrap_around(inp, out):
    h, w = len(inp), len(inp[0])
    pairs = correct_pairs(inp, out)
    if all(0 <= true_place(p, q)[0] < h and 0 <= true_place(p, q)[1] < w for p, q in pairs):
        return None
    return make(true_place, wrap=True)(inp, out)


ALTERNATIVES = [
    ("turn the pointer direction clockwise instead of counter-clockwise", turn_cw),
    ("no turn: mark placed along the pointer direction at the pointer's own distance", no_turn),
    ("mark placed opposite the pointer (reflected through the pivot)", reflect),
    ("mark one cell too far (distance plus one)", dist_plus_one),
    ("mark always adjacent to the pivot regardless of distance", dist_one),
    ("pointers are not erased", keep_pointers),
    ("pointers erased but no marks placed", no_marks),
    ("marks drawn in the pointer color instead of the new color", mark_is_pointer_color),
    ("pivots are erased along with the pointers", erase_pivots),
    ("direction is turned about the pointer instead of the pivot", rotate_about_pointer),
    ("marks falling off the grid wrap around to the opposite edge", wrap_around),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/1a244afd.json"))
    train = task["train"]
    for inp, out in ((p["input"], p["output"]) for p in train):
        assert build(inp, correct_pairs(inp, out), *info(inp, out)[2:3], info(inp, out)[5],
                     true_place) == out, "helper does not reproduce the true output"
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
