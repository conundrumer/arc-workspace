import json
from collections import Counter
from pathlib import Path

UP, RIGHT, LEFT = (-1, 0), (0, 1), (0, -1)


def _info(inp, out):
    """Walker color, walker start cell, background color, wall color or None."""
    h, w = len(inp), len(inp[0])
    diff = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != out[r][c]]
    col = out[diff[0][0]][diff[0][1]]
    start = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == col][0]
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    walls = [v for v in cnt if v not in (bg, col)]
    return col, start, bg, (walls[0] if walls else None)


def _walk(inp, start, bg, dirs, on_wall="turn", edge="stop", ignore_walls=False):
    """Staircase walk; returns the ordered list of cells visited."""
    h, w = len(inp), len(inp[0])
    pos, i = start, 0
    cells = [pos]
    seen = set()
    while (pos, i) not in seen:
        seen.add((pos, i))
        d = dirs[i]
        q = (pos[0] + d[0], pos[1] + d[1])
        inside = 0 <= q[0] < h and 0 <= q[1] < w
        if not inside:
            if edge == "stop":
                break
            i = 1 - i  # bounce: turn in place like at a wall
            continue
        if inp[q[0]][q[1]] != bg and not ignore_walls:
            if on_wall == "stop":
                break
            if on_wall == "double":
                # turn and step in the other direction, but keep that direction next
                d2 = dirs[1 - i]
                q2 = (pos[0] + d2[0], pos[1] + d2[1])
                if 0 <= q2[0] < h and 0 <= q2[1] < w and inp[q2[0]][q2[1]] == bg:
                    pos = q2
                    cells.append(pos)
                    i = 1 - i
                    continue
                break
            i = 1 - i
            continue
        pos = q
        cells.append(pos)
        i = 1 - i
    return cells


def _paint(inp, cells, color, keep_start=True):
    g = [row[:] for row in inp]
    for r, c in cells:
        g[r][c] = color
    return g


def _run(inp, out, dirs=(UP, RIGHT), **kw):
    col, start, bg, wall = _info(inp, out)
    return col, start, bg, wall, _walk(inp, start, bg, list(dirs), **kw)


def first_axis_right(inp, out):
    col, s, bg, wall, cells = _run(inp, out, dirs=(RIGHT, UP))
    return _paint(inp, cells, col)


def ignore_walls(inp, out):
    col, s, bg, wall, cells = _run(inp, out, ignore_walls=True)
    return _paint(inp, cells, col)


def stop_at_wall(inp, out):
    col, s, bg, wall, cells = _run(inp, out, on_wall="stop")
    return _paint(inp, cells, col)


def double_step(inp, out):
    col, s, bg, wall, cells = _run(inp, out, on_wall="double")
    return _paint(inp, cells, col)


def edge_bounce(inp, out):
    col, s, bg, wall, cells = _run(inp, out, edge="turn")
    return _paint(inp, cells, col)


def wrong_color(inp, out):
    col, s, bg, wall, cells = _run(inp, out)
    new = wall if wall is not None else 1
    g = [row[:] for row in out]
    for r, c in cells:
        g[r][c] = new
    return g


def walls_erased(inp, out):
    col, s, bg, wall, cells = _run(inp, out)
    if wall is None:
        return None
    return [[bg if v == wall else v for v in row] for row in out]


def start_erased(inp, out):
    col, s, bg, wall, cells = _run(inp, out)
    g = [row[:] for row in out]
    g[s[0]][s[1]] = bg
    return g


def mirrored_left(inp, out):
    col, s, bg, wall, cells = _run(inp, out, dirs=(UP, LEFT))
    return _paint(inp, cells, col)


def diagonal_ray(inp, out):
    col, s, bg, wall, _ = _run(inp, out)
    h, w = len(inp), len(inp[0])
    r, c = s
    cells = [s]
    while True:
        r, c = r - 1, c + 1
        if not (0 <= r < h and 0 <= c < w) or inp[r][c] != bg:
            break
        cells.append((r, c))
    return _paint(inp, cells, col)


def one_short(inp, out):
    col, s, bg, wall, cells = _run(inp, out)
    return _paint(inp, cells[:-1], col)


ALTERNATIVES = [
    ("first move goes right instead of up", first_axis_right),
    ("walker passes through walls", ignore_walls),
    ("walker stops when it meets a wall", stop_at_wall),
    ("at a wall the walker steps sideways and keeps going sideways", double_step),
    ("grid edge turns the walker instead of ending the path", edge_bounce),
    ("path drawn in the wall color (or 1) instead of the walker color", wrong_color),
    ("wall cells are erased", walls_erased),
    ("walker's start cell is erased", start_erased),
    ("staircase goes up-left instead of up-right", mirrored_left),
    ("path is a single diagonal ray that ends at a wall", diagonal_ray),
    ("path is one cell short", one_short),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/69889d6e.json"))
    pairs = task["train"]
    # sanity: the correct walk reproduces the true output
    for k, p in enumerate(pairs):
        col, s, bg, wall, cells = _run(p["input"], p["output"])
        assert _paint(p["input"], cells, col) == p["output"], k
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if (
                g is not None
                and len({len(r) for r in g}) == 1
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                and g != p["output"]
            ):
                n += 1
        print(n, desc)
