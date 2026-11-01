"""ch4o and ch4s: the choice steer's facts of the atoms as a set, on a row with no marks (dagset.view).  ch4o(row, option) -> {o<n>_<what>: float}.

Definitions:
- E is the atoms of the prefix (at a stop row, all of them) and A is the atom in progress (at a stop row, none).
- A label's sites are its occurrences in E. Its reads are its sites less one. It is unread at one site.
- The join graph has an edge between two labels when an atom of E holds both.
- `dmin` of a label is its distance in the join graph to the nearest unread label, or its eccentricity plus 1 where its component has none. `dmax` is its eccentricity in its component.
  A label held only by A has 0 for both.

Label names are compared for equality only.  Where several labels have equal features they tie.

o1  Atom place: size of E, E non-empty, A reads no label yet, A shares no label with E; at a stop row, the atoms whose labels each have one holder.
o2  Same relation: the atoms of E with A's relation, as a set.  Counts of those that name more columns than A has, that name the option's
    column, that hold a label of the option's type, and, for a value, that hold the same or another label at the same place.
o3  Label order: reader count, unread, dmin and dmax, and the number of option labels (all, unread, of the same type) that are
    farther from or nearer to an unread label.
o4  Label holders: the relation and column of the sites of the atoms that hold the label, crossed with the column being filled; the kind, column count and private
    label count of the holder atoms; labels made in this atom and not read in it.
o5  Column choice: the column's type against the unread labels and the labels in scope, and against the other unnamed columns, with labels
    split by whether a holder atom is linked to A or holds an unread label.
o6  Columns named so far, as a set of types: the type of a named column against the option's type, and at STOP.
o7  e7_kind_frac2: among the atoms of A's relation in E that fill the column, the share whose site has the option's kind.
ch4s  The stop row's facts of the atoms as a set, on the STOP option.
"""
import os
import re
import sys
from collections import Counter

_S = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _S not in sys.path:
    sys.path.insert(0, _S)
import choicefeat as cf  # noqa: E402

DEBUG = False
ERRORS = Counter()  # exceptions swallowed, by family

_TOK = re.compile(r'\(|\)|[^\s()]+')
_LABV = re.compile(r'^(\*?)(V\d+)$')
_LABL = re.compile(r'^(\*?)L(\d+)$')
_AC = {}


class _Atom:
    __slots__ = ('rel', 'neg', 'cols', 'occ', 'labs', 'reads', 'nstar', 'open_col', 'nzero')


def _lab_v(t):
    m = _LABV.match(t)
    return (bool(m.group(1)), m.group(2)) if m else None


def _parse(s, lab):
    """An atom string (balanced or cut off) -> _Atom: relation token, columns [name, [(star, label)], zeros], every label occurrence."""
    a = _Atom()
    toks = _TOK.findall(s)
    n = len(toks)
    rel, neg, base, depth, cur, cdepth = None, False, 1, 0, None, 0
    cols, occ, nzero = [], [], 0
    for i, t in enumerate(toks):
        if t == '(':
            depth += 1
            if i + 1 < n and toks[i + 1][:1] == ':' and depth == base + 1 and cur is None:
                cur = [toks[i + 1][1:], [], 0]
                cols.append(cur)
                cdepth = depth
            continue
        if t == ')':
            if cur is not None and depth == cdepth:
                cur = None
            depth -= 1
            continue
        if t[:1] == ':':
            continue
        if t == 'NOT' and rel is None and depth == 1 and not neg:
            neg, base = True, 2
            continue
        if rel is None and depth == base:
            rel = t
            continue
        if t == '0':
            nzero += 1
            if cur is not None:
                cur[2] += 1
            continue
        x = lab(t)
        if x:
            occ.append(x)
            if cur is not None:
                cur[1].append(x)
    a.rel, a.neg, a.cols, a.occ, a.nzero = rel, neg, cols, occ, nzero
    a.labs = frozenset(l for _, l in occ)
    reads = {}
    for st, l in occ:
        if not st:
            reads[l] = reads.get(l, 0) + 1
    a.reads = reads
    a.nstar = sum(1 for st, _ in occ if st)
    a.open_col = cur is not None
    return a


def _parse_v(s):
    a = _AC.get(s)
    if a is None:
        if len(_AC) > 60000:
            _AC.clear()
        a = _AC[s] = _parse(s, _lab_v)
    return a


_EMPTY = _parse('', _lab_v)


