"""Model input layer: the role a table's values play in a grid of its example. A color may fill whole lines, mark single cells, or enclose another color;
a number may be one of the grid's counts; a direction, an axis or a symmetry may state how the input stands to itself; a cell may be a corner, the center
or a tip of its component, or a cell of the background next to the foreground or enclosed by it. A rule may hold of most rows, and a group's changed cells
may take colors from it, from around it, or from a line through them. A group may recur at another place of the input, hold a cell of another color, or
hide behind the foreground, and a run of cells may alternate two colors. Each feature gives the share of a table's values that play a role, so it keeps its
value under the symmetries of the square and a permutation of the colors.
"""
from collections import Counter

import outputs as OC
from grids import CELL_ROLES, labeling
from grammar import ABSENT, GRIDS, INPUT, OUTPUT, SCHEMAS as ALL_SCHEMAS, Var, operator, tails
from vocabulary import BASE_STAGE, GRID_STAGE, OWN_STAGE, columns, other_than

NUM = ('Nat', 'Int')
AXES = ('Axis', 'DiagAxis', 'Axis4')
DIRS = ('Dir', 'Dir8')
TURNS = ('D4', 'C4')
MAX_ROWS = 5000
MAX_GROUPS = 60  # the groups of a column up to which a feature looks at each one
MAX_TURNED = 20  # the groups up to which a feature looks for each one's images under the symmetries of the square
MAX_CELLS = 900
GROUPS = 'its Ident, Color and key columns'
COLOR_ROLES = ('that fill whole lines', 'that are single cells', 'of one component', 'that touch every edge', 'that touch no edge', 'that enclose another color',
               'enclosed by another color', 'that fill their boxes', 'of the largest foreground component', 'with the most components', 'with a symmetric cell set')
NEEDS_BACKGROUND = tuple(r for r in CELL_ROLES if 'background' in r) + ('at a crossing of two lines',)
COUNTS = ('the longer side of the input', 'the shorter side of the input', 'the input color count', 'the input foreground count',
          'the input foreground component count', 'the largest input foreground component', 'the count of some input color', 'the input full line count',
          'the input one-color component count')
ORIENT = (' the input is unchanged by the reflection across it, proportion', ' the input is unchanged by the reflection that swaps it, proportion',
          ' the input agrees with itself under the reflection across it, mean', ' the input agrees with itself under the reflection that swaps it, mean',
          ' the longer side of the input lies along it, proportion', ' the longer side of the input foreground lies along it, proportion',
          ' the input edge toward it is one color, proportion', ' the input foreground touches the edge toward it, proportion', ' the input is unchanged by it, proportion',
          ' the input agrees with itself under it, mean')
AGREES = ' agrees with the other rows of its value, proportion'

def share(flags):
    flags = list(flags)
    return round(sum(flags) / len(flags), 3) if flags else None


n, x, b = (Var(v) for v in 'n x b'.split())
FIRST = len(ALL_SCHEMAS)


def few_rows(c):
    return c.rows and len(c.rows) <= MAX_ROWS


def grid_view(c, grid):
    """The labeling of the grid of the context."""
    return labeling(c.array(grid))


def stage_of(grid):
    return OWN_STAGE if grid is INPUT else GRID_STAGE


def color_columns(c, e):
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[1] == 'Color'] if few_rows(c) else ()


def cell_columns_of(grid):
    """A column of cells in a frame of the grid's size, with a cell in the grid."""
    def dom(c, e):
        if not few_rows(c):
            return ()
        G = grid_view(c, grid)
        return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.cs and c.sizes.get(c.cs[col[0]][0]) == (G.H, G.W) and c.cs[col[0]][1] & G.cells]
    return dom


@operator
def proportion_of_colors_in_role(c, e, v, grid, role):
    G = grid_view(c, grid)
    colors = {r[e[v]] for r in c.rows} & set(G.by_label)
    return share(G.label_roles(y)[role] for y in colors) if colors else ABSENT


@operator
def proportion_of_cells_in_role(c, e, v, grid, role):
    G = grid_view(c, grid)
    if G.background is None and role in NEEDS_BACKGROUND:
        return ABSENT
    S = c.cs[c.cols[e[v]][0]][1] & G.cells
    return round(len(S & G.cell_roles[role]) / len(S), 3)


