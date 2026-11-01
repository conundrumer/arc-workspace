"""Explorer f: symmetric repetition in the clause, typed column classes, row-relative scale, atom-class runs, relation identity.

The row's prefix is read as atoms that bind labels (`*X`) and read them (`X`).  Label types are rebuilt from `scope` and the
options' column types.  Names of labels are compared only for equality within the row.  Fields read: k, scope, prefix, and per
option tok, kind, columns, types, p, dag.depth.

F1  Parallel application.  A relation the prefix applied once, reading labels, tends to be applied again to a still unread
    label of the same type as a label it read: f1_*.
F2  Twin labels.  Two unread labels of one type, bound by two atoms of one relation in one column (or by two different atoms),
    are taken together by one atom with two columns of that type, or compared with `!=`: f2_*.
F3  Column classes.  Counts of grid, color, ident, enumerable-constant and numeric columns, and how many of them no label
    in scope can fill: f3_*.
F4  Scale inside the row: percentile of depth and arity, rank and share of p within the option's kind: f4_*.
F5  Atom classes.  The class (input, lib, derived, comparison, NOT) of the last atom and the run of the option's class
    at the end of the prefix: f5_*.
F6  Identity of a library relation or a comparison, to rescale the sampler's share per relation: f6_*.
"""
import bisect
import functools
import re

_SUPER = {'Position': 'Box', 'Offset': 'Box', 'Dir': 'Dir8', 'DiagDir': 'Dir8', 'Axis': 'Axis4', 'DiagAxis': 'Axis4',
          'Nat': 'Number', 'Int': 'Number', 'C4': 'D4'}

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



ENUM = frozenset({'Dir', 'Axis', 'DiagDir', 'DiagAxis', 'D4', 'C4', 'Sym', 'Sense', 'Dir8', 'Axis4'})
GRID = frozenset({'Box', 'Position', 'Offset'})
NUM = frozenset({'Number', 'Int', 'Nat'})
CMP = {'=': 'eq', '!=': 'ne', '<': 'lt', '<=': 'le', '>': 'gt', '>=': 'ge'}
LIBS = ('input', 'relative', 'axis_of', 'inside', 'margin', 'split', 'neighbor', 'compose', 'opposite', 'perp', 'dir_elem',
        'axis_elem', 'box_extent', 'diag_dirs', 'same_line', 'same_corner', 'divide', 'apply', 'dist_pair', 'corner_dir',
        'nearer', 'perp_dir', 'axis_inset', 'turn', 'interior', 'dir8_opposite', 'centered', 'diag_opposite', 'diag_dist',
        'diag_dir_elem', 'axis4_of', 'dir8_elem', 'axis_inversion', 'corner_dist', 'd4_elem', 'sub_extent', 'jump',
        'frame_extent', 'jump_offset', 'c4_elem', 'same_dist', 'uniform_outset', 'uniform_inset')
LIBSET = frozenset(LIBS)

_cache = [None, None]
_by_types_of = {}  # the values of a row that _by_types reads -> {column types -> _by_types' answer}
_BY_TYPES_CAP = 256  # rows' values kept; the store is emptied past it


def _atom_class(a):
    """(class, negated) of a prefix atom: class in in, lib, der, cmp."""
    neg = a.startswith('(NOT')
    m = REL.match(a)
    s = m.group(1) if m else ''
    if s.startswith('&'):
        return 'der', neg, s.partition('.')[0]
    if s in CMP:
        return 'cmp', neg, s
    if s == 'input':
        return 'in', neg, s
    return 'lib', neg, s.partition('.')[0]


def _pct(vals, v):
    if not vals:
        return 0.0
    return (sum(1 for x in vals if x < v) + 0.5 * sum(1 for x in vals if x == v)) / len(vals)


