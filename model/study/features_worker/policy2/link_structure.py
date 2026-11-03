"""Features of a table B against the tables A that it reads (A -> B), and against the tables already in the program.

Hypotheses (feature keys are prefixed hd_):
- g: B continues the program's chain. It reads the deepest table so far, covers the program's tables as ancestors, and closes open ends
  (tables that nothing reads yet). Computed from `parents` alone.
  Gold reads the deepest table in INIT and RULE points, and a table that many tables read in DET points (hd_g_taskwide, hd_g_cons_max).
- j: B is joined to what it reads. Each relation parent A shares a same-type column whose values B's rows keep inside A's values; A's values
  survive in B; a parent that B does not join to is an orphan (a cross product).
- p: the parents of B fit each other: same-type columns of two parents overlap on values.
- r: B adds a column that no table in the program has: columns of B equal, example by example, to a column of an available table are redundant.
All of them read train rows only (x_rows entries of kind 1, and kind 0 split by the Example column).
"""
import math

WID = {'Position': 4, 'Box': 4, 'Offset': 4}
_C = {}


def _state(ctx):
    if _C.get('ctx') is not ctx:
        by = ctx['by_token']
        av = {n['token'] for n in ctx['available']}
        dep = {}

        def depth(t, stack=()):
            if t in dep:
                return dep[t]
            n = by.get(t)
            d = 1 + max([depth(x, stack + (t,)) for x in (n['parents'] or []) if x in by and x not in stack] or [0]) if n else 0
            dep[t] = d
            return d
        for t in by:
            depth(t)
        cons = {}
        for t in av:
            for x in by[t]['parents'] or []:
                if x in av:
                    cons[x] = cons.get(x, 0) + 1
        _C.clear()
        _C.update(ctx=ctx, by=by, av=av, dep=dep, cons=cons, front={t for t in av if t not in cons},
                  maxd=max([dep[t] for t in av] or [0]), cols={}, sigs=None)
    return _C


def _cols(node):
    """{column: {example or None: set of values}} of the train rows, and the column types. None where rows do not fit the types."""
    S = _C
    tok = node['token']
    if tok in S['cols']:
        return S['cols'][tok]
    tt = node.get('table_types') or []
    w = [WID.get(t, 1) for t in tt]
    off = [0]
    for x in w:
        off.append(off[-1] + x)
    exc = tt.index('Example') if 'Example' in tt else None
    out = [dict() for _ in tt]
    ok = bool(tt)
    nrows = {}
    for ent in node.get('x_rows') or []:
        (k, e), rows = ent[0], ent[1]
        if k == 2 or not ok:
            continue
        for r in rows:
            if len(r) != off[-1]:
                ok = False
                break
            cell = [tuple(r[off[i]:off[i + 1]]) if w[i] > 1 else r[off[i]] for i in range(len(tt))]
            key = (cell[exc] if exc is not None else None) if k == 0 else e
            nrows[key] = nrows.get(key, 0) + 1
            for i, v in enumerate(cell):
                out[i].setdefault(key, set()).add(v)
    res = (out, list(tt), nrows) if ok else None
    S['cols'][tok] = res
    return res


def _get(colmap, e):
    s = colmap.get(e)
    return s if s is not None else colmap.get(None, ())


def _pooled(colmap, exs):
    out = set()
    for e in exs:
        for v in _get(colmap, e):
            out.add((e, v))
    return out


def _exs(*maps):
    s = set()
    for m in maps:
        s |= {k for k in m if k is not None}
    return s or {None}


def _link(cb, ca):
    """Best same-type column pair between B (cb) and A (ca): (inclusion of B's values in A's, share of A's values kept in B, B rows per kept value, type)."""
    colsb, tb, nb = cb
    colsa, ta, na = ca
    exs = _exs(*(colsb + colsa))
    best = None
    for j, t in enumerate(tb):
        sb = None
        for k, t2 in enumerate(ta):
            if t != t2:
                continue
            if sb is None:
                sb = _pooled(colsb[j], exs)
            if not sb:
                break
            sa = _pooled(colsa[k], exs)
            if not sa:
                continue
            inter = len(sa & sb)
            cand = (inter / len(sb), len(sa), inter / len(sa), t)
            if best is None or cand[:2] > best[:2]:
                best = cand
    if best is None:
        return None
    return best


