import json
from pathlib import Path

WALL = 5
BG = 0


def _components(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            col = inp[r][c]
            if col in (BG, WALL) or (r, c) in seen:
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
                        if (0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen
                                and inp[ny][nx] == col):
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            comps.append((col, sorted(cells)))
    return comps


def _norm(cells):
    r0 = min(y for y, _ in cells)
    c0 = min(x for _, x in cells)
    return frozenset((y - r0, x - c0) for y, x in cells)


def _variants(cells):
    n = _norm(cells)
    out = set()
    cur = n
    for _ in range(4):
        cur = frozenset((x, -y) for y, x in cur)
        for f in (cur, frozenset((y, -x) for y, x in cur)):
            m = min(y for y, _ in f), min(x for _, x in f)
            out.add(frozenset((y - m[0], x - m[1]) for y, x in f))
    return out


def _corner_region(inp):
    h, w = len(inp), len(inp[0])
    best = None
    for sy, sx in ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)):
        if inp[sy][sx] == WALL:
            continue
        seen = {(sy, sx)}
        stack = [(sy, sx)]
        while stack:
            y, x = stack.pop()
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if (0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen
                        and inp[ny][nx] != WALL):
                    seen.add((ny, nx))
                    stack.append((ny, nx))
        if best is None or len(seen) < len(best):
            best = seen
    return best


def _parts(inp):
    """Returns (keys, others) where keys are shapes in the cut-off corner."""
    region = _corner_region(inp)
    keys, others = [], []
    for col, cells in _components(inp):
        (keys if cells[0] in region else others).append((col, cells))
    return keys, others


def _paint(inp, shapes, color):
    g = [row[:] for row in inp]
    for _, cells in shapes:
        for y, x in cells:
            g[y][x] = color
    return g


def _matching(inp, pred):
    keys, others = _parts(inp)
    if not keys:
        return None
    k = keys[0][1]
    return [s for s in others if pred(k, s[1])]


def all_others_gray(inp, out):
    keys, others = _parts(inp)
    return _paint(inp, others, WALL)


def non_matching_gray(inp, out):
    m = _matching(inp, lambda k, c: _norm(k) == _norm(c))
    keys, others = _parts(inp)
    return _paint(inp, [s for s in others if s not in m], WALL)


def match_color_of_key(inp, out):
    keys, _ = _parts(inp)
    m = _matching(inp, lambda k, c: _norm(k) == _norm(c))
    return _paint(inp, m, keys[0][0])


def include_key_gray(inp, out):
    keys, _ = _parts(inp)
    m = _matching(inp, lambda k, c: _norm(k) == _norm(c))
    return _paint(inp, m + keys, WALL)


def match_by_cell_count(inp, out):
    m = _matching(inp, lambda k, c: len(k) == len(c))
    return _paint(inp, m, WALL)


def match_by_bbox_size(inp, out):
    def dims(c):
        n = _norm(c)
        return max(y for y, _ in n), max(x for _, x in n)
    m = _matching(inp, lambda k, c: dims(k) == dims(c))
    return _paint(inp, m, WALL)


def match_up_to_rotation(inp, out):
    m = _matching(inp, lambda k, c: _norm(c) in _variants(k))
    return _paint(inp, m, WALL)


def fill_bbox_gray(inp, out):
    m = _matching(inp, lambda k, c: _norm(k) == _norm(c))
    g = [row[:] for row in inp]
    for _, cells in m:
        for y in range(min(y for y, _ in cells), max(y for y, _ in cells) + 1):
            for x in range(min(x for _, x in cells), max(x for _, x in cells) + 1):
                if g[y][x] == BG:
                    g[y][x] = WALL
    return g


def erase_matching(inp, out):
    m = _matching(inp, lambda k, c: _norm(k) == _norm(c))
    return _paint(inp, m, BG)


def largest_shape_is_key(inp, out):
    comps = _components(inp)
    if not comps:
        return None
    big = max(comps, key=lambda s: len(s[1]))
    m = [s for s in comps if s is not big and _norm(s[1]) == _norm(big[1])]
    return _paint(inp, m, WALL)


def key_shape_extra_neighbor(inp, out):
    # recolor the matching shapes plus every shape touching a matching one by distance 1
    m = _matching(inp, lambda k, c: _norm(k) == _norm(c))
    keys, others = _parts(inp)
    cells = {p for _, cs in m for p in cs}
    near = [s for s in others if s not in m and any(
        abs(y - a) <= 2 and abs(x - b) <= 2 for y, x in s[1] for a, b in cells)]
    return _paint(inp, m + near, WALL)


ALTERNATIVES = [
    ("recolor every shape outside the corner to gray, not only the one equal to the key", all_others_gray),
    ("recolor the shapes that differ from the key instead of the one that equals it", non_matching_gray),
    ("recolor the matching shape with the key's own color instead of gray", match_color_of_key),
    ("recolor the key shape in the corner to gray as well", include_key_gray),
    ("match shapes to the key by cell count only", match_by_cell_count),
    ("match shapes to the key by bounding-box size only", match_by_bbox_size),
    ("match shapes to the key up to rotation and reflection", match_up_to_rotation),
    ("paint the whole bounding box of the matching shape gray", fill_bbox_gray),
    ("erase the matching shape to background instead of recoloring it gray", erase_matching),
    ("take the largest shape in the grid as the key instead of the corner shape", largest_shape_is_key),
    ("also recolor shapes lying near a matching shape", key_shape_extra_neighbor),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/63613498.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
