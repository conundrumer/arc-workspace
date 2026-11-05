import json
from collections import Counter
from pathlib import Path

MARK = 2


def bg_of(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def components(g):
    bg = bg_of(g)
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != bg and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append(cells)
    return comps


def box(cells):
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return min(ys), max(ys), min(xs), max(xs)


def is_square(cells):
    r0, r1, c0, c1 = box(cells)
    return r1 - r0 == c1 - c0


def no_gap(cells):
    r0, r1, c0, c1 = box(cells)
    s = set(cells)
    for y in range(r0, r1 + 1):
        for x in range(c0, c1 + 1):
            if (y in (r0, r1) or x in (c0, c1)) and (y, x) not in s:
                return False
    return True


def qualifying(g):
    return [c for c in components(g) if len(c) > 1 and is_square(c)]


def corners(cells):
    r0, r1, c0, c1 = box(cells)
    # (row, col, vertical outward sign, horizontal outward sign)
    return [(r0, c0, -1, -1), (r0, c1, -1, 1), (r1, c0, 1, -1), (r1, c1, 1, 1)]


def paint(g, cells_color):
    bg = bg_of(g)
    o = [row[:] for row in g]
    h, w = len(g), len(g[0])
    for y, x, col in cells_color:
        if 0 <= y < h and 0 <= x < w and g[y][x] == bg:
            o[y][x] = col
    return o


def solve(inp, comps=None, per_corner=None, color=MARK):
    comps = qualifying(inp) if comps is None else comps
    per_corner = per_corner or (lambda r, c, sv, sh: [(r + sv, c), (r, c + sh)])
    out = []
    for cm in comps:
        for r, c, sv, sh in corners(cm):
            for y, x in per_corner(r, c, sv, sh):
                col = color(inp, cm) if callable(color) else color
                out.append((y, x, col))
    return paint(inp, out)


def horizontal_only(inp, out):
    return solve(inp, per_corner=lambda r, c, sv, sh: [(r, c + sh)])


def vertical_only(inp, out):
    return solve(inp, per_corner=lambda r, c, sv, sh: [(r + sv, c)])


def diagonal_cell(inp, out):
    return solve(inp, per_corner=lambda r, c, sv, sh: [(r + sv, c + sh)])


def inward(inp, out):
    # marks drawn on the cells just inside the corner, over the object
    o = [row[:] for row in inp]
    for cm in qualifying(inp):
        for r, c, sv, sh in corners(cm):
            for y, x in ((r - sv, c), (r, c - sh)):
                o[y][x] = MARK
    return o


def include_nonsquare(inp, out):
    comps = [c for c in components(inp) if len(c) > 1]
    return solve(inp, comps=comps)


def object_color(inp, out):
    return solve(inp, color=lambda g, cm: g[cm[0][0]][cm[0][1]])


def offset_two(inp, out):
    return solve(inp, per_corner=lambda r, c, sv, sh: [(r + 2 * sv, c), (r, c + 2 * sh)])


def top_corners_only(inp, out):
    comps = qualifying(inp)
    res = []
    for cm in comps:
        r0, r1, c0, c1 = box(cm)
        for r, c, sv, sh in corners(cm):
            if sv == -1:
                res += [(r + sv, c, MARK), (r, c + sh, MARK)]
    return paint(inp, res)


def full_frame(inp, out):
    res = []
    for cm in qualifying(inp):
        r0, r1, c0, c1 = box(cm)
        for y in range(r0 - 1, r1 + 2):
            for x in range(c0 - 1, c1 + 2):
                if y in (r0 - 1, r1 + 1) or x in (c0 - 1, c1 + 1):
                    res.append((y, x, MARK))
    return paint(inp, res)


def with_diagonal(inp, out):
    return solve(inp, per_corner=lambda r, c, sv, sh: [(r + sv, c), (r, c + sh), (r + sv, c + sh)])


def ring_only(inp, out):
    # only objects with an empty interior are marked
    comps = []
    for cm in qualifying(inp):
        r0, r1, c0, c1 = box(cm)
        s = set(cm)
        if r1 - r0 >= 2 and any((y, x) not in s for y in range(r0 + 1, r1) for x in range(c0 + 1, c1)):
            comps.append(cm)
    return solve(inp, comps=comps)


def single_diagonal_mark_outer(inp, out):
    # marks only on the one corner pair along the main diagonal
    res = []
    for cm in qualifying(inp):
        for r, c, sv, sh in corners(cm):
            if sv == sh:
                res += [(r + sv, c, MARK), (r, c + sh, MARK)]
    return paint(inp, res)


ALTERNATIVES = [
    ("marks only the horizontal neighbour outside each corner", horizontal_only),
    ("marks only the vertical neighbour outside each corner", vertical_only),
    ("marks the diagonal cell outside each corner instead of the two side neighbours", diagonal_cell),
    ("marks the cells just inside each corner, over the object", inward),
    ("marks every multi-cell object, square or not", include_nonsquare),
    ("marks in the object's own color instead of the new color", object_color),
    ("marks two cells away from each corner instead of adjacent", offset_two),
    ("marks only the two top corners of each square", top_corners_only),
    ("draws a full one-cell frame of marks around each square", full_frame),
    ("adds the diagonal cell to the two side marks at each corner", with_diagonal),
    ("marks only squares that have an empty interior", ring_only),
    ("marks only the top-left and bottom-right corners", single_diagonal_mark_outer),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/14b8e18c.json'))
    pairs = task["train"]
    assert all(solve(p["input"]) == p["output"] for p in pairs), "reference solve mismatch"
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
