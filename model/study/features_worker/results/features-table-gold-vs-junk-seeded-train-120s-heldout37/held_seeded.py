"""Fits seeded gold against junk on non-held seed level 1 pools, and reads one stated count on the held seed level 2 pools, by depth. Nothing is tuned on the held read."""
import collections, glob, json, os, statistics as st, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as M
H = os.path.dirname(os.path.abspath(__file__))
exec(open(H + '/census2_fit.py').read().split("print('tasks with scores'")[0])
HE = [json.loads(l) for l in open(H + '/census-seeded2.jsonl')]
HE = [dict(r, gold=r['seeded'], score=None) for r in HE if r['seeded'] or not r['gold']]
for kind, sets in (('RULE', ('shape', 'task')), ('RULE', ('shape', 'build', 'task')), ('INIT', ('shape', 'task')), ('INIT', ('shape', 'build', 'task'))):
    tr = [r for r in R if r['kind'] == kind]
    te = [r for r in HE if r['kind'] == kind]
    names = sorted(facts(tr[0], sets))
    m = M(max_iter=100, learning_rate=.1, max_leaf_nodes=15, min_samples_leaf=10, class_weight='balanced', random_state=0).fit(np.array([[facts(r, sets)[n] for n in names] for r in tr], float), [r['gold'] for r in tr])
    p = m.predict_proba(np.array([[facts(r, sets)[n] for n in names] for r in te], float))[:, 1]
    by = collections.defaultdict(list)
    for i, r in enumerate(te):
        by[r['task']].append(i)
    out = collections.defaultdict(list)
    for ix in by.values():
        j = np.sort([p[i] for i in ix if not te[i]['gold']])
        if not len(j):
            continue
        for i in ix:
            if te[i]['gold']:
                s = (np.searchsorted(j, p[i], 'left') + np.searchsorted(j, p[i], 'right')) / 2 / len(j)
                d = te[i]['depth']
                out['all'].append(s)
                out['depth 1 to 2' if d <= 2 else 'depth 3 to 4' if d <= 4 else 'depth 5 and more'].append(s)
    print(kind, '+'.join(sets), 'train gold', sum(r['gold'] for r in tr), {k: dict(n=len(v), auc=round(float(st.mean(v)), 3), top1=round(sum(x >= .99 for x in v) / len(v), 3), top10=round(sum(x >= .9 for x in v) / len(v), 3)) for k, v in sorted(out.items())}, flush=True)
