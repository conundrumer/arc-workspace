"""Round 14, explorer d: the use of the order and set components (Order, Cardinality, Excess, Singleton, Inclusion,
Quotient, Distance and the walks) against the tables they build.

A candidate either reads the output tables of an earlier instance of such a component (an atom `&inst.port`), or is a
port table of one (an INIT point). A read fits the task where the table it reads is not degenerate: an order whose
keys hold one member or tie everywhere, a count that never varies, a Singleton whose keys all agree or all clash, an
Inclusion whose pairs all hold or none does. The functions read the instance's own tables (rows per key and example),
the candidate's atoms and X, never a label or relation name for meaning: a component comes from the INIT clause and a
port from the table's source name after the instance.
"""
import collections as C

from featlib import feature

ORDER = ('Order', 'Ordinal', 'Extremes', 'ArgExtremes', 'Mode', 'LexOrder')
COUNT = ('Cardinality', 'Tally', 'Excess')
SINGLE = ('Singleton', 'Unanimous')
INCL = ('Inclusion', 'KeyedSetCompare')
GRAPH = ('Quotient', 'Canon', 'IdentOf', 'Distance', 'GraphDistance', 'Propagation', 'Walk', 'CycleWalk', 'Unfold', 'Take',
         'IndexCycle')
MINE = frozenset(ORDER + COUNT + SINGLE + INCL + GRAPH + ('DemonstrationConsistency',))
MAX_ROWS = 60000


def _port(table):
    """The port a table belongs to: the part of its source name after the instance."""
    name = getattr(table, 'name', '') or ''
    return name.split('.', 1)[1] if '.' in name else ''


def _instances(p):
    """{instance relation: (component, {port: Table})} for the earlier INIT clauses of a component of this area."""
    cache = getattr(p, '_r14d_inst', None)
    if cache is not None:
        return cache
    out = {}
    try:
        for cl in p.clauses_before():
            if cl.keyword == 'INIT' and cl.component in MINE:
                ports = {}
                for tb in cl.tables():
                    ports[_port(tb)] = tb
                out[cl.relation] = (cl.component, ports)
    except Exception:
        out = {}
    try:
        p._r14d_inst = out
    except Exception:
        pass
    return out


def _reads(p):
    """[(component, instance, port, table)] for each atom of the candidate that reads a table of an instance of this
    area (one entry per atom)."""
    out = []
    try:
        inst = _instances(p)
        for a in p.clause.body.atoms:
            rel = a.relation or ''
            if '.' not in rel or a.kind not in ('table', 'port', 'relation'):
                continue
            head, port = rel.split('.', 1)
            if head in inst:
                comp, ports = inst[head]
                tb = a.table
                if tb is None:
                    tb = ports.get(port)
                if tb is not None:
                    out.append((comp, head, port, tb))
    except Exception:
        return []
    return out


def _groups(table, key_names=('key',)):
    """{(assignment, example, key values): [non-key value tuples]} of a table, or None if it is too large."""
    try:
        if sum(len(e['rows']) for e in table.entries) > MAX_ROWS:
            return None
        cols = table.columns()
        kidx = [c.index for c in cols if c.column in key_names]
        vidx = [c.index for c in cols if c.column not in key_names and c.type != 'Example']
        out = C.defaultdict(list)
        for a, e, m, row in table.rows():
            out[(a, e, tuple(row[i] for i in kidx))].append(tuple(row[i] for i in vidx))
        return out
    except Exception:
        return None


def _mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None


def _agg(acc, name, vals, how=('mean',)):
    vals = [v for v in vals if v is not None]
    if not vals:
        return
    if 'mean' in how:
        acc[name] = sum(vals) / len(vals)
    if 'min' in how:
        acc[name + '_min'] = min(vals)
    if 'max' in how:
        acc[name + '_max'] = max(vals)


def _member_sizes(ports):
    """Members per key of an Order instance, from its rank table: {(a, e, key): count}."""
    tb = ports.get('rank') or ports.get('dual_rank') or ports.get('score') or ports.get('member')
    if tb is None:
        return None
    g = _groups(tb)
    return None if g is None else {k: len(v) for k, v in g.items()}


