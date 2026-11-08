"""Model input layer: the rules that compare a table's values with the train output of its example.

A number is compared with the output's extents, area, color count and foreground; a direction, an axis or a symmetry with how the output differs from the
input; a color with what the output does to that color; a cell set, a box or a group with the output's colors on it and with the changed cells; a shape with
where it occurs in the output. An orientation value or a color enters a feature only through such a relation, so a feature keeps its value under the
symmetries of the square and under a permutation of the colors.
"""
from collections import Counter

from grammar import ABSENT, INPUT, OUTPUT, Var, operator
from grids import bounding_interval, example, labeling
from vocabulary import (cardinality, cells, compare, contains, equal, is_subset, jaccard, labels, maximum, row_total, set_relation, set_relation_in, several, value_list, values as vocabulary_values, GROUPS, GRID_STAGE, INPUT_GRID_STAGE, MAX_CELLS, MAX_ROWS, BASE_STAGE, cell_columns, columns, is_function, other_than, proportion, guarded)

NUM = ('Nat', 'Int')
ORIENT_DIRS = ('Dir', 'Dir8', 'DiagDir')
ORIENT_AXES = ('Axis', 'DiagAxis', 'Axis4')
TURNS = ('D4', 'C4')
STEP = {'DIR_T': (-1, 0), 'DIR_B': (1, 0), 'DIR_L': (0, -1), 'DIR_R': (0, 1), 'DIAG_TL': (-1, -1), 'DIAG_TR': (-1, 1), 'DIAG_BL': (1, -1), 'DIAG_BR': (1, 1)}
LINE = {'DIR_T': 'AXIS_V', 'DIR_B': 'AXIS_V', 'DIR_L': 'AXIS_H', 'DIR_R': 'AXIS_H', 'DIAG_TL': 'DAXIS_DG', 'DIAG_BR': 'DAXIS_DG', 'DIAG_TR': 'DAXIS_AD', 'DIAG_BL': 'DAXIS_AD'}
REFLECTION_ACROSS = {'AXIS_V': 'D4_LR', 'AXIS_H': 'D4_TB', 'DAXIS_DG': 'D4_DG', 'DAXIS_AD': 'D4_AD'}  # the reflection across the line along an axis
REFLECTION_SWAPPING = {'AXIS_V': 'D4_TB', 'AXIS_H': 'D4_LR', 'DAXIS_DG': 'D4_AD', 'DAXIS_AD': 'D4_DG'}  # the reflection that swaps the two directions on an axis
D4 = ('D4_ID', 'D4_LR', 'D4_TB', 'D4_HT', 'D4_CW', 'D4_CC', 'D4_DG', 'D4_AD')
ALL_SIDES = ('the output area', 'the longer side of the output', 'the shorter side of the output', 'the output color count', 'the output foreground count',
             'the output foreground component count', 'the changed cell count', 'the changed component count')
OF_OUTPUT = tuple(s for s in ALL_SIDES if 'changed' not in s)

n, d, x, y, m, b = (Var(v) for v in 'n d x y m b'.split())


def image(g, s):
    """The grid g under the symmetry s, as a tuple of rows."""
    if s == 'D4_ID':
        return tuple(tuple(r) for r in g)
    if s == 'D4_LR':
        return tuple(tuple(r[::-1]) for r in g)
    if s == 'D4_TB':
        return tuple(tuple(r) for r in g[::-1])
    if s == 'D4_HT':
        return tuple(tuple(r[::-1]) for r in g[::-1])
    if s == 'D4_CW':
        return tuple(zip(*g[::-1]))
    if s == 'D4_CC':
        return tuple(zip(*g))[::-1]
    if s == 'D4_DG':
        return tuple(zip(*g))
    return tuple(r[::-1] for r in zip(*g))[::-1]  # D4_AD


def cell_image(u, H, W, s):
    """The cell u of an H by W grid under the symmetry s."""
    r, k = u
    return {'D4_ID': (r, k), 'D4_LR': (r, W - 1 - k), 'D4_TB': (H - 1 - r, k), 'D4_HT': (H - 1 - r, W - 1 - k), 'D4_CW': (k, H - 1 - r), 'D4_CC': (W - 1 - k, r),
            'D4_DG': (k, r), 'D4_AD': (W - 1 - k, H - 1 - r)}[s]


def cmp(u, v):
    return '<' if u < v else '=' if u == v else '>'


def measures(c):
    """The input and the train output of the example of context c."""
    return example(c.gi, c.go)


def extent(S):
    return bounding_interval(S)


def reach(box, step):
    """How far a box (first row, last row, first column, last column) goes toward a step, the larger the farther; None for no axis."""
    r0, r1, k0, k1 = box
    parts = []
    if step[0]:
        parts.append(r1 if step[0] > 0 else -r0)
    if step[1]:
        parts.append(k1 if step[1] > 0 else -k0)
    return parts


def margin(box, step, H, W):
    r0, r1, k0, k1 = box
    return {(-1, 0): r0, (1, 0): H - 1 - r1, (0, -1): k0, (0, 1): W - 1 - k1}.get(step)


# ---- the rows' values

def values(c, e, v):
    i = e[v]
    held = c.memo.get(('values', i))
    if held is None:
        held = c.memo['values', i] = {r[i] for r in c.rows}
    return held


def has_rows(dom):
    def wrapped(c, e):
        return dom(c, e) if c.rows else ()
    return wrapped


# ---- numbers against the output's measures

@operator(reads=('output',))
def grid_measure(c, e, name):
    v = measures(c).measures.get(name)
    return ABSENT if v is None else v


def declare_counts():
    for s in ALL_SIDES:
        GRID_STAGE.define('rows vs ' + s, compare(row_total(), grid_measure(s)))
        GRID_STAGE.define('{n} max vs ' + s, compare(maximum(value_list(n)), grid_measure(s)), n=has_rows(columns(NUM)))
        GRID_STAGE.define('{n} includes ' + s, contains(several(vocabulary_values(n)), grid_measure(s)), n=has_rows(columns(NUM)))
        GRID_STAGE.define('{n} distinct vs ' + s, compare(cardinality(labels(n)), grid_measure(s)), n=has_rows(columns(('Ident',))))


# ---- orientations against how the output differs from the input

@operator(reads=('input', 'output'))
def directional_extent(c, e, v, kind):
    """The share of the directions of a column along which the output's foreground, or the changed cells, go past the input's foreground, or its center moves."""
    G = measures(c)
    steps = [STEP[u] for u in values(c, e, v)]
    if kind == 'changed cells reach':
        return proportion(all(a_ > b_ for a_, b_ in zip(reach(G.changed_box, s), reach(G.input.foreground_box, s))) for s in steps) if G.changed_box and G.input.foreground_box else ABSENT
    if not (G.same and G.output.foreground_box and G.input.foreground_box):
        return ABSENT
    if kind == 'moves':
        center_o, center_i = (G.output.foreground_box[0] + G.output.foreground_box[1], G.output.foreground_box[2] + G.output.foreground_box[3]), (G.input.foreground_box[0] + G.input.foreground_box[1], G.input.foreground_box[2] + G.input.foreground_box[3])
        delta = (center_o[0] - center_i[0], center_o[1] - center_i[1])
        return proportion(all((not s[a_]) or (delta[a_] * s[a_] > 0) for a_ in (0, 1)) for s in steps)
    return proportion(all(a_ > b_ for a_, b_ in zip(reach(G.output.foreground_box, s), reach(G.input.foreground_box, s))) for s in steps)


