"""Near-miss readings for ARC task b5bb5719 (pyramid grows below the seed row)."""
import json
from pathlib import Path

BG = 7
SWAP = {2: 5, 5: 2}


def _bg(inp):
    return BG


def _simulate(inp, color, cond="and", rows=None):
    """Grow rows below row 0. color(left, right) gives the new cell color from the two
    diagonal parent colors (None when the parent is outside the grid or background)."""
    h, w = len(inp), len(inp[0])
    g = [r[:] for r in inp]
    last = h if rows is None else min(h, rows + 1)
    for r in range(1, last):
        for c in range(w):
            if g[r][c] != BG:
                continue
            a = g[r - 1][c - 1] if c - 1 >= 0 and g[r - 1][c - 1] != BG else None
            b = g[r - 1][c + 1] if c + 1 < w and g[r - 1][c + 1] != BG else None
            if cond == "and" and (a is None or b is None):
                continue
            if cond == "or" and a is None and b is None:
                continue
            g[r][c] = color(a, b)
        # keep row-by-row semantics: g row r-1 is final before row r
    return g


def _true_color(a, b):
    return SWAP[a] if a == b else b


def _first_color(inp):
    return next(v for v in inp[0] if v != BG)


def _copy(g):
    return [r[:] for r in g]


def take_left(inp, out):
    return _simulate(inp, lambda a, b: a if a == b or a is not None else b)


def keep_same(inp, out):
    return _simulate(inp, lambda a, b: a if a == b else b)


def keep_on_mixed_left(inp, out):
    return _simulate(inp, lambda a, b: SWAP[a] if a == b else a)


def const_color(inp, out):
    k = _first_color(inp)
    return _simulate(inp, lambda a, b: k)


def swap_always(inp, out):
    return _simulate(inp, lambda a, b: SWAP[b] if b is not None else SWAP[a])


def either_parent(inp, out):
    def f(a, b):
        if a is None:
            return b
        if b is None:
            return a
        return _true_color(a, b)
    return _simulate(inp, f, cond="or")


def grows_upward(inp, out):
    return _copy(out[::-1])


def column_fill(inp, out):
    h, w = len(out), len(out[0])
    g = _copy(out)
    for c in range(w):
        for r in range(1, h):
            if out[r][c] != BG:
                for rr in range(r + 1, h):
                    g[rr][c] = out[r][c]
                break
    return g


def drop_last_row(inp, out):
    return _copy(out[:-1])


def skip_first_row(inp, out):
    g = _copy(out)
    g[1] = list(inp[1])
    return g


def recolor_seed_row(inp, out):
    g = _copy(out)
    g[0] = [SWAP.get(v, v) for v in g[0]]
    return g


def mirrored_fill(inp, out):
    # pyramid reflected left-right while the seed row stays as is
    g = _copy(out)
    for r in range(1, len(g)):
        g[r] = g[r][::-1]
    return g if g != out else None


def double_swap(inp, out):
    g = _copy(out)
    for r in range(1, len(g)):
        g[r] = [SWAP.get(v, v) if inp[r][c] == BG and v != BG else v for c, v in enumerate(g[r])]
    return g


ALTERNATIVES = [
    ("new cell takes its left diagonal parent's color", take_left),
    ("new cell keeps the parent color when parents agree (no swap), right parent when they differ", keep_same),
    ("parents agree: swap; parents differ: left parent's color instead of right", keep_on_mixed_left),
    ("whole pyramid painted in the first seed color", const_color),
    ("new cell always takes the swap of the right parent's color", swap_always),
    ("cell fills when either diagonal parent is filled (cone widens, clipped by grid)", either_parent),
    ("pyramid grows toward the seed row's side reversed (grid flipped vertically)", grows_upward),
    ("pyramid cells extend straight down their columns to the bottom edge", column_fill),
    ("output is one row short (last pyramid row dropped)", drop_last_row),
    ("first pyramid row under the seed is left unfilled", skip_first_row),
    ("seed row colors are swapped as well", recolor_seed_row),
    ("swap partner applied once too often: every pyramid cell takes the opposite of its true color", double_swap),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b5bb5719.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {fn.__name__}: {desc}")
