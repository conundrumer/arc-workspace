import json
from pathlib import Path


def _rects(inp):
    """Bounding boxes (color, r0, c0, r1, c1) of 4-connected same-color non-zero components."""
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 or (r, c) in seen:
                continue
            col = inp[r][c]
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] == col:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            res.append((col, min(ys), min(xs), max(ys), max(xs)))
    return res


def _paint(inp, pred, inset=1, which=None, fill=0, include_border=False):
    """Copy inp; in each chosen rectangle set cells to fill where pred(r, c, box) holds."""
    g = [row[:] for row in inp]
    rects = _rects(inp)
    for i, b in enumerate(rects):
        if which is not None and i not in which(rects):
            continue
        col, r0, c0, r1, c1 = b
        lo = 0 if include_border else inset
        for r in range(r0 + lo, r1 - lo + 1):
            for c in range(c0 + lo, c1 - lo + 1):
                if pred(r, c, b):
                    g[r][c] = fill
    return g


def odd_parity(inp, out):
    return _paint(inp, lambda r, c, b: ((r - b[1]) + (c - b[2])) % 2 == 1)


def bottom_right_anchor(inp, out):
    return _paint(inp, lambda r, c, b: ((b[3] - r) + (b[4] - c)) % 2 == 0)


def grid_origin_parity(inp, out):
    return _paint(inp, lambda r, c, b: (r + c) % 2 == 0)


def fill_whole_interior(inp, out):
    return _paint(inp, lambda r, c, b: True)


def only_largest(inp, out):
    def which(rects):
        areas = [(b[3] - b[1] + 1) * (b[4] - b[2] + 1) for b in rects]
        return {areas.index(max(areas))}
    return _paint(inp, lambda r, c, b: ((r - b[1]) + (c - b[2])) % 2 == 0, which=which)


def only_first(inp, out):
    def which(rects):
        return {0}
    return _paint(inp, lambda r, c, b: ((r - b[1]) + (c - b[2])) % 2 == 0, which=which)


def checker_includes_border(inp, out):
    return _paint(inp, lambda r, c, b: ((r - b[1]) + (c - b[2])) % 2 == 0, include_border=True)


def inset_two(inp, out):
    return _paint(inp, lambda r, c, b: ((r - b[1]) + (c - b[2])) % 2 == 0, inset=2)


def row_stripes(inp, out):
    return _paint(inp, lambda r, c, b: (r - b[1]) % 2 == 0)


def sparse_odd_odd(inp, out):
    return _paint(inp, lambda r, c, b: (r - b[1]) % 2 == 1 and (c - b[2]) % 2 == 1)


def hole_color_five(inp, out):
    return _paint(inp, lambda r, c, b: ((r - b[1]) + (c - b[2])) % 2 == 0, fill=5)


def crop_to_content(inp, out):
    cells = [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v != 0]
    r0 = min(p[0] for p in cells)
    r1 = max(p[0] for p in cells)
    c0 = min(p[1] for p in cells)
    c1 = max(p[1] for p in cells)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("holes on the odd-parity cells (row+col distance from the top-left corner is odd) instead of even", odd_parity),
    ("distance sum counted from the bottom-right corner of each rectangle instead of the top-left", bottom_right_anchor),
    ("parity taken from absolute grid coordinates (row+col even) instead of from each rectangle's corner", grid_origin_parity),
    ("the whole inside of each rectangle is emptied, with no checker pattern", fill_whole_interior),
    ("only the largest rectangle is punched", only_largest),
    ("only the first rectangle in reading order is punched", only_first),
    ("the checker also covers the outline cells, so the outline is punched too", checker_includes_border),
    ("the outline is two cells thick, so the checker starts two cells in", inset_two),
    ("holes fill whole alternate rows instead of a checker", row_stripes),
    ("holes only where both row and column offsets from the corner are odd (sparse lattice)", sparse_odd_odd),
    ("holes are painted color 5 instead of background", hole_color_five),
    ("output is cropped to the bounding box of the non-background content", crop_to_content),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/ba9d41b8.json').read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
