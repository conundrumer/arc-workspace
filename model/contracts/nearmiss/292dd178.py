import json
from collections import Counter
from pathlib import Path

DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for row in inp for v in row)
    wall = min(cnt, key=lambda k: (cnt[k], k))
    bg = max(cnt, key=lambda k: (cnt[k], -k))
    seen = set()
    boxes = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != wall or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in DIRS:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == wall and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            boxes.append((min(ys), min(xs), max(ys), max(xs), len(cells)))
    return h, w, wall, bg, boxes


def _holes(inp, wall, boxes):
    out = []
    for (t, l, b, r, _) in boxes:
        for y in range(t + 1, b):
            for x in range(l + 1, r):
                if inp[y][x] != wall:
                    out.append((y, x, (t, l, b, r)))
    return out


def _ray(inp, wall, h, w, y, x, d, through_walls=False):
    cells = []
    y, x = y + d[0], x + d[1]
    while 0 <= y < h and 0 <= x < w:
        if inp[y][x] == wall and not through_walls:
            break
        cells.append((y, x))
        y, x = y + d[0], x + d[1]
    return cells


def _paint(inp, cells, color=2):
    g = [row[:] for row in inp]
    for (y, x) in cells:
        g[y][x] = color
    return g


def _true_cells(inp, dirs=DIRS, through_walls=False):
    h, w, wall, bg, boxes = _parse(inp)
    cells = set()
    for (y, x, box) in _holes(inp, wall, boxes):
        cells.add((y, x))
        for d in dirs:
            cells.update(_ray(inp, wall, h, w, y, x, d, through_walls))
    return cells, box_info(inp)


def box_info(inp):
    return _parse(inp)


def _inside(y, x, box):
    t, l, b, r = box
    return t <= y <= b and l <= x <= r


def no_leak(inp, out):
    h, w, wall, bg, boxes = _parse(inp)
    return _paint(inp, [(y, x) for (y, x, _) in _holes(inp, wall, boxes)])


def stop_at_break(inp, out):
    h, w, wall, bg, boxes = _parse(inp)
    cells = set()
    for (y, x, box) in _holes(inp, wall, boxes):
        cells.add((y, x))
        for d in DIRS:
            cells.update(c for c in _ray(inp, wall, h, w, y, x, d) if _inside(c[0], c[1], box))
    return _paint(inp, cells)


def one_past_box(inp, out):
    h, w, wall, bg, boxes = _parse(inp)
    cells = set()
    for (y, x, box) in _holes(inp, wall, boxes):
        cells.add((y, x))
        for d in DIRS:
            seen_out = 0
            for c in _ray(inp, wall, h, w, y, x, d):
                if _inside(c[0], c[1], box):
                    cells.add(c)
                elif seen_out < 1:
                    cells.add(c)
                    seen_out += 1
    return _paint(inp, cells)


def vertical_only(inp, out):
    return _paint(inp, _true_cells(inp, [(-1, 0), (1, 0)])[0])


def horizontal_only(inp, out):
    return _paint(inp, _true_cells(inp, [(0, -1), (0, 1)])[0])


def through_walls(inp, out):
    h, w, wall, bg, boxes = _parse(inp)
    cells = set()
    for (y, x, box) in _holes(inp, wall, boxes):
        cells.add((y, x))
        for d in DIRS:
            cells.update(c for c in _ray(inp, wall, h, w, y, x, d, True) if inp[c[0]][c[1]] != wall)
    return _paint(inp, cells)


def fill_color_3(inp, out):
    return [[3 if v == 2 and inp[y][x] != 2 else v for x, v in enumerate(row)] for y, row in enumerate(out)]


def fill_with_wall_color(inp, out):
    h, w, wall, bg, boxes = _parse(inp)
    return [[wall if v == 2 and inp[y][x] != 2 else v for x, v in enumerate(row)] for y, row in enumerate(out)]


def flood_all_background(inp, out):
    h, w, wall, bg, boxes = _parse(inp)
    cells = set()
    stack = [(y, x) for (y, x, _) in _holes(inp, wall, boxes)]
    cells.update(stack)
    while stack:
        y, x = stack.pop()
        for dy, dx in DIRS:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != wall and (ny, nx) not in cells:
                cells.add((ny, nx))
                stack.append((ny, nx))
    return _paint(inp, cells)


def opposite_side(inp, out):
    h, w, wall, bg, boxes = _parse(inp)
    cells = set()
    for (y, x, box) in _holes(inp, wall, boxes):
        cells.add((y, x))
    t0 = _true_cells(inp)[0]
    for (t, l, b, r, _) in boxes:
        for (y, x) in t0:
            if _inside(y, x, (t, l, b, r)) and not (t < y < b and l < x < r):
                my, mx = t + b - y, l + r - x
                if 0 <= my < h and 0 <= mx < w and inp[my][mx] != wall:
                    cells.add((my, mx))
        for (y, x) in t0:
            if not any(_inside(y, x, (bt, bl, bb, br)) for (bt, bl, bb, br, _) in boxes):
                # outside every box: belongs to this box if collinear with it
                if (t <= y <= b) != (l <= x <= r):
                    my, mx = t + b - y, l + r - x
                    if 0 <= my < h and 0 <= mx < w and inp[my][mx] != wall:
                        cells.add((my, mx))
    return _paint(inp, cells)


def crop_largest_box(inp, out):
    h, w, wall, bg, boxes = _parse(inp)
    t, l, b, r, _ = max(boxes, key=lambda bx: bx[4])
    return [row[l:r + 1] for row in out[t:b + 1]]


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("Fill only the enclosed interior of each box; the break gives no leak", no_leak),
    ("Fill leaks only as far as the break cell in the box outline, not beyond", stop_at_break),
    ("Fill leaks one cell past the box and then stops", one_past_box),
    ("Fill escapes only vertically; horizontal breaks are ignored", vertical_only),
    ("Fill escapes only horizontally; vertical breaks are ignored", horizontal_only),
    ("Fill rays pass through walls and run to the grid edge", through_walls),
    ("Correct fill shape painted with color 3 instead of 2", fill_color_3),
    ("Correct fill shape painted with the wall color instead of a new color", fill_with_wall_color),
    ("Leak floods all background connected to the hole, not just a straight ray", flood_all_background),
    ("Fill exits on the side of the box opposite the break", opposite_side),
    ("Output is only the crop of the largest box instead of the full grid", crop_largest_box),
    ("Output is the input unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/292dd178.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, fn.__name__, "-", desc)
