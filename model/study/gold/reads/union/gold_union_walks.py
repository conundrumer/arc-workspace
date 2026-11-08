"""The enabled queries of the states of state sequences over a set's union graph, over the task's goal. Prints the counts and writes walks-SET.json in GOLD_UNION_DIR (default work/lm/data-study/gold/gold-union).

  .venv/bin/python gold_union_walks.py SET [SET ...]

- A state sequence starts at the empty state, a set of built graph tables. At each step it records the state and its enabled queries (each table the query uses is built, and some head is not), then adds the heads of one enabled query, chosen at random by the sequence's seed. It stops when every table of some goal option is built, or when nothing is enabled. Base tables aren't graph tables, so a query that uses none is enabled in the empty state.
- State sequence type: `union` picks among all enabled queries. 8 state sequences a task, seeds 0 to 7. A task is taken when its graph-tasks-SET.jsonl line has goals and no `error`.
- The frontier depth of a step is the least depth among its enabled queries (graph-prods-SET.jsonl).
- A state is the set of queries the state sequence has added (their Python identities in graph-prods-SET.jsonl), closed under use; two states with equal tables but different queries are different states. The built tables are a measurement of the state.
- A state sequence adds only a query that computes a table not yet built. A query not in the state whose heads are all built is not a step; per state, `redundant_forms` counts the applicable queries of that kind, as a measurement.
- For union state sequences, per distinct state (task, set of queries), counted at its first step, and again summed over every step (`over_steps`, where `distinct_states` is the step count): applicable queries (every table a query uses is built), the distinct tables they compute, enabled queries, and the distinct unbuilt tables they compute. The distinct states go to walk-states-SET.jsonl (task, forms, queries, built, depth, redundant_forms; `forms` holds the Python identities of the state's queries and `queries` their QueryHashes, or the Python identity where the row store lacks it), and walks-SET.json gives `distinct_table_sets`, the count of distinct (task, built set) pairs.
- Each union state sequence goes to walk-seqs-SET.jsonl: task, seed, reached_goal, and `states`, the line numbers (from 0) of its states in walk-states-SET.jsonl, in step order.
- Some output field names keep older terms: `*_forms` fields count queries, and `walks` in walks-SET.json counts state sequences.
- WALK_KINDS (default `union`) picks the state sequence types; `union` is the only one.
"""
import collections, json, os, random, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..'))  # model/study
import study_zst as Z  # the graph files are zstd streams or plain files, whichever is on disk

OUT = os.environ.get('GOLD_UNION_DIR', '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union') + '/'  # GOLD_UNION_DIR: the folder of the inputs and outputs
PER_TASK = 8
KINDS = os.environ.get('WALK_KINDS', 'union').split()


def quart(xs):
    xs = sorted(xs)
    if not xs:
        return {}
    q = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]
    return dict(n=len(xs), p25=q(.25), median=q(.5), p75=q(.75), p90=q(.9), max=xs[-1], mean=round(sum(xs) / len(xs), 2))


def state_sequence(queries, goals, seed):
    """(steps, reached): each step is (built tables, queries added so far, enabled queries)."""
    rng = random.Random(seed)
    built, added, steps = set(), set(), []
    while not any(set(g) <= built for g in goals):
        enabled = [p for p in queries if set(p['reads']) <= built and not set(p['heads']) <= built]
        if not enabled:
            return steps, False
        steps.append((frozenset(built), frozenset(added), enabled))
        pick = rng.choice(enabled)
        built |= set(pick['heads'])
        added.add(pick['ident'])
    return steps, True