def _info(row):
    if _cache[0] is row:
        return _cache[1]
    labs = _labels(row)
    L = {l[0]: l for l in labs}
    prefix = row.get('prefix') or []
    atoms = {}
    classes = []
    sites = {}
    for j, a in enumerate(prefix):
        cl, neg, slot = _atom_class(a)
        classes.append((cl, neg))
        if cl == 'cmp':
            continue
        leaves = LEAF.findall(a)
        for col, _, nm in leaves:
            sites.setdefault(nm, []).append((slot, col, j))
        names = {nm for _, _, nm in leaves}
        atoms.setdefault(slot, []).append((j, {x for x in names if x in L and L[x][3] > 0}, {x for x in names if x in L and L[x][3] == 0}))
    bound_by = {n: s[0] for n, s in sites.items() if len(s) == 1}  # the one site of a label of one site
    dang = [l for l in labs if l[3] == 0]
    opts = row['options']
    by_tok = {o['tok']: o for o in opts}
    scope = [_nt(t) for t in row.get('scope') or []] or [l[1] for l in labs if l[1] is not None]
    pool = [l[1] for l in labs if l[1] is not None] or scope
    scount = {}
    for t in scope:
        scount[t] = scount.get(t, 0) + 1

    def cands(a, b):
        """Types a pair of labels bound by one relation column may have."""
        slot, col, _ = bound_by[a[0]]
        o = by_tok.get(slot)
        if o is None or not o.get('types'):
            return frozenset()
        if o['kind'] == 'lib' and o.get('columns') and col in o['columns']:
            return frozenset([_nt(o['types'][o['columns'].index(col)])])
        return frozenset(t for t in {_nt(x) for x in o['types']} if scount.get(t, 0) >= 2)
    twin, cross, same = [], {}, {}
    twin_of = {}
    for x in range(len(labs)):
        for y in range(x + 1, len(labs)):
            ba, bb = bound_by.get(labs[x][0]), bound_by.get(labs[y][0])
            if ba is not None and bb is not None and ba[2] != bb[2] and ba[:2] == bb[:2]:
                twin_of.setdefault(labs[x][0], set()).add(labs[y][0])
                twin_of.setdefault(labs[y][0], set()).add(labs[x][0])
    for x in range(len(dang)):
        for y in range(x + 1, len(dang)):
            a, b = dang[x], dang[y]
            ba, bb = bound_by.get(a[0]), bound_by.get(b[0])
            if ba is None or bb is None:
                continue
            if ba[2] != bb[2] and ba[:2] == bb[:2]:
                twin.append(cands(a, b))
            elif a[1] is not None and a[1] == b[1]:
                if ba[2] == bb[2]:
                    same[a[1]] = same.get(a[1], 0) + 1
                else:
                    cross[a[1]] = cross.get(a[1], 0) + 1
    bykind = {}
    for o in opts:
        bykind.setdefault(o['kind'], []).append(o)
    ps = {k: sorted((o['p'] for o in v), reverse=True) for k, v in bykind.items()}
    neg_ps = {k: [-p for p in v] for k, v in ps.items()}
    sum_ps = {k: sum(v) for k, v in ps.items()}
    depths = sorted(o['dag']['depth'] for o in bykind.get('derived', []) if o.get('dag') and o['dag'].get('depth') is not None)
    arity = {k: [len(o.get('types') or []) for o in v] for k, v in bykind.items()}
    last = classes[-1] if classes else None
    demand = {}
    for x in opts:
        if x['kind'] == 'op' or not x.get('types'):
            continue
        xt = [_nt(t) for t in x['types']]
        fd = [any(_sub(s, t) or _sub(t, s) for s in pool) for t in xt]
        if any(fd):
            for t, f in zip(xt, fd):
                if not f and t in ENUM:
                    demand[t] = demand.get(t, 0) + 1
    run = {}
    for cls in ('in', 'lib', 'der', 'cmp', 'neg'):
        n = 0
        for c, neg in reversed(classes):
            if (('neg' if neg else c) == cls):
                n += 1
            else:
                break
        run[cls] = n
    # _by_types reads these and the column types: rows with the same values share the answers
    sig = (tuple(twin), tuple(cross), tuple(same), tuple(pool), tuple(demand.items()))
    if len(_by_types_of) >= _BY_TYPES_CAP:
        _by_types_of.clear()
    info = dict(labs=labs, L=L, atoms=atoms, dang=dang, twin=twin, cross=cross, same=same, ps=ps, neg_ps=neg_ps, sum_ps=sum_ps, by_types=_by_types_of.setdefault(sig, {}), pct={}, depths=depths, arity=arity,
                scope=scope, pool=pool, demand=demand, last=last, run=run, nneg=sum(1 for c, n in classes if n), ncmp=sum(1 for c, n in classes if c == 'cmp'),
                twin_n=len(twin), twin_of=twin_of, cross_n=sum(cross.values()), same_n=sum(same.values()))
    _cache[0], _cache[1] = row, info
    return info


