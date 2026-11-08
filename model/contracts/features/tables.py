"""Model input layer: what a table's rows state with no grid: the values of each column, the cells and the groups of a Position column, the boxes of a Box column, what two columns
of one row state together, and how the table stands to the tables upstream of it. A color, a number or an orientation enters a feature only through a relation, so a feature keeps
its value under the symmetries of the square and under a permutation of the colors.
"""
from collections import Counter

from grammar import ABSENT, Var, function, operator
from vocabulary import GROUPS, TABLE_STAGE, all_distinct, all_same, all_true, cardinality, columns, equal, frequencies, groups, is_subset, label_frequencies, labels, maximum, minimum, nonempty, other_than, over, row_total, several, total, value_list, values

NUM = ('Nat', 'Int')
ORIENT = ('Dir', 'Dir8', 'DiagDir', 'Axis', 'Axis4', 'DiagAxis', 'D4', 'C4', 'Sym', 'Sense')
DIRECTIONS = ('Dir', 'Dir8', 'DiagDir')
TYPE_SIZE = {'Dir': 4, 'DiagDir': 4, 'Dir8': 8, 'Axis': 2, 'DiagAxis': 2, 'Axis4': 4, 'D4': 8, 'C4': 4, 'Sense': 2}
AXIS_OF = {'DIR_T': 'V', 'DIR_B': 'V', 'DIR_L': 'H', 'DIR_R': 'H', 'DIAG_TL': 'DG', 'DIAG_BR': 'DG', 'DIAG_TR': 'AD', 'DIAG_BL': 'AD'}
OPPOSITE = {'DIR_T': 'DIR_B', 'DIR_B': 'DIR_T', 'DIR_L': 'DIR_R', 'DIR_R': 'DIR_L', 'DIAG_TL': 'DIAG_BR', 'DIAG_BR': 'DIAG_TL', 'DIAG_TR': 'DIAG_BL', 'DIAG_BL': 'DIAG_TR'}
ROTATIONS = {'D4_ID', 'D4_CW', 'D4_HT', 'D4_CC'}

n, a, b, g, x, t, u, y = (Var(v) for v in 'n a b g x t u y'.split())


def F():
    import features
    return features


class Constant:
    """A fixed value in a term."""
    is_term = True

    def __init__(self, value):
        self.value = value

    def __call__(self, c, e):
        return self.value

    def __hash__(self):
        return hash(frozenset(self.value))

    def __eq__(self, other):
        return isinstance(other, Constant) and self.value == other.value

    def __repr__(self):
        return 'constant'


def with_rows(dom):
    def wrapped(c, e):
        return dom(c, e) if c.rows else ()
    return wrapped


# ---- one column

@function
def top_two_ratio(u):
    return F().top2(u)


@function
def is_consecutive(u):
    return max(u) - min(u) + 1 == len(u)


@function
def is_arithmetic_progression(u):
    if len(u) < 3:
        return ABSENT
    held = sorted(u)
    return len({q - p for p, q in zip(held, held[1:])}) == 1


@operator
def type_size(c, e, v):
    return TYPE_SIZE.get(c.cols[e[v]][1], ABSENT)


@function
def on_one_axis(u):
    return len({AXIS_OF[q] for q in u}) == 1


@function
def contains_opposite_pair(u):
    return any(OPPOSITE[q] in u for q in u)


@function
def contains_identity(u):
    return 'D4_ID' in u


@operator
def rows_grouped_values(c, e, v, w):
    """The set of the values of column w per value of column v, as the strings of column v."""
    sets = {}
    for r in c.rows:
        sets.setdefault(str(r[e[v]]), set()).add(r[e[w]])
    return list(sets.values())


@function
def distinct_sets(u):
    return len({frozenset(q) for q in u})


@function
def sizes_of(u):
    return [len(q) for q in u]


@operator
def translations(c, e, v):
    return {(r[e[v]][0], r[e[v]][2]) for r in c.rows}


@function
def is_zero_in(u):
    return (0, 0) in u


@function
def all_along_rows_or_columns(u):
    return all(p == 0 or q == 0 for p, q in u)


