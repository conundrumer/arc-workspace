"""Features of explorer D, round 3: INIT input tables read as relations, and their link to the earlier ports.

Ident values are local to their table, so no function here compares an Ident of X with an Ident of
another table. Idents are compared only inside X. Counts of idents are compared across tables.
"""
import collections as C
import itertools

from featlib import feature, signature

NOMINAL = ('Ident', 'Color')


def _groups(table, cols_key, cols_val):
    """(assignment, train, model index) -> {key tuple: list of value tuples} over a table's entries."""
    out = {}
    for e in table.entries:
        g = C.defaultdict(list)
        for r in e['rows']:
            g[tuple(tuple(r[i]['value']) for i in cols_key)].append(tuple(tuple(r[i]['value']) for i in cols_val))
        out[e['assignment'], e['train'], e['model']] = g
    return out


def _key_cols(table):
    return [i for i, n in enumerate(table.names()) if n.startswith('key')]


def _relation_pairs(table, types=NOMINAL):
    """Every unordered pair of non-key columns of one nominal type, as (column, column) in no order."""
    key = set(_key_cols(table))
    by_type = C.defaultdict(list)
    for c in table.columns():
        if c.index not in key and c.type in types:
            by_type[c.type].append(c)
    return [pair for cs in by_type.values() for pair in itertools.combinations(cs, 2)]


@feature
def d1_relation_laws(p):
    """D1: X read as a binary relation (every pair of non-key Ident columns, and every pair of non-key Color columns, grouped by the key columns and pooled; the laws do not depend on which column comes first): share of reflexive rows, of rows whose converse is a row, transitivity violations per row, pairs covered over the pairs among its elements, and whether every group is a strict partial order (no reflexive row, no row with its converse, transitive) or a strict total order."""
    if not p.kind.startswith('INIT'):
        return None
    x = p.x
    pairs = _relation_pairs(x)
    if not pairs:
        return None
    rows = refl = sym = viol = npairs = maxpairs = 0
    groups = bad = lax = 0
    for ca, cb in pairs:
        for g in _groups(x, _key_cols(x), [ca.index, cb.index]).values():
            for vals in g.values():
                s = set(vals)
                ids = {u for u, _ in s} | {v for _, v in s}
                if len(ids) < 2:
                    continue
                succ = C.defaultdict(set)
                for u, v in s:
                    succ[u].add(v)
                r = sum(u == v for u, v in s)
                sy = sum(u != v and (v, u) in s for u, v in s)
                tv = sum((u, c) not in s for u, v in s for c in succ.get(v, ()) if c != u) if len(s) < 50000 else 0
                und = len({frozenset(t) for t in s if t[0] != t[1]})
                mp = len(ids) * (len(ids) - 1) // 2
                rows += len(s); refl += r; sym += sy; viol += tv; npairs += und; maxpairs += mp
                groups += 1
                lax += not (r == 0 and sy == 0 and tv == 0)
                bad += not (r == 0 and sy == 0 and tv == 0 and und == mp)
    if not rows:
        return None
    return {'refl': refl / rows, 'sym': sym / rows, 'trans': viol / rows, 'density': npairs / maxpairs,
            'strict_partial': float(lax == 0), 'strict_total': float(bad == 0)}


def _key_fields(p, table):
    """The columns of a table's key column (the component's key column, whose record fields are the key's labels),
    as Columns; [] where the component has none."""
    comp = p.lib.component(p.clause.component) if p.clause.component else None
    key = comp.get('key') if comp else None
    return [c for c in table.columns() if key is not None and c.column == key and c.field is not None]


@feature
def d2_member_gap(p):
    """D2: at an INIT input point, per key, the number of distinct Idents in X (all its non-key Ident columns) against the number in the Ident columns of an earlier port's table of the same instance (every such table, pooled), whose key fields align with X's key columns by their types (a table is left out where its key types differ from X's, and the feature is None where X's key types repeat): share of keys with fewer (short), more (excess) or as many (exact), and the mean ratio."""
    clause = p.clause
    if not p.kind.startswith('INIT') or clause.key is None or not clause.relation:
        return None
    x = p.x
    xkey = _key_fields(p, x)
    types = [c.type for c in xkey]
    if not xkey or None in types or len(set(types)) != len(types):
        return None
    keyidx = {c.index for c in xkey}
    xid = [c.index for c in x.columns() if c.type == 'Ident' and c.index not in keyidx]
    if not xid:
        return None
    earlier = {clause.relation + '.' + s.name for s in clause.before if s is not clause.key}
    refs = []
    for t in p.available():
        if t.name not in earlier:
            continue
        tk = {c.type: c.index for c in _key_fields(p, t)}
        if set(tk) != set(types) or len(tk) != len(_key_fields(p, t)):
            continue
        tid = [c.index for c in t.columns() if c.type == 'Ident' and c.index not in tk.values()]
        if tid:
            refs.append((t, [tk[ty] for ty in types], tid))
    if not refs:
        return None
    xs = {k[:2]: g for k, g in _groups(x, [c.index for c in xkey], xid).items()}
    n = short = excess = exact = 0
    ratio = 0.0
    for t, tkey, tid in refs:
        ts = {k[:2]: g for k, g in _groups(t, tkey, tid).items()}
        for ck, tg in ts.items():
            xg = xs.get(ck, {})
            for key, vals in tg.items():
                have = len({v for tup in vals for v in tup})
                got = len({v for tup in xg.get(key, ()) for v in tup})
                if not have:
                    continue
                n += 1
                short += got < have
                excess += got > have
                exact += got == have
                ratio += got / have
    if not n:
        return None
    return {'short': short / n, 'excess': excess / n, 'exact': exact / n, 'ratio': ratio / n}


