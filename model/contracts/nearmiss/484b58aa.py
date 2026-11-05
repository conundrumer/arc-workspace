"""Near-miss readings for ARC task 484b58aa (fill 0-holes in a periodic tiling)."""
import json
from collections import Counter
from pathlib import Path


def _copy(g):
    return [list(r) for r in g]


def _holes(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 0]


def _components(inp):
    h, w = len(inp), len(inp[0])
    seen, comps = set(), []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 and (r, c) not in seen:
                stack, comp = [(r, c)], []
                seen.add((r, c))
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            n = (y + dy, x + dx)
                            if 0 <= n[0] < h and 0 <= n[1] < w and inp[n[0]][n[1]] == 0 and n not in seen:
                                seen.add(n)
                                stack.append(n)
                comps.append(comp)
    return comps


def _hpos(out):
    """Smallest horizontal period of the true output."""
    w = len(out[0])
    for p in range(1, w):
        if all(row[c] == row[c + p] for row in out for c in range(w - p)):
            return p
    return w


def left_smear(inp, out):
    g = _copy(inp)
    for r, row in enumerate(g):
        last = None
        for c, v in enumerate(row):
            if v == 0:
                if last is not None:
                    row[c] = last
            else:
                last = v
    return g


def up_smear(inp, out):
    g = _copy(inp)
    for c in range(len(g[0])):
        last = None
        for r in range(len(g)):
            if g[r][c] == 0:
                if last is not None:
                    g[r][c] = last
            else:
                last = g[r][c]
    return g


def dominant_color(inp, out):
    col = Counter(v for row in inp for v in row if v != 0).most_common(1)[0][0]
    return [[col if v == 0 else v for v in row] for row in inp]


def leave_largest_hole(inp, out):
    comps = _components(inp)
    big = max(comps, key=len)
    g = _copy(out)
    for r, c in big:
        g[r][c] = 0
    return g


def column_shift_one(inp, out):
    g = _copy(inp)
    w = len(out[0])
    for r, c in _holes(inp):
        g[r][c] = out[r][(c + 1) % w]
    return g


def row_shift_one(inp, out):
    g = _copy(inp)
    h = len(out)
    for r, c in _holes(inp):
        g[r][c] = out[(r + 1) % h][c]
    return g


def wrong_period(inp, out):
    p = _hpos(out) - 1
    if p < 1:
        return None
    g = _copy(inp)
    w = len(out[0])
    for r, c in _holes(inp):
        v = 0
        for k in range(1, w):
            for cc in (c - k * p, c + k * p):
                if 0 <= cc < w and inp[r][cc] != 0:
                    v = inp[r][cc]
                    break
            if v:
                break
        g[r][c] = v
    return g


def mirror_fill(inp, out):
    g = _copy(inp)
    w = len(out[0])
    for r, c in _holes(inp):
        v = inp[r][w - 1 - c]
        g[r][c] = v if v != 0 else out[r][w - 1 - c]
    return g


def transpose_fill(inp, out):
    g = _copy(inp)
    for r, c in _holes(inp):
        g[r][c] = out[c][r]
    return g


def crop_largest_hole(inp, out):
    big = max(_components(inp), key=len)
    r0, r1 = min(r for r, _ in big), max(r for r, _ in big)
    c0, c1 = min(c for _, c in big), max(c for _, c in big)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def hole_bbox_zeroed(inp, out):
    g = _copy(out)
    for comp in _components(inp):
        r0, r1 = min(r for r, _ in comp), max(r for r, _ in comp)
        c0, c1 = min(c for _, c in comp), max(c for _, c in comp)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                g[r][c] = 0
    return g


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("fill each hole cell with the nearest intact color to its left in the same row", left_smear),
    ("fill each hole cell with the nearest intact color above it in the same column", up_smear),
    ("fill every hole cell with the most common non-hole color", dominant_color),
    ("repair all holes except the largest one", leave_largest_hole),
    ("fill holes from the pattern shifted one column", column_shift_one),
    ("fill holes from the pattern shifted one row", row_shift_one),
    ("measure the horizontal period one too small and copy along rows by that period", wrong_period),
    ("assume left-right mirror symmetry and fill holes from the mirrored cell", mirror_fill),
    ("assume diagonal symmetry and fill holes from the transposed cell", transpose_fill),
    ("output only the repaired content of the largest hole as a crop", crop_largest_hole),
    ("output the input unchanged", unchanged),
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
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/484b58aa.json").read_text())
    pairs = task["train"]
    print(f"pairs: {len(pairs)}")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(_copy(p["input"]), _copy(p["output"]))
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
