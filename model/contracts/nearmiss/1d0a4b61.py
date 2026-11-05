import json
from collections import Counter
from pathlib import Path


def _copy(g):
    return [row[:] for row in g]


def _holes(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 0]


def _period(out, axis):
    h, w = len(out), len(out[0])
    n = h if axis == 0 else w
    for p in range(1, n):
        ok = True
        for r in range(h):
            for c in range(w):
                rr, cc = (r + p, c) if axis == 0 else (r, c + p)
                if rr < h and cc < w and out[r][c] != out[rr][cc]:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            return p
    return n


def _components(cells):
    cells = set(cells)
    comps = []
    while cells:
        s = cells.pop()
        comp, stack = [s], [s]
        while stack:
            r, c = stack.pop()
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (r + d[0], c + d[1])
                if n in cells:
                    cells.remove(n)
                    comp.append(n)
                    stack.append(n)
        comps.append(comp)
    return comps


def fill_one(inp, out):
    g = _copy(inp)
    for r, c in _holes(inp):
        g[r][c] = 1
    return g


def fill_above(inp, out):
    g = _copy(inp)
    for r, c in _holes(inp):
        rr = r
        while rr >= 0 and inp[rr][c] == 0:
            rr -= 1
        if rr < 0:
            rr = r
            while rr < len(inp) and inp[rr][c] == 0:
                rr += 1
        g[r][c] = inp[rr][c]
    return g


def _shifted_period(dp, dq):
    def f(inp, out):
        h, w = len(out), len(out[0])
        pr, pc = _period(out, 0), _period(out, 1)
        qr, qc = pr + dp, pc + dq
        g = _copy(inp)
        for r, c in _holes(inp):
            val = None
            for k in range(1, 6):
                for sr, sc in ((qr * k, 0), (-qr * k, 0), (0, qc * k), (0, -qc * k)):
                    rr, cc = r + sr, c + sc
                    if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] != 0:
                        val = inp[rr][cc]
                        break
                if val is not None:
                    break
            g[r][c] = out[r][c] if val is None else val
        return g
    return f


def wrong_period_plus_one(inp, out):
    return _shifted_period(1, 1)(inp, out)


def wrong_period_minus_one(inp, out):
    pr, pc = _period(out, 0), _period(out, 1)
    if pr < 3 or pc < 3:
        return None
    return _shifted_period(-1, -1)(inp, out)


def mirror_fill(inp, out):
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r, c in _holes(inp):
        v = inp[r][w - 1 - c]
        if v == 0:
            v = inp[h - 1 - r][c]
        if v == 0:
            v = inp[h - 1 - r][w - 1 - c]
        g[r][c] = v if v != 0 else 1
    return g


def leave_largest_hole(inp, out):
    comps = _components(_holes(inp))
    if len(comps) < 2:
        return None
    big = max(comps, key=len)
    g = _copy(out)
    for r, c in big:
        g[r][c] = 0
    return g


def leave_smallest_hole(inp, out):
    comps = _components(_holes(inp))
    if len(comps) < 2:
        return None
    small = min(comps, key=len)
    g = _copy(out)
    for r, c in small:
        g[r][c] = 0
    return g


def crop_hole_bbox(inp, out):
    hs = _holes(inp)
    r0 = min(r for r, c in hs)
    r1 = max(r for r, c in hs)
    c0 = min(c for r, c in hs)
    c1 = max(c for r, c in hs)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def column_mode(inp, out):
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r, c in _holes(inp):
        cnt = Counter(inp[i][c] for i in range(h) if inp[i][c] != 0)
        g[r][c] = cnt.most_common(1)[0][0] if cnt else 1
    return g


def row_mode(inp, out):
    g = _copy(inp)
    for r, c in _holes(inp):
        cnt = Counter(v for v in inp[r] if v != 0)
        g[r][c] = cnt.most_common(1)[0][0] if cnt else 1
    return g


def phase_off_by_one(inp, out):
    w = len(out[0])
    g = _copy(inp)
    for r, c in _holes(inp):
        g[r][c] = out[r][(c + 1) % w]
    return g


def horizontal_only_phase(inp, out):
    # period class by column phase only: row phase ignored, take the row above
    h = len(out)
    pr = _period(out, 0)
    g = _copy(inp)
    for r, c in _holes(inp):
        g[r][c] = out[(r + 1) % h][c] if pr > 1 else out[r][c]
    return g


def keep_hole_border(inp, out):
    # fill only the interior of each hole, leaving its outer ring as 0
    holes = set(_holes(inp))
    g = _copy(out)
    n = 0
    for r, c in holes:
        if any((r + dr, c + dc) not in holes for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            g[r][c] = 0
            n += 1
    return g if n else None


ALTERNATIVES = [
    ("fill every hole with the background color 1", fill_one),
    ("fill each hole cell by copying the nearest intact cell above in its column", fill_above),
    ("assume both periods are one larger than the true periods", wrong_period_plus_one),
    ("assume both periods are one smaller than the true periods", wrong_period_minus_one),
    ("fill holes from the mirror image of the grid instead of the periodic tiling", mirror_fill),
    ("leave the largest hole unfilled, fill the others", leave_largest_hole),
    ("leave the smallest hole unfilled, fill the others", leave_smallest_hole),
    ("output only the true content of the bounding box of all holes", crop_hole_bbox),
    ("fill each hole cell with the most common intact color of its column", column_mode),
    ("fill each hole cell with the most common intact color of its row", row_mode),
    ("fill holes with the correct tiling shifted by one column", phase_off_by_one),
    ("fill holes with the correct tiling shifted by one row", horizontal_only_phase),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/1d0a4b61.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
