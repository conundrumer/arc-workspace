from pathlib import Path
import json
from collections import Counter


def _cells(g, c):
    return [(r, k) for r, row in enumerate(g) for k, v in enumerate(row) if v == c]


def _box_of(g, c):
    cs = _cells(g, c)
    return (min(r for r, _ in cs), min(k for _, k in cs),
            max(r for r, _ in cs), max(k for _, k in cs))


def _rare(g, rank=0):
    cnt = Counter(v for row in g for v in row)
    order = sorted(cnt, key=lambda c: (cnt[c], c))
    return order[rank]


def _outline_box(g):
    return _box_of(g, _rare(g))


def _crop(g, r0, c0, r1, c1):
    H, W = len(g), len(g[0])
    r0, c0 = max(r0, 0), max(c0, 0)
    r1, c1 = min(r1, H - 1), min(c1, W - 1)
    if r0 > r1 or c0 > c1:
        return None
    return [row[c0:c1 + 1] for row in g[r0:r1 + 1]]


def interior_only(inp, out):
    r0, c0, r1, c1 = _outline_box(inp)
    return _crop(inp, r0 + 1, c0 + 1, r1 - 1, c1 - 1)


def box_plus_one(inp, out):
    r0, c0, r1, c1 = _outline_box(inp)
    return _crop(inp, r0 - 1, c0 - 1, r1 + 1, c1 + 1)


def box_shifted(inp, out):
    r0, c0, r1, c1 = _outline_box(inp)
    return _crop(inp, r0 + 1, c0 + 1, r1 + 1, c1 + 1)


def box_cut_one_side(inp, out):
    r0, c0, r1, c1 = _outline_box(inp)
    return _crop(inp, r0, c0, r1 - 1, c1 - 1)


def second_rarest_color_box(inp, out):
    r0, c0, r1, c1 = _box_of(inp, _rare(inp, 1))
    return _crop(inp, r0, c0, r1, c1)


def row_band(inp, out):
    r0, c0, r1, c1 = _outline_box(inp)
    return [row[:] for row in inp[r0:r1 + 1]]


def col_band(inp, out):
    r0, c0, r1, c1 = _outline_box(inp)
    return [row[c0:c1 + 1] for row in inp]


def outline_removed(inp, out):
    c = _rare(inp)
    inner = Counter(v for row in out[1:-1] for v in row[1:-1])
    fill = inner.most_common(1)[0][0]
    return [[fill if v == c else v for v in row] for row in out]


def outline_blanked_to_zero(inp, out):
    c = _rare(inp)
    return [[0 if v == c else v for v in row] for row in out]


def rotated_crop(inp, out):
    return [list(r) for r in zip(*out[::-1])]


def mirrored_position(inp, out):
    r0, c0, r1, c1 = _outline_box(inp)
    W = len(inp[0])
    return _crop(inp, r0, W - 1 - c1, r1, W - 1 - c0)


def pattern_tile_instead(inp, out):
    # reads the outline-free pattern: the same-size window from the top-left corner
    h, w = len(out), len(out[0])
    return _crop(inp, 0, 0, h - 1, w - 1)


ALTERNATIVES = [
    ("crop only the interior of the outline, dropping the outline cells", interior_only),
    ("crop the outline box grown by one cell on every side", box_plus_one),
    ("crop a box of the right size shifted one cell down and right", box_shifted),
    ("crop the outline box but cut off its last row and column", box_cut_one_side),
    ("crop the bounding box of the second-rarest color instead of the outline color", second_rarest_color_box),
    ("crop the full-width band of rows spanned by the outline", row_band),
    ("crop the full-height band of columns spanned by the outline", col_band),
    ("crop the box but paint the outline cells with the interior's background color", outline_removed),
    ("crop the box but replace the outline color with 0", outline_blanked_to_zero),
    ("correct crop rotated a quarter turn", rotated_crop),
    ("crop the box at the horizontally mirrored position", mirrored_position),
    ("crop a same-size window from the grid's top-left corner", pattern_tile_instead),
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
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/c909285e.json')))
    train = t["train"]
    print("pairs", len(train))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", e)
                g = None
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