def _origin_kind(rel):
    r = rel or ''
    if r.startswith('&'):
        return 'derived'
    if r.endswith('_elem'):
        return 'elem'
    if r in ('input', 'ex_input', 'ex_output'):
        return 'base'
    return 'lib'


def _role(a, colname):
    return 'DER' if (a.rel or '').startswith('&') else '%s.%s' % (a.rel, colname)


class _Lab:
    __slots__ = ('name', 'reads', 'unread', 'in_a', 'dmin', 'dmax', 'type', 'held')


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
    ph = row['phase']
    pre = row.get('prefix') or []
    g.ph = ph
    stop = ph == 'stop'
    created = g.created = cf.context(row)['created']
    if stop:
        g.E = [_parse_v(a) for a in pre]
        g.A = _EMPTY
    else:
        def lab(t):
            m = _LABL.match(t)
            if not m:
                return None
            i = int(m.group(2))
            return (bool(m.group(1)), created[i] if i < len(created) else 'L%d' % i)
        g.E = [_parse_v(a) for a in pre]
        g.A = _parse(row.get('text') or '', lab)
    E, A = g.E, g.A
    g.nE = len(E)
    g.stype = dict(zip(row.get('scope_labels') or [], row.get('scope_types') or []))
    g.rt = row.get('rtypes') or []
    g.sig = row.get('rkind') == 'lib relation'
    holders, sites = {}, {}
    for i, a in enumerate(E):
        for _, l in a.occ:
            holders.setdefault(l, set()).add(i)
            sites[l] = sites.get(l, 0) + 1
    g.holders, g.sites = holders, sites
    reads = g.reads = {l: n - 1 for l, n in sites.items()}
    new_a = {l for _, l in A.occ if l not in holders}  # the labels of A that E doesn't hold
    g.A_nfresh = len(new_a)
    g.A_nread = len(A.occ) - len(new_a)
    # types of labels made in A (a library relation's column type; a derived relation's column position is not read)
    atype = {}
    if g.sig:
        for name, leaves, _ in A.cols:
            if name.isdigit() and int(name) < len(g.rt):
                for st, l in leaves:
                    if l not in holders:
                        atype[l] = g.rt[int(name)]
    g.atype = atype
    A_labs = A.labs
    if stop:
        U = {l for l, n in sites.items() if n == 1}
    else:
        U = {l for l in (set(holders) | set(g.stype)) if reads.get(l, 0) == 0 and l not in A_labs}
    g.U = U
    g.T = {i for i, a in enumerate(E) if a.labs & A_labs}
    g.F = {i for l in U for i in holders.get(l, ())}
    g.sty = list(g.stype.values()) + list(atype.values())
    g._dist = _distances(g)
    g._lab = {}
    rel = A.rel
    g.S = [a for a in E if rel is not None and a.rel == rel]
    g.nA = len(A.cols) - (1 if ph in ('val', 'fval') and A.cols and A.open_col else 0)
    g._place = None
    return g


def _distances(g):
    """{label: (dmin, dmax)} of the labels of E."""
    adj = {l: set() for l in g.holders}
    for a in g.E:
        for x in a.labs:
            adj[x] |= a.labs - {x}
    out = {}
    for l in adj:
        seen, layer, d, near = {l}, {l}, 0, None
        while layer:
            if near is None and layer & g.U:
                near = d
            layer = {y for x in layer for y in adj[x]} - seen
            seen |= layer
            d += 1
        out[l] = (d if near is None else near, d - 1)
    return out


def _attr(g, l):
    a = g._lab.get(l)
    if a is not None:
        return a
    a = _Lab()
    a.name = l
    a.reads = g.reads.get(l, 0)
    a.in_a = l in g.A.labs
    a.unread = l in g.U
    a.type = g.stype.get(l) or g.atype.get(l)
    a.held = g.holders.get(l, frozenset())
    if l in g._dist:
        a.dmin, a.dmax = g._dist[l]
    elif a.in_a:
        a.dmin = a.dmax = 0
    else:
        a.dmin = a.dmax = None
    g._lab[l] = a
    return a


def _lab_of(g, tok):
    try:
        i = int(tok[1:])
    except ValueError:
        return None
    return g.created[i] if i < len(g.created) else 'L%d' % i


def _opts(g, row):
    r = getattr(g, '_ol', None)
    if r is None:
        r = g._ol = [_attr(g, _lab_of(g, o['tok'])) for o in row['options'] if o['kind'] == 'label']
    return r


def _n_scope(g, t):
    return sum(cf.compat(t, x) for x in g.sty)


