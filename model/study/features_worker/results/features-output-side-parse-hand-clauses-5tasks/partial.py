"""For each gold relation, the largest set of its columns that a relation of the same name gives exactly, on every train example."""
import sys, os, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
S = os.path.dirname(os.path.abspath(__file__)); prog, T = sys.argv[1:3]
swap(f'{S}/tasks/{T}.json', f'{S}/swapped/{T}.json')
g = tables(f'{S}/gold', f'{S}/tasks', T); p = tables(f'{S}/{prog}', f'{S}/swapped', T)
def tup(rows): return [tuple(v for _, v in r) for r in rows]
for name, ex in g.items():
    if name.startswith('ex_'): continue
    G = {i: tup(ex[i]) for i in ex}; w = len(next((r for rs in G.values() for r in rs), ()))
    names = [n for n, _ in next((r for rs in ex.values() for r in rs), ())]
    if name not in p: print(f'{name:30} no table on the output side'); continue
    P = {i: tup(p[name].get(i, ())) for i in ex}; pw = len(next((r for rs in P.values() for r in rs), ()))
    best = None
    for k in range(w, 0, -1):
        for sub in itertools.combinations(range(w), k):
            for m in itertools.permutations(range(pw), k):
                if all({tuple(r[j] for j in sub) for r in G[i]} == {tuple(r[j] for j in m) for r in P[i]} for i in ex):
                    best = sub; break
            if best: break
        if best: break
    full = best is not None and len(best) == w and all(len(set(G[i])) == len(set(P[i])) for i in ex)
    print(f'{name:30} {"all columns" if full else ("columns " + ",".join(names[j] for j in best) + " of " + ",".join(names)) if best else "no column agrees"}')
print('sample gold target', sorted(next(iter(g['&target'].values())))[:1] if '&target' in g else '')
print('sample gold marker', sorted(next(iter(g['&marker'].values())))[:1] if '&marker' in g else '')
print('sample gold block_cell', sorted(next(iter(g['&block_cell'].values())))[:1] if '&block_cell' in g else '')