@operator(reads=('output',))
def stable_under_gravity(c, e, v):
    """The share of the directions along a row or a column toward which each cell of the output's foreground has the foreground or the grid's edge next to it."""
    G = measures(c)
    if not G.output.foreground:
        return ABSENT
    flags = []
    for u in values(c, e, v):
        s = STEP[u]
        if 0 in s:
            flags.append(all((k[0] + s[0], k[1] + s[1]) in G.output.foreground or (k[0] + s[0], k[1] + s[1]) not in G.output.cells for k in G.output.foreground))
    return proportion(flags) if flags else ABSENT


def lines_of(c, e, v):
    return {LINE.get(u, u) for u in values(c, e, v)}


@operator(reads=('input', 'output'))
def extent_along(c, e, v):
    G = measures(c)
    straight = lines_of(c, e, v) & {'AXIS_V', 'AXIS_H'}
    if not straight:
        return ABSENT
    seen = {cmp(G.output.H, G.input.H) if u == 'AXIS_V' else cmp(G.output.W, G.input.W) for u in straight}
    return next(iter(seen)) if len(seen) == 1 else 'mixed'


@operator(reads=('output',))
def reflection_keeps_output(c, e, v, reflect):
    G = measures(c)
    usable = [u for u in lines_of(c, e, v) if u in ('AXIS_V', 'AXIS_H') or G.output.H == G.output.W]
    return proportion(image(G.go, reflect[u]) == G.output.as_tuple for u in usable) if usable else ABSENT


@operator(reads=('input', 'output'))
def symmetry_maps_grid(c, e, v, which):
    G = measures(c)
    return proportion(image(G.gi if which == 'input' else G.go, u) == G.output.as_tuple for u in values(c, e, v))


@operator(reads=('input', 'output'))
def symmetry_maps_foreground(c, e, v):
    import features as F
    G = measures(c)
    if not (G.input.foreground and G.output.foreground):
        return ABSENT
    want = F.normalized(G.output.foreground)
    return proportion(F.normalized({cell_image(u, G.input.H, G.input.W, s) for u in G.input.foreground}) == want for s in values(c, e, v))


def translations_of(c, e, v):
    return {(r[e[v]][0], r[e[v]][2]) for r in c.rows}


@operator(reads=('input', 'output'))
def contains_foreground_translation(c, e, v):
    import features as F
    G = measures(c)
    if not (G.same and G.input.foreground and G.output.foreground and len(G.input.foreground) == len(G.output.foreground) and F.normalized(G.input.foreground) == F.normalized(G.output.foreground)):
        return ABSENT
    return (min(u[0] for u in G.output.foreground) - min(u[0] for u in G.input.foreground), min(u[1] for u in G.output.foreground) - min(u[1] for u in G.input.foreground)) in translations_of(c, e, v)


@operator(reads=('input', 'output'))
def translation_maps_foreground(c, e, v):
    G = measures(c)
    if not (G.same and G.input.foreground and G.output.foreground):
        return ABSENT
    return proportion({(u[0] + a_, u[1] + b_) for u in G.input.foreground} == G.output.foreground for a_, b_ in translations_of(c, e, v))


@operator(reads=('input', 'output'))
def number_equals_measure(c, e, v, u, kind):
    """The share of a row's pairs of an orientation and a number in which the number is the output's extent along it, or the margin of the output's foreground or the changed cells toward it."""
    G = measures(c)
    pairs = {(r[e[v]], r[e[u]]) for r in c.rows}
    if kind == 'extent':
        return proportion((G.output.H if LINE.get(a_, a_) == 'AXIS_V' else G.output.W) == b_ for a_, b_ in pairs)
    box = G.output.foreground_box if kind == 'foreground' else G.changed_box
    return proportion(margin(box, STEP[a_], G.output.H, G.output.W) == b_ for a_, b_ in pairs) if box else ABSENT


def declare_orientations():
    dirs, lines, turns = has_rows(columns(ORIENT_DIRS)), has_rows(columns(ORIENT_DIRS + ORIENT_AXES)), has_rows(columns(TURNS))
    GRID_STAGE.define('{d} the output foreground moves toward it, proportion', directional_extent(d, 'moves'), d=dirs)
    GRID_STAGE.define('{d} the output foreground reaches past the input foreground toward it, proportion', directional_extent(d, 'output reaches'), d=dirs)
    GRID_STAGE.define('{d} the changed cells reach past the input foreground toward it, proportion', directional_extent(d, 'changed cells reach'), d=dirs)
    GRID_STAGE.define('{d} the output foreground is stable under gravity toward it, proportion', stable_under_gravity(d), d=dirs)
    GRID_STAGE.define('{d} the output extent along it vs the input', extent_along(d), d=lines)
    GRID_STAGE.define('{d} the output is unchanged by the reflection across it, proportion', reflection_keeps_output(d, Mapping(REFLECTION_ACROSS)), d=lines)
    GRID_STAGE.define('{d} the output is unchanged by the reflection that swaps it, proportion', reflection_keeps_output(d, Mapping(REFLECTION_SWAPPING)), d=lines)
    GRID_STAGE.define('{d} maps the input to the output, proportion', symmetry_maps_grid(d, 'input'), d=turns)
    GRID_STAGE.define('{d} keeps the output, proportion', symmetry_maps_grid(d, 'output'), d=turns)
    GRID_STAGE.define('{d} maps the input foreground shape to the output foreground shape, proportion', symmetry_maps_foreground(d), d=turns)
    offsets = has_rows(columns(('Offset',)))
    GRID_STAGE.define('{d} includes the translation of the foreground into the output', contains_foreground_translation(d), d=offsets)
    GRID_STAGE.define('{d} translates the input foreground onto the output foreground, proportion', translation_maps_foreground(d), d=offsets)
    both_axis = has_rows(columns(('Axis', 'Dir')))
    GRID_STAGE.define('{d},{n} is the output extent along it, proportion', number_equals_measure(d, n, 'extent'), d=both_axis, n=columns(NUM))
    edges = has_rows(columns(('Dir',)))
    GRID_STAGE.define('{d},{n} is the output foreground margin toward it, proportion', number_equals_measure(d, n, 'foreground'), d=edges, n=columns(NUM))
    GRID_STAGE.define('{d},{n} is the changed cells margin toward it, proportion', number_equals_measure(d, n, 'changed'), d=edges, n=columns(NUM))


class Mapping(dict):
    """A map in a term, which has a name in its tree."""

    def __hash__(self):
        return hash(tuple(sorted(self.items())))


# ---- colors against what the output does to them

def line_colors(g):
    """The sequence of colors along each axis of the grid g on which every line holds one color."""
    out = []
    if all(len(set(row)) == 1 for row in g):
        out.append([row[0] for row in g])
    if all(len({row[k] for row in g}) == 1 for k in range(len(g[0]))):
        out.append(list(g[0]))
    return out


def collapse_runs(sequence):
    """The sequence with each run of one value as one value."""
    return [u for i, u in enumerate(sequence) if i == 0 or sequence[i - 1] != u]


@operator(reads=('output',))
def is_set_of_line_labels(c, e, v):
    sequences = line_colors(measures(c).go)
    return any(values(c, e, v) == set(q) for q in sequences) if sequences else ABSENT


