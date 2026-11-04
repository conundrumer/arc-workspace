from pathlib import Path
import json
from collections import Counter

DIRS = [(-1, 0), (0, 1), (1, 0), (0, -1)]  # up, right, down, left


def _setup(inp):
    cnt = Counter(c for r in inp for c in r)
    seed = min(cnt, key=lambda c: cnt[c])
    wall = [c for c in cnt if c != seed and c != 7]
    wall = wall[0] if wall else 8
    return seed, wall


def _blocked(inp, wall, r, c):
    return not (0 <= r < len(inp) and 0 <= c < len(inp[0])) or inp[r][c] == wall


def _run(inp, wall, r, c, d):
    """Cells walked from (r,c) in direction d until the next cell is blocked."""
    cells = [(r, c)]
    while True:
        nr, nc = cells[-1][0] + DIRS[d][0], cells[-1][1] + DIRS[d][1]
        if _blocked(inp, wall, nr, nc):
            return cells
        cells.append((nr, nc))


def _starts(inp, seed):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == seed]
    out = []
    for (r, c) in cells:
        for d, (dr, dc) in enumerate(DIRS):
            if (r + dr, c + dc) in cells:
                out.append((r, c, d))
    return out  # start cell, direction toward the other seed cell


def _sim(inp, rule="correct", first=0, max_legs=40, only_start=None):
    seed, wall = _setup(inp)
    starts = _starts(inp, seed)
    if only_start is not None:
        starts = [starts[only_start % len(starts)]]
    legs = []
    for (r, c, d) in starts:
        pos, dd, seen, n = (r, c), d, set(), 0
        while n < max_legs and (pos, dd) not in seen:
            seen.add((pos, dd))
            cells = _run(inp, wall, pos[0], pos[1], dd)
            legs.append(cells)
            n += 1
            e = cells[-1]
            nxt = None
            for p in ((dd + 1) % 4, (dd + 3) % 4):
                a = (e[0] + DIRS[p][0], e[1] + DIRS[p][1])
                b = (e[0] - DIRS[p][0], e[1] - DIRS[p][1])
                ok_a = not _blocked(inp, wall, *a)
                ok_b = not _blocked(inp, wall, *b)
                if rule == "correct" and ok_a and not ok_b:
                    nxt = p
                    break
                if rule == "anyopen" and ok_a:
                    nxt = p
                    break
                if rule == "wrongside" and ok_a and ok_b:
                    nxt = p
                    break
            if nxt is None:
                break
            pos, dd = e, nxt
    return legs, seed, wall


def _paint(inp, cells, color):
    g = [row[:] for row in inp]
    for (r, c) in cells:
        if inp[r][c] != 8 and not (inp[r][c] not in (7,) and False):
            g[r][c] = color
    return g


def _paint_open(inp, cells, color, wall):
    g = [row[:] for row in inp]
    for (r, c) in cells:
        if g[r][c] != wall:
            g[r][c] = color
    return g


def correct_cells(inp):
    legs, seed, wall = _sim(inp)
    return [p for l in legs for p in l], seed, wall


def alt_other_start(inp, out):
    legs, seed, wall = _sim(inp, only_start=1)
    return _paint_open(inp, [p for l in legs for p in l], seed, wall)


def alt_first_leg(inp, out):
    legs, seed, wall = _sim(inp, only_start=0)
    return _paint_open(inp, legs[0], seed, wall)


def alt_two_legs(inp, out):
    legs, seed, wall = _sim(inp, only_start=0)
    return _paint_open(inp, [p for l in legs[:2] for p in l], seed, wall)


def alt_path_wall_color(inp, out):
    cells, seed, wall = correct_cells(inp)
    return _paint_open(inp, cells, wall, wall)


def alt_no_corners(inp, out):
    legs, seed, wall = _sim(inp)
    corners = {l[-1] for l in legs[:-1]} | {l[0] for l in legs[1:]}
    cells = [p for l in legs for p in l if p not in corners]
    return _paint_open(inp, cells, seed, wall)


def alt_last_leg_short(inp, out):
    legs, seed, wall = _sim(inp)
    cells = [p for l in legs[:-1] for p in l] + legs[-1][:-1]
    return _paint_open(inp, cells, seed, wall)


def alt_flood_region(inp, out):
    seed, wall = _setup(inp)
    start = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == seed]
    seen, st = set(start), list(start)
    while st:
        r, c = st.pop()
        for dr, dc in DIRS:
            n = (r + dr, c + dc)
            if not _blocked(inp, wall, *n) and n not in seen:
                seen.add(n)
                st.append(n)
    return _paint_open(inp, seen, seed, wall)


def alt_cross(inp, out):
    seed, wall = _setup(inp)
    cells = set()
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == seed:
                for d in range(4):
                    cells.update(_run(inp, wall, r, c, d))
    return _paint_open(inp, cells, seed, wall)


def alt_turn_any_open(inp, out):
    legs, seed, wall = _sim(inp, rule="anyopen", max_legs=12)
    return _paint_open(inp, [p for l in legs for p in l], seed, wall)


def alt_turn_wrong_side(inp, out):
    legs, seed, wall = _sim(inp, rule="wrongside")
    return _paint_open(inp, [p for l in legs for p in l], seed, wall)


def alt_transpose(inp, out):
    return [list(r) for r in zip(*out)]


def alt_mirror_rows(inp, out):
    return [r[::-1] for r in out]


def alt_seed_erased(inp, out):
    seed, wall = _setup(inp)
    g = [row[:] for row in out]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == seed:
                g[r][c] = 7
    return g


ALTERNATIVES = [
    ("walker leaves the seed pair in the opposite direction", alt_other_start),
    ("only the first straight run through the seed is painted", alt_first_leg),
    ("walker stops after the second straight run", alt_two_legs),
    ("path is painted in the wall color instead of the seed color", alt_path_wall_color),
    ("corner cells where the walker turns are left unpainted", alt_no_corners),
    ("final straight run stops one cell short of the wall", alt_last_leg_short),
    ("whole open region reachable from the seed is filled", alt_flood_region),
    ("seed shoots a cross of runs in all four directions", alt_cross),
    ("walker turns at every run end that has any open side", alt_turn_any_open),
    ("walker turns only where both sides are open", alt_turn_wrong_side),
    ("output is transposed (wrong orientation)", alt_transpose),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if any(len(r) != len(g[0]) or len(r) == 0 for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/6bcdb01e.json')))
    pairs = t["train"]
    legs_ok = []
    for p in pairs:
        cells, seed, wall = correct_cells(p["input"])
        g = _paint_open(p["input"], cells, seed, wall)
        legs_ok.append(g == p["output"])
    print("simulator reproduces true output per pair:", legs_ok)
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