@feature
def d3_ident_in_two_keys(p):
    """D3: at an INIT input point, the share of Idents of X (per context, over its non-key Ident columns) that occur under more than one value of an Axis-typed key column (axis) or of a Dir-typed key column (dir)."""
    if not p.kind.startswith('INIT'):
        return None
    x = p.x
    key = _key_cols(x)
    ident = [i for i, t in enumerate(x.types()) if t == 'Ident' and i not in key]
    if not key or not ident:
        return None
    out = {}
    for ty, name in (('Axis', 'axis'), ('Dir', 'dir')):
        kc = [i for i in key if x.types()[i] == ty]
        if not kc:
            continue
        total = multi = 0
        for e in x.entries:
            seen = C.defaultdict(set)
            for r in e['rows']:
                k = tuple(tuple(r[i]['value']) for i in kc)
                for i in ident:
                    seen[tuple(r[i]['value'])].add(k)
            total += len(seen)
            multi += sum(len(v) > 1 for v in seen.values())
        if total:
            out[name] = multi / total
    return out or None


def _color_position_table(p, colors):
    """The available table with exactly one Color column and exactly one Position column, whose Color values cover
    X's colors, with the fewest rows (ties by table name): (size, table, Color index, Position index)."""
    best = None
    for t in p.available():
        cols = t.columns()
        cs = [c for c in cols if c.type == 'Color']
        ps = [c for c in cols if c.type == 'Position']
        if len(cs) != 1 or len(ps) != 1:
            continue
        ci, pi = cs[0].index, ps[0].index
        have = {tuple(r[ci]['value']) for e in t.entries for r in e['rows']}
        if not colors or len(colors & have) < len(colors):
            continue
        size = sum(len(e['rows']) for e in t.entries)
        if best is None or (size, t.name) < (best[0], best[1].name):
            best = (size, t, ci, pi)
    return best


def _role_order(p, a, b):
    """Whether X's column a comes before column b in the roles of the INIT port at the point (the order of the port's
    columns in the component's interface); None where the point has no port or a column is not one of its columns."""
    clause = p.clause
    if not p.kind.startswith('INIT') or clause.port is None or not clause.component:
        return None
    comp = p.lib.component(clause.component)
    cols = [c for c, _, _ in (comp['inputs'].get(clause.port, []) if comp else [])]
    if a.column in cols and b.column in cols and a.column != b.column:
        return cols.index(a.column) < cols.index(b.column)
    return None


@feature
def d4_order_orientation(p):
    """D4: where X relates two Color columns under a Dir key column, the share of rows (a, b) whose color a lies nearer the key's side than b: margin index d of the position that an available table with one Color and one Position column gives the color (d = the Dir value; [top, bottom, left, right]); ties skipped. Over every pair of non-key Color columns, a is the pair's first column by the port's column roles, and the orientation that orients more rows where the pair has no roles. None without such a table."""
    if not p.kind.startswith('INIT'):
        return None
    x = p.x
    pairs = _relation_pairs(x, ('Color',))
    key = _key_cols(x)
    if not pairs:
        return None
    dirs = [i for i in key if x.types()[i] == 'Dir']
    if len(dirs) != 1:
        return None
    colors = {tuple(r[c.index]['value']) for e in x.entries for r in e['rows'] for pair in pairs for c in pair}
    found = _color_position_table(p, colors)
    if found is None:
        return None
    _, t, ci, pi = found
    nearest = {}
    for e in t.entries:
        for r in e['rows']:
            v = r[pi]['value']
            if len(v) != 4:
                continue
            k = (e['assignment'], e['train'], tuple(r[ci]['value']))
            nearest[k] = [min(a, b) for a, b in zip(nearest.get(k, v), v)]
    ok = bad = tie = 0
    for ca, cb in pairs:
        order = _role_order(p, ca, cb)
        ab = ba = ties = 0
        for e in x.entries:
            for r in e['rows']:
                d = r[dirs[0]]['value']
                if len(d) != 1 or not 0 <= d[0] <= 3:
                    continue
                ka = nearest.get((e['assignment'], e['train'], tuple(r[ca.index]['value'])))
                kb = nearest.get((e['assignment'], e['train'], tuple(r[cb.index]['value'])))
                if ka is None or kb is None:
                    continue
                if ka[d[0]] == kb[d[0]]:
                    ties += 1
                elif ka[d[0]] < kb[d[0]]:
                    ab += 1
                else:
                    ba += 1
        if order is False:
            ab, ba = ba, ab
        elif order is None and ba > ab:
            ab, ba = ba, ab
        ok += ab; bad += ba; tie += ties
    if ok + bad == 0:
        return None
    return {'oriented': ok / (ok + bad), 'ties': tie / (ok + bad + tie)}


