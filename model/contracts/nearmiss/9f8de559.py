import json
from collections import Counter
from pathlib import Path


def _copy(g):
    return [row[:] for row in g]


def _info(inp, out):
    """Head, direction, field color, field box, body cells of the pointer."""
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for row in inp for v in row)
    head_col = min(cnt, key=lambda c: cnt[c])
    hr, hc = next((r, c) for r in range(h) for c in range(w) if inp[r][c] == head_col)
    others = [c for c in cnt if c != head_col]
    body_col = min(others, key=lambda c: cnt[c])
    body = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == body_col]
    br, bc = next((r, c) for r, c in body if max(abs(r - hr), abs(c - hc)) == 1)
    d = (hr - br, hc - bc)
    diff = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != out[r][c]]
    fr, fc = diff[0]
    field_col = out[fr][fc]
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == field_col]
    box = (min(r for r, _ in cells), max(r for r, _ in cells),
           min(c for _, c in cells), max(c for _, c in cells))
    return dict(h=h, w=w, head=(hr, hc), head_col=head_col, body_col=body_col,
                body=body, d=d, field_col=field_col, box=box)


def _inside(box, r, c):
    return box[0] <= r <= box[1] and box[2] <= c <= box[3]


def _ray(info, start, d):
    """Cells from start (exclusive) stepping by d, inside the grid."""
    r, c = start
    cells = []
    while True:
        r += d[0]
        c += d[1]
        if not (0 <= r < info["h"] and 0 <= c < info["w"]):
            return cells
        cells.append((r, c))


def _first_outside(info, start, d):
    for r, c in _ray(info, start, d):
        if not _inside(info["box"], r, c):
            return (r, c)
    return None


def _paint(base, cells, color):
    g = _copy(base)
    for r, c in cells:
        g[r][c] = color
    return g


def last_inside_head_color(inp, out):
    i = _info(inp, out)
    cells = [(r, c) for r, c in _ray(i, i["head"], i["d"]) if _inside(i["box"], r, c)]
    return _paint(inp, cells[-1:], i["head_col"])


def reverse_direction(inp, out):
    i = _info(inp, out)
    d = (-i["d"][0], -i["d"][1])
    p = _first_outside(i, i["head"], d)
    return _paint(inp, [p], i["field_col"]) if p else None


def head_color_mark(inp, out):
    i = _info(inp, out)
    p = _first_outside(i, i["head"], i["d"])
    return _paint(inp, [p], i["head_col"]) if p else None


def body_color_mark(inp, out):
    i = _info(inp, out)
    p = _first_outside(i, i["head"], i["d"])
    return _paint(inp, [p], i["body_col"]) if p else None


def both_ends(inp, out):
    i = _info(inp, out)
    p = _first_outside(i, i["head"], i["d"])
    q = _first_outside(i, i["head"], (-i["d"][0], -i["d"][1]))
    return _paint(inp, [p, q], i["field_col"]) if p and q else None


def whole_ray_head_color(inp, out):
    i = _info(inp, out)
    return _paint(out, _ray(i, i["head"], i["d"]), i["head_col"])


def erase_pointer(inp, out):
    i = _info(inp, out)
    return _paint(out, i["body"] + [i["head"]], i["field_col"])


def perpendicular(inp, out):
    i = _info(inp, out)
    d = (-i["d"][1], i["d"][0])
    p = _first_outside(i, i["head"], d)
    return _paint(inp, [p], i["field_col"]) if p else None


def second_cell_outside(inp, out):
    i = _info(inp, out)
    p = _first_outside(i, i["head"], i["d"])
    if not p:
        return None
    q = (p[0] + i["d"][0], p[1] + i["d"][1])
    if not (0 <= q[0] < i["h"] and 0 <= q[1] < i["w"]):
        return None
    return _paint(inp, [q], i["field_col"])


def axis_only_direction(inp, out):
    i = _info(inp, out)
    dr, dc = i["d"]
    if dr == 0 or dc == 0:
        return None
    p = _first_outside(i, i["head"], (0, dc))
    return _paint(inp, [p], i["field_col"]) if p else None


def unchanged(inp, out):
    return _copy(inp)


def edge_cell_instead(inp, out):
    """Marks the grid-edge cell of the ray instead of the first cell outside the field."""
    i = _info(inp, out)
    cells = _ray(i, i["head"], i["d"])
    g = _paint(inp, cells[-1:], i["field_col"])
    return None if g == out else g


ALTERNATIVES = [
    ("marks the last field cell on the ray with the head color instead of the cell past the field", last_inside_head_color),
    ("ray runs from the head toward the body instead of away from it", reverse_direction),
    ("cell past the field takes the head color instead of the field color", head_color_mark),
    ("cell past the field takes the body color instead of the field color", body_color_mark),
    ("marks the cell past the field at both ends of the line", both_ends),
    ("paints the whole ray, field and beyond, in the head color", whole_ray_head_color),
    ("erases the pointer to the field color as well as marking the ray end", erase_pointer),
    ("ray runs perpendicular to the pointer line", perpendicular),
    ("marks the second cell past the field instead of the first", second_cell_outside),
    ("diagonal pointers are treated as moving along their column direction only", axis_only_direction),
    ("marks the grid-edge cell of the ray instead of the first cell past the field", edge_cell_instead),
    ("output is the input unchanged", unchanged),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/9f8de559.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None:
                assert _valid(g, p["output"]), (desc, "invalid")
                n += 1
        print(n, desc)
