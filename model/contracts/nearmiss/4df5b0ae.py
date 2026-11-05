import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _comps(g, bg):
    """4-connected same-color non-background components: (color, cells)."""
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            col = g[r][c]
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if (0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen
                            and g[ny][nx] == col):
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            res.append((col, sorted(cells)))
    return res


def _norm(cells):
    y0 = min(y for y, _ in cells)
    x0 = min(x for _, x in cells)
    return [(y - y0, x - x0) for y, x in cells]


def _dims(cells):
    return max(y for y, _ in cells) + 1, max(x for _, x in cells) + 1


def _layout(inp, key=None, reverse=False, from_right=False, top=False,
            gap=0, xform=None, drop_smallest=False, float_top=False,
            base=None):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    comps = _comps(inp, bg)
    if key is None:
        key = lambda c: (len(c[1]), c[1][0])
    comps.sort(key=key, reverse=reverse)
    if drop_smallest:
        comps = sorted(comps, key=lambda c: (len(c[1]), c[1][0]))[1:]
        comps.sort(key=key, reverse=reverse)
    shapes = []
    for col, cells in comps:
        n = _norm(cells)
        if xform:
            n = _norm(xform(n))
        shapes.append((col, n))
    maxh = max(_dims(n)[0] for _, n in shapes)
    out = [row[:] for row in base] if base else [[bg] * w for _ in range(h)]
    x = w if from_right else 0
    for col, n in shapes:
        sh, sw = _dims(n)
        if from_right:
            x0 = x - sw
            x = x0 - gap
        else:
            x0 = x
            x = x0 + sw + gap
        if x0 < 0 or x0 + sw > w or sh > h:
            return None
        if top:
            y0 = 0
        elif float_top:
            y0 = h - maxh
        else:
            y0 = h - sh
        for y, xx in n:
            out[y0 + y][x0 + xx] = col
    return out


def _transpose(g):
    return [list(r) for r in zip(*g)]


def desc_order(inp, out):
    return _layout(inp, reverse=True)


def from_right(inp, out):
    return _layout(inp, from_right=True)


def top_edge(inp, out):
    return _layout(inp, top=True)


def by_color(inp, out):
    return _layout(inp, key=lambda c: (c[0], c[1][0]))


def with_gap(inp, out):
    return _layout(inp, gap=1)


def filled_bbox(inp, out):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    comps = sorted(_comps(inp, bg), key=lambda c: (len(c[1]), c[1][0]))
    res = [[bg] * w for _ in range(h)]
    x = 0
    for col, cells in comps:
        sh, sw = _dims(_norm(cells))
        if x + sw > w:
            return None
        for y in range(h - sh, h):
            for xx in range(x, x + sw):
                res[y][xx] = col
        x += sw
    return res


def by_height(inp, out):
    return _layout(inp, key=lambda c: (_dims(_norm(c[1]))[0], len(c[1]), c[1][0]))


def rotated_shapes(inp, out):
    return _layout(inp, xform=lambda n: [(x, y) for y, x in n])


def right_edge_column(inp, out):
    t = _layout(_transpose(inp))
    return None if t is None else _transpose(t)


def top_aligned_in_row(inp, out):
    return _layout(inp, float_top=True)


def overlay_on_input(inp, out):
    return _layout(inp, base=inp)


def skip_smallest(inp, out):
    return _layout(inp, drop_smallest=True)


ALTERNATIVES = [
    ("shapes ordered by size largest first instead of smallest first", desc_order),
    ("row starts at the right edge and grows leftward", from_right),
    ("shapes rest on the top edge instead of the bottom edge", top_edge),
    ("shapes ordered by color value instead of size", by_color),
    ("one empty column left between neighbouring shapes", with_gap),
    ("each shape replaced by its solid bounding box", filled_bbox),
    ("shapes ordered by bounding-box height instead of cell count", by_height),
    ("each shape rotated a quarter turn when placed", rotated_shapes),
    ("row runs down the right edge, shapes resting on the right edge (wrong quarter turn)", right_edge_column),
    ("shapes top-aligned in a band as tall as the tallest shape, not resting on the bottom", top_aligned_in_row),
    ("packed row painted over the input without erasing the original shapes", overlay_on_input),
    ("smallest shape treated as noise and dropped", skip_smallest),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/4df5b0ae.json"))
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