@feature
def d5_column_selectivity(p):
    """D5: for X's Box and Position columns, among the available tables' columns of the same type and frame tag that contain every X value of that column (per context), the largest share of that table column's distinct values that X holds (1 means X restricts nothing); averaged over contexts where X is not empty. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so its rows would be compared with one example's rows of an earlier table."""
    if p.kind == 'Det':
        return None
    x = p.x
    best = None
    for ci, (ty, fr) in enumerate(zip(x.types(), x.frames())):
        if ty not in ('Box', 'Position'):
            continue
        xv = {}
        for e in x.entries:
            xv.setdefault((e['assignment'], e['train']), set()).update(tuple(r[ci]['value']) for r in e['rows'])
        xv = {k: v for k, v in xv.items() if v}
        if not xv:
            continue
        for t in p.available():
            for tj, (tty, tfr) in enumerate(zip(t.types(), t.frames())):
                if tty != ty or tfr != fr:
                    continue
                tv = {}
                for e in t.entries:
                    tv.setdefault((e['assignment'], e['train']), set()).update(tuple(r[tj]['value']) for r in e['rows'])
                shares = []
                for k, v in xv.items():
                    w = tv.get(k)
                    if not w or not v <= w:
                        shares = None
                        break
                    shares.append(len(v) / len(w))
                if shares:
                    m = sum(shares) / len(shares)
                    best = m if best is None else max(best, m)
    return best


def _made(scope):
    """The arguments that make their label. A label made outside every OR is made at its starred site. A label that an
    OR's first branch makes and every later branch names is made in each branch of that OR, at the branch's positive
    site (or `=` operand) of the label, outside NOT, ALL and IF tests, whose atom comes first in canonical order,
    wherever the stars stand."""
    out = {id(a) for a in scope.arguments if a.binds}
    branches = C.defaultdict(set)
    for a in scope.atoms:
        for orp, k in a.branch:
            branches[orp].add(k)
    for v in scope.variables.values():
        for b in v.binders:
            for orp, k in b.atom.branch:
                if k != 1:
                    continue
                picks = []
                for kk in sorted(branches[orp]):
                    occ = [a for a in v.occurrences if a.atom is not None and a.atom.branch and a.atom.branch[-1] == (orp, kk)
                           and not a.atom.negated and a.atom.conditional != 'test' and a.atom.quantifier is None
                           and (a.atom.operator is None or (a.atom.operator == '=' and a is a.atom.first))]
                    if not occ:
                        picks = None
                        break
                    picks.append(min(occ, key=lambda a: (repr(signature(a.atom)), a.name)))
                if picks:
                    out -= {id(a) for a in v.occurrences if a.atom is not None and any(o == orp for o, _ in a.atom.branch)}
                    out |= {id(a) for a in picks}
    return out


READS = ('table', 'fact')


@feature
def d6_join_cut(p):
    """D6: for each label that a positive read of one available table makes (a starred site, or its first site in a later branch of an OR that exports it) and a positive read of another available table holds at a site that does not make it, the share of the making column's values per context that the other table's column also holds; Ident labels are left out, since Ident values are local to their table. Reported as the smallest share (min), the number of such joins below 1 (cut) and equal to 1 (vacuous), and the number with a context where no value is held (void)."""
    body = p.clause.body
    if body is None:
        return None
    made = _made(body)
    joins = []
    for v in body.variables.values():
        if v.resolved_type == 'Ident':
            continue
        sites = [a for a in v.occurrences if a.atom is not None and a.atom.operator is None and not a.atom.negated
                 and a.atom.kind in READS and a.atom.interface is not None and a.atom.interface.table]
        for b in sites:
            if id(b) not in made:
                continue
            for j in sites:
                if id(j) not in made and j.atom.interface.table != b.atom.interface.table:
                    joins.append((b, j))
    shares = []
    void = 0
    for b, j in joins:
        s = _domains(b)
        t = _domains(j)
        if s is None or t is None:
            continue
        per = [len(s[k] & t[k]) / len(s[k]) for k in s if s[k] and k in t]
        if not per:
            continue
        shares.append(sum(per) / len(per))
        void += any(v == 0 for v in per)
    if not shares:
        return None
    return {'min': min(shares), 'cut': sum(v < 1 for v in shares), 'vacuous': sum(v == 1 for v in shares), 'void': void}


def _domains(arg):
    """(assignment, train) -> set of values of the table column an argument reads, or None."""
    table = arg.atom.table
    col = arg.atom.interface.column(arg.name)
    if table is None or col is None or col.index is None:
        return None
    out = {}
    for e in table.entries:
        out.setdefault((e['assignment'], e['train']), set()).update(tuple(r[col.index]['value']) for r in e['rows'])
    return out
