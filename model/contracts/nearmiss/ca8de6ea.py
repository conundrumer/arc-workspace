import json
from pathlib import Path


def _ring(inp):
    # inner diagonal pixels of the 5x5 input: A top-left, B top-right, C bottom-right, D bottom-left
    return inp[1][1], inp[1][3], inp[3][3], inp[3][1]


def _build(inp, top, right, bottom, left, corners=None, center=None):
    c = corners if corners is not None else [inp[0][0], inp[0][4], inp[4][4], inp[4][0]]
    mid = inp[2][2] if center is None else center
    return [
        [c[0], top, c[1]],
        [left, mid, right],
        [c[3], bottom, c[2]],
    ]


def ring_other_way(inp, out):
    a, b, c, d = _ring(inp)
    return _build(inp, b, c, d, a)


def edges_take_center_color(inp, out):
    m = inp[2][2]
    return _build(inp, m, m, m, m, center=inp[1][1])


def no_corners(inp, out):
    return _build(inp, *(_ring(inp)[i] for i in (0, 1, 2, 3)), corners=[0, 0, 0, 0])


def center_cleared(inp, out):
    a, b, c, d = _ring(inp)
    return _build(inp, a, b, c, d, center=0)


def center_takes_edge_color(inp, out):
    a, b, c, d = _ring(inp)
    return _build(inp, a, b, c, d, center=a)


def corners_rotated(inp, out):
    a, b, c, d = _ring(inp)
    k = [inp[4][0], inp[0][0], inp[0][4], inp[4][4]]
    return _build(inp, a, b, c, d, corners=k)


def roles_swapped(inp, out):
    # inner diagonal pixels become the corners, outer corners go to the edge middles
    a, b, c, d = _ring(inp)
    o = [inp[0][0], inp[0][4], inp[4][4], inp[4][0]]
    return _build(inp, o[0], o[1], o[2], o[3], corners=[a, b, c, d])


def crop_inner(inp, out):
    return [row[1:4] for row in inp[1:4]]


def only_vertical_pair_moved(inp, out):
    a, b, c, d = _ring(inp)
    return _build(inp, a, 0, c, 0)


def one_color_on_all_edges(inp, out):
    a, b, c, d = _ring(inp)
    return _build(inp, a, a, a, a)


def mirrored_output(inp, out):
    return [row[::-1] for row in out]


def input_unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("inner pixels move one step round the ring the other way", ring_other_way),
    ("centre and inner pixels swap roles: edge middles take the centre colour", edges_take_center_color),
    ("outer corner pixels are dropped", no_corners),
    ("centre cell is left empty", center_cleared),
    ("centre cell takes the colour of an inner pixel", center_takes_edge_color),
    ("outer corner pixels are rotated one step", corners_rotated),
    ("inner pixels go to the corners and outer corners go to the edge middles", roles_swapped),
    ("output is the plain inner 3x3 crop of the input", crop_inner),
    ("only the top and bottom edge middles are filled", only_vertical_pair_moved),
    ("all edge middles take the colour of one inner pixel", one_color_on_all_edges),
    ("correct output mirrored left to right", mirrored_output),
    ("input returned unchanged", input_unchanged),
]


def _valid(g, out):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/ca8de6ea.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
