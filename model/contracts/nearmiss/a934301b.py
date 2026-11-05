import json
from pathlib import Path


def _objects(inp, diag=False):
    h, w = len(inp), len(inp[0])
    seen = set()
    objs = []
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diag:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0 and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy, dx in steps:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0 and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                objs.append(cells)
    return objs


def _marks(inp, cells):
    return sum(1 for y, x in cells if inp[y][x] == 8)


def _erase(inp, pred, only=None):
    """Erase objects for which pred(marks, cells, all_counts) holds; only limits erased colors."""
    objs = _objects(inp)
    counts = [_marks(inp, o) for o in objs]
    res = [row[:] for row in inp]
    for o, n in zip(objs, counts):
        if pred(n, o, counts):
            for y, x in o:
                if only is None or inp[y][x] == only:
                    res[y][x] = 0
    return res


def threshold0(inp, out):
    return _erase(inp, lambda n, o, cs: n > 0)


def threshold2(inp, out):
    return _erase(inp, lambda n, o, cs: n > 2)


def inverted(inp, out):
    return _erase(inp, lambda n, o, cs: n <= 1)


def only_marks(inp, out):
    return _erase(inp, lambda n, o, cs: n > 1, only=8)


def only_bodies(inp, out):
    return _erase(inp, lambda n, o, cs: n > 1, only=1)


def most_marks_only(inp, out):
    return _erase(inp, lambda n, o, cs: n == max(cs))


def exactly_one_kept(inp, out):
    return _erase(inp, lambda n, o, cs: n != 1)


def above_mean(inp, out):
    return _erase(inp, lambda n, o, cs: n > sum(cs) / len(cs))


def even_marks(inp, out):
    return _erase(inp, lambda n, o, cs: n % 2 == 0)


def largest_area(inp, out):
    return _erase(inp, lambda n, o, cs: False) if False else _erase_largest(inp)


def _erase_largest(inp):
    objs = _objects(inp)
    big = max(len(o) for o in objs)
    res = [row[:] for row in inp]
    for o in objs:
        if len(o) == big:
            for y, x in o:
                res[y][x] = 0
    return res


def mark_groups(inp, out):
    # count 8-connected groups of marks instead of mark cells
    objs = _objects(inp)
    res = [row[:] for row in inp]
    for o in objs:
        mk = {(y, x) for y, x in o if inp[y][x] == 8}
        groups = 0
        seen = set()
        for p in mk:
            if p in seen:
                continue
            groups += 1
            st = [p]
            seen.add(p)
            while st:
                y, x = st.pop()
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        q = (y + dy, x + dx)
                        if q in mk and q not in seen:
                            seen.add(q)
                            st.append(q)
        if groups > 1:
            for y, x in o:
                res[y][x] = 0
    return res


def crop_kept(inp, out):
    pts = [(y, x) for y, row in enumerate(out) for x, v in enumerate(row) if v]
    if not pts:
        return None
    y0 = min(p[0] for p in pts); y1 = max(p[0] for p in pts)
    x0 = min(p[1] for p in pts); x1 = max(p[1] for p in pts)
    return [row[x0:x1 + 1] for row in out[y0:y1 + 1]]


ALTERNATIVES = [
    ("erase every object with at least one mark (keep only mark-free objects)", threshold0),
    ("erase only objects with more than 2 marks", threshold2),
    ("keep the crowded objects and erase the sparse ones (inverted condition)", inverted),
    ("erase only the mark cells of crowded objects, leaving the body", only_marks),
    ("erase only the body cells of crowded objects, leaving the marks", only_bodies),
    ("erase only the object with the most marks", most_marks_only),
    ("keep only objects with exactly one mark; erase mark-free ones too", exactly_one_kept),
    ("erase objects whose mark count is above the average across objects", above_mean),
    ("erase objects with an even number of marks", even_marks),
    ("erase the largest-area object(s) instead of testing marks", largest_area),
    ("count 8-connected groups of marks rather than mark cells", mark_groups),
    ("crop the true output to the bounding box of the kept objects", crop_kept),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/a934301b.json'))
    train = task['train']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
