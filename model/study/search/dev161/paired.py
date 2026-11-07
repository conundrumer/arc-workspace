"""paired.py RUN_A ARM_A RUN_B ARM_B [--kinds]: an ARM may be ARM@SEED. table recall by dependency depth of two arms of dev_run.py, paired by task: over the whole budget and at k, each task's smaller count of draws. Depths are the union graph's, 0, 1, 2-3 and 4+. It also prints the draws per task, and the tasks where arm A is above, below or equal to arm B at k, over depth 1 and deeper. With --kinds, the rows are non-DET and DET tables in place of depths, and the tasks above, below and equal are by non-DET tables at k, as the pass rule of work/measures.md reads them in tables.

Tables are named from the draw records (reach.py --by tables). Only tasks that both arms finished and the out-of-scope list leaves in count."""
import collections, json, math, statistics as st, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import draw_file  # noqa: E402
import reach as R

U = R.DATA / 'gold/gold-union-exp46'
SKIP = {json.loads(l)['task'] for l in open(R.OUT_OF_SCOPE)}
KINDS = '--kinds' in sys.argv
DEPTH = collections.defaultdict(dict)
KIND = {}
for r in map(json.loads, open(U / 'graph-tables-dev.jsonl')):
    if r['table'].startswith('t') and r.get('kind') != 'DEMONSTRATED':
        DEPTH[r['task']][r['table']] = r['depth']
        KIND[(r['task'], r['table'])] = 'DET' if r.get('kind') in ('DET', 'RIGID_DET') else 'non-DET'
BANDS = ('non-DET', 'DET') if KINDS else ('0', '1', '2-3', '4+')


def band(d):
    return '0' if d == 0 else '1' if d == 1 else '2-3' if d <= 3 else '4+'


def first_draws(job):
    """{graph table: the draw that first gave it}, and the count of draws."""
    outputs, entries, order = [], [], []
    for d in draw_file.draws(job):
        if 'steps' not in d:
            continue
        q = d['steps'][-1]['query_hash']
        order.append(q)
        for o in d.get('tables') or ():
            outputs.append((q, o['name']))
            for row in o['at']:
                entries.append((q, o['name'], list(zip(o['dets'], row[:-1])), row[-1]))
    of_q = collections.defaultdict(set)
    for (q, _), g in R.graph_names(outputs, entries).items():
        of_q[q].add(g)
    first = {}
    for i, q in enumerate(order):
        for g in of_q.get(q, ()):
            first.setdefault(g, i)
    return first, len(order)


def jobs(run, arm):
    """{task: (job folder, draws)} of an arm, written ARM or ARM@SEED for one seed of a run with several."""
    arm, _, seed = arm.partition('@')
    return {r['task']: (Path(run) / 'jobs' / r['job'], r['draws']) for r in map(json.loads, open(Path(run) / 'results.jsonl')) if r['arm'] == arm and (not seed or int(r['seed']) == int(seed))}


def main():
    run_a, arm_a, run_b, arm_b = [x for x in sys.argv[1:] if x != '--kinds'][:4]
    a, b = jobs(run_a, arm_a), jobs(run_b, arm_b)
    tasks = sorted(t for t in set(a) & set(b) if t not in SKIP and t in DEPTH)
    tot, whole_a, whole_b, at_k_a, at_k_b = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    diffs = collections.defaultdict(list)
    wins = losses = ties = 0
    draws_a, draws_b = [], []
    for t in tasks:
        fa, na = first_draws(a[t][0])
        fb, nb = first_draws(b[t][0])
        draws_a.append(na); draws_b.append(nb)
        k = min(na, nb)
        here = collections.Counter()
        for g, d in DEPTH[t].items():
            x = KIND[(t, g)] if KINDS else band(d)
            tot[x] += 1
            ia, ib = fa.get(g), fb.get(g)
            whole_a[x] += ia is not None
            whole_b[x] += ib is not None
            ka, kb = ia is not None and ia < k, ib is not None and ib < k
            at_k_a[x] += ka
            at_k_b[x] += kb
            here[x] += int(ia is not None) - int(ib is not None)
            if (x == 'non-DET') if KINDS else d >= 1:
                here['k'] += int(ka) - int(kb)
        for x in BANDS:
            diffs[x].append(here[x])
        wins += here['k'] > 0; losses += here['k'] < 0; ties += here['k'] == 0
    print('%d tasks paired, %s of %s less %s of %s' % (len(tasks), arm_a, Path(run_a).name, arm_b, Path(run_b).name))
    if not tasks:
        return
    print('draws per task: median %d against %d, mean %.0f against %.0f' % (st.median(draws_a), st.median(draws_b), st.mean(draws_a), st.mean(draws_b)))
    for x in BANDS:
        d = diffs[x]
        print('%-13s tables %5d  budget %4d against %4d (%+d, bound %.1f)  at k %4d against %4d' % (x if KINDS else 'depth ' + x, tot[x], whole_a[x], whole_b[x], sum(d), 1.96 * math.sqrt(sum(v * v for v in d)), at_k_a[x], at_k_b[x]))
    print('tasks at k over %s: %d above, %d below, %d equal' % ('non-DET tables' if KINDS else 'depth 1 and deeper', wins, losses, ties))


if __name__ == '__main__':
    main()
