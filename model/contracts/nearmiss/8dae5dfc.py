from pathlib import Path
import json
from collections import Counter

N4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def bgcolor(g):
    return Counter(c for r in g for c in r).most_common(1)[0][0]


def components(g, cells, same_color):
    cells = set(cells)
    seen, comps = set(), []
    for s in sorted(cells):
        if s in seen:
            continue
        stack, comp = [s], []
        seen.add(s)
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for dr, dc in N4:
                q = (r + dr, c + dc)
                if q in cells and q not in seen and (not same_color or g[q[0]][q[1]] == g[r][c]):
                    seen.add(q)
                    stack.append(q)
        comps.append(comp)
    return comps


def objects(inp):
    """Per object: list of (cells), ring depth map, layers sorted outside-in."""
    bg = bgcolor(inp)
    h, w = len(inp), len(inp[0])
    nb = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != bg]
    res = []
    for comp in components(inp, nb, False):
        cs = set(comp)
        depth, rem, d = {}, set(cs), 0
        while rem:
            edge = [p for p in rem
                    if any((p[0] + dr, p[1] + dc) not in rem for dr, dc in N4)]
            for p in edge:
                depth[p] = d
            rem -= set(edge)
            d += 1
        fused = components(inp, comp, True)
        layers = [(min(depth[p] for p in f), inp[f[0][0]][f[0][1]], f) for f in fused]
        layers.sort(key=lambda t: t[0])
        rings = {}
        for p, k in depth.items():
            rings.setdefault(k, []).append(p)
        ringl = [(k, inp[v[0][0]][v[0][1]], v) for k, v in sorted(rings.items())]
        res.append((comp, depth, layers, ringl))
    return res


def recolor(inp, pick, which=None, use_rings=False):
    """pick(n, i) -> source index for layer i of n. which: object indices to change."""
    g = [row[:] for row in inp]
    objs = objects(inp)
    for oi, (comp, depth, layers, ringl) in enumerate(objs):
        if which is not None and oi not in which(objs):
            continue
        L = ringl if use_rings else layers
        n = len(L)
        for i, (_, _, cells) in enumerate(L):
            col = L[pick(n, i)][1]
            for r, c in cells:
                g[r][c] = col
    return g


def correct_like(inp, out):
    return recolor(inp, lambda n, i: n - 1 - i)


def a_rings(inp, out):
    return recolor(inp, lambda n, i: n - 1 - i, use_rings=True)


def a_shift(inp, out):
    return recolor(inp, lambda n, i: (i + 1) % n)


def a_shift_out(inp, out):
    return recolor(inp, lambda n, i: (i - 1) % n)


def a_swap_ends(inp, out):
    def p(n, i):
        if i == 0:
            return n - 1
        if i == n - 1:
            return 0
        return i
    return recolor(inp, p)


def a_outer_only(inp, out):
    return recolor(inp, lambda n, i: n - 1 if i == 0 else i)


def a_core_fixed(inp, out):
    return recolor(inp, lambda n, i: (n - 2 - i) if i < n - 1 else i)


def a_outer_fixed(inp, out):
    return recolor(inp, lambda n, i: (n - i) if i > 0 else 0)


def a_largest_only(inp, out):
    def which(objs):
        return {max(range(len(objs)), key=lambda k: len(objs[k][0]))}
    return recolor(inp, lambda n, i: n - 1 - i, which=which)


def a_smallest_only(inp, out):
    def which(objs):
        return {min(range(len(objs)), key=lambda k: len(objs[k][0]))}
    return recolor(inp, lambda n, i: n - 1 - i, which=which)


def a_global_map(inp, out):
    objs = objects(inp)
    big = max(objs, key=lambda o: len(o[0]))
    L = big[2]
    n = len(L)
    m = {L[i][1]: L[n - 1 - i][1] for i in range(n)}
    bg = bgcolor(inp)
    return [[m.get(c, c) if c != bg else c for c in row] for row in inp]


def a_fliph(inp, out):
    g = recolor(inp, lambda n, i: n - 1 - i)
    return [row[::-1] for row in g]


def a_unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("reverse per ring, so adjacent same-color rings are not fused into one layer", a_rings),
    ("each layer takes the color of the next layer inward (cyclic shift)", a_shift),
    ("each layer takes the color of the next layer outward (cyclic shift)", a_shift_out),
    ("only the outermost and innermost layer swap colors; middle layers stay", a_swap_ends),
    ("only the outermost layer takes the innermost color", a_outer_only),
    ("the innermost layer keeps its color; the others reverse among themselves", a_core_fixed),
    ("the outermost layer keeps its color; the others reverse among themselves", a_outer_fixed),
    ("only the largest object is reversed", a_largest_only),
    ("only the smallest object is reversed", a_smallest_only),
    ("one color substitution, read off the largest object, applied to every object", a_global_map),
    ("correct reversal, then the grid is mirrored left to right", a_fliph),
    ("input returned unchanged", a_unchanged),
]


def valid(g, out):
    if g is None or not g or not isinstance(g, list):
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/8dae5dfc.json')))
    pairs = task["train"]
    print("pairs", len(pairs))
    assert all(correct_like(p["input"], p["output"]) == p["output"] for p in pairs), "reference reversal wrong"
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, e)
                g = None
            n += valid(g, p["output"])
        print(n, desc)
