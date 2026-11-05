"""Near-miss readings for ARC task 985ae207.

Rule: each 3x3 shape (uniform ring around a differently colored center) is
stamped repeatedly, 3 cells apart, toward the solid block whose color equals
the shape's center color. Stamping stops after the first stamp that overlaps
that block.
"""
import json
from collections import Counter
from pathlib import Path

DIRS = [(0, 1), (0, -1), (1, 0), (-1, 0)]


def _bg(inp):
    return Counter(v for row in inp for v in row).most_common(1)[0][0]


def _marks(inp):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    marks = []
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            cc = inp[r][c]
            if cc == bg:
                continue
            ring = {inp[r + dr][c + dc] for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)}
            if len(ring) == 1:
                rc = ring.pop()
                if rc != bg and rc != cc:
                    marks.append((r, c, rc, cc))
    return bg, marks


def _blocks(inp, bg, marks):
    mc = set()
    for r, c, _, _ in marks:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                mc.add((r + dr, c + dc))
    cells = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v != bg and (r, c) not in mc:
                cells.setdefault(v, set()).add((r, c))
    return cells


def _pattern(inp, r, c):
    return [(dr, dc, inp[r + dr][c + dc]) for dr in (-1, 0, 1) for dc in (-1, 0, 1)]


def _hits(r, c, off, blk, test="any"):
    if test == "center":
        return (r + off[0], c + off[1]) in blk
    return any((r + dr + off[0], c + dc + off[1]) in blk for dr in (-1, 0, 1) for dc in (-1, 0, 1))


def _land(inp, r, c, blk, d, pitch, test="any"):
    h, w = len(inp), len(inp[0])
    k = 1
    while True:
        off = (d[0] * pitch * k, d[1] * pitch * k)
        if r + off[0] < -1 or r + off[0] > h or c + off[1] < -1 or c + off[1] > w:
            return None
        if _hits(r, c, off, blk, test):
            return k
        k += 1


def _stamp(g, pat, r, c, off, bgonly=None, solid=None):
    h, w = len(g), len(g[0])
    for dr, dc, v in pat:
        rr, cc = r + dr + off[0], c + dc + off[1]
        if 0 <= rr < h and 0 <= cc < w:
            if bgonly is not None and g[rr][cc] != bgonly:
                continue
            g[rr][cc] = solid if (solid is not None and (dr, dc) == (0, 0)) else v


def _run(inp, pitch=3, extra=0, test="any", marks_sel=None, targets=None,
         opposite=False, both=False, bgonly=False, solid=False, corridor=False):
    bg, marks = _marks(inp)
    if not marks:
        return None
    blocks = _blocks(inp, bg, marks)
    g = [row[:] for row in inp]
    sel = marks if marks_sel is None else marks_sel(marks)
    for i, (r, c, rc, cc) in enumerate(sel):
        tcol = cc if targets is None else targets(marks, i)
        blk = blocks.get(tcol, set())
        pat = _pattern(inp, r, c)
        for d in DIRS:
            kl = _land(inp, r, c, blk, d, pitch, test)
            if kl is None:
                continue
            dirs = []
            if both:
                dirs = [(d, kl), ((-d[0], -d[1]), None)]
            elif opposite:
                dirs = [((-d[0], -d[1]), None)]
            else:
                dirs = [(d, kl)]
            for dd, n in dirs:
                if n is None:
                    n = 0
                    while True:
                        n += 1
                        off = (dd[0] * pitch * n, dd[1] * pitch * n)
                        if r + off[0] < -1 or r + off[0] > len(inp) or c + off[1] < -1 or c + off[1] > len(inp[0]):
                            break
                    n -= 1
                else:
                    n += extra
                for k in range(1, n + 1):
                    off = (dd[0] * pitch * k, dd[1] * pitch * k)
                    if corridor:
                        _stamp(g, [(a, b, rc) for a, b, _ in pat], r, c, off)
                    else:
                        _stamp(g, pat, r, c, off, bgonly=bg if bgonly else None,
                               solid=rc if solid else None)
            break
    return g


def stop_before_block(inp, out):
    return _run(inp, extra=-1)


def one_extra_stamp(inp, out):
    return _run(inp, extra=1)


def pitch_one(inp, out):
    return _run(inp, pitch=1)


def pitch_four(inp, out):
    return _run(inp, pitch=4)


def away_from_block(inp, out):
    return _run(inp, opposite=True)


def first_shape_only(inp, out):
    return _run(inp, marks_sel=lambda m: sorted(m)[:1])


def shapes_swap_targets(inp, out):
    def tg(marks, i):
        s = sorted(marks)
        return s[(i + 1) % len(s)][3]
    return _run(inp, marks_sel=lambda m: sorted(m), targets=tg)


def solid_square_stamp(inp, out):
    return _run(inp, solid=True)


def paint_background_only(inp, out):
    return _run(inp, bgonly=True)


def both_directions(inp, out):
    return _run(inp, both=True)


def corridor_filled_with_ring(inp, out):
    return _run(inp, corridor=True)


ALTERNATIVES = [
    ("stop the stamping one stamp before the one that overlaps the block", stop_before_block),
    ("stamp one more time after the stamp that overlaps the block", one_extra_stamp),
    ("step the stamps by 1 cell instead of 3", pitch_one),
    ("step the stamps by 4 cells (a gap cell between stamps)", pitch_four),
    ("stamp away from the target block, to the grid edge", away_from_block),
    ("handle only the first shape in reading order", first_shape_only),
    ("each shape goes to the block of the next shape's center color", shapes_swap_targets),
    ("stamps are solid squares of the ring color (center lost)", solid_square_stamp),
    ("stamps never overwrite non-background cells (block kept)", paint_background_only),
    ("stamp toward the block and also the opposite way to the edge", both_directions),
    ("fill the corridor to the block with ring-colored 3x3 squares, no centers", corridor_filled_with_ring),
]


def _valid(g, out):
    if g is None or not g or not isinstance(g, list):
        return False
    w = len(g[0])
    if any(not isinstance(r, list) or len(r) != w for r in g):
        return False
    if any(not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / "data/tasks/985ae207.json"
    train = json.load(open(path))["train"]
    # sanity: the full rule reproduces the true outputs
    print("true rule reproduced:", [_run(p["input"]) == p["output"] for p in train])
    print("readings:", len(ALTERNATIVES), "pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in train)
        print(f"{n}/{len(train)}  {desc}")
