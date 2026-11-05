import json
from collections import Counter
from pathlib import Path

DIRS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}


def _analyse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    ink = Counter({k: v for k, v in cnt.items() if k != bg})
    shape = ink.most_common(1)[0][0]
    markers = []
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v != bg and v != shape:
                # component of non-bg cells (4-connected) holding the marker
                seen = {(r, c)}
                st = [(r, c)]
                while st:
                    a, b = st.pop()
                    for da, db in DIRS.values():
                        x, y = a + da, b + db
                        if 0 <= x < h and 0 <= y < w and (x, y) not in seen and inp[x][y] != bg:
                            seen.add((x, y))
                            st.append((x, y))
                r0 = min(a for a, _ in seen)
                r1 = max(a for a, _ in seen)
                c0 = min(b for _, b in seen)
                c1 = max(b for _, b in seen)
                d = "U" if r == r0 else "D" if r == r1 else "L" if c == c0 else "R"
                markers.append((r, c, v, d))
    return bg, shape, markers


def _render(inp, dirfn=lambda d: [d], spacing=2, start=2, edge=True, dots=True,
            colorfn=None, corner="new", inset=0):
    h, w = len(inp), len(inp[0])
    bg, shape, markers = _analyse(inp)
    g = [row[:] for row in inp]
    lines = []  # (kind, index, color)
    for (r, c, col, d) in markers:
        if colorfn:
            col = colorfn(col, shape, bg)
        for dd in dirfn(d):
            dr, dc = DIRS[dd]
            if dots:
                k = start
                while True:
                    x, y = r + dr * k, c + dc * k
                    if not (0 <= x < h and 0 <= y < w):
                        break
                    g[x][y] = col
                    k += spacing
            if edge:
                if dd == "U":
                    lines.append(("row", inset, col))
                elif dd == "D":
                    lines.append(("row", h - 1 - inset, col))
                elif dd == "L":
                    lines.append(("col", inset, col))
                else:
                    lines.append(("col", w - 1 - inset, col))
    for kind, i, col in lines:
        if kind == "row":
            for y in range(w):
                g[i][y] = col
        else:
            for x in range(h):
                g[x][i] = col
    for a in lines:
        for b in lines:
            if a[0] == "row" and b[0] == "col":
                cc = {"new": 0, "row": a[2], "col": b[2]}[corner]
                g[a[1]][b[1]] = cc
    return g


OPP = {"U": "D", "D": "U", "L": "R", "R": "L"}
CW = {"U": "R", "R": "D", "D": "L", "L": "U"}
TRANSPOSE = {"U": "L", "L": "U", "D": "R", "R": "D"}


def _true(inp):
    return _render(inp)


def corner_marker_color(inp, out):
    return _render(inp, corner="row")


def no_edge(inp, out):
    return _render(inp, edge=False)


def no_dots(inp, out):
    return _render(inp, dots=False)


def solid_trail(inp, out):
    return _render(inp, spacing=1, start=1)


def spacing_three(inp, out):
    return _render(inp, spacing=3, start=3)


def odd_offset(inp, out):
    return _render(inp, spacing=2, start=1)


def reversed_dir(inp, out):
    return _render(inp, dirfn=lambda d: [OPP[d]])


def rotated_dir(inp, out):
    return _render(inp, dirfn=lambda d: [CW[d]])


def transposed_dir(inp, out):
    return _render(inp, dirfn=lambda d: [TRANSPOSE[d]])


def both_ways(inp, out):
    return _render(inp, dirfn=lambda d: [d, OPP[d]])


def shape_color(inp, out):
    return _render(inp, colorfn=lambda col, shape, bg: shape)


def edge_inset(inp, out):
    return _render(inp, inset=1)


ALTERNATIVES = [
    ("corner where two edges meet takes the horizontal-edge marker colour instead of the new colour", corner_marker_color),
    ("trail dots only; the border line is not drawn", no_edge),
    ("border line only; no dotted trail", no_dots),
    ("trail is a solid line (spacing 1)", solid_trail),
    ("trail dots every 3 cells", spacing_three),
    ("trail dots start one cell from the marker (odd offsets)", odd_offset),
    ("marker direction reversed (points into the shape)", reversed_dir),
    ("marker direction rotated 90 degrees clockwise", rotated_dir),
    ("marker direction read with rows and columns swapped", transposed_dir),
    ("trail and border fire both ways from the marker", both_ways),
    ("trail and border use the shape colour, not the marker colour", shape_color),
    ("border line drawn one cell inside the grid edge", edge_inset),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/13f06aa5.json"))
    pairs = task["train"]
    # sanity: the model of the true rule reproduces the true outputs
    ok = sum(_true(p["input"]) == p["output"] for p in pairs)
    print(f"true-rule reproduction: {ok}/{len(pairs)}")
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if (g is not None and isinstance(g, list) and g
                    and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                    and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                    and g != p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
