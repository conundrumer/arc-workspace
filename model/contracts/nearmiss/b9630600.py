"""Near-miss readings for ARC task b9630600 (hollow rooms joined by corridors)."""
import json
from collections import Counter
from pathlib import Path


def _rooms(g):
    h, w = len(g), len(g[0])
    bg = Counter(v for r in g for v in r).most_common(1)[0][0]
    seen = set()
    rooms = []
    for r in range(h):
        for c in range(w):
            if g[r][c] != bg and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != bg and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                rooms.append({
                    "r0": min(y for y, _ in cells), "r1": max(y for y, _ in cells),
                    "c0": min(x for _, x in cells), "c1": max(x for _, x in cells),
                    "col": g[r][c],
                })
    return bg, rooms


def _pairs(g, bg, rooms, ignore_block=False):
    res = []
    n = len(rooms)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            a, b = rooms[i], rooms[j]
            # axis h: a left of b; axis v: a above b
            if a["c1"] < b["c0"]:
                lo = max(a["r0"], b["r0"]) + 1
                hi = min(a["r1"], b["r1"]) - 1
                if lo > hi:
                    continue
                band = [(r, c) for r in range(lo, hi + 1) for c in range(a["c1"] + 1, b["c0"])]
                p = ("h", lo, hi, a["c1"], b["c0"])
            elif a["r1"] < b["r0"]:
                lo = max(a["c0"], b["c0"]) + 1
                hi = min(a["c1"], b["c1"]) - 1
                if lo > hi:
                    continue
                band = [(r, c) for c in range(lo, hi + 1) for r in range(a["r1"] + 1, b["r0"])]
                p = ("v", lo, hi, a["r1"], b["r0"])
            else:
                continue
            if not ignore_block and any(g[r][c] != bg for r, c in band):
                continue
            res.append({"a": i, "b": j, "axis": p[0], "lo": p[1], "hi": p[2],
                        "wa": p[3], "wb": p[4], "gap": p[4] - p[3] - 1})
    return res


def _find(par, x):
    while par[x] != x:
        par[x] = par[par[x]]
        x = par[x]
    return x


def _select(pairs, n, mode):
    if mode == "all":
        return list(pairs)
    if mode.startswith("max") and mode != "maxtree":
        lim = int(mode[3:])
        return [p for p in pairs if p["gap"] <= lim]
    if mode == "nearest":
        out = []
        for i in range(n):
            mine = [p for p in pairs if i in (p["a"], p["b"])]
            if mine:
                out.append(min(mine, key=lambda p: p["gap"]))
        return out
    if mode in ("mst", "area"):
        wt = (lambda p: p["gap"]) if mode == "mst" else (lambda p: p["gap"] * (p["hi"] - p["lo"] + 3))
        out = []
        for p in pairs:
            par = list(range(n))
            for q in pairs:
                if wt(q) < wt(p):
                    par[_find(par, q["a"])] = _find(par, q["b"])
            if _find(par, p["a"]) != _find(par, p["b"]):
                out.append(p)
        return out
    if mode == "maxtree":
        par = list(range(n))
        out = []
        for p in sorted(pairs, key=lambda p: -p["gap"]):
            ra, rb = _find(par, p["a"]), _find(par, p["b"])
            if ra != rb:
                par[ra] = rb
                out.append(p)
        return out
    raise ValueError(mode)


def _put(g, axis, line, pos, v):
    if axis == "h":
        g[line][pos] = v
    else:
        g[pos][line] = v


def solve(inp, select="mst", ignore_block=False, axes="hv", paint="normal"):
    bg, rooms = _rooms(inp)
    pairs = [p for p in _pairs(inp, bg, rooms, ignore_block) if p["axis"] in axes]
    chosen = _select(pairs, len(rooms), select)
    g = [list(r) for r in inp]
    col = rooms[0]["col"]
    for p in chosen:
        ax, lo, hi = p["axis"], p["lo"], p["hi"]
        a, b = rooms[p["a"]], rooms[p["b"]]
        if paint == "wider":
            if ax == "h":
                lo, hi = min(a["r0"], b["r0"]) + 1, max(a["r1"], b["r1"]) - 1
                if (lo, hi) == (p["lo"], p["hi"]):
                    continue
            else:
                lo, hi = min(a["c0"], b["c0"]) + 1, max(a["c1"], b["c1"]) - 1
                if (lo, hi) == (p["lo"], p["hi"]):
                    continue
        if paint == "margin":
            lo, hi = lo - 1, hi + 1
        gap_cells = range(p["wa"] + 1, p["wb"])
        lines = {"normal": [lo, hi], "solid": list(range(lo, hi + 1)),
                 "noopen": [lo, hi], "nolines": [], "all_open": [lo, hi],
                 "one_side": [lo, hi], "wider": [lo, hi], "margin": [lo, hi],
                 "inner": [lo + 1, hi - 1]}[paint]
        for ln in lines:
            for pos in gap_cells:
                _put(g, ax, ln, pos, col)
        if paint in ("normal", "nolines", "one_side", "wider", "inner"):
            rng = range(lo + 1, hi)
        elif paint == "all_open":
            rng = range(lo, hi + 1)
        else:
            rng = range(0)
        for ln in rng:
            for pos in ([p["wa"], p["wb"]] if paint != "one_side" else [p["wa"]]):
                if (inp[ln][pos] if ax == "h" else inp[pos][ln]) == col:
                    _put(g, ax, ln, pos, bg)
        if paint == "nolines":
            for ln in range(lo, hi + 1):
                for pos in gap_cells:
                    _put(g, ax, ln, pos, bg)
    return g


def _wrap(**kw):
    def f(inp, out):
        g = solve(inp, **kw)
        return None if g == out else g
    return f


ALTERNATIVES = [
    ("every facing pair gets a corridor, not only a least-gap spanning tree", _wrap(select="all")),
    ("a spanning tree of the largest gaps instead of the least gaps", _wrap(select="maxtree")),
    ("only pairs with gap at most 2 get a corridor", _wrap(select="max2")),
    ("each room joins only its nearest facing neighbour", _wrap(select="nearest")),
    ("only horizontal corridors are built", _wrap(axes="h")),
    ("only vertical corridors are built", _wrap(axes="v")),
    ("corridor is a solid bar over the whole span with no opening in the walls", _wrap(paint="solid")),
    ("corridor lines are drawn but the facing walls are not opened", _wrap(paint="noopen")),
    ("only the first room's facing wall is opened", _wrap(paint="one_side")),
    ("the whole span is opened in the walls, outer lines included", _wrap(paint="all_open")),
    ("corridor lines sit one line outside the shared span", _wrap(paint="margin")),
    ("corridor lines sit one line inside the shared span", _wrap(paint="inner")),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/b9630600.json"))
    train = task["train"]
    # sanity: the base solver reproduces the true outputs
    print("base ok:", [solve(p["input"]) == p["output"] for p in train])
    for desc, fn in ALTERNATIVES:
        valid = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))
            if ok and g != p["output"]:
                valid += 1
        print(f"{valid}/{len(train)}  {desc}")
