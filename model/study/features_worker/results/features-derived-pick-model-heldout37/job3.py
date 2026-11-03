"""S, the gold clause's bits under the recorded scope (or_q.walk, summed over orders, as REC/job.py walks it), with the relation steer as the kit has it (off) and with the derived pick
model in its place (M1, M2). design.md, "The read".

    bash REC/env.sh ../features-derived-pick-model-heldout37/job3.py --set C|covered [--shard I/N] [--budget S] [--only TASK:G,...] [--check-regroup] [--order-checks N] [--fit DIR] [--out FILE]

Forms: the rows of REC/forms.<i>of2.jsonl (C) or REC/forms-covered.<i>of2.jsonl (covered) with status mapped and S valid. A task stays in one shard (crc32 of the task). One JSON line a form to
X/walks-<set>.<I>of<N>.jsonl, streamed; forms already there are skipped. It exits 75 when the peak RSS passes 3 GiB (run it again); --budget S stops after the form in progress.
Per form: S_rec (recorded), S: {arm: compact walk record}, ro: {arm: {bits, picks}} (the relation-pick bits at rel_off picks, weighted by the order shares of that arm's walk), switch picks.
--check-regroup: the first 10 forms of the set also run arm G (M1's lines with s = log(ws * rf)); read3.py compares G with REC/split-steer S_on.
--order-checks N: on the first N forms of this run that have an exact order sum of 2 or more orders and a fast M1 walk, M1 is walked again on the last order's text (check 4).
"""
import argparse
import itertools
import json
import math
import os
import resource
import sys
import time
import zlib

T0 = time.time()
X = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37'
REC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22'
ap = argparse.ArgumentParser()
ap.add_argument('--set', required=True, choices=['C', 'covered'])
ap.add_argument('--shard', default='0/1')
ap.add_argument('--budget', type=float, default=None)
ap.add_argument('--only', default=None)
ap.add_argument('--check-regroup', action='store_true')
ap.add_argument('--order-checks', type=int, default=0)
ap.add_argument('--fit', default=None, help='the model dir (default X/fit; with --cal X/fit-cal)')
ap.add_argument('--out', default=None)
ap.add_argument('--cal', action='store_true', help='the calibrated model X/fit-cal (no build-order facts; gate temperature and bias) and the output dir X/m2cal')
ap.add_argument('--outdir', default=None, help='the output dir (default X; with --cal X/m2cal)')
ap.add_argument('--arms', default='off,M1,M2', help='comma list of arms to walk: off, M1, M2, M2s (M2 only where the steer acts)')
ap.add_argument('--skip', default='', help='forms to leave out, TASK:G,TASK:G (the slow f560132c:10)')
ap.add_argument('--reuse-off', default=None, help='a walks file of an earlier run: a form found there takes its off arm from it (same code, same recorded scope) instead of a walk')
ARGS = ap.parse_args()
SHARD_I, SHARD_N = (int(x) for x in ARGS.shard.split('/'))
FIT = ARGS.fit or (X + '/fit-cal' if ARGS.cal else X + '/fit')
OUTDIR = ARGS.outdir or (X + '/m2cal' if ARGS.cal else X)
OUT = ARGS.out or '%s/walks-%s.%dof%d.jsonl' % (OUTDIR, ARGS.set, SHARD_I, SHARD_N)
ARMS = ARGS.arms.split(',')
assert set(ARMS) <= {'off', 'M1', 'M2', 'M2s'} and 'off' in ARMS, ARMS
os.makedirs(os.path.dirname(OUT), exist_ok=True)
RSS_LIMIT = 3 * 2 ** 30

sys.path.insert(0, X)
src = open(REC + '/job.py').read()
src = src[:src.rindex('\nmain()')]
sys.argv = ['job.py'] + (['--covered'] if ARGS.set == 'covered' else [])
ns = dict(__name__='jobmod', __file__=REC + '/job.py')
exec(compile(src, REC + '/job.py', 'exec'), ns)
or_q, live = ns['or_q'], ns['live']
S = live.S
M = S.M
import feats  # noqa: E402
import hook  # noqa: E402

ENV = dict(D=ns['D'], live=live, sampler=ns['sampler'], col_sigs=ns['col_sigs'])
MEMO = {}


def relations_x(texts, sess, d):
    k = tuple(texts)
    if k not in MEMO:
        if len(MEMO) > 400:
            MEMO.clear()
        MEMO[k] = feats.replay(texts, sess, d, ENV)
    return MEMO[k]


ns['relations'] = lambda texts, sess, d: {k: v for k, v in relations_x(texts, sess, d).items() if not v['no_table']}
MODEL = hook.Model(FIT)

SW = dict(arm='off', log=None, call=-1, scope=None, valid=None, got=None, stats=None)
_drawer = or_q.GuidedRun.drawer


def drawer(self, pg, kind, dec, place=None, prior=None):
    dr = _drawer(self, pg, kind, dec, place, prior)
    dr._pg, dr._kind = pg, kind
    return dr


or_q.GuidedRun.drawer = drawer
_rf = S.Drawer.rel_factors


