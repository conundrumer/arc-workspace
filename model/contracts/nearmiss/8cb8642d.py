import json
from pathlib import Path


def _bg(g):
    c = {}
    for r in g:
        for v in r:
            c[v] = c.get(v, 0) + 1
    return max(c, key=c.get)


def _comps(g):
    """4-connected non-background components -> list of dicts."""
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
                    if 0 <= x < h and 0 <= y < w and g[x][y] != bg and (x, y) not in seen:
                        seen.add((x, y))
                        st.append((x, y))
            r0 = min(a for a, b in cells)
            r1 = max(a for a, b in cells)
            c0 = min(b for a, b in cells)
            c1 = max(b for a, b in cells)
            frame = g[r0][c0]
            marker = None
            for a, b in cells:
                if g[a][b] != frame:
                    marker = (a, b, g[a][b])
            res.append(dict(r0=r0, r1=r1, c0=c0, c1=c1, frame=frame, marker=marker, n=len(cells)))
    return res


def _margins(r0, r1, c0, c1, i, j):
    return (i - r0, r1 - i, j - c0, c1 - j)  # top, bottom, left, right


def _tie_cells(r0, r1, c0, c1, perp_only=False):
    out = set()
    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            m = _margins(r0, r1, c0, c1, i, j)
            lo = min(m)
            idx = [k for k in range(4) if m[k] == lo]
            if len(idx) < 2:
                continue
            if perp_only and not any(k < 2 for k in idx) or perp_only and not any(k >= 2 for k in idx):
                continue
            out.add((i, j))
    return out


