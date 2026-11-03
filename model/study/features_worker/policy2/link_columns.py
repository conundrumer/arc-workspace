"""Features of a table B against the tables A it reads (A -> B), and against the prefix's tables that nothing reads yet.

hc_front: gold's next table consumes the prefix's tables that no other prefix table reads yet (open ends), and merges several of them;
  a sampled table reads available tables with no regard to which are still unread.
hc_carry: gold's next table carries the columns of the tables it reads (each parent's columns reappear in B, and B's rows are rows
  of the join of the parents), where a sampled table reads a parent for a filter or a key and drops the rest.

Both read only the parents list, the other prefix tables' parents, and row values; no is_gold, tags or clause text.
"""

_CACHE = {}


def _ctxinfo(ctx):
    c = _CACHE.get('ctx')
    if c is not None and c[0] is ctx:
        return c[1]
    by = ctx['by_token']
    av = [a['token'] for a in ctx['available']]
    avs = set(av)
    used = set(p for a in ctx['available'] for p in a['parents'] if p in avs)
    front = avs - used
    memo = {}

    def anc(tok):
        if tok in memo:
            return memo[tok]
        memo[tok] = set()  # guards a cycle
        out = set()
        for p in by[tok]['parents']:
            if p in avs:
                out.add(p)
                out |= anc(p)
        memo[tok] = out
        return out
    info = dict(avs=avs, front=front, anc=anc, tabs={})
    _CACHE['ctx'] = (ctx, info)
    return info


def hc_front(node, ctx):
    """Reads of open ends: how many of B's parents have no reader in the prefix, and how much of the prefix's open ends B's ancestry reaches."""
    info = _ctxinfo(ctx)
    avs, front = info['avs'], info['front']
    by = ctx['by_token']
    ps = [p for p in node['parents'] if p in avs]
    fr = [p for p in ps if p in front]
    closure = set()
    for p in ps:
        closure.add(p)
        closure |= info['anc'](p)
    cf = closure & front
    link = sum(1 for p in ps for q in ps if p != q and q in by[p]['parents'])
    nav, nfr = max(len(avs), 1), max(len(front), 1)
    return {
        'nfront': float(len(fr)),
        'fshare': len(fr) / len(ps) if ps else -1.0,
        'fcov': len(fr) / nfr,
        'nclosed': float(len(ps) - len(fr)),
        'closure_share': len(closure) / nav,
        'front_left': float(len(front) - len(cf)),
        'parent_links': float(link),
    }


def _cols(info, node, key):
    """The table at an example key as a list of columns, each a list of cell values (a Position or Box cell is a 4-tuple); None where the rows do not fit the types. Falls back to the table of all examples."""
    t = info['tabs'].get(node['token'])
    if t is None:
        types = node.get('table_types') or node.get('types') or []
        w = [4 if x in ('Position', 'Box') else 1 for x in types]
        tot = sum(w)
        t = {}
        for ent in node.get('x_rows') or []:
            (a, e), rows = ent[0], ent[1]
            if any(len(r) != tot for r in rows):
                t[(a, e)] = None
                continue
            cols = []
            s = 0
            for n in w:
                if n == 1:
                    cols.append([r[s] for r in rows])
                else:
                    cols.append(list(zip(*[[r[s + q] for r in rows] for q in range(n)])))
                s += n
            t[(a, e)] = (len(rows), cols, [set(c) for c in cols])
        info['tabs'][node['token']] = t
    if key in t:
        return t[key]
    return t.get((0, 0))


def _keys(info, B, A):
    ks = set()
    for n in (B, A):
        _cols(info, n, (1, 0))
        ks |= set(k for k in info['tabs'][n['token']] if k[0] == 1)
    return sorted(ks) or [(0, 0)]


def _link(info, B, A):
    """Match B's columns to A's columns, one to one, by the share of B's column values that A's column holds. Returns (map, ground, nA, nB) or None."""
    tyB = B.get('table_types') or []
    tyA = A.get('table_types') or []
    if not tyB or not tyA:
        return None
    data = []
    for k in _keys(info, B, A):
        tb, ta = _cols(info, B, k), _cols(info, A, k)
        if tb is None or ta is None or not tb[0] or not ta[0]:
            continue
        data.append((ta, tb))
    if not data:
        return None
    sc = []
    for j, t in enumerate(tyB):
        for i, u in enumerate(tyA):
            if t != u:
                continue
            nb = nin = 0
            for ta, tb in data:
                vb = tb[2][j]
                nb += len(vb)
                nin += len(vb & ta[2][i])
            if nb and nin / nb >= .95:
                sc.append((nin / nb, j, i))
    sc.sort(key=lambda x: (-x[0], x[1], x[2]))
    uj, ui, mp = set(), set(), {}
    for c, j, i in sc:
        if j in uj or i in ui:
            continue
        mp[j] = i
        uj.add(j)
        ui.add(i)
    if not mp:
        return {}, 0.0, len(tyA), len(tyB)
    J = sorted(mp)
    I = [mp[j] for j in J]
    gs = []
    for ta, tb in data:
        pa = set(zip(*[ta[1][i] for i in I]))
        gs.append(sum(r in pa for r in zip(*[tb[1][j] for j in J])) / tb[0])
    return mp, sum(gs) / len(gs), len(tyA), len(tyB)


def hc_carry(node, ctx):
    """Columns of B that come from each parent: the share of B's columns found in the parent, the share of the parent's columns found in B, and the share of B's rows whose found-columns tuple is a row of the parent."""
    info = _ctxinfo(ctx)
    by = ctx['by_token']
    avs, front = info['avs'], info['front']
    res = []
    for p in node['parents']:
        if p in avs:
            r = _link(info, node, by[p])
            if r is not None:
                res.append((p, r))
    if not res:
        return {'bmatch_max': -1.0, 'bmatch_mean': -1.0, 'bmatch_min': -1.0, 'carry_max': -1.0, 'carry_mean': -1.0,
                'carry_min': -1.0, 'ground_mean': -1.0, 'ground_min': -1.0, 'matched_total': 0.0, 'carry_front': -1.0}
    bm = [len(m) / nb for _, (m, g, na, nb) in res]
    cr = [len(m) / na for _, (m, g, na, nb) in res]
    gr = [g for _, (m, g, na, nb) in res]
    cf = [len(m) / na for p, (m, g, na, nb) in res if p in front]
    return {
        'bmatch_max': max(bm), 'bmatch_mean': sum(bm) / len(bm), 'bmatch_min': min(bm),
        'carry_max': max(cr), 'carry_mean': sum(cr) / len(cr), 'carry_min': min(cr),
        'ground_mean': sum(gr) / len(gr), 'ground_min': min(gr),
        'matched_total': float(sum(len(m) for _, (m, g, na, nb) in res)),
        'carry_front': sum(cf) / len(cf) if cf else -1.0,
    }


FEATURE_FUNCS = {'hc_front': hc_front, 'hc_carry': hc_carry}
