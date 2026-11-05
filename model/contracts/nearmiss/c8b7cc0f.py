import json
from collections import Counter
from pathlib import Path


def _info(inp):
    cnt = Counter(v for r in inp for v in r if v)
    frame = cnt.most_common(1)[0][0]
    dot = [c for c in cnt if c != frame][0]
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == frame]
    r0 = min(i for i, _ in cells)
    r1 = max(i for i, _ in cells)
    c0 = min(j for _, j in cells)
    c1 = max(j for _, j in cells)
    return frame, dot, (r0, r1, c0, c1)


def _dots(inp):
    frame, dot, (r0, r1, c0, c1) = _info(inp)
    ins, outs = [], []
    for i, r in enumerate(inp):
        for j, v in enumerate(r):
            if v == dot:
                if r0 < i < r1 and c0 < j < c1:
                    ins.append((i, j))
                else:
                    outs.append((i, j))
    return ins, outs


def _fill(n, dot, order, bg=0, size=3):
    g = [[bg] * size for _ in range(size)]
    for k, (i, j) in enumerate(order):
        if k < n:
            g[i][j] = dot
    return g


ROW_MAJOR = [(i, j) for i in range(3) for j in range(3)]
COL_MAJOR = [(i, j) for j in range(3) for i in range(3)]


def _make(order, count_fn, color_fn=None):
    def f(inp, out):
        frame, dot, _ = _info(inp)
        n = count_fn(inp)
        if n > 9:
            return None
        return _fill(n, dot if color_fn is None else color_fn(inp), order)
    return f


def _n_inside(inp):
    return len(_dots(inp)[0])


def _n_all(inp):
    a, b = _dots(inp)
    return len(a) + len(b)


def _n_outside(inp):
    return len(_dots(inp)[1])


def _n_comp8(inp):
    ins = set(_dots(inp)[0])
    seen = set()
    k = 0
    for p in ins:
        if p in seen:
            continue
        k += 1
        st = [p]
        seen.add(p)
        while st:
            a, b = st.pop()
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    q = (a + di, b + dj)
                    if q in ins and q not in seen:
                        seen.add(q)
                        st.append(q)
    return k


def _frame_color(inp):
    return _info(inp)[0]


def _row_output(inp, out):
    _, dot, _ = _info(inp)
    n = _n_inside(inp)
    return [[dot] * n]


def _interior_crop(inp, out):
    _, _, (r0, r1, c0, c1) = _info(inp)
    return [r[c0 + 1:c1] for r in inp[r0 + 1:r1]]


def _inverted(inp, out):
    _, dot, _ = _info(inp)
    return [[dot if v == 0 else 0 for v in r] for r in out]


def _plus_one(inp, out):
    _, dot, _ = _info(inp)
    n = _n_inside(inp) + 1
    return _fill(min(n, 9), dot, ROW_MAJOR) if n <= 9 else None


def _minus_one(inp, out):
    _, dot, _ = _info(inp)
    n = _n_inside(inp) - 1
    return _fill(n, dot, ROW_MAJOR)


def _bottom_right_first(inp, out):
    _, dot, _ = _info(inp)
    return _fill(_n_inside(inp), dot, ROW_MAJOR[::-1])


def _top_right_cols(inp, out):
    _, dot, _ = _info(inp)
    order = [(i, j) for i in range(3) for j in range(2, -1, -1)]
    return _fill(_n_inside(inp), dot, order)


def _bbox_size(inp, out):
    # output sized like the frame box interior, filled row-major
    _, dot, (r0, r1, c0, c1) = _info(inp)
    h, w = r1 - r0 - 1, c1 - c0 - 1
    n = _n_inside(inp)
    g = [[0] * w for _ in range(h)]
    for k in range(min(n, h * w)):
        g[k // w][k % w] = dot
    return g


ALTERNATIVES = [
    ("count all dots, inside and outside the outline",
     _make(ROW_MAJOR, _n_all)),
    ("count only the dots outside the outline",
     _make(ROW_MAJOR, _n_outside)),
    ("fill column by column instead of row by row",
     _make(COL_MAJOR, _n_inside)),
    ("fill starting at the top-right corner, right to left",
     _top_right_cols),
    ("fill starting at the bottom-right corner, reverse order",
     _bottom_right_first),
    ("count is one too high", _plus_one),
    ("count is one too low", _minus_one),
    ("filled cells take the frame color instead of the dot color",
     _make(ROW_MAJOR, _n_inside, _frame_color)),
    ("count 8-connected dot groups inside instead of dot cells",
     _make(ROW_MAJOR, _n_comp8)),
    ("output is one row of dot-colored cells, one per inside dot",
     _row_output),
    ("output is the cropped interior of the outline", _interior_crop),
    ("fill and background colors swapped in the output", _inverted),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/c8b7cc0f.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            if (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                    and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                    and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                    and g != p["output"]):
                ok += 1
        print(ok, desc)
