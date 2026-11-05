"""Near-miss readings for ARC task 952a094c.

Rule: a rectangle frame holds four colored marks at its four inner corners.
Each mark is removed and drawn outside the frame, diagonally beyond the
frame corner that is opposite to the corner the mark came from.
"""
import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != bg]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return h, w, bg, r0, r1, c0, c1


# corner keys: (vertical, horizontal) with 0 = top/left, 1 = bottom/right
def _marks(inp):
    h, w, bg, r0, r1, c0, c1 = _parse(inp)
    pos = {
        (0, 0): (r0 + 1, c0 + 1),
        (0, 1): (r0 + 1, c1 - 1),
        (1, 0): (r1 - 1, c0 + 1),
        (1, 1): (r1 - 1, c1 - 1),
    }
    return {k: (p, inp[p[0]][p[1]]) for k, p in pos.items()}


def _outer(inp, k, dr=0, dc=0):
    """Cell diagonally outside frame corner k, plus optional offset."""
    h, w, bg, r0, r1, c0, c1 = _parse(inp)
    r = r0 - 1 if k[0] == 0 else r1 + 1
    c = c0 - 1 if k[1] == 0 else c1 + 1
    return r + dr, c + dc


def _build(inp, dest, erase=True, keep_corners=None):
    """Clear marks (if erase), then draw each mark colour at dest(key)."""
    h, w, bg, *_ = _parse(inp)
    g = [row[:] for row in inp]
    ms = _marks(inp)
    if erase:
        for (r, c), _ in ms.values():
            g[r][c] = bg
    for k, (_, col) in ms.items():
        if keep_corners is not None and k not in keep_corners:
            continue
        t = dest(inp, k)
        if t is None:
            continue
        r, c = t
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = col
    return g


def horizontal_only(inp, out):
    # mark goes to the outside corner on the opposite side horizontally, same row side
    return _build(inp, lambda i, k: _outer(i, (k[0], 1 - k[1])))


def vertical_only(inp, out):
    return _build(inp, lambda i, k: _outer(i, (1 - k[0], k[1])))


def same_corner(inp, out):
    return _build(inp, lambda i, k: _outer(i, k))


def clockwise_corner(inp, out):
    nxt = {(0, 0): (0, 1), (0, 1): (1, 1), (1, 1): (1, 0), (1, 0): (0, 0)}
    return _build(inp, lambda i, k: _outer(i, nxt[k]))


def transpose_corner(inp, out):
    # corner swap along the other diagonal: TL and BR stay, TR and BL swap
    return _build(inp, lambda i, k: _outer(i, (k[1], k[0])))


def marks_copied(inp, out):
    # marks drawn in the right places but never removed from inside
    return _build(inp, lambda i, k: _outer(i, (1 - k[0], 1 - k[1])), erase=False)


def marks_dropped(inp, out):
    # marks removed but nothing is drawn outside
    return _build(inp, lambda i, k: None)


def onto_frame_corner(inp, out):
    # mark lands on the frame corner cell itself, not beyond it
    return _build(inp, lambda i, k: _outer(i, (1 - k[0], 1 - k[1]),
                                           -1 if k[0] == 1 else 1,
                                           -1 if k[1] == 1 else 1))


def orthogonal_neighbour(inp, out):
    # mark lands directly below/above the opposite frame corner, not diagonal
    def d(i, k):
        o = (1 - k[0], 1 - k[1])
        return _outer(i, o, dr=(-1 if o[0] == 0 else 1) * -1, dc=0)
    return _build(inp, d)


def only_top_marks(inp, out):
    # only the two upper marks are moved; the lower marks are left out
    return _build(inp, lambda i, k: _outer(i, (1 - k[0], 1 - k[1])),
                  keep_corners={(0, 0), (0, 1)})


def grid_corners(inp, out):
    # marks fly to the opposite corner of the whole grid, not of the frame
    h, w = len(inp), len(inp[0])
    return _build(inp, lambda i, k: ((h - 1) if k[0] == 0 else 0,
                                     (w - 1) if k[1] == 0 else 0))


def one_cell_too_far(inp, out):
    # drawn two cells beyond the frame corner (off by one), clipped to the grid
    def d(i, k):
        o = (1 - k[0], 1 - k[1])
        return _outer(i, o, dr=1 if o[0] else -1, dc=1 if o[1] else -1)
    return _build(inp, d)


ALTERNATIVES = [
    ("marks swap left-right only: each goes to the outside corner on the other side horizontally", horizontal_only),
    ("marks swap top-bottom only: each goes to the outside corner on the other side vertically", vertical_only),
    ("each mark goes to the outside frame corner on its own side", same_corner),
    ("each mark goes to the next outside corner clockwise", clockwise_corner),
    ("marks swap along the other diagonal (transposed corner)", transpose_corner),
    ("marks are drawn outside but also left inside the frame", marks_copied),
    ("marks are removed from inside but not drawn anywhere", marks_dropped),
    ("marks land on the frame corner cells instead of outside", onto_frame_corner),
    ("marks land orthogonally next to the opposite frame corner, not diagonally", orthogonal_neighbour),
    ("only the two upper marks are moved", only_top_marks),
    ("marks go to the opposite corners of the whole grid", grid_corners),
    ("marks land one cell too far past the opposite frame corner", one_cell_too_far),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/952a094c.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                g = None
            n += _valid(g, p["output"])
        print(f"{n}/{len(pairs)}  {fn.__name__}: {desc}")
