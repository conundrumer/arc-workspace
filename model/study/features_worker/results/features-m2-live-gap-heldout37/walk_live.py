"""Part (b): the gold clause's bits under the live scopes where a C list form was held with its kind, with the live kit's code and settings, M2 off (control) and on.

    bash env.sh walk_live.py [--shard I/N] [--budget S] [--k K] [--only TASK:G,...] [--skip TASK:G,...] [--out FILE]

Items: for each live job, task and C form (held/<job>__<task>.json), the held-with-kind openings. A form with at most K such openings with tries above 0 has all of them walked;
one with more has K drawn with replacement, chance in proportion to the slot tries (numpy default_rng(crc32 of 'job task g')), so that sum tries * chance is estimated
by (sum of tries) * (mean chance over the draws). The opening's scope is its visit's form ids, sorted by (depth, fid) as REC/job.py:scope_of sorts them, with the live bank's texts.
The target is REC/job.py:build_target of the kit gold form on that scope. The walk is REC/job.py:measure's S walk (or_q.walk summed over orders) on the live kit
(sampler-pool-m2-48211b300, models-cf, P_DAG=1 ORDER_FREE=col,tie,key ARCLOG_IDENT_SOURCE=value ONE_REPAIR=30 CHOOSE_LIFT=0), arm off with S.STEER_DERIVED empty and arm M2 with
S.STEER_DERIVED = models-cf/m2-export.pkl.
One JSON line an opening to OUT (default walks.<I>of<N>.jsonl), streamed; openings already in any walks*.jsonl file of this folder are skipped. A form stays in one shard (shard_of_forms: by estimated seconds, largest first, to the least loaded shard). Exit 75 when the peak RSS
passes 3 GiB (run it again). --budget S stops after the opening in progress.
"""
import argparse
import glob
import json
import os
import resource
import sys
import time
import zlib

T0 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
REC = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-scope-loss-c-read-heldout37-ramp22'
KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-m2-48211b300'
RUNOUT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-pool-m2-600s/out'
JOBS = ['m2c_s0', 'm2s_s0', 'm2c_s1', 'm2s_s1']
ap = argparse.ArgumentParser()
ap.add_argument('--shard', default='0/1')
ap.add_argument('--budget', type=float, default=None)
ap.add_argument('--k', type=int, default=6)
ap.add_argument('--only', default=None)
ap.add_argument('--skip', default='')
ap.add_argument('--out', default=None)
ARGS = ap.parse_args()
SHARD_I, SHARD_N = (int(x) for x in ARGS.shard.split('/'))
OUT = ARGS.out or '%s/walks.%dof%d.jsonl' % (HERE, SHARD_I, SHARD_N)
RSS_LIMIT = 3 * 2 ** 30

src = open(REC + '/job.py').read()
src = src[:src.rindex('\nmain()')]
for old, new in [("KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943'", 'KIT = %r' % KIT),
                 ("os.environ.update(P_DAG='1', ORDER_FREE='tie,key'", "os.environ.update(P_DAG='1', ORDER_FREE='col,tie,key'"),
                 ("live.Sampler(KIT + '/models-tk')", "live.Sampler(KIT + '/models-cf')")]:
    assert src.count(old) == 1, old
    src = src.replace(old, new)
os.environ['STEER_DERIVED'] = 'm2-export.pkl'
sys.argv = ['job.py']
ns = dict(__name__='jobmod', __file__=REC + '/job.py')
exec(compile(src, REC + '/job.py', 'exec'), ns)
or_q, live, D, P = ns['or_q'], ns['live'], ns['D'], ns['P']
S = live.S
assert S.__file__.startswith(KIT), S.__file__
print('ORDER_FREE', S.ORDER_FREE, 'models', ns['sampler'].__dict__.get('models_dir', ''), flush=True)
M2PATH = S.STEER_DERIVED
assert M2PATH.endswith('models-cf/m2-export.pkl'), M2PATH
compact = ns['compact']
_relations = ns['relations']
MEMO = {}


def relations_memo(texts, sess, d):
    """REC/job.py:relations, kept by the texts and the session (the gold lines of a task are replayed once)."""
    k = (tuple(texts), id(sess))
    if k not in MEMO:
        if len(MEMO) > 200:
            MEMO.clear()
        MEMO[k] = _relations(texts, sess, d)
    return MEMO[k]


ns['relations'] = relations_memo


class LiveCtx:
    def __init__(self, job, task):
        self.lines = [l for l in ns['pe'][task].strip().split('\n') if not l.startswith('(OUT')]
        self.heads = [l.split()[1] for l in self.lines]
        self.bank = P.load_bank('%s/%s/%s/work/%s.out.jsonl.bank' % (RUNOUT, job, task, task))
        self.pports = ns['reader_ports'](self.lines, [f.text for f in self.bank['forms'].values()])


CTX = {}
SESS = {}


def ctx_of(job, task):
    if CTX.get('key') != (job, task):
        CTX.clear()
        CTX.update(key=(job, task), ctx=LiveCtx(job, task))
    return CTX['ctx']


