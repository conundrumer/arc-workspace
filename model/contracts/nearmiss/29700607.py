import json
from pathlib import Path


def parse(inp):
    h, w = len(inp), len(inp[0])
    headers = [(c, inp[0][c]) for c in range(w) if inp[0][c]]
    markers = [(r, c, inp[r][c]) for r in range(1, h) for c in range(w) if inp[r][c]]
    return h, w, headers, markers


def draw(inp, vert="elbow", horiz="marker", unmarked="full", priority="vert", lowest=False):
    h, w, headers, markers = parse(inp)
    low = max(m[0] for m in markers)
    g = [[0] * w for _ in range(h)]
    hor, ver = [], []
    for c, col in headers:
        m = [x for x in markers if x[2] == col]
        if not m:
            if unmarked == "full":
                ver.append((c, 0, h - 1, col))
            elif unmarked == "none":
                ver.append((c, 0, 0, col))
            continue
        r, mc, _ = m[0]
        if lowest:
            r = low
        end = {"elbow": r, "full": h - 1, "early": r - 1}[vert]
        ver.append((c, 0, end, col))
        lo, hi = (0, c) if mc < c else (c, w - 1)
        if horiz == "marker":
            pass
        elif horiz == "none":
            continue
        elif horiz == "opposite":
            lo, hi = (c, w - 1) if mc < c else (0, c)
        elif horiz == "fullrow":
            lo, hi = 0, w - 1
        elif horiz == "down1":
            r = min(r + 1, h - 1)
        if vert == "early":
            lo, hi = (lo, hi - 1) if mc < c else (lo + 1, hi)
        hor.append((r, lo, hi, col))
    def paint_h():
        for r, lo, hi, col in hor:
            for x in range(lo, hi + 1):
                g[r][x] = col
    def paint_v():
        for c, r0, r1, col in ver:
            for y in range(r0, r1 + 1):
                g[y][c] = col
    if priority == "vert":
        paint_h(); paint_v()
    else:
        paint_v(); paint_h()
    for y in range(h):
        for x in range(w):
            if inp[y][x] and not g[y][x]:
                g[y][x] = inp[y][x]
    return g


def only_horizontal(inp, out):
    h, w, headers, markers = parse(inp)
    g = [row[:] for row in inp]
    for r, mc, col in markers:
        c = [c for c, k in headers if k == col]
        if not c:
            continue
        for x in range(min(mc, c[0]), max(mc, c[0]) + 1):
            g[r][x] = col
    return g


ALTERNATIVES = [
    ("turned lines keep going down to the bottom edge instead of stopping at the elbow row",
     lambda i, o: draw(i, vert="full")),
    ("only vertical legs are drawn; the horizontal leg to the marker is missing",
     lambda i, o: draw(i, horiz="none")),
    ("only horizontal legs from marker to header column are drawn; no vertical legs",
     lambda i, o: only_horizontal(i, o)),
    ("vertical leg stops one row above the elbow row",
     lambda i, o: draw(i, vert="early")),
    ("horizontal leg spans the whole row, both sides of the header column",
     lambda i, o: draw(i, horiz="fullrow")),
    ("horizontal leg goes away from the marker, to the opposite edge",
     lambda i, o: draw(i, horiz="opposite")),
    ("horizontal leg is drawn one row below the marker row",
     lambda i, o: draw(i, horiz="down1")),
    ("header with no marker gets no line",
     lambda i, o: draw(i, unmarked="none")),
    ("every line turns at the lowest marker row instead of its own marker row",
     lambda i, o: draw(i, lowest=True)),
    ("output drops the header row (off-by-one crop)",
     lambda i, o: [r[:] for r in o[1:]]),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/29700607.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for p in pairs:
        assert draw(p["input"]) == p["output"], "reference drawing mismatch"
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
