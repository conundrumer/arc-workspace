import json
from pathlib import Path


def _cells(g, c):
    return [(r, k) for r, row in enumerate(g) for k, v in enumerate(row) if v == c]


def _box(cells):
    rs = [r for r, _ in cells]
    cs = [k for _, k in cells]
    return min(rs), min(cs), max(rs), max(cs)


def _copy(g):
    return [row[:] for row in g]


def _shape_in(inp):
    return _cells(inp, 2)


def _shape_out(out):
    return _cells(out, 2)


def _blank_shape(g):
    h = _copy(g)
    for r, k in _cells(h, 2):
        h[r][k] = 0
    return h


def _draw(base, cells, color=2):
    h = _copy(base)
    for r, k in cells:
        if not (0 <= r < len(h) and 0 <= k < len(h[0])):
            return None
        h[r][k] = color
    return h


def _shifted_out(inp, out, dr, dc, color=2):
    cells = [(r + dr, k + dc) for r, k in _shape_out(out)]
    return _draw(_blank_shape(out), cells, color)


def unmoved(inp, out):
    return _copy(inp)


def top_left_on_marker(inp, out):
    return _shifted_out(inp, out, -1, -1)


def shift_down_one(inp, out):
    return _shifted_out(inp, out, 1, 0)


def horizontal_only(inp, out):
    m = _cells(inp, 3)
    mr0, mc0, mr1, mc1 = _box(m)
    sr0, sc0, sr1, sc1 = _box(_shape_in(inp))
    dc = (mc0 + 1) - sc0
    return _draw(_blank_shape(inp), [(r, k + dc) for r, k in _shape_in(inp)])


def vertical_only(inp, out):
    m = _cells(inp, 3)
    mr0, mc0, mr1, mc1 = _box(m)
    sr0, sc0, sr1, sc1 = _box(_shape_in(inp))
    dr = (mr0 + 1) - sr0
    return _draw(_blank_shape(inp), [(r + dr, k) for r, k in _shape_in(inp)])


def keep_original(inp, out):
    h = _copy(out)
    for r, k in _shape_in(inp):
        h[r][k] = 2
    return h


def marker_color_shape(inp, out):
    h = _copy(out)
    for r, k in _shape_out(out):
        h[r][k] = 3
    return h


def mirrored_in_place(inp, out):
    cells = _shape_out(out)
    r0, c0, r1, c1 = _box(cells)
    return _draw(_blank_shape(out), [(r, c0 + c1 - k) for r, k in cells])


def flipped_vertically(inp, out):
    cells = _shape_out(out)
    r0, c0, r1, c1 = _box(cells)
    return _draw(_blank_shape(out), [(r0 + r1 - r, k) for r, k in cells])


def interior_filled(inp, out):
    r0, c0, r1, c1 = _box(_shape_out(out))
    h = _blank_shape(out)
    for r in range(r0, r1 + 1):
        for k in range(c0, c1 + 1):
            h[r][k] = 2
    return h


def crop_marker_rectangle(inp, out):
    r0, c0, r1, c1 = _box(_cells(out, 3))
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def only_shape_drawn(inp, out):
    h = _copy(out)
    for r, k in _cells(h, 3):
        h[r][k] = 0
    return h


def rotated_90(inp, out):
    cells = _shape_out(out)
    r0, c0, r1, c1 = _box(cells)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    # rotate bounding box 90 degrees clockwise, anchor at the box's top-left
    new = [(r0 + (k - c0), c0 + (h - 1 - (r - r0))) for r, k in cells]
    return _draw(_blank_shape(out), new)


ALTERNATIVES = [
    ("the shape does not move; output equals input", unmoved),
    ("shape bounding box placed with its corner on the marker corner (off by one up and left)", top_left_on_marker),
    ("shape placed one row too low", shift_down_one),
    ("shape moves horizontally into the interior columns but stays on its rows", horizontal_only),
    ("shape moves vertically into the interior rows but stays on its columns", vertical_only),
    ("shape is copied into the interior and the original is left in place", keep_original),
    ("moved shape takes the marker color", marker_color_shape),
    ("shape placed at the right spot but mirrored left to right", mirrored_in_place),
    ("shape placed at the right spot but flipped top to bottom", flipped_vertically),
    ("shape placed at the right spot and its bounding box filled solid", interior_filled),
    ("output is the crop of the marker rectangle, markers included", crop_marker_rectangle),
    ("markers are erased and only the moved shape is drawn", only_shape_drawn),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/a1570a43.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
