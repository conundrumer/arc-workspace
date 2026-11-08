"""Model input layer: the second version of the library, whose schemas take the equivalence type as a parameter.

A feature reads a color only through equality, so a color is one equivalence type among others. Each schema here holds for a labeling of a grid by another equivalence type (grammar.LABEL_TYPES): the
shape of a cell's component, up to translation or up to D4, the component itself, or its size. So what the first version states of colors, this one states of shapes, components and counts. The
schemas also take the type of a table's own label column as a parameter, group a column of cells by any such column, and give a group's shape the measures that a color column has.
"""
from collections import Counter

from grammar import ABSENT, INPUT, LABELINGS, OUTPUT, Var, function, operator
from grids import labeling
from dependencies import CELL_PARTITIONS, GROUP_PROPERTIES, MAX_ROWS_PER_EXAMPLE, column_value, determines, disjunction, grid_label_of_cell, grid_label_of_row, groups_in_grid, group_property, over_examples, pair, rows_if_several, rows_in_grid, cells_in_grid, unique_label, all_grids_same_size, grids_same_size
from grids import CELL_ROLES
from outputs import EQUIVALENCES, image
from roles import AGREES, agreeing, alternates, proportion_of_cells_in_role, straight_runs
from vocabulary import (GROUPS, MAX_CELLS, MAX_GROUPS, MAX_ROWS, OWN_OUTPUT_STAGE, OWN_STAGE, POSITION, TRAIN_EXAMPLES_STAGE, cardinality, cell_columns, columns, compare, contains, guarded, maximum, minimum, other_than, over, proportion, row_total, value_list, values)

NUM = ('Nat', 'Int')
ORIENT = ('Dir', 'Dir8', 'DiagDir', 'Axis', 'Axis4', 'DiagAxis', 'D4', 'C4', 'Sym', 'Sense')
OTHER_LABELS = ('Ident',) + NUM + ORIENT  # the types of a table's label columns, beside Color
GROUP_KEYS = NUM + ORIENT  # the types of the columns by which the first version does not group

n, p, x, g, b, d = (Var(v) for v in 'n p x g b d'.split())
COMPARABLE = tuple(u for u in LABELINGS if u.label != 'component')  # a component means nothing at another example


def F():
    import features
    return features


def stage_of(grid):
    return OWN_STAGE if grid.grid == 'input' else OWN_OUTPUT_STAGE


def view(c, grid):
    return labeling(c.array(grid))


def on(grid):
    """A column of cells in a frame of the grid's size, with a cell in the grid."""
    return cell_columns(grid)


def positions_of(grid):
    base = cell_columns(grid)

    def dom(c, e):
        return [(i, tok) for i, tok in base(c, e) if c.cols[i][1] == 'Position']
    return dom


def clipped(c, e, v, grid):
    G = view(c, grid)
    return c.cs[c.cols[e[v]][0]][1] & G.cells


# ---- the labels under a column's cells

@operator
def label_cardinality(c, e, v, grid):
    a = c.array(grid)
    return len({a[r][k] for r, k in clipped(c, e, v, grid)})


@operator
def is_union_of_classes(c, e, v, grid):
    G, S = view(c, grid), clipped(c, e, v, grid)
    return all(G.by_label[G.array[r][k]] <= S for r, k in S)


@operator
def boundary_label_cardinality(c, e, v, grid):
    G, S = view(c, grid), clipped(c, e, v, grid)
    near = {(r + a, k + q) for r, k in S for a in (-1, 0, 1) for q in (-1, 0, 1)} & G.cells
    near -= S
    return len({G.array[r][k] for r, k in near}) if near else ABSENT


@operator(memo=True)
def labels_per_group(c, e, v, grid):
    groups = F().grouped(c.cols, c.rows, e[v])
    if not groups:
        return ABSENT
    G = view(c, grid)
    cells = [u & G.cells for u in groups.values()]
    held = [frozenset(G.array[r][k] for r, k in u) for u in cells if u]
    return held if held else ABSENT


