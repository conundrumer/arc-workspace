"""Near-miss readings for task 3ad05f52.

Rule: 8-walls enclose rooms; a gap in a wall (a door) joins two rooms. Paint
spreads from the painted room through doors into every connected room, and
across the open ground between outward doors.
"""
import json
from collections import deque
from pathlib import Path

WALL = 8
N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
N8 = N4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _setup(inp, door_mode="both"):
    h, w = len(inp), len(inp[0])
    wall = {(r, c) for r in range(h) for c in range(w) if inp[r][c] == WALL}
    doors = set()
    for r in range(h):
        for c in range(w):
            if (r, c) in wall:
                continue
            lr = (r, c - 1) in wall and (r, c + 1) in wall
            ud = (r - 1, c) in wall and (r + 1, c) in wall
            if (door_mode in ("both", "lr") and lr) or (door_mode in ("both", "ud") and ud):
                doors.add((r, c))
    free = {(r, c) for r in range(h) for c in range(w)} - wall - doors
    comps, seen = [], set()
    for p in sorted(free):
        if p in seen:
            continue
        comp, q = {p}, deque([p])
        seen.add(p)
        while q:
            a, b = q.popleft()
            for dr, dc in N4:
                n = (a + dr, b + dc)
                if n in free and n not in seen:
                    seen.add(n)
                    comp.add(n)
                    q.append(n)
        comps.append(comp)
    outside = max(comps, key=len)
    paint = {inp[r][c] for r in range(h) for c in range(w)} - {0, WALL}
    src = [(r, c) for r in range(h) for c in range(w) if inp[r][c] in paint]
    col = min(paint)
    return h, w, wall, doors, free, outside, src, col


def _bbox(cells):
    rs = [p[0] for p in cells]
    cs = [p[1] for p in cells]
    return min(rs), max(rs), min(cs), max(cs)


def _outward(doors, outside):
    return {d for d in doors if any((d[0] + dr, d[1] + dc) in outside for dr, dc in N4)}


def _crossing(inp, mode="span", grow=0, door_mode="both"):
    h, w, wall, doors, free, outside, src, col = _setup(inp, door_mode)
    od = _outward(doors, outside)
    if mode == "none" or not od:
        return set()
    if mode == "alldoors":
        r0, r1, c0, c1 = _bbox(doors)
    elif mode == "line":
        cells = set()
        for a in od:
            for b in od:
                if a < b and (a[0] == b[0] or a[1] == b[1]):
                    for r in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                        for c in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                            if (r, c) in outside:
                                cells.add((r, c))
        return cells
    else:
        r0, r1, c0, c1 = _bbox(od)
    r0 -= grow
    c0 -= grow
    r1 += grow
    c1 += grow
    return {p for p in outside if r0 <= p[0] <= r1 and c0 <= p[1] <= c1}


def _flood(inp, crossing_mode="span", grow=0, door_mode="both", nbrs=N4,
           doors_open=True, max_doors=None, whole_outside=False):
    h, w, wall, doors, free, outside, src, col = _setup(inp, door_mode)
    cross = _crossing(inp, crossing_mode, grow, door_mode)
    if whole_outside:
        cross = set(outside)
    nodes = (free - outside) | (doors if doors_open else set()) | cross
    nodes |= set(src) if crossing_mode != "none" else set(src) & (free - outside)
    start = [p for p in src if p in nodes]
    cost = {p: 0 for p in start}
    q = deque(start)
    while q:
        a = q.popleft()
        for dr, dc in nbrs:
            n = (a[0] + dr, a[1] + dc)
            if n in nodes and n not in cost:
                k = cost[a] + (1 if n in doors else 0)
                if max_doors is not None and k > max_doors:
                    continue
                cost[n] = k
                q.append(n)
    res = [row[:] for row in inp]
    for (r, c) in cost:
        res[r][c] = col
    return res


def correct(inp):
    return _flood(inp)


# ---- wrong readings -------------------------------------------------------

def no_ground_crossing(inp, out):
    return _flood(inp, crossing_mode="none")


def rooms_only_no_doors_open(inp, out):
    return _flood(inp, doors_open=False, crossing_mode="none")


def one_door_hop(inp, out):
    return _flood(inp, max_doors=1)


def whole_ground_floods(inp, out):
    return _flood(inp, whole_outside=True)


def eight_connected_flood(inp, out):
    return _flood(inp, nbrs=N8)


def box_of_all_doors(inp, out):
    return _flood(inp, crossing_mode="alldoors")


def straight_line_only(inp, out):
    return _flood(inp, crossing_mode="line")


def box_grown_by_one(inp, out):
    return _flood(inp, grow=1)


def only_side_gaps_are_doors(inp, out):
    return _flood(inp, door_mode="lr")


def only_top_bottom_gaps_are_doors(inp, out):
    return _flood(inp, door_mode="ud")


def fill_every_room(inp, out):
    h, w, wall, doors, free, outside, src, col = _setup(inp)
    res = [row[:] for row in out]
    for (r, c) in (free - outside) | doors:
        res[r][c] = col
    return res


def doors_left_open(inp, out):
    h, w, wall, doors, free, outside, src, col = _setup(inp)
    res = [row[:] for row in out]
    for (r, c) in doors:
        if (r, c) not in set(src):
            res[r][c] = inp[r][c]
    return res


def crop_to_content(inp, out):
    r0, r1, c0, c1 = _bbox([(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v])
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("paint stays in rooms and doors, never crosses the open ground", no_ground_crossing),
    ("doors do not pass paint, so only the source room is painted", rooms_only_no_doors_open),
    ("paint passes through one door only", one_door_hop),
    ("paint floods the whole open ground reached by an outward door", whole_ground_floods),
    ("ground painted in the box of all doors, not just outward doors", box_of_all_doors),
    ("ground painted along the straight line between door pairs only", straight_line_only),
    ("ground box is one cell larger on each side", box_grown_by_one),
    ("only gaps with walls left and right count as doors", only_side_gaps_are_doors),
    ("every enclosed room is painted, reached or not", fill_every_room),
    ("door cells are left unpainted", doors_left_open),
    ("input returned unchanged", unchanged),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/3ad05f52.json").read_text())
    pairs = task["train"]
    print("correct solver reproduces:", [correct(p["input"]) == p["output"] for p in pairs])
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
