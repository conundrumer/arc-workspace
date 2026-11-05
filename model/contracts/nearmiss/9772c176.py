import json
from pathlib import Path


def _cells(inp, out):
    return [(r, c) for r in range(len(out)) for c in range(len(out[0]))
            if out[r][c] != inp[r][c]]


def _components(inp):
    h, w = len(inp), len(inp[0])
    seen = {}
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0 and (r, c) not in seen:
                idx = len(comps)
                stack = [(r, c)]
                seen[(r, c)] = idx
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0
                                and (ny, nx) not in seen):
                            seen[(ny, nx)] = idx
                            stack.append((ny, nx))
                comps.append(cells)
    return comps


def _owner(inp, cell, comps):
    best, bi = None, None
    for i, cells in enumerate(comps):
        d = min(abs(cell[0] - y) + abs(cell[1] - x) for y, x in cells)
        if best is None or d < best:
            best, bi = d, i
    return bi


def _bbox(cells):
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return min(ys), max(ys), min(xs), max(xs)


def _copy(g):
    return [row[:] for row in g]


def _recolor(color):
    def f(inp, out):
        g = _copy(out)
        for r, c in _cells(inp, out):
            g[r][c] = color
        return g
    return f


def _drop_object(pick):
    def f(inp, out):
        comps = _components(inp)
        if len(comps) < 2:
            return None
        target = pick(range(len(comps)), key=lambda i: len(comps[i]))
        g = _copy(out)
        for cell in _cells(inp, out):
            if _owner(inp, cell, comps) == target:
                g[cell[0]][cell[1]] = 0
        return g
    return f


def _drop_axis(vertical):
    def f(inp, out):
        comps = _components(inp)
        g = _copy(out)
        for cell in _cells(inp, out):
            i = _owner(inp, cell, comps)
            y0, y1, x0, x1 = _bbox(comps[i])
            in_cols = x0 <= cell[1] <= x1
            in_rows = y0 <= cell[0] <= y1
            if vertical and in_cols and not in_rows:
                g[cell[0]][cell[1]] = 0
            if not vertical and in_rows and not in_cols:
                g[cell[0]][cell[1]] = 0
        return g
    return f


def _touching(inp, r, c):
    h, w = len(inp), len(inp[0])
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ny, nx = r + dy, c + dx
        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0:
            return True
    return False


def one_deep(inp, out):
    g = _copy(inp)
    for r, c in _cells(inp, out):
        if _touching(inp, r, c):
            g[r][c] = out[r][c]
    return g


def gap_before_wedge(inp, out):
    g = _copy(out)
    for r, c in _cells(inp, out):
        if _touching(inp, r, c):
            g[r][c] = 0
    return g


def bbox_filled(inp, out):
    cells = set(_cells(inp, out))
    seen = set()
    g = _copy(out)
    for s in cells:
        if s in seen:
            continue
        stack = [s]
        seen.add(s)
        grp = []
        while stack:
            y, x = stack.pop()
            grp.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    n = (y + dy, x + dx)
                    if n in cells and n not in seen:
                        seen.add(n)
                        stack.append(n)
        y0, y1, x0, x1 = _bbox(grp)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if inp[y][x] == 0:
                    g[y][x] = 4
    return g


def fat_wedges(inp, out):
    h, w = len(out), len(out[0])
    g = _copy(out)
    for r, c in _cells(inp, out):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                y, x = r + dy, c + dx
                if 0 <= y < h and 0 <= x < w and g[y][x] == 0:
                    g[y][x] = 4
    return g


def unchanged(inp, out):
    return _copy(inp)


def wedges_overwrite_object(inp, out):
    # wedge shifted one cell toward the object: it replaces the object's border
    g = _copy(out)
    h, w = len(out), len(out[0])
    for r, c in _cells(inp, out):
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            y, x = r + dy, c + dx
            if 0 <= y < h and 0 <= x < w and inp[y][x] != 0 and not _touching_bg_free(inp, y, x):
                g[y][x] = 4
    return g


def _touching_bg_free(inp, r, c):
    h, w = len(inp), len(inp[0])
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ny, nx = r + dy, c + dx
        if not (0 <= ny < h and 0 <= nx < w) or inp[ny][nx] == 0:
            return False
    return True


def _shifted(dy, dx):
    def f(inp, out):
        h, w = len(out), len(out[0])
        g = _copy(inp)
        for r, c in _cells(inp, out):
            y, x = r + dy, c + dx
            if 0 <= y < h and 0 <= x < w and inp[y][x] == 0:
                g[y][x] = 4
        return g
    return f


ALTERNATIVES = [
    ("wedge color is 3 instead of 4", _recolor(3)),
    ("wedge takes the object's own color 8", _recolor(8)),
    ("the smallest object gets no wedges", _drop_object(min)),
    ("only the smallest object gets wedges", lambda i, o: _only_smallest(i, o)),
    ("only the largest object gets no wedges", _drop_object(max)),
    ("no wedges above or below objects (left and right only)", _drop_axis(True)),
    ("no wedges left or right of objects (top and bottom only)", _drop_axis(False)),
    ("wedges are one cell deep, no tapering stack", one_deep),
    ("wedge starts one cell away from the object, leaving a gap", gap_before_wedge),
    ("each wedge filled as its full bounding rectangle", bbox_filled),
    ("wedges one cell fatter in every direction", fat_wedges),
    ("wedges shifted one row down", _shifted(1, 0)),
]


def _only_smallest(inp, out):
    comps = _components(inp)
    if len(comps) < 2:
        return None
    target = min(range(len(comps)), key=lambda i: len(comps[i]))
    g = _copy(out)
    for cell in _cells(inp, out):
        if _owner(inp, cell, comps) != target:
            g[cell[0]][cell[1]] = 0
    return g


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/9772c176.json').read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
