"""Near-miss rules for ARC task 03560426."""
import json
from pathlib import Path


def blocks(inp):
    """Return a list of (color, r0, c0, r1, c1, cells) for each non-zero color."""
    pos = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v:
                pos.setdefault(v, []).append((r, c))
    res = []
    for col, cells in pos.items():
        rs = [p[0] for p in cells]
        cs = [p[1] for p in cells]
        res.append((col, min(rs), min(cs), max(rs), max(cs)))
    return res


def build(inp, order, step=0, mirror_x=False, from_bottom=False, later_wins=True,
          layout="chain"):
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    # cursor: where the next block's near corner lands
    cr, cc = 0, 0
    seq = order if later_wins else list(reversed(order))
    placed = []
    for (col, r0, c0, r1, c1) in order:
        bh, bw = r1 - r0 + 1, c1 - c0 + 1
        placed.append((col, cr, cc, bh, bw))
        if layout == "chain":
            cr, cc = cr + bh - 1 + step, cc + bw - 1 + step
        else:  # row layout
            cc = cc + bw
    if not later_wins:
        placed = list(reversed(placed))
    for (col, pr, pc, bh, bw) in placed:
        for dr in range(bh):
            for dc in range(bw):
                r = pr + dr
                c = pc + dc
                if from_bottom:
                    r = h - 1 - r
                if mirror_x:
                    c = w - 1 - c
                if 0 <= r < h and 0 <= c < w:
                    g[r][c] = col
    return g


def by_left(inp):
    return sorted(blocks(inp), key=lambda b: (b[2], b[1]))


def size_desc(b):
    return -(b[3] - b[1] + 1) * (b[4] - b[2] + 1)


def alt_earlier_wins(inp, out):
    return build(inp, by_left(inp), later_wins=False)


def alt_no_overlap(inp, out):
    return build(inp, by_left(inp), step=1)


def alt_reverse_order(inp, out):
    return build(inp, list(reversed(by_left(inp))))


def alt_largest_first(inp, out):
    return build(inp, sorted(blocks(inp), key=size_desc))


def alt_tallest_first(inp, out):
    return build(inp, sorted(blocks(inp), key=lambda b: (-(b[3] - b[1]), b[2])))


def alt_top_right_start(inp, out):
    return build(inp, by_left(inp), mirror_x=True)


def alt_bottom_left_start(inp, out):
    return build(inp, by_left(inp), from_bottom=True)


def alt_side_by_side(inp, out):
    return build(inp, by_left(inp), layout="row")


def alt_drop_last(inp, out):
    order = by_left(inp)[:-1]
    if not order:
        return None
    return build(inp, order)


def alt_drop_first_block(inp, out):
    order = by_left(inp)
    first = order[0][0]
    return [[0 if v == first else v for v in row] for row in out]


def alt_overlap_two(inp, out):
    # next block's near corner two cells inside the previous block's far corner
    return build(inp, by_left(inp), step=-1)


def alt_unmoved_blocks_on_chain_clear(inp, out):
    # chain drawn correctly but the original blocks are left where they were
    g = [row[:] for row in out]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v and g[r][c] == 0:
                g[r][c] = v
    return g


ALTERNATIVES = [
    ("overlap cell at a shared corner keeps the earlier block's color", alt_earlier_wins),
    ("next block starts diagonally past the previous far corner (no overlap)", alt_no_overlap),
    ("chain runs right-to-left (blocks in reverse order)", alt_reverse_order),
    ("blocks chained largest area first instead of left to right", alt_largest_first),
    ("blocks chained tallest first instead of left to right", alt_tallest_first),
    ("chain starts at the top-right corner and runs down-left", alt_top_right_start),
    ("chain starts at the bottom-left corner and runs up-right", alt_bottom_left_start),
    ("blocks laid side by side along the top row, no diagonal", alt_side_by_side),
    ("last block of the chain is left out", alt_drop_last),
    ("first block of the chain is left unfilled", alt_drop_first_block),
    ("next block overshoots: its near corner is one cell before the far corner", alt_overlap_two),
    ("chain correct but the original blocks stay in the grid", alt_unmoved_blocks_on_chain_clear),
]


def valid(g, out):
    if g is None:
        return False
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/03560426.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = sum(valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(n, "-", desc)
