import json, math, statistics as st, collections, sys
R = [json.loads(l) for l in open(sys.argv[1])]
P = [(r, p) for r in R for p in r['picks']]
print('points', len(R), 'errors', sum('error' in r for r in R), 'picks', len(P), 'with row', sum(p['row'] is not None for _, p in P))
print('mean bits per pick', round(st.mean(-math.log2(max(p['q'], 1e-9)) for _, p in P), 2), 'median options', st.median(p['n'] for _, p in P), 'median scope forms', st.median(r.get('scope', 0) for r in R))
k = collections.defaultdict(list)
for r, p in P:
    g = p['gold']; kk = 'derived' if g.startswith('&') else 'op' if g in ('NOT', '=', '!=', '<', '<=', '>', '>=') else 'base'
    o = p['row']['options'] if p['row'] else []
    d = sum(x['kind'] == 'relation' or x.get('name', '').startswith('&') for x in o)
    gp = next((x['p'] for x in o if x.get('name') == g or x.get('tok') == g), None)
    k[kk].append((-math.log2(max(p['q'], 1e-9)), p['n'], d, gp))
for kk, v in k.items():
    print(kk, len(v), 'bits', round(st.mean(x[0] for x in v), 2), 'options', st.median(x[1] for x in v), 'derived options', st.median(x[2] for x in v), 'uniform over all', round(st.mean(math.log2(max(x[1], 1)) for x in v), 2))
r = next(p['row'] for _, p in P if p['row'])
print(sorted(r), json.dumps(r['options'][0])[:260]); print(collections.Counter(o['kind'] for o in r['options']))
