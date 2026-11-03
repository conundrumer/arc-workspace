"""Compares each gold relation's rows with the rows of the same name in a program run on the swapped task."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from lib import *
norm = lambda r: frozenset(((n if not n[1:].isdigit() else ''), v) for n, v in r)
S = os.path.dirname(os.path.abspath(__file__)); T = sys.argv[2] if len(sys.argv) > 2 else '1f642eb9'
swap(f'{S}/tasks/{T}.json', f'{S}/swapped/{T}.json')
g = tables(f'{S}/gold', f'{S}/tasks', T)
p = tables(f'{S}/{sys.argv[1]}', f'{S}/swapped', T)
print(f'{"relation":24}{"columns":34} ' + ' '.join(f'ex{i}:gold/same/extra' for i in range(3)))
for name, ex in g.items():
    cols = [n for n, _ in next((r for rows in ex.values() for r in rows), ())]
    cells = []; ok = name in p
    for i in sorted(ex):
        G = {norm(r) for r in ex[i]}; P = {norm(r) for r in p.get(name, {}).get(i, ())}
        ok = ok and G == P
        cells.append(f'{len(G)}/{len(G&P)}/{len(P-G)}'.ljust(19))
    print(f'{name:24}{",".join(cols):34} ' + ' '.join(cells) + (' MATCH' if ok else ' differ'))
print('in the program only:', [n for n in p if n not in g])
c = arclog.corpus_tables(f'{S}/{sys.argv[1]}', f'{S}/swapped', task_ids=[T], all_cases=False)[0][0]
t = c.tables; et = ints(c,'entries','table'); vals = array.array('i'); vals.frombytes(c.values)
ae, ad, ar, ao = (ints(c,'assigned',k) for k in ('entry','det','rows','offset'))
seen = {}
for a in range(len(ae)):
    n = t['relation_name'][et[ae[a]]]; d = t['det_relations'][et[ae[a]]]
    if len(d) == 1: seen.setdefault(n, set()).add(tuple(vals[ao[a]:ao[a]+ar[a]].tolist()))
print('DET values on the outputs:', seen)
