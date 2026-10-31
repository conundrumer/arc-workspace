"""Explorer d (round 2): pairs of fresh labels, derived generators, and the grammar state of the clause.

The features read `prefix`, `scope`, `k`, and per option `tok`, `kind`, `types`, `columns`, `p`, `dag.method`.  They read no
`readers`, no depth of the point and no author name; two relation tokens or two label names are only compared for equality.
Labels are rebuilt from `prefix` by rk1c._labels (the round-1 helper); a label is "unread" when no later atom reads it.

Hypotheses (keys d<n>_*):

D1  Pair combiners.  A comparison (labels read at most once), or a library relation that joins two box-like labels (compose), is picked when the clause holds
    two unread labels of one type that come from different atoms, most of all when one of them is bound by the last atom and
    the other by an earlier atom, or both are the same result column of two atoms of one relation (a "twin" pair: the
    relation was read twice).  Keys d1_cmp_*, d1_take_pairs, d1_take_twin, d1_box_*.
D2  Derived generators.  A derived relation that is not a member of a base and that no label of the clause fits (all its
    columns are new) starts a new generator and is picked about twice as often as the model says; a member of a base
    (dag.method) that no label fits is never picked.  Keys d2_*.
D3  Grammar state of the clause.  The kind of the last atom, whether `input` was read, and whether NOT was used decide
    NOT, a derived relation and `input`: NOT after a derived atom is rare, NOT after `input` or after NOT is common.
    Keys d3_*.
D5  Context of the sampler's share.  The rank of an option by `p` in its row, its log share relative to the row's top, and the
    mass of its own kind.  Keys d5_*.
"""
import importlib.util
import math
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('rk1c_for_rk2d', os.path.join(_HERE, 'rk1c.py'))
_c1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_c1)

_ATOM = re.compile(r'^\((NOT )?\(?([^\s():][^\s()]*)')
_LEAF = re.compile(r'\(:(\w+) (\*?)([A-Za-z_]\w*)(?=[ )])')
_CMP = frozenset(('=', '!=', '<', '<=', '>', '>='))
_NUM = frozenset(('Int', 'Nat', 'Number'))
_BOX = frozenset(('Box', 'Position', 'Offset'))
_cache = [None, None]


def _compat(a, b):
    return a == b or (a in _NUM and b in _NUM)


def _cls(o):
    tok = o.get('tok')
    if tok == 'NOT':
        return 'not'
    if tok in _CMP:
        return 'cmp'
    if tok == 'input':
        return 'input'
    return 'der' if o.get('kind') == 'derived' else 'lib'


