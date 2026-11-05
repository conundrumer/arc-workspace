"""Near-miss readings for 4093f84a.

Rule: a stripe of 5s crosses the grid. Each dot on a side of the stripe is
removed. Along each line perpendicular to the stripe, the stripe grows toward
the dots by as many cells as the line holds dots on that side.
"""
import json
from pathlib import Path

STRIPE = 5


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _analyze(inp):
    """Return (horizontal grid, was_transposed, r0, r1) with the stripe as rows r0..r1."""
    h, w = len(inp), len(inp[0])
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == STRIPE]
    if not cells:
        return None
    rows = {r for r, _ in cells}
    cols = {c for _, c in cells}
    if len(cols) == w:
        g, t = [list(r) for r in inp], False
    elif len(rows) == h:
        g, t = _transpose(inp), True
    else:
        return None
    r0 = min(r for r in range(len(g)) if STRIPE in g[r])
    r1 = max(r for r in range(len(g)) if STRIPE in g[r])
    return g, t, r0, r1


def _build(inp, length=None, sides=("up", "down"), keep_dots=False,
           flip=False, color=None, recolor_dots=False, bg_fill=0):
    """Draw the stripe, then grow it per line.

    length(count, far, k) -> number of cells grown; count = dots on that
    side of that line, far = distance of the farthest dot (1 = adjacent).
    """
    a = _analyze(inp)
    if a is None:
        return None
    g, t, r0, r1 = a
    h, w = len(g), len(g[0])
    o = [[bg_fill] * w for _ in range(h)]
    for r in range(r0, r1 + 1):
        o[r] = [STRIPE] * w
    if keep_dots:
        for r in range(h):
            for c in range(w):
                if g[r][c] not in (0, STRIPE):
                    o[r][c] = g[r][c]
    if recolor_dots:
        for r in range(h):
            for c in range(w):
                if g[r][c] not in (0, STRIPE):
                    o[r][c] = STRIPE
    if length is not None:
        for c in range(w):
            for side in ("up", "down"):
                if side not in sides:
                    continue
                if side == "up":
                    ds = [r0 - r for r in range(r0) if g[r][c] not in (0, STRIPE)]
                else:
                    ds = [r - r1 for r in range(r1 + 1, h) if g[r][c] not in (0, STRIPE)]
                if not ds:
                    continue
                n = length(len(ds), max(ds), side, c, g, r0, r1)
                tgt = side if not flip else ("down" if side == "up" else "up")
                col = STRIPE if color is None else color(g, r0, r1, c, side)
                for k in range(1, n + 1):
                    r = r0 - k if tgt == "up" else r1 + k
                    if 0 <= r < h:
                        o[r][c] = col
    return _transpose(o) if t else o


def _side_total(g, r0, r1, side):
    h = len(g)
    rng = range(r0) if side == "up" else range(r1 + 1, h)
    return sum(1 for r in rng for v in g[r] if v not in (0, STRIPE))


def alt_dots_kept(inp, out):
    return _build(inp, length=lambda n, f, s, c, g, a, b: n, keep_dots=True)


def alt_length_one(inp, out):
    return _build(inp, length=lambda n, f, s, c, g, a, b: 1)


def alt_length_count_plus_one(inp, out):
    return _build(inp, length=lambda n, f, s, c, g, a, b: n + 1)


def alt_fill_to_farthest(inp, out):
    return _build(inp, length=lambda n, f, s, c, g, a, b: f)


def alt_one_side_only(inp, out):
    return _build(inp, length=lambda n, f, s, c, g, a, b: n, sides=("up",))


def alt_opposite_side(inp, out):
    return _build(inp, length=lambda n, f, s, c, g, a, b: n, flip=True)


def alt_no_growth(inp, out):
    return _build(inp, length=None)


def alt_dots_recolored(inp, out):
    return _build(inp, length=None, recolor_dots=True)


def alt_growth_in_dot_color(inp, out):
    def col(g, r0, r1, c, side):
        rng = range(r0) if side == "up" else range(r1 + 1, len(g))
        for r in rng:
            if g[r][c] not in (0, STRIPE):
                return g[r][c]
        return STRIPE
    return _build(inp, length=lambda n, f, s, c, g, a, b: n, color=col)


def alt_side_total(inp, out):
    return _build(inp, length=lambda n, f, s, c, g, a, b: _side_total(g, a, b, s))


def alt_max_count_per_side(inp, out):
    def ln(n, f, s, c, g, a, b):
        h, w = len(g), len(g[0])
        best = 0
        for cc in range(w):
            rng = range(a) if s == "up" else range(b + 1, h)
            best = max(best, sum(1 for r in rng if g[r][cc] not in (0, STRIPE)))
        return best
    return _build(inp, length=ln)


def alt_count_dots_in_adjacent_rows_only(inp, out):
    """Counts only dots within 2 cells of the stripe."""
    def ln(n, f, s, c, g, a, b):
        h = len(g)
        rng = range(max(0, a - 2), a) if s == "up" else range(b + 1, min(h, b + 3))
        return sum(1 for r in rng if g[r][c] not in (0, STRIPE))
    return _build(inp, length=ln)


ALTERNATIVES = [
    ("growth drawn correctly but the dots are left in place", alt_dots_kept),
    ("every dotted line grows by exactly one cell regardless of dot count", alt_length_one),
    ("growth is the dot count plus one", alt_length_count_plus_one),
    ("growth fills from the stripe out to the farthest dot on the line", alt_fill_to_farthest),
    ("only the upper/left side of the stripe grows; the other side's dots are just removed", alt_one_side_only),
    ("growth appears on the side opposite the dots", alt_opposite_side),
    ("dots are removed but the stripe does not grow", alt_no_growth),
    ("dots are recolored to the stripe color in place, no growth", alt_dots_recolored),
    ("growth uses the dot's color instead of the stripe color", alt_growth_in_dot_color),
    ("growth length is the total dot count on that side of the stripe", alt_side_total),
    ("every dotted line grows by the largest per-line dot count on that side", alt_max_count_per_side),
    ("only dots within two cells of the stripe are counted", alt_count_dots_in_adjacent_rows_only),
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
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/4093f84a.json"))
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