def _total(nr):
    return sum(nr.values())


def _sig(colmap):
    return hash(tuple(sorted((str(e), tuple(sorted(map(str, s)))) for e, s in colmap.items())))


def _avail_sigs(S):
    if S['sigs'] is None:
        d = {}
        for t in S['av']:
            c = _cols(S['by'][t])
            if not c:
                continue
            for i, ty in enumerate(c[1]):
                d.setdefault((ty, _sig(c[0][i])), set()).add(t)
        S['sigs'] = d
    return S['sigs']


WEAK = {'Color', 'Dir', 'Dir8', 'DiagDir', 'Axis', 'DiagAxis', 'Sym', 'Sense', 'C4', 'D4'}


def _use(cb, cas):
    """Per parent: (use over any type, use over key types, share of the parent's values that B keeps, crispness of the best link). A use is
    join (B's values lie in the parent's), exclude (B's values lie in another parent's column that shares values with this parent's, and
    avoid this parent's) or none."""
    colsb, tb, _ = cb
    exs = _exs(*colsb, *[m for ca in cas for m in ca[0]])
    sb = {}
    for j, t in enumerate(tb):
        s = _pooled(colsb[j], exs)
        if s:
            sb[j] = s
    sa = [{k: _pooled(ca[0][k], exs) for k in range(len(ca[1]))} for ca in cas]
    # inclusion[(j, a, k)] = share of B's values of column j that lie in parent a's column k
    inc = {}
    for j, s in sb.items():
        for a, ca in enumerate(cas):
            for k, t in enumerate(ca[1]):
                if t == tb[j] and sa[a][k]:
                    inc[j, a, k] = len(s & sa[a][k]) / len(s)
    res = []
    for a, ca in enumerate(cas):
        flags = {0: 'none', 1: 'none'}
        surv = None
        crisp = 0.0
        for (j, a2, k), v in inc.items():
            if a2 != a:
                continue
            weak = tb[j] in WEAK
            c = 1 - 2 * min(v, 1 - v)
            crisp = max(crisp, c)
            if v >= 0.99:
                flags[0] = 'join'
                if not weak:
                    flags[1] = 'join'
                kept = len(sb[j] & sa[a][k]) / len(sa[a][k])
                surv = kept if surv is None else min(surv, kept)
            elif v == 0 and flags[0] != 'join':
                for (j2, a3, k3), v3 in inc.items():
                    if j2 == j and a3 != a and v3 >= 0.99 and sa[a][k] & sa[a3][k3]:
                        flags[0] = 'exclude'
                        if not weak and flags[1] != 'join':
                            flags[1] = 'exclude'
                        break
        res.append((flags[0], flags[1], surv, crisp))
    return res



