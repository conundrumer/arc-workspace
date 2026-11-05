import json
from collections import Counter
from pathlib import Path


def bgcolor(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def components(g, diag=True):
    bg = bgcolor(g)
    h, w = len(g), len(g[0])
    seen = set()
    objs = []
    if diag:
        steps = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
    else:
        steps = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            col = g[r][c]
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in steps:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and g[ny][nx] == col:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            objs.append({"color": col, "cells": cells, "box": (min(ys), min(xs), max(ys), max(xs))})
    return objs


def blank(g):
    bg = bgcolor(g)
    return [[bg] * len(g[0]) for _ in g]


def shapes_by_color(objs):
    sh = {}
    for o in objs:
        r0, c0, _, _ = o["box"]
        sh.setdefault(o["color"], set()).update((y - r0, x - c0) for y, x in o["cells"])
    return sh


def shape_dims(s):
    return max(p[0] for p in s) + 1, max(p[1] for p in s) + 1


def solve(inp, diag=True, recolor="swap", shape="other", anchor="tl", flip=None,
          keep_input=False, only=None, one_per_color=False):
    objs = components(inp, diag)
    sh = shapes_by_color(objs)
    colors = sorted(sh)
    if len(colors) != 2:
        return None
    out = [row[:] for row in inp] if keep_input else blank(inp)
    h, w = len(inp), len(inp[0])
    done = set()
    for o in objs:
        c = o["color"]
        other = colors[1] if c == colors[0] else colors[0]
        if only is not None and c != colors[only]:
            continue
        if one_per_color:
            if c in done:
                continue
            done.add(c)
        s = sh[other] if shape == "other" else sh[c]
        paint = other if recolor == "swap" else c
        r0, c0, r1, c1 = o["box"]
        sh_h, sh_w = shape_dims(s)
        bh, bw = r1 - r0 + 1, c1 - c0 + 1
        for dy, dx in s:
            if flip == "h":
                dx = sh_w - 1 - dx
            elif flip == "v":
                dy = sh_h - 1 - dy
            elif flip == "hv":
                dx = sh_w - 1 - dx
                dy = sh_h - 1 - dy
            if anchor == "tl":
                y, x = r0 + dy, c0 + dx
            elif anchor == "br":
                y, x = r1 - (sh_h - 1 - dy), c1 - (sh_w - 1 - dx)
            elif anchor == "shift":
                y, x = r0 + dy, c0 + dx + 1
            if 0 <= y < h and 0 <= x < w:
                out[y][x] = paint
    return out


def true_out(inp):
    return solve(inp)


def swap_in_place(inp, out):
    cols = sorted({v for r in inp for v in r} - {bgcolor(inp)})
    if len(cols) != 2:
        return None
    m = {cols[0]: cols[1], cols[1]: cols[0]}
    return [[m.get(v, v) for v in r] for r in inp]


def true_with_one_color_unpainted(inp, out):
    # the true output with one color's painted cells erased
    cols = sorted({v for r in out for v in r} - {bgcolor(out)})
    if len(cols) != 2:
        return None
    bg = bgcolor(out)
    return [[bg if v == cols[0] else v for v in r] for r in out]


def true_with_other_painted_cells_to_bg(inp, out):
    cols = sorted({v for r in out for v in r} - {bgcolor(out)})
    if len(cols) != 2:
        return None
    bg = bgcolor(out)
    return [[bg if v == cols[1] else v for v in r] for r in out]


def crop_to_bbox_union(inp, out):
    objs = components(inp)
    r0 = min(o["box"][0] for o in objs)
    c0 = min(o["box"][1] for o in objs)
    r1 = max(o["box"][2] for o in objs)
    c1 = max(o["box"][3] for o in objs)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def paint_extra_row(inp, out):
    # off-by-one: shapes painted one row too low
    bg = bgcolor(out)
    h, w = len(out), len(out[0])
    new = [[bg] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if out[y][x] != bg:
                if y + 1 >= h:
                    return None
                new[y + 1][x] = out[y][x]
    return new


ALTERNATIVES = [
    ("Shape is swapped but colors are not: each object gets the other color's shape in its own color",
     lambda i, o: solve(i, recolor="own")),
    ("Colors are swapped in place; each object keeps its own shape",
     swap_in_place),
    ("Objects are found with 4-connectivity, so diagonal links do not join cells into one object",
     lambda i, o: solve(i, diag=False)),
    ("The input objects are not erased; the swapped shapes are painted over the input",
     lambda i, o: solve(i, keep_input=True)),
    ("Swapped shape is mirrored left to right inside each object's box",
     lambda i, o: solve(i, flip="h")),
    ("Swapped shape is mirrored top to bottom inside each object's box",
     lambda i, o: solve(i, flip="v")),
    ("Swapped shape is rotated 180 degrees inside each object's box",
     lambda i, o: solve(i, flip="hv")),
    ("Swapped shape is placed one column to the right of the box",
     lambda i, o: solve(i, anchor="shift")),
    ("Only objects of the lower-numbered color are swapped; the other color's objects are dropped",
     lambda i, o: solve(i, only=0)),
    ("Only objects of the higher-numbered color are swapped; the other color's objects are dropped",
     lambda i, o: solve(i, only=1)),
    ("Only the first object of each color is swapped; later objects are dropped",
     lambda i, o: solve(i, one_per_color=True)),
    ("Painted cells are shifted one row down",
     paint_extra_row),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/3391f8c0.json").read_text())
    pairs = task["train"]
    for p in pairs:
        assert true_out(p["input"]) == p["output"], "reference mismatch"
    print("task 3391f8c0:", len(ALTERNATIVES), "readings,", len(pairs), "train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
