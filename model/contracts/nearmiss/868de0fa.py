import json
from pathlib import Path

INK = 1


def holes(inp):
    """Enclosed non-ink regions: list of (cells, top, left, height, width), in reading order."""
    h, w = len(inp), len(inp[0])
    seen = [[False] * w for _ in range(h)]
    stack = [(r, c) for r in range(h) for c in range(w)
             if (r in (0, h - 1) or c in (0, w - 1)) and inp[r][c] != INK]
    for r, c in stack:
        seen[r][c] = True
    while stack:
        r, c = stack.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            y, x = r + dr, c + dc
            if 0 <= y < h and 0 <= x < w and not seen[y][x] and inp[y][x] != INK:
                seen[y][x] = True
                stack.append((y, x))
    out = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != INK and not seen[r][c]:
                comp, st = [], [(r, c)]
                seen[r][c] = True
                while st:
                    y, x = st.pop()
                    comp.append((y, x))
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        a, b = y + dr, x + dc
                        if 0 <= a < h and 0 <= b < w and not seen[a][b] and inp[a][b] != INK:
                            seen[a][b] = True
                            st.append((a, b))
                ys = [p[0] for p in comp]
                xs = [p[1] for p in comp]
                out.append((comp, min(ys), min(xs), max(ys) - min(ys) + 1, max(xs) - min(xs) + 1))
    return out


def paint(inp, colour_of, cells_of=None):
    g = [row[:] for row in inp]
    for i, (cells, t, l, hh, ww) in enumerate(holes(inp)):
        col = colour_of(i, hh, ww)
        if col is None:
            continue
        for (y, x) in (cells_of(cells, t, l, hh, ww) if cells_of else cells):
            g[y][x] = col
    return g


def swapped(inp, out):
    return paint(inp, lambda i, h, w: 2 if (h % 2 and w % 2) else 7)


def alternate_by_order(inp, out):
    return paint(inp, lambda i, h, w: 7 if i % 2 == 0 else 2)


def only_odd_filled(inp, out):
    return paint(inp, lambda i, h, w: 7 if (h % 2 and w % 2) else None)


def only_even_filled(inp, out):
    return paint(inp, lambda i, h, w: None if (h % 2 and w % 2) else 2)


def both_even(inp, out):
    return paint(inp, lambda i, h, w: 7 if (h % 2 == 0 and w % 2 == 0) else 2)


def all_two(inp, out):
    return paint(inp, lambda i, h, w: 2)


def all_seven(inp, out):
    return paint(inp, lambda i, h, w: 7)


def min_dim_three(inp, out):
    return paint(inp, lambda i, h, w: 7 if min(h, w) >= 3 else 2)


def first_only(inp, out):
    return paint(inp, lambda i, h, w: (7 if (h % 2 and w % 2) else 2) if i == 0 else None)


def largest_only(inp, out):
    hs = holes(inp)
    big = max(range(len(hs)), key=lambda i: len(hs[i][0]))
    return paint(inp, lambda i, h, w: (7 if (h % 2 and w % 2) else 2) if i == big else None)


def inset_ring(inp, out):
    def cells_of(cells, t, l, hh, ww):
        return [(y, x) for (y, x) in cells if t < y < t + hh - 1 and l < x < l + ww - 1]
    g = paint(inp, lambda i, h, w: 7 if (h % 2 and w % 2) else 2, cells_of)
    return g


def fill_with_walls(inp, out):
    g = [row[:] for row in inp]
    for cells, t, l, hh, ww in holes(inp):
        col = 7 if (hh % 2 and ww % 2) else 2
        for y in range(t - 1, t + hh + 1):
            for x in range(l - 1, l + ww + 1):
                g[y][x] = col
    return g


ALTERNATIVES = [
    ("odd and even fill colours swapped (2 for odd-sided holes, 7 for the rest)", swapped),
    ("colour alternates 7, 2, 7, ... by hole position in reading order", alternate_by_order),
    ("only odd-sided holes are filled (7); even-sided holes stay 0", only_odd_filled),
    ("only even-sided holes are filled (2); odd-sided holes stay 0", only_even_filled),
    ("7 only when both sides are even (parity flipped by an off-by-one)", both_even),
    ("every hole filled with 2", all_two),
    ("every hole filled with 7", all_seven),
    ("7 when the smaller side is at least 3, else 2 (size threshold instead of parity)", min_dim_three),
    ("only the first hole in reading order is filled", first_only),
    ("only the largest hole is filled", largest_only),
    ("fill leaves a one-cell ring of the hole unfilled", inset_ring),
    ("fill also overwrites the surrounding outline walls", fill_with_walls),
]


def valid(g, ref):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != ref)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/868de0fa.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(n, desc)
    # sanity: the swapped-free true rule reproduces the output
    for p in pairs:
        t = paint(p['input'], lambda i, h, w: 7 if (h % 2 and w % 2) else 2)
        assert t == p['output'], "rule check failed"
