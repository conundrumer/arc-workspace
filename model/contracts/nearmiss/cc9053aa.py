"""Near-miss rules for cc9053aa: a route of wall cells joins two edge markers
and avoids cells next to hazards; the route is painted in the marker color."""
import json
from collections import Counter, deque
from pathlib import Path

N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
N8 = N4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def roles(inp, out):
    h, w = len(inp), len(inp[0])
    diff = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != out[r][c]]
    wall = inp[diff[0][0]][diff[0][1]]
    ink = out[diff[0][0]][diff[0][1]]
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    hazard = [k for k in cnt if k not in (bg, wall, ink)][0]
    markers = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == ink]
    return h, w, bg, wall, ink, hazard, markers, set(diff)


def paint(inp, cells, color):
    g = [row[:] for row in inp]
    for r, c in cells:
        g[r][c] = color
    return g


def bfs(start, ok, dirs, h, w):
    dist = {start: 0}
    q = deque([start])
    while q:
        r, c = q.popleft()
        for dr, dc in dirs:
            p = (r + dr, c + dc)
            if 0 <= p[0] < h and 0 <= p[1] < w and p not in dist and ok(p):
                dist[p] = dist[(r, c)] + 1
                q.append(p)
    return dist


def fewest_cells(inp, walkable, dirs, markers, h, w):
    """Cells on the fewest-step walks between the two markers (union)."""
    a, b = markers
    ok = lambda p: p in walkable or p in (a, b)
    da = bfs(a, ok, dirs, h, w)
    db = bfs(b, ok, dirs, h, w)
    if b not in da:
        return None
    d = da[b]
    return {p for p in da if p in db and da[p] + db[p] == d}


def walls_where(inp, wall, hazard, radius_dirs, h, w):
    ws = set()
    for r in range(h):
        for c in range(w):
            if inp[r][c] != wall:
                continue
            bad = False
            for dr, dc in radius_dirs:
                rr, cc = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] == hazard:
                    bad = True
            if not bad:
                ws.add((r, c))
    return ws


def wrong_result(g, out):
    return g if g != out else None


def revert_contacts(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    contacts = [p for p in route if any((p[0] + dr, p[1] + dc) in mk for dr, dc in N4)]
    g = [row[:] for row in out]
    for r, c in contacts:
        g[r][c] = inp[r][c]
    return g


def hazard_4adj(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    ws = walls_where(inp, wall, hz, N4, h, w)
    cells = fewest_cells(inp, ws, N4, mk, h, w)
    return None if cells is None else paint(inp, cells - set(mk), ink)


def hazard_self_only(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    ws = walls_where(inp, wall, hz, [(0, 0)], h, w)
    cells = fewest_cells(inp, ws, N4, mk, h, w)
    return None if cells is None else paint(inp, cells - set(mk), ink)


def ignore_hazards(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    ws = {(r, c) for r in range(h) for c in range(w) if inp[r][c] in (wall, hz)}
    cells = fewest_cells(inp, ws, N4, mk, h, w)
    return None if cells is None else paint(inp, cells - set(mk), ink)


def diagonal_steps(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    ws = walls_where(inp, wall, hz, N8, h, w)
    cells = fewest_cells(inp, ws, N8, mk, h, w)
    return None if cells is None else paint(inp, cells - set(mk), ink)


def all_reachable_clear(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    ws = walls_where(inp, wall, hz, N8, h, w)
    ok = lambda p: p in ws or p in mk
    seen = set()
    for m in mk:
        seen |= set(bfs(m, ok, N4, h, w))
    return paint(inp, seen - set(mk), ink)


def route_in_hazard_color(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    return paint(inp, route, hz)


def route_in_wall_color_removed(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    return paint(inp, route, bg)


def whole_wall_recolored(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    cells = {(r, c) for r in range(h) for c in range(w) if inp[r][c] == wall}
    return paint(inp, cells, ink)


def first_half_only(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    a = mk[0]
    cells = sorted(route, key=lambda p: abs(p[0] - a[0]) + abs(p[1] - a[1]))
    keep = cells[: len(cells) // 2]
    return paint(inp, keep, ink)


def straight_L_between_markers(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    (r1, c1), (r2, c2) = mk
    cells = set()
    for c in range(min(c1, c2), max(c1, c2) + 1):
        cells.add((r1, c))
    for r in range(min(r1, r2), max(r1, r2) + 1):
        cells.add((r, c2))
    return paint(inp, cells - set(mk), ink)


def thick_route(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    cells = set(route)
    for r, c in route:
        for dr, dc in N4:
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] == wall:
                cells.add((rr, cc))
    return paint(inp, cells, ink)


def paint_closed_walls(inp, out):
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    clear = walls_where(inp, wall, hz, N8, h, w)
    closed = {(r, c) for r in range(h) for c in range(w) if inp[r][c] == wall} - clear
    return paint(inp, closed, ink)


def fewest_turns(inp, out):
    """Fewest turns first, then fewest hops, through clear wall cells."""
    import heapq
    h, w, bg, wall, ink, hz, mk, route = roles(inp, out)
    ws = walls_where(inp, wall, hz, N8, h, w)
    a, b = mk
    ok = lambda p: p in ws or p in (a, b)
    best = {}
    pq = [(0, 0, a, None, (a,))]
    while pq:
        t, n, p, d, path = heapq.heappop(pq)
        if p == b:
            return paint(inp, set(path) - set(mk), ink)
        if (p, d) in best:
            continue
        best[(p, d)] = t
        for nd in N4:
            q = (p[0] + nd[0], p[1] + nd[1])
            if 0 <= q[0] < h and 0 <= q[1] < w and ok(q):
                heapq.heappush(pq, (t + (1 if d is not None and nd != d else 0), n + 1, q, nd, path + (q,)))
    return None


ALTERNATIVES = [
    ("route leaves its contact cells next to the markers unpainted", revert_contacts),
    ("route also paints every wall cell 4-adjacent to it", thick_route),
    ("hazard closes only the wall cell it sits in, not its neighbors", hazard_self_only),
    ("hazards are ignored and the route may cross them", ignore_hazards),
    ("route may step diagonally between clear wall cells", diagonal_steps),
    ("every clear wall cell reachable from the markers is painted", all_reachable_clear),
    ("route is painted in the hazard color", route_in_hazard_color),
    ("route cells are erased to background instead of painted", route_in_wall_color_removed),
    ("the whole wall network is painted in the marker color", whole_wall_recolored),
    ("only the half of the route nearer the first marker is painted", first_half_only),
    ("markers are joined by a straight L ignoring the walls", straight_L_between_markers),
    ("the wall cells next to hazards are painted instead of the route", paint_closed_walls),
]


def valid(g, out):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/cc9053aa.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
