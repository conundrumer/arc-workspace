"""Throwaway look at census-base.jsonl: rows by kind and scope, and the form counts."""
import collections
import json
import os

B = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/'
W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/'
rows = [json.loads(x) for x in open(B + 'census-base.jsonl')]
held = set(open(W + 'held/tasks.txt').read().split())
print(sorted(held))
print(collections.Counter((r['kind'], r['scope']) for r in rows))
print(collections.Counter((r['kind'], r['scope'], bool(r['bad']), r['dead'] is not None, r['left'] > 0, r.get('match')) for r in rows))
pts = {p['task']: p['gold_sexp'] for p in json.load(open(B + 'points-base.json'))}
fs = json.load(open(B + 'forms-base.json'))
print(collections.Counter(f[0] for f in fs), len({f[4] for f in fs}))
tot, inc = collections.Counter(), collections.Counter()
forms = {(f[4], f[5]) for f in fs}
out = []
for t in held:
    ls = [x for x in pts[t].splitlines() if x.strip()]
    for i, x in enumerate(ls):
        k = x.split()[0].lstrip('(')
        tot[k] += 1
        if (t, i) in forms:
            inc[k] += 1
        else:
            out.append((t, i, x[:80]))
print(tot, inc)
print(out[:20])
r = [r for r in rows if r['task'] == '5961cc34' and r['kind'] == 'RULE' and r['scope'] == 'before'][3]
print(json.dumps(r)[:1800])
ls = [x for x in pts['5961cc34'].splitlines() if x.strip()]
print(len(ls))
print('\n'.join(ls[:r['line'] + 1])[:2500])
print(r['line'])
ks = collections.Counter()
for r in rows:
    for d in r['detail']:
        for k in d['cur']:
            ks[k] += 1
print(ks)
ks = collections.Counter()
for r in rows:
    for k in r['parts']:
        ks[k] += 1
print(ks)
p = W + 'sampler-relation-pick-read-heldout431-census/'
print([(e.name, e.stat().st_size) for e in os.scandir(p)])
f = json.load(open(p + 'forms_all.json'))
print(len(f), f[:2])