@function
def chebyshev_lengths(u):
    return {max(abs(p), abs(q)) for p, q in u}


@operator
def is_key(c, e, v):
    return len({str(r[e[v]]) for r in c.rows}) == len(c.rows) if len(c.rows) > 1 else ABSENT


def unframed_columns(c, e):
    """A Position or Box column whose values are the cells or the boxes of no one frame."""
    if not c.rows:
        return ()
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[1] in ('Position', 'Box') and col[0] not in c.cs and not (col[1] == 'Box' and col[2] in c.sizes)]


@operator
def box_values(c, e, v):
    return {tuple(r[e[v]]) for r in c.rows}


@operator
def box_extents(c, e, v):
    return {(r[e[v]][0] + r[e[v]][1] + 1, r[e[v]][2] + r[e[v]][3] + 1) for r in c.rows}


@operator
def when_table_has_cells(c, e, term):
    return term(c, e) if c.cs else ABSENT


def declare_columns():
    colors, numbers, labeled, offsets = columns(('Color',)), columns(NUM), columns(ORIENT + ('Ident',)), columns(('Offset',))
    TABLE_STAGE.define('rows', row_total())
    TABLE_STAGE.define('empty', equal(row_total(), 0))
    TABLE_STAGE.define('one row', equal(row_total(), 1))
    TABLE_STAGE.define('{n} distinct', cardinality(values(n)), n=colors)
    TABLE_STAGE.define('{n} top-two count ratio', when_table_has_cells(top_two_ratio(frequencies(n))), n=colors)
    TABLE_STAGE.define('{n} distinct', cardinality(values(n)), n=numbers)
    some = with_rows(numbers)
    TABLE_STAGE.define('{n} max', maximum(value_list(n)), n=some)
    TABLE_STAGE.define('{n} min', minimum(value_list(n)), n=some)
    TABLE_STAGE.define('{n} top-two ratio', top_two_ratio(value_list(n)), n=some)
    TABLE_STAGE.define('{n} is a range of consecutive integers', is_consecutive(values(n)), n=some)
    TABLE_STAGE.define('{n} is an arithmetic progression', is_arithmetic_progression(values(n)), n=some)
    TABLE_STAGE.define('{n} rows per value max', maximum(frequencies(n)), n=some)
    TABLE_STAGE.define('{n} rows per value min', minimum(frequencies(n)), n=some)
    TABLE_STAGE.define('{n} rows per value all distinct', all_distinct(several(frequencies(n))), n=some)
    TABLE_STAGE.define('{n} distinct', cardinality(labels(n)), n=labeled)
    TABLE_STAGE.define('{n} covers its type', equal(cardinality(values(n)), type_size(n)), n=labeled)
    directions, symmetries, idents = with_rows(columns(DIRECTIONS)), with_rows(columns(('D4', 'C4'))), with_rows(columns(('Ident',)))
    TABLE_STAGE.define('{n} on one axis', on_one_axis(values(n)), n=directions)
    TABLE_STAGE.define('{n} includes an opposite pair', contains_opposite_pair(values(n)), n=directions)
    TABLE_STAGE.define('{n} all rotations', is_subset(values(n), Constant(ROTATIONS)), n=symmetries)
    TABLE_STAGE.define('{n} includes the identity', contains_identity(values(n)), n=symmetries)
    TABLE_STAGE.define('rows per {n} min', minimum(label_frequencies(n)), n=idents)
    TABLE_STAGE.define('rows per {n} max', maximum(label_frequencies(n)), n=idents)
    TABLE_STAGE.define('rows per {n} all distinct', all_distinct(several(label_frequencies(n))), n=idents)
    TABLE_STAGE.define('{x} values per {n} max', maximum(sizes_of(rows_grouped_values(n, x))), n=idents, x=colors)
    TABLE_STAGE.define('{x} value sets per {n} distinct', distinct_sets(rows_grouped_values(n, x)), n=idents, x=colors)
    TABLE_STAGE.define('{n} distinct', cardinality(translations(n)), n=offsets)
    some_offsets = with_rows(offsets)
    TABLE_STAGE.define('{n} includes the zero translation', is_zero_in(translations(n)), n=some_offsets)
    TABLE_STAGE.define('{n} along rows or columns', all_along_rows_or_columns(translations(n)), n=some_offsets)
    TABLE_STAGE.define('{n} longest translation', maximum(chebyshev_lengths(translations(n))), n=some_offsets)
    TABLE_STAGE.define('{n} translations of one length', equal(cardinality(chebyshev_lengths(translations(n))), 1), n=some_offsets)
    TABLE_STAGE.define('{n} is unique', is_key(n), n=columns())
    TABLE_STAGE.define('{n} values distinct', cardinality(box_values(n)), n=unframed_columns)
    TABLE_STAGE.define('{n} extents distinct', cardinality(box_extents(n)), n=unframed_columns)


