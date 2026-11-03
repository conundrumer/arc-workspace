"""Content key of a table: the engine's order-free key (superdag_search.table_key) computed from x_rows, with each Ident value
first replaced by the hash of the set of its rows without Ident columns. Pure Python, no session. Hashes are of ints, so they
agree between processes.

  content_key(types, x_rows) -> (sorted column types by value hash order, least body hash)
  key_str(key) -> str
"""
import collections, itertools, math

WID = {'Position': 4, 'Box': 4, 'Offset': 4}


def _spans(types):
    sp, at = [], 0
    for t in types:
        w = WID.get(t, 1)
        sp.append((at, at + w))
        at += w
    return sp


def unident(types, x_rows):
    """x_rows entries as (example, rows as tuples) with Ident cells replaced by the hash of their class."""
    sp = _spans(types)
    ids = [i for i, t in enumerate(types) if t == 'Ident']
    ents = [(tuple(e[0]), [tuple(r) for r in e[1]]) for e in x_rows]
    if not ids:
        return ents
    drop = {sp[i][0] for i in ids}
    out = []
    for ex, rows in ents:
        cls = collections.defaultdict(set)
        for r in rows:
            rest = tuple(v for j, v in enumerate(r) if j not in drop)
            for i in ids:
                cls[(i, r[sp[i][0]])].add(rest)
        h = {k: hash(frozenset(v)) for k, v in cls.items()}
        new = []
        for r in rows:
            r = list(r)
            for i in ids:
                r[sp[i][0]] = h[(i, r[sp[i][0]])]
            new.append(tuple(r))
        out.append((ex, new))
    return out


def content_key(types, x_rows):
    sp = _spans(types)
    entries = unident(types, x_rows)
    cols = []
    for t, (a, b) in zip(types, sp):
        cols.append((str(t), hash(tuple(sorted((ex, hash(frozenset(r[a:b] for r in rows))) for ex, rows in entries))), a, b))
    order = sorted(cols)
    groups = [list(g) for _, g in itertools.groupby(order, key=lambda c: c[:2])]
    if math.prod(math.factorial(len(g)) for g in groups) > 720:
        groups = [[c] for c in order]
    least = None
    for perm in itertools.product(*(itertools.permutations(g) for g in groups)):
        seq = [c for g in perm for c in g]
        per = collections.defaultdict(set)
        for ex, rows in entries:
            per[ex].add(hash(frozenset(tuple(v for _, _, a, b in seq for v in r[a:b]) for r in rows)))
        body = hash(tuple(sorted((ex, tuple(sorted(s))) for ex, s in per.items())))
        least = body if least is None else min(least, body)
    return tuple(c[0] for c in order), least


def key_str(k):
    return '%s|%d' % (','.join(k[0]), k[1])