@operator(reads=('output',))
def orders_line_colors(c, e, v, u):
    sequences = line_colors(measures(c).go)
    if not sequences:
        return ABSENT
    by = {}
    for r in c.rows:
        by.setdefault(r[e[v]], set()).add(r[e[u]])
    if not (all(len(w) == 1 for w in by.values()) and len(by) > 1):
        return ABSENT
    held = [next(iter(w)) for w in by.values()]
    if len(set(held)) != len(held):
        return ABSENT
    ranked = [k for k, _ in sorted(((k, next(iter(w))) for k, w in by.items()), key=lambda t: t[1])]
    return any(collapse_runs(q) in (ranked, ranked[::-1]) for q in sequences)


@operator(reads=('output',))
def output_coverage(c, e, v):
    G = measures(c)
    return round(sum(G.output.counts[k] for k in values(c, e, v)) / (G.output.H * G.output.W), 3)


def cells_of_colors_in_output(c, e, v):
    G = measures(c)
    return {u for k in values(c, e, v) for u in G.output.positions.get(k, ())}


def cells_of_colors_in_input(c, e, v):
    colors = values(c, e, v)
    return {(r, k) for r, row in enumerate(c.gi) for k, u in enumerate(row) if u in colors}


@operator(reads=('output',))
def output_component_count(c, e, v):
    import features as F
    cells = cells_of_colors_in_output(c, e, v)
    return F.comps(cells) if cells else 0


@operator(reads=('input', 'output'))
def component_count_vs_input(c, e, v):
    import features as F
    cells = cells_of_colors_in_output(c, e, v)
    cells_i = cells_of_colors_in_input(c, e, v)
    return cmp(F.comps(cells) if cells else 0, F.comps(cells_i) if cells_i else 0)


@operator(reads=('input', 'output'))
def count_change_from_input(c, e, v):
    G = measures(c)
    signs = {cmp(G.output.counts[k], G.input.counts[k]) for k in values(c, e, v)}
    return next(iter(signs)) if len(signs) == 1 else 'mixed'


@operator(reads=('input', 'output'))
def set_relation_to_changed(c, e, v, cells_of):
    import features as F
    G = measures(c)
    return F.setrel(cells_of(c, e, v), G.changed, G.output.cells) if G.changed else ABSENT


@operator(reads=('output',))
def rows_per_value_equal_output_counts(c, e, v):
    G = measures(c)
    return proportion(q == G.output.counts[k] for k, q in Counter(r[e[v]] for r in c.rows).items())


@operator(reads=('output',))
def number_equals_output_count(c, e, v, u):
    G = measures(c)
    return proportion(q == G.output.counts[k] for k, q in {(r[e[v]], r[e[u]]) for r in c.rows})


@operator(reads=('output',))
def output_count_monotonicity(c, e, v, u):
    G = measures(c)
    pairs = {(r[e[v]], r[e[u]]) for r in c.rows}
    if not (len({q for _, q in pairs}) > 1 and len({k for k, _ in pairs}) > 1):
        return ABSENT
    ordered = sorted({(q, G.output.counts[k]) for k, q in pairs})
    up = all(a_[1] <= b_[1] for a_, b_ in zip(ordered, ordered[1:]) if a_[0] < b_[0]) and all(a_[1] == b_[1] for a_, b_ in zip(ordered, ordered[1:]) if a_[0] == b_[0])
    down = all(a_[1] >= b_[1] for a_, b_ in zip(ordered, ordered[1:]) if a_[0] < b_[0]) and all(a_[1] == b_[1] for a_, b_ in zip(ordered, ordered[1:]) if a_[0] == b_[0])
    return 'rises' if up else 'falls' if down else 'neither'


@operator(reads=('output',))
def groups_per_color_equal_output_counts(c, e, v, u):
    G = measures(c)
    ids = {}
    for r in c.rows:
        ids.setdefault(r[e[v]], set()).add(str(r[e[u]]))
    return proportion(len(w) == G.output.counts[k] for k, w in ids.items())


def declare_colors():
    colors = has_rows(columns(('Color',)))
    for s in ('the output color count', 'the longer side of the output', 'the shorter side of the output', 'the output area'):
        GRID_STAGE.define('{x} distinct vs ' + s, compare(cardinality(vocabulary_values(x)), grid_measure(s)), x=colors)
    GRID_STAGE.define('{x} is the set of output line colors', is_set_of_line_labels(x), x=colors)
    GRID_STAGE.define('{x},{n} orders the output lines', orders_line_colors(x, n), x=colors, n=columns(NUM))
    GRID_STAGE.define('{x} includes the most frequent output color', contains_grid_extreme_color(x, OUTPUT, max), x=colors)
    GRID_STAGE.define('{x} includes the least frequent output color', contains_grid_extreme_color(x, OUTPUT, min), x=colors)
    GRID_STAGE.define('{x} covers the output, proportion', output_coverage(x), x=colors)
    GRID_STAGE.define('{x} output cell components', output_component_count(x), x=colors)
    GRID_STAGE.define('{x} output cell components vs the input', component_count_vs_input(x), x=colors)
    GRID_STAGE.define('{x} vs the colors the output adds', set_relation(vocabulary_values(x), nonempty_set(added_labels())), x=colors)
    GRID_STAGE.define('{x} vs the colors the output drops', set_relation(vocabulary_values(x), nonempty_set(dropped_labels())), x=colors)
    GRID_STAGE.define('{x} output count vs the input count', count_change_from_input(x), x=colors)
    GRID_STAGE.define('{x} vs the colors the changed cells had', set_relation(vocabulary_values(x), nonempty_set(changed_from())), x=colors)
    GRID_STAGE.define('{x} vs the colors the changed cells take', set_relation(vocabulary_values(x), nonempty_set(changed_to())), x=colors)
    GRID_STAGE.define('{x} input cells vs the changed cells', set_relation_to_changed(x, NamedFunction(cells_of_colors_in_input)), x=colors)
    GRID_STAGE.define('{x} output cells vs the changed cells', set_relation_to_changed(x, NamedFunction(cells_of_colors_in_output)), x=colors)
    GRID_STAGE.define('{x} rows per value agree with the output color counts, proportion', rows_per_value_equal_output_counts(x), x=colors)
    GRID_STAGE.define('{x},{n} is the output count of the color, proportion', number_equals_output_count(x, n), x=colors, n=columns(NUM))
    GRID_STAGE.define('{x},{n} output count as it rises', output_count_monotonicity(x, n), x=colors, n=columns(NUM))
    GRID_STAGE.define('{x},{n} groups per color are the output counts, proportion', groups_per_color_equal_output_counts(x, n), x=colors, n=columns(('Ident',)))


class NamedFunction:
    """A function in a term, which has a name in its tree."""

    def __init__(self, fn):
        self.fn, self.name = fn, fn.__name__

    def __call__(self, *a):
        return self.fn(*a)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return isinstance(other, NamedFunction) and self.name == other.name

    def __repr__(self):
        return self.name


# ---- a cell set against the colors under it and the changed cells

def cells_clipped_to_grid(c, e, v, grid):
    """The cells of a column that lie in the grid."""
    H, W = c.size(grid)
    return {u for u in c.cs[c.cols[e[v]][0]][1] if 0 <= u[0] < H and 0 <= u[1] < W}


@operator(reads=('output',))
def color_cardinality_under(c, e, v):
    g = c.go
    return len({g[r][k] for r, k in cells_clipped_to_grid(c, e, v, OUTPUT)})


@operator(reads=('output',))
def is_union_of_color_classes(c, e, v):
    G, S = measures(c), cells_clipped_to_grid(c, e, v, OUTPUT)
    colors = {G.go[r][k] for r, k in S}
    return all(sum(1 for u in S if G.go[u[0]][u[1]] == q) == G.output.counts[q] for q in colors)


