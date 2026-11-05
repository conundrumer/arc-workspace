"""Near-miss rules for ARC task 0b148d64."""


def _runs(flags):
    """Return (start, end) inclusive runs of True in flags."""
    runs, start = [], None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        if not f and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(flags) - 1))
    return runs


def _panels(inp):
    """Panels as a dict {(row_idx, col_idx): (r0, r1, c0, c1)}; separators are all-0 lines."""
    h, w = len(inp), len(inp[0])
    rows = _runs([any(v != 0 for v in inp[r]) for r in range(h)])
    cols = _runs([any(inp[r][c] != 0 for r in range(h)) for c in range(w)])
    return {(i, j): (r0, r1, c0, c1)
            for i, (r0, r1) in enumerate(rows) for j, (c0, c1) in enumerate(cols)}


def _crop(g, box):
    r0, r1, c0, c1 = box
    return [row[c0:c1 + 1] for row in g[r0:r1 + 1]]


def _target(inp, out):
    """Key of the panel whose crop is the true output."""
    for k, box in _panels(inp).items():
        if _crop(inp, box) == out:
            return k
    return None


def _colors(inp, box):
    return {v for row in _crop(inp, box) for v in row if v != 0}


def _ink_count(inp, box):
    return sum(v != 0 for row in _crop(inp, box) for v in row)


def _shared_color(inp, tk, panels):
    """The ink color that the target panel does not own."""
    own = _colors(inp, panels[tk]) - set().union(
        *[_colors(inp, b) for k, b in panels.items() if k != tk])
    others = set().union(*[_colors(inp, b) for k, b in panels.items() if k != tk])
    return own, others


def diagonal_panel(inp, out):
    ps, tk = _panels(inp), _target(inp, out)
    if tk is None:
        return None
    return _crop(inp, ps[(1 - tk[0], 1 - tk[1])])


def horizontal_neighbor(inp, out):
    ps, tk = _panels(inp), _target(inp, out)
    if tk is None:
        return None
    return _crop(inp, ps[(tk[0], 1 - tk[1])])


def vertical_neighbor(inp, out):
    ps, tk = _panels(inp), _target(inp, out)
    if tk is None:
        return None
    return _crop(inp, ps[(1 - tk[0], tk[1])])


def top_left_panel(inp, out):
    ps = _panels(inp)
    g = _crop(inp, ps[(0, 0)])
    return g if g != out else None


def densest_panel(inp, out):
    ps = _panels(inp)
    k = max(ps, key=lambda k: _ink_count(inp, ps[k]))
    g = _crop(inp, ps[k])
    return g if g != out else None


def ink_bbox_only(inp, out):
    ps, tk = _panels(inp), _target(inp, out)
    if tk is None:
        return None
    r0, r1, c0, c1 = ps[tk]
    cells = [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
             if inp[r][c] != 0]
    if not cells:
        return None
    # bounding box of the cells of the target color, ignoring the shared 0 margins
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    g = [row[min(cs):max(cs) + 1] for row in inp[min(rs):max(rs) + 1]]
    # shrink one cell on the bottom and right: box of strictly interior ink
    g = [row[:-1] for row in g[:-1]]
    return g if g and g[0] else None


def padded_crop(inp, out):
    ps, tk = _panels(inp), _target(inp, out)
    if tk is None:
        return None
    r0, r1, c0, c1 = ps[tk]
    h, w = len(inp), len(inp[0])
    return _crop(inp, (max(r0 - 1, 0), min(r1 + 1, h - 1), max(c0 - 1, 0), min(c1 + 1, w - 1)))


def shared_color_recolor(inp, out):
    ps, tk = _panels(inp), _target(inp, out)
    if tk is None:
        return None
    own, others = _shared_color(inp, tk, ps)
    shared = others - own
    if len(shared) != 1:
        return None
    s = next(iter(shared))
    return [[s if v != 0 else 0 for v in row] for row in out]


def inverted_cells(inp, out):
    ink = max({v for row in out for v in row})
    return [[0 if v != 0 else ink for v in row] for row in out]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def flipped_horizontal(inp, out):
    return [row[::-1] for row in out]


def drop_first_row(inp, out):
    return out[1:]


def whole_band(inp, out):
    ps, tk = _panels(inp), _target(inp, out)
    if tk is None:
        return None
    r0, r1, _, _ = ps[tk]
    return [row[:] for row in inp[r0:r1 + 1]]


def blank_other_panels(inp, out):
    ps, tk = _panels(inp), _target(inp, out)
    if tk is None:
        return None
    g = [[0] * len(inp[0]) for _ in inp]
    r0, r1, c0, c1 = ps[tk]
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            g[r][c] = inp[r][c]
    return g


ALTERNATIVES = [
    ("crop the panel diagonally opposite the one with the unique color", diagonal_panel),
    ("crop the horizontally adjacent panel", horizontal_neighbor),
    ("crop the vertically adjacent panel", vertical_neighbor),
    ("always crop the top-left panel", top_left_panel),
    ("crop the right panel with a one-cell margin of separator included", padded_crop),
    ("recolor the ink of the right crop to the color the other panels share", shared_color_recolor),
    ("swap ink and background cells inside the right crop", inverted_cells),
    ("transpose the right crop", transposed),
    ("mirror the right crop left to right", flipped_horizontal),
    ("drop the first row of the right crop", drop_first_row),
    ("output the full-width band of rows containing the right panel", whole_band),
    ("keep the full grid size and blank every panel except the right one", blank_other_panels),
]


if __name__ == "__main__":
    import json
    from pathlib import Path

    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/0b148d64.json').read_text())
    pairs = task["train"]

    def valid(g, out):
        return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
                and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                and g != out)

    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
