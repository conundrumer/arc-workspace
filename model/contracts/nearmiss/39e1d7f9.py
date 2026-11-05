"""Near-miss rules for ARC task 39e1d7f9.

Rule: dividers cut the grid into tiles. One multi-tile (8-connected) motif and
some lone tiles exist. Each lone tile is the seat of a copy of the motif: the
motif cell with the lone tile's color lands on the lone tile, and the whole
motif is painted around it.
"""
import json
from pathlib import Path


def _bands(flags):
    bands, start = [], None
    for i, f in enumerate(flags + [True]):
        if not f and start is None:
            start = i
        elif f and start is not None:
            bands.append((start, i))
            start = None
    return bands


def _parse(g):
    h, w = len(g), len(g[0])
    rows = _bands([len(set(r)) == 1 for r in g])
    cols = _bands([len({g[r][c] for r in range(h)}) == 1 for c in range(w)])
    T = [[g[r0][c0] for (c0, _) in cols] for (r0, _) in rows]
    return rows, cols, T


def _render(g, rows, cols, T):
    o = [r[:] for r in g]
    for i, (r0, r1) in enumerate(rows):
        for j, (c0, c1) in enumerate(cols):
            for r in range(r0, r1):
                for c in range(c0, c1):
                    o[r][c] = T[i][j]
    return o


def _components(T):
    H, W = len(T), len(T[0])
    seen, comps = set(), []
    for i in range(H):
        for j in range(W):
            if T[i][j] == 0 or (i, j) in seen:
                continue
            comp, stack = [], [(i, j)]
            seen.add((i, j))
            while stack:
                a, b = stack.pop()
                comp.append((a, b))
                for da in (-1, 0, 1):
                    for db in (-1, 0, 1):
                        n = (a + da, b + db)
                        if 0 <= n[0] < H and 0 <= n[1] < W and n not in seen and T[n[0]][n[1]] != 0:
                            seen.add(n)
                            stack.append(n)
            comps.append(sorted(comp))
    return comps


def _analyse(inp):
    rows, cols, T = _parse(inp)
    comps = _components(T)
    motif = max(comps, key=len)
    seeds = sorted(c[0] for c in comps if len(c) == 1)
    return rows, cols, T, motif, seeds


def _seat(T, motif, color, pick="match"):
    if pick == "match":
        cells = [p for p in motif if T[p[0]][p[1]] == color]
    else:  # most common color in the motif
        cnt = {}
        for p in motif:
            cnt[T[p[0]][p[1]]] = cnt.get(T[p[0]][p[1]], 0) + 1
        top = max(cnt, key=lambda k: cnt[k])
        cells = [p for p in motif if T[p[0]][p[1]] == top]
    return cells[0] if cells else None


def _stamp(inp, seeds_use=None, keep=None, recolor=False, wrap=False,
           anchor="match", seed_clear=False, erase_motif=False, only_bg=False,
           shift=(0, 0)):
    rows, cols, T, motif, seeds = _analyse(inp)
    H, W = len(T), len(T[0])
    N = [r[:] for r in T]
    if erase_motif:
        for a, b in motif:
            N[a][b] = 0
    use = seeds if seeds_use is None else seeds_use(seeds)
    for s in use:
        sc = T[s[0]][s[1]]
        if anchor == "match":
            seat = _seat(T, motif, sc)
        elif anchor == "common":
            seat = _seat(T, motif, sc, "common")
        else:  # top-left corner of the motif box
            seat = (min(p[0] for p in motif), min(p[1] for p in motif))
        if seat is None:
            return None
        for a, b in motif:
            if keep is not None and not keep(a - seat[0], b - seat[1]):
                continue
            y, x = s[0] + a - seat[0] + shift[0], s[1] + b - seat[1] + shift[1]
            if wrap:
                y, x = y % H, x % W
            elif not (0 <= y < H and 0 <= x < W):
                continue
            if only_bg and T[y][x] != 0:
                continue
            N[y][x] = sc if recolor else T[a][b]
    if seed_clear:
        for s in seeds:
            N[s[0]][s[1]] = 0
    return _render(inp, rows, cols, N)


def first_seed_only(inp, out):
    return _stamp(inp, seeds_use=lambda s: s[:1])


def shifted_right(inp, out):
    return _stamp(inp, shift=(0, 1))


def shifted_down(inp, out):
    return _stamp(inp, shift=(1, 0))


def without_top_row(inp, out):
    return _stamp(inp, keep=lambda da, db: da != -1)


def anchor_top_left(inp, out):
    return _stamp(inp, anchor="corner")


def anchor_common_color(inp, out):
    return _stamp(inp, anchor="common")


def wrap_around(inp, out):
    return _stamp(inp, wrap=True)


def seed_color_everywhere(inp, out):
    return _stamp(inp, recolor=True)


def move_not_copy(inp, out):
    return _stamp(inp, erase_motif=True)


def seed_cleared(inp, out):
    return _stamp(inp, seed_clear=True)


def pixel_scale_stamp(inp, out):
    """Stamp with one motif cell per tile-width block, ignoring the dividers."""
    rows, cols, T, motif, seeds = _analyse(inp)
    tw = cols[0][1] - cols[0][0]
    th = rows[0][1] - rows[0][0]
    o = [r[:] for r in inp]
    for s in seeds:
        sc = T[s[0]][s[1]]
        seat = _seat(T, motif, sc)
        if seat is None:
            return None
        for a, b in motif:
            y0 = rows[s[0]][0] + (a - seat[0]) * th
            x0 = cols[s[1]][0] + (b - seat[1]) * tw
            for y in range(y0, y0 + th):
                for x in range(x0, x0 + tw):
                    if 0 <= y < len(o) and 0 <= x < len(o[0]):
                        o[y][x] = T[a][b]
    return o


def unchanged(inp, out):
    return [r[:] for r in inp]


ALTERNATIVES = [
    ("copy the motif at the first lone tile only", first_seed_only),
    ("copy lands one tile to the right of the lone tile", shifted_right),
    ("copy drops the motif's top row of tiles", without_top_row),
    ("seat the copy by the motif box top-left corner instead of the matching color", anchor_top_left),
    ("seat the copy on a cell of the motif's most common color", anchor_common_color),
    ("copy lands one tile below the lone tile", shifted_down),
    ("copy wraps around the grid edges instead of clipping", wrap_around),
    ("paint every copy cell in the lone tile's color", seed_color_everywhere),
    ("move the motif to the lone tiles instead of copying it", move_not_copy),
    ("copy the motif around each lone tile but clear the lone tile", seed_cleared),
    ("copy the motif at pixel scale of one tile width, ignoring dividers", pixel_scale_stamp),
    ("output equals the input", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/39e1d7f9.json"))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
