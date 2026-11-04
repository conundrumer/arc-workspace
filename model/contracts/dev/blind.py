"""Dev labeling layer: the row changes that no feature shows, for one task.

    CONTRACTS_OUT=<out dir> python3 blind.py TASK [N [TABLE ...]]

Counts, per table, the variants whose rows of the table change while every feature of the table keeps its value at the variant's source
example. For the N tables with the most such variants (or for the TABLEs given), reruns the engine on two of them and prints the rows that the variant removes and adds.
"""
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / 'features'))
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import proposers as PR  # noqa: E402
import query as Q  # noqa: E402
import tablecache as C  # noqa: E402
from growth import parsed  # noqa: E402

OUTDIR = Path(os.environ.get('CONTRACTS_OUT', HERE / 'out'))


def rows_at(tab, ex):
    return tab['rows'].get(ex, tab['rows'].get('task')) or []


def main(task, n_show=4, only=()):
    lines = parsed(OUTDIR / (task + '.variants.jsonl'))
    base = next(l for l in lines if l['kind'] == 'base')
    V = [l for l in lines if l['kind'] != 'base' and 'features' in l and 'digests' in l]
    exs = base['examples']
    blind = defaultdict(list)
    for v in V:
        d0 = base['digests'].get(v['source'], {})
        for t, dg in v['digests'].items():
            if t in d0 and dg != d0[t]:
                keys = [k for k in exs[v['source']] if k.split('|')[0] == t]
                if all(v['features'].get(k, 'MISSING') == exs[v['source']][k] for k in keys):
                    blind[t].append(v)
    print('%s: %d variants' % (task, len(V)))
    for t, vs in sorted(blind.items(), key=lambda x: -len(x[1])):
        print('  %-30s %5d blind, kinds %s' % (t, len(vs), dict(Counter(v['kind'] for v in vs))))
    s = E.Solver(task)
    bj = json.load(open(E.ROOT / 'data/tasks' / (task + '.json')))
    T0 = s.tables(bj)
    qf = Q.query_features(s.text)
    pins = {rel: rows for rel, rows in s.stored.items() if rel in E.proposer_relations(qf)}
    proposer_of = {n: q.get('proposer') for n, q in qf.items()}
    for t, vs in [(t, blind[t]) for t in only if t in blind] or sorted(blind.items(), key=lambda x: -len(x[1]))[:n_show]:
        print('\n== %s, columns %s' % (t, T0[t]['columns']))
        for v in vs[:2]:
            tj, ex = C.task_with(bj, v)
            T = s.tables(tj, pin=pins, no_assignment=lambda p: PR.missing(p, proposer_of, tj))
            a = {json.dumps(r) for r in rows_at(T0[t], v['source'])}
            b = {json.dumps(r) for r in rows_at(T[t], ex)}
            print('  %s (%s, ops %s): %d rows -> %d rows' % (v['id'], v['kind'], v.get('ops', '')[:6], len(a), len(b)))
            print('    removed:', sorted(a - b)[:6])
            print('    added:  ', sorted(b - a)[:6])


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 4, sys.argv[3:])
