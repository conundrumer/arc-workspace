import json
from collections import Counter
from pathlib import Path

LINE = 1


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _line(inp):
    n = len(inp)
    for r in range(n):
        if all(v == LINE for v in inp[r]):
            return ("row", r)
    for c in range(len(inp[0])):
        if all(inp[r][c] == LINE for r in range(n)):
            return ("col", c)
    if all(inp[i][i] == LINE for i in range(n)):
        return ("diag", 0)
    if all(inp[i][n - 1 - i] == LINE for i in range(n)):
        return ("anti", 0)
    return None


def _flip(inp, kind, k, shift=0):
    n = len(inp)
    if kind == "row":
        a = k + shift
        return lambda r, c: (2 * a - r, c)
    if kind == "col":
        a = k + shift
        return lambda r, c: (r, 2 * a - c)
    if kind == "diag":
        return lambda r, c: (c - shift, r + shift)
    return lambda r, c: (n - 1 - c + shift, n - 1 - r + shift)


def _counts(inp):
    bg = _bg(inp)
    cnt = Counter(v for r in inp for v in r if v not in (bg, LINE))
    return bg, cnt


def _render(inp, colors, f, mode="over", paint=None, erase=False):
    bg = _bg(inp)
    g = [row[:] for row in inp]
    h, w = len(inp), len(inp[0])
    if erase:
        for r in range(h):
            for c in range(w):
                if inp[r][c] in colors:
                    g[r][c] = bg
    for r in range(h):
        for c in range(w):
            if inp[r][c] in colors:
                q, d = f(r, c)
                if 0 <= q < h and 0 <= d < w:
                    if mode == "bg" and inp[q][d] != bg:
                        continue
                    g[q][d] = inp[r][c] if paint is None else paint
    return g


def _setup(inp):
    ln = _line(inp)
    bg, cnt = _counts(inp)
    if ln is None or len(cnt) != 2:
        return None
    rare = min(cnt, key=cnt.get)
    common = max(cnt, key=cnt.get)
    return ln, bg, rare, common


def common_color(inp, out):
    ln, bg, rare, common = _setup(inp)
    return _render(inp, {common}, _flip(inp, *ln))


def both_colors(inp, out):
    ln, bg, rare, common = _setup(inp)
    return _render(inp, {rare, common}, _flip(inp, *ln))


def _components(inp, color):
    h, w = len(inp), len(inp[0])
    seen = set()
    n = 0
    for r in range(h):
        for c in range(w):
            if inp[r][c] == color and (r, c) not in seen:
                n += 1
                st = [(r, c)]
                seen.add((r, c))
                while st:
                    a, b = st.pop()
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        x, y = a + da, b + db
                        if 0 <= x < h and 0 <= y < w and inp[x][y] == color and (x, y) not in seen:
                            seen.add((x, y))
                            st.append((x, y))
    return n


def fewest_objects(inp, out):
    ln, bg, rare, common = _setup(inp)
    a, b = rare, common
    pick = a if _components(inp, a) < _components(inp, b) else b
    return _render(inp, {pick}, _flip(inp, *ln))


def perpendicular_axis(inp, out):
    ln, bg, rare, common = _setup(inp)
    n = len(inp)
    kind, k = ln
    if kind == "row":
        new = ("col", (len(inp[0]) - 1) // 2)
    elif kind == "col":
        new = ("row", (n - 1) // 2)
    elif kind == "diag":
        new = ("anti", 0)
    else:
        new = ("diag", 0)
    return _render(inp, {rare}, _flip(inp, *new))


def always_left_right(inp, out):
    ln, bg, rare, common = _setup(inp)
    w = len(inp[0])
    return _render(inp, {rare}, lambda r, c: (r, w - 1 - c))


def point_reflection(inp, out):
    ln, bg, rare, common = _setup(inp)
    h, w = len(inp), len(inp[0])
    return _render(inp, {rare}, lambda r, c: (h - 1 - r, w - 1 - c))


def axis_shifted(inp, out):
    ln, bg, rare, common = _setup(inp)
    return _render(inp, {rare}, _flip(inp, *ln, shift=1))


def move_not_copy(inp, out):
    ln, bg, rare, common = _setup(inp)
    return _render(inp, {rare}, _flip(inp, *ln), erase=True)


def wrong_paint_color(inp, out):
    ln, bg, rare, common = _setup(inp)
    return _render(inp, {rare}, _flip(inp, *ln), paint=common)


def box_fill(inp, out):
    ln, bg, rare, common = _setup(inp)
    f = _flip(inp, *ln)
    h, w = len(inp), len(inp[0])
    pts = [f(r, c) for r in range(h) for c in range(w) if inp[r][c] == rare]
    r0 = min(p[0] for p in pts); r1 = max(p[0] for p in pts)
    c0 = min(p[1] for p in pts); c1 = max(p[1] for p in pts)
    g = [row[:] for row in inp]
    for r in range(max(r0, 0), min(r1, h - 1) + 1):
        for c in range(max(c0, 0), min(c1, w - 1) + 1):
            if inp[r][c] == bg:
                g[r][c] = rare
    return g


def largest_object_only(inp, out):
    ln, bg, rare, common = _setup(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == rare and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                comp = []
                while st:
                    a, b = st.pop()
                    comp.append((a, b))
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        x, y = a + da, b + db
                        if 0 <= x < h and 0 <= y < w and inp[x][y] == rare and (x, y) not in seen:
                            seen.add((x, y))
                            st.append((x, y))
                comps.append(comp)
    best = max(comps, key=len)
    f = _flip(inp, *ln)
    g = [row[:] for row in inp]
    for r, c in best:
        q, d = f(r, c)
        if 0 <= q < h and 0 <= d < w:
            g[q][d] = rare
    return g


ALTERNATIVES = [
    ("mirror the more frequent shape color instead of the rarer", common_color),
    ("mirror both shape colors", both_colors),
    ("mirror the color with fewer 4-connected objects, ties to the more frequent", fewest_objects),
    ("mirror across the grid axis perpendicular to the drawn line", perpendicular_axis),
    ("always mirror left-right across the center column", always_left_right),
    ("rotate the rarer color 180 degrees about the grid center", point_reflection),
    ("mirror axis offset by one cell from the drawn line", axis_shifted),
    ("move the rarer color to its mirror image, erasing the original", move_not_copy),
    ("mirror the rarer color's cells but paint them in the common color", wrong_paint_color),
    ("fill the bounding box of the mirror image with the rarer color", box_fill),
    ("mirror only the largest 4-connected object of the rarer color", largest_object_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/ad3b40cf.json').read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
