"""Bins of the held-out ramp on order-free bits: deciles of the hardest form over training stems of gold-v3-dag-bits/pod-all, for the 59 tasks of gold-heldout-ramp-pass1.

  python3 gold_heldout_ramp_dag.py
"""
import bisect, collections, glob, json, os, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__))
D = HERE + '/../..'
rows = {}
for f in glob.glob(HERE + '/../gold-v3-dag-bits/pod-all/rows-*.jsonl'):
    for l in open(f):
        r = json.loads(l)
        rows[r['task']] = r
h37 = open(D + '/features-worker/arm/held-tasks.txt').read().split()
h99 = set(open(D + '/features-worker/arm/eval-tasks.txt').read().split())
picks = open(HERE + '/../gold-heldout-ramp-pass1/ramp-fold.txt').read().split()
old = json.load(open(HERE + '/../gold-heldout-ramp-pass1/bins.json'))


def hardest(r):
    """The largest form's bits, and whether every form has a figure."""
    if r.get('error'):
        v = [f.get('bits') for f in r.get('forms') or [] if f.get('status') != 'no draw']
        return (max((x for x in v if x is not None), default=None), False)
    v = [f.get('bits') for f in r['forms'] if f.get('status') != 'no draw']
    got = [x for x in v if x is not None]
    return (max(got) if got else None, len(got) == len(v))


train = {t: hardest(r) for t, r in rows.items() if t not in h99}
whole = sorted(b for b, ok in train.values() if ok and b is not None)
n = len(whole)
inner = [whole[0] + 0 for _ in ()]
inner = []
for k in range(1, 10):
    p = k * (n - 1) / 10
    i = int(p)
    inner.append(whole[i] + (whole[min(i + 1, n - 1)] - whole[i]) * (p - i))
tasks = {}
for t in h37 + picks:
    b, ok = hardest(rows[t])
    tasks[t] = dict(task=t, source='eval-37' if t in h37 else 'train-fill', bits=b, whole=ok, bin=bisect.bisect_left(inner, b) if b is not None else None, old_bin=(old['tasks'].get(t, {}).get('bin') if isinstance(old['tasks'].get(t), dict) else old['tasks'].get(t)), lower_bound=not ok)
json.dump(dict(axis='largest form, order-free bits, or_q.walk', edges=[whole[0]] + inner + [whole[-1]], inner_edges=inner, training_stems=n, tasks=tasks), open(HERE + '/bins.json', 'w'), indent=1)
with open(HERE + '/heldout-ramp.jsonl', 'w') as f:
    for x in tasks.values():
        f.write(json.dumps(x) + '\n')
c = collections.Counter((x['bin'], x['source']) for x in tasks.values())
print('training stems with every form', n, 'of', len(train), 'edges', [round(x, 1) for x in inner])
print({b: (c[b, 'eval-37'], c[b, 'train-fill']) for b in range(10)}, 'no figure', c[None, 'eval-37'], c[None, 'train-fill'])
print('moved bin', sum(x['bin'] != x['old_bin'] for x in tasks.values()), 'by over 1', sum(x['bin'] is not None and x['old_bin'] is not None and abs(x['bin'] - x['old_bin']) > 1 for x in tasks.values()), 'partial', sum(x['lower_bound'] for x in tasks.values()))
