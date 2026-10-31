"""G10 paint: X paints the right colour.

X paints a cell when a row holds a Position column (frame tag `input` or `output`, read in the train grid of that
tag) and a Color column. A Position column of any other frame tag is not read in the train grids. Each context
counts the first model of X's table; a context that X has with no row counts as empty.
"""
import collections as C

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


def _cell(m, size):
    """The (top, left) cell of a Position on a grid of that size, or None."""
    if not hasattr(m, 'margins'):
        return None
    t, b, l, r = m.margins
    h, w = size
    return (t, l) if min(m.margins) >= 0 and t + b == h - 1 and l + r == w - 1 else False


def _paint(p, ctxs, pos, col):
    """Counts for one (Position column, Color column) pair, summed over contexts, or None where no example counts.
    A Position column with tag `input` counts on examples whose grids have one size; one with tag `output` counts
    on the changed cells of such an example, else on all output cells."""
    exs = p.examples()
    c = C.Counter()
    for (_, k), rows in ctxs.items():
        if k >= len(exs):
            continue
        ex = exs[k]
        if pos.frame_kind == 'input' and not ex.same_size:
            continue
        gout = ex.output
        h, w = gout.size
        todo = ex.changed() if ex.same_size else {(r, q) for r in range(h) for q in range(w)}
        if not todo:
            continue
        c['seen'] += 1
        hit, cells, colors = set(), set(), {}
        for row in rows:
            cell = _cell(row[pos.index], gout.size)
            if cell is None:
                continue
            c['rows'] += 1
            if cell is False:
                c['wrong'] += 1
                continue
            ok = gout[cell] == row[col.index]
            cells.add(cell)
            colors.setdefault(cell, set()).add(row[col.index])
            c['wrong'] += not ok
            if cell in todo:
                c['ch_rows'] += 1
                c['ch_right'] += ok
            if ok:
                hit.add(cell)
        c['need'] += len(todo)
        c['hit'] += len(hit & todo)
        c['cells'] += h * w
        c['covered'] += len(cells)
        c['right_cells'] += len(hit)
        c['conflict'] += sum(len(v) > 1 for v in colors.values())
    return c if c['seen'] else None


@feature
def g10_paint(p):
    """G10 paint: the share of X's (cell, color) rows that agree with the train output.

    For the pair of a Position column (frame tag input or output) and a Color column of X with the highest recall of the cells to produce (the changed cells; for a tag output on a pair of grids of two sizes, all output cells), then the lowest `wrong`, then the larger counts (so that columns tied on both give one result in any column order):
    wrong: the share of X's rows whose cell is off the grid or whose color is not the output's color there.
    conflict: the share of the covered cells that X paints with two or more colors.
    prec_changed: the share of X's rows on a cell to produce that have the output's color.
    cover: the share of the grid's cells with a row; right_cover: the share with a row of the output's color.
    modal, novel: for the Position column with tag input that has the most common output color under its cells, on examples with one grid size: the share of its distinct cells whose output color is that color (modal), and the share whose output color does not occur in that example's input (novel).
    disp: over X's rows with a Position cell (tag input) and an Offset cell on examples with one grid size, the share where the input color at the cell equals the output color at the cell moved by the offset.
    None where a key has no such columns; the feature is None if no key applies.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    Needs: partial. Monotone: no (a filter can remove the wrong rows).
    """
    if p.kind == 'Det':
        return None
    x = p.x
    cols = x.columns()
    poss = [c for c in cols if c.type == 'Position' and c.frame_kind in ('input', 'output')]
    if not poss:
        return None
    ctxs = _contexts(x)
    res = {}
    best = None
    for pos in poss:
        for col in (c for c in cols if c.type == 'Color'):
            c = _paint(p, ctxs, pos, col)
            if c is None or not c['need']:
                continue
            cand = (c['hit'] / c['need'], -(c['wrong'] / c['rows'] if c['rows'] else 1.0), tuple(sorted(c.items())))
            if best is None or cand[:3] > best[:3]:
                best = cand + (c,)
    if best is not None:
        c = best[3]
        res.update({'wrong': c['wrong'] / c['rows'] if c['rows'] else 1.0,
                    'conflict': c['conflict'] / c['covered'] if c['covered'] else 0.0,
                    'prec_changed': c['ch_right'] / c['ch_rows'] if c['ch_rows'] else 0.0,
                    'cover': c['covered'] / c['cells'], 'right_cover': c['right_cells'] / c['cells']})
    exs = p.examples()
    # What the output holds under the cells of an input-frame Position column.
    top = None
    for pos in poss:
        if pos.frame_kind != 'input':
            continue
        outs, novel, n = C.Counter(), 0, 0
        for (_, k), rows in ctxs.items():
            if k >= len(exs) or not exs[k].same_size:
                continue
            ex = exs[k]
            seen = set()
            inp = set(ex.input.colors())
            for row in rows:
                cell = _cell(row[pos.index], ex.input.size)
                if not cell or cell in seen:
                    continue
                seen.add(cell)
                o = ex.output[cell]
                outs[o] += 1
                novel += o not in inp
                n += 1
        if n:
            got = (max(outs.values()) / n, novel / n)
            if top is None or got > top:
                top = got
    if top is not None:
        res.update({'modal': top[0], 'novel': top[1]})
    # An input-frame cell moved by an Offset.
    offs = [c for c in cols if c.type == 'Offset']
    seen = agree = 0
    for pos in poss:
        if pos.frame_kind != 'input':
            continue
        for (_, k), rows in ctxs.items():
            if k >= len(exs) or not exs[k].same_size:
                continue
            ex = exs[k]
            h, w = ex.input.size
            for row in rows:
                m = row[pos.index]
                if not hasattr(m, 'margins'):
                    continue
                for off in offs:
                    o = row[off.index]
                    if not hasattr(o, 'margins'):
                        continue
                    nt, nl = m.top + o.top, m.left + o.left
                    if 0 <= m.top < h and 0 <= m.left < w and 0 <= nt < h and 0 <= nl < w:
                        seen += 1
                        agree += ex.input[m.top, m.left] == ex.output[nt, nl]
    if seen:
        res['disp'] = agree / seen
    return res or None
