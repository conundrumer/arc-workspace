"""Near-miss readings for bc93ec48: each corner shape moves to the next corner clockwise."""
import json
from collections import Counter
from pathlib import Path

# corner order, clockwise
CORNERS = ["TL", "TR", "BR", "BL"]


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _corner_cell(g, c):
    h, w = len(g), len(g[0])
    return {"TL": (0, 0), "TR": (0, w - 1), "BR": (h - 1, w - 1), "BL": (h - 1, 0)}[c]


def _component(g, start, bg, conn8=False):
    h, w = len(g), len(g[0])
    col = g[start[0]][start[1]]
    if col == bg:
        return None
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if conn8:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    seen = {start}
    stack = [start]
    while stack:
        r, c = stack.pop()
        for dr, dc in steps:
            q = (r + dr, c + dc)
            if 0 <= q[0] < h and 0 <= q[1] < w and q not in seen and g[q[0]][q[1]] == col:
                seen.add(q)
                stack.append(q)
    return col, seen


def _shapes(g, conn8=False):
    bg = _bg(g)
    res = {}
    for c in CORNERS:
        comp = _component(g, _corner_cell(g, c), bg, conn8)
        if comp:
            res[c] = comp
    return bg, res


def _anchor(corner, hh, ww, h, w):
    top = 0 if corner in ("TL", "TR") else h - hh
    left = 0 if corner in ("TL", "BL") else w - ww
    return top, left


def _render(inp, mapping, transform="id", erase=False, blank=False, inset=0,
            conn8=False, fill_box=False, recolor=None, only=None):
    h, w = len(inp), len(inp[0])
    bg, shapes = _shapes(inp, conn8)
    g = [[bg] * w for _ in range(h)] if blank else [r[:] for r in inp]
    if erase:
        for c, (col, cells) in shapes.items():
            for r, k in cells:
                g[r][k] = bg
    for c, (col, cells) in shapes.items():
        if only is not None and c not in only:
            continue
        t = mapping[c]
        top = min(r for r, k in cells)
        left = min(k for r, k in cells)
        rel = [(r - top, k - left) for r, k in cells]
        hh = max(r for r, k in rel) + 1
        ww = max(k for r, k in rel) + 1
        if fill_box:
            rel = [(r, k) for r in range(hh) for k in range(ww)]
        if transform == "mirror":
            if (c in ("TL", "BL")) != (t in ("TL", "BL")):
                rel = [(r, ww - 1 - k) for r, k in rel]
            if (c in ("TL", "TR")) != (t in ("TL", "TR")):
                rel = [(hh - 1 - r, k) for r, k in rel]
        elif transform == "rot":
            rel = [(k, hh - 1 - r) for r, k in rel]
            hh, ww = ww, hh
        t0, l0 = _anchor(t, hh, ww, h, w)
        dr = inset if t in ("TL", "TR") else -inset
        dk = inset if t in ("TL", "BL") else -inset
        color = col
        if recolor == "target" and t in shapes:
            color = shapes[t][0]
        for r, k in rel:
            rr, kk = t0 + r + dr, l0 + k + dk
            if 0 <= rr < h and 0 <= kk < w:
                g[rr][kk] = color
    return g


CW = {"TL": "TR", "TR": "BR", "BR": "BL", "BL": "TL"}
CCW = {v: k for k, v in CW.items()}
OPP = {"TL": "BR", "BR": "TL", "TR": "BL", "BL": "TR"}


def ccw(inp, out):
    return _render(inp, CCW)


def opposite(inp, out):
    return _render(inp, OPP)


def no_erase_wrong_keep_vs_erase(inp, out):
    # moved-away shapes are erased
    return _render(inp, CW, erase=True)


def mirrored(inp, out):
    return _render(inp, CW, transform="mirror")


def rotated(inp, out):
    return _render(inp, CW, transform="rot")


def inset_one(inp, out):
    return _render(inp, CW, inset=1)


def only_top_corners(inp, out):
    return _render(inp, CW, only=("TL", "TR"))


def recolor_target(inp, out):
    return _render(inp, CW, recolor="target")


def blank_background(inp, out):
    return _render(inp, CW, blank=True)


def box_filled(inp, out):
    return _render(inp, CW, fill_box=True)


def ccw_erase(inp, out):
    return _render(inp, CCW, erase=True)


def swap_adjacent_pairs(inp, out):
    # corners swap in pairs horizontally instead of cycling
    return _render(inp, {"TL": "TR", "TR": "TL", "BL": "BR", "BR": "BL"})


ALTERNATIVES = [
    ("shapes move counterclockwise instead of clockwise", ccw),
    ("shapes move to the diagonally opposite corner", opposite),
    ("the source shape is erased after it moves", no_erase_wrong_keep_vs_erase),
    ("the copy is mirrored across the grid axis as it moves", mirrored),
    ("the copy is rotated 90 degrees as it moves", rotated),
    ("the copy sits one cell in from the target corner's edges", inset_one),
    ("only the two top corners' shapes are copied", only_top_corners),
    ("the copy takes the color of the target corner's own shape", recolor_target),
    ("the output is blank background holding only the copies", blank_background),
    ("each shape is replaced by its filled bounding box when copied", box_filled),
    ("counterclockwise move with the source shape erased", ccw_erase),
    ("corners swap in horizontal pairs instead of cycling", swap_adjacent_pairs),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/bc93ec48.json"))
    pairs = task["train"]
    # sanity: the true rule reproduces the outputs
    ok = all(_render(p["input"], CW) == p["output"] for p in pairs)
    print("true rule reproduces outputs:", ok)
    print(f"pairs: {len(pairs)}")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
