import json
from pathlib import Path

BG = 0


def _runs(flags):
    runs, start = [], None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        if not f and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(flags)))
    return runs


def _decode(inp):
    """Return (box, tiles, border, mask, palette) for the correct reading."""
    h, w = len(inp), len(inp[0])
    rows = [any(v != BG for v in r) for r in inp]
    cols = [any(inp[y][x] != BG for y in range(h)) for x in range(w)]
    ry, cx = _runs(rows), _runs(cols)
    y0, y1, x0, x1 = ry[0][0], ry[-1][1], cx[0][0], cx[-1][1]
    tiles = {}
    for i, (a, b) in enumerate(ry):
        for j, (c, d) in enumerate(cx):
            tiles[i, j] = [row[c:d] for row in inp[a:b]]
    sets = {k: {v for r in t for v in r} - {BG} for k, t in tiles.items()}
    border = set.intersection(*sets.values()).pop()
    plain = [k for k in tiles if sets[k] == {border}]
    key = [k for k in tiles if sets[k] != {border}][0]
    mask = [[v != BG for v in r] for r in tiles[plain[0]]]
    th, tw = len(mask), len(mask[0])
    holes = [(y, x) for y in range(th) for x in range(tw)
             if any(tiles[k][y][x] == BG for k in plain)]
    hy = sorted({y for y, _ in holes})
    hx = sorted({x for _, x in holes})
    kt = tiles[key]
    palette = [[kt[y][x] for x in hx] for y in hy]
    return (y0, y1, x0, x1), border, mask, palette


def _build(mask, palette, border, gap=1, hole_color=None, body_color=None,
           gap_color=None, empty_color=None):
    th, tw = len(mask), len(mask[0])
    nr, nc = len(palette), len(palette[0])
    H = nr * th + (nr - 1) * gap
    W = nc * tw + (nc - 1) * gap
    gc = border if gap_color is None else gap_color
    g = [[gc] * W for _ in range(H)]
    for i in range(nr):
        for j in range(nc):
            col = palette[i][j]
            for y in range(th):
                for x in range(tw):
                    if empty_color is not None and col == border:
                        v = empty_color
                    elif mask[y][x]:
                        v = col if body_color is None else body_color
                    else:
                        v = border if hole_color is None else (
                            col if hole_color == "key" else hole_color)
                    g[i * (th + gap) + y][j * (tw + gap) + x] = v
    return g


def _ref(inp):
    _, border, mask, palette = _decode(inp)
    return border, mask, palette


def hflip_palette(inp, out):
    b, m, p = _ref(inp)
    return _build(m, [r[::-1] for r in p], b)


def roll_rows(inp, out):
    b, m, p = _ref(inp)
    return _build(m, p[-1:] + p[:-1], b)


def transpose_palette(inp, out):
    b, m, p = _ref(inp)
    return _build(m, [list(r) for r in zip(*p)], b)


def roll_palette(inp, out):
    b, m, p = _ref(inp)
    flat = [v for r in p for v in r]
    flat = flat[-1:] + flat[:-1]
    n = len(p[0])
    return _build(m, [flat[i:i + n] for i in range(0, len(flat), n)], b)


def holes_filled(inp, out):
    b, m, p = _ref(inp)
    return _build(m, p, b, hole_color="key")


def inverted_tile(inp, out):
    b, m, p = _ref(inp)
    return _build(m, p, b, hole_color="key", body_color=b)


def gap_bg(inp, out):
    b, m, p = _ref(inp)
    return _build(m, p, b, gap_color=BG)


def no_gap(inp, out):
    b, m, p = _ref(inp)
    return _build(m, p, b, gap=0)


def border_as_bg(inp, out):
    return [[BG if v == _ref(inp)[0] else v for v in r] for r in out]


def empty_tiles_bg(inp, out):
    b, m, p = _ref(inp)
    return _build(m, p, b, empty_color=BG)


def crop_input(inp, out):
    (y0, y1, x0, x1), b, _, _ = _decode(inp)
    return [[b if v == BG else v for v in r[x0:x1]] for r in inp[y0:y1]]


def drop_last_palette_row(inp, out):
    b, m, p = _ref(inp)
    if len(p) < 2:
        return None
    return _build(m, p[:-1], b)


ALTERNATIVES = [
    ("palette mirrored left-right", hflip_palette),
    ("palette rows shifted down by one, last row moved to the top", roll_rows),
    ("palette transposed (rows and columns swapped)", transpose_palette),
    ("palette colors shifted by one tile in reading order", roll_palette),
    ("holes painted with the tile color as well as the body", holes_filled),
    ("tile inverted: holes take the key color, body takes the border color", inverted_tile),
    ("gaps between tiles drawn in background 0 instead of the border color", gap_bg),
    ("tiles placed with no gap between them", no_gap),
    ("border color treated as background 0 everywhere", border_as_bg),
    ("tiles whose key is the border color left as background 0", empty_tiles_bg),
    ("input bounding box cropped and its background recolored, no rebuild", crop_input),
    ("last palette row dropped", drop_last_palette_row),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and all(len(r) == len(g[0]) and len(r) > 0 for r in g)
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/1be83260.json").read_text())
    pairs = task["train"]
    b, m, p = _ref(pairs[0]["input"])
    for pr in pairs:
        bb, mm, pp = _ref(pr["input"])
        assert _build(mm, pp, bb) == pr["output"], "reference mismatch"
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in pairs:
            g = fn(pr["input"], pr["output"])
            if g is not None and _valid(g) and g != pr["output"]:
                n += 1
        print(n, desc)