@feature
def d1_order_read(p):
    """D1 The Order outputs a candidate reads (rank, dual_rank, minimal, maximal, successor, cyclic_successor), as
    tables of their instance: `single` (share of keys with one member), `tied` (share of keys whose members share a
    rank), `sel` (for minimal and maximal: the rows over the members, per key, mean), `edges` (for the successor
    tables: rows per member, mean), `self_loop` (share of cyclic successor rows that join a member to itself),
    `empty` (the table read has no row), `ports` (distinct output ports read) and `reads` (atoms).

    Needs: the earlier INIT clauses' tables. Monotone: no.
    """
    try:
        rd = [r for r in _reads(p) if r[0] in ORDER]
        if not rd:
            return None
        acc = {}
        single, tied, sel, edges, loops, empty = [], [], [], [], [], []
        seen = set()
        for comp, inst, port, tb in rd:
            ports = _instances(p)[inst][1]
            sizes = _member_sizes(ports)
            if sizes is None or not sizes:
                continue
            if (inst, 'inst') not in seen:
                seen.add((inst, 'inst'))
                single.append(sum(1 for n in sizes.values() if n == 1) / len(sizes))
                rk = ports.get('rank')
                g = _groups(rk, ('key',)) if rk is not None else None
                if g:
                    cols = rk.columns()
                    ridx = [c.index for c in cols if c.column == 'R']
                    if ridx:
                        t = 0
                        for k, rows in g.items():
                            rs = [r[-1] for r in rows]
                            if len(set(rs)) < len(rs):
                                t += 1
                        tied.append(t / len(g))
            g = _groups(tb)
            if g is None:
                continue
            empty.append(0.0 if g else 1.0)
            if port in ('minimal', 'maximal') and g:
                sel.append(_mean([len(v) / sizes[k] for k, v in g.items() if sizes.get(k)]))
            elif port in ('successor', 'cyclic_successor'):
                n_mem = sum(sizes.values())
                edges.append(sum(len(v) for v in g.values()) / n_mem if n_mem else None)
                if port == 'cyclic_successor':
                    tot = loop = 0
                    for rows in g.values():
                        for r in rows:
                            tot += 1
                            h = len(r) // 2
                            loop += r[:h] == r[h:]
                    if tot:
                        loops.append(loop / tot)
        _agg(acc, 'single', single, ('mean', 'max'))
        _agg(acc, 'tied', tied, ('mean', 'max'))
        _agg(acc, 'sel', sel, ('mean', 'max'))
        _agg(acc, 'edges', edges, ('mean',))
        _agg(acc, 'self_loop', loops, ('mean',))
        _agg(acc, 'empty', empty, ('max',))
        acc['ports'] = len({(i, pt) for _, i, pt, _ in rd})
        acc['reads'] = len(rd)
        return acc
    except Exception:
        return None



def _quantities(p):
    """{name: [per-example value]} of grid counts that a count could equal: sides, cells, colours, cells off the
    most common colour, for the input and the output of each train example."""
    cache = getattr(p, '_r14d_q', None)
    if cache is not None:
        return cache
    q = C.defaultdict(list)
    try:
        for ex in p.examples():
            for side, g in (('in', ex.input), ('out', ex.output)):
                if g is None:
                    q[side + '_h'].append(None)
                    continue
                h, w = g.size
                cols = C.Counter(c for row in g.cells for c in row)
                bg = max(cols.values()) if cols else 0
                q[side + '_h'].append(h)
                q[side + '_w'].append(w)
                q[side + '_cells'].append(h * w)
                q[side + '_colors'].append(len(cols))
                q[side + '_fg'].append(h * w - bg)
                q[side + '_fg_colors'].append(max(0, len(cols) - 1))
                q[side + '_least'].append(min(cols.values()) if cols else 0)
                q[side + '_max'].append(bg)
    except Exception:
        q = C.defaultdict(list)
    try:
        p._r14d_q = q
    except Exception:
        pass
    return q


