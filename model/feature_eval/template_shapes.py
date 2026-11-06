#!/usr/bin/env python
"""The first version's Candidate templates, written as expressions of the grammar.

  uv run python model/feature_eval/template_shapes.py ENCODER [--tasks N] [--items K] [--kinds REGEX]

Each entry in ENTRIES takes a template of results/candidate-rank.tsv and gives its terms, and
how the terms' counts give the first version's value. The script samples Candidate tables,
evaluates each term through the engine, and compares the two values at each train pair.
It writes results/template-shapes.tsv, one line per template in rank order.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

ROOT = Path('/Users/davidlu/code/arc-workspace')
RESULTS = ROOT / 'work/feature-spec/results'
C = ROOT / 'model/contracts'
TOKEN = re.compile(r'(?:key\.)?⟦CT#(\d+)⟧')
GROUPS = 'its Ident, Color and key columns'
PLACE = ('Position', 'Box')

ENTRIES = OrderedDict()


def entry(*kinds, note=''):
    def add(fn):
        for kind in kinds:
            ENTRIES[kind] = (fn, note)
        return fn
    return add


class Table:
    """What an entry reads of a table: the columns by kind."""

    def __init__(self, names, types):
        self.names, self.types = names, types
        self.columns = [f'T{i}' for i in range(len(names))]
        self.groups = [c for c, n, t in zip(self.columns, names, types) if t in ('Ident', 'Color') or n.startswith('key.')]
        self.ids = [c for c, n, t in zip(self.columns, names, types) if t == 'Ident' or n.startswith('key.')]

    def others(self, *cols):
        return [c for c in self.columns if c not in cols]

    def type_of(self, column):
        return self.types[self.columns.index(column)]


def words(cols):
    return ' '.join(cols)


def fields(cols):
    """One field, or a record of several."""
    return cols[0] if len(cols) == 1 else f'({words(cols)})'


def ratio(n, d):
    return round(n / d, 3) if d else None


def share(counts, _firsts):
    return ratio(counts[0], counts[1])


def count(counts, _firsts):
    return counts[0]


def is_zero(counts, _firsts):
    return counts[0] == 0


def nonzero(counts, _firsts):
    return counts[0] > 0


def first_cell(_counts, firsts):
    return firsts[0]


def cmp(u, v):
    return '<' if u < v else '=' if u == v else '>'


def cmp_counts(counts, _firsts):
    return cmp(counts[0], counts[1])


def set_relation(counts, _firsts):
    """From |u - v|, |v - u| and |u & v|."""
    left, right, both = counts[:3]
    if not left and not right:
        return 'equal'
    if not both:
        return 'disjoint'
    return 'subset' if not left else 'superset' if not right else 'overlap'


def all_of(domain, body, pairs, outer=''):
    """(all D B (outer) pairs): false on a domain with no rows."""
    written = ' '.join(f'({a} {b})' for a, b in pairs)
    return f'(all {domain} {body} ({outer}) {written})'


def holds(counts, _firsts):
    """Whether a relation has a row."""
    return counts[0] > 0


def single_values(rel, keys, field):
    """A relation's keys with one value of a field, and that value."""
    return f'(component Singleton (member {rel} ({words(keys)}) ({field})) value)'


def determines_form(rel, keys, field, outer=''):
    """Each row's key has one value of the field."""
    return all_of(rel, single_values(rel, keys, field), [(k, k) for k in keys], outer)


CHANGED = '(select (join input output (P P)) Col != Col_2)'
BOUNDARY = '(component Boundary (cell output (Col) (P)) boundary)'
PER_COLOR = '(component Cardinality (member output (Col) (P)) size)'
BACKGROUND = f'(component Order (member {PER_COLOR} () (Col)) (score {PER_COLOR} () (Col N)) maximal)'
FOREGROUND = f'(antijoin output {BACKGROUND} (Col Col))'


def O(p):
    return f'(join &t output ({p} P))'


def I(p):
    return f'(join &t input ({p} P))'


def IO(p):
    return f'(join {I(p)} output ({p} P))'


def clipped(p):
    return f'(project {O(p)} {p})'


ROLE_TEXTS = []


def role_share(role):
    ROLE_TEXTS.append(role)

    def make(t, p):
        return [f'(semijoin {clipped(p)} {role} ({p} P))', clipped(p)], share
    return make


def maximum(rel, column):
    """The greatest value of a number column."""
    return f'(component Order (member {rel} () ({column})) (score {rel} () ({column} {column})) maximal)'


# ---- rank 1 to 30, and the kinds that share a form with them

@entry('C outer boundary output colors distinct')
def outer_boundary(t, p):
    return [f'(project (join (antijoin (lib-join &t neighbor (P {p})) &t (Q {p})) output (Q P)) Col)'], count


@entry('C,C determines the output color', 'C,key.C determines the output color')
def determines_output(t, p, x):
    return [determines_form(O(p), [x], 'Col')], holds


@entry('C cells with a changed cell on their rows or columns, proportion', 'key.C cells with a changed cell on their rows or columns, proportion')
def cells_on_changed_lines(t, p):
    lines = f'(join (lib-join {O(p)} split (P {p})) (lib-join {CHANGED} split (P P)) (A A) (Along Along))'
    return [f'(project {lines} {p})', clipped(p)], share


@entry('C its Moore neighborhood determines the output color')
def moore_determines(t, p):
    around = f'(join (lib-join (project &t {p}) neighbor (P {p})) input (Q P))'
    same = f'(component Inclusion (pattern {around} () ({p} (D Col))) (observed {around} () ({p} (D Col))) equal)'
    pairs = f'(join (join {same} input ({p} P)) input ({p}_2 P) (Col Col))'
    return [all_of(f'(join {pairs} output ({p} P))', 'output', [(f'{p}_2', 'P'), ('Col_2', 'Col')])], holds


@entry('C its color and its same-color neighbor count determines the output color')
def same_color_neighbors_determine(t, p):
    around = f'(join (lib-join {I(p)} neighbor (P {p})) input (Q P) (Col Col))'
    counted = f'(component Cardinality (member {around} ({p} Col) (D)) (domain {I(p)} ({p} Col)) size)'
    return [determines_form(f'(join {counted} output ({p} P))', ['Col', 'N'], 'Col_2')], holds


@entry(f'C groups of {GROUPS} with one output color, proportion')
def groups_one_color(t, p):
    return [f'(component Singleton (member {O(p)} ({words(t.groups)}) (Col)) value)', f'(project {O(p)} {words(t.groups)})'], share


@entry('C its row or column determines the output color')
def line_determines(t, p):
    return [determines_form(f'(lib-join {O(p)} split (P {p}))', ['A', 'Along'], 'Col', 'A')], holds


@entry('C output colors distinct', 'key.C output colors distinct')
def output_colors(t, p):
    return [f'(project {O(p)} Col)'], count


@entry('C its coordinate parity determines the output color', note='no parity operator: the class of a cell under diagonal steps')
def parity_determines(t, p):
    steps = '(lib-join diag_dir_elem step_offset (D D))'
    classes = f'(component Connectivity (node output () (P)) (step {steps} () (V)) component)'
    return [determines_form(f'(join (join &t {classes} ({p} P)) output ({p} P))', ['Id'], 'Col')], holds


@entry('C its neighbor colors determines the output color')
def neighbor_colors_determine(t, p):
    around = f'(join (lib-join (project &t {p}) neighbor (P {p})) input (Q P))'
    counted = f'(component Cardinality (member {around} ({p} Col) (D)) size)'
    same = f'(component Inclusion (pattern {counted} () ({p} (Col N))) (observed {counted} () ({p} (Col N))) equal)'
    return [all_of(f'(join {same} output ({p} P))', 'output', [(f'{p}_2', 'P'), ('Col', 'Col')])], holds


@entry('C,C with the input color determines the output color', 'C,key.C with the input color determines the output color')
def with_input_determines(t, p, x):
    return [determines_form(IO(p), [x, 'Col'], 'Col_2')], holds


@entry('C its diagonal determines the output color', 'key.C its diagonal determines the output color')
def diagonal_determines(t, p):
    return [determines_form(f'(lib-join {O(p)} corner_dist (P {p}))', ['Diag', 'K'], 'Col', 'Diag')], holds


ENTRIES['C cells on the boundary of their component in the output, proportion'] = (role_share(BOUNDARY), '')
ENTRIES['key.C cells on the boundary of their component in the output, proportion'] = (role_share(BOUNDARY), '')


@entry('C its distance from the grid border determines the output color')
def border_distance_determines(t, p):
    margins = f'(lib-join &t margin (B {p}))'
    least = f'(component Order (member {margins} ({p}) (K)) (score {margins} ({p}) (K K)) minimal)'
    return [determines_form(f'(join {least} output ({p} P))', ['K'], 'Col')], holds


@entry(f'C groups of {GROUPS} output colors per group max')
def most_colors_per_group(t, p):
    return [maximum(f'(component Cardinality (member {O(p)} ({words(t.groups)}) (Col)) size)', 'N')], first_cell


def kept_and_changed(p):
    return f'(antijoin {I(p)} output ({p} P) (Col Col))', f'(join {I(p)} output ({p} P) (Col Col))'


@entry('C,C determines which cells change', 'C,key.C determines which cells change')
def determines_change(t, p, x):
    changed, kept = kept_and_changed(p)
    return [all_of(O(p), f'(antijoin (project &t {x}) (semijoin {changed} {kept} ({x} {x})) ({x} {x}))', [(x, x)])], holds


@entry('C occurs in the output up to rotation and reflection, proportion', 'key.C occurs in the output up to rotation and reflection, proportion')
def occurs_under_d4(t, p):
    if not t.ids:
        return [f'(component Occurrences (shape {I(p)} () ({p} Col)) (cell output () (P Col)) (transform d4_elem () (D)) occurrence)'], lambda n, f: float(n[0] > 0)
    found = f'(component Occurrences (shape {I(p)} ({words(t.ids)}) ({p} Col)) (cell output () (P Col)) (transform d4_elem () (D)) occurrence)'
    return [f'(project {found} {words(t.ids)})', f'(project {I(p)} {words(t.ids)})'], share


@entry(f'C groups of {GROUPS} output color sets distinct', f'key.C groups of {GROUPS} output color sets distinct')
def color_sets_distinct(t, p):
    g = t.groups
    second = [f'{c}_2' for c in g]
    same = f'(component Inclusion (pattern {O(p)} () ({fields(g)} Col)) (observed {O(p)} () ({fields(g)} Col)) equal)'
    return [f'(project (component Quotient (equivalent {same} () ({fields(g)} {fields(second)})) class) Id)'], count


