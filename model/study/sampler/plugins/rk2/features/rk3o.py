"""rk3o: order-free restatements of the lexical ranker features, on a masked relation row.  rk3o(row, option) -> {o<n>_<what>: float}.

A value depends on the unordered set of earlier atoms E (row['prefix']), the row's scope as a multiset, and the option.  A clause body is a set
of atoms that share labels, so the value does not read which atom comes first, which atom carries the '*' of a label, the order of `scope`, or
the order of `prefix_bases`.  What it reads of a label is how many times the earlier atoms hold it (once: unread), which atoms hold it, and its type.
A label's type comes from its library columns (the most specific one), else from the columns of a derived relation and the types in scope.
A frontier atom is an earlier atom that holds an unread label; it stands in for "the last atom".  Where several atoms or labels tie, they tie.
The first earlier atom, the maker of a label, the position of a slot and the distance between atoms are not read.

o1  Empty set: size of E, E is empty (by option kind, and a member of a base), no column type of the option is in scope.
    Replaces c_k, x:kk:<kind>:<k>, lib_k1, derived_k1, op_k1, none_in_scope, rk1a.a5_none_fit, rk2d.d2_k1_method, rk2f.f5_last_none.
o2  Frontier atoms: the number and kinds of the atoms that hold an unread label (kinds crossed with the option's class), the atoms of the option's own class,
    and the library relations that follow or repeat a frontier atom.
    Replaces b_follows_crop, b_follows_relative, b_repeat, b_fits_enum, rk2d.d3_last_<kind>, rk2d.d3_x_<class>_<kind>, rk2d.d3_not_after_der,
    rk2f.f5_last_<class>, rk2f.f5_same_as_last, rk2f.f5_run.
o3  Labels of one atom: the columns of the option matched to the unread labels of one frontier atom, and to all labels of one frontier atom.
    Replaces rk1c.c2_last_cols, c2_last_any, c2_last_share, c2_last_all, c2_touch_cols, c2_touch_share.
o4  Comparison on a pair: pairs of compatible labels, held once or twice, that share an atom or come from different atoms; pairs made at the same
    column of two atoms of one relation; numeric and unread labels of one atom.
    Replaces rk2d.d1_cmp_fresh_old, d1_cmp_fresh_old_num, d1_cmp_fresh_old0, d1_cmp_both_last, d1_cmp_twin, d1_cmp_stale, d1_cmp_nopair,
    rk2e.e2_cmp_numfresh, e2_cmp_lastfresh, e2_cmp_numfresh_pair.
o5  Twin pairs that two columns of a relation option can take.
    Replaces rk2d.d1_take_twin.
o6  Parallel application: the atoms of the option's relation share a label with another atom, and an unread label outside them has a type that
    they share or is a twin of a label they share.
    Replaces rk2f.f1_cons, f1_pend_n, f1_pend_twin_n, f1_pend_both_n, f1_pend_bdang, f1_pend_both_bdang, f1_once_cons_bdang, f1_gen_bdang.
Not restated: rk2e.e1_* and rk2e.e5_* (slot numbers), rk1c.c2_recent (distance between atoms), rk2d.d3_last_not, d3_last_cmp, d3_x_<class>_not,
d3_x_<class>_cmp, d3_not_after_not, rk2f.f5_last_cmp and f5_last_neg (a NOT or comparison atom holds no unread label; rk2d.d3_n_not, rk2f.f5_n_neg
and f5_n_cmp count them), rk1a.a1_not_k1_target, rk1b.b5_k1_not_nat and b5_k1_nat_unary (one pick shows them), and recency0, recency_log (not emitted).
"""
import os
import re
import sys
from collections import Counter

_S = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _S not in sys.path:
    sys.path.insert(0, _S)
import relfeat as RF  # noqa: E402

DEBUG = False
ERRORS = Counter()  # exceptions swallowed, by family

_SUPER = {'Position': 'Box', 'Offset': 'Box', 'Dir': 'Dir8', 'DiagDir': 'Dir8', 'Axis': 'Axis4', 'DiagAxis': 'Axis4',
          'Nat': 'Number', 'Int': 'Number', 'C4': 'D4'}
