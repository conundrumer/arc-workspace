"""G11 foreground: X's cells against the input's foreground.

The foreground of a train input is its cells off its most common color (the smallest color on a tie). X's cells are
those of its Position columns whose frame tag is `input`; a Position column of any other frame tag is not read in the
train grids. Each context counts the first model of X's table; a context that X has with no row counts as empty.
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


@feature
def g11_foreground(p):
    """G11 foreground: how X's input-frame Position cells lie on the input's foreground.

    recall: the share of the input's foreground cells that the column holds; prec: the share of the column's distinct cells that are foreground; both averaged over the contexts whose input has a foreground cell; the column with the largest recall, then prec.
    exact: 1 when that column has recall and prec 1 in every such context.
    cover_max: over columns, the largest mean share of the grid's cells that a column holds.
    None without an input-frame Position column or a context with a foreground cell.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    Needs: partial. Monotone: partly (`recall` and `cover_max` only fall under atoms that make no new Position column, a new column can raise them; `prec` and `exact` are not monotone).
    """
    if p.kind == 'Det':
        return None
    x = p.x
    cols = [c for c in x.columns() if c.type == 'Position' and c.frame_kind == 'input']
    if not cols:
        return None
    exs = p.examples()
    ctxs = [(exs[k].input, rows) for (_, k), rows in _contexts(x).items() if k < len(exs)]
    best = None
    covers = []
    for col in cols:
        rec = prec = cover = 0.0
        exact = 1
        n = n_cover = 0
        for grid, rows in ctxs:
            h, w = grid.size
            held = set()
            for r in rows:
                m = r[col.index]
                if hasattr(m, 'margins') and min(m.margins) >= 0 and m.top + m.bottom == h - 1 \
                        and m.left + m.right == w - 1:
                    held.add((m.top, m.left))
            cover += len(held) / (h * w)
            n_cover += 1
            back = min(grid.most_common())
            fg = {(r, q) for r in range(h) for q in range(w) if grid[r, q] != back}
            if not fg:
                continue
            on = len(held & fg)
            r_, p_ = on / len(fg), (on / len(held) if held else 0.0)
            rec += r_
            prec += p_
            exact &= r_ == 1.0 and p_ == 1.0
            n += 1
        if n_cover:
            covers.append(cover / n_cover)
        if n:
            res = {'recall': rec / n, 'prec': prec / n, 'exact': exact}
            if best is None or (res['recall'], res['prec']) > (best['recall'], best['prec']):
                best = res
    if best is None:
        return None
    best['cover_max'] = max(covers)
    return best
