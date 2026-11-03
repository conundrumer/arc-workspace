#!/usr/bin/env python
"""Item 10 copy of features_ps_tune.py, on the rows of perrel/. A fit arm's tune read on non-held rows, from the rows the fit wrote: per key, out-of-fold solo gain at the rounds that `chosen` keeps, summed over keys, in bits per pick of the tune set.

  python features_dagc_tune.py ARM[,ARM...]    prints one line per arm, and appends it to perrel/tune-table.tsv. The gains are sums over picks weighted by the pick weight, as the fit wrote them.

Held rows play no part. Solo gains add over keys only roughly, as each is read alone. This compares arms and isn't a measure.
"""
import glob
import json
import os
import sys

import numpy as np

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
ROWS = ME + 'perrel/'
os.makedirs(ROWS, exist_ok=True)
CPS = (0, 1, 3, 6, 12, 25, 50, 100, 200, 400)
out = open(ROWS + 'tune-table.tsv', 'a')
for arm in sys.argv[1].split(','):
    tot = np.zeros(2)
    keys = rounds = 0
    picks = None
    for p in glob.glob(ROWS + 'rows-%s-w*.jsonl' % arm):
        for x in open(p):
            d = json.loads(x)
            if 'folds' not in d:
                continue
            t = np.zeros(len(CPS))
            for f in d['folds']:
                t += np.array(f['before'][0]) + np.array(f['parents'][0])
            i = int(np.argmax(t))
            if t[i] <= 0:
                continue
            keys += 1
            rounds += CPS[i]
            tot[0] += sum(f['before'][0][i] for f in d['folds'])
            tot[1] += sum(f['parents'][0][i] for f in d['folds'])
    line = '%s\tkeys %d\trounds %d\tbits fit rows out of fold %.0f\tbits tune rows out of fold %.0f' % (arm, keys, rounds, tot[0], tot[1])
    print(line)
    out.write(line + '\n')
