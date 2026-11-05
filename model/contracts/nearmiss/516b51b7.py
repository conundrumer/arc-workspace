import json
from collections import deque
from pathlib import Path


def _copy(g):
    return [row[:] for row in g]


def _components(inp):
    h, w = len(inp), len(inp[0])
    comp = [[-1] * w for _ in range(h)]
    n = 0
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0 and comp[r][c] < 0:
                q = deque([(r, c)])
                comp[r][c] = n
                while q:
                    y, x = q.popleft()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0 and comp[ny][nx] < 0:
                            comp[ny][nx] = n
                            q.append((ny, nx))
                n += 1
    return comp, n


def _depth(inp):
    """Layers from the object's edge: 0 on the outline, -1 on background."""
    h, w = len(inp), len(inp[0])
    d = [[-1] * w for _ in range(h)]
    q = deque()
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0:
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = r + dy, c + dx
                    if not (0 <= ny < h and 0 <= nx < w) or inp[ny][nx] == 0:
                        d[r][c] = 0
                        q.append((r, c))
                        break
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0 and d[ny][nx] < 0:
                d[ny][nx] = d[y][x] + 1
                q.append((ny, nx))
    return d


def _bboxes(inp):
    comp, n = _components(inp)
    boxes = {}
    for r, row in enumerate(comp):
        for c, k in enumerate(row):
            if k >= 0:
                b = boxes.setdefault(k, [r, c, r, c, 0])
                b[0] = min(b[0], r); b[1] = min(b[1], c)
                b[2] = max(b[2], r); b[3] = max(b[3], c)
                b[4] += 1
    return comp, boxes


def _cells(inp):
    return [(r, c) for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] != 0]


def only_first_ring(inp, out):
    d = _depth(inp)
    g = _copy(out)
    for r, c in _cells(inp):
        if d[r][c] >= 2:
            g[r][c] = 1
    return g


def period_three(inp, out):
    d = _depth(inp)
    g = _copy(out)
    for r, c in _cells(inp):
        g[r][c] = (1, 2, 3)[d[r][c] % 3]
    return g


def swapped_colors(inp, out):
    g = _copy(out)
    for r, row in enumerate(out):
        for c, v in enumerate(row):
            if v in (2, 3):
                g[r][c] = 5 - v
    return g


def outline_starts_cycle(inp, out):
    d = _depth(inp)
    g = _copy(out)
    for r, c in _cells(inp):
        g[r][c] = 2 if d[r][c] % 2 == 0 else 3
    return g


def largest_object_only(inp, out):
    comp, boxes = _bboxes(inp)
    big = max(boxes, key=lambda k: boxes[k][4])
    g = _copy(inp)
    for r, c in _cells(inp):
        if comp[r][c] == big:
            g[r][c] = out[r][c]
    return g


def skip_largest_object(inp, out):
    comp, boxes = _bboxes(inp)
    big = max(boxes, key=lambda k: boxes[k][4])
    g = _copy(out)
    for r, c in _cells(inp):
        if comp[r][c] == big:
            g[r][c] = inp[r][c]
    return g


def top_left_distance(inp, out):
    comp, boxes = _bboxes(inp)
    g = _copy(out)
    for r, c in _cells(inp):
        t, l = boxes[comp[r][c]][:2]
        k = min(r - t, c - l)
        g[r][c] = 1 if k == 0 else (2 if k % 2 else 3)
    return g


def row_bands_only(inp, out):
    comp, boxes = _bboxes(inp)
    g = _copy(out)
    for r, c in _cells(inp):
        t, l, b, rr, _ = boxes[comp[r][c]]
        k = min(r - t, b - r)
        g[r][c] = 1 if (c in (l, rr) or k == 0) else (2 if k % 2 else 3)
    return g


def whole_interior_two(inp, out):
    d = _depth(inp)
    g = _copy(out)
    for r, c in _cells(inp):
        g[r][c] = 1 if d[r][c] == 0 else 2
    return g


def outline_erased(inp, out):
    d = _depth(inp)
    g = _copy(out)
    for r, c in _cells(inp):
        if d[r][c] == 0:
            g[r][c] = 0
    return g


def core_only_three(inp, out):
    comp, _ = _components(inp)
    d = _depth(inp)
    deepest = {}
    for r, c in _cells(inp):
        k = comp[r][c]
        deepest[k] = max(deepest.get(k, 0), d[r][c])
    g = _copy(out)
    for r, c in _cells(inp):
        v = d[r][c]
        if v > 0:
            g[r][c] = 3 if v == deepest[comp[r][c]] else 2
    return g


ALTERNATIVES = [
    ("only the first ring inside the outline is recolored; deeper cells stay the object color", only_first_ring),
    ("ring colors repeat with period 3 (1, 2, 3) counted from the outline", period_three),
    ("the two ring colors are swapped (first inner ring 3, next 2)", swapped_colors),
    ("the cycle starts at the outline: outline 2, next ring 3, alternating", outline_starts_cycle),
    ("only the largest object gets rings; other objects stay solid", largest_object_only),
    ("every object but the largest gets rings; the largest stays solid", skip_largest_object),
    ("depth is measured from the top and left edges only", top_left_distance),
    ("depth is measured from the top and bottom edges only; left and right columns stay outline", row_bands_only),
    ("every cell inside the outline becomes 2", whole_interior_two),
    ("the outline is erased to background while the rings are drawn", outline_erased),
    ("only the deepest layer of each object is 3; all other inner layers are 2", core_only_three),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/516b51b7.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
