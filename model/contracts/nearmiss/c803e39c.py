"""Near-miss readings for ARC task c803e39c.

Rule: four panels split by full divider lines; panel 0 holds the tile shape,
panel 1 the map shape, panel 2 a solid fill square, panel 3 a solid ground
square. Output: n x n blocks; block (i, j) is the tile (1 -> fill, 0 -> ground)
where map cell (i, j) is set, and all ground elsewhere.
"""
import json
from pathlib import Path


def panels(inp):
    h, w = len(inp), len(inp[0])
    div = [c for c in range(w) if all(inp[r][c] == 5 for r in range(h))]
    segs, start = [], 0
    for c in div + [w]:
        if c > start:
            segs.append((start, c))
        start = c + 1
    return segs


def square(inp, seg, dr=1, dc=1, size=None):
    n = len(inp) - 2 if size is None else size
    c0 = seg[0]
    return [[inp[dr + r][c0 + dc + c] for c in range(n)] for r in range(n)]


def full(inp, seg):
    return [row[seg[0]:seg[1]] for row in inp]


def ink(sq):
    return max(v for row in sq for v in row)


def build(tile, mp, fill, ground, tile_on=1, map_on=True, unset=None):
    """tile/mp are 0/1 masks; fill/ground colors; unset = color of unset blocks."""
    if unset is None:
        unset = ground
    n, m = len(tile), len(mp)
    out = [[unset] * (n * len(mp[0])) for _ in range(m * n)]
    for i in range(m):
        for j in range(len(mp[0])):
            if (mp[i][j] == 1) == map_on:
                for a in range(n):
                    for b in range(len(tile[0])):
                        out[i * n + a][j * len(tile[0]) + b] = (
                            fill if tile[a][b] == tile_on else ground)
    return out


def parts(inp):
    segs = panels(inp)
    sq = [square(inp, s) for s in segs]
    tile = [[1 if v else 0 for v in row] for row in sq[0]]
    mp = [[1 if v else 0 for v in row] for row in sq[1]]
    return segs, tile, mp, sq[2][0][0], sq[3][0][0]


def swap_roles(inp, out):
    _, tile, mp, f, g = parts(inp)
    return build(mp, tile, f, g)


def swap_colors(inp, out):
    _, tile, mp, f, g = parts(inp)
    return build(tile, mp, g, f)


def unset_background(inp, out):
    _, tile, mp, f, g = parts(inp)
    return build(tile, mp, f, g, unset=0)


def unset_fill(inp, out):
    _, tile, mp, f, g = parts(inp)
    return build(tile, mp, f, g, unset=f)


def inverted_tile(inp, out):
    _, tile, mp, f, g = parts(inp)
    return build(tile, mp, f, g, tile_on=0)


def inverted_map(inp, out):
    _, tile, mp, f, g = parts(inp)
    return build(tile, mp, f, g, map_on=False)


def transposed_tile(inp, out):
    _, tile, mp, f, g = parts(inp)
    return build([list(r) for r in zip(*tile)], mp, f, g)


def mirrored_map(inp, out):
    _, tile, mp, f, g = parts(inp)
    return build(tile, [r[::-1] for r in mp], f, g)


def shape_ink_colors(inp, out):
    segs, tile, mp, f, g = parts(inp)
    return build(tile, mp, ink(square(inp, segs[0])), g)


def whole_panel_frame(inp, out):
    segs = panels(inp)
    tile = [[1 if v else 0 for v in row] for row in full(inp, segs[0])]
    mp = [[1 if v else 0 for v in row] for row in full(inp, segs[1])]
    f = square(inp, segs[2])[0][0]
    g = square(inp, segs[3])[0][0]
    return build(tile, mp, f, g)


def unshifted_crop(inp, out):
    segs = panels(inp)
    tile = [[1 if v else 0 for v in row] for row in square(inp, segs[0], 0, 0)]
    mp = [[1 if v else 0 for v in row] for row in square(inp, segs[1], 0, 0)]
    f = square(inp, segs[2])[0][0]
    g = square(inp, segs[3])[0][0]
    return build(tile, mp, f, g)


ALTERNATIVES = [
    ("tile and map panels swapped: the map shape is stamped where the tile shape is set", swap_roles),
    ("fill and ground colors swapped", swap_colors),
    ("blocks where the map is unset left as background 0 instead of ground", unset_background),
    ("blocks where the map is unset filled with the fill color", unset_fill),
    ("tile inverted: its 0 cells take the fill color, its 1 cells the ground color", inverted_tile),
    ("tile placed where the map is NOT set", inverted_map),
    ("tile transposed before stamping", transposed_tile),
    ("map mirrored left-right before stamping", mirrored_map),
    ("tile cells painted with the tile shape's own ink color instead of the fill panel color", shape_ink_colors),
    ("shapes read from the whole panel including its 1-cell margin, giving (n+2)^2 output", whole_panel_frame),
    ("shapes cropped from the panel corner with no one-cell inset", unshifted_crop),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/c803e39c.json").read_text())
    train = task["train"]
    for p in train:
        _, tile, mp, f, g = parts(p["input"])
        assert build(tile, mp, f, g) == p["output"], "base construction mismatch"
    print(f"{len(ALTERNATIVES)} readings, {len(train)} pairs")
    for desc, fn in ALTERNATIVES:
        cnt = 0
        for p in train:
            r = fn(p["input"], p["output"])
            if r is not None and valid(r) and r != p["output"]:
                cnt += 1
        print(f"{cnt}/{len(train)}  {desc}")
