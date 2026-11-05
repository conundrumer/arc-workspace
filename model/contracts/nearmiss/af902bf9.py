"""Near-miss readings for ARC task af902bf9.

Rule: groups of four 4-markers at rectangle corners; the cells strictly inside
each rectangle become 2.
"""
import json
from pathlib import Path


def _rects(out):
    """Bounding boxes (r0, r1, c0, c1) of the 4-connected 2-regions of out."""
    h, w = len(out), len(out[0])
    seen = set()
    boxes = []
    for r in range(h):
        for c in range(w):
            if out[r][c] == 2 and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and out[ny][nx] == 2 and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                rs = [p[0] for p in cells]
                cs = [p[1] for p in cells]
                boxes.append((min(rs), max(rs), min(cs), max(cs)))
    return sorted(boxes)


def _blank(inp):
    return [row[:] for row in inp]


def _paint(g, r0, r1, c0, c1, color, only_empty=True):
    h, w = len(g), len(g[0])
    for r in range(max(r0, 0), min(r1, h - 1) + 1):
        for c in range(max(c0, 0), min(c1, w - 1) + 1):
            if not only_empty or g[r][c] == 0:
                g[r][c] = color


def _same(g, out):
    return g == out


def inclusive_box(inp, out):
    g = _blank(inp)
    for r0, r1, c0, c1 in _rects(out):
        _paint(g, r0 - 1, r1 + 1, c0 - 1, c1 + 1, 2)
    return g


def wrong_color_4(inp, out):
    g = _blank(inp)
    for r0, r1, c0, c1 in _rects(out):
        _paint(g, r0, r1, c0, c1, 4)
    return g


def wrong_color_1(inp, out):
    g = _blank(inp)
    for r0, r1, c0, c1 in _rects(out):
        _paint(g, r0, r1, c0, c1, 1)
    return g


def shrunk_by_one(inp, out):
    g = _blank(inp)
    for r0, r1, c0, c1 in _rects(out):
        _paint(g, r0 + 1, r1 - 1, c0 + 1, c1 - 1, 2)
    return g


def shifted_down_right(inp, out):
    g = _blank(inp)
    for r0, r1, c0, c1 in _rects(out):
        _paint(g, r0 + 1, r1 + 1, c0 + 1, c1 + 1, 2)
    return g


def edge_lines_between_markers(inp, out):
    g = _blank(inp)
    for r0, r1, c0, c1 in _rects(out):
        _paint(g, r0 - 1, r0 - 1, c0, c1, 2)
        _paint(g, r1 + 1, r1 + 1, c0, c1, 2)
        _paint(g, r0, r1, c0 - 1, c0 - 1, 2)
        _paint(g, r0, r1, c1 + 1, c1 + 1, 2)
    return g


def top_half_only(inp, out):
    g = _blank(inp)
    for r0, r1, c0, c1 in _rects(out):
        half = (r1 - r0 + 1) // 2
        _paint(g, r0, r0 + half - 1, c0, c1, 2)
    return g


def full_width_band(inp, out):
    g = _blank(inp)
    for r0, r1, c0, c1 in _rects(out):
        _paint(g, r0, r1, 0, len(g[0]) - 1, 2)
    return g


def global_marker_box(inp, out):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 4]
    if not cells:
        return None
    rs = [p[0] for p in cells]
    cs = [p[1] for p in cells]
    g = _blank(inp)
    _paint(g, min(rs) + 1, max(rs) - 1, min(cs) + 1, max(cs) - 1, 2)
    return None if _same(g, out) else g


def skip_single_cell_interiors(inp, out):
    g = _blank(inp)
    for r0, r1, c0, c1 in _rects(out):
        if r0 == r1 and c0 == c1:
            continue
        _paint(g, r0, r1, c0, c1, 2)
    return None if _same(g, out) else g


def only_first_rectangle(inp, out):
    boxes = _rects(out)
    g = _blank(inp)
    for r0, r1, c0, c1 in boxes[:1]:
        _paint(g, r0, r1, c0, c1, 2)
    return None if _same(g, out) else g


def box_overwrites_markers(inp, out):
    g = _blank(inp)
    for r0, r1, c0, c1 in _rects(out):
        _paint(g, r0 - 1, r1 + 1, c0 - 1, c1 + 1, 2, only_empty=False)
    return g


def unchanged_input(inp, out):
    return _blank(inp)


ALTERNATIVES = [
    ("fill the inclusive bounding box of each marker rectangle (one cell too large per side), keeping markers", inclusive_box),
    ("fill each rectangle interior with the marker color 4 instead of 2", wrong_color_4),
    ("fill the interior shrunk by one cell on every side", shrunk_by_one),
    ("fill the interior offset by one cell down and right", shifted_down_right),
    ("fill only the lines of cells between adjacent corner markers, not the interior", edge_lines_between_markers),
    ("fill only the top half of each interior", top_half_only),
    ("fill the interior rows across the full grid width", full_width_band),
    ("fill the interior of one bounding box around all markers in the grid", global_marker_box),
    ("skip rectangles whose interior is a single cell", skip_single_cell_interiors),
    ("fill only the first (top-left) rectangle found", only_first_rectangle),
    ("fill the inclusive bounding box and overwrite the corner markers with 2", box_overwrites_markers),
    ("return the input unchanged", unchanged_input),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1
        and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/af902bf9.json").read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
