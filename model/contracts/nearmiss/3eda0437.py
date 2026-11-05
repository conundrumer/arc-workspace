import json
from pathlib import Path


def rects(inp, minh=1, minw=1):
    H, W = len(inp), len(inp[0])
    res = []
    for r0 in range(H):
        for r1 in range(r0, H):
            for c0 in range(W):
                for c1 in range(c0, W):
                    if r1 - r0 + 1 < minh or c1 - c0 + 1 < minw:
                        continue
                    if all(inp[r][c] == 0 for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)):
                        res.append((r0, r1, c0, c1))
    return res


def area(r):
    return (r[1] - r[0] + 1) * (r[3] - r[2] + 1)


def hh(r):
    return r[1] - r[0] + 1


def ww(r):
    return r[3] - r[2] + 1


def true_rect(inp, out):
    cells = [(r, c) for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] != out[r][c]]
    return (min(r for r, _ in cells), max(r for r, _ in cells),
            min(c for _, c in cells), max(c for _, c in cells))


def paint(inp, rs, color=6):
    g = [row[:] for row in inp]
    for r0, r1, c0, c1 in rs:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                g[r][c] = color
    return g


def pick(inp, key, minh=2, minw=2, rank=0, reverse=True):
    rs = rects(inp, minh, minw)
    rs.sort(key=key, reverse=reverse)
    return rs[rank] if len(rs) > rank else None


def largest_square(inp, out):
    rs = [r for r in rects(inp, 2, 2) if hh(r) == ww(r)]
    if not rs:
        return None
    return paint(inp, [max(rs, key=lambda r: (area(r), -r[0], -r[2]))])


def second_largest(inp, out):
    t = true_rect(inp, out)
    rs = [r for r in rects(inp, 2, 2) if not (r[0] >= t[0] and r[1] <= t[1] and r[2] >= t[2] and r[3] <= t[3])]
    if not rs:
        return None
    return paint(inp, [max(rs, key=lambda r: (area(r), -r[0], -r[2]))])


def smallest_rect(inp, out):
    rs = rects(inp, 2, 2)
    if not rs:
        return None
    return paint(inp, [min(rs, key=lambda r: (area(r), r[0], r[2]))])


def widest_strip(inp, out):
    rs = rects(inp, 1, 1)
    return paint(inp, [max(rs, key=lambda r: (area(r), -r[0], -r[2]))])


def widest_rect(inp, out):
    rs = rects(inp, 2, 2)
    return paint(inp, [max(rs, key=lambda r: (ww(r), hh(r), -r[0], -r[2]))])


def tallest_rect(inp, out):
    rs = rects(inp, 2, 2)
    return paint(inp, [max(rs, key=lambda r: (hh(r), ww(r), -r[0], -r[2]))])


def all_zero(inp, out):
    return [[6 if v == 0 else v for v in row] for row in inp]


def all_big_rects(inp, out):
    rs = [r for r in rects(inp, 2, 2) if area(r) >= 4]
    # every maximal-ish 2x2 block of zeros
    return paint(inp, [r for r in rs if hh(r) == 2 and ww(r) == 2])


def wrong_color(inp, out):
    return [[8 if o == 6 else o for o in row] for row in out]


def shrunk(inp, out):
    r0, r1, c0, c1 = true_rect(inp, out)
    if r1 - r0 < 2 or c1 - c0 < 2:
        return None
    g = [row[:] for row in inp]
    for r in range(r0 + 1, r1):
        for c in range(c0 + 1, c1):
            g[r][c] = 6
    return g


def grown(inp, out):
    r0, r1, c0, c1 = true_rect(inp, out)
    g = [row[:] for row in out]
    for r in range(r0, min(r1 + 2, len(inp))):
        for c in range(c0, min(c1 + 2, len(inp[0]))):
            g[r][c] = 6
    return g


def top_left_half(inp, out):
    r0, r1, c0, c1 = true_rect(inp, out)
    return paint(inp, [(r0, r0 + (r1 - r0 + 1) // 2 - 1 if r1 > r0 else r0, c0, c1)])


def largest_component(inp, out):
    H, W = len(inp), len(inp[0])
    seen = set()
    best = []
    for r in range(H):
        for c in range(W):
            if inp[r][c] == 0 and (r, c) not in seen:
                comp, st = [], [(r, c)]
                seen.add((r, c))
                while st:
                    y, x = st.pop()
                    comp.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < H and 0 <= nx < W and inp[ny][nx] == 0 and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                if len(comp) > len(best):
                    best = comp
    g = [row[:] for row in inp]
    for y, x in best:
        g[y][x] = 6
    return g


ALTERNATIVES = [
    ("fill the largest empty square instead of the largest empty rectangle", largest_square),
    ("fill the second-largest empty rectangle", second_largest),
    ("fill the smallest empty rectangle of at least 2x2", smallest_rect),
    ("allow 1-wide strips: fill the largest empty rectangle of any shape", widest_strip),
    ("rank empty rectangles by width, not area", widest_rect),
    ("rank empty rectangles by height, not area", tallest_rect),
    ("fill every 0 cell with 6", all_zero),
    ("fill every empty 2x2 block", all_big_rects),
    ("fill the right rectangle with the wrong color 8", wrong_color),
    ("fill only the interior of the rectangle, leaving a one-cell border", shrunk),
    ("fill the rectangle grown by one cell to the right and down", grown),
    ("fill only the top half of the rectangle", top_left_half),
    ("fill the largest 4-connected zero region", largest_component),
]

if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/3eda0437.json').read_text())
    pairs = task['train']
    print('pairs', len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            ok = (g is not None and len(g) > 0 and all(len(r) == len(g[0]) for r in g)
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                  and g != p['output'])
            n += ok
        print(n, desc)
