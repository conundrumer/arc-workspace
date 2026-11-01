"""ch2d: explorer d, round 2.  One function, ch2d(row, option) -> {d<n>_<what>: float}, on a masked row (choicefeat.mask_row).

Fields read beyond the round-1 set: `point_group` (a dict; only ['kind'] is read) and `prior_uses` (not in the rows yet; D7
returns nothing without it).  A missing field gives no key.

D1  Column types of a derived relation come from the options, not from rtypes.  rtypes is not aligned to the column tokens of a
    derived relation (97 percent of gold labels have the option's ctype, 59 percent have rtypes[j]), so every rtypes-based test
    of "which columns are left" is noisy.  Here the columns left are the column options with an index above the last named one
    (`rem`), and the unread labels are the labels the clause made that no prefix atom and no part of the atom so far reads.
    Gold seldom skips a column that fits an unread label (138 of 1518 gold column picks at k>=2, against 2268 of 4668 options).
    keys: d1_col_skipped_fit_unread, d1_col_skipped_fit_scope, d1_col_first_fit_unread, d1_col_later_fit_unread,
          d1_col_same_type_rem, d1_col_type_rank_rem, d1_col_gap, d1_col_gap_free,
          d1_stop_pend, d1_stop_pend0, d1_stop_fwd_n, d1_stop_fwd_fit_unread, d1_stop_fwd_fit_scope, d1_stop_nofit
D2  A lib relation's column takes a label by the role the label had before: the pair (this relation.column, the relation.column the
    label was made or read in) is stable (relative.X takes the label that was inside.A, relative.Base the one that was inside.B).
    keys: d2_r_<rel>.<col>__<prel>.<pcol>[*] (any earlier role), d2_l_... (the latest role only), d2_slot_before, d2_name_before.
    A derived column crosses its ctype: d2_r_DER:<ctype>__..., and a derived earlier role is 'DER'.
D3  A new atom joins labels that no earlier atom has joined: the candidate label has not shared an atom with a label that this
    atom already holds.  keys: d3_cooc_n, d3_cooc_any, d3_cooc_none (only where the atom holds a label).
D4  Atom stop, on the STOP option: the shape of the finished atom (fresh labels, reads) and the types of the labels no atom reads.
    keys: d4_nf, d4_nr, d4_nf0, d4_nr0, d4_nr_ge3, d4_pure_fresh, d4_unread_<Type>, d4_newtype_<Type>, d4_unread_one_<Type>.
D5  The clause kind changes the stop and column rates.
    keys: d5_pg_<kind> (every option), d5_stop_pg_<kind> (STOP option).
D6  A label made by the atom's own earlier column and not yet read in the atom is read next, in the order made (fval and val).
    keys: d6_inatom_new, d6_inatom_first, d6_inatom_rank.
D7  A relation that an earlier clause (or an earlier atom of this clause) used again names the same columns, and fills each column
    with the same kind of value.  Needs row['prior_uses'] = list, oldest first, of the earlier atoms with this atom's relation
    token: {'same_clause': bool, 'cols': {':3': 'fresh'|'read'|'zero'|'rec', ...}}.
    keys: e7_has, e7_col_in_last, e7_col_in_any, e7_col_frac, e7_stop_left, e7_stop_done, e7_stop_count_eq, e7_kind_last,
          e7_kind_frac.
"""
import os
import re
import sys

_S = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _S not in sys.path:
    sys.path.insert(0, _S)
import choicefeat as cf  # noqa: E402
import relfeat  # noqa: E402

_HEAD = re.compile(r'^\((?:NOT \()?([^\s()]+)')
_LIBCOL = re.compile(r'\(:([^\s()]+) (\*?)(V\d+)\)')
_ANYLAB = re.compile(r'(\*?)\b(V\d+)\b')
_CURCOL = re.compile(r'\(:(\d+)[^()]*$')
_TOPCOL = re.compile(r'\(:(\d+)')


def _toplevel_cols(text):
    out = []
    for m in _TOPCOL.finditer(text):
        if text[:m.start()].count('(') - text[:m.start()].count(')') == 1:
            out.append(int(m.group(1)))
    return out


