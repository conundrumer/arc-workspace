"""Near-miss rules for 54db823b: erase the object with the fewest 9 cells."""
import json
from pathlib import Path


def _objects(g):
    h, w = len(g), len(g[0])
    seen = set()
    objs = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == 0 or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != 0 and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            objs.append(cells)
    return objs


def _marks(g, obj):
    return sum(1 for y, x in obj if g[y][x] == 9)


def _box(obj):
    ys = [y for y, _ in obj]
    xs = [x for _, x in obj]
    return min(ys), min(xs), max(ys), max(xs)


def _erase(g, cells, fill=0):
    o = [row[:] for row in g]
    for y, x in cells:
        o[y][x] = fill
    return o


def _box_cells(obj, shrink=0):
    y0, x0, y1, x1 = _box(obj)
    return [(y, x) for y in range(y0 + shrink, y1 + 1 - shrink)
            for x in range(x0 + shrink, x1 + 1 - shrink)]


def _pick(inp, key, reverse=False):
    objs = _objects(inp)
    if not objs:
        return None, objs
    vals = [key(inp, o) for o in objs]
    t = max(vals) if reverse else min(vals)
    return [o for o, v in zip(objs, vals) if v == t], objs


def most_marks(inp, out):
    sel, _ = _pick(inp, _marks, True)
    return _erase(inp, [c for o in sel for c in _box_cells(o)])


def largest(inp, out):
    sel, _ = _pick(inp, lambda g, o: len(o), True)
    return _erase(inp, [c for o in sel for c in _box_cells(o)])


def smallest(inp, out):
    sel, _ = _pick(inp, lambda g, o: len(o))
    return _erase(inp, [c for o in sel for c in _box_cells(o)])


def keep_only_fewest(inp, out):
    sel, objs = _pick(inp, _marks)
    keep = {c for o in sel for c in o}
    return _erase(inp, [c for o in objs for c in o if c not in keep])


def fewest_and_second(inp, out):
    objs = _objects(inp)
    counts = sorted({_marks(inp, o) for o in objs})
    if len(counts) < 2:
        return None
    chosen = [o for o in objs if _marks(inp, o) in counts[:2]]
    return _erase(inp, [c for o in chosen for c in o])


def fewest_threes(inp, out):
    sel, _ = _pick(inp, lambda g, o: sum(1 for y, x in o if g[y][x] == 3))
    return _erase(inp, [c for o in sel for c in _box_cells(o)])


def nines_only_erased(inp, out):
    sel, _ = _pick(inp, _marks)
    return _erase(inp, [(y, x) for o in sel for y, x in o if inp[y][x] == 9])


def fill_with_three(inp, out):
    sel, _ = _pick(inp, _marks)
    return _erase(inp, [c for o in sel for c in o], fill=3)


def shrunk_box(inp, out):
    sel, _ = _pick(inp, _marks)
    cells = [c for o in sel for c in _box_cells(o, 1)]
    if not cells:
        return None
    return _erase(inp, cells)


def highest_mark_density(inp, out):
    sel, _ = _pick(inp, lambda g, o: _marks(g, o) / len(o), True)
    return _erase(inp, [c for o in sel for c in _box_cells(o)])


def crop_fewest(inp, out):
    sel, _ = _pick(inp, _marks)
    o = sel[0]
    y0, x0, y1, x1 = _box(o)
    return [row[x0:x1 + 1] for row in inp[y0:y1 + 1]]


def first_tied_only(inp, out):
    sel, _ = _pick(inp, _marks)
    if len(sel) < 2:
        return None
    o = min(sel, key=lambda o: min(o))
    return _erase(inp, _box_cells(o))


def nines_to_three(inp, out):
    sel, _ = _pick(inp, _marks)
    return [[3 if (y, x) in {c for o in sel for c in o} and v == 9 else v
             for x, v in enumerate(row)] for y, row in enumerate(inp)]


ALTERNATIVES = [
    ("erase the object with the most 9 cells instead of the fewest", most_marks),
    ("erase the largest object by cell count", largest),
    ("erase the smallest object by cell count", smallest),
    ("keep only the fewest-9 object and erase all others", keep_only_fewest),
    ("erase both the fewest-9 and second-fewest-9 objects", fewest_and_second),
    ("count the 3 cells as marks and erase the object with the fewest 3s", fewest_threes),
    ("erase only the 9 cells of the fewest-9 object", nines_only_erased),
    ("paint the fewest-9 object with 3 instead of the background 0", fill_with_three),
    ("erase the fewest-9 object's box shrunk by one cell on each side", shrunk_box),
    ("erase the object with the highest share of 9 cells", highest_mark_density),
    ("output the cropped fewest-9 object instead of the full grid", crop_fewest),
    ("recolor the 9 cells of the fewest-9 object to 3 instead of erasing", nines_to_three),
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
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/54db823b.json').read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
