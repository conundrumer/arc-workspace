import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(c for r in g for c in r).most_common(1)[0][0]


def _components(g, bg, diag=True):
    h, w = len(g), len(g[0])
    steps = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diag:
        steps += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    seen = set()
    comps = []
    for i in range(h):
        for j in range(w):
            if g[i][j] == bg or (i, j) in seen:
                continue
            stack = [(i, j)]
            seen.add((i, j))
            comp = []
            while stack:
                a, b = stack.pop()
                comp.append((a, b))
                for da, db in steps:
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and g[x][y] != bg and (x, y) not in seen:
                        seen.add((x, y))
                        stack.append((x, y))
            comps.append(comp)
    return comps


def solve(inp, diag=True, rare="min", erase=True, align="anchor", match_dots=True,
          first_only=False, recolor=None, flip=None, keep_other_dots=False):
    g = inp
    h, w = len(g), len(g[0])
    bg = _bg(g)
    comps = _components(g, bg, diag)
    shapes = [c for c in comps if len(c) > 1]
    dots = [c[0] for c in comps if len(c) == 1]
    tally = Counter(g[a][b] for s in shapes for a, b in s)
    if not tally:
        return None
    if rare == "min":
        target = min(tally.values())
    else:
        target = max(tally.values())
    rare_cols = {c for c, n in tally.items() if n == target}
    out = [[bg] * w for _ in range(h)]
    if not erase:
        for s in shapes:
            for a, b in s:
                out[a][b] = g[a][b]
    stamps = []
    for s in shapes:
        cells = {p: g[p[0]][p[1]] for p in s}
        anchors = [p for p in s if g[p[0]][p[1]] in rare_cols]
        if not anchors:
            continue
        if align == "anchor":
            ap = anchors[0]
        elif align == "topleft":
            ap = (min(a for a, _ in s), min(b for _, b in s))
        elif align == "center":
            ap = ((min(a for a, _ in s) + max(a for a, _ in s)) // 2,
                  (min(b for _, b in s) + max(b for _, b in s)) // 2)
        acol = g[anchors[0][0]][anchors[0][1]]
        ds = [d for d in dots if (g[d[0]][d[1]] == acol or not match_dots)]
        if first_only:
            ds = ds[:1]
        for d in ds:
            stamps.append((cells, ap, d, acol))
    for cells, ap, d, acol in stamps:
        for (a, b), c in cells.items():
            da, db = a - ap[0], b - ap[1]
            if flip == "h":
                db = -db
            elif flip == "v":
                da = -da
            elif flip == "r":
                da, db = -da, -db
            elif flip == "t":
                da, db = db, da
            x, y = d[0] + da, d[1] + db
            if 0 <= x < h and 0 <= y < w:
                out[x][y] = recolor if recolor is not None else c
    stamped = {d for _, _, d, _ in stamps}
    for a, b in dots:
        if (a, b) in stamped:
            continue
        if not keep_other_dots:
            continue
        if out[a][b] == bg:
            out[a][b] = g[a][b]
    return out


def _body_color(inp):
    bg = _bg(inp)
    cnt = Counter(inp[a][b] for c in _components(inp, bg) if len(c) > 1 for a, b in c)
    return cnt.most_common(1)[0][0]


ALTERNATIVES = [
    ("original shapes are left in place after stamping", lambda i, o: solve(i, erase=False)),
    ("anchor is the most common shape color instead of the rarest", lambda i, o: solve(i, rare="max")),
    ("shapes are 4-connected only, so diagonal cells split off", lambda i, o: solve(i, diag=False)),
    ("shape is stamped on every dot, whatever its color", lambda i, o: solve(i, match_dots=False)),
    ("shape bounding-box top-left corner is put on the dot", lambda i, o: solve(i, align="topleft")),
    ("shape bounding-box center is put on the dot", lambda i, o: solve(i, align="center")),
    ("shape is stamped on only the first matching dot of each shape", lambda i, o: solve(i, first_only=True)),
    ("stamp is rotated 180 degrees", lambda i, o: solve(i, flip="r")),
    ("stamp is mirrored top to bottom", lambda i, o: solve(i, flip="v")),
    ("stamp is transposed", lambda i, o: solve(i, flip="t")),
    ("stamp is drawn in the shape's body color only, anchor color lost", lambda i, o: solve(i, recolor=_body_color(i))),
    ("dots that match no shape anchor stay in the output", lambda i, o: solve(i, keep_other_dots=True)),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/1b59e163.json'))
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", e)
                g = None
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
