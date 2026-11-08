"""Model input layer: how a table stands to the tables upstream of it: its values against theirs, its cells and boxes against theirs, its groups and shapes against theirs, and what
the pairs of objects in its rows are like, by what the upstream tables say of those objects.
"""
from grammar import ABSENT, Var, operator
from vocabulary import TABLE_STAGE, UPSTREAM_STAGE, columns

NUM = ('Nat', 'Int')
ORIENT = ('Dir', 'Dir8', 'DiagDir', 'Axis', 'Axis4', 'DiagAxis', 'D4', 'C4', 'Sym', 'Sense')

n, x, a, b, t, u, y, m = (Var(v) for v in 'n x a b t u y m'.split())


def F():
    import features
    return features


def cmp(p, q):
    return '<' if p < q else '=' if p == q else '>'


def tables_with_count(c, e):
    return [(i, v.name) for i, v in enumerate(c.views) if v.count is not None]


def tables_with_rows(c, e):
    return [(i, v.name) for i, v in enumerate(c.views) if v.rows is not None]


def their_columns(test):
    """A column of the upstream table for which test(c, e, its column, the view) holds."""
    def dom(c, e):
        v = c.views[e[t]]
        return [(j, col[0]) for j, col in enumerate(v.tab['columns']) if test(c, e, col, v)]
    return dom


def view(c, e):
    return c.views[e[t]]


def values_of(c, e, v):
    return {r[e[v]] for r in c.rows}


def their_values(c, e, w):
    return {r[e[w]] for r in view(c, e).rows}


def my_cells(c, e, v):
    return c.cs[c.cols[e[v]][0]]


def their_cells(c, e, w):
    v = view(c, e)
    return v.cells[v.tab['columns'][e[w]][0]]


def my_groups(c, e, v):
    return c.memo_groups(c.name, c.cols, c.rows, c.cols[e[v]][0])


def their_groups(c, e, w):
    v = view(c, e)
    return c.memo_groups(v.name, v.tab['columns'], v.rows, v.tab['columns'][e[w]][0])


def form(c, key, S, fn):
    if (key, fn) not in c.shared:
        c.shared[key, fn] = fn(S)
    return c.shared[key, fn]


@operator
def row_count_vs_table(c, e):
    return cmp(len(c.rows), view(c, e).count)


@operator
def label_agreement(c, e, v, w, label):
    """Whether, per label, the values of column v are those of column w of the upstream table. The table's Ident column for the labels is the last one with the same labels."""
    ut = view(c, e)
    mine_by = {}
    for r in c.rows:
        mine_by.setdefault(str(r[e[label]]), []).append(r)
    found = ABSENT
    for bi, col in enumerate(ut.tab['columns']):
        if col[1] != 'Ident':
            continue
        theirs_by = {}
        for r in ut.rows:
            theirs_by.setdefault(str(r[bi]), []).append(r)
        if set(mine_by) != set(theirs_by):
            continue
        agree = [{str(r[e[v]]) for r in mine_by[k]} == {str(r[e[w]]) for r in theirs_by[k]} for k in mine_by]
        found = 'for every one' if all(agree) else 'for none' if not any(agree) else 'for some'
    return found


@operator
def value_set_relation(c, e, v, w):
    return F().setrel2(values_of(c, e, v), their_values(c, e, w))


@operator
def orientation_set_relation(c, e, v, w):
    return F().setrel2({str(r[e[v]]) for r in c.rows}, {str(r[e[w]]) for r in view(c, e).rows})


@operator
def max_vs_rows(c, e, v):
    return cmp(max(r[e[v]] for r in c.rows), len(view(c, e).rows))


@operator
def max_vs_groups(c, e, v, w):
    held = their_groups(c, e, w)
    return cmp(max(r[e[v]] for r in c.rows), len(held)) if held else ABSENT


def same_frame_cells(c, e, col, v):
    return col[0] in v.cells and v.cells[col[0]][0] == my_cells(c, e, n)[0]


