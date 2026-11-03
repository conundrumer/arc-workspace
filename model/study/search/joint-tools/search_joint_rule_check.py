"""Check of the live joint rule against the replay: the same picks on the recorded pools of round 1.

  <python> -I search_joint_rule_check.py RULE_FILE [OPENINGS_PER_JOB] [JOB ...]

RULE_FILE   scope/joint.py of the kit.
JOB         arm/task of a round 1 job, for example bundle_s0/135a2760. Default: three bundle jobs.
At evenly spaced recorded openings of each job the check makes the pool, the uses and the scope size as set-pick/replay.py does, and gives the rule and the replay's
joint pick the same random.Random state. The replay's Gumbel draws are the draws of that Random, in the order of the pool's node ids.
Per opening it compares: the picks, the uses after the rule, and the Random state after the rule. Then it runs the rule on a pool whose nodes fail,
and expects no picks, one count of the fallback counter, and no change of the uses.
Prints the counts. Exit status 0 where all openings agree and the fallback test passes, else 2.
"""
import collections
import importlib.util
import json
import os
import random
import sys
import time
import zlib

import numpy as np

sys.dont_write_bytecode = True
SETPICK = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/set-pick'
CACHE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/r1-forms/cache'
SW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker'
RUN = SW + '/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out'
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SETPICK)
import picks as P  # noqa: E402  (the replay's picks and model)
sys.path.insert(0, TOOLS)
import search_node_score_parity as PA  # noqa: E402

DEFAULT_JOBS = ['bundle_s0/135a2760', 'bundle_s1/16b78196', 'bundle_s0/b6f77b65']


class Adapter:
    """Gives the replay's gumbel() the draws of a random.Random: random(n) is n calls of random()."""

    def __init__(self, rng):
        self.rng = rng

    def random(self, n):
        return np.array([self.rng.random() for _ in range(n)])


class FakePolicy:
    def __init__(self, n, score, uses):
        self.ids = list(range(n))
        self.score = {i: float(score[i]) for i in range(n)}
        self.uses = {i: float(uses[i]) for i in range(n)}


class FakePool:
    def __init__(self, policy, nodes, forms):
        self.policy, self.nodes, self.forms, self.c = policy, nodes, forms, collections.Counter()


def load_rule(path):
    spec = importlib.util.spec_from_file_location('scope_rule', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def uses_at(ops, o, N):
    """The uses before opening o: the picks of earlier kept openings of other processes, and of earlier openings of o's own process."""
    uses = np.zeros(N)
    for p in ops:
        if p['time'] >= o['time']:
            break
        if (p['proc'] == o['proc'] and p['seq'] < o['seq']) or (p['proc'] != o['proc'] and p['kept']):
            for i in p['picks']:
                if i < N:
                    uses[i] += 1
    return uses


def check_job(rule, model, job, count, lineage):
    arm, task = job.split('/')
    r = json.load(open('%s/%s__%s.json' % (CACHE, arm, task)))
    rec = json.load(open('%s/prep/r1__%s__%s.json' % (SETPICK, arm, task)))
    bank = PA.load_bank('%s/%s/%s/work/%s.out.jsonl.bank' % (RUN, arm, task, task))
    ref_pool = P.Pool(rec, model)
    N = rec['n']
    lin = {e['proc']: e for e in lineage[arm + '__' + task]}
    last1 = lineage[arm + '__' + task][-1]['nodes1'] if lineage[arm + '__' + task] else 0
    ops = sorted(r['openings'], key=lambda o: o['time'])
    with_picks = [o for o in ops if o['picks']]
    chosen = sorted({int(x) for x in np.linspace(0, len(with_picks) - 1, count)})
    out = collections.Counter()
    for idx in chosen:
        o = with_picks[idx]
        uses = uses_at(ops, o, N)
        cap = N if o['kept'] else min(N, lin[o['proc']]['nodes1'] if o['proc'] in lin else last1)
        n = min(o['n'], cap)
        k = len(o['picks'])
        seed = zlib.crc32(('%s %d' % (job, idx)).encode())
        a, b = random.Random(seed), random.Random(seed)
        fp = FakePool(FakePolicy(n, rec['ship'], uses), bank['nodes'], bank['forms'])
        t0 = time.perf_counter()
        live = rule.picks(fp, k, a)
        out['rule microseconds'] += int(1e6 * (time.perf_counter() - t0))
        g = P.gumbel(Adapter(b), n)
        ref = P.joint_pick(ref_pool, uses, g, n, k, 0.5)
        out['openings'] += 1
        out['picks differ'] += live != ref
        want = {i: float(uses[i]) + (i in set(ref)) for i in range(n)}
        out['uses differ'] += fp.policy.uses != want
        out['rng state differs'] += a.getstate() != b.getstate()
        out['fallbacks'] += fp.c[rule.FALLBACK]
        out['rule picks counted'] += fp.c[rule.PICKED]
        out['picks per opening'] += len(ref)
    return out


def fallback_test(rule):
    """A pool whose nodes raise: the rule gives None, counts one fallback, and leaves the uses as they were."""
    class Bad:
        def __getitem__(self, i):
            raise KeyError(i)
    fp = FakePool(FakePolicy(8, [0.1 * i for i in range(8)], [0] * 8), Bad(), Bad())
    got = rule.picks(fp, 6, random.Random(1))
    return got is None and fp.c[rule.FALLBACK] == 1 and all(v == 0 for v in fp.policy.uses.values())


def main():
    rule = load_rule(sys.argv[1])
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 70
    jobs = sys.argv[3:] or DEFAULT_JOBS
    model = P.Model(SETPICK + '/model.json')
    lineage = json.load(open(SETPICK + '/prep/lineage.json'))
    total = collections.Counter()
    for job in jobs:
        got = check_job(rule, model, job, count, lineage)
        total.update(got)
        print('%-22s %s' % (job, dict(got)), flush=True)
    ok_fb = fallback_test(rule)
    print('total %s' % dict(total))
    print('fallback test %s' % ('pass' if ok_fb else 'FAIL'))
    bad = total['picks differ'] + total['uses differ'] + total['rng state differs'] + total['fallbacks']
    print('rule time per opening: %.2f ms' % (total['rule microseconds'] / 1000 / max(total['openings'], 1)))
    print('openings %d, differences %d (picks %d, uses %d, rng state %d), fallbacks %d' % (
        total['openings'], bad, total['picks differ'], total['uses differ'], total['rng state differs'], total['fallbacks']))
    return 0 if total['openings'] >= 200 and not bad and ok_fb else 2


if __name__ == '__main__':
    sys.exit(main())
