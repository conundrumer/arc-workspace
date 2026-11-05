import json
from collections import Counter
from pathlib import Path

SIDE = 26
MARGIN = 2


def tiles(inp):
    nr, nc = (len(inp) - 1) // 2, (len(inp[0]) - 1) // 2
    return nr, nc, {(r, c): inp[2 * r + 1][2 * c + 1]
                    for r in range(nr) for c in range(nc)
                    if inp[2 * r + 1][2 * c + 1] != 0}


def spans(n, gap, side=SIDE, margin=MARGIN):
    size = (side - 2 * margin - gap * (n - 1)) // n
    return [(margin + i * (size + gap), margin + i * (size + gap) + size) for i in range(n)]


def groups(inp, mode):
    """Partition ink tiles into groups; mode selects the joining reading."""
    nr, nc, t = tiles(inp)
    parent = {k: k for k in t}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        parent[find(a)] = find(b)

    for (r, c), col in t.items():
        right, down = (r, c + 1), (r + 1, c)
        if mode == "true":
            if t.get(right) == col:
                union((r, c), right)
        if mode in ("horizontal", "anyspan"):
            if t.get(right) == col:
                union((r, c), right)
        if mode == "anyspan" and t.get(down) == col:
            union((r, c), down)
    if mode == "true":
        # vertical neighbours join when their horizontal runs have the same extent
        def run(k):
            col = t[k]
            a = b = k[1]
            while t.get((k[0], a - 1)) == col:
                a -= 1
            while t.get((k[0], b + 1)) == col:
                b += 1
            return a, b
        for (r, c), col in t.items():
            if t.get((r + 1, c)) == col and run((r, c)) == run((r + 1, c)):
                union((r, c), (r + 1, c))
    if mode == "rowcolor":
        for (r, c), col in t.items():
            for (r2, c2), col2 in t.items():
                if r == r2 and col == col2:
                    union((r, c), (r2, c2))
    if mode == "globalcolor":
        for k, col in t.items():
            for k2, col2 in t.items():
                if col == col2:
                    union(k, k2)
    out = {}
    for k in t:
        out.setdefault(find(k), []).append(k)
    return list(out.values()), t


def render(inp, mode="true", gap=2, side=SIDE, margin=MARGIN, skip_single=False, fill_box=True):
    gs, t = groups(inp, mode)
    nr, nc, _ = tiles(inp)
    rs, cs = spans(nr, gap, side, margin), spans(nc, gap, side, margin)
    g = [[0] * side for _ in range(side)]
    for grp in gs:
        if skip_single and len(grp) == 1:
            continue
        col = t[grp[0]]
        cells = grp if not fill_box else None
        if fill_box:
            r0, r1 = min(k[0] for k in grp), max(k[0] for k in grp)
            c0, c1 = min(k[1] for k in grp), max(k[1] for k in grp)
            boxes = [(rs[r0][0], rs[r1][1], cs[c0][0], cs[c1][1])]
        else:
            boxes = [(rs[k[0]][0], rs[k[0]][1], cs[k[1]][0], cs[k[1]][1]) for k in cells]
        for a, b, c, d in boxes:
            for y in range(a, b):
                for x in range(c, d):
                    g[y][x] = col
    return g


def no_join(inp, out):
    return render(inp, "none")


def horizontal_only(inp, out):
    return render(inp, "horizontal")


def any_span(inp, out):
    return render(inp, "anyspan")


def row_color(inp, out):
    return render(inp, "rowcolor")


def global_color(inp, out):
    return render(inp, "globalcolor")


def gap_one(inp, out):
    return render(inp, "true", gap=1)


def no_margin_crop(inp, out):
    return [row[1:-1] for row in out[1:-1]]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def flip_rows(inp, out):
    return [list(r) for r in reversed(out)]


def drop_single(inp, out):
    return render(inp, "true", skip_single=True)


def dominant_color(inp, out):
    ink = Counter(v for row in inp for v in row if v != 0)
    top = max(sorted(ink), key=lambda k: ink[k])
    return [[top if v != 0 else 0 for v in row] for row in out]


def no_margin(inp, out):
    return render(inp, "true", margin=0)


ALTERNATIVES = [
    ("each ink tile painted alone; same-colour neighbours are not joined", no_join),
    ("only horizontal neighbours join; vertical neighbours never join", horizontal_only),
    ("vertical neighbours of the same colour join whatever their horizontal extent", any_span),
    ("all same-colour tiles in one tile row join, even across gaps and other colours", row_color),
    ("all tiles of one colour join into a single box", global_color),
    ("gap between output tiles is one cell wide instead of two", gap_one),
    ("canvas is 24 by 24: the outer ring of margin is cut off", no_margin_crop),
    ("output is transposed", transposed),
    ("output is flipped top to bottom", flip_rows),
    ("tiles that join no other tile are left out", drop_single),
    ("every box takes the most common ink colour of the input", dominant_color),
    ("tiles run to the canvas edge with no margin", no_margin),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/33067df9.json").read_text())
    train = task["train"]
    assert all(render(p["input"]) == p["output"] for p in train), "render check failed"
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if (g and isinstance(g, list) and all(isinstance(r, list) for r in g)
                    and len({len(r) for r in g}) == 1
                    and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                    and g != p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
