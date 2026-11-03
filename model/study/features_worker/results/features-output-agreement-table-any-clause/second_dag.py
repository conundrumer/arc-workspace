"""On one task: the main DAG's tables on the real task against a second DAG of DET and instance forms over ex_output. Prints, for each main table, the second-DAG tables equal to it on every train example, on some of their columns, Ident columns aside."""
import itertools, json, os, re, sys
f = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agree_tables.py'); __file__ = f; T = sys.argv[1]; second = open(sys.argv[2]).read(); sys.argv = [f, 'x']
s = open(f).read().split("if sys.argv[1] == 'one'")[0]
s = s.replace('tuple(sorted(map(repr, row)))', 'tuple(map(repr, row))').replace("'id' if ty == 'Ident' else", "'id' if ty == 'Ident' else ('E', int(cells[p])) if ty == 'Example' else").replace('kind[i] not in (1, 2)', 'kind[i] not in (0, 1, 2)').replace('all_cases=False)', 'all_cases=False, table_work_cap=1 << 36)')
exec(s)
d = f'{W}/{T}'; p = open(f'{d}/prog/{T}.arclog').read(); j = p.rindex('(OUT')
heads = {t['table'].split('.')[0] for t in json.load(open(f'{W}/{T}.one.json'))['tables'] if t['side'] == 'node'}
i = re.search(r'\((RULE|INIT|DET) &f\d+', p).start()
fs = {}
for a, b in forms(p[i:j], '(RULE ') + forms(p[i:j], '(INIT ') + forms(p[i:j], '(DET '):
    c = p[i:j][a:b]; fs.setdefault(c.split()[1], c)
keep = set(); todo = list(heads)
while todo:
    h = todo.pop()
    if h in keep or h not in fs: continue
    keep.add(h); todo += re.findall(r'&f\d+', fs[h])
main = '\n'.join(c for h, c in sorted(fs.items(), key=lambda x: int(x[0][2:])) if h in keep)
open(f'{d}/second/{T}.arclog', 'w').write(p[:i] + main + '\n\n' + second + '\n\n' + p[j:])
tb, amb = tables(f'{d}/second', f'{d}/real', T); n = len(json.load(open(f'{ROOT}/data/tasks/{T}.json'))['train'])
tb_names = {}
want = [t for t in json.load(open(f'{W}/{T}.one.json'))['tables']]
back = {}
for y, v in tb.items():
    if not y.startswith(('&b_', '&g_')) or y in amb: continue
    rs = [r for k, x in v.items() for r in x]
    if not rs: continue
    e = next((i for i, c in enumerate(rs[0]) if c.startswith("('E'")), None)
    if e is None: print('no example column', y); continue
    by = {i: set() for i in range(n)}
    for r in rs:
        i = eval(r[e])[1]
        if i < n: by[i].add(r[:e] + r[e + 1:])
    back[y] = by
print('second-DAG tables with rows', len(back), 'ambiguous', sorted(x for x in amb if x.startswith('&b_')))
for t in want:
    x = t['table']
    if x not in tb: print(t['side'], x, 'missing'); continue
    a = [{tuple(c for c in r if c != "'id'") for r in tb[x].get((1, e), ())} for e in range(n)]
    w = len(next(r for rs in a for r in rs)); hits = []
    for y, b in back.items():
        c = len(next(r for rs in b.values() for r in rs))
        if c < w: continue
        vals = [{r[k] for e in range(n) for r in b[e]} for k in range(c)]; need = [{r[k] for e in range(n) for r in a[e]} for k in range(w)]
        opts = [[k for k in range(c) if vals[k] == need[q]] for q in range(w)]
        for m in itertools.product(*opts):
            if len(set(m)) == w and all({tuple(r[k] for k in m) for r in b[e]} == a[e] for e in range(n)): hits.append(y + ('' if c == w else ' (some columns)')); break
    part = ''
    if not hits:
        names = tb_names.get(x, [str(q) for q in range(w)]); found = None
        for k in range(w - 1, 0, -1):
            for sub in itertools.combinations(range(w), k):
                pa = [{tuple(r[q] for q in sub) for r in a[e]} for e in range(n)]
                for y, b in back.items():
                    c = len(next(r for rs in b.values() for r in rs))
                    if c < k: continue
                    vals = [{r[q] for e in range(n) for r in b[e]} for q in range(c)]; need = [{r[q] for rs in pa for r in rs} for q in range(k)]
                    opts = [[q for q in range(c) if vals[q] == need[i]] for i in range(k)]
                    for m in itertools.product(*opts):
                        if len(set(m)) == k and all({tuple(r[q] for q in m) for r in b[e]} == pa[e] for e in range(n)): found = (sub, y); break
                    if found: break
                if found: break
            if found: break
        part = f' columns {[names[q] for q in found[0]]} of {names} by {found[1]}' if found else ''
    print(t['side'], x, hits if hits else 'NOT MET' + part)
