import json
from collections import Counter
from pathlib import Path

FILL = 2


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _ink(inp):
    bg = _bg(inp)
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != bg]


def _bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def _paint(inp, pred, color=FILL):
    bg = _bg(inp)
    return [[color if (v == bg and pred(r, c)) else v for c, v in enumerate(row)]
            for r, row in enumerate(inp)]


def _components(inp, diag):
    cells = set(_ink(inp))
    steps = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    if diag:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    seen, comps = set(), []
    for s in sorted(cells):
        if s in seen:
            continue
        stack, comp = [s], []
        seen.add(s)
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for dr, dc in steps:
                n = (r + dr, c + dc)
                if n in cells and n not in seen:
                    seen.add(n)
                    stack.append(n)
        comps.append(comp)
    return comps


def wrong_color(inp, out):
    return [[3 if v == FILL else v for v in row] for row in out]


def ink_color_fill(inp, out):
    ink = Counter(v for r, c in _ink(inp) for v in [inp[r][c]]).most_common(1)[0][0]
    return [[ink if v == FILL else v for v in row] for row in out]


def shrunk_box(inp, out):
    r0, r1, c0, c1 = _bbox(_ink(inp))
    g = _paint(inp, lambda r, c: r0 + 1 <= r <= r1 - 1 and c0 + 1 <= c <= c1 - 1)
    return g


def grown_box(inp, out):
    r0, r1, c0, c1 = _bbox(_ink(inp))
    return _paint(inp, lambda r, c: r0 - 1 <= r <= r1 + 1 and c0 - 1 <= c <= c1 + 1)


def row_span_only(inp, out):
    ink = _ink(inp)
    span = {}
    for r, c in ink:
        lo, hi = span.get(r, (c, c))
        span[r] = (min(lo, c), max(hi, c))
    return _paint(inp, lambda r, c: r in span and span[r][0] <= c <= span[r][1])


def col_span_only(inp, out):
    span = {}
    for r, c in _ink(inp):
        lo, hi = span.get(c, (r, r))
        span[c] = (min(lo, r), max(hi, r))
    return _paint(inp, lambda r, c: c in span and span[c][0] <= r <= span[c][1])


def overwrite_ink(inp, out):
    r0, r1, c0, c1 = _bbox(_ink(inp))
    return [[FILL if (r0 <= r <= r1 and c0 <= c <= c1) else v for c, v in enumerate(row)]
            for r, row in enumerate(inp)]


def upper_half_box(inp, out):
    r0, r1, c0, c1 = _bbox(_ink(inp))
    mid = (r0 + r1) // 2
    return _paint(inp, lambda r, c: r0 <= r <= mid and c0 <= c <= c1)


def cropped_to_box(inp, out):
    r0, r1, c0, c1 = _bbox(_ink(inp))
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def full_width_rows(inp, out):
    r0, r1, _, _ = _bbox(_ink(inp))
    return _paint(inp, lambda r, c: r0 <= r <= r1)


def enclosed_only(inp, out):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    stack = [(r, c) for r in range(h) for c in range(w)
             if (r in (0, h - 1) or c in (0, w - 1)) and inp[r][c] == bg]
    seen.update(stack)
    while stack:
        r, c = stack.pop()
        for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            n = (r + dr, c + dc)
            if 0 <= n[0] < h and 0 <= n[1] < w and inp[n[0]][n[1]] == bg and n not in seen:
                seen.add(n)
                stack.append(n)
    return _paint(inp, lambda r, c: (r, c) not in seen)


def touching_ink_only(inp, out):
    r0, r1, c0, c1 = _bbox(_ink(inp))
    ink = set(_ink(inp))
    def near(r, c):
        return any((r + dr, c + dc) in ink for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)))
    return _paint(inp, lambda r, c: r0 <= r <= r1 and c0 <= c <= c1 and near(r, c))


ALTERNATIVES = [
    ("fill with color 3 instead of 2", wrong_color),
    ("fill with the ink color instead of the new color", ink_color_fill),
    ("fill only the bounding box interior, one cell in from each edge", shrunk_box),
    ("fill the bounding box grown by one cell on every side", grown_box),
    ("fill only background cells between the leftmost and rightmost ink in each row", row_span_only),
    ("fill only background cells between the topmost and bottommost ink in each column", col_span_only),
    ("fill the whole bounding box, overwriting ink cells too", overwrite_ink),
    ("fill only the upper half of the bounding box", upper_half_box),
    ("output only the bounding box crop of the filled result", cropped_to_box),
    ("fill every background cell in the ink rows across the full grid width", full_width_rows),
    ("fill only background cells enclosed by ink, not reachable from the grid border", enclosed_only),
    ("fill only box background cells that touch ink by an edge", touching_ink_only),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/6d75e8bb.json'))
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
