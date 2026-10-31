"""Explorer a: depth-target, type-supply and open-variable features of the relation pick.

One function, rk1a(row, option) -> {key: float}.  Row-level work is done once per row and cached; the per-option work is
a few set look-ups.  Types are compared by their base name (text before '(').  Subtype relation: the one of
relfeat.py (Position < Box, Dir/DiagDir < Dir8, Axis/DiagAxis < Axis4, Nat/Int < Number, ...).

Hypotheses (keys a<n>_*):

A1  The head of the clause has depth D (point_group['depth']), so every relation the clause reads has depth < D and at
    least one has depth D-1.  A derived option with dag.depth >= D is impossible; one with dag.depth == D-1 is a target.
A2  While prefix_depth < D-1 the clause has not read a target yet; a candidate that supplies a column type that a
    target still lacks (the scope has no comparable type) is a step toward it.
A4  A derived option nobody reads yet (dag.readers == 0), and a method of a base that the prefix reads
    through another method, is a likely next read.
A3  Same as A2 but through one lib relation: the candidate's new type is linked, by the signature of some lib option, to a
    type that a target lacks (a 2-step chain, for example axis4_elem -> axis4_of -> Dir8).
A5  A slot type counts as met when some scope type is comparable to it (either one is a subtype of the other).  The
    exact-membership test misses Position/Box and Axis/Axis4.
A6  A variable bound in the prefix and not read by any later atom is open.  A candidate that has a column type that an
    open variable can fill is likely to read it.
"""
import functools
import re

_SUPER = {'Position': 'Box', 'Offset': 'Box', 'Dir': 'Dir8', 'DiagDir': 'Dir8', 'Axis': 'Axis4', 'DiagAxis': 'Axis4',
          'Nat': 'Number', 'Int': 'Number'}
_ATOM = re.compile(r'\((NOT )?\(?([^\s():][^\s()]*)')
_COL = re.compile(r'\(:(\w+)\s+([^()]*)\)')
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
def _sub(a, b):
    return b in _up(a)


@functools.cache
def _comp(a, b):
    return a == b or _sub(a, b) or _sub(b, a)


def _is_num(t):
    return t == 'Number' or _SUPER.get(t) == 'Number'


def _lib_by_tok(row):
    return {o['tok']: o for o in row['options'] if o.get('kind') == 'lib'}


def _parse_prefix(row):
    """Returns (bound, read): bound = [(var, atom_index, tok, column)] in order; read = {var: last atom index that reads it}."""
    bound, read = [], {}
    for i, a in enumerate(row.get('prefix') or []):
        m = _ATOM.match(a)
        if not m:
            continue
        name = m.group(2)
        if name == 'NOT':
            m2 = _ATOM.match(a[a.index('(', 1):]) if a.count('(') > 1 else None
            name = m2.group(2) if m2 else name
        tok = name.partition('.')[0]
        for col, args in _COL.findall(a):
            for v in args.split():
                if v.startswith('*'):
                    bound.append((v[1:], i, tok, col))
                elif v and not v[0].isdigit() and v[0] not in '-"':
                    read[v] = i
    return bound, read


def _row_info(row):
    if _cache[0] is row:
        return _cache[1]
    scope = [_nt(t) for t in row.get('scope') or []]
    opts = row['options']
    D = (row.get('point_group') or {}).get('depth')
    pdepth = row.get('prefix_depth')
    prefix_text = ' '.join(row.get('prefix') or [])
    read_toks = set(re.findall(r'&r\d+', prefix_text)) | set(t for t in re.findall(r'\((?:NOT \()?([^\s()]+)', prefix_text))
    info = {'scope': scope, 'D': D, 'pdepth': pdepth, 'read_toks': read_toks}

    # D1: open variables
    lib = _lib_by_tok(row)
    bound, read = _parse_prefix(row)
    open_lib, n_open, n_open_der, n_der = set(), 0, 0, 0
    lib_types = []
    for v, i, tok, col in bound:
        is_open = not (v in read and read[v] > i)
        o = lib.get(tok)
        if o is not None and o.get('columns') and col in o['columns']:
            t = _nt(o['types'][o['columns'].index(col)])
            lib_types.append(t)
            if is_open:
                open_lib.add(t)
        elif tok.startswith('&r'):
            n_der += 1
            n_open_der += is_open
        n_open += is_open
    pool = list(scope)
    for t in lib_types:
        for j, u in enumerate(pool):
            if u == t:
                del pool[j]
                break
    open_types = set(open_lib)
    if n_der and n_open_der == n_der:
        open_types |= set(pool)
    info['open_types'] = open_types
    info['n_open'] = n_open

    # A2/A3: targets and their lacking types
    lacking = {}
    n_target = 0
    target_open = D is not None and pdepth is not None and pdepth < D - 1
    if target_open:
        for o in opts:
            d = o.get('dag') or {}
            if o.get('kind') == 'derived' and d.get('depth') == D - 1 and o['tok'] not in read_toks:
                n_target += 1
                miss = {_nt(t) for t in o.get('types') or []}
                miss = {t for t in miss if not _is_num(t) and not any(_comp(u, t) for u in scope)}
                for t in miss:
                    lacking[t] = lacking.get(t, 0) + 1
    info['target_open'] = target_open
    info['n_target'] = n_target
    info['lacking'] = lacking

    # links: type x -> types y that some lib signature puts next to a supertype of x
    link = {}
    if lacking:
        sigs = [[_nt(t) for t in (o.get('types') or [])] for o in opts if o.get('kind') == 'lib']
        for sig in sigs:
            for i, a in enumerate(sig):
                for j, b in enumerate(sig):
                    if i != j:
                        link.setdefault(a, set()).add(b)
    info['link'] = link
    _cache[0], _cache[1] = row, info
    return info


