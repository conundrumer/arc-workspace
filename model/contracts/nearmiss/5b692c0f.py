"""Near-miss rules for 5b692c0f.

Rule: each object has a mark color (4) drawn as an axis line plus a few
off-axis cells. The object is mirrored across its axis: the side with more
cells is copied onto the other side.
"""
import json
from collections import Counter
from pathlib import Path


def background(g):
    return Counter(v for row in g for v in row).most_common(1)[0][0]


def components(g):
    bg = background(g)
    h, w = len(g), len(g[0])
    seen, objs = set(), []
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            stack, cells = [(r, c)], []
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h and 0 <= nx < w and g[ny][nx] != bg
                                and (ny, nx) not in seen):
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            objs.append(cells)
    return objs


def analyze(g, cells):
    cnt = Counter(g[r][c] for r, c in cells)
    main = cnt.most_common(1)[0][0]
    marks = [(r, c) for r, c in cells if g[r][c] != main]
    lines = Counter()
    for r, c in marks:
        lines[("r", r)] += 1
        lines[("c", c)] += 1
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return {
        "cells": cells, "marks": marks, "lines": lines,
        "box": (min(rs), max(rs), min(cs), max(cs)),
        "markcolor": [v for v in cnt if v != main][0] if len(cnt) > 1 else None,
    }


def best_line(o):
    return sorted(o["lines"].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def worst_line(o):
    return sorted(o["lines"].items(), key=lambda kv: (kv[1], kv[0]))[0][0]


def side(orient, L, r, c):
    v = c - L if orient == "c" else r - L
    return (v > 0) - (v < 0)


def src_more(o, orient, L):
    n = Counter(side(orient, L, r, c) for r, c in o["cells"])
    return 1 if n[1] >= n[-1] else -1


def src_fewer(o, orient, L):
    return -src_more(o, orient, L)


def src_far(o, orient, L):
    return 1


def mirror(inp, line=best_line, src=src_more, shift=0, rotate=False,
           skip_last=False, nozero=False, recolor=None):
    out = [row[:] for row in inp]
    h, w = len(inp), len(inp[0])
    objs = [analyze(inp, cells) for cells in components(inp)]
    if skip_last:
        objs = objs[:-1]
    for o in objs:
        if not o["lines"]:
            continue
        orient, L = line(o)
        L += shift
        s = src(o, orient, L)
        r0, r1, c0, c1 = o["box"]
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if side(orient, L, r, c) != s:
                    continue
                if orient == "c":
                    pr, pc = (r0 + r1 - r if rotate else r), 2 * L - c
                else:
                    pr, pc = 2 * L - r, (c0 + c1 - c if rotate else c)
                if not (0 <= pr < h and 0 <= pc < w):
                    continue
                v = inp[r][c]
                if nozero and v == 0:
                    continue
                out[pr][pc] = v if recolor is None else (recolor if v else 0)
    return out


def recolor_new(inp, out):
    """True output, with the cells that were added painted in the mark color."""
    objs = [analyze(inp, cells) for cells in components(inp)]
    mark = next((o["markcolor"] for o in objs if o["markcolor"]), 4)
    return [[mark if out[r][c] != inp[r][c] and out[r][c] != 0 else out[r][c]
             for c in range(len(out[0]))] for r in range(len(out))]


def keep_marks_only_fill(inp, out):
    """True output, but cells the mirror removed are kept (no clearing)."""
    return [[inp[r][c] if out[r][c] == 0 else out[r][c]
             for c in range(len(out[0]))] for r in range(len(out))]


def no_extension(inp, out):
    """True output cropped to the input's own object boxes (no growth outside them)."""
    objs = [analyze(inp, cells) for cells in components(inp)]
    res = [row[:] for row in inp]
    for o in objs:
        r0, r1, c0, c1 = o["box"]
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                res[r][c] = out[r][c]
    return res


ALTERNATIVES = [
    ("no mirroring: the input is the answer", lambda i, o: [r[:] for r in i]),
    ("source side is the side with fewer cells", lambda i, o: mirror(i, src=src_fewer)),
    ("source side is always the lower or right side", lambda i, o: mirror(i, src=src_far)),
    ("mirror across the line through the object's box center, perpendicular to the axis",
     lambda i, o: mirror(i, line=lambda ob: (("r", (ob["box"][0] + ob["box"][1]) // 2)
                                            if best_line(ob)[0] == "c"
                                            else ("c", (ob["box"][2] + ob["box"][3]) // 2)))),
    ("mirror line is one cell off the axis", lambda i, o: mirror(i, shift=1)),
    ("mirror line is the line with the fewest mark cells", lambda i, o: mirror(i, line=worst_line)),
    ("point-reflect (rotate 180 degrees) instead of mirror", lambda i, o: mirror(i, rotate=True)),
    ("the last object is left unfixed", lambda i, o: mirror(i, skip_last=True)),
    ("only paste source cells, never clear target cells", lambda i, o: mirror(i, nozero=True)),
    ("added cells are painted in the mark color", recolor_new),
    ("cells that the mirror clears stay in place", keep_marks_only_fill),
    ("mirroring is clipped to the object's original box", no_extension),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/5b692c0f.json"))
    pairs = task["train"]
    # sanity: the correct reading reproduces the true outputs
    print("correct reading matches:", [mirror(p["input"]) == p["output"] for p in pairs])
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
