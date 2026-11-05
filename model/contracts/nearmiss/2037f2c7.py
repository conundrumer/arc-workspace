import json
from pathlib import Path

MARK = 8


def comps(inp, conn=8):
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    if conn == 8:
        nb = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
    else:
        nb = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0 and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x))
                    for dy, dx in nb:
                        n = (y + dy, x + dx)
                        if 0 <= n[0] < h and 0 <= n[1] < w and inp[n[0]][n[1]] != 0 and n not in seen:
                            seen.add(n)
                            st.append(n)
                res.append(cells)
    res.sort(key=lambda cs: min(cs))
    return res


def shapes(inp, align="tl", conn=8, colors=False):
    """List of dicts rel-pos -> color (or 1), one per component."""
    out = []
    for cells in comps(inp, conn):
        r0 = min(y for y, x in cells)
        r1 = max(y for y, x in cells)
        c0 = min(x for y, x in cells)
        c1 = max(x for y, x in cells)
        out.append((r0, r1, c0, c1, cells))
    H = max(s[1] - s[0] + 1 for s in out)
    W = max(s[3] - s[2] + 1 for s in out)
    res = []
    for r0, r1, c0, c1, cells in out:
        h, w = r1 - r0 + 1, c1 - c0 + 1
        oy = 0 if align in ("tl", "tr") else H - h
        ox = 0 if align in ("tl", "bl") else W - w
        if align == "center":
            oy, ox = (H - h) // 2, (W - w) // 2
        d = {}
        for y, x in cells:
            d[(y - r0 + oy, x - c0 + ox)] = inp[y][x] if colors else 1
        res.append(d)
    return res, H, W


def render(cells, pad=0, H=None, W=None, mark=MARK, origin=None, invert=False):
    """Crop to the bbox of cells (plus pad), or to a given frame."""
    if origin is None:
        ys = [y for y, x in cells]
        xs = [x for y, x in cells]
        y0, y1, x0, x1 = min(ys) - pad, max(ys) + pad, min(xs) - pad, max(xs) + pad
    else:
        y0, x0 = 0, 0
        y1, x1 = H - 1, W - 1
    g = [[0] * (x1 - x0 + 1) for _ in range(y1 - y0 + 1)]
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            inside = (y, x) in cells
            if inside != invert:
                g[y - y0][x - x0] = mark
    return g


def sym_diff_cells(sh):
    keys = set().union(*[set(s) for s in sh])
    return {k for k in keys if any(k not in s for s in sh)}


def true_like(inp):
    sh, H, W = shapes(inp)
    return render(sym_diff_cells(sh))


def union_cells(inp):
    sh, H, W = shapes(inp)
    return render(set().union(*[set(s) for s in sh]))


def common_cells(inp):
    sh, H, W = shapes(inp)
    c = set(sh[0])
    for s in sh[1:]:
        c &= set(s)
    return render(c)


def wrong_mark_color(inp, out):
    return [[(1 if v else 0) for v in r] for r in out]


def inverted(inp, out):
    return [[(MARK if v == 0 else 0) for v in r] for r in out]


def full_frame(inp, out):
    sh, H, W = shapes(inp)
    return render(sym_diff_cells(sh), H=H, W=W, origin=(0, 0))


def padded(inp, out):
    sh, H, W = shapes(inp)
    return render(sym_diff_cells(sh), pad=1)


def vflip_align(inp, out):
    sh, H, W = shapes(inp)
    flipped = [sh[0]] + [{(H - 1 - y, x): v for (y, x), v in s.items()} for s in sh[1:]]
    return render(sym_diff_cells(flipped))


def shifted_align(inp, out):
    sh, H, W = shapes(inp)
    moved = [sh[0]] + [{(y, x + 1): v for (y, x), v in s.items()} for s in sh[1:]]
    return render(sym_diff_cells(moved))


def in_input_frame(inp, out):
    sh, H, W = shapes(inp)
    cs = comps(inp)
    cells = sym_diff_cells(sh)
    g = [[0] * len(inp[0]) for _ in inp]
    for comp in cs:
        r0 = min(y for y, x in comp)
        c0 = min(x for y, x in comp)
        for dy, dx in cells:
            if (r0 + dy, c0 + dx) not in set(comp) and 0 <= r0 + dy < len(inp) and 0 <= c0 + dx < len(inp[0]):
                g[r0 + dy][c0 + dx] = MARK
    return g


def intact_shape_crop(inp, out):
    sh, H, W = shapes(inp, colors=True)
    big = max(sh, key=len)
    return [[big.get((y, x), 0) for x in range(W)] for y in range(H)]


def dilated(inp, out):
    cells = {(y, x) for y, r in enumerate(out) for x, v in enumerate(r) if v}
    grown = set(cells)
    for y, x in cells:
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            grown.add((y + dy, x + dx))
    return render(grown)


def rows_only(inp, out):
    sh, H, W = shapes(inp)
    cells = sym_diff_cells(sh)
    ys = [y for y, x in cells]
    full = {(y, x) for y in range(min(ys), max(ys) + 1) for x in range(W)}
    g = render(full)
    for y in range(len(g)):
        for x in range(W):
            g[y][x] = MARK if (y + min(ys), x) in cells else 0
    return g


def largest_cluster(inp, out):
    cells = [[v for v in r] for r in out]
    cs = comps(cells)
    if len(cs) < 2:
        return None
    big = max(cs, key=len)
    keep = set(big)
    return [[v if (y, x) in keep else 0 for x, v in enumerate(r)] for y, r in enumerate(out)]


def four_conn_shapes(inp, out):
    sh, H, W = shapes(inp, conn=4)
    if len(sh) < 2:
        return None
    return render(sym_diff_cells(sh))


def drop_last_row(inp, out):
    return [list(r) for r in out[:-1]] if len(out) > 1 else None


def mirrored(inp, out):
    return [list(reversed(r)) for r in out]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def four_conn(inp, out):
    sh, H, W = shapes(inp, conn=4)
    if len(sh) < 2:
        return None
    return render(sym_diff_cells(sh))


ALTERNATIVES = [
    ("mark cells filled by any shape (union) instead of cells where shapes disagree", lambda i, o: union_cells(i)),
    ("mark cells filled by every shape (intersection) instead of disagreements", lambda i, o: common_cells(i)),
    ("right disagreement cells but marked with color 1 instead of the new color 8", wrong_mark_color),
    ("swap marked and background cells inside the disagreement box", inverted),
    ("crop to the full shape bounding box instead of the disagreement bounding box", full_frame),
    ("crop the disagreement box with one extra cell margin", padded),
    ("compare shapes with the second one flipped vertically", vflip_align),
    ("compare shapes with the second one offset one column", shifted_align),
    ("draw the marks at their places in the input grid instead of a cropped box", in_input_frame),
    ("output the intact shape's colored crop instead of marking the disagreement", intact_shape_crop),
    ("keep only the largest cluster of marked cells", largest_cluster),
    ("drop the last row of the correct output (off-by-one crop)", drop_last_row),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/2037f2c7.json"))
    pairs = task["train"]
    print("sanity: true-like reproduces output:",
          [true_like(p["input"]) == p["output"] for p in pairs])
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("   error", repr(e))
                g = None
            ok = (
                g is not None
                and len(g) > 0
                and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                and g != p["output"]
            )
            n += ok
        print(n, "/", len(pairs), desc)
