from collections import Counter
from pathlib import Path
import json


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _copy(g):
    return [list(r) for r in g]


def _replace(out, src, dst):
    return [[dst if v == src else v for v in r] for r in out]


def no_outline(inp, out):
    return _replace(out, 3, _bg(inp))


def no_fill(inp, out):
    return _replace(out, 4, _bg(inp))


def fill_as_outline_color(inp, out):
    return _replace(out, 4, 3)


def swapped_colors(inp, out):
    return [[4 if v == 3 else 3 if v == 4 else v for v in r] for r in out]


def outline_in_shape_color(inp, out):
    return _replace(out, 3, 6)


def outline_orthogonal_only(inp, out):
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    res = _copy(out)
    for r in range(h):
        for c in range(w):
            if out[r][c] != 3:
                continue
            ortho = any(
                0 <= r + dr < h and 0 <= c + dc < w and inp[r + dr][c + dc] != bg
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
            if not ortho:
                res[r][c] = bg
    return res


def outline_width_two(inp, out):
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    res = _copy(out)
    for r in range(h):
        for c in range(w):
            if out[r][c] != bg:
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] != bg:
                        res[r][c] = 3
    return res


def outline_above_left_only(inp, out):
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    res = _copy(out)
    for r in range(h):
        for c in range(w):
            if out[r][c] != 3:
                continue
            ok = any(
                0 <= r + dr < h and 0 <= c + dc < w and inp[r + dr][c + dc] != bg
                for dr in (0, 1)
                for dc in (0, 1)
                if (dr, dc) != (0, 0)
            )
            if not ok:
                res[r][c] = bg
    return res


def fill_shape_interior_too(inp, out):
    # Also recolor shape cells that are not on the border of the shape's bounding box.
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    seen = set()
    res = _copy(out)
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            comp, stack = [], [(r, c)]
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        yy, xx = y + dy, x + dx
                        if (0 <= yy < h and 0 <= xx < w and (yy, xx) not in seen
                                and inp[yy][xx] != bg):
                            seen.add((yy, xx))
                            stack.append((yy, xx))
            y0 = min(p[0] for p in comp)
            y1 = max(p[0] for p in comp)
            x0 = min(p[1] for p in comp)
            x1 = max(p[1] for p in comp)
            for y, x in comp:
                if y0 < y < y1 and x0 < x < x1:
                    res[y][x] = 4
    return res


def crop_to_content(inp, out):
    h, w = len(out), len(out[0])
    bg = _bg(inp)
    cells = [(r, c) for r in range(h) for c in range(w) if out[r][c] != bg]
    if not cells:
        return None
    r0 = min(p[0] for p in cells)
    r1 = max(p[0] for p in cells)
    c0 = min(p[1] for p in cells)
    c1 = max(p[1] for p in cells)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def only_largest_shape_processed(inp, out):
    # Rule applied to the largest shape only; the other shapes stay as in the input.
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            comp, stack = [], [(r, c)]
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        yy, xx = y + dy, x + dx
                        if (0 <= yy < h and 0 <= xx < w and (yy, xx) not in seen
                                and inp[yy][xx] != bg):
                            seen.add((yy, xx))
                            stack.append((yy, xx))
            comps.append(comp)
    if len(comps) < 2:
        return None
    comps.sort(key=len, reverse=True)
    res = _copy(out)
    for comp in comps[1:]:
        y0 = min(p[0] for p in comp)
        y1 = max(p[0] for p in comp)
        x0 = min(p[1] for p in comp)
        x1 = max(p[1] for p in comp)
        for y in range(max(0, y0 - 1), min(h, y1 + 2)):
            for x in range(max(0, x0 - 1), min(w, x1 + 2)):
                if inp[y][x] == bg and res[y][x] in (3, 4):
                    res[y][x] = bg
    return res


ALTERNATIVES = [
    ("outline step skipped: no 3 ring around shapes", no_outline),
    ("fill step skipped: enclosed background left as background", no_fill),
    ("enclosed background filled with the outline color 3", fill_as_outline_color),
    ("fill and outline colors swapped (fill 3, outline 4)", swapped_colors),
    ("outline drawn in the shape's own color instead of 3", outline_in_shape_color),
    ("outline uses only orthogonal neighbors, corners missing", outline_orthogonal_only),
    ("outline ring two cells wide instead of one", outline_width_two),
    ("outline drawn only on the up/left sides of each shape", outline_above_left_only),
    ("shape cells off the bounding-box border also recolored to the fill color", fill_shape_interior_too),
    ("output cropped to the bounding box of the non-background content", crop_to_content),
    ("outline and fill applied to the largest shape only", only_largest_shape_processed),
]


def _valid(g, t):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != t)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/543a7ed5.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = sum(1 for p in pairs if (g := fn(p["input"], p["output"])) is not None
                and _valid(g, p["output"]))
        print(n, desc)
