#!/usr/bin/env python
"""Which facts a fit's trees split on, with the facts named. Reads fit lines only, no held rows.

  python features_ps_learned.py ARM    writes learned-ARM.json and prints the top facts over all keys, and the top per key
"""
import collections
import glob
import json
import os
import sys

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')
import features_perrel_lib as L  # noqa: E402
import features_ps_read as RD  # noqa: E402

arm = sys.argv[1]
V = L.Vocabs(L.OUT + 'vocab-%s.json' % arm)
heads = V.list('heads')
names = L.NAMES
comp, rel = V.list('comp'), V.list('rel')


def nm(f):
    k, c, t = f
    if k == 'x':
        return '%s>=%.3g' % (names[int(c)], t)
    if k == 't':
        return heads[int(c)]
    if k == 'c':
        return 'self-comp:' + comp[int(c)]
    return 'self-rel:' + rel[int(c)]


def walk(t, c):
    if isinstance(t, list):
        f = nm(t[0])
        c[f.split('>=')[0]] += 1
        walk(t[1], c), walk(t[2], c)


tot = collections.Counter()
per = {}
for d in RD.lines(arm):
    if 'folds' not in d:
        continue
    r = RD.chosen(d)
    c = collections.Counter()
    for s in d['stumps'][:r]:
        if s[0] == 'T':
            walk(s[1], c)
    tot += c
    per[d['key']] = dict(rounds=r, pos=d['pos'], top=c.most_common(8))
n = sum(tot.values())
json.dump(dict(total=n, top=tot.most_common(80), keys=per), open(L.ME + 'learned-%s.json' % arm, 'w'), indent=1)
print(n, [(k, round(v / n, 3)) for k, v in tot.most_common(30)])