# ---- a set of cells, whole or per group

def whole_grid(H, W):
    return {(r, k) for r in range(H) for k in range(W)}


CELL_MEASURES = {
    'cells': lambda S, H, W: len(S),
    'covers the grid': lambda S, H, W: len(S) == H * W,
    'components': lambda S, H, W: F().comps(S),
    'on one line': lambda S, H, W: len({q[0] for q in S}) <= 1 or len({q[1] for q in S}) <= 1,
    'touches the grid edge': lambda S, H, W: any(q[0] in (0, H - 1) or q[1] in (0, W - 1) for q in S),
    'complement is 4-connected': lambda S, H, W: F().comps(whole_grid(H, W) - S, diag=False) == 1,
    '4-connected components': lambda S, H, W: F().comps(S, diag=False),
    'every component is a straight line': lambda S, H, W: all(F().straight(q) for q in F().components(S)),
    'full lines': lambda S, H, W: F().full_lines(S, H, W),
    'cells per line max': lambda S, H, W: max(max(Counter(q[0] for q in S).values()), max(Counter(q[1] for q in S).values())),
    'fills its bounding box': lambda S, H, W: F().fills_box(S),
    'is the outline of its bounding box': lambda S, H, W: F().outlines_box(S),
    'symmetry count': lambda S, H, W: F().symmetry_count(S),
    'enclosed regions': lambda S, H, W: F().enclosed_regions(S),
    'box proportion of the grid': lambda S, H, W: round((max(q[0] for q in S) - min(q[0] for q in S) + 1) * (max(q[1] for q in S) - min(q[1] for q in S) + 1) / (H * W), 3)}
ANY_SET = ('cells', 'covers the grid', 'components', 'on one line', 'touches the grid edge', 'complement is 4-connected')


@operator
def of_set(c, e, S, name, v):
    """A measure of a set of cells of the frame of a column."""
    return CELL_MEASURES[name](S, *c.sizes[c.cs[c.cols[e[v]][0]][0]])


@operator
def cell_measure(c, e, name, v):
    """A measure of the set of cells of a column."""
    return CELL_MEASURES[name](c.cs[c.cols[e[v]][0]][1], *c.sizes[c.cs[c.cols[e[v]][0]][0]])


def cell_columns(c, e):
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.cs]


def nonempty_cell_columns(c, e):
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.cs and c.cs[col[0]][1]]


def frames_other_than_input(c, e):
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.cs and c.cs[col[0]][0] != 'input' and 'input' in c.sizes]


FRAME_RELATIONS = {'is the input size': lambda H, W, Hi, Wi: (H, W) == (Hi, Wi), 'is square': lambda H, W, Hi, Wi: H == W, 'proportion of the input': lambda H, W, Hi, Wi: round(H * W / (Hi * Wi), 3),
                   'is a multiple of the input size': lambda H, W, Hi, Wi: (H, W) != (Hi, Wi) and H % Hi == 0 and W % Wi == 0,
                   'divides the input size': lambda H, W, Hi, Wi: (H, W) != (Hi, Wi) and Hi % H == 0 and Wi % W == 0}


@operator
def frame_relation(c, e, name, v):
    return FRAME_RELATIONS[name](*c.sizes[c.cs[c.cols[e[v]][0]][0]], *c.sizes['input'])


@operator
def group_labels(c, e, v):
    """{group: cells} of a column of cells, or ABSENT where the table has no group."""
    held = c.grouped(e[v])
    return ABSENT if held is None else held