def _open_cols(g, row):
    r = getattr(g, '_open', None)
    if r is None:
        r = g._open = [(o['tok'], o.get('ctype')) for o in row['options'] if o['kind'] == 'column']
    return r


def _fit(t, types):
    return sum(1 for u in types if cf.compat(t, u))


def _utypes(g):
    r = getattr(g, '_ut', None)
    if r is None:
        r = g._ut = [t for t in (_attr(g, l).type for l in g.U) if t]
    return r


# ---- o1 ----

def _o1(g, row, o, d):
    ph, nE = g.ph, g.nE
    d['o1_n_earlier'] = float(nE)
    d['o1_has_earlier'] = float(nE > 0)
    if ph == 'stop':
        d['o1_isolated_n'] = float(sum(1 for a in g.E if a.labs and all(len(g.holders[l]) == 1 for l in a.labs)))
        return
    noread = nE > 0 and g.A_nread == 0
    d['o1_noread'] = float(noread)
    if ph == 'cols':
        opens = _open_cols(g, row)
        if o['kind'] == 'stop':
            d['o1_stop_noread'] = float(noread)
            if noread:
                d['o1_stop_joinable_left'] = float(sum(1 for _, t in opens if t and _n_scope(g, t) > 0))
            if row.get('rel') == 'declared' and nE > 0 and g.A.cols:
                d['o1_stop_left_n'] = float(len(opens))
                d['o1_stop_left_in'] = float(sum(1 for _, t in opens if t and _n_scope(g, t) > 0))
        elif o['kind'] == 'column':
            t = o.get('ctype')
            d['o1_col_join_candidate'] = float(noread and bool(t) and _n_scope(g, t) > 0)
    elif ph == 'val':
        arity = len(g.rt)
        if arity and g.A.cols:
            left = arity - len(g.A.cols)
            d['o5_left_after_fill'] = float(max(left, 0))
            d['o1_last_col_nojoin'] = float(noread and left <= 0)


# ---- o2 ----

def _place(g, row):
    """Per atom of the same relation: (leaves at the place, zeros at the place).  A library column is the place by name; otherwise the
    place is the leaves whose label type fits the column type."""
    r = g._place
    if r is not None:
        return r
    col, ct = row.get('col'), row.get('ctype')
    out = []
    for s in g.S:
        if row['phase'] == 'val' and col and g.sig:
            pl, z = [], 0
            for c in s.cols:
                if c[0] == col:
                    pl.extend(c[1])
                    z += c[2]
        else:
            pl = [x for x in s.occ if ct is None or cf.compat(ct, _attr(g, x[1]).type)]
            z = s.nzero
        out.append((pl, z))
    g._place = out
    return out


