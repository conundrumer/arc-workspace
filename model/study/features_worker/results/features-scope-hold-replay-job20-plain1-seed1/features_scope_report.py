"""Hold rates of replayed scope rules by parent count: mean share of visits whose scope holds all parents, forms held by any visit, median forms in a scope. Reads partial output.

  features_scope_report.py OUT
"""
import collections, glob, json, os, statistics as st, sys
out = sys.argv[1]
base = None
for d in sorted(x for x in glob.glob(out + '/*') if os.path.basename(x) != 'scores'):
    R = [json.load(open(f)) for f in glob.glob(d + '/*.json')]
    by = collections.defaultdict(list); log = collections.defaultdict(list); anyh = collections.Counter()
    for r in R:
        for x in r['rows']:
            p = min(x['parents'], 3)
            by[p].append(x['hold'] / max(r['visits'], 1)); log[p].append(x['logged'] / max(r['visits'], 1)); anyh[p] += x['hold'] > 0
    fit = [v for r in R for v in r['fit'].values()]
    print(os.path.basename(d), 'tasks', len(R), 'median forms', st.median(r['forms'] for r in R) if R else 0, 'scopes', sum(r['scopes'] for r in R), 'join fit of parent sets', f'{sum(fit)}/{len(fit)}')
    if any('pair_fit' in r for r in R):
        print('   pool pairs that fit, median task', round(st.median(r['pair_fit'] for r in R if 'pair_fit' in r), 3))
    for p in sorted(by):
        print(f'   {p if p < 3 else "3+"} parents: forms {len(by[p])}, hold {st.mean(by[p]):.4f} (logged plain {st.mean(log[p]):.4f}), held by any visit {anyh[p]}')
