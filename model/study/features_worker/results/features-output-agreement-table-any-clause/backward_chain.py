"""On one task: the output-side clauses go from the output to the input and no further. Prints each forward table, gold's and the nodes', that equals a table of that chain, whole or on some of its columns."""
import itertools, json, os, re, sys
f = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agree_tables.py'); __file__ = f; T = sys.argv[1]; chain = open(sys.argv[2]).read(); sys.argv = [f, 'x']
exec(open(f).read().split("if sys.argv[1] == 'one'")[0].replace('tuple(sorted(map(repr, row)))', 'tuple(map(repr, row))'))
d = f'{W}/{T}'; p = open(f'{d}/prog/{T}.arclog').read(); j = p.rindex('(OUT')
os.makedirs(f'{d}/chain', exist_ok=True); open(f'{d}/chain/{T}.arclog', 'w').write(p[:j] + chain + '\n\n' + p[j:]); subprocess.run(['cp', f'{d}/prog/{T}.arcdata', f'{d}/chain/'])
tb, amb = tables(f'{d}/chain', f'{d}/tasks', T); n = len(json.load(open(f'{ROOT}/data/tasks/{T}.json'))['train'])
back = {x: [v.get((2, e), frozenset()) for e in range(n)] for x, v in tb.items() if x.startswith('&b_') and x not in ('&b_region.step',)}
real = lambda a: [{tuple(sorted(r)) for r in rs} for rs in a]
for x in back: print('chain', x, 'columns', len(next((r for rs in back[x] for r in rs), ())), 'empty' if not any(back[x]) else '')
for s, keep in (('gold', lambda x: not re.match(r'&(f\d|b_)', x)), ('node', lambda x: re.match(r'&f\d', x))):
    for x in sorted(filter(keep, tb)):
        if x in amb: continue
        a = [tb[x].get((1, e), frozenset()) for e in range(n)]
        if not any(a): continue
        w = len(next(r for rs in a for r in rs)); hits = []
        for y, b in back.items():
            c = len(next((r for rs in b for r in rs), ()))
            if not c or c > w: continue
            if c == w and real(a) == real(b): hits.append(y + ' whole'); continue
            if c < w and any(all({tuple(sorted(r[k] for k in sub)) for r in a[e]} == {tuple(sorted(r)) for r in b[e]} for e in range(n)) for sub in itertools.combinations(range(w), c)): hits.append(y + ' on some columns')
        if hits: print(s, x, hits[:3])