def _mine(row):
    c = cf.context(row)
    ph = row['phase']
    stype = dict(zip(row.get('scope_labels') or [], row.get('scope_types') or []))
    created, reads, refs = c['created'], c['reads'], c['refs']
    text = row.get('text') or ''
    unread = [stype.get(nm) for i, nm in enumerate(created) if reads[nm] == 0 and (ph == 'stop' or i not in refs)]  # at a stop row refs holds every label of the finished atom
    unread = [t for t in unread if t]
    scope_types = [t for t in stype.values() if t]
    named = _toplevel_cols(text)
    last = named[-1] if named and ph == 'cols' else (c['last'] if ph == 'cols' else -1)
    rem = []
    if ph == 'cols':
        for o in row['options']:
            if o['kind'] == 'column':
                rem.append((int(o['tok'][1:]), o.get('ctype')))
    fwd = [(j, t) for j, t in rem if j > last]
    # roles of the labels in the prefix: name -> [(rel, col, made)] in order; the atoms that hold each label
    roles, holds = {}, {}
    for a_i, a in enumerate(row.get('prefix') or []):
        m = _HEAD.match(a)
        rel = m.group(1) if m else '?'
        der = rel.startswith('&')
        if not der:
            for cm in _LIBCOL.finditer(a):
                roles.setdefault(cm.group(3), []).append((rel, cm.group(1), False))
        for lm in _ANYLAB.finditer(a):
            nm = lm.group(2)
            if der:
                roles.setdefault(nm, []).append(('DER', '', False))
            holds.setdefault(nm, set()).add(a_i)
    # labels made in this atom's text and not read in it
    new_in_text = c['new']
    new_unread = [i for i in new_in_text if i not in refs]
    return dict(c=c, stype=stype, unread=unread, scope_types=scope_types, rem=rem, fwd=fwd, last=last, roles=roles, holds=holds,
                new_unread=sorted(set(new_unread)), text=text, nnew=len(new_in_text), nref=c['nread'])


def _fit(t, types):
    return sum(1 for u in types if cf.compat(t, u))


def _d1_cols(row, o, m, d):
    unread, st, fwd = m['unread'], m['scope_types'], m['fwd']
    if o['kind'] == 'stop':
        pend = 0
        for u in set(unread):
            if any(t and cf.compat(u, t) for _, t in fwd):
                pend += sum(1 for x in unread if x == u)
        d['d1_stop_pend'] = float(pend)
        d['d1_stop_pend0'] = float(pend == 0)
        d['d1_stop_fwd_n'] = float(len(fwd))
        fu = sum(1 for _, t in fwd if t and _fit(t, unread))
        fs = sum(1 for _, t in fwd if t and _fit(t, st))
        d['d1_stop_fwd_fit_unread'] = float(fu)
        d['d1_stop_fwd_fit_scope'] = float(fs)
        d['d1_stop_nofit'] = float(len(fwd) > 0 and fs == 0)
        return
    if o['kind'] != 'column':
        return
    j = int(o['tok'][1:])
    t = o.get('ctype')
    before = [(x, tx) for x, tx in fwd if x < j]
    after = [(x, tx) for x, tx in fwd if x > j]
    sk_u = sum(1 for _, tx in before if tx and _fit(tx, unread))
    sk_s = sum(1 for _, tx in before if tx and _fit(tx, st))
    d['d1_col_skipped_fit_unread'] = float(sk_u)
    d['d1_col_skipped_fit_scope'] = float(sk_s)
    d['d1_col_gap'] = float(len(before))
    d['d1_col_gap_free'] = float(len(before) - sk_s)
    if t:
        fu = _fit(t, unread) > 0
        d['d1_col_first_fit_unread'] = float(fu and sk_u == 0)
        same = [(x, tx) for x, tx in fwd if tx and x != j and cf.compat(tx, t)]
        d['d1_col_same_type_rem'] = float(len(same))
        d['d1_col_type_rank_rem'] = float(sum(1 for x, _ in same if x < j))
    d['d1_col_later_fit_unread'] = float(sum(1 for _, tx in after if tx and _fit(tx, unread)))


def _cur_slot(row):
    if row.get('rel') == 'declared' or not row.get('col'):
        ct = row.get('ctype')
        return 'DER:' + ct if ct else None
    return '%s.%s' % (row['rel'], row['col'])


def _label_name(m, o):
    i = int(o['tok'][1:])
    cr = m['c']['created']
    return (cr[i] if i < len(cr) else None), i