def _row(row):
    if _cache[0] is row:
        return _cache[1]
    prefix = row.get('prefix') or []
    n = len(prefix)
    try:
        labs = _c1._labels(row)
    except Exception:
        labs = []
    all_t = [l[1] for l in labs]
    unread = [l for l in labs if l[3] == 0 and l[1] is not None]
    # atoms: relation token and the star-bound label names by leaf position
    atoms = []
    last = 'none'
    n_input = n_not = n_cmp = n_lib = n_der = 0
    for ai, a in enumerate(prefix):
        m = _ATOM.match(a)
        if not m:
            kind = 'cmp'
            atoms.append((None, {}))
            n_cmp += 1
        else:
            rel = m.group(2)
            if m.group(1):
                kind = 'not'
                n_not += 1
            elif rel.startswith('&r'):
                kind = 'der'
                n_der += 1
            elif rel == 'input':
                kind = 'input'
                n_input += 1
            elif rel in _CMP:
                kind = 'cmp'
                n_cmp += 1
            else:
                kind = 'lib'
                n_lib += 1
            stars = {}
            for li, (col, star, name) in enumerate(_LEAF.findall(a)):
                if star:
                    stars[li] = name
            atoms.append((rel, stars))
        last = kind
    # twin pairs: the same leaf position of two atoms of one relation, both labels read at most once
    byname = {l[0]: l for l in labs}
    twins = []
    for i in range(n):
        ri, si = atoms[i]
        if ri is None or ri == 'input':
            continue
        for j in range(i + 1, n):
            rj, sj = atoms[j]
            if rj != ri:
                continue
            for li, v in sj.items():
                u = si.get(li)
                if u is None or u == v:
                    continue
                a, b = byname.get(u), byname.get(v)
                if a and b and a[3] <= 1 and b[3] <= 1:
                    twins.append((a[1], b[1]))
    # unread pairs from different atoms, by type pair
    pair_types = {}
    fresh_old = both_last = n_pairs = fresh_old_num = 0
    for x in range(len(unread)):
        for y in range(x + 1, len(unread)):
            a, b = unread[x], unread[y]
            if a[2] == b[2]:
                continue
            key = tuple(sorted((a[1], b[1])))
            pair_types[key] = pair_types.get(key, 0) + 1
    # pairs for comparisons: labels read at most once, bound by different atoms, one of them bound by the last atom
    semi = [l for l in labs if l[3] <= 1 and l[1] is not None]
    semi_pairs = fresh_old0 = 0
    for x in range(len(semi)):
        for y in range(x + 1, len(semi)):
            a, b = semi[x], semi[y]
            if not _compat(a[1], b[1]):
                continue
            semi_pairs += 1
            if a[2] != b[2] and (a[2] == n - 1) != (b[2] == n - 1):
                fresh_old += 1
                fresh_old_num += a[1] in _NUM
                fresh_old0 += a[3] == 0 and b[3] == 0
    n_pairs = semi_pairs
    for x in range(len(unread)):
        for y in range(x + 1, len(unread)):
            a, b = unread[x], unread[y]
            if a[2] == b[2] == n - 1 and _compat(a[1], b[1]):
                both_last += 1
    box_un = [l for l in unread if l[1] in _BOX]
    box_atoms = len({l[2] for l in box_un})
    # p context
    ps = [o.get('p') or 0.0 for o in row['options']]
    order = sorted(range(len(ps)), key=lambda j: -ps[j])
    rank = {j: i for i, j in enumerate(order)}
    top = math.log(max(ps[order[0]], 1e-12)) if ps else 0.0
    by_kind = {}
    for j, o in enumerate(row['options']):
        by_kind.setdefault(o.get('kind'), []).append(j)
    krank, kmass = {}, {}
    tot = sum(ps) or 1.0
    for kd, js in by_kind.items():
        js = sorted(js, key=lambda j: -ps[j])
        for i, j in enumerate(js):
            krank[j] = i
        kmass[kd] = sum(ps[j] for j in js) / tot
    info = dict(n=n, labs=labs, all_t=all_t, last=last, n_input=n_input, n_not=n_not, n_cmp=n_cmp, n_lib=n_lib, n_der=n_der,
                twins=twins, pair_types=pair_types, fresh_old=fresh_old, fresh_old_num=fresh_old_num, both_last=both_last,
                n_pairs=n_pairs, fresh_old0=fresh_old0, box_n=len(box_un), box_atoms=box_atoms, rank=rank, top=top, krank=krank, kmass=kmass,
                optidx={id(o): j for j, o in enumerate(row['options'])})
    _cache[0], _cache[1] = row, info
    return info


def _take_pairs(cols, pair_types):
    """Number of unread pairs (different atoms) that two distinct columns of the option can take."""
    if len(cols) < 2:
        return 0
    tot = 0
    for (ta, tb), cnt in pair_types.items():
        ok = False
        for i, ci in enumerate(cols):
            if not _c1._fits(ta, ci):
                continue
            for j, cj in enumerate(cols):
                if i != j and _c1._fits(tb, cj):
                    ok = True
                    break
            if ok:
                break
        if not ok:
            for i, ci in enumerate(cols):
                if not _c1._fits(tb, ci):
                    continue
                for j, cj in enumerate(cols):
                    if i != j and _c1._fits(ta, cj):
                        ok = True
                        break
                if ok:
                    break
        if ok:
            tot += cnt
    return tot


