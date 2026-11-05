import json
from collections import Counter
from pathlib import Path


def parse(inp):
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    shape_col = max((c for c in cnt if c != bg), key=lambda c: cnt[c])
    shape = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == shape_col]
    marks = [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row)
             if v not in (bg, shape_col)]
    return bg, shape_col, shape, marks


def anchor_of(mark, shape):
    """Return (axis, anchor cell); axis 'h' when mark and anchor share a row."""
    mr, mc, _ = mark
    row = [s for s in shape if s[0] == mr]
    if row:
        return 'h', row[0]
    col = [s for s in shape if s[1] == mc]
    if col:
        return 'v', col[0]
    return None, None


def render(inp, flip=None, color=None, shift=0, skip_line=False, skip_axes=(),
           bbox_anchor=False, grid_center=False, rot=False, base=None):
    H, W = len(inp), len(inp[0])
    bg, scol, shape, marks = parse(inp)
    g = [row[:] for row in (base if base is not None else inp)]
    for mark in marks:
        mr, mc, mcol = mark
        axis, anc = anchor_of(mark, shape)
        if axis is None or axis in skip_axes:
            continue
        ax = flip(axis) if flip else axis
        if bbox_anchor:
            if axis == 'h':
                cs = [c for _, c in shape]
                anc = (anc[0], min(cs, key=lambda c: abs(c - mc)))
            else:
                rs = [r for r, _ in shape]
                anc = (min(rs, key=lambda r: abs(r - mr)), anc[1])
        sgn_r = 1 if mr > anc[0] else -1
        sgn_c = 1 if mc > anc[1] else -1
        for (r, c) in shape:
            dr, dc = r - anc[0], c - anc[1]
            if skip_line:
                if axis == 'h':
                    far = max(abs(cc - anc[1]) for _, cc in shape)
                    if abs(dc) == far:
                        continue
                else:
                    far = max(abs(rr - anc[0]) for rr, _ in shape)
                    if abs(dr) == far:
                        continue
            if rot:
                nr, nc = mr - dr, mc - dc
            elif ax == 'h':
                nr, nc = mr + dr, mc - dc
            elif ax == 'v':
                nr, nc = mr - dr, mc + dc
            else:
                nr, nc = mr + dr, mc + dc
            if grid_center:
                if axis == 'h':
                    nr, nc = r, W - 1 - c
                else:
                    nr, nc = H - 1 - r, c
            if axis == 'h':
                nc += shift * sgn_c * -1
            else:
                nr += shift * sgn_r * -1
            if 0 <= nr < H and 0 <= nc < W:
                g[nr][nc] = scol if color == 'shape' else mcol
    return g


def correct(inp):
    return render(inp)


def no_flip(inp, out):
    return render(inp, flip=lambda a: 'n')


def swapped_axis(inp, out):
    return render(inp, flip=lambda a: 'v' if a == 'h' else 'h')


def shape_color(inp, out):
    return render(inp, color='shape')


def rot180(inp, out):
    return render(inp, rot=True)


def shifted_anchor(inp, out):
    return render(inp, shift=1)


def ignore_vertical(inp, out):
    return render(inp, skip_axes=('v',))


def skip_far_edge(inp, out):
    return render(inp, skip_line=True)


def erase_original(inp, out):
    bg, scol, shape, marks = parse(inp)
    g = [row[:] for row in out]
    for r, c in shape:
        g[r][c] = bg
    return g


def grid_center_mirror(inp, out):
    return render(inp, grid_center=True)


def bbox_edge_anchor(inp, out):
    return render(inp, bbox_anchor=True)


def recolor_original(inp, out):
    bg, scol, shape, marks = parse(inp)
    g = [row[:] for row in out]
    for r, c in shape:
        g[r][c] = marks[0][2]
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("copy keeps the shape's orientation (translated to the mark, no mirroring)", no_flip),
    ("mirror axis swapped: row-aligned marks flip vertically, column-aligned marks flip horizontally", swapped_axis),
    ("copy is drawn in the shape's color instead of the mark's color", shape_color),
    ("copy is the shape rotated 180 degrees about the anchor cell", rot180),
    ("copy placed one cell farther from the shape than the anchor cell implies", shifted_anchor),
    ("only row-aligned marks (horizontal mirror) are handled; column-aligned marks are ignored", ignore_vertical),
    ("copy leaves out the shape's outermost column (or row) farthest from the anchor", skip_far_edge),
    ("original shape is erased, leaving only the mirrored copies", erase_original),
    ("shape mirrored about the grid's center line instead of about the mark", grid_center_mirror),
    ("anchor taken as the shape's bounding-box edge nearest the mark, not the cell on the mark's line", bbox_edge_anchor),
    ("original shape is recolored with the first mark's color as well", recolor_original),
    ("output equals the input (no copy made)", unchanged),
]


def valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/963f59bc.json'))
    train = task['train']
    assert all(correct(p['input']) == p['output'] for p in train), 'reference rule mismatch'
    print('pairs:', len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p['input'], p['output'])
            except Exception as e:
                print('  error', e)
                g = None
            n += valid(g, p['output'])
        print(f'{n}/{len(train)}  {desc}')
