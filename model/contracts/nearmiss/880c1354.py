"""Near-miss rules for ARC task 880c1354."""
import json
from pathlib import Path


def _info(inp, out):
    """Return (fixed colors, region color mapping inp->out) derived from the pair."""
    h, w = len(inp), len(inp[0])
    seen = {}
    for r in range(h):
        for c in range(w):
            seen.setdefault(inp[r][c], set()).add(out[r][c])
    fixed = {c for c, s in seen.items() if s == {c}}
    m = {c: next(iter(s)) for c, s in seen.items() if c not in fixed}
    return fixed, m


def _remap(inp, fixed, m):
    return [[v if v in fixed else m.get(v, v) for v in row] for row in inp]


def _order(inp, fixed):
    """Region colors in row-major order of first appearance."""
    res = []
    for row in inp:
        for v in row:
            if v not in fixed and v not in res:
                res.append(v)
    return res


def reverse_cycle(inp, out):
    fixed, m = _info(inp, out)
    inv = {v: k for k, v in m.items()}
    return _remap(inp, fixed, inv)


def shift_two(inp, out):
    fixed, m = _info(inp, out)
    return _remap(inp, fixed, {c: m[m[c]] for c in m})


def keep_first_region(inp, out):
    fixed, m = _info(inp, out)
    first = _order(inp, fixed)[0]
    mm = dict(m)
    mm[first] = first
    return _remap(inp, fixed, mm)


def top_half_only(inp, out):
    h = len(inp)
    return [list(out[r]) if r < h // 2 else list(inp[r]) for r in range(h)]


def band_as_region(inp, out):
    """Color 4 (the broad band) treated as a region that takes the first region's new color."""
    fixed, m = _info(inp, out)
    first = _order(inp, fixed)[0]
    return [[m[first] if v == 4 else o for v, o in zip(ri, ro)]
            for ri, ro in zip(inp, out)]


def band_diagonal_wrong(inp, out):
    """Diagonal wall color 7 replaced by 4 in the output."""
    return [[4 if v == 7 else v for v in row] for row in out]


def mirror_horizontal(inp, out):
    return [row[::-1] for row in out]


def transpose_out(inp, out):
    return [list(col) for col in zip(*out)]


def drop_first_row(inp, out):
    return [list(r) for r in out[1:]]


def sorted_color_shift(inp, out):
    """Regions take the next larger region color (cyclic by color value)."""
    fixed, m = _info(inp, out)
    cols = sorted(m)
    mm = {c: cols[(i + 1) % len(cols)] for i, c in enumerate(cols)}
    return _remap(inp, fixed, mm)


def reading_order_shift(inp, out):
    """Regions take the color of the next region in reading order of first appearance."""
    fixed, m = _info(inp, out)
    o = _order(inp, fixed)
    mm = {c: o[(i + 1) % len(o)] for i, c in enumerate(o)}
    return _remap(inp, fixed, mm)


def largest_region_unchanged(inp, out):
    fixed, m = _info(inp, out)
    cnt = {}
    for row in inp:
        for v in row:
            if v not in fixed:
                cnt[v] = cnt.get(v, 0) + 1
    big = max(cnt, key=lambda c: (cnt[c], c))
    mm = dict(m)
    mm[big] = big
    return _remap(inp, fixed, mm)


def input_unchanged(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("regions take the color of the previous region instead of the next (cycle reversed)", reverse_cycle),
    ("regions take the color two steps ahead along the cycle", shift_two),
    ("the first region in reading order keeps its color", keep_first_region),
    ("only the top half of the grid is recolored", top_half_only),
    ("the broad band color 4 is also recolored as if it were a region", band_as_region),
    ("the diagonal wall color 7 is replaced by 4 in the output", band_diagonal_wrong),
    ("output mirrored left to right", mirror_horizontal),
    ("output transposed", transpose_out),
    ("output lacks its first row (off-by-one crop)", drop_first_row),
    ("regions take the next larger region color by color value", sorted_color_shift),
    ("regions take the next region's color in order of first appearance in reading order", reading_order_shift),
    ("the largest region keeps its color", largest_region_unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/880c1354.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