def rel_factors(self, fr, n, popts, k, scope_types, key, rel, joined, leaf):
    got = _rf(self, fr, n, popts, k, scope_types, key, rel, joined, leaf)
    if SW['arm'] == 'off':
        return got
    self._pend_rf = list(got)
    return [1.0] * len(got)


S.Drawer.rel_factors = rel_factors
_pc = or_q.GuidedDrawer.pick_complete


def pick_complete(self, n, opts, weights, key, alt=None):
    rf = getattr(self, '_pend_rf', None)
    arm, st = SW['arm'], SW['stats']
    if rf is not None:
        self._pend_rf = None
        assert n.phase in ('root', 'root2') and len(rf) == len(opts), (n.phase, len(rf), len(opts))
        KIND = self.fr.KIND
        is_d = [KIND[o] == 'relation' and self.rel_name(o) == 'declared' for o in opts]
        st['picks'] += 1
        st['non_declared'] += sum(1 for o in opts if KIND[o] == 'relation') - sum(is_d)
        if arm == 'G':
            e = [weights[i] * rf[i] if is_d[i] else 0.0 for i in range(len(opts))]
            ea = [alt[i] * rf[i] if is_d[i] else 0.0 for i in range(len(opts))] if alt is not None else None
            sigma = 0.0
        else:
            pst, d_idx, bases, facts, gf = hook.pick_facts(self, n, opts, weights, SW['scope'], st['miss']) if not (arm == 'M2s' and self.rel_off) else (None, [], [], [], None)
            e, ea, sigma = [0.0] * len(opts), None, 0.0
            if d_idx:
                s = MODEL.scores(facts)
                mx = float(s.max())
                ex = [math.exp(float(x) - mx) for x in s]
                for i, v in zip(d_idx, ex):
                    e[i] = v
                if arm in ('M2', 'M2s'):
                    sigma = MODEL.sigma(gf, s)
                if alt is not None:
                    ea = [e[i] if alt[i] > 0 else 0.0 for i in range(len(opts))]
                    st['alt_extra'] += sum(1 for i in range(len(opts)) if is_d[i] and alt[i] > 0 and weights[i] <= 0)
        if any(abs(x - 1.0) > 0 for x in rf):
            st['regrouped'] += 1
        if arm == 'M2s' and self.rel_off:
            assert all(x == 1.0 for x in rf)  # the kit's factors are 1 at rel_off picks: P's weights stay (M2s acts where today's steer acts)
        else:
            an = 'M1' if arm == 'G' else 'M2' if arm == 'M2s' else arm
            weights = hook.arm_weights(an, weights, rf, is_d, e, sigma)
            if alt is not None:
                alt = hook.arm_weights(an, alt, rf, is_d, ea, sigma)
    o, q = _pc(self, n, opts, weights, key, alt)
    if SW['log'] is not None and n.phase in ('root', 'root2') and o is not None:
        SW['log'].append((SW['call'], bool(self.rel_off), -math.log2(q) if q and q > 0 else math.inf))
    return o, q


or_q.GuidedDrawer.pick_complete = pick_complete
_wo = or_q.walk_order


def walk_order(*a, **k):
    SW['call'] += 1
    return _wo(*a, **k)


or_q.walk_order = walk_order
_so = or_q.O.sum_orders


def sum_orders(form, walk, *a, **k):
    def w2(text):
        res = walk(text)
        res['_call'] = SW['call']
        return res
    got = _so(form, w2, *a, **k)
    SW['valid'] = [(r['_call'], r['bits']) for _, r in got['walks'] if r['bits'] is not None]
    SW['written'] = (got['written'].get('_call'), got['written']['bits'])
    SW['got'] = got
    return got


or_q.O.sum_orders = sum_orders
compact = ns['compact']


def walk_arm(arm, item, x, target=None):
    """compact walk record of the arm, with ro: the relation-pick bits at rel_off picks, weighted by the order shares of the walk."""
    task, g = item[1], item[2]
    texts = list(x['scope'])
    srel = relations_x(texts, x['sess'], x['d'])
    SW.update(arm=arm, log=[], call=-1, valid=None, got=None, scope=feats.Scope(texts, srel), stats=dict(picks=0, regrouped=0, non_declared=0, alt_extra=0, miss=[0]))
    try:
        w = or_q.walk(ns['sampler'], task, item[0], [g, 0], x['scope'], target or x['target'], x['sess'], x['d'], x['kind'])
    finally:
        log, SW['log'] = SW['log'], None
        SW['arm'] = 'off'
    rec = compact(w)
    st = SW['stats']
    vo = SW['valid']
    if vo is None:
        vo = [(0, rec['total'])] if rec['valid'] else []
    elif not vo and not SW['got']['orders_exact'] and SW['written'][1] is not None and (w.get('orders') or {}).get('only_written'):
        vo = [SW['written']]
    ro_bits, ro_picks = 0.0, 0.0
    if vo and rec['valid']:
        low = min(b for _, b in vo)
        sh = {c: 2 ** (low - b) for c, b in vo}
        tot = sum(sh.values())
        for c, ro, bits in log:
            if ro and c in sh:
                ro_bits += sh[c] / tot * bits
                ro_picks += sh[c] / tot
    rec['pick_stats'] = dict(picks=st['picks'], regrouped=st['regrouped'], non_declared=st['non_declared'], alt_extra=st['alt_extra'], miss=st['miss'][0])
    rec['ro'] = dict(bits=round(ro_bits, 4), picks=round(ro_picks, 3))
    return rec


