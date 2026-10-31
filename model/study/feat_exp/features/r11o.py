"""Round 11, explorer o: Det points, gold against the draws that the score keeps.

At a Det point the output-reading families (M3, M5, C2, C3, L5 and others) return None, because X there is the task-level
body table without its Example column. These features read X as a task level table: a cell is judged against every train
grid of its extent, a color against the union of the train grids.
"""
import collections as C

from featlib import feature, decode

POSITION_FRAMES = ('input', 'output')


def _train_list(p):
    tr = p.train
    return tr['train'] if isinstance(tr, dict) and 'train' in tr else tr


def _background(grid):
    """The most common color of a grid, the smallest on a tie."""
    count = C.Counter(v for row in grid for v in row)
    top = max(count.values())
    return min(v for v, k in count.items() if k == top)


def _frame_cells(p, frame):
    """{column index: set of (top, left, size)} of the distinct Position cells of the columns with that frame tag."""
    x = p.x
    cols = list(x.columns())
    out = {}
    for i, col in enumerate(cols):
        if col.type != 'Position' or col.frame != frame:
            continue
        cells = set()
        for e in x.entries:
            for row in e['rows']:
                m = decode(row[i], col, x)
                if hasattr(m, 'margins'):
                    cells.add((m.top, m.left, m.size))
        if cells:
            out[i] = cells
    return out


@feature
def o1_never_fg(p):
    """O1: at a Det point, over the Position columns with frame tag input or output (distinct cells, all rows): never_fg,
    the share of a column's cells that lie on the most common color (or off the grid) in every train grid of that frame
    and of the cell's extent (all grids where the extent is unresolved), for the column with the largest share; cover,
    that column's distinct cells over the mean area of those grids, at most 1; chg_any, for input columns on the
    examples whose input and output have one size, the share of cells that the output changes in at least one such
    example (the column with the largest share). None at other points and without such a column."""
    if p.kind != 'Det':
        return None
    train = _train_list(p)
    if not train:
        return None
    best, chg_best = None, None
    for frame in POSITION_FRAMES:
        grids = [t[frame] for t in train]
        backs = {id(g): _background(g) for g in grids}
        for cells in _frame_cells(p, frame).values():
            n = never = chg_n = chg_any = 0
            by_size = {}
            for top, left, size in cells:
                if size not in by_size:
                    cand = [g for g in grids if size is None or (len(g), len(g[0])) == tuple(size)]
                    same = []
                    if frame == 'input':
                        same = [t for t in train if len(t['input']) == len(t['output'])
                                and len(t['input'][0]) == len(t['output'][0])
                                and (size is None or (len(t['input']), len(t['input'][0])) == tuple(size))]
                    by_size[size] = (cand, same)
                cand, same = by_size[size]
                if not cand:
                    continue
                n += 1
                seen = any(0 <= top < len(g) and 0 <= left < len(g[0]) and g[top][left] != backs[id(g)] for g in cand)
                never += not seen
                if same:
                    chg_n += 1
                    chg_any += any(0 <= top < len(t['input']) and 0 <= left < len(t['input'][0])
                                   and t['input'][top][left] != t['output'][top][left] for t in same)
            if not n:
                continue
            area = sum(len(g) * len(g[0]) for g in grids) / len(grids)
            row = {'never_fg': never / n, 'cover': min(1.0, len(cells) / area)}
            if best is None or row['never_fg'] > best['never_fg']:
                best = row
            if chg_n and (chg_best is None or chg_any / chg_n > chg_best):
                chg_best = chg_any / chg_n
    if best is None:
        return None
    if chg_best is not None:
        best['chg_any'] = chg_best
    return best


@feature
def o3_new_colors(p):
    """O3: at a Det point, the share of the colors that the train outputs hold and no train input holds that X's Color
    columns hold (new_cov), over all rows. None at other points, without a Color column or without such a color."""
    if p.kind != 'Det':
        return None
    train = _train_list(p)
    if not train:
        return None
    x = p.x
    cols = [i for i, c in enumerate(x.columns()) if c.type == 'Color']
    if not cols:
        return None
    ins = {v for t in train for row in t['input'] for v in row}
    outs = {v for t in train for row in t['output'] for v in row}
    new = outs - ins
    if not new:
        return None
    held = {row[i]['value'][0] for e in x.entries for row in e['rows'] for i in cols if row[i].get('value')}
    return {'new_cov': len(held & new) / len(new)}