@function
def least_distance(held):
    return F().least_distance(held)


@function
def extreme_is_unique(sizes_, extreme):
    if len(sizes_) < 2:
        return ABSENT
    return sizes_.count(extreme(sizes_)) == 1


@function
def greatest_distance_to_nearest(held):
    if len(held) < 2 or len(held) > 30 or sum(len(q) for q in held.values()) > 300:
        return ABSENT
    return max(F().group_distances(held, each=True, cap=False).values())


@operator
def distinct_forms(c, e, items, eq):
    held = items(c, e)
    return ABSENT if held is ABSENT else len({eq.form(q) for q in held})


@operator
def groups_adjacent_toward_a_direction(c, e, v):
    """Whether, for one direction along a row or a column, each group has a cell next to another group or the grid's edge in that direction."""
    held = groups(v)(c, e)
    if held is ABSENT:
        return ABSENT
    gs = [q for q in held if q]
    if len(gs) < 2 or sum(len(q) for q in gs) > 900:
        return ABSENT
    H, W = c.sizes[c.cs[c.cols[e[v]][0]][0]]
    owner = {}
    for i, q in enumerate(gs):
        for k in q:
            owner.setdefault(k, set()).add(i)

    def rests(i, q, d):
        return any(not (0 <= k[0] + d[0] < H and 0 <= k[1] + d[1] < W) or owner.get((k[0] + d[0], k[1] + d[1]), {i}) - {i} for k in q)
    return any(all(rests(i, q, d) for i, q in enumerate(gs)) for d in ((1, 0), (-1, 0), (0, 1), (0, -1)))


BOX_MEASURES = ('least margin', 'edges touched max', 'edges touched min', 'centered axes max', 'aligned', 'boxes of one size', 'some boxes overlap', 'nested boxes', 'boxes cover the grid',
                'evenly spaced along an axis', 'shorter side min', 'longer side max', 'every box is square', 'proportion of the grid', 'more than one cell along each axis', 'is the whole grid')


@operator(memo=True)
def box_set_measures(c, e, source):
    """{measure: value} of a set of boxes: of a Box column, the bounding box of a column's cells, or the bounding boxes of its groups."""
    kind, v = source
    if kind == 'column':
        fr, B = c.box_sets()[c.cols[e[v]][0]]
        H, W = c.sizes[fr]
        return F().box_features(B, H, W)
    fr, S = c.cs[c.cols[e[v]][0]]
    H, W = c.sizes[fr]
    if kind == 'cells':
        return F().box_features({F().bounding_box(S, H, W)}, H, W)
    held = groups(v)(c, e)
    return ABSENT if held is ABSENT else F().box_features({F().bounding_box(q, H, W) for q in held}, H, W)


@operator
def box_measure(c, e, source, name):
    held = box_set_measures(source)(c, e)
    return ABSENT if held is ABSENT else held.get(name, ABSENT)


def box_columns(c, e):
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.box_sets()]


