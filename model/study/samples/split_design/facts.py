"""One row per task of data/tasks: source, grid facts, union graph structure, cases, held-list membership. Writes facts.jsonl here.

Grid facts follow gold_task_facts.py: cells are height times width; input_cells_median is over train inputs and test inputs;
output_cells_median and output_size_equals_input are over train pairs. No test output is read.
Graph fields read: graph-tasks-SET.jsonl task, tables, productions, goals, goal_depth, goal_depth_cases;
graph-prods-SET.jsonl task, ident, heads, reads. case-counts.jsonl task, cases (already net of excluded cases: gold_case_counts.py lines 71 and 78), distinct_programs.
No bits, cost_* or path field is read.
"""
import glob, json, os, resource, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = '/Users/davidlu/code/arc-workspace/'
sys.path.append(R + 'model/study')
import study_zst as Z  # the graph files are zstd streams or plain files, whichever is on disk
U = R + 'work/lm/data-study/gold/gold-union/'
H = R + 'work/lm/data-study/sampler/sampler-worker/held/'
LIMIT = 3 * 1024 ** 3


def mem_check():
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > LIMIT:  # bytes on darwin
        print('past 3 GiB', file=sys.stderr)
        sys.exit(75)


def cells(g):
    return len(g) * len(g[0]) if g and g[0] else 0


def fewest(goals, prods):
    """Upper bound on the fewest productions of a hyperpath that makes the goal: per table, the least production set by set union, to a fixed point."""
    best = {}
    for _ in range(100):
        changed = False
        for pid, p in prods.items():
            if any(r not in best for r in p['reads']):
                continue
            s = {pid}
            for r in p['reads']:
                s |= best[r]
            for h in p['heads']:
                if h not in best or len(s) < len(best[h]):
                    best[h] = frozenset(s)
                    changed = True
        if not changed:
            break
    got = []
    for o in goals:
        if all(g in best for g in o):
            s = set()
            for g in o:
                s |= best[g]
            got.append(len(s))
    return min(got) if got else None


def main():
    held = {name: set(open(H + f).read().split()) for name, f in (('r22', 'ramp-fold.txt'), ('h37', 'tasks.txt'), ('h99', 'leave_out.txt'))}
    graph = {}
    for s in ('training', 'ramp', '37'):
        for l in Z.open_text(U + 'graph-tasks-%s.jsonl' % s):
            r = json.loads(l)
            if 'error' in r:
                graph[r['task']] = dict(gset=s, g_error=r['error'].split(':')[0])
                continue
            graph[r['task']] = dict(gset=s, g_tables=r['tables'], g_productions=r['productions'], g_goal_options=len(r['goals']),
                                    goal_depth=r['goal_depth'], goal_depth_cases=r['goal_depth_cases'], goals=r['goals'])
        prods = {}
        for l in Z.open_text(U + 'graph-prods-%s.jsonl' % s):
            r = json.loads(l)
            prods.setdefault(r['task'], {})[r['ident']] = dict(heads=r['heads'], reads=r['reads'])
            mem_check()
        for t, ps in prods.items():
            if t in graph and graph[t]['gset'] == s and 'goals' in graph[t]:
                graph[t]['fewest_productions'] = fewest(graph[t]['goals'], ps)
    cc = {}
    for l in open(U + 'case-counts.jsonl'):
        r = json.loads(l)
        if r.get('cases') is not None:
            cc[r['task']] = dict(cases=int(r['cases']), distinct_programs=r.get('distinct_programs'))
    out = open(HERE + '/facts.jsonl', 'w')
    for p in sorted(glob.glob(R + 'data/tasks/*.json')):
        t = os.path.basename(p)[:-5]
        task = json.load(open(p))
        tr, te = task['train'], task['test']
        ins = [cells(x['input']) for x in tr] + [cells(x['input']) for x in te]
        outs = [cells(x['output']) for x in tr]
        same = all(len(x['input']) == len(x['output']) and len(x['input'][0]) == len(x['output'][0]) for x in tr)
        src = sorted('%s/%s' % (s['dataset'], s['split']) for s in task.get('source', []))
        row = dict(task=t, source=src, train_pairs=len(tr), test_cases=len(te), input_cells_median=statistics.median(ins),
                   output_cells_median=statistics.median(outs), output_size_equals_input=int(same),
                   **{k: (t in v) for k, v in held.items()})
        g = graph.get(t)
        if g:
            row.update({k: v for k, v in g.items() if k != 'goals'})
        if t in cc:
            row.update(cc[t])
        out.write(json.dumps(row) + '\n')
        mem_check()
    out.close()


main()
