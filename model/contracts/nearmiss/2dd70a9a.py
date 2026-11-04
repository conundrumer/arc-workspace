from pathlib import Path
import json

SRC, TGT = 3, 2


def cells_of(g, c):
    return [(r, k) for r, row in enumerate(g) for k, v in enumerate(row) if v == c]


def ray(g, start, d):
    """Open cells walked from start in direction d until a non-zero cell or the edge."""
    h, w = len(g), len(g[0])
    r, c = start
    res = []
    while True:
        r, c = r + d[0], c + d[1]
        if not (0 <= r < h and 0 <= c < w) or g[r][c] != 0:
            return res
        res.append((r, c))


def ends(inp):
    s = sorted(cells_of(inp, SRC))
    if len(s) < 2:
        return []
    a, b = s[0], s[-1]
    d = (b[0] - a[0], b[1] - a[1])
    d = ((d[0] > 0) - (d[0] < 0), (d[1] > 0) - (d[1] < 0))
    return [(a, (-d[0], -d[1])), (b, d)]


def path_info(inp, out):
    """Returns (start_dir_pair, ordered path cells, incoming move per cell) or None."""
    diff = {(r, c) for r in range(len(out)) for c in range(len(out[0]))
            if out[r][c] != inp[r][c]}
    for (st, d) in ends(inp):
        first = ray(inp, st, d)
        if first and all(x in diff for x in first):
            order = list(first)
            moves = [d] * len(first)
            seen = set(order)
            cur, cd = order[-1], d
            while True:
                nxt = None
                cand = [cd] + [m for m in ((0, 1), (0, -1), (1, 0), (-1, 0)) if m != cd]
                for m in cand:
                    q = (cur[0] + m[0], cur[1] + m[1])
                    if q in diff and q not in seen:
                        nxt = (q, m)
                        break
                if not nxt:
                    break
                order.append(nxt[0])
                moves.append(nxt[1])
                seen.add(nxt[0])
                cur, cd = nxt
            if seen != diff:
                return None
            return (st, d), order, moves
    return None


def paint(inp, cells, col):
    g = [row[:] for row in inp]
    for r, c in cells:
        g[r][c] = col
    return g


def keep_cells(inp, out, keep):
    pi = path_info(inp, out)
    if pi is None:
        return None
    return paint(inp, [x for x in keep(pi)], SRC)


def path_color_2(inp, out):
    pi = path_info(inp, out)
    return paint(inp, pi[1], TGT) if pi else None


def path_color_8(inp, out):
    pi = path_info(inp, out)
    return paint(inp, pi[1], 8) if pi else None


def first_leg_only(inp, out):
    return keep_cells(inp, out, lambda pi: ray(inp, pi[0][0], pi[0][1]))


def drop_last_leg(inp, out):
    def k(pi):
        _, order, moves = pi
        last = moves[-1]
        n = len(moves)
        while n > 0 and moves[n - 1] == last:
            n -= 1
        return order[:n]
    return keep_cells(inp, out, k)


def one_short(inp, out):
    return keep_cells(inp, out, lambda pi: pi[1][:-1])


def opposite_end_ray(inp, out):
    pi = path_info(inp, out)
    if not pi:
        return None
    (st, d), _, _ = pi
    for (s2, d2) in ends(inp):
        if (s2, d2) != (st, d):
            cells = ray(inp, s2, d2)
            return paint(inp, cells, SRC) if cells else None
    return None


def ray_through_walls(inp, out):
    pi = path_info(inp, out)
    if not pi:
        return None
    (st, d), _, _ = pi
    h, w = len(inp), len(inp[0])
    r, c = st
    cells = []
    while True:
        r, c = r + d[0], c + d[1]
        if not (0 <= r < h and 0 <= c < w):
            break
        cells.append((r, c))
    return paint(inp, cells, SRC)


def wrong_turn(inp, out):
    pi = path_info(inp, out)
    if not pi:
        return None
    (st, d), order, moves = pi
    first = ray(inp, st, d)
    turn = next((m for m in moves if m != d), None)
    if turn is None:
        return None
    opp = (-turn[0], -turn[1])
    second = ray(inp, first[-1], opp)
    return paint(inp, first + second, SRC)


def l_shape_ignoring_walls(inp, out):
    pi = path_info(inp, out)
    if not pi:
        return None
    (st, d), _, _ = pi
    t = cells_of(inp, TGT)
    if not t:
        return None
    tr, tc = t[0]
    h, w = len(inp), len(inp[0])
    cells = []
    r, c = st
    # go along d until the target's row (or column) is reached
    while (d[0] != 0 and r != tr) or (d[1] != 0 and c != tc):
        r, c = r + d[0], c + d[1]
        if not (0 <= r < h and 0 <= c < w):
            return None
        cells.append((r, c))
    # then straight toward the target
    sc = (tc > c) - (tc < c) if d[0] != 0 else 0
    sr = (tr > r) - (tr < r) if d[1] != 0 else 0
    while 0 <= r + sr < h and 0 <= c + sc < w and inp[r + sr][c + sc] != TGT:
        r, c = r + sr, c + sc
        cells.append((r, c))
    return paint(inp, [x for x in cells if inp[x[0]][x[1]] == 0], SRC)


def both_directions(inp, out):
    pi = path_info(inp, out)
    if not pi:
        return None
    (st, d), _, _ = pi
    g = [row[:] for row in out]
    for (s2, d2) in ends(inp):
        if (s2, d2) != (st, d):
            for r, c in ray(inp, s2, d2):
                g[r][c] = SRC
    return g


def into_target(inp, out):
    pi = path_info(inp, out)
    if not pi:
        return None
    _, order, moves = pi
    r, c = order[-1]
    m = moves[-1]
    q = (r + m[0], c + m[1])
    if 0 <= q[0] < len(inp) and 0 <= q[1] < len(inp[0]) and inp[q[0]][q[1]] == TGT:
        g = [row[:] for row in out]
        g[q[0]][q[1]] = SRC
        return g
    return None


def only_last_leg(inp, out):
    def k(pi):
        _, order, moves = pi
        last = moves[-1]
        n = len(moves)
        while n > 0 and moves[n - 1] == last:
            n -= 1
        return order[n:]
    return keep_cells(inp, out, k)


ALTERNATIVES = [
    ("path drawn in the target color 2 instead of the source color 3", path_color_2),
    ("path drawn in the wall color 8", path_color_8),
    ("only the first straight leg from the stub is drawn", first_leg_only),
    ("the last leg before the target is left undrawn", drop_last_leg),
    ("only the last leg is drawn, the earlier legs are left out", only_last_leg),
    ("path stops one cell short of where it should end", one_short),
    ("walker leaves from the other end of the stub, one leg only", opposite_end_ray),
    ("first leg runs to the grid edge through walls", ray_through_walls),
    ("walker turns away from the target at the first wall", wrong_turn),
    ("L-shaped route straight to the target that ignores walls", l_shape_ignoring_walls),
    ("walkers leave from both ends of the stub", both_directions),
    ("path runs one cell into the target and overwrites it", into_target),
]


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/2dd70a9a.json')))
    train = task["train"]

    def valid(g, out):
        if g is None or not isinstance(g, list) or not g:
            return False
        if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
            return False
        if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
            return False
        return g != out

    print("pairs:", len(train))
    for name, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", name, repr(e))
                g = None
            n += valid(g, p["output"])
        print(n, name)