@entry('C occurs in the output in place, proportion')
def occurs_in_place(t, p):
    if not t.ids:
        return [f'(select (component Occurrences (shape {I(p)} () ({p} Col)) (cell output () (P Col)) occurrence) P = 0)'], lambda n, f: float(n[0] > 0)
    found = f'(component Occurrences (shape {I(p)} ({words(t.ids)}) ({p} Col)) (cell output () (P Col)) occurrence)'
    return [f'(project (select {found} P = 0) {words(t.ids)})', f'(project {I(p)} {words(t.ids)})'], share


def agreement_rows(t, p, x, rows):
    """The rows whose color is the one most frequent color of their key, in a key of two rows or more."""
    rest = fields(t.others(x))
    per = f'(component Cardinality (member {rows} ({x} Col) ({rest})) size)'
    most = f'(component Order (member {per} ({x}) (Col)) (score {per} ({x}) (Col N)) maximal)'
    one_most = f'(component Singleton (member {most} ({x}) (Col)) value)'
    one_row = f'(component Singleton (member &t ({x}) ({rest})) value)'
    return f'(join {rows} (antijoin {one_most} {one_row} ({x} {x})) ({x} {x}) (Col Col))'


@entry('C,C output color agrees with the other rows of its value, proportion', 'C,key.C output color agrees with the other rows of its value, proportion')
def output_agrees(t, p, x):
    return [agreement_rows(t, p, x, O(p)), '&t'], share


@entry('C changed cells on its rows or columns, proportion', 'key.C changed cells on its rows or columns, proportion')
def changed_on_lines(t, p):
    lines = f'(join (lib-join {CHANGED} split (P P)) (lib-join {O(p)} split (P {p})) (A A) (Along Along))'
    return [f'(project {lines} P)', f'(project {CHANGED} P)'], share


@entry('C,C whether it changes agrees with the other rows of its value, proportion', 'C,key.C whether it changes agrees with the other rows of its value, proportion',
       note='no two-valued column: each side counts apart, and a union joins them')
def change_agrees(t, p, x):
    rest = fields(t.others(x))
    changed, kept = kept_and_changed(p)
    counted = lambda rows: f'(component Cardinality (member {rows} ({x}) ({rest})) (domain &t ({x})) size)'
    one_row = f'(component Singleton (member &t ({x}) ({rest})) value)'
    wins = lambda op: f'(antijoin (select (join {counted(changed)} {counted(kept)} ({x} {x})) N {op} N_2) {one_row} ({x} {x}))'
    return [f'(join {changed} {wins(">")} ({x} {x}))', f'(join {kept} {wins("<")} ({x} {x}))', '&t'], lambda n, f: ratio(n[0] + n[1], n[2])


def group_shapes_same(t, p):
    g = t.groups
    box = f'(component BoundingBox (cell {O(p)} ({words(g)}) ({p})) box)'
    pairs = ' '.join(f'({c} {c})' for c in g)
    placed = f'(lib-join (join {O(p)} {box} {pairs}) relative (Base B) (X {p}))'
    return f'(component Inclusion (pattern {placed} () ({fields(g)} X_rel)) (observed {placed} () ({fields(g)} X_rel)) equal)'


@entry(f'C groups of {GROUPS} their shape determines their output color', note='no shape class: the cells relative to the box, then Inclusion')
def shape_determines(t, p):
    g = t.groups
    one = f'(component Singleton (member {O(p)} ({words(g)}) (Col)) value)'
    first = ' '.join(f'({c} {c})' for c in g)
    second = ' '.join(f'({c}_2 {c})' for c in g)
    both = [(f'{c}_2', c) for c in g] + [('Col', 'Col')]
    return [all_of(f'(join {group_shapes_same(t, p)} {one} {first})', one, both)], holds


def compare_tests(left, left_column, right, right_column):
    """The two tests that a value of '<', '=', '>' stands for, over one number column of each relation."""
    second = f'{right_column}_2' if right_column == left_column else right_column
    product = f'(join {left} {right})'
    return [f'(select {product} {left_column} < {second})', f'(select {product} {left_column} = {second})']


def from_tests(counts, _firsts):
    return '<' if counts[0] else '=' if counts[1] else '>'


EVERY_STEP = 'step_offset'
FOREGROUND_COMPONENTS = f'(project (component Connectivity (node {FOREGROUND} () (P)) (step {EVERY_STEP} () (V)) component) Id)'
CHANGED_COMPONENTS = f'(project (component Connectivity (node {CHANGED} () (P)) (step {EVERY_STEP} () (V)) component) Id)'


def side_of_output(op):
    return f'(project (select (lib-join output axis_extents (P P)) N1 {op} N2) N1)'


MEASURES = {
    'the output area': ('(component Cardinality (member output () (P)) size)', 'N'),
    'the longer side of the output': (side_of_output('>='), 'N1'),
    'the shorter side of the output': (side_of_output('<='), 'N1'),
    'the output color count': ('(component Cardinality (member output () (Col)) size)', 'N'),
    'the output foreground count': (f'(component Cardinality (member {FOREGROUND} () (P)) size)', 'N'),
    'the output foreground component count': (f'(component Cardinality (member {FOREGROUND_COMPONENTS} () (Id)) size)', 'N'),
    'the changed cell count': (f'(component Cardinality (member {CHANGED} () (P)) size)', 'N'),
    'the changed component count': (f'(component Cardinality (member {CHANGED_COMPONENTS} () (Id)) size)', 'N'),
}


def add_measures():
    for name, (rel, column) in MEASURES.items():
        def rows_vs(t, rel=rel, column=column):
            left = f'(component Cardinality (member &t () ({fields(t.columns)})) size)'
            return compare_tests(left, 'N', rel, column), from_tests

        def max_vs(t, n, rel=rel, column=column):
            return compare_tests(maximum('&t', n), n, rel, column), from_tests

        def includes(t, n, rel=rel, column=column):
            return [f'(join &t {rel} ({n} {column}))'], nonzero

        def distinct_vs(t, n, rel=rel, column=column):
            left = f'(component Cardinality (member &t () ({n})) size)'
            return compare_tests(left, 'N', rel, column), from_tests

        ENTRIES[f'rows vs {name}'] = (rows_vs, '')
        for lead in ('C', 'key.C'):
            ENTRIES[f'{lead} max vs {name}'] = (max_vs, '')
            ENTRIES[f'{lead} includes {name}'] = (includes, '')
            ENTRIES[f'{lead} distinct vs {name}'] = (distinct_vs, '')


add_measures()


LEAST_COLOR = f'(component Order (member {PER_COLOR} () (Col)) (score {PER_COLOR} () (Col N)) minimal)'
MOST_COLOR = f'(component Order (member {PER_COLOR} () (Col)) (score {PER_COLOR} () (Col N)) maximal)'


@entry('C includes the least frequent output color', 'key.C includes the least frequent output color')
def includes_least(t, x):
    return [f'(join &t {LEAST_COLOR} ({x} Col))'], nonzero


@entry('C includes the most frequent output color')
def includes_most(t, x):
    return [f'(join &t {MOST_COLOR} ({x} Col))'], nonzero


@entry('C occurs elsewhere in the output, proportion', 'key.C occurs elsewhere in the output, proportion')
def occurs_elsewhere(t, p):
    if not t.ids:
        return [f'(select (component Occurrences (shape {I(p)} () ({p} Col)) (cell output () (P Col)) occurrence) P != 0)'], lambda n, f: float(n[0] > 0)
    found = f'(component Occurrences (shape {I(p)} ({words(t.ids)}) ({p} Col)) (cell output () (P Col)) occurrence)'
    return [f'(project (select {found} P != 0) {words(t.ids)})', f'(project {I(p)} {words(t.ids)})'], share


@entry('C within the output colors', 'key.C within the output colors')
def within_output_colors(t, x):
    return [all_of('&t', 'output', [(x, 'Col')])], holds


@entry('C vs the output colors', 'key.C vs the output colors')
def versus_output_colors(t, x):
    return [f'(antijoin (project &t {x}) output ({x} Col))', f'(antijoin (project output Col) &t (Col {x}))', f'(join (project &t {x}) output ({x} Col))'], set_relation


@entry('C is a union of output colors')
def union_of_colors(t, p):
    # A color with a cell under the column and a cell outside it.
    held = f'(semijoin output {O(p)} (Col Col))'
    return [all_of(held, '&t', [('P', p)])], holds


@entry('C,C is determined by the output color', 'C,key.C is determined by the output color', 'key.C,C is determined by the output color')
def determined_by_color(t, p, x):
    return [determines_form(O(p), ['Col'], x)], holds


# ---- the next ranks

COMPONENTS = '(component Connectivity (node output (Col) (P)) (step step_offset () (V)) component)'
COMPONENT_BOX = f'(component BoundingBox (cell {COMPONENTS} (Col Id) (P)) box)'
IN_COMPONENT_BOX = f'(join {COMPONENTS} {COMPONENT_BOX} (Col Col) (Id Id))'
SAME_COLOR_NEIGHBOR = '(join (lib-join output neighbor (P P)) output (Q P) (Col Col))'
LINES = '(lib-join output split (P P))'
FULL_LINES = f'(component Singleton (member {LINES} (A Along) (Col)) value)'
ON_FULL_LINE = f'(project (join {LINES} {FULL_LINES} (A A) (Along Along)) P)'
BACKGROUND_CELLS = f'(join output {BACKGROUND} (Col Col))'
AT_ZERO_MARGIN = '(select (lib-join output margin (B P)) K = 0)'
DROPPED = '(antijoin (project input Col) output (Col Col))'
ADDED = '(antijoin (project output Col) input (Col Col))'
FOREGROUND_BOX = f'(component BoundingBox (cell {FOREGROUND} () (P)) box)'
INPUT_BACKGROUND = BACKGROUND.replace('output', 'input')
INPUT_FOREGROUND = FOREGROUND.replace('output', 'input')


def set_relation_in(counts, _firsts):
    """From |u - v|, |v - u|, |u & v| and the count in neither."""
    left, right, both, neither = counts[:4]
    if not left and not right:
        return 'equal'
    if not both:
        return 'disjoint' if neither else 'complement'
    return 'subset' if not left else 'superset' if not right else 'overlap'


def versus_cells(a, a_column, b, b_column, universe):
    return [f'(antijoin (project {a} {a_column}) {b} ({a_column} {b_column}))', f'(antijoin (project {b} {b_column}) {a} ({b_column} {a_column}))',
            f'(join (project {a} {a_column}) {b} ({a_column} {b_column}))', f'(antijoin (antijoin {universe} {a} (P {a_column})) {b} (P {b_column}))'], set_relation_in


def versus_colors(x, colors, column):
    return [f'(antijoin (project &t {x}) {colors} ({x} {column}))', f'(antijoin (project {colors} {column}) &t ({column} {x}))', f'(join (project &t {x}) {colors} ({x} {column}))'], set_relation


