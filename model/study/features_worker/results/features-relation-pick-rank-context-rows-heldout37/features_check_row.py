#!/usr/bin/env python
"""Checks that a steer's factors on a row rebuilt from a walk equal its factors on the same pick's row in sampler-steers-context-rows-test."""
import collections
import io
import json
import sys

import numpy as np
import zstandard

import features_rel_crossfit as X
import features_rel_data as FD
import relsteer

s = relsteer.Scorer(X.STEER)
rows = collections.defaultdict(list)
for d in X.rows('test'):
    if d['order'] == 0:
        rows[d['task'], d['point'][0]].append(d)
n = same_opts = 0
gaps = []
for p in FD.records(sys.argv[1:]):
    if p['rec'] != 'rel' or 'rowopts' not in p:
        continue
    cand = [r for r in rows.get((p['task'], p['line']), ()) if r['k'] == p['k'] and r['phase'] == p['phase'] and [o['tok'] for o in r['options']] == [o['tok'] for o in p['rowopts']] and r['prefix'] == p['prefix']]
    n += 1
    if not cand:
        continue
    same_opts += 1
    row = dict(k=p['k'], phase=p['phase'], scope=p['scope'], prefix=p['prefix'], point_group={}, prefix_bases=p.get('prefix_bases') or [], prefix_depth=p.get('prefix_depth') or 0, options=[])
    for o in p['rowopts']:
        q = dict(tok=o['tok'], kind=o['kind'], name=o['tok'], p=o['p'], types=o.get('types') or [])
        if o.get('cols') is not None:
            q['columns'] = o['cols']
        if o.get('dag') is not None:
            q['dag'] = o['dag']
        row['options'].append(q)
    a, b = np.array(s.score(row)), np.array(s.score(cand[0]))
    gaps.append(float(np.abs(a - b).max()))
    if n >= 300:
        break
print('picks', n, 'with a row of the same options and prefix', same_opts, 'median max gap %.5f, 95th %.5f, largest %.5f' % (np.median(gaps), np.percentile(gaps, 95), max(gaps)))
