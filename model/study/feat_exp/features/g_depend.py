"""G18 How the columns of X depend on each other.

Replaces `r4l.l6_association`, `r3h.h2_fanout`, `r1.e5_free_columns`, `r5n.n4_key_counts`,
`r7t.t1_number_displacement` and `r7t.t2_key_partition.uniq`.
"""
import collections as C
import itertools
import math
import operator

from featlib import feature

MAX_ROWS = 50000
CELL_TYPES = ('Position', 'Box')
NOMINAL_SKIP = ('Position', 'Box', 'Offset', 'Example')
# The distances a Number at two cells usually holds: |dr| + |dc|, max(|dr|, |dc|) and the cells strictly between.
METRICS = (
    lambda dr, dc: abs(dr) + abs(dc),
    lambda dr, dc: max(abs(dr), abs(dc)),
    lambda dr, dc: max(abs(dr), abs(dc)) - 1,
)


def _contexts(x):
    """{(assignment, example): the distinct rows of the first model}; a row is a tuple of decoded cells."""
    return {k: ms[0] for k, ms in x.examples(tests=True).items() if ms and ms[0]}


def _entropy(counts):
    n = sum(counts.values())
    return -sum(c / n * math.log2(c / n) for c in counts.values() if c) if n else 0.0


def _key_indices(p, x):
    """The X columns that hold the Key column of the INIT port at the point; [] where the point has no key."""
    clause = p.clause
    comp = p.lib.component(clause.component) if clause is not None and clause.component and clause.port else None
    ports = comp['inputs'].get(clause.port) if comp else None
    names = {name for name, _t, param in ports or [] if param == 'Key'}
    return [c.index for c in x.columns() if c.column in names]


def _value(v):
    return v.margins if hasattr(v, 'margins') else v


def _association(x, ctxs):
    cols = [c.index for c in x.columns() if c.type not in NOMINAL_SKIP and c.type is not None]
    if len(cols) < 2:
        return {}
    acc = C.defaultdict(lambda: [0, 0.0])
    for rows in ctxs.values():
        n = len(rows)
        if n < 6:
            continue
        keys = {c: [_value(r[c]) for r in rows] for c in cols}
        marg = {c: C.Counter(keys[c]) for c in cols}
        for a, b in itertools.combinations(cols, 2):
            ca, cb = marg[a], marg[b]
            if not (2 <= len(ca) <= 12 and 2 <= len(cb) <= 12):
                continue
            joint = C.Counter(zip(keys[a], keys[b]))
            ha, hb = _entropy(ca), _entropy(cb)
            mi = ha + hb - _entropy(joint) - (len(ca) - 1) * (len(cb) - 1) / (2 * n)
            v = min(1.0, max(0.0, mi / min(ha, hb)))
            acc[a, b][0] += n
            acc[a, b][1] += n * v
    if not acc:
        return {}
    types = {c.index: c.type for c in x.columns()}
    vals = {k: s / w for k, (w, s) in acc.items()}
    out = {'assoc_mean': sum(vals.values()) / len(vals), 'assoc_min': min(vals.values()),
           'assoc_low': sum(v < 0.05 for v in vals.values())}
    dd = [v for (a, b), v in vals.items() if types[a] in ('Dir', 'DiagDir') and types[b] in ('Dir', 'DiagDir')]
    if dd:
        out['assoc_dir_mean'] = sum(dd) / len(dd)
    return out


def _codes(values):
    """Ints that are equal for the values that are equal (as the values are in a dict), so a test of equality or a
    key reads an int, not a value that hashes through Python code. A value's int is the place of its first row."""
    return list(map({}.setdefault, values, range(len(values))))


def _determines(ci, cj, ck=None):
    """Whether the codes ck + ci determine the code cj, row by row: no two rows with equal ck and ci differ in cj."""
    return all(map(operator.eq, map({}.setdefault, ci if ck is None else zip(ck, ci), cj), cj))


