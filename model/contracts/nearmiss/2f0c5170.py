"""Near-miss readings for ARC task 2f0c5170."""
import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    seen = set()
    comps = []
    for i in range(h):
        for j in range(w):
            if inp[i][j] == bg or (i, j) in seen:
                continue
            st = [(i, j)]
            seen.add((i, j))
            cells = []
            while st:
                y, x = st.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != bg and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        st.append((ny, nx))
            comps.append(cells)
    canvas = Counter(inp[y][x] for c in comps for y, x in c).most_common(1)[0][0]
    info = []
    for c in comps:
        y0 = min(y for y, _ in c); y1 = max(y for y, _ in c)
        x0 = min(x for _, x in c); x1 = max(x for _, x in c)
        marks = {(y, x): inp[y][x] for y, x in c if inp[y][x] != canvas}
        info.append({"box": (y0, x0, y1, x1), "marks": marks})
    lone = [p for p in info if len(p["marks"]) == 1]
    glyph = [p for p in info if len(p["marks"]) > 1]
    if len(lone) != 1 or len(glyph) != 1:
        return None
    lone, glyph = lone[0], glyph[0]
    (lp, lc), = lone["marks"].items()
    handles = sorted(p for p, c in glyph["marks"].items() if c == lc)
    if not handles:
        return None
    return {"bg": bg, "canvas": canvas, "lone": lone, "glyph": glyph,
            "lp": lp, "lc": lc, "handle": handles[0]}


def _blank(box, canvas):
    y0, x0, y1, x1 = box
    return [[canvas] * (x1 - x0 + 1) for _ in range(y1 - y0 + 1)]


def _stamp(g, box, canvas, cells, anchor_to, anchor_from, lone_mark=True, color=None):
    """cells: dict pos->color. Move so anchor_from lands on anchor_to."""
    y0, x0, y1, x1 = box
    grid = _blank(box, canvas)
    dy, dx = anchor_to[0] - anchor_from[0], anchor_to[1] - anchor_from[1]
    for (y, x), c in cells.items():
        ny, nx = y + dy, x + dx
        if y0 <= ny <= y1 and x0 <= nx <= x1:
            grid[ny - y0][nx - x0] = c if color is None else color
    return grid


def _ctx(inp):
    p = _parse(inp)
    return p


def glyph_panel_crop(inp, out):
    p = _ctx(inp)
    if not p:
        return None
    y0, x0, y1, x1 = p["glyph"]["box"]
    return [row[x0:x1 + 1] for row in inp[y0:y1 + 1]]


def align_bbox_corner(inp, out):
    p = _ctx(inp)
    if not p:
        return None
    gy = min(y for y, _ in p["glyph"]["marks"]); gx = min(x for _, x in p["glyph"]["marks"])
    return _stamp(inp, p["lone"]["box"], p["canvas"], p["glyph"]["marks"], p["lp"], (gy, gx))


def handle_most_common_color(inp, out):
    p = _ctx(inp)
    if not p:
        return None
    cnt = Counter(p["glyph"]["marks"].values())
    top = cnt.most_common(1)[0][0]
    anchors = sorted(q for q, c in p["glyph"]["marks"].items() if c == top)
    return _stamp(inp, p["lone"]["box"], p["canvas"], p["glyph"]["marks"], p["lp"], anchors[0])


def lone_mark_only(inp, out):
    p = _ctx(inp)
    if not p:
        return None
    y0, x0, _, _ = p["lone"]["box"]
    g = _blank(p["lone"]["box"], p["canvas"])
    g[p["lp"][0] - y0][p["lp"][1] - x0] = p["lc"]
    return g


def shifted_one_column(inp, out):
    p = _ctx(inp)
    if not p:
        return None
    return _stamp(inp, p["lone"]["box"], p["canvas"], p["glyph"]["marks"],
                  (p["lp"][0], p["lp"][1] + 1), p["handle"])