def declare_cells():
    from outputs import EQUIVALENCES
    for name in CELL_MEASURES:
        TABLE_STAGE.define('{n} ' + name, cell_measure(name, n), n=cell_columns if name in ANY_SET else nonempty_cell_columns)
    for name in FRAME_RELATIONS:
        TABLE_STAGE.define('{n} frame ' + name, frame_relation(name, n), n=frames_other_than_input)
    per_group = '{n} bounding box per group of %s ' % GROUPS
    for name in BOX_MEASURES:
        TABLE_STAGE.define('{n} bounding box ' + name, box_measure(('cells', n), name), n=nonempty_cell_columns)
        TABLE_STAGE.define(per_group + name, box_measure(('groups', n), name), n=cell_columns)
        TABLE_STAGE.define('{n} ' + name, box_measure(('column', n), name), n=box_columns)
    TABLE_STAGE.define(per_group + 'distinct', box_measure(('groups', n), 'distinct'), n=cell_columns)
    TABLE_STAGE.define('{n} distinct', box_measure(('column', n), 'distinct'), n=box_columns)
    TABLE_STAGE.define('{n} least distance between groups of ' + GROUPS, least_distance(group_labels(n)), n=cell_columns)
    each = lambda name: nonempty(over(groups(n), of_set(name, n)))
    lead = '{n} %s per group of ' + GROUPS
    TABLE_STAGE.define(lead % 'cells' + ' min', minimum(each('cells')), n=cell_columns)
    TABLE_STAGE.define(lead % 'cells' + ' max', maximum(each('cells')), n=cell_columns)
    TABLE_STAGE.define(lead % 'components' + ' max', maximum(each('components')), n=cell_columns)
    TABLE_STAGE.define(lead % 'components' + ' total', total(each('components')), n=cell_columns)
    TABLE_STAGE.define(lead % 'fills its bounding box', all_true(each('fills its bounding box')), n=cell_columns)
    TABLE_STAGE.define(lead % 'symmetry count' + ' min', minimum(each('symmetry count')), n=cell_columns)
    TABLE_STAGE.define(lead % 'enclosed regions' + ' max', maximum(each('enclosed regions')), n=cell_columns)
    TABLE_STAGE.define(lead % 'full lines' + ' max', maximum(each('full lines')), n=cell_columns)
    TABLE_STAGE.define('{n} largest group of %s is unique' % GROUPS, extreme_is_unique(each('cells'), max), n=cell_columns)
    TABLE_STAGE.define('{n} smallest group of %s is unique' % GROUPS, extreme_is_unique(each('cells'), min), n=cell_columns)
    TABLE_STAGE.define('{n} distance to the nearest other group of %s, max' % GROUPS, greatest_distance_to_nearest(group_labels(n)), n=cell_columns)
    for eq in EQUIVALENCES:
        TABLE_STAGE.define('{n} distinct shapes per group of %s%s' % (GROUPS, eq.say), distinct_forms(nonempty(groups(n)), eq), n=cell_columns)
    TABLE_STAGE.define('{n} every group of %s adjoins another group or the grid edge in one direction' % GROUPS, groups_adjacent_toward_a_direction(n), n=cell_columns)


# ---- two columns of one row

def later_columns(v, types=None, same_type=False):
    """A column after v's in the table."""
    def dom(c, e):
        i = e[v]
        return [(j, c.cols[j][0]) for j in range(i + 1, len(c.cols)) if (types is None or c.cols[j][1] in types) and (not same_type or c.cols[j][1] == c.cols[i][1])]
    return dom


@operator
def order_of_numbers(c, e, v, w):
    signs = {(r[e[v]] > r[e[w]]) - (r[e[v]] < r[e[w]]) for r in c.rows}
    return {frozenset({-1}): '<', frozenset({-1, 0}): '<=', frozenset({0}): '=', frozenset({0, 1}): '>=', frozenset({1}): '>'}.get(frozenset(signs), 'mixed')


@operator
def monotonicity(c, e, v, w):
    """Whether column w rises or falls as column v rises."""
    i, j = e[v], e[w]
    if len({r[i] for r in c.rows}) < 2 or len({r[j] for r in c.rows}) < 2:
        return ABSENT
    pairs = sorted({(r[i], r[j]) for r in c.rows})
    up = all(p[1] <= q[1] for p, q in zip(pairs, pairs[1:]) if p[0] < q[0]) and all(p[1] == q[1] for p, q in zip(pairs, pairs[1:]) if p[0] == q[0])
    down = all(p[1] >= q[1] for p, q in zip(pairs, pairs[1:]) if p[0] < q[0]) and all(p[1] == q[1] for p, q in zip(pairs, pairs[1:]) if p[0] == q[0])
    return 'rises' if up else 'falls' if down else 'neither'


@operator
def equality_of_columns(c, e, v, w):
    same = {str(r[e[v]]) == str(r[e[w]]) for r in c.rows}
    return 'in every row' if same == {True} else 'in no row' if same == {False} else 'in some rows'


@operator(memo=True)
def graph_shape_of(c, e, v, w):
    return F().graph_shape([(str(r[e[v]]), str(r[e[w]])) for r in c.rows])


@operator
def graph_component_count(c, e, v, w):
    return graph_shape_of(v, w)(c, e)[0]


