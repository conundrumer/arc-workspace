"""Near-miss readings for ARC task bd14c3bf.

True rule: the color-2 shape is the reference. Each color-1 shape whose
bounding box, with runs of identical adjacent rows and columns cut to one
line, equals the reference's reduced box up to a rotation or flip turns 2.
"""
import json
from pathlib import Path

REF = 2
MARK = 1


def components(g, color):
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == color and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and g[ny][nx] == color and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                comps.append(cells)
    return comps


def box(cells):
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return min(ys), min(xs), max(ys), max(xs)


def crop(cells):
    y0, x0, y1, x1 = box(cells)
    s = set(cells)
    return tuple(tuple(1 if (y, x) in s else 0 for x in range(x0, x1 + 1)) for y in range(y0, y1 + 1))


def dedup_rows(m):
    res = []
    for row in m:
        if not res or res[-1] != row:
            res.append(row)
    return tuple(res)


def transpose(m):
    return tuple(zip(*m))


def reduce_full(m):
    m = dedup_rows(m)
    m = transpose(dedup_rows(transpose(m)))
    m = dedup_rows(m)
    return m


def d4(m):
    out = []
    cur = m
    for _ in range(4):
        cur = tuple(zip(*cur[::-1]))
        out.append(cur)
        out.append(tuple(r[::-1] for r in cur))
    return out


def ref_cells(inp):
    comps = components(inp, REF)
    return comps[0] if comps else []


def paint(inp, comps, color=REF):
    g = [row[:] for row in inp]
    for cells in comps:
        for y, x in cells:
            g[y][x] = color
    return g


def finish(g, out):
    return None if g == out else g


def marks(inp):
    return components(inp, MARK)


def true_matches(inp):
    ref = reduce_full(crop(ref_cells(inp)))
    return [c for c in marks(inp) if ref in d4(reduce_full(crop(c)))]


def r_no_stretch(inp, out):
    ref = crop(ref_cells(inp))
    hit = [c for c in marks(inp) if ref in d4(crop(c)) and crop(c) in d4(ref)]
    hit = [c for c in hit if box(c)[2] - box(c)[0] == len(ref) - 1 and box(c)[3] - box(c)[1] == len(ref[0]) - 1]
    return finish(paint(inp, hit), out)


def r_no_transform(inp, out):
    ref = reduce_full(crop(ref_cells(inp)))
    hit = [c for c in marks(inp) if reduce_full(crop(c)) == ref]
    return finish(paint(inp, hit), out)


def r_all_marks(inp, out):
    return finish(paint(inp, marks(inp)), out)


def r_inverse(inp, out):
    good = {tuple(sorted(c)) for c in true_matches(inp)}
    hit = [c for c in marks(inp) if tuple(sorted(c)) not in good]
    return finish(paint(inp, hit), out)


def r_cell_count(inp, out):
    n = len(ref_cells(inp))
    hit = [c for c in marks(inp) if len(c) == n]
    return finish(paint(inp, hit), out)


def r_bbox_dims(inp, out):
    y0, x0, y1, x1 = box(ref_cells(inp))
    dims = {(y1 - y0, x1 - x0), (x1 - x0, y1 - y0)}
    hit = []
    for c in marks(inp):
        a, b, cc, d = box(c)
        if (cc - a, d - b) in dims:
            hit.append(c)
    return finish(paint(inp, hit), out)


def r_fill_box(inp, out):
    g = [row[:] for row in inp]
    for c in true_matches(inp):
        y0, x0, y1, x1 = box(c)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                g[y][x] = REF
    return finish(g, out)


def r_first_only(inp, out):
    hit = sorted(true_matches(inp), key=lambda c: box(c)[:2])[:1]
    return finish(paint(inp, hit), out)


def r_erase_others(inp, out):
    good = {tuple(sorted(c)) for c in true_matches(inp)}
    g = [row[:] for row in inp]
    for c in marks(inp):
        if tuple(sorted(c)) not in good:
            for y, x in c:
                g[y][x] = 0
    return finish(paint(g, true_matches(inp)), out)


def r_rows_only(inp, out):
    ref = dedup_rows(crop(ref_cells(inp)))
    hit = [c for c in marks(inp) if dedup_rows(crop(c)) == ref]
    return finish(paint(inp, hit), out)


def r_topology_holes(inp, out):
    def holes(cells):
        m = crop(cells)
        h, w = len(m), len(m[0])
        seen = set()
        n = 0
        for r in range(h):
            for c in range(w):
                if m[r][c] == 0 and (r, c) not in seen:
                    stack = [(r, c)]
                    seen.add((r, c))
                    while stack:
                        y, x = stack.pop()
                        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < h and 0 <= nx < w and m[ny][nx] == 0 and (ny, nx) not in seen:
                                seen.add((ny, nx))
                                stack.append((ny, nx))
                    n += 1
        return n
    k = holes(ref_cells(inp))
    hit = [c for c in marks(inp) if holes(c) == k]
    return finish(paint(inp, hit), out)


def r_unchanged(inp, out):
    return finish([row[:] for row in inp], out)


ALTERNATIVES = [
    ("match needs identical size, with no cutting of repeated rows and columns", r_no_stretch),
    ("match allows the cut-down only in the same orientation, no rotation or flip", r_no_transform),
    ("every mark shape turns the reference color", r_all_marks),
    ("the mark shapes that do not match turn the reference color instead", r_inverse),
    ("a mark matches when it has as many cells as the reference", r_cell_count),
    ("a mark matches when its bounding box has the reference box's dimensions, in either order", r_bbox_dims),
    ("a matching shape's whole bounding box is filled with the reference color", r_fill_box),
    ("only the top-left-most matching shape turns the reference color", r_first_only),
    ("matching shapes turn the reference color and non-matching marks are erased", r_erase_others),
    ("only identical adjacent rows are cut, not columns, before comparing", r_rows_only),
    ("a mark matches when its box has as many background parts as the reference's", r_topology_holes),
    ("the grid is returned unchanged", r_unchanged),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/bd14c3bf.json').read_text())
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
