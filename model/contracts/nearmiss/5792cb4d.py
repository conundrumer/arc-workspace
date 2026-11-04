from pathlib import Path
import json
from collections import Counter

TASK = str(Path(__file__).resolve().parents[3] / 'data/tasks/5792cb4d.json')


def bg_of(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def chain(inp):
    """Ordered list of non-background cells, from one chain end to the other."""
    bg = bg_of(inp)
    h, w = len(inp), len(inp[0])
    cells = {(r, c) for r in range(h) for c in range(w) if inp[r][c] != bg}

    def nb(p):
        r, c = p
        return [q for q in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)) if q in cells]

    ends = sorted(p for p in cells if len(nb(p)) == 1)
    if not ends:
        return None
    path, seen, cur = [], set(), ends[0]
    while cur is not None:
        path.append(cur)
        seen.add(cur)
        nxt = [q for q in nb(cur) if q not in seen]
        cur = nxt[0] if nxt else None
    return path


def paint(inp, positions, colors):
    g = [r[:] for r in inp]
    for (r, c), v in zip(positions, colors):
        g[r][c] = v
    return g


def with_chain(f):
    def wrapper(inp, out):
        p = chain(inp)
        if not p:
            return None
        return f(inp, out, p, [inp[r][c] for r, c in p], bg_of(inp))
    return wrapper


@with_chain
def keep_ends(inp, out, p, cols, bg):
    # Reverse only the cells after the first end; the first cell keeps its color.
    return paint(inp, p, cols[:1] + cols[1:][::-1])


@with_chain
def swap_ends_only(inp, out, p, cols, bg):
    return paint(inp, p, [cols[-1]] + cols[1:-1] + [cols[0]])


@with_chain
def rotate_by_one(inp, out, p, cols, bg):
    return paint(inp, p, cols[1:] + cols[:1])


@with_chain
def reverse_half(inp, out, p, cols, bg):
    n = len(cols) // 2
    return paint(inp, p, cols[:n][::-1] + cols[n:])


@with_chain
def rotate_by_half(inp, out, p, cols, bg):
    n = len(cols) // 2
    return paint(inp, p, cols[n:] + cols[:n])


@with_chain
def first_cell_erased(inp, out, p, cols, bg):
    g = paint(inp, p, cols[::-1])
    r, c = p[0]
    g[r][c] = bg
    return g


@with_chain
def last_cell_erased(inp, out, p, cols, bg):
    g = paint(inp, p, cols[::-1])
    r, c = p[-1]
    g[r][c] = bg
    return g


@with_chain
def shift_reversed_by_one(inp, out, p, cols, bg):
    rev = cols[::-1]
    return paint(inp, p, rev[1:] + rev[:1])


@with_chain
def swap_adjacent_pairs(inp, out, p, cols, bg):
    c = cols[:]
    for i in range(0, len(c) - 1, 2):
        c[i], c[i + 1] = c[i + 1], c[i]
    return paint(inp, p, c)


@with_chain
def reversed_chain_one_cell_displaced(inp, out, p, cols, bg):
    # Colors reversed, but the whole chain is drawn shifted one row down.
    g = [[bg] * len(inp[0]) for _ in inp]
    h = len(inp)
    for (r, c), v in zip(p, cols[::-1]):
        if r + 1 >= h:
            return None
        g[r + 1][c] = v
    return g


def flip_lr(inp, out):
    return [r[::-1] for r in inp]


def reverse_only_first_branch_colors(inp, out):
    # Reverse the colors inside the bounding box row by row.
    bg = bg_of(inp)
    g = [r[:] for r in inp]
    for r in g:
        idx = [i for i, v in enumerate(r) if v != bg]
        vals = [r[i] for i in idx][::-1]
        for i, v in zip(idx, vals):
            r[i] = v
    return g


ALTERNATIVES = [
    ("reverse the chain except the first end cell, which keeps its color", keep_ends),
    ("swap only the two end colors", swap_ends_only),
    ("shift colors one step along the chain instead of reversing", rotate_by_one),
    ("reverse only the first half of the chain", reverse_half),
    ("swap the two halves of the chain instead of reversing", rotate_by_half),
    ("reverse the chain but erase the first cell to background", first_cell_erased),
    ("reverse the chain but erase the last cell to background", last_cell_erased),
    ("reverse the chain, then shift colors by one position", shift_reversed_by_one),
    ("swap neighboring color pairs along the chain", swap_adjacent_pairs),
    ("reverse the chain but draw it one row lower", reversed_chain_one_cell_displaced),
    ("mirror the whole grid left to right", flip_lr),
    ("reverse colors within each row separately", reverse_only_first_branch_colors),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    pairs = json.load(open(TASK))["train"]
    print("pairs:", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error:", e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