@function
def most_per_group(held):
    return max(len(u) for u in held)


@function
def proportion_single(held):
    return proportion(len(u) == 1 for u in held)


@function
def distinct_sets(held):
    return len(set(held))


# ---- rules over rows and groups, for a labeling

@operator
def agreement_under(c, e, v, u, grid):
    a, G = c.array(grid), view(c, grid)
    i = e[v]
    return agreeing([str(r[e[u]]) for r in c.rows], [a[r[i][0]][r[i][2]] if (r[i][0], r[i][2]) in G.cells else None for r in c.rows])


def several_rows(dom):
    def wrapped(c, e):
        return dom(c, e) if len(c.rows or ()) > 1 else ()
    return wrapped


@operator
def proportion_of_alternating_runs(c, e, v, grid):
    S = c.cs[c.cols[e[v]][0]][1]
    if not S <= view(c, grid).cells:
        return ABSENT
    runs = straight_runs(S)
    return proportion(alternates(run, c.array(grid)) for run in runs) if runs else ABSENT


# ---- symmetries and periods of a labeling

def agreement_of(array, d):
    im = image(array, d)
    if len(im) != len(array) or len(im[0]) != len(array[0]):
        return 0.0
    return round(sum(y == w for row, other in zip(array, im) for y, w in zip(row, other)) / (len(array) * len(array[0])), 3)


REFLECT_ACROSS = {'AXIS_V': 'D4_LR', 'AXIS_H': 'D4_TB', 'DAXIS_DG': 'D4_DG', 'DAXIS_AD': 'D4_AD'}
SYMMETRIES = ('D4_ID', 'D4_LR', 'D4_TB', 'D4_HT', 'D4_CW', 'D4_CC', 'D4_DG', 'D4_AD')


@operator
def proportion_of_axes_keeping(c, e, v, grid):
    lines = [y for y in {r[e[v]] for r in c.rows} if y in REFLECT_ACROSS]
    return proportion(agreement_of(c.array(grid), REFLECT_ACROSS[y]) == 1 for y in lines) if lines else ABSENT


@operator
def proportion_of_symmetries_keeping(c, e, v, grid):
    held = [y for y in {r[e[v]] for r in c.rows} if y in SYMMETRIES]
    return proportion(agreement_of(c.array(grid), y) == 1 for y in held) if held else ABSENT


def periods_of(array):
    H, W = len(array), len(array[0])
    out = set()
    for k in range(1, W):
        if all(row[q] == row[q + k] for row in array for q in range(W - k)):
            out.add(k)
    for k in range(1, H):
        if all(array[r][q] == array[r + k][q] for r in range(H - k) for q in range(W)):
            out.add(k)
    return out


@operator
def proportion_of_periods(c, e, v, grid):
    held = {r[e[v]] for r in c.rows if r[e[v]] > 0}
    if not held:
        return ABSENT
    kept = periods_of(c.array(grid))
    return proportion(y in kept for y in held)


# ---- numbers against a labeling's classes

@operator
def class_count(c, e, grid):
    return len(view(c, grid).counts)


@operator
def class_sizes(c, e, grid):
    return set(view(c, grid).counts.values())


@function
def intersects_set(u, v):
    return bool(u & v)


COMPONENT_ROLES = ('on the boundary of their component', 'at a corner of the box of their component', 'at the center of the box of their component', 'at a tip of their component',
                   'in a component of one cell', 'on a full line of one color')  # a labeling by components has the components of the colors
PLACE_ROLES = ('on the grid edge', 'at a grid corner')  # a cell's place alone gives them


def roles_that_read_labels(grid):
    return [r for r in CELL_ROLES if r not in PLACE_ROLES and not (grid.label == 'component' and r in COMPONENT_ROLES)]