def _two(T, cols):
    return sum(1 for c in cols if _fits(T, c)) >= 2


def _class_of(o):
    if o['kind'] == 'derived':
        return 'der'
    if o['kind'] == 'lib':
        return 'in' if o['tok'] == 'input' else 'lib'
    return 'neg' if o['tok'] == 'NOT' else 'cmp'


def _by_types(types, info):
    """What the option's column types and the row give, which options with one column list share: (the keys of F2, the keys of F3)."""
    two = {'f2_twin_cons': float(sum(1 for cs in info['twin'] if any(_two(T, types) for T in cs))),
           'f2_cross_cons': float(sum(1 for T in info['cross'] if _two(T, types))),
           'f2_same_cons': float(sum(1 for T in info['same'] if _two(T, types)))}
    d = {}
    pool = info['pool']
    cnt = dict(grid=0, color=0, ident=0, enum=0, num=0, other=0)
    unf = dict(grid=0, color=0, ident=0, enum=0, num=0, other=0)
    for t in types:
        c = ('grid' if t in GRID else 'color' if t == 'Color' else 'ident' if t == 'Ident' else 'enum' if t in ENUM
             else 'num' if t in NUM else 'other')
        cnt[c] += 1
        if not any(_sub(s, t) or _sub(t, s) for s in pool):
            unf[c] += 1
    for c in cnt:
        d['f3_n_' + c] = float(cnt[c])
        d['f3_u_' + c] = float(unf[c])
    d['f3_all_enum'] = float(cnt['enum'] == len(types))
    for c in ('color', 'grid', 'num', 'ident'):
        d['f3_all_' + c] = float(cnt[c] == len(types))
    dm = sum(info['demand'].get(t, 0) for t in set(types) if t in ENUM and not any(_sub(s, t) or _sub(t, s) for s in pool))
    d['f3_enum_demand'] = float(dm)
    d['f3_enum_demand_all'] = float(dm if cnt['enum'] == len(types) and unf['enum'] == len(types) else 0)
    d['f3_u_data'] = float(unf['grid'] + unf['color'] + unf['ident'])
    d['f3_u_all'] = float(sum(unf.values()))
    return two, d


def _row_pct(info, name, vals, v):
    """_pct(vals, v), once per name and v in a row."""
    key = name, v
    got = info['pct'].get(key)
    if got is None:
        got = info['pct'][key] = _pct(vals, v)
    return got


