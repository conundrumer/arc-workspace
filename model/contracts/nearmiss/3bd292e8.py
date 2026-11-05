import json
from pathlib import Path


def _wall(inp):
    counts = {}
    for r in inp:
        for v in r:
            counts[v] = counts.get(v, 0) + 1
    return min(counts, key=lambda c: counts[c])


def _components(inp, diag=False):
    h, w = len(inp), len(inp[0])
    wall = _wall(inp)
    comp = [[-1] * w for _ in range(h)]
    sizes = []
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diag:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    for i in range(h):
        for j in range(w):
            if inp[i][j] == wall or comp[i][j] != -1:
                continue
            k = len(sizes)
            comp[i][j] = k
            stack = [(i, j)]
            n = 0
            while stack:
                a, b = stack.pop()
                n += 1
                for da, db in steps:
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and inp[x][y] != wall and comp[x][y] == -1:
                        comp[x][y] = k
                        stack.append((x, y))
            sizes.append(n)
    return comp, sizes


def _paint(inp, pick, diag=False):
    wall = _wall(inp)
    comp, sizes = _components(inp, diag)
    return [[wall if inp[i][j] == wall else pick(comp[i][j], sizes, comp, i, j)
             for j in range(len(inp[0]))] for i in range(len(inp))]


def swap_colors(inp, out):
    return [[5 if v == 3 else 3 if v == 5 else v for v in r] for r in out]


def one_color_3(inp, out):
    return [[3 if v == 5 else v for v in r] for r in out]


def one_color_5(inp, out):
    return [[5 if v == 3 else v for v in r] for r in out]


def only_smallest_region(inp, out):
    return _paint(inp, lambda k, s, c, i, j: 3 if s[k] == min(s) else 5)


def only_largest_region_other(inp, out):
    return _paint(inp, lambda k, s, c, i, j: 5 if s[k] == max(s) else 3)


def eight_connected(inp, out):
    return _paint(inp, lambda k, s, c, i, j: 3 if s[k] == min(s) else 5, diag=True)


def scan_parity(inp, out):
    return _paint(inp, lambda k, s, c, i, j: 3 if k % 2 == 0 else 5)


def top_left_side(inp, out):
    wall = _wall(inp)
    comp, sizes = _components(inp)
    first = next(comp[i][j] for i in range(len(inp)) for j in range(len(inp[0])) if comp[i][j] != -1)
    return _paint(inp, lambda k, s, c, i, j: 3 if k == first else 5)


def left_half_3(inp, out):
    w = len(inp[0])
    return [[v if v == _wall(inp) else (3 if j < w // 2 else 5) for j, v in enumerate(r)]
            for r in inp]


def wall_recolored(inp, out):
    wall = _wall(inp)
    return [[3 if inp[i][j] == wall else v for j, v in enumerate(r)] for i, r in enumerate(out)]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def crop_wall_bbox(inp, out):
    wall = _wall(inp)
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == wall]
    i0 = min(a for a, _ in cells)
    i1 = max(a for a, _ in cells)
    j0 = min(b for _, b in cells)
    j1 = max(b for _, b in cells)
    return [r[j0:j1 + 1] for r in out[i0:i1 + 1]]


def input_unchanged(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("side colors swapped: smallest region's side gets 5, other side gets 3", swap_colors),
    ("side distinction missed: all non-wall cells get 3", one_color_3),
    ("side distinction missed: all non-wall cells get 5", one_color_5),
    ("only the single smallest region gets 3, every other region gets 5", only_smallest_region),
    ("largest region gets 5, every other region gets 3", only_largest_region_other),
    ("regions found with 8-connectivity; smallest region gets 3, others 5", eight_connected),
    ("regions colored alternately 3/5 in scan order", scan_parity),
    ("region holding the first non-wall cell in scan order gets 3, others 5", top_left_side),
    ("columns left of the middle get 3, the rest 5, wall kept", left_half_3),
    ("wall cells recolored to 3 as well", wall_recolored),
    ("output transposed", transposed),
    ("input returned unchanged", input_unchanged),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/3bd292e8.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(n, desc)
