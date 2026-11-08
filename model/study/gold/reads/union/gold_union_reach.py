"""RETIRED for graph files written after the graph dropped its bits: this script reads `bits`, `cost_known` and the cheapest hyperpath (and it imports `max_production` and `cheapest` from gold_union_graph.py, which has neither now) of graph-tasks-SET.jsonl / graph-prods-SET.jsonl, which gold_union_graph.py no longer writes. It runs only on graph files of earlier rounds. Reach of the union tables of one set by each search job, on the AND-OR graph of gold_union_graph.py. Writes reach-SET.jsonl in work/lm/data-study/gold/gold-union, one line per (task, job, seconds).

  <runtime python> gold_union_reach.py SET

- Reach: search-worker's reach-SET.jsonl (`at`: the tables a job reached by 60, 300 and 600 s), with its "key:output" tables named through outmap-SET.jsonl ("key" for a table that isn't INIT, "key.name" for an INIT output) and then by the graph table that has that name in its `members`. An INIT output that no case reads is not a union table, and it is counted in `unnamed`.
- Read past: a table is read past when a reached table reads it through any production, at any distance.
- Open: a table that is neither reached nor read past. `lowest_open` is the least depth of an open table, depth by productions.
- `per`: for each depth, the union tables, the reached, the read past (not reached), and the open.
- Remaining path: `remaining` is the cheapest hyperpath to the goal with each reached or read-past table made at no cost, on known bits: its bits, its count of productions (each one unreached), and the production on it with the most bits (`max_production`), with that production's bits and depth.
- Bits: `open_cost_known` and `open_cost_low` are the tree cost of the goal (the least over the goal options of graph-tasks-SET.jsonl of the sum over the option's tables) with each reached or read-past table's cost taken as 0, on known bits (a production without bits unusable) and on low bits (a production without bits at 0 bits).
"""
import ast, collections, json, os, sys
from gold_union_graph import cheapest, max_production
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..'))  # model/study
import study_zst as Z  # the union files are zstd streams or plain files, whichever is on disk

D = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
OUT = D + 'gold/gold-union/'
RUNS = D + 'sampler/search-worker/runs/search-union-reach-ramp22-heldout37/'
INF = float('inf')


def lit(v):
    return ast.literal_eval(v) if isinstance(v, str) else v


def main():
    s = sys.argv[1]
    names = {}
    for r in map(json.loads, open(RUNS + 'outmap-%s.jsonl' % s)):
        names[r['task'], r['table']] = str(r['key']) if not r['component'] else '%d.%s' % (r['key'], r['name']) if r['name'] else None
    tables, member_of = collections.defaultdict(dict), collections.defaultdict(dict)
    for r in map(json.loads, Z.open_text(OUT + 'graph-tables-%s.jsonl' % s)):
        tables[r['task']][r['table']] = r
        for m in r['members']:
            member_of[r['task']][m] = r['table']
    goals = {r['task']: r.get('goals', []) for r in map(json.loads, Z.open_text(OUT + 'graph-tasks-%s.jsonl' % s))}
    prods, byid, made = collections.defaultdict(list), collections.defaultdict(dict), collections.defaultdict(lambda: collections.defaultdict(list))
    for r in map(json.loads, Z.open_text(OUT + 'graph-prods-%s.jsonl' % s)):
        prods[r['task']].append(r)
        byid[r['task']][r['ident']] = r
        for h in r['heads']:
            made[r['task']][h].append(r['ident'])
    for t in tables:
        for k in tables[t]:
            made[t].setdefault(k, [])
    n = 0
    with open(OUT + 'reach-%s.jsonl' % s, 'w') as out:
        for r in map(json.loads, open(RUNS + 'reach-%s.jsonl' % s)):
            t = r['task']
            ts, ps = tables[t], prods[t]
            reads = collections.defaultdict(set)
            for p in ps:
                for h in p['heads']:
                    reads[h] |= set(p['reads'])
            for sec, got in lit(r['at']).items():
                mapped = [member_of[t].get(names.get((t, x))) for x in got]
                reached = {x for x in mapped if x in ts}
                past, todo = set(), [y for x in reached for y in reads[x]]
                while todo:
                    y = todo.pop()
                    if y not in past:
                        past.add(y)
                        todo.extend(reads[y])
                past -= reached
                per = {}
                for name, x in ts.items():
                    d = per.setdefault(str(min(x['depth'], 7)), dict(tables=0, reached=0, read_past=0, open=0))
                    d['tables'] += 1
                    d['reached' if name in reached else 'read_past' if name in past else 'open'] += 1
                opened = [x['depth'] for name, x in ts.items() if name not in reached and name not in past]
                free = reached | past
                cost = {}
                for kind in ('known', 'low'):
                    v = {k: 0.0 if k in free else INF for k in ts}
                    while True:
                        new = dict(v)
                        for p in ps:
                            c = p['bits'] if p['bits'] is not None else (INF if kind == 'known' else 0.0)
                            c += sum(v.get(x, INF) for x in p['reads'])
                            for h in p['heads']:
                                if h not in free and c < new[h]:
                                    new[h] = c
                        if new == v:
                            break
                        v = new
                    c = min((sum(v[g] for g in o) for o in goals[t]), default=INF)
                    cost[kind] = None if c == INF else round(c, 2)
                left = cheapest(goals[t], made[t], byid[t], lambda p: p['bits'] if p['bits'] is not None else INF, frozenset(free)) if goals[t] else None
                rest = dict(bits=round(left[0], 2), productions=len(left[1]), max_production=max_production(left[1], byid[t])) if left else None
                out.write(json.dumps(dict(task=t, set=s, job=r['job'], seconds=int(sec), soak_time=r.get('soak_time'), reached=len(reached), read_past=len(past), unnamed=sum(x is None for x in mapped),
                                          lowest_open=min(opened) if opened else None, per=per, open_cost_known=cost['known'], open_cost_low=cost['low'], remaining=rest)) + '\n')
                n += 1
    print(n, 'lines')


if __name__ == '__main__':
    main()
