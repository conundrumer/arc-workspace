import json
from pathlib import Path

BOX = 1
MARK = 4


def _template(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == BOX]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    motif = [(r - r0, c - c0) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if inp[r][c] == MARK]
    return r0, c0, r1 - r0 + 1, c1 - c0 + 1, motif


def _transforms(h, w):
    """The 8 D4 poses as (name, new_h, new_w, point map)."""
    return [
        ("id", h, w, lambda r, c: (r, c)),
        ("rot90", w, h, lambda r, c: (c, h - 1 - r)),
        ("rot180", h, w, lambda r, c: (h - 1 - r, w - 1 - c)),
        ("rot270", w, h, lambda r, c: (w - 1 - c, r)),
        ("flipv", h, w, lambda r, c: (h - 1 - r, c)),
        ("fliph", h, w, lambda r, c: (r, w - 1 - c)),
        ("transpose", w, h, lambda r, c: (c, r)),
        ("antitranspose", w, h, lambda r, c: (w - 1 - c, h - 1 - r)),
    ]


def _placements(inp, names=None, include_template=True):
    """Every posed box that sits on the marks: (r, c, h, w, motif cells in grid)."""
    R, C = len(inp), len(inp[0])
    r0, c0, h, w, motif = _template(inp)
    found = []
    for name, nh, nw, f in _transforms(h, w):
        if names is not None and name not in names:
            continue
        pm = [f(r, c) for r, c in motif]
        for dr in range(-nh, R + nh):
            for dc in range(-nw, C + nw):
                ok = True
                for pr, pc in pm:
                    rr, cc = pr + dr, pc + dc
                    if not (0 <= rr < R and 0 <= cc < C and inp[rr][cc] == MARK):
                        ok = False
                        break
                if ok:
                    found.append((dr, dc, nh, nw, [(pr + dr, pc + dc) for pr, pc in pm]))
    return found


def _draw(inp, places, color=BOX, margin=0, shift=(0, 0), part="all", overwrite_marks=False, clip_full=False):
    R, C = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for (r, c, h, w, _) in places:
        r, c, h, w = r - margin + shift[0], c - margin + shift[1], h + 2 * margin, w + 2 * margin
        if clip_full and (r < 0 or c < 0 or r + h > R or c + w > C):
            continue
        for rr in range(r, r + h):
            for cc in range(c, c + w):
                if not (0 <= rr < R and 0 <= cc < C):
                    continue
                border = rr in (r, r + h - 1) or cc in (c, c + w - 1)
                if part == "border" and not border:
                    continue
                if part == "interior" and border:
                    continue
                if g[rr][cc] == MARK and not overwrite_marks:
                    continue
                g[rr][cc] = color
    return g


def _strip_template(inp, g):
    r0, c0, h, w, _ = _template(inp)
    g = [row[:] for row in g]
    for r in range(r0, r0 + h):
        for c in range(c0, c0 + w):
            if g[r][c] == BOX:
                g[r][c] = 0
    return g


def _all(inp):
    return _placements(inp)


def true_rule(inp):
    return _draw(inp, _all(inp))


def alt_quarter_turns_only(inp, out):
    return _draw(inp, _placements(inp, {"id", "rot90", "rot270"}))


def alt_no_rotation(inp, out):
    return _draw(inp, _placements(inp, {"id", "flipv", "fliph", "rot180"}))


def alt_no_transpose(inp, out):
    # keeps the template's height and width: poses that swap them are dropped
    return _draw(inp, _placements(inp, {"id", "rot180", "flipv", "fliph"}))


def alt_border_only(inp, out):
    return _draw(inp, _all(inp), part="border")


def alt_interior_only(inp, out):
    return _draw(inp, _all(inp), part="interior")


def alt_box_color_mark(inp, out):
    return _draw(inp, _all(inp), color=MARK)


def alt_overwrite_marks(inp, out):
    return _draw(inp, _all(inp), overwrite_marks=True)


def alt_margin_two(inp, out):
    return _draw(inp, _all(inp), margin=1)


def alt_skip_clipped(inp, out):
    return _draw(inp, _all(inp), clip_full=True)


def alt_shifted(inp, out):
    return _draw(inp, _all(inp), shift=(1, 0))


def alt_first_only(inp, out):
    places = sorted(_all(inp), key=lambda p: (p[0], p[1]))
    tr, tc = _template(inp)[:2]
    others = [p for p in places if (p[0], p[1]) != (tr, tc)]
    return _draw(inp, others[:1])


def alt_erase_template(inp, out):
    return _strip_template(inp, out)


ALTERNATIVES = [
    ("only the template pose and quarter turns are tried, 180 turn and mirrors are missed", alt_quarter_turns_only),
    ("only mirror poses and 180 turn are tried, 90 degree turns are missed", alt_no_rotation),
    ("poses that swap box height and width are missed", alt_no_transpose),
    ("each found box is drawn as a hollow outline, interior left empty", alt_border_only),
    ("only the interior of each found box is filled, no outline ring", alt_interior_only),
    ("found boxes are drawn in the mark color instead of the box color", alt_box_color_mark),
    ("found boxes are drawn over the marks too, marks become box color", alt_overwrite_marks),
    ("found boxes are drawn one cell larger on every side", alt_margin_two),
    ("boxes that run past the grid edge are dropped", alt_skip_clipped),
    ("found boxes are drawn one row too low", alt_shifted),
    ("only the first found copy is drawn", alt_first_only),
    ("the original template box is erased", alt_erase_template),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    w = len(g[0])
    if w == 0:
        return False
    for row in g:
        if not isinstance(row, list) or len(row) != w:
            return False
        for v in row:
            if type(v) is not int or not 0 <= v <= 9:
                return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/7df24a62.json"))
    train = task["train"]
    for i, p in enumerate(train):
        assert true_rule(p["input"]) == p["output"], f"true rule differs on pair {i}"
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in train)
        print(f"{n}/{len(train)}  {desc}")