def rk1a(row, option):
    info = _row_info(row)
    scope, D, pdepth = info['scope'], info['D'], info['pdepth']
    types = [_nt(t) for t in option.get('types') or []]
    d = option.get('dag') or {}
    out = {}

    # A1
    depth = d.get('depth')
    kind = option.get('kind')
    if D is not None and depth is not None:
        out['a1_infeasible'] = float(depth >= D)
        out['a1_is_target'] = float(depth == D - 1)
        out['a1_slack'] = float(D - depth)
        out['a1_target_unread'] = float(depth == D - 1 and info['target_open'] and option['tok'] not in info['read_toks'])
    out['a1_target_open'] = float(info['target_open'])
    out['a1_remaining'] = float(D - 1 - pdepth) if info['target_open'] else 0.0
    out['a1_not_k1_target'] = float(option.get('tok') == 'NOT' and row.get('k') == 1 and info['n_target'] >= 1)

    # C1
    fit = [any(_comp(u, t) for u in scope) for t in types]
    out['a5_fit_n'] = float(sum(fit))
    out['a5_fit_frac'] = sum(fit) / len(fit) if fit else 0.0
    out['a5_new_n'] = float(len(fit) - sum(fit))
    out['a5_fit_any'] = float(any(fit))
    out['a5_none_fit'] = float(bool(types) and not any(fit) and row.get('k', 1) > 1)

    # A2 / A3
    lacking = info['lacking']
    if lacking and depth != (D - 1 if D is not None else None):
        new = [t for t, f in zip(types, fit) if not f]
        hit1 = sum(c for m, c in lacking.items() if any(_comp(t, m) for t in types))
        out['a2_supply_n'] = float(hit1)
        out['a2_supply_frac'] = hit1 / max(info['n_target'], 1)
        out['a2_supply_new'] = float(any(any(_comp(t, m) for m in lacking) for t in new))
        link = info['link']
        reach = set()
        for t in new:
            for u in _up(t):
                reach |= link.get(u, set())
        hit2 = sum(c for m, c in lacking.items() if any(_comp(y, m) for y in reach))
        out['a3_link_n'] = float(hit2)
        out['a3_link_frac'] = hit2 / max(info['n_target'], 1)
        out['a3_link_only'] = float(hit2 > 0 and hit1 == 0 and bool(new))

    # D1
    ot = info['open_types']
    if ot:
        hit = sum(any(_sub(u, t) or _sub(t, u) for u in ot) for t in types)
        out['a6_open_hit'] = float(hit)
        out['a6_open_frac'] = hit / len(types) if types else 0.0
    out['a6_n_open'] = float(info['n_open'])

    # A4: readers and unread siblings (dag fields that dag_options.py does not read)
    if d:
        out['a4_unread'] = float(d.get('readers') == 0)
        out['a4_readers'] = float(min(d.get('readers') or 0, 3))
        out['a4_sibling_unread'] = float(bool(d.get('sibling')) and bool(d.get('method')) and option['tok'] not in info['read_toks']
                                         and d.get('base') in set(row.get('prefix_bases') or []))
    return out


FEATURE_FUNCS = {'rk1a': rk1a}
