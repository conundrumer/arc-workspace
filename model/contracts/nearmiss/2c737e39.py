import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != bg and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                comp = []
                while st:
                    a, b = st.pop()
                    comp.append((a, b))
                    for da in (-1, 0, 1):
                        for db in (-1, 0, 1):
                            n = (a + da, b + db)
                            if 0 <= n[0] < h and 0 <= n[1] < w and n not in seen and inp[n[0]][n[1]] != bg:
                                seen.add(n)
                                st.append(n)
                comps.append(comp)
    shape = max(comps, key=len)
    mark_col = Counter(inp[r][c] for comp in comps for r, c in comp
                       if comp is not shape).most_common(1)[0][0]
    marker = [p for comp in comps if comp is not shape for p in comp if inp[p[0]][p[1]] == mark_col][0]
    anchor = [p for p in shape if inp[p[0]][p[1]] == mark_col][0]
    return bg, shape, mark_col, marker, anchor


def _copy(g):
    return [row[:] for row in g]


def _paint(grid, cells, bg_erase=None):
    # cells: list of (r, c, color); clipped to grid
    h, w = len(grid), len(grid[0])
    for r, c, v in cells:
        if 0 <= r < h and 0 <= c < w:
            grid[r][c] = v


def _stamp(inp, dr, dc, keep_mark=False, tf=None, erase_orig=False, only=None):
    bg, shape, mk, marker, anchor = _parse(inp)
    g = _copy(inp)
    if erase_orig:
        for r, c in shape:
            g[r][c] = bg
    cells = []
    for r, c in shape:
        v = inp[r][c]
        rr, cc = r - anchor[0], c - anchor[1]
        if tf:
            rr, cc = tf(rr, cc)
        if only is not None and not only(v):
            continue
        cells.append((marker[0] + rr + dr, marker[1] + cc + dc, v))
    _paint(g, cells)
    if not keep_mark:
        r, c = marker[0] + dr, marker[1] + dc
        if 0 <= r < len(g) and 0 <= c < len(g[0]) and (dr, dc) == (0, 0):
            g[r][c] = bg
    return g


def keep_marker(inp, out):
    return _stamp(inp, 0, 0, keep_mark=True)


def anchor_topleft(inp, out):
    bg, shape, mk, marker, anchor = _parse(inp)
    r0 = min(r for r, c in shape)
    c0 = min(c for r, c in shape)
    g = _copy(inp)
    cells = [(marker[0] + r - r0, marker[1] + c - c0, inp[r][c]) for r, c in shape if (r, c) != anchor]
    g[marker[0]][marker[1]] = bg
    _paint(g, cells)
    return g


def anchor_bbox_center(inp, out):
    bg, shape, mk, marker, anchor = _parse(inp)
    rs = [r for r, c in shape]
    cs = [c for r, c in shape]
    cr, cc = (min(rs) + max(rs)) // 2, (min(cs) + max(cs)) // 2
    g = _copy(inp)
    g[marker[0]][marker[1]] = bg
    _paint(g, [(marker[0] + r - cr, marker[1] + c - cc, inp[r][c]) for r, c in shape if (r, c) != anchor])
    return g


def mirrored(inp, out):
    return _stamp(inp, 0, 0, tf=lambda r, c: (r, -c))


def flipped_vertical(inp, out):
    return _stamp(inp, 0, 0, tf=lambda r, c: (-r, c))


def rotated_180(inp, out):
    return _stamp(inp, 0, 0, tf=lambda r, c: (-r, -c))


def move_not_copy(inp, out):
    bg, shape, mk, marker, anchor = _parse(inp)
    g = _copy(inp)
    for r, c in shape:
        g[r][c] = bg
    g[marker[0]][marker[1]] = bg
    _paint(g, [(marker[0] + r - anchor[0], marker[1] + c - anchor[1], inp[r][c]) for r, c in shape if (r, c) != anchor])
    return g


def off_by_one_row(inp, out):
    bg, shape, mk, marker, anchor = _parse(inp)
    g = _copy(inp)
    g[marker[0]][marker[1]] = bg
    _paint(g, [(marker[0] + 1 + r - anchor[0], marker[1] + c - anchor[1], inp[r][c]) for r, c in shape if (r, c) != anchor])
    return g


def opposite_side(inp, out):
    bg, shape, mk, marker, anchor = _parse(inp)
    dr, dc = marker[0] - anchor[0], marker[1] - anchor[1]
    g = _copy(inp)
    g[marker[0]][marker[1]] = bg
    _paint(g, [(r - dr, c - dc, inp[r][c]) for r, c in shape if (r, c) != anchor])
    return g


def erase_all_marks(inp, out):
    # the marker color is also erased from the original shape
    bg, shape, mk, marker, anchor = _parse(inp)
    g = _copy(out)
    g[anchor[0]][anchor[1]] = bg
    return g


def skip_majority_color(inp, out):
    bg, shape, mk, marker, anchor = _parse(inp)
    cols = Counter(inp[r][c] for r, c in shape if (r, c) != anchor)
    top = cols.most_common(1)[0][0]
    return _stamp(inp, 0, 0, only=lambda v: v != top)


def drop_last_row(inp, out):
    # copy lacks the shape's bottom row
    bg, shape, mk, marker, anchor = _parse(inp)
    rmax = max(r for r, c in shape)
    g = _copy(inp)
    g[marker[0]][marker[1]] = bg
    _paint(g, [(marker[0] + r - anchor[0], marker[1] + c - anchor[1], inp[r][c])
               for r, c in shape if (r, c) != anchor and r != rmax])
    return g


def copy_keeps_marker_color_orig_loses(inp, out):
    bg, shape, mk, marker, anchor = _parse(inp)
    g = _copy(out)
    g[marker[0]][marker[1]] = mk
    g[anchor[0]][anchor[1]] = bg
    return g


ALTERNATIVES = [
    ("copy keeps the marker color in the pasted anchor cell", keep_marker),
    ("copy aligned by the shape's top-left corner to the marker", anchor_topleft),
    ("copy aligned by the shape's bounding-box center to the marker", anchor_bbox_center),
    ("copy is mirrored left-right around the anchor", mirrored),
    ("copy is flipped top-bottom around the anchor", flipped_vertical),
    ("copy is rotated 180 degrees around the anchor", rotated_180),
    ("shape is moved to the marker, original erased", move_not_copy),
    ("copy placed one row too low", off_by_one_row),
    ("copy placed on the opposite side of the original", opposite_side),
    ("marker color also erased from the original shape", erase_all_marks),
    ("copy omits the shape's most common color", skip_majority_color),
    ("copy omits the shape's bottom row", drop_last_row),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/2c737e39.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, e)
                g = None
            n += _valid(g, p["output"])
        print(n, desc)
