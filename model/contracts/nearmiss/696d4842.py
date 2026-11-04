from pathlib import Path
import json, copy

N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def comps(g):
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if g[r][c] and (r, c) not in seen:
                col = g[r][c]
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x))
                    for dy, dx in N4:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and g[ny][nx] == col:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                res.append((col, cells))
    return res


def info(inp, out):
    """Return (s->d map, growth cells by s, recolored cells by s, dot cells by d)."""
    h, w = len(inp), len(inp[0])
    smap = {}
    for r in range(h):
        for c in range(w):
            if inp[r][c] and out[r][c] != inp[r][c]:
                smap[inp[r][c]] = out[r][c]
    growth = {s: [] for s in smap}
    recol = {s: [] for s in smap}
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 and out[r][c] in smap:
                growth[out[r][c]].append((r, c))
            elif inp[r][c] in smap and out[r][c] == smap[inp[r][c]]:
                recol[inp[r][c]].append((r, c))
    dots = [(col, cells[0]) for col, cells in comps(inp) if len(cells) == 1]
    return smap, growth, recol, dots


def alt_no_recolor(inp, out):
    smap, growth, recol, dots = info(inp, out)
    g = copy.deepcopy(out)
    for s, cells in recol.items():
        for r, c in cells:
            g[r][c] = s
    return g


def alt_erase_far_end(inp, out):
    smap, growth, recol, dots = info(inp, out)
    g = copy.deepcopy(out)
    for s, cells in recol.items():
        for r, c in cells:
            g[r][c] = 0
    return g


def alt_growth_dot_color(inp, out):
    smap, growth, recol, dots = info(inp, out)
    g = copy.deepcopy(out)
    for s, cells in growth.items():
        for r, c in cells:
            g[r][c] = smap[s]
    return g


def alt_one_short(inp, out):
    smap, growth, recol, dots = info(inp, out)
    h, w = len(inp), len(inp[0])
    dotpos = {p for _, p in dots}
    g = copy.deepcopy(out)
    for s, cells in growth.items():
        for r, c in cells:
            if any((r + dy, c + dx) in dotpos for dy, dx in N4):
                g[r][c] = 0
    for s, cells in recol.items():
        for r, c in cells:
            for dy, dx in N4:
                y, x = r + dy, c + dx
                if 0 <= y < h and 0 <= x < w and inp[y][x] == s and out[y][x] == s:
                    g[r][c] = s
                    break
    return g


def alt_whole_shape_recolored(inp, out):
    smap, growth, recol, dots = info(inp, out)
    g = copy.deepcopy(out)
    for r in range(len(g)):
        for c in range(len(g[0])):
            if inp[r][c] in smap and out[r][c] == inp[r][c]:
                g[r][c] = smap[inp[r][c]]
    return g


def alt_wrong_end(inp, out):
    smap, growth, recol, dots = info(inp, out)
    h, w = len(inp), len(inp[0])
    g = copy.deepcopy(out)
    for s in smap:
        shape = None
        for col, cells in comps(inp):
            if col == s and len(cells) > 1:
                shape = set(cells)
        if shape is None:
            return None
        gset = set(growth[s])
        ends = [p for p in sorted(shape)
                if any((p[0] + dy, p[1] + dx) in gset for dy, dx in N4)]
        if not ends:
            return None
        path, seen, st = [], set(), [ends[0]]
        while st:
            p = st.pop()
            if p in seen:
                continue
            seen.add(p)
            path.append(p)
            for dy, dx in N4:
                q = (p[0] + dy, p[1] + dx)
                if q in shape and q not in seen:
                    st.append(q)
        n = len(recol[s])
        for r, c in recol[s]:
            g[r][c] = s
        for r, c in path[:n]:
            g[r][c] = smap[s]
    return g


def alt_first_shape_only(inp, out):
    smap, growth, recol, dots = info(inp, out)
    if len(smap) < 2:
        return None
    first = min(smap, key=lambda s: min(r for r, c in recol[s] + growth[s]))
    g = copy.deepcopy(out)
    for s in smap:
        if s == first:
            continue
        for r, c in growth[s]:
            g[r][c] = 0
        for r, c in recol[s]:
            g[r][c] = s
    return g


def alt_dot_erased(inp, out):
    smap, growth, recol, dots = info(inp, out)
    g = copy.deepcopy(out)
    for _, (r, c) in dots:
        g[r][c] = 0
    return g


def alt_dot_swallowed(inp, out):
    smap, growth, recol, dots = info(inp, out)
    inv = {d: s for s, d in smap.items()}
    g = copy.deepcopy(out)
    for col, (r, c) in dots:
        if col in inv:
            g[r][c] = inv[col]
    return g


def alt_wrong_dot_pairing(inp, out):
    smap, growth, recol, dots = info(inp, out)
    if len(smap) < 2:
        return None
    ss = sorted(smap)
    ds = [smap[s] for s in ss]
    rot = ds[1:] + ds[:1]
    g = copy.deepcopy(out)
    for s, d in zip(ss, rot):
        for r, c in recol[s]:
            g[r][c] = d
    return g


def alt_overshoot(inp, out):
    smap, growth, recol, dots = info(inp, out)
    h, w = len(inp), len(inp[0])
    dotpos = {p for _, p in dots}
    g = copy.deepcopy(out)
    for s, cells in growth.items():
        for r, c in cells:
            for dy, dx in N4:
                p = (r + dy, c + dx)
                if p in dotpos:
                    y, x = p[0] + dy, p[1] + dx
                    while 0 <= y < h and 0 <= x < w and inp[y][x] == 0:
                        g[y][x] = s
                        y, x = y + dy, x + dx
    return g


def alt_identity(inp, out):
    return copy.deepcopy(inp)


ALTERNATIVES = [
    ("far end of the shape keeps its own color (no recoloring to the dot color)", alt_no_recolor),
    ("far end of the shape is erased to background instead of recolored", alt_erase_far_end),
    ("growth cells take the dot color instead of the shape color", alt_growth_dot_color),
    ("growth stops one cell short of the dot and one fewer far-end cell is recolored", alt_one_short),
    ("the whole original shape is recolored to the dot color, not just the far end", alt_whole_shape_recolored),
    ("the recolored cells are taken from the near end of the shape, not the far end", alt_wrong_end),
    ("only the topmost shape is processed; other shapes stay unchanged", alt_first_shape_only),
    ("the dot is consumed and erased once the growth reaches it", alt_dot_erased),
    ("the growth overwrites the dot cell with the shape color", alt_dot_swallowed),
    ("each shape is recolored with the dot color of the other shape", alt_wrong_dot_pairing),
    ("growth does not stop at the dot but runs on to the next obstacle or border", alt_overshoot),
    ("nothing changes: output equals input", alt_identity),
]


def valid(g):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    return all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/696d4842.json')))
    pairs = task["train"]
    counts = []
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, e)
                g = None
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        counts.append(n)
        print(f"{n}/{len(pairs)}  {desc}")
    print(counts)
