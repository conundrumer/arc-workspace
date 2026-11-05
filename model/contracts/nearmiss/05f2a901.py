import json
from collections import Counter
from pathlib import Path

DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


def _info(inp, out):
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    cols = [c for c in cnt if c != bg]
    anchor = min(cols, key=lambda c: cnt[c])
    mover = [c for c in cols if c != anchor][0]
    cells = lambda c: [(y, x) for y, r in enumerate(inp) for x, v in enumerate(r) if v == c]
    return bg, anchor, mover, cells(mover), cells(anchor)


def _sim(inp, bg, anchor, mover, mc, ac, d, k, trail=False, anchor_moves=False,
         mover_over_anchor=True, mover_color=None, vacate=None, flip=False):
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    if trail:
        for y, x in mc:
            g[y][x] = mover
    elif vacate is not None:
        for y, x in mc:
            g[y][x] = vacate
    dy, dx = DIRS[d]
    mcols = mover if mover_color is None else mover_color

    def put(cs, col):
        for y, x in cs:
            if 0 <= y < h and 0 <= x < w:
                g[y][x] = col

    if anchor_moves:
        put([(y - dy * k, x - dx * k) for y, x in ac], anchor)
        put(mc, mcols)
        return g
    put(ac, anchor)
    cs = mc
    if flip:
        xs = [x for _, x in mc]
        lo, hi = min(xs), max(xs)
        cs = [(y, lo + hi - x) for y, x in mc]
    put([(y + dy * k, x + dx * k) for y, x in cs], mcols)
    return g


def _truth(inp, out):
    bg, anchor, mover, mc, ac = _info(inp, out)
    for d in DIRS:
        for k in range(0, 40):
            if _sim(inp, bg, anchor, mover, mc, ac, d, k) == out:
                return bg, anchor, mover, mc, ac, d, k
    return None


def _edge_k(inp, mc, d):
    h, w = len(inp), len(inp[0])
    dy, dx = DIRS[d]
    k = 0
    while all(0 <= y + dy * (k + 1) < h and 0 <= x + dx * (k + 1) < w for y, x in mc):
        k += 1
    return k


def _with(inp, out, **kw):
    t = _truth(inp, out)
    if t is None:
        return None
    bg, anchor, mover, mc, ac, d, k = t
    k2 = kw.pop("k", k)
    d2 = kw.pop("d", d)
    return _sim(inp, bg, anchor, mover, mc, ac, d2, k2, **kw)


def stop_short(inp, out):
    t = _truth(inp, out)
    return _with(inp, out, k=max(t[6] - 1, 0))


def overshoot(inp, out):
    t = _truth(inp, out)
    return _with(inp, out, k=t[6] + 1)


def half_way(inp, out):
    t = _truth(inp, out)
    return _with(inp, out, k=t[6] // 2)


def pass_through(inp, out):
    t = _truth(inp, out)
    return _with(inp, out, k=_edge_k(inp, t[3], t[5]))


def away_to_edge(inp, out):
    t = _truth(inp, out)
    opp = {"up": "down", "down": "up", "left": "right", "right": "left"}[t[5]]
    return _with(inp, out, d=opp, k=_edge_k(inp, t[3], opp))


def keep_original(inp, out):
    return _with(inp, out, trail=True)


def anchor_moves(inp, out):
    return _with(inp, out, anchor_moves=True)


def sideways_offset(inp, out):
    t = _truth(inp, out)
    bg, anchor, mover, mc, ac, d, k = t
    dy, dx = DIRS[d]
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    for y, x in ac:
        g[y][x] = anchor
    for y, x in mc:
        ny, nx = y + dy * k + dx, x + dx * k + dy
        if 0 <= ny < h and 0 <= nx < w:
            g[ny][nx] = mover
    return g


def fixed_down(inp, out):
    t = _truth(inp, out)
    bg, anchor, mover, mc, ac, d, k = t
    h = len(inp)
    k2 = 0
    cols = {x for _, x in mc}
    while True:
        nxt = [(y + k2 + 1, x) for y, x in mc]
        if any(y >= h for y, _ in nxt) or any((y, x) in set(ac) for y, x in nxt):
            break
        k2 += 1
    return _sim(inp, bg, anchor, mover, mc, ac, "down", k2)


def mirror_on_landing(inp, out):
    return _with(inp, out, flip=True)


def recolor_to_anchor(inp, out):
    t = _truth(inp, out)
    return _with(inp, out, mover_color=t[1])


def vacated_filled_anchor(inp, out):
    t = _truth(inp, out)
    return _with(inp, out, vacate=t[1])


ALTERNATIVES = [
    ("mover stops one cell short of touching the anchor", stop_short),
    ("mover overshoots by one and overlaps the anchor", overshoot),
    ("mover travels only half the distance to the anchor", half_way),
    ("mover ignores the anchor and slides to the grid edge, drawn over the anchor", pass_through),
    ("mover moves away from the anchor to the opposite edge", away_to_edge),
    ("mover is copied, original cells are not cleared", keep_original),
    ("anchor moves toward the mover instead of the mover toward the anchor", anchor_moves),
    ("mover lands one cell off sideways from the true landing spot", sideways_offset),
    ("mover always falls downward until it hits the anchor or the edge", fixed_down),
    ("mover is mirrored left-right as it lands", mirror_on_landing),
    ("mover takes the anchor color after moving", recolor_to_anchor),
    ("cells the mover vacates are filled with the anchor color", vacated_filled_anchor),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/05f2a901.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