@operator
def graph_greatest_degree(c, e, v, w):
    return graph_shape_of(v, w)(c, e)[1]


def in_one_frame(c, e, v, w):
    return c.cols[e[v]][1] == 'Position' and c.cols[e[w]][1] == 'Position' and c.cols[e[v]][0] in c.cs and c.cols[e[w]][0] in c.cs and c.cs[c.cols[e[v]][0]][0] == c.cs[c.cols[e[w]][0]][0]


def in_two_frames(c, e, v, w):
    return c.cols[e[v]][1] == 'Position' and c.cols[e[w]][1] == 'Position' and c.cols[e[v]][0] in c.cs and c.cols[e[w]][0] in c.cs and c.cs[c.cols[e[v]][0]][0] != c.cs[c.cols[e[w]][0]][0]


def displacements(c, e, v, w):
    return {(r[e[w]][0] - r[e[v]][0], r[e[w]][2] - r[e[v]][2]) for r in c.rows}


@operator
def displacement_measure(c, e, v, w, name):
    if not in_one_frame(c, e, v, w):
        return ABSENT
    moves = displacements(c, e, v, w)
    dist = [max(abs(p), abs(q)) for p, q in moves]
    if name == 'displacements distinct':
        return len(moves)
    if name == 'distance max':
        return max(dist)
    if name == 'distance min':
        return min(dist)
    if name == 'along rows or columns':
        return all(p == 0 or q == 0 for p, q in moves)
    return all(abs(p) == abs(q) for p, q in moves)


@operator
def displacements_across_frames(c, e, v, w):
    return len(displacements(c, e, v, w)) if in_two_frames(c, e, v, w) else ABSENT


def position_in_frame_of_box(c, e):
    """A Box column in the frame of the Position column v."""
    held = c.cs[c.cols[e[a]][0]]
    return [(j, col[0]) for j, col in enumerate(c.cols) if col[1] == 'Box' and col[2] == held[0]]


@operator
def cell_in_box_in_every_row(c, e, v, w):
    i, j = e[v], e[w]
    return all(r[i][0] >= r[j][0] and r[i][1] >= r[j][1] and r[i][2] >= r[j][2] and r[i][3] >= r[j][3] for r in c.rows)


@operator
def key_determines_row(c, e):
    keys = [i for i, col in enumerate(c.cols) if col[0].startswith('key.')]
    if not keys or len(keys) >= len(c.cols):
        return ABSENT
    seen = {}
    return all(seen.setdefault(tuple(str(r[i]) for i in keys), tuple(str(q) for q in r)) == tuple(str(q) for q in r) for r in c.rows)


def declare_pairs():
    some = with_rows(columns())
    orient_or_label = with_rows(columns(ORIENT + ('Ident', 'Color')))
    numbers = with_rows(columns(NUM))
    positions = with_rows(lambda c, e: [(i, tok) for i, tok in columns(('Position',))(c, e) if tok in c.cs])

    def number_pairs(c, e):
        i = e[a]
        return [(j, c.cols[j][0]) for j in range(len(c.cols)) if j != i and c.cols[j][1] in NUM]
    TABLE_STAGE.define('{a} vs {b} in every row', order_of_numbers(a, b), a=numbers, b=number_pairs)
    TABLE_STAGE.define('{b} as {a} rises', monotonicity(a, b), a=numbers, b=number_pairs)
    TABLE_STAGE.define('{a} equals {b}', equality_of_columns(a, b), also='{b} equals {a}', a=orient_or_label, b=later_columns(a, same_type=True))
    graphs = with_rows(columns(('Ident', 'Position', 'Color', 'Nat', 'Int')))
    TABLE_STAGE.define('{a}-{b} graph components', graph_component_count(a, b), also='{b}-{a} graph components', a=graphs, b=later_columns(a, same_type=True))
    TABLE_STAGE.define('{a}-{b} graph greatest degree', graph_greatest_degree(a, b), also='{b}-{a} graph greatest degree', a=graphs, b=later_columns(a, same_type=True))
    for name in ('displacements distinct', 'distance max', 'distance min', 'along rows or columns', 'along diagonals'):
        TABLE_STAGE.define('{a} to {b} ' + name, displacement_measure(a, b, name), also='{b} to {a} ' + name, a=positions, b=later_columns(a, ('Position',)))
    TABLE_STAGE.define('{a} to {b} offsets distinct, across frames', displacements_across_frames(a, b), also='{b} to {a} offsets distinct, across frames', a=positions, b=later_columns(a, ('Position',)))
    TABLE_STAGE.define('{a} inside {b} in every row', cell_in_box_in_every_row(a, b), a=positions, b=position_in_frame_of_box)
    TABLE_STAGE.define('key determines the row', guarded_rows(key_determines_row()))


