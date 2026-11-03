"""Probe of restatement relations among the tables of a pool. Reads node records only.

Tables are first put in plain form: an Example column that holds one value per example, a column with one value over all examples, and a repeated column are dropped. Tables equal in plain form are one class. Relations are tested between classes, and each candidate is put in plain form before the match.

A chance baseline repeats each one-source relation with the source's examples rotated, so a hit there can't be a true restatement of that example, unless the table is the same in every example.

Each task writes one row to OUT as soon as it's done, and a rerun skips finished tasks.

  probe2.py NODES_DIR OUT STEP [OFFSET] [CAP]     every STEP-th task, starting at OFFSET
"""
import collections, itertools, json, os, statistics, subprocess, sys, time

WIDTH = {'Position': 4, 'Box': 4, 'Offset': 4}
PAIR_CAP = 40  # pairs tried inside one bucket
GROUP_CAP = 150  # classes of one column signature in the pairwise set reads
MOTION = 2  # largest shift tried, in cells
TIE_CAP = 24  # column orders tried for columns tied on type and values
ONE_WAY = ['projection', 'count of rows per key', 'selection on a value, column kept', 'selection on a value, column dropped', 'complement in the values seen', 'grid-symmetry', 'shift', 'symmetric closure', 'reflexive closure', 'transitive closure']


def split(row, types):
    out, i = [], 0
    for t in types:
        w = WIDTH.get(t, 1)
        out.append(tuple(row[i:i + w]) if w > 1 else row[i])
        i += w
    return tuple(out)


def project(ex, cols):
    return tuple(frozenset(tuple(r[c] for c in cols) for r in rows) for rows in ex)


def canon(types, ex):
    """Columns in an order that doesn't depend on the table's own order. Columns tied on type and value sets are tried in each order, up to TIE_CAP orders."""
    n = len(types)
    if n == 1:
        return types, tuple(ex)
    tag = [(types[c], hash(tuple(frozenset(r[c] for r in rows) for rows in ex))) for c in range(n)]
    base = sorted(range(n), key=lambda c: tag[c])
    ties = [list(g) for _, g in itertools.groupby(base, key=lambda c: tag[c])]
    size = 1
    for g in ties:
        for i in range(2, len(g) + 1):
            size *= i
    if size == 1 or size > TIE_CAP:
        return tuple(types[c] for c in base), project(ex, base)
    best, best_h = None, None
    for orders in itertools.product(*(itertools.permutations(g) for g in ties)):
        idx = [c for o in orders for c in o]
        e = project(ex, idx)
        h = hash(e)
        if best_h is None or h < best_h:
            best, best_h = e, h
    return tuple(types[c] for c in base), best


def key(types, ex):
    return hash(canon(types, ex))


def plain_columns(types, ex, example=True, constant=True, repeat=True):
    keep = []
    for c in range(len(types)):
        per = [{r[c] for r in rows} for rows in ex]
        if example and types[c] == 'Example' and all(len(v) <= 1 for v in per):
            continue
        if constant and len(set().union(*per)) <= 1:
            continue
        if repeat and any(types[d] == types[c] and all(r[c] == r[d] for rows in ex for r in rows) for d in keep):
            continue
        keep.append(c)
    return keep


def plain_key(types, ex, **kw):
    keep = plain_columns(types, ex, **kw)
    if not keep:
        return hash(('no columns', tuple(bool(x) for x in ex)))
    if len(keep) == len(types):
        return key(types, ex)
    return key(tuple(types[c] for c in keep), project(ex, keep))


class Table:
    __slots__ = ('id', 'types', 'ex', 'gold', 'parents')


class Rep:
    __slots__ = ('i', 'ids', 'types', 'ex', 'gold', 'parents', 'canon', 'bin', 'rows')


