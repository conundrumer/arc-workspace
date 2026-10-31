"""G13 vs_earlier: X's columns against the columns of the tables built before the point.

The earlier tables are the tables of the clauses before the point (`p.clauses_before()`), and the tables that the
atoms of the INIT's earlier ports read. A column is compared as a set of values per context, over the contexts where
both tables have a row, and only with a column of the same type. Ident and Example columns are not compared (an
Ident is local to its table), and Number columns are left out of the single-column relations (small integer sets lie
inside each other by chance). Each context counts the first model of a table.
"""
import collections as C
import itertools

from featlib import ORIENTATION_TYPES, feature

MAX_TABLE_ROWS = 20000
MAX_MAPPINGS = 24
SKIP_TYPES = ('Ident', 'Example', 'Number')
BIG = 0.3  # an earlier column that makes up at least this share of the X column it lies in is not a chance subset


class _Rows(dict):
    """The rows of a table by context, with the column sets already made (`_column_sets`)."""

    def __init__(self, *args):
        super().__init__(*args)
        self.sets = {}


def _rows(table):
    """{(assignment, example): list of raw rows of the first model}; a context the table has with no row is empty.
    Kept on the table, so an earlier table of the point reads its rows once for every draw: do not modify them."""
    shape = (id(table.entries), tuple(len(e['rows']) for e in table.entries))
    cached = table.__dict__.get('_vs_earlier_rows')
    if cached is None or cached[0] != shape:
        ex = table.examples(decoded=False)
        if any(c.type == 'Example' for c in table.columns()):
            rows = _Rows({k: m[0] for k, m in ex.items() if m})
        else:
            keys = {(e['assignment'], e['train']) for e in table.entries}
            rows = _Rows({k: (ex[k][0] if ex.get(k) else []) for k in keys})
        cached = table.__dict__['_vs_earlier_rows'] = (shape, rows)
    return cached[1]


def _earlier(p):
    """The earlier tables, each once, without the tables of more than MAX_TABLE_ROWS rows."""
    seen, out = set(), []
    tables = [t for c in p.clauses_before() for t in c.tables()]
    for scope in p.clause.before or []:
        tables += [a.table for a in scope.atoms if a.positive and a.operator is None and a.table is not None]
    for t in tables:
        if t is None or t.id in seen:
            continue
        seen.add(t.id)
        if sum(len(e['rows']) for e in t.entries) <= MAX_TABLE_ROWS:
            out.append(t)
    return out


def _column_sets(rows, j):
    if j not in rows.sets:
        rows.sets[j] = {k: frozenset(r[j] for r in rs) for k, rs in rows.items()}
    return rows.sets[j]


def _relation(v, w):
    """How X's value sets v relate to the earlier column's sets w over the contexts where both are non-empty:
    (relation in every context: eq, sub, sup, disj or ovl; mean of |w| / |v|; the relation of each context)."""
    ks = [k for k in v if v[k] and w.get(k)]
    if not ks:
        return None, 0.0, C.Counter(), ks
    ratio = sum(len(w[k]) / len(v[k]) for k in ks) / len(ks)
    per = C.Counter('eq' if v[k] == w[k] else 'sub' if v[k] <= w[k] else 'sup' if v[k] >= w[k]
                    else 'disj' if not (v[k] & w[k]) else 'ovl' for k in ks)
    n = len(ks)
    for rel, parts in (('eq', ('eq',)), ('sub', ('eq', 'sub')), ('sup', ('eq', 'sup')), ('disj', ('disj',))):
        if sum(per[q] for q in parts) == n:
            return rel, ratio, per, ks
    return 'ovl', ratio, per, ks