@operator
def outer_boundary_color_cardinality(c, e, v, grid):
    g, S = c.array(grid), cells_clipped_to_grid(c, e, v, grid)
    H, W = c.size(grid)
    border_distance = {(r + a_, k + b_) for r, k in S for a_ in (-1, 0, 1) for b_ in (-1, 0, 1) if 0 <= r + a_ < H and 0 <= k + b_ < W} - S
    return len({g[r][k] for r, k in border_distance}) if border_distance else ABSENT


def requires_changed_cells(fn):
    """An operator that holds where the example has changed cells: fn(G, S, c, e, *args) of the measures and the column's cell set."""
    def wrapped(c, e, v, *args):
        G = measures(c)
        return fn(G, cells_clipped_to_grid(c, e, v, OUTPUT), *args) if G.changed else ABSENT
    wrapped.__name__ = fn.__name__
    return operator(wrapped, reads=('input', 'output'))


@requires_changed_cells
def changed_within_chebyshev_one(G, S):
    return proportion(any((u[0] + a_, u[1] + b_) in S for a_ in (-1, 0, 1) for b_ in (-1, 0, 1)) for u in G.changed)


@requires_changed_cells
def changed_on_shared_lines(G, S):
    rows, cols = {u[0] for u in S}, {u[1] for u in S}
    return proportion(u[0] in rows or u[1] in cols for u in G.changed)


@requires_changed_cells
def on_lines_of_changed_cells(G, S):
    rows, cols = {u[0] for u in G.changed}, {u[1] for u in G.changed}
    return proportion(u[0] in rows or u[1] in cols for u in S)


@requires_changed_cells
def changed_in_bounding_box(G, S):
    r0, r1, k0, k1 = extent(S)
    return proportion(r0 <= u[0] <= r1 and k0 <= u[1] <= k1 for u in G.changed)


def line_spans(S):
    span = {}
    for u in S:
        for key, at in (((0, u[0]), u[1]), ((1, u[1]), u[0]), ((2, u[0] - u[1]), u[0]), ((3, u[0] + u[1]), u[0])):
            lo, hi = span.get(key, (at, at))
            span[key] = (min(lo, at), max(hi, at))
    return span


@requires_changed_cells
def changed_between_on_row_or_column(G, S):
    span = line_spans(S)
    inside = lambda key, at: key in span and span[key][0] < at < span[key][1]
    return proportion(inside((0, u[0]), u[1]) or inside((1, u[1]), u[0]) for u in G.changed)


@requires_changed_cells
def changed_between_on_diagonal(G, S):
    span = line_spans(S)
    inside = lambda key, at: key in span and span[key][0] < at < span[key][1]
    return proportion(inside((2, u[0] - u[1]), u[0]) or inside((3, u[0] + u[1]), u[0]) for u in G.changed)


@requires_changed_cells
def changed_in_holes(G, S):
    import features as F
    hole = F.holes(S)
    return proportion(u in hole for u in G.changed)


def chebyshev_distances(S, grid):
    """{cell of the grid: the least count of steps, each to one of the eight neighbors, from S to it}."""
    out = {u: 0 for u in S}
    layer, k = list(S), 0
    while layer:
        k += 1
        ahead = []
        for r, q in layer:
            for a_ in (-1, 0, 1):
                for b_ in (-1, 0, 1):
                    y_ = (r + a_, q + b_)
                    if y_ in grid and y_ not in out:
                        out[y_] = k
                        ahead.append(y_)
        layer = ahead
    return out


@requires_changed_cells
def farthest_changed_distance(G, S):
    away = chebyshev_distances(S, G.output.cells)
    return max(away[u] for u in G.changed)


@operator(reads=('input', 'output'))
def reflection_across_line_maps_input_to_output(c, e, v):
    G, S = measures(c), cells_clipped_to_grid(c, e, v, OUTPUT)
    if not (G.same and G.input.foreground and (len({u[0] for u in S}) == 1 or len({u[1] for u in S}) == 1) and len(S) > 1):
        return ABSENT
    across_row = len({u[0] for u in S}) == 1
    line = next(iter(S))[0 if across_row else 1]
    flags = []
    for r, k in G.input.foreground:
        im = (2 * line - r, k) if across_row else (r, 2 * line - k)
        if im in G.output.cells and im != (r, k):
            flags.append(G.go[im[0]][im[1]] == G.gi[r][k])
    return proportion(flags) if flags else ABSENT


@operator(memo=True)
def cells_by_group(c, e, v, grid):
    """The cell sets of the groups of a column, in the grid, or ABSENT where the table has no group."""
    import features as F
    groups = c.grouped(e[v])
    if not groups:
        return ABSENT
    H, W = c.size(grid)
    cells = [{u for u in g if 0 <= u[0] < H and 0 <= u[1] < W} for g in groups.values()]
    cells = [g for g in cells if g]
    return cells if cells else ABSENT


@operator(memo=True)
def colors_by_group(c, e, v, grid):
    cells = cells_by_group(v, grid)(c, e)
    if cells is ABSENT:
        return ABSENT
    g = c.array(grid)
    return [frozenset(g[r][k] for r, k in u) for u in cells]


@operator
def max_colors_per_group(c, e, v, grid):
    sets = colors_by_group(v, grid)(c, e)
    return ABSENT if sets is ABSENT else max(len(u) for u in sets)


@operator
def proportion_with_unique_color(c, e, v, grid):
    sets = colors_by_group(v, grid)(c, e)
    return ABSENT if sets is ABSENT else proportion(len(u) == 1 for u in sets)


@operator
def distinct_color_sets(c, e, v, grid):
    sets = colors_by_group(v, grid)(c, e)
    return ABSENT if sets is ABSENT else len(set(sets))


@operator(reads=('input', 'output'))
def groups_with_changed_cells(c, e, v, whole):
    G = measures(c)
    cells = cells_by_group(v, OUTPUT)(c, e)
    if cells is ABSENT or not G.changed:
        return ABSENT
    return proportion(g <= G.changed for g in cells) if whole else proportion(bool(g & G.changed) for g in cells)


def declare_cells():
    cells = cell_columns(OUTPUT)
    GRID_STAGE.define('{n} output colors distinct', color_cardinality_under(n), n=cells)
    GRID_STAGE.define('{n} is a union of output colors', is_union_of_color_classes(n), n=cells)
    GRID_STAGE.define('{n} changed cells within Chebyshev distance 1, proportion', changed_within_chebyshev_one(n), n=cells)
    GRID_STAGE.define('{n} changed cells on its rows or columns, proportion', changed_on_shared_lines(n), n=cells)
    GRID_STAGE.define('{n} cells with a changed cell on their rows or columns, proportion', on_lines_of_changed_cells(n), n=cells)
    GRID_STAGE.define('{n} changed cells inside its bounding box, proportion', changed_in_bounding_box(n), n=cells)
    GRID_STAGE.define('{n} changed cells between two of its cells on a line, proportion', changed_between_on_row_or_column(n), n=cells)
    GRID_STAGE.define('{n} changed cells between two of its cells on a diagonal, proportion', changed_between_on_diagonal(n), n=cells)
    GRID_STAGE.define('{n} changed cells in its holes, proportion', changed_in_holes(n), n=cells)
    GRID_STAGE.define('{n} greatest distance from a changed cell', farthest_changed_distance(n), n=cells)
    GRID_STAGE.define('{n} reflection across it maps the input onto the output, proportion', reflection_across_line_maps_input_to_output(n), n=cells)
    lead = '{n} groups of %s ' % GROUPS
    GRID_STAGE.define(lead + 'that change, proportion', groups_with_changed_cells(n, False), n=cells)
    GRID_STAGE.define(lead + 'that change wholly, proportion', groups_with_changed_cells(n, True), n=cells)
    for grid, stage in ((OUTPUT, GRID_STAGE), (INPUT, BASE_STAGE)):
        on = cell_columns(grid)
        stage.define('{n} outer boundary %s colors distinct' % grid, outer_boundary_color_cardinality(n, grid), n=on)
        stage.define(lead + '%s colors per group max' % grid, max_colors_per_group(n, grid), n=on)
        stage.define(lead + 'with one %s color, proportion' % grid, proportion_with_unique_color(n, grid), n=on)
        stage.define(lead + '%s color sets distinct' % grid, distinct_color_sets(n, grid), n=on)


