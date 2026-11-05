import json
from collections import Counter
from pathlib import Path


def _segments(flags):
    segs, start = [], None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        if not f and start is not None:
            segs.append((start, i - 1))
            start = None
    if start is not None:
        segs.append((start, len(flags) - 1))
    return segs


def _info(inp):
    h, w = len(inp), len(inp[0])
    rows = _segments([any(inp[r][c] for c in range(w)) for r in range(h)])
    cols = _segments([any(inp[r][c] for r in range(h)) for c in range(w)])
    cnt = Counter(v for row in inp for v in row if v)
    base = cnt.most_common(1)[0][0]
    marks = [(r, c) for r in range(h) for c in range(w) if inp[r][c] not in (0, base)]
    if not marks:
        return None
    mr, mc = marks[0]
    mark = inp[mr][mc]
    bi = next(i for i, (a, b) in enumerate(rows) if a <= mr <= b)
    bj = next(i for i, (a, b) in enumerate(cols) if a <= mc <= b)
    return dict(h=h, w=w, rows=rows, cols=cols, base=base, mark=mark,
                mr=mr, mc=mc, bi=bi, bj=bj)


def _paint_blocks(inp, pred, color=None, base_only=True):
    d = _info(inp)
    g = [r[:] for r in inp]
    col = d["mark"] if color is None else color
    for i, (r0, r1) in enumerate(d["rows"]):
        for j, (c0, c1) in enumerate(d["cols"]):
            if pred(i, j, d):
                for r in range(r0, r1 + 1):
                    for c in range(c0, c1 + 1):
                        if not base_only or inp[r][c] == d["base"]:
                            g[r][c] = col
    return g


def row_only(inp, out):
    return _paint_blocks(inp, lambda i, j, d: i == d["bi"])


def col_only(inp, out):
    return _paint_blocks(inp, lambda i, j, d: j == d["bj"])


def fill_all(inp, out):
    return _paint_blocks(inp, lambda i, j, d: True)


def hole(inp, out):
    d = _info(inp)
    g = [r[:] for r in out]
    r0, r1 = d["rows"][d["bi"]]
    c0, c1 = d["cols"][d["bj"]]
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            g[r][c] = d["base"]
    return g


def rays_forward(inp, out):
    return _paint_blocks(inp, lambda i, j, d: (i == d["bi"] and j >= d["bj"]) or (j == d["bj"] and i >= d["bi"]))


def neighbors(inp, out):
    return _paint_blocks(inp, lambda i, j, d: (i == d["bi"] and abs(j - d["bj"]) <= 1) or (j == d["bj"] and abs(i - d["bi"]) <= 1))


def diagonals(inp, out):
    return _paint_blocks(inp, lambda i, j, d: abs(i - d["bi"]) == abs(j - d["bj"]))


def pixel_lines(inp, out):
    d = _info(inp)
    g = [r[:] for r in inp]
    for r in range(d["h"]):
        for c in range(d["w"]):
            if inp[r][c] == d["base"] and (r == d["mr"] or c == d["mc"]):
                g[r][c] = d["mark"]
    return g


def dividers_too(inp, out):
    d = _info(inp)
    g = [r[:] for r in out]
    r0, r1 = d["rows"][d["bi"]]
    c0, c1 = d["cols"][d["bj"]]
    for r in range(d["h"]):
        for c in range(d["w"]):
            if (r0 <= r <= r1 or c0 <= c <= c1) and inp[r][c] == 0:
                g[r][c] = d["mark"]
    return g


def swap_colors(inp, out):
    d = _info(inp)
    g = [r[:] for r in out]
    for r in range(d["h"]):
        for c in range(d["w"]):
            if out[r][c] == d["mark"]:
                g[r][c] = d["base"]
            elif out[r][c] == d["base"]:
                g[r][c] = d["mark"]
    return g


ALTERNATIVES = [
    ("paint only the block row of the mark, not its block column", row_only),
    ("paint only the block column of the mark, not its block row", col_only),
    ("paint every block with the mark color", fill_all),
    ("paint the cross but leave the mark block itself in the base color", hole),
    ("paint only rightward and downward from the mark block", rays_forward),
    ("paint only blocks adjacent to the mark block in its row and column", neighbors),
    ("paint blocks on the diagonals through the mark block", diagonals),
    ("paint only the one-cell-thick pixel row and column of the mark pixels", pixel_lines),
    ("paint the divider cells along the mark row and column too", dividers_too),
    ("swap the base and mark colors in the true output", swap_colors),
    ("paint nothing: return the input unchanged", lambda inp, out: [r[:] for r in inp]),
]


def _valid(g, out):
    if g is None:
        return False
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/4f537728.json"))
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in train)
        print(f"{n}/{len(train)}  {desc}")
