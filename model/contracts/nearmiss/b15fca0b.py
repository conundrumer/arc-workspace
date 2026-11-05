import json
from collections import deque
from pathlib import Path

E, W, BG, P = 2, 1, 0, 4
N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
N8 = N4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def copy(g):
    return [r[:] for r in g]


def ends(g):
    return [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v == E]


def path_cells(inp, out):
    return [(r, c) for r, row in enumerate(out) for c, v in enumerate(row)
            if v == P and inp[r][c] != P]


def bfs(g, passable, dirs, a, b):
    h, w = len(g), len(g[0])
    prev = {a: None}
    q = deque([a])
    while q:
        cur = q.popleft()
        if cur == b:
            break
        for dr, dc in dirs:
            n = (cur[0] + dr, cur[1] + dc)
            if 0 <= n[0] < h and 0 <= n[1] < w and n not in prev and (n == b or passable(g[n[0]][n[1]])):
                prev[n] = cur
                q.append(n)
    if b not in prev:
        return None
    cells, cur = [], prev[b]
    while cur is not None and cur != a:
        cells.append(cur)
        cur = prev[cur]
    return cells[::-1]


def ordered_path(inp, out):
    """True path cells in walk order from the first endpoint."""
    a, b = ends(inp)
    cells = set(path_cells(inp, out))
    order, cur, seen = [], a, {a}
    while True:
        nxt = None
        for dr, dc in N4:
            n = (cur[0] + dr, cur[1] + dc)
            if n in cells and n not in seen:
                nxt = n
                break
        if nxt is None:
            return order
        order.append(nxt)
        seen.add(nxt)
        cur = nxt


def paint(g, cells, color=P, only=None):
    g = copy(g)
    for r, c in cells:
        if only is None or g[r][c] in only:
            g[r][c] = color
    return g


def wrong_color(inp, out):
    return [[3 if v == P else v for v in row] for row in out]


def endpoints_painted(inp, out):
    g = copy(out)
    for r, c in ends(inp):
        g[r][c] = P
    return g


def walls_passable(inp, out):
    a, b = ends(inp)
    cells = bfs(inp, lambda v: True, N4, a, b)
    return paint(inp, cells, P, only=(BG, W))


def diagonal_steps(inp, out):
    a, b = ends(inp)
    cells = bfs(inp, lambda v: v == BG, N8, a, b)
    return paint(inp, cells, P, only=(BG,))


def flood_region(inp, out):
    a, _ = ends(inp)
    h, w = len(inp), len(inp[0])
    seen, q = {a}, deque([a])
    while q:
        cur = q.popleft()
        for dr, dc in N4:
            n = (cur[0] + dr, cur[1] + dc)
            if 0 <= n[0] < h and 0 <= n[1] < w and n not in seen and inp[n[0]][n[1]] == BG:
                seen.add(n)
                q.append(n)
    return paint(inp, seen, P, only=(BG,))


def trimmed_ends(inp, out):
    cells = path_cells(inp, out)
    es = ends(inp)
    drop = [p for p in cells
            if any(abs(p[0] - e[0]) + abs(p[1] - e[1]) == 1 for e in es)]
    g = copy(out)
    for r, c in drop:
        g[r][c] = inp[r][c]
    return g


def first_half(inp, out):
    order = ordered_path(inp, out)
    return paint(inp, order[:len(order) // 2], P)


def rays_from_ends(inp, out):
    h, w = len(inp), len(inp[0])
    g = copy(inp)
    for r, c in ends(inp):
        for dr, dc in N4:
            y, x = r + dr, c + dc
            while 0 <= y < h and 0 <= x < w and inp[y][x] == BG:
                g[y][x] = P
                y += dr
                x += dc
    return g


def bounding_box(inp, out):
    a, b = ends(inp)
    r0, r1 = sorted((a[0], b[0]))
    c0, c1 = sorted((a[1], b[1]))
    cells = [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
    return paint(inp, cells, P, only=(BG,))


def mirrored_path(inp, out):
    w = len(inp[0])
    cells = [(r, w - 1 - c) for r, c in path_cells(inp, out)]
    return paint(inp, cells, P, only=(BG,))


def l_shape(inp, out):
    a, b = ends(inp)
    cells = []
    step = 1 if b[1] >= a[1] else -1
    for c in range(a[1], b[1] + step, step):
        cells.append((a[0], c))
    step = 1 if b[0] >= a[0] else -1
    for r in range(a[0], b[0] + step, step):
        cells.append((r, b[1]))
    return paint(inp, cells, P, only=(BG,))


def unchanged(inp, out):
    return copy(inp)


ALTERNATIVES = [
    ("path painted with color 3 instead of the new color 4", wrong_color),
    ("endpoint cells are painted with the path color too", endpoints_painted),
    ("route may cross walls, and the walls on it are painted", walls_passable),
    ("route may step diagonally (8-connected)", diagonal_steps),
    ("all background connected to an endpoint is painted, not only the shortest route", flood_region),
    ("route stops one cell short of each endpoint", trimmed_ends),
    ("only the half of the route nearer the first endpoint is painted", first_half),
    ("rays from each endpoint over background until a wall are painted", rays_from_ends),
    ("every background cell in the bounding box of the endpoints is painted", bounding_box),
    ("route painted mirrored left-right", mirrored_path),
    ("route is an L shape: along the first endpoint's row, then the second's column", l_shape),
    ("input returned unchanged", unchanged),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/b15fca0b.json').read_text())
    train = task['train']
    print(len(ALTERNATIVES), 'readings,', len(train), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in train:
            g = fn(pr['input'], pr['output'])
            if g is not None and valid(g, pr['output']):
                n += 1
        print(n, desc)