# ---- boxes against the output

def crop(g, r0, r1, k0, k1):
    return tuple(tuple(row[k0:k1 + 1]) for row in g[r0:r1 + 1])


def crop_tests(boxes_, G):
    """(a span of the input crops to the output, its crop does up to a symmetry, its crop maps onto the output by a function of the colors), over the spans, each
    as first row, last row, first column, last column."""
    target = G.output.as_tuple
    exact = turned = mapped = False
    for r0, r1, k0, k1 in boxes_:
        if not (0 <= r0 <= r1 < G.input.H and 0 <= k0 <= k1 < G.input.W):
            continue
        u = crop(G.gi, r0, r1, k0, k1)
        if (len(u), len(u[0])) == (G.output.H, G.output.W):
            exact = exact or u == target
            pairs = {(a_, b_) for x_, y_ in zip(u, target) for a_, b_ in zip(x_, y_)}
            mapped = mapped or len({a_ for a_, _ in pairs}) == len(pairs)
        if {len(u), len(u[0])} == {G.output.H, G.output.W} and not turned:
            turned = any(image(u, s) == target for s in D4)
    return exact, turned, mapped


def framed_box_columns(c, e):
    """A Box column in a grid's frame, with few enough boxes to read each one."""
    import features as F
    if not c.rows:
        return ()
    return [(i, column[0]) for i, column in enumerate(c.cols) if column[0] in c.box_sets() and c.box_sets()[column[0]][1] and len(c.box_sets()[column[0]][1]) <= 200]


def closed_intervals_of_boxes(c, e, v):
    fr, B = c.box_sets()[c.cols[e[v]][0]]
    H, W = c.sizes[fr]
    return fr, H, W, {(t, H - 1 - d_, l, W - 1 - r) for t, d_, l, r in B}


@operator(reads=('input', 'output'))
def crop_of_some_box(c, e, v, which):
    fr, _, _, boxes_ = closed_intervals_of_boxes(c, e, v)
    return crop_tests(boxes_, measures(c))[which] if fr == 'input' else ABSENT


@operator(memo=True, reads=('output',))
def boxes_clipped_to_output(c, e, v):
    """The boxes of a column in a frame of the output's size, each cut to that frame."""
    G = measures(c)
    _, H, W, boxes_ = closed_intervals_of_boxes(c, e, v)
    if (H, W) != (G.output.H, G.output.W):
        return ABSENT
    real = [(max(a_, 0), min(b_, H - 1), max(u, 0), min(w, W - 1)) for a_, b_, u, w in boxes_]
    real = [s for s in real if s[0] <= s[1] and s[2] <= s[3]]
    if not real or sum((s[1] - s[0] + 1) * (s[3] - s[2] + 1) for s in real) > 20000:
        return ABSENT
    return real


@operator(memo=True, reads=('output',))
def colors_in_boxes(c, e, v):
    real = boxes_clipped_to_output(v)(c, e)
    if real is ABSENT:
        return ABSENT
    return [{c.go[r][k] for r in range(s[0], s[1] + 1) for k in range(s[2], s[3] + 1)} for s in real]


@operator(reads=('output',))
def proportion_of_boxes_with_unique_color(c, e, v):
    held = colors_in_boxes(v)(c, e)
    return ABSENT if held is ABSENT else proportion(len(u) == 1 for u in held)


@operator(reads=('output',))
def color_cardinality_in_boxes(c, e, v):
    held = colors_in_boxes(v)(c, e)
    return ABSENT if held is ABSENT else len(set().union(*held))


@operator(reads=('input', 'output'))
def changed_cells_and_boxes(c, e, v, kind):
    G, real = measures(c), boxes_clipped_to_output(v)(c, e)
    if real is ABSENT or not G.changed:
        return ABSENT
    ch = G.changed
    if kind == 'changed cells inside':
        return proportion(any(s[0] <= u[0] <= s[1] and s[2] <= u[1] <= s[3] for s in real) for u in ch)
    if kind == 'boxes holding':
        return proportion(any(s[0] <= u[0] <= s[1] and s[2] <= u[1] <= s[3] for u in ch) for s in real)
    return extent(ch) in {(s[0], s[1], s[2], s[3]) for s in real}


def colors_in_box(c, H, W, r, bi):
    t, d_, l, q = r[bi]
    a0, a1, c0, c1 = max(t, 0), min(H - 1 - d_, H - 1), max(l, 0), min(W - 1 - q, W - 1)
    return frozenset(c.go[u][w] for u in range(a0, a1 + 1) for w in range(c0, c1 + 1))


@operator(reads=('output',))
def box_has_row_color(c, e, v, u):
    if boxes_clipped_to_output(v)(c, e) is ABSENT or len(c.rows) > 2000:
        return ABSENT
    _, H, W, _ = closed_intervals_of_boxes(c, e, v)
    return proportion(colors_in_box(c, H, W, r, e[v]) == {r[e[u]]} for r in c.rows)


@operator(reads=('output',))
def determines_box_colors(c, e, v, u):
    if boxes_clipped_to_output(v)(c, e) is ABSENT or len(c.rows) > 2000:
        return ABSENT
    _, H, W, _ = closed_intervals_of_boxes(c, e, v)
    return is_function((str(r[e[u]]), colors_in_box(c, H, W, r, e[v])) for r in c.rows)


def declare_boxes():
    GRID_STAGE.define('{b} some box crop of the input is the output', crop_of_some_box(b, 0), b=framed_box_columns)
    GRID_STAGE.define('{b} some box crop of the input is the output up to rotation and reflection', crop_of_some_box(b, 1), b=framed_box_columns)
    GRID_STAGE.define('{b} some box crop of the input maps onto the output by a color map', crop_of_some_box(b, 2), b=framed_box_columns)
    GRID_STAGE.define('{b} boxes of one output color, proportion', proportion_of_boxes_with_unique_color(b), b=framed_box_columns)
    GRID_STAGE.define('{b} output colors inside its boxes distinct', color_cardinality_in_boxes(b), b=framed_box_columns)
    GRID_STAGE.define('{b} changed cells inside its boxes, proportion', changed_cells_and_boxes(b, 'changed cells inside'), b=framed_box_columns)
    GRID_STAGE.define('{b} boxes holding a changed cell, proportion', changed_cells_and_boxes(b, 'boxes holding'), b=framed_box_columns)
    GRID_STAGE.define('{b} some box is the box of the changed cells', changed_cells_and_boxes(b, 'the box of the changed cells'), b=framed_box_columns)
    GRID_STAGE.define('{b},{x} is the output color of the box, proportion', box_has_row_color(b, x), b=framed_box_columns, x=other_than(b, ('Color',)))
    GRID_STAGE.define('{b},{x} determines the output colors in the box', determines_box_colors(b, x), b=framed_box_columns, x=other_than(b))


