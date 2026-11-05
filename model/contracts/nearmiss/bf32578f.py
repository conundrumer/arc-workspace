"""Near-miss readings for ARC task bf32578f."""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _hue(inp):
    b = _bg(inp)
    return next(v for r in inp for v in r if v != b)


def _shape(inp):
    b = _bg(inp)
    return {(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != b}


def _grid(h, w, bg, cells, col):
    g = [[bg] * w for _ in range(h)]
    for r, c in cells:
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = col
    return g


def _enclosed(outline, h, w, diag=False):
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diag:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    seen = set()
    stack = [(r, c) for r in range(h) for c in range(w)
             if (r in (0, h - 1) or c in (0, w - 1)) and (r, c) not in outline]
    seen.update(stack)
    while stack:
        r, c = stack.pop()
        for dr, dc in steps:
            q = (r + dr, c + dc)
            if 0 <= q[0] < h and 0 <= q[1] < w and q not in outline and q not in seen:
                seen.add(q)
                stack.append(q)
    return {(r, c) for r in range(h) for c in range(w)
            if (r, c) not in outline and (r, c) not in seen}


def _map(cells, axis, f):
    return {((f(r), c) if axis == 0 else (r, f(c))) for r, c in cells}


def _reflect(shape, axis, sign, shift):
    """Mirror across the line `shift` cells past the edge toward sign (shift 0.5 = just past)."""
    vals = [p[axis] for p in shape]
    edge = max(vals) if sign > 0 else min(vals)
    line2 = 2 * edge + sign  # twice the line coordinate, for just past the edge
    if shift == 0:
        line2 = 2 * edge
    return _map(shape, axis, lambda x: line2 - x)


def _true(inp, out):
    """Find (axis, sign, image, outline, interior) that reproduces the true output."""
    h, w = len(inp), len(inp[0])
    b = _bg(inp)
    want = {(r, c) for r in range(h) for c in range(w) if out[r][c] != b}
    shape = _shape(inp)
    for axis in (0, 1):
        for sign in (1, -1):
            img = _reflect(shape, axis, sign, 1)
            if any(not (0 <= r < h and 0 <= c < w) for r, c in img):
                continue
            outline = shape | img
            if _enclosed(outline, h, w) == want:
                return axis, sign, img, outline, want
    raise ValueError("no direction fits")


def bbox_fill(inp, out):
    h, w = len(inp), len(inp[0])
    _, _, _, outline, _ = _true(inp, out)
    rs = [r for r, _ in outline]
    cs = [c for _, c in outline]
    cells = {(r, c) for r in range(min(rs), max(rs) + 1) for c in range(min(cs), max(cs) + 1)}
    return _grid(h, w, _bg(inp), cells, _hue(inp))


def shape_plus_fill(inp, out):
    h, w = len(inp), len(inp[0])
    _, _, _, _, inner = _true(inp, out)
    return _grid(h, w, _bg(inp), inner | _shape(inp), _hue(inp))


def outline_only(inp, out):
    h, w = len(inp), len(inp[0])
    _, _, _, outline, _ = _true(inp, out)
    return _grid(h, w, _bg(inp), outline, _hue(inp))


def _half(inp, out, shape_side):
    h, w = len(inp), len(inp[0])
    axis, sign, _, _, inner = _true(inp, out)
    vals = [p[axis] for p in _shape(inp)]
    edge = max(vals) if sign > 0 else min(vals)
    line = edge + sign * 0.5
    keep = {p for p in inner if ((p[axis] - line) * sign < 0) == shape_side}
    return _grid(h, w, _bg(inp), keep, _hue(inp))


def shape_half_only(inp, out):
    return _half(inp, out, True)


def image_half_only(inp, out):
    return _half(inp, out, False)


def reflect_through_edge(inp, out):
    h, w = len(inp), len(inp[0])
    axis, sign, _, _, _ = _true(inp, out)
    shape = _shape(inp)
    outline = shape | _reflect(shape, axis, sign, 0)
    return _grid(h, w, _bg(inp), _enclosed(outline, h, w), _hue(inp))


def dilated_fill(inp, out):
    h, w = len(inp), len(inp[0])
    _, _, _, _, inner = _true(inp, out)
    cells = set(inner)
    for r, c in inner:
        cells.update([(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)])
    return _grid(h, w, _bg(inp), cells, _hue(inp))


def translate_copy(inp, out):
    h, w = len(inp), len(inp[0])
    axis, sign, _, _, _ = _true(inp, out)
    shape = _shape(inp)
    width = max(p[axis] for p in shape) - min(p[axis] for p in shape) + 1
    copy = _map(shape, axis, lambda x: x + sign * width)
    return _grid(h, w, _bg(inp), shape | copy, _hue(inp))


def crop_to_outline(inp, out):
    _, _, _, outline, _ = _true(inp, out)
    rs = [r for r, _ in outline]
    cs = [c for _, c in outline]
    return [row[min(cs):max(cs) + 1] for row in out[min(rs):max(rs) + 1]]


def eroded_fill(inp, out):
    h, w = len(inp), len(inp[0])
    _, _, _, _, inner = _true(inp, out)
    keep = {(r, c) for r, c in inner
            if all((r + dr, c + dc) in inner for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    return _grid(h, w, _bg(inp), keep, _hue(inp))


ALTERNATIVES = [
    ("fill every cell in the bounding box of the shape and its mirror image", bbox_fill),
    ("keep the original shape and fill its interior, dropping the mirror image's outline", shape_plus_fill),
    ("draw the closed outline (shape plus mirror image) and leave its interior empty", outline_only),
    ("fill only the interior half on the shape's side of the mirror line", shape_half_only),
    ("fill only the interior half on the mirror image's side of the mirror line", image_half_only),
    ("mirror across the shape's edge column itself instead of the line just past it", reflect_through_edge),
    ("fill the interior plus every cell 4-adjacent to it, the outline cells that touch it included", dilated_fill),
    ("copy the shape by translation instead of reflection and draw both without fill", translate_copy),
    ("crop the true output to the bounding box of the closed outline", crop_to_outline),
    ("fill the interior less its rim (erode the filled region by one)", eroded_fill),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/bf32578f.json').read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {fn.__name__}: {desc}")
