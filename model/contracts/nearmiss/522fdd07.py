"""Near-miss readings for ARC task 522fdd07.

True rule: each single-color square loses its outer ring and stays centered;
a 3x3 square becomes one cell; a one-cell square grows to 9x9.
"""
import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _squares(g):
    """Return (color, r0, c0, r1, c1) per 4-connected single-color body."""
    bg = _bg(g)
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            col = g[r][c]
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and g[ny][nx] == col:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            res.append((col, min(ys), min(xs), max(ys), max(xs)))
    return res


def _render(inp, rule):
    """rule(color, r0, c0, r1, c1) -> list of (color, r0, c0, r1, c1) rectangles (inclusive)."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    for sq in _squares(inp):
        for col, a, b, c, d in rule(*sq):
            for y in range(max(a, 0), min(c, h - 1) + 1):
                for x in range(max(b, 0), min(d, w - 1) + 1):
                    g[y][x] = col
    return g


def _true_rule(col, r0, c0, r1, c1, bloom=4):
    if r0 == r1 and c0 == c1:
        return [(col, r0 - bloom, c0 - bloom, r0 + bloom, c0 + bloom)]
    if r1 - r0 == 2:
        return [(col, r0 + 1, c0 + 1, r1 - 1, c1 - 1)]
    return [(col, r0 + 1, c0 + 1, r1 - 1, c1 - 1)]


def unchanged(inp, out):
    return [row[:] for row in inp]


def small_vanish(inp, out):
    def rule(col, r0, c0, r1, c1):
        if r1 - r0 == 2:
            return []
        return _true_rule(col, r0, c0, r1, c1)
    return _render(inp, rule)


def shrink_two(inp, out):
    def rule(col, r0, c0, r1, c1):
        if r0 == r1:
            return _true_rule(col, r0, c0, r1, c1)
        a, b, c, d = r0 + 2, c0 + 2, r1 - 2, c1 - 2
        if a > c:
            a = c = (r0 + r1) // 2
            b = d = (c0 + c1) // 2
        return [(col, a, b, c, d)]
    return _render(inp, rule)


def corner_anchored(inp, out):
    def rule(col, r0, c0, r1, c1):
        if r0 == r1:
            return _true_rule(col, r0, c0, r1, c1)
        n = r1 - r0 - 1
        return [(col, r0, c0, r0 + n - 1, c0 + n - 1)]
    return _render(inp, rule)


def only_small_shrink(inp, out):
    def rule(col, r0, c0, r1, c1):
        if r1 - r0 == 2:
            return _true_rule(col, r0, c0, r1, c1)
        if r0 == r1:
            return _true_rule(col, r0, c0, r1, c1)
        return [(col, r0, c0, r1, c1)]
    return _render(inp, rule)


def grow_ring(inp, out):
    def rule(col, r0, c0, r1, c1):
        if r0 == r1:
            return _true_rule(col, r0, c0, r1, c1)
        return [(col, r0 - 1, c0 - 1, r1 + 1, c1 + 1)]
    return _render(inp, rule)


def outline_kept(inp, out):
    def rule(col, r0, c0, r1, c1):
        if r0 == r1:
            return _true_rule(col, r0, c0, r1, c1)
        bg = _bg(inp)
        inner = (bg, r0 + 1, c0 + 1, r1 - 1, c1 - 1)
        return [(col, r0, c0, r1, c1), inner]
    return _render(inp, rule)


def bloom_seven(inp, out):
    return _render(inp, lambda *s: _true_rule(*s, bloom=3))


def single_stays(inp, out):
    def rule(col, r0, c0, r1, c1):
        if r0 == r1:
            return [(col, r0, c0, r1, c1)]
        return _true_rule(col, r0, c0, r1, c1)
    return _render(inp, rule)


def width_only(inp, out):
    def rule(col, r0, c0, r1, c1):
        if r0 == r1:
            return _true_rule(col, r0, c0, r1, c1)
        return [(col, r0, c0 + 1, r1, c1 - 1)]
    return _render(inp, rule)


def shifted_right(inp, out):
    def rule(col, r0, c0, r1, c1):
        return [(col, a, b + 1, c, d + 1) for col, a, b, c, d in _true_rule(col, r0, c0, r1, c1)]
    return _render(inp, rule)


ALTERNATIVES = [
    ("squares are left as in the input", unchanged),
    ("a 3x3 square vanishes instead of becoming one cell", small_vanish),
    ("every square loses two rings instead of one", shrink_two),
    ("the shrunk square is anchored at the top-left of its old box", corner_anchored),
    ("only 3x3 squares shrink; larger squares stay whole", only_small_shrink),
    ("every square gains a ring instead of losing one", grow_ring),
    ("the outer ring is kept and the inside is erased", outline_kept),
    ("a one-cell square grows to 7x7 instead of 9x9", bloom_seven),
    ("a one-cell square stays one cell", single_stays),
    ("squares lose columns on the left and right only", width_only),
    ("the shrunk square sits one column right of the center", shifted_right),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/522fdd07.json'))
    train = task["train"]
    # sanity: the true rule reproduces the outputs
    ok = all(_render(p["input"], _true_rule) == p["output"] for p in train)
    print("true rule reproduces outputs:", ok)
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, "/", len(train), desc)