def main():
    files = ['%s/%s.%dof2.jsonl' % (REC, 'forms' if ARGS.set == 'C' else 'forms-covered', i) for i in range(2)]
    rows = [json.loads(l) for f in files for l in open(f)]
    rec = {(r['arm'], r['task'], r['g']): r for r in rows if r.get('status') == 'mapped' and r.get('S') and r['S'].get('valid')}
    items = {it[:3]: it for it in ns['build_items']()}
    allk = sorted(rec, key=lambda k: (k[1], k[0], k[2]))
    first10 = set(allk[:10])
    want = [k for k in allk if zlib.crc32(k[1].encode()) % SHARD_N == SHARD_I]
    if ARGS.skip:
        skip = {(x.split(':')[0], int(x.split(':')[1])) for x in ARGS.skip.split(',')}
        want = [k for k in want if (k[1], k[2]) not in skip]
    if ARGS.only:
        sel = {(x.split(':')[0], int(x.split(':')[1])) for x in ARGS.only.split(',')}
        want = [k for k in want if (k[1], k[2]) in sel]
    reuse = {}
    if ARGS.reuse_off:
        for l in open(ARGS.reuse_off) if os.path.exists(ARGS.reuse_off) else []:
            try:
                y = json.loads(l)
            except ValueError:  # a last line that is not whole (the writer is running)
                continue
            if y.get('status') == 'ok':
                reuse[(y['arm'], y['task'], y['g'])] = y
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            y = json.loads(l)
            done.add((y['arm'], y['task'], y['g']))
    todo = [k for k in want if k not in done]
    print('set %s shard %d/%d: %d forms, %d done, %d todo -> %s' % (ARGS.set, SHARD_I, SHARD_N, len(want), len(want) - len(todo), len(todo), OUT), flush=True)
    n, nchk = 0, 0
    for k in todo:
        if ARGS.budget is not None and time.time() - T0 > ARGS.budget:
            break
        t1 = time.time()
        r = rec[k]
        out = dict(arm=k[0], task=k[1], g=k[2], set=ARGS.set, S_rec=r['S']['total'], DB=(r.get('DB') or {}).get('bits'), DB_status=(r.get('DB') or {}).get('status'), S={}, wall_arm={})
        try:
            row, x = ns['prepare'](items[k])
            assert row['status'] == 'mapped' and row['target'] == r['target'], (row['status'], row['target'], r['target'])
            arms = ARMS + (['G'] if ARGS.check_regroup and k in first10 else [])
            for arm in arms:
                a = time.time()
                if arm == 'off' and k in reuse and reuse[k]['S'].get('off'):
                    out['S'][arm], out['reused_off'] = reuse[k]['S']['off'], True
                    out['wall_arm'][arm] = 0.0
                    continue
                out['S'][arm] = walk_arm(arm, items[k], x)
                out['wall_arm'][arm] = round(time.time() - a, 2)
            m1 = out['S'].get('M1') or {}
            if nchk < ARGS.order_checks and m1.get('valid') and (m1.get('orders') or {}).get('exact') and (m1['orders'].get('valid') or 0) >= 2 and out['wall_arm']['M1'] < 5:
                form = ns['O'].Form(x['target'])
                last = form.text(list(itertools.islice(form.orders(), or_q.ORDER_CAP))[-1])
                w = walk_arm('M1', items[k], x, target=last)
                out['order_check'] = dict(M1=m1['total'], M1_last_order=w['total'], text_differs=last != x['target'])
                nchk += 1
            out['status'] = 'ok'
        except Exception as e:  # noqa: BLE001
            out.update(status='error', error='%s: %s' % (type(e).__name__, str(e)[:300]))
        out['wall'] = round(time.time() - t1, 2)
        out['rss_gib'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 30, 3)
        with open(OUT, 'a') as fh:
            fh.write(json.dumps(out, default=str) + '\n')
        n += 1
        el = time.time() - T0
        print('%s %s g%d %s rec %s %s %.1fs | %.2f forms/min, ETA %s' % (
            k[0], k[1], k[2], out['status'], out['S_rec'], ' '.join('%s %s' % (a, (v or {}).get('total')) for a, v in out['S'].items()), out['wall'], n / el * 60,
            '%.0f s' % ((len(todo) - n) * el / n) if len(todo) > n else 'done'), flush=True)
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > RSS_LIMIT:
            print('RSS passed 3 GiB: run it again', flush=True)
            sys.exit(75)
    print('done %d todo %d, %.1fs' % (len(want) - len(todo) + n, len(todo) - n, time.time() - T0), flush=True)


main()
