"""Where each union table of a dev161 run's jobs is lost, per arm and band.

    loss_split.py RUN_FOLDER ARM [OUT.jsonl]

A table is reached when a draw's tables name it (reach.py's naming, --by tables). An unreached table falls in the first of these that holds:
  blocked      every production of it reads a table that the job never reached
  no scope     some production's reads were all reached, but no draw of its kind had them all in its state
  written      a draw of the production's kind had all its reads in its state, and the query did not come
The output has one line per task with each table's class; the last lines print the totals by band.
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draw_file  # noqa: E402
import reach as R

run, arm = Path(sys.argv[1]), sys.argv[2]
out = open(sys.argv[3], 'w') if len(sys.argv) > 3 else None
U = R.DATA / 'gold/gold-union-exp46'
skip = {json.loads(l)['task'] for l in open(R.OUT_OF_SCOPE)}
tables = collections.defaultdict(dict)
for r in map(json.loads, open(U / 'graph-tables-dev.jsonl')):
    if r['table'].startswith('t') and r.get('kind') != 'DEMONSTRATED':
        tables[r['task']][r['table']] = r
prods = collections.defaultdict(lambda: collections.defaultdict(list))
for p in map(json.loads, open(U / 'graph-prods-dev.jsonl')):
    for h in p['heads']:
        prods[p['task']][h].append(p)
band = lambda d: '0' if d == 0 else '1' if d == 1 else '2-3' if d <= 3 else '4+'  # noqa: E731
tot = collections.Counter()
visits_total = collections.Counter()
for r in map(json.loads, open(run / 'results.jsonl')):
    if r['arm'] != arm or r['task'] in skip or r['task'] not in tables:
        continue
    task = r['task']
    w = run / 'jobs' / r['job']
    outputs, entries, draws = [], [], []
    for d in draw_file.draws(w):
        if 'steps' not in d:
            continue
        q = d['steps'][-1]['query_hash']
        draws.append((d['kind'], q, d['steps'][-1]['state'], d.get('result')))
        for o in d.get('tables') or ():
            outputs.append((q, o['name']))
            for row in o['at']:
                entries.append((q, o['name'], list(zip(o['dets'], row[:-1])), row[-1]))
    names = R.graph_names(outputs, entries)
    of_query = collections.defaultdict(set)
    for (q, _), g in names.items():
        of_query[q].add(g)
    reached = set(names.values())
    # the draws that had each set of tables in their state, per kind
    by_kind = collections.defaultdict(list)
    for kind, q, state, _ in draws:
        got = set()
        for s in state:
            got |= of_query.get(s, set())
        by_kind[kind].append(got)
    rec = {'task': task, 'draws': len(draws), 'classes': {}}
    for t, row in tables[task].items():
        b = band(row['depth'])
        tot[b, 'tables'] += 1
        if t in reached:
            tot[b, 'reached'] += 1
            rec['classes'][t] = 'reached'
            continue
        cls, tries = 'blocked', 0
        for p in prods[task].get(t, ()):
            need = set(p['reads'])
            if not need <= reached:
                continue
            if cls == 'blocked':
                cls = 'no scope'
            n = sum(need <= got for got in by_kind.get(p['kind'], ()))
            if n:
                cls = 'written'
                tries = max(tries, n)
        tot[b, cls] += 1
        if cls == 'written':
            tot[b, 'tries'] += tries
        rec['classes'][t] = [cls, tries]
    if out:
        out.write(json.dumps(rec) + '\n')
        out.flush()
for b in ('0', '1', '2-3', '4+'):
    n = tot[b, 'written']
    print('depth %-4s tables %5d  reached %4d  written-lost %5d (mean draws with its reads in state %.1f)  no-scope %5d  blocked %5d' % (
        b, tot[b, 'tables'], tot[b, 'reached'], n, tot[b, 'tries'] / max(n, 1), tot[b, 'no scope'], tot[b, 'blocked']))
