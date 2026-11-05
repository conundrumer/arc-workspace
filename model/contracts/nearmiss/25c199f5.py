import json
from pathlib import Path

BG = 7
SEP = 6


def _panels(inp):
    """Split the input at columns that are all SEP; return list of panels."""
    h, w = len(inp), len(inp[0])
    seps = [c for c in range(w) if all(inp[r][c] == SEP for r in range(h))]
    cuts = [-1] + seps + [w]
    panels = []
    for a, b in zip(cuts, cuts[1:]):
        if b > a + 1:
            panels.append([row[a + 1:b] for row in inp])
    return panels


def _ordered(inp):
    """Panels in the true stacking order: last panel first (top of the stack)."""
    return list(reversed(_panels(inp)))


def _ink_rows(panel):
    return [row for row in panel if any(v != BG for v in row)]


def _stack_bottom(rows, h, w):
    pad = [[BG] * w for _ in range(h - len(rows))]
    return pad + [list(r) for r in rows]


def _stack_top(rows, h, w):
    pad = [[BG] * w for _ in range(h - len(rows))]
    return [list(r) for r in rows] + pad


def reversed_panels(inp, out):
    ps = _panels(inp)
    rows = [r for p in ps for r in _ink_rows(p)]
    return _stack_bottom(rows, len(inp), len(ps[0][0]))


def gap_between_panels(inp, out):
    ps = _ordered(inp)
    w = len(ps[0][0])
    rows = []
    for i, p in enumerate(ps):
        if i:
            rows.append([BG] * w)
        rows.extend(_ink_rows(p))
    h = len(inp)
    return _stack_bottom(rows[-h:], h, w)


def lines_shifted_right(inp, out):
    return [[row[-1]] + row[:-1] if any(v != BG for v in row) else list(row) for row in out]


def overlay_in_place(inp, out):
    ps = _panels(inp)
    h, w = len(ps[0]), len(ps[0][0])
    g = [[BG] * w for _ in range(h)]
    for p in ps:
        for r in range(h):
            for c in range(w):
                if p[r][c] != BG:
                    g[r][c] = p[r][c]
    return g


def first_panel_only(inp, out):
    return _panels(inp)[0]


def drop_last_panel(inp, out):
    ps = _ordered(inp)[:-1]
    rows = [r for p in ps for r in _ink_rows(p)]
    return _stack_bottom(rows, len(inp), len(ps[0][0]))


def keep_blank_rows(inp, out):
    ps = _ordered(inp)
    return [list(r) for p in ps for r in p]


def stack_columns_right(inp, out):
    ps = _panels(inp)
    h = len(ps[0])
    cols = []
    for p in ps:
        for c in range(len(p[0])):
            col = [p[r][c] for r in range(h)]
            if any(v != BG for v in col):
                cols.append(col)
    cols = [[BG] * h for _ in range(len(ps[0][0]) - len(cols))] + cols
    return [[cols[c][r] for c in range(len(cols))] for r in range(h)]


def recolor_ink_one(inp, out):
    return [[1 if v != BG else BG for v in row] for row in out]


def flip_output_vertically(inp, out):
    return [list(r) for r in reversed(out)]


def order_by_ink_size(inp, out):
    ps = sorted(_ordered(inp), key=lambda p: -sum(v != BG for r in p for v in r))
    rows = [r for p in ps for r in _ink_rows(p)]
    return _stack_bottom(rows, len(inp), len(ps[0][0]))


def drop_first_line_of_each(inp, out):
    ps = _ordered(inp)
    rows = [r for p in ps for r in _ink_rows(p)[1:]]
    return _stack_bottom(rows, len(inp), len(ps[0][0]))


ALTERNATIVES = [
    ("panels stacked in reverse order (last panel at the bottom)", reversed_panels),
    ("one background line left between consecutive panels", gap_between_panels),
    ("every ink line shifted one column right with wraparound", lines_shifted_right),
    ("panels overlaid in place on one grid instead of stacked", overlay_in_place),
    ("output is the first panel alone", first_panel_only),
    ("panel at the top of the stack left out", drop_last_panel),
    ("background lines kept, so all panel rows are concatenated", keep_blank_rows),
    ("panels stacked sideways: ink columns packed to the right", stack_columns_right),
    ("all ink recolored to color 1", recolor_ink_one),
    ("true output flipped top to bottom", flip_output_vertically),
    ("panels ordered by ink cell count, largest at the top", order_by_ink_size),
    ("first ink line of each panel dropped", drop_first_line_of_each),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/25c199f5.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
