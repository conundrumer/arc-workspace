"""Near-miss rules for ARC task 8e1813be.

Rule: the input holds parallel one-color stripes and a solid square on top of
them. The output has the square's size; the stripes appear in spatial order,
one per line of the output.
"""
import json
from collections import Counter
from pathlib import Path


def _info(inp, out):
    h, w = len(inp), len(inp[0])
    flat = [v for r in inp for v in r]
    bg = Counter(flat).most_common(1)[0][0]
    out_colors = {v for r in out for v in r}
    sq = [c for c in set(flat) if c != bg and c not in out_colors][0]
    cells = [(i, j) for i in range(h) for j in range(w) if inp[i][j] == sq]
    r0 = min(i for i, _ in cells)
    r1 = max(i for i, _ in cells)
    c0 = min(j for _, j in cells)
    c1 = max(j for _, j in cells)
    horiz = all(len(set(r)) == 1 for r in out)  # stripes are rows
    if horiz:
        order = [r[0] for r in out]
    else:
        order = list(out[0])
    pos = {}
    cnt = {}
    for i in range(h):
        for j in range(w):
            c = inp[i][j]
            if c in order:
                pos[c] = i if horiz else j
                cnt[c] = cnt.get(c, 0) + 1
    return dict(h=h, w=w, bg=bg, sq=sq, box=(r0, r1, c0, c1), horiz=horiz,
                order=order, pos=pos, cnt=cnt, size=len(out) if horiz else len(out[0]))


def _build(order, horiz, cross):
    """Stripes in the given order, each of length `cross`."""
    if horiz:
        return [[c] * cross for c in order]
    return [list(order) for _ in range(cross)]


def _cross(out, horiz):
    return len(out[0]) if horiz else len(out)


def reverse_order(inp, out):
    d = _info(inp, out)
    if d["horiz"]:
        return [list(r) for r in out[::-1]]
    return [list(r[::-1]) for r in out]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def drop_occluded(inp, out):
    d = _info(inp, out)
    r0, r1, c0, c1 = d["box"]
    lo, hi = (r0, r1) if d["horiz"] else (c0, c1)
    keep = [c for c in d["order"] if not (lo <= d["pos"][c] <= hi)]
    if not keep:
        return None
    return _build(keep, d["horiz"], _cross(out, d["horiz"]))


def full_span(inp, out):
    d = _info(inp, out)
    cross = d["w"] if d["horiz"] else d["h"]
    return _build(d["order"], d["horiz"], cross)


def short_by_one(inp, out):
    d = _info(inp, out)
    if d["horiz"]:
        return [r[:-1] for r in out]
    return [list(r) for r in out[:-1]]


def crop_square(inp, out):
    d = _info(inp, out)
    r0, r1, c0, c1 = d["box"]
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def longest_first(inp, out):
    d = _info(inp, out)
    order = sorted(d["order"], key=lambda c: -d["cnt"][c])
    return _build(order, d["horiz"], _cross(out, d["horiz"]))


def color_descending(inp, out):
    d = _info(inp, out)
    order = sorted(d["order"], reverse=True)
    return _build(order, d["horiz"], _cross(out, d["horiz"]))


def window_on_picture(inp, out):
    d = _info(inp, out)
    r0, r1, c0, c1 = d["box"]
    g = [[d["bg"]] * (c1 - c0 + 1) for _ in range(r1 - r0 + 1)]
    for c in d["order"]:
        p = d["pos"][c]
        if d["horiz"] and r0 <= p <= r1:
            g[p - r0] = [c] * (c1 - c0 + 1)
        elif not d["horiz"] and c0 <= p <= c1:
            for row in g:
                row[p - c0] = c
    return g


def keep_gaps(inp, out):
    d = _info(inp, out)
    cross = _cross(out, d["horiz"])
    order = []
    for k, c in enumerate(d["order"]):
        if k:
            order.append(d["bg"])
        order.append(c)
    return _build(order, d["horiz"], cross)


ALTERNATIVES = [
    ("stripes listed in reverse spatial order", reverse_order),
    ("stripes laid out along the wrong axis (output transposed)", transposed),
    ("stripes that pass under the square are left out", drop_occluded),
    ("each stripe drawn at the full input span instead of the square's size", full_span),
    ("output one cell too short across the stripes", short_by_one),
    ("output is the crop of the input at the square's bounding box", crop_square),
    ("stripes ordered by visible length, longest first", longest_first),
    ("stripes ordered by color value, highest first", color_descending),
    ("square used as a window onto the picture, other cells background", window_on_picture),
    ("background gap line kept between consecutive stripes", keep_gaps),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/8e1813be.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {fn.__name__}: {desc}")