_NUM = frozenset(('Int', 'Nat', 'Number'))
_CMP = frozenset(('=', '!=', '<', '<=', '>', '>='))
_ENUM_ATOMS = frozenset(('axis_of', 'opposite', 'perp', 'diag_dirs'))
_TOK = re.compile(r'\(|\)|[^\s()]+')
_IDENT = re.compile(r'^\*?[A-Za-z_]\w*$')
_STAR = re.compile(r'\*([A-Za-z_]\w*)')
_AC = {}
_FITS = {}


def _nt(t):
    return str(t).split('(')[0]


def _sub(a, b):
    while a:
        if a == b:
            return True
        a = _SUPER.get(a)
    return False


def _fits(lt, ct):
    """A label of type lt can fill a column of type ct (lt None: any)."""
    if lt is None:
        return True
    k = (lt, ct)
    v = _FITS.get(k)
    if v is None:
        v = _FITS[k] = _sub(lt, ct)
    return v


def _loose(a, b):
    return a == b or _sub(a, b) or _sub(b, a)


def _compat(a, b):
    return a == b or (a in _NUM and b in _NUM)


def _match(lts, cols):
    """Size of a largest matching of labels to distinct columns (the label's type fits the column's type)."""
    if not lts or not cols:
        return 0
    adj = [[j for j, c in enumerate(cols) if _fits(lt, c)] for lt in lts]
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
    for i in range(len(lts)):
        if adj[i] and aug(i, set()):
            n += 1
    return n


class _Atom:
    __slots__ = ('rel', 'slot', 'neg', 'cls', 'occ', 'raw')


def _parse(s):
    """An atom string -> _Atom: relation token, its slot (before a dot), negated, class, and every identifier occurrence (name, innermost column)."""
    a = _AC.get(s)
    if a is not None:
        return a
    if len(_AC) > 60000:
        _AC.clear()
    a = _Atom()
    toks = _TOK.findall(s)
    rel, neg, depth, base, col = None, False, 0, 1, None
    raw = []
    prev = ''
    for t in toks:
        if t == '(':
            depth += 1
        elif t == ')':
            depth -= 1
        elif t[0] == ':':
            col = t[1:]
        elif t == 'NOT' and rel is None and depth == 1 and not neg and prev == '(':
            neg, base = True, 2
        elif rel is None and depth == base and prev == '(':
            rel = t
        elif _IDENT.match(t):
            raw.append((t.lstrip('*'), col))
        prev = t
    a.rel, a.neg, a.raw = rel or '', neg, raw
    a.slot = a.rel.partition('.')[0]
    if neg:
        a.cls = 'not'
    elif a.rel in _CMP:
        a.cls = 'cmp'
    elif a.rel == 'input':
        a.cls = 'input'
    elif a.rel.startswith('&'):
        a.cls = 'der'
    else:
        a.cls = 'lib'
    a.occ = None
    _AC[s] = a
    return a


class _G:
    pass


_cache = [None, None]


def _graph(row):
    if _cache[0] is row:
        return _cache[1]
    g = _build(row)
    _cache[0], _cache[1] = row, g
    return g


def _build(row):
    g = _G()
    pre = row.get('prefix') or []
    names = set()
    for s in pre:
        names.update(_STAR.findall(s))
    E = [_parse(s) for s in pre]
    g.E = E
    g.nE = len(E)
    g.opts = {o['tok']: o for o in row['options']}
    cnt = Counter()
    hold = {}
    alabs = []  # per atom: distinct labels in text order
    aocc = []   # per atom: [(name, col)] of labels
    for i, a in enumerate(E):
        occ = [(n, c) for n, c in a.raw if n in names]
        aocc.append(occ)
        seen = []
        for n, _ in occ:
            cnt[n] += 1
            if n not in seen:
                seen.append(n)
            hold.setdefault(n, set()).add(i)
        alabs.append(seen)
    g.cnt, g.hold, g.alabs, g.aocc = cnt, hold, alabs, aocc
    g.aunread = [[n for n in al if cnt[n] == 1] for al in alabs]
    g.front = [i for i, a in enumerate(E) if a.cls != 'cmp' and g.aunread[i]]
    g.scope_raw = set(row.get('scope') or [])
    g.scope = [_nt(t) for t in row.get('scope') or []]
    g.lt = _types(g, names)
    g._cm = None
    g._tw = None
    g._f1 = {}
    g._sig = {}
    g._cmpinfo = None
    g._kinds = None
    return g


