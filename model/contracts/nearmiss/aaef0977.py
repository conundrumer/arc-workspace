from pathlib import Path
import json, sys

CYC = [3, 4, 0, 5, 2, 8, 9, 6, 1]
BG = 7


def seed(inp):
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v != BG:
                return r, c, v
    return None


def render(inp, dist, cyc=CYC, step=1, offset=0, clamp=False, at=None):
    s = seed(inp)
    if s is None:
        return None
    sr, sc, col = s
    if at is not None:
        sr, sc = at(inp, sr, sc)
    h, w = len(inp), len(inp[0])
    i0 = cyc.index(col) if col in cyc else 0
    n = len(cyc)
    out = []
    for r in range(h):
        row = []
        for c in range(w):
            k = dist(r, c, sr, sc, h, w) + offset
            idx = i0 + step * k
            if clamp:
                idx = min(idx, n - 1 + i0) if step > 0 else idx
                idx = min(max(i0 + step * k, 0), n - 1) if False else idx
            row.append(cyc[idx % n])
        out.append(row)
    return out


def manhattan(r, c, sr, sc, h, w):
    return abs(r - sr) + abs(c - sc)


def cheb(r, c, sr, sc, h, w):
    return max(abs(r - sr), abs(c - sc))


def rowonly(r, c, sr, sc, h, w):
    return abs(r - sr)


def colonly(r, c, sr, sc, h, w):
    return abs(c - sc)


def torus(r, c, sr, sc, h, w):
    dr, dc = abs(r - sr), abs(c - sc)
    return min(dr, h - dr) + min(dc, w - dc)


def f_cheb(inp, out):
    return render(inp, cheb)


def f_rowonly(inp, out):
    return render(inp, rowonly)


def f_colonly(inp, out):
    return render(inp, colonly)


def f_torus(inp, out):
    return render(inp, torus)


def f_reverse(inp, out):
    return render(inp, manhattan, step=-1)


def f_offby1(inp, out):
    return render(inp, manhattan, offset=1)


def f_start_fixed(inp, out):
    # rings always start from the first color of the cycle, not the seed color
    s = seed(inp)
    if s is None:
        return None
    h, w = len(inp), len(inp[0])
    return [[CYC[manhattan(r, c, s[0], s[1], h, w) % 9] for c in range(w)] for r in range(h)]


def f_numeric(inp, out):
    # colors advance in numeric order 0..9 instead of the true cycle
    return render(inp, manhattan, cyc=list(range(10)))


def f_period8(inp, out):
    # one color of the cycle is missed (period 8)
    s = seed(inp)
    if s is None:
        return None
    cyc = [c for c in CYC if c != 1]
    return render(inp, manhattan, cyc=cyc)


def f_clamp(inp, out):
    # the cycle does not repeat; colors stop at the last color of the walk
    s = seed(inp)
    if s is None:
        return None
    h, w = len(inp), len(inp[0])
    i0 = CYC.index(s[2])
    return [[CYC[min(i0 + manhattan(r, c, s[0], s[1], h, w), 8)] if i0 + manhattan(r, c, s[0], s[1], h, w) < 9 else CYC[8]
             for c in range(w)] for r in range(h)]


def f_seed_bg(inp, out):
    # seed cell itself left as background
    s = seed(inp)
    if s is None:
        return None
    g = [row[:] for row in out]
    g[s[0]][s[1]] = BG
    return g


def f_flip_seed(inp, out):
    # seed row taken mirrored top to bottom
    return render(inp, manhattan, at=lambda i, r, c: (len(i) - 1 - r, c))


def f_crop(inp, out):
    # off-by-one size: last row and column dropped
    return [row[:-1] for row in out[:-1]]


def f_center(inp, out):
    # rings measured from the grid center, not the seed
    h, w = len(inp), len(inp[0])
    return render(inp, manhattan, at=lambda i, r, c: (h // 2, w // 2))


ALTERNATIVES = [
    ("distance is Chebyshev (square rings) instead of Manhattan", f_cheb),
    ("distance counts rows only (horizontal bands)", f_rowonly),
    ("distance wraps around the grid edges (toroidal)", f_torus),
    ("cycle is walked in reverse direction", f_reverse),
    ("ring k takes k+1 steps after the seed color (off by one)", f_offby1),
    ("rings start from the first cycle color, not the seed color", f_start_fixed),
    ("colors advance in numeric order 0..9", f_numeric),
    ("cycle misses one color (period 8)", f_period8),
    ("cycle does not repeat; colors stop at the last cycle color", f_clamp),
    ("seed cell left as background", f_seed_bg),
    ("seed location mirrored top to bottom", f_flip_seed),
    ("output cropped by one row and column", f_crop),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    path = str(Path(__file__).resolve().parents[3] / 'data/tasks/aaef0977.json')
    pairs = json.load(open(path))["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
