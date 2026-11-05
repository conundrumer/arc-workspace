"""Near-miss rules for 5168d44c.

Rule: a 3x3 ring of 2 around a 3 slides two cells along the line of 3-dots,
toward the side that holds more dots, and lands on the next dot. The old
center dot and all other dots stay.
"""
import json
from pathlib import Path

RING, DOT = 2, 3


def _bbox(g, color):
    cells = [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v == color]
    r0 = min(r for r, _ in cells); r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells); c1 = max(c for _, c in cells)
    return r0, r1, c0, c1


def _center(g):
    r0, r1, c0, c1 = _bbox(g, RING)
    return (r0 + r1) // 2, (c0 + c1) // 2


def _sign(x):
    return (x > 0) - (x < 0)


def _move(inp, out):
    (ir, ic), (orr, oc) = _center(inp), _center(out)
    return ir, ic, orr - ir, oc - ic


def _render(inp, center, color=RING, ring_center=DOT, keep_old=False):
    """Input with the old ring cleared, plus a ring drawn at center (clipped)."""
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    ir, ic = _center(inp)
    if not keep_old:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if (dr or dc) and g[ir + dr][ic + dc] == RING:
                    g[ir + dr][ic + dc] = 0
    cr, cc = center
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            r, c = cr + dr, cc + dc
            if 0 <= r < h and 0 <= c < w:
                g[r][c] = ring_center if (dr == 0 and dc == 0) else color
    return g


def _dots_on_line(inp, ir, ic, ur, uc):
    """Dot positions ahead of the ring center along unit direction (ur, uc)."""
    h, w = len(inp), len(inp[0])
    res, r, c = [], ir + ur, ic + uc
    while 0 <= r < h and 0 <= c < w:
        if inp[r][c] == DOT:
            res.append((r, c))
        r += ur; c += uc
    return res


def opposite_direction(inp, out):
    ir, ic, dr, dc = _move(inp, out)
    return _render(inp, (ir - dr, ic - dc))


def one_step(inp, out):
    ir, ic, dr, dc = _move(inp, out)
    return _render(inp, (ir + _sign(dr), ic + _sign(dc)))


def two_dots_ahead(inp, out):
    ir, ic, dr, dc = _move(inp, out)
    return _render(inp, (ir + 2 * dr, ic + 2 * dc))


def last_dot(inp, out):
    ir, ic, dr, dc = _move(inp, out)
    dots = _dots_on_line(inp, ir, ic, _sign(dr), _sign(dc))
    return _render(inp, dots[-1]) if dots else None


def perpendicular(inp, out):
    ir, ic, dr, dc = _move(inp, out)
    return _render(inp, (ir + dc, ic + dr))


def keep_old_ring(inp, out):
    ir, ic, dr, dc = _move(inp, out)
    return _render(inp, (ir + dr, ic + dc), keep_old=True)


def dots_consumed(inp, out):
    ir, ic, dr, dc = _move(inp, out)
    g = [[0 if v == DOT else v for v in row] for row in out]
    g[ir + dr][ic + dc] = DOT
    return g


def old_center_cleared(inp, out):
    ir, ic, _, _ = _move(inp, out)
    g = [row[:] for row in out]
    g[ir][ic] = 0
    return g


def filled_ring(inp, out):
    ir, ic, dr, dc = _move(inp, out)
    g = [row[:] for row in out]
    g[ir + dr][ic + dc] = RING
    return g


def ring_in_dot_color(inp, out):
    ir, ic, dr, dc = _move(inp, out)
    return _render(inp, (ir + dr, ic + dc), color=DOT)


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("ring moves two cells the opposite way, toward the side with fewer dots", opposite_direction),
    ("ring moves one cell instead of landing on the next dot", one_step),
    ("ring moves four cells, to the second dot ahead", two_dots_ahead),
    ("ring slides to the last dot on the line", last_dot),
    ("ring moves two cells along the perpendicular axis", perpendicular),
    ("ring is copied to the next dot and the old ring stays", keep_old_ring),
    ("ring lands correctly but the other dots on the line are removed", dots_consumed),
    ("ring lands correctly but the old center dot is erased", old_center_cleared),
    ("ring lands correctly but its center is filled with the ring color", filled_ring),
    ("ring lands correctly but is drawn in the dot color", ring_in_dot_color),
    ("input returned unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/5168d44c.json'))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
