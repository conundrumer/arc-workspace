"""Q5 Split and narrowed filters: the sound versions of the q1 to q4 keys, for a clause sampler that rejects early.

Each key is a count (form keys) or a 0 or 1 (table keys), and None where the test does not apply. A feature reads only
the train inputs and outputs, the available tables, X, the candidate's form, the clauses before the point and the
library interfaces. The old key stays in its module, so that the two can be compared; the new key is named like it,
with the suffix of its split.

Class (when the rule can decide):
    SP: static, decided on a prefix; the atom or binder that completes the violation is placed and no extension repairs it.
    SC: static, on completion; an obligation that a later atom can still meet.
    DA: data-dependent, anti-monotone: removed rows and added atoms keep the violation (the sampler need not drop the prefix).
    DC: data-dependent, on completion; it needs the whole of X.
Soundness (a rule is sound if it never rejects a valid clause):
    S: the violation contradicts the train output, or a library law makes the clause unsatisfiable.
    R: the library makes the atom valid, constant or an alias, or gives an equal clause in a canonical spelling; a smaller
       or canonical clause with the same meaning stays reachable.
    H: the rule rests on what gold writes.
Assumptions.
    A1: `OUT` reads the candidate's relation (`p.out_reads` is True), and `OUT` picks one Position (or Box) column and one
        Color column of X to paint. A key with A1 is None at any other clause, and where `p.out_reads` is None. Where X has
        more than one column that could fill a role, `OUT` can pick any of them: a key that depends on the pick fires only
        if every pick fails.
    A2: a clause is valid if one assignment of the `DET` parameters solves every train pair, so a table key fires only if
        every assignment has the violation.
A key that needs the type of a label reads the column of the label's first binder (`_btype`), which later sites cannot change.
A literal 0 that is the frame (`featlib.frame_zero`) is legal and never counts.
"""
import collections as C
import importlib.util
from pathlib import Path

from featlib import FEATURES, feature