def load(path):
    p = subprocess.Popen(['zstd', '-dcq', path], stdout=subprocess.PIPE, text=True)
    raw = []
    for line in p.stdout:
        try:
            raw.append(json.loads(line))
        except ValueError:
            continue
    p.wait()
    names = sorted({tuple(e[0]) for r in raw for e in r['x_rows'] or ()})
    at = {n: i for i, n in enumerate(names)}
    merged, out, cut, empty, one_parent = {}, [], 0, 0, 0
    gold_nodes = 0
    for r in raw:
        tags = r.get('tags') or {}
        gold = tags.get('kind') == 'gold'
        gold_nodes += gold
        if not r.get('table_types') or not r.get('x_rows'):
            empty += 1
            continue
        types = tuple(r['table_types'])
        worlds = any(e[3] for e in r['x_rows'])  # entries of one example are the alternatives of a DET choice
        ex = [set() for _ in names]
        bad = False
        for e in r['x_rows']:
            if len(e[1]) < e[2]:
                bad = True
                break
            w = (str(sorted(json.dumps(v, sort_keys=True) for v in e[3].values())),) if worlds else ()
            ex[at[tuple(e[0])]].update(w + split(x, types) for x in e[1])
        if worlds:
            types = ('Model',) + types
        ex = [frozenset(x) for x in ex]
        if bad:
            cut += 1
            continue
        if not any(ex):
            empty += 1
            continue
        ex = tuple(ex)
        one_parent += len(r.get('parents') or []) == 1
        k = hash((types, ex))
        t = merged.get(k)
        if t is None:
            t = Table()
            t.id, t.types, t.ex, t.gold, t.parents = int(r['token']), types, ex, False, set()
            merged[k] = t
            out.append(t)
        t.gold = t.gold or gold
        t.parents.update(int(x) for x in r.get('parents') or [])
        merged[('token', int(r['token']))] = t
    token_of = {k[1]: t.id for k, t in merged.items() if isinstance(k, tuple)}
    return out, token_of, dict(nodes=len(raw), gold_nodes=gold_nodes, truncated=cut, empty=empty, one_parent=one_parent, examples=len(names))


def size_bin(ex):
    sizes = [len(x) for x in ex if x]
    m = statistics.median(sizes) if sizes else 0
    return '1' if m <= 1 else '2-9' if m < 10 else '10+'


def classes_of(tables, token_of):
    funnel = {'unique tables': len(tables)}
    funnel['up to column order'] = len({key(t.types, t.ex) for t in tables})
    funnel['dropping Example columns'] = len({plain_key(t.types, t.ex, constant=False, repeat=False) for t in tables})
    funnel['and columns constant over all examples'] = len({plain_key(t.types, t.ex, repeat=False) for t in tables})
    by = collections.defaultdict(list)
    for t in tables:
        by[plain_key(t.types, t.ex)].append(t)
    funnel['and repeated columns'] = len(by)
    reps, rep_of = [], {}
    no_columns = 0
    for members in by.values():
        t = members[0]
        keep = plain_columns(t.types, t.ex)
        for m in members:
            rep_of[m.id] = None
        if not keep:
            no_columns += 1
            continue
        r = Rep()
        r.i = len(reps)
        r.ids = [m.id for m in members]
        r.types = tuple(t.types[c] for c in keep)
        r.ex = project(t.ex, keep)
        r.gold = any(m.gold for m in members)
        r.canon = canon(r.types, r.ex)
        r.bin = size_bin(r.ex)
        r.rows = sum(map(len, r.ex))
        r.parents = set()
        reps.append(r)
        for m in members:
            rep_of[m.id] = r.i
    for r, members in zip(reps, [m for m in by.values() if plain_columns(m[0].types, m[0].ex)]):
        for m in members:
            for p in m.parents:
                x = rep_of.get(token_of.get(p))
                if x is not None and x != r.i:
                    r.parents.add(x)
    funnel['classes with no columns left'] = no_columns
    return reps, funnel


def position_columns(types):
    return [c for c, x in enumerate(types) if x == 'Position']


def partition_of(t):
    """For a class with one Position column and more: the partition of its cells by the rest of each row, with the values' names dropped."""
    ps = position_columns(t.types)
    if len(ps) != 1 or len(t.types) < 2:
        return None
    p = ps[0]
    rest = [c for c in range(len(t.types)) if c != p]
    out = []
    for rows in t.ex:
        cell = collections.defaultdict(set)
        for r in rows:
            cell[r[p]].add(tuple(r[c] for c in rest))
        groups = collections.defaultdict(set)
        for pos, vals in cell.items():
            groups[frozenset(vals)].add(pos)
        out.append(frozenset(frozenset(g) for g in groups.values()))
    return hash(tuple(out))


def support_of(t):
    ps = position_columns(t.types)
    if not ps:
        return None
    return hash((len(ps), tuple(frozenset(r[p] for r in rows for p in ps) for rows in t.ex)))


