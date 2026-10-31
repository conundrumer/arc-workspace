"""Q4 Filters from the study of the mutants that static pruning could not check (status `unavailable`).

Each key is a count of the atoms of the candidate's body where the test holds (0 where none does), 0 or 1 where its
description says so, and None where the test needs a context the candidate is not in. A test reads the candidate's form
(`ports`, `geometry`, `declared`), or X and the train outputs (`differs_no_box`, `multi_model`). Where a test extends one
of q2 and q3, it calls that module's helper: the sibling module is loaded as a private copy, so that loading it
registers no feature.

ports: atoms that read a component port (`&inst.port`).
    port_zero_other: the literal 0 at a port column other than walk.p0, end.Origin, distance.K, cell.P_inner and
    dual_rank.R (the columns at which a 0 can be a position, an origin, a distance or a rank).
    port_repeat_label: one label at two columns of the atom (field arguments left out).
geometry: literal 0 and Box labels at Position sites.
    zero_site_strict: atoms with the literal 0 at a Position, Box or Offset column that is not a frame site, except
    `relative.X`.
    dp_box_at_position: declared-table and port atoms with a label of type Box at a Position column (the site makes the
    label or joins it).
declared: reads of declared tables, and X.
    differs_no_box: where `OUT` reads the candidate's relation, X has no Box column and q2's `final_vs_output.differs` holds (0 or 1).
    multi_model: some train example has more than one model of X (0 or 1).
    rep_join: declared-table atoms that read one joined label at two sites. rep_join_not: those below NOT.
"""
import collections as C
import importlib.util
from pathlib import Path

from featlib import FEATURES, feature, frame_zero


def _sibling(name):
    """A private copy of the feature module `name` next to this file, to reuse its helpers; its features are not registered."""
    saved = dict(FEATURES)
    spec = importlib.util.spec_from_file_location('_q4_' + name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        FEATURES.clear()
        FEATURES.update(saved)
    return module


q2 = _sibling('q2_table_tests')
q3 = _sibling('q3_form_filters')

# The (port, column) sites at which gold writes the literal 0 on a port atom.
ZERO_OK = frozenset({('walk', 'p0'), ('end', 'Origin'), ('distance', 'K'), ('cell', 'P_inner'), ('dual_rank', 'R')})


@feature
def q4a_ports(p):
    """Q4a Component ports. `port_zero_other`: port atoms with the literal 0 at a column outside ZERO_OK.
    `port_repeat_label`: port atoms with one label at two columns (a field argument does not count).

    Needs: form. Monotone: yes.
    """
    body = q3._body(p)
    if body is None:
        return None
    zero = repeat = 0
    for a in body.atoms:
        port = q3._port(a)
        if port is None:
            continue
        zero += any(x.is_zero and (port, x.column) not in ZERO_OK for x in a.arguments)
        columns = C.defaultdict(set)
        for x in a.arguments:
            if x.label is not None and x.field is None:
                columns[x.label].add(x.column)
        repeat += any(len(c) > 1 for c in columns.values())
    return {'port_zero_other': zero, 'port_repeat_label': repeat}


@feature
def q4b_geometry(p):
    """Q4b Position sites. `zero_site_strict`: atoms (comparisons left out) with the literal 0 at a Position, Box or
    Offset column that is not a frame site (`featlib.frame_zero`), except `relative.X`. `dp_box_at_position`: atoms of
    a declared table or a port with a label of type Box at a Position column. The label counts whether the site makes
    it or joins it, because which site of a label has the `*` depends on the order of the OR branches.

    Needs: form. Monotone: yes.
    """
    body = q3._body(p)
    if body is None:
        return None
    zero = box = 0
    for a in body.atoms:
        if a.operator is not None:
            continue
        zero += any(x.is_zero and x.column_type in ('Position', 'Box', 'Offset') and not frame_zero(x) and
                    not (a.relation == 'relative' and x.column == 'X') for x in a.arguments)
        if a.relation.startswith('&'):
            box += any(x.label is not None and x.column_type == 'Position' and x.resolved_type == 'Box' for x in a.arguments)
    return {'zero_site_strict': zero, 'dp_box_at_position': box}


def _multi_model(x):
    """Whether some example, train or test, has more than one model of X (X's own entries)."""
    return int(any(len(models) > 1 for models in list(x.contexts().values()) + list(x.test_contexts().values())))


def _differs_no_box(p):
    """q2's `differs` where `OUT` reads the candidate's relation and X has no Box column; None elsewhere, and at a Det point."""
    if p.kind == 'Det' or not p.out_reads or any(q2._fills(c, 'Box') for c in p.x.columns()):
        return None
    xc = q2._contexts(p.x)  # the train entries: X is held against the train outputs
    return q2._differs(p, xc, p.examples()) if xc else None


@feature
def q4c_declared(p):
    """Q4c Declared tables and X. `differs_no_box`: where `OUT` reads the candidate's relation (see q2), X has no Box column and
    `final_vs_output.differs` is 1; None elsewhere and where X has no Position and Color column or no rows. `differs_no_box` is None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids. `multi_model`:
    for some example (test inputs too) X has more than one model. `rep_join`: declared-table atoms (`&name`) that read one joined
    label at two sites. `rep_join_not`: those below NOT.

    Needs: partial. Monotone: no.
    """
    out = {'differs_no_box': _differs_no_box(p), 'multi_model': _multi_model(p.x), 'rep_join': None, 'rep_join_not': None}
    body = q3._body(p)
    if body is None:
        return out
    rep = rep_not = 0
    for a in body.atoms:
        if not q3._declared(a):
            continue
        reads = C.Counter(x.label for x in a.arguments if x.joins)
        if any(n > 1 for n in reads.values()):
            rep += 1
            rep_not += a.negated
    out['rep_join'], out['rep_join_not'] = rep, rep_not
    return out