def main():
    for s in sys.argv[1:]:
        queries, query_of = collections.defaultdict(list), {}
        for p in map(json.loads, Z.open_text(OUT + 'graph-prods-%s.jsonl' % s)):
            queries[p['task']].append(p)
            query_of[p['task'], p['ident']] = p.get('query')
        out, states, steps_of, seqs, tables_seen = {}, {}, collections.defaultdict(list), [], set()
        for kind in KINDS:
            rows, reached, count = [], 0, 0
            for t in map(json.loads, Z.open_text(OUT + 'graph-tasks-%s.jsonl' % s)):
                if not t.get('goals') or t.get('error'):
                    continue
                for seed in range(PER_TASK):
                    steps, ok = state_sequence(queries[t['task']], t['goals'], seed)
                    count += 1
                    reached += ok
                    if kind == 'union':
                        seqs.append((t['task'], seed, ok, [(t['task'], added) for _, added, _ in steps]))
                    for state, added, e in steps:
                        if kind == 'union':
                            key = (t['task'], added)
                            tables_seen.add((t['task'], state))
                            if key not in states:
                                applicable = [p for p in queries[t['task']] if set(p['reads']) <= state]
                                redundant = sum(p['ident'] not in added and set(p['heads']) <= state for p in applicable)
                                states[key] = dict(built=state, redundant_forms=redundant, depth=min((p['depth'] for p in e if p['depth'] is not None), default=None),
                                                   applicable_forms=len(applicable), applicable_tables=len({h for p in applicable for h in p['heads']}),
                                                   enabled_forms=len(e), enabled_tables=len({h for p in e for h in p['heads'] if h not in state}))
                            step_depth = min((p['depth'] for p in e if p['depth'] is not None), default=None)
                            steps_of[step_depth].append(states[key])
                        rows.append(dict(task=t['task'], enabled=len(e), frontier=min(p['depth'] for p in e if p['depth'] is not None) if any(p['depth'] is not None for p in e) else None))
            per = collections.defaultdict(list)
            for r in rows:
                per[r['frontier']].append(r)
            summary = lambda rs: dict(steps=len(rs), **{k: quart([r.get(k, 0) for r in rs]) for k in ('enabled',)})
            out[kind] = dict(walks=count, reached_goal=reached, all=summary(rows),
                             per_frontier_depth={str(d): summary(rs) for d, rs in sorted(per.items(), key=lambda x: (x[0] is None, x[0] or 0))})
            print(s, kind, 'walks', count, 'reached', reached, json.dumps(out[kind]['all']))
        if states:
            by = collections.defaultdict(list)
            for v in states.values():
                by[v['depth']].append(v)
            cols = ('applicable_forms', 'applicable_tables', 'enabled_forms', 'enabled_tables', 'redundant_forms')
            dist = lambda vs: dict(distinct_states=len(vs), **{c: sum(v[c] for v in vs) for c in cols})  # noqa: E731
            out['union']['distinct'] = dict(all=dist(list(states.values())), per_frontier_depth={str(d): dist(vs) for d, vs in sorted(by.items(), key=lambda x: (x[0] is None, x[0] or 0))})
            out['union']['over_steps'] = dict(all=dist([v for vs in steps_of.values() for v in vs]), per_frontier_depth={str(d): dist(vs) for d, vs in sorted(steps_of.items(), key=lambda x: (x[0] is None, x[0] or 0))})
            out['union']['distinct_table_sets'] = len(tables_seen)
            print(s, 'distinct states', json.dumps(out['union']['distinct']['all']), 'distinct table sets', len(tables_seen))
            print(s, 'over steps', json.dumps(out['union']['over_steps']['all']))
            line = {}
            with Z.open_part(OUT + 'walk-states-%s.jsonl' % s) as f:
                for i, ((task, added), v) in enumerate(states.items()):
                    line[task, added] = i
                    f.write(json.dumps(dict(task=task, forms=sorted(added), queries=sorted(query_of[task, i] for i in added), built=sorted(v['built']), depth=v['depth'], redundant_forms=v['redundant_forms'])) + '\n')
            with Z.open_part(OUT + 'walk-seqs-%s.jsonl' % s) as f:
                for task, seed, ok, keys in seqs:
                    f.write(json.dumps(dict(task=task, seed=seed, reached_goal=bool(ok), states=[line[k] for k in keys])) + '\n')
            for name in ('walk-states-%s.jsonl' % s, 'walk-seqs-%s.jsonl' % s):  # a reader never sees a part-written file, nor states without their sequences
                Z.commit(OUT + name)
        json.dump(out, open(OUT + 'walks-%s.json.part' % s, 'w'), indent=1)
        os.replace(OUT + 'walks-%s.json.part' % s, OUT + 'walks-%s.json' % s)


if __name__ == '__main__':
    main()
