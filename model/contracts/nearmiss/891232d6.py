import json
from pathlib import Path

WALL = 7
MARKER = 6


def _copy(g):
    return [row[:] for row in g]


def _sim(inp, side=1, turns=None, extra=0):
    """Replay the rule: climb up from each marker; at a wall, mark it 8, mark
    the cell under it 4, slide sideways under the wall, then climb again."""
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r0 in range(h):
        for c0 in range(w):
            if inp[r0][c0] != MARKER:
                continue
            r, c, k = r0, c0, 0
            while True:
                path = [(r, c)]
                while r - 1 >= 0 and inp[r - 1][c] != WALL:
                    r -= 1
                    path.append((r, c))
                for pr, pc in path[1:-1]:
                    g[pr][pc] = 2
                if r == 0:
                    g[r][c] = 6
                    break
                if turns is not None and k >= turns:
                    g[r][c] = 6
                    break
                cs = c + side
                while 0 <= cs < w and inp[r][cs] != WALL and inp[r - 1][cs] == WALL:
                    cs += side
                if extra and 0 <= cs < w and inp[r][cs] != WALL:
                    cs += side * extra
                if not (0 <= cs < w) or inp[r][cs] == WALL:
                    g[r][c] = 6
                    break
                g[r - 1][c] = 8
                g[r][c] = 4
                lo, hi = sorted((c + side, cs))
                for x in range(lo, hi + 1):
                    if x != cs:
                        g[r][x] = 2
                g[r][cs] = 3
                c = cs
                k += 1
    return g


def _slide_left(inp, out):
    return _sim(inp, side=-1)


def _straight(inp, out):
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r0 in range(h):
        for c0 in range(w):
            if inp[r0][c0] == MARKER:
                for r in range(r0 - 1, -1, -1):
                    if inp[r][c0] != WALL:
                        g[r][c0] = 2
                g[0][c0] = 6
    return g


def _stop_first_wall(inp, out):
    return _sim(inp, turns=0)


def _one_turn(inp, out):
    return _sim(inp, turns=1)


def _recolor(out, old, new, keep_if=None):
    g = _copy(out)
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v == old:
                g[r][c] = new
    return g


def _corner_as_trail(inp, out):
    return _recolor(out, 4, 2)


def _wall_not_marked(inp, out):
    return _recolor(out, 8, 7)


def _onward_as_trail(inp, out):
    return _recolor(out, 3, 2)


def _no_end_marker(inp, out):
    g = _copy(out)
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v == 6 and inp[r][c] != 6:
                g[r][c] = 2
    return g


def _slide_one_extra(inp, out):
    return _sim(inp, extra=1)


def _swap_hit_and_corner(inp, out):
    g = _copy(out)
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v == 8:
                g[r][c] = 4
            elif v == 4:
                g[r][c] = 8
    return g


def _whole_wall_hit(inp, out):
    g = _copy(out)
    for r, row in enumerate(out):
        for c, v in enumerate(row):
            if v == 8:
                for step in (-1, 1):
                    x = c + step
                    while 0 <= x < len(row) and out[r][x] == WALL:
                        g[r][x] = 8
                        x += step
    return g


ALTERNATIVES = [
    ("slide goes left under the wall instead of right", _slide_left),
    ("beam goes straight up to the top edge through the walls", _straight),
    ("beam stops at the first wall with no turn", _stop_first_wall),
    ("beam turns at the first wall only, then stops at the second", _one_turn),
    ("cell under the wall is painted as trail 2 instead of 4", _corner_as_trail),
    ("hit wall cell is left as 7", _wall_not_marked),
    ("cell where the climb resumes is painted as trail 2 instead of 3", _onward_as_trail),
    ("beam end cells are painted as trail instead of marker 6", _no_end_marker),
    ("slide runs one cell past the wall edge before climbing", _slide_one_extra),
    ("hit color 8 and corner color 4 are swapped", _swap_hit_and_corner),
    ("the whole wall segment is painted 8 instead of one cell", _whole_wall_hit),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/891232d6.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(_copy(p["input"]), _copy(p["output"]))
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