@operator
def color_agreement_at_shared_cells(c, e, v, w, p, q):
    mine = {}
    for r in c.rows:
        mine.setdefault((r[e[v]][0], r[e[v]][2]), set()).add(r[e[w]])
    theirs = {}
    for r in view(c, e).rows:
        theirs.setdefault((r[e[p]][0], r[e[p]][2]), set()).add(r[e[q]])
    shared = set(mine) & set(theirs)
    if not shared:
        return ABSENT
    agree = [mine[k] == theirs[k] for k in shared]
    return 'at every one' if all(agree) else 'at none' if not any(agree) else 'at some'


@operator
def box_set_relation(c, e, v, w):
    uv = view(c, e)
    held = uv.boxes[uv.tab['columns'][e[w]][0]]
    return F().setrel2(uv.my_boxes[c.cols[e[v]][0]][1], held[1])


@operator
def groups_relation(c, e, v, w):
    mine, theirs = my_groups(c, e, v), their_groups(c, e, w)
    if not mine or not theirs or my_cells(c, e, v)[0] != their_cells(c, e, w)[0]:
        return ABSENT
    return F().setrel2({frozenset(q) for q in mine.values()}, {frozenset(q) for q in theirs.values()})


@operator
def group_count_comparison(c, e, v, w):
    mine, theirs = my_groups(c, e, v), their_groups(c, e, w)
    return cmp(len(mine), len(theirs)) if mine and theirs else ABSENT


@operator
def group_shapes_relation(c, e, v, w):
    mine, theirs = my_groups(c, e, v), their_groups(c, e, w)
    if not mine or not theirs:
        return ABSENT
    return F().setrel2({F().normalized(q) for q in mine.values() if q}, {F().normalized(q) for q in theirs.values() if q})


@operator
def same_shape(c, e, v, w, fn):
    S, U = my_cells(c, e, v)[1], their_cells(c, e, w)[1]
    if not S or not U:
        return ABSENT
    uv = view(c, e)
    return len(S) == len(U) and form(c, (c.name, c.cols[e[v]][0]), S, fn) == form(c, (uv.name, uv.tab['columns'][e[w]][0]), U, fn)


def grid_of_frame(c, fr):
    H, W = c.sizes[fr]
    return {(r, k) for r in range(H) for k in range(W)}


@operator
def cells_relation(c, e, v, w):
    fr, S = my_cells(c, e, v)
    return F().setrel(S, their_cells(c, e, w)[1], grid_of_frame(c, fr))


@operator
def cell_count_comparison(c, e, v, w):
    return cmp(len(my_cells(c, e, v)[1]), len(their_cells(c, e, w)[1]))


@operator
def relation_to_derived_cells(c, e, v, w, fn):
    fr, S = my_cells(c, e, v)
    U = their_cells(c, e, w)[1]
    if not U:
        return ABSENT
    uv = view(c, e)
    return F().setrel(S, form(c, (uv.name, uv.tab['columns'][e[w]][0]), U, fn), grid_of_frame(c, fr))


@operator
def overlapping_row_or_column_ranges(c, e, v, w):
    S, U = my_cells(c, e, v)[1], their_cells(c, e, w)[1]
    if not S or not U:
        return ABSENT
    rs, ks, urs, uks = {q[0] for q in S}, {q[1] for q in S}, {q[0] for q in U}, {q[1] for q in U}
    return (min(rs) <= max(urs) and min(urs) <= max(rs)) or (min(ks) <= max(uks) and min(uks) <= max(ks))


@operator
def least_chebyshev_distance(c, e, v, w):
    S, U = my_cells(c, e, v)[1], their_cells(c, e, w)[1]
    if not S or not U or len(S) > 300 or len(U) > 300:
        return ABSENT
    return F().least_distance({0: S, 1: U})


@operator
def proportion_on_boundary(c, e, v, w):
    S, U = my_cells(c, e, v)[1], their_cells(c, e, w)[1]
    if not S or not S <= U:
        return ABSENT
    return round(len([q for q in S if any((q[0] + p, q[1] + r) not in U for p, r in ((-1, 0), (1, 0), (0, -1), (0, 1)))]) / len(S), 3)


@operator
def mean_neighbors_in(c, e, v, w):
    S, U = my_cells(c, e, v)[1], their_cells(c, e, w)[1]
    if not S:
        return ABSENT
    return round(sum((q[0] + p, q[1] + r) in U for q in S for p in (-1, 0, 1) for r in (-1, 0, 1) if (p, r) != (0, 0)) / len(S), 3)


