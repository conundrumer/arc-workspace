import json
from collections import deque
from pathlib import Path

BG, WALL = 0, 8
D4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
D8 = D4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _copy(g):
    return [row[:] for row in g]


def _seed(inp):
    h, w = len(inp), len(inp[0])
    ink = [(r, c) for r in range(h) for c in range(w) if inp[r][c] not in (BG, WALL)]
    s = set(ink)

    def n(p):
        return sum(((p[0] + dr, p[1] + dc) in s) for dr, dc in D4)

    center = max(ink, key=n)
    cc = inp[center[0]][center[1]]
    other = next(inp[r][c] for r, c in ink if inp[r][c] != cc)
    return ink, center, cc, other


def _flood(inp, ink, dirs, through):
    h, w = len(inp), len(inp[0])
    seen = set(ink)
    q = deque(ink)
    while q:
        r, c = q.popleft()
        for dr, dc in dirs:
            a, b = r + dr, c + dc
            if 0 <= a < h and 0 <= b < w and (a, b) not in seen and inp[a][b] in through:
                seen.add((a, b))
                q.append((a, b))
    return seen - set(ink)


def _paint(inp, cells, color_of):
    g = _copy(inp)
    for r, c in cells:
        g[r][c] = color_of(r, c)
    return g


def _ne(g, out):
    return None if g == out else g


def _parity_painter(center, cc, other):
    return lambda r, c: cc if (r + c) % 2 == (center[0] + center[1]) % 2 else other


def swapped_parity(inp, out):
    ink, center, cc, other = _seed(inp)
    cells = _flood(inp, ink, D4, (BG,))
    return _ne(_paint(inp, cells, _parity_painter(center, other, cc)), out)


def near_center_only(inp, out):
    ink, center, cc, other = _seed(inp)
    cells = [p for p in _flood(inp, ink, D4, (BG,))
             if abs(p[0] - center[0]) + abs(p[1] - center[1]) <= 6]
    return _ne(_paint(inp, cells, _parity_painter(center, cc, other)), out)


def center_color_only(inp, out):
    ink, center, cc, other = _seed(inp)
    cells = _flood(inp, ink, D4, (BG,))
    return _ne(_paint(inp, cells, lambda r, c: cc), out)


def arm_color_only(inp, out):
    ink, center, cc, other = _seed(inp)
    cells = _flood(inp, ink, D4, (BG,))
    return _ne(_paint(inp, cells, lambda r, c: other), out)


def every_bg_cell(inp, out):
    ink, center, cc, other = _seed(inp)
    h, w = len(inp), len(inp[0])
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == BG]
    return _ne(_paint(inp, cells, _parity_painter(center, cc, other)), out)


def through_walls(inp, out):
    ink, center, cc, other = _seed(inp)
    h, w = len(inp), len(inp[0])
    cells = [(r, c) for r in range(h) for c in range(w) if (r, c) not in set(ink)]
    return _ne(_paint(inp, cells, _parity_painter(center, cc, other)), out)


def only_even_parity_painted(inp, out):
    ink, center, cc, other = _seed(inp)
    cells = _flood(inp, ink, D4, (BG,))
    par = (center[0] + center[1]) % 2
    cells = [p for p in cells if (p[0] + p[1]) % 2 == par]
    return _ne(_paint(inp, cells, lambda r, c: cc), out)


def only_odd_parity_painted(inp, out):
    ink, center, cc, other = _seed(inp)
    cells = _flood(inp, ink, D4, (BG,))
    par = (center[0] + center[1]) % 2
    cells = [p for p in cells if (p[0] + p[1]) % 2 != par]
    return _ne(_paint(inp, cells, lambda r, c: other), out)


def skip_cells_next_to_seed(inp, out):
    ink, center, cc, other = _seed(inp)
    s = set(ink)
    g = _copy(out)
    for r, c in ink:
        for dr, dc in D4:
            a, b = r + dr, c + dc
            if 0 <= a < len(g) and 0 <= b < len(g[0]) and (a, b) not in s:
                g[a][b] = inp[a][b]
    return _ne(g, out)


def row_parity_stripes(inp, out):
    ink, center, cc, other = _seed(inp)
    cells = _flood(inp, ink, D4, (BG,))
    return _ne(_paint(inp, cells, lambda r, c: cc if r % 2 == center[0] % 2 else other), out)


def row_and_column_of_center_only(inp, out):
    ink, center, cc, other = _seed(inp)
    cells = [p for p in _flood(inp, ink, D4, (BG,)) if p[0] == center[0] or p[1] == center[1]]
    return _ne(_paint(inp, cells, _parity_painter(center, cc, other)), out)


def unchanged(inp, out):
    return _ne(_copy(inp), out)


ALTERNATIVES = [
    ("the parity colors are swapped: the center's parity takes the arm color", swapped_parity),
    ("the paint reaches only cells within Manhattan distance 6 of the center", near_center_only),
    ("every flooded cell takes the center color", center_color_only),
    ("every flooded cell takes the arm color", arm_color_only),
    ("every bg cell of the grid is painted, not only those joined to the seed", every_bg_cell),
    ("the walk and the paint also pass through wall cells", through_walls),
    ("only flooded cells of the center's parity are painted", only_even_parity_painted),
    ("only flooded cells of the other parity are painted", only_odd_parity_painted),
    ("the bg cells next to the seed are left unpainted", skip_cells_next_to_seed),
    ("color follows row parity alone", row_parity_stripes),
    ("only flooded cells in the center's row or column are painted", row_and_column_of_center_only),
    ("the grid is left unchanged", unchanged),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b782dc8a.json").read_text())
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(train), desc)
