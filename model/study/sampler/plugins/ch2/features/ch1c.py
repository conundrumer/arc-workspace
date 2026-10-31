"""ch1c: explorer c's features for the picks after the relation (cols, fcol, val, fval, op).

One function, ch1c(row, option) -> {key: float}, on a masked row (choicefeat.mask_row).  Hypotheses:
  C1  A column pick for an atom at k >= 2 is a join pick: while the atom reads no scope label yet, a column whose type has a scope label
      is the join candidate, and STOP is unlikely.  Keys c1_joined, c1_stop_unjoined, c1_col_join_candidate, c1_stop_joinable_left.
  C2  The join column is the column whose type fits an unread scope label, preferably one made in the previous atom (88% of the first
      labels read by a k >= 2 atom were unread, 74% were made in atom k-1).  Keys c2_fit_unread_prev, c2_fit_unread_old,
      c2_fit_read_prev, c2_fit_read_old, c2_stop_pending.
  C3  Among columns of one type in a relation, the first or the only one of that type is the pick.  Keys c3_type_mult, c3_type_rank,
      c3_first_of_type, c3_scope_n_vs_mult.
  C4  Position counted from the end of the relation: the last column, and STOP when no column is left.  Keys c4_from_end, c4_last.
  C5  Value pick: once the atom has a join, a fresh label is as likely as an old label; before the join, the label wins (k >= 2:
      label 80-90 percent with no join in the atom, fresh 55-75 percent with an old label after a join).  Keys c5_joined, c5_nfresh,
      c5_ord, c5_last_col_nojoin, c5_left_after.
  C6  Competition among the label options: how many are unread and not yet in the atom, and the rank of this label among labels of
      its type by recency.  Keys c6_n_unread_opts, c6_unread_rank, c6_only_unread, c6_n_unread_prev, c6_same_type_rank, c6_same_type_n.
  C7  A label made by an atom with one column or one fresh label is the point of that atom and is read next; a label from a
      many-column atom is read less.  Keys c7_origin_<kind>, c7_origin_ncols, c7_origin_nfresh, c7_origin_gap.
"""
import os
import re
import sys

_S = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/sampler'
if _S not in sys.path:
    sys.path.insert(0, _S)
import choicefeat as cf  # noqa: E402
import relfeat  # noqa: E402

REL = re.compile(r'^\((?:NOT \()?([^\s()]+)')
TOPCOL = re.compile(r'\(:[^\s()]+')


def _depth1_cols(text):
    out = []
    for m in cf.TXT_COL.finditer(text):
        if text[:m.start()].count('(') - text[:m.start()].count(')') == 1:
            out.append(int(m.group(1)))
    return out


def _origin_kind(atom):
    m = REL.match(atom)
    r = m.group(1) if m else ''
    if r.startswith('&'):
        return 'derived'
    if r.endswith('_elem'):
        return 'elem'
    if r in ('input', 'ex_input', 'ex_output'):
        return 'base'
    return 'lib'


def _mine(row):
    c = cf.context(row)
    k = row['k']
    pre = row.get('prefix') or []
    first_at, last_at, reads = {}, {}, {}
    for t, a in enumerate(pre, 1):
        for m in cf.CANON.finditer(a):
            nm = m.group(2)
            if m.group(1):
                first_at.setdefault(nm, t)
            else:
                reads[nm] = reads.get(nm, 0) + 1
            last_at[nm] = t
    created = c['created']
    idx = {nm: i for i, nm in enumerate(created)}
    stype = dict(zip(row.get('scope_labels') or [], row.get('scope_types') or []))
    refs = c['refs']
    labels = []  # (name, type, made_prev, unread)
    for nm, t in stype.items():
        unread = reads.get(nm, 0) == 0 and idx.get(nm) not in refs
        labels.append((nm, t, first_at.get(nm) == k - 1, unread))
    rt = c['rtypes'] or []
    cols = _depth1_cols(row.get('text') or '')
    cur = cols[-1] if cols else -1
    return dict(c=c, k=k, first_at=first_at, reads=reads, idx=idx, stype=stype, refs=refs, labels=labels, rt=rt, cur=cur,
                pre=pre, nfresh=sum(1 for _ in cf.TXT_NEW.finditer(row.get('text') or '')),
                nrefs=len(refs))


