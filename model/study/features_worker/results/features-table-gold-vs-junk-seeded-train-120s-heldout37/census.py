"""One row per table class of a pool: what built it, its shape, how it meets the training pairs, and its place in the restatement order. Gold is a label only.

Each task writes its rows to OUT as soon as it's done, and a rerun skips finished tasks.

  census.py NODES_DIR TASKS_DIR OUT STEP OFFSET [--no-arrows]
"""
import collections, itertools, json, math, os, statistics, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe2 as P
import forms

READ = ('input', 'ex_input', 'ex_output')


def raw_nodes(path):
    out = {}
    for line in subprocess.run(['zstd', '-dcq', path], capture_output=True, text=True).stdout.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        out[int(r['token'])] = r
    return out


def clause_facts(text):
    if not text:
        return dict(kind='none', op='none', reads=0, fixed=0, negated=0, union=0)
    p = forms.parse(text)
    kind = p[0]
    named = len(p) > 2 and isinstance(p[2], str)
    body = p[3:] if named else p[2:]
    op = p[2] if named else 'body'
    al = list(forms.atoms(body))
    reads = [a for a in al if a[0].startswith('&') or a[0] in READ]
    return dict(kind=kind, op=op, reads=len(reads), distinct_reads=len({a[0] for a in reads}), fixed=len(al) - len(reads), negated=sum(a[1] for a in reads), union=int(any(a[2] for a in al)))


def walk(x):
    if isinstance(x, list):
        yield x
        for y in x:
            yield from walk(y)


def own_sources(text):
    """What a clause reads from the task by itself: 'colors' or 'shape' from the input grid, 'output' from training outputs."""
    out = set()
    if not text:
        return out
    p = forms.parse(text)
    for a in walk(p):
        if not a or not isinstance(a[0], str):
            continue
        if a[0] in ('input', 'ex_input'):
            out.add('colors' if ':Col' in str(a) else 'shape')
        elif a[0] == 'ex_output':
            out.add('output')
    if len(p) > 2 and isinstance(p[2], str):
        if p[2] in ('ColorDomain', 'NumberDomain'):
            out.add('colors')
        elif not p[2].endswith('Domain') and p[0] != 'INIT':
            out.add('colors')
    return out


def sources(nodes):
    memo = {}

    def go(t):
        if t in memo:
            return memo[t]
        memo[t] = set()
        n = nodes.get(t)
        if n is None:
            return memo[t]
        got = own_sources(n['clause'])
        for x in n['parents'] or ():
            got |= go(int(x))
        memo[t] = got
        return got

    return go


