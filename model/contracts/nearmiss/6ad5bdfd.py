import json
from pathlib import Path


def _wall(inp):
    """Return (color, (dr, dc)) of the constant non-zero full edge line, and the direction toward it."""
    h, w = len(inp), len(inp[0])
    edges = [
        (inp[0], (-1, 0)),
        (inp[-1], (1, 0)),
        ([r[0] for r in inp], (0, -1)),
        ([r[-1] for r in inp], (0, 1)),
    ]
    for line, d in edges:
        if line[0] != 0 and len(set(line)) == 1:
            return line[0], d
    return None, None


def _components(g, skip):
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if g[r][c] in (0, skip) or (r, c) in seen:
                continue
            col = g[r][c]
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and g[ny][nx] == col:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append((col, cells))
    return comps


def _slide(inp, d, clearance=1, movers=None, solid=True):
    """Slide each non-wall object rigidly along d until blocked.

    clearance: number of free cells needed ahead for a step (2 leaves a gap).
    movers: indices of components allowed to move (None = all).
    solid: if False, objects do not block each other (only the wall does).
    """
    h, w = len(inp), len(inp[0])
    wc, _ = _wall(inp)
    comps = [[col, list(cells)] for col, cells in _components(inp, wc)]
    grid = [row[:] for row in inp]
    base = [[(v if v == wc else 0) for v in row] for row in inp]

    def occupied():
        occ = {}
        for i, (col, cells) in enumerate(comps):
            for p in cells:
                occ[p] = i
        return occ

    changed = True
    while changed:
        changed = False
        for i, (col, cells) in enumerate(comps):
            if movers is not None and i not in movers:
                continue
            occ = occupied()
            own = set(cells)
            ok = True
            for k in range(1, clearance + 1):
                for (y, x) in cells:
                    ny, nx = y + d[0] * k, x + d[1] * k
                    if not (0 <= ny < h and 0 <= nx < w):
                        ok = False
                        break
                    if base[ny][nx] != 0:
                        ok = False
                        break
                    if solid and (ny, nx) in occ and (ny, nx) not in own:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                comps[i][1] = [(y + d[0], x + d[1]) for (y, x) in cells]
                changed = True
    res = [row[:] for row in base]
    for col, cells in comps:
        for (y, x) in cells:
            res[y][x] = col
    return res


def unchanged(inp, out):
    return [row[:] for row in inp]


def away_from_wall(inp, out):
    _, d = _wall(inp)
    return _slide(inp, (-d[0], -d[1]))


def perpendicular(inp, out):
    _, d = _wall(inp)
    return _slide(inp, (d[1], d[0]) if d[0] == 0 else (d[1], d[0]))


def wall_erased(inp, out):
    wc, _ = _wall(inp)
    return [[0 if v == wc else v for v in row] for row in out]


def pass_through(inp, out):
    _, d = _wall(inp)
    return _slide(inp, d, solid=False)


def gap_left(inp, out):
    _, d = _wall(inp)
    return _slide(inp, d, clearance=2)


def recolor_to_wall(inp, out):
    wc, _ = _wall(inp)
    return [[wc if v != 0 else 0 for v in row] for row in out]


def copy_not_move(inp, out):
    return [[a if a != 0 else b for a, b in zip(ri, ro)] for ri, ro in zip(inp, out)]


def crop_wall(inp, out):
    wc, d = _wall(inp)
    if d[0] == 1:
        return [r[:] for r in out[:-1]]
    if d[0] == -1:
        return [r[:] for r in out[1:]]
    if d[1] == 1:
        return [r[:-1] for r in out]
    return [r[1:] for r in out]


def only_nearest_moves(inp, out):
    wc, d = _wall(inp)
    comps = _components(inp, wc)
    h, w = len(inp), len(inp[0])

    def dist(cells):
        if d[0] == 1:
            return min(h - 1 - y for y, x in cells)
        if d[0] == -1:
            return min(y for y, x in cells)
        if d[1] == 1:
            return min(w - 1 - x for y, x in cells)
        return min(x for y, x in cells)

    best = min(range(len(comps)), key=lambda i: dist(comps[i][1]))
    return _slide(inp, d, movers={best})


def only_far_half_moves(inp, out):
    # objects already adjacent to the wall side of the board half stay; only those in the far half fall
    wc, d = _wall(inp)
    comps = _components(inp, wc)
    h, w = len(inp), len(inp[0])

    def far(cells):
        if d[0] != 0:
            mid = (h - 1) / 2
            return all((y < mid) if d[0] == 1 else (y > mid) for y, x in cells)
        mid = (w - 1) / 2
        return all((x < mid) if d[1] == 1 else (x > mid) for y, x in cells)

    movers = {i for i, (c, cells) in enumerate(comps) if far(cells)}
    return _slide(inp, d, movers=movers)


ALTERNATIVES = [
    ("objects stay where they are (no movement)", unchanged),
    ("objects slide away from the wall instead of toward it", away_from_wall),
    ("objects slide along the axis perpendicular to the wall", perpendicular),
    ("correct slide but the wall line is erased to background", wall_erased),
    ("objects slide to the wall but pass through each other instead of stacking", pass_through),
    ("objects stop one cell short of what they hit, leaving a gap", gap_left),
    ("landed objects take the wall color", recolor_to_wall),
    ("objects are copied to the landing place and also remain at the start", copy_not_move),
    ("output crops off the wall line, one row or column smaller", crop_wall),
    ("only the object nearest the wall moves", only_nearest_moves),
    ("only objects wholly in the half far from the wall move", only_far_half_moves),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/6ad5bdfd.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, repr(e))
                g = None
            if g is None:
                continue
            ok = (
                isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                and g != p["output"]
            )
            n += ok
        print(n, desc)