def _determination(x, ctxs, key):
    """The determination keys. Where the point has Key columns (`key`), a column function is held per key, so
    `det_top` and `det_share` are left out and `det_top_key` and `det_share_key` take their place: the same shares over the
    columns that are not Key columns, a column determining another together with the row's key."""
    cols = [c.index for c in x.columns() if c.type != 'Example']
    n = len(cols)
    if n < 2:
        return {}
    free = [i for i in cols if i not in key]
    m = len(free)
    acc = {'fan0': 0.0, 'fan_max': 0.0, 'det_top': 0.0, 'det_share': 0.0, 'n_det': 0.0}
    by_key = {'det_top_key': 0.0, 'det_share_key': 0.0}
    used = 0
    for rows in ctxs.values():
        used += 1
        code = {}
        for i in cols:
            code[i] = _codes([r[i] for r in rows])
        distinct = [len(set(code[i])) for i in cols]
        acc['fan_max'] += max(len(rows) / d for d in distinct)
        det = 0
        per = [0] * n
        for a, i in enumerate(cols):
            for b, j in enumerate(cols):
                if a != b:
                    ok = _determines(code[i], code[j])
                    det += ok
                    per[a] += ok
        top = max(per)
        acc['det_top'] += top / (n - 1)
        acc['fan0'] += min(len(rows) / distinct[a] for a in range(n) if per[a] == top)
        acc['det_share'] += det / (n * (n - 1))
        acc['n_det'] += det
        if key and m >= 2:
            ck = list(zip(*[code[k] if k in code else _codes([r[k] for r in rows]) for k in key]))
            held = [[i != j and _determines(code[i], code[j], ck) for j in free] for i in free]
            by_key['det_top_key'] += max(map(sum, held)) / (m - 1)
            by_key['det_share_key'] += sum(map(sum, held)) / (m * (m - 1))
    if not used:
        return {}
    if key:
        del acc['det_top'], acc['det_share']
        if m >= 2:
            acc.update(by_key)
    return {k: v / used for k, v in acc.items()}


def _free(x, ctxs):
    cols = [c.index for c in x.columns() if c.type != 'Example']
    if len(cols) < 2:
        return {}
    free = {c: True for c in cols}
    seen = {c: False for c in cols}
    for rows in ctxs.values():
        proj = set(zip(*[_codes([r[c] for r in rows]) for c in cols]))  # only equality is read below
        if len(proj) < 2:
            continue
        for a, c in enumerate(cols):
            if not free[c]:
                continue
            dom = {r[a] for r in proj}
            if len(dom) < 2:
                continue
            rest = {r[:a] + r[a + 1:] for r in proj}
            seen[c] = True
            if len(proj) != len(dom) * len(rest):
                free[c] = False
    count = sum(1 for c in cols if free[c] and seen[c])
    return {'free_cols': count, 'free_share': count / len(cols)}


def _by_key(p, x, ctxs):
    key = _key_indices(p, x)
    if not key:
        return {}
    other = [c.index for c in x.columns() if c.index not in key and c.type in CELL_TYPES]
    uni, spr, cvs = [], [], []
    n_val = n_one = n_keys = 0
    for rows in ctxs.values():
        counts = C.Counter(tuple(r[k] for k in key) for r in rows)
        if len(counts) < 2:
            continue
        vals = list(counts.values())
        mean = sum(vals) / len(vals)
        sd = math.sqrt(sum((c - mean) ** 2 for c in vals) / len(vals))
        uni.append(len(set(vals)) == 1)
        spr.append(len(set(vals)) / len(vals))
        cvs.append(sd / mean)
        if other:
            groups = C.defaultdict(set)
            for r in rows:
                groups[tuple(_value(r[i]) for i in other)].add(tuple(r[k] for k in key))
            n_val += len(groups)
            n_one += sum(len(ks) == 1 for ks in groups.values())
            n_keys += sum(len(ks) for ks in groups.values())
    if not uni:
        return {}
    n = len(uni)
    out = {'key_uniform': sum(uni) / n, 'key_spread': sum(spr) / n, 'key_cv': sum(cvs) / n}
    if n_val:
        out['key_cells_one'] = n_one / n_val
        out['key_cells_mean'] = n_keys / n_val
    return out


