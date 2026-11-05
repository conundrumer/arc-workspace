import json
from pathlib import Path

INK = 8
OUTLINE = 1
DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


def _copy(g):
    return [row[:] for row in g]


def _components(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == OUTLINE and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = y + dy, x + dx
                            if (0 <= ny < h and 0 <= nx < w
                                    and inp[ny][nx] == OUTLINE
                                    and (ny, nx) not in seen):
                                seen.add((ny, nx))
                                stack.append((ny, nx))
                comps.append(cells)
    return comps


def _rects(inp):
    """Per rectangle: (top, left, bottom, right, gaps) with gaps = [(r, c, dir)]."""
    res = []
    for cells in _components(inp):
        t = min(y for y, _ in cells)
        b = max(y for y, _ in cells)
        l = min(x for _, x in cells)
        rr = max(x for _, x in cells)
        gaps = []
        for y in range(t, b + 1):
            for x in range(l, rr + 1):
                if inp[y][x] == OUTLINE:
                    continue
                on_t, on_b, on_l, on_r = y == t, y == b, x == l, x == rr
                if not (on_t or on_b or on_l or on_r):
                    continue
                if on_t:
                    gaps.append((y, x, "up"))
                elif on_b:
                    gaps.append((y, x, "down"))
                elif on_l:
                    gaps.append((y, x, "left"))
                else:
                    gaps.append((y, x, "right"))
        res.append((t, l, b, rr, gaps))
    return res


def _ray(g, r, c, d, limit=None, include_start=True):
    h, w = len(g), len(g[0])
    dy, dx = DIRS[d]
    y, x = (r, c) if include_start else (r + dy, c + dx)
    n = 0
    while 0 <= y < h and 0 <= x < w and (limit is None or n < limit):
        g[y][x] = INK
        y += dy
        x += dx
        n += 1


def _fill_interior(g, rect, color=INK):
    t, l, b, r, _ = rect
    for y in range(t + 1, b):
        for x in range(l + 1, r):
            g[y][x] = color


def _opposite(d):
    return {"up": "down", "down": "up", "left": "right", "right": "left"}[d]


def correct(inp):
    g = _copy(inp)
    for rect in _rects(inp):
        _fill_interior(g, rect)
        for (y, x, d) in rect[4]:
            _ray(g, y, x, d)
    return g


def no_rays(inp, out):
    g = _copy(inp)
    for rect in _rects(inp):
        _fill_interior(g, rect)
    return g


def no_interior(inp, out):
    g = _copy(inp)
    for rect in _rects(inp):
        for (y, x, d) in rect[4]:
            _ray(g, y, x, d)
    return g


def short_rays(inp, out):
    g = _copy(inp)
    for rect in _rects(inp):
        _fill_interior(g, rect)
        for (y, x, d) in rect[4]:
            _ray(g, y, x, d, limit=2)
    return g


def inward_rays(inp, out):
    g = _copy(inp)
    for rect in _rects(inp):
        _fill_interior(g, rect)
        for (y, x, d) in rect[4]:
            _ray(g, y, x, _opposite(d))
    return g


def wrong_ink(inp, out):
    g = _copy(inp)
    for rect in _rects(inp):
        _fill_interior(g, rect, 2)
        for (y, x, d) in rect[4]:
            _ray(g, y, x, d)
            dy, dx = DIRS[d]
            h, w = len(g), len(g[0])
            yy, xx = y, x
            while 0 <= yy < h and 0 <= xx < w:
                g[yy][xx] = 2
                yy += dy
                xx += dx
    return g


def ray_without_gap_cell(inp, out):
    g = _copy(inp)
    for rect in _rects(inp):
        _fill_interior(g, rect)
        for (y, x, d) in rect[4]:
            _ray(g, y, x, d, include_start=False)
    return g


def overwrite_outline(inp, out):
    g = correct(inp)
    for (t, l, b, r, _) in _rects(inp):
        for y in range(t, b + 1):
            for x in range(l, r + 1):
                g[y][x] = INK
    return g


def both_directions(inp, out):
    g = _copy(inp)
    for rect in _rects(inp):
        _fill_interior(g, rect)
        for (y, x, d) in rect[4]:
            _ray(g, y, x, d)
            _ray(g, y, x, _opposite(d))
    return g


def only_gapped_filled(inp, out):
    g = _copy(inp)
    for rect in _rects(inp):
        if not rect[4]:
            continue
        _fill_interior(g, rect)
        for (y, x, d) in rect[4]:
            _ray(g, y, x, d)
    return g


def horizontal_rays_only(inp, out):
    g = _copy(inp)
    for rect in _rects(inp):
        _fill_interior(g, rect)
        for (y, x, d) in rect[4]:
            if d in ("left", "right"):
                _ray(g, y, x, d)
    return g


def only_largest_rect(inp, out):
    rects = _rects(inp)
    if len(rects) < 2:
        return None
    big = max(rects, key=lambda q: (q[2] - q[0] + 1) * (q[3] - q[1] + 1))
    g = _copy(inp)
    _fill_interior(g, big)
    for (y, x, d) in big[4]:
        _ray(g, y, x, d)
    return g


def rays_short_of_edge(inp, out):
    g = _copy(inp)
    h, w = len(g), len(g[0])
    for rect in _rects(inp):
        _fill_interior(g, rect)
        for (y, x, d) in rect[4]:
            dist = {"up": y, "down": h - 1 - y, "left": x, "right": w - 1 - x}[d]
            _ray(g, y, x, d, limit=max(dist, 1))
    return g


ALTERNATIVES = [
    ("fill rectangle interiors only; gaps cast no rays", no_rays),
    ("cast rays from gaps but leave interiors unfilled", no_interior),
    ("rays travel only two cells from the gap", short_rays),
    ("rays go from the gap inward and across the rectangle instead of outward", inward_rays),
    ("interior and rays painted with color 2 instead of 8", wrong_ink),
    ("rays start one cell past the gap, leaving the gap cell unpainted", ray_without_gap_cell),
    ("whole bounding box including the outline is painted 8", overwrite_outline),
    ("rays extend both outward and inward along the gap line", both_directions),
    ("only rectangles that have a gap are filled", only_gapped_filled),
    ("only gaps in left and right sides cast rays", horizontal_rays_only),
    ("only the largest rectangle is filled and casts rays", only_largest_rect),
    ("rays stop one cell short of the grid edge", rays_short_of_edge),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/551d5bf1.json").read_text())
    pairs = task["train"]
    for p in pairs:
        assert correct(p["input"]) == p["output"], "reference reconstruction mismatch"
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
