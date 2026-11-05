"""Near-miss readings for ARC task 902510d5.

True rule: the largest 8-connected group of ink is the shape and stays. The ink
cell in a grid corner is the marker. All other ink is loose. Loose cells and
the marker are erased. A staircase triangle with N rows (N = loose count) is
drawn in the marker's corner, in the most frequent loose color.
"""
import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    ink = {(i, j) for i in range(h) for j in range(w) if inp[i][j] != bg}
    seen, comps = set(), []
    for p in sorted(ink):
        if p in seen:
            continue
        comp, stack = [], [p]
        seen.add(p)
        while stack:
            a, b = stack.pop()
            comp.append((a, b))
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    q = (a + da, b + db)
                    if q in ink and q not in seen:
                        seen.add(q)
                        stack.append(q)
        comps.append(comp)
    shape = set(max(comps, key=len))
    corners = [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]
    marker = next(c for c in corners if c in ink)
    return h, w, bg, ink, shape, marker


def _loose(inp, ink, shape, marker):
    return sorted(p for p in ink if p not in shape and p != marker)


def _most_common(colors, least=False):
    cnt = Counter(colors)
    if least:
        return min(cnt, key=lambda c: (cnt[c], c))
    return max(cnt, key=lambda c: (cnt[c], -c))


def _render(inp, size=None, fill=None, corner=None, keep_loose=False,
            keep_shape=True, keep_marker=False, square=False, use_cells=None):
    h, w, bg, ink, shape, marker = _parse(inp)
    loose = _loose(inp, ink, shape, marker)
    n = len(loose) if size is None else size
    col = _most_common([inp[i][j] for i, j in loose]) if fill is None else fill
    cr, cc = marker if corner is None else corner
    res = [[bg] * w for _ in range(h)]
    if keep_shape:
        for i, j in shape:
            res[i][j] = inp[i][j]
    if keep_loose:
        for i, j in loose:
            res[i][j] = inp[i][j]
    if keep_marker:
        res[marker[0]][marker[1]] = inp[marker[0]][marker[1]]
    for i in range(h):
        for j in range(w):
            di, dj = abs(i - cr), abs(j - cc)
            inside = (di < n and dj < n) if square else (di + dj < n)
            if inside:
                res[i][j] = col
    return res


def _ret(g, out):
    return None if g == out else g


def size_plus_one(inp, out):
    h, w, bg, ink, shape, marker = _parse(inp)
    n = len(_loose(inp, ink, shape, marker))
    return _ret(_render(inp, size=n + 1), out)


def size_minus_one(inp, out):
    h, w, bg, ink, shape, marker = _parse(inp)
    n = len(_loose(inp, ink, shape, marker))
    return _ret(_render(inp, size=n - 1), out)


def size_distinct_colors(inp, out):
    h, w, bg, ink, shape, marker = _parse(inp)
    loose = _loose(inp, ink, shape, marker)
    return _ret(_render(inp, size=len({inp[i][j] for i, j in loose})), out)


def fill_shape_color(inp, out):
    h, w, bg, ink, shape, marker = _parse(inp)
    col = _most_common([inp[i][j] for i, j in shape])
    return _ret(_render(inp, fill=col), out)


def fill_least_frequent(inp, out):
    h, w, bg, ink, shape, marker = _parse(inp)
    loose = _loose(inp, ink, shape, marker)
    col = _most_common([inp[i][j] for i, j in loose], least=True)
    return _ret(_render(inp, fill=col), out)


def fill_marker_color(inp, out):
    h, w, bg, ink, shape, marker = _parse(inp)
    return _ret(_render(inp, fill=inp[marker[0]][marker[1]]), out)


def opposite_corner(inp, out):
    h, w, bg, ink, shape, marker = _parse(inp)
    corner = (h - 1 - marker[0], w - 1 - marker[1])
    return _ret(_render(inp, corner=corner), out)


def mirrored_corner(inp, out):
    h, w, bg, ink, shape, marker = _parse(inp)
    corner = (marker[0], w - 1 - marker[1])
    return _ret(_render(inp, corner=corner), out)


def keep_loose_cells(inp, out):
    return _ret(_render(inp, keep_loose=True), out)


def keep_marker_cell(inp, out):
    h, w, bg, ink, shape, marker = _parse(inp)
    g = _render(inp)
    # Marker cell stays in its own color on top of the triangle.
    g[marker[0]][marker[1]] = inp[marker[0]][marker[1]]
    return _ret(g, out)


def square_not_triangle(inp, out):
    return _ret(_render(inp, square=True), out)


def shape_erased(inp, out):
    return _ret(_render(inp, keep_shape=False), out)


def shape_is_dominant_color(inp, out):
    """Shape = every cell of the most frequent ink color, connected or not."""
    h, w, bg, ink, shape, marker = _parse(inp)
    dom = _most_common([inp[i][j] for i, j in ink])
    shape2 = {(i, j) for i, j in ink if inp[i][j] == dom}
    loose = sorted(p for p in ink if p not in shape2 and p != marker)
    if not loose:
        return None
    col = _most_common([inp[i][j] for i, j in loose])
    res = [[bg] * w for _ in range(h)]
    for i, j in shape2:
        res[i][j] = inp[i][j]
    cr, cc = marker
    for i in range(h):
        for j in range(w):
            if abs(i - cr) + abs(j - cc) < len(loose):
                res[i][j] = col
    return _ret(res, out)


ALTERNATIVES = [
    ("triangle has one row too many (loose count + 1)", size_plus_one),
    ("triangle has one row too few (loose count - 1)", size_minus_one),
    ("triangle size is the number of distinct loose colors", size_distinct_colors),
    ("triangle filled with the shape's color", fill_shape_color),
    ("triangle filled with the least frequent loose color", fill_least_frequent),
    ("triangle filled with the marker's own color", fill_marker_color),
    ("triangle drawn in the diagonally opposite corner", opposite_corner),
    ("loose cells left in place", keep_loose_cells),
    ("filled square instead of staircase triangle", square_not_triangle),
    ("shape erased along with the loose cells", shape_erased),
    ("shape taken as all cells of the dominant color, connected or not",
     shape_is_dominant_color),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/902510d5.json'))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(ok, desc)
