import json
from pathlib import Path


def hflip(g):
    return [r[::-1] for r in g]


def vflip(g):
    return [r[:] for r in g[::-1]]


def rot(g):
    return vflip(hflip(g))


def ident(g):
    return [r[:] for r in g]


def assemble(tiles):
    """tiles: 2D list of grids, all the same size."""
    out = []
    for trow in tiles:
        for i in range(len(trow[0])):
            out.append([v for t in trow for v in t[i]])
    return out


def plain_tiling(inp, out):
    return assemble([[inp, inp], [inp, inp]])


def only_h_mirror(inp, out):
    h = hflip(inp)
    return assemble([[inp, h], [inp, h]])


def only_v_mirror(inp, out):
    v = vflip(inp)
    return assemble([[inp, inp], [v, v]])


def anchor_bottom_right(inp, out):
    return assemble([[rot(inp), vflip(inp)], [hflip(inp), inp]])


def anchor_top_right(inp, out):
    return assemble([[hflip(inp), inp], [rot(inp), vflip(inp)]])


def diagonal_unflipped(inp, out):
    return assemble([[inp, hflip(inp)], [vflip(inp), inp]])


def axes_swapped(inp, out):
    # horizontal neighbour gets the vertical flip, vertical neighbour the horizontal flip
    return assemble([[inp, vflip(inp)], [hflip(inp), rot(inp)]])


def three_by_three_alternating(inp, out):
    def tile(r, c):
        g = inp
        if c % 2:
            g = hflip(g)
        if r % 2:
            g = vflip(g)
        return g
    return assemble([[tile(r, c) for c in range(3)] for r in range(3)])


def one_row_only(inp, out):
    return [r + hflip([r])[0] for r in inp]


def shared_edge_reflection(inp, out):
    # reflect across the edge row/column, so the edge is not repeated
    w = len(inp[0])
    h = len(inp)
    rows = [r + r[-2::-1] for r in inp]
    return rows + rows[-2::-1]


def foreground_wrong_color(inp, out):
    return [[5 if v else 0 for v in r] for r in out]


def inverted_cells(inp, out):
    fg = max(v for r in out for v in r)
    return [[0 if v else fg for v in r] for r in out]


def crop_off_by_one(inp, out):
    return [r[:-1] for r in out[:-1]]


ALTERNATIVES = [
    ("tile the input 2x2 with no mirroring", plain_tiling),
    ("mirror horizontally only; rows of tiles repeat unflipped", only_h_mirror),
    ("mirror vertically only; columns of tiles repeat unflipped", only_v_mirror),
    ("anchor tile at bottom-right instead of top-left", anchor_bottom_right),
    ("anchor tile at top-right instead of top-left", anchor_top_right),
    ("diagonal tile left unflipped instead of rotated 180", diagonal_unflipped),
    ("horizontal and vertical flips swapped between neighbour tiles", axes_swapped),
    ("3x3 tiles with alternating mirrors instead of 2x2", three_by_three_alternating),
    ("only one row of tiles: input plus its horizontal mirror", one_row_only),
    ("reflection across a shared edge so the edge row and column are not repeated", shared_edge_reflection),
    ("foreground colored 5 instead of the input color", foreground_wrong_color),
    ("last row and column of the output dropped", crop_off_by_one),
]


def is_valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/3af2c5a8.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and is_valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