def plain_or_key(*kinds):
    """Each kind, and the kind with its leading columns read as key columns."""
    out = []
    for kind in kinds:
        lead, rest = kind.split(' ', 1)
        options = [['C', 'key.C'] for _ in lead.split(',')]
        heads = ['']
        for option in options:
            heads = [f'{h},{o}' if h else o for h in heads for o in option]
        out.extend(f'{h} {rest}' for h in heads)
    return out


def groups_rel(t):
    return words(t.groups)


def group_pairs(t, suffix=''):
    return ' '.join(f'({c}{suffix} {c})' for c in t.groups)


def one_color_of_group(t, p):
    return f'(component Singleton (member {O(p)} ({groups_rel(t)}) (Col)) value)'


def colors_of(x):
    return f'(project (join &t output ({x} Col)) {x})'


def color_role(holding):
    ROLE_TEXTS.append(holding)

    def make(t, x):
        return [f'(semijoin {colors_of(x)} {holding} ({x} Col))', colors_of(x)], share
    return make


def color_not_role(failing):
    ROLE_TEXTS.append(failing)

    def make(t, x):
        return [f'(antijoin {colors_of(x)} {failing} ({x} Col))', colors_of(x)], share
    return make


def count_of_rel(rel, column):
    return f'(component Cardinality (member {rel} () ({column})) size)'


@entry(*plain_or_key('C cells vs the output foreground cells'))
def cells_vs_foreground(t, p):
    return compare_tests(count_of_rel('&t', p), 'N', MEASURES['the output foreground count'][0], 'N'), from_tests


@entry(*plain_or_key(f'C groups of {GROUPS} their shape up to rotation and reflection determines their output color'), note='no shape class under D4: the images of the cells relative to the box, then Inclusion')
def shape_d4_determines(t, p):
    g = t.groups
    box = f'(component BoundingBox (cell {O(p)} ({words(g)}) ({p})) box)'
    placed = f'(lib-join (join {O(p)} {box} {group_pairs(t)}) relative (Base B) (X {p}))'
    images = f'(lib-join (join {placed} d4_elem) apply (D D) (P X_rel))'
    same = f'(component Inclusion (observed {images} () (({words(g)} D) P_out)) (pattern {placed} () ({fields(g)} X_rel)) equal)'
    one = one_color_of_group(t, p)
    second = ' '.join(f'({c}_2 {c})' for c in g)
    both = [(f'{c}_2', c) for c in g] + [('Col', 'Col')]
    return [all_of(f'(join {same} {one} {group_pairs(t)})', one, both)], holds


def moved_rows(p):
    return f'(select {IO(p)} Col != Col_2)'


@entry(*plain_or_key('C changed cells whose output color lies on their row or column in the input, proportion'))
def changed_on_input_lines(t, p):
    found = f'(join (lib-join {moved_rows(p)} split (P {p})) (lib-join input split (P P)) (A A) (Along Along) (Col_2 Col))'
    return [f'(project {found} {p})', f'(project {moved_rows(p)} {p})'], share


@entry(*plain_or_key('C changed cells whose output color lies on their diagonals in the input, proportion'))
def changed_on_input_diagonals(t, p):
    found = f'(join (lib-join {moved_rows(p)} corner_dist (P {p})) (lib-join input corner_dist (P P)) (Diag Diag) (K K) (Col_2 Col))'
    return [f'(project {found} {p})', f'(project {moved_rows(p)} {p})'], share


@entry(*plain_or_key('C bounding box is the output foreground box'))
def box_is_foreground_box(t, p):
    return [f'(join (component BoundingBox (cell &t () ({p})) box) {FOREGROUND_BOX} (B B))'], nonzero


def components_of_colors(grid, x):
    return f'(project (component Connectivity (node (join {grid} &t (Col {x})) () (P)) (step step_offset () (V)) component) Id)'


@entry(*plain_or_key('C output cell components'))
def output_components(t, x):
    return [components_of_colors('output', x)], count


@entry(*plain_or_key('C output cell components vs the input'))
def components_vs_input(t, x):
    return compare_tests(count_of_rel(components_of_colors('output', x), 'Id'), 'N', count_of_rel(components_of_colors('input', x), 'Id'), 'N'), from_tests


@entry(*plain_or_key(f'C groups of {GROUPS} vs the output foreground components'))
def groups_vs_components(t, p):
    left = f'(component Cardinality (member &t () ({fields(t.groups)})) size)'
    return compare_tests(left, 'N', MEASURES['the output foreground component count'][0], 'N'), from_tests


@entry(*plain_or_key('C vs the changed cells'))
def versus_changed(t, p):
    return versus_cells('&t', p, CHANGED, 'P', 'input')


def axis_rows(t, d):
    """T's rows with the axis of an orientation column."""
    kind = t.type_of(d)
    if kind in ('Axis', 'Axis4'):
        return '&t', d
    if kind == 'Dir':
        return f'(lib-join &t axis_of (D {d}))', 'A'
    return f'(lib-join &t axis4_of (D {d}))', 'A'


@entry(*plain_or_key('C the output extent along it vs the input'))
def extent_vs_input(t, d):
    rows, column = axis_rows(t, d)
    extents = '(join (project (lib-join output frame_extent (P P)) A N) (project (lib-join input frame_extent (P P)) A N) (A A))'
    at = f'(join {rows} {extents} ({column} A))'
    def how(n, f):
        held = [s for s, c in zip('<=>', n) if c]
        return held[0] if len(held) == 1 else 'mixed' if held else None
    keep = column
    return [f'(project (select {at} N {op} N_2) {keep})' for op in ('<', '=', '>')], how


@entry(*plain_or_key('C Jaccard index with the changed cells'), note='a share of two counts')
def jaccard_changed(t, p):
    both = f'(join (project &t {p}) {CHANGED} ({p} P))'
    either = f'(union (project &t {p}) (project {CHANGED} P) ({p} P))'
    return [both, either], lambda n, f: round(n[0] / n[1], 3) if n[1] else 1.0


@entry(*plain_or_key('C changed cells inside its bounding box, proportion'))
def changed_in_box(t, p):
    box = f'(component BoundingBox (cell {O(p)} () ({p})) box)'
    return [f'(project (lib-join (join {CHANGED} {box}) inside (A P) (B B)) P)', f'(project {CHANGED} P)'], share


COLOR_BOX = '(component BoundingBox (cell output (Col) (P)) box)'
COLOR_PLACED = f'(lib-join (join output {COLOR_BOX} (Col Col)) relative (Base B) (X P))'
COLOR_MISMATCH = f'(component Agreement (source {COLOR_PLACED} (Col) (X_rel Col)) (target {COLOR_PLACED} (Col) (X_rel Col)) (transform d4_elem () (D)) mismatch)'
COLOR_SYMMETRIC = f'(project (antijoin (join (project output Col) (antijoin d4_elem d4_identity (D D))) {COLOR_MISMATCH} (Col Col) (D D)) Col)'

for lead in ('C', 'key.C'):
    ENTRIES[f'{lead} colors with a symmetric cell set in the output, proportion'] = (color_role(COLOR_SYMMETRIC), 'no symmetry test on a cell set: Agreement on the cells relative to the box')
    ENTRIES[f'{lead} cells at a corner of the box of their component in the output, proportion'] = (role_share(f'(project (lib-join {IN_COMPONENT_BOX} same_corner (P1 P) (P2 B)) P)'), '')
    ENTRIES[f'{lead} cells at the center of the box of their component in the output, proportion'] = (role_share(f'(project (lib-join (lib-join {IN_COMPONENT_BOX} relative (Base B) (X P)) centered (P X_rel)) P)'), '')
    ENTRIES[f'{lead} cells at a tip of their component in the output, proportion'] = (role_share(f'(project (component Singleton (member {SAME_COLOR_NEIGHBOR} (P) (D)) value) P)'), '')
    ENTRIES[f'{lead} cells in a component of one cell in the output, proportion'] = (role_share(f'(antijoin output {SAME_COLOR_NEIGHBOR} (P P))'), '')
    ENTRIES[f'{lead} cells on a full line of one color in the output, proportion'] = (role_share(ON_FULL_LINE), '')
    ENTRIES[f'{lead} cells on the grid edge in the output, proportion'] = (role_share(f'(project {AT_ZERO_MARGIN} P)'), '')
    ENTRIES[f'{lead} cells at a grid corner in the output, proportion'] = (role_share('(project (select (lib-join output corner_dist (P P)) K = 0) P)'), '')
    ENTRIES[f'{lead} cells of the background next to the foreground in the output, proportion'] = (role_share(f'(antijoin (project (join (lib-join output neighbor (P P)) {FOREGROUND} (Q P)) P) {FOREGROUND} (P P))'), '')
    ENTRIES[f'{lead} cells of the background enclosed by the foreground in the output, proportion'] = (role_share(f'(project (component Enclosure (cell {BACKGROUND_CELLS} () (P)) enclosed) P)'), '')
    ENTRIES[f'{lead} colors that fill their boxes in the output, proportion'] = (color_not_role(f'(project (antijoin (lib-join (join {COMPONENT_BOX} output) inside (A P) (B B)) {COMPONENTS} (Col Col) (Id Id) (P P)) Col)'), '')
    ENTRIES[f'{lead} colors of one component in the output, proportion'] = (color_role(f'(component Singleton (member {COMPONENTS} (Col) (Id)) value)'), '')
    per_color_components = f'(component Cardinality (member {COMPONENTS} (Col) (Id)) size)'
    ENTRIES[f'{lead} colors with the most components in the output, proportion'] = (color_role(f'(component Order (member {per_color_components} () (Col)) (score {per_color_components} () (Col N)) maximal)'), '')
    ENTRIES[f'{lead} colors that fill whole lines in the output, proportion'] = (color_not_role(f'(project (antijoin output {ON_FULL_LINE} (P P)) Col)'), '')
    ENTRIES[f'{lead} colors that touch no edge in the output, proportion'] = (color_not_role(f'(project {AT_ZERO_MARGIN} Col)'), '')
    ENTRIES[f'{lead} colors that touch every edge in the output, proportion'] = (color_not_role(f'(project (antijoin (join (project output Col) dir_elem) {AT_ZERO_MARGIN} (Col Col) (D D)) Col)'), '')
    ENTRIES[f'{lead} colors that are single cells in the output, proportion'] = (color_not_role(f'(project {SAME_COLOR_NEIGHBOR} Col)'), '')
    foreground_sizes = f'(component Cardinality (member (antijoin {COMPONENTS} (component Singleton (member {BACKGROUND} () (Col)) value) (Col Col)) (Col Id) (P)) size)'
    ENTRIES[f'{lead} colors of the largest foreground component in the output, proportion'] = (color_role(f'(component Order (member {foreground_sizes} () ((Col Id))) (score {foreground_sizes} () ((Col Id) N)) maximal)'), '')
    free = '(antijoin (join (project output Col) (project output P)) output (P P) (Col Col))'
    enclosed = f'(component Enclosure (cell {free} (Col) (P)) enclosed)'
    ENTRIES[f'{lead} colors that enclose another color in the output, proportion'] = (color_role(enclosed), '')
    two_colors = '(select (join (project output Col) output) Col != Col_2)'
    failing = f'(project (antijoin {two_colors} {enclosed} (Col Col) (P P)) Col Col_2)'
    held_by = f'(project (antijoin (select (join (project output Col) (project output Col)) Col != Col_2) {failing} (Col Col) (Col_2 Col_2)) Col_2)'
    ENTRIES[f'{lead} colors enclosed by another color in the output, proportion'] = (lambda t, x, held_by=held_by: ([f'(project (join &t {held_by} ({x} Col_2)) {x})', colors_of(x)], share), '')


