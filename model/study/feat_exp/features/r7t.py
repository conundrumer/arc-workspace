"""Round 7, explorer T: structure that a valid table keeps where valid tables are both smaller and larger than
invalid ones.

T1: a Number column that is a function of the displacement between two cells of one frame (a distance, a gap).
T2: at an INIT input point, each cell of the port's table lies under one key of the component, and every value of
    the source column the port binds a cell from is held that way.
"""
import collections as C
import itertools

from featlib import feature

MAX_ROWS = 50000
CELL_TYPES = ('Position', 'Box')
# The distances a Number at two cells usually holds: |dr| + |dc|, max(|dr|, |dc|) and the cells strictly between.
METRICS = (
    lambda dr, dc: abs(dr) + abs(dc),
    lambda dr, dc: max(abs(dr), abs(dc)),
    lambda dr, dc: max(abs(dr), abs(dc)) - 1,
)


def _contexts(table):
    """{(assignment, example): distinct rows of the first model}; a row is a tuple of decoded cells."""
    return {key: set(models[0]) for key, models in table.examples().items() if models and models[0]}


def _value(v):
    """A cell for comparison across two tables: a Position, Box or Offset by its margins (an X label bound from a
    table column holds that column's values, so the two frame tags need not be compared), else the decoded value."""
    return v.margins if hasattr(v, 'margins') else v


def _size(table):
    return sum(e.get('row_count', len(e.get('rows') or ())) for e in table.entries)


# ---------------------------------------------------------------- T1

@feature
def t1_number_displacement(p):
    """T1: for each Number column N of X and each pair of Position or Box columns of one non-empty frame tag, per
    context where N has 2 or more values, the value pairs grouped by their displacement (the difference of their top
    and left margins) and by the values of X's Dir and DiagDir columns in the row (a Number at a direction, such as a
    margin, is a function of the displacement and the direction); a displacement is tested when 2 or more distinct
    value pairs have it. `pure`: the largest share, over the (N, pair)
    combinations with a tested displacement, of tested value pairs whose displacement holds one value of N; `tested`:
    the share of the value pairs that are tested, for that combination; `metric`: the largest share of distinct
    (value, value, N) rows where N is |dr| + |dc|, max(|dr|, |dc|) or max(|dr|, |dc|) - 1, over the combinations;
    `n`: the combinations with a tested displacement. None without a Number column, such a pair of columns, or a
    tested displacement."""
    x = p.x
    cols = x.columns()
    nums = [c.index for c in cols if c.type == 'Number']
    pos = [c for c in cols if c.type in CELL_TYPES and c.frame]
    dirs = [c.index for c in cols if c.type in ('Dir', 'DiagDir')]
    pairs = [(a.index, b.index) for a, b in itertools.combinations(pos, 2) if a.frame == b.frame]
    if not nums or not pairs or _size(x) > MAX_ROWS:
        return None
    ctxs = _contexts(x)
    best_pure, best_tested, best_metric, n = None, 0.0, 0.0, 0
    for k in nums:
        for i, j in pairs:
            groups = C.defaultdict(lambda: C.defaultdict(set))
            triples = set()
            for ck, rows in ctxs.items():
                if len({r[k] for r in rows}) < 2:
                    continue
                for r in rows:
                    a, b, v = r[i], r[j], r[k]
                    if not hasattr(a, 'row') or not hasattr(b, 'row') or not isinstance(v, int):
                        continue
                    d = (b.row - a.row, b.col - a.col, *(r[q] for q in dirs))
                    groups[ck, d][(a.margins, b.margins)].add(v)
                    triples.add((ck, a.margins, b.margins, v))
            if not triples:
                continue
            npairs = sum(len(g) for g in groups.values())
            tested = pure = 0
            for g in groups.values():
                if len(g) < 2:
                    continue
                tested += len(g)
                if len({v for vals in g.values() for v in vals}) == 1:
                    pure += len(g)
            met = 0.0
            for f in METRICS:
                hit = 0
                for ck, am, bm, v in triples:
                    if f(bm[0] - am[0], bm[2] - am[2]) == v:
                        hit += 1
                met = max(met, hit / len(triples))
            best_metric = max(best_metric, met)
            if not tested:
                continue
            n += 1
            share = pure / tested
            if best_pure is None or share > best_pure or (share == best_pure and tested / npairs > best_tested):
                best_pure, best_tested = share, tested / npairs
    if best_pure is None:
        return None
    return {'pure': best_pure, 'tested': best_tested, 'metric': best_metric, 'n': n}


