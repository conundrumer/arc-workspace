"""Near-miss readings for b775ac94: a shape is mirrored into the quadrants of
its 2x2 key block where single marker cells sit, in each marker's color."""
import json
from collections import Counter
from pathlib import Path


def _components(g):
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == 0 or (r, c) in seen:
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
                        if (0 <= ny < h and 0 <= nx < w and g[ny][nx] != 0
                                and (ny, nx) not in seen):
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            comps.append(cells)
    return comps


def _objects(g):
    """Yield (shape cells, shape color, markers [(r, c, color)], key, block)."""
    res = []
    for cells in _components(g):
        cnt = Counter(g[r][c] for r, c in cells)
        col = cnt.most_common(1)[0][0]
        shape = [(r, c) for r, c in cells if g[r][c] == col]
        marks = [(r, c, g[r][c]) for r, c in cells if g[r][c] != col]
        if not marks:
            continue
        r0 = min(r for r, _ in shape)
        r1 = max(r for r, _ in shape)
        c0 = min(c for _, c in shape)
        c1 = max(c for _, c in shape)
        key = None
        for r, c in shape:
            if r not in (r0, r1) or c not in (c0, c1):
                continue
            dr = -1 if r == r0 else 1
            dc = -1 if c == c0 else 1
            block = {(r, c), (r + dr, c), (r, c + dc), (r + dr, c + dc)}
            if all((m[0], m[1]) in block for m in marks):
                key = (r, c, dr, dc)
                break
        if key is None:
            continue
        r, c, dr, dc = key
        rb0, cb0 = min(r, r + dr), min(c, c + dc)
        res.append(dict(shape=shape, color=col, marks=marks, key=key,
                        rb0=rb0, cb0=cb0, bbox=(r0, r1, c0, c1)))
    return res


def _render(inp, tf, over=False, color="marker", marks_only=None,
            erase_markers=False, all_corners=False):
    h, w = len(inp), len(inp[0])
    out = [row[:] for row in inp]
    copies = []
    for ob in _objects(inp):
        kr, kc, dr, dc = ob["key"]
        marks = ob["marks"]
        if marks_only is not None:
            marks = marks[:marks_only]
        if all_corners:
            corners = [(kr + a, kc + b) for a in (0, dr) for b in (0, dc)
                       if (a, b) != (0, 0)]
            marks = [(r, c, marks[0][2]) for r, c in corners]
        for mr, mc, mcol in marks:
            kind = ("row" if mr == kr else "col" if mc == kc else "diag")
            paint = mcol if color == "marker" else ob["color"]
            for (r, c) in ob["shape"]:
                t = tf(kind, r, c, ob, (mr, mc))
                if t is None:
                    continue
                ny, nx = t
                if 0 <= ny < h and 0 <= nx < w:
                    copies.append((ny, nx, paint))
    if erase_markers:
        for ob in _objects(inp):
            for r, c, _ in ob["marks"]:
                out[r][c] = 0
    for ny, nx, paint in copies:
        if over or out[ny][nx] == 0:
            out[ny][nx] = paint
    return out


def _true_tf(kind, r, c, ob, m):
    rb, cb = ob["rb0"], ob["cb0"]
    if kind == "row":
        return r, 2 * cb + 1 - c
    if kind == "col":
        return 2 * rb + 1 - r, c
    return 2 * rb + 1 - r, 2 * cb + 1 - c


def _swapped_axes(kind, r, c, ob, m):
    rb, cb = ob["rb0"], ob["cb0"]
    if kind == "row":
        return 2 * rb + 1 - r, c
    if kind == "col":
        return r, 2 * cb + 1 - c
    return 2 * rb + 1 - r, 2 * cb + 1 - c


def _diag_one_axis(kind, r, c, ob, m):
    rb, cb = ob["rb0"], ob["cb0"]
    if kind == "diag":
        return r, 2 * cb + 1 - c
    return _true_tf(kind, r, c, ob, m)


def _translate(kind, r, c, ob, m):
    kr, kc = ob["key"][0], ob["key"][1]
    return r + (m[0] - kr), c + (m[1] - kc)


def _line_through_key(kind, r, c, ob, m):
    kr, kc = ob["key"][0], ob["key"][1]
    if kind == "row":
        return r, 2 * kc - c
    if kind == "col":
        return 2 * kr - r, c
    return 2 * kr - r, 2 * kc - c


def _bbox_edge(kind, r, c, ob, m):
    r0, r1, c0, c1 = ob["bbox"]
    kr, kc, dr, dc = ob["key"]
    er = r0 if dr < 0 else r1
    ec = c0 if dc < 0 else c1
    if kind == "row":
        return r, 2 * ec + (1 if dc < 0 else -1) - c
    if kind == "col":
        return 2 * er + (1 if dr < 0 else -1) - r, c
    return (2 * er + (1 if dr < 0 else -1) - r,
            2 * ec + (1 if dc < 0 else -1) - c)


def _rot180_block(kind, r, c, ob, m):
    rb, cb = ob["rb0"], ob["cb0"]
    return 2 * rb + 1 - r, 2 * cb + 1 - c


def _transpose(kind, r, c, ob, m):
    rb, cb = ob["rb0"], ob["cb0"]
    dr, dc = r - rb, c - cb
    return rb + dc, cb + dr


def _row_col_only(kind, r, c, ob, m):
    if kind == "diag":
        return None
    return _true_tf(kind, r, c, ob, m)


def alt_overwrite(inp, out):
    return _render(inp, _true_tf, over=True)


def alt_shape_color(inp, out):
    return _render(inp, _true_tf, color="shape")


def alt_first_marker(inp, out):
    return _render(inp, _true_tf, marks_only=1)


def alt_swapped(inp, out):
    return _render(inp, _swapped_axes)


def alt_diag_one_axis(inp, out):
    return _render(inp, _diag_one_axis)


def alt_translate(inp, out):
    return _render(inp, _translate)


def alt_key_line(inp, out):
    return _render(inp, _line_through_key)


def alt_bbox_edge(inp, out):
    return _render(inp, _bbox_edge)


def alt_rot180(inp, out):
    return _render(inp, _rot180_block)


def alt_transpose(inp, out):
    return _render(inp, _transpose)


def alt_no_diag(inp, out):
    return _render(inp, _row_col_only)


def alt_erase_markers(inp, out):
    return _render(inp, _true_tf, erase_markers=True)


def alt_all_corners(inp, out):
    return _render(inp, _true_tf, all_corners=True)


ALTERNATIVES = [
    ("copies take the shape's color instead of the marker's color", alt_shape_color),
    ("only the first marker of each object produces a copy", alt_first_marker),
    ("row-adjacent and column-adjacent markers use the wrong mirror axis", alt_swapped),
    ("the diagonal marker's copy is mirrored on one axis only", alt_diag_one_axis),
    ("copies are the shape translated to the marker, not reflected", alt_translate),
    ("mirror line runs through the key cell, not the block center", alt_key_line),
    ("mirror line is the shape's bounding-box edge, not the block center", alt_bbox_edge),
    ("every marker gets the shape rotated 180 degrees about the block center", alt_rot180),
    ("copies are the shape transposed about the block corner", alt_transpose),
    ("diagonal markers produce no copy", alt_no_diag),
    ("all three other block corners get a copy, in the first marker's color", alt_all_corners),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len(set(len(r) for r in g)) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b775ac94.json").read_text())
    pairs = task["train"]
    # sanity: the true reading reproduces the outputs
    ok = sum(_render(p["input"], _true_tf) == p["output"] for p in pairs)
    print(f"true reading reproduces {ok}/{len(pairs)} outputs")
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
