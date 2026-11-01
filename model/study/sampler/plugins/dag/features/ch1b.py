"""Explorer b, round 1: features for the picks after the relation (cols, fcol, val, fval, op).

Written against the masked row of choicefeat.mask_row.  A field a row may lack is read with .get:
ctype, rtypes (the recollection), neg (not in the row yet: 1 if the atom being built is wrapped in NOT).

Hypotheses (key prefix b<n>_):
  B1  A second use of a derived or lib relation in a clause repeats the first use's column count, and the first use's
      column types by slot.  (cols)
  B2  A column is named when its type is the type of a label that no atom has read yet (a pending join), and the atom
      stops once the unread labels have no matching column left.  (cols)
  B3  The shape of the atom so far (how many fresh labels and reads it holds) tells whether it takes another column,
      and a k>=2 atom with no read yet needs one.  (cols, val)
  B4  Column types come in pairs: the type of the last named column predicts the type of the next one.  (cols)
  B5  A label is the newest of its type, or the oldest/newest unread of its type (labels are consumed per type).  (val)
  B6  A second use of a relation fills the same column with the same kind of value (the same label, or fresh again).  (val)
  B7  In a NOT atom every value is a label that is already bound (no fresh, no column without a label in scope).  (cols, val)
  B9  A comparison compares two labels of one type, one of them the newest label.  (op)
"""
import os
import re
import sys
import collections

try:
    import choicefeat as cf
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    import choicefeat as cf

import relfeat

CANON = re.compile(r'(\*?)\b(V\d+)\b')
HEAD = re.compile(r'\((?:NOT \()?([^\s()]+)')
NUMERIC = frozenset(['Nat', 'Int', 'Offset', 'Number', 'number'])

_cache = [None, None]


def _top_cols(atom):
    """The top-level column groups '(:x ...)' of an atom string, NOT stripped."""
    if atom.startswith('(NOT '):
        atom = atom[5:-1]
    out, depth, start = [], 0, None
    for i, ch in enumerate(atom):
        if ch == '(':
            depth += 1
            if depth == 2 and atom[i + 1:i + 2] == ':':
                start = i
        elif ch == ')':
            if depth == 2 and start is not None:
                out.append(atom[start:i + 1])
                start = None
            depth -= 1
    return out


def _col_name(g):
    return g[2:].split(' ', 1)[0].rstrip(')')


def _parse(row):
    if _cache[0] is row:
        return _cache[1]
    pre, text, k = row.get('prefix') or [], row.get('text') or '', row['k']
    c = cf.context(row)
    reads, last_types = c['reads'], []
    stype = dict(zip(row.get('scope_labels') or [], row.get('scope_types') or []))
    created = c['created']
    refs = c['refs']
    # unread labels: made by the prefix, read by no prefix atom, not read in this atom's text
    unread = [stype.get(n) for i, n in enumerate(created) if reads[n] == 0 and i not in refs]
    hm = HEAD.match(text)
    rtok = hm.group(1) if hm else None
    prev = None
    if rtok:
        for a in reversed(pre):
            hp = HEAD.match(a)
            if hp and hp.group(1) == rtok:
                prev = _top_cols(a)
                break
    nfresh = c['nfresh']
    nread = c['nread']
    d = dict(c=c, reads=reads, stype=stype, created=created, unread=unread, last_types=last_types, prev=prev, rtok=rtok,
             nfresh=nfresh, nread=nread, newest_type=(stype.get(created[-1]) if created else None),
             neg=row.get('neg'), k=k)
    _cache[0], _cache[1] = row, d
    return d


def _cnt(types, t):
    return sum(cf.compat(t, x) for x in types if x)


def _f_cols(row, o, P):
    c = P['c']
    rt = c['rtypes']
    nn = len(c['named'])
    named = set(c['named'])
    k = P['k']
    prev = P['prev']
    d = {}
    # B1
    if prev is not None:
        d['b1_prev_exists'] = 1.0
        d['b1_prev_left'] = float(len(prev) - nn)
        if o['kind'] == 'stop':
            d['b1_stop_eq'] = float(nn == len(prev))
        elif o['kind'] == 'column':
            d['b1_more'] = float(nn < len(prev))
            nm = o.get('name')
            if nm:
                d['b1_name_in_prev'] = float(any(_col_name(g) == nm for g in prev))
            t = o.get('ctype')
            if t and nn < len(prev):
                labs = CANON.findall(prev[nn])
                pt = P['stype'].get(labs[0][1]) if labs else None
                if pt:
                    d['b1_slot_type'] = 1.0 if pt == t else -1.0
    # B2
    unread, last_types = P['unread'], P['last_types']
    left = [j for j in range(len(rt)) if j not in named] if rt else []
    d['b2_n_unread'] = float(len(unread))
    if o['kind'] == 'stop':
        d['b2_pending'] = float(sum(any(cf.compat(rt[j], u) for u in unread if u) for j in left if rt[j]))
    elif o['kind'] == 'column':
        t = o.get('ctype')
        if t:
            d['b2_unread_match'] = float(_cnt(unread, t))
            d['b2_last_match'] = float(_cnt(last_types, t))
            nt_ = P['newest_type']
            if nt_:
                d['b2_newest_match'] = 1.0 if cf.compat(t, nt_) else -1.0
    # B3
    d['b3_nfresh'] = float(P['nfresh'])
    d['b3_nread'] = float(P['nread'])
    d['b3_noread_k2'] = float(k >= 2 and P['nread'] == 0)
    d['b3_only_fresh'] = float(P['nfresh'] > 0 and P['nread'] == 0)
    # B4
    t = o.get('ctype') if o['kind'] == 'column' else None
    if t:
        if nn and rt and c['last'] < len(rt) and rt[c['last']]:
            d['b4_pt_%s__%s' % (rt[c['last']], t)] = 1.0
        elif not nn:
            d['b4_first_' + t] = 1.0
    elif o['kind'] == 'stop' and nn and rt and 0 <= c['last'] < len(rt) and rt[c['last']]:
        d['b4_stop_after_' + rt[c['last']]] = 1.0
    # B7
    neg = P['neg']
    if neg is not None:
        d['b7_neg'] = float(bool(neg))
        if neg and o['kind'] == 'column':
            t = o.get('ctype')
            if t:
                d['b7_neg_nolabel'] = float(_cnt(c['types'], t) == 0)
        if neg and o['kind'] == 'stop':
            d['b7_neg_stop'] = 1.0
    return d