def declare_roles():
    for grid in GRIDS:
        stage = stage_of(grid)
        for role in COLOR_ROLES:
            stage.define('{x} colors %s in the %s, proportion' % (role, grid), proportion_of_colors_in_role(x, grid, role), x=color_columns)
        for role in CELL_ROLES:
            stage.define('{n} cells %s in the %s, proportion' % (role, grid), proportion_of_cells_in_role(n, grid, role), n=cell_columns_of(grid))


# ---- a rule that holds of most rows

def agreeing(keys, at):
    """The proportion of the rows whose value stays a most frequent value among the other rows that hold the same key. A row with no such other row does not agree, so a key
    that names each row claims nothing."""
    by = {}
    for y, o in zip(keys, at):
        by.setdefault(y, Counter())[o] += 1
    hits = 0
    for cnt in by.values():
        for o, q in cnt.items():
            if q > 1 and q - 1 >= max((w for u, w in cnt.items() if u != o), default=0):
                hits += q
    return round(hits / len(at), 3)


def row_value(what, c, e, v):
    i = e[v]
    in_grid = grid_view(c, INPUT if what == 'input color' else OUTPUT).cells
    if what == 'input color':
        return [c.gi[r[i][0]][r[i][2]] if (r[i][0], r[i][2]) in in_grid else None for r in c.rows]
    if what == 'output color':
        return [c.go[r[i][0]][r[i][2]] if (r[i][0], r[i][2]) in in_grid else None for r in c.rows]
    return [c.go[r[i][0]][r[i][2]] != c.gi[r[i][0]][r[i][2]] if (r[i][0], r[i][2]) in in_grid else None for r in c.rows]


@operator
def agreement_under_column(c, e, v, u, what, grids):
    return agreeing([str(r[e[u]]) for r in c.rows], row_value(what, c, e, v))


@operator
def agreement_under_other_columns(c, e, v, what, grids):
    others = [j for j in range(len(c.cols)) if j != e[v]]
    if len(others) < 2:
        return ABSENT
    return agreeing([str([r[j] for j in others]) for r in c.rows], row_value(what, c, e, v))


def position_columns_of(grid, same=False):
    """A Position column in a frame of the grid's size, the table having several rows."""
    def dom(c, e):
        if not few_rows(c) or len(c.rows) < 2 or (same and (len(c.gi), len(c.gi[0])) != (len(c.go), len(c.go[0]))):
            return ()
        G = grid_view(c, grid)
        return [(i, col[0]) for i, col in enumerate(c.cols) if col[1] == 'Position' and col[0] in c.cs and c.sizes.get(c.cs[col[0]][0]) == (G.H, G.W)]
    return dom


def declare_agreement():
    for what, grid, grids, stage, same in (('input color', INPUT, (INPUT,), OWN_STAGE, False), ('output color', OUTPUT, (OUTPUT,), GRID_STAGE, False), ('whether it changes', OUTPUT, (INPUT, OUTPUT), GRID_STAGE, True)):
        on = position_columns_of(grid, same)
        stage.define('{n},{x} %s%s' % (what, AGREES), agreement_under_column(n, x, what, grids), n=on, x=other_than(n))
        stage.define('{n} %s under its other columns%s' % (what, AGREES), agreement_under_other_columns(n, what, grids), n=on)


# ---- what a group holds and meets

def straight_runs(S):
    """The longest straight runs of at least three cells of the cell set S along its rows and its columns."""
    out = []
    for a, d in ((0, 1), (1, 0)):
        for u in S:
            if (u[0] - a, u[1] - d) not in S:
                run = [u]
                while (run[-1][0] + a, run[-1][1] + d) in S:
                    run.append((run[-1][0] + a, run[-1][1] + d))
                if len(run) > 2:
                    out.append(run)
    return out


def alternates(run, array):
    xs = [array[r][k] for r, k in run]
    return xs[0] != xs[1] and all(y == xs[i % 2] for i, y in enumerate(xs))