def _number_col(tb, names):
    cols = tb.columns()
    idx = [c.index for c in cols if c.column in names and c.type == 'Number']
    return idx[0] if idx else None


@feature
def d2_count_read(p):
    """D2 The counts a candidate reads (Cardinality.size, Excess.excess, Distance.distance), from the table read:
    `distinct` (distinct counts over all keys and examples), `const` (1 where all counts are equal), `zero` (share of
    zero counts), `vary` (1 where an example's counts differ from another example's), and the fit to the train grids:
    `fit_out` and `fit_in`, the largest share of examples whose set of counts holds the example's output (input)
    grid quantity (a side, the cells, the colours, the cells off the most common colour), taken over the quantities
    and over the examples that have a count.

    Needs: the earlier INIT clauses' tables and the train grids. Monotone: no.
    """
    try:
        rd = [r for r in _reads(p) if (r[0] in COUNT and r[2] in ('size', 'excess', 'tally')) or (r[0] in ('Distance', 'GraphDistance') and r[2] == 'distance')]
        if not rd:
            return None
        acc = {}
        distinct, const, zero, vary, fo, fi = [], [], [], [], [], []
        q = _quantities(p)
        for comp, inst, port, tb in rd:
            col = _number_col(tb, ('N', 'K', 'n'))
            if col is None:
                continue
            by_ex = C.defaultdict(set)
            vals = []
            for a, e, m, row in tb.rows():
                v = row[col]
                by_ex[e].add(v)
                vals.append(v)
            if not vals:
                continue
            sv = set(vals)
            distinct.append(len(sv))
            const.append(1.0 if len(sv) == 1 else 0.0)
            zero.append(sum(1 for v in vals if v == 0) / len(vals))
            vary.append(1.0 if len({frozenset(s) for s in by_ex.values()}) > 1 else 0.0)
            for side, out in (('out', fo), ('in', fi)):
                best = None
                for name, per in q.items():
                    if not name.startswith(side + '_'):
                        continue
                    hit = n = 0
                    for e, s in by_ex.items():
                        if e < len(per) and per[e] is not None:
                            n += 1
                            hit += per[e] in s
                    if n:
                        r = hit / n
                        best = r if best is None else max(best, r)
                if best is not None:
                    out.append(best)
        _agg(acc, 'distinct', distinct, ('mean', 'min'))
        _agg(acc, 'const', const, ('max',))
        _agg(acc, 'zero', zero, ('max',))
        _agg(acc, 'vary', vary, ('max',))
        _agg(acc, 'fit_out', fo, ('max',))
        _agg(acc, 'fit_in', fi, ('max',))
        return acc or None
    except Exception:
        return None


@feature
def d3_singleton_read(p):
    """D3 The Singleton tables a candidate reads (value, plural), from their instance: `plural` (share of the keys
    whose members disagree), `keys` (keys with members, distinct), `mixed` (1 where some keys agree and some do not),
    `reads_value` and `reads_plural` (atoms reading each).

    Needs: the earlier INIT clauses' tables. Monotone: no.
    """
    try:
        rd = [r for r in _reads(p) if r[0] in SINGLE and r[2] in ('value', 'plural')]
        if not rd:
            return None
        acc = {'reads_value': 0, 'reads_plural': 0}
        seen = set()
        plural, keys, mixed = [], [], []
        for comp, inst, port, tb in rd:
            acc['reads_' + port] += 1
            if inst in seen:
                continue
            seen.add(inst)
            ports = _instances(p)[inst][1]
            v, pl = ports.get('value'), ports.get('plural')
            nv = len(_groups(v) or {}) if v is not None else 0
            npl = len(_groups(pl) or {}) if pl is not None else 0
            if nv + npl:
                plural.append(npl / (nv + npl))
                keys.append(nv + npl)
                mixed.append(1.0 if nv and npl else 0.0)
        _agg(acc, 'plural', plural, ('mean', 'max'))
        _agg(acc, 'keys', keys, ('mean',))
        _agg(acc, 'mixed', mixed, ('max',))
        return acc
    except Exception:
        return None


