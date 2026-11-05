"""Near-miss readings for ARC task 1acc24af.

Rule: the wall (color 1) has notches that open downward. Each loose piece
(color 5) that can be turned so that it exactly plugs one notch, with all of
its cells in space reachable from below, becomes color 2.
"""
import json
from pathlib import Path

WALL, PIECE, MARK = 1, 5, 2


def _components(inp, color):
    h, w = len(inp), len(inp[0])
    seen, comps = set(), []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == color and (r, c) not in seen:
                stack, comp = [(r, c)], set()
                seen.add((r, c))
                while stack:
                    y, x = stack.pop()
                    comp.add((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        n = (y + dy, x + dx)
                        if (0 <= n[0] < h and 0 <= n[1] < w and n not in seen
                                and inp[n[0]][n[1]] == color):
                            seen.add(n)
                            stack.append(n)
                comps.append(comp)
    return comps


def _flood(inp, blocked_colors, sources):
    h, w = len(inp), len(inp[0])
    reached = set()
    stack = [s for s in sources if inp[s[0]][s[1]] not in blocked_colors]
    reached.update(stack)
    while stack:
        y, x = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (y + dy, x + dx)
            if (0 <= n[0] < h and 0 <= n[1] < w and n not in reached
                    and inp[n[0]][n[1]] not in blocked_colors):
                reached.add(n)
                stack.append(n)
    return reached


def _access(inp):
    h, w = len(inp), len(inp[0])
    return _flood(inp, {WALL}, [(h - 1, c) for c in range(w)])


def _wall_box(inp):
    cells = [(r, c) for r in range(len(inp)) for c in range(len(inp[0]))
             if inp[r][c] == WALL]
    r0, r1 = min(r for r, _ in cells), max(r for r, _ in cells)
    c0, c1 = min(c for _, c in cells), max(c for _, c in cells)
    return r0, r1, c0, c1


def _notch_cells(inp, access=None):
    access = _access(inp) if access is None else access
    r0, r1, c0, c1 = _wall_box(inp)
    return {(r, c) for (r, c) in access if r0 <= r <= r1 and c0 <= c <= c1}


def _split(cells):
    cells = set(cells)
    comps = []
    while cells:
        s = cells.pop()
        comp, stack = {s}, [s]
        while stack:
            y, x = stack.pop()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (y + dy, x + dx)
                if n in cells:
                    cells.remove(n)
                    comp.add(n)
                    stack.append(n)
        comps.append(comp)
    return comps


def _rot(cells):
    return {(c, -r) for r, c in cells}


def _flip(cells):
    return {(r, -c) for r, c in cells}


def _norm(cells):
    r0 = min(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    return frozenset((r - r0, c - c0) for r, c in cells)


def _orients(cells, mode):
    out, cur = [], set(cells)
    for _ in range(4):
        out.append(cur)
        cur = _rot(cur)
        if mode == "id":
            break
    if mode == "d4":
        f = _flip(cells)
        for _ in range(4):
            out.append(f)
            f = _rot(f)
    seen, res = set(), []
    for o in out:
        n = _norm(o)
        if n not in seen:
            seen.add(n)
            res.append(n)
    return res


def _plug_placements(inp, piece, mode="c4", need_access=True, exact=True):
    """Yield placed cell sets (rotated piece shifted onto a notch)."""
    access = _access(inp)
    notch = _notch_cells(inp, access)
    if not need_access:
        r0, r1, c0, c1 = _wall_box(inp)
        notch = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
                 if inp[r][c] != WALL}
        access = {(r, c) for r in range(len(inp)) for c in range(len(inp[0]))
                  if inp[r][c] != WALL}
    ncomps = _split(notch)
    found = []
    for o in _orients(piece, mode):
        for comp in ncomps:
            for q in o:
                for p in comp:
                    t = (p[0] - q[0], p[1] - q[1])
                    placed = {(a + t[0], b + t[1]) for a, b in o}
                    if not placed <= access:
                        continue
                    if exact:
                        if comp <= placed:
                            found.append((placed, comp))
                    else:
                        if placed <= notch:
                            found.append((placed, comp))
    return found


def _paint(inp, cells, color):
    g = [row[:] for row in inp]
    for r, c in cells:
        g[r][c] = color
    return g


def _marked_pieces(inp, **kw):
    return [p for p in _components(inp, PIECE) if _plug_placements(inp, p, **kw)]


def _recolor(inp, pieces, color=MARK):
    return _paint(inp, set().union(*pieces) if pieces else set(), color)


# ---- wrong readings -------------------------------------------------------

def no_turning(inp, out):
    return _recolor(inp, _marked_pieces(inp, mode="id"))


def half_turn_only(inp, out):
    ok = []
    for piece in _components(inp, PIECE):
        saved = _orients
        try:
            globals()["_orients"] = lambda cells, mode: list({
                _norm(cells), _norm(_rot(_rot(cells)))})
            if _plug_placements(inp, piece):
                ok.append(piece)
        finally:
            globals()["_orients"] = saved
    return _recolor(inp, ok)


def ignore_reachability(inp, out):
    return _recolor(inp, _marked_pieces(inp, need_access=False))


def fits_without_filling(inp, out):
    return _recolor(inp, _marked_pieces(inp, exact=False))


def recolor_all_pieces(inp, out):
    return _recolor(inp, _components(inp, PIECE))


def inverse_marking(inp, out):
    ok = _marked_pieces(inp)
    return _recolor(inp, [p for p in _components(inp, PIECE) if p not in ok])


def wrong_mark_color(inp, out):
    return _recolor(inp, _marked_pieces(inp), color=3)


def fill_notch_not_piece(inp, out):
    ok = _marked_pieces(inp)
    cells = set()
    for p in ok:
        for placed, comp in _plug_placements(inp, p):
            cells |= comp
            break
    return _paint(inp, cells, MARK)


def recolor_wall(inp, out):
    ok = _marked_pieces(inp)
    if not ok:
        return None
    return _recolor(inp, _components(inp, WALL))


def piece_moves_into_notch(inp, out):
    g = [row[:] for row in inp]
    for p in _marked_pieces(inp):
        placed, _ = _plug_placements(inp, p)[0]
        for r, c in p:
            g[r][c] = 0
        for r, c in placed:
            g[r][c] = MARK
    return g


def first_marked_only(inp, out):
    ok = sorted(_marked_pieces(inp), key=lambda p: min(p))
    if len(ok) < 2:
        return None
    return _recolor(inp, ok[:1])


def area_match_only(inp, out):
    """Mark pieces whose cell count equals some notch's cell count."""
    notch_sizes = {len(c) for c in _split(_notch_cells(inp))}
    return _recolor(inp, [p for p in _components(inp, PIECE)
                          if len(p) in notch_sizes])


def bbox_match_only(inp, out):
    """Mark pieces whose bounding box matches a notch's box (in some turn)."""
    def dims(cells):
        rs = [r for r, _ in cells]
        cs = [c for _, c in cells]
        return (max(rs) - min(rs) + 1, max(cs) - min(cs) + 1)
    nd = set()
    for c in _split(_notch_cells(inp)):
        a, b = dims(c)
        nd |= {(a, b), (b, a)}
    return _recolor(inp, [p for p in _components(inp, PIECE) if dims(p) in nd])


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("pieces may not be turned, only slid", no_turning),
    ("pieces may only be kept as they are or turned half a turn", half_turn_only),
    ("placement ignores reachability from the open side", ignore_reachability),
    ("a piece that fits inside a notch counts, even if it leaves notch cells empty", fits_without_filling),
    ("every piece is recolored", recolor_all_pieces),
    ("the pieces that do not plug a notch are recolored", inverse_marking),
    ("plugging pieces are recolored to 3 instead of 2", wrong_mark_color),
    ("the notch cells are colored 2 and the pieces stay 5", fill_notch_not_piece),
    ("the plugging pieces move into the notch and are colored 2", piece_moves_into_notch),
    ("only the first plugging piece is recolored", first_marked_only),
    ("pieces whose cell count equals a notch's cell count are recolored", area_match_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/1acc24af.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {fn.__name__}: {desc}")
