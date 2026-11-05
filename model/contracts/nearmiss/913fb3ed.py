import json
from collections import Counter
from pathlib import Path

D8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
D4 = [(-1, 0), (0, -1), (0, 1), (1, 0)]


def _dots(inp):
    ground = Counter(v for row in inp for v in row).most_common(1)[0][0]
    return ground, [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != ground]


def _ring_color(out, r, c):
    return out[r - 1][c] if r > 0 else out[r + 1][c]


def _stamp(inp, dots, color_of, offsets, keep_dots=True, shift=(0, 0)):
    g = [row[:] for row in inp]
    dot_cells = {(r, c) for r, c, _ in dots}
    for r, c, v in dots:
        col = color_of(r, c, v)
        for dr, dc in offsets:
            rr, cc = r + dr + shift[0], c + dc + shift[1]
            if 0 <= rr < len(g) and 0 <= cc < len(g[0]) and not (keep_dots and (rr, cc) in dot_cells):
                g[rr][cc] = col
    return g


def four_neighbors_only(inp, out):
    ground, dots = _dots(inp)
    g = [row[:] for row in out]
    for r, c, v in dots:
        for dr, dc in D8:
            if dr != 0 and dc != 0:
                g[r + dr][c + dc] = ground
    return g


def horizontal_arms_only(inp, out):
    ground, dots = _dots(inp)
    g = [row[:] for row in out]
    for r, c, v in dots:
        for dr, dc in D8:
            if dr != 0:
                g[r + dr][c + dc] = ground
    return g


def all_rings_color_six(inp, out):
    ground, dots = _dots(inp)
    return _stamp(inp, dots, lambda r, c, v: 6, D8)


def ring_same_color_as_dot(inp, out):
    ground, dots = _dots(inp)
    return _stamp(inp, dots, lambda r, c, v: v, D8)


def ring_colors_rotated(inp, out):
    ground, dots = _dots(inp)
    rot = {6: 1, 1: 4, 4: 6}
    return _stamp(inp, dots, lambda r, c, v: rot[_ring_color(out, r, c)], D8)


def radius_two_ring(inp, out):
    ground, dots = _dots(inp)
    offs = [(dr, dc) for dr in range(-2, 3) for dc in range(-2, 3) if (dr, dc) != (0, 0)]
    return _stamp(inp, dots, lambda r, c, v: _ring_color(out, r, c), offs)


def centre_overpainted(inp, out):
    ground, dots = _dots(inp)
    g = [row[:] for row in out]
    for r, c, v in dots:
        g[r][c] = _ring_color(out, r, c)
    return g


def ring_shifted_down_right(inp, out):
    ground, dots = _dots(inp)
    return _stamp(inp, dots, lambda r, c, v: _ring_color(out, r, c), D8, shift=(1, 1))


def dots_erased(inp, out):
    ground, dots = _dots(inp)
    g = [row[:] for row in out]
    for r, c, v in dots:
        g[r][c] = ground
    return g


def only_topmost_dot_stamped(inp, out):
    ground, dots = _dots(inp)
    if len(dots) < 2:
        return None
    r0, c0, v0 = dots[0]
    return _stamp(inp, [(r0, c0, v0)], lambda r, c, v: _ring_color(out, r, c), D8)


ALTERNATIVES = [
    ("ring covers only the 4 orthogonal neighbours of each dot", four_neighbors_only),
    ("ring covers only the left and right neighbours of each dot", horizontal_arms_only),
    ("every dot gets the same ring color 6", all_rings_color_six),
    ("ring is drawn in the dot's own color", ring_same_color_as_dot),
    ("ring colors are cycled (6->1, 1->4, 4->6)", ring_colors_rotated),
    ("ring is 5x5 (radius 2) instead of 3x3", radius_two_ring),
    ("dot's own cell is repainted with the ring color", centre_overpainted),
    ("ring is placed one cell down and right of the dot", ring_shifted_down_right),
    ("dot is erased, only the ring remains", dots_erased),
    ("only the first dot in reading order gets a ring", only_topmost_dot_stamped),
]


def _valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/913fb3ed.json").read_text())
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = sum(1 for p in train if (g := fn(p["input"], p["output"])) is not None and _valid(g, p["output"]))
        print(f"{n}/{len(train)}  {desc}")
