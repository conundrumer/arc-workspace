"""RETIRED for graph files written after the graph dropped its bits: this script reads `minimax_path` and `bits` of graph-tasks-SET.jsonl / graph-prods-SET.jsonl, which gold_union_graph.py no longer writes. It runs only on graph files of earlier rounds. The minimax path of each task of one set against the search jobs that reached its tables. Writes minimax-reach-SET.json in work/lm/data-study/gold/gold-union and prints one line per task.

  .venv/bin/python gold_union_minimax_reach.py SET [JOB_PREFIX]

- The minimax path is `minimax_path` of graph-tasks-SET.jsonl, by its `idents`; its productions come from graph-prods-SET.jsonl.
- A job is a line of search-worker's reach-SET.jsonl whose `job` starts with JOB_PREFIX (all jobs where it is left out), at 600 s. Its reached tables are named as in gold_union_reach.py, through outmap-SET.jsonl and the graph tables' `members`.
- A production on the path is done when each of its heads is reached, or read past by a reached table. Per job: done, left, and left over CUT bits (12.6, one job's reach).
"""
import json, ast, collections, statistics, sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..'))  # model/study
import study_zst as Z  # the union files are zstd streams or plain files, whichever is on disk
W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
U = W + 'gold/gold-union/'
RUNS = W + 'sampler/search-worker/runs/search-union-reach-ramp22-heldout37/'
SET, JOBS = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ''
CUT = 12.6
names = {}
for r in map(json.loads, open(RUNS + 'outmap-%s.jsonl' % SET)):
    names[r['task'], r['table']] = str(r['key']) if not r['component'] else '%d.%s' % (r['key'], r['name']) if r['name'] else None
member_of = collections.defaultdict(dict)
for r in map(json.loads, Z.open_text(U + 'graph-tables-%s.jsonl' % SET)):
    for m in r['members']:
        member_of[r['task']][m] = r['table']
prods = {(p['task'], p['ident']): p for p in map(json.loads, Z.open_text(U + 'graph-prods-%s.jsonl' % SET))}
reads = collections.defaultdict(lambda: collections.defaultdict(set))
for p in prods.values():
    for h in p['heads']:
        reads[p['task']][h] |= set(p['reads'])
tasks = {json.loads(l)['task']: json.loads(l) for l in Z.open_text(U + 'graph-tasks-%s.jsonl' % SET)}
jobs = collections.defaultdict(list)
for r in map(json.loads, open(RUNS + 'reach-%s.jsonl' % SET)):
    if not str(r['job']).startswith(JOBS):
        continue
    at = ast.literal_eval(r['at']) if isinstance(r['at'], str) else r['at']
    t = r['task']
    got = {member_of[t].get(names.get((t, x))) for x in at.get('600', [])} - {None}
    past, todo = set(), [y for x in got for y in reads[t][x]]
    while todo:
        y = todo.pop()
        if y not in past:
            past.add(y); todo.extend(reads[t][y])
    jobs[t].append((r['job'], got | past))
print('task prods height >12.6 >16 | per round-1 job at 600 s: productions with every head reached or read past; left; left over 12.6')
out = {}
for t, k in sorted(tasks.items()):
    m = k.get('minimax_path') or {}
    ps = [prods[t, i] for i in m.get('idents', [])]
    if not ps:
        print(t, 'no minimax path'); continue
    b = [p['bits'] or 0 for p in ps]
    rows = []
    for job, free in jobs[t]:
        done = [p for p in ps if set(p['heads']) <= free]
        left = [p for p in ps if not set(p['heads']) <= free]
        rows.append((job, len(done), len(left), sum((p['bits'] or 0) > CUT for p in left)))
    best = min(rows, key=lambda x: (x[3], x[2])) if rows else None
    out[t] = dict(productions=len(ps), height=m.get('height'), over_12_6=sum(x > CUT for x in b), over_16=sum(x > 16 for x in b), jobs=rows)
    print(t, len(ps), m.get('height'), out[t]['over_12_6'], out[t]['over_16'], '| jobs', len(rows), 'best', best, 'median left over 12.6', statistics.median([x[3] for x in rows]) if rows else None)
ok = [t for t, v in out.items() if v['jobs'] and min(x[3] for x in v['jobs']) <= 3]
print('%s: %d of %d tasks leave at most 3 productions over %s bits after the better job' % (SET, len(ok), len(tasks), CUT))
json.dump(out, open(U + 'minimax-reach-%s.json' % SET, 'w'))
