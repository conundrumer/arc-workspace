import json
from pathlib import Path


def _cells(g, c):
    return [(r, k) for r, row in enumerate(g) for k, v in enumerate(row) if v == c]


def _ink(out):
    s = {v for row in out for v in row if v not in (0, 1, 8)}
    return max(s) if s else 8


def _components(cells, diag):
    left = set(cells)
    comps = []
    while left:
        stack = [left.pop()]
        comp = set(stack)
        while stack:
            r, c = stack.pop()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if (dr or dc) and (diag or not (dr and dc)):
                        n = (r + dr, c + dc)
                        if n in left:
                            left.remove(n)
                            comp.add(n)
                            stack.append(n)
        comps.append(comp)
    return comps


def _paint(grid, cells, v):
    g = [row[:] for row in grid]
    for r, c in cells:
        g[r][c] = v
    return g


def keep_key(inp, out):
    return _paint(out, _cells(inp, 1), 1)


def key_color(inp, out):
    return _paint(out, _cells(out, _ink(out)), 1)


def stay_eight(inp, out):
    return _paint(out, _cells(out, _ink(out)), 8)


def always_two(inp, out):
    return _paint(out, _cells(out, _ink(out)), 2)


def count_color(inp, out):
    n = len(_cells(inp, 1))
    return _paint(out, _cells(out, _ink(out)), n)


def largest_only(inp, out):
    comps = _components(_cells(inp, 8), True)
    big = max(comps, key=len)
    g = _paint(inp, _cells(inp, 1), 0)
    return _paint(g, big, _ink(out))


def key_painted_too(inp, out):
    return _paint(out, _cells(inp, 1), _ink(out))


def flip_vertical(inp, out):
    return [row[:] for row in out[::-1]]


def transpose(inp, out):
    return [list(r) for r in zip(*out)]


def bbox_filled(inp, out):
    cs = _cells(inp, 8)
    r0, r1 = min(r for r, _ in cs), max(r for r, _ in cs)
    c0, c1 = min(c for _, c in cs), max(c for _, c in cs)
    g = [[0] * len(out[0]) for _ in out]
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            g[r][c] = _ink(out)
    return g


def crop_to_shape(inp, out):
    cs = _cells(inp, 8)
    r0, r1 = min(r for r, _ in cs), max(r for r, _ in cs)
    c0, c1 = min(c for _, c in cs), max(c for _, c in cs)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def unchanged(inp, out):
    return [row[:] for row in inp]


def connected_only(inp, out):
    cs = set(_cells(inp, 8))
    iso = [p for p in cs
           if not any((p[0] + d, p[1] + e) in cs for d, e in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    g = _paint(out, iso, 8)
    return None if g == out else g


ALTERNATIVES = [
    ("key shape is left in place in the output", keep_key),
    ("shape recolored with the key's color 1", key_color),
    ("key removed but shape keeps color 8", stay_eight),
    ("shape always recolored with color 2", always_two),
    ("shape color is the number of key cells", count_color),
    ("key cells are recolored with the shape color instead of removed", key_painted_too),
    ("output is vertically flipped", flip_vertical),
    ("output is transposed", transpose),
    ("bounding box of the shape is filled with the ink color", bbox_filled),
    ("output is cropped to the shape's bounding box", crop_to_shape),
    ("isolated 8 cells are left uncolored", connected_only),
    ("input is returned unchanged", unchanged),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/009d5c81.json'))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
