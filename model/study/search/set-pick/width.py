"""Scope width in forms (the picks' forms with their ancestors, as superdag.Pool.scope makes it, cap 96) of the recorded, shipped and joint picks
of the replay (same Gumbel draws as replay.jsonl). Also checks the recorded picks' width against the matched visit's forms. One line per job in width.jsonl. Resumable.
  python -I width.py [BUDGET_SECONDS]      python -I width.py report
"""
import bisect, collections, json, os, sys, time, zlib
sys.dont_write_bytecode = True
HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/set-pick'
sys.path.insert(0, HERE)
import numpy as np
import picks as P
SW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker'
sys.path[:0] = [SW + '/refit-tools', SW]
import search_node_score_parity as PA
RUN = SW + '/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out'
CACHE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/r1-forms/cache'
KIT = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/refit/out-r1'
OUT = HERE + '/width.jsonl'
ARMS = ['bundle_s0', 'bundle_s1', 'refit_s0', 'refit_s1']
CAP = 96


def width(picked, node_form, parents):
    seen = set()
    for n in picked:
        if n >= len(node_form):
            continue
        got, todo = set(), [node_form[n]]
        while todo:
            f = todo.pop()
            if f not in got and f not in seen:
                got.add(f)
                todo += parents[f]
        if len(seen) + len(got) <= CAP:
            seen |= got
    return seen


def job(arm, task, model, lineage):
    r = json.load(open('%s/%s__%s.json' % (CACHE, arm, task)))
    rec = json.load(open('%s/prep/r1__%s__%s.json' % (HERE, arm, task)))
    b = PA.load_bank('%s/%s/%s/work/%s.out.jsonl.bank' % (RUN, arm, task, task))
    node_form = [b['nodes'][i].form for i in range(len(b['nodes']))]
    parents = {f: list(b['forms'][f].parents) for f in b['forms']}
    pool = P.Pool(rec, model)
    N = rec['n']
    lin = {e['proc']: e for e in lineage}
    last1 = lineage[-1]['nodes1'] if lineage else 0
    ops = sorted(r['openings'], key=lambda o: o['time'])
    nr = sorted([v for v in r['visits'] if not v['resume']], key=lambda v: v['time'])
    vt = [v['time'] for v in nr]
    rng = np.random.default_rng(zlib.crc32(('%s %s' % (arm, task)).encode()))
    t = collections.Counter()
    for i, o in enumerate(ops):
        if not o['picks']:
            continue
        uses = np.zeros(N)
        for p in ops:
            if p['time'] >= o['time']:
                break
            if (p['proc'] == o['proc'] and p['seq'] < o['seq']) or (p['proc'] != o['proc'] and p['kept']):
                for x in p['picks']:
                    if x < N:
                        uses[x] += 1
        cap = N if o['kept'] else min(N, lin[o['proc']]['nodes1'] if o['proc'] in lin else last1)
        n = min(o['n'], cap)
        k = len(o['picks'])
        g = P.gumbel(rng, n)
        sp = P.policy_pick(pool.ship, uses, g, n, k)
        if pool.refit is not None:
            P.policy_pick(pool.refit, uses, g, n, k)
        jp = {}
        for bt in (0.25, 0.5, 1, None):
            jp[bt] = P.joint_pick(pool, uses, g, n, k, bt)
        t['openings'] += 1
        t['w_ship'] += len(width(sp, node_form, parents))
        t['w_joint'] += len(width(jp[0.5], node_form, parents))
        t['shapes_ship'] += len({int(pool.shape_ids[x]) for x in sp})
        t['shapes_joint'] += len({int(pool.shape_ids[x]) for x in jp[0.5]})
        if o['kept'] and all(x < N for x in o['picks']):
            hi = ops[i + 1]['time'] if i + 1 < len(ops) else float('inf')
            j = bisect.bisect_right(vt, o['time'])
            if j < len(nr) and vt[j] < hi:
                t['checked'] += 1
                t['w_rec'] += len(width(o['picks'], node_form, parents))
                t['w_visit'] += len(nr[j]['fids'])
                t['equal'] += width(o['picks'], node_form, parents) == set(nr[j]['fids'])
    return dict(arm=arm, task=task, **t)


def report():
    agg = collections.defaultdict(collections.Counter)
    for l in open(OUT):
        r = json.loads(l)
        agg[r['arm']].update({k: v for k, v in r.items() if k not in ('arm', 'task')})
    for a, v in sorted(agg.items()):
        print(a, 'openings', v['openings'], 'forms per scope: ship %.2f joint %.2f' % (v['w_ship'] / v['openings'], v['w_joint'] / v['openings']),
              'shapes per scope: ship %.2f joint %.2f' % (v['shapes_ship'] / v['openings'], v['shapes_joint'] / v['openings']),
              '| check: %d openings, recorded %.2f visit %.2f, equal %.3f' % (v['checked'], v['w_rec'] / max(v['checked'], 1), v['w_visit'] / max(v['checked'], 1), v['equal'] / max(v['checked'], 1)))


def main():
    if sys.argv[1:] == ['report']:
        return report()
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 15
    t0 = time.time()
    model = P.Model()
    lineage = json.load(open(HERE + '/prep/lineage.json'))
    have = {(json.loads(l)['arm'], json.loads(l)['task']) for l in open(OUT)} if os.path.exists(OUT) else set()
    todo = [(a, t) for a in ARMS for t in json.load(open(KIT + '/refit-tasks.json'))['heldout37'] if (a, t) not in have]
    n = 0
    with open(OUT, 'a') as f:
        for a, t in todo:
            if time.time() - t0 > budget:
                break
            f.write(json.dumps(job(a, t, model, lineage[a + '__' + t])) + '\n')
            f.flush()
            n += 1
    print('wrote', n, 'left', len(todo) - n, 'seconds %.1f' % (time.time() - t0))


main()
