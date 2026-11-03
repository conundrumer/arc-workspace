#!/usr/bin/env python
"""Rows per key, by level, from the fit lines and the held tables: how many keys have too few rows to fit, and what share of held picks they hold."""
import json
import os

import numpy as np

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
import sys
sys.path.insert(0, ME)
import features_perrel_read as RD  # noqa: E402

out = {}
L = ['| Level | Keys with fit rows | Too few gold rows to fit (under 5) | Fit but chose no trees | With a model | Median gold rows, keys fit | Held picks whose gold key has no model | Held picks at keys under 30 fit gold rows |', '|---|---|---|---|---|---|---|---|']
for a in ('final-rel', 'final-comp', 'final-fam', 'final-hyb-noorder'):
    ls = RD.lines(a)
    r = json.load(open(ME + 'read-%s.json' % a))
    sparse = [d for d in ls if 'folds' not in d]
    fit = [d for d in ls if 'folds' in d]
    on = {d['key'] for d in fit if RD.chosen(d) > 0}
    tab = r['keys_table']
    nomodel = sum(k['n'] for k in tab if k['key'] not in on) / r['read_picks']
    low = sum(k['n'] for k in tab if k['fit'] < 30) / r['read_picks']
    row = dict(keys=len(ls), sparse=len(sparse), zero_rounds=len(fit) - len(on), with_model=len(on), median_gold_rows=float(np.median([d['pos'] for d in fit])), share_no_model=nomodel, share_under_30=low)
    out[a] = row
    L.append('| %s | %d | %d | %d | %d | %.0f | %.3f | %.3f |' % (a, row['keys'], row['sparse'], row['zero_rounds'], row['with_model'], row['median_gold_rows'], nomodel, low))
json.dump(out, open(ME + 'rows-per-key.json', 'w'), indent=1)
open(ME + 'rows-per-key.md', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
