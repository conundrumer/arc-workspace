"""Near-miss rules for ARC task 342ae2ed.

Rule: blocks of one color come in pairs. From each block's corner, a diagonal
ray leaves toward the partner's facing corner and paints the background cells
between them with that color; figures stop a ray.
"""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _painted(inp, out):
    """Return {color: [(r, c), ...]} of cells the true output paints."""
    bg = _bg(inp)
    res = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == bg and out[r][c] != bg:
                res.setdefault(out[r][c], []).append((r, c))
    return res


def _blocks(inp):
    """Connected non-bg components (4-conn): list of (color, cells)."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
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
                    if (0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen
                            and inp[ny][nx] == col):
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append((col, cells))
    return comps


def _copy(g):
    return [list(r) for r in g]


def _with_paint(inp, paint):
    """inp with {(r, c): color} painted on background cells only."""
    bg = _bg(inp)
    g = _copy(inp)
    for (r, c), v in paint.items():
        if 0 <= r < len(g) and 0 <= c < len(g[0]) and g[r][c] == bg:
            g[r][c] = v
    return g


def _flat(painted):
    return {p: col for col, cells in painted.items() for p in cells}


def no_paint(inp, out):
    return _copy(inp)


def one_color_paint(inp, out):
    # All rays take the color of the largest figure instead of their own block.
    comps = _blocks(inp)
    big = max(comps, key=lambda t: len(t[1]))[0]
    return _with_paint(inp, {p: big for p in _flat(_painted(inp, out))})


def first_half_only(inp, out):
    # Each ray stops halfway between the facing corners.
    paint = {}
    for col, cells in _painted(inp, out).items():
        rows = sorted(r for r, _ in cells)
        mid = rows[len(rows) // 2]
        for p in cells:
            if p[0] < mid:
                paint[p] = col
    return _with_paint(inp, paint)


def rays_to_edge(inp, out):
    # Every corner of every figure shoots outward along all four diagonals
    # until it meets a figure or the grid edge.
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    paint = {}
    for col, cells in _blocks(inp):
        r0 = min(r for r, _ in cells)
        r1 = max(r for r, _ in cells)
        c0 = min(c for _, c in cells)
        c1 = max(c for _, c in cells)
        for r, c, dr, dc in ((r0, c0, -1, -1), (r0, c1, -1, 1),
                             (r1, c0, 1, -1), (r1, c1, 1, 1)):
            y, x = r + dr, c + dc
            while 0 <= y < h and 0 <= x < w and inp[y][x] == bg:
                paint[(y, x)] = col
                y += dr
                x += dc
    return _with_paint(inp, paint)


def shifted_one_column(inp, out):
    # Rays start one column off the corner.
    paint = {(r, c + 1): col for (r, c), col in _flat(_painted(inp, out)).items()}
    return _with_paint(inp, paint)


def one_cell_short(inp, out):
    # Each ray misses its first cell (off by one in length).
    paint = {}
    for col, cells in _painted(inp, out).items():
        for p in sorted(cells)[1:]:
            paint[p] = col
    return _with_paint(inp, paint)


def mirrored_diagonal(inp, out):
    # Each ray runs along the other diagonal of the box between the corners.
    paint = {}
    for col, cells in _painted(inp, out).items():
        c_lo = min(c for _, c in cells)
        c_hi = max(c for _, c in cells)
        for r, c in cells:
            paint[(r, c_lo + c_hi - c)] = col
    return _with_paint(inp, paint)


def rotated_colors(inp, out):
    # Rays take the color of the next pair instead of their own.
    painted = _painted(inp, out)
    cols = sorted(painted)
    if len(cols) < 2:
        return None
    nxt = {cols[i]: cols[(i + 1) % len(cols)] for i in range(len(cols))}
    return _with_paint(inp, {p: nxt[col] for p, col in _flat(painted).items()})


def fill_box(inp, out):
    # The whole box between the facing corners is filled, not just the diagonal.
    paint = {}
    for col, cells in _painted(inp, out).items():
        r0 = min(r for r, _ in cells)
        r1 = max(r for r, _ in cells)
        c0 = min(c for _, c in cells)
        c1 = max(c for _, c in cells)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                paint[(r, c)] = col
    return _with_paint(inp, paint)


def only_largest_pair(inp, out):
    # Only the pair with the longest ray gets connected.
    painted = _painted(inp, out)
    if len(painted) < 2:
        return None
    best = max(painted, key=lambda k: len(painted[k]))
    return _with_paint(inp, {p: best for p in painted[best]})


def crop_to_content(inp, out):
    # Output is cropped to the bounding box of the non-background cells.
    bg = _bg(inp)
    pts = [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v != bg]
    r0 = min(r for r, _ in pts)
    r1 = max(r for r, _ in pts)
    c0 = min(c for _, c in pts)
    c1 = max(c for _, c in pts)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("no ray is painted; the input is returned", no_paint),
    ("every ray takes the color of the largest figure", one_color_paint),
    ("each ray stops halfway between the facing corners", first_half_only),
    ("every figure corner shoots diagonals to the grid edge or the next figure", rays_to_edge),
    ("each ray starts one column off the corner", shifted_one_column),
    ("each ray misses its first cell", one_cell_short),
    ("each ray runs along the wrong diagonal of the box between corners", mirrored_diagonal),
    ("each ray takes the color of the next pair", rotated_colors),
    ("the whole box between facing corners is filled", fill_box),
    ("only the pair with the longest ray is connected", only_largest_pair),
    ("output is cropped to the bounding box of the non-background cells", crop_to_content),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / "data/tasks/342ae2ed.json"
    train = json.load(open(path))["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(_copy(p["input"]), _copy(p["output"]))
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
