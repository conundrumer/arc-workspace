import json
from collections import Counter
from pathlib import Path

TL, TR, BL, BR, CORE = 6, 1, 2, 3, 4


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _objects(inp):
    """4-connected non-background components as (cells, (r0, c0, r1, c1))."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
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
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != bg and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            res.append((cells, (min(ys), min(xs), max(ys), max(xs))))
    return res


def _paint(inp, depth=lambda hh, ww: 2, cmap=(TL, TR, BL, BR), core=CORE,
           mode="quad", split=(0, 0), only_largest=False, center=None):
    g = [row[:] for row in inp]
    objs = _objects(inp)
    if only_largest:
        objs = [max(objs, key=lambda o: len(o[0]))]
    for cells, (r0, c0, r1, c1) in objs:
        hh, ww = r1 - r0 + 1, c1 - c0 + 1
        d = depth(hh, ww)
        for (y, x) in cells:
            r, c = y - r0, x - c0
            m = min(r, hh - 1 - r, c, ww - 1 - c)
            if m >= d:
                if core is not None:
                    g[y][x] = core
                continue
            if mode == "quad":
                if center is not None:
                    top = y < center[0]
                    left = x < center[1]
                else:
                    top = 2 * r < hh - 1 + 2 * split[0]
                    left = 2 * c < ww - 1 + 2 * split[1]
                g[y][x] = cmap[(0 if top else 2) + (0 if left else 1)]
            elif mode == "side":
                dists = [(r, TL), (ww - 1 - c, TR), (hh - 1 - r, BR), (c, BL)]
                g[y][x] = min(dists, key=lambda t: t[0])[1]
    return g


def _true(inp):
    return _paint(inp)


def mirror_lr(inp, out):
    return _paint(inp, cmap=(TR, TL, BR, BL))


def mirror_ud(inp, out):
    return _paint(inp, cmap=(BL, BR, TL, TR))


def rotated(inp, out):
    return _paint(inp, cmap=(BL, TL, BR, TR))


def thin_band(inp, out):
    return _paint(inp, depth=lambda hh, ww: 1)


def thick_band(inp, out):
    return _paint(inp, depth=lambda hh, ww: 3)


def keep_core(inp, out):
    return _paint(inp, core=None)


def no_core(inp, out):
    return _paint(inp, depth=lambda hh, ww: 99)


def sides(inp, out):
    return _paint(inp, mode="side")


def grid_center(inp, out):
    h, w = len(inp), len(inp[0])
    return _paint(inp, center=(h / 2 - 0.5, w / 2 - 0.5))


def only_largest(inp, out):
    return _paint(inp, only_largest=True)


def proportional_depth(inp, out):
    return _paint(inp, depth=lambda hh, ww: min(hh, ww) // 3)


def split_off_by_one(inp, out):
    return _paint(inp, split=(1, 1))


ALTERNATIVES = [
    ("left and right corner colors swapped", mirror_lr),
    ("top and bottom corner colors swapped", mirror_ud),
    ("corner colors rotated one place", rotated),
    ("band one cell deep instead of two", thin_band),
    ("band three cells deep instead of two", thick_band),
    ("core left as the input color", keep_core),
    ("no core: every cell takes its quadrant color", no_core),
    ("band split into four edge sides instead of quadrants", sides),
    ("quadrants taken about the grid center, not the object center", grid_center),
    ("only the largest object repainted", only_largest),
    ("band depth proportional to object size (min side // 3)", proportional_depth),
    ("quadrant split one cell off the object center", split_off_by_one),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/639f5a19.json"))
    train = task["train"]
    for p in train:
        assert _true(p["input"]) == p["output"], "generator does not reproduce output"
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in train)
        print(n, desc)
