import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(c for r in g for c in r).most_common(1)[0][0]


def _box(out):
    """Bounding box (r0, r1, c0, c1) of the non-background cells of out."""
    bg = _bg(out)
    cells = [(i, j) for i, r in enumerate(out) for j, c in enumerate(r) if c != bg]
    return (min(i for i, _ in cells), max(i for i, _ in cells),
            min(j for _, j in cells), max(j for _, j in cells))


def _colors(out):
    """(background, fill color, diagonal color) of the true output."""
    bg = _bg(out)
    r0, r1, c0, c1 = _box(out)
    cnt = Counter(out[i][j] for i in range(r0, r1 + 1) for j in range(c0, c1 + 1))
    fill = cnt.most_common(1)[0][0]
    diag = [c for c in cnt if c != fill][0]
    return bg, fill, diag


def _blank(out):
    bg = _bg(out)
    return [[bg] * len(out[0]) for _ in out]


def _draw(out, r0, r1, c0, c1, fill, diag, corners=("bl", "br"), box=True):
    """Box with fill color; diagonals leave the listed corners and meet in the middle."""
    g = _blank(out)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            if 0 <= i < len(g) and 0 <= j < len(g[0]):
                g[i][j] = fill if box else g[i][j]
    for i in range(h):
        for j in range(w):
            on = False
            for k in corners:
                di = i if k[0] == "t" else h - 1 - i
                dj = j if k[1] == "l" else w - 1 - j
                if di == dj:
                    on = True
            if on and 0 <= r0 + i < len(g) and 0 <= c0 + j < len(g[0]):
                g[r0 + i][c0 + j] = diag
    return g


def _hflip(g):
    return [r[::-1] for r in g]


def _vflip(g):
    return g[::-1]


def swap_colors(inp, out):
    bg, fill, diag = _colors(out)
    return [[diag if c == fill else fill if c == diag else c for c in r] for r in out]


def anchor_bottom_right(inp, out):
    return _hflip(out)


def anchor_top_left(inp, out):
    return _vflip(out)


def transposed_box(inp, out):
    r0, r1, c0, c1 = _box(out)
    bg, fill, diag = _colors(out)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    H, W = len(out), len(out[0])
    if h == w:
        return None
    # swapped extents, still anchored at bottom-left
    return _draw(out, H - w, H - 1, 0, h - 1, fill, diag)


def taller_by_one(inp, out):
    r0, r1, c0, c1 = _box(out)
    bg, fill, diag = _colors(out)
    return _draw(out, r0 - 1, r1, c0, c1, fill, diag)


def narrower_by_one(inp, out):
    r0, r1, c0, c1 = _box(out)
    bg, fill, diag = _colors(out)
    return _draw(out, r0, r1, c0, c1 - 1, fill, diag)


def one_diagonal(inp, out):
    r0, r1, c0, c1 = _box(out)
    bg, fill, diag = _colors(out)
    return _draw(out, r0, r1, c0, c1, fill, diag, corners=("bl",))


def no_diagonals(inp, out):
    r0, r1, c0, c1 = _box(out)
    bg, fill, diag = _colors(out)
    return _draw(out, r0, r1, c0, c1, fill, diag, corners=())


def diagonals_only(inp, out):
    r0, r1, c0, c1 = _box(out)
    bg, fill, diag = _colors(out)
    return _draw(out, r0, r1, c0, c1, fill, diag, box=False)


def diagonals_from_top(inp, out):
    r0, r1, c0, c1 = _box(out)
    bg, fill, diag = _colors(out)
    return _draw(out, r0, r1, c0, c1, fill, diag, corners=("tl", "tr"))


def crop_to_box(inp, out):
    r0, r1, c0, c1 = _box(out)
    return [r[c0:c1 + 1] for r in out[r0:r1 + 1]]


def square_box(inp, out):
    r0, r1, c0, c1 = _box(out)
    bg, fill, diag = _colors(out)
    H = len(out)
    n = c1 - c0 + 1
    if n > H:
        return None
    return _draw(out, H - n, H - 1, c0, c1, fill, diag)


def box_in_top_right(inp, out):
    return _vflip(_hflip(out))


ALTERNATIVES = [
    ("fill and diagonal colors exchanged", swap_colors),
    ("box anchored at the bottom-right corner instead of bottom-left", anchor_bottom_right),
    ("box anchored at the top-left corner instead of bottom-left", anchor_top_left),
    ("box width and height swapped", transposed_box),
    ("box one row too tall", taller_by_one),
    ("box one column too narrow", narrower_by_one),
    ("only one diagonal drawn, from the bottom-left corner", one_diagonal),
    ("box filled with no diagonals", no_diagonals),
    ("only the diagonals drawn, box interior left as background", diagonals_only),
    ("diagonals start at the top corners of the box instead of the bottom", diagonals_from_top),
    ("output cropped to the box instead of the full canvas", crop_to_box),
    ("box made square with the long side as its height", square_box),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9
                    for r in g for c in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/878187ab.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
