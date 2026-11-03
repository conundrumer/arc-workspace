#!/usr/bin/env python
"""Grid facts of each task in the fit and held arrays, with the code of features-init-component-grid-fact-auc-nonheld. A fact reads train pairs and test inputs. Writes scratch/grid-facts.json and scratch/grid-facts-names.json."""
import json
import math
import os
import sys

import numpy as np

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-init-component-grid-fact-auc-nonheld')
import features_grid_fact_rows as G  # noqa: E402

tasks = set()
for n in ('train-before-0', 'train-before-1', 'train-before-2', 'test-before', 'test-parents', 'held'):
    tasks |= set(np.load(ME + 'scratch/data-%s.npz' % n)['m_task'].tolist())
names = sorted(G.DEFS)
cls = [v for k, v in vars(G).items() if isinstance(v, type) and 'objects' in vars(v)][0]
out = {}
for t in sorted(tasks):
    v = cls(G.load(t))
    row = []
    for n in names:
        try:
            x = float(G.DEFS[n][0](v))
            row.append(x if math.isfinite(x) else -1.0)
        except Exception:  # noqa: BLE001
            row.append(-1.0)
    out[t] = row
json.dump(out, open(ME + 'scratch/grid-facts.json', 'w'))
json.dump(names, open(ME + 'scratch/grid-facts-names.json', 'w'))
print(len(out), 'tasks', len(names), 'facts')
