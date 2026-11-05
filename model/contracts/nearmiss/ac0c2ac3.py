import json
from collections import Counter
from pathlib import Path


def _marks(inp):
    n = len(inp)
    c = n // 2
    bg = Counter(v for row in inp for v in row).most_common(1)[0][0]
    ring = {}
    raster = []
    for r in range(n):
        for col in range(n):
            if inp[r][col] != bg:
                ring[max(abs(r - c), abs(col - c))] = inp[r][col]
                raster.append(inp[r][col])
    return n, c, bg, ring, raster


def _paint(n, c, f):
    return [[f(r, col, max(abs(r - c), abs(col - c))) for col in range(n)] for r in range(n)]


def manhattan_layers(inp, out):
    n, c, bg, ring, _ = _marks(inp)
    top = max(ring)
    return _paint(n, c, lambda r, col, k: ring[min(abs(r - c) + abs(col - c), top)])


def reversed_order(inp, out):
    n, c, bg, ring, _ = _marks(inp)
    top = max(ring)
    return _paint(n, c, lambda r, col, k: ring[top - k])


def raster_order(inp, out):
    n, c, bg, ring, raster = _marks(inp)
    top = max(ring)
    return _paint(n, c, lambda r, col, k: raster[top - k])


def crop_border(inp, out):
    return [row[1:-1] for row in out[1:-1]]


def outer_unmarked(inp, out):
    n, c, bg, ring, _ = _marks(inp)
    top = max(ring)
    return _paint(n, c, lambda r, col, k: bg if k == top else ring[k])


def center_unfilled(inp, out):
    n, c, bg, ring, _ = _marks(inp)
    return _paint(n, c, lambda r, col, k: bg if k == 0 else ring[k])


def row_bands(inp, out):
    n, c, bg, ring, _ = _marks(inp)
    return _paint(n, c, lambda r, col, k: ring[abs(r - c)])


def column_bands(inp, out):
    n, c, bg, ring, _ = _marks(inp)
    return _paint(n, c, lambda r, col, k: ring[abs(col - c)])


def shifted_inward(inp, out):
    n, c, bg, ring, _ = _marks(inp)
    return _paint(n, c, lambda r, col, k: ring[max(k - 1, 0)])


def shifted_outward(inp, out):
    n, c, bg, ring, _ = _marks(inp)
    top = max(ring)
    return _paint(n, c, lambda r, col, k: ring[min(k + 1, top)])


def swap_outer_two(inp, out):
    n, c, bg, ring, _ = _marks(inp)
    top = max(ring)
    sw = {top: ring[top - 1], top - 1: ring[top]}
    return _paint(n, c, lambda r, col, k: sw.get(k, ring[k]))


def marks_only(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("rings are diamonds (Manhattan distance from center), not squares", manhattan_layers),
    ("ring colors are assigned in reverse: the outermost ring takes the center mark color", reversed_order),
    ("ring colors follow the marks' reading order in the input, not their distance from center", raster_order),
    ("output is cropped one cell short on every side, dropping the outermost ring", crop_border),
    ("outermost ring is treated as unmarked and keeps the background color", outer_unmarked),
    ("center cell is treated as unmarked and keeps the background color", center_unfilled),
    ("cells take the color of the mark by row distance from center, giving horizontal bands", row_bands),
    ("cells take the color of the mark by column distance from center, giving vertical bands", column_bands),
    ("each ring takes the color of the next ring inward (off by one), the center repeating", shifted_inward),
    ("each ring takes the color of the next ring outward (off by one), the outermost repeating", shifted_outward),
    ("the two outermost ring colors are swapped", swap_outer_two),
    ("output is the input with only the marks drawn", marks_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/ac0c2ac3.json'))
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(ok, desc)
