"""Near-miss rules for b94a9452: crop the nested-square object and swap its two colors."""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _box(inp):
    bg = _bg(inp)
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v != bg]
    r0 = min(i for i, _ in cells)
    r1 = max(i for i, _ in cells)
    c0 = min(j for _, j in cells)
    c1 = max(j for _, j in cells)
    return r0, r1, c0, c1


def _colors(inp):
    r0, r1, c0, c1 = _box(inp)
    outer = inp[r0][c0]
    inner = inp[(r0 + r1) // 2][(c0 + c1) // 2]
    return outer, inner


def _crop(inp, r0, r1, c0, c1, bg=0):
    h, w = len(inp), len(inp[0])
    return [[inp[i][j] if 0 <= i < h and 0 <= j < w else bg
             for j in range(c0, c1 + 1)] for i in range(r0, r1 + 1)]


def crop_only(inp, out):
    return _crop(inp, *_box(inp))


def swap_no_crop(inp, out):
    outer, inner = _colors(inp)
    m = {outer: inner, inner: outer}
    return [[m.get(v, v) for v in r] for r in inp]


def box_pad_one(inp, out):
    r0, r1, c0, c1 = _box(inp)
    outer, inner = _colors(inp)
    m = {outer: inner, inner: outer}
    g = _crop(inp, r0 - 1, r1 + 1, c0 - 1, c1 + 1, _bg(inp))
    return [[m.get(v, v) for v in r] for r in g]


def box_shrink_one(inp, out):
    r0, r1, c0, c1 = _box(inp)
    outer, inner = _colors(inp)
    m = {outer: inner, inner: outer}
    g = _crop(inp, r0 + 1, r1 - 1, c0 + 1, c1 - 1)
    return [[m.get(v, v) for v in r] for r in g]


def box_offset(inp, out):
    r0, r1, c0, c1 = _box(inp)
    outer, inner = _colors(inp)
    m = {outer: inner, inner: outer}
    g = _crop(inp, r0 + 1, r1 + 1, c0 + 1, c1 + 1, _bg(inp))
    return [[m.get(v, v) for v in r] for r in g]


def inner_to_outer_only(inp, out):
    outer, inner = _colors(inp)
    return [[outer for _ in r] for r in out]


def outer_to_inner_only(inp, out):
    outer, inner = _colors(inp)
    return [[inner for _ in r] for r in out]


def outer_erased(inp, out):
    outer, inner = _colors(inp)
    g = _crop(inp, *_box(inp))
    return [[0 if v == outer else v for v in r] for r in g]


def inner_unfilled(inp, out):
    outer, inner = _colors(inp)
    return [[_bg(inp) if v == outer else v for v in r] for r in out]


def upscaled(inp, out):
    return [[v for v in r for _ in range(2)] for r in out for _ in range(2)]


def inner_box_only(inp, out):
    outer, inner = _colors(inp)
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == inner]
    r0 = min(i for i, _ in cells)
    r1 = max(i for i, _ in cells)
    c0 = min(j for _, j in cells)
    c1 = max(j for _, j in cells)
    return [[outer] * (c1 - c0 + 1) for _ in range(r0, r1 + 1)]


def swap_with_background(inp, out):
    # Treats the background as one of the two colors that swap: outer -> bg, bg -> inner.
    outer, inner = _colors(inp)
    bg = _bg(inp)
    g = _crop(inp, *_box(inp))
    return [[bg if v == outer else v for v in r] for r in g]


ALTERNATIVES = [
    ("crop to the object but keep its colors (no swap)", crop_only),
    ("swap the two colors but keep the whole input grid (no crop)", swap_no_crop),
    ("crop box one cell too large on every side, with the swap", box_pad_one),
    ("crop box one cell too small on every side, with the swap", box_shrink_one),
    ("crop box shifted one row and one column down-right, with the swap", box_offset),
    ("only the inner color is recolored to the outer color: output is one solid outer color", inner_to_outer_only),
    ("only the outer color is recolored to the inner color: output is one solid inner color", outer_to_inner_only),
    ("outer color erased to background, inner color kept", outer_erased),
    ("true output with the new inner region left as background", inner_unfilled),
    ("true output scaled up 2x", upscaled),
    ("output is the inner square's box only, filled with the outer color", inner_box_only),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b94a9452.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")

    def valid(g, out):
        return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                and all(type(v) is int and 0 <= v <= 9 for r in g for v in r) and g != out)

    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
