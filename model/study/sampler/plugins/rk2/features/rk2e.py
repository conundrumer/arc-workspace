"""Explorer e, round 2: member position, relative depth, comparison context and target demand for the relation pick.

One function, rk2e(row, option) -> {key: float}.  Row-level work is cached on the row object (the model passes the same
masked row for every option).  Types are compared by their base name (the text before '(').  Fields read: k, scope, prefix,
prefix_depth, prefix_bases, and per option tok, kind, name (only a member suffix that LIB_MEMBERS declares), columns, types,
dag.depth, dag.base, dag.method.  It never reads gold, clause, gold_atom, point_group, dag.readers or the author's names.

E1  A derived option that is a member of a library component (dag.method) is read by position in its component, not by
    what the program's author called it.  The first member of a run of consecutive slots of one base is the one the
    program reads (gold/p lift 1.7 to 3.5); every later member has lift 0.01 to 0.2, except the 4th of an 8-member run
    (maximal, 0.56).  Keys e1_*.  The suffix one-hot e1_s_<member> works only if the mask keeps declared member names
    (relfeat mask 'group' or 'group_nogrp'); under mask 'all' it is empty and the positional keys carry the signal.
E2  A comparison is picked when the scope holds two or more numeric labels (37% of such picks against 1.5% to 5%
    otherwise), and right after a library atom that bound fresh numeric labels (dist_pair, margin).  Keys e2_*.
E3  The target of a clause is the deepest relation that nothing read so far has reached.  The head's depth is unknown, so
    the deepest derived option of the row stands in for it: 54% of derived golds that lie deeper than the prefix are at
    the deepest level of those options, against 23% of the options.  Keys e3_*.
E4  While that deepest level is still unread, an option that supplies a type which its options lack and the scope lacks is
    a step to it (an enumerator of Dir/DiagDir/Axis/Sense/D4/C4 for example; lift 2.0 on enumerators).  Keys e4_*.
E5  (off unless env RK2E_SLOT=1) Slot recency: 33% of derived golds are the relation defined last, against 6% of options.
    The earlier ranker excluded slot-distance features, so this block is off by default.  Keys e5_*.
"""
import functools
import os
import re

_SUPER = {'Position': 'Box', 'Offset': 'Box', 'Dir': 'Dir8', 'DiagDir': 'Dir8', 'Axis': 'Axis4', 'DiagAxis': 'Axis4',
          'Nat': 'Number', 'Int': 'Number', 'C4': 'D4'}
_NUM = frozenset(('Int', 'Nat', 'Number'))
_CMP = frozenset(('=', '!=', '<', '<=', '>', '>='))
_ORD = frozenset(('<', '<=', '>', '>='))
# types whose lack is not a reason to look for an enumerator
_PLAIN = frozenset(('Int', 'Nat', 'Number', 'Color', 'Example', 'Ident'))
LIB_MEMBERS = frozenset(
    'cell member node successor score rank probe dual_rank minimal secondary_score maximal cyclic_successor before source box size '
    'domain step gap dir component adjacent extent end ray side tile parts plural value edge reached inner outer observed equal '
    'superset pattern transform join predecessor conflict distance equivalent class exposed boundary target mismatch '
    'source_distance weight shape steps walk enclosed candidate occurrence excess'.split())
SLOT_ON = os.environ.get('RK2E_SLOT') == '1'
_SLOT = re.compile(r'&r(\d+)')
_FRESH = re.compile(r'\(:(\w+) \*(\w+)')
_LASTREL = re.compile(r'^\((?:NOT \()?([^\s()]+)')
_cache = [None, None]


@functools.cache
def _nt(t):
    return str(t).split('(')[0]


def _up(t):
    out = []
    while t:
        out.append(t)
        t = _SUPER.get(t)
    return out


@functools.cache
def _comp(a, b):
    return a == b or b in _up(a) or a in _up(b)


def _slot(o):
    s = o.get('tok', '')
    return int(s[2:]) if s.startswith('&r') and s[2:].isdigit() else None


