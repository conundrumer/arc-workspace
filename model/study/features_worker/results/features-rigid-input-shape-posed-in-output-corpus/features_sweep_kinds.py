"""Most positive tasks hit by any grid form, by shape kind and match.

  features_sweep_kinds.py SWEEP_ROWS...
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
names = json.load(open(HERE + 'sweep-forms.json'))
rows = []
for p in sys.argv[1:]:
    rows += [json.loads(x) for x in open(p)]
pos = collections.Counter()
neg = collections.Counter()
for r in rows:
    if r['whole'][0] + r['whole'][1]:
        continue
    for j in r['hits']:
        if r['group'] == 'positive':
            pos[int(j)] += 1
        elif r['group'] == 'plain':
            neg[int(j)] += 1
best = {}
for j, n in enumerate(names):
    x = n.split('/')
    k = (x[0], x[2])
    if k not in best or pos[j] > best[k][0]:
        best[k] = (pos[j], neg[j], n)
for k, v in sorted(best.items()):
    print(k, v)
