"""Near-miss rules for ARC task 817e6c09.

Rule: the 2x2 blocks of color 2 are ordered by column from the right.
The rightmost block, then every second block after it, turns to color 8.
"""
import json
from pathlib import Path

INK = 2
MARK = 8


def blocks(inp):
    """4-connected components of color 2, each a list of (r, c)."""
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != INK or (r, c) in seen:
                continue
            stack, comp = [(r, c)], []
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if (0 <= ny < h and 0 <= nx < w and inp[ny][nx] == INK
                            and (ny, nx) not in seen):
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append(comp)
    return comps


def left(b):
    return min(x for _, x in b)


def top(b):
    return min(y for y, _ in b)


def bottom(b):
    return max(y for y, _ in b)


def paint(inp, chosen, color=MARK):
    g = [row[:] for row in inp]
    for b in chosen:
        for y, x in b:
            g[y][x] = color
    return g


def alt(order, start=0, step=2):
    return order[start::step]


def by_col_desc(inp):
    return sorted(blocks(inp), key=lambda b: (-left(b), -top(b)))


def by_col_asc(inp):
    return sorted(blocks(inp), key=lambda b: (left(b), top(b)))


def from_left(inp, out):
    return paint(inp, alt(by_col_asc(inp)))


def swapped_parity(inp, out):
    return paint(inp, alt(by_col_desc(inp), 1))


def all_blocks(inp, out):
    return paint(inp, blocks(inp))


def every_third(inp, out):
    return paint(inp, alt(by_col_desc(inp), 0, 3))


def rightmost_only(inp, out):
    return paint(inp, by_col_desc(inp)[:1])


def wrong_color(inp, out):
    return paint(inp, alt(by_col_desc(inp)), 4)


def top_row_only(inp, out):
    ch = alt(by_col_desc(inp))
    g = [row[:] for row in inp]
    for b in ch:
        t = top(b)
        for y, x in b:
            if y == t:
                g[y][x] = MARK
    return g


def by_bottom_row(inp, out):
    order = sorted(blocks(inp), key=lambda b: (-bottom(b), -left(b)))
    return paint(inp, alt(order))


def by_top_row(inp, out):
    order = sorted(blocks(inp), key=lambda b: (top(b), left(b)))
    return paint(inp, alt(order))


def right_half_only(inp, out):
    w = len(inp[0])
    ch = [b for b in blocks(inp) if left(b) >= w // 2]
    return paint(inp, ch)


def erase_marked(inp, out):
    return paint(inp, alt(by_col_desc(inp)), 0)


def diagonal_order(inp, out):
    order = sorted(blocks(inp), key=lambda b: (-(left(b) + top(b)), -left(b)))
    return paint(inp, alt(order))


ALTERNATIVES = [
    ("alternate from the leftmost block instead of the rightmost", from_left),
    ("mark the other parity: second from the right and every second after", swapped_parity),
    ("mark every block", all_blocks),
    ("mark every third block from the right", every_third),
    ("mark only the rightmost block", rightmost_only),
    ("right marking set, but paint color 4 instead of 8", wrong_color),
    ("paint only the top row of each marked block", top_row_only),
    ("order blocks by bottom row (lowest first) instead of by column", by_bottom_row),
    ("order blocks by top row (topmost first) instead of by column", by_top_row),
    ("mark every block whose left edge is in the right half of the grid", right_half_only),
    ("erase the marked blocks to 0 instead of painting 8", erase_marked),
    ("order blocks along the diagonal (row + column) instead of by column", diagonal_order),
]


def valid(g, out):
    if g is None or not g or not isinstance(g, list):
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/817e6c09.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
