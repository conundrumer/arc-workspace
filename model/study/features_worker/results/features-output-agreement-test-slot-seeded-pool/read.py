"""Paired read of agreement.jsonl: per task, mean form agreement of gold and of nodes; bootstrap over tasks."""
import json, random, sys, os
H = os.path.dirname(os.path.abspath(__file__)); rows = [json.loads(l) for l in open(f'{H}/agreement.jsonl')]
ok = [r for r in rows if 'error' not in r]; bad = [r for r in rows if 'error' in r]
both = [r for r in ok if r['gold'] and r['node']]
m = lambda d: sum(d.values()) / len(d)
g = [m(r['gold']) for r in both]; n = [m(r['node']) for r in both]; dif = [a - b for a, b in zip(g, n)]
mean = lambda x: sum(x) / len(x)
rng = random.Random(0); boot = sorted(mean(rng.choices(dif, k=len(dif))) for _ in range(10000))
print('tasks', len(rows), 'errors', len(bad), 'with both', len(both))
print('gold', round(mean(g), 3), 'node', round(mean(n), 3), 'diff', round(mean(dif), 3), 'ci', round(boot[250], 3), round(boot[9750], 3))
print('tasks gold above node', sum(d > 0 for d in dif), 'below', sum(d < 0 for d in dif), 'equal', sum(d == 0 for d in dif))
# precision of agreement: the share of forms that are gold among agreeing and among not agreeing forms, equal weight per task
ag, no = [], []
for r in both:
    v = [(1, x) for x in r['gold'].values()] + [(0, x) for x in r['node'].values()]
    a = [g for g, x in v if x == 1]; b = [g for g, x in v if x < 1]
    if a and b: ag.append(mean(a)); no.append(mean(b))
print('share gold among forms fully agreed', round(mean(ag), 3), 'among others', round(mean(no), 3), 'tasks', len(ag))
print('errors', [(r['task'], r['error'][:80]) for r in bad][:8])