def _types(g, names):
    """label -> type or None, from the atoms as a set.  A library column type bounds the label's type from above; a derived relation's types
    (the one at the label's place when the atom names all columns, else any of them) narrow it; the types in scope, with a type used up by a
    label that has no other choice, decide.  A label with more than one choice has type None (it fits any column)."""
    ub, soft = {}, {}
    for i, a in enumerate(g.E):
        if a.cls == 'cmp':
            continue
        o = g.opts.get(a.slot)
        if o is None or not o.get('types'):
            continue
        occ = g.aocc[i]
        if o.get('columns') and o['kind'] == 'lib':
            cm = dict(zip(o['columns'], o['types']))
            for n, c in occ:
                t = cm.get(c)
                if t:
                    ub.setdefault(n, set()).add(_nt(t))
        elif o['kind'] == 'derived':
            ts = [_nt(t) for t in o['types']]
            full = len(occ) == len(ts)
            for li, (n, _) in enumerate(occ):
                soft.setdefault(n, []).append((ts[li],) if full else tuple(ts))
    lt = {n: None for n in g.cnt}
    todo = [n for n in g.cnt if n in ub or n in soft]
    pool = Counter(g.scope)
    for _ in range(3):
        pset = {t for t, c in pool.items() if c > 0}
        res = {}
        for n in todo:
            if lt[n] is not None:
                continue
            u = ub.get(n)
            f = {p for p in pset if all(_sub(p, x) for x in u)} if u else set(pset)
            if not pset:
                f = set(u) if u else set()
            f2 = f
            for st in soft.get(n, ()):
                ex = {p for p in f if p in st} or {p for p in f if any(_loose(p, t) for t in st)}
                f2 = f2 & ex
            if not pset and not u:
                one = {st[0] for st in soft[n] if len(st) == 1}
                f2 = one if len(one) == 1 else set()
            if not f2:
                f2 = f
            if len(f2) > 1 and u:
                eq = f2 & u
                if len(eq) == 1:
                    f2 = eq
            if len(f2) == 1:
                res[n] = next(iter(f2))
        if not res:
            break
        for n, t in res.items():
            lt[n] = t
            if pool[t] > 0:
                pool[t] -= 1
    return lt


def _twins(g):
    """Pairs of labels held at the same column of the same relation in two different atoms (the relation is not input and not a comparison)."""
    r = g._tw
    if r is not None:
        return r
    sites = {}
    for i, a in enumerate(g.E):
        if a.cls in ('cmp', 'input'):
            continue
        for n, c in g.aocc[i]:
            sites.setdefault((a.slot, c), []).append((i, n))
    pairs = set()
    for lst in sites.values():
        for x in range(len(lst)):
            for y in range(x + 1, len(lst)):
                (i, a), (j, b) = lst[x], lst[y]
                if i != j and a != b:
                    pairs.add((a, b) if (a, b) <= (b, a) else (b, a))
    g._tw = r = sorted(pairs)
    return r


def _opt_class(o):
    tok = o['tok']
    if tok == 'NOT':
        return 'not'
    if tok in _CMP:
        return 'cmp'
    if tok == 'input':
        return 'input'
    return 'der' if o['kind'] == 'derived' else 'lib'


# ---- o1 ----

def _o1(g, row, o, d):
    nE = g.nE
    d['o1_n_earlier'] = float(nE)
    kind = o['kind']
    if nE == 0:
        d['o1_empty'] = 1.0
        d['o1_empty_' + kind] = 1.0
        if kind == 'derived' and (o.get('dag') or {}).get('method'):
            d['o1_empty_member'] = 1.0
        return
    ts = o.get('types')
    if ts:
        if not any(t in g.scope_raw for t in ts):
            d['o1_none_in_scope'] = 1.0
        if not any(_loose(u, _nt(t)) for u in g.scope for t in ts):
            d['o1_none_fit'] = 1.0


