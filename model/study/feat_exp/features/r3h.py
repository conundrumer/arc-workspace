"""Features of explorer H, round 3: how X relates to the tables built before the point."""
import itertools

from featlib import ORIENTATION_TYPES, feature

MAX_TABLE_ROWS = 20000
MAX_MAPPINGS = 24


def _contexts(table, keep=None):
    """(assignment, train) -> set of rows (tuples of cell values) over the context's models, restricted to keep."""
    out = {}
    for e in table.all_entries:  # X against the earlier tables: the test entries too, where both tables have them
        rows = out.setdefault((e['assignment'], e['train'] if 'train' in e else ('test', e['test'])), set())
        for r in e['rows']:
            rows.add(tuple(tuple(r[i]['value']) for i in keep) if keep is not None else tuple(tuple(c['value']) for c in r))
    return out


def _mappings(p, xcols, table):
    """The maps from X's kept columns to the table's columns that H3 compares. Where the candidate reads every kept X
    column's label from one column of the table, that read is the one map. Otherwise every injective map onto columns
    of equal type and compatible frame tag (equal, or one of them empty), when there are at most MAX_MAPPINGS of
    them, and none when there are more."""
    tcols = table.columns()
    own = []
    for c in xcols:
        v = p.clause.x_columns.get(c.name)
        hit = None
        for a in v.occurrences if v is not None else []:
            atom = a.atom
            if atom is not None and atom.operator is None and not atom.negated and atom.interface is not None \
                    and atom.interface.table == table.id:
                tc = atom.interface.column(a.name)
                if tc is not None and tc.index is not None and tc.type == c.type:
                    hit = tc.index
                    break
        own.append(hit)
    if None not in own and len(set(own)) == len(own):
        return [tuple(own)]
    cands = [[t.index for t in tcols if t.type == c.type and (t.frame == c.frame or not t.frame or not c.frame)]
             for c in xcols]
    out = []
    for combo in itertools.product(*cands):
        if len(set(combo)) == len(combo):
            out.append(combo)
            if len(out) > MAX_MAPPINGS:
                return []
    return out


@feature
def h1_avail_relation(p):
    """H1: how X's rows relate to the projection of each table built before the point onto columns of the same type.

    eq: some table's projection equals X in every shared context; sup: X strictly contains it in every shared context;
    sub: X is strictly inside it in every shared context; eq_share, precision, coverage: best over tables of the share of
    contexts with equality, the share of X's rows found in the projection, and the share of the projection's rows found in X.
    A table's columns map to X's by the candidate's read of that table where it reads every X column there, else by every
    type-compatible map (at most 24). Ident columns of X are left out; None when X has no other column or no table matches.
    eq, sup, sub, eq_share and precision are absent where every column kept is of an orientation type (such as Dir or
    Axis): any table that lists the orientations has the same rows, so the equality says nothing.

    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so its rows would be compared with one example's rows of an earlier table.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    xcols = [c for c in x.columns() if c.type not in ('Ident', 'Example')]
    if not xcols or not x.all_entries:
        return None
    xs = {k: frozenset(rows) for k, rows in _contexts(x, [c.index for c in xcols]).items()}
    best_eq = best_prec = best_cov = 0.0
    eq_all = sup_all = sub_all = 0
    n_tables = 0
    for t in p.available():
        if t.name in ('ex_input', 'ex_output') or sum(len(e['rows']) for e in t.entries) > MAX_TABLE_ROWS:
            continue
        found = False
        for mp in _mappings(p, xcols, t):
            ts = _contexts(t, list(mp))
            shared = [k for k in xs if k in ts]
            if not shared:
                continue
            eq = sup = sub = 0
            prec = cov = 0.0
            for k in shared:
                a, b = xs[k], frozenset(ts[k])
                eq += a == b
                sup += a > b
                sub += a < b
                inter = len(a & b)
                prec += inter / len(a) if a else 1.0
                cov += inter / len(b) if b else 1.0
            n = len(shared)
            found = True
            best_eq = max(best_eq, eq / n)
            best_prec = max(best_prec, prec / n)
            best_cov = max(best_cov, cov / n)
            eq_all |= eq == n
            sup_all |= sup == n
            sub_all |= sub == n
        n_tables += found
    if not n_tables:
        return None
    if all(c.type in ORIENTATION_TYPES for c in xcols):
        return {'coverage': best_cov, 'n_tables': n_tables}
    return {'eq': int(eq_all), 'sup': int(sup_all), 'sub': int(sub_all), 'eq_share': best_eq,
            'precision': best_prec, 'coverage': best_cov, 'n_tables': n_tables}
