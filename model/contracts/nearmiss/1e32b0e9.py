import json
from collections import Counter
from pathlib import Path


def _structure(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for row in inp for v in row).most_common(1)[0][0]
    div = None
    for row in inp:
        if len(set(row)) == 1 and row[0] != bg:
            div = row[0]
            break
    drows = {r for r in range(h) if all(v == div for v in inp[r])}
    dcols = {c for c in range(w) if all(inp[r][c] == div for r in range(h))}

    def segs(n, d):
        out, cur = [], []
        for i in range(n):
            if i in d:
                if cur:
                    out.append(cur)
                cur = []
            else:
                cur.append(i)
        if cur:
            out.append(cur)
        return out

    rs, cs = segs(h, drows), segs(w, dcols)
    tiles = [(r, c) for r in rs for c in cs]  # (row list, col list)
    return bg, div, tiles


def _local(inp, tile, bg):
    rows, cols = tile
    return {(i, j) for i, r in enumerate(rows) for j, c in enumerate(cols)
            if inp[r][c] != bg}


def _true_stamp(inp, out):
    bg, div, tiles = _structure(inp)
    s = set()
    for t in tiles:
        s |= _local(out, t, bg)
    return s


def _render(inp, stamp, fill, overwrite=False, only=None):
    """Paint stamp cells with fill in every tile (tiles filtered by `only`)."""
    bg, div, tiles = _structure(inp)
    g = [row[:] for row in inp]
    for t in tiles:
        if only is not None and not only(inp, t, bg):
            continue
        rows, cols = t
        for (i, j) in stamp:
            if 0 <= i < len(rows) and 0 <= j < len(cols):
                r, c = rows[i], cols[j]
                if overwrite or g[r][c] == bg:
                    g[r][c] = fill
    return g


def _shape_color(inp):
    bg, div, tiles = _structure(inp)
    cnt = Counter(inp[r][c] for t in tiles for r in t[0] for c in t[1]
                  if inp[r][c] != bg)
    return cnt.most_common(1)[0][0]


def _shapes(inp):
    bg, div, tiles = _structure(inp)
    return [_local(inp, t, bg) for t in tiles if _local(inp, t, bg)]


def partial_untouched(inp, out):
    # fill only tiles that hold no shape; tiles with a partial shape stay as input
    st = _true_stamp(inp, out)
    bg, div, _ = _structure(inp)
    return _render(inp, st, div, only=lambda i, t, b: not _local(i, t, b))


def empty_untouched(inp, out):
    # complete only tiles that already hold a partial shape; empty tiles stay empty
    st = _true_stamp(inp, out)
    bg, div, _ = _structure(inp)
    return _render(inp, st, div, only=lambda i, t, b: bool(_local(i, t, b)))


def shape_color_fill(inp, out):
    st = _true_stamp(inp, out)
    return _render(inp, st, _shape_color(inp))


def overwrite_shape_cells(inp, out):
    st = _true_stamp(inp, out)
    bg, div, _ = _structure(inp)
    return _render(inp, st, div, overwrite=True)


def smallest_shape_stamp(inp, out):
    bg, div, _ = _structure(inp)
    sh = _shapes(inp)
    st = min(sh, key=len)
    return _render(inp, st, div)


def common_cells_stamp(inp, out):
    bg, div, _ = _structure(inp)
    sh = _shapes(inp)
    st = set(sh[0])
    for s in sh[1:]:
        st &= s
    return _render(inp, st, div)


def shift_down(inp, out):
    st = {(i + 1, j) for i, j in _true_stamp(inp, out)}
    bg, div, _ = _structure(inp)
    return _render(inp, st, div)


def shift_diag(inp, out):
    st = {(i + 1, j + 1) for i, j in _true_stamp(inp, out)}
    bg, div, _ = _structure(inp)
    return _render(inp, st, div)


def inverse_region(inp, out):
    # fill the tile cells outside the stamp instead of the stamp
    st = _true_stamp(inp, out)
    bg, div, tiles = _structure(inp)
    n, m = len(tiles[0][0]), len(tiles[0][1])
    inv = {(i, j) for i in range(n) for j in range(m)} - st
    return _render(inp, inv, div)


def recolor_only(inp, out):
    # recolor existing shape cells to the divider color; no completion
    bg, div, tiles = _structure(inp)
    g = [row[:] for row in inp]
    for t in tiles:
        for r in t[0]:
            for c in t[1]:
                if g[r][c] != bg:
                    g[r][c] = div
    return g


ALTERNATIVES = [
    ("fill only tiles with no shape; partial tiles left as in input", partial_untouched),
    ("complete only tiles that already hold a shape; empty tiles stay empty", empty_untouched),
    ("fill the missing stamp cells with the shape color instead of the divider color", shape_color_fill),
    ("repaint the existing shape cells in divider color too, overwriting them", overwrite_shape_cells),
    ("take the smallest shape as the stamp instead of the largest", smallest_shape_stamp),
    ("take only the cells common to all tile shapes as the stamp", common_cells_stamp),
    ("stamp placed one row too low in each tile", shift_down),
    ("stamp placed one row and one column off in each tile", shift_diag),
    ("fill the tile cells outside the stamp instead of the stamp", inverse_region),
    ("only recolor existing shape cells to the divider color, no completion", recolor_only),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/1e32b0e9.json').read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = sum(1 for p in pairs
                if (g := f(p["input"], p["output"])) is not None and _valid(g, p["output"]))
        print(n, desc)
