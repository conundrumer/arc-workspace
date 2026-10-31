"""G12 colors: the colors that X's Color columns hold, against the colors of the train grids.

A grid's background is its most common color (the smallest on a tie). Each context counts the first model of X's
table; a context that X has with no row counts as empty.
A table with the same rows in every one of 2 or more non-empty contexts does not depend on the example: its colors
are compared with the colors of all the train examples together.
"""
from featlib import feature


def _contexts(table):
    """{(assignment, example): rows of the first model, a row being a tuple of decoded cells}; a context the table
    has with no row is empty."""
    ex = table.examples()
    if any(c.type == 'Example' for c in table.columns()):
        return {k: m[0] for k, m in ex.items() if m}
    keys = {(e['assignment'], e['train']) for e in table.entries}
    return {k: (ex[k][0] if ex.get(k) else []) for k in keys}


def _plain(cell):
    return cell.margins if hasattr(cell, 'margins') else cell


def _example_free(contexts):
    """Whether the table has the same rows in every non-empty context, and there are 2 or more such contexts."""
    rows = [frozenset(tuple(_plain(c) for c in r) for r in rs) for rs in contexts.values() if rs]
    return len(rows) >= 2 and len(set(rows)) == 1


@feature
def g12_colors(p):
    """G12 colors: the share of the train grids' colors that X's Color columns hold.

    out_cov, in_cov, new_cov: the share of the output's colors off its background, of the input's colors off its background, and of the colors that the output has and the input lacks (1 where there are none), that the Color columns of X hold together; seen: the share of X's colors that occur in the input or the output (1 for an empty X; for a table that is the same in every context, in the input or the output of any example). Means over contexts.
    exact: the number of Color columns whose colors equal the output's colors in every non-empty context.
    same_input: the number whose colors equal the input's colors in every non-empty context.
    None without a Color column or a context. At a Det point only `seen` is given: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so the other keys would compare a row with another example's grids.
    Needs: partial. Monotone: partly (`out_cov`, `in_cov` and `new_cov` only fall; `seen` only rises; `exact` and `same_input` are not monotone).
    """
    x = p.x
    cols = [c for c in x.columns() if c.type == 'Color']
    if not cols:
        return None
    exs = p.examples()
    acc = {'out_cov': 0.0, 'in_cov': 0.0, 'new_cov': 0.0, 'seen': 0.0}
    n = 0
    equal_out = {c.index: True for c in cols}
    equal_in = dict(equal_out)
    nonempty = {c.index: False for c in cols}
    contexts = _contexts(x)
    pooled = set()
    if _example_free(contexts):
        for e in exs:
            pooled |= set(e.input.colors()) | set(e.output.colors())
    for (_, k), rows in contexts.items():
        if k >= len(exs):
            continue
        gin, gout = exs[k].input, exs[k].output
        back_in, back_out = min(gin.most_common()), min(gout.most_common())
        out_colors = set(gout.colors()) - {back_out}
        in_colors = set(gin.colors()) - {back_in}
        new_colors = out_colors - in_colors
        held = {r[c.index] for r in rows for c in cols}
        known = out_colors | in_colors | {back_in, back_out}
        n += 1
        acc['out_cov'] += len(held & out_colors) / len(out_colors) if out_colors else 1.0
        acc['in_cov'] += len(held & in_colors) / len(in_colors) if in_colors else 1.0
        acc['new_cov'] += len(held & new_colors) / len(new_colors) if new_colors else 1.0
        acc['seen'] += len(held & (pooled or known)) / len(held) if held else 1.0
        for c in cols:
            v = {r[c.index] for r in rows}
            if v:
                nonempty[c.index] = True
                equal_out[c.index] &= v == set(gout.colors())
                equal_in[c.index] &= v == set(gin.colors())
    if not n:
        return None
    res = {key: v / n for key, v in acc.items()}
    res['exact'] = sum(equal_out[i] and nonempty[i] for i in equal_out)
    res['same_input'] = sum(equal_in[i] and nonempty[i] for i in equal_in)
    if p.kind == 'Det':
        for key in ('out_cov', 'in_cov', 'new_cov', 'exact', 'same_input'):
            res[key] = None
    return res
