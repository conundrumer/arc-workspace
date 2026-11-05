import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(c for r in g for c in r).most_common(1)[0][0]


def _squares(g):
    """Bounding boxes (r0, c0, r1, c1) of 4-connected non-background components."""
    bg = _bg(g)
    h, w = len(g), len(g[0])
    seen = set()
    boxes = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != bg and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            boxes.append((min(ys), min(xs), max(ys), max(xs)))
    return sorted(boxes)


def _paint(inp, colors, dist=1, boxes=None, inside=False):
    """colors: (TL, TR, BL, BR). Seats lie dist cells diagonally outside each box corner."""
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for (r0, c0, r1, c1) in (_squares(inp) if boxes is None else boxes):
        if inside:
            pts = [(r0, c0), (r0, c1), (r1, c0), (r1, c1)]
        else:
            pts = [(r0 - dist, c0 - dist), (r0 - dist, c1 + dist),
                   (r1 + dist, c0 - dist), (r1 + dist, c1 + dist)]
        for (y, x), col in zip(pts, colors):
            if 0 <= y < h and 0 <= x < w:
                g[y][x] = col
    return g


def _recolor(out, mapping):
    return [[mapping.get(c, c) for c in row] for row in out]


def only_top_corners(inp, out):
    return _paint(inp, (1, 2, 0, 0))


def swap_lr(inp, out):
    return _recolor(out, {1: 2, 2: 1, 3: 4, 4: 3})


def swap_ud(inp, out):
    return _recolor(out, {1: 3, 3: 1, 2: 4, 4: 2})


def rot180_colors(inp, out):
    return _recolor(out, {1: 4, 4: 1, 2: 3, 3: 2})


def clockwise_colors(inp, out):
    return _paint(inp, (1, 2, 4, 3))


def all_one_color(inp, out):
    return _paint(inp, (1, 1, 1, 1))


def two_cells_away(inp, out):
    return _paint(inp, (1, 2, 3, 4), dist=2)


def corners_inside_square(inp, out):
    return _paint(inp, (1, 2, 3, 4), inside=True)


def last_square_skipped(inp, out):
    boxes = _squares(inp)[:-1]
    return _paint(inp, (1, 2, 3, 4), boxes=boxes)


def first_square_only(inp, out):
    boxes = _squares(inp)[:1]
    if len(_squares(inp)) < 2:
        return None
    return _paint(inp, (1, 2, 3, 4), boxes=boxes)


def edge_midpoints(inp, out):
    """Paint the cells orthogonally beside the square (above, below, left, right of its top-left/bottom-right) instead of diagonals."""
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for (r0, c0, r1, c1) in _squares(inp):
        pts = [(r0 - 1, c0), (r0 - 1, c1), (r1 + 1, c0), (r1 + 1, c1)]
        for (y, x), col in zip(pts, (1, 2, 3, 4)):
            if 0 <= y < h and 0 <= x < w:
                g[y][x] = col
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("only the two top corner seats are painted", only_top_corners),
    ("left and right corner colors swapped (1<->2, 3<->4)", swap_lr),
    ("top and bottom corner colors swapped (1<->3, 2<->4)", swap_ud),
    ("corner colors rotated half a turn (1<->4, 2<->3)", rot180_colors),
    ("corner colors numbered clockwise: TL 1, TR 2, BR 3, BL 4", clockwise_colors),
    ("all four seats painted with one color 1", all_one_color),
    ("seats two cells diagonally away instead of one", two_cells_away),
    ("corner colors placed on the square's own corner cells", corners_inside_square),
    ("the last square in reading order gets no seats", last_square_skipped),
    ("only the first square in reading order gets seats", first_square_only),
    ("seats placed orthogonally above and below the square's columns, not diagonally", edge_midpoints),
    ("input returned unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/95990924.json"))
    pairs = task["train"]
    print(f"pairs: {len(pairs)}")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