def _mappings(p, xcols, table):
    """The maps from X's kept columns to the table's columns. Where the candidate reads every kept X column's label
    from one column of the table, that read is the one map. Otherwise every injective map onto columns of equal type
    and compatible frame tag (equal, or one of them empty), when there are at most MAX_MAPPINGS of them, else none."""
    tcols = table.columns()
    own = []
    for c in xcols:
        v = p.clause.x_columns.get(c.name)
        hit = None
        for a in v.occurrences if v is not None else []:
            atom = a.atom
            if atom is not None and atom.operator is None and atom.positive and atom.interface is not None \
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
def g13_columns(p):
    """G13 vs_earlier: how X's single columns lie against the same-type columns of the earlier tables.

    eq, sub, sup, disj, ovl: the number of distinct earlier columns (one that has the same sets in several tables counts once), summed over X's columns not of type Ident, Example or Number, that X's column equals in every context, lies inside in every context (not equal), strictly contains in every context, is disjoint from in every context, or relates to in any other way. Columns compare when their frame tags are equal or one is empty.
    sup_cell, sup_label: sup split into Position and Box columns, and other types; share: sup over all relations; absorb: the largest mean share of an X column that a column it contains makes up.
    ctx_sup, ctx_ovl, ctx_disj: the share of the (X column, earlier column, context) triples in which X's column contains it, overlaps it without containing it, or is disjoint from it.
    sub_ratio: over Box and Position columns and earlier columns of the same type and the same frame tag that contain X's column in every context, the largest mean share of the earlier column's distinct values that X holds (1 means X restricts nothing).
    None without such a column or related earlier column.
    Needs: partial. Monotone: no (`sub` and `disj` stay under a filter; `sup`, `ctx_sup` can clear).

    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so its rows would be compared with one example's rows of an earlier table.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    xrows = _rows(x)
    cols = [c for c in x.columns() if c.type not in SKIP_TYPES]
    if not cols or not xrows:
        return None
    tables = [(t, _rows(t)) for t in _earlier(p)]
    acc = C.Counter()
    absorb = 0.0
    ctxs = total = 0
    best_ratio = None
    for xc in cols:
        v = _column_sets(xrows, xc.index)
        seen = set()
        for t, trows in tables:
            for tc in t.columns():
                if tc.type != xc.type or not (xc.frame == tc.frame or not xc.frame or not tc.frame):
                    continue
                w = _column_sets(trows, tc.index)
                rel, ratio, per, ks = _relation(v, w)
                if rel is None:
                    continue
                sig = (rel, tuple(sorted((k, tuple(sorted(w[k]))) for k in ks)))
                if sig in seen:
                    continue
                seen.add(sig)
                acc[rel] += 1
                total += 1
                for name, n in per.items():
                    acc['ctx_' + name] += n
                    ctxs += n
                if rel == 'sup':
                    acc['sup_cell' if xc.type in ('Position', 'Box') else 'sup_label'] += 1
                    absorb = max(absorb, ratio)
                if xc.type in ('Position', 'Box') and xc.frame == tc.frame and per['eq'] + per['sub'] == len(ks):
                    share = sum(len(v[k]) / len(w[k]) for k in ks) / len(ks)
                    best_ratio = share if best_ratio is None else max(best_ratio, share)
    if not total:
        return None
    res = {key: acc[key] for key in ('eq', 'sub', 'sup', 'disj', 'ovl', 'sup_cell', 'sup_label')}
    res.update({'share': acc['sup'] / total, 'absorb': absorb, 'ctx_sup': acc['ctx_sup'] / ctxs,
                'ctx_ovl': acc['ctx_ovl'] / ctxs, 'ctx_disj': acc['ctx_disj'] / ctxs})
    if best_ratio is not None:
        res['sub_ratio'] = best_ratio
    return res


@feature
def g13_rows(p):
    """G13 vs_earlier: how X's rows relate to the projection of each earlier table onto columns of the same type.

    eq, sup, sub: 1 when, in every shared context, some earlier table's projection equals X (eq), X strictly contains it (sup), or X lies strictly inside it (sub); X's columns other than Ident and Example are projected.
    eq_share, precision, coverage: the best over earlier tables of the share of contexts with equality, the share of X's rows found in the projection, and the share of the projection's rows found in X.
    eq, sup, sub, eq_share and precision are absent where every column projected is of an orientation type (such as Dir or Axis): any table that lists the orientations has the same rows.
    n_tables: the number of earlier tables with a map.
    A table's columns map to X's by the candidate's read of that table where it reads every X column there, else by every type-compatible map (at most 24).
    port_inside: at an INIT point with earlier ports, the share of X's Position and Box cells (frame tag input) that lie in a column of the same type and frame tag of a table that an earlier port's atoms read. A column is left out where X has another input-frame column of its type (a relation's two ends, such as an edge's endpoints, are not drawn from what an earlier port reads).
    None where neither applies.
    Needs: partial. Monotone: no (`precision` and `port_inside` stay under a filter, `coverage` only falls; `eq`, `sup`, `sub` can change).

    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so its rows would be compared with one example's rows of an earlier table.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    xcols = [c for c in x.columns() if c.type not in ('Ident', 'Example')]
    xrows = _rows(x)
    res = {}
    if xcols and xrows:
        xs = {k: frozenset(tuple(r[c.index] for c in xcols) for r in rs) for k, rs in xrows.items()}
        best_eq = best_prec = best_cov = 0.0
        eq_all = sup_all = sub_all = n_tables = 0
        for t in _earlier(p):
            trows = _rows(t)
            found = False
            for mp in _mappings(p, xcols, t):
                if ('rows', mp) not in trows.sets:
                    trows.sets['rows', mp] = {k: frozenset(tuple(r[i] for i in mp) for r in rs) for k, rs in trows.items()}
                ts = trows.sets['rows', mp]
                shared = [k for k in xs if k in ts]
                if not shared:
                    continue
                eq = sup = sub = 0
                prec = cov = 0.0
                for k in shared:
                    a, b = xs[k], ts[k]
                    eq += a == b
                    sup += a > b
                    sub += a < b
                    inter = len(a & b)
                    prec += inter / len(a) if a else 1.0
                    cov += inter / len(b) if b else 1.0
                n = len(shared)
                found = True
                best_eq, best_prec, best_cov = max(best_eq, eq / n), max(best_prec, prec / n), max(best_cov, cov / n)
                eq_all |= eq == n
                sup_all |= sup == n
                sub_all |= sub == n
            n_tables += found
        if n_tables:
            res.update({'eq': eq_all, 'sup': sup_all, 'sub': sub_all, 'eq_share': best_eq, 'precision': best_prec,
                        'coverage': best_cov, 'n_tables': n_tables})
            if all(c.type in ORIENTATION_TYPES for c in xcols):
                for key in ('eq', 'sup', 'sub', 'eq_share', 'precision'):
                    del res[key]
    # X's cells inside what the earlier ports of the same INIT read.
    domain = C.defaultdict(set)
    kinds = set()
    for scope in p.clause.before or []:
        for atom in scope.atoms:
            t = atom.table if atom.positive and atom.operator is None else None
            if t is None:
                continue
            trows = _rows(t)
            for a in atom.arguments:
                tc = atom.interface.column(a.name)
                if tc is not None and tc.index is not None and tc.type in ('Position', 'Box') \
                        and tc.frame_kind == 'input':
                    kinds.add(tc.type)
                    for k, rs in trows.items():
                        domain[tc.type, k] |= {r[tc.index] for r in rs}
    # Two input-frame columns of one type are the two ends of a relation (an edge's endpoints), which ranges over
    # more cells than the seeds an earlier port reads: only a column that has no such partner is compared.
    grid = [c for c in x.columns() if c.type in ('Position', 'Box') and c.frame_kind == 'input']
    cells = [c for c in grid if c.type in kinds and sum(d.type == c.type for d in grid) == 1]
    if cells:
        total = inside = 0
        for k, rs in xrows.items():
            for r in rs:
                for c in cells:
                    total += 1
                    inside += r[c.index] in domain.get((c.type, k), ())
        if total:
            res['port_inside'] = inside / total
    return res or None