@operator
def proportion_of_runs_alternating(c, e, v, grid):
    S = c.cs[c.cols[e[v]][0]][1]
    if not S <= grid_view(c, grid).cells:
        return ABSENT
    runs = straight_runs(S)
    return share(alternates(run, c.array(grid)) for run in runs) if runs else ABSENT


@operator
def coordinate_parity_determines_color(c, e, v, grid):
    """Whether the parity of the cells' rows, or of their columns, gives one color at the odd lines and another at the even lines."""
    S, array = c.cs[c.cols[e[v]][0]][1], c.array(grid)
    if not S <= grid_view(c, grid).cells or len(S) <= 3:
        return ABSENT
    for a in (0, 1):
        at = ({array[u[0]][u[1]] for u in S if u[a] % 2 == 0}, {array[u[0]][u[1]] for u in S if u[a] % 2})
        if len(at[0]) == 1 and len(at[1]) == 1 and at[0] != at[1]:
            return True
    return False


def occurs_elsewhere_in(cells, G):
    """Whether the colored cells occur by a translation at another place of the grid."""
    return bool(OC.occurrences({u: G.array[u[0]][u[1]] for u in cells}, G) - {(0, 0)})


def occurs_elsewhere_under_d4(cells, G):
    """Whether an image of the colored cells under an element of D4 occurs on other cells of the grid."""
    M = {u: G.array[u[0]][u[1]] for u in cells}
    r1, k1 = max(u[0] for u in M) + 1, max(u[1] for u in M) + 1
    for d in OC.D4:
        im = {OC.cell_image(u, r1, k1, d): y for u, y in M.items()}
        if any({(u[0] + dr, u[1] + dk) for u in im} != cells for dr, dk in OC.occurrences(im, G)):
            return True
    return False


@operator(memo=True)
def groups_of_few_cells(c, e, v):
    """The groups of a column, where they are few enough to look at each one."""
    import features as F
    groups = c.grouped(e[v])
    if not groups or len(groups) > MAX_GROUPS or sum(len(y) for y in groups.values()) > MAX_CELLS:
        return ABSENT
    return groups


@operator(memo=True, reads=('input',))
def input_group_tests(c, e, v):
    """{test: its flags over the groups} of what the groups hold and meet in the input grid."""
    groups = groups_of_few_cells(v)(c, e)
    if groups is ABSENT:
        return ABSENT
    import features as F
    G, g = grid_view(c, INPUT), c.gi
    apart, touch, hidden, again, turned = [], [], [], [], []
    for group in groups.values():
        cells = group & G.cells
        if not cells:
            continue
        count = Counter(g[r][k] for r, k in cells)
        apart.append(len(cells) > 2 and len(count) > 1 and min(count.values()) == 1)
        near = {(r + a, k + d) for r, k in cells for a in (-1, 0, 1) for d in (-1, 0, 1)} & G.cells
        touch.append(any(len(G.component_of[u]) == 1 and g[u[0]][u[1]] not in count for u in near - cells))
        if G.foreground is not None and not F.fills_box(cells):
            rs, ks = [u[0] for u in cells], [u[1] for u in cells]
            hidden.append(all((r, k) in G.foreground for r in range(min(rs), max(rs) + 1) for k in range(min(ks), max(ks) + 1)))
        elif G.foreground is not None:
            hidden.append(False)
        if len(cells) > 1 and (G.background is None or set(count) != {G.background}):
            again.append(occurs_elsewhere_in(cells, G))
            if len(groups) <= MAX_TURNED:
                turned.append(occurs_elsewhere_under_d4(cells, G))
    return {'that hold one cell of a color apart from the rest': apart, 'that touch a lone cell of another color': touch, 'whose box is full of foreground beyond their own cells': hidden,
            'occurs elsewhere in the input': again, 'occurs elsewhere in the input up to rotation and reflection': turned}


@operator(reads=('input',))
def proportion_of_groups(c, e, v, test):
    held = input_group_tests(v)(c, e)
    if held is ABSENT or not held[test]:
        return ABSENT
    return share(held[test])


@operator(reads=('input',))
def group_shapes_vs_input_components(c, e, v, eq):
    import features as F
    groups = groups_of_few_cells(v)(c, e)
    parts = grid_view(c, INPUT).foreground_component_sets
    if groups is ABSENT or not parts:
        return ABSENT
    return F.setrel2({eq.form(y) for y in groups.values() if y}, {eq.form(q) for q in parts})


