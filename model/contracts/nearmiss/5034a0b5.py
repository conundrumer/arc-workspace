import json
from pathlib import Path

DIRS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
OPP = {"U": "D", "D": "U", "L": "R", "R": "L"}
TR = {"U": "L", "L": "U", "D": "R", "R": "D"}
CW = {"U": "R", "R": "D", "D": "L", "L": "U"}


def frame(inp):
    h, w = len(inp), len(inp[0])
    bg = inp[0][0]
    side = {"U": inp[0][1], "D": inp[h - 1][1], "L": inp[1][0], "R": inp[1][w - 1]}
    return h, w, bg, side


def inner(h, w, r, c):
    return 1 <= r <= h - 2 and 1 <= c <= w - 2


def sim(inp, dirmap=lambda d: d, steps=1, comp="8", trail=False,
        vanish=False, no_block=False, fill=None):
    h, w, bg, side = frame(inp)
    col2dir = {col: d for d, col in side.items()}
    heads = {}
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            v = inp[r][c]
            if v in col2dir and v != bg:
                heads[(r, c)] = dirmap(col2dir[v])

    def faces(p):
        dr, dc = DIRS[heads[p]]
        return not inner(h, w, p[0] + dr, p[1] + dc)

    blocked = set()
    if not no_block:
        direct = {p for p in heads if faces(p)}
        if comp == "none":
            blocked = direct
        elif comp == "global":
            blocked = set(heads) if direct else set()
        else:
            nb = ([(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
                  if comp == "8" else [(-1, 0), (1, 0), (0, -1), (0, 1)])
            seen = set()
            for p in heads:
                if p in seen:
                    continue
                grp, stack = [], [p]
                seen.add(p)
                while stack:
                    q = stack.pop()
                    grp.append(q)
                    for a, b in nb:
                        n = (q[0] + a, q[1] + b)
                        if n in heads and n not in seen and inp[n[0]][n[1]] == inp[p[0]][p[1]]:
                            seen.add(n)
                            stack.append(n)
                if comp == "color":
                    continue
                if any(q in direct for q in grp):
                    blocked.update(grp)
            if comp == "color":
                bad = {inp[q[0]][q[1]] for q in direct}
                blocked = {p for p in heads if inp[p[0]][p[1]] in bad}
    res = [row[:] for row in inp]
    movers = []
    for p, d in heads.items():
        if p in blocked:
            if vanish:
                res[p[0]][p[1]] = bg
            continue
        dr, dc = DIRS[d]
        r, c = p
        for _ in range(steps):
            if inner(h, w, r + dr, c + dc) or no_block:
                r, c = r + dr, c + dc
                if not inner(h, w, r, c):
                    break
            else:
                break
        movers.append((p, (r, c), inp[p[0]][p[1]]))
    if not trail:
        for p, _, _ in movers:
            res[p[0]][p[1]] = bg if fill is None else fill(inp, p)
    for _, q, col in movers:
        res[q[0]][q[1]] = col
    return res


def true_rule(inp):
    return sim(inp)


def mk(**kw):
    return lambda inp, out: sim(inp, **kw)


def slide_all(inp, out):
    return sim(inp, steps=99)


def cell_by_cell(inp, out):
    return sim(inp, comp="none")


def side_color_fill(inp, out):
    h, w, bg, side = frame(inp)
    col2dir = {c: d for d, c in side.items()}
    return sim(inp, fill=lambda g, p: g[p[0]][p[1]])


def crop_interior(inp, out):
    return [row[1:-1] for row in out[1:-1]]


def move_wrong_frame_side_only_vertical(inp, out):
    # only top and bottom colors move; left and right colors ignored
    h, w, bg, side = frame(inp)
    res = [row[:] for row in inp]
    g = sim(inp)
    keep = {side["L"], side["R"]}
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            if inp[r][c] in keep and inp[r][c] != bg:
                continue
    # recompute with only U/D heads
    h, w, bg, side = frame(inp)
    cols = {side["U"]: "U", side["D"]: "D"}
    res = [row[:] for row in inp]
    mv = []
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            v = inp[r][c]
            if v in cols and v != bg:
                dr, dc = DIRS[cols[v]]
                if inner(h, w, r + dr, c + dc):
                    mv.append(((r, c), (r + dr, c + dc), v))
    for p, _, _ in mv:
        res[p[0]][p[1]] = bg
    for _, q, v in mv:
        res[q[0]][q[1]] = v
    return res


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("cells move away from the side of their color instead of toward it", mk(dirmap=lambda d: OPP[d])),
    ("cells move toward the clockwise-next side instead of the side of their color", mk(dirmap=lambda d: CW[d])),
    ("no blocking: cells next to the frame move onto the frame", mk(no_block=True)),
    ("cells move along the transposed axis (top color moves left, left color moves up, and so on)", mk(dirmap=lambda d: TR[d])),
    ("cells move two steps instead of one", mk(steps=2)),
    ("one blocked cell blocks every cell of that color anywhere", mk(comp="color")),
    ("origin cells are filled with the top side color instead of the background", lambda inp, out: sim(inp, fill=lambda g, p: g[0][1])),
    ("cells slide until they reach the frame instead of one step", slide_all),
    ("moved cells leave a copy behind (no erasing of the origin)", mk(trail=True)),
    ("blocked cells vanish to background instead of staying", mk(vanish=True)),
    ("only cells of the top and bottom side colors move", move_wrong_frame_side_only_vertical),
    ("output is the interior only, with the frame cropped off", crop_interior),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/5034a0b5.json"))
    pairs = task["train"]
    print("true rule reproduces outputs:", all(true_rule(p["input"]) == p["output"] for p in pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            ok = (g is not None and len(g) > 0 and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                  and g != p["output"])
            n += ok
        print(n, "/", len(pairs), desc)