def product_split(t):
    """The smallest column split that writes the rows as a product of two tables, in every example and world, where both sides have over one value in some example. 0 if none."""
    cols = [c for c, x in enumerate(t.types) if x != 'Model']
    m = [c for c, x in enumerate(t.types) if x == 'Model']
    n = len(cols)
    if n < 2 or n > 7:
        return 0
    groups = []
    for rows in t.ex:
        by = collections.defaultdict(list)
        for r in rows:
            by[r[m[0]] if m else 0].append(r)
        groups.extend(by.values())
    for size in range(1, n // 2 + 1):
        for a in itertools.combinations(cols, size):
            b = [c for c in cols if c not in a]
            real = False
            for g in groups:
                pa = {tuple(r[c] for c in a) for r in g}
                pb = {tuple(r[c] for c in b) for r in g}
                if len(pa) * len(pb) != len(g):
                    break
                real = real or (len(pa) > 1 and len(pb) > 1)
            else:
                if real:
                    return size
    return 0


def entropy(c):
    n = sum(c.values())
    return -sum(v / n * math.log2(v / n) for v in c.values()) if n else 0.0


def cell_labels(t, k):
    """For a table with one Position column: each cell of example k with the set of the rest of its rows."""
    p = P.position_columns(t.types)[0]
    rest = [c for c in range(len(t.types)) if c != p]
    got = collections.defaultdict(set)
    for r in t.ex[k]:
        got[(r[p][0], r[p][2])].add(tuple(r[c] for c in rest))
    return {c: frozenset(v) for c, v in got.items()}


def explains_output(t, names, task):
    """Leave one training pair out: predict each output cell from the input color and the table's label, with counts from the other pairs, against input color alone. Labels must repeat across pairs to help, so a table that gives each cell its own label gains nothing."""
    pairs = []
    for i, pair in enumerate(task['train']):
        k = names.get((1, i))
        a, b = pair['input'], pair['output']
        if k is None or len(a) != len(b) or len(a[0]) != len(b[0]):
            continue
        lab = cell_labels(t, k)
        pairs.append([(lab.get((r, c)), a[r][c], b[r][c]) for r in range(len(a)) for c in range(len(a[0]))])
    if len(pairs) < 2:
        return {}
    right, base, n = 0, 0, 0
    for h, held in enumerate(pairs):
        both, col = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
        for g, other in enumerate(pairs):
            if g != h:
                for l, x, y in other:
                    both[(l, x)][y] += 1
                    col[x][y] += 1
        for l, x, y in held:
            c = col.get(x)
            g0 = c.most_common(1)[0][0] if c else x
            b = both.get((l, x))
            g1 = b.most_common(1)[0][0] if b else g0
            right += g1 == y
            base += g0 == y
            n += 1
    return dict(output_gain=round((right - base) / n, 4), output_acc=round(right / n, 4))


def survives(t, names, task):
    keys = [k for n, k in names.items() if n[0] in (1, 2)]
    if not keys or not any(t.ex[k] for k in keys):
        return {}
    test = [k for n, k in names.items() if n[0] == 2]
    sizes = [len(t.ex[k]) for k in keys]
    m = statistics.mean(sizes)
    return dict(nonempty=round(sum(x > 0 for x in sizes) / len(keys), 3), test_nonempty=int(all(t.ex[k] for k in test)), size_spread=round(statistics.pstdev(sizes) / m, 3) if m else None)


def new_information(t, parents, grid, reads_grid, names):
    """H(T|S) / H(T) over cells, with S the parent that leaves least unknown. 0 means a parent determines T."""
    keys = [k for n, k in names.items() if n[0] in (1, 2)]
    sources = [p for p in parents if len(P.position_columns(p.types)) == 1]
    best, h_t = None, None
    joint_of = lambda a, b: collections.Counter((a.get(c), b.get(c)) for c in set(a) | set(b))
    labels = [(k, cell_labels(t, k)) for k in keys]
    total = sum(entropy(collections.Counter(l.values())) * len(l) for k, l in labels)
    if not total:
        return {}
    for s in sources + ([grid] if reads_grid else []):
        cond = 0.0
        for k, l in labels:
            o = s[k] if isinstance(s, dict) else cell_labels(s, k)
            j = joint_of(l, o)
            so = collections.Counter(o.get(c) for c in set(l) | set(o))
            cond += (entropy(j) - entropy(so)) * sum(j.values())
        v = cond / total
        best = v if best is None else min(best, v)
    return dict(new_info=round(best, 4)) if best is not None else {}


def diff_cells(pair):
    a, b = pair['input'], pair['output']
    if len(a) != len(b) or len(a[0]) != len(b[0]):
        return None
    return {(r, c) for r in range(len(a)) for c in range(len(a[0])) if a[r][c] != b[r][c]}


def meet(t, names, task):
    """How a table with one Position column meets the training pairs. The train pairs alone are read; test grids aren't."""
    ps = P.position_columns(t.types)
    if len(ps) != 1:
        return {}
    jac, in_diff, of_grid, inside = [], [], [], []
    for i, pair in enumerate(task['train']):
        k = names.get((1, i))
        if k is None:
            continue
        cells = {(p[0], p[2]) for p in (r[ps[0]] for r in t.ex[k])}
        if not cells:
            continue
        h, w = len(pair['input']), len(pair['input'][0])
        of_grid.append(len(cells) / (h * w))
        d = diff_cells(pair)
        if d is None or not d:
            continue
        jac.append(len(cells & d) / len(cells | d))
        in_diff.append(len(cells & d) / len(d))
        inside.append(len(cells & d) / len(cells))
    m = lambda v: round(statistics.mean(v), 4) if v else None
    return dict(jaccard=m(jac), covers_changed=m(in_diff), share_changed=m(inside), of_grid=m(of_grid))


def order(reps):
    by_key = collections.defaultdict(set)
    for t in reps:
        by_key[hash(t.canon)].add(t.i)
    arrows, rels = set(), collections.defaultdict(set)

    def mark(rel, types, ex, sid):
        if any(ex):
            for x in by_key.get(P.plain_key(types, ex, example=False), ()):
                if x != sid:
                    arrows.add((sid, x))
                    rels[x].add(rel)

    domain = collections.defaultdict(lambda: [set() for _ in reps[0].ex])
    for t in reps:
        for c, ty in enumerate(t.types):
            for i, rows in enumerate(t.ex):
                domain[ty][i].update(r[c] for r in rows)
    for s in reps:
        P.one_source(s.types, s.ex, domain, s.i, mark)
    into = collections.Counter(b for a, b in arrows)
    out = collections.Counter(a for a, b in arrows)
    return into, out, rels


def main():
    base, tasks, out, step, offset = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    arrows = '--no-arrows' not in sys.argv
    files = sorted(e.name for e in os.scandir(base) if e.name.endswith('.nodes.jsonl.zst'))[offset::step]
    done = {json.loads(x)['task'] for x in open(out)} if os.path.exists(out) else set()
    t0, ran = time.time(), 0
    with open(out, 'a') as w:
        for i, f in enumerate(files, 1):
            task = f.split('.')[0]
            if task in done:
                continue
            t1 = time.time()
            path = os.path.join(base, f)
            tables, token_of, info = P.load(path)
            reps, funnel = P.classes_of(tables, token_of)
            if len(reps) < 2:
                continue
            nodes = raw_nodes(path)
            data = json.load(open(os.path.join(tasks, task + '.json')))
            names = {n: k for k, n in enumerate(sorted({tuple(e[0]) for r in nodes.values() for e in r['x_rows'] or ()}))}
            src = sources(nodes)
            grid = {}
            for kind, key in ((1, 'train'), (2, 'test')):
                for j, pair in enumerate(data[key]):
                    k = names.get((kind, j))
                    if k is not None:
                        g = pair['input']
                        grid[k] = {(a, b): g[a][b] for a in range(len(g)) for b in range(len(g[0]))}
            into, outs, rels = order(reps) if arrows else ({}, {}, {})
            readers = collections.Counter(int(x) for r in nodes.values() for x in set(r['parents'] or ()))
            for r in reps:
                n = nodes[min(r.ids)]
                sizes = [len(x) for x in r.ex if x]
                row = dict(task=task, c=r.i, members=len(r.ids), gold=int(r.gold), token=min(r.ids), clause=(n['clause'] or '')[:400], depth=n['depth'], parents=len(n['parents'] or ()), types=sorted(r.types), columns=len(r.types),
                           rows=statistics.median(sizes) if sizes else 0, same_each_example=int(len(set(r.ex[1:])) == 1 if any(r.ex[1:]) else True), draw=n['tags'].get('draw'), seeded=int(bool(n['tags'].get('seeded'))), readers=sum(readers[x] for x in r.ids))
                row.update(clause_facts(n['clause']))
                row.update(sources=sorted(src(min(r.ids))), product=product_split(r))
                row.update(meet(r, names, data))
                row.update(survives(r, names, data))
                if len(P.position_columns(r.types)) == 1 and any(r.ex[1:]):
                    row.update(explains_output(r, names, data))
                    row.update(new_information(r, [reps[x] for x in r.parents], grid, '(input ' in (n['clause'] or ''), names))
                if arrows:
                    row.update(into=into.get(r.i, 0), below=outs.get(r.i, 0), rels=sorted(rels.get(r.i, ())))
                w.write(json.dumps(row) + '\n')
            w.flush()
            ran += 1
            print('%d/%d %s classes %d %.1f s | ETA %.0f s' % (i, len(files), task, len(reps), time.time() - t1, (time.time() - t0) / ran * (len(files) - i)), flush=True)
    print('done', round(time.time() - t0), 's', flush=True)


if __name__ == '__main__':
    main()
