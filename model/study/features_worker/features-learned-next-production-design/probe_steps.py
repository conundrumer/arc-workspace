"""Counts of steps and positives per step on the union AND-OR graph of a set, by random walks over gold's productions.

  python3 probe_steps.py SET WALKS OUT.json

A state is a set of built graph tables. A production is enabled at a state when each table it reads is built and some head of it is not.
A walk starts at the empty set, takes an enabled production at random (uniform), adds its heads, and stops when a goal option's tables are
all built, or when nothing is enabled. Per step it counts the enabled productions (the positives of that step).
The path walk does the same, but takes only productions of the task's least-bits path, so it counts the positives at states of that path.
Files stream line by line; the ramp and the 37 graph files are under 1 MB.
"""
import collections, json, random, statistics, sys

G = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'


def dist(xs):
    xs = sorted(xs)
    if not xs:
        return {}
    q = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]
    return dict(n=len(xs), min=xs[0], p25=q(.25), median=q(.5), p75=q(.75), p90=q(.9), max=xs[-1], mean=round(statistics.mean(xs), 2), sum=sum(xs))


def walk(prods, goals, rng, allowed=None):
    built, steps = set(), []
    while True:
        if any(set(g) <= built for g in goals):
            return steps, True, len(built)
        en = [i for i, p in enumerate(prods) if set(p['reads']) <= built and not set(p['heads']) <= built]
        if not en:
            return steps, False, len(built)
        pick_from = [i for i in en if allowed is None or prods[i]['ident'] in allowed]
        if not pick_from:
            return steps, False, len(built)
        steps.append(dict(enabled=len(en), on_path=len(pick_from) if allowed is not None else None))
        built |= set(prods[rng.choice(pick_from)]['heads'])


def main():
    s, K, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    prods = collections.defaultdict(list)
    for line in open(G + 'graph-prods-%s.jsonl' % s):
        p = json.loads(line)
        prods[p['task']].append(p)
    tasks = {}
    for line in open(G + 'graph-tasks-%s.jsonl' % s):
        t = json.loads(line)
        tasks[t['task']] = t
    rng = random.Random(0)
    per_walk_steps, per_step_pos, reached, built_n = [], [], 0, []
    path_steps, path_pos, path_reached = [], [], 0
    roots = []
    for t, row in sorted(tasks.items()):
        ps = prods.get(t, [])
        goals = row.get('goals') or []
        roots.append(sum(1 for p in ps if not p['reads']))
        for _ in range(K):
            st, ok, nb = walk(ps, goals, rng)
            per_walk_steps.append(len(st)); per_step_pos += [x['enabled'] for x in st]; reached += ok; built_n.append(nb)
        if row.get('path'):
            allowed = set(row['path']['idents'])
            for _ in range(K):
                st, ok, _ = walk(ps, goals, rng, allowed)
                path_steps.append(len(st)); path_pos += [x['enabled'] for x in st]; path_reached += ok
    res = dict(set=s, tasks=len(tasks), productions=sum(map(len, prods.values())), walks_per_task=K,
               roots_per_task=dist(roots),
               union_walk=dict(walks=len(per_walk_steps), reached_goal=reached, steps_per_walk=dist(per_walk_steps),
                               positives_per_step=dist(per_step_pos), tables_built_at_end=dist(built_n)),
               path_walk=dict(tasks_with_path=sum(1 for r in tasks.values() if r.get('path')), walks=len(path_steps), reached_goal=path_reached,
                              steps_per_walk=dist(path_steps), positives_per_step=dist(path_pos)))
    json.dump(res, open(out, 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
