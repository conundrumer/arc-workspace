#!/usr/bin/env python
"""Forms covered at 60, 300 and 600 s on Kaggle version 5, a reference column that needs gold. Reads the replay labels (node token, gold form index) and the cuts of signal-cheap.jsonl.

  features_v5_cover.py LABELS_DIR CHEAP.jsonl OUT.jsonl
"""
import glob
import json
import os
import sys

labels, cheap, out = sys.argv[1:4]
C = {r['task']: r for r in map(json.loads, open(cheap)) if r['run'] == 'kaggle-v5'}
with open(out + '.new', 'w') as g:
    for f in sorted(glob.glob(labels + '/*.json')):
        v = json.load(open(f))
        t = v['task']
        if t not in C:
            continue
        c = v.get('best')
        cov = {}
        for S in ('60', '300', '600'):
            n = C[t]['cuts'][S]['nodes']
            cov[S] = len({i for h in v['hits'] if int(h['token']) < n for cc, i in h['hit'] if cc == c})
        g.write(json.dumps(dict(task=t, covered=cov)) + '\n')
os.replace(out + '.new', out)