def _f_val(row, o, P):
    c = P['c']
    k = P['k']
    ct = c['ctype']
    d = {}
    ph = row['phase']
    kind = o['kind']
    if ph == 'op':
        return _f_op(row, o, P)
    d['b3_noread_k2'] = float(k >= 2 and P['nread'] == 0)
    neg = P['neg']
    if neg is not None:
        d['b7_neg'] = float(bool(neg))
        if neg and kind in ('fresh', 'zero'):
            d['b7_neg_free'] = 1.0
    # B6 (val only)
    if ph == 'val' and P['prev'] is not None:
        slot = None
        nm = row.get('col')
        if nm:
            for g in P['prev']:
                if _col_name(g) == nm:
                    slot = g
        elif len(c['named']) < len(P['prev']):
            slot = P['prev'][len(c['named'])]
        if slot is not None:
            labs = CANON.findall(slot)
            if labs:
                star, name = labs[0]
                if kind == 'fresh':
                    d['b6_kind_match'] = 1.0 if star else -1.0
                elif kind == 'label':
                    d['b6_kind_match'] = -1.0 if star else 1.0
                    i = int(o['tok'][1:])
                    if i < len(P['created']):
                        d['b6_same_label'] = 1.0 if P['created'][i] == name else -1.0
    if kind != 'label':
        return d
    # B5
    i = int(o['tok'][1:])
    info = c['info']
    if i not in info:
        return d
    lt = info[i][3]
    labs = c['labs']
    ref = ct or lt
    same = [j for j in labs if ref and info[j][3] and cf.compat(ref, info[j][3])]
    if i in same:
        d['b5_ct_rank'] = float(sum(j > i for j in same))
        d['b5_ct_newest'] = float(i == max(same))
        d['b5_ct_oldest'] = float(i == min(same))
        d['b5_ct_n'] = float(len(same))
        unr = [j for j in same if info[j][2] == 0 and j not in c['refs']]
        if i in unr:
            d['b5_unr_newest'] = float(i == max(unr))
            d['b5_unr_oldest'] = float(i == min(unr))
            d['b5_unr_n'] = float(len(unr))
    return d


def _f_op(row, o, P):
    c = P['c']
    info = c['info']
    labs = c['labs']
    d = {}
    kind = o['kind']
    if kind == 'zero':
        if c['ref_types'] & NUMERIC:
            d['b9_zero_numeric'] = 1.0
        return d
    if kind != 'label':
        return d
    i = int(o['tok'][1:])
    if i not in info or not labs:
        return d
    lt = info[i][3]
    if not lt:
        return d
    all_labels = sorted(set(labs) | set(c['refs']))
    types = {j: info[j][3] for j in all_labels if j in info}
    newest = max(types) if types else None
    partners = [j for j, t in types.items() if j != i and t and cf.compat(lt, t)]
    d['b9_partners'] = float(len(partners))
    d['b9_has_partner'] = float(bool(partners))
    if newest is not None and i != newest and types.get(newest) and cf.compat(lt, types[newest]):
        d['b9_pairs_newest'] = 1.0
    if newest is not None and i == newest:
        d['b9_is_newest'] = 1.0
    same = [j for j, t in types.items() if t and cf.compat(lt, t)]
    d['b9_oldest_of_type'] = float(i == min(same))
    return d


def ch1b(row, o):
    ph = row['phase']
    P = _parse(row)
    if ph in ('cols', 'fcol'):
        return _f_cols(row, o, P) if ph == 'cols' else _f_fcol(row, o, P)
    if ph in ('val', 'fval', 'op'):
        return _f_val(row, o, P)
    return {}


def _f_fcol(row, o, P):
    d = {}
    neg = P['neg']
    if neg is not None:
        d['b7_neg'] = float(bool(neg))
    return d


FEATURE_FUNCS = {'ch1b': ch1b}
