import json
from pathlib import Path

BG = 8
N = 5
OFFS = (0, 6, 12)
DIRS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def panels(inp):
    return [[row[o:o + N] for row in inp] for o in OFFS]


def components(p, conn=4):
    seen = set()
    comps = []
    nbrs = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    if conn == 8:
        nbrs += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    for r in range(N):
        for c in range(N):
            if p[r][c] == BG or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            comp = {}
            while stack:
                y, x = stack.pop()
                comp[(y, x)] = p[y][x]
                for dy, dx in nbrs:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < N and 0 <= nx < N and (ny, nx) not in seen and p[ny][nx] == p[r][c]:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append(comp)
    return comps


def pieces(inp, conn=4, largest=True):
    res = []
    for p in panels(inp):
        comps = components(p, conn)
        if largest:
            comps = [max(comps, key=len)] if comps else []
            res.append(comps[0] if comps else {})
        else:
            m = {}
            for c in comps:
                m.update(c)
            res.append(m)
    return res


def shift(piece, d, k):
    return {(r + d[0] * k, c + d[1] * k): v for (r, c), v in piece.items()}


def inb(piece):
    return all(0 <= r < N and 0 <= c < N for r, c in piece)


def fits(ps, i, d, k):
    others = [p for j, p in enumerate(ps) if j != i]
    seen = set()
    for o in others:
        if seen & set(o):
            return False
        seen |= set(o)
    s = shift(ps[i], d, k)
    return inb(s) and not (set(s) & seen)


def options(ps):
    """Per piece: list of (k, dir) sorted by shortest slide."""
    res = []
    for i in range(len(ps)):
        o = sorted((k, d) for d in DIRS for k in range(0, N) if fits(ps, i, d, k))
        res.append(o)
    return res


def render(ps, mover=None, d=None, k=0, extra=None):
    g = [[BG] * N for _ in range(N)]
    for i, p in enumerate(ps):
        if i == mover:
            p = shift(p, d, k)
        for (r, c), v in p.items():
            if 0 <= r < N and 0 <= c < N:
                g[r][c] = v
    return g


def solve(inp, conn=4, pick="min", kadd=0, flip=False, largest=True, nomove=False):
    ps = pieces(inp, conn, largest)
    opts = options(ps)
    cands = [(o[0][0], i, o[0][1]) for i, o in enumerate(opts) if o]
    if not cands:
        return None
    if nomove:
        return render(ps)
    cands.sort()
    k, i, d = cands[0] if pick == "min" else cands[-1]
    if flip:
        d = (-d[0], -d[1])
    return render(ps, i, d, k + kadd)


def a_no_slide(inp, out):
    return solve(inp, nomove=True)


def forced(inp, dirs):
    ps = pieces(inp)
    cands = []
    for i in range(len(ps)):
        o = sorted((k, d) for d in dirs for k in range(1, N) if fits(ps, i, d, k))
        if o:
            cands.append((o[0][0], i, o[0][1]))
    if not cands:
        return None
    k, i, d = sorted(cands)[0]
    return render(ps, i, d, k)


def a_forced_slide(inp, out):
    # a slide of at least one cell is required, even when the shapes already fit
    return forced(inp, DIRS)


def a_forced_vertical(inp, out):
    # a column slide of at least one cell is required
    return forced(inp, DIRS[2:])


def a_slide_one_extra(inp, out):
    return solve(inp, kadd=1)


def a_slide_opposite(inp, out):
    return solve(inp, flip=True)


def a_keep_strays(inp, out):
    return solve(inp, largest=False)


def a_smallest_piece_kept(inp, out):
    # keep the smaller shape of each panel instead of the larger one
    ps = []
    for p in panels(inp):
        comps = components(p)
        ps.append(min(comps, key=len) if comps else {})
    return render(ps)


def a_first_panel(inp, out):
    return [row[:] for row in panels(inp)[0]]


def a_last_panel(inp, out):
    return [row[:] for row in panels(inp)[2]]


def a_background_zero(inp, out):
    return [[0 if v == BG else v for v in row] for row in out]


def a_transposed(inp, out):
    return [list(r) for r in zip(*out)]


def a_mirrored(inp, out):
    return [row[::-1] for row in out]


def a_mover_dropped(inp, out):
    ps = pieces(inp)
    opts = options(ps)
    cands = sorted((o[0][0], i) for i, o in enumerate(opts) if o)
    if not cands:
        return None
    ps2 = [p for j, p in enumerate(ps) if j != cands[0][1]]
    return render(ps2)


ALTERNATIVES = [
    ("overlay the three largest shapes with no slide", a_no_slide),
    ("a slide of at least one cell is always applied, even to shapes that already fit", a_forced_slide),
    ("slide the right piece one cell too far", a_slide_one_extra),
    ("slide the right piece the opposite way", a_slide_opposite),
    ("a slide of at least one cell is applied, along columns only", a_forced_vertical),
    ("keep every non-background cell of each panel, strays included", a_keep_strays),
    ("keep the smaller shape of each panel instead of the larger", a_smallest_piece_kept),
    ("answer is the left panel alone", a_first_panel),
    ("answer is the right panel alone", a_last_panel),
    ("background painted 0 instead of 8", a_background_zero),
    ("true answer transposed", a_transposed),
    ("true answer mirrored left to right", a_mirrored),
]


def valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/337b420f.json").read_text())
    train = task["train"]
    ok_solver = [solve(p["input"]) == p["output"] for p in train]
    print("reference solver matches true output:", ok_solver)
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
