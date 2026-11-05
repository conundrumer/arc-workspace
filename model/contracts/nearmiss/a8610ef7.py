import json
from pathlib import Path


def _size(g):
    return len(g), len(g[0])


def _recolor(inp, f, matched=2, unmatched=5, bg=0, src=8):
    """Recolor each non-bg cell by whether its image under f (row, col -> row, col or None) is non-bg."""
    h, w = _size(inp)
    res = [row[:] for row in inp]
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg:
                continue
            q = f(r, c, h, w)
            on = q is not None and 0 <= q[0] < h and 0 <= q[1] < w and inp[q[0]][q[1]] != bg
            res[r][c] = matched if on else unmatched
    return res


def lr_mirror(inp, out):
    return _recolor(inp, lambda r, c, h, w: (r, w - 1 - c))


def transpose_mirror(inp, out):
    return _recolor(inp, lambda r, c, h, w: (c, r))


def rot180_mirror(inp, out):
    return _recolor(inp, lambda r, c, h, w: (h - 1 - r, w - 1 - c))


def anti_transpose_mirror(inp, out):
    return _recolor(inp, lambda r, c, h, w: (w - 1 - c, h - 1 - r))


def off_by_one_mirror(inp, out):
    # flips about a point one row off: row r pairs with row h-2-r
    return _recolor(inp, lambda r, c, h, w: (h - 2 - r, c))


def swapped_colors(inp, out):
    sw = {2: 5, 5: 2}
    return [[sw.get(v, v) for v in row] for row in out]


def unmatched_left_unrecolored(inp, out):
    return [[8 if v == 5 else v for v in row] for row in out]


def matched_left_unrecolored(inp, out):
    return [[8 if v == 2 else v for v in row] for row in out]


def single_color(inp, out):
    return [[2 if v == 5 else v for v in row] for row in out]


def top_half_only(inp, out):
    h = len(out)
    return [[(inp[r][c] if r >= h // 2 else out[r][c]) for c in range(len(out[0]))] for r in range(h)]


def background_also_marked(inp, out):
    # bg cells whose mirror is non-bg also get a color
    h, w = _size(inp)
    res = [row[:] for row in out]
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 and inp[h - 1 - r][c] != 0:
                res[r][c] = 5
    return res


def neighbor_below(inp, out):
    # partner is the cell directly below (adjacency) instead of the flipped cell
    return _recolor(inp, lambda r, c, h, w: (r + 1, c))


ALTERNATIVES = [
    ("mirror partner is the left-right flip instead of up-down", lr_mirror),
    ("mirror partner is the transpose", transpose_mirror),
    ("mirror partner is the 180-degree rotation", rot180_mirror),
    ("mirror partner is the anti-diagonal transpose", anti_transpose_mirror),
    ("up-down flip about a point one row off", off_by_one_mirror),
    ("colors swapped: matched cells 5, unmatched cells 2", swapped_colors),
    ("unmatched cells are left as 8, only matched cells recolored", unmatched_left_unrecolored),
    ("matched cells are left as 8, only unmatched cells recolored", matched_left_unrecolored),
    ("matched condition ignored: all non-bg cells become 2", single_color),
    ("rule applied only to the top half; bottom half left as input", top_half_only),
    ("background cells facing a non-bg cell are also marked 5", background_also_marked),
    ("partner is the adjacent cell below, not the flipped cell", neighbor_below),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/a8610ef7.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