def _o2(g, row, o, d):
    ph = g.ph
    if ph not in ('cols', 'val', 'fval') or g.A.rel is None:
        return
    S = g.S
    ns = len(S)
    d['o2_n_same'] = float(ns)
    if not ns:
        return
    d['o2_has_same'] = 1.0
    d['o2_s_pairs_share'] = float(sum(1 for i in range(ns) for j in range(i + 1, ns) if S[i].labs & S[j].labs))
    d['o2_a_shares_s'] = float(sum(1 for s in S if s.labs & g.A.labs))
    kind = o['kind']
    if ph == 'cols':
        m = g.nA
        if kind == 'stop':
            at = sum(1 for s in S if len(s.cols) == m)
            more = sum(1 for s in S if len(s.cols) > m)
            d['o2_stop_at_n'] = float(at)
            d['o2_stop_at_frac'] = at / ns
            d['o2_stop_more_n'] = float(more)
        elif kind == 'column':
            more = sum(1 for s in S if len(s.cols) > m)
            d['o2_col_more_n'] = float(more)
            d['o2_col_more_frac'] = more / ns
            d['o2_col_beyond_n'] = float(ns - more)
            nm, t = o.get('name'), o.get('ctype')
            if nm:
                n = sum(1 for s in S if any(c[0] == nm for c in s.cols))
                d['o2_name_in_n'] = float(n)
                d['o2_name_in_frac'] = n / ns
            if t:
                echo = clash = 0
                for s in S:
                    ls = [l for c in s.cols if (not nm or not g.sig or c[0] == nm) for _, l in c[1]] if s.cols else [l for _, l in s.occ]
                    tt = [x for x in (_attr(g, l).type for l in ls) if x]
                    if tt:
                        if any(cf.compat(x, t) for x in tt):
                            echo += 1
                        else:
                            clash += 1
                d['o2_type_echo_n'] = float(echo)
                d['o2_type_clash_n'] = float(clash)
        return
    pl = _place(g, row)
    if kind == 'fresh':
        d['o2_fresh_s_fresh_n'] = float(sum(1 for p, _ in pl if any(g.sites[x] == 1 for _, x in p)))
        d['o2_fresh_s_read_n'] = float(sum(1 for p, _ in pl if any(g.sites[x] > 1 for _, x in p)))
    elif kind == 'zero':
        d['o2_zero_s_zero_n'] = float(sum(1 for _, z in pl if z))
        d['o2_zero_s_label_n'] = float(sum(1 for p, _ in pl if p))
    elif kind == 'label':
        l = _lab_of(g, o['tok'])
        a = _attr(g, l)
        sf = sr = of = orr = shift = dt = deeper = 0
        for s, (p, _) in zip(S, pl):
            has = False
            for st, x in p:
                if x == l:
                    has = True
                    if g.sites[x] == 1:
                        sf += 1
                    else:
                        sr += 1
                    break
            if has:
                continue
            if p:
                if any(g.sites[y] == 1 for _, y in p):
                    of += 1
                else:
                    orr += 1
                comp = [_attr(g, xl) for _, xl in p if a.type and _attr(g, xl).type and cf.compat(_attr(g, xl).type, a.type)]
                if comp:
                    dt += 1
                    if a.dmax is not None and any(xa.dmax is not None and xa.dmax < a.dmax for xa in comp):
                        deeper += 1
            if l in s.labs:
                shift += 1
        d['o2_lab_same_s_fresh_n'] = float(sf)
        d['o2_lab_same_s_read_n'] = float(sr)
        d['o2_lab_same_frac'] = (sf + sr) / ns
        d['o2_lab_other_s_fresh_n'] = float(of)
        d['o2_lab_other_s_read_n'] = float(orr)
        d['o2_lab_shift_n'] = float(shift)
        d['o2_lab_other_same_type_n'] = float(dt)
        d['o2_lab_deeper_same_type_n'] = float(deeper)


# ---- o3 ----

def _rel_count(vals, v):
    return sum(1 for x in vals if x > v), sum(1 for x in vals if x < v)


def _o3(g, row, o, d):
    if g.ph not in ('val', 'fval', 'op') or o['kind'] != 'label':
        return
    l = _lab_of(g, o['tok'])
    a = _attr(g, l)
    OL = _opts(g, row)
    d['o3_readers'] = float(a.reads)
    d['o3_unread'] = float(a.unread)
    d['o3_made_here'] = float(l not in g.holders)
    nur = [x for x in OL if x.unread]
    d['o3_n_unread_linked'] = float(sum(1 for x in nur if x.held & g.T))
    ref = row.get('ctype') or a.type
    same = [x for x in OL if ref and x.type and cf.compat(ref, x.type)]
    if a.reads is not None:
        fewer = sum(1 for x in OL if x.reads < a.reads)
        d['o3_readers_fewer_n'] = float(fewer)
        d['o3_readers_more_n'] = float(sum(1 for x in OL if x.reads > a.reads))
    if a.dmax is None:
        return
    d['o3_dmin'] = float(a.dmin)
    d['o3_dmax'] = float(a.dmax)
    dm = [x for x in OL if x.dmax is not None]
    if dm:
        d['o3_dmax_gap_top'] = float(max(x.dmax for x in dm) - a.dmax)
        d['o3_dmax_gap_bot'] = float(a.dmax - min(x.dmax for x in dm))
        d['o3_dmin_gap_top'] = float(max(x.dmin for x in dm) - a.dmin)
        d['o3_dmin_gap_bot'] = float(a.dmin - min(x.dmin for x in dm))
        d['o3_is_deepest'] = float(a.dmax >= max(x.dmax for x in dm))

    def rank(pref, xs):
        xs = [x for x in xs if x.dmax is not None]
        up = sum(1 for x in xs if x.dmax > a.dmax)
        dn = sum(1 for x in xs if x.dmax < a.dmax)
        d[pref + '_deeper_n'] = float(up)
        d[pref + '_shallower_n'] = float(dn)
        return up, dn
    up, dn = rank('o3_ct', same)
    d['o3_ct_deepest'] = float(up == 0)
    d['o3_ct_shallowest'] = float(dn == 0)
    if a.type:
        rank('o3_st', [x for x in OL if x.type == a.type])
    if a.unread:
        rank('o3_unr', nur)
        up, dn = rank('o3_unr_ct', [x for x in same if x.unread])
        d['o3_unr_ct_deepest'] = float(up == 0)
        d['o3_unr_ct_shallowest'] = float(dn == 0)
    if g.ph == 'op':
        allx = {x.name: x for x in OL}
        for lb in g.A.labs:
            allx.setdefault(lb, _attr(g, lb))
        dv = [x for x in allx.values() if x.dmax is not None]
        if dv:
            top = max(x.dmax for x in dv)
            d['o3_op_is_deepest'] = float(a.dmax >= top)
            if a.dmax < top and a.type:
                d['o3_op_pairs_deepest'] = float(sum(1 for x in dv if x.dmax == top and x.name != l and x.type and cf.compat(a.type, x.type)))