def their_box_columns(c, e):
    v = view(c, e)
    fr = my_cells(c, e, n)[0]
    return [(j, col[0]) for j, col in enumerate(v.tab['columns']) if col[0] in v.boxes and v.boxes[col[0]][0] == fr]


def their_boxes(c, e, w):
    v = view(c, e)
    return v.boxes[v.tab['columns'][e[w]][0]][1]


def box_interval(c, e, v, w):
    fr = my_cells(c, e, v)[0]
    H, W = c.sizes[fr]
    d, q, l, r = next(iter(their_boxes(c, e, w)))
    return d, H - 1 - q, l, W - 1 - r


@operator
def inside_some_box(c, e, v, w):
    fr, S = my_cells(c, e, v)
    B = their_boxes(c, e, w)
    if len(B) < 2 or not S:
        return ABSENT
    H, W = c.sizes[fr]
    spans = [(d, H - 1 - q, l, W - 1 - r) for d, q, l, r in B]
    return all(any(r0 <= k[0] <= r1 and c0 <= k[1] <= c1 for r0, r1, c0, c1 in spans) for k in S)


def single_box(fn):
    def wrapped(c, e, v, w):
        if len(their_boxes(c, e, w)) != 1:
            return ABSENT
        S = my_cells(c, e, v)[1]
        r0, r1, c0, c1 = box_interval(c, e, v, w)
        inside = [k for k in S if r0 <= k[0] <= r1 and c0 <= k[1] <= c1]
        return fn(S, inside, r0, r1, c0, c1)
    wrapped.__name__ = fn.__name__
    return operator(wrapped)


@single_box
def inside_the_box(S, inside, r0, r1, c0, c1):
    return len(inside) == len(S)


@single_box
def proportion_on_box_border(S, inside, r0, r1, c0, c1):
    return round(len([k for k in S if k in inside and (k[0] in (r0, r1) or k[1] in (c0, c1))]) / len(S), 3) if S else None


@single_box
def distance_from_edge_midpoint(S, inside, r0, r1, c0, c1):
    if len(S) != 1:
        return ABSENT
    (p, q), = S
    offs = []
    if q in (c0, c1) and r0 <= p <= r1:
        offs.append(abs(p - (r0 + r1) / 2))
    if p in (r0, r1) and c0 <= q <= c1:
        offs.append(abs(q - (c0 + c1) / 2))
    return min(offs) if offs else None


def mine_of(types):
    def dom(c, e):
        return [(i, col[0]) for i, col in enumerate(c.cols) if col[1] in types]
    return dom


def with_rows(dom):
    def wrapped(c, e):
        return dom(c, e) if c.rows else ()
    return wrapped


def my_cell_columns(c, e):
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.cs]


