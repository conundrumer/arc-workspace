"""Counts of what a set's union graph gives as supervised examples. Prints them and writes supervision-SET.json in work/lm/data-study/gold/gold-union.

  .venv/bin/python gold_union_supervision.py SET

- Productions: the lines of graph-prods-SET.jsonl, in all and per form kind.
- Patterns: distinct (kind, read kinds), where a read kind is the kind of a graph table the production reads (an INIT table with its component output, from its `members`). Base relations such as `input` are not graph tables, so they are not among the read kinds.
- OR tables: tables of graph-tables-SET.jsonl with more than one production, and the mean productions per table, in all and per depth.
- Cases per task: `cases` of case-counts.jsonl, for the set's tasks.
- Per task: the goal depth, from graph-tasks-SET.jsonl. A task whose goal depth is infinite (no goal option has all its tables made) is counted apart, and the task errors.
"""
import collections, json, statistics, sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..'))  # model/study
import study_zst as Z  # the union files are zstd streams or plain files, whichever is on disk
OUT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'


def dist(xs):
    xs = sorted(xs)
    if not xs:
        return {}
    q = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]
    return dict(n=len(xs), min=xs[0], p25=q(.25), median=q(.5), p75=q(.75), p90=q(.9), max=xs[-1], mean=round(statistics.mean(xs), 2))


def main():
    s = sys.argv[1]
    tables = {(t['task'], t['table']): t for t in map(json.loads, Z.open_text(OUT + 'graph-tables-%s.jsonl' % s))}
    prods = [json.loads(l) for l in Z.open_text(OUT + 'graph-prods-%s.jsonl' % s)]
    tasks = [json.loads(l) for l in Z.open_text(OUT + 'graph-tasks-%s.jsonl' % s)]

    def read_kind(task, table):
        t = tables.get((task, table))
        if not t:
            return '?'
        if t['kind'] == 'INIT':
            return 'INIT:' + '/'.join(sorted({m.split('.', 1)[-1] for m in t['members']}))
        return t['kind']

    patterns = collections.Counter((p['kind'], tuple(sorted({read_kind(p['task'], r) for r in p['reads']}))) for p in prods)
    per_table = [t['productions'] for t in tables.values()]
    by_depth = collections.defaultdict(list)
    for t in tables.values():
        by_depth[t['depth'] if isinstance(t['depth'], int) else None].append(t)
    ours = {t['task'] for t in tasks}
    cases = [c['cases'] for c in map(json.loads, open(OUT + 'case-counts.jsonl')) if c.get('task') in ours and 'cases' in c]
    out = dict(
        set=s, tasks=len(tasks), tables=len(tables), productions=len(prods),
        productions_per_kind=dict(collections.Counter(p['kind'] for p in prods).most_common()),
        patterns=len(patterns), patterns_top=[[k, list(r), n] for (k, r), n in patterns.most_common(20)],
        patterns_used_once=sum(n == 1 for n in patterns.values()),
        or_tables=sum(n > 1 for n in per_table), productions_per_table_mean=round(statistics.mean(per_table), 3),
        productions_per_table=dict(sorted(collections.Counter(per_table).items())),
        per_depth={str(d): dict(tables=len(ts), or_tables=sum(t['productions'] > 1 for t in ts), productions_per_table_mean=round(statistics.mean(t['productions'] for t in ts), 3))
                   for d, ts in sorted(by_depth.items(), key=lambda x: (x[0] is None, x[0] or 0))},
        cases_per_task=dist(cases),
        goal_depth=dist([t['goal_depth'] for t in tasks if t.get('goal_depth') is not None and t['goal_depth'] != float('inf')]),
        goal_depth_infinite=sum(t.get('goal_depth') == float('inf') for t in tasks),
        task_errors=dict(collections.Counter(t['error'].split(':')[0] for t in tasks if t.get('error'))))
    json.dump(out, open(OUT + 'supervision-%s.json' % s, 'w'), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != 'patterns_top'}, indent=1))
    for k, r, n in out['patterns_top']:
        print('  %5d  %s %s' % (n, k, ' '.join(r)))


if __name__ == '__main__':
    main()
