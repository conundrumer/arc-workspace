"""Rank of gold forms in a saved pool by their distance to OUT. A form OUT reads is at distance 1, a form that only such a form reads at 2, and so on. Bits over uniform: log2 of the pool size less log2 of the node's rank by policy score. Writes one row per gold form that holds a node, then one table.

  features_helper_rank.py soak LABELS RANKS POINTS_STORE OUT
  features_helper_rank.py pool RUN_DIR SCORES POINTS_JSON OUT
"""
import collections, glob, json, math, os, random, re, statistics as st, sys
NAME = re.compile(r'&[A-Za-z_0-9.]+')


def distances(text):
    L = text.strip().split('\n')
    out = next((x for x in L if x.startswith('(OUT')), None)
    forms = [x for x in L if not x.startswith('(OUT')]
    heads = collections.defaultdict(list)
    for i, x in enumerate(forms):
        heads[NAME.search(x)[0]].append(i)
    reads = [{j for n in NAME.findall(x) for j in heads.get(n.split('.')[0], ()) if j != i} for i, x in enumerate(forms)]
    d = {}; now = {j for n in NAME.findall(out or '') for j in heads.get(n.split('.')[0], ())}; k = 1
    while now:
        for i in now:
            d[i] = k
        now = {j for i in now for j in reads[i]} - set(d); k += 1
    return forms, d


def bits(score, token, band=None):
    v = score[token]; a = list(score.values()) if band is None else [x for k, x in score.items() if band[k] == band[token]]
    rank = 1 + sum(x > v for x in a) + (sum(x == v for x in a) - 1) / 2
    return math.log2(len(a)) - math.log2(rank)


def depth_band(d):
    return '1' if d <= 1 else '2-3' if d <= 3 else '4-6' if d <= 6 else '7+'


def soak(labels, ranks, store):
    idx = collections.defaultdict(list)
    for e in os.scandir(store):
        if not e.name.endswith('.building'):
            idx[e.name[:8]].append(e.path)
    rows = []; have = collections.Counter(); skip = 0
    for f in sorted(glob.glob(labels + '/*.json')):
        v = json.load(open(f)); t = v['task']; c = v.get('best')
        rf = f'{ranks}/{t}.json'
        if not c or not os.path.exists(rf):
            continue
        text = None
        for p in idx[t]:
            if json.load(open(p + '/point.json'))['case'] == c:
                text = open(p + '/gold.arclog').read(); break
        if text is None:
            skip += 1; continue
        forms, d = distances(text)
        if len(forms) != v['sizes'][c]:
            skip += 1; continue
        z = json.load(open(rf)); score, bd = z['score'], z['band']
        have.update(d.values())
        best = {}
        for h in v['hits']:
            for cc, i in h['hit']:
                if cc == c and i in d and str(h['token']) in score:
                    b = bits(score, str(h['token']))
                    if i not in best or b > best[i][0]:
                        best[i] = (b, h['depth'], bits(score, str(h['token']), bd))
        rows += [dict(task=t, form=i, distance=d[i], bits=b, depth=dp, bits_band=q) for i, (b, dp, q) in best.items()]
    print('skipped tasks, gold changed or no point', skip, flush=True)
    return rows, have


def pool(run, scores, points):
    gold = {x['task']: x['gold_sexp'] for x in json.load(open(points))}
    rows = []; have = collections.Counter(); skip = 0
    for f in sorted(glob.glob(run + '/*.events.jsonl')):
        t = os.path.basename(f).split('.')[0]; sf = f'{scores}/{t}.json'
        if t not in gold or not os.path.exists(sf):
            skip += 1; continue
        forms, d = distances(gold[t]); z = json.load(open(sf)); score = {str(k): v for k, v in z['score'].items()}; bd = {str(k): depth_band(v) for k, v in z['depth'].items()}
        have.update(d.values()); best = {}
        for l in open(f):
            try:
                e = json.loads(l)
            except ValueError:
                continue
            if e['event'] == 'cover' and e['draw'] > 0 and e['gold'] in d and str(e['node']) in score:
                b = bits(score, str(e['node'])); i = e['gold']
                if i not in best or b > best[i][0]:
                    best[i] = (b, e['depth'], bits(score, str(e['node']), bd))
        rows += [dict(task=t, form=i, distance=d[i], bits=b, depth=dp, bits_band=q) for i, (b, dp, q) in best.items()]
    print('skipped tasks', skip, flush=True)
    return rows, have


mode, a, b, c, out = sys.argv[1:6]
rows, have = (soak if mode == 'soak' else pool)(a, b, c)
with open(out + '.rows.jsonl.new', 'w') as g:
    for r in rows:
        g.write(json.dumps(r) + '\n')
os.replace(out + '.rows.jsonl.new', out + '.rows.jsonl')
band = lambda d: '3+' if d >= 3 else str(d)
H = collections.Counter()
for d, n in have.items():
    H[band(d)] += n
print('distance | gold forms | reached | tasks | median bits | mean bits, task bootstrap 95% | mean bits in own depth band, 95% | median node depth', flush=True)
rng = random.Random(0)
by = collections.defaultdict(lambda: collections.defaultdict(list))
for r in rows:
    by[band(r['distance'])][r['task']].append(r)
for k in ('1', '2', '3+'):
    v = by[k]; R = [x for t in v.values() for x in t]
    if not R:
        print(k, '|', H[k], '| 0'); continue
    T = list(v); mk = lambda key: lambda p: sum(sum(x[key] for x in v[t]) for t in p) / sum(len(v[t]) for t in p)
    m = mk('bits'); q = mk('bits_band')
    s = sorted(m([rng.choice(T) for _ in T]) for _ in range(2000)); u = sorted(q([rng.choice(T) for _ in T]) for _ in range(2000))
    print(f"{k} | {H[k]} | {len(R)} | {len(T)} | {st.median(x['bits'] for x in R):.2f} | {m(T):.2f} ({s[50]:.2f} {s[1949]:.2f}) | {q(T):.2f} ({u[50]:.2f} {u[1949]:.2f}) | {st.median(x['depth'] for x in R)}", flush=True)
