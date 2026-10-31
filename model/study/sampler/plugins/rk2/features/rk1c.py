"""Explorer c: label-level structure of the clause so far, and type-level fit of each option.

The row's `scope` lists the types of the bound labels but not which atom bound them, nor whether a later atom read them.
These features rebuild the labels from `prefix`, then ask, for each option, which labels its columns can take.
Label names are compared only for equality.  A label bound by a derived atom gets its type from `scope` (the positional
guess in the option's `types`, then elimination against the multiset `scope`); if that fails the label has type None and
fits any column.  Fields read: prefix, scope, k, and per option tok, kind, name (member suffix), columns, types, p, dag.base.

C1  Gold takes labels that no later atom has read yet: c1_dang_cols, c1_dang_frac, c1_dang_closes, c1_n_dang.
C2  Gold takes labels the last atom bound (or touched): c2_last_*, c2_touch_*, c2_recent.
C3  Gold's columns match distinct labels (the atom closes, binds few new labels): c3_*.
C4  Gold supplies the one type another option still lacks (a derived relation waiting for its input): c4_*.
C5  Gold joins or introduces a type that few options carry (idf over the row's options): c5_*.
C6  A comparison op is picked when two unread labels have the same type, or an unread number exists: c6_*.
"""
import functools
import math
import re

_SUPER = {'Position': 'Box', 'Offset': 'Box', 'Dir': 'Dir8', 'DiagDir': 'Dir8', 'Axis': 'Axis4', 'DiagAxis': 'Axis4',
          'Nat': 'Number', 'Int': 'Number'}

LEAF = re.compile(r'\(:(\w+) (\*?)([A-Za-z_]\w*)(?=[ )])')
REL = re.compile(r'^\((?:NOT \()?([^\s()]+)')
OPARGS = re.compile(r'(?<![\w*:])([A-Za-z_]\w*)(?=[ )])')


@functools.cache
def _nt(t):
    return str(t).split('(')[0]


@functools.cache
def _sub(a, b):
    while a:
        if a == b:
            return True
        a = _SUPER.get(a)
    return False


_compat_cache = {}


def _fits(label_t, col_t):
    """A label of type label_t can fill a column of type col_t (None label type: any)."""
    if label_t is None:
        return True
    k = (label_t, col_t)
    v = _compat_cache.get(k)
    if v is None:
        v = _compat_cache[k] = _sub(label_t, col_t)
    return v


def _same_base(opts, o):
    b = (o.get('dag') or {}).get('base')
    if b is None:
        return [o]
    return [x for x in opts.values() if x['kind'] == 'derived' and (x.get('dag') or {}).get('base') == b] or [o]


def _atom_option(opts, rel):
    """The option an atom's relation token names, and whether its types are that atom's own (a member of a derived base is
    found by the member suffix when the option's name still carries it)."""
    slot, _, member = rel.partition('.')
    o = opts.get(slot)
    if o is None or o['kind'] != 'derived' or not member:
        return o, o is not None
    ms = [x for x in _same_base(opts, o) if (x.get('name') or '').endswith('.' + member)]
    if len(ms) == 1:
        return ms[0], True
    return o, False


def _loose(a, b):
    return a == b or _sub(a, b) or _sub(b, a)


