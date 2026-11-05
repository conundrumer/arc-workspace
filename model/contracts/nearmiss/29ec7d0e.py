import json
from pathlib import Path


def _period(out):
    return len(set(v for row in out for v in row))


def _copy(g):
    return [list(r) for r in g]


def _noise(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 0]


def _formula(out, k, off=1, f=None):
    h, w = len(out), len(out[0])
    f = f or (lambda r, c, k: (r * c) % k)
    return [[f(r, c, k) + off for c in range(w)] for r in range(h)]


def _components(cells):
    cells = set(cells)
    comps = []
    while cells:
        s = cells.pop()
        comp, stack = [s], [s]
        while stack:
            r, c = stack.pop()
            for n in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if n in cells:
                    cells.remove(n)
                    comp.append(n)
                    stack.append(n)
        comps.append(comp)
    return comps


def period_plus_one(inp, out):
    return _formula(out, _period(out) + 1)


def period_minus_one(inp, out):
    return _formula(out, _period(out) - 1)


def additive_tile(inp, out):
    return _formula(out, _period(out), f=lambda r, c, k: (r + c) % k)


def no_offset(inp, out):
    return _formula(out, _period(out), off=0)


def fill_background_one(inp, out):
    g = _copy(inp)
    for r, c in _noise(inp):
        g[r][c] = 1
    return g


def fill_from_left(inp, out):
    g = _copy(inp)
    for r, c in _noise(inp):
        cc = c
        while cc >= 0 and inp[r][cc] == 0:
            cc -= 1
        g[r][c] = inp[r][cc] if cc >= 0 else inp[r][c + 1]
        if g[r][c] == 0:
            g[r][c] = 1
    return g


def shift_wrong_by_one(inp, out):
    k = _period(out)
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r, c in _noise(inp):
        v = inp[r][(c + k - 1) % w]
        g[r][c] = v if v else 1
    return g


def largest_block_only(inp, out):
    comps = _components(_noise(inp))
    if len(comps) < 2:
        return None
    g = _copy(inp)
    big = max(comps, key=len)
    for r, c in big:
        g[r][c] = out[r][c]
    return g


def top_half_only(inp, out):
    g = _copy(out)
    h = len(inp)
    for r, c in _noise(inp):
        if r >= h // 2:
            g[r][c] = 0
    return g


def mirrored_fill(inp, out):
    w = len(out[0])
    g = _copy(inp)
    for r, c in _noise(inp):
        g[r][c] = out[r][w - 1 - c]
    return g


def crop_border(inp, out):
    return [row[1:] for row in out[1:]]


ALTERNATIVES = [
    ("tile period is palette size plus one", period_plus_one),
    ("tile period is palette size minus one", period_minus_one),
    ("tile cell is (r+c) mod k instead of (r*c) mod k", additive_tile),
    ("tile values start at 0 instead of 1", no_offset),
    ("noise cells filled with background color 1", fill_background_one),
    ("noise cells filled from nearest clean cell to the left", fill_from_left),
    ("noise cells filled from a shift of period minus one", shift_wrong_by_one),
    ("only the largest noise block is repaired", largest_block_only),
    ("only noise in the top half is repaired", top_half_only),
    ("noise cells filled from the horizontally mirrored output", mirrored_fill),
    ("output cropped by dropping border row and column", crop_border),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/29ec7d0e.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(n, desc)