@feature
def d4_inclusion_read(p):
    """D4 The Inclusion tables a candidate reads (superset, equal), from their instance: `fill` (rows over the pairs of
    an observed key and a pattern, per example, mean), `full` and `none` (1 where a table has all or no pairs),
    `equal_share` (equal rows over superset rows) and `unique` (share of observed keys with at most one equal
    pattern).

    Needs: the earlier INIT clauses' tables. Monotone: no.
    """
    try:
        rd = [r for r in _reads(p) if r[0] in INCL and r[2] in ('superset', 'equal')]
        if not rd:
            return None
        acc = {}
        fill, full, none, eqs, uniq = [], [], [], [], []
        for comp, inst, port, tb in rd:
            ports = _instances(p)[inst][1]
            sup, eq = ports.get('superset'), ports.get('equal')
            obs, pat = ports.get('observed'), ports.get('pattern')
            def keyset(t, name):
                if t is None:
                    return None
                cols = t.columns()
                idx = [c.index for c in cols if c.column == name]
                return {(e, tuple(row[i] for i in idx)) for a, e, m, row in t.rows()} if idx else None
            ko, kp = keyset(obs, 'observed'), keyset(pat, 'pattern')
            pairs = _groups(tb, ())
            n_pairs = sum(len(v) for v in pairs.values()) if pairs else 0
            if ko is not None and kp is not None:
                tot = 0
                for e in {x[0] for x in ko}:
                    tot += sum(1 for x in ko if x[0] == e) * sum(1 for x in kp if x[0] in (e,))
                if tot == 0:
                    tot = len(ko) * len(kp)
                fill.append(min(1.0, n_pairs / tot) if tot else None)
                full.append(1.0 if tot and n_pairs >= tot else 0.0)
            none.append(1.0 if n_pairs == 0 else 0.0)
            if sup is not None and eq is not None:
                ns = sum(len(v) for v in (_groups(sup, ()) or {}).values())
                ne = sum(len(v) for v in (_groups(eq, ()) or {}).values())
                if ns:
                    eqs.append(ne / ns)
                g = _groups(eq, ('observed',))
                if g:
                    uniq.append(sum(1 for v in g.values() if len(v) <= 1) / len(g))
        _agg(acc, 'fill', fill, ('mean',))
        _agg(acc, 'full', full, ('max',))
        _agg(acc, 'none', none, ('max',))
        _agg(acc, 'equal_share', eqs, ('mean',))
        _agg(acc, 'unique', uniq, ('mean',))
        return acc or None
    except Exception:
        return None


@feature
def d5_graph_read(p):
    """D5 The Quotient classes and the Walk and Propagation tables a candidate reads: `classes` (classes over elements
    of a Quotient.class, 1 for the identity partition, 1/n for one class), `reach` (rows of a Propagation.reached over
    its source rows), `steps` (distinct step counts of a Walk.walk) and `moved` (share of walk rows whose end differs
    from its start).

    Needs: the earlier INIT clauses' tables. Monotone: no.
    """
    try:
        rd = [r for r in _reads(p) if r[2] in ('class', 'reached', 'walk')]
        if not rd:
            return None
        acc = {}
        cl, rc, st, mv = [], [], [], []
        for comp, inst, port, tb in rd:
            if port == 'class':
                cols = tb.columns()
                idc = [c.index for c in cols if c.type == 'Ident']
                if idc:
                    vals = list(tb.rows())
                    n_el = len(vals)
                    n_cl = len({(a, e, row[idc[-1]]) for a, e, m, row in vals})
                    if n_el:
                        cl.append(n_cl / n_el)
            elif port == 'reached':
                src = _instances(p)[inst][1].get('source')
                n_src = sum(len(e['rows']) for e in src.entries) if src is not None else 0
                n_r = sum(len(e['rows']) for e in tb.entries)
                if n_src:
                    rc.append(n_r / n_src)
            elif port == 'walk':
                cols = tb.columns()
                ni = [c.index for c in cols if c.column == 'N']
                if ni:
                    rows = list(tb.rows())
                    st.append(len({row[ni[0]] for a, e, m, row in rows}))
                    pi = [c.index for c in cols if c.column == 'p0']
                    qi = [c.index for c in cols if c.column == 'p']
                    if pi and qi and rows:
                        mv.append(sum(1 for a, e, m, row in rows if row[pi[0]] != row[qi[0]]) / len(rows))
        _agg(acc, 'classes', cl, ('mean',))
        _agg(acc, 'reach', rc, ('mean',))
        _agg(acc, 'steps', st, ('mean',))
        _agg(acc, 'moved', mv, ('mean',))
        return acc or None
    except Exception:
        return None