# ---- shapes against the output

class Equivalence:
    """When two cell sets count as one shape. form: one form per class; limit: the cells up to which a feature finds the form."""

    def __init__(self, name, say, form, limit):
        self.name, self.say, self.form, self.limit = name, say, form, limit

    def __repr__(self):
        return self.name


def _translation_form(S):
    import features as F
    return F.normalized(S)


def _d4_form(S):
    import features as F
    return F.canon(S)


UP_TO_TRANSLATION = Equivalence('up to a move', '', _translation_form, None)
UP_TO_D4 = Equivalence('up to a symmetry of the square', ' up to rotation and reflection', _d4_form, MAX_CELLS)
EQUIVALENCES = (UP_TO_TRANSLATION, UP_TO_D4)


def shape_columns(c, e):
    """A column of cell values, none off its frame, the rows being few enough to read each one."""
    if not c.rows or len(c.rows) > MAX_ROWS:
        return ()
    return [(i, column[0]) for i, column in enumerate(c.cols) if column[0] in c.cs and c.cs[column[0]][1] and not any(min(r[i]) < 0 for r in c.rows)]


def cells_of_column(c, e, v):
    return set(c.cs[c.cols[e[v]][0]][1])


@operator(reads=('output',))
def same_shape_as_foreground(c, e, v, eq):
    G, S = measures(c), cells_of_column(c, e, v)
    if not G.output.foreground or (eq.limit is not None and len(S) > eq.limit):
        return ABSENT
    return len(S) == len(G.output.foreground) and eq.form(S) == eq.form(G.output.foreground)


@operator(reads=('output',))
def group_shapes_vs_component_shapes(c, e, v, eq):
    import features as F
    G = measures(c)
    groups = c.grouped(e[v])
    if not (groups and G.output.foreground_components and sum(len(g) for g in groups.values()) <= MAX_CELLS and len(groups) <= 60):
        return ABSENT
    return F.setrel2({eq.form(g) for g in groups.values() if g}, {eq.form(q) for q in G.output.foreground_components})


CROP_EXACT, CROP_TURNED, CROP_MAPPED = 0, 1, 2


@operator(reads=('input', 'output'))
def crop_of_some_group_box(c, e, v, which):
    import features as F
    G = measures(c)
    groups = c.grouped(e[v])
    if not (groups and c.cs[c.cols[e[v]][0]][0] == 'input' and 1 < len(groups) <= 200):
        return ABSENT
    if not any(0 <= u[0] < G.input.H and 0 <= u[1] < G.input.W for g in groups.values() for u in g):
        return ABSENT
    return crop_tests([extent(g) for g in groups.values() if g], G)[which]


@operator(reads=('input', 'output'))
def crop_of_bounding_box(c, e, v, which):
    S = cells_of_column(c, e, v)
    if c.cs[c.cols[e[v]][0]][0] != 'input' or len(S) > MAX_CELLS:
        return ABSENT
    return crop_tests([extent(S)], measures(c))[which]


def occurrences(pattern, G):
    """The translations that take the labeled cells `pattern` ({cell: label}) into the labeling G."""
    cells = list(pattern.items())
    anchor, label = min(cells, key=lambda kv: (len(G.positions.get(kv[1], ())), kv[0]))
    moves = set()
    for r, k in G.positions.get(label, ()):
        dr, dk = r - anchor[0], k - anchor[1]
        if all(0 <= u[0] + dr < G.H and 0 <= u[1] + dk < G.W and G.array[u[0] + dr][u[1] + dk] == q for u, q in cells):
            moves.add((dr, dk))
    return moves


def occurs_under_d4(pattern, G):
    """Whether the image of the labeled cells under some element of D4 occurs in the labeling G."""
    r1 = max(u[0] for u in pattern) + 1
    k1 = max(u[1] for u in pattern) + 1
    return any(occurrences({cell_image(u, r1, k1, s): q for u, q in pattern.items()}, G) for s in D4)


@operator(memo=True, reads=('input',))
def colored_cells_by_group(c, e, v, u):
    """{group: {cell: color}} of a cell column with the table's color, or the input's color where u is None and the column stands in the input's frame; ABSENT where a
    cell of one group would hold two colors, a cell lies off the input, or there are too many groups or cells."""
    import features as F
    n_, pi = c.cols[e[v]][0], e[v]
    fr, S = c.cs[n_]
    if len(S) > MAX_CELLS or (u is None and fr != 'input'):
        return ABSENT
    G = measures(c)
    j = None if u is None else e[u]
    ids = [i for i, (m_, ty, _) in enumerate(c.cols) if ty == 'Ident' or m_.startswith('key.')]
    sets = {}
    for r in c.rows:
        k = F.cell(r[pi])
        if j is None:
            if not (0 <= k[0] < G.input.H and 0 <= k[1] < G.input.W):
                return ABSENT
            q = G.gi[k[0]][k[1]]
        else:
            q = r[j]
        key = tuple(str(r[i]) for i in ids) if ids else (q if j is not None else ())
        if sets.setdefault(key, {}).setdefault(k, q) != q:
            return ABSENT
    return sets if sets and len(sets) <= 60 else ABSENT


@operator(memo=True, reads=('output',))
def occurrence_translations(c, e, v, u):
    sets = colored_cells_by_group(v, u)(c, e)
    return ABSENT if sets is ABSENT else [occurrences(m_, measures(c).output) for m_ in sets.values()]


def frame_has_output_size(c, e, v):
    G = measures(c)
    return c.sizes.get(c.cs[c.cols[e[v]][0]][0]) == (G.output.H, G.output.W)


@operator(reads=('output',))
def occurs_in_place(c, e, v, u):
    moves = occurrence_translations(v, u)(c, e)
    return ABSENT if moves is ABSENT or not frame_has_output_size(c, e, v) else proportion((0, 0) in m_ for m_ in moves)


@operator(reads=('output',))
def occurs_elsewhere(c, e, v, u):
    moves = occurrence_translations(v, u)(c, e)
    if moves is ABSENT:
        return ABSENT
    return proportion(bool(m_ - {(0, 0)}) for m_ in moves) if frame_has_output_size(c, e, v) else proportion(bool(m_) for m_ in moves)


@operator(reads=('output',))
def common_translation(c, e, v, u):
    moves = occurrence_translations(v, u)(c, e)
    if moves is ABSENT or len(moves) < 2:
        return ABSENT
    common = set.intersection(*moves)
    return bool(common - {(0, 0)}) if frame_has_output_size(c, e, v) else bool(common)


@operator(reads=('output',))
def occurs_under_d4_proportion(c, e, v, u):
    sets = colored_cells_by_group(v, u)(c, e)
    if sets is ABSENT or len(sets) > 20:
        return ABSENT
    return proportion(occurs_under_d4(m_, measures(c).output) for m_ in sets.values())


def changed_along_direction(G, way):
    """({cell: a changed cell lies toward the way from it}, {cell: every cell toward the way from it is changed, and there is one})."""
    if way not in G.paths:
        s = STEP[way]
        hit, whole = {}, {}
        for u in sorted(G.output.cells, key=lambda u: -(u[0] * s[0] + u[1] * s[1])):
            q = (u[0] + s[0], u[1] + s[1])
            if q in G.output.cells:
                hit[u] = q in G.changed or hit[q]
                following = (q[0] + s[0], q[1] + s[1])
                whole[u] = q in G.changed and (following not in G.output.cells or whole[q])
            else:
                hit[u] = whole[u] = False
        G.paths[way] = (hit, whole)
    return G.paths[way]


