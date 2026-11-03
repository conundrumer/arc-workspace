"""The order of restatement among a pool's table classes. Reads node records only.

An arrow S -> T means a one-source relation from S gives T. Classes with arrows both ways, directly or not, collapse to one node, so what remains is a DAG. Generators are the sources of that DAG. Each count is also given after dropping arrows that also appear with S's examples assigned wrongly, which are chance or tables that don't vary by example.

Families: for a source and a column, the classes that are selections of that column on different values, where at least two are in the pool.
Lattice fill: for a source with 2 to 6 columns, the share of its proper column subsets whose projection is in the pool, other than the source.

Each task writes one row to OUT as soon as it's done, and a rerun skips finished tasks.

  arrows.py NODES_DIR OUT STEP [OFFSET]
"""
import collections, itertools, json, os, statistics, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_restatement_probe as P

sys.setrecursionlimit(100000)


def components(n, out):
    """Strongly connected components, with Tarjan's method."""
    index, low, on, stack, comp = {}, {}, set(), [], [-1] * n
    count, c = [0], [0]

    def go(v):
        index[v] = low[v] = count[0]
        count[0] += 1
        stack.append(v)
        on.add(v)
        for w in out[v]:
            if w not in index:
                go(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            while True:
                w = stack.pop()
                on.discard(w)
                comp[w] = c[0]
                if w == v:
                    break
            c[0] += 1

    for v in range(n):
        if v not in index:
            go(v)
    return comp, c[0]


def shape(reps, arrows):
    n = len(reps)
    out = [set() for _ in range(n)]
    for a, b in arrows:
        out[a].add(b)
    comp, m = components(n, out)
    d_out = [set() for _ in range(m)]
    for a, b in arrows:
        if comp[a] != comp[b]:
            d_out[comp[a]].add(comp[b])
    has_in = [False] * m
    for a in range(m):
        for b in d_out[a]:
            has_in[b] = True
    # Tarjan numbers components so that an arrow goes from a higher number to a lower one
    depth, below = [0] * m, [None] * m
    for a in range(m):
        s = set()
        for b in d_out[a]:
            s.add(b)
            s |= below[b]
            depth[a] = max(depth[a], depth[b] + 1)
        below[a] = s
    cover = 0
    for a in range(m):
        reach = set()
        for b in d_out[a]:
            reach |= below[b]
        cover += len(d_out[a] - reach)
    gen = [a for a in range(m) if not has_in[a]]
    # layers from the sources, for gold's distance
    level = [0] * m
    for a in range(m - 1, -1, -1):
        for b in d_out[a]:
            level[b] = max(level[b], level[a] + 1)
    gold = [comp[r.i] for r in reps if r.gold]
    gold_gen = sum(not has_in[c] for c in gold)
    reach_sizes = sorted(len(below[a]) for a in gen)
    size = collections.Counter(comp)
    gen_alone = sum(1 for a in gen if not d_out[a] and size[a] == 1)
    return dict(nodes=m, mutual_merged=n - m, generators=len(gen), generators_alone=gen_alone, covering_edges=cover, longest_path=max(depth, default=0), gold=len(gold), gold_generators=gold_gen,
                gold_levels=dict(collections.Counter(str(min(level[c], 4)) for c in gold)), median_below_generator=statistics.median(reach_sizes) if reach_sizes else 0, most_below_generator=reach_sizes[-1] if reach_sizes else 0)


def read(reps):
    by_key = collections.defaultdict(set)
    for t in reps:
        by_key[hash(t.canon)].add(t.i)
    real, fake = set(), set()
    per = collections.Counter()

    def sink(store):
        def mark(rel, types, ex, sid):
            if not any(ex):
                return
            for x in by_key.get(P.plain_key(types, ex, example=False), ()):
                if x != sid:
                    store.add((sid, x))
        return mark

    domain = collections.defaultdict(lambda: [set() for _ in reps[0].ex])
    for t in reps:
        for c, ty in enumerate(t.types):
            for i, rows in enumerate(t.ex):
                domain[ty][i].update(r[c] for r in rows)
    rotated = {ty: P.rotate(v) for ty, v in domain.items()}
    m_real, m_fake = sink(real), sink(fake)
    multi = len(reps[0].ex) > 1
    for s in reps:
        P.one_source(s.types, s.ex, domain, s.i, m_real)
        if multi:
            ex, dom = P.wrong_examples(s, domain, rotated)
            if ex is not None:
                P.one_source(s.types, ex, dom, s.i, m_fake)

    # families of selection slices
    fam_sizes = []
    in_family = set()
    gold_in_family = set()
    for s in reps:
        n = len(s.types)
        if n < 2:
            continue
        for c in range(n):
            vals = {r[c] for rows in s.ex for r in rows}
            if len(vals) < 2 or len(vals) > 40:
                continue
            rest = [d for d in range(n) if d != c]
            rest_ty = tuple(s.types[d] for d in rest)
            got = set()
            for v in vals:
                ex = tuple(frozenset(r for r in rows if r[c] == v) for rows in s.ex)
                got |= by_key.get(P.plain_key(s.types, ex, example=False), set())
                got |= by_key.get(P.plain_key(rest_ty, P.project(ex, rest), example=False), set())
            got.discard(s.i)
            if len(got) >= 2:
                fam_sizes.append(len(got))
                in_family |= got
                gold_in_family |= {x for x in got if reps[x].gold}

    # how much of each table's projection lattice is present
    have, total = 0, 0
    for s in reps:
        n = len(s.types)
        if not 2 <= n <= 6:
            continue
        for size in range(1, n):
            for cols in itertools.combinations(range(n), size):
                total += 1
                x = by_key.get(P.plain_key(tuple(s.types[c] for c in cols), P.project(s.ex, cols), example=False), ())
                have += any(i != s.i for i in x)

    return dict(all=shape(reps, real), without_chance=shape(reps, real - fake), arrows=len(real), arrows_chance=len(real & fake), families=len(fam_sizes), family_median=statistics.median(fam_sizes) if fam_sizes else 0, family_max=max(fam_sizes, default=0),
                in_family=len(in_family), gold_in_family=len(gold_in_family), lattice_have=have, lattice_total=total)


def main():
    base, out, step = sys.argv[1], sys.argv[2], int(sys.argv[3])
    offset = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    files = sorted(e.name for e in os.scandir(base) if e.name.endswith('.nodes.jsonl.zst'))[offset::step]
    done = {json.loads(x)['task'] for x in open(out)} if os.path.exists(out) else set()
    t0, ran = time.time(), 0
    with open(out, 'a') as w:
        for i, f in enumerate(files, 1):
            task = f.split('.')[0]
            if task in done:
                continue
            t1 = time.time()
            tables, token_of, info = P.load(os.path.join(base, f))
            reps, funnel = P.classes_of(tables, token_of)
            if len(reps) < 2:
                continue
            row = dict(task=task, classes=len(reps), gold_classes=sum(r.gold for r in reps), **read(reps))
            row['seconds'] = round(time.time() - t1, 1)
            w.write(json.dumps(row) + '\n')
            w.flush()
            ran += 1
            print('%d/%d %s %.1f s | ETA %.0f s' % (i, len(files), task, time.time() - t1, (time.time() - t0) / ran * (len(files) - i)), flush=True)
    print('done', round(time.time() - t0), 's', flush=True)


if __name__ == '__main__':
    main()