@entry(*plain_or_key('C is a union of components in the output'))
def union_of_components(t, p):
    held = f'(semijoin {COMPONENTS} (join &t {COMPONENTS} ({p} P)) (Col Col) (Id Id))'
    return [all_of(held, '&t', [('P', p)])], holds


@entry(*plain_or_key('C vs the colors the output drops'))
def versus_dropped(t, x):
    return versus_colors(x, DROPPED, 'Col')


@entry(*plain_or_key('C vs the colors the output adds'))
def versus_added(t, x):
    return versus_colors(x, ADDED, 'Col')


@entry(*plain_or_key('C vs the colors the changed cells take'))
def versus_taken(t, x):
    return versus_colors(x, f'(project {CHANGED} Col_2)', 'Col_2')


@entry(*plain_or_key('C vs the colors the changed cells had'))
def versus_had(t, x):
    return versus_colors(x, f'(project {CHANGED} Col)', 'Col')


@entry(*plain_or_key('C is the set of the colors the changed cells take'))
def set_of_taken(t, x):
    made, _ = versus_colors(x, f'(project {CHANGED} Col_2)', 'Col_2')
    taken = f'(project {CHANGED} Col_2)'
    return [f"(join {all_of('&t', taken, [(x, 'Col_2')])} {all_of(taken, '&t', [('Col_2', x)])})"], holds


@entry(*plain_or_key('C greatest distance from a changed cell'))
def greatest_distance(t, p):
    distance = f'(component CellDistance (node output () (P)) (source {O(p)} () ({p})) (step step_offset () (V)) distance)'
    return [maximum(f'(join {distance} {CHANGED} (P P))', 'K')], first_cell


def own_box_cells(rel, column):
    box = f'(component BoundingBox (cell {rel} () ({column})) box)'
    return f'(lib-join (join {rel} {box}) relative (Base B) (X {column}))'


@entry(*plain_or_key('C same shape as the output foreground'))
def same_shape_as_foreground(t, p):
    mine, theirs = own_box_cells('&t', p), own_box_cells(FOREGROUND, 'P')
    return [f"(join {all_of(mine, theirs, [('X_rel', 'X_rel')])} {all_of(theirs, mine, [('X_rel', 'X_rel')])})"], holds


@entry(*plain_or_key('C same shape up to rotation and reflection as the output foreground'))
def same_shape_d4(t, p):
    mine, theirs = own_box_cells('&t', p), own_box_cells(FOREGROUND, 'P')
    images = f'(lib-join (join {mine} d4_elem) apply (D D) (P X_rel))'
    over = f'(project (antijoin {images} {theirs} (P_out X_rel)) D)'
    under = f'(project (antijoin (join {theirs} d4_elem) {images} (D D) (X_rel P_out)) D)'
    return [f'(antijoin (antijoin d4_elem {over} (D D)) {under} (D D))'], nonzero


def cells_of_colors(grid, x):
    return f'(project (join {grid} &t (Col {x})) P)'


@entry(*plain_or_key('C input cells vs the changed cells'))
def input_cells_vs_changed(t, x):
    return versus_cells(cells_of_colors('input', x), 'P', CHANGED, 'P', 'output')


@entry(*plain_or_key('C output cells vs the changed cells'))
def output_cells_vs_changed(t, x):
    return versus_cells(cells_of_colors('output', x), 'P', CHANGED, 'P', 'output')


@entry(*plain_or_key('C,C agrees with the output colors, proportion'))
def agrees_with_output(t, p, x):
    return [f'(join &t output ({p} P) ({x} Col))', '&t'], share


def agreement_keyed(t, keys, rest, rows):
    on = ' '.join(f'({k} {k})' for k in keys)
    per = f'(component Cardinality (member {rows} ({words(keys)} Col) ({rest})) size)'
    most = f'(component Order (member {per} ({words(keys)}) (Col)) (score {per} ({words(keys)}) (Col N)) maximal)'
    one_most = f'(component Singleton (member {most} ({words(keys)}) (Col)) value)'
    one_row = f'(component Singleton (member &t ({words(keys)}) ({rest})) value)'
    return f'(join {rows} (antijoin {one_most} {one_row} {on}) {on} (Col Col))'


@entry(*plain_or_key('C output color under its other columns agrees with the other rows of its value, proportion'))
def output_agrees_under_others(t, p):
    return [agreement_keyed(t, t.others(p), p, O(p)), '&t'], share


@entry(*plain_or_key('C whether it changes under its other columns agrees with the other rows of its value, proportion'))
def change_agrees_under_others(t, p):
    keys = t.others(p)
    on = ' '.join(f'({k} {k})' for k in keys)
    changed, kept = kept_and_changed(p)
    counted = lambda rows: f'(component Cardinality (member {rows} ({words(keys)}) ({p})) (domain &t ({words(keys)})) size)'
    one_row = f'(component Singleton (member &t ({words(keys)}) ({p})) value)'
    wins = lambda op: f'(antijoin (select (join {counted(changed)} {counted(kept)} {on}) N {op} N_2) {one_row} {on})'
    return [f'(join {changed} {wins(">")} {on})', f'(join {kept} {wins("<")} {on})', '&t'], lambda n, f: ratio(n[0] + n[1], n[2])


@entry(*plain_or_key('C,C vs the output cells of its colors'))
def versus_output_cells(t, p, x):
    return versus_cells('&t', p, cells_of_colors('output', x), 'P', 'output')


def group_flag_determines(t, p, flagged):
    """Whether a group property of two values gives one color per value: the colors of each side."""
    one = one_color_of_group(t, p)
    on = group_pairs(t)
    on_same = ' '.join(f'({c} {c})' for c in t.groups)
    return [f'(project (join {one} {flagged} {on_same}) Col)', f'(project (antijoin {one} {flagged} {on_same}) Col)'], lambda n, f: n[0] < 2 and n[1] < 2


@entry(*plain_or_key(f'C groups of {GROUPS} their size determines their output color'))
def size_determines(t, p):
    sizes = f'(component Cardinality (member {O(p)} ({groups_rel(t)}) ({p})) size)'
    on = ' '.join(f'({c} {c})' for c in t.groups)
    return [determines_form(f'(join {sizes} {one_color_of_group(t, p)} {on})', ['N'], 'Col')], holds


@entry(*plain_or_key(f'C groups of {GROUPS} their holes determines their output color'))
def holes_determine(t, p):
    g = groups_rel(t)
    on = ' '.join(f'({c} {c})' for c in t.groups)
    free = f'(antijoin (join (project {O(p)} {g}) (project output P)) {O(p)} {on} (P {p}))'
    enclosed = f'(component Enclosure (cell {free} ({g}) (P)) enclosed)'
    counted = f'(component Cardinality (member {enclosed} ({g}) (Id)) (domain {O(p)} ({g})) size)'
    return [determines_form(f'(join {counted} {one_color_of_group(t, p)} {on})', ['N'], 'Col')], holds


@entry(*plain_or_key(f'C groups of {GROUPS} their touching the edge determines their output color'))
def touching_determines(t, p):
    touching = f'(project (select (lib-join {O(p)} margin (B {p})) K = 0) {groups_rel(t)})'
    return group_flag_determines(t, p, touching)


@entry(*plain_or_key(f'C groups of {GROUPS} their filling its box determines their output color'))
def filling_determines(t, p):
    g = groups_rel(t)
    on = ' '.join(f'({c} {c})' for c in t.groups)
    box = f'(component BoundingBox (cell {O(p)} ({g}) ({p})) box)'
    gaps = f'(project (antijoin (lib-join (join {box} (project output P)) inside (A P) (B B)) {O(p)} {on} (P {p})) {g})'
    return group_flag_determines(t, p, gaps)


@entry(*plain_or_key(f'C groups of {GROUPS} their symmetry determines their output color'))
def symmetry_determines(t, p):
    g = groups_rel(t)
    on = ' '.join(f'({c} {c})' for c in t.groups)
    box = f'(component BoundingBox (cell {O(p)} ({g}) ({p})) box)'
    placed = f'(lib-join (join {O(p)} {box} {on}) relative (Base B) (X {p}))'
    mismatch = f'(component Agreement (source {placed} ({g}) (X_rel Col)) (target {placed} ({g}) (X_rel Col)) (transform d4_elem () (D)) mismatch)'
    holding = f'(antijoin (join (project {O(p)} {g}) d4_elem) {mismatch} {on} (D D))'
    counted = f'(component Cardinality (member {holding} ({g}) (D)) size)'
    return [determines_form(f'(join {counted} {one_color_of_group(t, p)} {on})', ['N'], 'Col')], holds


@entry(*plain_or_key('C changed cells within Chebyshev distance 1, proportion'))
def changed_near(t, p):
    near = f'(union (project (lib-join {O(p)} neighbor (P {p})) Q) (project {O(p)} {p}) (Q {p}))'
    return [f'(project (join {CHANGED} {near} (P Q)) P)', f'(project {CHANGED} P)'], share


def moved_groups(t, p):
    return f'(project {moved_rows(p)} {groups_rel(t)})'


@entry(*plain_or_key(f'C groups of {GROUPS} whose changed cells take one color, proportion'))
def groups_take_one(t, p):
    return [f'(component Singleton (member {moved_rows(p)} ({groups_rel(t)}) (Col_2)) value)', moved_groups(t, p)], share


@entry(*plain_or_key(f'C groups of {GROUPS} whose changed cells take colors they hold, proportion'))
def groups_take_held(t, p):
    on = ' '.join(f'({c} {c})' for c in t.groups)
    failing = f'(project (antijoin {moved_rows(p)} {I(p)} {on} (Col_2 Col)) {groups_rel(t)})'
    return [f'(antijoin {moved_groups(t, p)} {failing} {on})', moved_groups(t, p)], share