# ---- o2 ----

def _kinds(g):
    r = g._kinds
    if r is None:
        c = Counter(g.E[i].cls for i in g.front)
        rels = {g.E[i].slot for i in g.front if g.E[i].cls in ('lib', 'input')}
        enum = []
        for i in g.front:
            a = g.E[i]
            if a.cls == 'lib' and (a.rel.endswith('_elem') or a.rel in _ENUM_ATOMS):
                enum.extend(t for t in (g.lt.get(n) for n in g.aunread[i]) if t)
        total = Counter(a.cls for a in g.E)
        r = g._kinds = (c, rels, enum, total)
    return r


def _o2(g, row, o, d):
    if not g.E:
        return
    c, rels, enum, total = _kinds(g)
    cls = _opt_class(o)
    for k, n in c.items():
        d['o2_front_' + k] = float(min(n, 3))
        d['o2_x_%s_%s' % (cls, k)] = 1.0
    d['o2_front_n'] = float(min(len(g.front), 4))
    d['o2_own_n'] = float(min(total.get(cls, 0), 4))
    d['o2_own_front'] = float(min(c.get(cls, 0), 3))
    d['o2_own_same_front'] = float(c.get(cls, 0) > 0)
    tok = o['tok']
    if o['kind'] == 'lib' and tok in RF.INPUT_SLOTS:
        d['o2_follows_crop'] = float('inside' in rels and tok in RF.FOLLOWS_INSIDE)
        d['o2_follows_relative'] = float('relative' in rels and tok in RF.FOLLOWS_RELATIVE)
        d['o2_repeat'] = float(tok in rels and tok in RF.REPEATS)
        if enum:
            d['o2_fits_enum'] = float(any(_sub(m, _nt(t)) for m in enum for t in o.get('types') or []))


# ---- o3 ----

def _sigres(g, sig):
    """The type-dependent values for an option whose column types are `sig` (cached for the row)."""
    r = g._sig.get(sig)
    if r is not None:
        return r
    r = {}
    cols = list(sig)
    best = share = nhit = ntb = 0
    allm = False
    tbest = tshare = 0.0
    for i in g.front:
        u = [g.lt.get(n) for n in g.aunread[i]]
        m = _match(u, cols)
        if m:
            nhit += 1
            best = max(best, m)
            share = max(share, m / len(u))
            if m == len(u):
                allm = True
        t = [g.lt.get(n) for n in g.alabs[i]]
        mt = _match(t, cols)
        tbest = max(tbest, mt)
        tshare = max(tshare, mt / len(t))
    if g.front:
        r['o3_atom_cols'] = float(best)
        r['o3_atom_any'] = float(best > 0)
        r['o3_atom_share'] = share
        r['o3_atom_all'] = float(allm)
        r['o3_atoms_hit'] = float(nhit)
        r['o3_touch_cols'] = float(tbest)
        r['o3_touch_share'] = tshare
    # o5: twin pairs two columns can take
    tw = 0
    if len(cols) >= 2:
        for a, b in _twins(g):
            if g.cnt[a] > 2 or g.cnt[b] > 2:
                continue
            ta, tb = g.lt.get(a), g.lt.get(b)
            ai = [i for i, c in enumerate(cols) if _fits(ta, c)]
            bj = [j for j, c in enumerate(cols) if _fits(tb, c)]
            if any(i != j for i in ai for j in bj):
                tw += 1
        if tw:
            r['o5_take_twin'] = float(min(tw, 3))
    g._sig[sig] = r
    return r


# ---- o4 ----