def motions():
    d4 = {
        'flip-rows': lambda r, ri, c, ci: (ri, r, c, ci),
        'flip-cols': lambda r, ri, c, ci: (r, ri, ci, c),
        'rotate-180': lambda r, ri, c, ci: (ri, r, ci, c),
        'transpose': lambda r, ri, c, ci: (c, ci, r, ri),
        'anti-transpose': lambda r, ri, c, ci: (ci, c, ri, r),
        'rotate-90': lambda r, ri, c, ci: (c, ci, ri, r),
        'rotate-270': lambda r, ri, c, ci: (ci, c, r, ri),
    }
    for f in d4.values():
        yield 'grid-symmetry', f
    for dr in range(-MOTION, MOTION + 1):
        for dc in range(-MOTION, MOTION + 1):
            if dr or dc:
                yield 'shift', (lambda dr, dc: lambda r, ri, c, ci: (r + dr, ri - dr, c + dc, ci - dc))(dr, dc)


MOTIONS = list(motions())


def closure(pairs):
    next_of = collections.defaultdict(set)
    for a, b in pairs:
        next_of[a].add(b)
    out = set(pairs)
    todo = list(pairs)
    while todo and len(out) < 4000:
        a, b = todo.pop()
        for c in next_of.get(b, ()):
            if (a, c) not in out:
                out.add((a, c))
                todo.append((a, c))
    return out


def one_source(s_types, s_ex, dom, sid, mark):
    """Every candidate that a single class gives, for one assignment of its rows to examples."""
    n = len(s_types)
    sizes = range(1, n) if n <= 6 else range(1, 4)
    for size in sizes:
        for cols in itertools.combinations(range(n), size):
            ty = tuple(s_types[c] for c in cols)
            mark('projection', ty, project(s_ex, cols), sid)
            if size <= 2:
                counts = []
                for rows in s_ex:
                    got = collections.Counter(tuple(r[c] for c in cols) for r in rows)
                    counts.append(frozenset(k + (v,) for k, v in got.items()))
                mark('count of rows per key', ty + ('Nat',), tuple(counts), sid)
    if n == 1:
        c = 0
        mark('complement in the values seen', s_types, tuple(frozenset((v,) for v in dom[s_types[0]][i]) - rows for i, rows in enumerate(s_ex)), sid)
    for c in range(n if n > 1 else 0):
        vals = {r[c] for rows in s_ex for r in rows}
        if len(vals) > 40:
            continue
        rest = [d for d in range(n) if d != c]
        rest_ty = tuple(s_types[d] for d in rest)
        for v in vals:
            ex = tuple(frozenset(r for r in rows if r[c] == v) for rows in s_ex)
            mark('selection on a value, column kept', s_types, ex, sid)
            mark('selection on a value, column dropped', rest_ty, project(ex, rest), sid)
    ps = position_columns(s_types)
    if ps and sum(map(len, s_ex)) <= 3000:
        for fam, f in MOTIONS:
            ex = []
            for rows in s_ex:
                got = set()
                for r in rows:
                    moved = list(r)
                    ok = True
                    for p in ps:
                        m = f(*r[p])
                        if min(m) < 0:
                            ok = False
                            break
                        moved[p] = m
                    if ok:
                        got.add(tuple(moved))
                ex.append(frozenset(got))
            mark(fam, s_types, tuple(ex), sid)
    if n == 2 and s_types[0] == s_types[1] and sum(map(len, s_ex)) <= 1500:
        mark('symmetric closure', s_types, tuple(frozenset(rows | {(b, a) for a, b in rows}) for rows in s_ex), sid)
        mark('reflexive closure', s_types, tuple(frozenset(rows | {(a, a) for a, _ in rows} | {(b, b) for _, b in rows}) for rows in s_ex), sid)
        mark('transitive closure', s_types, tuple(frozenset(closure(set(rows))) for rows in s_ex), sid)


def rotate(x):
    return x[1:] + x[:1]


def wrong_examples(s, domain, rotated):
    """The rows of a class assigned to the wrong examples, with the domains to match. A table held whole in the first entry moves by its Example column, and without one it has no example to get wrong."""
    if any(s.ex[1:]):
        return rotate(s.ex), rotated
    es = [c for c, t in enumerate(s.types) if t == 'Example']
    if not es:
        return None, None
    vals = sorted({r[es[0]] for r in s.ex[0]})
    if len(vals) < 2:
        return None, None
    move = dict(zip(vals, vals[1:] + vals[:1]))
    ex = (frozenset(tuple(move.get(x, x) if c in es else x for c, x in enumerate(r)) for r in s.ex[0]),) + s.ex[1:]
    return ex, domain


