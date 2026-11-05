import json
from pathlib import Path


def _T(g):
    return [list(r) for r in zip(*g)]


def _orient(inp, out):
    """True if stripes are columns (each output column is constant)."""
    return all(len(set(col)) == 1 for col in zip(*out))


def _marks(g):
    return [(r, c, g[r][c]) for r in range(len(g)) for c in range(len(g[0])) if g[r][c] != 0]


def _setup(inp, out):
    """Return (g, transposed, marks as (idx, color) sorted by idx), working in column-line form."""
    tr = not _orient(inp, out)
    g = _T(inp) if tr else [list(r) for r in inp]
    ms = sorted((c, v) for r, c, v in _marks(g))
    return g, tr, ms


def _render(lines, h, w, tr):
    """lines: dict col->color. Returns grid in original orientation."""
    g = [[lines.get(c, 0) for c in range(w)] for _ in range(h)]
    return _T(g) if tr else g


def _alt(start, d, colors, w, lo=0, limit=None):
    lines = {}
    k = 0
    pos = start
    while pos < w and (limit is None or k < limit):
        if pos >= lo:
            lines[pos] = colors[k % len(colors)]
        pos += d
        k += 1
    return lines


def _generic(inp, out, f):
    g, tr, ms = _setup(inp, out)
    if len(ms) != 2:
        return None
    h, w = len(g), len(g[0])
    (p1, c1), (p2, c2) = ms
    d = p2 - p1
    lines = f(h, w, p1, c1, p2, c2, d)
    if lines is None:
        return None
    return _render(lines, h, w, tr)


def only_marks(inp, out):
    return _generic(inp, out, lambda h, w, p1, c1, p2, c2, d: {p1: c1, p2: c2})


def half_step(inp, out):
    return _generic(inp, out, lambda h, w, p1, c1, p2, c2, d:
                    _alt(p1, max(d // 2, 1), [c1, c2], w))


def step_plus_one(inp, out):
    return _generic(inp, out, lambda h, w, p1, c1, p2, c2, d:
                    _alt(p1, d + 1, [c1, c2], w))


def both_directions(inp, out):
    def f(h, w, p1, c1, p2, c2, d):
        lines = _alt(p1, d, [c1, c2], w)
        k = 1
        while p1 - k * d >= 0:
            lines[p1 - k * d] = c1 if k % 2 == 0 else c2
            k += 1
        return lines
    return _generic(inp, out, f)


def from_second_mark(inp, out):
    return _generic(inp, out, lambda h, w, p1, c1, p2, c2, d:
                    _alt(p2, d, [c2, c1], w))


def swapped_colors(inp, out):
    return _generic(inp, out, lambda h, w, p1, c1, p2, c2, d:
                    _alt(p1, d, [c2, c1], w))


def single_color(inp, out):
    return _generic(inp, out, lambda h, w, p1, c1, p2, c2, d:
                    _alt(p1, d, [c1], w))


def offset_by_one(inp, out):
    return _generic(inp, out, lambda h, w, p1, c1, p2, c2, d:
                    _alt(p1 + 1, d, [c1, c2], w))


def only_three_lines(inp, out):
    return _generic(inp, out, lambda h, w, p1, c1, p2, c2, d:
                    _alt(p1, d, [c1, c2], w, limit=3))


def first_half_only(inp, out):
    return _generic(inp, out, lambda h, w, p1, c1, p2, c2, d:
                    {p: c for p, c in _alt(p1, d, [c1, c2], w).items() if p < w // 2})


def wrong_axis(inp, out):
    """Stripes drawn along the other axis, through the rows/columns of the marks."""
    g, tr, ms = _setup(inp, out)
    if len(ms) != 2:
        return None
    gt = _T(g)
    ms2 = sorted((c, v) for r, c, v in _marks(gt))
    h, w = len(gt), len(gt[0])
    (p1, c1), (p2, c2) = ms2
    d = p2 - p1
    if d > 0:
        lines = _alt(p1, d, [c1, c2], w)
    else:
        lines = {p1: c1}
    return _render(lines, h, w, not tr)


def skip_alternation_gap(inp, out):
    """Stripes at every second period only (period doubled), colors kept in order."""
    return _generic(inp, out, lambda h, w, p1, c1, p2, c2, d:
                    _alt(p1, 2 * d, [c1, c2], w))


ALTERNATIVES = [
    ("only the two marked lines are drawn, no repetition", only_marks),
    ("period taken as half the mark distance", half_step),
    ("period taken as mark distance plus one", step_plus_one),
    ("stripes extend toward the near edge as well as the far edge", both_directions),
    ("repetition starts at the second mark instead of the first", from_second_mark),
    ("the two stripe colors alternate in swapped order", swapped_colors),
    ("all stripes use the first mark's color", single_color),
    ("stripe positions shifted by one cell", offset_by_one),
    ("only three stripes drawn", only_three_lines),
    ("stripes drawn only in the first half of the grid", first_half_only),
    ("stripes run along the other axis through the marks", wrong_axis),
    ("period taken as twice the mark distance", skip_alternation_gap),
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
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/0a938d79.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
