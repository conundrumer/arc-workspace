"""Near-miss rules for task 825aa9e9.

Rule: the color that touches the bottom edge is the floor. Every other
non-background shape (4-connected) falls down as a rigid body until one empty
row is left between it and the floor or the grid bottom.
"""
import json
from pathlib import Path

BG = 7


def _floor_color(inp):
    cols = [c for c in inp[-1] if c != BG]
    return cols[0] if cols else None


def _bodies(inp, floor):
    h, w = len(inp), len(inp[0])
    seen = set()
    out = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] in (BG, floor) or (r, c) in seen:
                continue
            stack, comp = [(r, c)], []
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if (0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen
                            and inp[ny][nx] not in (BG, floor)):
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            out.append(comp)
    return out


def _free_steps(blocked, h, w, y, x, dy, dx):
    k = 0
    while True:
        ny, nx = y + dy * (k + 1), x + dx * (k + 1)
        if not (0 <= ny < h and 0 <= nx < w) or (ny, nx) in blocked:
            return k
        k += 1


def _distances(inp, bodies, floor, d, gap, floor_cells=None, mover_gap=None):
    """Distance each body moves along direction d, bodies settled in order."""
    h, w = len(inp), len(inp[0])
    dy, dx = d
    if floor_cells is None:
        floor_cells = {(r, c) for r in range(h) for c in range(w)
                       if inp[r][c] == floor}
    if mover_gap is None:
        mover_gap = gap
    order = sorted(range(len(bodies)),
                   key=lambda i: -max(y * dy + x * dx for y, x in bodies[i]))
    settled = set()
    dist = {}
    for i in order:
        best = None
        for y, x in bodies[i]:
            blocked = floor_cells | settled
            f = _free_steps(blocked, h, w, y, x, dy, dx)
            # Gap against settled movers may differ from the gap against floor.
            ny, nx = y + dy * (f + 1), x + dx * (f + 1)
            g = mover_gap if (ny, nx) in settled else gap
            v = max(0, f - g)
            best = v if best is None else min(best, v)
        dist[i] = best or 0
        for y, x in bodies[i]:
            settled.add((y + dy * dist[i], x + dx * dist[i]))
    return dist


def _render(inp, bodies, dist, d, recolor=None, keep_trail=False):
    dy, dx = d
    g = [row[:] for row in inp]
    if not keep_trail:
        for b in bodies:
            for y, x in b:
                g[y][x] = BG
    for i, b in enumerate(bodies):
        for y, x in b:
            ny, nx = y + dy * dist[i], x + dx * dist[i]
            g[ny][nx] = inp[y][x] if recolor is None else recolor
    return g


def _fall(inp, d=(1, 0), gap=1, **kw):
    floor = _floor_color(inp)
    bodies = _bodies(inp, floor)
    dist = _distances(inp, bodies, floor, d, gap)
    return _render(inp, bodies, dist, d, **kw)


# ---- wrong readings -------------------------------------------------------

def gap_zero(inp, out):
    return _fall(inp, gap=0)


def gap_two(inp, out):
    return _fall(inp, gap=2)


def gap_is_height(inp, out):
    floor = _floor_color(inp)
    bodies = _bodies(inp, floor)
    g = [row[:] for row in inp]
    for b in bodies:
        for y, x in b:
            g[y][x] = BG
    dists = []
    for i, b in enumerate(bodies):
        height = max(y for y, _ in b) - min(y for y, _ in b) + 1
        dists.append(_distances(inp, [b], floor, (1, 0), height)[0])
    for b, dd in zip(bodies, dists):
        for y, x in b:
            g[y + dd][x] = inp[y][x]
    return g


def only_bottom_edge_is_floor(inp, out):
    h, w = len(inp), len(inp[0])
    floor = _floor_color(inp)
    bodies = _bodies(inp, floor)
    dist = _distances(inp, bodies, floor, (1, 0), 1, floor_cells=set())
    g = [row[:] for row in inp]
    for b in bodies:
        for y, x in b:
            g[y][x] = BG
    for i, b in enumerate(bodies):
        for y, x in b:
            g[y + dist[i]][x] = inp[y][x]
    return g


def copy_not_move(inp, out):
    return _fall(inp, keep_trail=True)


def only_largest_moves(inp, out):
    floor = _floor_color(inp)
    bodies = _bodies(inp, floor)
    dist = _distances(inp, bodies, floor, (1, 0), 1)
    big = max(range(len(bodies)), key=lambda i: len(bodies[i]))
    dist = {i: (v if i == big else 0) for i, v in dist.items()}
    return _render(inp, bodies, dist, (1, 0))


def all_fall_max_distance(inp, out):
    floor = _floor_color(inp)
    bodies = _bodies(inp, floor)
    dist = _distances(inp, bodies, floor, (1, 0), 1)
    m = max(dist.values())
    h = len(inp)
    for i, b in enumerate(bodies):
        m = min(m, h - 1 - max(y for y, _ in b))
    return _render(inp, bodies, {i: m for i in dist}, (1, 0))


def same_color_rigid(inp, out):
    floor = _floor_color(inp)
    bodies = _bodies(inp, floor)
    dist = _distances(inp, bodies, floor, (1, 0), 1)
    by_col = {}
    for i, b in enumerate(bodies):
        by_col.setdefault(inp[b[0][0]][b[0][1]], []).append(i)
    shared = {}
    for ids in by_col.values():
        m = min(dist[i] for i in ids)
        for i in ids:
            shared[i] = m
    return _render(inp, bodies, shared, (1, 0))


def slide_right(inp, out):
    return _fall(inp, d=(0, 1))


def slide_left(inp, out):
    return _fall(inp, d=(0, -1))


def cells_fall_separately(inp, out):
    floor = _floor_color(inp)
    bodies = [[p] for b in _bodies(inp, floor) for p in b]
    dist = _distances(inp, bodies, floor, (1, 0), 1, mover_gap=0)
    return _render(inp, bodies, dist, (1, 0))


def landed_take_floor_color(inp, out):
    floor = _floor_color(inp)
    return _fall(inp, recolor=floor)


ALTERNATIVES = [
    ("clearance of zero rows: shapes rest directly on the floor", gap_zero),
    ("clearance of two rows under each shape", gap_two),
    ("clearance equals the shape's own height", gap_is_height),
    ("only the grid's bottom edge stops shapes; side and partial floor cells are ignored", only_bottom_edge_is_floor),
    ("shapes are copied down, original cells stay painted", copy_not_move),
    ("only the largest shape falls", only_largest_moves),
    ("every shape falls by the same, largest, distance", all_fall_max_distance),
    ("shapes of one color fall together as one body", same_color_rigid),
    ("shapes slide right instead of falling down", slide_right),
    ("shapes slide left instead of falling down", slide_left),
    ("each cell falls on its own instead of whole shapes", cells_fall_separately),
    ("landed shapes take the floor color", landed_take_floor_color),
]


def _drop_equal(fn):
    def wrapped(inp, out):
        g = fn(inp, out)
        return None if g == out else g
    wrapped.__name__ = fn.__name__
    return wrapped


ALTERNATIVES = [(d, _drop_equal(f)) for d, f in ALTERNATIVES]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/825aa9e9.json").read_text())
    pairs = task["train"]
    ref = [_fall(p["input"]) == p["output"] for p in pairs]
    print("reference (gap 1 fall) matches true output per pair:", ref)
    print("readings:", len(ALTERNATIVES), "pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn([r[:] for r in p["input"]], [r[:] for r in p["output"]])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
