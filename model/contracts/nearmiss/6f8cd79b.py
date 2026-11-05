import json
from pathlib import Path


def _size(out):
    return len(out), len(out[0])


def _blank(h, w, v=0):
    return [[v] * w for _ in range(h)]


def recolor_border(inp, out):
    return [[1 if v == 8 else v for v in row] for row in out]


def fill_interior(inp, out):
    h, w = _size(out)
    return _blank(h, w, 8)


def top_bottom_only(inp, out):
    h, w = _size(out)
    g = _blank(h, w)
    for c in range(w):
        g[0][c] = 8
        g[h - 1][c] = 8
    return g


def left_right_only(inp, out):
    h, w = _size(out)
    g = _blank(h, w)
    for r in range(h):
        g[r][0] = 8
        g[r][w - 1] = 8
    return g


def top_left_only(inp, out):
    h, w = _size(out)
    g = _blank(h, w)
    for c in range(w):
        g[0][c] = 8
    for r in range(h):
        g[r][0] = 8
    return g


def inset_ring(inp, out):
    h, w = _size(out)
    g = _blank(h, w)
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            if r in (1, h - 2) or c in (1, w - 2):
                g[r][c] = 8
    return g


def crop_interior(inp, out):
    return [row[1:-1] for row in out[1:-1]]


def pad_with_border(inp, out):
    w = len(out[0])
    return [[8] * (w + 2)] + [[8] + list(row) + [8] for row in out] + [[8] * (w + 2)]


def no_corners(inp, out):
    h, w = _size(out)
    g = [list(row) for row in out]
    for r, c in ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)):
        g[r][c] = 0
    return g


def dashed_border(inp, out):
    h, w = _size(out)
    g = [list(row) for row in out]
    for r in range(h):
        for c in range(w):
            if out[r][c] == 8 and (r + c) % 2 == 1:
                g[r][c] = 0
    return g


def striped_interior(inp, out):
    h, w = _size(out)
    g = [list(row) for row in out]
    for r in range(1, h - 1):
        if r % 2 == 1:
            for c in range(1, w - 1):
                g[r][c] = 8
    return g


def unchanged(inp, out):
    return [list(row) for row in inp]


ALTERNATIVES = [
    ("border drawn in color 1 instead of 8", recolor_border),
    ("whole grid filled with the border color", fill_interior),
    ("only top and bottom rows get the border", top_bottom_only),
    ("only left and right columns get the border", left_right_only),
    ("only top row and left column get the border", top_left_only),
    ("border ring drawn one cell inside the edge", inset_ring),
    ("output cropped to the interior, border dropped", crop_interior),
    ("border added around the true output, growing it by 2 in each dimension", pad_with_border),
    ("border without its four corner cells", no_corners),
    ("border drawn as alternating cells", dashed_border),
    ("interior rows at odd offsets also filled with the border color", striped_interior),
    ("input returned unchanged", unchanged),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/6f8cd79b.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