def items():
    import numpy as np
    out = []
    tasks = json.load(open(KIT + '/refit-tasks.json'))['heldout37']
    for job in JOBS:
        for task in tasks:
            r = json.load(open('%s/held/%s__%s.json' % (HERE, job, task)))
            for f in r['forms']:
                ops = [x for x in f['hk'] if x['tries'] > 0]
                if not ops:
                    continue
                tot = sum(x['tries'] for x in ops)
                if len(ops) <= ARGS.k:
                    pick = [(x, 1) for x in ops]
                    mode = 'all'
                else:
                    rng = np.random.default_rng(zlib.crc32(('%s %s %d' % (job, task, f['g'])).encode()))
                    idx = rng.choice(len(ops), size=ARGS.k, replace=True, p=[x['tries'] / tot for x in ops])
                    cnt = {}
                    for i in idx:
                        cnt[int(i)] = cnt.get(int(i), 0) + 1
                    pick = [(ops[i], c) for i, c in sorted(cnt.items())]
                    mode = 'pps'
                for x, c in pick:
                    out.append(dict(job=job, task=task, g=f['g'], kind=f['kind'], i=x['i'], fids=x['fids'], tries=x['tries'], draws=c, mode=mode, n_hk=len(ops), tries_hk=tot, k=ARGS.k))
    return out


def walk_one(it):
    c = ctx_of(it['job'], it['task'])
    g = it['g']
    kind = c.lines[g].split()[0][1:]
    fs = c.bank['forms']
    fids = sorted(it['fids'], key=lambda f: (fs[f].depth, f))
    scope = [fs[f].text for f in fids]
    if SESS.get('task') != it['task']:
        SESS.clear()
        SESS.update(task=it['task'], got=D.session_of(it['task']))
    sess, d, _ = SESS['got']
    bt = ns['build_target'](c, g, kind, scope, sess, d)
    row = dict(it, fids=None, scope_n=len(scope), status=bt['status'], target=bt.get('target'), how=bt['how'], absent=bt['absent'])
    if bt['status'] != 'mapped':
        return row
    row['S'], row['wall_arm'] = {}, {}
    for arm, path in (('off', ''), ('M2', M2PATH)):
        a = time.time()
        S.STEER_DERIVED = path
        st0 = dict(S.DERIVED_STATS)
        try:
            w = or_q.walk(ns['sampler'], it['task'], it['job'], [g, 0], scope, bt['target'], sess, d, kind)
        finally:
            S.STEER_DERIVED = M2PATH
        rc = compact(w)
        rc.pop('atoms', None)
        rc.pop('detail', None)
        rc['derived_calls'] = S.DERIVED_STATS['calls'] - st0.get('calls', 0)
        row['S'][arm] = rc
        row['wall_arm'][arm] = round(time.time() - a, 2)
    return row


SLOW = {('dd6b8c4b', 14): 30.0}  # seconds an opening (two arms), from the offline read's rate; others about 2 s


def shard_of_forms(its):
    """{(task, g): shard}: forms by estimated seconds, largest first, each to the shard with the least seconds so far."""
    cost = {}
    for it in its:
        k = (it['task'], it['g'])
        cost[k] = cost.get(k, 0.0) + SLOW.get(k, 2.0)
    load, out = [0.0] * SHARD_N, {}
    for k in sorted(cost, key=lambda k: (-cost[k], k)):
        s = min(range(SHARD_N), key=lambda s: (load[s], s))
        out[k] = s
        load[s] += cost[k]
    return out


def main():
    skip = {(x.split(':')[0], int(x.split(':')[1])) for x in ARGS.skip.split(',') if x}
    allit = [it for it in items() if (it['task'], it['g']) not in skip]
    sh = shard_of_forms(allit)
    allit = [it for it in allit if sh[(it['task'], it['g'])] == SHARD_I]
    if ARGS.only:
        sel = {(x.split(':')[0], int(x.split(':')[1])) for x in ARGS.only.split(',')}
        allit = [it for it in allit if (it['task'], it['g']) in sel]
    done = set()
    for path in sorted(set(glob.glob(HERE + '/walks*.jsonl')) | {OUT}):  # an opening walked in any walks file is done, whatever shard wrote it
        if not os.path.exists(path):
            continue
        for l in open(path):
            try:
                y = json.loads(l)
            except ValueError:
                continue
            done.add((y['job'], y['task'], y['g'], y['i']))
    todo = [it for it in allit if (it['job'], it['task'], it['g'], it['i']) not in done]
    print('shard %d/%d: %d openings, %d done, %d todo -> %s' % (SHARD_I, SHARD_N, len(allit), len(allit) - len(todo), len(todo), OUT), flush=True)
    n = 0
    for it in todo:
        if ARGS.budget is not None and time.time() - T0 > ARGS.budget:
            break
        t1 = time.time()
        try:
            row = walk_one(it)
        except Exception as e:  # noqa: BLE001
            row = dict(it, fids=None, status='error', error='%s: %s' % (type(e).__name__, str(e)[:300]))
        row['wall'] = round(time.time() - t1, 2)
        row['rss_gib'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 30, 3)
        with open(OUT, 'a') as fh:
            fh.write(json.dumps(row, default=str) + '\n')
        n += 1
        el = time.time() - T0
        print('%s %s g%d i%d %s off %s M2 %s %.1fs | %.2f /min, ETA %s' % (it['job'], it['task'], it['g'], it['i'], row['status'], ((row.get('S') or {}).get('off') or {}).get('total'),
              ((row.get('S') or {}).get('M2') or {}).get('total'), row['wall'], n / el * 60, '%.0f s' % ((len(todo) - n) * el / n) if len(todo) > n else 'done'), flush=True)
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > RSS_LIMIT:
            print('RSS passed 3 GiB: run it again', flush=True)
            sys.exit(75)
    print('done %d todo %d, %.1fs' % (len(allit) - len(todo) + n, len(todo) - n, time.time() - T0), flush=True)


main()
