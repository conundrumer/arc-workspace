"""Does a fit on seeded gold read how a seeded clause was written? Sets run with folds by task on seeded pools, then a model fit on all seeded rows ranks gold that search wrote itself, in unseeded pools, against junk there. A fit that reads writing style ranks those low."""
import collections, glob, json, os, statistics as st, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as M
H = os.path.dirname(os.path.abspath(__file__))
sys.argv = ['x']
src = open(H + '/census2_fit.py').read().split("print('tasks with scores'")[0]
exec(src)
PL = [json.loads(l) for l in open(H + '/census-plain.jsonl')]


def fit(rows, sets):
    names = sorted(facts(rows[0], sets))
    X = np.array([[facts(r, sets)[n] for n in names] for r in rows], float)
    return names, M(max_iter=100, learning_rate=.1, max_leaf_nodes=15, min_samples_leaf=10, class_weight='balanced', random_state=0).fit(X, [r['gold'] for r in rows])


def read(names, m, rows):
    p = m.predict_proba(np.array([[facts(r, tuple(SETS))[n] for n in names] for r in rows], float))[:, 1]
    by = collections.defaultdict(list)
    for i, r in enumerate(rows):
        by[r['task']].append(i)
    v, a = [], []
    for ix in by.values():
        g = [i for i in ix if rows[i]['gold']]
        j = np.sort([p[i] for i in ix if not rows[i]['gold']])
        if g and len(j):
            s = [(np.searchsorted(j, p[i], 'left') + np.searchsorted(j, p[i], 'right')) / 2 / len(j) for i in g]
            a.append(st.mean(s))
            v += s
    return dict(tasks=len(a), gold=len(v), auc=round(float(st.mean(a)), 3), top1=round(sum(x >= .99 for x in v) / len(v), 3), top10=round(sum(x >= .9 for x in v) / len(v), 3))


for kind in ('RULE', 'INIT'):
    rows = [r for r in R if r['kind'] == kind]
    pl = [dict(r, score=None) for r in PL if r['kind'] == kind and 'sources' in r]
    for sets in (('shape',), ('build',), ('task',), ('shape', 'task'), ('shape', 'build', 'task')):
        SETS = sets
        cv = run(rows, sets)
        n, m = fit(rows, sets)
        print(kind, '+'.join(sets), 'seeded folds', cv, '| search-written gold', read(n, m, pl), flush=True)
    w = [r for r in rows if r['gold']]
    j = [r for r in rows if not r['gold']]
    for name, f in (('parents', lambda r: r['parents']), ('reads', lambda r: r['reads']), ('fixed', lambda r: r['fixed']), ('distinct', lambda r: r.get('distinct_reads', 0))):
        print('  ', name, 'seeded gold', collections.Counter(min(f(r), 4) for r in w).most_common(5), 'junk', [(k, round(v / len(j), 3)) for k, v in collections.Counter(min(f(r), 4) for r in j).most_common(5)])
