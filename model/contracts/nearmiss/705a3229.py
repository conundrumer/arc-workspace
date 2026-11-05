import json
from collections import Counter
from pathlib import Path

DIRS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}


def background(g):
    return Counter(v for row in g for v in row).most_common(1)[0][0]


def markers(g):
    bg = background(g)
    return [(r, c, v) for r, row in enumerate(g) for c, v in enumerate(row) if v != bg]


def dists(g, r, c):
    h, w = len(g), len(g[0])
    return {"U": r, "D": h - 1 - r, "L": c, "R": w - 1 - c}


def near_dirs(g, r, c):
    d = dists(g, r, c)
    return [k for k, o in (("U", "D"), ("D", "U"), ("L", "R"), ("R", "L")) if d[k] < d[o]]


def cast(g, base, r, c, v, dirs, stop_short=0):
    d = dists(g, r, c)
    for k in dirs:
        dr, dc = DIRS[k]
        for i in range(1, d[k] + 1 - stop_short):
            base[r + dr * i][c + dc * i] = v


def draw(inp, dirs_fn, which=None, color=None, stop_short=0):
    g = [row[:] for row in inp]
    ms = markers(inp)
    if which is not None:
        ms = which(ms)
    for r, c, v in ms:
        cast(inp, g, r, c, color if color is not None else v, dirs_fn(inp, r, c), stop_short)
    return g


def far_dirs(g, r, c):
    d = dists(g, r, c)
    return [k for k, o in (("U", "D"), ("D", "U"), ("L", "R"), ("R", "L")) if d[k] > d[o]]


def alt_farther(inp, out):
    return draw(inp, far_dirs)


def alt_vertical_only(inp, out):
    return draw(inp, lambda g, r, c: [k for k in near_dirs(g, r, c) if k in "UD"])


def alt_horizontal_only(inp, out):
    return draw(inp, lambda g, r, c: [k for k in near_dirs(g, r, c) if k in "LR"])


def alt_all_four(inp, out):
    return draw(inp, lambda g, r, c: list("UDLR"))


def alt_stop_short(inp, out):
    return draw(inp, near_dirs, stop_short=1)


def alt_single_nearest_edge(inp, out):
    def f(g, r, c):
        d = dists(g, r, c)
        k = min("UDLR", key=lambda x: d[x])
        return [k] if sorted(d.values())[0] < sorted(d.values())[1] else near_dirs(g, r, c)
    return draw(inp, f)


def alt_vertical_far_horizontal_near(inp, out):
    def f(g, r, c):
        return [k for k in far_dirs(g, r, c) if k in "UD"] + [k for k in near_dirs(g, r, c) if k in "LR"]
    return draw(inp, f)


def alt_diagonal(inp, out):
    g = [row[:] for row in inp]
    h, w = len(inp), len(inp[0])
    for r, c, v in markers(inp):
        nd = near_dirs(inp, r, c)
        vs = [k for k in nd if k in "UD"]
        hs = [k for k in nd if k in "LR"]
        if not vs or not hs:
            continue
        dr, dc = DIRS[vs[0]][0], DIRS[hs[0]][1]
        i = 1
        while 0 <= r + dr * i < h and 0 <= c + dc * i < w:
            g[r + dr * i][c + dc * i] = v
            i += 1
    return g


def alt_first_marker_only(inp, out):
    ms = markers(inp)
    if len(ms) < 2:
        return None
    return draw(inp, near_dirs, which=lambda m: m[:1])


def alt_off_by_one_size(inp, out):
    return [row[:-1] for row in out[:-1]]


def alt_one_color(inp, out):
    ms = markers(inp)
    if len(set(v for _, _, v in ms)) < 2:
        return None
    return draw(inp, near_dirs, color=ms[0][2])


def alt_full_line_on_nearer_axis(inp, out):
    def f(g, r, c):
        d = dists(g, r, c)
        if min(d["U"], d["D"]) < min(d["L"], d["R"]):
            return ["U", "D"]
        return ["L", "R"]
    return draw(inp, f)


def _guard(fn):
    def wrapped(inp, out):
        res = fn(inp, out)
        if res is None or res == out:
            return None
        return res
    return wrapped


ALTERNATIVES = [
    ("rays go toward the farther edge instead of the nearer edge", alt_farther),
    ("only vertical rays are cast", alt_vertical_only),
    ("only horizontal rays are cast", alt_horizontal_only),
    ("rays go in all four directions", alt_all_four),
    ("rays stop one cell before the grid edge", alt_stop_short),
    ("each marker casts only toward its single closest edge", alt_single_nearest_edge),
    ("vertical ray goes to the farther edge, horizontal ray to the nearer edge", alt_vertical_far_horizontal_near),
    ("marker casts one diagonal ray toward its nearer corner", alt_diagonal),
    ("only the first marker in reading order casts rays", alt_first_marker_only),
    ("output grid is one row and one column smaller than the input", alt_off_by_one_size),
    ("all rays take the color of the first marker", alt_one_color),
    ("full line both ways along the axis whose nearest edge is closer", alt_full_line_on_nearer_axis),
]
ALTERNATIVES = [(d, _guard(f)) for d, f in ALTERNATIVES]


def _valid(g, out):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/705a3229.json").read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
