import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _flood(inp, sources, diag=False):
    """Background cells reachable from the given source cells through background cells."""
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diag:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    seen = set(p for p in sources if inp[p[0]][p[1]] == bg)
    stack = list(seen)
    while stack:
        y, x = stack.pop()
        for dy, dx in steps:
            a, b = y + dy, x + dx
            if 0 <= a < h and 0 <= b < w and (a, b) not in seen and inp[a][b] == bg:
                seen.add((a, b))
                stack.append((a, b))
    return seen


def _border(inp, top=True, bottom=True, left=True, right=True):
    h, w = len(inp), len(inp[0])
    s = []
    for x in range(w):
        if top:
            s.append((0, x))
        if bottom:
            s.append((h - 1, x))
    for y in range(h):
        if left:
            s.append((y, 0))
        if right:
            s.append((y, w - 1))
    return s


def _regions(inp):
    """Enclosed background regions (4-connected), as lists of cells."""
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    outside = _flood(inp, _border(inp))
    seen = set(outside)
    regs = []
    for y in range(h):
        for x in range(w):
            if inp[y][x] == bg and (y, x) not in seen:
                reg = [(y, x)]
                seen.add((y, x))
                i = 0
                while i < len(reg):
                    cy, cx = reg[i]
                    i += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        a, b = cy + dy, cx + dx
                        if 0 <= a < h and 0 <= b < w and (a, b) not in seen and inp[a][b] == bg:
                            seen.add((a, b))
                            reg.append((a, b))
                regs.append(reg)
    return regs


def _colors(inp, out):
    bg = _bg(inp)
    outside = _flood(inp, _border(inp))
    y, x = next(iter(outside))
    out_col = out[y][x]
    inside = [(y, x) for y in range(len(inp)) for x in range(len(inp[0]))
              if inp[y][x] == bg and (y, x) not in outside]
    in_col = out[inside[0][0]][inside[0][1]] if inside else None
    line = Counter(v for r in inp for v in r if v != bg).most_common(1)[0][0]
    return bg, out_col, in_col, line


def _build(inp, outside_col, fill_for, line_col=None):
    """fill_for(y, x) -> colour for a background cell; line cells keep line_col or input."""
    bg = _bg(inp)
    return [[fill_for(y, x) if inp[y][x] == bg else (inp[y][x] if line_col is None else line_col)
             for x in range(len(inp[0]))] for y in range(len(inp))]


def a_inside_as_outside(inp, out):
    bg, oc, ic, line = _colors(inp, out)
    return [[oc if v == ic else v for v in r] for r in out]


def a_outside_unchanged(inp, out):
    bg, oc, ic, line = _colors(inp, out)
    return [[bg if v == oc else v for v in r] for r in out]


def a_inside_line_color(inp, out):
    bg, oc, ic, line = _colors(inp, out)
    return [[line if v == ic else v for v in r] for r in out]


def a_swap_fills(inp, out):
    bg, oc, ic, line = _colors(inp, out)
    return [[ic if v == oc else oc if v == ic else v for v in r] for r in out]


def a_bbox_fill(inp, out):
    bg, oc, ic, line = _colors(inp, out)
    cells = [(y, x) for y in range(len(inp)) for x in range(len(inp[0])) if inp[y][x] != bg]
    y0 = min(c[0] for c in cells)
    y1 = max(c[0] for c in cells)
    x0 = min(c[1] for c in cells)
    x1 = max(c[1] for c in cells)
    return _build(inp, oc, lambda y, x: ic if y0 <= y <= y1 and x0 <= x <= x1 else oc)


def a_top_edge_only(inp, out):
    bg, oc, ic, line = _colors(inp, out)
    outside = _flood(inp, _border(inp, bottom=False, left=False, right=False))
    return _build(inp, oc, lambda y, x: oc if (y, x) in outside else ic)


def a_row_scan_between_lines(inp, out):
    bg, oc, ic, line = _colors(inp, out)
    def fill(y, x):
        row = inp[y]
        inside = any(v != bg for v in row[:x]) and any(v != bg for v in row[x + 1:])
        return ic if inside else oc
    return _build(inp, oc, fill)


def a_largest_region_only(inp, out):
    bg, oc, ic, line = _colors(inp, out)
    regs = _regions(inp)
    if not regs:
        return None
    big = set(max(regs, key=len))
    return _build(inp, oc, lambda y, x: ic if (y, x) in big else oc)


def a_smallest_region_unfilled(inp, out):
    bg, oc, ic, line = _colors(inp, out)
    regs = _regions(inp)
    if not regs:
        return None
    small = set(min(regs, key=len))
    return _build(inp, oc, lambda y, x: oc if (y, x) in small or (y, x) not in
                  {c for r in regs for c in r} else ic)


def a_lines_recolored_outside(inp, out):
    bg, oc, ic, line = _colors(inp, out)
    return [[oc if inp[y][x] == line else out[y][x] for x in range(len(inp[0]))]
            for y in range(len(inp))]


def a_lines_recolored_inside(inp, out):
    bg, oc, ic, line = _colors(inp, out)
    return [[ic if inp[y][x] == line else out[y][x] for x in range(len(inp[0]))]
            for y in range(len(inp))]


def a_crop_to_line_bbox(inp, out):
    bg, oc, ic, line = _colors(inp, out)
    cells = [(y, x) for y in range(len(inp)) for x in range(len(inp[0])) if inp[y][x] != bg]
    y0 = min(c[0] for c in cells)
    y1 = max(c[0] for c in cells)
    x0 = min(c[1] for c in cells)
    x1 = max(c[1] for c in cells)
    return [r[x0:x1 + 1] for r in out[y0:y1 + 1]]


def a_transposed(inp, out):
    return [list(r) for r in zip(*out)]


ALTERNATIVES = [
    ("enclosed regions get the outside colour instead of their own fill", a_inside_as_outside),
    ("outside background is left unrecoloured, only enclosed regions are filled", a_outside_unchanged),
    ("enclosed regions are filled with the line colour", a_inside_line_color),
    ("inside and outside fill colours are swapped", a_swap_fills),
    ("every background cell inside the bounding box of the lines is filled", a_bbox_fill),
    ("only the top edge counts as outside, regions open to other edges count as enclosed", a_top_edge_only),
    ("a background cell is filled when the line has a cell to its left and right in the same row", a_row_scan_between_lines),
    ("only the largest enclosed region is filled, other regions get the outside colour", a_largest_region_only),
    ("the smallest enclosed region is left with the outside colour", a_smallest_region_unfilled),
    ("line cells are recoloured with the outside colour", a_lines_recolored_outside),
    ("line cells are recoloured with the inside fill colour", a_lines_recolored_inside),
    ("output is cropped to the bounding box of the lines", a_crop_to_line_bbox),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len(set(len(r) for r in g)) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/7b6016b9.json'))
    pairs = task['train']
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
