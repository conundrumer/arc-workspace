"""Replays the openings of the round 1 jobs on the 37 with each pick, and counts exposure. One line per job in replay.jsonl. Resumable.
  python -I replay.py [BUDGET_SECONDS]      python -I replay.py report
At each opening with picks: the pool is the bank's nodes born before it (ids below the policy's node count, and below the bank's saved nodes of that process);
the uses are those of the job's own earlier picks that the policy held (kept picks of earlier processes, and the process's own earlier picks);
the scope size is the size of the recorded pick. Every replayed pick uses the same Gumbel draws at an opening.
Exposure: as read.md: the picked nodes hold, for each read of a gold form still uncovered, a kept covering node whose cover time is before the opening.
"""
import collections, json, os, sys, time, zlib
sys.dont_write_bytecode = True
HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/set-pick'
sys.path.insert(0, HERE)
import numpy as np
import picks as P
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/refit-tools')
import search_node_score_read as R

CACHE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/r1-forms/cache'
KIT = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/refit/out-r1'
DRAWS = int(os.environ.get('REPLAY_DRAWS', 0))  # >0: that many Gumbel draws per opening, picks ship, refit and joint at BETA only (draw spread check)
IDENT = os.environ.get('REPLAY_IDENT') == '1'  # also count openings that expose an Ident-only gold form (gold-ident-only-refit.json)
OUT = HERE + ('/replay-draws.jsonl' if DRAWS else '/replay-ident.jsonl' if IDENT else '/replay.jsonl')
IDO = {t: set(v['ident_only']) for t, v in json.load(open(KIT + '/gold-ident-only-refit.json')).items()}
ARMS = ['bundle_s0', 'bundle_s1', 'refit_s0', 'refit_s1']
BETA = 0.5  # chosen on the N600 cross-fit (tune-cross.jsonl) before this replay
BETAS = [0.25, 0.5, 1, None]


def job(arm, task, model, gold, lineage):
    r = json.load(open('%s/%s__%s.json' % (CACHE, arm, task)))
    rec = json.load(open('%s/prep/r1__%s__%s.json' % (HERE, arm, task)))
    pool = P.Pool(rec, model)
    N = rec['n']
    info = gold[task]
    reads = info['reads']
    lin = {e['proc']: e for e in lineage}
    last1 = lineage[-1]['nodes1'] if lineage else 0
    first = {}
    kc = collections.defaultdict(list)
    for c in r['covers']:
        first[c['gold']] = min(first.get(c['gold'], float('inf')), c['time'])
        if c['kept']:
            kc[c['gold']].append((c['time'], c['node']))
    gs = [g for g, rd in enumerate(reads) if rd and all(kc[q] for q in rd)]
    ops = sorted(r['openings'], key=lambda o: o['time'])
    rng = np.random.default_rng(zlib.crc32(('%s %s%s' % (arm, task, ' draws' if DRAWS else '')).encode()))  # REPLAY_IDENT keeps the draws of replay.jsonl
    tot = collections.defaultdict(collections.Counter)

    def hits(picked, t):
        ps = set(picked)
        return [g for g in gs if first.get(g, float('inf')) >= t and all(any(a < t and n in ps for a, n in kc[q]) for q in reads[g])]
    for o in ops:
        if not o['picks']:
            continue
        uses = np.zeros(N)
        for p in ops:
            if p['time'] >= o['time']:
                break
            if (p['proc'] == o['proc'] and p['seq'] < o['seq']) or (p['proc'] != o['proc'] and p['kept']):
                for i in p['picks']:
                    if i < N:
                        uses[i] += 1
        cap = N if o['kept'] else min(N, lin[o['proc']]['nodes1'] if o['proc'] in lin else last1)
        n = min(o['n'], cap)
        k = len(o['picks'])
        got = dict(rec=o['picks'])
        if DRAWS:
            for d in range(DRAWS):
                g = P.gumbel(rng, n)
                got['ship_d%d' % d] = P.policy_pick(pool.ship, uses, g, n, k)
                if pool.refit is not None:
                    got['refit_d%d' % d] = P.policy_pick(pool.refit, uses, g, n, k)
                got['joint_%s_d%d' % (BETA, d)] = P.joint_pick(pool, uses, g, n, k, BETA)
        else:
            g = P.gumbel(rng, n)
            got['ship'] = P.policy_pick(pool.ship, uses, g, n, k)
            if pool.refit is not None:
                got['refit'] = P.policy_pick(pool.refit, uses, g, n, k)
            for b in BETAS:
                got['joint_%s' % b] = P.joint_pick(pool, uses, g, n, k, b)
        for coin in ('all', o['score'] or 'ship'):
            t = tot[coin]
            t['openings'] += 1
            for name, pk in got.items():
                h = hits(pk, o['time'])
                t[name] += bool(h)
                t[name + '_2read'] += any(len(reads[x]) >= 2 for x in h)
                t[name + '_forms'] += len(h)
                if IDENT:
                    t[name + '_ident'] += any(x in IDO.get(task, ()) for x in h)
    return dict(arm=arm, task=task, tot={c: dict(v) for c, v in tot.items()})


def report():
    rows = [json.loads(l) for l in open(OUT)]
    agg = collections.defaultdict(collections.Counter)
    for r in rows:
        for c, v in r['tot'].items():
            agg[r['arm'], c].update(v)
    names = ['rec', 'ship', 'refit'] + ['joint_%s' % b for b in BETAS]
    print('jobs', len(rows))
    for (arm, coin), v in sorted(agg.items()):
        o = v['openings']
        print('%-10s %-6s openings %5d  ' % (arm, coin, o) + '  '.join('%s %.1f%% (2+ %.1f%%)' % (nm, 100 * v[nm] / o, 100 * v[nm + '_2read'] / o) for nm in names if nm in v))


def main():
    if sys.argv[1:] == ['report']:
        return report()
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 15
    t0 = time.time()
    model = P.Model()
    gold = {x['task']: R.gold_info(x['gold_sexp']) for x in json.load(open(KIT + '/points-eval.json'))}
    lineage = json.load(open(HERE + '/prep/lineage.json'))
    have = {(json.loads(l)['arm'], json.loads(l)['task']) for l in open(OUT)} if os.path.exists(OUT) else set()
    todo = [(a, t) for a in ARMS for t in json.load(open(KIT + '/refit-tasks.json'))['heldout37'] if (a, t) not in have]
    n = 0
    with open(OUT, 'a') as f:
        for a, t in todo:
            if time.time() - t0 > budget:
                break
            f.write(json.dumps(job(a, t, model, gold, lineage[a + '__' + t])) + '\n')
            f.flush()
            n += 1
    print('wrote', n, 'left', len(todo) - n, 'seconds %.1f' % (time.time() - t0))


main()
