"""How much the bundled policy favors gold nodes when it picks: each scope's slots on gold nodes against the share a uniform pick over the nodes then alive would give. Split by the gold node's depth, DET apart, with a task-level bootstrap."""
import collections, glob, json, os, random, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SC = re.compile(r'"scope": ?\[([^\]]*)\]')
TK = re.compile(r'"token": ?"(\d+)"')
DP = re.compile(r'"depth": ?(\d+)')
rec = sys.argv[1]
B = [(1, 1, '1'), (2, 3, '2-3'), (4, 6, '4-6'), (7, 99, '7+')]
bucket = lambda x: next(n for a, b, n in B if a <= x <= b)
per = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0]))  # band -> task -> [slots, uniform]
for lab in sorted(glob.glob(os.environ.get('LABELS', HERE + '/labels') + '/*.json')):
    v = json.load(open(lab)); task = v['task']
    gold = {}
    for h in v['hits']:
        gold[h['token']] = bucket(h['depth'])
    f = glob.glob(f'{rec}/{task}*.zst')
    if not f or not gold:
        continue
    seen = 0; alive = collections.Counter()
    src = subprocess.Popen(['zstd', '-dcq', f[0]], stdout=subprocess.PIPE)
    for raw in src.stdout:
        s = raw.decode('utf8', 'ignore')
        m, q = TK.search(s), SC.search(s)
        if q and q[1].strip() and seen:
            sc = [x.strip().strip('"') for x in q[1].split(',')]
            for b in alive:
                per[b][task][1] += len(sc) * alive[b] / seen
            for t in sc:
                if t in gold:
                    per[gold[t]][task][0] += 1
        if m:
            seen += 1
            if m[1] in gold:
                alive[gold[m[1]]] += 1
print('band tasks slots uniform enrichment 90%')
rng = random.Random(0)
for _, _, b in B:
    d = per[b]
    if not d:
        continue
    ts = list(d); s = sum(d[t][0] for t in ts); u = sum(d[t][1] for t in ts)
    boot = sorted((lambda p: sum(d[t][0] for t in p) / max(sum(d[t][1] for t in p), 1e-9))([rng.choice(ts) for _ in ts]) for _ in range(2000))
    print(b, len(ts), round(s), round(u), round(s / max(u, 1e-9), 2), round(boot[100], 2), round(boot[1900], 2))
