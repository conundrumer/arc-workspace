"""Near-miss readings for task 7e0986d6.

True rule: background 0; the most common non-background color forms solid
rectangles; the other color is sprinkle noise. Sprinkle cells inside a
rectangle become rectangle color; sprinkle cells outside become background.
"""
import json
from collections import Counter
from pathlib import Path

BG = 0


def _copy(g):
    return [row[:] for row in g]


def _colors(inp, out):
    cnt = Counter(v for row in out for v in row if v != BG)
    rect = cnt.most_common(1)[0][0]
    spr = sorted({v for row in inp for v in row if v not in (BG, rect)})
    return rect, spr


def _sprinkle_cells(inp, out):
    rect, spr = _colors(inp, out)
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v in spr]


def keep_input(inp, out):
    return _copy(inp)


def remove_all_sprinkles(inp, out):
    g = _copy(out)
    for r, c in _sprinkle_cells(inp, out):
        g[r][c] = BG
    return g


def keep_inside_sprinkles(inp, out):
    g = _copy(out)
    for r, c in _sprinkle_cells(inp, out):
        if out[r][c] != BG:
            g[r][c] = inp[r][c]
    return g


def keep_outside_sprinkles(inp, out):
    g = _copy(out)
    for r, c in _sprinkle_cells(inp, out):
        if out[r][c] == BG:
            g[r][c] = inp[r][c]
    return g


def recolor_outside_sprinkles(inp, out):
    rect, _ = _colors(inp, out)
    g = _copy(out)
    for r, c in _sprinkle_cells(inp, out):
        g[r][c] = rect
    return g


def swapped_roles(inp, out):
    rect, spr = _colors(inp, out)
    return [[v if v in spr else BG for v in row] for row in inp]


def interior_only_fill(inp, out):
    rect, _ = _colors(inp, out)
    h, w = len(inp), len(inp[0])
    g = _copy(out)
    for r, c in _sprinkle_cells(inp, out):
        if out[r][c] == rect:
            ok = all(
                0 <= r + dr < h and 0 <= c + dc < w and inp[r + dr][c + dc] == rect
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
            if not ok:
                g[r][c] = BG
    return g


def crop_to_content(inp, out):
    rows = [r for r, row in enumerate(out) if any(v != BG for v in row)]
    cols = [c for c in range(len(out[0])) if any(row[c] != BG for row in out)]
    if not rows:
        return None
    return [row[cols[0]:cols[-1] + 1] for row in out[rows[0]:rows[-1] + 1]]


def fill_only_largest_rect(inp, out):
    rect, _ = _colors(inp, out)
    h, w = len(out), len(out[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if out[r][c] == rect and (r, c) not in seen:
                comp, stack = [], [(r, c)]
                seen.add((r, c))
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and out[ny][nx] == rect and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                comps.append(comp)
    if len(comps) < 2:
        return None
    comps.sort(key=len, reverse=True)
    g = _copy(out)
    for comp in comps[1:]:
        for y, x in comp:
            if inp[y][x] != rect:
                g[y][x] = BG
    return g


def flip_horizontal(inp, out):
    return [row[::-1] for row in out]


def transpose_output(inp, out):
    return [list(col) for col in zip(*out)]


ALTERNATIVES = [
    ("Leave the grid as given: sprinkles are not touched", keep_input),
    ("Delete every sprinkle cell, including those inside rectangles (no fill)", remove_all_sprinkles),
    ("Remove sprinkles outside rectangles but keep sprinkle color inside rectangles", keep_inside_sprinkles),
    ("Fill sprinkles inside rectangles but leave sprinkles outside in place", keep_outside_sprinkles),
    ("Recolor every sprinkle to rectangle color, also those outside rectangles", recolor_outside_sprinkles),
    ("Swap roles: treat the rarer color as the shape and erase the rectangle color", swapped_roles),
    ("Fill only sprinkles fully surrounded on four sides; edge sprinkles are erased", interior_only_fill),
    ("Crop the result to the bounding box of all non-background cells", crop_to_content),
    ("Fill sprinkles only in the largest rectangle; erase them in other rectangles", fill_only_largest_rect),
    ("Correct cleaning but the result is mirrored left to right", flip_horizontal),
    ("Correct cleaning but the result is transposed", transpose_output),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(row, list) and len(row) == len(g[0]) and len(row) > 0 for row in g):
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for row in g for v in row):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/7e0986d6.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            if _valid(fn(p["input"], p["output"]), p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
