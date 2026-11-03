"""One record per available gold table at sampled stored points: is it read by gold's next table, its distance to OUT, and table measures on train pairs. Streams to rows.jsonl; a pair record per table pair."""
import json, os, random, re, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/model/study', os.path.dirname(HERE)]
from nodefeat import load_pairs
from outfeat import split_power
FX = '/Users/davidlu/code/arc-workspace/work/lm/data-study/feat-exp/fstore-gen3/points'
C = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/choice'
TASKS = {t for v in json.load(open(C + '/round-2/tasks.json')).values() for t in v}
PER, NPOINTS = 3, int(sys.argv[1])
HEAD = re.compile(r'^\((?:DET|RULE|INIT|OUT)\s+(&[\w.]+)?')
REF = re.compile(r'&[\w]+')


def graph(text):
    """{head: heads it reads}, the heads OUT reads, and each head's line, on base names."""
    reads, out, line = {}, set(), {}
    for i, l in enumerate(text.strip().split('\n')):
        m = HEAD.match(l)
        names = REF.findall(l)
        if l.startswith('(OUT'):
            out |= set(names)
        elif m and m[1]:
            h = m[1].split('.')[0]
            reads.setdefault(h, set()).update(n for n in names[1:] if n != h)
            line.setdefault(h, i)
    return reads, out, line


def dist(reads, out):
    d = {h: 1 for h in out}; todo = list(out)
    while todo:
        h = todo.pop(0)
        for r in reads.get(h, ()):
            if r not in d:
                d[r] = d[h] + 1; todo.append(r)
    return d


def depth(reads):
    memo = {}
    def f(h, seen=()):
        if h in memo or h in seen:
            return memo.get(h, 0)
        memo[h] = 1 + max((f(r, seen + (h,)) for r in reads.get(h, ())), default=0)
        return memo[h]
    for h in reads:
        f(h)
    return memo


def cols(t):
    """Per train example, per column, the set of cell values, under assignment 0 first found; and per column the Position cells."""
    types = [f['type'] for f in t['fields']]
    by = {}
    for e in t['entries']:
        if 'train' not in e or e.get('assignment', 0) != 0:
            continue
        s = by.setdefault(e['train'], [set() for _ in types])
        for r in e['rows'][:2000]:
            for i, c in enumerate(r):
                v = c.get('value')
                s[i].add(tuple(v) if isinstance(v, list) else v)
    return types, by


def measures(types, by, pairs):
    m = dict(hasPos=int('Position' in types), arity=len(types), nex=len(by), rows=sum(max((len(x) for x in s), default=0) for s in by.values()))
    vals = list(by.values())
    if len(vals) > 1:
        m['same_all'] = int(all(a == vals[0] for a in vals))
    best = None
    for i, t in enumerate(types):
        if t != 'Position':
            continue
        x = [q for e, p in enumerate(pairs) if e in by and (q := split_power(p, {(v[0], v[2]) for v in by[e][i]})) is not None]
        if x:
            best = max(best or 0, sum(x) / len(x))
    if best is not None:
        m['split'] = best
    return m


def pair(a, b):
    ta, ba = a; tb, bb = b
    share = sum(x == y for x in ta for y in tb) if ta and tb else 0
    best = 0.0
    for i, x in enumerate(ta):
        for j, y in enumerate(tb):
            if x != y:
                continue
            js = []
            for e in set(ba) & set(bb):
                u = ba[e][i] | bb[e][j]
                js.append(len(ba[e][i] & bb[e][j]) / len(u) if u else 0.0)
            if js:
                best = max(best, sum(js) / len(js))
    return dict(share=int(any(x == y for x in ta for y in tb)), overlap=best)


seen, n, t0 = {}, 0, time.time(); rng = random.Random(0)
with open(HERE + '/rows.jsonl', 'w') as out:
    for ent in os.scandir(FX):
        t = ent.name[:8]
        if t not in TASKS or seen.get(t, 0) >= PER or ent.name.startswith('.') :
            continue
        try:
            j = json.load(open(ent.path + '/point.json'))
            reads, ot, line = graph(open(ent.path + '/gold.arclog').read())
            g = next(x for x in j['tables'] if 'target' in x['roles'])
            gh = g['source_name'].split('.')[0]
            if gh not in reads:
                continue
            dd, de, pairs = dist(reads, ot), depth(reads), load_pairs(t)
            tabs = []
            for x in j['tables']:
                if 'available' not in x['roles'] or not x['source_name'].startswith('&'):
                    continue
                h = x['source_name'].split('.')[0]
                if h == gh:
                    continue
                tp, by = cols(json.load(open(f"{ent.path}/{x['path']}")))
                tabs.append((h, tp, by, measures(tp, by, pairs)))
            pos = [i for i, x in enumerate(tabs) if x[0] in reads[gh]]
            if not pos or len(tabs) < 3:
                continue
            for h, tp, by, m in tabs:
                out.write(json.dumps(dict(r='t', pt=ent.name, task=t, read=int(h in reads[gh]), dout=dd.get(h), ddepth=de.get(h), gap=line.get(gh, 0) - line.get(h, 0), gdout=dd.get(gh), **m)) + '\n')
            idx = list(range(len(tabs)))
            for i in pos:
                others = [k for k in idx if k != i]
                rng.shuffle(others)
                for k in others[:12] + [k for k in pos if k != i]:
                    q = pair((tabs[i][1], tabs[i][2]), (tabs[k][1], tabs[k][2]))
                    out.write(json.dumps(dict(r='p', pt=ent.name, task=t, co=int(k in pos), **q)) + '\n')
            out.flush()
            seen[t] = seen.get(t, 0) + 1; n += 1
            if n % 20 == 0:
                print(n, 'points', len(seen), 'tasks', round(time.time() - t0), 's', flush=True)
            if n >= NPOINTS:
                break
        except Exception as e:  # noqa: BLE001
            print('skip', ent.name, repr(e)[:120], flush=True)
print('done', n, 'points', len(seen), 'tasks', round(time.time() - t0), 's')