def columns_off_no_frame(c, e):
    """A column of cells with no value off its frame, the rows being few enough to read each one."""
    if not few_rows(c):
        return ()
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.cs and not any(min(r[i]) < 0 for r in c.rows)]


def columns_of_position_in(grid):
    def dom(c, e):
        if not few_rows(c):
            return ()
        H, W = c.size(grid)
        return [(i, tok) for i, tok in columns_off_no_frame(c, e) if c.cols[i][1] == 'Position' and c.sizes.get(c.cs[tok][0]) == (H, W)]
    return dom


def declare_groups():
    lead = '{n} groups of %s ' % GROUPS
    for eq in OC.EQUIVALENCES:
        OWN_STAGE.define('{n} group shapes%s vs the input foreground component shapes' % eq.say, group_shapes_vs_input_components(n, eq), n=columns_off_no_frame)
    on = columns_of_position_in(INPUT)
    for test in ('that hold one cell of a color apart from the rest', 'that touch a lone cell of another color', 'whose box is full of foreground beyond their own cells', 'occurs elsewhere in the input',
                 'occurs elsewhere in the input up to rotation and reflection'):
        OWN_STAGE.define(lead + test + ', proportion', proportion_of_groups(n, test), n=on)
    for grid in GRIDS:
        stage = stage_of(grid)
        on = columns_of_position_in(grid) if grid is INPUT else columns_of_position_in(grid)
        stage.define('{n} runs that alternate two colors in the %s, proportion' % grid, proportion_of_runs_alternating(n, grid), n=on)
        stage.define('{n} its row or column parity determines the %s color' % grid, coordinate_parity_determines_color(n, grid), n=on)


# ---- numbers, directions, axes and symmetries against the input grid

@operator(reads=('input',))
def contains_input_count(c, e, v, count):
    G = grid_view(c, INPUT)
    held = G.input_measures.get(count)
    return ABSENT if held is None else bool({r[e[v]] for r in c.rows} & held)


def agreement(array, d):
    """The proportion of the cells of the grid that hold the color of the same cell of its image under the symmetry d, or 0 where the image has another shape."""
    im = OC.image(array, d)
    if len(im) != len(array) or len(im[0]) != len(array[0]):
        return 0.0
    return round(sum(y == w for a, d_ in zip(array, im) for y, w in zip(a, d_)) / (len(array) * len(array[0])), 3)


def lines_of_values(c, e, v):
    return [y for y in {r[e[v]] for r in c.rows} if y in OC.REFLECTION_ACROSS]


@operator(reads=('input',))
def input_invariance(c, e, v, table, mean):
    lines = lines_of_values(c, e, v)
    if not lines:
        return ABSENT
    held = [agreement(c.gi, table[y]) for y in lines]
    return round(sum(held) / len(held), 3) if mean else share(y == 1 for y in held)


def straight_axes(c, e, v):
    return [y for y in {r[e[v]] for r in c.rows} if y in ('AXIS_V', 'AXIS_H')]


@operator(reads=('input',))
def input_longer_along(c, e, v):
    G, axes = grid_view(c, INPUT), straight_axes(c, e, v)
    return share((G.H > G.W) if y == 'AXIS_V' else (G.W > G.H) for y in axes) if axes else ABSENT


@operator(reads=('input',))
def foreground_longer_along(c, e, v):
    G, axes = grid_view(c, INPUT), straight_axes(c, e, v)
    if not axes or not G.foreground:
        return ABSENT
    h = max(u[0] for u in G.foreground) - min(u[0] for u in G.foreground)
    w = max(u[1] for u in G.foreground) - min(u[1] for u in G.foreground)
    return share((h > w) if y == 'AXIS_V' else (w > h) for y in axes)


def edge_directions(c, e, v):
    return [y for y in {r[e[v]] for r in c.rows} if y in OC.STEP and 0 in OC.STEP[y]]