def _fn(node, ctx):
    S = _state(ctx)
    by, av, dep = S['by'], S['av'], S['dep']
    tok = node['token']
    ps = [p for p in (node['parents'] or []) if p in by]
    out = {}
    # g: the chain
    pd = [dep[p] for p in ps]
    maxd = S['maxd'] or 1
    out['hd_g_maxpar_rel'] = (max(pd) / maxd) if pd else 0.0
    out['hd_g_reads_deepest'] = float(bool(pd) and max(pd) == S['maxd'])
    out['hd_g_depth_gap'] = float(S['maxd'] - max(pd)) if pd else float(S['maxd'])
    anc, stack = set(), list(ps)
    while stack:
        t = stack.pop()
        if t in anc:
            continue
        anc.add(t)
        stack.extend(x for x in (by[t]['parents'] or []) if x in by)
    out['hd_g_anc_frac'] = len(anc & av) / max(len(av), 1)
    front = S['front']
    out['hd_g_front_read'] = float(len(set(ps) & front))
    out['hd_g_cons_mean'] = (sum(S['cons'].get(p, 0) for p in ps) / len(ps)) if ps else 0.0
    out['hd_g_cons_max'] = float(max([S['cons'].get(p, 0) for p in ps] or [0]))
    out['hd_g_taskwide'] = float(any(e[0][0] == 0 for e in (node.get('x_rows') or [])))
    # j: how each relation parent is used
    cb = _cols(node)
    rp0 = [p for p in ps if _cols(by[p]) and _total(_cols(by[p])[2])]
    used = _use(cb, [_cols(by[p]) for p in rp0]) if cb and _total(cb[2]) else None
    if used:
        n = len(used)
        for lab, ix in (('any', 0), ('strong', 1)):
            u = [x[ix] for x in used]
            out['hd_j_%s_joined' % lab] = u.count('join') / n
            out['hd_j_%s_unused' % lab] = u.count('none') / n
        sv = [x[2] for x in used if x[2] is not None]
        out['hd_j_survive_min'] = min(sv) if sv else -1.0
        out['hd_j_survive_mean'] = sum(sv) / len(sv) if sv else -1.0
        out['hd_j_crisp_min'] = min(x[3] for x in used)
    else:
        for k in ('any_joined', 'any_unused', 'strong_joined', 'strong_unused'):
            out['hd_j_' + k] = -1.0
        out['hd_j_survive_min'] = out['hd_j_survive_mean'] = out['hd_j_crisp_min'] = -1.0
    # p: parents against each other
    ov = []
    rp = rp0
    for a in range(len(rp)):
        for b in range(a + 1, len(rp)):
            ca, cbb = _cols(by[rp[a]]), _cols(by[rp[b]])
            lk = _link(ca, cbb)
            if lk is None:
                ov.append(-1.0)
                continue
            ov.append(lk[0] * lk[2] if False else (lk[0] + lk[2]) / 2)
    out['hd_p_overlap_mean'] = sum(ov) / len(ov) if ov else -2.0
    out['hd_p_overlap_min'] = min(ov) if ov else -2.0
    # r: columns equal to a column of an available table
    if cb:
        sigs = _avail_sigs(S)
        psig = set()
        for p in ps:
            c = _cols(by[p])
            if c:
                for i, ty in enumerate(c[1]):
                    psig.add((ty, _sig(c[0][i])))
        carry = other = tot = 0
        for i, ty in enumerate(cb[1]):
            if max([len(s) for s in cb[0][i].values()] or [0]) <= 1:
                continue
            tot += 1
            sg = (ty, _sig(cb[0][i]))
            if sg in psig:
                carry += 1
            elif sigs.get(sg, set()) - {tok}:
                other += 1
        out['hd_r_carry'] = float(carry)
        out['hd_r_other'] = float(other)
        out['hd_r_new'] = float(tot - carry - other)
        out['hd_r_carry_frac'] = carry / tot if tot else -1.0
        out['hd_r_dup_frac'] = (carry + other) / tot if tot else -1.0
    else:
        for k in ('carry', 'other', 'new', 'carry_frac', 'dup_frac'):
            out['hd_r_' + k] = -1.0
    return out


KEYS = ['hd_g_anc_frac', 'hd_g_cons_max', 'hd_g_cons_mean', 'hd_g_taskwide', 'hd_g_depth_gap', 'hd_g_front_read', 'hd_g_maxpar_rel', 'hd_g_reads_deepest', 'hd_j_any_joined', 'hd_j_any_unused', 'hd_j_crisp_min', 'hd_j_strong_joined', 'hd_j_strong_unused', 'hd_j_survive_mean', 'hd_j_survive_min', 'hd_p_overlap_mean', 'hd_p_overlap_min', 'hd_r_carry', 'hd_r_carry_frac', 'hd_r_dup_frac', 'hd_r_new', 'hd_r_other']


def fn(node, ctx):
    try:
        out = _fn(node, ctx)
    except Exception:  # a table that does not parse gives the no-information value
        _C.clear()
        out = {}
    return {k: float(out.get(k, -1.0)) for k in KEYS}


FEATURE_FUNCS = {'hd': fn}
