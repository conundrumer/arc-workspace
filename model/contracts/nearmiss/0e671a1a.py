"""Near-miss readings for ARC task 0e671a1a."""
import json
from pathlib import Path

PATH = 5


def _copy(g):
    return [row[:] for row in g]


def _marks(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def _path_cells(inp, out):
    return {(r, c) for r, row in enumerate(out) for c, v in enumerate(row)
            if v == PATH and inp[r][c] == 0}


def _filled(inp, out):
    """Cells that are path or mark in the true output."""
    return {(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v != 0}


def recolor_path(color):
    def f(inp, out):
        g = _copy(out)
        for r, c in _path_cells(inp, out):
            g[r][c] = color
        return g
    return f


def path_in_first_mark_color(inp, out):
    m = _marks(inp)
    if not m:
        return None
    g = _copy(out)
    for r, c in _path_cells(inp, out):
        g[r][c] = m[0][2]
    return g


def path_overwrites_marks(inp, out):
    g = _copy(out)
    for r, c, _ in _marks(inp):
        g[r][c] = PATH
    return g


def marks_erased(inp, out):
    g = _copy(out)
    for r, c, _ in _marks(inp):
        g[r][c] = 0
    return g


def _keep_axis(inp, out, vertical):
    filled = _filled(inp, out)
    g = _copy(out)
    for r, c in _path_cells(inp, out):
        if vertical:
            has = (r - 1, c) in filled or (r + 1, c) in filled
        else:
            has = (r, c - 1) in filled or (r, c + 1) in filled
        if not has:
            g[r][c] = 0
    return g


def vertical_only(inp, out):
    return _keep_axis(inp, out, True)


def horizontal_only(inp, out):
    return _keep_axis(inp, out, False)


def _legs(inp, out):
    """Mark pairs joined by an L of path cells, with the elbow used."""
    filled = _filled(inp, out)
    marks = _marks(inp)
    res = []
    for i, (r1, c1, _) in enumerate(marks):
        for (r2, c2, _) in marks[i + 1:]:
            if r1 == r2 or c1 == c2:
                continue
            for e in ((r1, c2), (r2, c1)):
                other = (r1 + r2 - e[0], c1 + c2 - e[1])
                if _seg_ok(filled, (r1, c1), e) and _seg_ok(filled, e, (r2, c2)):
                    res.append(((r1, c1), (r2, c2), e, other))
    return res


def _seg(a, b):
    (r1, c1), (r2, c2) = a, b
    if r1 == r2:
        return [(r1, c) for c in range(min(c1, c2), max(c1, c2) + 1)]
    return [(r, c1) for r in range(min(r1, r2), max(r1, r2) + 1)]


def _seg_ok(filled, a, b):
    return all(p in filled for p in _seg(a, b))


def mirrored_elbow(inp, out):
    g = _copy(inp)
    for a, b, e, o in _legs(inp, out):
        for p in _seg(a, o) + _seg(o, b):
            if g[p[0]][p[1]] == 0:
                g[p[0]][p[1]] = PATH
    return g


def path_stops_short_of_marks(inp, out):
    g = _copy(out)
    for r, c, _ in _marks(inp):
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < len(g) and 0 <= cc < len(g[0]) and g[rr][cc] == PATH:
                g[rr][cc] = 0
    return g


def elbow_lines_to_edge(inp, out):
    filled = _filled(inp, out)
    g = _copy(out)
    h, w = len(out), len(out[0])
    for r, c in _path_cells(inp, out):
        horiz = (r, c - 1) in filled or (r, c + 1) in filled
        vert = (r - 1, c) in filled or (r + 1, c) in filled
        if horiz and vert:
            for cc in range(w):
                if g[r][cc] == 0:
                    g[r][cc] = PATH
            for rr in range(h):
                if g[rr][c] == 0:
                    g[rr][c] = PATH
    return g


def path_thick(inp, out):
    h, w = len(out), len(out[0])
    g = _copy(out)
    for r, c in _path_cells(inp, out):
        for rr, cc in ((r, c + 1), (r + 1, c)):
            if rr < h and cc < w and g[rr][cc] == 0:
                g[rr][cc] = PATH
    return g


def crop_to_marks(inp, out):
    ms = _marks(inp)
    r0, r1 = min(m[0] for m in ms), max(m[0] for m in ms)
    c0, c1 = min(m[1] for m in ms), max(m[1] for m in ms)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def transposed(inp, out):
    return [list(col) for col in zip(*out)]


ALTERNATIVES = [
    ("path painted with color 8 instead of 5", recolor_path(8)),
    ("path painted with the color of the first mark in reading order", path_in_first_mark_color),
    ("path overwrites the mark cells with 5", path_overwrites_marks),
    ("marks erased, only the path kept", marks_erased),
    ("only the vertical halves of each leg drawn", vertical_only),
    ("only the horizontal halves of each leg drawn", horizontal_only),
    ("each leg bends at the other corner of its rectangle", mirrored_elbow),
    ("path stops one cell short of every mark", path_stops_short_of_marks),
    ("lines through each elbow extend to the grid edges", elbow_lines_to_edge),
    ("path drawn two cells wide", path_thick),
    ("output cropped to the bounding box of the marks", crop_to_marks),
    ("output transposed (axis swapped)", transposed),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/0e671a1a.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