# ---- o4 ----

def _cur_slot(row, g):
    if row.get('rel') == 'declared' or not row.get('col'):
        ct = row.get('ctype')
        return 'DER:' + ct if ct else None
    return '%s.%s' % (row['rel'], row['col'])


def _o4(g, row, o, d):
    if g.ph not in ('val', 'fval') or o['kind'] != 'label':
        return
    l = _lab_of(g, o['tok'])
    a = _attr(g, l)
    cur = _cur_slot(row, g)
    same_col = False
    for i in a.held:
        s = g.E[i]
        for c in s.cols or [['', s.occ, 0]]:
            if any(x == l for _, x in c[1]):
                if cur:
                    d['o4_h_%s__%s' % (cur, _role(s, c[0]))] = 1.0
                same_col = same_col or c[0] == row.get('col')
    if a.held:
        hs = [g.E[i] for i in a.held]
        for s in hs:
            d['o4_h_kind_' + _origin_kind(s.rel)] = 1.0
        d['o4_h_ncols'] = float(max(len(s.cols) for s in hs))
        d['o4_h_private'] = float(max(sum(1 for x in s.labs if g.sites[x] == 1) for s in hs))
        if row.get('col') and g.sig:
            d['o4_h_samecol'] = float(same_col)
            d['o4_h_samerel'] = float(any(s.rel == g.A.rel for s in hs))
    once = Counter(x for _, x in g.A.occ)  # a label of A that E doesn't hold, at one site of A, is made in A and read nowhere
    if a.in_a and l not in g.holders and once[l] == 1:
        new = [x for x in g.A.labs if x not in g.holders and once[x] == 1]
        d['o4_inatom_n'] = float(len(new))
        ct = row.get('ctype')
        if ct:
            d['o4_inatom_typed_n'] = float(sum(1 for x in new if (_attr(g, x).type is None) or cf.compat(ct, _attr(g, x).type)))


# ---- o5, o6 ----

def _named_types(g, row):
    r = getattr(g, '_nt', 0)
    if r != 0:
        return r
    r = None
    rt = [t for t in g.rt if t]
    if g.sig:
        r = []
        for name, _, _ in g.A.cols:
            if name.isdigit() and int(name) < len(g.rt) and g.rt[int(name)]:
                r.append(g.rt[int(name)])
    elif row['phase'] == 'cols' and rt:
        c = Counter(rt)
        ok = True
        for _, t in _open_cols(g, row):
            if t is None:
                continue
            if c[t] > 0:
                c[t] -= 1
            else:
                ok = False
                break
        if ok:
            r = list(c.elements())
    g._nt = r
    return r


