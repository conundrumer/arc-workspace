"""Counts of the shadow tables over a folder of port_shadow.py files, as they exist.

  port_report.py ROWS_DIR
"""
import collections, glob, json, math, statistics as st, sys
J = [json.load(open(f)) for f in sorted(glob.glob(sys.argv[1] + '/*.json'))]
print('forms', len(J), 'tasks', len({r['task'] for r in J}), 'match', sum(bool(r.get('match')) for r in J), 'errors', sum(1 for r in J if any(k.startswith('error') for k in r)))
G = collections.Counter((g['place'], g['state']) for r in J for g in r['gold'])
print('gold prefixes', sorted(G.items()))
print('gold forms with an empty prefix', sum(any(g['state'] == 'empty' for g in r['gold']) for r in J))
for g in (g for r in J for g in r['gold'] if g['state'] == 'empty'):
    print('  gold empty', g)
for m in ('sampling', 'search'):
    C = collections.Counter()
    for r in J:
        C.update(r['counts'].get(m, {}))
    print('==', m)
    print({k: v for k, v in sorted(C.items()) if k.startswith('state ')})
    for k, v in C.most_common():
        if k.startswith('why '):
            print(' ', v, k[4:])
    for pl in ('key', 'port'):
        print(pl, 'repeat at first by atom', [(k, C[f'repeat {pl} {k}'], C[f'alive {pl} {k}']) for k in range(1, 7)])
        print(pl, 'empty at first by atom', [(k, C[f'empty {pl} {k}'], C[f'alive {pl} {k}']) for k in range(1, 7)])
    print('nonempty', C['nonempty'], 'equal', C['equal'], 'rate', round(C['equal'] / max(C['nonempty'], 1), 3))
    if m == 'sampling':
        sh = [(r['counts'].get(m, {}).get('clean clauses', 0), r['counts'].get(m, {}).get('clauses', 0)) for r in J]
        print('clean with repeats too', C['clean clauses, repeats too'], 'bits', round(-math.log2(max(C['clean clauses, repeats too'], 1) / max(C['clauses'], 1)), 2))
        print('clauses', C['clauses'], 'clean', C['clean clauses'], 'pooled bits', round(-math.log2(max(C['clean clauses'], 1) / max(C['clauses'], 1)), 2))
        b = [-math.log2(c / n) for c, n in sh if n and c]
        print('per form: forms', len(b), 'median bits', round(st.median(b), 2) if b else None, 'mean', round(st.mean(b), 2) if b else None, 'max', round(max(b), 2) if b else None, 'none clean', sum(1 for c, n in sh if n and not c))
    else:
        d = [r['counts'].get(m, {}) for r in J]
        e = [(x.get('equal', 0), x.get('nonempty', 0)) for x in d if x.get('nonempty')]
        print('per form equal rate median', round(st.median(a / b for a, b in e), 3) if e else None)
T = collections.Counter()
for r in J:
    for k, v in r['counts'].get('sampling', {}).items():
        if k.startswith('state '):
            T[k.split(' ', 3)[3]] += v
print('sampled paths by state', dict(T), 'total', sum(T.values()))
print('shadow cpu', round(sum(r['shadow_cpu'] for r in J)), 'tables', sum(r['shadow_n'] for r in J), 'ms each', round(1000 * sum(r['shadow_cpu'] for r in J) / max(sum(r['shadow_n'] for r in J), 1), 1))
