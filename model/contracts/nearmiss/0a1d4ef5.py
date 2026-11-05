import json
from pathlib import Path


def _rects(inp, out):
    """Solid rectangles (min side 3) of the colors present in the output."""
    h, w = len(inp), len(inp[0])
    colors = {v for r in out for v in r if v}
    used = [[False] * w for _ in range(h)]
    found = []
    while True:
        best = None
        for c in colors:
            for r0 in range(h):
                for c0 in range(w):
                    if inp[r0][c0] != c or used[r0][c0]:
                        continue
                    # widest-first scan for the largest solid block from (r0, c0)
                    maxw = w - c0
                    for r1 in range(r0, h):
                        k = 0
                        while k < maxw and inp[r1][c0 + k] == c and not used[r1][c0 + k]:
                            k += 1
                        maxw = min(maxw, k)
                        if maxw == 0:
                            break
                        hh, ww = r1 - r0 + 1, maxw
                        if hh >= 3 and ww >= 3 and (best is None or hh * ww > best[0]):
                            best = (hh * ww, c, r0, r1, c0, c0 + ww - 1)
        if best is None:
            break
        _, c, r0, r1, c0, c1 = best
        for r in range(r0, r1 + 1):
            for cc in range(c0, c1 + 1):
                used[r][cc] = True
        found.append((c, r0, r1, c0, c1))
    return found


def _bands(intervals, merge=True):
    """Group intervals into bands; return a list of band index per interval."""
    order = sorted(range(len(intervals)), key=lambda i: intervals[i])
    idx = [0] * len(intervals)
    band = -1
    end = None
    prev = None
    for i in order:
        lo, hi = intervals[i]
        if merge:
            new = end is None or lo > end
        else:
            new = prev != (lo, hi)
        if new:
            band += 1
            end = hi
        else:
            end = max(end, hi)
        prev = (lo, hi)
        idx[i] = band
    return idx


def _layout(rects, rmode="overlap", cmode="overlap", key=None):
    ri_iv = [(r[1], r[2]) for r in rects]
    ci_iv = [(r[3], r[4]) for r in rects]
    if rmode == "start":
        ri_iv = [(a, a) for a, _ in ri_iv]
    if cmode == "start":
        ci_iv = [(a, a) for a, _ in ci_iv]
    ri = _bands(ri_iv, rmode == "overlap")
    ci = _bands(ci_iv, cmode == "overlap")
    return ri, ci


def _build(rects, ri, ci, skip=()):
    nr, nc = max(ri) + 1, max(ci) + 1
    g = [[0] * nc for _ in range(nr)]
    for i, r in enumerate(rects):
        if i in skip:
            continue
        g[ri[i]][ci[i]] = r[0]
    return g


def _area(r):
    return (r[2] - r[1] + 1) * (r[4] - r[3] + 1)


def exact_bands(inp, out):
    rects = _rects(inp, out)
    ri, ci = _layout(rects, "exact", "exact")
    return _build(rects, ri, ci)


def start_bands(inp, out):
    rects = _rects(inp, out)
    ri, ci = _layout(rects, "start", "start")
    return _build(rects, ri, ci)


def rows_exact_cols_overlap(inp, out):
    rects = _rects(inp, out)
    ri, ci = _layout(rects, "exact", "overlap")
    return _build(rects, ri, ci)


def drop_smallest(inp, out):
    rects = _rects(inp, out)
    ri, ci = _layout(rects)
    i = min(range(len(rects)), key=lambda k: _area(rects[k]))
    return _build(rects, ri, ci, skip={i})


def drop_largest(inp, out):
    rects = _rects(inp, out)
    ri, ci = _layout(rects)
    i = max(range(len(rects)), key=lambda k: _area(rects[k]))
    return _build(rects, ri, ci, skip={i})


def first_of_each_color(inp, out):
    rects = _rects(inp, out)
    ri, ci = _layout(rects)
    seen = set()
    skip = set()
    for i in sorted(range(len(rects)), key=lambda k: (ri[k], ci[k])):
        if rects[i][0] in seen:
            skip.add(i)
        seen.add(rects[i][0])
    return _build(rects, ri, ci, skip=skip)


def single_row(inp, out):
    rects = _rects(inp, out)
    ri, ci = _layout(rects)
    order = sorted(range(len(rects)), key=lambda k: (ri[k], ci[k]))
    return [[rects[i][0] for i in order]]


def column_major_single_row(inp, out):
    rects = _rects(inp, out)
    ri, ci = _layout(rects)
    order = sorted(range(len(rects)), key=lambda k: (ci[k], ri[k]))
    return [[rects[i][0] for i in order]]


def transpose(inp, out):
    return [list(r) for r in zip(*out)]


def mirror_columns(inp, out):
    return [r[::-1] for r in out]


def flip_rows(inp, out):
    return out[::-1]


def rotate_cw(inp, out):
    return [list(r) for r in zip(*out[::-1])]


def crop_last_column(inp, out):
    return [r[:-1] for r in out]


def fill_gaps_from_left(inp, out):
    g = [list(r) for r in out]
    for r in g:
        last = 0
        for j, v in enumerate(r):
            if v:
                last = v
            elif last:
                r[j] = last
    return g


def rows_by_top_only_cols_overlap(inp, out):
    rects = _rects(inp, out)
    ri, ci = _layout(rects, "start", "overlap")
    return _build(rects, ri, ci)


ALTERNATIVES = [
    ("bands need identical spans, not overlapping ones", exact_bands),
    ("bands keyed by rectangle start line only", start_bands),
    ("row bands need identical spans, column bands merge overlaps", rows_exact_cols_overlap),
    ("row bands keyed by top line only, column bands merge overlaps", rows_by_top_only_cols_overlap),
    ("smallest rectangle is dropped as noise", drop_smallest),
    ("largest rectangle is dropped", drop_largest),
    ("each color is reported only once, at its first position", first_of_each_color),
    ("rectangles are listed as a single row in reading order", single_row),
    ("rectangles are listed as a single row in column-major order", column_major_single_row),
    ("layout is transposed", transpose),
    ("layout is mirrored left to right", mirror_columns),
    ("layout is flipped top to bottom", flip_rows),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/0a1d4ef5.json").read_text())
    train = task["train"]
    # sanity: correct reading reproduces the output
    for k, p in enumerate(train):
        rects = _rects(p["input"], p["output"])
        ri, ci = _layout(rects)
        print("pair", k, "correct reading matches:", _build(rects, ri, ci) == p["output"])
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
