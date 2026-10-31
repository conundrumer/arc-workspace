"""ch2e: explorer e, round 2.  One function, ch2e(row, option) -> {key: float}, on a masked row (choicefeat.mask_row).

Atom stop (row phase 'stop'; the prefix holds the finished atom, text is the finished atom).  Keys are set on the STOP option only.
  E1  Connectedness.  Atoms are joined by the labels they share.  A clause with more than one component, or a finished atom that
      shares no label with an earlier atom, is not finished: STOP 3 percent (RULE k>=2, 293 picks) against 51 percent.
      keys e1_comps, e1_multi, e1_comps_nonot, e1_last_isolated, e1_k_isolated
  E2  Shape of the finished atom: how many fresh labels it makes, how many earlier labels it reads, how many of those no atom had read
      before (it consumes them).  A check atom (reads only) stops 60 to 80 percent; an atom with fresh labels and no read of an earlier
      label stops 2 percent.
      keys e2_nfresh, e2_nread_prior, e2_nread_self, e2_consumed, e2_check_only, e2_nconst
  E3  Unread labels by the kind of atom that made them.  An unread output of a derived atom is a result (STOP 78 percent when it is
      the only unread label); unread outputs of library atoms are intermediates the next atom reads.
      keys e3_unread, e3_unread_lib, e3_unread_der, e3_unread_last, e3_unread_old, e3_unread_old_lib, e3_only_der_out
  E5  Unread labels by type.  Unread Dir, Axis, DiagDir and Int labels are intermediates (STOP 5 to 20 percent); unread Position, Color,
      Ident, Box and Nat labels are results (STOP 50 to 78 percent).
      keys e5_unread_helper, e5_unread_entity, e5_unr_<Type>, e5_unread_ntypes
  E7  Atom kind and clause kind.
      keys e7_neg_unread0, e7_det

Value pick (phases val, fval; k >= 2)
  E4  Bridging.  While the clause so far has two or more components, a label from a component the atom has not read yet is the pick
      (96 percent: 244 of 253 picks with no component linked yet, label_new 200 of 352 with one linked), and a fresh label is rare.
      keys e4_ncomp, e4_n_unlinked, e4_bridge, e4_inlinked, e4_fresh_unlinked

Column pick of a derived relation after at least one named column
  E6  The options of a column pick list every unnamed column with its own type, which the row's rtypes can disagree with (in 25 percent
      of derived atoms rtypes is in another column order, or flattens a record key).  STOP is less likely when the unnamed columns have
      types that fit scope labels (STOP 51, 37, 20, 20 percent for 0, 1, 2, 3+ fitting columns).
      keys e6_left_n, e6_left_in, e6_left_unread_fit, e6_left_unread_fit_ge1
"""
import re
import sys

_S = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/sampler'
if _S not in sys.path:
    sys.path.insert(0, _S)
import choicefeat as cf  # noqa: E402
import relfeat  # noqa: E402

LAB = re.compile(r'(?<![\w:&.])(\*?)(V\d+)\b')
HEAD = re.compile(r'^\((?:NOT \()?([^\s()]+)')
HELPER = frozenset(['Dir', 'Axis', 'DiagDir', 'DiagAxis', 'Dir8', 'Int', 'Offset', 'D4', 'C4', 'Sense', 'Sym'])


def _comps(atoms):
    """(number of components, {label: component root}) of the atoms joined by shared labels; an atom with no label is no component."""
    atoms = [a for a in atoms if LAB.search(a)]
    n = len(atoms)
    par = list(range(n))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    owner = {}
    for a, t in enumerate(atoms):
        for _, l in LAB.findall(t):
            if l in owner:
                par[find(a)] = find(owner[l])
            else:
                owner[l] = a
    roots = {find(a) for a in range(n)}
    return len(roots), {l: find(a) for l, a in owner.items()}


def _stop_info(row):
    pre = row.get('prefix') or []
    if not pre:
        return None
    last = pre[-1]
    c = cf.context(row)
    ncomp, _ = _comps(pre)
    ncomp_nonot, _ = _comps([a for a in pre if not a.startswith('(NOT')])
    prior = set()
    for a in pre[:-1]:
        for _, l in LAB.findall(a):
            prior.add(l)
    fresh, reads = [], []
    for s, l in LAB.findall(last):
        (fresh if s else reads).append(l)
    reads_before = {}
    for a in pre[:-1]:
        for s, l in LAB.findall(a):
            if not s:
                reads_before[l] = reads_before.get(l, 0) + 1
    rprior = [l for l in reads if l in prior]
    consumed = sum(1 for l in set(rprior) if reads_before.get(l, 0) == 0)
    made = {}
    for a in pre:
        m = HEAD.match(a)
        h = m.group(1) if m else ''
        for s, l in LAB.findall(a):
            if s and l not in made:
                made[l] = h
    unread = [n for n in set(c['created']) if c['reads'][n] == 0]
    st = dict(zip(row.get('scope_labels') or [], row.get('scope_types') or []))
    fset = set(fresh)
    u_lib = sum(1 for n in unread if not made.get(n, '').startswith('&r'))
    u_last = sum(1 for n in unread if n in fset)
    u_old_lib = sum(1 for n in unread if n not in fset and not made.get(n, '').startswith('&r'))
    types = [st.get(n) for n in unread]
    return dict(ncomp=ncomp, ncomp_nonot=ncomp_nonot, isolated=(len(pre) > 1 and bool(fresh or reads) and not any(l in prior for l in fresh + reads)),
                nfresh=len(fresh), nread_prior=len(rprior), nread_self=sum(1 for l in reads if l in fset),
                nconst=len(re.findall(r'(?<![\w:&.*])0(?![\w.])', last)), consumed=consumed, nun=len(unread), u_lib=u_lib,
                u_der=len(unread) - u_lib, u_last=u_last, u_old=len(unread) - u_last, u_old_lib=u_old_lib, types=types)