def rk2d(row, o):
    """D1 pair combiners, D2 derived generators, D3 grammar state of the clause, D5 context of the sampler's share."""
    info = _row(row)
    out = {}
    kind = o.get('kind')
    cls = _cls(o)
    lk = info['last']
    k = row.get('k') or 1

    # D3: the grammar state
    if lk != 'none':
        out['d3_last_' + lk] = 1.0
        out['d3_x_%s_%s' % (cls, lk)] = 1.0
    out['d3_n_input'] = float(min(info['n_input'], 2))
    out['d3_n_not'] = float(min(info['n_not'], 2))
    out['d3_n_lib'] = float(min(info['n_lib'], 4))
    if cls == 'not':
        out['d3_not_ninput'] = float(min(info['n_input'], 2))
        out['d3_not_nlib'] = float(min(info['n_lib'], 4))
        out['d3_not_nder'] = float(min(info['n_der'], 4))
        out['d3_not_after_not'] = float(lk == 'not')
        out['d3_not_after_der'] = float(lk == 'der')
    if cls == 'input':
        out['d3_input_again'] = float(info['n_input'] > 0)

    # D5: context of p
    j = info['optidx'].get(id(o))
    if j is not None:
        out['d5_prank'] = math.log2(1 + info['rank'][j])
        out['d5_dlogp'] = math.log(max(o.get('p') or 0.0, 1e-12)) - info['top']
        out['d5_kind_prank'] = math.log2(1 + info['krank'].get(j, 0))
        out['d5_kind_mass'] = info['kmass'].get(kind, 0.0)

    if k <= 1 or not info['labs']:
        if kind == 'derived' and (o.get('dag') or {}).get('method') is not None and k <= 1:
            out['d2_k1_method'] = float(bool((o.get('dag') or {}).get('method')))
        return out

    # D1 and D2 need labels
    if cls == 'cmp':
        out['d1_cmp_fresh_old'] = float(min(info['fresh_old'], 3))
        out['d1_cmp_fresh_old_num'] = float(min(info['fresh_old_num'], 3))
        out['d1_cmp_fresh_old0'] = float(min(info['fresh_old0'], 3))
        out['d1_cmp_both_last'] = float(min(info['both_last'], 3))
        out['d1_cmp_twin'] = float(min(len(info['twins']), 3))
        out['d1_cmp_stale'] = float(info['n_pairs'] > 0 and info['fresh_old'] == 0 and info['both_last'] == 0)
        out['d1_cmp_nopair'] = float(info['n_pairs'] == 0 and not info['twins'])
        return out
    if cls == 'not':
        out['d1_not_pairs'] = float(min(info['n_pairs'], 3))
        return out
    cols = _c1._arity_types(o)
    if not cols:
        return out
    tp = _take_pairs(cols, info['pair_types'])
    out['d1_take_pairs'] = float(min(tp, 4))
    if info['twins']:
        tw = 0
        for (ta, tb) in info['twins']:
            a_ok = [i for i, c in enumerate(cols) if _c1._fits(ta, c)]
            b_ok = [i for i, c in enumerate(cols) if _c1._fits(tb, c)]
            if any(i != j2 for i in a_ok for j2 in b_ok):
                tw += 1
        out['d1_take_twin'] = float(min(tw, 3))
    nbox = sum(1 for c in cols if c in _BOX or c == 'Box')
    if nbox >= 2 and kind == 'lib':
        out['d1_box_atoms'] = float(min(info['box_atoms'], 3))
        out['d1_box_atoms_ar3'] = float(min(info['box_atoms'], 3)) if len(cols) >= 3 else 0.0
        out['d1_box_un_n'] = float(min(info['box_n'], 4))

    # D2: derived generators and members that nothing fits
    if kind == 'derived':
        free = _c1._free_cols(cols, info['all_t'])
        nfed = len(cols) - len(free)
        method = bool((o.get('dag') or {}).get('method'))
        if nfed == 0:
            if method:
                out['d2_member_unfed'] = 1.0
            else:
                out['d2_gen'] = 1.0
                out['d2_gen_nfree'] = float(min(len(free), 4))
        else:
            out['d2_member_fed' if method else 'd2_base_fed'] = 1.0
    return out


FEATURE_FUNCS = {'rk2d': rk2d}