def read_task(reps):
    hit = collections.defaultdict(set)
    built = collections.defaultdict(set)
    null = collections.defaultdict(set)
    by_key = collections.defaultdict(set)
    for t in reps:
        by_key[hash(t.canon)].add(t.i)

    def sink(store, with_built):
        def mark(rel, types, ex, sid):
            if not any(ex):
                return
            for x in by_key.get(plain_key(types, ex, example=False), ()):
                if x != sid:
                    store[rel].add(x)
                    if with_built and sid in reps[x].parents:
                        built[rel].add(x)
        return mark

    mark_real, mark_null = sink(hit, True), sink(null, False)
    domain = collections.defaultdict(lambda: [set() for _ in reps[0].ex])
    for t in reps:
        for c, ty in enumerate(t.types):
            for i, rows in enumerate(t.ex):
                domain[ty][i].update(r[c] for r in rows)
    rotated = {ty: rotate(v) for ty, v in domain.items()}
    multi = len(reps[0].ex) > 1
    for s in reps:
        one_source(s.types, s.ex, domain, s.i, mark_real)
        if multi:
            ex, dom = wrong_examples(s, domain, rotated)
            if ex is not None:
                one_source(s.types, ex, dom, s.i, mark_null)

    # one value per example: a fact of the example, so the rest of the rows and that fact are two sources
    facts = collections.defaultdict(set)
    for t in reps:
        keep = [c for c in range(len(t.types)) if not all(len({r[c] for r in rows}) <= 1 for rows in t.ex)]
        if keep and len(keep) < len(t.types):
            facts[plain_key(tuple(t.types[c] for c in keep), project(t.ex, keep), example=False)].add(t.i)
    for k, v in facts.items():
        for x in by_key.get(k, ()):
            v.add(x)
        if len(v) > 1:
            hit['same rows apart from a column with one value per example'].update(v)

    groups = {'partition': collections.defaultdict(set), 'cells': collections.defaultdict(set)}
    for t in reps:
        k = partition_of(t)
        if k is not None:
            groups['partition'][k].add(t.i)
        k = support_of(t)
        if k is not None:
            groups['cells'][k].add(t.i)
    for name, rel in (('partition', 'same partition of cells'), ('cells', 'same cell set')):
        for v in groups[name].values():
            if len(v) > 1:
                hit[rel].update(v)

    # set algebra among classes of one signature
    sig = collections.defaultdict(list)
    for t in reps:
        sig[t.canon[0]].append(t)
    for ty, g in sig.items():
        g = g[:GROUP_CAP]
        for a, b in itertools.combinations(g, 2):
            ea, eb = a.canon[1], b.canon[1]
            inner = None
            if all(x <= y for x, y in zip(ea, eb)):
                inner, outer, e_in, e_out = a, b, ea, eb
            elif all(y <= x for x, y in zip(ea, eb)):
                inner, outer, e_in, e_out = b, a, eb, ea
            if inner:
                hit['subset of another table'].add(inner.i)
                if outer.i in inner.parents:
                    built['subset of another table'].add(inner.i)
                diff = tuple(y - x for x, y in zip(e_in, e_out))
                for x in by_key.get(plain_key(ty, diff, example=False), ()):
                    if x not in (a.i, b.i):
                        hit['complement inside another table'].add(x)
                        if outer.i in reps[x].parents or inner.i in reps[x].parents:
                            built['complement inside another table'].add(x)
            else:
                for name, e in (('union of two tables', tuple(x | y for x, y in zip(ea, eb))), ('intersection of two tables', tuple(x & y for x, y in zip(ea, eb)))):
                    if not any(e):
                        continue
                    for x in by_key.get(plain_key(ty, e, example=False), ()):
                        if x not in (a.i, b.i):
                            hit[name].add(x)
                            if a.i in reps[x].parents or b.i in reps[x].parents:
                                built[name].add(x)

    # a column mapped by a function, the other columns equal
    buckets = collections.defaultdict(list)
    for t in reps:
        n = len(t.types)
        if n < 2:
            continue
        for c in range(n):
            rest = [d for d in range(n) if d != c]
            ty, e = canon(tuple(t.types[d] for d in rest), project(t.ex, rest))
            buckets[hash((ty, e, tuple(len(x) for x in t.ex)))].append((t, c, rest))
    pairs = []
    for bucket in buckets.values():
        tried = 0
        for (a, ca, ra), (b, cb, rb) in itertools.combinations(bucket, 2):
            if a.i == b.i:
                continue
            tried += 1
            if tried > PAIR_CAP:
                break
            if len(ra) > 1 and tuple(a.types[d] for d in ra) != tuple(b.types[d] for d in rb):
                ra_order = sorted(ra, key=lambda d: a.types[d])
                rb_order = sorted(rb, key=lambda d: b.types[d])
            else:
                ra_order, rb_order = ra, rb
            f, whole, local, ok = {}, True, True, True
            for x, y in zip(a.ex, b.ex):
                ma = {tuple(r[d] for d in ra_order): r[ca] for r in x}
                mb = {tuple(r[d] for d in rb_order): r[cb] for r in y}
                if len(ma) != len(x) or len(mb) != len(y) or ma.keys() != mb.keys():
                    ok = False
                    break
                fe = {}
                for k, v in ma.items():
                    if fe.setdefault(v, mb[k]) != mb[k]:
                        local = False
                        break
                    if f.setdefault(v, mb[k]) != mb[k]:
                        whole = False
                if not local:
                    break
            if not ok or not local or not f:
                continue
            if whole and all(k == v for k, v in f.items()):
                continue
            one_to_one = len(set(f.values())) == len(f)
            rel = ('fixed one-to-one map on a column' if one_to_one else 'fixed many-to-one map on a column') if whole else 'map on a column, fixed per example'
            if whole and one_to_one and len(f) > 1:
                pairs.append((a.i, b.i))
            for t, o in ((b, a), (a, b)):
                hit[rel].add(t.i)
                if o.i in t.parents:
                    built[rel].add(t.i)
    return hit, built, null, groups, pairs


