import json
from pathlib import Path

PLUS = [(-1, 0), (0, -1), (0, 0), (0, 1), (1, 0)]
RING = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]


def _copy(g):
    return [row[:] for row in g]


def _rings(inp):
    """Centers of 3x3 rings: eight cells of 1 around a 0 center."""
    h, w = len(inp), len(inp[0])
    found = []
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            if inp[r][c] == 0 and all(inp[r + a][c + b] == 1 for a, b in RING):
                found.append((r, c))
    return found


def _pluses(inp):
    """Centers of complete plus shapes of 1 with empty corners."""
    h, w = len(inp), len(inp[0])
    found = []
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            if all(inp[r + a][c + b] == 1 for a, b in PLUS) and all(
                inp[r + a][c + b] == 0 for a in (-1, 1) for b in (-1, 1)
            ):
                found.append((r, c))
    return found


def _put(g, cells, v):
    h, w = len(g), len(g[0])
    for r, c in cells:
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = v


def full_square(inp, out):
    g = _copy(inp)
    for r, c in _rings(inp):
        _put(g, [(r + a, c + b) for a in (-1, 0, 1) for b in (-1, 0, 1)], 2)
    return g


def center_only(inp, out):
    g = _copy(inp)
    for r, c in _rings(inp):
        _put(g, [(r + a, c + b) for a in (-1, 0, 1) for b in (-1, 0, 1)], 0)
        g[r][c] = 2
    return g


def keep_ring_corners(inp, out):
    g = _copy(out)
    for r, c in _rings(inp):
        _put(g, [(r + a, c + b) for a in (-1, 1) for b in (-1, 1)], 1)
    return g


def shifted_plus(inp, out):
    g = _copy(inp)
    rings = _rings(inp)
    for r, c in rings:
        _put(g, [(r + a, c + b) for a in (-1, 0, 1) for b in (-1, 0, 1)], 0)
    for r, c in rings:
        _put(g, [(r + a + 1, c + b) for a, b in PLUS], 2)
    return g


def recolor_all_ones(inp, out):
    g = _copy(out)
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == 1 and out[r][c] == 1:
                g[r][c] = 2
    return g


def first_ring_only(inp, out):
    g = _copy(inp)
    rings = sorted(_rings(inp))
    if not rings:
        return None
    r, c = rings[0]
    _put(g, [(r + a, c + b) for a in (-1, 0, 1) for b in (-1, 0, 1)], 0)
    _put(g, [(r + a, c + b) for a, b in PLUS], 2)
    return g


def ring_recolored_in_place(inp, out):
    g = _copy(inp)
    for r, c in _rings(inp):
        _put(g, [(r + a, c + b) for a, b in RING], 2)
    return g


def rings_erased(inp, out):
    g = _copy(inp)
    for r, c in _rings(inp):
        _put(g, [(r + a, c + b) for a, b in RING], 0)
    return g


def horizontal_bar(inp, out):
    g = _copy(inp)
    rings = _rings(inp)
    for r, c in rings:
        _put(g, [(r + a, c + b) for a in (-1, 0, 1) for b in (-1, 0, 1)], 0)
    for r, c in rings:
        _put(g, [(r, c - 1), (r, c), (r, c + 1)], 2)
    return g


def plus_to_ring(inp, out):
    """Roles swapped: the plus shapes are turned into rings, rings stay."""
    g = _copy(inp)
    pl = _pluses(inp)
    if not pl:
        return None
    for r, c in pl:
        _put(g, [(r + a, c + b) for a in (-1, 0, 1) for b in (-1, 0, 1)], 0)
        _put(g, [(r + a, c + b) for a, b in RING], 2)
    return g


def plus_wrong_color(inp, out):
    g = _copy(out)
    for r in range(len(out)):
        for c in range(len(out[0])):
            if out[r][c] == 2:
                g[r][c] = 3
    return g


ALTERNATIVES = [
    ("plus is a filled 3x3 square instead of a plus", full_square),
    ("ring is reduced to a single center cell of 2", center_only),
    ("plus is drawn but the ring corners stay in place", keep_ring_corners),
    ("plus is drawn one row below the ring center", shifted_plus),
    ("every shape of 1 not turned into a plus is also recolored 2", recolor_all_ones),
    ("only the first ring in reading order is replaced", first_ring_only),
    ("ring is recolored 2 in place, no plus", ring_recolored_in_place),
    ("rings are erased, no plus drawn", rings_erased),
    ("replacement is a horizontal bar of three cells", horizontal_bar),
    ("plus shapes are turned into rings, rings stay as is", plus_to_ring),
    ("plus is drawn in color 3", plus_wrong_color),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/6c434453.json").read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(_copy(p["input"]), _copy(p["output"]))
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
