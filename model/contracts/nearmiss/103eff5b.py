"""Near-miss readings for ARC task 103eff5b.

Rule: a small multicolor key (a block layout) sits next to a large shape
made of one color. The key is turned 90 degrees clockwise, blown up to the
shape's bounding box, and each block of the shape takes that block's key
color. The key stays where it is.
"""
import json
from collections import Counter
from pathlib import Path


def _info(inp, out):
    h, w = len(inp), len(inp[0])
    cells = Counter(v for r in inp for v in r)
    bg = cells.most_common(1)[0][0]
    changed = Counter(inp[r][c] for r in range(h) for c in range(w) if inp[r][c] != out[r][c])
    sc = changed.most_common(1)[0][0]
    key = [(r, c) for r in range(h) for c in range(w) if inp[r][c] not in (bg, sc)]
    shp = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == sc]
    kr0, kr1 = min(r for r, _ in key), max(r for r, _ in key)
    kc0, kc1 = min(c for _, c in key), max(c for _, c in key)
    sr0, sr1 = min(r for r, _ in shp), max(r for r, _ in shp)
    sc0, sc1 = min(c for _, c in shp), max(c for _, c in shp)
    K = [[inp[r][c] if inp[r][c] not in (sc,) else bg for c in range(kc0, kc1 + 1)]
         for r in range(kr0, kr1 + 1)]
    return dict(h=h, w=w, bg=bg, sc=sc, key=key, shp=shp, kb=(kr0, kc0, kr1, kc1),
                sb=(sr0, sc0, sr1, sc1), K=K)


def _cw(G):
    h, w = len(G), len(G[0])
    return [[G[h - 1 - i][j] for i in range(h)] for j in range(w)]


def _ccw(G):
    return _cw(_cw(_cw(G)))


def _r180(G):
    return [row[::-1] for row in G[::-1]]


def _tr(G):
    return [list(r) for r in zip(*G)]


def _paint(inp, I, G):
    """Blow G up over the shape's box and recolor the shape cells by block."""
    g = [row[:] for row in inp]
    r0, c0, r1, c1 = I["sb"]
    gh, gw = len(G), len(G[0])
    bh = max(1, (r1 - r0 + 1) // gh)
    bw = max(1, (c1 - c0 + 1) // gw)
    for r, c in I["shp"]:
        bi = min((r - r0) // bh, gh - 1)
        bj = min((c - c0) // bw, gw - 1)
        g[r][c] = G[bi][bj]
    return g


def _true(inp, I):
    return _paint(inp, I, _cw(I["K"]))


def no_turn(inp, out):
    I = _info(inp, out)
    return _paint(inp, I, I["K"])


def turn_ccw(inp, out):
    I = _info(inp, out)
    return _paint(inp, I, _ccw(I["K"]))


def turn_180(inp, out):
    I = _info(inp, out)
    return _paint(inp, I, _r180(I["K"]))


def transpose(inp, out):
    I = _info(inp, out)
    return _paint(inp, I, _tr(I["K"]))


def key_consumed(inp, out):
    I = _info(inp, out)
    g = [row[:] for row in out]
    for r, c in I["key"]:
        g[r][c] = I["bg"]
    return g


def uniform_majority(inp, out):
    I = _info(inp, out)
    cnt = Counter(inp[r][c] for r, c in I["key"])
    col = cnt.most_common(1)[0][0]
    g = [row[:] for row in inp]
    for r, c in I["shp"]:
        g[r][c] = col
    return g


def reading_order(inp, out):
    """Key colors dealt to the shape's blocks in reading order, ignoring layout."""
    I = _info(inp, out)
    G = _cw(I["K"])
    gh, gw = len(G), len(G[0])
    cols = [v for row in I["K"] for v in row if v != I["bg"]]
    r0, c0, r1, c1 = I["sb"]
    bh, bw = (r1 - r0 + 1) // gh, (c1 - c0 + 1) // gw
    blocks = []
    for bi in range(gh):
        for bj in range(gw):
            if inp[r0 + bi * bh][c0 + bj * bw] == I["sc"]:
                blocks.append((bi, bj))
    if len(blocks) != len(cols):
        return None
    g = [row[:] for row in inp]
    for (bi, bj), col in zip(blocks, cols):
        for r in range(r0 + bi * bh, r0 + (bi + 1) * bh):
            for c in range(c0 + bj * bw, c0 + (bj + 1) * bw):
                g[r][c] = col
    return g


def top_half_only(inp, out):
    I = _info(inp, out)
    r0, _, r1, _ = I["sb"]
    mid = (r0 + r1 + 1) // 2
    g = [row[:] for row in out]
    for r, c in I["shp"]:
        if r >= mid:
            g[r][c] = I["sc"]
    return g


def box_one_short(inp, out):
    """Shape box taken one row too short: the bottom row stays shape-colored."""
    I = _info(inp, out)
    _, _, r1, _ = I["sb"]
    g = [row[:] for row in out]
    for r, c in I["shp"]:
        if r == r1:
            g[r][c] = I["sc"]
    return g


def shape_deleted(inp, out):
    I = _info(inp, out)
    g = [row[:] for row in inp]
    for r, c in I["shp"]:
        g[r][c] = I["bg"]
    return g


def unscaled_stamp(inp, out):
    """Turned key pasted 1:1 at the shape's corner; the shape is cleared."""
    I = _info(inp, out)
    g = [row[:] for row in inp]
    for r, c in I["shp"]:
        g[r][c] = I["bg"]
    G = _cw(I["K"])
    r0, c0, _, _ = I["sb"]
    for i, row in enumerate(G):
        for j, v in enumerate(row):
            if v != I["bg"] and r0 + i < I["h"] and c0 + j < I["w"]:
                g[r0 + i][c0 + j] = v
    return g


def key_turned_in_place(inp, out):
    """The turn is applied to the key itself; the shape is left alone."""
    I = _info(inp, out)
    g = [row[:] for row in inp]
    kr0, kc0, _, _ = I["kb"]
    for r, c in I["key"]:
        g[r][c] = I["bg"]
    for i, row in enumerate(_cw(I["K"])):
        for j, v in enumerate(row):
            if v != I["bg"] and kr0 + i < I["h"] and kc0 + j < I["w"]:
                g[kr0 + i][kc0 + j] = v
    return g


ALTERNATIVES = [
    ("key used without any turn", no_turn),
    ("key turned 90 degrees counterclockwise instead of clockwise", turn_ccw),
    ("key turned 180 degrees", turn_180),
    ("key mirrored across its diagonal (transposed) instead of turned", transpose),
    ("correct recolor but the key is erased afterwards", key_consumed),
    ("whole shape takes the key's most common color", uniform_majority),
    ("key colors dealt to shape blocks in reading order, layout ignored", reading_order),
    ("recolor applied only to the top half of the shape (bottom half left as shape color)", top_half_only),
    ("shape box one row short: bottom row of the shape left unrecolored", box_one_short),
    ("shape deleted, no recolor", shape_deleted),
    ("turned key pasted unscaled at the shape's corner, shape cleared", unscaled_stamp),
    ("turn applied to the key in place, shape left unchanged", key_turned_in_place),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/103eff5b.json"))
    pairs = task["train"]
    for p in pairs:
        I = _info(p["input"], p["output"])
        assert _true(p["input"], I) == p["output"], "helper does not reproduce the true output"
    print("task 103eff5b:", len(pairs), "train pairs;", len(ALTERNATIVES), "readings")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            ok = (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                  and g != p["output"])
            n += ok
        print(f"{n}/{len(pairs)}  {desc}")
