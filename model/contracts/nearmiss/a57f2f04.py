"""Near-miss readings for ARC task a57f2f04.

Rule: each panel (a solid rectangle of one blank color on a field) holds mark
cells in one corner. The bounding box of the marks is a tile. The panel is
filled with copies of the tile, laid on the tile's own grid.
"""
import json
from collections import Counter
from pathlib import Path


def _copy(g):
    return [row[:] for row in g]


def _info(inp):
    """Return field, blank, and panels: (cells, bbox, tile bbox, mark color)."""
    h, w = len(inp), len(inp[0])
    cnt = Counter(c for row in inp for c in row)
    field = cnt.most_common(1)[0][0]
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != field and (r, c) not in seen:
                st, comp = [(r, c)], []
                seen.add((r, c))
                while st:
                    y, x = st.pop()
                    comp.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != field and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                comps.append(comp)
    blank = Counter(inp[y][x] for comp in comps for y, x in comp).most_common(1)[0][0]
    panels = []
    for comp in comps:
        ys = [y for y, _ in comp]
        xs = [x for _, x in comp]
        box = (min(ys), min(xs), max(ys), max(xs))
        marks = [(y, x) for y, x in comp if inp[y][x] != blank]
        mcol = inp[marks[0][0]][marks[0][1]]
        tile = (min(y for y, _ in marks), min(x for _, x in marks),
                max(y for y, _ in marks), max(x for _, x in marks))
        panels.append({"box": box, "tile": tile, "mark": mcol})
    return field, blank, panels


def _tile_of(inp, p):
    t0, l0, t1, l1 = p["tile"]
    return [row[l0:l1 + 1] for row in inp[t0:t1 + 1]]


def _render(inp, tile_fn=None, tile_box_fn=None, extent_fn=None, phase_fn=None, panel_filter=None):
    field, blank, panels = _info(inp)
    res = _copy(inp)
    H, W = len(inp), len(inp[0])
    for i, p in enumerate(panels):
        if panel_filter and not panel_filter(i, p, panels):
            continue
        tb = tile_box_fn(inp, p) if tile_box_fn else p["tile"]
        t0, l0, t1, l1 = tb
        tile = [row[l0:l1 + 1] for row in inp[t0:t1 + 1]]
        if tile_fn:
            tile = tile_fn(tile, blank, p, field)
        th, tw = len(tile), len(tile[0])
        pr, pc = phase_fn(p) if phase_fn else (t0, l0)
        y0, x0, y1, x1 = extent_fn(p, H, W) if extent_fn else p["box"]
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                res[y][x] = tile[(y - pr) % th][(x - pc) % tw]
    return res


