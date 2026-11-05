"""Near-miss readings for ARC task 3bdb4ada."""
import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _rects(g):
    """Bounding boxes (r0, c0, r1, c1, color) of 4-connected non-bg components."""
    bg = _bg(g)
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    for i in range(h):
        for j in range(w):
            if g[i][j] == bg or (i, j) in seen:
                continue
            st = [(i, j)]
            seen.add((i, j))
            cells = []
            while st:
                a, b = st.pop()
                cells.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and (x, y) not in seen and g[x][y] == g[i][j]:
                        seen.add((x, y))
                        st.append((x, y))
            rs = [c[0] for c in cells]
            cs = [c[1] for c in cells]
            res.append((min(rs), min(cs), max(rs), max(cs), g[i][j]))
    res.sort()
    return res


def _copy(g):
    return [list(r) for r in g]


def _mid(r):
    r0, c0, r1, c1, _ = r
    return (r0 + r1) // 2


def _true_erase(r):
    """Cells the correct rule erases for rect r (horizontal dash)."""
    r0, c0, r1, c1, _ = r
    m = _mid(r)
    return [(m, c) for c in range(c0 + 1, c1) if (c - c0) % 2 == 1]


def _apply(g, cells, val):
    o = _copy(g)
    for a, b in cells:
        o[a][b] = val
    return o


def whole_row_erased(inp, out):
    bg = _bg(inp)
    cells = []
    for r in _rects(inp):
        cells += [(_mid(r), c) for c in range(r[1], r[3] + 1)]
    return _apply(inp, cells, bg)


def inverted_phase(inp, out):
    bg = _bg(inp)
    cells = []
    for r in _rects(inp):
        cells += [(_mid(r), c) for c in range(r[1] + 1, r[3]) if (c - r[1]) % 2 == 0]
    return _apply(inp, cells, bg)


def period_three(inp, out):
    bg = _bg(inp)
    cells = []
    for r in _rects(inp):
        cells += [(_mid(r), c) for c in range(r[1] + 1, r[3]) if (c - r[1]) % 3 != 0]
    return _apply(inp, cells, bg)


def checkerboard(inp, out):
    bg = _bg(inp)
    cells = []
    for r in _rects(inp):
        m = _mid(r)
        cells += [(m, c) for c in range(r[1] + 1, r[3]) if (m - r[0] + c - r[1]) % 2 == 1]
    return _apply(inp, cells, bg)


def only_first_gap(inp, out):
    bg = _bg(inp)
    cells = []
    for r in _rects(inp):
        cells += _true_erase(r)[:1]
    return _apply(inp, cells, bg)


def wrong_fill_color(inp, out):
    rs = _rects(inp)
    if len(rs) < 2:
        return None
    o = _copy(inp)
    for k, r in enumerate(rs):
        other = rs[(k + 1) % len(rs)][4]
        for a, b in _true_erase(r):
            o[a][b] = other
    return o


def only_first_rect(inp, out):
    rs = _rects(inp)
    if len(rs) < 2:
        return None
    bg = _bg(inp)
    cells = []
    for r in rs[:1]:
        cells += _true_erase(r)
    return _apply(inp, cells, bg)


def border_rows_dashed(inp, out):
    bg = _bg(inp)
    cells = []
    for r in _rects(inp):
        r0, c0, r1, c1, _ = r
        for rr in (r0, r1):
            cells += [(rr, c) for c in range(c0 + 1, c1) if (c - c0) % 2 == 1]
    return _apply(inp, cells, bg)


def ends_also_erased(inp, out):
    bg = _bg(inp)
    cells = []
    for r in _rects(inp):
        cells += _true_erase(r) + [(_mid(r), r[1]), (_mid(r), r[3])]
    return _apply(inp, cells, bg)


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("the whole middle row of each rectangle is erased, not every other cell", whole_row_erased),
    ("dash phase is inverted: the cells next to the rim are kept and the alternate ones erased", inverted_phase),
    ("dash period is one ink cell then two gap cells", period_three),
    ("the interior is erased as a checkerboard on row and column parity", checkerboard),
    ("only the first gap cell of each rectangle is erased", only_first_gap),
    ("erased cells are painted with the other rectangle's color instead of background", wrong_fill_color),
    ("only the first rectangle in reading order gets the dash", only_first_rect),
    ("the dash is cut into the top and bottom rim rows instead of the middle row", border_rows_dashed),
    ("the rim cells at both ends of the middle row are also erased", ends_also_erased),
    ("the input is returned unchanged", unchanged),
]


def _valid(g, ref):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != ref
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/3bdb4ada.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