def _port_stats(g):
    """Group sizes and agreement of a port table's groups: {key: number}."""
    sizes = [len(v) for v in g.values()]
    out = {'keys': len(g), 'size_mean': sum(sizes) / len(sizes), 'size_max': max(sizes),
           'single': sum(1 for n in sizes if n == 1) / len(sizes), 'size_distinct': len(set(sizes))}
    sets = {frozenset(v) for v in g.values()}
    out['sets_distinct'] = len(sets) / len(g)
    return out


@feature
def d6_port_table(p):
    """D6 The port table that an INIT point of this area draws, X, against what its component builds from it. For the
    groups of X by key and example: `keys`, `size_mean`, `size_max`, `single` (share of groups of one row),
    `size_distinct` (distinct group sizes: a Cardinality or Excess whose groups all have one size builds one count)
    and `sets_distinct` (distinct member sets over groups). Singleton.member: `unanimous` (share of groups whose
    members agree) and `mixed`. Order.score and secondary_score: `tied` (share of groups with two members of one
    score). Quotient.equivalent and Inclusion: `classes` for the first (classes over elements of the pairs).

    Needs: X. Monotone: no.
    """
    try:
        cl = p.clause
        comp, port = cl.component, cl.port
        if comp not in MINE or not port:
            return None
        x = p.x
        g = _groups(x, ('key', 'observed', 'pattern'))
        if not g:
            return None
        out = _port_stats(g)
        if comp in SINGLE and port == 'member':
            ag = [1.0 if len(set(v)) == 1 else 0.0 for v in g.values()]
            out['unanimous'] = sum(ag) / len(ag)
            out['mixed'] = 1.0 if 0 < out['unanimous'] < 1 else 0.0
        if comp in ORDER and port in ('score', 'secondary_score'):
            tied = 0
            for v in g.values():
                sc = [r[-1] for r in v]
                tied += len(set(sc)) < len(sc)
            out['tied'] = tied / len(g)
        if comp in COUNT and port == 'member':
            q = _quantities(p)
            by_ex = C.defaultdict(set)
            for (a, e, k), v in g.items():
                by_ex[e].add(len(v))
            for side in ('out', 'in'):
                best = None
                for name, per in q.items():
                    if not name.startswith(side + '_'):
                        continue
                    n = hit = 0
                    for e, sz in by_ex.items():
                        if e < len(per) and per[e] is not None:
                            n += 1
                            hit += per[e] in sz
                    if n:
                        best = max(best or 0.0, hit / n)
                if best is not None:
                    out['fit_' + side] = best
        if comp in GRAPH and port in ('equivalent', 'edge') and comp in ('Quotient', 'Canon'):
            par = {}

            def find(a):
                while par.setdefault(a, a) != a:
                    par[a] = par[par[a]]
                    a = par[a]
                return a
            for key, rows in g.items():
                for r in rows:
                    if len(r) >= 2:
                        par[find((key[1], r[0]))] = find((key[1], r[1]))
            elems = list(par)
            if elems:
                out['classes'] = len({find(a) for a in elems}) / len(elems)
        return out
    except Exception:
        return None
