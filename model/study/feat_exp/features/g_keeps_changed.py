"""G9 keeps_changed: X keeps the cells the task changes.

The cells the task changes are the cells where the train output differs from the train input, on the examples whose
two grids have one size. X's cell columns are the Position and Box columns whose frame tag is `input` or `output`:
a Position holds its cell, a Box holds the cells it covers. A column of any other frame tag is not read in the train
grids. Each context counts the first model of X's table; a context that X has with no row counts as empty.
"""
import numpy as np

from featlib import feature


def _contexts(table):
    """{(assignment, example): rows of the first model, a row being a tuple of decoded cells}; a context the table
    has with no row is empty."""
    ex = table.examples()
    if any(c.type == 'Example' for c in table.columns()):
        return {k: m[0] for k, m in ex.items() if m}
    keys = {(e['assignment'], e['train']) for e in table.entries}
    return {k: (ex[k][0] if ex.get(k) else []) for k in keys}


def _cell_columns(x):
    return [c for c in x.columns() if c.type in ('Position', 'Box') and c.frame_kind in ('input', 'output')]


def _mask(rows, col, size):
    """The cells of a grid of that size that a Position or Box column holds (a value off the grid is left out)."""
    h, w = size
    out = np.zeros((h, w), dtype=bool)
    for r in rows:
        m = r[col.index]
        if not hasattr(m, 'margins'):
            continue
        t, b, l, rt = m.margins
        if min(m.margins) < 0:
            continue
        if col.type == 'Position':
            if t + b == h - 1 and l + rt == w - 1:
                out[t, l] = True
        elif t + b <= h - 1 and l + rt <= w - 1:
            out[t:h - b, l:w - rt] = True
    return out


@feature
def g9_keeps_changed(p):
    """G9 keeps_changed: the share of the changed cells that X's cell columns hold.

    recall: the share of the changed cells that the union of X's Position and Box columns (frame tag input or output) holds, summed over contexts.
    recall_max: the same for the one column that holds the most.
    prec: the share of the union's cells that are changed cells.
    paint: the share of the changed cells that a Position column and a Color column of X together paint with the output's color (the best pair).
    None without such a column or without a changed cell.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    Needs: partial. Monotone: partly (`recall` and `paint` only fall under atoms that make no new cell column; a new column can raise them; `prec` is not monotone).
    """
    if p.kind == 'Det':
        return None
    x = p.x
    cols = _cell_columns(x)
    if not cols:
        return None
    colors = [c for c in x.columns() if c.type == 'Color']
    exs = p.examples()
    need = hit_u = union_n = 0
    hit = {c.index: 0 for c in cols}
    painted = {}
    for (_, k), rows in _contexts(x).items():
        if k >= len(exs) or not exs[k].same_size:
            continue
        ex = exs[k]
        changed = ex.input.array != ex.output.array
        n = int(changed.sum())
        if not n:
            continue
        need += n
        union = np.zeros(changed.shape, dtype=bool)
        for c in cols:
            m = _mask(rows, c, ex.input.size)
            hit[c.index] += int((m & changed).sum())
            union |= m
        hit_u += int((union & changed).sum())
        union_n += int(union.sum())
        out = ex.output.array
        for c in cols:
            if c.type != 'Position':
                continue
            for col in colors:
                got = np.zeros(changed.shape, dtype=bool)
                for r in rows:
                    m = r[c.index]
                    if not hasattr(m, 'margins'):
                        continue
                    t, b, l, rt = m.margins
                    if min(m.margins) >= 0 and t + b == ex.input.height - 1 and l + rt == ex.input.width - 1 \
                            and out[t, l] == r[col.index]:
                        got[t, l] = True
                painted[c.index, col.index] = painted.get((c.index, col.index), 0) + int((got & changed).sum())
    if not need:
        return None
    res = {'recall': hit_u / need, 'recall_max': max(hit.values()) / need,
           'prec': hit_u / union_n if union_n else 0.0}
    if painted:
        res['paint'] = max(painted.values()) / need
    return res