@operator(reads=('input', 'output'))
def direction_reaches_changed(c, e, v, u, which):
    G = measures(c)
    if not G.changed:
        return ABSENT
    pairs = {((r[e[v]][0], r[e[v]][2]), r[e[u]]) for r in c.rows}
    return proportion(changed_along_direction(G, way)[which].get(k, False) for k, way in pairs)


def columns_in_output_sized_frame(c, e):
    """A column of cell values in a frame of the output's size, the rows being few enough to read each one."""
    if not c.rows or len(c.rows) > MAX_ROWS:
        return ()
    G = measures(c)
    return [(i, column[0]) for i, column in enumerate(c.cols) if column[0] in c.cs and c.sizes.get(c.cs[column[0]][0]) == (G.output.H, G.output.W)]


def declare_shapes():
    cells = shape_columns
    lead = '{n} groups of %s ' % GROUPS
    for eq in EQUIVALENCES:
        GRID_STAGE.define('{n} same shape%s as the output foreground' % eq.say, same_shape_as_foreground(n, eq), n=cells)
        GRID_STAGE.define('{n} group shapes%s vs the output foreground component shapes' % eq.say, group_shapes_vs_component_shapes(n, eq), n=cells)
    for which, say in ((CROP_EXACT, ' is the output'), (CROP_TURNED, ' is the output up to rotation and reflection')):
        GRID_STAGE.define(lead + 'some group box crop of the input' + say, crop_of_some_group_box(n, which), n=cells)
    for which, say in ((CROP_EXACT, ' is the output'), (CROP_TURNED, ' is the output up to rotation and reflection'), (CROP_MAPPED, ' maps onto the output by a color map')):
        GRID_STAGE.define('{n} bounding box crop of the input' + say, crop_of_bounding_box(n, which), n=cells)
    for head, color, binders in (('{n}', None, dict(n=cells)), ('{n},{x}', x, dict(n=cells, x=columns(('Color',))))):
        GRID_STAGE.define(head + ' occurs in the output in place, proportion', occurs_in_place(n, color), **binders)
        GRID_STAGE.define(head + ' occurs elsewhere in the output, proportion', occurs_elsewhere(n, color), **binders)
        GRID_STAGE.define(head + ' one translation takes them all into the output', common_translation(n, color), **binders)
        GRID_STAGE.define(head + ' occurs in the output up to rotation and reflection, proportion', occurs_under_d4_proportion(n, color), **binders)
    GRID_STAGE.define('{n},{d} has a changed cell toward it, proportion', direction_reaches_changed(n, d, 0), n=columns_in_output_sized_frame, d=columns(ORIENT_DIRS))
    GRID_STAGE.define('{n},{d} every cell toward it is changed, proportion', direction_reaches_changed(n, d, 1), n=columns_in_output_sized_frame, d=columns(ORIENT_DIRS))


# ---- a table's values against each grid

@operator
def grid_labels(c, e, grid):
    """The set of the grid's labels."""
    return labeling(c.array(grid)).labels


@operator
def foreground(c, e, grid):
    """The grid's foreground, where one label is the most frequent."""
    held = labeling(c.array(grid)).foreground
    return ABSENT if held is None else held


@operator
def grid_cells(c, e, grid):
    return labeling(c.array(grid)).cells


@operator(reads=('input', 'output'))
def changed_cells(c, e):
    """The cells where the input and the train output differ. Empty where the two grids differ in size."""
    return measures(c).changed


@operator(reads=('input', 'output'))
def added_labels(c, e):
    return measures(c).added_labels


@operator(reads=('input', 'output'))
def dropped_labels(c, e):
    return measures(c).dropped_labels


@operator(reads=('input', 'output'))
def changed_from(c, e):
    return measures(c).changed_from


@operator(reads=('input', 'output'))
def changed_to(c, e):
    return measures(c).changed_to


@operator
def nonempty_set(c, e, term):
    held = term(c, e)
    return held if held is not ABSENT and held else ABSENT


@operator
def input_measure(c, e, name):
    G = labeling(c.gi)
    return {'the longer side of the input': max(G.H, G.W), 'the shorter side of the input': min(G.H, G.W), 'the input color count': len(G.counts)}[name]

def label_counts(c, grid):
    """The cell count of each color of the grid."""
    held = c.memo.get(('color counts', grid))
    if held is None:
        held = c.memo['color counts', grid] = Counter(u for row in c.array(grid) for u in row)
    return held


def foreground_of(c, grid):
    """The cells that do not hold the grid's one most frequent color, or None where no one color is the most frequent."""
    key = ('foreground', grid)
    if key not in c.memo:
        c.memo[key] = foreground_set(c.array(grid))
    return c.memo[key]


def foreground_set(g):
    count = Counter(u for row in g for u in row)
    tops = [k for k, q in count.items() if q == max(count.values())]
    if len(tops) != 1:
        return None
    return {(r, k) for r, row in enumerate(g) for k, u in enumerate(row) if u != tops[0]}


def all_cells(c, grid):
    H, W = c.size(grid)
    return {(r, k) for r in range(H) for k in range(W)}


def column_cells(c, e, v):
    return c.cs[c.cols[e[v]][0]]


def columns_in_frame(accepts):
    """A column of cells whose frame the test accepts. accepts(c, frame)."""
    def dom(c, e):
        return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.cs and accepts(c, c.cs[col[0]][0])]
    return dom


INPUT_FRAME = columns_in_frame(lambda c, fr: fr == 'input')
OUTPUT_ALIGNED_FRAME = columns_in_frame(lambda c, fr: fr == 'output' or (fr == 'input' and c.same()))
OUTPUT_FRAME = columns_in_frame(lambda c, fr: fr == 'output')


def nonempty_cells_in(frames):
    def dom(c, e):
        return [(i, tok) for i, tok in frames(c, e) if c.cs[tok][1]]
    return dom


@operator(reads=('input',))
def color_cardinality_of_input_cells(c, e, v):
    H, W = c.size(INPUT)
    return len({c.gi[u[0]][u[1]] for u in column_cells(c, e, v)[1] if 0 <= u[0] < H and 0 <= u[1] < W})


@operator(reads=('input',))
def is_union_of_input_color_classes(c, e, v):
    H, W = c.size(INPUT)
    count = label_counts(c, INPUT)
    under = Counter(c.gi[u[0]][u[1]] for u in column_cells(c, e, v)[1] if 0 <= u[0] < H and 0 <= u[1] < W)
    return all(count[k] == q for k, q in under.items())


@operator
def contains_grid_extreme_color(c, e, v, grid, extreme):
    count = label_counts(c, grid)
    want = extreme(count.values())
    return any(count[k] == want for k in values(c, e, v))


@operator
def proportion_of_rows_matching_grid(c, e, v, u, grid):
    """The proportion of the rows whose cell of column v holds the color of column u in the grid."""
    H, W = c.size(grid)
    g, i, j = c.array(grid), e[v], e[u]
    return round(sum(0 <= r[i][0] < H and 0 <= r[i][2] < W and g[r[i][0]][r[i][2]] == r[j] for r in c.rows) / len(c.rows), 3)