def declare_labelings():
    for grid in LABELINGS:
        stage = stage_of(grid)
        cells, positions = on(grid), positions_of(grid)
        cells2 = cells_in_grid(p, grid, 2)
        for name, ways in CELL_PARTITIONS.items():
            stage.define('{p} %s determines the %s' % (name, grid.one), disjunction(*[determines(cells2, way, grid_label_of_cell(grid)) for way in ways(grid)]), p=POSITION)
        stage.define('{p},{x} determines the %s' % grid.one, determines(rows_if_several(), column_value(x), grid_label_of_row(p, grid)), p=cells, x=other_than(p))
        stage.define('{p},{x} is determined by the %s' % grid.one, determines(rows_if_several(), grid_label_of_row(p, grid), column_value(x)), p=cells, x=other_than(p))
        for role in roles_that_read_labels(grid):
            stage.define('{n} cells %s in the %s, proportion' % (role, grid), proportion_of_cells_in_role(n, grid, role), n=cells)
        stage.define('{n},{x} %s%s' % (grid.one, AGREES), agreement_under(n, x, grid), n=several_rows(positions), x=other_than(n))
        stage.define('{n} runs that alternate two %s, proportion' % grid.many, proportion_of_alternating_runs(n, grid), n=positions)
        stage.define('{n} %s distinct' % grid.many, label_cardinality(n, grid), n=cells)
        stage.define('{n} is a union of %s' % grid.many, is_union_of_classes(n, grid), n=cells)
        stage.define('{n} ring %s distinct' % grid.many, boundary_label_cardinality(n, grid), n=cells)
        lead = '{n} groups of %s ' % GROUPS
        stage.define(lead + '%s per group max' % grid.many, most_per_group(labels_per_group(n, grid)), n=cells)
        stage.define(lead + 'with one %s, proportion' % grid.one, proportion_single(labels_per_group(n, grid)), n=cells)
        stage.define(lead + '%s sets distinct' % grid.one, distinct_sets(labels_per_group(n, grid)), n=cells)
        some = lambda types: (lambda dom: (lambda c, e: dom(c, e) if c.rows and len(c.rows) <= MAX_ROWS else ()))(columns(types))
        stage.define('{b} the %s is unchanged by the reflection across it, proportion' % grid, proportion_of_axes_keeping(b, grid), b=some(('Axis', 'DiagAxis', 'Axis4')))
        stage.define('{b} the %s is unchanged by it, proportion' % grid, proportion_of_symmetries_keeping(b, grid), b=some(('D4', 'C4')))
        stage.define('{b} is a period of the %s, proportion' % grid, proportion_of_periods(b, grid), b=some(NUM))
        stage.define('rows vs the %s count' % grid.one, compare(row_total(), class_count(grid)))
        stage.define('{b} max vs the %s count' % grid.one, compare(maximum(value_list(b)), class_count(grid)), b=some(NUM))
        if grid.label != 'component' or grid.grid != 'input':  # the first version has the number of the input's components
            stage.define('{b} includes the %s count' % grid.one, contains(values(b), class_count(grid)), b=some(NUM))
        stage.define('{b} includes the count of some %s' % grid.one, intersects_set(values(b), class_sizes(grid)), b=some(NUM))
    for grid in LABELINGS:
        if grid.grid != 'output':
            continue
        cells2 = groups_in_grid(p, OUTPUT, 2)
        for name in GROUP_PROPERTIES:
            OWN_OUTPUT_STAGE.define('{p} groups of %s their %s determines their %s' % (GROUPS, name, grid.one), determines(groups_in_grid(p, OUTPUT, 2), group_property(name), unique_label(grid), 'defined'), p=POSITION)
    for grid in LABELINGS:
        if grid.grid != 'input':
            continue
        rows2 = rows_in_grid(p, INPUT, 2)
        OWN_OUTPUT_STAGE.define('{p} its %s determines the output color' % grid.one, guarded(grids_same_size(), determines(rows2, grid_label_of_row(p, grid), grid_label_of_row(p, OUTPUT))), p=POSITION)
        OWN_OUTPUT_STAGE.define('{p} its %s determines whether it changes' % grid.one, guarded(grids_same_size(), determines(rows2, grid_label_of_row(p, grid), changed_at(p))), p=POSITION)
        OWN_OUTPUT_STAGE.define('{p},{x} with the %s determines the output color' % grid.one, guarded(grids_same_size(), determines(rows2, pair(column_value(x), grid_label_of_row(p, grid)), grid_label_of_row(p, OUTPUT))), p=POSITION, x=other_than(p))
    for grid in COMPARABLE:
        if grid.grid == 'input':
            rows1 = rows_in_grid(p, OUTPUT, 1)
            TRAIN_EXAMPLES_STAGE.define('{p} its %s determines the output color across the examples' % grid.one, guarded(all_grids_same_size(MAX_ROWS_PER_EXAMPLE, True), over_examples(determines(rows1, grid_label_of_row(p, grid), grid_label_of_row(p, OUTPUT)), MAX_ROWS_PER_EXAMPLE, True)), p=POSITION)


