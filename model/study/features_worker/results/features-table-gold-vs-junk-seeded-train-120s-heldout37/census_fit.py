"""Can table facts tell covered gold from junk? Fits on census rows with folds by task, and reads the AUC inside a task and the median rank share of gold. Age (draw) is left out. Gold is the label only. Clause text gives only counts and the component's name, never an atom's place.

Fact sets: shape (columns, rows, types), build (kind, component, read counts), task (sources, product, cells against the pairs), pool (class members, readers).
"""
import collections, json, os, statistics as st, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as M
H = os.path.dirname(os.path.abspath(__file__))
R = [json.loads(l) for l in open(H + '/census-plain-snapshot.jsonl')]
TYPES = sorted({t for r in R for t in r['types']})
OPS = [k for k, v in collections.Counter(r['op'] for r in R).most_common() if v >= 20]


def facts(r, sets):
    d = {}
    if 'shape' in sets:
        d.update(columns=r['columns'], rows=np.log2(1 + r['rows']), same=r['same_each_example'])
        c = collections.Counter(r['types'])
        d.update({'t_' + t: c[t] for t in TYPES})
    if 'build' in sets:
        d.update(depth=r['depth'], parents=r['parents'], reads=r['reads'], distinct=r.get('distinct_reads', 0), fixed=r['fixed'], negated=r['negated'], union=r['union'], kind_rule=int(r['kind'] == 'RULE'), kind_init=int(r['kind'] == 'INIT'))
        d.update({'op_' + o: int(r['op'] == o) for o in OPS})
    if 'task' in sets:
        s = r['sources']
        d.update(src_none=int(not s), src_shape=int('shape' in s), src_colors=int('colors' in s), src_output=int('output' in s), product=int(r['product'] > 0))
        for k in ('jaccard', 'covers_changed', 'share_changed', 'of_grid'):
            d[k] = r.get(k) if r.get(k) is not None else np.nan
    if 'pool' in sets:
        d.update(members=r['members'], readers=np.log2(1 + r['readers']))
    return d


def run(rows, sets, folds=5):
    names = sorted(facts(rows[0], sets))
    X = np.array([[facts(r, sets)[n] for n in names] for r in rows], float)
    y = np.array([r['gold'] for r in rows])
    tasks = sorted({r['task'] for r in rows})
    fold = {t: i % folds for i, t in enumerate(tasks)}
    f = np.array([fold[r['task']] for r in rows])
    p = np.zeros(len(rows))
    for k in range(folds):
        m = M(max_iter=120, learning_rate=.1, max_leaf_nodes=15, min_samples_leaf=10, class_weight='balanced', random_state=0)
        m.fit(X[f != k], y[f != k])
        p[f == k] = m.predict_proba(X[f == k])[:, 1]
    aucs, share, top = [], [], collections.Counter()
    by = collections.defaultdict(list)
    for i, r in enumerate(rows):
        by[r['task']].append(i)
    for t, ix in by.items():
        g = [i for i in ix if y[i]]
        j = [i for i in ix if not y[i]]
        if not g or not j:
            continue
        pj = np.sort(p[j])
        s = [np.searchsorted(pj, p[i]) / len(j) for i in g]
        aucs.append(st.mean(s))
        for v in s:
            share.append(1 - v)
            top['top 1%'] += v >= .99
            top['top 10%'] += v >= .9
    n = len(share)
    return dict(tasks=len(aucs), gold=n, auc=round(st.mean(aucs), 3), median_rank_share=round(st.median(share), 3), **{k: round(v / n, 3) for k, v in top.items()})


print('classes', len(R), 'tasks', len({r['task'] for r in R}), 'gold', sum(r['gold'] for r in R))
for name, rows in (('RULE', [r for r in R if r['kind'] == 'RULE']), ('non-DET', [r for r in R if r['kind'] != 'DET'])):
    for sets in (('shape',), ('build',), ('task',), ('pool',), ('shape', 'build', 'task'), ('shape', 'build', 'task', 'pool')):
        print(' ', name, '+'.join(sets), run(rows, sets), flush=True)
