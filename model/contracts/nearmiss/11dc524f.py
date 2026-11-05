import json
from collections import Counter
from pathlib import Path

SHAPE, BLOCK = 2, 5


def _parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    sh = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == SHAPE]
    bl = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == BLOCK]
    if not sh or not bl:
        return None
    def box(cs):
        rs = [r for r, _ in cs]
        cc = [c for _, c in cs]
        return min(rs), max(rs), min(cc), max(cc)
    sb, bb = box(sh), box(bl)
    # axis along which the two boxes are disjoint
    gaps = []
    if bb[0] > sb[1]:
        gaps.append((bb[0] - sb[1] - 1, (1, 0)))
    if bb[1] < sb[0]:
        gaps.append((sb[0] - bb[1] - 1, (-1, 0)))
    if bb[2] > sb[3]:
        gaps.append((bb[2] - sb[3] - 1, (0, 1)))
    if bb[3] < sb[2]:
        gaps.append((sb[2] - bb[3] - 1, (0, -1)))
    if not gaps:
        return None
    gap, d = max(gaps)
    return dict(h=h, w=w, bg=bg, sh=sh, bl=bl, sb=sb, bb=bb, gap=gap, d=d)


def _mirror_cells(cells, d, mode):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    hh, ww = r1 - r0 + 1, c1 - c0 + 1
    out = []
    for r, c in cells:
        if d[0]:
            # movement along rows; true mirror reflects across the far edge
            if mode == "true":
                nr = (2 * r1 + 1 - r) if d[0] > 0 else (2 * r0 - 1 - r)
                nc = c
            elif mode == "copy":
                nr, nc = r + hh * d[0], c
            elif mode == "perp":
                nr, nc = r + hh * d[0], c0 + c1 - c
            else:  # rot180
                nr = (2 * r1 + 1 - r) if d[0] > 0 else (2 * r0 - 1 - r)
                nc = c0 + c1 - c
        else:
            if mode == "true":
                nc = (2 * c1 + 1 - c) if d[1] > 0 else (2 * c0 - 1 - c)
                nr = r
            elif mode == "copy":
                nr, nc = r, c + ww * d[1]
            elif mode == "perp":
                nr, nc = r0 + r1 - r, c + ww * d[1]
            else:
                nc = (2 * c1 + 1 - c) if d[1] > 0 else (2 * c0 - 1 - c)
                nr = r0 + r1 - r
        out.append((nr, nc))
    return out


def _build(inp, k=None, mode="true", mcolor=BLOCK, keep_block=False,
           clip_to_block=False, k_mirror=None):
    p = _parse(inp)
    if p is None:
        return None
    g = [[p["bg"]] * p["w"] for _ in range(p["h"])]
    d = p["d"]
    kk = p["gap"] if k is None else k
    moved = [(r + d[0] * kk, c + d[1] * kk) for r, c in p["sh"]]
    base = moved if k_mirror is None else [
        (r + d[0] * k_mirror, c + d[1] * k_mirror) for r, c in p["sh"]]
    mir = [] if keep_block else _mirror_cells(base, d, mode)
    if keep_block:
        mir = p["bl"]
    if clip_to_block:
        b = p["bb"]
        mir = [(r, c) for r, c in mir if b[0] <= r <= b[1] and b[2] <= c <= b[3]]
    for r, c in mir:
        if 0 <= r < p["h"] and 0 <= c < p["w"]:
            g[r][c] = mcolor
    for r, c in moved:
        if 0 <= r < p["h"] and 0 <= c < p["w"]:
            g[r][c] = SHAPE
    return g


def shape_stays(inp, out):
    p = _parse(inp)
    return _build(inp, k=0, k_mirror=p["gap"]) if p else None


def stops_one_short(inp, out):
    p = _parse(inp)
    return _build(inp, k=p["gap"] - 1) if p else None


def overshoots_one(inp, out):
    p = _parse(inp)
    return _build(inp, k=p["gap"] + 1) if p else None


def copy_not_mirror(inp, out):
    return _build(inp, mode="copy")


def flip_wrong_axis(inp, out):
    return _build(inp, mode="perp")


def rotate_180(inp, out):
    return _build(inp, mode="rot180")


def block_unchanged(inp, out):
    return _build(inp, keep_block=True)


def mirror_in_shape_color(inp, out):
    return _build(inp, mcolor=SHAPE)


def moves_away(inp, out):
    p = _parse(inp)
    return _build(inp, k=-p["gap"], k_mirror=p["gap"]) if p else None


def mirror_clipped_to_block_box(inp, out):
    return _build(inp, clip_to_block=True)


def block_moves_instead(inp, out):
    p = _parse(inp)
    if p is None:
        return None
    g = [[p["bg"]] * p["w"] for _ in range(p["h"])]
    d = p["d"]
    for r, c in p["sh"]:
        g[r][c] = SHAPE
    for r, c in p["bl"]:
        nr, nc = r - d[0] * p["gap"], c - d[1] * p["gap"]
        if 0 <= nr < p["h"] and 0 <= nc < p["w"]:
            g[nr][nc] = BLOCK
    return g


ALTERNATIVES = [
    ("shape stays in place; only the mirror is drawn next to the shape's true landing spot", shape_stays),
    ("shape stops one cell short of the block, mirror drawn beside it", stops_one_short),
    ("shape moves one cell too far, mirror drawn beside it", overshoots_one),
    ("block becomes a plain translated copy of the shape, not a mirror", copy_not_mirror),
    ("block mirrors the shape across the wrong axis (flip along the perpendicular axis)", flip_wrong_axis),
    ("block becomes the shape rotated 180 degrees", rotate_180),
    ("block is left as the original 2x2 square; shape moves", block_unchanged),
    ("mirror image is painted in the shape's color", mirror_in_shape_color),
    ("shape moves away from the block by the gap distance", moves_away),
    ("mirror is clipped to the block's original bounding box", mirror_clipped_to_block_box),
    ("block moves toward the shape instead; shape stays", block_moves_instead),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/11dc524f.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in pairs:
            g = fn(pr["input"], pr["output"])
            if g is not None and _valid(g, pr["output"]):
                n += 1
        print(n, desc)
