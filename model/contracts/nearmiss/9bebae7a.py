import json
from collections import Counter
from pathlib import Path

DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
CCW = {"up": "left", "left": "down", "down": "right", "right": "up"}
CW = {v: k for k, v in CCW.items()}
OPP = {"up": "down", "down": "up", "left": "right", "right": "left"}


def parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    cols = [c for c in cnt if c != bg]
    cols.sort(key=lambda c: -cnt[c])
    sc, mc = cols[0], cols[1]
    shape = {(r, c) for r in range(h) for c in range(w) if inp[r][c] == sc}
    mark = {(r, c) for r in range(h) for c in range(w) if inp[r][c] == mc}
    return h, w, bg, sc, mc, shape, mark


def bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def arms(mark):
    for (r, c) in mark:
        if all(((r + dr, c + dc) in mark) for dr, dc in ((1, 0), (-1, 0))) or \
           all(((r + dr, c + dc) in mark) for dr, dc in ((0, 1), (0, -1))):
            pass
    cross = None
    for (r, c) in mark:
        v = (r - 1, c) in mark or (r + 1, c) in mark
        hz = (r, c - 1) in mark or (r, c + 1) in mark
        if v and hz:
            cross = (r, c)
    r, c = cross
    res = {}
    for d, (dr, dc) in DIRS.items():
        n = 0
        while (r + dr * (n + 1), c + dc * (n + 1)) in mark:
            n += 1
        res[d] = n
    return cross, res


def far_dir(mark):
    _, a = arms(mark)
    return max(a, key=lambda d: a[d])


def true_side(mark):
    return CCW[far_dir(mark)]


def reflect(shape, side, gap=0):
    r0, r1, c0, c1 = bbox(shape)
    out = set()
    for r, c in shape:
        if side == "down":
            out.add((2 * r1 + 1 - r + gap, c))
        elif side == "up":
            out.add((2 * r0 - 1 - r - gap, c))
        elif side == "right":
            out.add((r, 2 * c1 + 1 - c + gap))
        else:
            out.add((r, 2 * c0 - 1 - c - gap))
    return out


def translate(shape, side):
    r0, r1, c0, c1 = bbox(shape)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    dr, dc = DIRS[side]
    return {(r + dr * h, c + dc * w) for r, c in shape}


def render(h, w, bg, cells_by_color):
    g = [[bg] * w for _ in range(h)]
    for color, cells in cells_by_color:
        for r, c in cells:
            if 0 <= r < h and 0 <= c < w:
                g[r][c] = color
    return g


def build(inp, side, copy_color=None, keep_orig=True, keep_mark=False, mode="reflect", gap=0):
    h, w, bg, sc, mc, shape, mark = parse(inp)
    if mode == "reflect":
        cp = reflect(shape, side, gap)
    elif mode == "translate":
        cp = translate(shape, side)
    else:  # translate then flip along the other axis
        cp = translate(shape, side)
        r0, r1, c0, c1 = bbox(cp)
        if side in ("up", "down"):
            cp = {(r, c0 + c1 - c) for r, c in cp}
        else:
            cp = {(r0 + r1 - r, c) for r, c in cp}
    layers = []
    if keep_mark:
        layers.append((mc, mark))
    if keep_orig:
        layers.append((sc, shape))
    layers.append((sc if copy_color is None else copy_color, cp))
    return render(h, w, bg, layers)


def wrong_turn(inp, out):
    _, _, _, _, _, _, mark = parse(inp)
    return build(inp, CW[far_dir(mark)])


def no_turn(inp, out):
    _, _, _, _, _, _, mark = parse(inp)
    return build(inp, far_dir(mark))


def half_turn(inp, out):
    _, _, _, _, _, _, mark = parse(inp)
    return build(inp, OPP[true_side(mark)])


def keep_marker(inp, out):
    _, _, _, _, _, _, mark = parse(inp)
    return build(inp, true_side(mark), keep_mark=True)


def translated_copy(inp, out):
    _, _, _, _, _, _, mark = parse(inp)
    return build(inp, true_side(mark), mode="translate")


def gap_one(inp, out):
    _, _, _, _, _, _, mark = parse(inp)
    return build(inp, true_side(mark), gap=1)


def overlap_edge(inp, out):
    _, _, _, _, _, _, mark = parse(inp)
    return build(inp, true_side(mark), gap=-1)


def marker_color_copy(inp, out):
    _, _, _, _, mc, _, mark = parse(inp)
    return build(inp, true_side(mark), copy_color=mc)


def translate_flip_other_axis(inp, out):
    _, _, _, _, _, _, mark = parse(inp)
    return build(inp, true_side(mark), mode="flip_other")


def both_sides(inp, out):
    h, w, bg, sc, mc, shape, mark = parse(inp)
    s = true_side(mark)
    return render(h, w, bg, [(sc, shape), (sc, reflect(shape, s)), (sc, reflect(shape, OPP[s]))])


def move_not_copy(inp, out):
    _, _, _, _, _, _, mark = parse(inp)
    return build(inp, true_side(mark), keep_orig=False)


def toward_marker(inp, out):
    h, w, bg, sc, mc, shape, mark = parse(inp)
    r0, r1, c0, c1 = bbox(shape)
    m0, m1, n0, n1 = bbox(mark)
    dr = (m0 + m1) - (r0 + r1)
    dc = (n0 + n1) - (c0 + c1)
    if abs(dr) >= abs(dc):
        side = "down" if dr > 0 else "up"
    else:
        side = "right" if dc > 0 else "left"
    return build(inp, side)


ALTERNATIVES = [
    ("quarter turn from the far direction goes the other way (clockwise instead of counterclockwise)", wrong_turn),
    ("copy goes to the marker's far direction itself, with no quarter turn", no_turn),
    ("copy goes to the side opposite the correct side (half turn)", half_turn),
    ("marker is left in the output instead of erased", keep_marker),
    ("copy is a plain translation of the shape, not a reflection", translated_copy),
    ("copy sits one cell beyond the edge (gap of one cell)", gap_one),
    ("copy is reflected across the edge row/column itself, overlapping the shape's edge line", overlap_edge),
    ("copy is painted in the marker's color", marker_color_copy),
    ("copy is translated and flipped along the axis parallel to the edge instead of reflected", translate_flip_other_axis),
    ("copies go to the correct side and the opposite side", both_sides),
    ("shape is moved to the reflected place, original erased", move_not_copy),
    ("copy goes to the side the marker lies on relative to the shape", toward_marker),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/9bebae7a.json"))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
