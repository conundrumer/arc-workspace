"""Model input layer: what holds of a table across the examples of its task: whether its values, its shapes and its rules stay the same from one
example to the next. A color, a number or an orientation value is compared only with the same column's values at other examples, so a feature
keeps its value under one symmetry of the square or one permutation of the colors applied to the whole task. An Ident names nothing outside its
example, so no feature compares one across examples.
"""
from grammar import ABSENT, Var, operator
from vocabulary import ALL_EXAMPLES_STAGE, Context, columns, other_than

NUM = ('Nat', 'Int')
ORIENT = ('Dir', 'Dir8', 'DiagDir', 'Axis', 'Axis4', 'DiagAxis', 'D4', 'C4', 'Sym', 'Sense')
VALUE = ('Color',) + NUM + ORIENT
MAX_ROWS = 2000  # the rows at one example up to which a feature reads each row
MAX_CELLS = 300  # the cells of a shape up to which a feature compares it up to an element of D4

ACROSS = (' at every example', ' to every example', ' across the examples', ' the other train examples', ' the other train examples, proportion')  # the features of this module


n, x = Var('n'), Var('x')


def F():
    import features
    return features


def examples_of(c):
    """The contexts of the table at each of its examples, or None where it has fewer than two, or more than MAX_ROWS rows at one."""
    return c.every(MAX_ROWS)


def all_equal(held):
    return all(y == held[0] for y in held)


def cell(p):
    return (p[0], p[2])


def cells_at(k, e, v):
    return {cell(r[e[v]]) for r in k.rows}


def in_frame_at_every_example(c, e, v):
    ctxs = examples_of(c)
    return ctxs is not None and all(k.rows and all(min(r[e[v]]) >= 0 for r in k.rows) for k in ctxs)


@operator
def same_value_set(c, e, v):
    ctxs = examples_of(c)
    return ABSENT if ctxs is None else all_equal([{str(r[e[v]]) for r in k.rows} for k in ctxs])


@operator
def common_value_count(c, e, v):
    ctxs = examples_of(c)
    return ABSENT if ctxs is None else len(set.intersection(*[{str(r[e[v]]) for r in k.rows} for k in ctxs]))


@operator
def same_box_set(c, e, v):
    ctxs = examples_of(c)
    return ABSENT if ctxs is None else all_equal([{tuple(r[e[v]]) for r in k.rows} for k in ctxs])


@operator
def same_shape_at_every_example(c, e, v, eq):
    if not in_frame_at_every_example(c, e, v):
        return ABSENT
    cells = [cells_at(k, e, v) for k in examples_of(c)]
    if eq.limit is not None and any(len(u) > MAX_CELLS for u in cells):
        return ABSENT
    return all_equal([eq.form(u) for u in cells])


@operator
def same_colored_shape(c, e, v, w):
    if not in_frame_at_every_example(c, e, v):
        return ABSENT
    held = []
    for k in examples_of(c):
        r0, k0 = min(r[e[v]][0] for r in k.rows), min(r[e[v]][2] for r in k.rows)
        held.append({(r[e[v]][0] - r0, r[e[v]][2] - k0, r[e[w]]) for r in k.rows})
    return all_equal(held)


@operator
def common_group_shapes(c, e, v):
    if not in_frame_at_every_example(c, e, v):
        return ABSENT
    gcols = [j for j, (m, ty, _) in enumerate(c.cols) if ty in ('Ident', 'Color') or m.startswith('key.')]
    ctxs = examples_of(c)
    if not gcols or any(len(k.rows) > MAX_CELLS for k in ctxs):
        return ABSENT
    shapes = []
    for k in ctxs:
        groups = {}
        for r in k.rows:
            groups.setdefault(tuple(str(r[g]) for g in gcols), set()).add(cell(r[e[v]]))
        shapes.append({F().normalized(g) for g in groups.values()})
    return len(set.intersection(*shapes))


def declare_examples():
    from outputs import EQUIVALENCES
    ALL_EXAMPLES_STAGE.define('{n} same values at every example', same_value_set(n), n=columns(VALUE))
    ALL_EXAMPLES_STAGE.define('{n} values common to every example', common_value_count(n), n=columns(VALUE))
    ALL_EXAMPLES_STAGE.define('{n} same places at every example', same_box_set(n), n=columns(('Position', 'Box')))
    position = columns(('Position',))
    for eq in EQUIVALENCES:
        ALL_EXAMPLES_STAGE.define('{n} same shape%s at every example' % eq.say, same_shape_at_every_example(n, eq), n=position)
    ALL_EXAMPLES_STAGE.define('{n},{x} same colored shape at every example', same_colored_shape(n, x), n=position, x=columns(('Color',)))
    ALL_EXAMPLES_STAGE.define('{n} group shapes common to every example', common_group_shapes(n), n=position)


declare_examples()


def by_example(tab):
    """{example: rows} of a table with rows of its own at two or more examples and at most MAX_ROWS at each, or None."""
    rows = tab['rows']
    if 'task' in rows or len(rows) < 2 or any(len(r) > MAX_ROWS for r in rows.values()):
        return None
    return rows


def table_claims(tab):
    """{feature: value} of the table's rows over its examples."""
    return ALL_EXAMPLES_STAGE.run(Context(tab, None, None, None, None))


_memo = {}


def like_train(tab, ex):
    """{feature: value}: how the table's rows at ex stand to its rows at the task's other train examples. A test input has no output to tell a reading
    apart, so what a table does there is known only by how it stands to the train examples."""
    per = by_example(tab)
    if not per or ex not in per:
        return {}
    others = [rows for e, rows in per.items() if e.startswith('train/') and e != ex]
    if not others:
        return {}
    rows = per[ex]
    f = {'rows within the range of the other train examples': min(map(len, others)) <= len(rows) <= max(map(len, others))}
    for i, (n_, ty, _) in enumerate(tab['columns']):
        if ty in VALUE and rows:
            vals = {str(r[i]) for r in rows}
            seen = {str(r[i]) for o in others for r in o}
            f[n_ + ' values seen at the other train examples, proportion'] = round(len(vals & seen) / len(vals), 3)
    return f


def claims(tab, ex, task_json, grids_of):
    """{feature: value} of the table at example ex: table_claims, kept for the table's rows, and how its rows there stand to the other train examples."""
    rows = tab['rows']
    held = _memo.get(id(rows))
    if held is None or held[0] is not rows or held[1] != [c[0] for c in tab['columns']]:
        if len(_memo) > 2000:
            _memo.clear()
        held = (rows, [c[0] for c in tab['columns']], table_claims(tab))
        _memo[id(rows)] = held
    f = dict(held[2])
    f.update(like_train(tab, ex))
    return f
