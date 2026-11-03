"""Seeded gold against junk, folds by task, on whatever census rows exist. Seeded gold is there by construction, so the label doesn't depend on what search covered. Found gold that isn't seeded is left out. Age and pool facts are left out.

Populations: RULE, INIT, and plumbing, a RULE that reads one table, with no negation and no union. Fact sets: score (the ship7 node score), shape, build, task (sources, product, cells against pairs), new (output gain, survival, new information). All sets run on tasks with a node score, so rows compare.
"""
import collections, glob, json, os, statistics as st, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as M
H = os.path.dirname(os.path.abspath(__file__))
R = []
for f in glob.glob(H + '/census2-*.jsonl'):
    for l in open(f):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r['seeded'] or not r['gold']:
            R.append(r)
SC = {}
for f in glob.glob(H + '/scores/*.json'):
    SC[os.path.basename(f)[:-5]] = json.load(open(f))
R = [dict(r, gold=r['seeded'], score=SC[r['task']].get(str(r['token']))) for r in R if r['task'] in SC]
TYPES = sorted({t for r in R for t in r['types']})
OPS = [k for k, v in collections.Counter(r['op'] for r in R).most_common() if v >= 20]
num = lambda v: np.nan if v is None else v


def facts(r, sets):
    d = {}
    if 'score' in sets:
        d['score'] = num(r['score'])
    if 'shape' in sets:
        c = collections.Counter(r['types'])
        d.update(columns=r['columns'], rows=np.log2(1 + r['rows']), same=r['same_each_example'])
        d.update({'t_' + t: c[t] for t in TYPES})
    if 'build' in sets:
        d.update(parents=r['parents'], reads=r['reads'], distinct=r.get('distinct_reads', 0), fixed=r['fixed'], negated=r['negated'], union=r['union'])
        d.update({'op_' + o: int(r['op'] == o) for o in OPS})
    if 'task' in sets:
        s = r['sources']
        d.update(src_none=int(not s), src_shape=int('shape' in s), src_colors=int('colors' in s), src_output=int('output' in s), product=int(r['product'] > 0))
        for k in ('jaccard', 'covers_changed', 'share_changed', 'of_grid'):
            d[k] = num(r.get(k))
    if 'new' in sets:
        for k in ('output_gain', 'output_acc', 'nonempty', 'test_nonempty', 'size_spread', 'new_info'):
            d[k] = num(r.get(k))
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
        if y[f != k].sum() < 3:
            continue
        m = M(max_iter=100, learning_rate=.1, max_leaf_nodes=15, min_samples_leaf=10, class_weight='balanced', random_state=0)
        m.fit(X[f != k], y[f != k])
        p[f == k] = m.predict_proba(X[f == k])[:, 1]
    by = collections.defaultdict(list)
    for i, r in enumerate(rows):
        by[r['task']].append(i)
    aucs, val = [], []
    for ix in by.values():
        g = [i for i in ix if y[i]]
        j = np.sort([p[i] for i in ix if not y[i]])
        if not g or not len(j):
            continue
        s = [(np.searchsorted(j, p[i], 'left') + np.searchsorted(j, p[i], 'right')) / 2 / len(j) for i in g]
        aucs.append(st.mean(s))
        val += s
    n = len(val)
    return dict(tasks=len(aucs), gold=n, auc=round(float(st.mean(aucs)), 3) if aucs else None, top1=round(sum(v >= .99 for v in val) / max(n, 1), 3), top10=round(sum(v >= .9 for v in val) / max(n, 1), 3))


def single(rows):
    F = {'score': lambda r: r['score'], 'output gain': lambda r: r.get('output_gain'), 'low new info': lambda r: None if r.get('new_info') is None else -r['new_info'], 'nonempty': lambda r: r.get('nonempty'), 'test nonempty': lambda r: r.get('test_nonempty'), 'stable size': lambda r: None if r.get('size_spread') is None else -r['size_spread'], 'fewer columns': lambda r: -r['columns'], 'varies by example': lambda r: 1 - r['same_each_example']}
    out = {}
    for k, f in F.items():
        by = collections.defaultdict(lambda: ([], []))
        for r in rows:
            v = f(r)
            if v is not None:
                by[r['task']][r['gold']].append(v)
        a = []
        for j, g in by.values():
            if j and g:
                j = np.array(j, float)
                a.append(st.mean(float(((x > j) + .5 * (x == j)).mean()) for x in g))
        out[k] = (round(st.mean(a), 3), len(a)) if a else None
    return out


print('tasks with scores', len({r['task'] for r in R}), 'classes', len(R), 'seeded gold', sum(r['gold'] for r in R), flush=True)
plumb = [r for r in R if r['kind'] == 'RULE' and r.get('distinct_reads', 0) <= 1 and not r['negated'] and not r['union']]
for name, rows in (('plumbing', plumb), ('RULE', [r for r in R if r['kind'] == 'RULE']), ('INIT', [r for r in R if r['kind'] == 'INIT'])):
    print(name, 'classes', len(rows), 'gold', sum(r['gold'] for r in rows), single(rows), flush=True)
    for sets in (('score',), ('shape', 'build', 'task'), ('new',), ('shape', 'build', 'task', 'new'), ('score', 'shape', 'build', 'task', 'new')):
        print(' ', '+'.join(sets), run(rows, sets), flush=True)
