"""Chooses beta of the joint pick on the 50 N600 training tasks (the fit's own tasks; no held-out task). One line per job in tune.jsonl. Resumable.
  python -I tune.py [BUDGET_SECONDS]      python -I tune.py report
Openings: OPENINGS draws spread evenly over the run, from the first draw with K nodes born. The pool at a draw is the nodes born before it.
Uses come from a run of the shipped pick over these openings; every pick is read at the same uses and the same Gumbel draws.
Exposure as in read.md, with N600's covering nodes (tables equal to a gold table) and cover draws (node age).
"""
import collections, json, os, sys, time
sys.dont_write_bytecode = True
HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/set-pick'
sys.path.insert(0, HERE)
import numpy as np
import picks as P

SIG = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/gold-sig-n600.jsonl'
CROSS = os.environ.get('TUNE_CROSS') == '1'  # each task scored by the fold model that left it out
OUT = HERE + ('/tune-cross.jsonl' if CROSS else '/tune.jsonl')
K, OPENINGS = 6, 120
BETAS = [0.25, 0.5, 1, 2, 4, None]


def exposed(picked, d, reads, kc, first, gs):
    ps = set(picked)
    hit = [g for g in gs if first.get(g, 1 << 60) >= d and all(any(a < d and n in ps for a, n in kc[q]) for q in reads[g])]
    return hit


def job(t, model, reads):
    rec = json.load(open('%s/prep/n600__nodes_s0__%s.json' % (HERE, t)))
    pool = P.Pool(rec, model)
    age = np.array(rec['age'])
    kc = collections.defaultdict(list)
    first = {}
    for c in rec['covers']:
        kc[c['gold']].append((c['draw'], c['node']))
        first[c['gold']] = min(first.get(c['gold'], 1 << 60), c['draw'])
    gs = [g for g, rd in enumerate(reads) if rd and all(kc[q] for q in rd)]
    d0 = int(np.sort(age)[K - 1]) + 1 if len(age) >= K else rec['draws']
    rng = np.random.default_rng(int(t, 16))
    uses = np.zeros(rec['n'])
    tot = collections.Counter()
    for d in np.linspace(d0, rec['draws'], OPENINGS).astype(int):
        n = int((age < d).sum())
        g = P.gumbel(rng, n)
        sp = P.policy_pick(pool.ship, uses, g, n, K)
        tot['openings'] += 1
        h = exposed(sp, d, reads, kc, first, gs)
        tot['ship'] += bool(h)
        tot['ship_1read'] += any(len(reads[x]) == 1 for x in h)
        tot['ship_2read'] += any(len(reads[x]) >= 2 for x in h)
        for b in BETAS:
            jp = P.joint_pick(pool, uses, g, n, K, b)
            h = exposed(jp, d, reads, kc, first, gs)
            tot['joint_%s' % b] += bool(h)
            tot['joint_%s_1read' % b] += any(len(reads[x]) == 1 for x in h)
            tot['joint_%s_2read' % b] += any(len(reads[x]) >= 2 for x in h)
        for i in sp:
            uses[i] += 1
    return dict(task=t, **tot)


def report():
    rows = [json.loads(l) for l in open(OUT)]
    s = collections.Counter()
    for r in rows:
        s.update({k: v for k, v in r.items() if k != 'task'})
    o = s['openings']
    print('jobs', len(rows), 'openings', o)
    for k in ['ship'] + ['joint_%s' % b for b in BETAS]:
        print('%-12s exposure %.3f   1-read %.3f   2+read %.3f' % (k, s[k] / o, s[k + '_1read'] / o, s[k + '_2read'] / o))


def main():
    if sys.argv[1:] == ['report']:
        return report()
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 15
    t0 = time.time()
    model = P.Model()
    models = [P.Model(HERE + '/model-f%d.json' % k) for k in range(5)] if CROSS else None
    reads = {json.loads(l)['task']: json.loads(l)['reads'] for l in open(SIG)}
    have = {json.loads(l)['task'] for l in open(OUT)} if os.path.exists(OUT) else set()
    todo = [t for t in sorted(reads) if t not in have]
    n = 0
    with open(OUT, 'a') as f:
        for t in todo:
            if time.time() - t0 > budget:
                break
            m = models[sorted(reads).index(t) % 5] if CROSS else model
            f.write(json.dumps(job(t, m, reads[t])) + '\n')
            f.flush()
            n += 1
    print('wrote', n, 'left', len(todo) - n, 'seconds %.1f' % (time.time() - t0))


main()
