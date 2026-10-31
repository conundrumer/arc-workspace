"""G15 Laws of a column pair read as a relation.

Replaces `r3d.d1_relation_laws`, `r1.e3_binary_relation` (`sym`, `density`, `strict_total`), `r6q.q1_diag_stratum`
(`mirror`), `r3c.c4_number_order` and the classes of `r4l.l8_pair_relation`.
"""
import collections as C
import itertools

from featlib import feature

MAX_WORK = 200000
SKIP = ('Example', 'Number')
GRID = ('Position', 'Box')


def _key_indices(p, x):
    """The X columns that hold the Key column of the INIT port at the point (the port's columns of the type parameter
    Key); [] where the point has no key."""
    clause = p.clause
    comp = p.lib.component(clause.component) if clause is not None and clause.component and clause.port else None
    ports = comp['inputs'].get(clause.port) if comp else None
    names = {name for name, _t, param in ports or [] if param == 'Key'}
    return [c.index for c in x.columns() if c.column in names]


def _value(v):
    return v.margins if hasattr(v, 'margins') else v


def _pos_class(a, b):
    dt, dl = abs(a[0] - b[0]), abs(a[2] - b[2])
    if dt == 0 and dl == 0:
        return 'same'
    if dt <= 1 and dl <= 1:
        return 'adj'
    if dt == 0:
        return 'row'
    if dl == 0:
        return 'col'
    return 'diag' if dt == dl else 'other'


def _box_class(a, b):
    if a == b:
        return 'same'
    if all(x <= y for x, y in zip(a, b)) or all(x >= y for x, y in zip(a, b)):
        return 'nest'
    return 'other'


@feature
def g15_pair_laws(p):
    """G15 Laws of a column pair read as a relation. Over the pairs of non-key X columns of one type and one frame tag
    (not Number), each pair's distinct value pairs grouped by the key columns of the component and pooled: `refl`, `sym`
    (the shares of pairs that are reflexive and whose converse is a pair), `trans` (transitivity violations per pair),
    `density` (pairs over the pairs among the elements), `strict_partial` and `strict_total` (1 where every group is a
    strict partial or total order), `mirror` (the largest share, over column pairs, of the pairs with a != b whose
    converse is a pair), `geom_mix` and `geom_adj` (for Position pairs and Box pairs, 1 minus the largest class share
    of the row relation, and the adjacent share; largest over the pairs). Over the pairs of Number columns: `ordered`
    and `mixed` (the pairs weakly ordered in every row with a strict row, and those with a row of each strict order)
    and `mixed_share`. A group of fewer than 3 elements is left out of the keys over pairs of columns of one type (with 2
    elements a relation is trivially dense and total). None without a pair of either kind.

    Needs: partial. Monotone: no.
    """
    x = p.x
    cols = x.columns()
    key = set(_key_indices(p, x))
    free = [c for c in cols if c.index not in key and c.type is not None and c.frame is not None]
    pairs = [(a, b) for a, b in itertools.combinations(free, 2) if a.type == b.type and a.frame == b.frame]
    rel = [(a.index, b.index) for a, b in pairs if a.type not in SKIP]
    nums = [(a.index, b.index) for a, b in pairs if a.type == 'Number']
    if not rel and not nums:
        return None
    models = [m for ms in x.examples(tests=True).values() for m in ms]
    kidx = sorted(key)
    out = {}
    if rel:
        rows = refl = sym = viol = trans_rows = und = maxpairs = 0
        groups = lax = bad = 0
        mirror = 0.0
        geom = []
        for i, j in rel:
            n_off = n_mir = 0
            classes = C.Counter()
            kind = x.columns()[i].type
            for m in models:
                by = C.defaultdict(set)
                for r in m:
                    by[tuple(r[k] for k in kidx)].add((_value(r[i]), _value(r[j])))
                    if kind in GRID and len(_value(r[i])) == 4 and len(_value(r[j])) == 4:
                        a, b = _value(r[i]), _value(r[j])
                        classes[(_pos_class if kind == 'Position' else _box_class)(a, b)] += 1
                for s in by.values():
                    ids = {u for u, _ in s} | {v for _, v in s}
                    if len(ids) < 3:
                        continue
                    succ = C.defaultdict(set)
                    for u, v in s:
                        succ[u].add(v)
                    r_ = sum(u == v for u, v in s)
                    sy = sum(u != v and (v, u) in s for u, v in s)
                    work = sum(len(succ.get(v, ())) for _, v in s)
                    if work <= MAX_WORK:
                        tv = sum((u, c) not in s for u, v in s for c in succ.get(v, ()) if c != u)
                        trans_rows += len(s)
                    else:
                        tv = 0
                    pairs_und = len({frozenset(t) for t in s if t[0] != t[1]})
                    mp = len(ids) * (len(ids) - 1) // 2
                    rows += len(s)
                    refl += r_
                    sym += sy
                    viol += tv
                    und += pairs_und
                    maxpairs += mp
                    groups += 1
                    n_off += len(s) - r_
                    n_mir += sy
                    ok = r_ == 0 and sy == 0 and tv == 0
                    lax += not ok
                    bad += not (ok and pairs_und == mp)
            if n_off:
                mirror = max(mirror, n_mir / n_off)
            n = sum(classes.values())
            if n:
                geom.append((1.0 - max(classes.values()) / n, classes['adj'] / n))
        if rows:
            out.update({'refl': refl / rows, 'sym': sym / rows, 'density': und / maxpairs,
                        'strict_partial': float(lax == 0), 'strict_total': float(bad == 0), 'mirror': mirror})
            if trans_rows:
                out['trans'] = viol / trans_rows
            if geom:
                out['geom_mix'] = max(g[0] for g in geom)
                out['geom_adj'] = max(g[1] for g in geom)
    if nums:
        flat = [r for m in models for r in m]
        if len(flat) >= 2:
            ordered = mixed = 0
            for i, j in nums:
                lt = any(r[i] < r[j] for r in flat)
                gt = any(r[i] > r[j] for r in flat)
                if lt and gt:
                    mixed += 1
                elif lt or gt:
                    ordered += 1
            out.update({'ordered': ordered, 'mixed': mixed, 'mixed_share': mixed / (ordered + mixed) if ordered + mixed else 0.0})
    return out or None