def mirrored_horizontally(inp, out):
    p = _ctx(inp)
    if not p:
        return None
    hy, hx = p["handle"]
    cells = {(y, 2 * hx - x): c for (y, x), c in p["glyph"]["marks"].items()}
    return _stamp(inp, p["lone"]["box"], p["canvas"], cells, p["lp"], p["handle"])


def mirrored_vertically(inp, out):
    p = _ctx(inp)
    if not p:
        return None
    hy, hx = p["handle"]
    cells = {(2 * hy - y, x): c for (y, x), c in p["glyph"]["marks"].items()}
    return _stamp(inp, p["lone"]["box"], p["canvas"], cells, p["lp"], p["handle"])


def single_color_stamp(inp, out):
    p = _ctx(inp)
    if not p:
        return None
    return _stamp(inp, p["lone"]["box"], p["canvas"], p["glyph"]["marks"], p["lp"],
                  p["handle"], color=p["lc"])


def crop_with_border(inp, out):
    p = _ctx(inp)
    if not p:
        return None
    y0, x0, y1, x1 = p["lone"]["box"]
    h, w = len(inp), len(inp[0])
    if y0 < 1 or x0 < 1 or y1 + 1 >= h or x1 + 1 >= w:
        return None
    ys, xs = y0 - 1, x0 - 1
    base = [row[xs:x1 + 2] for row in inp[ys:y1 + 2]]
    for (y, x), c in p["glyph"]["marks"].items():
        ny = y + p["lp"][0] - p["handle"][0]
        nx = x + p["lp"][1] - p["handle"][1]
        if y0 <= ny <= y1 and x0 <= nx <= x1:
            base[ny - ys][nx - xs] = c
    return base


def background_fill_wrong(inp, out):
    # untouched cells take the outer background color instead of the panel color
    p = _ctx(inp)
    if not p:
        return None
    return [[p["bg"] if v == p["canvas"] else v for v in row] for row in out]


def rotated_180(inp, out):
    p = _ctx(inp)
    if not p:
        return None
    hy, hx = p["handle"]
    cells = {(2 * hy - y, 2 * hx - x): c for (y, x), c in p["glyph"]["marks"].items()}
    return _stamp(inp, p["lone"]["box"], p["canvas"], cells, p["lp"], p["handle"])


def glyph_center_on_lone(inp, out):
    p = _ctx(inp)
    if not p:
        return None
    ys = [y for y, _ in p["glyph"]["marks"]]; xs = [x for _, x in p["glyph"]["marks"]]
    c = ((min(ys) + max(ys)) // 2, (min(xs) + max(xs)) // 2)
    return _stamp(inp, p["lone"]["box"], p["canvas"], p["glyph"]["marks"], p["lp"], c)


ALTERNATIVES = [
    ("crop the glyph panel itself instead of the lone-mark panel", glyph_panel_crop),
    ("align the glyph's bounding-box corner, not its handle, with the lone mark", align_bbox_corner),
    ("use the most common glyph color as the handle", handle_most_common_color),
    ("copy only the lone mark into the blank panel, no glyph stamped", lone_mark_only),
    ("glyph stamped one column to the right of the correct place", shifted_one_column),
    ("glyph mirrored left-right about the handle before stamping", mirrored_horizontally),
    ("glyph mirrored top-bottom about the handle before stamping", mirrored_vertically),
    ("glyph rotated 180 degrees about the handle before stamping", rotated_180),
    ("every stamped cell takes the lone mark's color", single_color_stamp),
    ("output crop includes a one-cell border of outer background", crop_with_border),
    ("panel cells outside the glyph filled with outer background color", background_fill_wrong),
    ("glyph bounding-box center placed on the lone mark", glyph_center_on_lone),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/2f0c5170.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in pairs:
            g = fn(pr["input"], pr["output"])
            if g is not None and _valid(g, pr["output"]):
                n += 1
        print(n, desc)
