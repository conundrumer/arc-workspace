import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r if v)
    # tile color: the color of the repeated 3x3 rings (most common nonzero)
    tc = cnt.most_common(1)[0][0]
    seen = set()
    comps = []
    for i in range(h):
        for j in range(w):
            if inp[i][j] == tc and (i, j) not in seen:
                st = [(i, j)]
                seen.add((i, j))
                cells = []
                while st:
                    a, b = st.pop()
                    cells.append((a, b))
                    for da in (-1, 0, 1):
                        for db in (-1, 0, 1):
                            c, d = a + da, b + db
                            if 0 <= c < h and 0 <= d < w and inp[c][d] == tc and (c, d) not in seen:
                                seen.add((c, d))
                                st.append((c, d))
                comps.append(cells)
    boxes = []
    for cells in comps:
        rs = [a for a, _ in cells]
        cs = [b for _, b in cells]
        boxes.append((min(rs), min(cs), max(rs), max(cs)))
    rows = sorted(set(b[0] for b in boxes))
    cols = sorted(set(b[1] for b in boxes))
    size = boxes[0][2] - boxes[0][0] + 1
    mc = [(i, j) for i in range(h) for j in range(w) if inp[i][j] and inp[i][j] != tc]
    r0 = min(i for i, _ in mc)
    c0 = min(j for _, j in mc)
    r1 = max(i for i, _ in mc)
    c1 = max(j for _, j in mc)
    mini = [inp[i][c0:c1 + 1] for i in range(r0, r1 + 1)]
    return tc, rows, cols, size, (r0, c0, r1, c1), mini


def _paint(base, r, c, size, color, ring=True, center=True):
    g = [row[:] for row in base]
    for a in range(size):
        for b in range(size):
            edge = a in (0, size - 1) or b in (0, size - 1)
            if (edge and ring) or (not edge and center):
                g[r + a][c + b] = color
    return g


def _render(inp, f, ring=True, center=False, base=None):
    tc, rows, cols, size, _, mini = _parse(inp)
    g = [row[:] for row in (base or inp)]
    for ri, r in enumerate(rows):
        for ci, c in enumerate(cols):
            col = f(ri, ci, mini, len(rows), len(cols))
            if col is None:
                continue
            g = _paint(g, r, c, size, col, ring, center)
    return g


def _std(inp):
    return _render(inp, lambda r, c, m, nr, nc: m[r % len(m)][c % len(m[0])])


def flip_cols(inp, out):
    return _render(inp, lambda r, c, m, nr, nc: m[r % len(m)][-1 - (c % len(m[0]))])


def flip_rows(inp, out):
    return _render(inp, lambda r, c, m, nr, nc: m[-1 - (r % len(m))][c % len(m[0])])


def transpose(inp, out):
    return _render(inp, lambda r, c, m, nr, nc: m[c % len(m)][r % len(m[0])])


def shift_col(inp, out):
    return _render(inp, lambda r, c, m, nr, nc: m[r % len(m)][(c + 1) % len(m[0])])


def shift_row(inp, out):
    return _render(inp, lambda r, c, m, nr, nc: m[(r + 1) % len(m)][c % len(m[0])])


def fill_centers(inp, out):
    tc, rows, cols, size, _, mini = _parse(inp)
    g = [row[:] for row in out]
    for ri, r in enumerate(rows):
        for ci, c in enumerate(cols):
            col = mini[ri % len(mini)][ci % len(mini[0])]
            for a in range(size):
                for b in range(size):
                    g[r + a][c + b] = col
    return g


def center_only(inp, out):
    tc, rows, cols, size, _, mini = _parse(inp)
    g = [row[:] for row in inp]
    for ri, r in enumerate(rows):
        for ci, c in enumerate(cols):
            col = mini[ri % len(mini)][ci % len(mini[0])]
            for a in range(1, size - 1):
                for b in range(1, size - 1):
                    g[r + a][c + b] = col
    return g


def last_row_unpainted(inp, out):
    tc, rows, cols, size, _, mini = _parse(inp)
    g = [row[:] for row in out]
    r = rows[-1]
    for c in cols:
        for a in range(size):
            for b in range(size):
                if out[r + a][c + b]:
                    g[r + a][c + b] = tc
    return g


def erase_mini(inp, out):
    _, _, _, _, (r0, c0, r1, c1), _ = _parse(inp)
    g = [row[:] for row in out]
    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            g[i][j] = 0
    return g


def majority_color(inp, out):
    mini = _parse(inp)[5]
    col = Counter(v for r in mini for v in r).most_common(1)[0][0]
    return _render(inp, lambda r, c, m, nr, nc: col)


def row_stripes(inp, out):
    return _render(inp, lambda r, c, m, nr, nc: m[r % len(m)][0])


def first_row_only(inp, out):
    # colour only the first tile row; others stay the template colour
    return _render(inp, lambda r, c, m, nr, nc: m[0][c % len(m[0])] if r == 0 else None)


ALTERNATIVES = [
    ("miniature mirrored left-right before mapping to tiles", flip_cols),
    ("miniature mirrored top-bottom before mapping to tiles", flip_rows),
    ("miniature transposed before mapping to tiles", transpose),
    ("tile colors taken one miniature column to the right (off by one, wrapping)", shift_col),
    ("tile colors taken one miniature row below (off by one, wrapping)", shift_row),
    ("tile boxes filled solid with the color, including the hollow cells", fill_centers),
    ("only the tile centers are colored; tile rings keep the template color", center_only),
    ("last tile row left in the template color", last_row_unpainted),
    ("miniature erased from the output", erase_mini),
    ("every tile takes the most common miniature color", majority_color),
    ("every tile in a row takes the color of the miniature's first column", row_stripes),
    ("only the first tile row is colored", first_row_only),
]


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/33b52de3.json').read_text())
    pairs = task['train']
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is None:
                continue
            rect = all(len(r) == len(g[0]) for r in g)
            vals = all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            if rect and vals and g != p['output']:
                ok += 1
        print(f'{ok}/{len(pairs)}  {desc}')