@operator
def changed_at(c, e, r, v):
    u = r[e[v]]
    return c.gi[u[0]][u[2]] != c.go[u[0]][u[2]]


# ---- a table's own label columns of any equality type

def colored_cells(c, e, v, w):
    M = {}
    for r in c.rows:
        M.setdefault((r[e[v]][0], r[e[v]][2]), set()).add(str(r[e[w]]))
    return {k: next(iter(q)) for k, q in M.items()} if all(len(q) == 1 for q in M.values()) else None


@operator(memo=True)
def labeled_cell_measures(c, e, v, w):
    """{measure: value} of the cells of column v with the labels of column w, where a cell holds one label."""
    M = colored_cells(c, e, v, w)
    if M is None:
        return {}
    f = {'symmetry count': F().colored_symmetry_count(M)}
    by = {}
    for k, q in M.items():
        by.setdefault(q, set()).add(k)
    if 1 < len(by) <= 10:
        holes = {q: F().holes(s) for q, s in by.items()}
        f['a label lies in the holes of another'] = any(holes[u] and by[q] <= holes[u] for u in by for q in by if u != q)
        f['touching label pairs'] = len({frozenset((M[k], M[(k[0] + u, k[1] + q)])) for k in M for u, q in ((1, 0), (0, 1)) if (k[0] + u, k[1] + q) in M and M[(k[0] + u, k[1] + q)] != M[k]})
    if F().fills_box(set(M)):
        f['least period'] = F().least_period(M)
    return f


@operator
def labeled_cell_measure(c, e, v, w, name):
    return labeled_cell_measures(v, w)(c, e).get(name, ABSENT)


def all_cell_columns(c, e):
    if not c.rows or len(c.rows) > MAX_ROWS:
        return ()
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.cs]


# ---- groups by any column, and the measures of a group's shape

@operator(memo=True)
def groups_by(c, e, v, key):
    held = {}
    for r in c.rows:
        held.setdefault(str(r[e[key]]), set()).add((r[e[v]][0], r[e[v]][2]))
    return list(held.values()) if len(held) > 1 else ABSENT


@operator
def group_forms(c, e, items, eq):
    held = items(c, e)
    return ABSENT if held is ABSENT else list(Counter(eq.form(u) for u in held).values())


@function
def form_frequency_max(held):
    return max(held)


@function
def form_frequency_min(held):
    return min(held)


@function
def form_frequencies_all_distinct(held):
    return len(set(held)) == len(held) if len(held) > 1 else ABSENT


@function
def form_frequencies_all_same(held):
    return len(set(held)) == 1


@function
def form_top_two_ratio(held):
    return F().top2(held)


@operator
def groups_with_extreme_form(c, e, v, eq, extreme, grid):
    """The proportion of the groups whose shape is a most frequent, or a least frequent, shape among the components of the grid."""
    groups = F().grouped(c.cols, c.rows, e[v])
    if not groups or len(groups) > MAX_GROUPS or sum(len(u) for u in groups.values()) > MAX_CELLS:
        return ABSENT
    G = view(c, grid)
    held = Counter(eq.form(q) for q in G.component_set)
    want = extreme(held.values())
    return proportion(held.get(eq.form(u), 0) == want for u in groups.values() if u)


