"""Near-miss rules for ARC task 4290ef0e (concentric symmetric rings)."""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _depth(n, r, c):
    return min(r, c, n - 1 - r, n - 1 - c)


def _layer_colors(out, bg):
    n = len(out)
    nl = (n + 1) // 2
    cols = []
    for d in range(nl):
        cnt = Counter(out[r][c] for r in range(n) for c in range(n)
                      if _depth(n, r, c) == d and out[r][c] != bg)
        cols.append(cnt.most_common(1)[0][0] if cnt else None)
    return cols


def _map_colors(out, mapping):
    return [[mapping.get(v, v) for v in row] for row in out]


def same_as_input(inp, out):
    return [row[:] for row in inp]


def reversed_nesting(inp, out):
    bg = _bg(inp)
    cols = _layer_colors(out, bg)
    present = [c for c in cols if c is not None]
    uniq = []
    for c in present:
        if c not in uniq:
            uniq.append(c)
    mapping = dict(zip(uniq, reversed(uniq)))
    return _map_colors(out, mapping)


def swap_outer_two(inp, out):
    bg = _bg(inp)
    cols = [c for c in _layer_colors(out, bg)]
    uniq = []
    for c in cols:
        if c is not None and c not in uniq:
            uniq.append(c)
    if len(uniq) < 2:
        return None
    a, b = uniq[0], uniq[1]
    return _map_colors(out, {a: b, b: a})


def gaps_closed(inp, out):
    bg = _bg(inp)
    n = len(out)
    cols = _layer_colors(out, bg)
    return [[cols[_depth(n, r, c)] if out[r][c] == bg and cols[_depth(n, r, c)] is not None
             else out[r][c] for c in range(n)] for r in range(n)]


def canvas_one_ring_smaller(inp, out):
    n = len(out)
    if n < 3:
        return None
    return [row[1:-1] for row in out[1:-1]]


def canvas_one_ring_larger(inp, out):
    bg = _bg(inp)
    n = len(out)
    return [[bg] * (n + 2)] + [[bg] + row[:] + [bg] for row in out] + [[bg] * (n + 2)]


def top_left_quadrant_only(inp, out):
    bg = _bg(inp)
    n = len(out)
    h = n // 2
    return [[out[r][c] if r <= h and c <= h else bg for c in range(n)] for r in range(n)]


def vertical_copy_not_flip(inp, out):
    n = len(out)
    h = n // 2
    return [out[r][:] if r <= h else out[r - h - 1][:] for r in range(n)]


def gaps_take_outer_ring_color(inp, out):
    bg = _bg(inp)
    cols = _layer_colors(out, bg)
    fill = cols[0]
    if fill is None:
        return None
    return [[fill if v == bg else v for v in row] for row in out]


def largest_ring_only(inp, out):
    bg = _bg(inp)
    n = len(out)
    return [[out[r][c] if _depth(n, r, c) == 0 else bg for c in range(n)] for r in range(n)]


def innermost_ring_dropped(inp, out):
    bg = _bg(inp)
    n = len(out)
    cols = _layer_colors(out, bg)
    last = max(d for d, c in enumerate(cols) if c is not None)
    return [[bg if _depth(n, r, c) == last else out[r][c] for c in range(n)] for r in range(n)]


def crop_largest_bbox_object(inp, out):
    bg = _bg(inp)
    best = None
    for col in set(v for r in inp for v in r) - {bg}:
        cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == col]
        r0 = min(r for r, _ in cells)
        r1 = max(r for r, _ in cells)
        c0 = min(c for _, c in cells)
        c1 = max(c for _, c in cells)
        area = (r1 - r0 + 1) * (c1 - c0 + 1)
        if best is None or area > best[0]:
            best = (area, r0, r1, c0, c1)
    if best is None:
        return None
    _, r0, r1, c0, c1 = best
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


ALTERNATIVES = [
    ("Returns the input unchanged", same_as_input),
    ("Nests the rings in reverse order: smallest outermost, largest innermost", reversed_nesting),
    ("Swaps the colors of the two largest rings", swap_outer_two),
    ("Closes every ring's hollow gaps instead of leaving them as field", gaps_closed),
    ("Canvas one ring too small (outer frame cropped off)", canvas_one_ring_smaller),
    ("Canvas one ring too large (extra field border)", canvas_one_ring_larger),
    ("Mirrors nothing: only the top-left quadrant is drawn", top_left_quadrant_only),
    ("Bottom half is a translated copy of the top half instead of a vertical mirror", vertical_copy_not_flip),
    ("Hollow gaps in all rings take the largest ring's color", gaps_take_outer_ring_color),
    ("Draws only the largest ring", largest_ring_only),
    ("Leaves out the innermost ring", innermost_ring_dropped),
    ("Crops the bounding box of the object with the largest bounding box from the input", crop_largest_bbox_object),
]


def _valid(g, out):
    if g is None or not g or not isinstance(g, list):
        return False
    w = len(g[0])
    if w == 0:
        return False
    for row in g:
        if not isinstance(row, list) or len(row) != w:
            return False
        if any(type(v) is not int or not 0 <= v <= 9 for v in row):
            return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/4290ef0e.json'))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            ok += _valid(g, p["output"])
        print(f"{ok}/{len(pairs)}  {desc}")