@entry(*plain_or_key(f'C groups of {GROUPS} whose changed cells take colors around them, proportion'))
def groups_take_around(t, p):
    on = ' '.join(f'({c} {c})' for c in t.groups)
    around = f'(antijoin (join (lib-join {O(p)} neighbor (P {p})) input (Q P)) {O(p)} {on} (Q {p}))'
    failing = f'(project (antijoin {moved_rows(p)} {around} {on} (Col_2 Col_2)) {groups_rel(t)})'
    return [f'(antijoin {moved_groups(t, p)} {failing} {on})', moved_groups(t, p)], share


@entry(*plain_or_key(f'C groups of {GROUPS} that change, proportion'))
def groups_that_change(t, p):
    return [moved_groups(t, p), f'(project {O(p)} {groups_rel(t)})'], share


@entry(*plain_or_key(f'C groups of {GROUPS} that change wholly, proportion'))
def groups_change_wholly(t, p):
    on = ' '.join(f'({c} {c})' for c in t.groups)
    kept = f'(join {I(p)} output ({p} P) (Col Col))'
    return [f'(antijoin {moved_groups(t, p)} {kept} {on})', f'(project {O(p)} {groups_rel(t)})'], share


@entry(*plain_or_key('C output count vs the input count'))
def count_vs_input(t, x):
    per = lambda grid: f'(component Cardinality (member {grid} (Col) (P)) (domain (project &t {x}) ({x})) size)'
    both = f'(join (join (project &t {x}) {per("output")} ({x} Col)) {per("input")} ({x} Col))'
    def how(n, f):
        held = [s for s, c in zip('<=>', n) if c]
        return held[0] if len(held) == 1 else 'mixed'
    return [f'(select {both} N {op} N_2)' for op in ('<', '=', '>')], how


def rows_in_boxes(b, rel=None):
    return f'(lib-join (join {rel or f"(project &t {b})"} output) inside (A P) (B {b}))'


@entry(*plain_or_key('C,C determines the output colors in the box'))
def determines_box_colors(t, b, x):
    colors = rows_in_boxes(b)
    same = f'(component Inclusion (pattern {colors} () ({b} Col)) (observed {colors} () ({b} Col)) equal)'
    rows = f'(project &t {b} {x})'
    return [all_of(f'(join {rows} {rows} ({x} {x}))', same, [(b, b), (f'{b}_2', f'{b}_2')])], holds


@entry(*plain_or_key(f'C groups of {GROUPS} that are components in the output, proportion'))
def groups_are_components(t, p):
    same = f'(component Inclusion (observed {O(p)} () ({fields(t.groups)} {p})) (pattern {COMPONENTS} () ((Col Id) P)) equal)'
    return [f'(project {same} {groups_rel(t)})', f'(project {O(p)} {groups_rel(t)})'], share


@entry(*plain_or_key('C,C has a changed cell toward it, proportion'))
def changed_toward(t, p, d):
    rows = f'(project &t {p} {d})'
    return [f'(project (lib-join (join {rows} {CHANGED}) gap (D {d}) (P {p}) (Q P)) {p} {d})', rows], share


@entry(*plain_or_key('C vs the output foreground'))
def versus_foreground(t, p):
    return versus_cells('&t', p, FOREGROUND, 'P', 'output')


@entry(*plain_or_key('C,C the output color is the input color or this color, proportion'))
def input_or_this(t, p, x):
    columns = words(t.columns)
    same = ' '.join(f'({c} {c})' for c in t.columns)
    kept = f'(project (join {I(p)} output ({p} P) (Col Col)) {columns})'
    return [f'(union {kept} (join &t output ({p} P) ({x} Col)) {same})', I(p)], share


def colored_occurrences(t, p, x, extra=''):
    keys = t.ids or [x]
    return f'(component Occurrences (shape &t ({words(keys)}) ({p} {x})) (cell output () (P Col)) {extra} occurrence)', keys


@entry(*plain_or_key('C,C occurs in the output in place, proportion'))
def colored_in_place(t, p, x):
    found, keys = colored_occurrences(t, p, x)
    return [f'(project (select {found} P = 0) {words(keys)})', f'(project &t {words(keys)})'], share


@entry(*plain_or_key('C,C occurs elsewhere in the output, proportion'))
def colored_elsewhere(t, p, x):
    found, keys = colored_occurrences(t, p, x)
    return [f'(project (select {found} P != 0) {words(keys)})', f'(project &t {words(keys)})'], share


@entry(*plain_or_key('C,C occurs in the output up to rotation and reflection, proportion'))
def colored_d4(t, p, x):
    found, keys = colored_occurrences(t, p, x, '(transform d4_elem () (D))')
    return [f'(project {found} {words(keys)})', f'(project &t {words(keys)})'], share


@entry(*plain_or_key('C covers the output, proportion'))
def covers_output(t, x):
    return [cells_of_colors('output', x), 'output'], share


@entry(*plain_or_key('C boxes of one output color, proportion'))
def boxes_one_color(t, b):
    held = rows_in_boxes(b)
    return [f'(component Singleton (member {held} ({b}) (Col)) value)', f'(project {held} {b})'], share


@entry(*plain_or_key('C output colors inside its boxes distinct'))
def colors_in_boxes(t, b):
    return [f'(project {rows_in_boxes(b)} Col)'], count


def changed_in_boxes(b):
    return f'(lib-join (join (project &t {b}) {CHANGED}) inside (A P) (B {b}))'


@entry(*plain_or_key('C boxes holding a changed cell, proportion'))
def boxes_holding_changed(t, b):
    return [f'(project {changed_in_boxes(b)} {b})', f'(project {rows_in_boxes(b)} {b})'], share


@entry(*plain_or_key('C changed cells inside its boxes, proportion'))
def changed_inside_boxes(t, b):
    return [f'(project {changed_in_boxes(b)} P)', f'(project {CHANGED} P)'], share


@entry(*plain_or_key('C some box is the box of the changed cells'))
def box_of_changed(t, b):
    return [f'(join &t (component BoundingBox (cell {CHANGED} () (P)) box) ({b} B))'], nonzero


@entry(*plain_or_key('C boxes that are the box of a component in the output, proportion'))
def boxes_of_components(t, b):
    return [f'(project (join &t {COMPONENT_BOX} ({b} B)) {b})', f'(project &t {b})'], share


@entry(*plain_or_key('C,C is the output color of the box, proportion'))
def color_of_box(t, b, x):
    held = rows_in_boxes(b, f'(project &t {b} {x})')
    failing = f'(select {held} Col != {x})'
    return [f'(join &t (antijoin (project {held} {b} {x}) {failing} ({b} {b}) ({x} {x})) ({b} {b}) ({x} {x}))', '&t'], share


@entry(*plain_or_key('C,C color counts agree with the output, proportion'))
def color_counts_agree(t, p, x):
    per = f'(component Cardinality (member &t ({x}) ({p})) size)'
    return [f'(join {per} {PER_COLOR} ({x} Col) (N N))', f'(project &t {x})'], share


@entry(*plain_or_key('C rows per value agree with the output color counts, proportion'))
def rows_per_value_agree(t, x):
    per = f'(component Cardinality (member &t ({x}) ({fields(t.others(x))})) size)'
    return [f'(join {per} {PER_COLOR} ({x} Col) (N N))', f'(project &t {x})'], share


@entry(*plain_or_key('C,C is the output count of the color, proportion'))
def number_is_count(t, x, n):
    per = f'(component Cardinality (member output (Col) (P)) (domain (project &t {x}) ({x})) size)'
    return [f'(join (project &t {x} {n}) {per} ({x} Col) ({n} N))', f'(project &t {x} {n})'], share


@entry(*plain_or_key('C,C groups per color are the output counts, proportion'))
def groups_are_counts(t, x, g):
    per = f'(component Cardinality (member &t ({x}) ({g})) size)'
    return [f'(join {per} {PER_COLOR} ({x} Col) (N N))', f'(project &t {x})'], share


# ---- the remaining ranks

INPUT_BOX = f'(component BoundingBox (cell {INPUT_FOREGROUND} () (P)) box)'
CHANGED_BOX = f'(component BoundingBox (cell {CHANGED} () (P)) box)'
OUTPUT_EXTENTS = '(project (lib-join output frame_extent (P P)) A N)'


def input_and_output_at(p, q):
    return f'(join (join &t input ({p} P)) output ({q} P))'


@entry(*plain_or_key('C,C carries the input colors to the output, proportion'))
def carries_colors(t, p, q):
    return [f'(project (join (join &t input ({p} P)) output ({q} P) (Col Col)) {p} {q})', f'(project {input_and_output_at(p, q)} {p} {q})'], share


@entry(*plain_or_key('C,C covers the output cells, proportion'))
def covers_output_cells(t, p, q):
    return [f'(project {input_and_output_at(p, q)} {q})', 'output'], share


@entry(*plain_or_key('C,C translates the input color onto the output, proportion'))
def translates_color(t, p, v):
    moved = f'(lib-join {I(p)} compose (A {p}) (B {v}))'
    return [f'(project (join {moved} output (C P) (Col Col)) {p} {v})', f'(project (join {moved} output (C P)) {p} {v})'], share


@entry(*plain_or_key('C,C rotates or reflects the input color onto the output, proportion'))
def turns_color(t, p, d):
    moved = f'(lib-join {I(p)} apply (D {d}) (P {p}))'
    return [f'(project (join {moved} output (P_out P) (Col Col)) {p} {d})', f'(project (join {moved} output (P_out P)) {p} {d})'], share


@entry(*plain_or_key('C includes the translation of the foreground into the output'))
def includes_translation(t, v):
    moved = f'(lib-join (join {INPUT_BOX} {FOREGROUND_BOX}) relative (Base B) (X B_2))'
    return [f'(join &t {moved} ({v} X_rel))'], nonzero


@entry(*plain_or_key('C translates the input foreground onto the output foreground, proportion'))
def translates_foreground(t, v):
    offsets = f'(project &t {v})'
    moved = f'(lib-join (join {offsets} {INPUT_FOREGROUND}) compose (A P) (B {v}))'
    over = f'(project (antijoin {moved} {FOREGROUND} (C P)) {v})'
    under = f'(project (antijoin (join {offsets} {FOREGROUND}) {moved} ({v} {v}) (P C)) {v})'
    return [f'(antijoin (antijoin {offsets} {over} ({v} {v})) {under} ({v} {v}))', offsets], share


def keeps_grid(source):
    def make(t, d):
        turns = f'(project &t {d})'
        mismatch = f'(component Agreement (source {source} () (P Col)) (target output () (P Col)) (transform {turns} () ({d})) mismatch)'
        return [f'(antijoin {turns} {mismatch} ({d} D))', turns], share
    return make


for lead in ('C', 'key.C'):
    ENTRIES[f'{lead} keeps the output, proportion'] = (keeps_grid('output'), '')
    ENTRIES[f'{lead} maps the input to the output, proportion'] = (keeps_grid('input'), '')


