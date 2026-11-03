"""Fits gold against junk on non-held census rows, where gold is what search covered, and reads one stated count on a seeded held pool, where gold is there by construction. Nothing is tuned on the held read. Age and pool facts are left out.

  census_held.py SEEDED_ROWS
"""
import collections, json, os, statistics as st, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as M
H = os.path.dirname(os.path.abspath(__file__))
TR = [r for r in map(json.loads, open(H + '/census-plain.jsonl')) if r['kind'] != 'DET']
TE = [r for r in map(json.loads, open(sys.argv[1])) if r['kind'] != 'DET']
TYPES = sorted({t for r in TR for t in r['types']})
OPS = [k for k, v in collections.Counter(r['op'] for r in TR).most_common() if v >= 20]


def facts(r):
    c = collections.Counter(r['types'])
    s = r['sources']
    d = dict(columns=r['columns'], rows=np.log2(1 + r['rows']), same=r['same_each_example'], parents=r['parents'], reads=r['reads'], distinct=r.get('distinct_reads', 0), fixed=r['fixed'], negated=r['negated'], union=r['union'], kind_rule=int(r['kind'] == 'RULE'),
             src_none=int(not s), src_shape=int('shape' in s), src_colors=int('colors' in s), src_output=int('output' in s), product=int(r['product'] > 0))
    d.update({'t_' + t: c[t] for t in TYPES})
    d.update({'op_' + o: int(r['op'] == o) for o in OPS})
    for k in ('jaccard', 'covers_changed', 'share_changed', 'of_grid'):
        d[k] = r.get(k) if r.get(k) is not None else np.nan
    return d


names = sorted(facts(TR[0]))
X = lambda rows: np.array([[facts(r)[n] for n in names] for r in rows], float)
m = M(max_iter=120, learning_rate=.1, max_leaf_nodes=15, min_samples_leaf=10, class_weight='balanced', random_state=0).fit(X(TR), np.array([r['gold'] for r in TR]))
p = m.predict_proba(X(TE))[:, 1]
print('train classes', len(TR), 'gold', sum(r['gold'] for r in TR), 'tasks', len({r['task'] for r in TR}), '| held classes', len(TE), 'gold', sum(r['gold'] for r in TE), 'seeded gold', sum(r['gold'] and r['seeded'] for r in TE), 'tasks', len({r['task'] for r in TE}))
by = collections.defaultdict(list)
for i, r in enumerate(TE):
    by[r['task']].append(i)
out = collections.defaultdict(list)
for t, ix in by.items():
    j = np.sort([p[i] for i in ix if not TE[i]['gold']])
    if not len(j):
        continue
    for i in ix:
        r = TE[i]
        if r['gold']:
            s = np.searchsorted(j, p[i]) / len(j)
            for k in ('all gold', ('RULE' if r['kind'] == 'RULE' else 'INIT'), 'depth 1 to 2' if r['depth'] <= 2 else 'depth 3 to 4' if r['depth'] <= 4 else 'depth 5 and more'):
                out[k].append(s)
for k, v in sorted(out.items()):
    print('  %-18s n %4d AUC %.3f median rank share %.3f top 1%% %.3f top 10%% %.3f' % (k, len(v), st.mean(v), 1 - st.median(v), sum(x >= .99 for x in v) / len(v), sum(x >= .9 for x in v) / len(v)))
