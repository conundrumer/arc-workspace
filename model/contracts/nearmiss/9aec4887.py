import json
from pathlib import Path

SHAPE = 8


def _parts(out):
    h, w = len(out), len(out[0])
    sides = {"T": out[0][1], "B": out[h - 1][1], "L": out[1][0], "R": out[1][w - 1]}
    mask = [[out[r][c] != 0 for c in range(1, w - 1)] for r in range(1, h - 1)]
    return h, w, sides, mask


def _margins(r, c, n, m):
    return {"T": r, "B": n - 1 - r, "L": c, "R": m - 1 - c}


def _build(out, mask, pick, sides_override=None, corners=0):
    """Frame from out with the interior drawn from mask; pick(margins) gives a side or None for the shape color."""
    h, w, sides, _ = _parts(out)
    s = sides_override or sides
    g = [[0] * w for _ in range(h)]
    for c in range(1, w - 1):
        g[0][c], g[h - 1][c] = s["T"], s["B"]
    for r in range(1, h - 1):
        g[r][0], g[r][w - 1] = s["L"], s["R"]
    for r in (0, h - 1):
        for c in (0, w - 1):
            g[r][c] = corners
    n, m = h - 2, w - 2
    for r in range(n):
        for c in range(m):
            if mask[r][c]:
                k = pick(_margins(r, c, n, m))
                g[r + 1][c + 1] = SHAPE if k is None else s[k]
    return g


def _nearest(mg, allowed="TBLR", order="TBLR"):
    v = min(mg[k] for k in allowed)
    ks = [k for k in order if k in allowed and mg[k] == v]
    return ks[0] if len(ks) == 1 else None


def _first(mg, order):
    v = min(mg.values())
    return [k for k in order if mg[k] == v][0]


OPP = {"T": "B", "B": "T", "L": "R", "R": "L"}


def no_recolor(inp, out):
    h, w, s, mask = _parts(out)
    return _build(out, mask, lambda mg: None)


def tie_vertical_first(inp, out):
    h, w, s, mask = _parts(out)
    return _build(out, mask, lambda mg: _first(mg, "TBLR"))


def tie_horizontal_first(inp, out):
    h, w, s, mask = _parts(out)
    return _build(out, mask, lambda mg: _first(mg, "LRTB"))


def corners_filled(inp, out):
    g = [r[:] for r in out]
    h, w = len(g), len(g[0])
    for r in (0, h - 1):
        for c in (0, w - 1):
            g[r][c] = SHAPE
    return g


def opposite_side(inp, out):
    h, w, s, mask = _parts(out)
    return _build(out, mask, lambda mg: (lambda k: None if k is None else OPP[k])(_nearest(mg)))


def mask_flip_h(inp, out):
    h, w, s, mask = _parts(out)
    return _build(out, [row[::-1] for row in mask], lambda mg: _nearest(mg))


def mask_transpose(inp, out):
    h, w, s, mask = _parts(out)
    if len(mask) != len(mask[0]):
        return None
    t = [list(x) for x in zip(*mask)]
    return _build(out, t, lambda mg: _nearest(mg))


def interior_only(inp, out):
    return [row[1:-1] for row in out[1:-1]]


def sides_only(inp, out):
    h, w, s, mask = _parts(out)
    return _build(out, [[False] * len(mask[0]) for _ in mask], lambda mg: None)


def horizontal_sides_only(inp, out):
    h, w, s, mask = _parts(out)
    return _build(out, mask, lambda mg: _nearest(mg, "LR"))


def ties_erased(inp, out):
    g = [r[:] for r in out]
    for r in range(1, len(g) - 1):
        for c in range(1, len(g[0]) - 1):
            if g[r][c] == SHAPE:
                g[r][c] = 0
    return g


def lr_sides_swapped(inp, out):
    h, w, s, mask = _parts(out)
    s2 = dict(s)
    s2["L"], s2["R"] = s["R"], s["L"]
    return _build(out, mask, lambda mg: _nearest(mg), sides_override=s2)


ALTERNATIVES = [
    ("shape cells keep the shape color and take no side color", no_recolor),
    ("a tied cell takes the top or bottom side color instead of keeping the shape color", tie_vertical_first),
    ("a tied cell takes the left or right side color instead of keeping the shape color", tie_horizontal_first),
    ("the four open corners are filled with the shape color", corners_filled),
    ("a shape cell takes the color of the side farthest in its direction (opposite of nearest)", opposite_side),
    ("the shape is placed mirrored left to right inside the rectangle", mask_flip_h),
    ("the shape is placed transposed inside the rectangle", mask_transpose),
    ("the output is the interior only, without the border sides", interior_only),
    ("the output is the rectangle with an empty interior", sides_only),
    ("nearest side is chosen among only the left and right sides", horizontal_sides_only),
    ("tied cells are erased to background instead of keeping the shape color", ties_erased),
    ("the left and right side colors are swapped in the frame", lr_sides_swapped),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/9aec4887.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