def fn(row, o):
    """F1 parallel application, F2 twin labels, F3 column classes, F4 scale in the row, F5 atom-class runs, F6 identity."""
    info = _info(row)
    kind, tok = o['kind'], o['tok']
    d = {}
    # F1: an applied relation and the unread labels it has not taken
    apps = info['atoms'].get(tok) if kind != 'op' else None
    d['f1_napps'] = float(len(apps)) if apps else 0.0
    if apps:
        L = info['L']
        rd = set().union(*[a[1] for a in apps])
        bd = set().union(*[a[2] for a in apps])
        cons = bool(rd)
        bdang = any(b in L and L[b][3] == 0 for b in bd)
        rtypes = {L[x][1] for x in rd if x in L and L[x][1] is not None}
        mine = rd | bd
        tw = set().union(*[info['twin_of'].get(x, set()) for x in rd])
        pend = sum(1 for l in info['dang'] if l[0] not in mine and (l[1] in rtypes or l[0] in tw))
        pend_tw = sum(1 for l in info['dang'] if l[0] not in mine and l[0] in tw)
        pend_both = sum(1 for l in info['dang'] if l[0] not in mine and l[0] in tw and l[1] in rtypes)
        d['f1_cons'] = float(cons)
        d['f1_bdang'] = float(bdang)
        d['f1_pend_n'] = float(pend)
        d['f1_pend_twin_n'] = float(pend_tw)
        d['f1_pend_both_n'] = float(pend_both)
        d['f1_pend_bdang'] = float(pend > 0 and bdang)
        d['f1_pend_both_bdang'] = float(pend_both > 0 and bdang)
        d['f1_once_cons_bdang'] = float(len(apps) == 1 and cons and bdang)
        d['f1_gen_bdang'] = float((not cons) and bdang)
    # F2: twin labels
    types = [_nt(t) for t in o.get('types') or []]
    by_types = None
    if types:
        by_types = info['by_types'].get(tuple(types)) or info['by_types'].setdefault(tuple(types), _by_types(types, info))
    if kind == 'op':
        if tok in CMP:
            nm = CMP[tok]
            grp = 'ne' if tok == '!=' else 'ord'
            d['f2_%s_twin' % grp] = float(info['twin_n'])
            d['f2_%s_cross' % grp] = float(info['cross_n'])
            d['f2_%s_same' % grp] = float(info['same_n'])
    elif types:
        d.update(by_types[0])
    # F3: column classes
    if types:
        d.update(by_types[1])
    # F4: scale inside the row (every kind of the row has its ps)
    ps, total = info['ps'][kind], info['sum_ps'][kind]
    d['f4_p_rank_kind'] = float(bisect.bisect_left(info['neg_ps'][kind], -o['p'])) / len(ps)
    d['f4_p_rel_kind'] = o['p'] / ps[0] if ps[0] > 0 else 0.0
    d['f4_p_share_kind'] = o['p'] / total if total > 0 else 0.0
    d['f4_kind_mass'] = float(total)
    ar = info['arity'].get(kind)
    if ar and types:
        d['f4_arity_pct'] = _row_pct(info, kind, ar, len(types))
    dag = o.get('dag') or {}
    if kind == 'derived' and dag.get('depth') is not None and info['depths']:
        dep = dag['depth']
        d['f4_depth_pct'] = _row_pct(info, 'depth', info['depths'], dep)
        d['f4_depth_rel'] = dep / info['depths'][-1] if info['depths'][-1] else 0.0
    else:
        d['f4_depth_pct'] = -1.0
        d['f4_depth_rel'] = -1.0
    # F5: atom classes
    cls = _class_of(o)
    last = info['last']
    if last is None:
        d['f5_last_none'] = 1.0
    else:
        lc = 'neg' if last[1] else last[0]
        d['f5_last_' + lc] = 1.0
        d['f5_same_as_last'] = float(lc == cls)
    d['f5_run'] = float(info['run'][cls])
    d['f5_n_neg'] = float(info['nneg'])
    d['f5_n_cmp'] = float(info['ncmp'])
    # F6: identity
    if kind == 'lib' and tok in LIBSET:
        d['f6_id_' + tok] = 1.0
    elif kind == 'op' and tok in CMP:
        d['f6_op_' + CMP[tok]] = 1.0
    elif kind == 'op':
        d['f6_op_not'] = 1.0
    return d


FEATURE_FUNCS = {'rk2f': fn}
