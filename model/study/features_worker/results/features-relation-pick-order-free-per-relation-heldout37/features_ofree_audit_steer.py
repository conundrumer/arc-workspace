#!/usr/bin/env python
"""The names the live steer file holds that the audit bans. Writes audit-live-steer-names.txt."""
import os
import pickle
import re
import sys

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
P = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-helper-pool-gold-v3-helper-forms-a036da074/models-context/relR4_o.pkl'
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/model/study/sampler')
BANNED = re.compile(r'(_last|last_|touch|recent|^rk1c\.c2_|^rk2f\.f5_(last|same|run)|^rk2d\.d3_x_|^rk2d\.d3_not_after|b_follows|^b_repeat|^b_fits_enum|recency|first_at)')
ck = pickle.load(open(P, 'rb'))
names = ck['hgb']['names']
hits = sorted(n for n in names if BANNED.search(n) and not n.startswith('rk3o.'))
with open(ME + 'audit-live-steer-names.txt', 'w') as f:
    f.write('%d of %d names of relR4_o.pkl read lexical order\n' % (len(hits), len(names)))
    f.write('\n'.join(hits) + '\n')
print(len(hits), 'of', len(names))
print(hits)
