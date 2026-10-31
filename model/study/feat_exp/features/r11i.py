"""Round 11, explorer I: worst gold points.

Position cells are read as (top, left) of the margins [top, bottom, left, right]. A cell whose extent is resolved and
equals the train input's size is a cell of that grid, whatever the column's frame tag.
"""
import collections as C

from featlib import feature


def _train_list(p):
    tr = p.train
    return tr['train'] if isinstance(tr, dict) and 'train' in tr else tr


def _entries(p):
    """First model of each (assignment, train) context: (train index, rows), a row being a list of cells."""
    seen = {}
    for e in p.x.entries:
        seen.setdefault((e['assignment'], e['train']), (e['train'], e['rows']))
    return list(seen.values())


def _open_cols(p):
    """Position columns with an empty frame tag (the tagged columns are read by the cell features of earlier rounds)."""
    return [i for i, f in enumerate(p.x.fields) if f['type'] == 'Position' and not f.get('frame', '')]


def _open_cells(p):
    """For each context with a train grid: (train index, grid, {column index -> set of distinct (top, left) cells of
    that grid}), over the Position columns with an empty tag. A cell counts when its extent is resolved, equals the
    grid's size and its margins fit the grid."""
    train = _train_list(p)
    cols = _open_cols(p)
    out = []
    if not cols:
        return out
    for t, rows in _entries(p):
        if t >= len(train):
            continue
        grid = train[t]['input']
        h, w = len(grid), len(grid[0])
        per = {}
        for i in cols:
            cells = set()
            for r in rows:
                c = r[i]
                if c.get('extent_status') != 'resolved' or tuple(c.get('extent') or ()) != (h, w):
                    continue
                v = c['value']
                if len(v) == 4 and 0 <= v[0] < h and 0 <= v[2] < w and v[0] + v[1] == h - 1 and v[2] + v[3] == w - 1:
                    cells.add((v[0], v[2]))
            per[i] = cells
        out.append((t, grid, per))
    return out


@feature
def i1_open_cells(p):
    """I1: X's Position cells with an empty frame tag, on grids of the train input's size, against the cells where the
    train output differs from the train input (same-size examples). `precision`: share of the distinct cells (union
    over columns) that changed; `coverage`: share of the changed cells that some column holds; `bg`: share of the cells
    on the input's most common colour; `cover`: mean share of the grid that the cells fill. None without such a column,
    without a cell, or at a Det point.

    Needs: X, train grids. Monotone: no.
    """
    if p.kind == 'Det':
        return None
    info = _open_cells(p)
    if not info:
        return None
    train = _train_list(p)
    hit = tot = changed = covered = on_bg = 0
    cover = []
    seen = False
    for t, grid, per in info:
        union = set().union(*per.values()) if per else set()
        if not union:
            continue
        seen = True
        count = C.Counter(v for row in grid for v in row)
        back = count.most_common(1)[0][0]
        on_bg += sum(grid[r][c] == back for r, c in union)
        tot += len(union)
        cover.append(len(union) / (len(grid) * len(grid[0])))
        out = train[t]['output']
        if len(out) != len(grid) or len(out[0]) != len(grid[0]):
            continue
        diff = {(r, c) for r in range(len(grid)) for c in range(len(grid[0])) if grid[r][c] != out[r][c]}
        hit += len(union & diff)
        changed += len(diff)
        covered += len(union & diff)
    if not seen:
        return None
    res = {'bg': on_bg / tot, 'cover': sum(cover) / len(cover)}
    if changed:
        res.update(precision=hit / tot, coverage=covered / changed)
    return res
