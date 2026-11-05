"""Near-miss rules for ARC task 6350f1f4.

The grid is split by all-0 separator lines into equal blocks. One block shows
a two-color template; the other blocks are solid fields in one of the two
colors. Noise cells (a color absent from the output) are removed. In the
output, each template block becomes a solid field of the dominant template
color, and each solid block shows the template shape: the block's own color on
the minor cells and the dominant color elsewhere.
"""
import json
from collections import Counter
from pathlib import Path


def _spans(flags):
    spans, start = [], None
    for i, f in enumerate(flags + [True]):
        if not f and start is None:
            start = i
        if f and start is not None:
            spans.append((start, i))
            start = None
    return spans


def _info(inp, out):
    h, w = len(out), len(out[0])
    rs = _spans([all(v == 0 for v in out[r]) for r in range(h)])
    cs = _spans([all(out[r][c] == 0 for r in range(h)) for c in range(w)])
    noise = {v for row in inp for v in row} - {v for row in out for v in row}
    D = M = T = None
    for (r0, r1) in rs:
        for (c0, c1) in cs:
            cells = [out[r][c] for r in range(r0, r1) for c in range(c0, c1)]
            cnt = Counter(cells)
            if len(cnt) == 2 and T is None:
                (D, _), (M, _) = cnt.most_common(2)
                T = [[out[r][c] == M for c in range(c0, c1)]
                     for r in range(r0, r1)]
    kinds = {}
    for bi, (r0, r1) in enumerate(rs):
        for bj, (c0, c1) in enumerate(cs):
            cells = [inp[r][c] for r in range(r0, r1) for c in range(c0, c1)]
            has_noise = any(v in noise for v in cells)
            cols = {v for v in cells if v not in noise and v != 0}
            if len(cols) >= 2:
                kinds[(bi, bj)] = ("T", None, has_noise)
            else:
                kinds[(bi, bj)] = ("S", next(iter(cols), D), has_noise)
    return rs, cs, noise, D, M, T, kinds


def _paint(inp, out, fn):
    """Copy out; for each block, fn(kind, color, has_noise, h, w, D, M, T)
    returns a block grid or None (leave as is)."""
    rs, cs, noise, D, M, T, kinds = _info(inp, out)
    g = [row[:] for row in out]
    for (bi, bj), (k, c, hn) in kinds.items():
        r0, r1 = rs[bi]
        c0, c1 = cs[bj]
        blk = fn(k, c, hn, r1 - r0, c1 - c0, D, M, T)
        if blk is None:
            continue
        for i in range(r1 - r0):
            for j in range(c1 - c0):
                g[r0 + i][c0 + j] = blk[i][j]
    return g


def _pattern(T, c, D, M):
    """Correct rendering of a solid block of color c."""
    return [[c if t else D for t in row] for row in T]


def _solid_with(T2, inp, out):
    def fn(k, c, hn, h, w, D, M, T):
        if k == "S":
            return _pattern(T2(T), c, D, M)
        return None
    return _paint(inp, out, fn)


def alt_template_kept(inp, out):
    def fn(k, c, hn, h, w, D, M, T):
        if k == "T":
            return [[M if t else D for t in row] for row in T]
    return _paint(inp, out, fn)


def alt_solid_flat_own(inp, out):
    def fn(k, c, hn, h, w, D, M, T):
        if k == "S":
            return [[c] * w for _ in range(h)]
    return _paint(inp, out, fn)


def alt_inverted(inp, out):
    def fn(k, c, hn, h, w, D, M, T):
        if k == "S" and c == M:
            return [[D if t else M for t in row] for row in T]
    return _paint(inp, out, fn)


def alt_mirror(inp, out):
    return _solid_with(lambda T: [r[::-1] for r in T], inp, out)


def alt_rot180(inp, out):
    return _solid_with(lambda T: [r[::-1] for r in T[::-1]], inp, out)


def alt_roll_down(inp, out):
    return _solid_with(lambda T: T[-1:] + T[:-1], inp, out)


def alt_noise_on_separators(inp, out):
    rs, cs, noise, *_ = _info(inp, out)
    g = [row[:] for row in out]
    changed = False
    for r in range(len(out)):
        for c in range(len(out[0])):
            if out[r][c] == 0 and inp[r][c] in noise:
                g[r][c] = inp[r][c]
                changed = True
    return g if changed else None


def alt_no_separators(inp, out):
    rs, cs, *_ = _info(inp, out)
    rows = [r for (a, b) in rs for r in range(a, b)]
    cols = [c for (a, b) in cs for c in range(a, b)]
    return [[out[r][c] for c in cols] for r in rows]


def alt_crop_template(inp, out):
    rs, cs, noise, D, M, T, kinds = _info(inp, out)
    return [[M if t else D for t in row] for row in T]


def alt_template_to_minor(inp, out):
    def fn(k, c, hn, h, w, D, M, T):
        if k == "T":
            return [[M] * w for _ in range(h)]
    return _paint(inp, out, fn)


def alt_all_flat_dominant(inp, out):
    def fn(k, c, hn, h, w, D, M, T):
        return [[D] * w for _ in range(h)]
    return _paint(inp, out, fn)


def alt_noisy_block_flat(inp, out):
    def fn(k, c, hn, h, w, D, M, T):
        if hn and k == "S":
            return [[D] * w for _ in range(h)]
    return _paint(inp, out, fn)


ALTERNATIVES = [
    ("template blocks keep the template shape instead of becoming a solid field", alt_template_kept),
    ("solid blocks stay a flat field of their own color", alt_solid_flat_own),
    ("solid blocks show the template with the two colors swapped", alt_inverted),
    ("solid blocks show the template mirrored left to right", alt_mirror),
    ("solid blocks show the template rotated 180 degrees", alt_rot180),
    ("solid blocks show the template shifted down one row (cyclic)", alt_roll_down),
    ("noise cells on separator lines are left in place", alt_noise_on_separators),
    ("separator lines are dropped and the blocks packed together", alt_no_separators),
    ("output is only the template tile", alt_crop_template),
    ("template blocks become a field of the minor color", alt_template_to_minor),
    ("every block becomes a flat field of the dominant color", alt_all_flat_dominant),
    ("solid blocks that hold noise are flattened to the dominant color", alt_noisy_block_flat),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/6350f1f4.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