@operator(reads=('input',))
def edge_is_one_color(c, e, v):
    edges = edge_directions(c, e, v)
    if not edges:
        return ABSENT
    g = c.gi
    line = lambda y: g[0] if y == 'DIR_T' else g[-1] if y == 'DIR_B' else [row[0] for row in g] if y == 'DIR_L' else [row[-1] for row in g]
    return share(len(set(line(y))) == 1 for y in edges)


@operator(reads=('input',))
def foreground_touches_edge(c, e, v):
    G, edges = grid_view(c, INPUT), edge_directions(c, e, v)
    if not edges or not G.foreground:
        return ABSENT
    return share(any((u[0] + OC.STEP[y][0], u[1] + OC.STEP[y][1]) not in G.cells for u in G.foreground) for y in edges)


def symmetry_values(c, e, v):
    return [y for y in {r[e[v]] for r in c.rows} if y in OC.D4]


@operator(reads=('input',))
def symmetry_invariance(c, e, v, mean):
    held = [agreement(c.gi, y) for y in symmetry_values(c, e, v)]
    if not held:
        return ABSENT
    return round(sum(held) / len(held), 3) if mean else share(y == 1 for y in held)


def with_few_rows(dom):
    def wrapped(c, e):
        return dom(c, e) if few_rows(c) else ()
    return wrapped


def declare_input_orientation():
    nums, axes, dirs, turns = (with_few_rows(columns(t)) for t in (NUM, AXES, DIRS, TURNS))
    for count in COUNTS:
        OWN_STAGE.define('{n} includes ' + count, contains_input_count(n, count), n=nums)
    OWN_STAGE.define('{b} the input is unchanged by the reflection across it, proportion', input_invariance(b, OC.Mapping(OC.REFLECTION_ACROSS), False), b=axes)
    OWN_STAGE.define('{b} the input is unchanged by the reflection that swaps it, proportion', input_invariance(b, OC.Mapping(OC.REFLECTION_SWAPPING), False), b=axes)
    OWN_STAGE.define('{b} the input agrees with itself under the reflection across it, mean', input_invariance(b, OC.Mapping(OC.REFLECTION_ACROSS), True), b=axes)
    OWN_STAGE.define('{b} the input agrees with itself under the reflection that swaps it, mean', input_invariance(b, OC.Mapping(OC.REFLECTION_SWAPPING), True), b=axes)
    OWN_STAGE.define('{b} the longer side of the input lies along it, proportion', input_longer_along(b), b=axes)
    OWN_STAGE.define('{b} the longer side of the input foreground lies along it, proportion', foreground_longer_along(b), b=axes)
    OWN_STAGE.define('{b} the input edge toward it is one color, proportion', edge_is_one_color(b), b=dirs)
    OWN_STAGE.define('{b} the input foreground touches the edge toward it, proportion', foreground_touches_edge(b), b=dirs)
    OWN_STAGE.define('{b} the input is unchanged by it, proportion', symmetry_invariance(b, False), b=turns)
    OWN_STAGE.define('{b} the input agrees with itself under it, mean', symmetry_invariance(b, True), b=turns)


# ---- the rows against components of the output, and what the changed cells take

@operator(reads=('output',))
def is_union_of_output_components(c, e, v):
    G = grid_view(c, OUTPUT)
    S = c.cs[c.cols[e[v]][0]][1] & G.cells
    return all(G.component_of[u] <= S for u in S)


@operator(reads=('output',))
def groups_are_output_components(c, e, v):
    import features as F
    G = grid_view(c, OUTPUT)
    groups = c.grouped(e[v])
    if not groups:
        return ABSENT
    return share(frozenset(y) in G.component_set for y in (u & G.cells for u in groups.values()) if y)


def box_columns_of_output_size(c, e):
    if not few_rows(c):
        return ()
    G = grid_view(c, OUTPUT)
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.box_sets() and c.box_sets()[col[0]][1] and len(c.box_sets()[col[0]][1]) <= 200 and c.sizes.get(c.box_sets()[col[0]][0]) == (G.H, G.W)]


@operator(reads=('output',))
def boxes_are_component_boxes(c, e, v):
    G = grid_view(c, OUTPUT)
    return share((t, G.H - 1 - d, l, G.W - 1 - r) in G.component_boxes for t, d, l, r in c.box_sets()[c.cols[e[v]][0]][1])


