"""Near-miss rules for ARC task 99caaf76.

Rule: each multi-color shape is an arrow. Its center cell has four colored
arm cells; the other cells are the fletching (tail). The arrow flies away
from its fletching until its leading edge touches the grid edge, and the
arms swap colors with the opposite arm.
"""
import json
from collections import Counter
from pathlib import Path

DIRS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
OPP = {"U": "D", "D": "U", "L": "R", "R": "L"}
ROT = {"U": "R", "R": "D", "D": "L", "L": "U"}  # clockwise


def bg_of(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def components(g):
    bg = bg_of(g)
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for da in (-1, 0, 1):
                    for db in (-1, 0, 1):
                        n = (a + da, b + db)
                        if (0 <= n[0] < h and 0 <= n[1] < w and n not in seen
                                and g[n[0]][n[1]] != bg):
                            seen.add(n)
                            stack.append(n)
            comps.append(sorted(cells))
    return bg, comps


def analyse(g, cells):
    s = set(cells)
    center = None
    for (r, c) in cells:
        if all((r + d[0], c + d[1]) in s for d in DIRS.values()):
            center = (r, c)
            break
    arms = {k: (center[0] + d[0], center[1] + d[1]) for k, d in DIRS.items()}
    armset = set(arms.values())
    tail = [p for p in cells if p != center and p not in armset]
    sr = sum(p[0] - center[0] for p in tail)
    sc = sum(p[1] - center[1] for p in tail)
    if abs(sr) >= abs(sc):
        tail_dir = "D" if sr > 0 else "U"
    else:
        tail_dir = "R" if sc > 0 else "L"
    return center, arms, tail, OPP[tail_dir]


def margin(g, cells, d):
    h, w = len(g), len(g[0])
    if d == "U":
        return min(r for r, c in cells)
    if d == "D":
        return h - 1 - max(r for r, c in cells)
    if d == "L":
        return min(c for r, c in cells)
    return w - 1 - max(c for r, c in cells)


def render(inp, swap="opp", flip=False, dshift=0, fixed_dir=None,
           drop_tail=False, rot_tail=False, ghost=False, skip_last=False,
           shift_fn=None, same_dist=False, tail_color=False, turn=False, swap_axis=None):
    bg, comps = components(inp)
    h, w = len(inp), len(inp[0])
    if skip_last and len(comps) < 2:
        return None
    out = [row[:] for row in inp] if ghost else [[bg] * w for _ in range(h)]
    shifts = []
    for i, cells in enumerate(comps):
        center, arms, tail, fdir = analyse(inp, cells)
        if fixed_dir:
            fdir = fixed_dir
        if flip:
            fdir = OPP[fdir]
        if turn:
            fdir = ROT[fdir]
        k = margin(inp, cells, fdir) if shift_fn is None else shift_fn(inp, cells, fdir, center)
        shifts.append(k + dshift)
    if same_dist:
        shifts = [min(shifts)] * len(shifts)
    for i, cells in enumerate(comps):
        center, arms, tail, fdir = analyse(inp, cells)
        if skip_last and i == len(comps) - 1:
            for (r, c) in cells:
                out[r][c] = inp[r][c]
            continue
        if fixed_dir:
            fdir = fixed_dir
        if flip:
            fdir = OPP[fdir]
        if turn:
            fdir = ROT[fdir]
        d = DIRS[fdir]
        k = shifts[i]
        placed = {}
        placed[center] = inp[center[0]][center[1]]
        for key, pos in arms.items():
            if swap_axis and key not in swap_axis:
                src = pos
            elif swap == "opp":
                src = arms[OPP[key]]
            elif swap == "rot":
                src = arms[ROT[key]]
            else:
                src = pos
            placed[pos] = inp[src[0]][src[1]]
        if not drop_tail:
            for p in tail:
                if rot_tail:
                    q = (2 * center[0] - p[0], 2 * center[1] - p[1])
                    placed[q] = inp[p[0]][p[1]]
                elif tail_color:
                    placed[p] = inp[center[0]][center[1]]
                else:
                    placed[p] = inp[p[0]][p[1]]
        for (r, c), v in placed.items():
            nr, nc = r + d[0] * k, c + d[1] * k
            if not (0 <= nr < h and 0 <= nc < w):
                return None
            out[nr][nc] = v
    return out


def true_rule(inp):
    return render(inp)


def f_no_swap(inp, out):
    return render(inp, swap="none")


def f_rot_swap(inp, out):
    return render(inp, swap="rot")


def f_toward_tail(inp, out):
    return render(inp, flip=True)


def f_one_short(inp, out):
    return render(inp, dshift=-1)


def f_drop_tail(inp, out):
    return render(inp, drop_tail=True)


def f_ghost(inp, out):
    return render(inp, ghost=True)


def f_tail_color(inp, out):
    return render(inp, tail_color=True)


def f_skip_last(inp, out):
    return render(inp, skip_last=True)


def f_horizontal_only(inp, out):
    return render(inp, swap_axis="LR")


def f_any_touch(inp, out):
    # arrow stops as soon as any part of it touches an edge in the flight direction's axis
    def fn(g, cells, d, ctr):
        return min(margin(g, cells, x) for x in "UDLR")
    return render(inp, shift_fn=fn)


def f_all_up(inp, out):
    return render(inp, fixed_dir="U")


def f_turn(inp, out):
    return render(inp, turn=True)


ALTERNATIVES = [
    ("arms keep their colors; the arrow only moves", f_no_swap),
    ("arm colors rotate a quarter turn instead of swapping with the opposite arm", f_rot_swap),
    ("arrow flies toward its fletching instead of away from it", f_toward_tail),
    ("arrow stops one cell short of the grid edge", f_one_short),
    ("fletching is dropped; only the center and arms move", f_drop_tail),
    ("arrow leaves a copy of itself at the old position", f_ghost),
    ("fletching cells take the center color", f_tail_color),
    ("the last arrow in reading order is left in place", f_skip_last),
    ("only the left and right arms swap; up and down arms keep their colors", f_horizontal_only),
    ("arrow stops when any part of it touches any grid edge", f_any_touch),
    ("every arrow flies up", f_all_up),
    ("arrow flies a quarter turn off the true direction", f_turn),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/99caaf76.json"))
    pairs = task["train"]
    for p in pairs:
        assert true_rule(p["input"]) == p["output"], "reference rule mismatch"
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:  # noqa
                print("  error:", desc, repr(e))
                g = None
            ok = (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                  and g != p["output"])
            n += bool(ok)
        print(f"{n}/{len(pairs)}  {desc}")