def _cmpinfo(g):
    r = g._cmpinfo
    if r is not None:
        return r
    semi = [n for n in g.cnt if g.cnt[n] <= 2 and g.lt.get(n)]
    npairs = cross = cross_num = cross_un = same = 0
    for x in range(len(semi)):
        a = semi[x]
        for y in range(x + 1, len(semi)):
            b = semi[y]
            if not _compat(g.lt[a], g.lt[b]):
                continue
            npairs += 1
            if g.hold[a] & g.hold[b]:
                if g.cnt[a] == 1 and g.cnt[b] == 1:
                    same += 1
            else:
                cross += 1
                cross_num += g.lt[a] in _NUM
                cross_un += g.cnt[a] == 1 and g.cnt[b] == 1
    ntw = sum(1 for a, b in _twins(g) if g.cnt[a] <= 2 and g.cnt[b] <= 2)
    anum = aun = 0
    for i, un in enumerate(g.aunread):
        if g.E[i].cls == 'cmp':
            continue
        aun = max(aun, len(un))
        anum = max(anum, sum(1 for n in un if g.lt.get(n) in _NUM))
    r = g._cmpinfo = (npairs, cross, cross_num, cross_un, same, ntw, anum, aun)
    return r


def _o4(g, row, o, d):
    if o['tok'] not in _CMP or not g.E:
        return
    npairs, cross, cross_num, cross_un, same, ntw, anum, aun = _cmpinfo(g)
    d['o4_cmp_cross'] = float(min(cross, 3))
    d['o4_cmp_cross_num'] = float(min(cross_num, 3))
    d['o4_cmp_cross_unread'] = float(min(cross_un, 3))
    d['o4_cmp_same_atom'] = float(min(same, 3))
    d['o4_cmp_twin'] = float(min(ntw, 3))
    d['o4_cmp_stale'] = float(npairs > 0 and cross_un == 0 and same == 0)
    d['o4_cmp_nopair'] = float(npairs == 0 and ntw == 0)
    d['o4_cmp_atom_num'] = float(min(anum, 2))
    d['o4_cmp_atom_unread'] = float(min(aun, 3))
    d['o4_cmp_atom_num2'] = float(anum >= 2)


# ---- o6 ----

def _f1(g, tok):
    r = g._f1.get(tok, 0)
    if r != 0:
        return r
    apps = [i for i, a in enumerate(g.E) if a.cls != 'cmp' and a.slot == tok]
    r = None
    if apps:
        held = set()
        for i in apps:
            held.update(g.alabs[i])
        joined = {n for n in held if g.cnt[n] >= 2}
        bdang = any(g.cnt[n] == 1 for n in held)
        rtypes = {g.lt[n] for n in joined if g.lt.get(n)}
        tw = set()
        if joined:
            for a, b in _twins(g):
                if a in joined:
                    tw.add(b)
                if b in joined:
                    tw.add(a)
        pend = pend_tw = pend_both = 0
        for n in g.cnt:
            if g.cnt[n] != 1 or n in held:
                continue
            t = n in tw
            y = g.lt.get(n) in rtypes if g.lt.get(n) else False
            pend += t or y
            pend_tw += t
            pend_both += t and y
        r = (len(apps), bool(joined), bdang, pend, pend_tw, pend_both)
    g._f1[tok] = r
    return r


def _o6(g, row, o, d):
    if o['kind'] == 'op' or not g.E:
        return
    r = _f1(g, o['tok'])
    if r is None:
        return
    napps, joined, bdang, pend, pend_tw, pend_both = r
    d['o6_joined'] = float(joined)
    d['o6_pend_n'] = float(pend)
    d['o6_pend_twin_n'] = float(pend_tw)
    d['o6_pend_both_n'] = float(pend_both)
    d['o6_pend_bdang'] = float(pend > 0 and bdang)
    d['o6_pend_both_bdang'] = float(pend_both > 0 and bdang)
    d['o6_once_joined_bdang'] = float(napps == 1 and joined and bdang)
    d['o6_gen_bdang'] = float((not joined) and bdang)


def rk3o(row, o):
    try:
        g = _graph(row)
    except Exception:
        if DEBUG:
            raise
        ERRORS['graph'] += 1
        return {}
    d = {}
    for f in (_o1, _o2, _o4, _o6):
        try:
            f(g, row, o, d)
        except Exception:
            if DEBUG:
                raise
            ERRORS[f.__name__] += 1
    ts = o.get('types')
    if ts and o['kind'] != 'op' and g.E:
        try:
            d.update(_sigres(g, tuple(_nt(t) for t in ts)))
        except Exception:
            if DEBUG:
                raise
            ERRORS['sig'] += 1
    return d


FEATURE_FUNCS = {'rk3o': rk3o}