@operator(reads=('input', 'output'))
def changed_on_lines_through_input(c, e, v, kind):
    if (len(c.gi), len(c.gi[0])) != (len(c.go), len(c.go[0])):
        return ABSENT
    G = grid_view(c, OUTPUT)
    S = c.cs[c.cols[e[v]][0]][1] & G.cells
    moved = [u for u in S if c.go[u[0]][u[1]] != c.gi[u[0]][u[1]]]
    if not moved:
        return ABSENT
    by_row, by_col, down, up = grid_view(c, INPUT).line_labels
    go = c.go
    if kind == 'row or column':
        return share(go[r][k] in by_row[r] or go[r][k] in by_col[k] for r, k in moved)
    return share(go[r][k] in down[r - k] or go[r][k] in up[r + k] for r, k in moved)


@operator(memo=True, reads=('input', 'output'))
def group_paint_tests(c, e, v):
    """{test: its flags over the groups that hold a changed cell}."""
    import features as F
    if (len(c.gi), len(c.gi[0])) != (len(c.go), len(c.go[0])):
        return ABSENT
    groups = c.grouped(e[v])
    if not groups:
        return ABSENT
    G, Gi, gi, go = grid_view(c, OUTPUT), grid_view(c, INPUT), c.gi, c.go
    hold, near, one, nearest = [], [], [], []
    for y in groups.values():
        cells = y & G.cells
        taken = {go[u[0]][u[1]] for u in cells if go[u[0]][u[1]] != gi[u[0]][u[1]]}
        if not taken:
            continue
        around_ = {(r + a, k + d) for r, k in cells for a in (-1, 0, 1) for d in (-1, 0, 1)} & G.cells
        around_ -= cells
        hold.append(taken <= {gi[u[0]][u[1]] for u in cells})
        near.append(taken <= {gi[u[0]][u[1]] for u in around_})
        one.append(len(taken) == 1)
        if Gi.foreground is not None and len(groups) <= MAX_GROUPS:
            nearest.append(taken <= Gi.nearest_colors(cells))
    return dict(hold=hold, near=near, one=one, nearest=nearest)


@operator(reads=('input', 'output'))
def proportion_of_painting_groups(c, e, v, test):
    held = group_paint_tests(v)(c, e)
    if held is ABSENT or not held[test]:
        return ABSENT
    return share(held[test])


def declare_output_components():
    on = cell_columns_of(OUTPUT)
    position = lambda c, e: [(i, tok) for i, tok in on(c, e) if c.cols[i][1] == 'Position']
    lead = '{n} groups of %s ' % GROUPS
    GRID_STAGE.define('{n} is a union of components in the output', is_union_of_output_components(n), n=position)
    GRID_STAGE.define(lead + 'that are components in the output, proportion', groups_are_output_components(n), n=position)
    GRID_STAGE.define('{b} boxes that are the box of a component in the output, proportion', boxes_are_component_boxes(b), b=box_columns_of_output_size)
    GRID_STAGE.define('{n} changed cells whose output color lies on their row or column in the input, proportion', changed_on_lines_through_input(n, 'row or column'), n=position)
    GRID_STAGE.define('{n} changed cells whose output color lies on their diagonals in the input, proportion', changed_on_lines_through_input(n, 'diagonals'), n=position)
    GRID_STAGE.define(lead + 'whose changed cells take colors they hold, proportion', proportion_of_painting_groups(n, 'hold'), n=position)
    GRID_STAGE.define(lead + 'whose changed cells take colors around them, proportion', proportion_of_painting_groups(n, 'near'), n=position)
    GRID_STAGE.define(lead + 'whose changed cells take one color, proportion', proportion_of_painting_groups(n, 'one'), n=position)
    GRID_STAGE.define(lead + 'whose changed cells take the color of the nearest foreground around them, proportion', proportion_of_painting_groups(n, 'nearest'), n=position)


declare_roles()
declare_agreement()
declare_groups()
declare_input_orientation()
declare_output_components()
SCHEMAS = ALL_SCHEMAS[FIRST:]
WITH_OUTPUT = tails(SCHEMAS, lambda reads: 'output' in reads)  # the features of this module that read the train output
