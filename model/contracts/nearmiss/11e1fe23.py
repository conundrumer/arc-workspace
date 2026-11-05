import json
from pathlib import Path


def _info(inp):
    bg = max({v for r in inp for v in r}, key=lambda v: sum(r.count(v) for r in inp))
    marks = [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != bg]
    r0 = min(m[0] for m in marks)
    r1 = max(m[0] for m in marks)
    c0 = min(m[1] for m in marks)
    c1 = max(m[1] for m in marks)
    cr, cc = (r0 + r1) // 2, (c0 + c1) // 2
    return bg, marks, (r0, r1, c0, c1), (cr, cc)


def _sgn(a, b):
    return (a > b) - (a < b)


def _mini(inp, out, tf=lambda dr, dc: (dr, dc), step=1, center=None, paint=None, extra=None):
    """Mini placed on the input. tf maps the true (dr, dc) of a mark's quadrant."""
    bg, marks, (r0, r1, c0, c1), (cr, cc) = _info(inp)
    g = [row[:] for row in inp]
    if center is None:
        center = (cr, cc)
    cr, cc = center
    for r, c, v in marks:
        dr, dc = _sgn(r, (r0 + r1) // 2), _sgn(c, (c0 + c1) // 2)
        dr, dc = tf(dr, dc)
        rr, cc2 = cr + dr * step, cc + dc * step
        if 0 <= rr < len(g) and 0 <= cc2 < len(g[0]):
            g[rr][cc2] = v
    cp = paint if paint is not None else _center_color(inp, out)
    if cp is not None and 0 <= cr < len(g) and 0 <= cc < len(g[0]):
        g[cr][cc] = cp
    return g


def _center_color(inp, out):
    bg, marks, box, (cr, cc) = _info(inp)
    return out[cr][cc]


def no_center(inp, out):
    bg, marks, box, (cr, cc) = _info(inp)
    g = [r[:] for r in out]
    g[cr][cc] = bg
    return g


def center_is_mark_color(inp, out):
    bg, marks, box, (cr, cc) = _info(inp)
    g = [r[:] for r in out]
    g[cr][cc] = marks[0][2]
    return g


def step_two(inp, out):
    return _mini(inp, out, step=2)


def hflip(inp, out):
    return _mini(inp, out, tf=lambda dr, dc: (dr, -dc))


def vflip(inp, out):
    return _mini(inp, out, tf=lambda dr, dc: (-dr, dc))


def transposed(inp, out):
    return _mini(inp, out, tf=lambda dr, dc: (dc, dr))


def orthogonal(inp, out):
    return _mini(inp, out, tf=lambda dr, dc: (dr, 0) if dr < 0 or dc > 0 else (0, dc))


def offcenter(inp, out):
    bg, marks, box, (cr, cc) = _info(inp)
    return _mini(inp, out, center=(cr + 1, cc), paint=out[cr][cc])


def marks_erased(inp, out):
    bg, marks, box, c = _info(inp)
    g = [r[:] for r in out]
    for r, cc, v in marks:
        g[r][cc] = bg
    return g


def fourth_corner_filled(inp, out):
    bg, marks, box, (cr, cc) = _info(inp)
    g = [r[:] for r in out]
    for dr in (-1, 1):
        for dc in (-1, 1):
            if g[cr + dr][cc + dc] == bg:
                g[cr + dr][cc + dc] = out[cr][cc]
    return g


def grid_centered(inp, out):
    h, w = len(inp), len(inp[0])
    return _mini(inp, out, center=(h // 2, w // 2), paint=out[_info(inp)[3][0]][_info(inp)[3][1]])


def only_center_and_no_corners(inp, out):
    bg, marks, box, (cr, cc) = _info(inp)
    g = [r[:] for r in inp]
    g[cr][cc] = out[cr][cc]
    return g


ALTERNATIVES = [
    ("center cell of the marks' bounding box left unpainted", no_center),
    ("center cell painted with a mark color instead of the new color", center_is_mark_color),
    ("mini placed two cells diagonally from the center instead of one", step_two),
    ("mini mirrored left-right: each color in the opposite column quadrant", hflip),
    ("mini mirrored top-bottom: each color in the opposite row quadrant", vflip),
    ("mini transposed: each color in the transposed quadrant", transposed),
    ("mini colors placed orthogonally next to the center instead of diagonally", orthogonal),
    ("mini centered one row below the bounding box center", offcenter),
    ("marks moved into the mini instead of copied (original marks erased)", marks_erased),
    ("missing fourth diagonal filled with the center color", fourth_corner_filled),
    ("mini centered at the grid center instead of the bounding box center", grid_centered),
    ("only the center painted, marks not shrunk into the mini", only_center_and_no_corners),
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
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/11e1fe23.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
