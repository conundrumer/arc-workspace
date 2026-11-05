import json
from pathlib import Path

ECHO = 8
# quadrant name -> (row side, col side); side -1 is the low half, +1 the high half
QUADS = {"TL": (-1, -1), "TR": (-1, 1), "BL": (1, -1), "BR": (1, 1)}


def _geometry(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    qh = (r1 - r0 + 1) // 2
    qw = (c1 - c0 + 1) // 2
    return r0, c0, qh, qw


def _quad_rect(g, name):
    r0, c0, qh, qw = g
    sr, sc = QUADS[name]
    ra = r0 + (qh if sr > 0 else 0)
    ca = c0 + (qw if sc > 0 else 0)
    return ra, ca, qh, qw


def _filled(inp, g, name):
    ra, ca, qh, qw = _quad_rect(g, name)
    return any(inp[r][c] for r in range(ra, ra + qh) for c in range(ca, ca + qw))


def _paint(grid, ra, ca, h, w, color):
    for r in range(ra, ra + h):
        for c in range(ca, ca + w):
            if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
                grid[r][c] = color


def _copy(g):
    return [list(row) for row in g]


def _build(inp, which="empty", shift=lambda n: n, color=ECHO, only_first=False,
           dirs=None, size=None, clear_blocks=False):
    g = _geometry(inp)
    names = [n for n in QUADS if _filled(inp, g, n) == (which == "filled")]
    if only_first:
        names = names[:1]
    res = _copy(inp)
    if clear_blocks:
        res = [[0] * len(inp[0]) for _ in inp]
    for n in names:
        ra, ca, qh, qw = _quad_rect(g, n)
        sr, sc = QUADS[n]
        dr, dc = dirs(sr, sc) if dirs else (sr, sc)
        k = shift(qh)
        h, w = size(qh, qw) if size else (qh, qw)
        if size:
            # box-sized echo: anchored at the box corner nearest the quadrant
            ra = ra if sr < 0 else ra + qh - h
            ca = ca if sc < 0 else ca + qw - w
        _paint(res, ra + dr * k, ca + dc * k, h, w, color)
    return res


def wrong_color(inp, out):
    return _build(inp, color=inp_color(inp))


def inp_color(inp):
    return next(v for row in inp for v in row if v)


def first_only(inp, out):
    return _build(inp, only_first=True)


def echo_filled(inp, out):
    return _build(inp, which="filled")


def gap_by_one(inp, out):
    return _build(inp, shift=lambda n: n + 1)


def fill_in_place(inp, out):
    return _build(inp, shift=lambda n: 0)


def vertical_only(inp, out):
    return _build(inp, dirs=lambda sr, sc: (sr, 0))


def horizontal_only(inp, out):
    return _build(inp, dirs=lambda sr, sc: (0, sc))


def box_sized(inp, out):
    r0, c0, qh, qw = _geometry(inp)
    return _build(inp, size=lambda a, b: (2 * a, 2 * b))


def blocks_removed(inp, out):
    return _build(inp, clear_blocks=True)


def opposite_diagonal(inp, out):
    # echo drawn on the far side: the empty quadrant's echo goes toward the box instead
    return _build(inp, dirs=lambda sr, sc: (-sr, -sc))


def smaller_shift(inp, out):
    return _build(inp, shift=lambda n: max(n - 1, 0) if n > 1 else 0, which="empty")


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("echo drawn in the block color instead of 8", wrong_color),
    ("only the first empty quadrant is echoed", first_only),
    ("the filled quadrants are echoed outward instead of the empty ones", echo_filled),
    ("echo lands one cell farther than the quadrant size", gap_by_one),
    ("empty quadrants are filled in place with 8, no jump", fill_in_place),
    ("echo moves only vertically", vertical_only),
    ("echo moves only horizontally", horizontal_only),
    ("echo is as big as the whole box instead of one quadrant", box_sized),
    ("echo drawn but the original blocks are erased", blocks_removed),
    ("echo jumps from the empty quadrant toward the opposite corner, through the box", opposite_diagonal),
    ("jump is one less than the quadrant size", smaller_shift),
    ("output equals input", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/22233c11.json").read_text())
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(train), desc)