# ---------------------------------------------------------------- T2

def _port_key_columns(p):
    """At an INIT input point: (X key column indices, X cell column indices), where a key column is an X column
    whose top-level column is the component port's column of the type parameter Key, and a cell column is any other
    Position or Box column; else None."""
    clause = p.clause
    if clause is None or not clause.port or not clause.component:
        return None
    comp = p.lib.component(clause.component)
    if not comp:
        return None
    ports = comp['inputs'].get(clause.port)
    if not ports:
        return None
    key_names = {name for name, _t, param in ports if param == 'Key'}
    if not key_names:
        return None
    cols = p.x.columns()
    key = [c.index for c in cols if c.column in key_names]
    other = [c.index for c in cols if c.column not in key_names and c.type in CELL_TYPES]
    if not key or not other:
        return None
    return key, other


def _top_level(atom):
    return atom is not None and not (atom.negated or atom.branch or atom.quantifier or atom.conditional)


def _sources(p, other):
    """For each X column in `other`: the (X index, table, table column index) of each top-level atom of the candidate
    that binds the column's label from a column of the same type of an available table."""
    clause = p.clause
    out = []
    by_index = {}
    for v in clause.x_columns.values():
        if v is not None and v.column is not None and v.column.index is not None:
            by_index[v.column.index] = v
    for i in other:
        v = by_index.get(i)
        if v is None or v.column.type is None:
            continue
        for site in v.binders:
            atom = site.atom
            if not _top_level(atom) or atom.scope is not v.scope:
                continue
            t = atom.table
            if t is None:
                continue
            col = t.column(site.name)
            if col is None or col.type != v.column.type:
                continue
            out.append((i, t, col.index))
    return out


@feature
def t2_key_partition(p):
    """T2: at an INIT input point whose component port has a Key column and X has another Position or Box column, per
    context with 2 or more keys: `uniq`, the share of X's distinct tuples of those cell columns that occur under
    exactly one key; `keys`, the mean number of keys per such tuple; `total`, the smallest share, over the cell
    columns that a top-level atom binds from a column of an available table, of that column's distinct values (per
    context, pooled) that X holds under exactly one key, 1 where no such column; `ctx`, the contexts counted. None
    elsewhere or without a context of 2 keys."""
    kc = _port_key_columns(p)
    if kc is None:
        return None
    key, other = kc
    x = p.x
    if _size(x) > MAX_ROWS:
        return None
    ctxs = _contexts(x)
    n_val = n_one = n_keys = 0
    counted = 0
    per_col = C.defaultdict(lambda: C.defaultdict(lambda: C.defaultdict(set)))
    for ck, rows in ctxs.items():
        groups = C.defaultdict(set)
        for r in rows:
            groups[tuple(r[i] for i in other)].add(tuple(r[i] for i in key))
            for i in other:
                per_col[i][ck][_value(r[i])].add(tuple(r[j] for j in key))
        if len({k for ks in groups.values() for k in ks}) < 2:
            continue
        counted += 1
        n_val += len(groups)
        n_one += sum(len(ks) == 1 for ks in groups.values())
        n_keys += sum(len(ks) for ks in groups.values())
    if not counted:
        return None
    total = 1.0
    sources = _sources(p, other)
    if sources:
        shares = []
        for i, t, ti in sources:
            tctx = _contexts(t)
            have = held = 0
            for ck, trows in tctx.items():
                if ck not in ctxs:
                    continue
                vals = {_value(r[ti]) for r in trows}
                have += len(vals)
                held += sum(len(per_col[i][ck].get(v, ())) == 1 for v in vals)
            if have:
                shares.append(held / have)
        if shares:
            total = min(shares)
    return {'uniq': n_one / n_val, 'keys': n_keys / n_val, 'total': total, 'ctx': counted}