if os.environ.get('DBG'):
    for y in ('&b_ray', '&b_past', '&b_free', '&b_free_end', '&b_stop', '&rays_full.ray', '&rays.ray'):
        v = tb.get(y, {}); print(y, {k: len(x) for k, x in v.items()}, y in amb)
    print(sorted(next(iter(tb['&rays_full.ray'].values())))[:2]); print(sorted(next(iter(tb['&b_ray'].values()), []))[:2] if '&b_ray' in tb else '')
if os.environ.get('OCC'):
    print(sorted(tb['&occ.occurrence'][(1, 0)])); print(sorted(r for r in tb['&b_occ'].get((0, 0), []) if "('E', 0)" in r))
if os.environ.get('NEAR'):
    # for each main table, the second-DAG table and column map with the greatest Jaccard of rows, summed over the train examples
    out = open(f'{W}/{T}.near.jsonl', 'w')
    for t in want:
        x = t['table']
        if x not in tb: continue
        a = [{tuple(c for c in r if c != "'id'") for r in tb[x].get((1, e), ())} for e in range(n)]
        w = len(next(r for rs in a for r in rs)); need = [{r[q] for rs in a for r in rs} for q in range(w)]; best = (0, 0, 0, None)
        na = sum(map(len, a))
        for y, b in back.items():
            c = len(next(r for rs in b.values() for r in rs))
            if c < w: continue
            vals = [{r[q] for e in range(n) for r in b[e]} for q in range(c)]
            opts = [[q for q in range(c) if len(vals[q] & need[i]) * 2 >= len(need[i])] for i in range(w)]
            for m in itertools.islice(itertools.product(*opts), 3000):
                if len(set(m)) < w: continue
                pb = [{tuple(r[k] for k in m) for r in b[e]} for e in range(n)]
                both = sum(len(a[e] & pb[e]) for e in range(n)); un = na + sum(map(len, pb)) - both
                if both / un > best[0]: best = (both / un, both / na, both / max(sum(map(len, pb)), 1), y)
        out.write(json.dumps({'table': x, 'side': t['side'], 'rows': na, 'jaccard': round(best[0], 3), 'recall': round(best[1], 3), 'precision': round(best[2], 3), 'by': best[3]}) + '\n'); out.flush()
if os.environ.get('RESTATE'):
    # a table restates the input where two of its columns, a cell and a color, hold only input rows and at least half of them on every train example
    grids = [p['input'] for p in json.load(open(f'{ROOT}/data/tasks/{T}.json'))['train']]
    inp = [{(repr((r, len(g) - 1 - r, c, len(g[0]) - 1 - c)), repr(v)) for r, row in enumerate(g) for c, v in enumerate(row)} for g in grids]
    flags = {}
    for t in want:
        x = t['table']
        if x not in tb: continue
        a = [{tuple(c for c in r if c != "'id'") for r in tb[x].get((1, e), ())} for e in range(n)]
        w = len(next(r for rs in a for r in rs)); flags[x] = False
        for i, j in itertools.permutations(range(w), 2):
            pr = [{(r[i], r[j]) for r in a[e]} for e in range(n)]
            if all(pr[e] <= inp[e] and len(pr[e]) * 2 >= len(inp[e]) for e in range(n)): flags[x] = True; break
    json.dump(flags, open(f'{W}/{T}.restate.json', 'w'))
