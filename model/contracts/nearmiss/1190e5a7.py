import json
from pathlib import Path


def _analyze(inp):
    h, w = len(inp), len(inp[0])
    dcols = set()
    for r in inp:
        if len(set(r)) == 1:
            dcols.add(r[0])
    for c in range(w):
        col = {inp[r][c] for r in range(h)}
        if len(col) == 1:
            dcols.add(inp[0][c])
    div = next(iter(dcols)) if dcols else None
    row_div = [len(set(r)) == 1 and r[0] in dcols for r in inp]
    col_div = [len({inp[r][c] for r in range(h)}) == 1 and inp[0][c] in dcols
               for c in range(w)]

    def runs(flags):
        res, cur = [], []
        for i, f in enumerate(flags):
            if f:
                if cur:
                    res.append(cur)
                cur = []
            else:
                cur.append(i)
        if cur:
            res.append(cur)
        return res

    rb, cb = runs(row_div), runs(col_div)
    cell = inp[rb[0][0]][cb[0][0]]
    return div, rb, cb, cell, row_div, col_div


def _fill(h, w, v):
    return [[v] * w for _ in range(h)]


def count_dividers(inp, out):
    div, rb, cb, cell, rd, cd = _analyze(inp)
    return _fill(sum(rd), sum(cd), cell)


def bands_minus_one(inp, out):
    div, rb, cb, cell, rd, cd = _analyze(inp)
    return _fill(len(rb) - 1, len(cb) - 1, cell)


def bands_plus_one(inp, out):
    div, rb, cb, cell, rd, cd = _analyze(inp)
    return _fill(len(rb) + 1, len(cb) + 1, cell)


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def divider_color_fill(inp, out):
    div, rb, cb, cell, rd, cd = _analyze(inp)
    return _fill(len(out), len(out[0]), div)


def square_row_bands(inp, out):
    div, rb, cb, cell, rd, cd = _analyze(inp)
    return _fill(len(rb), len(rb), cell)


def square_col_bands(inp, out):
    div, rb, cb, cell, rd, cd = _analyze(inp)
    return _fill(len(cb), len(cb), cell)


def corner_cell_divider(inp, out):
    div, rb, cb, cell, rd, cd = _analyze(inp)
    g = [r[:] for r in out]
    g[-1][-1] = div
    return g


def drop_last_row_band(inp, out):
    return [r[:] for r in out[:-1]]


def drop_thin_bands(inp, out):
    div, rb, cb, cell, rd, cd = _analyze(inp)
    nr = len([b for b in rb if len(b) > 1])
    nc = len([b for b in cb if len(b) > 1])
    if nr == 0 or nc == 0:
        return None
    return _fill(nr, nc, cell)


def no_collapse(inp, out):
    div, rb, cb, cell, rd, cd = _analyze(inp)
    return _fill(sum(len(b) for b in rb), sum(len(b) for b in cb), cell)


def collapse_rows_only(inp, out):
    div, rb, cb, cell, rd, cd = _analyze(inp)
    return [inp[b[0]][:] for b in rb]


def single_cell(inp, out):
    div, rb, cb, cell, rd, cd = _analyze(inp)
    return [[cell]]


ALTERNATIVES = [
    ("size from divider line counts instead of band counts", count_dividers),
    ("one band too few on each axis", bands_minus_one),
    ("one band too many on each axis", bands_plus_one),
    ("output transposed (rows and columns swapped)", transposed),
    ("output filled with the divider color", divider_color_fill),
    ("square output sized by the row band count", square_row_bands),
    ("square output sized by the column band count", square_col_bands),
    ("last cell takes the divider color", corner_cell_divider),
    ("last row band dropped", drop_last_row_band),
    ("bands one line wide are ignored", drop_thin_bands),
    ("dividers removed but bands not collapsed to one cell", no_collapse),
    ("only row bands collapsed; columns kept at input width", collapse_rows_only),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not isinstance(g[0], list) or not g[0]:
        return False
    if any(not isinstance(r, list) or len(r) != len(g[0]) for r in g):
        return False
    if any(type(v) is not int or not 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/1190e5a7.json').read_text())
    train = task['train']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(f'{n}/{len(train)}  {desc}')
