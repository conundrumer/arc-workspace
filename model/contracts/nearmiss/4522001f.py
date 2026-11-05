import json
from collections import Counter
from pathlib import Path


def _boxes(out):
    """Solid boxes of the true output, as (r0, c0, r1, c1), found by 4-connectivity."""
    h, w = len(out), len(out[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if out[r][c] != 0 and (r, c) not in seen:
                col = out[r][c]
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and out[ny][nx] == col:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                ys = [p[0] for p in cells]
                xs = [p[1] for p in cells]
                res.append((min(ys), min(xs), max(ys), max(xs)))
    return res


def _corner_first(out):
    """Boxes ordered so the box touching a grid corner comes first."""
    h, w = len(out), len(out[0])
    bs = _boxes(out)

    def touches(b):
        return b[0] in (0, h - 1) and b[1] in (0, w - 1) or (
            b[2] in (0, h - 1) and b[3] in (0, w - 1)
            and (b[0] in (0, h - 1) or b[2] in (0, h - 1))
            and (b[1] in (0, w - 1) or b[3] in (0, w - 1)))

    def at_corner(b):
        return (b[0] == 0 or b[2] == h - 1) and (b[1] == 0 or b[3] == w - 1)

    bs.sort(key=lambda b: not at_corner(b))
    return bs


def _fill(h, w, color, boxes):
    g = [[0] * w for _ in range(h)]
    for r0, c0, r1, c1 in boxes:
        for r in range(max(r0, 0), min(r1, h - 1) + 1):
            for c in range(max(c0, 0), min(c1, w - 1) + 1):
                g[r][c] = color
    return g


def _color(out):
    return max(v for row in out for v in row if v)


def flip_lr(inp, out):
    return [row[::-1] for row in out]


def flip_ud(inp, out):
    return [row[:] for row in out[::-1]]


def mark_color(inp, out):
    cnt = Counter(v for row in inp for v in row)
    mark = min(cnt, key=lambda k: cnt[k])
    return [[mark if v else 0 for v in row] for row in out]


def only_corner_box(inp, out):
    bs = _corner_first(out)
    return _fill(len(out), len(out[0]), _color(out), bs[:1])


def shrunk_boxes(inp, out):
    bs = _boxes(out)
    return _fill(len(out), len(out[0]), _color(out),
                 [(r0, c0, r1 - 1, c1 - 1) for r0, c0, r1, c1 in bs])


def shifted(inp, out):
    h, w = len(out), len(out[0])
    g = [[0] * w for _ in range(h)]
    for r in range(h - 1):
        for c in range(w - 1):
            g[r + 1][c + 1] = out[r][c]
    return g


def rot180(inp, out):
    return [row[::-1] for row in out[::-1]]


def anti_transpose(inp, out):
    h, w = len(out), len(out[0])
    return [[out[h - 1 - c][w - 1 - r] for c in range(h)] for r in range(w)]


def extra_box(inp, out):
    bs = _corner_first(out)
    a, b = bs[0], bs[1]
    dr, dc = b[0] - a[0], b[1] - a[1]
    third = (b[0] + dr, b[1] + dc, b[2] + dr, b[3] + dc)
    return _fill(len(out), len(out[0]), _color(out), bs + [third])


def upscaled_input(inp, out):
    k = len(out) // len(inp)
    return [[inp[r // k][c // k] for c in range(len(inp[0]) * k)] for r in range(len(inp) * k)]


ALTERNATIVES = [
    ("chain mirrored left-right", flip_lr),
    ("chain mirrored top-bottom", flip_ud),
    ("boxes painted with the mark color instead of the block color", mark_color),
    ("only the box at the grid corner is drawn", only_corner_box),
    ("each box one cell too small", shrunk_boxes),
    ("whole picture offset one cell down and right", shifted),
    ("chain seated at the opposite grid corner (rotated 180)", rot180),
    ("chain runs along the other diagonal (anti-transposed)", anti_transpose),
    ("chain continues one box too far, clipped at the grid edge", extra_box),
    ("input upscaled by the canvas ratio instead of boxes", upscaled_input),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/4522001f.json'))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
