"""Near-miss readings for ARC task 5117e062."""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _mark(inp):
    c = Counter(v for r in inp for v in r)
    return min(c, key=lambda k: (c[k], k))


def _components(inp, diag=True):
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    seen = set()
    comps = []
    steps = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diag:
        steps += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in steps:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] != bg:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append(cells)
    return comps


def _marked_comp(inp):
    m = _mark(inp)
    for comp in _components(inp):
        if any(inp[y][x] == m for y, x in comp):
            return comp
    return None


def _bbox(cells):
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return min(ys), max(ys), min(xs), max(xs)


def _crop(inp, box):
    y0, y1, x0, x1 = box
    return [row[x0:x1 + 1] for row in inp[y0:y1 + 1]]


def _fill_color(inp, comp):
    bg, m = _bg(inp), _mark(inp)
    cols = {inp[y][x] for y, x in comp} - {bg, m}
    return next(iter(cols))


def mark_not_filled(inp, out):
    m = _mark(inp)
    comp = _marked_comp(inp)
    return _crop(inp, _bbox(comp)) if comp else None


def mark_becomes_bg(inp, out):
    bg, m = _bg(inp), _mark(inp)
    return [[bg if v == m else v for v in row] for row in _crop(inp, _bbox(_marked_comp(inp)))]


def padded_crop(inp, out):
    comp = _marked_comp(inp)
    y0, y1, x0, x1 = _bbox(comp)
    g = out
    bg = _bg(inp)
    w = len(g[0])
    return [[bg] * (w + 2)] + [[bg] + list(r) + [bg] for r in g] + [[bg] * (w + 2)]


def crop_lacks_last_row_col(inp, out):
    return [row[:-1] for row in out[:-1]]


def largest_other_component(inp, out):
    comp0 = _marked_comp(inp)
    others = [c for c in _components(inp) if c is not comp0]
    best = max(others, key=len)
    return _crop(inp, _bbox(best))


def fill_with_other_shape_color(inp, out):
    comp0 = _marked_comp(inp)
    own = _fill_color(inp, comp0)
    bg, m = _bg(inp), _mark(inp)
    others = [c for c in _components(inp) if c is not comp0]
    best = max(others, key=len)
    col = inp[best[0][0]][best[0][1]]
    if col == own:
        return None
    return [[col if v == own else v for v in row] for row in out]


def inverted_shape(inp, out):
    bg = _bg(inp)
    col = _fill_color(inp, _marked_comp(inp))
    return [[bg if v == col else col for v in row] for row in out]


def whole_grid_other_shapes_erased(inp, out):
    comp = set(_marked_comp(inp))
    col = _fill_color(inp, comp)
    bg, m = _bg(inp), _mark(inp)
    return [[(col if inp[y][x] == m else inp[y][x]) if (y, x) in comp else bg
             for x in range(len(inp[0]))] for y in range(len(inp))]


def shape_only_four_connected_without_mark(inp, out):
    # Component taken without diagonal links through the mark: mark cell treated as bg.
    m, bg = _mark(inp), _bg(inp)
    g = [[bg if v == m else v for v in row] for row in inp]
    pos = [(y, x) for y, row in enumerate(inp) for x, v in enumerate(row) if v == m][0]
    comps = _components(g, diag=False)
    best = None
    for comp in comps:
        if any(abs(y - pos[0]) + abs(x - pos[1]) == 1 for y, x in comp):
            if best is None or len(comp) > len(best):
                best = comp
    if best is None:
        return None
    return _crop(inp, _bbox(best))


def mirrored_horizontally(inp, out):
    return [list(reversed(r)) for r in out]


def rotated_quarter(inp, out):
    return [list(r) for r in zip(*out[::-1])]


ALTERNATIVES = [
    ("crop the marked shape but leave the mark cell as it is", mark_not_filled),
    ("crop the marked shape and turn the mark cell into background", mark_becomes_bg),
    ("crop one cell too much on every side of the marked shape", padded_crop),
    ("crop one row and column too little (bounding box off by one)", crop_lacks_last_row_col),
    ("crop the largest shape that does not hold the mark", largest_other_component),
    ("fill the shape with the color of the largest other shape", fill_with_other_shape_color),
    ("swap shape and background inside the crop", inverted_shape),
    ("keep the grid size and erase everything but the marked shape", whole_grid_other_shapes_erased),
    ("pick the shape by 4-connected contact with the mark, mark removed", shape_only_four_connected_without_mark),
    ("mirror the output left to right", mirrored_horizontally),
    ("rotate the output a quarter turn", rotated_quarter),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not isinstance(g[0], list) or not g[0]:
        return False
    if any(not isinstance(r, list) or len(r) != len(g[0]) for r in g):
        return False
    if any(type(v) is not int or not 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/5117e062.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
