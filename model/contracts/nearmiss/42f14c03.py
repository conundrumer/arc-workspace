"""Near-miss readings for ARC task 42f14c03.

Rule: the background is the most common color. Of the other objects, the frame
is the one whose bounding-box holes can all be filled by other objects of the
same shape. The output is the frame's bounding box, with each hole painted in
the color of the object that fits it.
"""
import json
from collections import Counter
from pathlib import Path


def _solve_parts(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(c for r in inp for c in r).most_common(1)[0][0]
    seen = set()
    objs = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            col = inp[r][c]
            stack, cells = [(r, c)], set()
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                cells.add((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] == col:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            objs.append({"color": col, "cells": cells})
    for o in objs:
        ys = [y for y, _ in o["cells"]]
        xs = [x for _, x in o["cells"]]
        o["box"] = (min(ys), min(xs), max(ys), max(xs))
        o["pattern"] = frozenset((y - o["box"][0], x - o["box"][1]) for y, x in o["cells"])
    for o in objs:
        y0, x0, y1, x1 = o["box"]
        hole_cells = {(y, x) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)} - o["cells"]
        holes, hs = [], set()
        for cell in sorted(hole_cells):
            if cell in hs:
                continue
            stack, comp = [cell], set()
            hs.add(cell)
            while stack:
                y, x = stack.pop()
                comp.add((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (y + dy, x + dx)
                    if n in hole_cells and n not in hs:
                        hs.add(n)
                        stack.append(n)
            pat = frozenset((y - y0, x - x0) for y, x in comp)
            fillers = [p for p in objs if p is not o and p["pattern"] == _norm(pat)]
            holes.append({"cells": comp, "pattern": pat, "fillers": fillers})
        o["holes"] = holes
    return bg, objs


def _norm(pat):
    my = min(y for y, _ in pat)
    mx = min(x for _, x in pat)
    return frozenset((y - my, x - mx) for y, x in pat)


def _frame(objs):
    for o in objs:
        if o["holes"] and all(hl["fillers"] for hl in o["holes"]):
            return o
    return None


def _crop(inp, y0, x0, y1, x1):
    h, w = len(inp), len(inp[0])
    y0, x0 = max(y0, 0), max(x0, 0)
    y1, x1 = min(y1, h - 1), min(x1, w - 1)
    return [row[x0:x1 + 1] for row in inp[y0:y1 + 1]]


def _render(inp, frame, colors):
    """Crop the frame box; paint hole i with colors[i] (None keeps the input)."""
    y0, x0, y1, x1 = frame["box"]
    g = _crop(inp, y0, x0, y1, x1)
    for hl, col in zip(frame["holes"], colors):
        if col is None:
            continue
        for y, x in hl["cells"]:
            g[y - y0][x - x0] = col
    return g


def _setup(inp):
    bg, objs = _solve_parts(inp)
    fr = _frame(objs)
    return bg, objs, fr


def _true_colors(fr):
    return [hl["fillers"][0]["color"] for hl in fr["holes"]]


def holes_left_as_frame_color(inp, out):
    bg, objs, fr = _setup(inp)
    return _render(inp, fr, [fr["color"]] * len(fr["holes"]))


def only_first_hole_filled(inp, out):
    bg, objs, fr = _setup(inp)
    cols = _true_colors(fr)
    order = sorted(range(len(cols)), key=lambda i: min(fr["holes"][i]["cells"]))
    keep = order[0]
    return _render(inp, fr, [c if i == keep else fr["color"] for i, c in enumerate(cols)])


def holes_left_as_background(inp, out):
    bg, objs, fr = _setup(inp)
    return _render(inp, fr, [None] * len(fr["holes"]))


def other_holed_object_cropped(inp, out):
    bg, objs, fr = _setup(inp)
    cands = [o for o in objs if o["holes"] and o is not fr]
    if not cands:
        return None
    o = max(cands, key=lambda p: (p["box"][2] - p["box"][0] + 1) * (p["box"][3] - p["box"][1] + 1))
    return _crop(inp, *o["box"])


def frame_and_fill_colors_swapped(inp, out):
    bg, objs, fr = _setup(inp)
    cols = _true_colors(fr)
    first = cols[0]
    y0, x0, y1, x1 = fr["box"]
    g = _render(inp, fr, cols)
    hole_cells = {(y - y0, x - x0) for hl in fr["holes"] for y, x in hl["cells"]}
    for y in range(len(g)):
        for x in range(len(g[0])):
            g[y][x] = fr["color"] if (y, x) in hole_cells else first
    return g


def output_rotated_clockwise(inp, out):
    h, w = len(out), len(out[0])
    return [[out[h - 1 - j][i] for j in range(h)] for i in range(w)]


def output_mirrored_left_right(inp, out):
    return [row[::-1] for row in out]


def crop_with_one_cell_margin(inp, out):
    bg, objs, fr = _setup(inp)
    y0, x0, y1, x1 = fr["box"]
    return _crop(inp, y0 - 1, x0 - 1, y1 + 1, x1 + 1)


def crop_missing_last_row_and_column(inp, out):
    return [row[:-1] for row in out[:-1]]


def output_is_first_filler_piece(inp, out):
    bg, objs, fr = _setup(inp)
    fills = []
    for hl in fr["holes"]:
        fills.append(hl["fillers"][0])
    first = min(fills, key=lambda p: min(p["cells"]))
    return _crop(inp, *first["box"])


def fillers_assigned_in_scan_order(inp, out):
    bg, objs, fr = _setup(inp)
    pieces = sorted(
        {id(hl["fillers"][0]): hl["fillers"][0] for hl in fr["holes"]}.values(),
        key=lambda p: min(p["cells"]),
    )
    order = sorted(range(len(fr["holes"])), key=lambda i: min(fr["holes"][i]["cells"]))
    cols = [None] * len(fr["holes"])
    for rank, i in enumerate(order):
        cols[i] = pieces[rank % len(pieces)]["color"]
    return _render(inp, fr, cols)


ALTERNATIVES = [
    ("holes painted with the frame color instead of the fitting piece color", holes_left_as_frame_color),
    ("only the first hole in scan order is filled", only_first_hole_filled),
    ("frame box cropped from the input, holes left as background", holes_left_as_background),
    ("a different object that has holes is picked as the frame and cropped", other_holed_object_cropped),
    ("frame cells and hole cells swap colors", frame_and_fill_colors_swapped),
    ("correct output rotated 90 degrees clockwise", output_rotated_clockwise),
    ("correct output mirrored left to right", output_mirrored_left_right),
    ("frame box taken with a one-cell margin on every side", crop_with_one_cell_margin),
    ("frame box one row and one column too small", crop_missing_last_row_and_column),
    ("output is only the first filler piece, cropped", output_is_first_filler_piece),
    ("pieces assigned to holes by scan order instead of by shape", fillers_assigned_in_scan_order),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(c) is int and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/42f14c03.json"))
    train = task["train"]
    for pair in train:
        bg, objs, fr = _setup(pair["input"])
        assert _render(pair["input"], fr, _true_colors(fr)) == pair["output"], "reference solver wrong"
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for pair in train:
            g = fn(pair["input"], pair["output"])
            if g is not None and _valid(g) and g != pair["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
