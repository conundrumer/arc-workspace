"""ch2f: explorer f, round 2.  One function ch2f(row, option) -> {key: float} on a masked row (choicefeat.mask_row).

F1  Atom stop: a clause whose atoms fall into two or more connected pieces (atoms linked by a shared label) almost never stops.
    With 2 unread labels, STOP is 30 percent in a connected clause and 2 percent in a clause of 2 pieces (62 picks, 21 tasks).
    keys (STOP option only): f1_ncomp, f1_disc, f1_disc_unread
F2  Atom stop: the TYPE of an unread label matters, and two unread labels of one type are consumed by a next atom.
    One unread label, k>=2: Int 1 of 13 STOP (7 tasks), Nat 13 of 15, Axis 7 of 8, DiagDir 6 of 7, Box 30 of 40 (15 tasks).
    Two unread labels of one type: 10 percent STOP (59 picks, 19 tasks); of two types: 25 percent (212 picks).
    keys (STOP option only): f2_un_<Type> (count of unread labels of that type), f2_un_pairs, f2_un_ntypes
F3  Cols: an atom at k>=2 over a clause of 2 or more pieces bridges them (the gold atom reads labels of 2 or more pieces in 113 of
    161 such atoms; 43 read one piece).  So the atom keeps naming columns until it has touched 2 pieces, and a column whose type fits
    a label of a piece the atom has not touched is the next join.
    keys: f3_need_bridge (STOP and column options), f3_col_fit_untouched, f3_col_fit_touched, f3_stop_untouched_fit
F4  Val: in a clause of 2 or more pieces, once the atom touched one piece, a label of an untouched piece is favoured
    (gold 107 against 100 expected under p) and a label of a touched piece disfavoured (22 against 28); fresh is favoured less
    while the atom needs to bridge.
    keys: f4_lab_newpiece, f4_lab_samepiece, f4_nonlab_need_bridge
F5  Val of a library relation: a label is read at the column of the same name as the column that made it (gold 130 of 235 such
    label options, expected 111 under p; 15 tasks).
    keys: f5_creator_samecol, f5_creator_samerel
F6  Cols, correct types of the open columns.  For a derived relation row['rtypes'] is not in column-position order (the types
    at `:j` differ from rtypes[j] in 58 percent of derived cols picks), but each column option's ctype is right.  So the
    count/rank of a type among the OPEN columns and the 'joinable left' for STOP must come from the options.
    keys: f6_open_n, f6_open_same_type, f6_first_open_of_type, f6_last_open_of_type, f6_stop_open_in_scope, f6_stop_open_unread_fit,
          f6_open_in_scope_unread
F7  Cols (needs the field prior_uses): a derived relation used again in a LATER clause of a program names the columns of the
    earlier use (174 of 211 repeats at RULE depth 3+ in tasks of f name the same column set; 37 do not).
    row['prior_uses'] is the list of earlier uses that ch2d.py defines.  Keys: f7_in_last_prior, f7_in_any_prior, f7_n_prior, f7_stop_at_prior_len, f7_stop_below_prior_len.
    Absent field: no keys.
"""
import re
import sys

_S = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/sampler'
if _S not in sys.path:
    sys.path.insert(0, _S)
import choicefeat as cf  # noqa: E402
import relfeat  # noqa: E402

_TOK = re.compile(r'\(|\)|[^\s()]+')
_NUM = re.compile(r'^-?\d+$')
_ACACHE = {}


def _atom(a):
    """(rel, made names, read names, [(colname, value token or None)] top-level columns) of an atom string."""
    hit = _ACACHE.get(a)
    if hit is not None:
        return hit
    toks = _TOK.findall(a)
    rel = None
    made, reads, cols = [], [], []
    depth = 0
    for i, t in enumerate(toks):
        if t == '(':
            depth += 1
            if depth >= 2 and i + 1 < len(toks) and toks[i + 1].startswith(':') and depth == 2:
                v = toks[i + 2] if i + 2 < len(toks) else None
                cols.append((toks[i + 1][1:], None if v in ('(', ')') else v))
            continue
        if t == ')':
            depth -= 1
            continue
        if t == 'NOT':
            continue
        if rel is None and not t.startswith(':'):
            rel = t
            continue
        if t.startswith(':') or _NUM.match(t):
            continue
        if t.startswith('*'):
            made.append(t[1:])
        else:
            reads.append(t)
    out = (rel, made, reads, cols)
    if len(_ACACHE) > 30000:
        _ACACHE.clear()
    _ACACHE[a] = out
    return out


def _mine(row):
    pre = row.get('prefix') or []
    atoms = [_atom(a) for a in pre]
    labs = [set(m) | set(r) for _, m, r, _ in atoms]
    par = list(range(len(atoms)))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    owner = {}
    for i, s in enumerate(labs):
        for x in s:
            if x in owner:
                par[find(i)] = find(owner[x])
            else:
                owner[x] = i
    cm = {}
    for i, s in enumerate(labs):
        for x in s:
            cm[x] = find(i)
    reads = {}
    creator = {}
    for t, (rel, made, rd, cols) in enumerate(atoms):
        for x in rd:
            reads[x] = reads.get(x, 0) + 1
        for nm, v in cols:
            if v and v.startswith('*'):
                creator.setdefault(v[1:], (rel, nm))
        for x in made:
            creator.setdefault(x, (rel, None))
    stype = dict(zip(row.get('scope_labels') or [], row.get('scope_types') or []))
    c = cf.context(row)
    created = c['created']
    touched_names = {created[i] for i in c['refs'] if i < len(created)}
    touched = {cm[n] for n in touched_names if n in cm}
    unread = [n for n in stype if reads.get(n, 0) == 0 and n not in touched_names]
    return dict(c=c, cm=cm, ncomp=len(set(cm.values())), reads=reads, creator=creator, stype=stype, created=created,
                touched_names=touched_names, touched=touched, unread=unread)