@feature
def g13_key_split(p):
    """G13 vs_earlier: how the cell sets of X's keys lie against the earlier tables' input-frame Position columns.

    For each X key column (type Ident or Box, 2 or more keys in some context) and each X Position column with frame tag input, the cell set of every (context, key) is compared with each input-frame Position column of an earlier table that does not hold every cell of the grid.
    key_inside: the largest share of keys whose cells all lie in an earlier column; key_apart: the largest share with no cell in it; key_split: the largest of min(share inside, 1 - share inside).
    small_inside, small_apart: key_inside and key_apart for the earlier column with the fewest distinct cells over all contexts.
    None without a key column, a cell column or such an earlier column.
    Needs: partial. Monotone: no.

    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so its rows would be compared with one example's rows of an earlier table.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    cols = x.columns()
    keys = [c for c in cols if c.type in ('Ident', 'Box')]
    cells = [c for c in cols if c.type == 'Position' and c.frame_kind == 'input']
    if not keys or not cells:
        return None
    exs = p.examples()
    area = {i: e.input.height * e.input.width for i, e in enumerate(exs)}
    earlier = []
    for t in _earlier(p):
        trows = _rows(t)
        for tc in t.columns():
            if tc.type == 'Position' and tc.frame_kind == 'input':
                cs = _column_sets(trows, tc.index)
                full = all(len(s) >= area.get(k[1], 1 << 30) for k, s in cs.items() if s)
                if cs and not full:
                    earlier.append(cs)
    if not earlier:
        return None
    xrows = _rows(x)
    size = [sum(len(v) for v in cs.values()) or 1 << 30 for cs in earlier]
    small = min(range(len(earlier)), key=lambda i: size[i])
    best_in = best_out = best_split = 0.0
    small_in = small_apart = None
    triples = 0
    for kc in keys:
        for cc in cells:
            if kc.index == cc.index:
                continue
            units = []
            for ctx, rs in xrows.items():
                by = {}
                for r in rs:
                    by.setdefault(r[kc.index], set()).add(r[cc.index])
                units.extend((ctx, s) for s in by.values())
            if len(units) < 2:
                continue
            for ei, cs in enumerate(earlier):
                n = inside = apart = 0
                for ctx, s in units:
                    ref = cs.get(ctx)
                    if ref is None:
                        continue
                    n += 1
                    inter = len(s & ref)
                    inside += inter == len(s)
                    apart += inter == 0
                if n < 2:
                    continue
                triples += 1
                share = inside / n
                best_in, best_out = max(best_in, share), max(best_out, apart / n)
                best_split = max(best_split, min(share, 1 - share))
                if ei == small:
                    small_in = max(small_in or 0.0, share)
                    small_apart = max(small_apart or 0.0, apart / n)
    if not triples:
        return None
    res = {'key_inside': best_in, 'key_apart': best_out, 'key_split': best_split}
    if small_in is not None:
        res.update({'small_inside': small_in, 'small_apart': small_apart})
    return res