def _labels(row):
    """[[name, type or None, atom index, reads]] for the labels the prefix binds, in binding order."""
    opts = {o['tok']: o for o in row['options']}
    labs = {}
    order = []
    cand = {}   # label bound by a derived atom -> the option's types (positional guess first)
    for ai, a in enumerate(row.get('prefix') or []):
        m = REL.match(a)
        rel = m.group(1) if m else ''
        o, exact = _atom_option(opts, rel)
        leaves = LEAF.findall(a)
        if leaves:
            cmap = dict(zip(o.get('columns') or [], o.get('types') or [])) if o and o.get('columns') else None
            for li, (col, star, name) in enumerate(leaves):
                if star:
                    if name in labs:
                        labs[name][3] += 1
                        labs[name][4] = ai
                        continue
                    t = None
                    if cmap is not None:
                        t = cmap.get(col)
                        t = _nt(t) if t else None
                    elif o and o.get('types'):
                        ts = [_nt(x) for x in o['types']]
                        if exact:
                            cand[name] = (ts[li] if li < len(ts) else None, ts)
                        else:
                            cand[name] = (None, sorted({_nt(t) for x in _same_base(opts, o) for t in x['types'] or []}))
                    labs[name] = [name, t, ai, 0, ai]
                    order.append(name)
                elif name in labs:
                    labs[name][3] += 1
                    labs[name][4] = ai
        elif rel and not rel[0].isalnum() and rel[0] != '&' and rel[0] != '_':
            for name in OPARGS.findall(a[1:]):
                if name != 'NOT' and name in labs:
                    labs[name][3] += 1
                    labs[name][4] = ai
    out = [labs[n] for n in order]
    scope = [_nt(t) for t in row.get('scope') or []]
    if not scope:
        # scope missing although labels exist: accept the positional guesses
        for l in out:
            if l[0] in cand:
                l[1] = cand[l[0]][0]
        return out
    pool = list(scope)
    todo = [l for l in out if l[0] in cand]
    known = [l for l in out if l[0] not in cand and l[1] is not None]
    want = {l[0]: l[1] for l in known}
    for l in todo:
        if cand[l[0]][0] is not None:
            want[l[0]] = cand[l[0]][0]
    left = {n for n in want}
    for l in out:
        l[1] = None if l[0] in cand else l[1]
    for strict in (True, False):   # exact type matches first, then matches through the type hierarchy
        for l in known + todo:
            if l[0] not in left:
                continue
            w = want[l[0]]
            hit = next((p for p in pool if p == w), None) if strict else next((p for p in pool if _loose(p, w)), None)
            if hit is not None:
                pool.remove(hit)
                l[1] = hit
                left.discard(l[0])
    again = True
    while again:   # a label whose option types fit exactly one distinct pool type
        again = False
        for l in todo:
            if l[1] is not None:
                continue
            fit = {p for p in pool if any(_loose(p, t) for t in cand[l[0]][1])}
            if len(fit) == 1:
                p = fit.pop()
                pool.remove(p)
                l[1] = p
                again = True
    rest = [l for l in todo if l[1] is None]
    if rest and len(pool) == len(rest) and len(set(pool)) == 1:
        for l in rest:
            l[1] = pool[0]
    return out


def _arity_types(o):
    return [_nt(t) for t in o.get('types') or []]


