import json
from collections import Counter
from pathlib import Path


def _box(inp):
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v != bg]
    r0 = min(i for i, _ in cells)
    r1 = max(i for i, _ in cells)
    c0 = min(j for _, j in cells)
    c1 = max(j for _, j in cells)
    return bg, r0, r1, c0, c1


def _crop(inp):
    _, r0, r1, c0, c1 = _box(inp)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def _dedupe_rows(g):
    res = []
    for r in g:
        if not res or res[-1] != r:
            res.append(list(r))
    return res


def _transpose(g):
    return [list(c) for c in zip(*g)]


def _dedupe(g):
    return _transpose(_dedupe_rows(_transpose(_dedupe_rows(g))))


def box_only(inp, out):
    return _crop(inp)


def rows_only(inp, out):
    return _dedupe_rows(_crop(inp))


def cols_only(inp, out):
    return _transpose(_dedupe_rows(_transpose(_crop(inp))))


def whole_grid(inp, out):
    return _dedupe(inp)


def bg_margin(inp, out):
    bg = _box(inp)[0]
    w = len(out[0]) + 2
    return [[bg] * w] + [[bg] + list(r) + [bg] for r in out] + [[bg] * w]


def drop_last_band(inp, out):
    return [list(r[:-1]) for r in out[:-1]]


def mirror_h(inp, out):
    return [list(r[::-1]) for r in out]


def mirror_v(inp, out):
    return [list(r) for r in out[::-1]]


def transposed(inp, out):
    return _transpose(out)


def rotate_cw(inp, out):
    return [list(r) for r in zip(*out[::-1])]


def roll_rows(inp, out):
    return [list(out[(i + 1) % len(out)]) for i in range(len(out))]


def bg_corner(inp, out):
    g = [list(r) for r in out]
    g[0][0] = _box(inp)[0]
    return g


def distinct_colors_row(inp, out):
    seen = []
    for r in _crop(inp):
        for v in r:
            if v not in seen:
                seen.append(v)
    return [seen]


ALTERNATIVES = [
    ("Output is the cropped bounding box at full size, with no collapse of bands", box_only),
    ("Collapse only repeated rows of the box; repeated columns kept", rows_only),
    ("Collapse only repeated columns of the box; repeated rows kept", cols_only),
    ("Collapse bands over the whole grid, without cropping to the box", whole_grid),
    ("Crop one cell too wide: a ring of background around the output", bg_margin),
    ("Crop one cell too small: last band row and column dropped", drop_last_band),
    ("Output mirrored left to right", mirror_h),
    ("Output flipped top to bottom", mirror_v),
    ("Output transposed (bands read in column-major order)", transposed),
    ("Band rows taken in cyclic shifted order", roll_rows),
    ("Top-left band left as background", bg_corner),
    ("One row listing each distinct color in reading order", distinct_colors_row),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/90c28cc7.json').read_text())
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
