"""Near-miss readings for ARC task 19bb5feb.

Rule: a panel (color 8) on a background (0) holds 2x2 marker blocks of other
colors. The output is a compact grid in which each marker sits at the dense
rank of its row and column among the markers.
"""
import json
from pathlib import Path

BG = 0
PANEL = 8


def _marks(inp):
    """Return a list of (row, col, color) for each 2x2 marker block (top-left cell)."""
    h, w = len(inp), len(inp[0])
    seen = set()
    marks = []
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v in (BG, PANEL) or (r, c) in seen:
                continue
            stack = [(r, c)]
            cells = []
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] == v:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            marks.append((min(y for y, _ in cells), min(x for _, x in cells), v))
    return sorted(marks)


def _panel_box(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != BG]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return r0, r1, c0, c1


def flip_v(inp, out):
    return [row[:] for row in out[::-1]]


def flip_h(inp, out):
    return [row[::-1] for row in out]


def rot_cw(inp, out):
    return [list(col) for col in zip(*out[::-1])]


def panel_crop(inp, out):
    r0, r1, c0, c1 = _panel_box(inp)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def marks_crop(inp, out):
    ms = _marks(inp)
    r0 = min(r for r, _, _ in ms)
    c0 = min(c for _, c, _ in ms)
    r1 = max(r for r, _, _ in ms) + 1
    c1 = max(c for _, c, _ in ms) + 1
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def empty_as_panel(inp, out):
    return [[PANEL if v == BG else v for v in row] for row in out]


def reading_order_row(inp, out):
    return [[v for _, _, v in _marks(inp)]]


def scaled_by_two(inp, out):
    res = []
    for row in out:
        wide = [v for v in row for _ in range(2)]
        res.append(wide[:])
        res.append(wide[:])
    return res


def drop_last_mark(inp, out):
    ms = _marks(inp)
    last = ms[-1][2]
    return [[BG if v == last else v for v in row] for row in out]


def no_tie_merge(inp, out):
    ms = _marks(inp)
    n = len(ms)
    by_row = sorted(range(n), key=lambda i: (ms[i][0], ms[i][1]))
    by_col = sorted(range(n), key=lambda i: (ms[i][1], ms[i][0]))
    rk_r = {i: k for k, i in enumerate(by_row)}
    rk_c = {i: k for k, i in enumerate(by_col)}
    res = [[BG] * n for _ in range(n)]
    for i, (_, _, v) in enumerate(ms):
        res[rk_r[i]][rk_c[i]] = v
    if res == out:
        return None
    return res


def border_added(inp, out):
    w = len(out[0]) + 2
    return [[PANEL] * w] + [[PANEL] + row[:] + [PANEL] for row in out] + [[PANEL] * w]


def reversed_colors(inp, out):
    cells = [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v != BG]
    vals = [out[r][c] for r, c in cells][::-1]
    res = [row[:] for row in out]
    for (r, c), v in zip(cells, vals):
        res[r][c] = v
    return res


ALTERNATIVES = [
    ("Ranks counted from the bottom edge, so rows come out upside down", flip_v),
    ("Ranks counted from the right edge, so columns come out mirrored", flip_h),
    ("Layout rotated a quarter turn clockwise", rot_cw),
    ("Output is the raw panel crop at full resolution", panel_crop),
    ("Output is the raw crop of the marker bounding box, gaps kept", marks_crop),
    ("Empty rank cells filled with the panel color instead of background", empty_as_panel),
    ("Markers listed in reading order as a single row", reading_order_row),
    ("Each rank cell drawn at marker size 2x2", scaled_by_two),
    ("Last marker in reading order left out", drop_last_mark),
    ("Markers sharing a row or column are not merged into one rank", no_tie_merge),
    ("Output framed with a one-cell panel-color border", border_added),
    ("Marker colors assigned in reverse reading order", reversed_colors),
]


def _valid(g, out):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/19bb5feb.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
