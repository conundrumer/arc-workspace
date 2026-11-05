import json
from collections import Counter
from pathlib import Path

FILL = 9


def split(inp):
    h = len(inp) // 2
    return [r[:] for r in inp[:h]], [r[:] for r in inp[h:]]


def blank(h, w, c=FILL):
    return [[c] * w for _ in range(h)]


def paste(g, t, r0, c0):
    for i, row in enumerate(t):
        for j, v in enumerate(row):
            g[r0 + i][c0 + j] = v


def place(inp, top_pos, bot_pos, gap_r=1, gap_c=1, fill=FILL, flip=False):
    """top_pos/bot_pos: (vert, horiz) in 'ul','ur','ll','lr' style corner strings."""
    a, b = split(inp)
    th, tw = len(a), len(a[0])
    if flip:
        a = [r[::-1] for r in a]
        b = [r[::-1] for r in b]
    g = blank(2 * th + gap_r, tw + gap_c, fill)

    def at(corner):
        return (0 if corner[0] == "u" else th + gap_r, 0 if corner[1] == "l" else gap_c)

    paste(g, a, *at(top_pos))
    paste(g, b, *at(bot_pos))
    return g


def swapped(inp, out):
    return place(inp, "lr", "ul")


def anti_diagonal(inp, out):
    return place(inp, "ur", "ll")


def filler_zero(inp, out):
    return place(inp, "ul", "lr", fill=0)


def filler_most_common(inp, out):
    c = Counter(v for r in inp for v in r).most_common(1)[0][0]
    return place(inp, "ul", "lr", fill=c)


def grow_two(inp, out):
    return place(inp, "ul", "lr", gap_r=2, gap_c=2)


def grow_rows_only(inp, out):
    return place(inp, "ul", "lr", gap_r=1, gap_c=0)


def grow_cols_only(inp, out):
    return place(inp, "ul", "lr", gap_r=0, gap_c=1)


def mirrored_tiles(inp, out):
    return place(inp, "ul", "lr", flip=True)


def bottom_tile_missing(inp, out):
    g = [r[:] for r in out]
    th, tw = len(inp) // 2, len(inp[0])
    for i in range(th):
        for j in range(tw):
            g[len(g) - th + i][len(g[0]) - tw + j] = FILL
    return g


def unchanged(inp, out):
    return [r[:] for r in inp]


def extra_filler_row(inp, out):
    return [r[:] for r in out] + [[FILL] * len(out[0])]


def top_tile_only_in_corner(inp, out):
    a, _ = split(inp)
    g = blank(len(out), len(out[0]))
    paste(g, a, 0, 0)
    return g


ALTERNATIVES = [
    ("tiles seated at swapped corners (top tile bottom-right, bottom tile top-left)", swapped),
    ("tiles seated at the anti-diagonal corners (top tile top-right, bottom tile bottom-left)", anti_diagonal),
    ("filler color is 0 instead of the new color", filler_zero),
    ("filler color is the most common input color", filler_most_common),
    ("frame grows by two in each dimension instead of one", grow_two),
    ("frame grows only along the row axis; bottom tile not shifted sideways", grow_rows_only),
    ("frame grows only along the column axis; no filler row between tiles", grow_cols_only),
    ("each tile is mirrored left-right when seated", mirrored_tiles),
    ("bottom tile omitted; its corner left as filler", bottom_tile_missing),
    ("input returned unchanged (tiles not reseated)", unchanged),
    ("output has one extra filler row at the bottom", extra_filler_row),
    ("only the top tile seated; bottom tile dropped", top_tile_only_in_corner),
]


def valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/8618d23e.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(n, fn.__name__, "-", desc)
