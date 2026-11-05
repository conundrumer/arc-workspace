import json
from collections import Counter
from pathlib import Path

DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def colors(inp):
    c = Counter(v for r in inp for v in r)
    bg = c.most_common(1)[0][0]
    shape = min(c, key=lambda k: c[k])
    return bg, shape


def inb(g, r, c):
    return 0 <= r < len(g) and 0 <= c < len(g[0])


def at(g, r, c):
    return g[r][c] if inb(g, r, c) else None


def copy(g):
    return [row[:] for row in g]


def changes(inp, out):
    bg, sh = colors(inp)
    added = [(r, c) for r in range(len(inp)) for c in range(len(inp[0]))
             if inp[r][c] == bg and out[r][c] == sh]
    taken = [(r, c) for r in range(len(inp)) for c in range(len(inp[0]))
             if inp[r][c] == sh and out[r][c] == bg]
    return bg, sh, added, taken


def add_dir(inp, sh, a):
    """Direction pointing away from the shape for an added bump cell."""
    roots = [d for d in DIRS if at(inp, a[0] - d[0], a[1] - d[1]) == sh]
    return roots[0] if len(roots) == 1 else None


def take_dir(inp, bg, sh, t):
    """Outward direction for a shape edge cell."""
    for d in DIRS:
        if at(inp, t[0] + d[0], t[1] + d[1]) == bg and at(inp, t[0] - d[0], t[1] - d[1]) == sh:
            return d
    return None


def perp(d):
    return (d[1], d[0])


def only_added(inp, out):
    bg, sh, added, taken = changes(inp, out)
    if not taken:
        return None
    g = copy(out)
    for r, c in taken:
        g[r][c] = sh
    return g


def only_taken(inp, out):
    bg, sh, added, taken = changes(inp, out)
    if not added:
        return None
    g = copy(out)
    for r, c in added:
        g[r][c] = bg
    return g


def unchanged(inp, out):
    return copy(inp)


def long_bump(inp, out):
    bg, sh, added, taken = changes(inp, out)
    g = copy(out)
    n = 0
    for a in added:
        d = add_dir(inp, sh, a)
        if d and inb(g, a[0] + d[0], a[1] + d[1]):
            g[a[0] + d[0]][a[1] + d[1]] = sh
            n += 1
    return g if n else None


def notch_inward(inp, out):
    bg, sh, added, taken = changes(inp, out)
    g = copy(out)
    n = 0
    for t in taken:
        d = take_dir(inp, bg, sh, t)
        if d:
            r, c = t[0] - d[0], t[1] - d[1]
            g[t[0]][t[1]] = sh
            g[r][c] = bg
            n += 1
    return g if n else None


def wrong_bump_color(inp, out):
    bg, sh, added, taken = changes(inp, out)
    if not added:
        return None
    g = copy(out)
    for r, c in added:
        g[r][c] = 2
    return g


def clean_shape(inp, out):
    bg, sh = colors(inp)
    g = copy(inp)
    h, w = len(inp), len(inp[0])
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            n_sh = sum(at(inp, r + dr, c + dc) == sh for dr, dc in DIRS)
            if v == bg:
                flank = (at(inp, r, c - 1) == sh and at(inp, r, c + 1) == sh) or \
                        (at(inp, r - 1, c) == sh and at(inp, r + 1, c) == sh)
                if flank:
                    g[r][c] = sh
            elif v == sh and n_sh == 1:
                g[r][c] = bg
    return g


def bump_off_by_one(inp, out):
    bg, sh, added, taken = changes(inp, out)
    g = copy(out)
    n = 0
    for a in added:
        d = add_dir(inp, sh, a)
        if not d:
            continue
        p = perp(d)
        r, c = a[0] + p[0], a[1] + p[1]
        if inb(g, r, c):
            g[a[0]][a[1]] = bg
            g[r][c] = sh
            n += 1
    return g if n else None


def notch_off_by_one(inp, out):
    bg, sh, added, taken = changes(inp, out)
    g = copy(out)
    n = 0
    for t in taken:
        d = take_dir(inp, bg, sh, t)
        if not d:
            continue
        p = perp(d)
        r, c = t[0] + p[0], t[1] + p[1]
        if inb(g, r, c):
            g[t[0]][t[1]] = sh
            g[r][c] = bg
            n += 1
    return g if n else None


def moved_not_mirrored(inp, out):
    bg, sh = colors(inp)
    g = copy(out)
    n = 0
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            if inp[r][c] == sh and sum(at(inp, r + dr, c + dc) == sh for dr, dc in DIRS) == 1:
                g[r][c] = bg
                n += 1
    return g if n else None


def vertical_only(inp, out):
    bg, sh, added, taken = changes(inp, out)
    g = copy(out)
    n = 0
    for a in added:
        d = add_dir(inp, sh, a)
        if d and d[0] == 0:
            g[a[0]][a[1]] = bg
            n += 1
    for t in taken:
        d = take_dir(inp, bg, sh, t)
        if d and d[0] == 0:
            g[t[0]][t[1]] = sh
            n += 1
    return g if n else None


ALTERNATIVES = [
    ("Only dents are turned into bumps; bumps are not turned into notches", only_added),
    ("Only bumps are turned into notches; dents are not turned into bumps", only_taken),
    ("Input returned unchanged", unchanged),
    ("Mirrored bump is two cells long instead of one", long_bump),
    ("Notch is cut one cell too deep, inside the far edge", notch_inward),
    ("Mirrored bump drawn in a wrong color", wrong_bump_color),
    ("Shape cleaned: dents filled, bumps deleted, nothing mirrored", clean_shape),
    ("Mirrored bump shifted one cell along the edge", bump_off_by_one),
    ("Mirrored notch shifted one cell along the edge", notch_off_by_one),
    ("Original bumps are deleted as well as mirrored", moved_not_mirrored),
    ("Anomalies on the left and right edges are ignored", vertical_only),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/8dab14c2.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            rect = len(g) > 0 and all(len(r) == len(g[0]) for r in g)
            ints = all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
            if rect and ints and g != p["output"]:
                ok += 1
        print(ok, desc)