def lines_of_column(t, d):
    """The axes of an orientation column, under the column A."""
    kind = t.type_of(d)
    if kind in ('Axis', 'DiagAxis', 'Axis4'):
        return f'(project &t {d})', d
    relation = {'Dir': 'axis_of', 'DiagDir': 'diag_axis_of', 'Dir8': 'axis4_of'}[kind]
    column = 'Da' if kind == 'DiagDir' else 'A'
    return f'(project (lib-join &t {relation} (D {d})) {column})', column


def reflection_keeps(relation):
    def make(t, d):
        lines, column = lines_of_column(t, d)
        if t.type_of(d) not in ('Axis', 'Dir'):
            not_square = '(select (lib-join output axis_extents (P P)) N1 != N2)'
            lines = f'(antijoin {lines} (join diag_axis_elem {not_square}) ({column} Da))'
        turns = f'(lib-join {lines} {relation} (A {column}))'
        mismatch = f'(component Agreement (source output () (P Col)) (target output () (P Col)) (transform {turns} () (T)) mismatch)'
        return [f'(antijoin {turns} {mismatch} (T D))', turns], share
    return make


for lead in ('C', 'key.C'):
    ENTRIES[f'{lead} the output is unchanged by the reflection across it, proportion'] = (reflection_keeps('reflection'), '')
    ENTRIES[f'{lead} the output is unchanged by the reflection that swaps it, proportion'] = (reflection_keeps('axis_inversion'), '')


def margins_of(box):
    return f'(lib-join {box} margin (B B))'


def reaches_past(ahead, behind):
    """The edges toward which one box goes past the other."""
    return f'(select (join {margins_of(ahead)} {margins_of(behind)} (D D)) K < K_2)'


def toward_each(t, d, holding):
    """The share of a direction column's values that holding gives, a corner needing both of its edges."""
    values = f'(project &t {d})'
    kind = t.type_of(d)
    straight = f'(project (join &t {holding} ({d} D)) {d})'
    if kind == 'Dir':
        return [straight, values], share
    failing = f'(project (antijoin (lib-join {values} corner_dir (C {d})) {holding} (D D)) {d})'
    corners = f'(antijoin (join {values} diag_dir_elem ({d} D)) {failing} ({d} {d}))'
    if kind == 'DiagDir':
        return [corners, values], share
    return [f'(union {straight} (project {corners} {d}) ({d} {d}))', values], share


@entry(*plain_or_key('C the changed cells reach past the input foreground toward it, proportion'))
def changed_reach(t, d):
    return toward_each(t, d, reaches_past(CHANGED_BOX, INPUT_BOX))


@entry(*plain_or_key('C the output foreground reaches past the input foreground toward it, proportion'))
def output_reach(t, d):
    return toward_each(t, d, reaches_past(FOREGROUND_BOX, INPUT_BOX))


@entry(*plain_or_key('C the output foreground moves toward it, proportion'))
def output_moves(t, d):
    moved = f'(lib-join (join {INPUT_BOX} {FOREGROUND_BOX}) relative (Base B) (X B_2))'
    return toward_each(t, d, f'(select (lib-join {moved} dist_pair (P X_rel)) K < K2)')


@entry(*plain_or_key('C the output foreground is stable under gravity toward it, proportion'))
def gravity(t, d):
    dirs = f'(project (join &t dir_elem ({d} D)) {d})'
    failing = f'(project (antijoin (join (lib-join {FOREGROUND} neighbor (P P)) output (Q P)) {FOREGROUND} (Q P)) D)'
    return [f'(antijoin {dirs} {failing} ({d} D))', dirs], share


def number_equals_margin(box):
    def make(t, d, n):
        rows = f'(project &t {d} {n})'
        return [f'(project (join {rows} {margins_of(box)} ({d} D) ({n} K)) {d} {n})', rows], share
    return make


for kind in plain_or_key('C,C is the changed cells margin toward it, proportion'):
    ENTRIES[kind] = (number_equals_margin(CHANGED_BOX), '')
for kind in plain_or_key('C,C is the output foreground margin toward it, proportion'):
    ENTRIES[kind] = (number_equals_margin(FOREGROUND_BOX), '')


@entry(*plain_or_key('C,C is the output extent along it, proportion'))
def number_is_extent(t, d, n):
    rows = f'(project &t {d} {n})'
    kind = t.type_of(d)
    if kind == 'Axis':
        return [f'(project (join {rows} {OUTPUT_EXTENTS} ({d} A) ({n} N)) {d} {n})', rows], share
    relation = 'axis_of' if kind == 'Dir' else 'axis4_of'
    return [f'(project (join (lib-join {rows} {relation} (D {d})) {OUTPUT_EXTENTS} (A A) ({n} N)) {d} {n})', rows], share


def one_translation(found, shape, keys, only=''):
    on = ' '.join(f'({k} {k})' for k in keys)
    moves = f'(project {found} P)'
    failing = f'(project (antijoin (join (project {shape} {words(keys)}) {moves}) {found} {on} (P P)) P)'
    return [f'(select (antijoin {moves} {failing} (P P)) P != 0)'], nonzero


@entry(*plain_or_key('C one translation takes them all into the output'))
def one_translation_plain(t, p):
    if not t.ids:
        return [f'(select (component Occurrences (shape {I(p)} () ({p} Col)) (cell output () (P Col)) occurrence) P != 0)'], nonzero
    found = f'(component Occurrences (shape {I(p)} ({words(t.ids)}) ({p} Col)) (cell output () (P Col)) occurrence)'
    return one_translation(found, I(p), t.ids)


@entry(*plain_or_key('C,C one translation takes them all into the output'))
def one_translation_colored(t, p, x):
    found, keys = colored_occurrences(t, p, x)
    return one_translation(found, '&t', keys)


@entry(*plain_or_key('C changed cells in its holes, proportion'))
def changed_in_holes(t, p):
    holes = f'(component Enclosure (cell (antijoin output &t (P {p})) () (P)) enclosed)'
    return [f'(project (join {CHANGED} {holes} (P P)) P)', f'(project {CHANGED} P)'], share


def between(t, p, elements, relation):
    toward = f'(project (lib-join (join (project {CHANGED} P) (project {O(p)} {p})) gap (P P) (Q {p})) P D)'
    return [f'(project (join (lib-join (join {toward} {elements} (D D)) {relation} (D D)) {toward} (P P) ({"Opp"} D)) P)', f'(project {CHANGED} P)'], share


@entry(*plain_or_key('C changed cells between two of its cells on a line, proportion'))
def changed_between_lines(t, p):
    return between(t, p, 'dir_elem', 'opposite')


@entry(*plain_or_key('C changed cells between two of its cells on a diagonal, proportion'))
def changed_between_diagonals(t, p):
    return between(t, p, 'diag_dir_elem', 'diag_opposite')


@entry(*plain_or_key('C is the set of output line colors'))
def set_of_line_colors(t, x):
    return [f"(join {all_of('&t', 'output', [(x, 'Col')])} {all_of('output', '&t', [('Col', x)])})"], holds


@entry(*plain_or_key('C,C output count as it rises'))
def count_rises(t, x, n):
    counted = f'(component Cardinality (member output (Col) (P)) (domain (project &t {x}) ({x})) size)'
    rows = f'(join (project &t {x} {n}) {counted} ({x} Col))'
    pairs = f'(select (join {rows} {rows}) {n} < {n}_2)'
    ties = f'(select (join {rows} {rows} ({n} {n})) N != N_2)'
    def how(c, f):
        if c[2]:
            return 'neither'
        return 'rises' if not c[0] else 'falls' if not c[1] else 'neither'
    return [f'(select {pairs} N > N_2)', f'(select {pairs} N < N_2)', ties], how


def group_cells_relative(t, p):
    g = t.groups
    on = ' '.join(f'({c} {c})' for c in g)
    box = f'(component BoundingBox (cell &t ({words(g)}) ({p})) box)'
    return f'(lib-join (join &t {box} {on}) relative (Base B) (X {p}))'


FOREGROUND_PARTS = f'(component Connectivity (node {FOREGROUND} () (P)) (step step_offset () (V)) component)'
PART_BOX = f'(component BoundingBox (cell {FOREGROUND_PARTS} (Id) (P)) box)'
PART_CELLS = f'(lib-join (join {FOREGROUND_PARTS} {PART_BOX} (Id Id)) relative (Base B) (X P))'


@entry(*plain_or_key('C group shapes vs the output foreground component shapes'))
def group_shapes_vs(t, p):
    g = t.groups
    on = ' '.join(f'({c} {c})' for c in g)
    same = f'(component Inclusion (observed {group_cells_relative(t, p)} () ({fields(g)} X_rel)) (pattern {PART_CELLS} () (Id X_rel)) equal)'
    return [f'(antijoin (project &t {words(g)}) {same} {on})', f'(antijoin (project {FOREGROUND_PARTS} Id) {same} (Id Id))', same], set_relation


def group_flag_change(t, p, flagged):
    """Whether a group property of two values gives whether the group changes: a side that holds both kinds says no."""
    changing = moved_groups(t, p)
    on = ' '.join(f'({c} {c})' for c in t.groups)
    groups = f'(project {O(p)} {groups_rel(t)})'
    yes, no = f'(join {groups} {flagged} {on})', f'(antijoin {groups} {flagged} {on})'
    both = lambda side: [f'(join {side} {changing} {on})', f'(antijoin {side} {changing} {on})']
    a, b = both(yes), both(no)
    return a + b, lambda n, f: not (n[0] and n[1]) and not (n[2] and n[3])


def number_of_groups_change(t, p, counted):
    changing = moved_groups(t, p)
    on = ' '.join(f'({c} {c})' for c in t.groups)
    both = f'(semijoin (join {counted} {changing} {on}) (antijoin {counted} {changing} {on}) (N N))'
    return [all_of(counted, f'(antijoin (project {counted} N) {both} (N N))', [('N', 'N')])], holds


@entry(*plain_or_key(f'C groups of {GROUPS} their size determines whether they change'))
def size_change(t, p):
    return number_of_groups_change(t, p, f'(component Cardinality (member {O(p)} ({groups_rel(t)}) ({p})) size)')


@entry(*plain_or_key(f'C groups of {GROUPS} their holes determines whether they change'))
def holes_change(t, p):
    g = groups_rel(t)
    on = ' '.join(f'({c} {c})' for c in t.groups)
    free = f'(antijoin (join (project {O(p)} {g}) (project output P)) {O(p)} {on} (P {p}))'
    enclosed = f'(component Enclosure (cell {free} ({g}) (P)) enclosed)'
    return number_of_groups_change(t, p, f'(component Cardinality (member {enclosed} ({g}) (Id)) (domain {O(p)} ({g})) size)')


