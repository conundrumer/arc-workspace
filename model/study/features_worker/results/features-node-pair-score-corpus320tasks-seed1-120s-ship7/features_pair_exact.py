"""Exact row-join pair features (candidate beside features_pair.py, which uses sketches).

  tb = tables(node, pairs)         # once per node: the node's rows keyed per column. Reads the node's rows, so one table read.
  d  = features_exact(ta, tb)      # {name: float}, symmetric. Joins on the keys of columns of one type, with the example as part of the key.

Row-level joins: a row of A matches when a row of B has the same (example, value) in the joined column.
For a Position column the value is the cell. The column pair joined is the first column of each shared type
(the first two Position columns count as two types, so a table with two Position columns offers two keys).
"""
from collections import Counter

WIDE = {'Position': 4, 'Box': 4}
MAXC = 2

FEATURES = {
    'ex_semi_lo': 'Largest over joinable column pairs of the smaller of: share of A rows with a match in B, share of B rows with a match in A.',
    'ex_semi_hi': 'Same pair, the larger of the two shares.',
    'ex_join_log': 'log2(1 + rows of the join) on the best column pair (best by smaller share).',
    'ex_fan_lo': 'Join rows divided by the larger table size, on the best column pair.',
    'ex_fan_hi': 'Join rows divided by the smaller table size, on the best column pair (above 1: many-to-many).',
    'ex_func': 'The best join is many-to-one or one-to-one: every matching row has exactly one match on the other side, on at least one side.',
    'ex_keys_hit': 'Share of joinable column pairs with at least one match.',
    'ex_pair_semi': 'Smaller semi-join share of A and B when A and B share both a Position and a Color column and the join key is (cell, color).',
    'ex_ctx_hit': 'Share of train examples with at least one join row on the best column pair.',
}


def tables(node, pairs):
    n = len(pairs)
    types = node.get('table_types') or node['types']
    w = [WIDE.get(t, 1) for t in types]
    offs = [0]
    for x in w:
        offs.append(offs[-1] + x)
    width = offs[-1]
    ex_col = types.index('Example') if 'Example' in types else None
    rows = []                                   # (e, flat row)
    glob = []
    for ent in node.get('x_rows') or []:
        (a, e), rs = ent[0], ent[1]
        if a == 1 and e < n:
            rows.extend((e, r) for r in rs if len(r) == width)
        elif a == 0:
            if ex_col is not None:
                o = offs[ex_col]
                rows.extend((r[o], r) for r in rs if len(r) == width and r[o] < n)
            else:
                glob.extend(r for r in rs if len(r) == width)
    for r in glob:
        rows.extend((e, r) for e in range(n))
    cols = []
    seen = Counter()
    pc = {}
    for ci, t in enumerate(types):
        if t == 'Example':
            continue
        seen[t] += 1
        if seen[t] > MAXC:
            continue
        o = offs[ci]
        if t == 'Position':
            keys = [(e, r[o], r[o + 2]) for e, r in rows]
        else:
            keys = [(e, tuple(r[o:o + w[ci]])) for e, r in rows]
        cols.append((t, seen[t], Counter(keys), len(rows)))
        pc[(t, seen[t])] = keys
    pk = None
    if ('Position', 1) in pc and ('Color', 1) in pc:
        pk = Counter(zip(pc[('Position', 1)], pc[('Color', 1)]))
    return dict(cols=cols, n=n, nrows=len(rows), pk=pk)


def _join(ca, cb):
    """Counters of keys. Returns (semi_a, semi_b, join_rows, functional, ctx_hit_set)."""
    if len(ca) > len(cb):
        small, big, sw = cb, ca, True
    else:
        small, big, sw = ca, cb, False
    ja = jb = rows = 0
    fa = fb = True
    ctx = set()
    for k, c in small.items():
        d = big.get(k)
        if d:
            ja += c; jb += d; rows += c * d
            if c > 1: fa = False
            if d > 1: fb = False
            ctx.add(k[0])
    if sw:
        ja, jb, fa, fb = jb, ja, fb, fa
    return ja, jb, rows, fa, fb, ctx


def features_exact(ta, tb):
    d = {}
    na, nb = ta['nrows'], tb['nrows']
    if not na or not nb:
        return d
    best = None; hit = tot = 0
    for (t1, i1, ca, _) in ta['cols']:
        for (t2, i2, cb, _) in tb['cols']:
            if t1 != t2 or i1 != i2:
                continue
            tot += 1
            ja, jb, rows, fa, fb, ctx = _join(ca, cb)
            hit += rows > 0
            sa, sb = ja / na, jb / nb
            cand = (min(sa, sb), max(sa, sb), rows, (fa or fb) and rows > 0, len(ctx))
            if best is None or cand[:3] > best[:3]:
                best = cand
    if best is None:
        return d
    lo, hi, rows, func, nctx = best
    d['ex_semi_lo'], d['ex_semi_hi'] = lo, hi
    d['ex_join_log'] = rows.bit_length()
    d['ex_fan_lo'] = rows / max(na, nb); d['ex_fan_hi'] = rows / min(na, nb)
    d['ex_func'] = float(func)
    d['ex_keys_hit'] = hit / tot
    d['ex_ctx_hit'] = nctx / ta['n']
    if ta['pk'] is not None and tb['pk'] is not None:
        ja, jb, *_ = _join(ta['pk'], tb['pk'])
        d['ex_pair_semi'] = min(ja / na, jb / nb)
    return d
