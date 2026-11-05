import json
from collections import Counter
from pathlib import Path

PAINT = 6


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _boxes(inp):
    """Bounding boxes (r0, c0, r1, c1) of 8-connected non-background components."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    boxes = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != bg and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            boxes.append((min(ys), min(xs), max(ys), max(xs)))
    return sorted(boxes)


def _centers(inp):
    return [((b[0] + b[2]) // 2, (b[1] + b[3]) // 2) for b in _boxes(inp)]


def _paint(inp, cells, color=PAINT, over=False):
    bg = _bg(inp)
    g = [row[:] for row in inp]
    for (r, c) in cells:
        if 0 <= r < len(g) and 0 <= c < len(g[0]) and (over or inp[r][c] == bg):
            g[r][c] = color
    return g


def _row(inp, r):
    return [(r, c) for c in range(len(inp[0]))]


def _col(inp, c):
    return [(r, c) for r in range(len(inp))]


def horizontal_only(inp, out):
    cells = [p for (r, c) in _centers(inp) for p in _row(inp, r)]
    return _paint(inp, cells)


def vertical_only(inp, out):
    cells = [p for (r, c) in _centers(inp) for p in _col(inp, c)]
    return _paint(inp, cells)


def overwrite_frame(inp, out):
    cells = [p for (r, c) in _centers(inp) for p in _row(inp, r) + _col(inp, c)]
    return _paint(inp, cells, over=True)


def outside_frame_only(inp, out):
    cells = []
    for b, (r, c) in zip(_boxes(inp), _centers(inp)):
        for p in _row(inp, r) + _col(inp, c):
            if not (b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]):
                cells.append(p)
    return _paint(inp, cells)


def center_off_by_one(inp, out):
    cells = [p for (r, c) in _centers(inp) for p in _row(inp, r + 1) + _col(inp, c + 1)]
    return _paint(inp, cells)


def first_square_only(inp, out):
    cs = _centers(inp)
    if len(cs) < 2:
        return None
    r, c = cs[0]
    return _paint(inp, _row(inp, r) + _col(inp, c))


def frame_color_lines(inp, out):
    bg = _bg(inp)
    frame = Counter(v for row in inp for v in row if v != bg).most_common(1)[0][0]
    cells = [p for (r, c) in _centers(inp) for p in _row(inp, r) + _col(inp, c)]
    return _paint(inp, cells, color=frame + 1 if frame + 1 != bg and frame + 1 != frame and frame + 1 <= 9 else 2)


def rays_right_down_only(inp, out):
    cells = []
    for (r, c) in _centers(inp):
        cells += [(r, x) for x in range(c, len(inp[0]))]
        cells += [(y, c) for y in range(r, len(inp))]
    return _paint(inp, cells)


def stop_at_obstacle(inp, out):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    cells = []
    for (r, c) in _centers(inp):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            y, x = r, c
            while 0 <= y < h and 0 <= x < w and inp[y][x] == bg:
                cells.append((y, x))
                y, x = y + dy, x + dx
    return _paint(inp, cells)


def thick_lines(inp, out):
    cells = []
    for (r, c) in _centers(inp):
        for d in (-1, 0, 1):
            cells += _row(inp, r + d) + _col(inp, c + d)
    return _paint(inp, [p for p in cells if 0 <= p[0] < len(inp) and 0 <= p[1] < len(inp[0])])


def diagonals(inp, out):
    h, w = len(inp), len(inp[0])
    cells = []
    for (r, c) in _centers(inp):
        for k in range(-max(h, w), max(h, w)):
            cells += [(r + k, c + k), (r + k, c - k)]
    return _paint(inp, cells)


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("Draw only the horizontal line through each square's center", horizontal_only),
    ("Draw only the vertical line through each square's center", vertical_only),
    ("Lines overwrite the square's outline cells too", overwrite_frame),
    ("Lines are drawn only outside the square, not through its hole", outside_frame_only),
    ("Line position is off by one row and column from the square's center", center_off_by_one),
    ("Only the first (top-left) square casts lines", first_square_only),
    ("Lines are drawn in a wrong color", frame_color_lines),
    ("Lines extend only to the right and downward from the center", rays_right_down_only),
    ("Lines stop at the first non-background cell", stop_at_obstacle),
    ("Lines are three cells wide", thick_lines),
    ("Diagonal lines through the center instead of horizontal and vertical", diagonals),
    ("Output equals the input", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/41e4d17e.json').read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
