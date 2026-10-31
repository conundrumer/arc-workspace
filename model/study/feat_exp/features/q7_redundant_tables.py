"""Q7 Keys for a Rule clause whose table repeats a table the program already has.

A feature reads only the train inputs and outputs, the available tables, X, the candidate's form, the clauses before the
point and the library interfaces. Classes and soundness are as in q6_residue_keys.

Keys:
    q7a_equals_input: `equals_input_t`, at a Rule point whose relation `OUT` does not read (`p.out_reads` is False): X's columns other than
        Example have distinct types, each the type of a column of `input`, and in every context of every assignment the
        rows of X equal the rows of `input` of that context's example, projected onto those types. Columns are matched
        by type, so the key does not read label names. The clause then gives a projection of `input`, which a reader
        can take from `input` itself. None elsewhere (also where `p.out_reads` is None), where X has no rows in any context,
        and on a clause with a `ONE` mark, whose models may keep fewer rows than X. The test entries of X and of `input` are
        compared as the train entries are. Class DC, soundness H. Needs: full X. Monotone: no.
"""
import importlib.util
from pathlib import Path

from featlib import FEATURES, feature


def _sibling(name):
    """A private copy of the feature module `name` next to this file, to reuse its helpers; its features are not registered."""
    saved = dict(FEATURES)
    spec = importlib.util.spec_from_file_location('_q7_' + name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        FEATURES.clear()
        FEATURES.update(saved)
    return module


q2 = _sibling('q2_table_tests')


@feature
def q7a_equals_input(p):
    """Q7a `equals_input_t`: X is a projection of `input` at a Rule point whose relation `OUT` does not read. See the module
    docstring."""
    if p.kind != 'Rule' or p.out_reads is not False:
        return None
    if p.clause.body is None or p.clause.body.marks:
        return {'equals_input_t': None}
    x, t = p.x, p.table('input')
    if t is None:
        return None
    xcols = [c for c in x.columns() if c.type != 'Example']
    by_t = {}
    for c in t.columns():
        by_t.setdefault(c.type, []).append(c.index)
    types = [c.type for c in xcols]
    if not xcols or len(set(types)) != len(types) or any(len(by_t.get(ty, ())) != 1 for ty in types):
        return {'equals_input_t': None}
    ix, it = [c.index for c in xcols], [by_t[ty][0] for ty in types]
    xc, tc = q2._contexts(x, True), q2._contexts(t, True)  # the test entries too: X is held against `input` there
    # `input` is the same at every assignment, so each context of X is compared with its example's input
    tin = {}
    for (_, e), rows in sorted(tc.items(), key=lambda kv: (kv[0][0], kv[0][1][1] if isinstance(kv[0][1], tuple) else kv[0][1])):
        tin.setdefault(e, rows)
    keys = [k for k in xc if k[1] in tin]
    if not keys or not any(xc[k] for k in keys):
        return {'equals_input_t': None}
    return {'equals_input_t': int(all(q2._rowset(xc[k], ix) == q2._rowset(tin[k[1]], it) for k in keys))}
