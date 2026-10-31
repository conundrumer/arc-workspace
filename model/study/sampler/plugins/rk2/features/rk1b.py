"""Explorer b: how well the scope feeds an option's columns, and what the option yields.

Hypotheses (keys of the dict that rk1b returns):
b1  Number pair: an option with two or more columns of numeric type that the scope does not feed (a distance pair) is chosen
    when its leading column is fed.  Keys b1_numun, b1_pair, b1_lead_pair.
b2  Scope feeding for every library relation, with the subtype direction right (a Position label fills a Box column).
    Keys b2_fed, b2_run, b2_lead_part, b2_yield, b2_cov, b2_cov_full.
b3  Narrowing: a column whose type is a strict subtype of a label type in scope (C4 under D4; Dir or DiagDir under Dir8;
    Axis or DiagAxis under Axis4) restricts that label.  Keys b3_narrow_d4, b3_narrow_union.
b4  Closing test: every column is fed by the scope.  Key b4_allfed.
b5  Keyless count at k=1: NOT first in a clause when a derived relation with the single column type Nat exists.
    Keys b5_k1_not_nat, b5_k1_nat_unary.
b6  Clause shape: how many library and derived atoms the prefix holds; a library option right after derived atoms only.
    Keys b6_prefix_lib_n, b6_prefix_der_n, b6_first_lib.
b8  Unread derived relations (dag.readers == 0): option is unread and not in the prefix; row has pending unread options; the
    prefix already read one.  Keys b8_rd0, b8_pending, b8_discharged.
"""
import functools
import re

_UP = {'Position': 'Box', 'Offset': 'Box', 'Dir': 'Dir8', 'DiagDir': 'Dir8', 'Axis': 'Axis4', 'DiagAxis': 'Axis4',
       'Nat': 'Number', 'Int': 'Number', 'C4': 'D4'}
_NUM = frozenset(('Number', 'Nat', 'Int'))
_UNION_UP = {'Dir': 'Dir8', 'DiagDir': 'Dir8', 'Axis': 'Axis4', 'DiagAxis': 'Axis4'}
_ATOM = re.compile(r'^\((?:NOT )?\(?([^\s():][^\s()]*)')
_SLOT = re.compile(r'&r\d+')
_cache = [None, None]


@functools.cache
def _t(x):
    return str(x).split('(')[0]


@functools.cache
def _sub(a, b):
    while a:
        if a == b:
            return True
        a = _UP.get(a)
    return False


def _row(row):
    if _cache[0] is row:
        return _cache[1]
    scope = [_t(s) for s in row.get('scope') or []]
    sset = set(scope)
    opts = row.get('options') or []
    by = {o.get('tok'): o for o in opts}
    optoks = {o.get('tok'): o.get('kind') for o in opts}
    lib_n = der_n = 0
    prefix_slots = set()
    discharged = 0
    for a in row.get('prefix') or []:
        m = _ATOM.match(a)
        name = m.group(1).split('.')[0] if m else ''
        if name.startswith('&r'):
            der_n += 1
            prefix_slots.add(name)
            o = by.get(name)
            if o and (o.get('dag') or {}).get('readers') == 0:
                discharged = 1
        elif optoks.get(name) == 'lib' and name not in ('input', 'ex_input', 'ex_output'):
            lib_n += 1
    pending = sum(1 for o in opts if o.get('kind') == 'derived' and (o.get('dag') or {}).get('readers') == 0
                  and o.get('tok') not in prefix_slots)
    nat_unary = sum(1 for o in opts if o.get('kind') == 'derived' and [_t(t) for t in o.get('types') or []] == ['Nat'])
    d = {'scope': sset, 'nscope': len(sset), 'lib_n': lib_n, 'der_n': der_n, 'prefix_slots': prefix_slots,
         'discharged': discharged, 'pending': pending, 'nat_unary': nat_unary, 'k': row.get('k') or 0,
         'has_prefix': bool(row.get('prefix'))}
    _cache[0], _cache[1] = row, d
    return d


def rk1b(row, o):
    c = _row(row)
    kind = o.get('kind')
    out = {'b6_prefix_lib_n': float(c['lib_n']), 'b6_prefix_der_n': float(c['der_n']), 'b8_pending': float(c['pending']),
           'b8_discharged': float(c['discharged'])}
    if kind == 'derived':
        dag = o.get('dag') or {}
        out['b8_rd0'] = float(dag.get('readers') == 0 and o.get('tok') not in c['prefix_slots'])
    if kind == 'op':
        if o.get('tok') == 'NOT' and c['k'] == 1 and c['nat_unary']:
            out['b5_k1_not_nat'] = 1.0
        return out
    types = [_t(t) for t in o.get('types') or []]
    if not types:
        return out
    S = c['scope']
    n = len(types)
    fed = [any(_sub(s, t) for s in S) for t in types]
    nfed = sum(fed)
    unfed = [t for t, f in zip(types, fed) if not f]
    numun = sum(t in _NUM for t in unfed)
    out['b1_numun'] = float(numun)
    out['b1_pair'] = float(numun >= 2)
    out['b2_fed'] = float(nfed)
    cov = sum(1 for s in S if any(_sub(s, t) for t in types)) / c['nscope'] if S else 0.0
    out['b2_cov'] = cov
    out['b2_cov_full'] = float(bool(S) and cov == 1.0)
    out['b4_allfed'] = float(nfed == n)
    nd4 = sum(1 for t in types if t == 'C4' and 'D4' in S)
    nun = sum(1 for t in types if t in _UNION_UP and _UNION_UP[t] in S and t not in S)
    out['b3_narrow_d4'] = float(nd4)
    out['b3_narrow_union'] = float(nun)
    if kind == 'derived':
        if c['k'] == 1 and types == ['Nat']:
            out['b5_k1_nat_unary'] = 1.0
        return out
    # library relation: the column order is the relation's own (inputs first)
    run = 0
    for f in fed:
        if not f:
            break
        run += 1
    lead = bool(fed[0])
    out['b2_run'] = float(run)
    out['b2_lead_part'] = float(lead and nfed < n)
    out['b2_yield'] = float(n - nfed) if lead else 0.0
    out['b1_lead_pair'] = float(lead and numun >= 2)
    out['b6_first_lib'] = float(c['lib_n'] == 0 and c['der_n'] > 0 and o.get('tok') not in ('input',))
    return out


FEATURE_FUNCS = {'rk1b': rk1b}
