import json
from pathlib import Path


def _copy(g):
    return [row[:] for row in g]


def _marks(inp):
    return sorted((r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v)


def _step(marks):
    return marks[1][0] - marks[0][0]


def _new_color(inp, out):
    for r, row in enumerate(out):
        for c, v in enumerate(row):
            if v and not inp[r][c]:
                return v
    return 2


def _added(inp, out):
    return [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v and not inp[r][c]]


def _walk(inp, start, step):
    h, w = len(inp), len(inp[0])
    cells = []
    r, c = start
    while 0 <= r < h and 0 <= c < w:
        cells.append((r, c))
        r += step
        c += step
    return cells


def _paint(inp, cells, v):
    g = _copy(inp)
    for r, c in cells:
        if 0 <= r < len(g) and 0 <= c < len(g[0]):
            g[r][c] = v
    return g


def _ext(inp, out, step_delta=0, skip=0, color=None, drop=0):
    m = _marks(inp)
    s = _step(m) + step_delta
    if s <= 0:
        return None
    v = color or _new_color(inp, out)
    cells = _walk(inp, (m[-1][0] + s * (1 + skip), m[-1][1] + s * (1 + skip)), s)
    if drop:
        cells = cells[:-drop]
    return _paint(inp, cells, v)


def old_color(inp, out):
    return _ext(inp, out, color=1)


def other_color(inp, out):
    return _ext(inp, out, color=3)


def step_plus_one(inp, out):
    return _ext(inp, out, step_delta=1)


def step_minus_one(inp, out):
    return _ext(inp, out, step_delta=-1)


def skip_first(inp, out):
    g = _ext(inp, out, skip=1)
    return g if g and g != inp else None


def stop_early(inp, out):
    return _ext(inp, out, drop=1)


def only_next(inp, out):
    m = _marks(inp)
    s = _step(m)
    return _paint(inp, [(m[-1][0] + s, m[-1][1] + s)], _new_color(inp, out))


def fill_diagonal(inp, out):
    m = _marks(inp)
    cells = _walk(inp, m[0], 1)
    g = _copy(inp)
    for r, c in cells:
        if not g[r][c]:
            g[r][c] = _new_color(inp, out)
    return g


def recolor_marks(inp, out):
    g = _copy(out)
    for r, c in _marks(inp):
        g[r][c] = _new_color(inp, out)
    return g


def mirrored(inp, out):
    v = _new_color(inp, out)
    g = _copy(inp)
    w = len(inp[0])
    for r, c in _added(inp, out):
        g[r][w - 1 - c] = v
    return g


def shifted_row(inp, out):
    v = _new_color(inp, out)
    g = _copy(inp)
    for r, c in _added(inp, out):
        if r + 1 < len(g):
            g[r + 1][c] = v
    return g


def span_as_step(inp, out):
    m = _marks(inp)
    s = m[-1][0] - m[0][0]
    cells = _walk(inp, (m[-1][0] + s, m[-1][1] + s), s)
    g = _paint(inp, cells, _new_color(inp, out))
    return g if g != inp else None


ALTERNATIVES = [
    ("added cells keep the mark color 1 instead of the new color", old_color),
    ("added cells use color 3 instead of 2", other_color),
    ("spacing read one too large", step_plus_one),
    ("spacing read one too small", step_minus_one),
    ("sequence starts one spacing late, skipping the first new position", skip_first),
    ("sequence stops one cell early", stop_early),
    ("only the next position is added", only_next),
    ("every empty cell of the diagonal is filled, ignoring spacing", fill_diagonal),
    ("existing marks are recolored along with the added cells", recolor_marks),
    ("added cells are on the anti-diagonal (mirrored columns)", mirrored),
    ("added cells are one row below the diagonal", shifted_row),
    ("spacing read as the distance from first to last mark", span_as_step),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/0b17323b.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (
                isinstance(g, list)
                and g
                and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                and g != p["output"]
            )
            n += bool(ok)
        print(n, desc)
