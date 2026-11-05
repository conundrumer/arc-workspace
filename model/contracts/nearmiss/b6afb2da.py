"""Near-miss rules for b6afb2da: solid rectangles get corner 1, edge 4, interior 2."""
import json
from pathlib import Path

CORNER, EDGE, INTERIOR = 1, 4, 2


def rects(inp):
    """Bounding boxes (r0, c0, r1, c1) of 8-connected nonzero components, in scan order."""
    h, w = len(inp), len(inp[0])
    seen = set()
    boxes = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0 and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            boxes.append((min(y for y, _ in cells), min(x for _, x in cells),
                          max(y for y, _ in cells), max(x for _, x in cells)))
    return boxes


def paint(inp, box_list, corner=CORNER, edge=EDGE, interior=INTERIOR, ring=1,
          corner_set=None, edge_rows=True, edge_cols=True):
    g = [row[:] for row in inp]
    for r0, c0, r1, c1 in box_list:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if g[r][c] == 0:
                    continue
                is_corner = (r in (r0, r1)) and (c in (c0, c1))
                if corner_set is not None:
                    is_corner = (r, c) in corner_set(r0, c0, r1, c1)
                d = min(r - r0, r1 - r, c - c0, c1 - c)
                if is_corner:
                    g[r][c] = corner
                elif d < ring and ((r in (r0, r1) and edge_rows) or (c in (c0, c1) and edge_cols) or d >= 1):
                    g[r][c] = edge
                elif d < ring:
                    g[r][c] = inp[r][c]
                else:
                    g[r][c] = interior
    return g


def corners_as_edge(inp, out):
    return paint(inp, rects(inp), corner=EDGE)


def interior_as_edge(inp, out):
    return paint(inp, rects(inp), interior=EDGE)


def swap_corner_edge(inp, out):
    return paint(inp, rects(inp), corner=EDGE, edge=CORNER)


def only_largest(inp, out):
    bs = rects(inp)
    big = max(bs, key=lambda b: (b[2] - b[0] + 1) * (b[3] - b[1] + 1))
    return paint(inp, [big])


def only_first(inp, out):
    return paint(inp, rects(inp)[:1])


def only_corners(inp, out):
    return paint(inp, rects(inp), edge=5, interior=5)


def interior_unpainted(inp, out):
    return paint(inp, rects(inp), interior=5)


def thick_border(inp, out):
    return paint(inp, rects(inp), ring=2)


def two_diagonal_corners(inp, out):
    return paint(inp, rects(inp),
                 corner_set=lambda r0, c0, r1, c1: {(r0, c0), (r1, c1)})


def side_edges_only(inp, out):
    return paint(inp, rects(inp), edge_rows=False)


def union_bbox(inp, out):
    bs = rects(inp)
    box = (min(b[0] for b in bs), min(b[1] for b in bs),
           max(b[2] for b in bs), max(b[3] for b in bs))
    g = [[0] * len(inp[0]) for _ in inp]
    r0, c0, r1, c1 = box
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            corner = r in (r0, r1) and c in (c0, c1)
            d = min(r - r0, r1 - r, c - c0, c1 - c)
            g[r][c] = CORNER if corner else EDGE if d == 0 else INTERIOR
    return g


def crop_first(inp, out):
    r0, c0, r1, c1 = rects(inp)[0]
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("corners get the edge color, so corners are not distinguished", corners_as_edge),
    ("interior cells get the edge color instead of the interior color", interior_as_edge),
    ("corner and edge colors are swapped", swap_corner_edge),
    ("only the largest rectangle is recolored", only_largest),
    ("only the first rectangle in scan order is recolored", only_first),
    ("only corners are recolored; edge and interior stay as input", only_corners),
    ("interior stays as input; only the border is recolored", interior_unpainted),
    ("the border is two cells thick", thick_border),
    ("only the top-left and bottom-right corners get the corner color", two_diagonal_corners),
    ("only left and right sides are edges; top and bottom sides stay as input", side_edges_only),
    ("all rectangles are treated as one object with a shared bounding box, background included", union_bbox),
    ("output is the recolored first rectangle cropped out", crop_first),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b6afb2da.json").read_text())
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
