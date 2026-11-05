"""Near-miss readings for a416fc5b."""
import json
from pathlib import Path

RING = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]  # clockwise from north
CW, CCW = 5, 8


def _copy(g):
    return [row[:] for row in g]


def _panel_cells(pr, pc):
    return [(pr * 4 + r, pc * 4 + c) for r in range(3) for c in range(3)]


def _shape_color(inp):
    cols = {}
    for r, row in enumerate(inp):
        for v in row:
            cols[v] = cols.get(v, 0) + 1
    return 2


def _shape(inp):
    """Relative shape cells (from the center panel) and the shape color."""
    col = _shape_color(inp)
    return [(r, c) for r in range(3) for c in range(3) if inp[4 + r][4 + c] == col]


def _other_idx(inp):
    col = _shape_color(inp)
    for i, (dr, dc) in enumerate(RING):
        pr, pc = 1 + dr, 1 + dc
        if any(inp[r][c] == col for r, c in _panel_cells(pr, pc)):
            return i
    return None


def _stamp(g, idx, color, cells):
    pr, pc = 1 + RING[idx % 8][0], 1 + RING[idx % 8][1]
    for r, c in cells:
        g[pr * 4 + r][pc * 4 + c] = color


def _build(inp, targets, cells=None, base=None):
    """targets: list of (ring index, color)."""
    g = _copy(base if base is not None else inp)
    cells = cells if cells is not None else _shape(inp)
    for idx, color in targets:
        _stamp(g, idx, color, cells)
    return g


def swap_colors(inp, out):
    m = {CW: CCW, CCW: CW}
    return [[m.get(v, v) for v in row] for row in out]


def _turn(k, c_cw=CW, c_ccw=CCW):
    def f(inp, out):
        i = _other_idx(inp)
        return _build(inp, [(i + k, c_cw), (i - k, c_ccw)])
    return f


def turn_four(inp, out):
    i = _other_idx(inp)
    return _build(inp, [(i + 4, CW)])


def only_cw(inp, out):
    i = _other_idx(inp)
    return _build(inp, [(i + 3, CW)])


def keep_shape_color(inp, out):
    i = _other_idx(inp)
    return _build(inp, [(i + 3, 2), (i - 3, 2)])


def same_color(inp, out):
    i = _other_idx(inp)
    return _build(inp, [(i + 3, CW), (i - 3, CW)])


def reversed_direction(inp, out):
    i = (_other_idx(inp) + 4) % 8
    return _build(inp, [(i + 3, CW), (i - 3, CCW)])


def filled_panels(inp, out):
    i = _other_idx(inp)
    allc = [(r, c) for r in range(3) for c in range(3)]
    return _build(inp, [(i + 3, CW), (i - 3, CCW)], cells=allc)


def complement_shape(inp, out):
    i = _other_idx(inp)
    s = set(_shape(inp))
    comp = [(r, c) for r in range(3) for c in range(3) if (r, c) not in s]
    return _build(inp, [(i + 3, CW), (i - 3, CCW)], cells=comp)


def shifted_shape(inp, out):
    i = _other_idx(inp)
    cells = [(r + 1, c) for r, c in _shape(inp) if r + 1 < 3]
    return _build(inp, [(i + 3, CW), (i - 3, CCW)], cells=cells)


def recolor_other_too(inp, out):
    i = _other_idx(inp)
    g = _copy(out)
    _stamp(g, i, CW, _shape(inp))
    return g


def point_mirror_targets(inp, out):
    # targets are the panels beside the opposite of the other panel, one step each way
    i = _other_idx(inp)
    return _build(inp, [(i + 5, CW), (i + 3, CCW)])


ALTERNATIVES = [
    ("cw and ccw colors swapped (8 for clockwise target, 5 for counterclockwise)", swap_colors),
    ("targets two ring steps from the other panel instead of three", _turn(2)),
    ("targets one ring step from the other panel instead of three", _turn(1)),
    ("only the opposite panel (four steps) receives a copy", turn_four),
    ("only the clockwise target receives a copy", only_cw),
    ("copies keep the original shape color 2", keep_shape_color),
    ("both targets get the same color 5", same_color),
    ("start the turn from the panel opposite the other panel", reversed_direction),
    ("targets are filled entirely with their color instead of the shape", filled_panels),
    ("copies hold the complement of the shape", complement_shape),
    ("copies are shifted down one row inside the target panel", shifted_shape),
    ("other shape panel is also recolored with 5", recolor_other_too),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/a416fc5b.json"))
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