def _sibling(name):
    """A private copy of the feature module `name` next to this file, to reuse its helpers; its features are not registered."""
    saved = dict(FEATURES)
    spec = importlib.util.spec_from_file_location('_q5_' + name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        FEATURES.clear()
        FEATURES.update(saved)
    return module


q1 = _sibling('q1_column_laws')
q2 = _sibling('q2_table_tests')
q3 = _sibling('q3_form_filters')

# What a library relation computes from which of its columns, as its definition in the library says (neighbor and
# jump compose an offset; split takes the margins of P on axis A; dist_pair is two margins). Gold restates a function of
# the other orientation relations (`axis_of(D D, A *A3)` after `axis_of(D *D, A *A)`), so they are not listed.
FUNCTIONS = {
    'neighbor': [({'P', 'D'}, {'Q'}), ({'Q', 'D'}, {'P'}), ({'P', 'Q'}, {'D'})],
    'step_offset': [({'D'}, {'V'}), ({'V'}, {'D'})],
    'opposite': [({'D'}, {'Opp'}), ({'Opp'}, {'D'})],
    'perp': [({'A'}, {'A2'}), ({'A2'}, {'A'})],
    'jump': [({'P', 'D', 'K'}, {'Q'}), ({'Q', 'D', 'K'}, {'P'})],
    'jump_offset': [({'D', 'K'}, {'V'})],
    'split': [({'P', 'A'}, {'Along', 'Across'})],
    'dist_pair': [({'P', 'D'}, {'K', 'K2'})],
}
SINGLE_K = frozenset({'edge_inset', 'uniform_inset', 'corner_inset', 'edge_outset', 'uniform_outset', 'corner_outset'})
AXIS_K = frozenset({'axis_inset', 'axis_outset'})
READS = ('table', 'clause', 'fact', 'port', 'output')


# ------------------------------------------------------------------------------------------------ helpers

_body = q3._body
_sites = q3._sites
_library = q3._library
_related = q3._related


def _positive(atom):
    return not atom.negated


def _btype(arg, declared=False):
    """The type of the label at arg: the column type of the first site that makes the label, if that site comes at or
    before arg in the text; else None. Sites placed later cannot change it. With declared, the first site must be a column
    of a declared table or a component port: a library relation types a column Box that can hold a Position, and the
    label then takes the type of the columns it is read at."""
    v = arg.variable
    if arg.label is None or v is None:
        return None
    first = next((o for o in v.occurrences if o.binds and o.atom is not None and o.column_type), None)
    if first is None or (declared and not first.atom.relation.startswith('&')):
        return None
    for o in v.occurrences:
        if o is first:
            return first.column_type
        if o is arg:
            return None
    return None


def _contexts(table, tests=False):
    """{(assignment, example): rows of the first model}; a row is the list of its cells (dicts). A table with an Example
    column is task-level, and a row belongs to the examples its Example values name. With `tests` the test entries are in
    it, under the example ('test', test index): an entry of a test input holds only that input's rows."""
    ex = [i for i, c in enumerate(table.columns()) if c.type == 'Example']
    got = C.defaultdict(dict)
    for e in (table.all_entries if tests else table.entries):
        m = e.get('model', 0)
        if 'train' not in e:
            got[e['assignment'], ('test', e['test'])].setdefault(m, []).extend(e['rows'])
            continue
        if not ex:
            got[e['assignment'], e['train']].setdefault(m, []).extend(e['rows'])
            continue
        for r in e['rows']:
            for t in {r[i]['value'][0] for i in ex if r[i].get('value')}:
                got[e['assignment'], t].setdefault(m, []).append(r)
    return {k: models[min(models)] for k, models in got.items()}


def _position(v, h, w):
    """The (row, col) cell of a Position value in a frame of h by w, or None where the value is not a cell of it."""
    if len(v) == 4 and v[0] >= 0 and v[2] >= 0 and v[0] + v[1] == h - 1 and v[2] + v[3] == w - 1:
        return v[0], v[2]
    return None


def _by_assignment(contexts):
    out = C.defaultdict(dict)
    for (a, t), rows in contexts.items():
        out[a][t] = rows
    return out


def _output_setting(p):
    """(contexts of X, train examples, Position column indices, Color column indices) where `OUT` reads the candidate's
    relation and X has no Box column, else None. What a Box row paints is not known, so a Box column leaves the tests
    below undecided."""
    if not p.out_reads:
        return None
    cols = p.x.columns()
    if any(q2._fills(c, 'Box') for c in cols):
        return None
    pos = [c.index for c in cols if q2._fills(c, 'Position')]
    color = [c.index for c in cols if q2._fills(c, 'Color')]
    ctx = _contexts(p.x)
    return (ctx, p.examples(), pos, color) if ctx else None


# ------------------------------------------------------------------------------------------------ output clause: whole table

@feature
def q5a_output_tables(p):
    """Q5a Tests of X as a whole against the train grids, where `OUT` reads the candidate's relation (A1); None elsewhere.
    `equals_input_e` (DC, S): X holds the `input` table's columns `P` and `Col` by name and type, has no other column that
    admits Position, Box or Color (so `OUT` has one pick), and its rows on those two columns equal the `input` rows in every context. The painted grid is
    then the input, and some train output differs from its input. (Split E of `available_size.equals_input`.)
    `contains_input_c` (DC, S): X has the column types of `input` (one column of each, matched by type), and in every
    context of every assignment its rows contain the `input` rows of that context's example.
    The painted grid is the input, or a cell has a second row or lies outside the frame. (Split C of
    `contains_input.equal` and `contains_input.strict_superset`.)
    `same_every_example_g` (DC, S): the examples that have an entry in X have unequal outputs, and the rows of X (the
    Example column left out) are one non-empty set over all contexts of all assignments. (Split G of
    `final_vs_output.same_every_example`.)
    `equals_input_e` and `contains_input_c` are None at a Det point: X there is the task-level body table without its Example
    column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's input.

    Needs: full X. Monotone: no.
    """
    if not p.out_reads:
        return None
    out = {'equals_input_e': None, 'contains_input_c': None, 'same_every_example_g': None}
    x = p.x
    t = p.table('input') if p.kind != 'Det' else None
    if t is not None and x.columns():
        xcols = {c.name: c for c in x.columns()}
        tcols = {c.name: c for c in t.columns()}
        need = ('P', 'Col')
        xc, tc = q2._contexts(x, True), q2._contexts(t, True)  # X's rows against `input`'s: the test entries too
        if (xc and all(n in xcols and n in tcols and xcols[n].type == tcols[n].type for n in need) and
                not any(q2._fills(c, 'Position', 'Box', 'Color') and c.name not in need for c in x.columns())):
            ix, it = [xcols[n].index for n in need], [tcols[n].index for n in need]
            out['equals_input_e'] = int(all((k in tc or isinstance(k[1], tuple)) and  # a test input `input` has no entry for is skipped
                                            (k not in tc or q2._values(rows, ix) == q2._values(tc[k], it))
                                            for k, rows in xc.items()))
        # the columns are matched by type, so that the order of X's columns (which follows the order of the conjuncts) is free
        by_x = {c.type: c.index for c in x.columns()}
        by_t = {c.type: c.index for c in t.columns()}
        if (xc and None not in by_x and len(by_x) == len(x.columns()) and len(by_t) == len(t.columns()) and
                set(by_x) == set(by_t)):
            order = sorted(by_t)
            ix, it = [by_x[k] for k in order], [by_t[k] for k in order]
            # `input` is the same at every assignment, so each context of X is compared with its example's input
            tin = {}
            for (_, e), rows in sorted(tc.items(), key=lambda kv: (kv[0][0], kv[0][1][1] if isinstance(kv[0][1], tuple) else kv[0][1])):
                tin.setdefault(e, rows)
            keys = [k for k in xc if k[1] in tin]
            if keys and not all(not xc[k] and not tin[k[1]] for k in keys):
                out['contains_input_c'] = int(all(q2._rowset(xc[k], ix) >= q2._rowset(tin[k[1]], it) for k in keys))
    ctx = _contexts(x)  # the train outputs are compared: the train entries
    examples = p.examples()
    if ctx:
        outputs = {examples[t].output.cells for (a, t) in ctx if t < len(examples)}
        if len(outputs) >= 2:
            keep = [c.index for c in x.columns() if c.type != 'Example']
            sets = {frozenset(q2._rowset(rows, keep)) for rows in _contexts(x, True).values()}  # X's own rows: test too
            out['same_every_example_g'] = int(len(sets) == 1 and bool(next(iter(sets))))
    return out


# ------------------------------------------------------------------------------------------------ output clause: columns and cells

@feature
def q5b_output_columns(p):
    """Q5b The columns `OUT` reads, where `OUT` reads the candidate's relation (A1); None elsewhere.
    `out_columns_f0` (SC, S): 1 where X has no Position or Box column, or no Color column: `OUT`'s first site selects a
    Position or a Box, and its second a Color. The end of the clause is not offered until it has both. Sound for a one-atom
    `OUT`; an atom of a two-atom `OUT` selects only one of the two, so there the key rests on gold (H). (Split F0 of `final_vs_output.fewer_rows` and `q4c_declared.differs_no_box`.)

    Needs: form, finished. Monotone: no.
    """
    if not p.out_reads:
        return None
    cols = p.x.columns()
    return {'out_columns_f0': int(not any(q2._fills(c, 'Position', 'Box') for c in cols)
                                  or not any(q2._fills(c, 'Color') for c in cols))}


@feature
def q5c_output_cells(p):
    """Q5c The cells that X paints, where `OUT` reads the candidate's relation (A1); None elsewhere, where X has a Box column, and where it has
    no Position column (`fewer_cells_f1`) or no Position and Color column (`differs_missing_f2`) or no rows. Both keys
    fire only if every assignment fails for every column. A removed row cannot repair a column that already fails, but a
    later atom can add a Position or Color column that passes, so neither key is anti-monotone on a prefix.
    `fewer_cells_f1` (DC, S): for every assignment and every Position column, some example has fewer distinct cells of
    its output frame in that column than the output has cells. (Split F1 of `final_vs_output.fewer_rows`.)
    `differs_missing_f2` (DC, S): for every assignment and every Position and Color column pair, some example has an
    output cell with no row (cell, output color) in that pair. (Split F2 of `q4c_declared.differs_no_box`.)
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.

    Needs: full X. Monotone: no.
    """
    if p.kind == 'Det':
        return None
    got = _output_setting(p)
    if got is None:
        return None
    ctx, examples, pos, color = got
    if not pos:
        return None
    by = _by_assignment(ctx)
    short = {}
    missing = {}
    for a, per in by.items():
        for t, rows in per.items():
            if t >= len(examples):
                continue
            out = examples[t].output
            h, w = out.size
            for i in pos:
                cells = {_position(tuple(r[i].get('value') or ()), h, w) for r in rows}
                cells.discard(None)
                short[a, i] = short.get((a, i), False) or len(cells) < h * w
                for j in color:
                    held = {(_position(tuple(r[i].get('value') or ()), h, w), tuple(r[j].get('value') or ())) for r in rows}
                    lacks = any(((r, c), (out[r, c],)) not in held for r in range(h) for c in range(w))
                    missing[a, i, j] = missing.get((a, i, j), False) or lacks
    if not short:
        return None
    return {'fewer_cells_f1': int(all(short.values())),
            'differs_missing_f2': int(all(missing.values())) if missing else None}


# ------------------------------------------------------------------------------------------------ Order.before

def _before_heads(p):
    """(the Label of head `a`, of head `b`) at the Order `before` port, else None."""
    if not q3._before_scope(p):
        return None
    heads = {h.column: h.label for h in p.clause.body.head if h.field is None and h.label}
    return (heads['a'], heads['b']) if 'a' in heads and 'b' in heads else None


def _tied_by_equals(body, x, y):
    """Whether labels x and y are one label or are compared by positive `=` atoms of the body's top conjunction."""
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a in body.atoms:
        if (a.operator == '=' and not a.negated and not a.branch and a.quantifier is None and a.conditional is None and
                a.first is not None and a.second is not None and a.first.label and a.second.label):
            parent[find(a.first.label)] = find(a.second.label)
    return find(x) == find(y)


@feature
def q5d_order_static(p):
    """Q5d The `before` port of Order, on its form; None elsewhere.
    `b_static` (SP, S): the head sites `a` and `b` hold one label, or a positive `=` of the top conjunction ties their
    labels. Every row is then a pair (x, x), and `before` is a strict order. (The static part of split B of
    `before_order.not_strict_order`.)

    Needs: form. Monotone: yes.
    """
    heads = _before_heads(p)
    if heads is None:
        return None
    return {'b_static': int(_tied_by_equals(p.clause.body, *heads))}


def _breaks(pairs):
    succ = C.defaultdict(set)
    for a, b in pairs:
        succ[a].add(b)
    return any(a == b or (b, a) in pairs or any((a, c) not in pairs for c in succ.get(b, ())) for a, b in pairs)


@feature
def q5e_order_rows(p):
    """Q5e The rows of an Order `before` table, at the `before` port; None elsewhere and where X has no column `a` and
    `b` of one type.
    `b_rows` (DC, S): for every assignment and every model, some example has a key group (the columns other than `a`
    and `b`) with a row (x, x), a pair with its converse, or (x, y) and (y, z) without (x, z). (Split B, the rows part, of
    `before_order.not_strict_order`; that key fires on any assignment.)

    Needs: full X. Monotone: no.
    """
    if _before_heads(p) is None:
        return None
    x = p.x
    ca, cb = x.column('a'), x.column('b')
    if ca is None or cb is None or ca.type != cb.type:
        return None
    others = [c.index for c in x.columns() if c.index not in (ca.index, cb.index)]
    broken = {}
    for e in x.all_entries:
        groups = C.defaultdict(set)
        for r in e['rows']:
            groups[tuple(q2._cell(r[i]) for i in others)].add((q2._cell(r[ca.index]), q2._cell(r[cb.index])))
        k = e['assignment'], e.get('model', 0)
        broken[k] = broken.get(k, False) or any(_breaks(g) for g in groups.values())
    return {'b_rows': int(all(broken.values()))} if broken else None


# ------------------------------------------------------------------------------------------------ atom laws

def _swapped_relative(a, b):
    """Whether relative atoms a and b read Base and X of one with the labels of X and Base of the other."""
    sa, sb = _sites(a), _sites(b)
    try:
        return (sa['Base'].joins and sa['X'].joins and sb['Base'].joins and sb['X'].joins and
                sa['Base'].label == sb['X'].label and sa['X'].label == sb['Base'].label)
    except KeyError:
        return False


def _positive_relative(body):
    return [a for a in body.atoms if a.relation == 'relative' and _library(a) and _positive(a) and a.quantifier is None]


def _count_neg_pairs(body, made=True):
    rel = _positive_relative(body)
    n = 0
    for i, a in enumerate(rel):
        for b in rel[i + 1:]:
            if a.conjunction == b.conjunction and _swapped_relative(a, b):
                n += (not made) or (_sites(a)['X_rel'].binds and _sites(b)['X_rel'].binds)
    return n


@feature
def q5f_atom_laws(p):
    """Q5f Laws of one atom or of two atoms, on the form.
    `compose_ab_same` (SP, H): a positive, unquantified `compose` atom with one label at A and B. `compose_c_eq_a_same`
    (SP, H): one label at C and A (B is then 0). `apply_pout_eq_p_same` (SP, H): a positive, unquantified `apply` atom
    with one label at P and P_out. (Split H of `q1_atom_laws.compose_ab_equal`, `compose_c_eq_a`, `apply_pout_eq_p`:
    the row test holds on every row and needs no rows.)
    `neg_pair_static` (SP, R): pairs of positive `relative` atoms of one conjunction, `relative(Base A, X B, X_rel U)` and
    `relative(Base B, X A, X_rel V)`, whose X_rel labels the two atoms make. V is then minus U on every row. (Split N of
    `q1_neg_pair`.)
    `dp_box_at_position_f` (SP, H): atoms of a declared table or a component port with a label at a Position column whose
    first binder is a Box column of a declared table or a port (`_btype`; split of `q4b_geometry.dp_box_at_position`,
    which reads the meet over all sites). A first binder in a library relation does not count: `neighbor.Q` is a Box
    column that holds a Position when P is one.

    Needs: form. Monotone: yes.
    """
    body = _body(p)
    if body is None:
        return None
    out = C.Counter({k: 0 for k in ('compose_ab_same', 'compose_c_eq_a_same', 'apply_pout_eq_p_same', 'neg_pair_static',
                                    'dp_box_at_position_f')})
    for a in body.atoms:
        if a.operator is not None:
            continue
        sites = _sites(a)
        same = lambda u, v: u in sites and v in sites and sites[u].label is not None and sites[u].label == sites[v].label
        if _library(a) and _positive(a) and a.quantifier is None:
            if a.relation == 'compose':
                out['compose_ab_same'] += same('A', 'B')
                out['compose_c_eq_a_same'] += same('C', 'A')
            elif a.relation == 'apply':
                out['apply_pout_eq_p_same'] += same('P', 'P_out')
        if a.relation.startswith('&'):
            out['dp_box_at_position_f'] += any(x.label is not None and x.column_type == 'Position' and _btype(x, True) == 'Box'
                                               for x in a.arguments)
    out['neg_pair_static'] = _count_neg_pairs(body)
    return dict(out)


# ------------------------------------------------------------------------------------------------ pairs of atoms

def _geometry(body):
    return [a for a in body.atoms if _library(a) and (a.relation in q3.GEO or a.relation.endswith('_elem'))]


def _fn_dup_pair(a, b):
    """Whether atoms a and b of one relation, of one polarity, repeat one another (split D). Per column the atoms read one
    label or the literal, or one makes the label the other reads, or both make a label. The pair repeats where
    1. neither makes a label, or 2. only one of them makes labels, and the other reads each of those; in both there is a
    column where both read one label. Or 3. both make a label at some column, and the labels they make there are a function,
    in the library's relation, of the columns where the atoms hold one label (read by both, or made by one and read by the
    other)."""
    if a.relation != b.relation or a.negated != b.negated or not _related(a, b):
        return False
    sa, sb = _sites(a), _sites(b)
    if set(sa) != set(sb):
        return False
    shared, made_a, made_b, both = set(), set(), set(), set()
    for name, x in sa.items():
        y = sb[name]
        lx, ly = x.label or '0', y.label or '0'
        if x.binds and y.binds:
            both.add(name)
        elif x.binds or y.binds:
            if lx != ly:
                return False
            (made_a if x.binds else made_b).add(name)
        else:
            if lx != ly:
                return False
            shared.add(name)
    if not both:
        return bool(shared) and not (made_a and made_b)
    agree = shared | made_a | made_b
    return any(ins <= agree and both <= outs for ins, outs in FUNCTIONS.get(a.relation, ()))


def _comparison_pairs(body):
    cmps = [a for a in body.comparisons if a.first is not None and a.second is not None and _positive(a) and a.quantifier is None]
    canon = [q3._canon_cmp(a) for a in cmps]
    for i, a in enumerate(cmps):
        for j in range(i + 1, len(cmps)):
            if canon[i] is not None and canon[j] is not None and canon[i][0] == canon[j][0] and q3._related(a, cmps[j]):
                yield canon[i][1], canon[j][1]


def _margin_pair(a, b, need_k):
    """Positive, related `margin` atoms a and b with one joined label at B and one at D; with need_k, also a K site
    that makes a label in one of them or holds one label (or the literal 0) in both."""
    if a.negated or b.negated or not _related(a, b):
        return False
    sa, sb = _sites(a), _sites(b)
    if not all(sa.get(c) is not None and sb.get(c) is not None and sa[c].joins and sb[c].joins and
               sa[c].label == sb[c].label for c in ('B', 'D')):
        return False
    if not need_k:
        return True
    ka, kb = sa.get('K'), sb.get('K')
    return ka is not None and kb is not None and (ka.binds or kb.binds or (ka.label or '0') == (kb.label or '0'))


def _single_not(body, atom):
    """Whether atom is the only atom of a NOT that is a conjunct of the list its own conjunction level would hold."""
    if not atom.negated or len(atom.path) < 2:
        return False
    node = _at(body.body, atom.path[:-1])
    return isinstance(node, list) and len(node) == 2 and node[0] == 'NOT'


def _at(tree, path):
    node = tree
    for i in path:
        if not isinstance(node, list) or i >= len(node):
            return None
        node = node[i]
    return node


def _contradictions(body, need_labels=True):
    """The NOT atoms that read a relation or table with the labels of a positive atom of the same conjunction, where the
    NOT holds that atom only (split T). With need_labels False, the labels are not compared."""
    reads = [a for a in body.atoms if a.operator is None and a.kind in READS]
    n = 0
    for b in reads:
        if not _single_not(body, b) or b.quantifier is not None or b.conditional is not None:
            continue
        for a in reads:
            if (a.negated or a.quantifier is not None or a.conditional is not None or a.branch != b.branch or
                    a.path[:-1] != b.path[:-2]):
                continue
            if (a.key()[1:] == b.key()[1:]) if need_labels else (a.key()[1] == b.key()[1]):
                n += 1
                break
    return n


@feature
def q5g_atom_pairs(p):
    """Q5g Two atoms that repeat or contradict one another, on the form. Each key counts pairs.
    `fn_dup_d` (SP, R): atoms of one cell-geometry relation, of one polarity, in related contexts, that repeat one another
    (split D of `q3a_cell_geometry.fn_dup`): an exact repeat, an atom that reads each label the other makes, or two atoms
    that make labels that are functions of their shared read columns in the library's relation (`FUNCTIONS`).
    `axis_of(D *d1, A a)` twice makes two free labels and does not count.
    `partial_overlap_related` (SP, R): two positive comparisons of related contexts, none below a quantifier, on the same
    two operands, with outcome sets that differ, overlap and do not cover <, = and > together (split O of
    `q3b_comparisons.partial_overlap_pair`).
    `dup_margin_k` (SP, R): two positive `margin` atoms of related contexts with one joined label at B and one at D, where
    a K site makes a label or both K sites hold one label (split M of `q3d_box_measures.dup_margin_BD`). A K joined to
    another label is an equality test and does not count.
    `contra_t` (SP, S; R where the pair stands in an OR branch, which is then dead): a NOT atom, alone in its NOT, that
    reads a relation or table with the labels of a positive atom of the list the NOT stands in, with no quantifier or
    conditional (split T of `q3f_table_reads.contra`).

    Needs: form. Monotone: yes.
    """
    body = _body(p)
    if body is None:
        return None
    geo = _geometry(body)
    dup = sum(1 for i, a in enumerate(geo) for b in geo[i + 1:] if _fn_dup_pair(a, b))
    overlap = 0
    for s, t in _comparison_pairs(body):
        overlap += s != t and bool(s & t) and (s | t) != q3.ALL_OUTCOMES
    margins = [a for a in body.atoms if a.relation == 'margin' and _library(a)]
    dm = sum(1 for i, a in enumerate(margins) for b in margins[i + 1:] if _margin_pair(a, b, True))
    return {'fn_dup_d': dup, 'partial_overlap_related': overlap, 'dup_margin_k': dm, 'contra_t': _contradictions(body)}


# ------------------------------------------------------------------------------------------------ literal 0

def _frames_of(p, frame):
    """The grids whose sizes a Position column of that frame tag can have, or None where the frame is unknown."""
    ex = p.examples()
    test = p.test_inputs  # a test output is not known: the test inputs are frames of `input` and of no tag only
    if frame == 'input':
        return [e.input for e in ex] + list(test)
    if frame == 'output':
        return [e.output for e in ex]
    if frame == '':
        return [g for e in ex for g in (e.input, e.output)] + list(test)
    return None


@feature
def q5h_zero_sites(p):
    """Q5h The literal 0 at a site where it is constant or has no meaning, on the form.
    `axis_k_zero_k` (SP, R): a positive `edge_*`, `uniform_*` or `corner_*` inset or outset atom with 0 at K, or an
    `axis_inset` or `axis_outset` atom with 0 at both K1 and K2 (split K of `q3c_containment.axis_k_zero`; an axis atom with
    one zero K is a legal one-sided inset).
    `zero_position` (SP, S): an atom of a declared table or of `input`, positive or below NOT, with 0 at a Position column
    whose frame tag is `input`, `output` or none, where every train grid of that frame has more than one cell. A Position
    has margins that sum to the frame's size less one, so 0 is a cell only in a one-cell frame. (Split Z of
    `q3f_table_reads.zero_nonnumber`; a Box or Offset column takes 0 as the frame or the identity, and a Color, Dir or
    Ident column refuses it.)

    Needs: form. Monotone: yes.
    """
    body = _body(p)
    if body is None:
        return None
    k = z = 0
    for a in body.atoms:
        if a.operator is not None:
            continue
        sites = _sites(a)
        if _library(a) and _positive(a):
            if a.relation in SINGLE_K:
                k += bool(sites.get('K') is not None and sites['K'].is_zero)
            elif a.relation in AXIS_K:
                k += bool(all(sites.get(c) is not None and sites[c].is_zero for c in ('K1', 'K2')))
        if q3._declared(a) or a.relation == 'input':
            for x in a.arguments:
                if x.is_zero and x.column_type == 'Position':
                    grids = _frames_of(p, x.frame)
                    if grids and all(g.height * g.width > 1 for g in grids):
                        z += 1
                        break
    return {'axis_k_zero_k': k, 'zero_position': z}


# ------------------------------------------------------------------------------------------------ unread labels

@feature
def q5i_unread_labels(p):
    """Q5i Labels that a clause makes and nothing reads; None except in a body (not an INIT key clause).
    `unread_label_u` (SC, H): labels made by `perp.A2` or by a `cell` port's `P_outer`, or, in a Rule clause, by `*` outside a
    record, that no site reads (no plain or `^` site, no head site) and, for the Rule case only, that X does not hold. A label
    that an atom of the clause could still read keeps the obligation open, so the end of the clause is offered only when the
    count is 0. (Split U of `q3d_box_measures.unread_perp_A2`, `unread_cell_P_outer` and `q3h_orphan.orphan_label`; the
    first does not exempt a label that X holds.)

    Needs: form, finished. Monotone: no.
    """
    body = _body(p)
    if body is None or body.name == 'key':
        return None
    held = {id(v) for v in p.clause.x_columns.values()}
    n = 0
    for v in body.variables.values():
        occ = v.occurrences
        if not occ or any(not (o.binds and not o.key and o.atom is not None) for o in occ):
            continue
        if q3._src(occ[0]) == 'port:cell.P_outer' or (q3._src(occ[0]) == 'perp.A2' and id(v) not in held):
            n += 1
        elif p.kind == 'Rule' and id(v) not in held and all(o.field is None for o in occ):
            n += 1
    return {'unread_label_u': n}


# ------------------------------------------------------------------------------------------------ equal columns, every assignment

@feature
def q5j_equal_columns(p):
    """Q5j Two columns of X that are equal on every row, with a count gate. The columns must not be tied by the form (one
    label, or a positive `=`), and the projection of X on the two columns must have at least 2 distinct rows over all
    contexts. A fresh-label atom can raise the total rows of X without adding information on the two columns, so the gate
    counts the distinct projected rows. None without two columns of the kind.
    `box_input_equal_q` (DC, H): two Box columns with the frame tag `input`. `ident_equal_q` (DC, H): two Ident columns.
    (Split Q of `q1_equal_cols.box_input_equal` and `ident_equal`.)

    Needs: partial. Monotone: no.
    """
    s = q1._series(p)
    if s.n == 0:
        return None
    tied = q1._tied(p)
    out = {}
    for name, pred in (('box_input_equal_q', lambda c: c.type == 'Box' and c.frame == 'input'),
                       ('ident_equal_q', lambda c: c.type == 'Ident')):
        cols = s.idx(pred)
        if len(cols) < 2:
            out[name] = None
            continue
        out[name] = int(any(q1._equal(s, i, j) and len(set(zip(s.vals[i], s.vals[j]))) >= 2
                            for i, j in q1._pairs(s, cols, tied)))
    return out


def _framed_bad(p, entries):
    """{assignment: whether some entry of it has a resolved extent of an `input` or `output` framed Position or Box column
    that is not the example's grid size}, or None where the test does not apply (see q1_off_grid.frame_bad)."""
    cols = [c for c in p.x.columns() if c.type in ('Position', 'Box') and c.frame in ('input', 'output')]
    if not cols or p.kind.startswith('INIT') or any(c.type == 'Example' for c in p.x.columns()):
        return None
    size = {e.index: {'input': e.input.size, 'output': e.output.size} for e in p.examples()}
    test_size = {('test', i): {'input': g.size} for i, g in enumerate(p.test_inputs)}  # a test output has no size here
    size.update(test_size)
    bad = {}
    for e in entries:
        hit = False
        key = e['train'] if 'train' in e else ('test', e['test'])
        for r in e['rows']:
            for c in cols:
                cell = r[c.index]
                ext = cell.get('extent')
                if (cell.get('extent_status') == 'resolved' and ext and len(ext) == 2 and c.frame in size.get(key, ()) and
                        tuple(ext) != size[key][c.frame]):
                    hit = True
        bad[e['assignment']] = bad.get(e['assignment'], False) or hit
    return bad


@feature
def q5k_every_assignment(p):
    """Q5k The data keys that fire on any assignment, narrowed to fire only if every assignment has the violation (A2).
    `compose_ab_equal_every` (DC, H): a positive `compose` atom whose A and B labels X holds, such that every assignment has
    a row with A equal to B (None without such an atom). (`q1_atom_laws.compose_ab_equal` with the row test per assignment.)
    `frame_bad_every` (DC, H): every assignment has an entry with a framed Position or Box column whose resolved extent is
    not the example's grid size (`q1_off_grid.frame_bad` with the test per assignment). None at a Det point: X there is
    the task-level body table without its Example column, and every train example's entry holds the rows of all
    examples, so a row's extent is compared with another example's grid.

    Needs: full X. Monotone: no.
    """
    x = p.x
    rows = C.defaultdict(list)
    for e in x.all_entries:  # X's own rows: the test entries too
        rows[e['assignment']].extend(tuple(tuple(c.get('value') or ()) for c in r) for r in e['rows'])
    ab = []
    if rows:
        for cols in q1._atom_columns(p, 'compose'):
            if 'A' in cols and 'B' in cols:
                ab.append(all(any(r[cols['A']] == r[cols['B']] for r in rs) for rs in rows.values()))
    bad = _framed_bad(p, x.all_entries) if rows and p.kind != 'Det' else None
    return {'compose_ab_equal_every': int(any(ab)) if ab else None,
            'frame_bad_every': int(all(bad.values())) if bad else None}


# ------------------------------------------------------------------------------------------------ static output tests

# Library relations that read the grid's frame: the inset and outset family give boxes of the grid, and the extent
# relations read its size. A body that holds one has rows that depend on the example.
GRID_RELATIONS = frozenset(q3.INSET | q3.OUTSET) | {'frame_extent', 'axis_extents', 'sub_extent', 'frame_offset', 'box_extent'}


def _per_example_clause(p, clause, memo):
    """Whether the rows of a clause before the point can differ between train examples. A DET holds one value per
    assignment, broadcast to every example (the table rows of every DET table in 500 sampled gold views are equal in all
    examples), so it differs only if its table has an Example column, or a Position, Box or Offset column, whose frame can
    differ. A Rule clause differs
    if one of its atoms does. Any other clause (an INIT, a CHOOSE, ...) and any clause the form cannot tell is taken to differ."""
    if clause.keyword == 'DET':
        tables = clause.tables()
        return not tables or any(c.type in ('Example', 'Position', 'Box', 'Offset') for t in tables for c in t.columns())
    if clause.keyword == 'RULE':
        return any(_per_example_atom(p, a, memo) for a in clause.atoms)
    return True


def _per_example_atom(p, a, memo):
    if a.operator is not None:
        return False
    if a.kind == 'fact' or a.relation in GRID_RELATIONS or any(x.literal == 'zero box' for x in a.arguments):
        return True
    if q3._declared(a):
        if a.relation not in memo:
            memo[a.relation] = True  # a cycle counts as per-example
            defs = [c for c in p.clauses_before() if c.relation == a.relation]
            memo[a.relation] = not defs or any(_per_example_clause(p, c, memo) for c in defs)
        return memo[a.relation]
    return not _library(a)


def _valid_atom(a):
    """Whether atom a, a conjunct of the top conjunction, holds on every row that the other conjuncts leave (it removes
    no row): `inside` of a label in itself, or of an `input` cell in the zero box (the frame); `centered` of the zero box;
    `=`, `<=` or `>=` of a label with itself."""
    if a.negated or a.branch or a.quantifier is not None or a.conditional is not None:
        return False
    if a.operator is not None:
        return a.operator in ('=', '<=', '>=') and a.first is not None and a.second is not None and a.first.label is not None and (
            a.first.label == a.second.label)
    if not _library(a):
        return False
    sites = _sites(a)
    if a.relation == 'inside':
        x, y = sites.get('A'), sites.get('B')
        return x is not None and y is not None and ((x.joins and x.label == y.label) or (
            y.is_zero and x.joins and q3._src(x) == 'input.P'))
    if a.relation == 'centered':
        return sites.get('P') is not None and sites['P'].is_zero
    return False


@feature
def q5l_static_output(p):
    """Q5l The clause that `OUT` reads, decided on its form (A1); None elsewhere.
    `same_every_example_s` (SC, S): the body reads nothing that differs between examples (no `input`, no `ex_input`, no
    zero box or grid relation, no component port, and no declared table whose clause reads one; a DET is one value per
    assignment, so only a DET table with an Example column differs), X has no Example column, and the train outputs are not
    all equal. X has the same rows in every example, so one grid stands for unequal outputs. A later atom can still read
    `input`, so the obligation is met at the end of the clause. (The static part of `final_vs_output.same_every_example`;
    the table key is `q5a_output_tables.same_every_example_g`.)
    `equals_input_s` (SC, S): the body is one positive `input` atom that makes both of its labels, plus only conjuncts that
    remove no row (`_valid_atom`); X holds exactly the `input` Position and Color, and some train output differs from its
    input. The painted grid is the input. (The static part of `available_size.equals_input` and `contains_input.equal`.)

    Needs: form, finished. Monotone: no.
    """
    if not p.out_reads:
        return None
    body = _body(p)
    if body is None or not body.atoms:
        return None
    examples = p.examples()
    cols = p.x.columns()
    memo = {}
    outputs = {e.output.cells for e in examples}
    same = int(len(outputs) > 1 and bool(cols) and not any(c.type == 'Example' for c in cols) and
               not any(_per_example_atom(p, a, memo) for a in body.atoms))
    inputs = [a for a in body.atoms if a.relation == 'input' and a.operator is None]
    equals = 0
    if len(inputs) == 1 and all(a is inputs[0] or _valid_atom(a) for a in body.atoms):
        i = inputs[0]
        s = _sites(i)
        types = sorted(c.type or '' for c in cols)
        if (not i.negated and not i.branch and i.quantifier is None and i.conditional is None and
                all(n in s and s[n].binds and s[n].field is None for n in ('P', 'Col')) and types == ['Color', 'Position'] and
                any(e.output.cells != e.input.cells for e in examples)):
            held = {v.label for v in p.clause.x_columns.values() if v is not None}
            equals = int(held == {s['P'].label, s['Col'].label})
    return {'same_every_example_s': same, 'equals_input_s': equals}


# ------------------------------------------------------------------------------------------------ soft keys

def _components(body, held):
    """The connected groups of the body's atoms, two atoms being joined by a label they share (the labels of an INIT port's
    key clause count as one label). An atom with no label is a group of its own. Returns a list of
    (atoms, whether the group holds a label that X holds, whether it holds a head label of the port)."""
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    key = set(body.clause.key.variables) if body.keyed and body.clause.key is not None else set()

    def node(label):
        return '#key' if label in key else label
    atoms = [(a, {x.label for x in a.arguments if x.label is not None}) for a in body.atoms]
    for _, labels in atoms:
        first = None
        for x in sorted(labels):
            first = first or x
            parent[find(node(x))] = find(node(first))
    groups = C.defaultdict(list)
    for n, (a, labels) in enumerate(atoms):
        groups[find(node(min(labels))) if labels else ('atom', n)].append((a, labels))
    heads = {h.label for h in body.head if h.label is not None}
    out = []
    for members in groups.values():
        labels = set().union(*[ls for _, ls in members])
        out.append(([a for a, _ in members], bool(labels & held), bool(labels & heads)))
    return out


@feature
def q5m_soft_form(p):
    """Q5m Two soft keys on the form, and narrowings of the second that gold may never fire. None without a body.
    `siteless_atom` (SP, H): atoms that have no label or literal at any site (a relation or table read for its existence).
    `siteless_not` (SP, H): those below NOT. `siteless_det` (SP, R): those that read a DET table, which has a row in every
    assignment, so the atom holds.
    `disconnected_body` (SC, H): groups of the body's atoms that share no label, less one (0 for a connected body; an atom with
    no label is a group). A later atom can join the groups.
    `disconnected_cross` (SC, H): 1 where two or more groups each hold a label that X holds, so that X is a product of
    independent row sets.
    `disconnected_filter` (SC, H): groups other than the one that holds a label of X or of the port's head, where the
    group's atoms are all negated or all comparisons (a test on nothing that X holds).
    `disconnected_valid` (SC, R): groups of atoms that all remove no row (`_valid_atom`), where the body has two groups or more.

    Needs: form, finished. Monotone: no.
    """
    body = _body(p)
    if body is None:
        return None
    bare = [a for a in body.atoms if a.operator is None and not a.arguments]
    dets = {c.relation for c in p.clauses_before() if c.keyword == 'DET'}
    held = {v.label for v in p.clause.x_columns.values() if v is not None}
    groups = _components(body, held)
    n = len(groups)
    cross = int(sum(1 for _, h, _ in groups if h) >= 2)
    filt = sum(1 for atoms, h, head in groups if n > 1 and not h and not head and all(a.negated or a.operator for a in atoms))
    valid = sum(1 for atoms, _, _ in groups if n > 1 and all(_valid_atom(a) for a in atoms))
    return {'siteless_atom': len(bare), 'siteless_not': sum(a.negated for a in bare),
            'siteless_det': sum(a.relation in dets and not a.negated for a in bare), 'disconnected_body': max(n - 1, 0), 'disconnected_cross': cross,
            'disconnected_filter': filt, 'disconnected_valid': valid}


# ------------------------------------------------------------------------------------------------ constructs
#
# The held-out run counts exposure for a form key as the distinct gold clauses that contain the construct the key tests.
# A construct is a function of a Pair (the gold view): True where the clause has the construct, False where it has not,
# None where the key does not apply to the clause. They are not features.

def _c_fn_dup(p):
    body = _body(p)
    if body is None:
        return None
    geo = _geometry(body)
    return any(a.relation == b.relation and a.negated == b.negated and _related(a, b) for i, a in enumerate(geo) for b in geo[i + 1:])


def _c_overlap(p):
    body = _body(p)
    return None if body is None else any(True for _ in _comparison_pairs(body))


def _c_margin(p):
    body = _body(p)
    if body is None:
        return None
    m = [a for a in body.atoms if a.relation == 'margin' and _library(a)]
    return any(_margin_pair(a, b, False) for i, a in enumerate(m) for b in m[i + 1:])


def _c_contra(p):
    body = _body(p)
    return None if body is None else _contradictions(body, need_labels=False) > 0


def _c_axis_k(p):
    body = _body(p)
    if body is None:
        return None
    return any(a.operator is None and _library(a) and _positive(a) and (a.relation in SINGLE_K or a.relation in AXIS_K) and
               any(x.is_zero and x.name in ('K', 'K1', 'K2') for x in a.arguments) for a in body.atoms)


def _c_zero_position(p):
    body = _body(p)
    if body is None:
        return None
    return any(a.operator is None and (q3._declared(a) or a.relation == 'input') and any(x.is_zero for x in a.arguments)
               for a in body.atoms)


def _c_relation(*names):
    def construct(p):
        body = _body(p)
        return None if body is None else any(a.relation in names and _library(a) for a in body.atoms)
    return construct


def _c_neg_pair(p):
    body = _body(p)
    if body is None:
        return None
    return _count_neg_pairs(body, made=False) > 0


def _c_dp_box(p):
    body = _body(p)
    if body is None:
        return None
    return any(a.operator is None and a.relation.startswith('&') and
               any(x.label is not None and x.column_type == 'Position' for x in a.arguments) for a in body.atoms)


def _c_unread(p):
    body = _body(p)
    if body is None or body.name == 'key':
        return None
    for v in body.variables.values():
        for o in v.occurrences:
            if o.binds and o.atom is not None and (q3._src(o) in ('perp.A2', 'port:cell.P_outer') or (
                    p.kind == 'Rule' and (o.atom.negated or o.atom.quantifier or o.atom.branch or o.atom.conditional))):
                return True
    return False


def _c_bare(p):
    body = _body(p)
    return None if body is None else any(a.operator is None and not a.arguments for a in body.atoms)


def _c_split_body(p):
    body = _body(p)
    return None if body is None else len(_components(body, set())) > 1


def _c_before(p):
    return None if _before_heads(p) is None else True


# key -> construct; the old keys that the new ones split map to the same construct
EXPOSURE = {
    'q5d_order_static.b_static': _c_before,
    'q5m_soft_form.siteless_not': _c_bare,
    'q5m_soft_form.siteless_det': _c_bare,
    'q5m_soft_form.disconnected_filter': _c_split_body,
    'q5m_soft_form.disconnected_valid': _c_split_body,
    'q5f_atom_laws.compose_ab_same': _c_relation('compose'),
    'q5f_atom_laws.compose_c_eq_a_same': _c_relation('compose'),
    'q5f_atom_laws.apply_pout_eq_p_same': _c_relation('apply'),
    'q5f_atom_laws.neg_pair_static': _c_neg_pair,
    'q5f_atom_laws.dp_box_at_position_f': _c_dp_box,
    'q4b_geometry.dp_box_at_position': _c_dp_box,
    'q5g_atom_pairs.fn_dup_d': _c_fn_dup,
    'q3a_cell_geometry.fn_dup': _c_fn_dup,
    'q5g_atom_pairs.partial_overlap_related': _c_overlap,
    'q3b_comparisons.partial_overlap_pair': _c_overlap,
    'q5g_atom_pairs.dup_margin_k': _c_margin,
    'q3d_box_measures.dup_margin_BD': _c_margin,
    'q5g_atom_pairs.contra_t': _c_contra,
    'q3f_table_reads.contra': _c_contra,
    'q5h_zero_sites.axis_k_zero_k': _c_axis_k,
    'q3c_containment.axis_k_zero': _c_axis_k,
    'q5h_zero_sites.zero_position': _c_zero_position,
    'q3f_table_reads.zero_nonnumber': _c_zero_position,
    'q5i_unread_labels.unread_label_u': _c_unread,
    'q3d_box_measures.unread_perp_A2': _c_unread,
    'q3d_box_measures.unread_cell_P_outer': _c_unread,
    'q3h_orphan.orphan_label': _c_unread,
}