def _match(cols, labs):
    """Size of a largest matching of columns to distinct labels (label type fits column type); small DFS."""
    if not cols or not labs:
        return 0
    adj = [[j for j, lt in enumerate(labs) if _fits(lt, c)] for c in cols]
    owner = {}

    def aug(i, seen):
        for j in adj[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in owner or aug(owner[j], seen):
                owner[j] = i
                return True
        return False
    n = 0
    for i in range(len(cols)):
        if adj[i] and aug(i, set()):
            n += 1
    return n


_CMP = ('=', '!=', '<', '<=', '>', '>=')
_ORD = ('<', '<=', '>', '>=')
_cache = [None, None]


def _rowinfo(row):
    if _cache[0] is row:
        return _cache[1]
    labs = _labels(row)
    nprefix = len(row.get('prefix') or [])
    all_t = [l[1] for l in labs]
    dang_t = [l[1] for l in labs if l[3] == 0]
    last_t = [l[1] for l in labs if l[2] == nprefix - 1 and l[3] == 0]
    touch_t = [l[1] for l in labs if l[4] == nprefix - 1]
    opts = [o for o in row['options'] if o['kind'] != 'op']
    ncount = {}
    for o in opts:
        for t in set(_arity_types(o)):
            ncount[t] = ncount.get(t, 0) + 1
    N = max(len(opts), 1)
    idf = {t: math.log((1 + N) / (1 + c)) for t, c in ncount.items()}
    # the single missing type of an option under the row's labels
    miss_p = {}
    miss_n = {}
    miss_of = {}
    for o in opts:
        cols = _arity_types(o)
        if not cols:
            continue
        free = _free_cols(cols, all_t)
        if len(free) == 1:
            T = free[0]
            miss_of[id(o)] = T
            miss_p[T] = miss_p.get(T, 0.0) + o['p']
            miss_n[T] = miss_n.get(T, 0) + 1
    numeric = ('Int', 'Nat', 'Number')
    dl = [l for l in labs if l[3] == 0]
    nnum = sum(1 for l in dl if l[1] in numeric)
    ages = [nprefix - 1 - l[2] for l in labs if l[3] == 0]
    byt = {}
    for t in all_t:
        if t is not None:
            byt[t] = byt.get(t, 0) + 1
    apairs = sum(c * (c - 1) // 2 for c in byt.values())
    info = dict(all_t=all_t, dang_t=dang_t, last_t=last_t, idf=idf, nlast=len(last_t), touch_t=touch_t, numpairs=nnum * (nnum - 1) // 2, nnum=nnum,
                apairs=apairs, age_t=sorted(zip(ages, [l[1] for l in labs if l[3] == 0]), key=lambda x: x[0]), miss_p=miss_p, miss_n=miss_n, miss_of=miss_of,
                nl=len(labs), nd=len(dang_t),
                pairs=_pairs([l for l in labs if l[3] == 0]), by_cols={})
    _cache[0], _cache[1] = row, info
    return info


def _free_cols(cols, labs):
    """The column types left over after a largest matching to distinct labels."""
    if not labs:
        return list(cols)
    adj = [[j for j, lt in enumerate(labs) if _fits(lt, c)] for c in cols]
    owner = {}

    def aug(i, seen):
        for j in adj[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in owner or aug(owner[j], seen):
                owner[j] = i
                return True
        return False
    matched = set()
    for i in range(len(cols)):
        if adj[i] and aug(i, set()):
            pass
    matched = set(owner.values())
    return [c for i, c in enumerate(cols) if i not in matched]


def _pairs(dang):
    """Number of pairs of dangling labels with the same known type."""
    n = 0
    for i in range(len(dang)):
        for j in range(i + 1, len(dang)):
            if dang[i][1] is not None and dang[i][1] == dang[j][1]:
                n += 1
    return n


def _fn(row, o):
    """C1 dangling labels, C2 last atom's labels, C3 distinct join, C4 unblocking, C5 rare types, C6 op on dangling pairs."""
    keys = ('c1_dang_cols', 'c1_dang_frac', 'c1_dang_closes', 'c1_n_dang', 'c2_last_cols', 'c2_last_any',
            'c3_match', 'c3_free', 'c3_closed', 'c3_match_frac', 'c4_unblock_n', 'c4_unblock_p', 'c4_unblock_max',
            'c2_last_share', 'c2_last_all', 'c2_recent', 'c2_touch_cols', 'c2_touch_share',
            'c5_idf_join', 'c5_idf_new', 'c5_idf_new_max', 'c6_pairs', 'c6_n_dang', 'c6_cmp', 'c6_ne', 'c6_eq', 'c6_ord', 'c6_not',
            'c6_cmp_dpairs', 'c6_cmp_apairs', 'c6_ord_numpairs', 'c6_cmp_numdang')
    d = dict.fromkeys(keys, 0.0)
    info = _rowinfo(row)
    d['c1_n_dang'] = float(info['nd'])
    d['c6_n_dang'] = float(info['nd'])
    d['c6_pairs'] = float(info['pairs'])
    if o['kind'] == 'op':
        tok = o['tok']
        if tok == 'NOT':
            d['c6_not'] = 1.0
        elif tok in _CMP:
            d['c6_cmp'] = 1.0
            d['c6_ne'] = float(tok == '!=')
            d['c6_eq'] = float(tok == '=')
            d['c6_ord'] = float(tok in _ORD)
            d['c6_cmp_dpairs'] = float(info['pairs'])
            d['c6_cmp_apairs'] = float(info['apairs'])
            d['c6_ord_numpairs'] = float(info['numpairs']) if tok in _ORD else 0.0
            d['c6_cmp_numdang'] = float(info['nnum'])
        return d
    cols = _arity_types(o)
    if not cols:
        return d
    block, supplied = info['by_cols'].get(tuple(cols)) or info['by_cols'].setdefault(tuple(cols), _by_cols(cols, info))
    d.update(block)
    # unblocking: other options whose single missing type this option supplies
    mp, mn, mo = info['miss_p'], info['miss_n'], info['miss_of']
    own = mo.get(id(o))
    n = pp = mx = 0.0
    for T in supplied:
        cn, cp = mn[T], mp[T]
        if own == T:
            cn -= 1
            cp -= o['p']
        if cn > 0:
            n += cn
            pp += cp
            mx = max(mx, cp)
    d['c4_unblock_n'] = n
    d['c4_unblock_p'] = pp
    d['c4_unblock_max'] = mx
    return d


def _by_cols(cols, info):
    """What the option's column types and the row's labels give, which options with one column list share: the keys of _fn that read
    nothing else, and the missing types of miss_p that the columns supply."""
    d = {}
    ar = len(cols)
    all_t = info['all_t']
    md = _match(cols, info['dang_t'])
    d['c1_dang_cols'] = float(md)
    d['c1_dang_frac'] = md / ar
    d['c1_dang_closes'] = float(info['nd'] > 0 and md >= info['nd'])
    ml = _match(cols, info['last_t'])
    d['c2_last_cols'] = float(ml)
    d['c2_last_any'] = float(ml > 0)
    if info['nlast']:
        d['c2_last_share'] = ml / info['nlast']
        d['c2_last_all'] = float(ml == info['nlast'])
    if info['touch_t']:
        mt = _match(cols, info['touch_t'])
        d['c2_touch_cols'] = float(mt)
        d['c2_touch_share'] = mt / len(info['touch_t'])
    # unread labels taken in order of recency: how recent the labels this option can take are
    rec = 0.0
    taken = set()
    for age, lt in info['age_t']:
        for ci, c in enumerate(cols):
            if ci not in taken and _fits(lt, c):
                taken.add(ci)
                rec += 1.0 / (1 + age)
                break
    d['c2_recent'] = rec
    free = _free_cols(cols, all_t)
    m = ar - len(free)
    d['c3_match'] = float(m)
    d['c3_free'] = float(len(free))
    d['c3_closed'] = float(m == ar and info['nl'] > 0)
    d['c3_match_frac'] = m / ar
    idf = info['idf']
    # rare type: joined columns and new columns, weighted by how few options carry that type
    freec = list(free)
    joined = list(cols)
    for t in freec:
        if t in joined:
            joined.remove(t)
    d['c5_idf_join'] = sum(idf.get(t, 0.0) for t in joined)
    d['c5_idf_new'] = sum(idf.get(t, 0.0) for t in freec)
    d['c5_idf_new_max'] = max((idf.get(t, 0.0) for t in freec), default=0.0)
    return d, [T for T in info['miss_p'] if any(_sub(t, T) for t in cols)]


def fn(row, o):
    """C1 dangling labels, C2 last atom's labels, C3 distinct join, C4 unblocking, C5 rare types, C6 comparison ops on dangling pairs."""
    return {k: float(v) for k, v in _fn(row, o).items()}


fn.unfiltered = _fn  # relsteer.Scorer calls this: its matrix takes the values as floats
FEATURE_FUNCS = {'rk1c': fn}