def _valid(g, out):
    return (g != out and g and all(len(r) == len(g[0]) for r in g)
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


def _wrap(f):
    def inner(inp, out):
        try:
            g = f(inp, out)
        except Exception:
            return None
        if g is None or g == out:
            return None
        return g
    return inner


# 1. Alternate copies are mirrored instead of plain repeats.
def mirrored_copies(inp, out):
    field, blank, panels = _info(inp)
    res = _copy(inp)
    for p in panels:
        t0, l0, t1, l1 = p["tile"]
        tile = _tile_of(inp, p)
        th, tw = len(tile), len(tile[0])
        y0, x0, y1, x1 = p["box"]
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                ky, ry = divmod(y - t0, th)
                kx, rx = divmod(x - l0, tw)
                if ky % 2:
                    ry = th - 1 - ry
                if kx % 2:
                    rx = tw - 1 - rx
                res[y][x] = tile[ry][rx]
    return res


# 2. Blank cells of the tile are painted with the field color.
def blank_to_field(inp, out):
    return _render(inp, tile_fn=lambda t, b, p, f: [[f if c == b else c for c in r] for r in t])


# 3. The tile is inverted: mark and blank swap.
def inverted_tile(inp, out):
    return _render(inp, tile_fn=lambda t, b, p, f: [[p["mark"] if c == b else b for c in r] for r in t])


# 4. The tile is rotated half a turn before it is repeated.
def rotated_tile(inp, out):
    return _render(inp, tile_fn=lambda t, b, p, f: [r[::-1] for r in t[::-1]])


# 5. The tile box is one row and one column too large (extends into the blank
#    on the far side), so copies do not line up with the true ones.
def tile_too_large(inp, out):
    def tb(inp_, p):
        t0, l0, t1, l1 = p["tile"]
        y0, x0, y1, x1 = p["box"]
        if t0 == y0:
            t1 = min(t1 + 1, y1)
        else:
            t0 = max(t0 - 1, y0)
        if l0 == x0:
            l1 = min(l1 + 1, x1)
        else:
            l0 = max(l0 - 1, x0)
        return (t0, l0, t1, l1)
    return _render(inp, tile_box_fn=tb)


# 6. The tile box is one row too short (last tile row lost).
def tile_too_small(inp, out):
    def tb(inp_, p):
        t0, l0, t1, l1 = p["tile"]
        y0, x0, y1, x1 = p["box"]
        if t1 > t0:
            if t0 == y0:
                t1 -= 1
            else:
                t0 += 1
        elif l1 > l0:
            if l0 == x0:
                l1 -= 1
            else:
                l0 += 1
        return (t0, l0, t1, l1)
    return _render(inp, tile_box_fn=tb)


# 7. Copies repeat only along the horizontal axis (one band of tile height).
def horizontal_only(inp, out):
    def ext(p, H, W):
        y0, x0, y1, x1 = p["box"]
        t0, _, t1, _ = p["tile"]
        return (t0, x0, t1, x1)
    return _render(inp, extent_fn=ext)


# 8. Copies repeat only along the vertical axis (one band of tile width).
def vertical_only(inp, out):
    def ext(p, H, W):
        y0, x0, y1, x1 = p["box"]
        _, l0, _, l1 = p["tile"]
        return (y0, l0, y1, l1)
    return _render(inp, extent_fn=ext)


# 9. Copies fill the whole grid, field included.
def fill_whole_grid(inp, out):
    return _render(inp, extent_fn=lambda p, H, W: (0, 0, H - 1, W - 1))


# 10. The fill region reaches one cell past the panel on every side.
def panel_plus_one(inp, out):
    def ext(p, H, W):
        y0, x0, y1, x1 = p["box"]
        return (max(0, y0 - 1), max(0, x0 - 1), min(H - 1, y1 + 1), min(W - 1, x1 + 1))
    return _render(inp, extent_fn=ext)


# 11. Only the first copy beside the tile is added: a 2 by 2 block of copies.
def two_by_two_only(inp, out):
    def ext(p, H, W):
        y0, x0, y1, x1 = p["box"]
        t0, l0, t1, l1 = p["tile"]
        th, tw = t1 - t0 + 1, l1 - l0 + 1
        # block of 2x2 copies, placed toward the panel interior
        by0 = t0 if t0 == y0 else t0 - th
        bx0 = l0 if l0 == x0 else l0 - tw
        return (max(y0, by0), max(x0, bx0), min(y1, by0 + 2 * th - 1), min(x1, bx0 + 2 * tw - 1))
    return _render(inp, extent_fn=ext)


# 12. Only the panel with the most cells is tiled; other panels stay as input.
def largest_panel_only(inp, out):
    def flt(i, p, panels):
        area = lambda q: (q["box"][2] - q["box"][0] + 1) * (q["box"][3] - q["box"][1] + 1)
        return area(p) == max(area(q) for q in panels)
    return _render(inp, panel_filter=flt)


ALTERNATIVES = [
    ("alternate copies of the tile are mirrored", _wrap(mirrored_copies)),
    ("blank cells of the tile are painted with the field color", _wrap(blank_to_field)),
    ("the tile is inverted: mark and blank colors swap", _wrap(inverted_tile)),
    ("the tile is rotated by half a turn before repeating", _wrap(rotated_tile)),
    ("the tile box is one row and one column too large", _wrap(tile_too_large)),
    ("the tile box is one row too short", _wrap(tile_too_small)),
    ("copies repeat only horizontally, in a band of the tile's height", _wrap(horizontal_only)),
    ("copies repeat only vertically, in a band of the tile's width", _wrap(vertical_only)),
    ("copies fill the whole grid, field included", _wrap(fill_whole_grid)),
    ("copies fill one cell past the panel on every side", _wrap(panel_plus_one)),
    ("only a 2 by 2 block of copies is laid", _wrap(two_by_two_only)),
    ("only the largest panel is tiled", _wrap(largest_panel_only)),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/a57f2f04.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in pairs:
            g = fn(pr["input"], pr["output"])
            if g is not None and _valid(g, pr["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
