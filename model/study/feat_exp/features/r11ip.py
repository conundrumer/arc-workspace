"""Round 11, explorer ip: INIT points where the score keeps many draws."""
import collections as C

from featlib import feature


def _port_params(p):
    """(the component's columns of the port at the point as {column: (type, parameter)}, the earlier scopes with their
    ports' columns) at an INIT port; None elsewhere."""
    clause = p.clause
    if clause is None or not clause.component or not clause.port:
        return None
    comp = p.lib.component(clause.component)
    if not comp:
        return None
    return comp, clause


@feature
def ip1_param_types(p):
    """IP1: at an INIT port, the head columns of the port at the point and of the INIT's earlier ports that the component declares with the same type parameter: `mismatch` the number of X head columns whose resolved type differs from the resolved type of an earlier port's head column of that parameter (a subtype in either direction counts as equal), `checked` the number compared."""
    if not p.kind.startswith('INIT'):
        return None
    got = _port_params(p)
    if got is None:
        return None
    comp, clause = got
    mine = {n: par for n, _t, par in (comp['inputs'].get(clause.port) or []) if par}
    if not mine:
        return None
    earlier = C.defaultdict(list)
    for scope in clause.before:
        for a in scope.head:
            ports = comp['inputs'].get(scope.name) or []
            par = next((pr for n, _t, pr in ports if n == a.column), None)
            if par and a.resolved_type:
                earlier[par].append(a.resolved_type)
    from featlib import subtype
    mismatch = checked = 0
    for a in clause.body.head:
        par = mine.get(a.column)
        if not par or par not in earlier or not a.resolved_type:
            continue
        checked += 1
        if not any(subtype(a.resolved_type, t) or subtype(t, a.resolved_type) for t in earlier[par]):
            mismatch += 1
    if not checked:
        return None
    return {'mismatch': mismatch, 'checked': checked}


# ---------------------------------------------------------------- shared reading of X

def _contexts(table):
    """(assignment, train) -> rows of the first model; a row is a list of cell values (tuples)."""
    out = {}
    for e in table.entries:
        out.setdefault((e['assignment'], e['train']), [[tuple(c['value']) for c in r] for r in e['rows']])
    return out



# ---------------------------------------------------------------- seeds of a flood on the frame's edge

@feature
def ip2_seed_border(p):
    """IP2: at the INIT port `source` of a component that also has a `node` input port and a `reached` output (the walk from sources inside a node set), over X's Position cells whose column has frame kind input or empty (rows of the first model of each context): `share` the share of cells with a margin of 0 (on the edge of the frame), `all` 1 where every cell is; None for another port or without such a column."""
    clause = p.clause
    if not p.kind.startswith('INIT') or clause is None or not clause.component or clause.port != 'source':
        return None
    comp = p.lib.component(clause.component)
    if not comp or 'node' not in comp['inputs'] or 'reached' not in comp['outputs']:
        return None
    cols = p.x.columns()
    idx = [c.index for c in cols if c.type == 'Position' and c.frame_kind in ('input', '', None)]
    if not idx:
        return None
    total = edge = 0
    for rows in _contexts(p.x).values():
        for r in rows:
            for i in idx:
                total += 1
                edge += min(r[i]) == 0
    if not total:
        return None
    return {'share': edge / total, 'all': int(edge == total)}