def declare_upstream():
    UPSTREAM_STAGE.define('rows vs {t}', row_count_vs_table(), t=tables_with_count)
    with_view = tables_with_rows
    same_type = lambda c, e, col, v: col[1] == c.cols[e[x]][1]
    UPSTREAM_STAGE.define('{x} agrees with {t}.{u} by {a}', label_agreement(x, u, a), t=with_view, a=with_rows(mine_of(('Ident',))),
                          x=lambda c, e: [(i, col[0]) for i, col in enumerate(c.cols) if i != e[a] and (col[1] == 'Color' or col[1] in NUM or col[1] in ORIENT)], u=their_columns(same_type))
    UPSTREAM_STAGE.define('{x} vs {t}.{u}', value_set_relation(x, u), t=with_view, x=mine_of(('Color', 'Nat', 'Int')),
                          u=their_columns(lambda c, e, col, v: (col[1] == 'Color') == (c.cols[e[x]][1] == 'Color') and (col[1] in NUM) == (c.cols[e[x]][1] in NUM)))
    UPSTREAM_STAGE.define('{x} orientations vs {t}.{u}', orientation_set_relation(x, u), t=with_view, x=mine_of(ORIENT), u=their_columns(same_type))
    UPSTREAM_STAGE.define('{x} max vs rows of {t}', max_vs_rows(x), t=with_view, x=with_rows(mine_of(NUM)))
    their_cell_columns = their_columns(lambda c, e, col, v: col[0] in v.cells)
    UPSTREAM_STAGE.define('{x} max vs groups of {t}.{u}', max_vs_groups(x, u), t=with_view, x=with_rows(mine_of(NUM)), u=their_cell_columns)
    same_frame = their_columns(same_frame_cells)
    UPSTREAM_STAGE.define('{n},{x} agrees with {t}.{u},{y} at shared cells', color_agreement_at_shared_cells(n, x, u, y), t=with_view, n=my_cell_columns, x=mine_of(('Color',)), u=same_frame,
                          y=their_columns(lambda c, e, col, v: col[1] == 'Color'))
    UPSTREAM_STAGE.define('{b} boxes vs {t}.{u} boxes', box_set_relation(b, u), t=with_view, b=lambda c, e: [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.views[e[t]].my_boxes],
                          u=their_columns(lambda c, e, col, v: col[0] in v.boxes and v.boxes[col[0]][0] == v.my_boxes[c.cols[e[b]][0]][0]))
    cells = my_cell_columns
    UPSTREAM_STAGE.define('{n} groups vs {t}.{u} groups', groups_relation(n, u), t=with_view, n=cells, u=their_cell_columns)
    UPSTREAM_STAGE.define('{n} group count vs {t}.{u} groups', group_count_comparison(n, u), t=with_view, n=cells, u=their_cell_columns)
    UPSTREAM_STAGE.define('{n} group shapes vs {t}.{u} group shapes', group_shapes_relation(n, u), t=with_view, n=cells, u=their_cell_columns)
    UPSTREAM_STAGE.define('{n} same shape as {t}.{u}', same_shape(n, u, _translation_form), t=with_view, n=cells, u=their_cell_columns)
    UPSTREAM_STAGE.define('{n} same shape up to rotation and reflection as {t}.{u}', same_shape(n, u, _d4_form), t=with_view, n=cells, u=their_cell_columns)
    UPSTREAM_STAGE.define('{n} vs {t}.{u}', cells_relation(n, u), t=with_view, n=cells, u=same_frame)
    UPSTREAM_STAGE.define('{n} cells vs {t}.{u} cells', cell_count_comparison(n, u), t=with_view, n=cells, u=same_frame)
    UPSTREAM_STAGE.define('{n} vs the holes of {t}.{u}', relation_to_derived_cells(n, u, _holes), t=with_view, n=cells, u=same_frame)
    UPSTREAM_STAGE.define('{n} vs the box of {t}.{u}', relation_to_derived_cells(n, u, _box_cells), t=with_view, n=cells, u=same_frame)
    UPSTREAM_STAGE.define('{n} shares rows or columns with {t}.{u}', overlapping_row_or_column_ranges(n, u), t=with_view, n=cells, u=same_frame)
    UPSTREAM_STAGE.define('{n} least distance to {t}.{u}', least_chebyshev_distance(n, u), t=with_view, n=cells, u=same_frame)
    UPSTREAM_STAGE.define('{n} on the boundary of {t}.{u}, proportion', proportion_on_boundary(n, u), t=with_view, n=cells, u=same_frame)
    UPSTREAM_STAGE.define('{n} neighbors in {t}.{u}, mean', mean_neighbors_in(n, u), t=with_view, n=cells, u=same_frame)
    UPSTREAM_STAGE.define('{n} inside the boxes of {t}.{u}', inside_some_box(n, u), t=with_view, n=cells, u=their_box_columns)
    UPSTREAM_STAGE.define('{n} inside {t}.{u}', inside_the_box(n, u), t=with_view, n=cells, u=their_box_columns)
    UPSTREAM_STAGE.define('{n} on the border of {t}.{u}, proportion', proportion_on_box_border(n, u), t=with_view, n=cells, u=their_box_columns)
    UPSTREAM_STAGE.define('{n} distance from the middle of an edge of {t}.{u}', distance_from_edge_midpoint(n, u), t=with_view, n=cells, u=their_box_columns)


def _translation_form(S):
    return F().normalized(S)


def _d4_form(S):
    return F().canon(S)


def _holes(S):
    return F().holes(S)


def _box_cells(S):
    return F().box_cells(S)


declare_upstream()