def group_key_columns(v):
    def dom(c, e):
        return [(i, col[0]) for i, col in enumerate(c.cols) if i != e[v] and col[1] in GROUP_KEYS]
    return dom


@operator
def set_measure(c, e, S, name):
    H, W = c.sizes[c.cs[c.cols[e[n]][0]][0]]
    return MEASURES[name](S, H, W)


MEASURES = {'cells': lambda S, H, W: len(S), 'components': lambda S, H, W: F().comps(S), 'symmetry count': lambda S, H, W: F().symmetry_count(S), 'enclosed regions': lambda S, H, W: F().enclosed_regions(S),
            'fills its bounding box': lambda S, H, W: F().fills_box(S), 'full lines': lambda S, H, W: F().full_lines(S, H, W)}


def declare_table_types():
    labels = columns(OTHER_LABELS)
    for name in ('symmetry count', 'a label lies in the holes of another', 'touching label pairs', 'least period'):
        OWN_STAGE.define('{n},{x} of a label column %s' % name, labeled_cell_measure(n, x, name), n=all_cell_columns, x=labels)
    for key in (g,):
        cells = all_cell_columns
        each = lambda name: over(groups_by(n, g), set_measure(name))
        lead = '{n} %s per group by {g} '
        OWN_STAGE.define(lead % 'cells' + 'min', minimum(each('cells')), n=cells, g=group_key_columns(n))
        OWN_STAGE.define(lead % 'cells' + 'max', maximum(each('cells')), n=cells, g=group_key_columns(n))
        OWN_STAGE.define(lead % 'components' + 'max', maximum(each('components')), n=cells, g=group_key_columns(n))
        OWN_STAGE.define(lead % 'symmetry count' + 'min', minimum(each('symmetry count')), n=cells, g=group_key_columns(n))
        OWN_STAGE.define(lead % 'enclosed regions' + 'max', maximum(each('enclosed regions')), n=cells, g=group_key_columns(n))
        OWN_STAGE.define(lead % 'fills its bounding box' + 'all', all_of(each('fills its bounding box')), n=cells, g=group_key_columns(n))
        OWN_STAGE.define(lead % 'full lines' + 'max', maximum(each('full lines')), n=cells, g=group_key_columns(n))
    for eq in EQUIVALENCES:
        OWN_STAGE.define('{n} shapes per group by {g}%s distinct' % eq.say, cardinality(group_forms(groups_by(n, g), eq)), n=all_cell_columns, g=group_key_columns(n))
        forms = group_forms(groups_of_table(n), eq)
        OWN_STAGE.define('{n} group shape%s frequency max' % eq.say, form_frequency_max(forms), n=all_cell_columns)
        OWN_STAGE.define('{n} group shape%s frequency min' % eq.say, form_frequency_min(forms), n=all_cell_columns)
        OWN_STAGE.define('{n} group shape%s frequencies all distinct' % eq.say, form_frequencies_all_distinct(forms), n=all_cell_columns)
        OWN_STAGE.define('{n} group shape%s frequencies all equal' % eq.say, form_frequencies_all_same(forms), n=all_cell_columns)
        OWN_STAGE.define('{n} group shape%s top-two count ratio' % eq.say, form_top_two_ratio(forms), n=all_cell_columns)
        for side in (INPUT, OUTPUT):
            stage = stage_of(side)
            on_grid = positions_of(side)
            stage.define('{n} groups of %s with the most frequent %s shape%s, proportion' % (GROUPS, side, eq.say), groups_with_extreme_form(n, eq, max, side), n=on_grid)
            stage.define('{n} groups of %s with the least frequent %s shape%s, proportion' % (GROUPS, side, eq.say), groups_with_extreme_form(n, eq, min, side), n=on_grid)


@function
def all_of(held):
    return all(held)


@operator(memo=True)
def groups_of_table(c, e, v):
    held = F().grouped(c.cols, c.rows, e[v])
    return list(held.values()) if held else ABSENT


declare_labelings()
declare_table_types()
