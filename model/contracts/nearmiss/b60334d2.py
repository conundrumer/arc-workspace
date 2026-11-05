import json
from pathlib import Path


def _markers(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 5]


def _stamp(inp, corner=5, side=1, center=0, markers=None, dr=0, dc=0, sides=None):
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for r, c in (_markers(inp) if markers is None else markers):
        r += dr
        c += dc
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                if a == 0 and b == 0:
                    v = center
                elif a != 0 and b != 0:
                    v = corner
                else:
                    if sides is not None and (a, b) not in sides:
                        continue
                    v = side
                if 0 <= r + a < h and 0 <= c + b < w:
                    g[r + a][c + b] = v
    return g


def center_kept(inp, out):
    return _stamp(inp, center=5)


def colors_swapped(inp, out):
    return _stamp(inp, corner=1, side=5)


def plus_only(inp, out):
    return _stamp(inp, corner=0)


def corners_only(inp, out):
    return _stamp(inp, side=0)


def all_ones_ring(inp, out):
    return _stamp(inp, corner=1)


def center_filled(inp, out):
    return _stamp(inp, center=1)


def shifted_down(inp, out):
    return _stamp(inp, dr=1)


def only_top_half(inp, out):
    h = len(inp)
    return _stamp(inp, markers=[m for m in _markers(inp) if m[0] < h // 2])


def vertical_sides_only(inp, out):
    return _stamp(inp, sides={(-1, 0), (1, 0)})


def markers_left_unringed_but_one(inp, out):
    ms = _markers(inp)
    return _stamp(inp, markers=ms[:1])


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def mirrored(inp, out):
    return [r[::-1] for r in out]


ALTERNATIVES = [
    ("marker cell stays 5 in the ring center", center_kept),
    ("corner and side colors swapped (corners 1, sides 5)", colors_swapped),
    ("ring is a plus only, corners left empty", plus_only),
    ("ring has corners only, sides left empty", corners_only),
    ("all eight ring cells are 1", all_ones_ring),
    ("ring center is filled with 1", center_filled),
    ("ring is centered one row below the marker", shifted_down),
    ("only markers in the top half get a ring", only_top_half),
    ("only the top and bottom sides are drawn", vertical_sides_only),
    ("only the first marker in reading order gets a ring", markers_left_unringed_but_one),
    ("output is the transpose of the true output", transposed),
    ("output is the left-right mirror of the true output", mirrored),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/b60334d2.json').read_text())
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
