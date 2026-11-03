#!/usr/bin/env python
"""What a per-relation fit learned (item 10): the copy of features_ps_learned.py. The facts that the trees of each key split on at the chosen rounds, named, and as pairs from D (key, sparse token). Reads fit lines only, no held rows.

  features_dagc_env.sh 1 features_dagc_plearned.py ARM    writes perrel/learned-ARM.json and prints the top facts over all keys, and the pairs

The fact list passes check_columns and check_tokens (features_dagc_pread.check_model). A sparse token is a fact of D, of the scope or of the pick's slot (prefix:, scope:, and the families of features_dagc_facts), so a pair (key, token) restates what a model learned as a function of D.
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_dagc_fitlib as L  # noqa: E402
import features_dagc_pread as RD  # noqa: E402

arm = sys.argv[1]
V = L.Vocabs(L.ROWS + 'vocab-%s.json' % arm)
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


def walk(t, c, tk):
    if isinstance(t, list):
        f = nm(t[0])
        c[f.split('>=')[0]] += 1
        if t[0][0] == 't':
            tk[f] += 1
        walk(t[1], c, tk), walk(t[2], c, tk)


tot = collections.Counter()
pairs = collections.Counter()
per = {}
ls = RD.lines(arm)
cols, toks = RD.check_model(ls, V)
for d in ls:
    if 'folds' not in d:
        continue
    r = RD.chosen(d)
    c, tk = collections.Counter(), collections.Counter()
    for s in d['stumps'][:r]:
        if s[0] == 'T':
            walk(s[1], c, tk)
    tot += c
    for t, n in tk.items():
        pairs[(d['key'], t)] += n
    per[d['key']] = dict(rounds=r, pos=d['pos'], top=c.most_common(8), tokens=tk.most_common(8))
n = sum(tot.values())
json.dump(dict(total=n, top=tot.most_common(80), pairs=[[k, t, v] for (k, t), v in pairs.most_common(200)], keys=per, columns=cols, tokens=toks, check='check_columns and check_tokens pass'), open(L.ROWS + 'learned-%s.json' % arm, 'w'), indent=1)
print(n, [(k, round(v / n, 3)) for k, v in tot.most_common(30)] if n else 'no splits')
print('pairs (key, token from D):', pairs.most_common(20))
