import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(c for r in inp for c in r)
    bg = cnt.most_common(1)[0][0]
    sc = max((c for c in cnt if c != bg), key=lambda c: cnt[c])
    seen = set()
    comps = []
    for i in range(h):
        for j in range(w):
            if inp[i][j] == sc and (i, j) not in seen:
                stack, comp = [(i, j)], []
                seen.add((i, j))
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        a, b = y + dy, x + dx
                        if 0 <= a < h and 0 <= b < w and inp[a][b] == sc and (a, b) not in seen:
                            seen.add((a, b))
                            stack.append((a, b))
                comps.append(sorted(comp))
    markers = [(i, j) for i in range(h) for j in range(w) if inp[i][j] not in (bg, sc)]
    info = []
    for comp in comps:
        cs = set(comp)
        touch = None
        for (y, x) in comp:
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (y + dy, x + dx)
                if q in markers:
                    touch = (q, (y, x))
        info.append((comp, touch))
    info.sort(key=lambda t: t[0][0])
    return bg, sc, info, markers


def _build(inp, colors, erase=True, marker_fill=None, only_touch=False, skip=()):
    bg, sc, info, markers = _parse(inp)
    g = [r[:] for r in inp]
    if erase:
        for (y, x) in markers:
            g[y][x] = bg
    for k, (comp, touch) in enumerate(info):
        if k in skip:
            continue
        col = colors[k]
        cells = [touch[1]] if only_touch else comp
        for (y, x) in cells:
            g[y][x] = col
        if marker_fill and touch:
            g[touch[0][0]][touch[0][1]] = col
    return g


def _mc(inp, k):
    bg, sc, info, markers = _parse(inp)
    q = info[k][1][0]
    return inp[q[0]][q[1]]


def keep_markers(inp, out):
    bg, sc, info, markers = _parse(inp)
    return _build(inp, [_mc(inp, k) for k in range(len(info))], erase=False)


def no_recolor(inp, out):
    bg, sc, info, markers = _parse(inp)
    return _build(inp, [sc] * len(info))


def rotated(inp, out):
    bg, sc, info, markers = _parse(inp)
    n = len(info)
    return _build(inp, [_mc(inp, (k + 1) % n) for k in range(n)])


def first_marker_all(inp, out):
    bg, sc, info, markers = _parse(inp)
    return _build(inp, [_mc(inp, 0)] * len(info))


def first_shape_only(inp, out):
    bg, sc, info, markers = _parse(inp)
    return _build(inp, [_mc(inp, k) for k in range(len(info))], skip=range(1, len(info)))


def touching_cell_only(inp, out):
    bg, sc, info, markers = _parse(inp)
    return _build(inp, [_mc(inp, k) for k in range(len(info))], only_touch=True)


def marker_absorbed(inp, out):
    bg, sc, info, markers = _parse(inp)
    return _build(inp, [_mc(inp, k) for k in range(len(info))], marker_fill=True)


def unchanged(inp, out):
    return [r[:] for r in inp]


def bbox_fill(inp, out):
    bg, sc, info, markers = _parse(inp)
    g = [r[:] for r in inp]
    for (y, x) in markers:
        g[y][x] = bg
    for k, (comp, touch) in enumerate(info):
        col = _mc(inp, k)
        ys = [p[0] for p in comp]
        xs = [p[1] for p in comp]
        for y in range(min(ys), max(ys) + 1):
            for x in range(min(xs), max(xs) + 1):
                if g[y][x] == bg or g[y][x] == sc:
                    g[y][x] = col
    return g


def largest_marker_all(inp, out):
    bg, sc, info, markers = _parse(inp)
    m = max(_mc(inp, k) for k in range(len(info)))
    return _build(inp, [m] * len(info))


def cropped(inp, out):
    bg = Counter(c for r in out for c in r).most_common(1)[0][0]
    cells = [(i, j) for i, r in enumerate(out) for j, c in enumerate(r) if c != bg]
    y0, y1 = min(c[0] for c in cells), max(c[0] for c in cells)
    x0, x1 = min(c[1] for c in cells), max(c[1] for c in cells)
    return [r[x0:x1 + 1] for r in out[y0:y1 + 1]]


ALTERNATIVES = [
    ("shapes take marker colors but marker cells stay in place", keep_markers),
    ("markers are erased but shapes keep the shape color", no_recolor),
    ("each shape takes the color of the next shape's marker (colors cyclically shifted)", rotated),
    ("all shapes take the color of the first marker in reading order", first_marker_all),
    ("only the first shape in reading order is recolored", first_shape_only),
    ("only the shape cell touching the marker is recolored", touching_cell_only),
    ("marker cell is absorbed into the shape (takes the new shape color)", marker_absorbed),
    ("grid returned unchanged", unchanged),
    ("each shape's bounding box is filled with its marker color", bbox_fill),
    ("all shapes take the largest marker color", largest_marker_all),
    ("output cropped to the bounding box of the non-background cells", cropped),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/b7256dcd.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                g = None
            n += _valid(g, p["output"])
        print(n, desc)