@entry(*plain_or_key(f'C groups of {GROUPS} their symmetry determines whether they change'))
def symmetry_change(t, p):
    g = groups_rel(t)
    on = ' '.join(f'({c} {c})' for c in t.groups)
    box = f'(component BoundingBox (cell {O(p)} ({g}) ({p})) box)'
    placed = f'(lib-join (join {O(p)} {box} {on}) relative (Base B) (X {p}))'
    mismatch = f'(component Agreement (source {placed} ({g}) (X_rel Col)) (target {placed} ({g}) (X_rel Col)) (transform d4_elem () (D)) mismatch)'
    holding = f'(antijoin (join (project {O(p)} {g}) d4_elem) {mismatch} {on} (D D))'
    return number_of_groups_change(t, p, f'(component Cardinality (member {holding} ({g}) (D)) size)')


@entry(*plain_or_key(f'C groups of {GROUPS} their touching the edge determines whether they change'))
def touching_change(t, p):
    return group_flag_change(t, p, f'(project (select (lib-join {O(p)} margin (B {p})) K = 0) {groups_rel(t)})')


@entry(*plain_or_key(f'C groups of {GROUPS} their filling its box determines whether they change'))
def filling_change(t, p):
    g = groups_rel(t)
    on = ' '.join(f'({c} {c})' for c in t.groups)
    box = f'(component BoundingBox (cell {O(p)} ({g}) ({p})) box)'
    return group_flag_change(t, p, f'(project (antijoin (lib-join (join {box} (project output P)) inside (A P) (B B)) {O(p)} {on} (P {p})) {g})')


@entry(*plain_or_key(f'C groups of {GROUPS} their shape determines whether they change'))
def shape_change(t, p):
    g = t.groups
    on = ' '.join(f'({c} {c})' for c in g)
    second = ' '.join(f'({c}_2 {c})' for c in g)
    changing = moved_groups(t, p)
    both = [(f'{c}_2', c) for c in g]
    return [all_of(f'(join {group_shapes_same(t, p)} {changing} {on})', changing, both)], holds


@entry(*plain_or_key('C,C Jaccard index with the output cells in the frame'), note='a share of two counts')
def jaccard_frame(t, p, x):
    rows = f'(project &t {p} {x})'
    return [f'(join {rows} output ({p} P) ({x} Col))', f'(union {rows} output ({p} P) ({x} Col))'], lambda n, f: round(n[0] / n[1], 3) if n[1] else 1.0


def boxes_in_grid(b):
    """The boxes of a column with no margin below 0."""
    return f'(antijoin (project &t {b}) (select (lib-join (project &t {b}) margin (B {b})) K < 0) ({b} {b}))'


def box_crop(b, rows=None):
    """Each box's input cells, with their places in the box's own frame."""
    rows = rows or boxes_in_grid(b)
    return f'(lib-join (lib-join (join {rows} input) inside (A P) (B {b})) relative (Base {b}) (X P))'


@entry(*plain_or_key('C some box crop of the input is the output'))
def crop_is_output(t, b):
    held = box_crop(b)
    return [all_of(held, 'output', [('X_rel', 'P'), ('Col', 'Col')], b)], holds


@entry(*plain_or_key('C some box crop of the input is the output up to rotation and reflection'))
def crop_is_output_d4(t, b):
    held = f'(lib-join (join {box_crop(b)} d4_elem) apply (D D) (P X_rel))'
    return [all_of(held, 'output', [('P_out', 'P'), ('Col', 'Col')], f'{b} D')], holds


@entry(*plain_or_key('C some box crop of the input maps onto the output by a color map'))
def crop_maps_output(t, b):
    held = box_crop(b)
    placed = f'(join {held} output (X_rel P))'
    return [f"(join {all_of(held, 'output', [('X_rel', 'P')], b)} {all_of(placed, single_values(placed, [b, 'Col'], 'Col_2'), [(b, b), ('Col', 'Col')], b)} ({b} {b}))"], holds


@entry(*plain_or_key('C some box has the output size'))
def box_has_output_size(t, b):
    extents = f'(project (lib-join (join (project &t {b}) input) box_extent (B {b}) (P P)) {b} A N)'
    failing = f'(project (antijoin {extents} {OUTPUT_EXTENTS} (A A) (N N)) {b})'
    return [f'(antijoin (project &t {b}) {failing} ({b} {b}))'], nonzero


@entry(*plain_or_key('C bounding box has the output size'))
def bounding_box_has_size(t, p):
    box = f'(component BoundingBox (cell &t () ({p})) box)'
    extents = f'(project (lib-join (join {box} (project &t {p})) box_extent (B B) (P {p})) A N)'
    return [all_of(extents, OUTPUT_EXTENTS, [('A', 'A'), ('N', 'N')])], holds


@entry(*plain_or_key('C is a period of the output, proportion'))
def period_of_output(t, n):
    values = f'(project (select &t {n} > 0) {n})'
    return [f'(project (join &t (component Periods (cell output () (P Col)) period) ({n} K)) {n})', values], share


@entry(*plain_or_key('C,C every cell toward it is changed, proportion'))
def every_toward_changed(t, p, d):
    rows = f'(project &t {p} {d})'
    ahead = f'(lib-join (join {rows} output) gap (D {d}) (P {p}) (Q P))'
    return [all_of(ahead, CHANGED, [('P', 'P')], f'{p} {d}'), rows], share


@entry(*plain_or_key(f'C groups of {GROUPS} some group box crop of the input is the output'))
def group_crop(t, p):
    g = t.groups
    box = f'(component BoundingBox (cell &t ({words(g)}) ({p})) box)'
    held = f'(lib-join (lib-join (join {box} input) inside (A P) (B B)) relative (Base B) (X P))'
    failing = f'(project (antijoin {held} output (X_rel P) (Col Col)) B)'
    return [f'(antijoin (project {box} B) {failing} (B B))'], nonzero


@entry(*plain_or_key(f'C groups of {GROUPS} some group box crop of the input is the output up to rotation and reflection'))
def group_crop_d4(t, p):
    g = t.groups
    box = f'(project (component BoundingBox (cell &t ({words(g)}) ({p})) box) B)'
    held = f'(lib-join (join (lib-join (lib-join (join {box} input) inside (A P) (B B)) relative (Base B) (X P)) d4_elem) apply (D D) (P X_rel))'
    failing = f'(project (antijoin {held} output (P_out P) (Col Col)) B D)'
    return [f'(antijoin (join {box} d4_elem) {failing} (B B) (D D))'], nonzero


@entry(*plain_or_key(f'C groups of {GROUPS} their shape up to rotation and reflection determines whether they change'))
def shape_d4_change(t, p):
    g = t.groups
    on = ' '.join(f'({c} {c})' for c in g)
    second = ' '.join(f'({c}_2 {c})' for c in g)
    box = f'(component BoundingBox (cell {O(p)} ({words(g)}) ({p})) box)'
    placed = f'(lib-join (join {O(p)} {box} {on}) relative (Base B) (X {p}))'
    images = f'(lib-join (join {placed} d4_elem) apply (D D) (P X_rel))'
    same = f'(component Inclusion (observed {images} () (({words(g)} D) P_out)) (pattern {placed} () ({fields(g)} X_rel)) equal)'
    changing = moved_groups(t, p)
    both = [(f'{c}_2', c) for c in g]
    return [all_of(f'(join {same} {changing} {on})', changing, both)], holds


@entry(*plain_or_key('C group shapes up to rotation and reflection vs the output foreground component shapes'))
def group_shapes_d4_vs(t, p):
    g = t.groups
    on = ' '.join(f'({c} {c})' for c in g)
    images = f'(lib-join (join {group_cells_relative(t, p)} d4_elem) apply (D D) (P X_rel))'
    same = f'(component Inclusion (observed {images} () (({words(g)} D) P_out)) (pattern {PART_CELLS} () (Id X_rel)) equal)'
    return [f'(antijoin (project &t {words(g)}) {same} {on})', f'(antijoin (project {FOREGROUND_PARTS} Id) {same} (Id Id))', same], set_relation


def toward_foreground(elements):
    toward = f'(project (lib-join (join (project {BACKGROUND_CELLS} P) (project {FOREGROUND} P)) gap (P P) (Q P_2)) P D)'
    return f'(project (join (lib-join (join {toward} {elements} (D D)) opposite (D D)) {toward} (P P) (Opp D)) P)'


for lead in ('C', 'key.C'):
    ENTRIES[f'{lead} cells of the background between the foreground on a line in the output, proportion'] = (role_share(toward_foreground('dir_elem')), '')


def pattern_cells(t, p, g, color=None):
    """Each pattern's cells and colors, placed relative to its box."""
    held = f'(join &t input ({p} P))' if color is None else '&t'
    column = 'Col' if color is None else color
    box = f'(component BoundingBox (cell {held} ({g}) ({p})) box)'
    return f'(lib-join (join {held} {box} ({g} {g})) relative (Base B) (X {p}))', column


def some_pattern_is_output(t, p, g, color=None):
    placed, column = pattern_cells(t, p, g, color)
    over = f'(project (antijoin {placed} output (X_rel P) ({column} Col)) {g})'
    under = f'(project (antijoin (join (project &t {g}) output) {placed} ({g} {g}) (P X_rel) (Col {column})) {g})'
    return [f'(antijoin (antijoin (project &t {g}) {over} ({g} {g})) {under} ({g} {g}))'], nonzero


@entry(*plain_or_key('C patterns by C some pattern is the output'))
def pattern_output(t, p, g):
    return some_pattern_is_output(t, p, g)


@entry(*plain_or_key('C,C patterns by C some pattern is the output'))
def colored_pattern_output(t, p, x, g):
    return some_pattern_is_output(t, p, g, x)


def parse(text):
    """A term as nested lists of symbols."""
    stack, here, word = [], [], ''
    for ch in text:
        if ch in '() ':
            if word:
                here.append(word)
                word = ''
            if ch == '(':
                stack.append(here)
                here = []
            elif ch == ')':
                stack[-1].append(here)
                here = stack.pop()
        else:
            word += ch
    if word:
        here.append(word)
    return here[0]


def unique_name(name, taken):
    if name not in taken:
        return name
    at = 2
    while f'{name}_{at}' in taken:
        at += 1
    return f'{name}_{at}'


def columns_of(node, t):
    """The columns of a term, or None where this function does not follow its names."""
    if isinstance(node, str):
        return list(t.columns) if node == '&t' else ['P', 'Col'] if node in ('input', 'output') else None
    head = node[0]
    if head == 'project':
        return node[2:]
    if head in ('semijoin', 'antijoin', 'union'):
        return columns_of(node[1], t)
    if head == 'select':
        held = columns_of(node[1], t)
        if held is None or node[3] != '=':
            return held
        return [c for c in held if c != (node[2] if node[4] == '0' else node[4])]
    if head == 'join':
        left, right = columns_of(node[1], t), columns_of(node[2], t)
        if left is None or right is None:
            return None
        matched = {pair[1] for pair in node[3:]}
        out = list(left)
        for c in right:
            if c not in matched:
                out.append(unique_name(c, out))
        return out
    if head == 'component' and node[-1] in ('value', 'size') and node[1] in ('Singleton', 'Cardinality'):
        binding = node[2]
        keys = list(binding[2])
        if node[1] == 'Cardinality':
            return keys + ['N']
        return keys + [f for f in binding[3] if isinstance(f, str)]
    return None


