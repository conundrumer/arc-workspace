"""Spread and missing counts of the candidate strata variables, over facts.jsonl. Prints to stdout."""
import collections, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
TF = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-task-facts/task-facts.jsonl'
rows = [json.loads(l) for l in open(HERE + '/facts.jsonl')]


def src(r):
    s = r['source']
    if 'arc-agi-2/evaluation' in s:
        return 'agi2-eval'
    if 'arc-agi-2/training' in s:
        return 'agi2-train'
    return 'other:' + ','.join(s)


def status(r):
    if 'goal_depth' in r:
        return 'graph'
    if 'g_error' in r:
        return 'err:' + r['g_error']
    return 'no-row' + ('(gold)' if 'cases' in r else '(no-gold)')


print('sources', collections.Counter(src(r) for r in rows))
print('source x status')
for k, v in sorted(collections.Counter((src(r), status(r)) for r in rows).items()):
    print('  ', k, v)
for h in ('r22', 'h37', 'h99'):
    print(h, 'status', sorted(collections.Counter(status(r) for r in rows if r[h]).items()), 'source', sorted(collections.Counter(src(r) for r in rows if r[h]).items()))
held = [r['task'] for r in rows if r['r22'] or r['h37'] or r['h99']]
print('held union', len(held))


def quant(xs):
    xs = sorted(xs)
    n = len(xs)
    return 'n=%d min=%s q10=%s q25=%s q50=%s q75=%s q90=%s max=%s' % (n, xs[0], xs[n // 10], xs[n // 4], xs[n // 2], xs[3 * n // 4], xs[9 * n // 10], xs[-1])


for k in ('goal_depth', 'goal_depth_cases', 'fewest_productions', 'g_tables', 'g_productions', 'g_goal_options', 'cases', 'distinct_programs',
          'train_pairs', 'test_cases', 'input_cells_median', 'output_cells_median', 'output_size_equals_input'):
    xs = [r[k] for r in rows if r.get(k) is not None]
    print(k, quant(xs), 'missing=%d' % (len(rows) - len(xs)))
    if k in ('goal_depth', 'fewest_productions', 'cases', 'train_pairs', 'output_size_equals_input', 'g_goal_options'):
        print('   counts', sorted(collections.Counter(xs).items()))
# grid fact check against gold-task-facts
tf = {json.loads(l)['task']: json.loads(l) for l in open(TF)}
bad = collections.Counter()
for r in rows:
    f = tf.get(r['task'])
    if not f:
        continue
    for k in ('train_pairs', 'test_cases', 'input_cells_median', 'output_cells_median', 'output_size_equals_input'):
        if float(f[k]) != float(r[k]):
            bad[k] += 1
print('grid facts vs task-facts.jsonl: tasks compared', sum(r['task'] in tf for r in rows), 'differences', dict(bad))
# correlations among graph variables (Spearman by ranks)


def ranks(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i])
    rk = [0.0] * len(xs)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and xs[o[j + 1]] == xs[o[i]]:
            j += 1
        for k in range(i, j + 1):
            rk[o[k]] = (i + j) / 2
        i = j + 1
    return rk


def spear(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    c = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return c / (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5


g = [r for r in rows if 'goal_depth' in r and r.get('cases') is not None and r.get('fewest_productions') is not None]
V = ['goal_depth', 'fewest_productions', 'g_tables', 'g_productions', 'cases', 'train_pairs', 'input_cells_median', 'output_cells_median', 'output_size_equals_input']
print('spearman over %d graph tasks' % len(g))
for i, a in enumerate(V):
    print('  %-24s' % a, ' '.join('%5.2f' % spear([r[a] for r in g], [r[b] for r in g]) for b in V))
