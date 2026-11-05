"""Near-miss rules for a48eeaf7.

Rule: a solid 2x2 block sits on a background. Each single-cell marker (color 5)
moves straight toward the block, in one of eight directions, and stops at the
first cell that touches the block by side or corner.
"""
import json
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    counts = {}
    for row in inp:
        for v in row:
            counts[v] = counts.get(v, 0) + 1
    bg = max(counts, key=counts.get)
    block_color = None
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v != bg and c + 1 < w and inp[r][c + 1] == v:
                block_color = v
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == block_color]
    r0 = min(r for r, c in cells)
    r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells)
    c1 = max(c for r, c in cells)
    markers = [(r, c, inp[r][c]) for r in range(h) for c in range(w)
               if inp[r][c] != bg and inp[r][c] != block_color]
    return h, w, bg, block_color, (r0, c0, r1, c1), markers


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _sign(v):
    return (v > 0) - (v < 0)


def _redraw(inp, targets, keep_origin=False, recolor=None):
    """Clear markers (unless keep_origin) and draw each marker at its target."""
    h, w, bg, bc, box, markers = _parse(inp)
    g = [row[:] for row in inp]
    if not keep_origin:
        for r, c, v in markers:
            g[r][c] = bg
    for (r, c, v), t in zip(markers, targets):
        if t is None:
            g[r][c] = v
            continue
        tr, tc = t
        if 0 <= tr < h and 0 <= tc < w:
            g[tr][tc] = v if recolor is None else recolor
    return g


def _ring_targets(inp, grow_lo=1, grow_hi=1):
    h, w, bg, bc, (r0, c0, r1, c1), markers = _parse(inp)
    out = []
    for r, c, v in markers:
        out.append((_clamp(r, r0 - grow_lo, r1 + grow_hi),
                    _clamp(c, c0 - grow_lo, c1 + grow_hi)))
    return out


def _is_diag(box, r, c):
    r0, c0, r1, c1 = box
    return not (r0 <= r <= r1) and not (c0 <= c <= c1)


def too_far(inp, out):
    """Stops two cells from the block instead of touching it."""
    h, w = len(inp), len(inp[0])
    t = _ring_targets(inp, 2, 2)
    t = [(_clamp(a, 0, h - 1), _clamp(b, 0, w - 1)) for a, b in t]
    return _redraw(inp, t)


def diag_only_vertical(inp, out):
    """A marker off the block's rows and columns moves only vertically."""
    h, w, bg, bc, box, markers = _parse(inp)
    r0, c0, r1, c1 = box
    t = []
    for r, c, v in markers:
        tr, tc = _clamp(r, r0 - 1, r1 + 1), _clamp(c, c0 - 1, c1 + 1)
        if _is_diag(box, r, c):
            tc = c
        t.append((tr, tc))
    return _redraw(inp, t)


def origin_kept(inp, out):
    """Marker is copied to the ring but its original cell is not cleared."""
    return _redraw(inp, _ring_targets(inp), keep_origin=True)


def enter_block(inp, out):
    """Marker moves onto the block's nearest cell, overwriting the block."""
    h, w, bg, bc, (r0, c0, r1, c1), markers = _parse(inp)
    t = [(_clamp(r, r0, r1), _clamp(c, c0, c1)) for r, c, v in markers]
    return _redraw(inp, t)


def away_from_block(inp, out):
    """Marker moves away from the block, to the grid edge or corner."""
    h, w, bg, bc, (r0, c0, r1, c1), markers = _parse(inp)
    t = []
    for r, c, v in markers:
        dr = -1 if r < r0 else (1 if r > r1 else 0)
        dc = -1 if c < c0 else (1 if c > c1 else 0)
        rr, cc = r, c
        while 0 <= rr + dr < h and 0 <= cc + dc < w:
            rr += dr
            cc += dc
        t.append((rr, cc))
    return _redraw(inp, t)


def recolored_to_block(inp, out):
    """Markers land in the right cells but take the block's color."""
    h, w, bg, bc, box, markers = _parse(inp)
    return _redraw(inp, _ring_targets(inp), recolor=bc)


def diagonals_stay(inp, out):
    """Only markers level with the block's rows or columns move."""
    h, w, bg, bc, box, markers = _parse(inp)
    t = [None if _is_diag(box, r, c) else tg
         for (r, c, v), tg in zip(markers, _ring_targets(inp))]
    return _redraw(inp, t)


def opposite_side(inp, out):
    """Marker lands on the ring cell on the far side of the block."""
    h, w, bg, bc, (r0, c0, r1, c1), markers = _parse(inp)
    t = []
    for r, c, v in markers:
        tr = r0 - 1 if r > r1 else (r1 + 1 if r < r0 else r)
        tc = c0 - 1 if c > c1 else (c1 + 1 if c < c0 else c)
        t.append((tr, tc))
    return _redraw(inp, t)


def ring_off_by_one(inp, out):
    """Ring is one cell too large on the bottom and right only."""
    h, w = len(inp), len(inp[0])
    h, w, bg, bc, (r0, c0, r1, c1), markers = _parse(inp)
    t = [(_clamp(r, r0 - 1, min(h - 1, r1 + 2)), _clamp(c, c0 - 1, min(w - 1, c1 + 2)))
         for r, c, v in markers]
    return _redraw(inp, t)


def one_step(inp, out):
    """Marker moves a single cell toward the block."""
    h, w, bg, bc, (r0, c0, r1, c1), markers = _parse(inp)
    t = []
    for r, c, v in markers:
        dr = 1 if r < r0 else (-1 if r > r1 else 0)
        dc = 1 if c < c0 else (-1 if c > c1 else 0)
        t.append((r + dr, c + dc))
    return _redraw(inp, t)


def only_nearest_moves(inp, out):
    """Only the marker nearest the block moves; the others stay."""
    h, w, bg, bc, (r0, c0, r1, c1), markers = _parse(inp)
    tg = _ring_targets(inp)
    dist = [max(abs(t[0] - r), abs(t[1] - c)) for (r, c, v), t in zip(markers, tg)]
    best = dist.index(min(dist))
    return _redraw(inp, [t if i == best else None for i, t in enumerate(tg)])


ALTERNATIVES = [
    ("marker stops two cells from the block instead of touching it", too_far),
    ("a marker off the block's rows and columns moves only vertically, keeping its column", diag_only_vertical),
    ("marker is drawn at the ring cell but its original cell is not cleared", origin_kept),
    ("marker moves onto the nearest block cell, overwriting the block", enter_block),
    ("marker moves away from the block to the grid edge or corner", away_from_block),
    ("marker lands in the right cell but takes the block's color", recolored_to_block),
    ("only markers level with the block's rows or columns move; diagonal markers stay", diagonals_stay),
    ("marker lands on the ring cell on the far side of the block", opposite_side),
    ("ring is one cell too large on the bottom and right, so markers from below or right stop short of touching", ring_off_by_one),
    ("marker moves a single cell toward the block", one_step),
    ("only the marker nearest the block moves; the others stay", only_nearest_moves),
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
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/a48eeaf7.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