def count_merged(n, sets):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for v in sets:
        v = list(v)
        for y in v[1:]:
            parent[find(y)] = find(v[0])
    return len({find(x) for x in range(n)})


def main():
    base, out, step = sys.argv[1], sys.argv[2], int(sys.argv[3])
    offset = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    files = sorted(e.name for e in os.scandir(base) if e.name.endswith('.nodes.jsonl.zst'))[offset::step]
    if len(sys.argv) > 5:
        files = files[:int(sys.argv[5])]
    done = set()
    if os.path.exists(out):
        done = {json.loads(x)['task'] for x in open(out)}
    t0, ran = time.time(), 0
    with open(out, 'a') as w:
        for i, f in enumerate(files, 1):
            task = f.split('.')[0]
            if task in done:
                continue
            t1 = time.time()
            tables, token_of, info = load(os.path.join(base, f))
            reps, funnel = classes_of(tables, token_of)
            if len(reps) < 2:
                continue
            hit, built, null, groups, pairs = read_task(reps)
            gold = {t.i for t in reps if t.gold}
            bins = collections.Counter(t.bin for t in reps)
            funnel['and same partition of cells or fixed one-to-one map'] = count_merged(len(reps), list(groups['partition'].values()) + pairs)
            reached = set().union(*(hit[r] for r in ONE_WAY))
            reached_null = set().union(*(null[r] for r in ONE_WAY))

            def by_bin(v):
                return dict(collections.Counter(reps[x].bin for x in v))

            row = dict(task=task, **info, tables=len(tables), classes=len(reps), gold_tables=sum(t.gold for t in tables), gold_classes=len(gold), bins=dict(bins), gold_bins=by_bin(gold), funnel=funnel,
                       reached=len(reached), reached_gold=len(reached & gold), reached_null=len(reached_null), reached_null_gold=len(reached_null & gold), reached_bins=by_bin(reached), reached_null_bins=by_bin(reached_null),
                       relations={r: dict(hit=len(v), gold=len(v & gold), built=len(built[r]), built_gold=len(built[r] & gold), null=len(null[r]), null_gold=len(null[r] & gold), bins=by_bin(v), null_bins=by_bin(null[r])) for r, v in hit.items()},
                       seconds=round(time.time() - t1, 1))
            w.write(json.dumps(row) + '\n')
            w.flush()
            ran += 1
            el = time.time() - t0
            print('%d/%d %s tables %d classes %d gold %d %.1f s | ETA %.0f s' % (i, len(files), task, len(tables), len(reps), len(gold), time.time() - t1, el / ran * (len(files) - i)), flush=True)
    print('done', round(time.time() - t0), 's', flush=True)


if __name__ == '__main__':
    main()