def _d2_d3_d6(row, o, m, d):
    if o['kind'] != 'label':
        return
    nm, i = _label_name(m, o)
    # D6: made by this atom's own earlier column, unread so far
    if i in m['new_unread']:
        d['d6_inatom_new'] = 1.0
        d['d6_inatom_first'] = float(i == m['new_unread'][0])
        d['d6_inatom_rank'] = float(m['new_unread'].index(i))
    if nm is None:
        return
    # D2
    cur = _cur_slot(row)
    rs = m['roles'].get(nm)
    if cur and rs:
        keys = []
        for rel, col, made in rs:
            keys.append(('DER' if rel == 'DER' else rel + '.' + col) + ('*' if made else ''))
        for k in set(keys):
            d['d2_r_%s__%s' % (cur, k)] = 1.0
        d['d2_l_%s__%s' % (cur, keys[-1])] = 1.0
        if row.get('col') and row.get('rel') != 'declared':
            d['d2_slot_before'] = float(any(r == row['rel'] and c == row['col'] for r, c, _ in rs))
            d['d2_name_before'] = float(any(c == row['col'] for _, c, _ in rs))
    # D3
    refs = m['c']['refs']
    cr = m['c']['created']
    in_text = {cr[x] for x in refs if x < len(cr)}
    if in_text:
        hs = m['holds'].get(nm, set())
        n = 0
        for t_nm in in_text:
            n += len(hs & m['holds'].get(t_nm, set()))
        d['d3_cooc_n'] = float(n)
        d['d3_cooc_any'] = float(n > 0)
        d['d3_cooc_none'] = float(n == 0)


def _d4_stop(row, o, m, d):
    if o['kind'] != 'stop' or o['tok'] != 'STOP':
        return
    nf, nr = m['nnew'], m['nref']
    d['d4_nf'] = float(nf)
    d['d4_nr'] = float(nr)
    d['d4_nf0'] = float(nf == 0)
    d['d4_nr0'] = float(nr == 0)
    d['d4_nr_ge3'] = float(nr >= 3)
    d['d4_pure_fresh'] = float(nf > 0 and nr == 0)
    for t in m['unread']:
        k = 'd4_unread_' + t
        d[k] = d.get(k, 0.0) + 1.0
    if len(m['unread']) == 1:
        d['d4_unread_one_' + m['unread'][0]] = 1.0
    pre = row.get('prefix') or []
    if pre:
        c = m['c']
        stype = m['stype']
        for lm in _ANYLAB.finditer(pre[-1]):
            if lm.group(1):
                t = stype.get(lm.group(2))
                if t:
                    d['d4_newtype_' + t] = 1.0


def _d7(row, o, m, d):
    pu = row.get('prior_uses')
    if not pu:
        return
    d['e7_has'] = 1.0
    last = pu[-1]['cols']
    ph = row['phase']
    if ph == 'cols':
        named = {':%d' % j for j in _toplevel_cols(m['text'])}
        if o['kind'] == 'column':
            tok = o['tok']
            d['e7_col_in_last'] = float(tok in last)
            d['e7_col_in_any'] = float(any(tok in u['cols'] for u in pu))
            d['e7_col_frac'] = sum(1 for u in pu if tok in u['cols']) / len(pu)
        elif o['kind'] == 'stop':
            j0 = m['last']
            left = [t for t in last if int(t[1:]) > j0]
            d['e7_stop_left'] = float(len(left))
            d['e7_stop_done'] = float(not left)
            d['e7_stop_count_eq'] = float(len(named) == len(last))
    elif ph == 'val':
        cm = _CURCOL.search(m['text'])
        if not cm:
            return
        tok = ':' + cm.group(1)
        kinds = [u['cols'].get(tok) for u in pu]
        want = {'fresh': 'fresh', 'label': 'read', 'zero': 'zero'}.get(o['kind'])
        if want and kinds[-1] is not None:
            d['e7_kind_last'] = 1.0 if kinds[-1] == want else -1.0
            ks = [k for k in kinds if k is not None]
            d['e7_kind_frac'] = sum(1 for k in ks if k == want) / len(ks)


def ch2d(row, o):
    d = {}
    ph = row.get('phase')
    pg = (row.get('point_group') or {}).get('kind')
    if pg:
        d['d5_pg_' + pg] = 1.0
        if ph == 'stop' and o['kind'] == 'stop' and o['tok'] == 'STOP':
            d['d5_stop_pg_' + pg] = 1.0
    if ph not in cf.PHASES:
        return d
    m = relfeat.row_cache(row, _mine)
    if ph == 'cols':
        _d1_cols(row, o, m, d)
    elif ph in ('val', 'fval'):
        _d2_d3_d6(row, o, m, d)
    elif ph == 'stop':
        _d4_stop(row, o, m, d)
    _d7(row, o, m, d)
    return d


FEATURE_FUNCS = {'ch2d': ch2d}