@operator
def guarded_rows(c, e, term):
    return term(c, e) if c.rows else ABSENT


# ---- a color with a column of cells

def colored_cells(c, e, v, w):
    M = {}
    for r in c.rows:
        M.setdefault((r[e[v]][0], r[e[v]][2]), set()).add(r[e[w]])
    return {k: next(iter(q)) for k, q in M.items()} if all(len(q) == 1 for q in M.values()) else None


@operator(memo=True)
def coloring_measures(c, e, v, w):
    """{measure: value} of the cells of column v with the colors of column w, where a cell holds one color."""
    M = colored_cells(c, e, v, w)
    if M is None:
        return {}
    f = {'symmetry count': F().colored_symmetry_count(M)}
    by = {}
    for k, q in M.items():
        by.setdefault(q, set()).add(k)
    if 1 < len(by) <= 10:
        holes = {q: F().holes(s) for q, s in by.items()}
        f['a color lies in the holes of another'] = any(holes[p] and by[q] <= holes[p] for p in by for q in by if p != q)
        f['touching color pairs'] = len({frozenset((M[k], M[(k[0] + p, k[1] + q)])) for k in M for p, q in ((1, 0), (0, 1)) if (k[0] + p, k[1] + q) in M and M[(k[0] + p, k[1] + q)] != M[k]})
    if F().fills_box(set(M)):
        f['least period'] = F().least_period(M)
    return f


@operator
def coloring_measure(c, e, v, w, name):
    return coloring_measures(v, w)(c, e).get(name, ABSENT)


@operator
def shape_and_colors_per_label(c, e, v, w, label, shape_first):
    cells_g, colors_g = {}, {}
    for r in c.rows:
        cells_g.setdefault(str(r[e[label]]), set()).add((r[e[v]][0], r[e[v]][2]))
        colors_g.setdefault(str(r[e[label]]), set()).add(r[e[w]])
    if len(cells_g) < 2:
        return ABSENT
    shape = {k: F().normalized(q) for k, q in cells_g.items()}
    colors = {k: frozenset(q) for k, q in colors_g.items()}
    return F().fixes(shape, colors) if shape_first else F().fixes(colors, shape)


def label_columns_other_than(*others):
    def dom(c, e):
        taken = {e[v] for v in others}
        return [(i, col[0]) for i, col in enumerate(c.cols) if i not in taken and (col[1] == 'Ident' or col[0].startswith('key.'))]
    return dom


def declare_colorings():
    colors = with_rows(columns(('Color',)))
    TABLE_STAGE.define('{x} rows per value all equal', all_same(frequencies(x)), x=colors)
    TABLE_STAGE.define('{x} rows per value all distinct', all_distinct(several(frequencies(x))), x=colors)
    for name in ('symmetry count', 'a color lies in the holes of another', 'touching color pairs', 'least period'):
        TABLE_STAGE.define('{n},{x} ' + name, coloring_measure(n, x, name), x=colors, n=cell_columns)
    TABLE_STAGE.define('{n},{x} same shape, same colors, per {g}', shape_and_colors_per_label(n, x, g, True), x=colors, n=cell_columns, g=label_columns_other_than(n, x))
    TABLE_STAGE.define('{n},{x} same colors, same shape, per {g}', shape_and_colors_per_label(n, x, g, False), x=colors, n=cell_columns, g=label_columns_other_than(n, x))


declare_columns()
declare_cells()
declare_pairs()
declare_colorings()