def all_form(numerator, denominator, t):
    """Whether a share is 1: each row of the denominator has a match in the numerator."""
    upper, lower = columns_of(parse(numerator), t), columns_of(parse(denominator), t)
    if upper is None or lower is None:
        return None
    shared = [c for c in lower if c in upper]
    if len(lower) == len(upper) and not set(lower) <= set(upper):
        pairs = list(zip(lower, upper))
    elif shared:
        pairs = [(c, c) for c in shared]
    else:
        return None
    return all_of(denominator, numerator, pairs)


def node_text(node):
    return node if isinstance(node, str) else '(' + ' '.join(node_text(x) for x in node) + ')'


OPERATORS = {'project', 'select', 'join', 'semijoin', 'antijoin', 'all', 'union', 'lib-join'}
LEAF_NAMES = {'changed cells': CHANGED, 'background': BACKGROUND, 'foreground': FOREGROUND, 'input foreground': INPUT_FOREGROUND, 'components': COMPONENTS, 'foreground parts': FOREGROUND_PARTS}
LEAF_TEXTS = {node_text(parse(text)) for text in LEAF_NAMES.values()}


def own_box_part(node):
    """The relation R of a term that places R's cells relative to their box, or None."""
    if isinstance(node, list) and node[0] == 'lib-join' and node[2] == 'relative' and isinstance(node[1], list) and node[1][0] == 'join':
        rel, box = node[1][1], node[1][2]
        if isinstance(box, list) and box[:2] == ['component', 'BoundingBox']:
            return rel
    return None


def operator_children(node):
    """(this node's own count, its child terms)."""
    head = node[0]
    if head in OPERATORS:
        if head in ('project', 'select', 'lib-join'):
            return 1, [node[1]]
        return 1, [node[1], node[2]]
    if head == 'component':
        bindings = node[2:-1]
        return max(1, len(bindings)), [binding[1] for binding in bindings]
    return 0, []


def size_of(terms, mode):
    """A root's count of operators: `sum` counts each use, `distinct` each distinct subexpression once, and `leaves` also reads the repeated parts as leaves."""
    seen = set()

    def walk(node):
        if isinstance(node, str):
            return 0
        text = node_text(node)
        if mode != 'sum':
            if text in seen:
                return 0
            seen.add(text)
        if mode == 'leaves':
            if text in LEAF_TEXTS:
                return 0
            rel = own_box_part(node)
            if rel is not None:
                return 1 + walk(rel)
        own, children = operator_children(node)
        return own + sum(walk(child) for child in children)

    return sum(walk(parse(term)) for term in terms)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('encoder')
    parser.add_argument('--tasks', type=int, default=16)
    parser.add_argument('--items', type=int, default=2)
    parser.add_argument('--kinds', default=None, help='a regular expression over the template texts')
    parser.add_argument('--per-schema', type=int, default=0, help='the tables to keep per set of column types, over every item')
    parser.add_argument('--processes', type=int, default=1)
    parser.add_argument('--out', default=str(RESULTS / 'template-shapes.tsv'))
    a = parser.parse_args()
    os.environ['CONTRACTS_OUT'] = str(C / 'dev/out-expand')
    sys.path[:0] = [str(C / 'dev/out-expand'), str(C / 'dev'), str(C / 'features')]
    import features as F
    import analyze as A

    ranks = {}
    for line in open(RESULTS / 'candidate-rank.tsv'):
        fields_ = line.rstrip('\n').split('\t')
        kind = TOKEN.sub(lambda m: m.group(0).split('⟦')[0] + 'C', fields_[3])
        ranks.setdefault(kind, len(ranks) + 1)
    wanted = {k for k in ENTRIES if not a.kinds or re.search(a.kinds, k)}

    tasks = [t for t in (ROOT / 'work/feature-spec/eval-tasks.txt').read_text().split() if (RESULTS / f'candidate-tables/{t}.json').exists()][:a.tasks]
    requests, records, seen_schema = [], [], Counter()
    for task in tasks:
        data = json.loads((RESULTS / f'candidate-tables/{task}.json').read_text())
        pairs = json.loads((ROOT / f'data/tasks/{task}.json').read_text())['train']
        tables = []
        for item in data['items'][:a.items] if not a.per_schema else data['items']:
            tables.append(item['gold'])
            tables.extend(m['table'] for m in item['mutants'][:1])
        for table in tables:
            types = table['types']
            if a.per_schema:
                schema = tuple(sorted(types))
                if seen_schema[schema] >= a.per_schema or not all(table['rows'].get(f'train/{i}') for i in range(len(pairs))):
                    continue
                seen_schema[schema] += 1
            if any(t.startswith('Pose') for t in types) or any(len(rows or []) > 2000 for rows in table['rows'].values()):
                continue
            view = Table(table['columns'], types)
            terms = {}
            for i, pair in enumerate(pairs):
                ex = f'train/{i}'
                rows = table['rows'].get(ex)
                if rows is None:
                    continue
                gi, go = pair['input'], pair['output']
                sizes = {'input': (len(gi), len(gi[0])), 'output': (len(go), len(go[0]))}
                tab = dict(columns=[(c, t, 'input' if t in PLACE else None) for c, t in zip(table['columns'], types)], rows={ex: rows})
                held = F.table_features('T', F.tokened('T', tab), ex, sizes, {}, (gi, go))
                for key, value in held.items():
                    if key.endswith(' describe') or not A.is_output('T|' + key):
                        continue
                    kind = TOKEN.sub(lambda m: m.group(0).split('⟦')[0] + 'C', key)
                    if kind not in wanted:
                        continue
                    holes = [f'T{m.group(1)}' for m in TOKEN.finditer(key)]
                    made, how = ENTRIES[kind][0](view, *holes)
                    whole = all_form(made[0], made[1], view) if how is share else None
                    records.append((kind, tuple(holes), len(requests), i, value, how, tuple(made), whole))
                    terms.update((term, None) for term in made)
                    if whole:
                        terms[whole] = None
            if terms:
                requests.append(dict(task=task, types=types, rows={k: v for k, v in table['rows'].items()}, terms=list(terms)))
    print(f'{len(requests)} tables, {sum(len(r["terms"]) for r in requests)} terms, {len(records)} values', flush=True)
    with tempfile.TemporaryDirectory() as folder:
        chunks = [requests[at::a.processes] for at in range(a.processes)]
        runs = []
        places = {}
        for at, chunk in enumerate(chunks):
            path, out = Path(folder) / f'requests{at}.jsonl', Path(folder) / f'values{at}.jsonl'
            lines = []
            for own, request in enumerate(chunk):
                places[(at, own)] = requests.index(request)
                lines.append(json.dumps(request))
            path.write_text('\n'.join(lines) + '\n')
            runs.append((at, out, subprocess.Popen([a.encoder, 'stored-eval', str(path), '--out', str(out)], cwd=ROOT, stderr=subprocess.PIPE, text=True)))
        results = {}
        for at, out, run in runs:
            _, stderr = run.communicate()
            if run.returncode:
                print(stderr[-2000:], flush=True)
            for line in out.read_text().splitlines():
                found = json.loads(line)
                results[(places[(at, found['line'])], found['term'])] = found
    tally = defaultdict(Counter)
    sample, sizes, refusals, differences = {}, defaultdict(list), {}, defaultdict(list)
    all_sample, all_sizes, all_refusals = {}, defaultdict(list), {}
    for kind, holes, at, pair, value, how, made, whole in records:
        got = [results.get((at, term)) for term in made]
        sample.setdefault(kind, made)
        if whole:
            all_sample.setdefault(kind, whole)
            found = results.get((at, whole))
            if found is None or 'refused' in found or found['counts'][pair] is None:
                tally[kind]['all_refused'] += 1
                if found and 'refused' in found:
                    all_refusals.setdefault(kind, found['refused'])
            else:
                all_sizes[kind].append(size_of([whole], 'distinct'))
                tally[kind]['all_agree' if (found['counts'][pair] > 0) == (value == 1.0) else 'all_differ'] += 1
        if any(g is None or 'refused' in g for g in got):
            tally[kind]['refused'] += 1
            refusals.setdefault(kind, next((g['refused'] for g in got if g and 'refused' in g), 'no result'))
            continue
        sizes[kind].append(tuple(size_of(list(made), mode) for mode in ('sum', 'distinct', 'leaves')))
        counts = [g['counts'][pair] for g in got]
        firsts = [g['firsts'][pair] for g in got]
        if any(c is None for c in counts):
            tally[kind]['none'] += 1
            continue
        mine = how(counts, firsts)
        if mine == value:
            tally[kind]['agree'] += 1
        else:
            tally[kind]['differ'] += 1
            if len(differences[kind]) < 3:
                differences[kind].append((requests[at]['task'], holes, pair, value, mine, counts))
    with open(a.out, 'w') as sink:
        sink.write('rank\ttemplate\tform\tsize by operators\tsize distinct\tsize with leaves\tagree\tdiffer\trefused\tall size\tall agree\tall differ\tnote\texpression\n')
        for kind in sorted(ENTRIES, key=lambda k: ranks.get(k, 10 ** 6)):
            t = tally[kind]
            held = max(sizes[kind], key=lambda x: x[1]) if sizes[kind] else ('', '', '')
            whole_size = max(all_sizes[kind]) if all_sizes[kind] else ''
            expression = ' ; '.join(sample.get(kind, ()))
            sink.write(f"{ranks.get(kind, '')}\t{kind}\t{'ratio' if kind in all_sample else ''}\t{held[0]}\t{held[1]}\t{held[2]}\t{t['agree']}\t{t['differ']}\t{t['refused']}\t{whole_size}\t{t['all_agree']}\t{t['all_differ']}\t{ENTRIES[kind][1]}\t{expression}\n")
            if kind in wanted:
                print(f"{ranks.get(kind, ''):>4} size {held[0]!s:>3} {held[1]!s:>3} {held[2]!s:>3} all {whole_size!s:>3} agree {t['agree']:>5} differ {t['differ']:>4} refused {t['refused']:>4} all {t['all_agree']:>5} {t['all_differ']:>4} {t['all_refused']:>4} {kind[:62]}", flush=True)
                if kind in refusals:
                    print(f'       refused: {refusals[kind]}', flush=True)
                if kind in all_refusals:
                    print(f'       all refused: {all_refusals[kind]}', flush=True)
                for difference in differences[kind]:
                    print(f'       differ: {difference}', flush=True)


if __name__ == '__main__':
    main()
