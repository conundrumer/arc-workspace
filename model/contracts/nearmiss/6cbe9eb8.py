import json
from pathlib import Path


def copy(g):
    return [row[:] for row in g]


def input_as_is(inp, out):
    return copy(inp)


def drop_frame_outline(inp, out):
    return [row[1:-1] for row in out[1:-1]]


def flip_rows(inp, out):
    return [row[:] for row in reversed(out)]


def flip_cols(inp, out):
    return [row[::-1] for row in out]


def rotate_180(inp, out):
    return [row[::-1] for row in reversed(out)]


def frame_only(inp, out):
    h, w = len(out), len(out[0])
    fill = out[1][1]
    return [[out[r][c] if r in (0, h - 1) or c in (0, w - 1) else fill
             for c in range(w)] for r in range(h)]


def _areas(out):
    frame = out[0][0]
    areas = {}
    for row in out:
        for v in row:
            if v != frame:
                areas[v] = areas.get(v, 0) + 1
    return areas


def swap_two_innermost_colors(inp, out):
    areas = _areas(out)
    if len(areas) < 2:
        return None
    a, b = sorted(areas, key=lambda v: (areas[v], v))[:2]
    return [[b if v == a else a if v == b else v for v in row] for row in out]


def extra_ring(inp, out):
    frame = out[0][0]
    w = len(out[0])
    g = [[frame] * (w + 2)]
    for row in out:
        g.append([frame] + row + [frame])
    g.append([frame] * (w + 2))
    return g


def crop_one_short(inp, out):
    return [row[:-1] for row in out[:-1]]


def crop_input_in_place(inp, out):
    frame = out[0][0]
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row)
             if v == frame]
    if not cells:
        return None
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def shifted_onto_rim(inp, out):
    h, w = len(out), len(out[0])
    g = copy(out)
    for r in range(1, h):
        for c in range(0, w - 2):
            sr, sc = r - 1, c + 1
            if 1 <= sr <= h - 2 and 1 <= sc <= w - 2:
                g[r][c] = out[sr][sc]
    return g


def innermost_block_too_big(inp, out):
    areas = _areas(out)
    if not areas:
        return None
    col = min(areas, key=lambda v: (areas[v], v))
    cells = [(r, c) for r, row in enumerate(out) for c, v in enumerate(row)
             if v == col]
    r0 = min(r for r, _ in cells)
    c1 = max(c for _, c in cells)
    c0 = min(c for _, c in cells)
    r1 = max(r for r, _ in cells)
    h, w = len(out), len(out[0])
    if r0 - 1 < 1 or c1 + 1 > w - 2:
        return None
    g = copy(out)
    for r in range(r0 - 1, r1 + 1):
        for c in range(c0, c1 + 2):
            g[r][c] = col
    return g


ALTERNATIVES = [
    ("returns the input unchanged, with no crop", input_as_is),
    ("drops the frame's outline ring and keeps only its inside", drop_frame_outline),
    ("stacks the nested shapes in the top-left corner (rows flipped)", flip_rows),
    ("stacks the nested shapes in the bottom-right corner (columns flipped)", flip_cols),
    ("stacks the nested shapes in the top-right corner (rotated 180 degrees)", rotate_180),
    ("draws only the outer frame and omits the nested shapes", frame_only),
    ("exchanges the colors of the two innermost shapes (wrong nesting order)", swap_two_innermost_colors),
    ("takes the frame's bounding box one cell too large on every side", extra_ring),
    ("takes the frame's bounding box one row and one column too small", crop_one_short),
    ("crops the frame from the input and leaves the shapes where they were", crop_input_in_place),
    ("places the nested shapes flush on the frame's rim, over its outline", shifted_onto_rim),
    ("makes the innermost block one row taller and one column wider", innermost_block_too_big),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not isinstance(g[0], list) or not g[0]:
        return False
    w = len(g[0])
    for row in g:
        if not isinstance(row, list) or len(row) != w:
            return False
        for v in row:
            if type(v) is not int or not 0 <= v <= 9:
                return False
    return g != out


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / "data/tasks/6cbe9eb8.json"
    train = json.load(open(path))["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(copy(p["input"]), copy(p["output"]))
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