def _origin(m, nm):
    t = m['first_at'].get(nm)
    if t is None:
        return None
    a = m['pre'][t - 1]
    return a, t


def ch1c(row, o):
    ph = row['phase']
    if ph not in cf.PHASES:
        return {}
    m = relfeat.row_cache(row, _mine)
    c, k, rt = m['c'], m['k'], m['rt']
    d = {}
    if ph in ('cols', 'fcol'):
        refs = m['nrefs']
        unjoined = k >= 2 and refs == 0
        d['c1_joined'] = float(refs)
        left = [j for j in range(len(rt)) if j not in set(c['named'])] if rt else []
        if o['kind'] == 'stop':
            d['c1_stop_unjoined'] = float(unjoined)
            if rt and unjoined:
                d['c1_stop_joinable_left'] = float(sum(1 for j in left if rt[j] and cf.n_in_scope(c, rt[j]) > 0))
            if rt:
                pend = 0
                for nm, t, prev, unread in m['labels']:
                    if unread and any(cf.compat(t, rt[j]) for j in left if rt[j]):
                        pend += 1
                d['c2_stop_pending'] = float(pend)
            return d
        if o['kind'] != 'column':
            return d
        j = int(o['tok'][1:])
        t = o.get('ctype')
        if rt:
            d['c4_from_end'] = float(len(rt) - 1 - j)
            d['c4_last'] = float(j == len(rt) - 1)
        if t:
            fit = [(prev, unread) for nm, lt, prev, unread in m['labels'] if cf.compat(lt, t)]
            d['c1_col_join_candidate'] = float(unjoined and bool(fit))
            d['c2_fit_unread_prev'] = float(sum(1 for p, u in fit if u and p))
            d['c2_fit_unread_old'] = float(sum(1 for p, u in fit if u and not p))
            d['c2_fit_read_prev'] = float(sum(1 for p, u in fit if not u and p))
            d['c2_fit_read_old'] = float(sum(1 for p, u in fit if not u and not p))
            if rt:
                same = [x for x in range(len(rt)) if rt[x] == t]
                d['c3_type_mult'] = float(len(same))
                d['c3_type_rank'] = float(same.index(j)) if j in same else 0.0
                d['c3_first_of_type'] = float(same[0] == j)
                d['c3_scope_n_vs_mult'] = float(sum(1 for lt in m['stype'].values() if lt == t) - len(same))
        return d

    # val, fval, op
    cols = _depth1_cols(row.get('text') or '')
    cur = cols[-1] if cols else -1
    refs = m['nrefs']
    d['c5_joined'] = float(refs)
    d['c5_nfresh'] = float(m['nfresh'])
    d['c5_ord'] = float(max(len(cols) - 1, 0))
    if rt and cur >= 0 and ph == 'val':
        left_after = len(rt) - 1 - cur
        d['c5_left_after'] = float(left_after)
        d['c5_last_col_nojoin'] = float(k >= 2 and refs == 0 and left_after == 0)
    labs = [i for i in c['labs']]
    info = c['info']
    unread_opts = [i for i in labs if info[i][2] == 0 and i not in c['refs']]
    d['c6_n_unread_opts'] = float(len(unread_opts))
    d['c6_n_unread_prev'] = float(sum(1 for i in unread_opts if info[i][0] == 1))
    if o['kind'] != 'label':
        return d
    i = int(o['tok'][1:])
    age, rec, rd, lt = info.get(i, (0, 0, 0, None))
    if i in unread_opts:
        order = sorted(unread_opts, key=lambda x: (info[x][1], -x))
        d['c6_unread_rank'] = float(order.index(i))
        d['c6_only_unread'] = float(len(unread_opts) == 1)
    if lt:
        same = sorted([x for x in labs if info[x][3] == lt], key=lambda x: (info[x][1], -x))
        d['c6_same_type_n'] = float(len(same))
        d['c6_same_type_rank'] = float(same.index(i)) if i in same else 0.0
    nm = c['created'][i] if i < len(c['created']) else None
    if nm is not None:
        og = _origin(m, nm)
        if og:
            a, t = og
            d['c7_origin_' + _origin_kind(a)] = 1.0
            d['c7_origin_ncols'] = float(len(TOPCOL.findall(a)))
            d['c7_origin_nfresh'] = float(a.count('*'))
            d['c7_origin_gap'] = float(k - t)
    return d


FEATURE_FUNCS = {'ch1c': ch1c}