def _o5(g, row, o, d):
    if g.ph != 'cols':
        return
    kind = o['kind']
    opens = _open_cols(g, row)
    ut = _utypes(g)
    nts = _named_types(g, row)
    if kind == 'stop':
        typed = [t for _, t in opens if t]
        fu = sum(1 for t in typed if _fit(t, ut))
        fs = sum(1 for t in typed if _n_scope(g, t) > 0)
        d['o5_stop_open_n'] = float(len(opens))
        d['o5_stop_open_fit_unread'] = float(fu)
        d['o5_stop_open_fit_scope'] = float(fs)
        d['o5_stop_open_nofit'] = float(len(opens) > 0 and fs == 0)
        d['o5_stop_pend'] = float(sum(1 for u in ut if any(cf.compat(u, t) for t in typed)))
        d['o5_stop_pend0'] = float(not any(cf.compat(u, t) for u in ut for t in typed))
        for t in set(nts or ()):
            d['o6_stop_nt_' + t] = 1.0
        return
    if kind != 'column':
        return
    t = o.get('ctype')
    others = [x for tok, x in opens if tok != o['tok']]
    ot = [x for x in others if x]
    ofu = sum(1 for x in ot if _fit(x, ut))
    d['o5_other_open_n'] = float(len(others))
    d['o5_other_open_fit_unread'] = float(ofu)
    d['o5_other_open_fit_scope'] = float(sum(1 for x in ot if _n_scope(g, x) > 0))
    d['o5_other_open_nofit'] = float(sum(1 for x in ot if _n_scope(g, x) == 0))
    if t:
        fu = _fit(t, ut) > 0
        d['o5_only_fit_unread'] = float(fu and ofu == 0)
        d['o5_other_open_same_type'] = float(sum(1 for x in ot if cf.compat(x, t)))
        fur = fun = frl = frn = frf = frb = 0
        for lb, lt in g.stype.items():
            if not cf.compat(lt, t):
                continue
            a = _attr(g, lb)
            linked = bool(a.held & g.T)
            front = bool(a.held & g.F)
            if a.unread:
                if linked:
                    fur += 1
                else:
                    fun += 1
            else:
                if linked:
                    frl += 1
                else:
                    frn += 1
                if front:
                    frf += 1
                else:
                    frb += 1
        d['o5_fit_unread_linked'] = float(fur)
        d['o5_fit_unread_unlinked'] = float(fun)
        d['o5_fit_read_linked'] = float(frl)
        d['o5_fit_read_unlinked'] = float(frn)
        d['o5_fit_read_front'] = float(frf)
        d['o5_fit_read_back'] = float(frb)
        for u in set(nts or ()):
            d['o6_nt_%s__%s' % (u, t)] = 1.0


def _o7(g, row, o, d):
    """e7_kind_frac2: among the atoms of A's relation in E that fill the column, the share whose site has the option's kind."""
    want = {'fresh': 'fresh', 'label': 'read', 'zero': 'zero'}.get(o['kind'])
    if g.ph != 'val' or not g.sig or not row.get('col') or want is None:
        return
    ks = ['zero' if z else 'fresh' if any(g.sites[x] == 1 for _, x in p) else 'read' for p, z in _place(g, row) if p or z]
    if ks:
        d['e7_kind_frac2'] = sum(k == want for k in ks) / len(ks)


def ch4o(row, o):
    try:
        g = _graph(row)
    except Exception:
        if DEBUG:
            raise
        ERRORS['graph'] += 1
        return {}
    d = {}
    for f in (_o1, _o2, _o3, _o4, _o5, _o7):
        try:
            f(g, row, o, d)
        except Exception:
            if DEBUG:
                raise
            ERRORS[f.__name__] += 1
    return d


_OPS = frozenset(('=', '!=', '<', '<=', '>', '>='))


def ch4s(row, o):
    """The stop row's facts of the atoms as a set, on the STOP option."""
    if row['phase'] != 'stop' or o['tok'] != 'STOP':
        return {}
    try:
        g = _graph(row)
    except Exception:
        if DEBUG:
            raise
        ERRORS['graph'] += 1
        return {}
    E = g.E
    d = {'s_zeros': float(sum(a.nzero for a in E))}
    rels = Counter(a.rel for a in E if a.rel)
    for r in rels:
        d['s_rel_' + ('declared' if r.startswith('&') else r)] = 1.0
    d['s_repeat_rel'] = float(sum(c for c in rels.values() if c > 1))
    kinds = Counter('cmp' if a.rel in _OPS else _origin_kind(a.rel) for a in E if a.rel)
    for k, c in kinds.items():
        d['s_rk_' + k] = float(c)
    cols = [len(a.cols) for a in E if a.cols]
    if cols:
        d['s_cols_min'], d['s_cols_max'], d['s_cols_mean'] = float(min(cols)), float(max(cols)), sum(cols) / len(cols)
    held = [a for a in E if a.labs]
    d['s_atoms_all_unread'] = float(sum(1 for a in held if a.labs <= g.U))
    d['s_atoms_no_unread'] = float(sum(1 for a in held if not a.labs & g.U))
    if g.sites:
        d['s_labels_joined'] = float(sum(n > 1 for n in g.sites.values()))
        d['s_sites_mean'] = sum(g.sites.values()) / len(g.sites)
    for t, c in Counter(g.stype.get(l) for l in g.holders).items():
        if t:
            d['s_type_' + t] = float(c)
    d['s_neg_unread0'] = float(any(a.neg for a in E) and not g.U)
    return d


FEATURE_FUNCS = {'ch4o': ch4o, 'ch4s': ch4s}