def _stop_feats(row, o, m, d):
    if o.get('tok') != 'STOP':
        return
    # atom stop: STOP option only (the GO option gets nothing)
    c = m['c']
    names = set(m['stype'])
    un = [n for n in names if m['reads'].get(n, 0) == 0]
    ncomp = m['ncomp']
    d['f1_ncomp'] = float(min(ncomp, 3))
    d['f1_disc'] = float(ncomp >= 2)
    d['f1_disc_unread'] = float((ncomp >= 2) * min(len(un), 3))
    ts = [m['stype'][n] for n in un]
    cnt = {}
    for t in ts:
        if t:
            cnt[t] = cnt.get(t, 0) + 1
    for t, v in cnt.items():
        d['f2_un_' + t] = float(v)
    d['f2_un_pairs'] = float(sum(v - 1 for v in cnt.values()))
    d['f2_un_ntypes'] = float(len(cnt))


def _cols_feats(row, o, m, d):
    c = m['c']
    opts = [x for x in row['options'] if x['kind'] == 'column']
    ncomp, cm, touched = m['ncomp'], m['cm'], m['touched']
    need = ncomp >= 2 and len(touched) < 2 and row['k'] >= 2
    if o['kind'] == 'stop':
        d['f3_need_bridge'] = float(need)
        if need:
            n = 0
            for nm, t in m['stype'].items():
                if cm.get(nm) in touched:
                    continue
                if any(cf.compat(t, x.get('ctype')) for x in opts):
                    n += 1
            d['f3_stop_untouched_fit'] = float(n)
        # f6: correct types from the options
        types = [x.get('ctype') for x in opts if x.get('ctype')]
        d['f6_open_n'] = float(len(opts))
        d['f6_stop_open_in_scope'] = float(sum(1 for t in types if cf.n_in_scope(c, t) > 0))
        d['f6_stop_open_unread_fit'] = float(sum(1 for nm in m['unread'] if any(cf.compat(m['stype'][nm], t) for t in types)))
        prior = row.get('prior_uses')
        if prior:
            named = len(c['named'])
            last = len(prior[-1]['cols'])
            d['f7_stop_at_prior_len'] = float(named == last)
            d['f7_stop_below_prior_len'] = float(named < last)
        return
    if o['kind'] != 'column':
        return
    t = o.get('ctype')
    j = int(o['tok'][1:])
    if need:
        d['f3_need_bridge'] = 1.0
    if t:
        un = fu = ft = 0
        for nm, lt in m['stype'].items():
            if not cf.compat(lt, t):
                continue
            if cm.get(nm) in touched:
                ft += 1
            else:
                fu += 1
        d['f3_col_fit_untouched'] = float(fu if ncomp >= 2 else 0)
        d['f3_col_fit_touched'] = float(ft if ncomp >= 2 else 0)
        same = sorted(int(x['tok'][1:]) for x in opts if x.get('ctype') == t)
        d['f6_open_same_type'] = float(len(same) - 1)
        d['f6_first_open_of_type'] = float(same[0] == j)
        d['f6_last_open_of_type'] = float(same[-1] == j and len(same) > 1)
        d['f6_open_in_scope_unread'] = float(sum(1 for nm in m['unread'] if cf.compat(m['stype'][nm], t)))
    prior = row.get('prior_uses')
    if prior:
        d['f7_n_prior'] = float(len(prior))
        tok = o['tok']
        d['f7_in_last_prior'] = float(tok in prior[-1]['cols'])
        d['f7_in_any_prior'] = float(any(tok in p['cols'] for p in prior))


def _val_feats(row, o, m, d):
    ncomp, cm, touched = m['ncomp'], m['cm'], m['touched']
    need = ncomp >= 2 and len(touched) < 2 and row['k'] >= 2
    if o['kind'] != 'label':
        if o['kind'] in ('fresh', 'zero'):
            d['f4_nonlab_need_bridge'] = float(need)
        return
    i = int(o['tok'][1:])
    created = m['created']
    if i >= len(created):
        return
    nm = created[i]
    if ncomp >= 2 and touched and nm in cm:
        if cm[nm] in touched:
            d['f4_lab_samepiece'] = 1.0
        else:
            d['f4_lab_newpiece'] = 1.0
    col = row.get('col')
    cr = m['creator'].get(nm)
    if col and cr:
        d['f5_creator_samecol'] = float(cr[1] == col)
        d['f5_creator_samerel'] = float(cr[0] == row.get('rel'))


def ch2f(row, o):
    ph = row['phase']
    if ph not in ('stop', 'cols', 'val'):
        return {}
    m = relfeat.row_cache(row, _mine)
    d = {}
    if ph == 'stop':
        _stop_feats(row, o, m, d)
    elif ph == 'cols':
        _cols_feats(row, o, m, d)
    else:
        _val_feats(row, o, m, d)
    return d


FEATURE_FUNCS = {'ch2f': ch2f}