def _displacement(x, ctxs):
    cols = x.columns()
    nums = [c.index for c in cols if c.type == 'Number']
    pos = [c for c in cols if c.type in CELL_TYPES and c.frame]
    dirs = [c.index for c in cols if c.type in ('Dir', 'DiagDir')]
    pairs = [(a.index, b.index) for a, b in itertools.combinations(pos, 2) if a.type == b.type and a.frame == b.frame]
    if not nums or not pairs or sum(len(r) for r in ctxs.values()) > MAX_ROWS:
        return {}
    best_pure, best_tested, best_metric = None, 0.0, 0.0
    for k in nums:
        for i, j in pairs:
            groups = C.defaultdict(lambda: C.defaultdict(set))
            triples = set()
            for ck, rows in ctxs.items():
                if len({r[k] for r in rows}) < 2:
                    continue
                for r in rows:
                    a, b, v = r[i], r[j], r[k]
                    if not hasattr(a, 'row') or not hasattr(b, 'row') or not isinstance(v, int):
                        continue
                    groups[ck, (b.row - a.row, b.col - a.col, *(r[q] for q in dirs))][(a.margins, b.margins)].add(v)
                    triples.add((ck, a.margins, b.margins, v))
            if not triples:
                continue
            npairs = sum(len(g) for g in groups.values())
            tested = pure = 0
            for g in groups.values():
                if len(g) < 2:
                    continue
                tested += len(g)
                if len({v for vals in g.values() for v in vals}) == 1:
                    pure += len(g)
            met = max(sum(f(bm[0] - am[0], bm[2] - am[2]) == v for ck, am, bm, v in triples) / len(triples)
                      for f in METRICS)
            best_metric = max(best_metric, met)
            if tested:
                share = pure / tested
                if best_pure is None or (share, tested / npairs) > (best_pure, best_tested):
                    best_pure, best_tested = share, tested / npairs
    out = {}
    if best_pure is not None:
        out['disp_pure'] = best_pure
    if best_metric:
        out['disp_metric'] = best_metric
    return out


@feature
def g18_depend(p):
    """G18 How the columns of X depend on each other, per context (an example's distinct rows in the first model),
    averaged over contexts. Graded dependence of nominal columns (not Position, Box, Offset or Example), the adjusted
    normalized mutual information of each pair in contexts of 6 or more rows: `assoc_mean`, `assoc_min`, `assoc_low`,
    `assoc_dir_mean`. Exact determination: `det_top` (the largest share of the other columns that one column determines),
    `fan0` (rows per value of such a column), `fan_max` (the largest rows per value), `det_share` and `n_det` (the
    ordered column pairs where the first determines the second). At a point with a Key column the table holds a
    function per key, so `det_top` and `det_share` are absent and `det_top_key` and `det_share_key` take their place:
    the same shares over the columns that are not Key columns, where a column determines another together with the
    row's key. `free_cols` and `free_share`: the columns that
    take every combination with the other columns' rows. At a point with a Key column: `key_uniform`, `key_spread`,
    `key_cv` (rows per key) and `key_cells_one`, `key_cells_mean` (the share of distinct non-key cell tuples under
    one key, and the mean number of keys per tuple). `disp_pure` and `disp_metric`: a Number column as a function of
    the displacement between two cells of one frame (and, for `disp_pure`, of the row's Dir and DiagDir values). None without a context or any of those.

    Needs: partial. Monotone: no (a determination stays under a filter, but a new column can end it).
    """
    x = p.x
    ctxs = _contexts(x)
    if not ctxs:
        return None
    out = {}
    for part in (_association, _free):
        out.update(part(x, ctxs))
    out.update(_determination(x, ctxs, _key_indices(p, x)))
    out.update(_by_key(p, x, ctxs))
    out.update(_displacement(x, ctxs))
    return out or None
