import json
from pathlib import Path

N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
N8 = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]


def _bg(g):
    cnt = {}
    for r in g:
        for v in r:
            cnt[v] = cnt.get(v, 0) + 1
    return max(cnt, key=cnt.get)


def _comps(g, bg, nb=N4):
    h, w = len(g), len(g[0])
    seen, comps = set(), []
    for i in range(h):
        for j in range(w):
            if g[i][j] != bg and (i, j) not in seen:
                st, c = [(i, j)], []
                seen.add((i, j))
                while st:
                    a, b = st.pop()
                    c.append((a, b))
                    for da, db in nb:
                        x, y = a + da, b + db
                        if 0 <= x < h and 0 <= y < w and g[x][y] != bg and (x, y) not in seen:
                            seen.add((x, y))
                            st.append((x, y))
                comps.append(c)
    return comps


def _blank_except(g, bg, cells):
    o = [[bg] * len(g[0]) for _ in g]
    for a, b in cells:
        o[a][b] = g[a][b]
    return o


def keep_touching(inp, out):
    """Keep every ink cell that has an ink 4-neighbour, so protrusions stay."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    cells = [(i, j) for i in range(h) for j in range(w) if inp[i][j] != bg and
             any(0 <= i + a < h and 0 <= j + b < w and inp[i + a][j + b] != bg for a, b in N4)]
    return _blank_except(inp, bg, cells)


def keep_touching8(inp, out):
    """Keep every ink cell with an ink neighbour including diagonals."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    cells = [(i, j) for i in range(h) for j in range(w) if inp[i][j] != bg and
             any(0 <= i + a < h and 0 <= j + b < w and inp[i + a][j + b] != bg for a, b in N8)]
    return _blank_except(inp, bg, cells)


def invert_remove(inp, out):
    """Erase the solid blocks and keep the scattered pixels."""
    bg = _bg(inp)
    return [[bg if out[i][j] != bg else inp[i][j] for j in range(len(inp[0]))] for i in range(len(inp))]


def largest_only(inp, out):
    """Keep only the largest block."""
    bg = _bg(out)
    cs = _comps(out, bg)
    if not cs:
        return None
    big = max(cs, key=len)
    return _blank_except(out, bg, big)


def smallest_only(inp, out):
    """Keep only the smallest block."""
    bg = _bg(out)
    cs = _comps(out, bg)
    if not cs:
        return None
    return _blank_except(out, bg, min(cs, key=len))


def drop_first_block(inp, out):
    """Miss the first block in reading order."""
    bg = _bg(out)
    cs = _comps(out, bg)
    if not cs:
        return None
    first = min(cs, key=lambda c: min(c))
    return [[bg if (i, j) in set(first) else out[i][j] for j in range(len(out[0]))] for i in range(len(out))]


def wrong_color(inp, out):
    """Right cells, wrong color."""
    bg = _bg(out)
    new = 8 if any(v == 1 for r in out for v in r) else 1
    return [[new if v != bg else v for v in r] for r in out]


def dilate(inp, out):
    """Blocks grown by one cell on every side."""
    bg = _bg(out)
    h, w = len(out), len(out[0])
    o = [r[:] for r in out]
    ink = [v for r in out for v in r if v != bg][0]
    for i in range(h):
        for j in range(w):
            if out[i][j] != bg:
                for a, b in N4:
                    x, y = i + a, j + b
                    if 0 <= x < h and 0 <= y < w:
                        o[x][y] = ink
    return o


def erode(inp, out):
    """Only the interior of each block, border cells lost."""
    bg = _bg(out)
    h, w = len(out), len(out[0])
    o = [[bg] * w for _ in range(h)]
    for i in range(h):
        for j in range(w):
            if out[i][j] != bg and all(0 <= i + a < h and 0 <= j + b < w and out[i + a][j + b] != bg for a, b in N4):
                o[i][j] = out[i][j]
    return o


def drop_last_row(inp, out):
    """Off-by-one crop: last row missing."""
    return [r[:] for r in out[:-1]]


def mirrored(inp, out):
    """Blocks placed at horizontally mirrored positions."""
    return [r[::-1] for r in out]


def big_components_4(inp, out):
    """Keep every 4-connected ink component of 4 or more cells, protrusions included."""
    bg = _bg(inp)
    cells = [c for comp in _comps(inp, bg) if len(comp) >= 4 for c in comp]
    return _blank_except(inp, bg, cells)


ALTERNATIVES = [
    ("keep ink cells with a 4-neighbour ink cell, so attached protrusions stay", keep_touching),
    ("keep ink cells with an 8-neighbour ink cell, so diagonal noise also stays", keep_touching8),
    ("erase the solid blocks and keep the scattered pixels", invert_remove),
    ("keep only the largest block", largest_only),
    ("keep only the smallest block", smallest_only),
    ("miss the first block in reading order", drop_first_block),
    ("keep the blocks but paint them in another color", wrong_color),
    ("grow each block by one cell on every side", dilate),
    ("keep only the interior of each block, border lost", erode),
    ("crop off the last row", drop_last_row),
    ("blocks at horizontally mirrored positions", mirrored),
    ("keep every 4-connected ink component of 4 or more cells, protrusions included", big_components_4),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/7f4411dc.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings', len(pairs), 'pairs')
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(n, desc)