def _row_info(row):
    if _cache[0] is row:
        return _cache[1]
    opts = row['options']
    scope = [_nt(t) for t in row.get('scope') or []]
    prefix = row.get('prefix') or []
    read = {int(x) for x in _SLOT.findall(' '.join(prefix))}
    pdepth = row.get('prefix_depth') or 0
    info = {'scope': scope, 'read': read, 'pdepth': pdepth}

    # E1: runs of consecutive slots of one base among the members
    groups = {}
    ders = []
    for o in opts:
        if o.get('kind') != 'derived':
            continue
        s = _slot(o)
        if s is None:
            continue
        ders.append((s, o))
        d = o.get('dag') or {}
        if d.get('method') and d.get('base') is not None:
            groups.setdefault(d['base'], []).append(s)
    pos = {}
    for base, slots in groups.items():
        slots.sort()
        runs, cur = [], []
        for s in slots:
            if cur and s != cur[-1] + 1:
                runs.append(cur)
                cur = []
            cur.append(s)
        runs.append(cur)
        for run in runs:
            run_read = [i for i, s in enumerate(run) if s in read]
            for i, s in enumerate(run):
                pos[s] = (i, len(run), bool(run_read), (i - 1) in run_read)
    info['pos'] = pos

    # E3: depth levels
    depths = [(o.get('dag') or {}).get('depth') for _, o in ders]
    depths = [d for d in depths if d is not None]
    maxd = max(depths) if depths else None
    deeper = sorted({d for d in depths if d > pdepth}, reverse=True)
    info['maxd'] = maxd
    info['deeper'] = deeper
    info['top_open'] = bool(maxd is not None and maxd > pdepth)
    info['ntop'] = sum(1 for d in depths if d == maxd) if maxd is not None else 0
    info['maxslot'] = max((s for s, _ in ders), default=None)

    # E4: types that the unread top level lacks and the scope lacks
    lack = set()
    if info['top_open']:
        for s, o in ders:
            d = (o.get('dag') or {}).get('depth')
            if d != maxd or s in read:
                continue
            for t in o.get('types') or []:
                t = _nt(t)
                if t not in _PLAIN and not any(_comp(u, t) for u in scope):
                    lack.add(t)
    info['lack'] = lack

    # E2: the last atom
    nnum = sum(1 for t in scope if t in _NUM)
    cnt = {}
    for t in scope:
        cnt[t] = cnt.get(t, 0) + 1
    info['nnum'] = nnum
    info['eqpairs'] = sum(1 for t, c in cnt.items() if c >= 2 and t not in _NUM)
    numfresh, nfresh = 0, 0
    if prefix:
        last = prefix[-1]
        nfresh = len(_FRESH.findall(last))
        m = _LASTREL.match(last)
        tok = m.group(1) if m else None
        lo = next((o for o in opts if o.get('tok') == tok and o.get('kind') == 'lib'), None) if tok else None
        if lo is not None and lo.get('columns') and lo.get('types'):
            cm = dict(zip(lo['columns'], lo['types']))
            numfresh = sum(1 for col, _ in _FRESH.findall(last) if _nt(cm.get(col, '')) in _NUM)
    info['numfresh'] = numfresh
    info['nfresh'] = nfresh
    _cache[0], _cache[1] = row, info
    return info


def rk2e(row, option):
    """E1 member position in its component run, E2 comparison context, E3 relative depth, E4 target demand, E5 slot recency."""
    info = _row_info(row)
    kind = option.get('kind')
    tok = option.get('tok')
    out = {}

    # ---- E1 ----
    if kind == 'derived':
        s = _slot(option)
        d = option.get('dag') or {}
        p = info['pos'].get(s) if s is not None else None
        if p is not None:
            i, n, base_read, follows = p
            out['e1_member'] = 1.0
            out['e1_idx'] = float(min(i, 6) + 1)
            out['e1_first'] = float(i == 0)
            out['e1_run_n'] = float(min(n, 11))
            out['e1_from_end'] = float(min(n - 1 - i, 10) + 1)
            out['e1_code'] = float(min(n, 11) * 10 + min(i, 9))
            out['e1_base_read'] = float(base_read)
            out['e1_follows_read'] = float(follows)
            out['e1_first_unread_base'] = float(i == 0 and not base_read)
            suf = (option.get('name') or '').partition('.')[2]
            if suf in LIB_MEMBERS:
                out['e1_s_' + suf] = 1.0
        # ---- E3 ----
        depth = d.get('depth')
        maxd = info['maxd']
        if depth is not None and maxd is not None:
            top = depth == maxd
            unread = s is not None and s not in info['read']
            out['e3_top'] = float(top)
            out['e3_gap'] = float(min(maxd - depth, 8))
            out['e3_frac'] = depth / maxd if maxd else 0.0
            if depth > info['pdepth']:
                out['e3_drank'] = float(info['deeper'].index(depth) + 1)
            out['e3_top_unread'] = float(top and info['top_open'] and unread)
            if top:
                out['e3_ntop'] = float(min(info['ntop'], 12))
        if SLOT_ON and s is not None and info['maxslot'] is not None:
            dist = info['maxslot'] - s
            out['e5_dist'] = float(min(dist, 12))
            out['e5_newest'] = float(dist == 0)
            out['e5_last3'] = float(dist < 3)
    out['e3_top_open'] = float(info['top_open'])

    # ---- E2 ----
    if kind == 'op' and tok in _CMP:
        out['e2_cmp'] = 1.0
        out['e2_cmp_ord'] = float(tok in _ORD)
        out['e2_cmp_nnum'] = float(min(info['nnum'], 4))
        out['e2_cmp_num2'] = float(info['nnum'] >= 2)
        out['e2_cmp_eqpairs'] = float(min(info['eqpairs'], 3))
        out['e2_cmp_numfresh'] = float(min(info['numfresh'], 2))
        out['e2_cmp_lastfresh'] = float(min(info['nfresh'], 3))
        out['e2_cmp_numfresh_pair'] = float(info['numfresh'] >= 2)

    # ---- E4 ----
    lack = info['lack']
    if lack and kind in ('lib', 'derived'):
        d = option.get('dag') or {}
        if not (kind == 'derived' and d.get('depth') == info['maxd']):
            ts = [_nt(t) for t in option.get('types') or []]
            hit = sum(1 for m in lack if any(_comp(t, m) for t in ts))
            if hit and kind == 'lib':
                out['e4_supply_n'] = float(hit)
                out['e4_supply_frac'] = hit / len(lack)
                out['e4_supply_enum'] = float(len(ts) == 1)
                new = [t for t in ts if not any(_comp(u, t) for u in info['scope'])]
                out['e4_supply_new'] = float(any(any(_comp(t, m) for m in lack) for t in new))
            elif hit:
                out['e4_dsupply_n'] = float(hit)
    return out


FEATURE_FUNCS = {'rk2e': rk2e}