def _plus_cells(r0, r1, c0, c1):
    rs = {(r0 + r1) // 2, (r0 + r1 + 1) // 2}
    cs = {(c0 + c1) // 2, (c0 + c1 + 1) // 2}
    return {(i, j) for i in range(r0, r1 + 1) for j in range(c0, c1 + 1) if i in rs or j in cs}


def _copy(g):
    return [r[:] for r in g]


def _interiors(inp):
    bg = _bg(inp)
    return bg, _comps(inp)


def _render(inp, per_comp, comps_filter=None):
    """Start from inp; per_comp(g, bg, comp) edits the interior of each component."""
    bg, comps = _interiors(inp)
    g = _copy(inp)
    for k, c in enumerate(comps):
        if comps_filter is not None and not comps_filter(k, c, comps):
            continue
        if c["marker"] is None:
            continue
        per_comp(g, bg, c)
    return g


def _clear_interior(g, bg, c):
    for i in range(c["r0"] + 1, c["r1"]):
        for j in range(c["c0"] + 1, c["c1"]):
            g[i][j] = bg


def _draw(g, cells, color):
    for i, j in cells:
        g[i][j] = color


def _interior(c):
    return c["r0"] + 1, c["r1"] - 1, c["c0"] + 1, c["c1"] - 1


def _same(a, b):
    return a == b


# ---- wrong readings ----

def frame_color(inp, out):
    def f(g, bg, c):
        r0, r1, c0, c1 = _interior(c)
        _clear_interior(g, bg, c)
        _draw(g, _tie_cells(r0, r1, c0, c1), c["frame"])
    return _render(inp, f)


def erase_only(inp, out):
    def f(g, bg, c):
        _clear_interior(g, bg, c)
    return _render(inp, f)


def inset_two(inp, out):
    def f(g, bg, c):
        r0, r1, c0, c1 = _interior(c)
        r0, r1, c0, c1 = r0 + 1, r1 - 1, c0 + 1, c1 - 1
        _clear_interior(g, bg, c)
        if r1 < r0 or c1 < c0:
            return
        _draw(g, _tie_cells(r0, r1, c0, c1), c["marker"][2])
    return _render(inp, f)


def main_diagonal_only(inp, out):
    def f(g, bg, c):
        r0, r1, c0, c1 = _interior(c)
        _clear_interior(g, bg, c)
        cells = set()
        for i, j in _tie_cells(r0, r1, c0, c1):
            m = _margins(r0, r1, c0, c1, i, j)
            lo = min(m)
            if (m[0] == lo and m[2] == lo) or (m[1] == lo and m[3] == lo):
                cells.add((i, j))
        _draw(g, cells, c["marker"][2])
    return _render(inp, f)


def marker_quadrant(inp, out):
    def f(g, bg, c):
        r0, r1, c0, c1 = _interior(c)
        mi, mj, col = c["marker"]
        top = mi <= (r0 + r1) / 2
        left = mj <= (c0 + c1) / 2
        _clear_interior(g, bg, c)
        cells = {
            (i, j) for (i, j) in _tie_cells(r0, r1, c0, c1)
            if (i <= (r0 + r1) / 2) == top and (j <= (c0 + c1) / 2) == left
        }
        _draw(g, cells, col)
    return _render(inp, f)


def plus_not_x(inp, out):
    def f(g, bg, c):
        r0, r1, c0, c1 = _interior(c)
        _clear_interior(g, bg, c)
        _draw(g, _plus_cells(r0, r1, c0, c1), c["marker"][2])
    return _render(inp, f)


def inverted(inp, out):
    def f(g, bg, c):
        r0, r1, c0, c1 = _interior(c)
        t = _tie_cells(r0, r1, c0, c1)
        for i in range(r0, r1 + 1):
            for j in range(c0, c1 + 1):
                g[i][j] = bg if (i, j) in t else c["marker"][2]
    return _render(inp, f)


def largest_only(inp, out):
    def flt(k, c, comps):
        return c["n"] == max(x["n"] for x in comps)
    def f(g, bg, c):
        r0, r1, c0, c1 = _interior(c)
        _clear_interior(g, bg, c)
        _draw(g, _tie_cells(r0, r1, c0, c1), c["marker"][2])
    g = _render(inp, f, flt)
    return g if g != out else None


def first_marker_color(inp, out):
    bg, comps = _interiors(inp)
    ms = [c for c in comps if c["marker"]]
    if len(ms) < 2:
        return None
    col = ms[0]["marker"][2]
    def f(g, bg, c):
        r0, r1, c0, c1 = _interior(c)
        _clear_interior(g, bg, c)
        _draw(g, _tie_cells(r0, r1, c0, c1), col)
    g = _render(inp, f)
    return g if g != out else None


def crop_interior(inp, out):
    bg, comps = _interiors(inp)
    c = comps[0]
    r0, r1, c0, c1 = _interior(c)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def crop_frame_box(inp, out):
    bg, comps = _interiors(inp)
    c = comps[0]
    return [row[c["c0"]:c["c1"] + 1] for row in out[c["r0"]:c["r1"] + 1]]


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("draw the interior pattern in the frame color instead of the marker color", frame_color),
    ("erase the marker and draw nothing inside", erase_only),
    ("draw the pattern one ring too far inside (inset by two instead of one)", inset_two),
    ("draw only the main diagonal (top-left to bottom-right) instead of both diagonals", main_diagonal_only),
    ("draw only the part of the pattern in the marker's quadrant", marker_quadrant),
    ("draw a centered plus (middle row and column) instead of the X", plus_not_x),
    ("fill the interior with the marker color and leave the X cells as background", inverted),
    ("process only the largest object and leave other objects as in the input", largest_only),
    ("use the first object's marker color for every object", first_marker_color),
    ("output only the interior of the first object (crop off the frame)", crop_interior),
    ("output only the first object's bounding box including frame", crop_frame_box),
    ("leave the input unchanged", unchanged),
]


def _valid(g):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    return all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/8cb8642d.json"))
    pairs = task["train"]
    # sanity: the correct rule reproduces the output
    def correct(inp, out):
        def f(g, bg, c):
            r0, r1, c0, c1 = _interior(c)
            _clear_interior(g, bg, c)
            _draw(g, _tie_cells(r0, r1, c0, c1), c["marker"][2])
        return _render(inp, f)
    ok = sum(correct(p["input"], p["output"]) == p["output"] for p in pairs)
    print(f"sanity: correct rule matches {ok}/{len(pairs)}")
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
