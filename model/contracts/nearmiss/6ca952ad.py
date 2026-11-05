import json
from pathlib import Path

HEAVY = 4


def bg_of(g):
    cnt = {}
    for r in g:
        for v in r:
            cnt[v] = cnt.get(v, 0) + 1
    return max(cnt, key=cnt.get)


def objects(g, conn=4):
    bg = bg_of(g)
    h, w = len(g), len(g[0])
    seen = set()
    objs = []
    if conn == 4:
        nb = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    else:
        nb = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
    for r in range(h):
        for c in range(w):
            if g[r][c] != bg and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    a, b = st.pop()
                    cells.append((a, b))
                    for da, db in nb:
                        x, y = a + da, b + db
                        if 0 <= x < h and 0 <= y < w and g[x][y] != bg and (x, y) not in seen:
                            seen.add((x, y))
                            st.append((x, y))
                objs.append(cells)
    return objs


def shift(cells, d, k):
    dr, dc = d
    return [(r + dr * k, c + dc * k) for r, c in cells]


def fall(g, pred, d=(1, 0), conn=4, ignore_static=False, cap=None, margin=0):
    h, w = len(g), len(g[0])
    bg = bg_of(g)
    objs = objects(g, conn)
    movers = [o for o in objs if pred(len(o))]
    statics = [o for o in objs if not pred(len(o))]
    occ = set()
    if not ignore_static:
        for o in statics:
            occ.update(o)
    # order: those nearest to the wall in direction d move first
    movers.sort(key=lambda o: -max(r * d[0] + c * d[1] for r, c in o))
    placed = []
    for o in movers:
        k = 0
        while True:
            nxt = shift(o, d, k + 1)
            if all(0 <= r < h and 0 <= c < w and (r, c) not in occ for r, c in nxt):
                k += 1
            else:
                break
        if cap is not None:
            k = min(k, cap)
        k = max(0, k - margin)
        new = shift(o, d, k)
        occ.update(new)
        placed.append((o, new))
    res = [[bg] * w for _ in range(h)]
    for o in statics:
        for r, c in o:
            res[r][c] = g[r][c]
    for o, new in placed:
        for (r, c), (nr, nc) in zip(o, new):
            res[nr][nc] = g[r][c]
    return res


def heavy_pred(n):
    return n >= HEAVY


def r_threshold_up(inp, out):
    return fall(inp, lambda n: n >= HEAVY + 1)


def r_threshold_down(inp, out):
    return fall(inp, lambda n: n >= HEAVY - 1)


def r_all_fall(inp, out):
    return fall(inp, lambda n: True)


def r_inverted(inp, out):
    return fall(inp, lambda n: n < HEAVY)


def r_up(inp, out):
    return fall(inp, heavy_pred, d=(-1, 0))


def r_right(inp, out):
    return fall(inp, heavy_pred, d=(0, 1))


def r_one_step(inp, out):
    return fall(inp, heavy_pred, cap=1)


def r_one_short(inp, out):
    return fall(inp, heavy_pred, margin=1)


def r_erase_heavy(inp, out):
    bg = bg_of(inp)
    g = [r[:] for r in inp]
    for o in objects(inp):
        if len(o) >= HEAVY:
            for r, c in o:
                g[r][c] = bg
    return g


def r_copy_heavy(inp, out):
    bg = bg_of(inp)
    g = [r[:] for r in out]
    for o in objects(inp):
        if len(o) >= HEAVY:
            for r, c in o:
                if g[r][c] == bg:
                    g[r][c] = inp[r][c]
    return g


def r_largest_only(inp, out):
    top = max(len(o) for o in objects(inp))
    return fall(inp, lambda n: n == top)


def r_common_distance(inp, out):
    h = len(inp)
    bg = bg_of(inp)
    heavy = [o for o in objects(inp) if len(o) >= HEAVY]
    if not heavy:
        return None
    k = min(h - 1 - max(r for r, c in o) for o in heavy)
    g = [r[:] for r in inp]
    for o in heavy:
        for r, c in o:
            g[r][c] = bg
    for o in heavy:
        for r, c in o:
            g[r + k][c] = inp[r][c]
    return g


def r_cell_gravity(inp, out):
    h, w = len(inp), len(inp[0])
    bg = bg_of(inp)
    res = [[bg] * w for _ in range(h)]
    for c in range(w):
        col = [inp[r][c] for r in range(h) if inp[r][c] != bg]
        for i, v in enumerate(reversed(col)):
            res[h - 1 - i][c] = v
    return res


def r_only_heavy_kept(inp, out):
    bg = bg_of(inp)
    g = [r[:] for r in out]
    for o in objects(inp):
        if len(o) < HEAVY:
            for r, c in o:
                g[r][c] = bg
    return g


ALTERNATIVES = [
    ("heavy threshold one too low (objects of at least 3 cells fall)", r_threshold_down),
    ("every object falls, light ones too", r_all_fall),
    ("roles inverted: light objects fall, heavy ones stay", r_inverted),
    ("heavy objects rise to the top instead of falling down", r_up),
    ("heavy objects slide right instead of falling down", r_right),
    ("heavy objects fall one row only", r_one_step),
    ("heavy objects stop one row short of their resting place", r_one_short),
    ("heavy objects are erased instead of moved", r_erase_heavy),
    ("heavy objects are copied to the resting place and left in place", r_copy_heavy),
    ("only the largest object falls", r_largest_only),
    ("all heavy objects fall by the same distance, the smallest one needed", r_common_distance),
    ("every cell falls separately within its column", r_cell_gravity),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/6ca952ad.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            ok = (
                g is not None
                and len(g) > 0
                and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                and g != p["output"]
            )
            n += ok
        print(n, desc)