def _f_stop(row, o, d):
    if o['tok'] != 'STOP':
        return
    s = relfeat.row_cache(row, _stop_info)
    if s is None:
        return
    k = row['k']
    d['e1_comps'] = float(s['ncomp'])
    d['e1_multi'] = float(s['ncomp'] > 1)
    d['e1_comps_nonot'] = float(s['ncomp_nonot'])
    d['e1_last_isolated'] = float(s['isolated'])
    d['e1_k_isolated'] = float(k) * s['isolated']
    d['e2_nfresh'] = float(s['nfresh'])
    d['e2_nread_prior'] = float(s['nread_prior'])
    d['e2_nread_self'] = float(s['nread_self'])
    d['e2_consumed'] = float(s['consumed'])
    d['e2_check_only'] = float(s['nfresh'] == 0 and s['nread_prior'] > 0)
    d['e2_nconst'] = float(s['nconst'])
    d['e3_unread'] = float(s['nun'])
    d['e3_unread_lib'] = float(s['u_lib'])
    d['e3_unread_der'] = float(s['u_der'])
    d['e3_unread_last'] = float(s['u_last'])
    d['e3_unread_old'] = float(s['u_old'])
    d['e3_unread_old_lib'] = float(s['u_old_lib'])
    d['e3_only_der_out'] = float(s['nun'] == 1 and s['u_der'] == 1)
    ty = [t for t in s['types'] if t]
    nh = sum(1 for t in ty if t in HELPER)
    d['e5_unread_helper'] = float(nh)
    d['e5_unread_entity'] = float(len(ty) - nh)
    d['e5_unread_ntypes'] = float(len(set(ty)))
    for t in ty:
        key = 'e5_unr_' + t
        d[key] = d.get(key, 0.0) + 1.0
    d['e7_neg_unread0'] = float(bool(row.get('neg')) and s['nun'] == 0)
    d['e7_det'] = float(((row.get('point_group') or {}).get('kind')) == 'DET')


def _val_info(row):
    pre = row.get('prefix') or []
    c = cf.context(row)
    ncomp, cm = _comps(pre)
    created = c['created']
    linked = set()
    for x in c['refs']:
        if x < len(created):
            r = cm.get(created[x])
            if r is not None:
                linked.add(r)
    return ncomp, cm, created, linked


def _f_val(row, o, d):
    if row.get('k', 1) < 2 or o['kind'] not in ('label', 'fresh', 'zero'):
        return
    ncomp, cm, created, linked = relfeat.row_cache(row, _val_info)
    if ncomp < 2:
        return
    n_un = ncomp - len(linked)
    d['e4_ncomp'] = float(ncomp)
    d['e4_n_unlinked'] = float(n_un)
    if o['kind'] == 'label':
        x = int(o['tok'][1:])
        r = cm.get(created[x]) if x < len(created) else None
        if r is not None:
            if r in linked:
                d['e4_inlinked'] = 1.0
            else:
                d['e4_bridge'] = 1.0
    elif o['kind'] == 'fresh':
        d['e4_fresh_unlinked'] = float(n_un)


def _cols_info(row):
    c = cf.context(row)
    cols = [o for o in row['options'] if o['kind'] == 'column']
    st = list(zip(row.get('scope_labels') or [], row.get('scope_types') or []))
    unread_t = [t for n, t in st if c['reads'][n] == 0 and t]
    left_in = sum(1 for o in cols if o.get('ctype') and cf.n_in_scope(c, o['ctype']) > 0)
    left_un = sum(1 for o in cols if o.get('ctype') and any(cf.compat(o['ctype'], t) for t in unread_t))
    return len(cols), left_in, left_un


def _f_cols(row, o, d):
    if o['kind'] != 'stop' or row.get('rel') != 'declared' or row.get('k', 1) < 2 or '(:' not in (row.get('text') or ''):
        return
    n, left_in, left_un = relfeat.row_cache(row, _cols_info)
    d['e6_left_n'] = float(n)
    d['e6_left_in'] = float(left_in)
    d['e6_left_unread_fit'] = float(left_un)
    d['e6_left_unread_fit_ge1'] = float(left_un > 0)


def ch2e(row, o):
    d = {}
    ph = row.get('phase')
    if ph == 'stop':
        _f_stop(row, o, d)
    elif ph in ('val', 'fval'):
        _f_val(row, o, d)
    elif ph == 'cols':
        _f_cols(row, o, d)
    return d


FEATURE_FUNCS = {'ch2e': ch2e}
