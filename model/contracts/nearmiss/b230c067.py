import json
from pathlib import Path


def _objects(inp):
    """8-connected components of non-zero cells, each a sorted list of (r, c)."""
    h, w = len(inp), len(inp[0])
    seen = set()
    objs = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0
                                and (ny, nx) not in seen):
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            objs.append(sorted(cells))
    return objs


def _norm(cells):
    r0 = min(y for y, _ in cells)
    c0 = min(x for _, x in cells)
    return frozenset((y - r0, x - c0) for y, x in cells)


def _odd_index(objs):
    shapes = [_norm(o) for o in objs]
    for i, s in enumerate(shapes):
        if sum(1 for t in shapes if t == s) == 1:
            return i
    return None


def _paint(inp, objs, colors):
    g = [[0] * len(inp[0]) for _ in inp]
    for o, col in zip(objs, colors):
        for y, x in o:
            g[y][x] = col
    return g


def _copy(g):
    return [row[:] for row in g]


def swap_colors(inp, out):
    m = {1: 2, 2: 1}
    return [[m.get(v, v) for v in row] for row in out]


def copies_only(inp, out):
    return [[8 if v == 2 else v for v in row] for row in out]


def odd_only(inp, out):
    return [[8 if v == 1 else v for v in row] for row in out]


def all_one_color(inp, out):
    objs = _objects(inp)
    return _paint(inp, objs, [1] * len(objs))


def last_object_odd(inp, out):
    objs = sorted(_objects(inp), key=lambda o: (min(y for y, _ in o), min(x for _, x in o)))
    return _paint(inp, objs, [1] * (len(objs) - 1) + [2])


def center_object_odd(inp, out):
    objs = _objects(inp)
    h, w = len(inp), len(inp[0])

    def dist(o):
        cy = sum(y for y, _ in o) / len(o)
        cx = sum(x for _, x in o) / len(o)
        return (cy - (h - 1) / 2) ** 2 + (cx - (w - 1) / 2) ** 2

    k = min(range(len(objs)), key=lambda i: dist(objs[i]))
    return _paint(inp, objs, [2 if i == k else 1 for i in range(len(objs))])


def largest_object_odd(inp, out):
    objs = _objects(inp)
    k = max(range(len(objs)), key=lambda i: (len(objs[i]), -i))
    return _paint(inp, objs, [2 if i == k else 1 for i in range(len(objs))])


def first_copy_only(inp, out):
    objs = _objects(inp)
    k = _odd_index(objs)
    if k is None:
        return None
    first = next(i for i in range(len(objs)) if i != k)
    colors = [8] * len(objs)
    colors[k] = 2
    colors[first] = 1
    return _paint(inp, objs, colors)


def bbox_filled(inp, out):
    objs = _objects(inp)
    k = _odd_index(objs)
    g = _copy(out)
    for i, o in enumerate(objs):
        col = 2 if i == k else 1
        for y in range(min(y for y, _ in o), max(y for y, _ in o) + 1):
            for x in range(min(x for _, x in o), max(x for _, x in o) + 1):
                g[y][x] = col
    return g


def odd_wrong_color(inp, out):
    return [[3 if v == 2 else v for v in row] for row in out]


ALTERNATIVES = [
    ("copy and odd colors exchanged: odd object gets 1, copies get 2", swap_colors),
    ("only the odd object is recolored; the copies stay 8", odd_only),
    ("only the copies are recolored; the odd object stays 8", copies_only),
    ("shapes compared by bbox height only, so no object is odd and all get the copy color", all_one_color),
    ("odd object is the last one in reading order", last_object_odd),
    ("odd object is the one nearest the grid center", center_object_odd),
    ("odd object is the one with the most cells (first on ties)", largest_object_odd),
    ("only the first copy is recolored, the second copy stays 8", first_copy_only),
    ("each object's whole bounding box is filled with its color", bbox_filled),
    ("odd object takes color 3 instead of 2", odd_wrong_color),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b230c067.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
