"""Near-miss readings for ARC task 67636eac."""
import json
from pathlib import Path


def _shapes(inp):
    """One shape per ink color: (color, r0, r1, c0, c1, crop)."""
    cells = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v:
                cells.setdefault(v, []).append((r, c))
    res = []
    for col, ps in cells.items():
        r0 = min(p[0] for p in ps); r1 = max(p[0] for p in ps)
        c0 = min(p[1] for p in ps); c1 = max(p[1] for p in ps)
        crop = [list(inp[r][c0:c1 + 1]) for r in range(r0, r1 + 1)]
        res.append((col, r0, r1, c0, c1, crop))
    return res


def _horizontal(shapes):
    """True when two shapes share a row, so shapes sit side by side."""
    for i in range(len(shapes)):
        for j in range(i + 1, len(shapes)):
            a, b = shapes[i], shapes[j]
            if not (a[2] < b[1] or b[2] < a[1]):
                return True
    return False


def _ordered(shapes, horiz):
    return sorted(shapes, key=lambda s: s[3] if horiz else s[1])


def _hcat(crops, sep=False):
    h = max(len(c) for c in crops)
    out = [[] for _ in range(h)]
    for i, c in enumerate(crops):
        for r in range(h):
            if sep and i:
                out[r].append(0)
            out[r].extend(c[r] if r < len(c) else [0] * len(c[0]))
    return out


def _vcat(crops, sep=False):
    out = []
    w = max(len(c[0]) for c in crops)
    for i, c in enumerate(crops):
        if sep and i:
            out.append([0] * w)
        for row in c:
            out.append(list(row) + [0] * (w - len(row)))
    return out


def _cat(crops, horiz, sep=False):
    return _hcat(crops, sep) if horiz else _vcat(crops, sep)


def _setup(inp):
    sh = _shapes(inp)
    horiz = _horizontal(sh)
    return sh, horiz, _ordered(sh, horiz)


def other_axis(inp, out):
    sh, horiz, o = _setup(inp)
    return _cat([s[5] for s in o], not horiz)


def reversed_order(inp, out):
    sh, horiz, o = _setup(inp)
    return _cat([s[5] for s in reversed(o)], horiz)


def one_color(inp, out):
    sh, horiz, o = _setup(inp)
    col = o[0][0]
    return [[col if v else 0 for v in row] for row in out]


def with_separator(inp, out):
    sh, horiz, o = _setup(inp)
    return _cat([s[5] for s in o], horiz, sep=True)


def joint_bbox_crop(inp, out):
    sh, horiz, o = _setup(inp)
    r0 = min(s[1] for s in sh); r1 = max(s[2] for s in sh)
    c0 = min(s[3] for s in sh); c1 = max(s[4] for s in sh)
    return [list(inp[r][c0:c1 + 1]) for r in range(r0, r1 + 1)]


def drop_last(inp, out):
    sh, horiz, o = _setup(inp)
    return _cat([s[5] for s in o[:-1]], horiz)


def color_descending(inp, out):
    sh, horiz, o = _setup(inp)
    g = _cat([s[5] for s in sorted(sh, key=lambda s: -s[0])], horiz)
    return None if g == out else g


def first_shape_only(inp, out):
    sh, horiz, o = _setup(inp)
    return [list(r) for r in o[0][5]]


def keep_cross_offsets(inp, out):
    """Pack along the layout axis but keep each shape's original offset across it."""
    sh, horiz, o = _setup(inp)
    if horiz:
        lo = min(s[1] for s in sh); hi = max(s[2] for s in sh)
        h = hi - lo + 1
        crops = []
        for s in o:
            c = [[0] * (s[4] - s[3] + 1) for _ in range(h)]
            for i, row in enumerate(s[5]):
                c[s[1] - lo + i] = list(row)
            crops.append(c)
        return _hcat(crops)
    lo = min(s[3] for s in sh); hi = max(s[4] for s in sh)
    w = hi - lo + 1
    crops = []
    for s in o:
        crops.append([[0] * (s[3] - lo) + list(row) + [0] * (hi - s[4]) for row in s[5]])
    return _vcat(crops)


def filled_boxes(inp, out):
    sh, horiz, o = _setup(inp)
    return _cat([[[s[0]] * len(s[5][0]) for _ in s[5]] for s in o], horiz)


def inverted_shapes(inp, out):
    sh, horiz, o = _setup(inp)
    return _cat([[[0 if v else s[0] for v in row] for row in s[5]] for s in o], horiz)


def transposed_output(inp, out):
    return [list(r) for r in zip(*out)]


ALTERNATIVES = [
    ("stack the shapes along the other axis than the layout axis", other_axis),
    ("lay the shapes out in reverse order", reversed_order),
    ("paint every shape in the first shape's color", one_color),
    ("leave a blank line between the packed shapes", with_separator),
    ("crop the joint bounding box without packing the blank lines", joint_bbox_crop),
    ("omit the last shape", drop_last),
    ("order the shapes by descending color instead of position", color_descending),
    ("output only the first shape", first_shape_only),
    ("pack along the layout axis but keep each shape's original cross offset", keep_cross_offsets),
    ("fill each shape's whole bounding box with its color", filled_boxes),
    ("invert each shape inside its bounding box", inverted_shapes),
    ("transpose the correct output", transposed_output),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/67636eac.json'))
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in train)
        print(n, "/", len(train), desc)