def declare_input_grid():
    INPUT_GRID_STAGE.define('{n} input colors distinct', color_cardinality_of_input_cells(n), n=nonempty_cells_in(INPUT_FRAME))
    INPUT_GRID_STAGE.define('{n} is a union of input colors', is_union_of_input_color_classes(n), n=nonempty_cells_in(INPUT_FRAME))
    INPUT_GRID_STAGE.define('{x} within the input colors', is_subset(vocabulary_values(x), grid_labels(INPUT)), x=columns(('Color',)))
    INPUT_GRID_STAGE.define('{x} vs the input colors', set_relation(vocabulary_values(x), grid_labels(INPUT)), x=columns(('Color',)))
    INPUT_GRID_STAGE.define('{x} includes the most frequent input color', contains_grid_extreme_color(x, INPUT, max), x=columns(('Color',)))
    INPUT_GRID_STAGE.define('{x} includes the least frequent input color', contains_grid_extreme_color(x, INPUT, min), x=columns(('Color',)))
    input_sized = lambda c, e: [(i, col[0]) for i, col in enumerate(c.cols) if c.rows and col[0] in c.cs and c.sizes.get(c.cs[col[0]][0]) == c.size(INPUT)]
    INPUT_GRID_STAGE.define('{n},{x} agrees with the input colors, proportion', proportion_of_rows_matching_grid(n, x, INPUT), x=columns(('Color',)), n=input_sized)
    INPUT_GRID_STAGE.define('{n} vs the input foreground', set_relation_in(cells(n), foreground(INPUT), grid_cells(INPUT)), n=INPUT_FRAME)
    for measure in ('the longer side of the input', 'the shorter side of the input', 'the input color count'):
        INPUT_GRID_STAGE.define('{n} max vs ' + measure, compare(maximum(value_list(n)), input_measure(measure)), n=has_rows(columns(NUM)))


def same_grids(dom):
    def wrapped(c, e):
        return dom(c, e) if c.same() else ()
    return wrapped


@operator(reads=('output',))
def cell_count_vs_foreground(c, e, v):
    fg = foreground_of(c, OUTPUT)
    return ABSENT if fg is None else cmp(len(column_cells(c, e, v)[1]), len(fg))


def bounding_box_of(S, H, W):
    rs, ks = [u[0] for u in S], [u[1] for u in S]
    return (min(rs), H - 1 - max(rs), min(ks), W - 1 - max(ks))


@operator(reads=('output',))
def bounding_box_is_foreground_box(c, e, v):
    fg, S = foreground_of(c, OUTPUT), column_cells(c, e, v)[1]
    if not fg or not S:
        return ABSENT
    H, W = c.size(OUTPUT)
    return bounding_box_of(S, H, W) == bounding_box_of(fg, H, W)


@operator(reads=('output',))
def group_count_vs_foreground_components(c, e, v):
    import features as F
    fg = foreground_of(c, OUTPUT)
    if fg is None:
        return ABSENT
    groups = c.grouped(e[v])
    if not groups:
        return ABSENT
    return cmp(len(groups), F.comps(fg) if fg else 0)


@operator(reads=('output',))
def bounding_box_has_output_size(c, e, v):
    fr, S = column_cells(c, e, v)
    if not (S and fr in c.sizes):
        return ABSENT
    rs, ks = [u[0] for u in S], [u[1] for u in S]
    return (max(rs) - min(rs) + 1, max(ks) - min(ks) + 1) == c.size(OUTPUT)


@operator(reads=('output',))
def some_box_has_output_size(c, e, v):
    fr, B = c.box_sets()[c.cols[e[v]][0]]
    H, W = c.sizes[fr]
    return any((H - t - d_, W - l - r) == c.size(OUTPUT) for t, d_, l, r in B)


@operator(reads=('output',))
def set_relation_to_output_cells_of_colors(c, e, v, u):
    import features as F
    colors, grid = values(c, e, u), all_cells(c, OUTPUT)
    return F.setrel(column_cells(c, e, v)[1], {q for q in grid if c.go[q[0]][q[1]] in colors}, grid)


@operator(reads=('output',))
def color_counts_equal_output(c, e, v, u):
    count = label_counts(c, OUTPUT)
    per = Counter(q for _, q in {((r[e[v]][0], r[e[v]][2]), r[e[u]]) for r in c.rows})
    return round(sum(per[q] == count[q] for q in per) / len(per), 3)


@operator(reads=('output',))
def jaccard_with_output_cells(c, e, v, u):
    pairs = {((r[e[v]][0], r[e[v]][2]), r[e[u]]) for r in c.rows}
    want = {((r, k), q) for r, row in enumerate(c.go) for k, q in enumerate(row)}
    return round(len(pairs & want) / len(pairs | want), 3) if pairs | want else 1.0


def declare_output_grid():
    GRID_STAGE.define('{n} vs the changed cells', set_relation_in(cells(n), changed_cells(), grid_cells(INPUT)), n=same_grids(INPUT_FRAME))
    GRID_STAGE.define('{n} Jaccard index with the changed cells', jaccard(cells(n), changed_cells()), n=same_grids(INPUT_FRAME))
    GRID_STAGE.define('{n} cells vs the output foreground cells', cell_count_vs_foreground(n), n=columns_in_frame(lambda c, fr: True))
    GRID_STAGE.define('{n} bounding box is the output foreground box', bounding_box_is_foreground_box(n), n=OUTPUT_ALIGNED_FRAME)
    GRID_STAGE.define('{n} vs the output foreground', set_relation_in(cells(n), foreground(OUTPUT), grid_cells(OUTPUT)), n=OUTPUT_ALIGNED_FRAME)
    GRID_STAGE.define('{n} groups of %s vs the output foreground components' % GROUPS, group_count_vs_foreground_components(n), n=columns_in_frame(lambda c, fr: True))
    GRID_STAGE.define('{n} bounding box has the output size', bounding_box_has_output_size(n), n=columns_in_frame(lambda c, fr: True))
    GRID_STAGE.define('{b} some box has the output size', some_box_has_output_size(b), b=lambda c, e: [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.box_sets()])
    aligned = has_rows(OUTPUT_ALIGNED_FRAME)
    GRID_STAGE.define('{n},{x} agrees with the output colors, proportion', proportion_of_rows_matching_grid(n, x, OUTPUT), x=columns(('Color',)), n=aligned)
    GRID_STAGE.define('{n},{x} vs the output cells of its colors', set_relation_to_output_cells_of_colors(n, x), x=columns(('Color',)), n=aligned)
    GRID_STAGE.define('{n},{x} color counts agree with the output, proportion', color_counts_equal_output(n, x), x=columns(('Color',)), n=has_rows(OUTPUT_ALIGNED_FRAME))
    GRID_STAGE.define('{x} is the set of the colors the changed cells take', equal(vocabulary_values(x), nonempty_set(changed_to())), x=columns(('Color',)))
    GRID_STAGE.define('{x} within the output colors', is_subset(vocabulary_values(x), grid_labels(OUTPUT)), x=columns(('Color',)))
    GRID_STAGE.define('{x} vs the output colors', set_relation(vocabulary_values(x), grid_labels(OUTPUT)), x=columns(('Color',)))
    GRID_STAGE.define('{n},{x} Jaccard index with the output cells', jaccard_with_output_cells(n, x), x=columns(('Color',)), n=OUTPUT_FRAME)


declare_counts()
declare_orientations()
declare_colors()
declare_cells()
declare_boxes()
declare_shapes()
declare_input_grid()
declare_output_grid()
